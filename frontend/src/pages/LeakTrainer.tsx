import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import confetti from "canvas-confetti";
import { ArrowRight, CheckCircle2, Loader2, RefreshCw, XCircle, Target, Maximize2, Minimize2, LayoutGrid, Flag, RotateCw, Trophy, Flame, Home } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { RangePanel } from "@/components/replayer/RangePanel";
import { useTableOrientation } from "@/hooks/use-table-orientation";
import { useIsLandscapeMobile } from "@/hooks/use-is-landscape-mobile";
import { leaktrainer } from "@/lib/api";
import type { LeakTrainerSpot, LeakTrainerGrade, LeakTrainerState, ReplayStep } from "@/lib/api";
import { cn } from "@/lib/utils";

type Phase = "intro" | "loading" | "question" | "feedback" | "error" | "empty" | "summary";

const LESSON_SIZE = 10;   // lição fechada: N spots, depois fim automático com veredito
type SessionStat = { label: string; hits: number; misses: number };

const ORDER = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];
const STATE_KEY = "leaklab_leaktrainer_state";

const FREQ_LABEL: Record<string, string> = { raise: "raise", call: "call", allin: "all-in", fold: "fold" };
const FREQ_COLOR: Record<string, string> = {
  raise: "bg-emerald-500", call: "bg-sky-500", allin: "bg-violet-500", fold: "bg-muted-foreground/40",
};

/** Postflop (Fase 2): mesa HU BB vs BTN com board + c-bet do vilão. */
function buildPostflopStep(sp: LeakTrainerSpot, bb: number) {
  const heroPos = sp.position, vsPos = sp.vs_position;
  const heroIdx = ORDER.indexOf(heroPos), vsIdx = ORDER.indexOf(vsPos);
  const stackChips = Math.round((sp.stack_bb || 40) * bb);
  const seats: Record<string, { player: string; stack: number; pos: string }> = {};
  const bets: Record<string, number> = {};
  const folded: string[] = [];
  ORDER.forEach((pos, i) => {
    const sn = String(i + 1);
    const isHero = pos === heroPos;
    seats[sn] = { player: isHero ? "Hero" : pos, stack: stackChips, pos };
    if (pos !== heroPos && pos !== vsPos) folded.push(isHero ? "Hero" : pos);
  });
  if (vsIdx >= 0) bets[String(vsIdx + 1)] = Math.round((sp.facing_size_bb || 1.65) * bb);  // c-bet
  const potChips = Math.round((sp.pot_bb || 5) * bb);   // pote já construído no preflop
  const step = {
    type: "action", street: sp.street || "flop", seats, bets, folded,
    pot_bb: potChips / bb, pot: potChips, bb,
    button: ORDER.indexOf("BTN") + 1, board: sp.board || [],
    player: "Hero", seat: heroIdx + 1, is_hero: true,
  } as unknown as ReplayStep;
  const heroCards = sp.hero_cards.map((c) => `${c.rank}${c.suit}`);
  return { step, heroCards, bb };
}

/** Monta um ReplayStep 9-max sintético a partir do spot (mesma lógica do academy preflop). */
function buildStep(sp: LeakTrainerSpot) {
  const bb = 100;
  if (sp.kind === "postflop") return buildPostflopStep(sp, bb);
  const heroPos = sp.position, vsPos = sp.vs_position, scen = sp.scenario;
  const heroIdx = ORDER.indexOf(heroPos);
  const vsIdx = vsPos ? ORDER.indexOf(vsPos) : -1;
  const stackChips = Math.round((sp.stack_bb || 50) * bb);

  const seats: Record<string, { player: string; stack: number; pos: string }> = {};
  const bets: Record<string, number> = {};
  const folded: string[] = [];

  ORDER.forEach((pos, i) => {
    const sn = String(i + 1);
    const isHero = pos === heroPos;
    seats[sn] = { player: isHero ? "Hero" : pos, stack: stackChips, pos };
    if (pos === "SB") bets[sn] = Math.round(bb * 0.5);
    else if (pos === "BB") bets[sn] = bb;
    let isFolded = false;
    if (scen === "rfi") isFolded = i < heroIdx;
    else if (scen === "vs_rfi") isFolded = i < heroIdx && pos !== vsPos;
    else isFolded = !isHero && pos !== vsPos;
    if (isFolded) folded.push(isHero ? "Hero" : pos);
  });

  if (scen === "vs_rfi" && vsIdx >= 0) {
    bets[String(vsIdx + 1)] = Math.round((sp.facing_size || 2.2) * bb);
  } else if (scen === "vs_3bet") {
    if (heroIdx >= 0) bets[String(heroIdx + 1)] = Math.round(2.2 * bb);
    if (vsIdx >= 0) bets[String(vsIdx + 1)] = Math.round((sp.facing_size || 8) * bb);
  }

  const potChips = Object.values(bets).reduce((a, b) => a + b, 0);
  const step = {
    type: "action", street: "preflop", seats, bets, folded,
    pot_bb: potChips / bb, pot: potChips, bb,
    button: ORDER.indexOf("BTN") + 1, board: [],
    player: "Hero", seat: heroIdx + 1, is_hero: true,
    preflop_gto: { available: false, scenario: scen, vs_position: vsPos || null },
  } as unknown as ReplayStep;

  const heroCards = sp.hero_cards.map((c) => `${c.rank}${c.suit}`);
  return { step, heroCards, bb };
}

function loadState(): LeakTrainerState {
  try { return JSON.parse(localStorage.getItem(STATE_KEY) || "{}"); } catch { return {}; }
}

const _TIER_META: Record<string, { label: string; ring: string; text: string; glow: string }> = {
  bronze:  { label: "Bronze",   ring: "#b08d57", text: "text-[#d9a86a]", glow: "shadow-[0_0_24px_rgba(176,141,87,0.35)]" },
  silver:  { label: "Prata",    ring: "#c8d0d8", text: "text-slate-200",  glow: "shadow-[0_0_24px_rgba(200,208,216,0.35)]" },
  gold:    { label: "Ouro",     ring: "#f5c542", text: "text-amber-300",  glow: "shadow-[0_0_28px_rgba(245,197,66,0.45)]" },
  diamond: { label: "Diamante", ring: "#5ad1ff", text: "text-cyan-300",   glow: "shadow-[0_0_30px_rgba(90,209,255,0.5)]" },
};

export default function LeakTrainer() {
  const { t } = useTranslation("academy");
  const navigate = useNavigate();

  const [phase, setPhase]               = useState<Phase>("intro");
  const [spot, setSpot]                 = useState<LeakTrainerSpot | null>(null);
  const [grade, setGrade]               = useState<LeakTrainerGrade | null>(null);
  const [selected, setSelected]         = useState<string | null>(null);
  const [submitting, setSubmitting]     = useState(false);
  const [streak, setStreak]             = useState(0);
  const [totalDone, setTotalDone]       = useState(0);
  const [totalCorrect, setTotalCorrect] = useState(0);
  const [xpEarned, setXpEarned]         = useState(0);
  // Domínio por categoria nesta sessão (antes→depois) — eixo de treino, p/ o veredito da lição.
  const [masteryByCat, setMasteryByCat] = useState<Record<string, { start: number; now: number; tier: string }>>({});
  const [unlockedAch, setUnlockedAch]   = useState<string[]>([]);   // conquistas de treino da sessão
  const [sessionStats, setSessionStats] = useState<Record<string, SessionStat>>({});
  const [showRange, setShowRange]       = useState(false);
  const stateRef = useRef<LeakTrainerState>(loadState());
  const rootRef = useRef<HTMLDivElement>(null);
  const [isFull, setIsFull] = useState(false);

  const toggleFull = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else rootRef.current?.requestFullscreen?.().catch(() => {});
  };
  useEffect(() => {
    const onFs = () => setIsFull(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);
  const canFull = typeof document !== "undefined" && !!document.documentElement.requestFullscreen;

  // mesmo padrão do Replayer: celular deitado = tela cheia imersiva; em pé = pedir pra girar.
  const { t: tr } = useTranslation("replayer");        // chaves de rotação reusadas do Replayer
  const tableOrientation = useTableOrientation();
  const landscapeMobile = useIsLandscapeMobile();
  const isStandalone = typeof window !== "undefined" &&
    (window.matchMedia?.("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true);
  const goImmersive = async () => {
    try {
      await rootRef.current?.requestFullscreen?.();
      await (screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> })?.lock?.("landscape");
    } catch { /* iOS / sem API de orientação — a dica de PWA cobre */ }
  };

  // rótulo humano da categoria de leak (cenário + posições)
  const labelFor = (sp: LeakTrainerSpot) =>
    sp.kind === "postflop" ? t("leakTrainer.cat.postflopBb", { pos: sp.position, vs: sp.vs_position })
    : sp.scenario === "rfi" ? t("leakTrainer.cat.rfi", { pos: sp.position })
    : sp.scenario === "vs_rfi" ? t("leakTrainer.cat.vsRfi", { pos: sp.position, vs: sp.vs_position })
    : t("leakTrainer.cat.vs3bet", { pos: sp.position, vs: sp.vs_position });

  const finishSession = () => setPhase("summary");
  const newSession = () => {
    setSessionStats({}); setTotalDone(0); setTotalCorrect(0); setStreak(0); setXpEarned(0);
    setMasteryByCat({}); setUnlockedAch([]);
    setPhase("intro");   // nova lição começa pela tela de início
  };

  const loadNext = useCallback(async () => {
    setPhase("loading"); setSelected(null); setGrade(null); setShowRange(false);
    try {
      const timeout = new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), 12000));
      const r = await Promise.race([leaktrainer.next(stateRef.current), timeout]);
      if (!r.spot) { setPhase("empty"); return; }
      setSpot(r.spot);
      setPhase("question");
    } catch { setPhase("error"); }
  }, []);

  // Não auto-inicia: a lição começa pela tela de "intro" (botão Começar → loadNext).
  const lessonComplete = totalDone >= LESSON_SIZE;
  const nextOrFinish = () => { if (totalDone >= LESSON_SIZE) setPhase("summary"); else loadNext(); };

  const submit = async (action: string) => {
    if (!spot || phase !== "question" || submitting) return;
    setSelected(action); setSubmitting(true);
    try {
      const g = await leaktrainer.grade(spot, action);
      setGrade(g);
      setTotalDone((n) => n + 1);
      setXpEarned((x) => x + (g.xp_awarded || 0));
      // stats DESTA sessão por categoria (pro recap), separado da adaptação persistida
      const lbl = labelFor(spot);
      setSessionStats((s) => {
        const c = s[spot.category] || { label: lbl, hits: 0, misses: 0 };
        return { ...s, [spot.category]: { label: lbl, hits: c.hits + (g.is_correct ? 1 : 0), misses: c.misses + (g.is_correct ? 0 : 1) } };
      });
      // atualiza o estado da sessão por categoria (adaptação) + persiste
      const st = stateRef.current;
      const cur = st[spot.category] || { hits: 0, misses: 0, seen: 0 };
      st[spot.category] = {
        hits: cur.hits + (g.is_correct ? 1 : 0),
        misses: cur.misses + (g.is_correct ? 0 : 1),
        seen: cur.seen + 1,
      };
      try { localStorage.setItem(STATE_KEY, JSON.stringify(st)); } catch { /* quota */ }
      // domínio da categoria (antes→depois) p/ o veredito da lição — eixo de treino
      if (g.training) {
        const tg = g.training;
        setMasteryByCat((m) => ({
          ...m,
          [spot.category]: { start: m[spot.category]?.start ?? tg.mastery_prev, now: tg.mastery, tier: tg.tier },
        }));
      }
      if (g.training_achievements?.length) {
        const got = g.training_achievements;
        setUnlockedAch((prev) => Array.from(new Set([...prev, ...got])));
      }
      if (g.is_correct) { setStreak((s) => s + 1); setTotalCorrect((n) => n + 1); }
      else setStreak(0);
      setPhase("feedback");
    } catch { setPhase("error"); }
    finally { setSubmitting(false); }
  };

  // Atalhos de teclado (drill rápido p/ grinder): F/C/R respondem; 1..3 = opções na ordem; Enter/Espaço
  // = próximo spot; G abre a tabela de ranges. Não dispara com modificadores.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (phase === "question" && spot && !submitting) {
        const byLetter: Record<string, string> = { f: "fold", c: "call", r: "raise" };
        const a = byLetter[k] || (/^[1-9]$/.test(k) ? spot.options[parseInt(k, 10) - 1] : undefined);
        if (k === "g") { e.preventDefault(); setShowRange((v) => !v); return; }
        if (a && spot.options.includes(a)) { e.preventDefault(); submit(a); }
      } else if (phase === "feedback") {
        if (e.key === "Enter" || e.key === " " || k === "n") { e.preventDefault(); nextOrFinish(); }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, spot, submitting, loadNext]);

  const accuracy = totalDone > 0 ? Math.round((totalCorrect / totalDone) * 100) : null;
  const table = spot ? buildStep(spot) : null;

  const catLabel = spot ? labelFor(spot) : "";

  // recap: melhor categoria (mais acertos) e a mais difícil (mais erros) desta sessão
  const statList = Object.values(sessionStats);
  const bestCat = statList.filter((s) => s.hits > 0).sort((a, b) => b.hits - a.hits)[0];
  const toughCat = statList.filter((s) => s.misses > 0).sort((a, b) => b.misses - a.misses)[0];
  // categoria PRINCIPAL da lição (mais tentativas) + seu domínio antes→depois (eixo de treino)
  const primaryCatKey = Object.entries(sessionStats)
    .sort((a, b) => (b[1].hits + b[1].misses) - (a[1].hits + a[1].misses))[0]?.[0];
  const primaryMastery = primaryCatKey ? masteryByCat[primaryCatKey] : undefined;
  const primaryLabel = primaryCatKey ? sessionStats[primaryCatKey]?.label : undefined;

  // comemoração estilo Duolingo ao concluir a lição (confete; mais forte se foi bem)
  useEffect(() => {
    if (phase !== "summary" || totalDone === 0) return;
    const acc = Math.round((totalCorrect / Math.max(1, totalDone)) * 100);
    const colors = ["#2DD4BF", "#f5c542", "#5ad1ff", "#E3E8EC"];
    const burst = (particleCount: number, spread: number, y: number) =>
      confetti({ particleCount, spread, startVelocity: 38, origin: { y }, colors, scalar: 0.9, disableForReducedMotion: true });
    burst(acc >= 80 ? 150 : 80, 70, 0.5);
    if (acc >= 80) setTimeout(() => burst(60, 110, 0.55), 220);
  }, [phase, totalDone, totalCorrect]);

  // rótulo da ação (raise muda por cenário: 3-Bet vs 4-Bet)
  const actLabel = (a: string) => {
    if (a === "raise") return spot?.kind === "postflop" ? t("leakTrainer.act.raisePost") : spot?.scenario === "vs_3bet" ? t("leakTrainer.act.raise4") : spot?.scenario === "vs_rfi" ? t("leakTrainer.act.raise3") : t("leakTrainer.act.raiseOpen");
    return t(`leakTrainer.act.${a}`, a);
  };

  const freqEntries = grade
    ? Object.entries(grade.hand_freq || {}).filter(([, v]) => v && v > 0.01).sort((a, b) => b[1] - a[1])
    : [];
  const verdictKind = grade ? (grade.gto_tier === "error" ? "error" : grade.mixed ? "mixed" : "correct") : null;

  // Veredito (cabeçalho + barras + Próximo) — markup ÚNICO reusado no aside (desktop) e no bottom-sheet (mobile).
  const verdictCard = grade && verdictKind ? (
    <>
      <div className={cn(
        "rounded-xl border p-4 space-y-3",
        verdictKind === "correct" ? "border-emerald-500/30 bg-emerald-500/5"
          : verdictKind === "mixed" ? "border-sky-500/30 bg-sky-500/5"
          : "border-amber-500/30 bg-amber-500/5",
      )}>
        <div className="flex items-center gap-2">
          {verdictKind === "error"
            ? <XCircle className="size-5 text-amber-400 shrink-0" aria-hidden />
            : <CheckCircle2 className={cn("size-5 shrink-0", verdictKind === "mixed" ? "text-sky-400" : "text-emerald-400")} aria-hidden />}
          <span className={cn("font-mono text-xs font-bold uppercase tracking-wider",
            verdictKind === "correct" ? "text-emerald-400" : verdictKind === "mixed" ? "text-sky-400" : "text-amber-400")}>
            {verdictKind === "correct" ? t("leakTrainer.vCorrect") : verdictKind === "mixed" ? t("leakTrainer.vMixed") : t("leakTrainer.vError")}
          </span>
          {grade.xp_awarded > 0 && (
            <span className="ml-auto font-mono text-[10px] text-emerald-400">+{grade.xp_awarded} XP</span>
          )}
        </div>
        {freqEntries.length > 0 && (
          <>
            <p className="font-mono text-[10px] text-muted-foreground">{t("leakTrainer.gtoPlays", { hand: spot?.hand })}</p>
            <div className="space-y-1.5">
              {freqEntries.map(([act, freq]) => (
                <div key={act} className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-muted-foreground w-10 shrink-0">{FREQ_LABEL[act] ?? act}</span>
                  <div className="relative flex-1 h-1.5 rounded-full bg-border overflow-hidden">
                    <div className={cn("h-full rounded-full", FREQ_COLOR[act] ?? "bg-primary")} style={{ width: `${Math.min(100, freq * 100)}%` }} />
                  </div>
                  <span className="font-mono text-[10px] font-bold tabular-nums w-8 text-right text-foreground">{Math.round(freq * 100)}%</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
      <button onClick={nextOrFinish} className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400">
        <ArrowRight className="size-4" aria-hidden /> {lessonComplete ? t("leakTrainer.lesson.seeResult") : t("leakTrainer.next")}
        <kbd className="hidden rounded border border-black/20 bg-black/10 px-1.5 py-0.5 text-[9px] font-normal md:inline-block">Enter</kbd>
      </button>
    </>
  ) : null;

  // ── CELULAR DEITADO: tela cheia imersiva (mesa preenche, botões/veredito flutuam) ──
  if (landscapeMobile && (phase === "question" || phase === "feedback") && spot && table) {
    return (
      <div ref={rootRef} className="h-dvh relative overflow-hidden hud-scanline"
        style={{ background: "radial-gradient(ellipse at 50% 45%, #14223a 0%, #080f1c 100%)" }}>
        <div className="absolute inset-0 flex items-center justify-center p-0.5">
          <div className="h-full w-auto max-w-full mx-auto" style={{ aspectRatio: "1160 / 710" }}>
            <PokerTableV3 step={table.step} hero="Hero" heroCards={table.heroCards} bb={table.bb} betUnit="bb" orientation="landscape" fill />
          </div>
        </div>
        {/* topo-esquerda: categoria treinada */}
        <div className="absolute top-[calc(0.4rem+env(safe-area-inset-top))] left-[calc(0.5rem+env(safe-area-inset-left))] z-30 flex items-center gap-1.5 rounded-full bg-background/70 px-3 py-1.5 ring-1 ring-amber-500/30 backdrop-blur">
          <Target className="size-3 text-amber-400" aria-hidden />
          <span className="font-mono text-[10px] font-bold text-foreground">{catLabel}</span>
          <span className="font-mono text-[9px] text-muted-foreground">{spot.stack_bb}bb</span>
        </div>
        {/* topo-direita: stats + ranges, e o Finalizar como pílula âmbar separada (claramente um botão) */}
        <div className="absolute top-[calc(0.4rem+env(safe-area-inset-top))] right-[calc(0.5rem+env(safe-area-inset-right))] z-30 flex items-center gap-2">
          <div className="flex items-center gap-2.5 rounded-full bg-background/70 px-3 py-1.5 font-mono text-[10px] tabular-nums ring-1 ring-border backdrop-blur">
            {totalDone > 0 && (<>
              <span className="text-foreground">{totalDone}/{LESSON_SIZE}</span>
              <span className={accuracy !== null && accuracy >= 70 ? "text-emerald-400" : "text-amber-400"}>{accuracy}%</span>
              <span className={streak >= 3 ? "text-amber-400" : "text-muted-foreground"}>{streak}🔥</span>
            </>)}
            <button onClick={() => setShowRange(true)} className="text-muted-foreground transition-colors hover:text-amber-400"><LayoutGrid className="size-3.5" aria-hidden /></button>
          </div>
          {totalDone > 0 && (
            <button onClick={finishSession}
              className="flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-400 ring-1 ring-amber-500/40 backdrop-blur transition-colors hover:bg-amber-500/25">
              <Flag className="size-3" aria-hidden /> {t("leakTrainer.finish")}
            </button>
          )}
        </div>
        {/* botões fold/call/raise — flutuando na base do feltro (safe-area) */}
        {phase === "question" && (
          <div className="absolute bottom-[calc(0.6rem+env(safe-area-inset-bottom))] left-1/2 z-30 flex -translate-x-1/2 items-center gap-2">
            {spot.options.map((a) => (
              <button key={a} onClick={() => submit(a)} disabled={submitting}
                className="min-w-[68px] rounded-full bg-background/85 px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground shadow-lg ring-1 ring-border backdrop-blur transition-all active:scale-95 hover:text-amber-400 hover:ring-amber-500/60 disabled:opacity-40">
                {actLabel(a)}
              </button>
            ))}
          </div>
        )}
        {/* veredito — bottom-sheet deslizante */}
        {phase === "feedback" && verdictCard && (
          <div className="absolute inset-x-0 bottom-0 z-40 animate-fade-in">
            <div className="mx-auto max-w-lg space-y-3 rounded-t-2xl border-t border-border bg-background/95 p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] shadow-2xl backdrop-blur">
              {verdictCard}
            </div>
          </div>
        )}
        {/* overlay de ranges */}
        {showRange && table && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setShowRange(false)}>
            <div className="w-full max-w-lg max-h-[88vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <RangePanel step={table.step} hero="Hero" heroCards={table.heroCards} onClose={() => setShowRange(false)} />
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── CELULAR EM PÉ: a mesa só funciona deitada → pedir pra girar (mesmo padrão do Replayer) ──
  if (tableOrientation === "portrait" && (phase === "question" || phase === "feedback") && spot) {
    return (
      <div className="h-dvh flex flex-col items-center justify-center gap-5 bg-background hud-scanline px-10 text-center"
        style={{ background: "radial-gradient(ellipse at 50% 45%, #14223a 0%, #080f1c 100%)" }}>
        <RotateCw className="size-14 text-amber-400" aria-hidden />
        <p className="font-mono text-[13px] uppercase tracking-widest text-muted-foreground leading-relaxed">{tr("rotatePrompt")}</p>
        {canFull && (
          <button onClick={goImmersive}
            className="flex items-center gap-2 rounded-full bg-amber-500 px-5 py-2.5 font-mono text-[12px] font-bold uppercase tracking-widest text-black shadow-lg transition-transform active:scale-95">
            <Maximize2 className="size-4" aria-hidden /> {tr("fullscreenRotate")}
          </button>
        )}
        {!canFull && !isStandalone && (
          <p className="max-w-[280px] rounded-xl bg-amber-500/10 px-4 py-2.5 font-mono text-[10px] leading-relaxed text-amber-400/90 ring-1 ring-amber-500/20">
            {tr("iosInstallHint")}
          </p>
        )}
      </div>
    );
  }

  return (
    <div ref={rootRef} className="h-dvh overflow-hidden bg-background hud-scanline flex flex-col">
      {!isFull && <HudHeader />}
      <main className="flex-1 min-h-0 mx-auto flex w-full max-w-[1500px] flex-col px-4 py-3 md:px-8 animate-fade-in">
        {/* header compacto + tela cheia (header grande do HudLayout causava scroll) */}
        <div className="mb-3 flex shrink-0 items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-amber-400">
              <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" aria-hidden />
              {t("leakTrainer.eyebrow")}
            </div>
            <h1 className="truncate text-lg font-semibold tracking-tight text-foreground md:text-xl">{t("leakTrainer.title")}</h1>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {totalDone > 0 && phase !== "summary" && (
              <button
                onClick={finishSession}
                className="inline-flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-amber-400 transition-colors hover:bg-amber-500/20"
              >
                <Flag className="size-3.5" aria-hidden />
                {t("leakTrainer.finish")}
              </button>
            )}
            {canFull && (
              <button
                onClick={toggleFull}
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-hud-surface px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:border-amber-500/50 hover:text-amber-400"
              >
                {isFull ? <Minimize2 className="size-3.5" aria-hidden /> : <Maximize2 className="size-3.5" aria-hidden />}
                {isFull ? t("leakTrainer.exitFull") : t("leakTrainer.fullscreen")}
              </button>
            )}
          </div>
        </div>

        <div className="flex min-h-0 flex-1 flex-col justify-center overflow-y-auto">

        {phase === "intro" && (
          <div className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/[0.08] to-transparent p-8 text-center">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-amber-500/10 ring-1 ring-amber-500/30">
              <Target className="size-7 text-amber-400" aria-hidden />
            </div>
            <div>
              <h2 className="font-heading text-xl font-bold text-foreground">{t("leakTrainer.lesson.title")}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{t("leakTrainer.lesson.desc", { count: LESSON_SIZE })}</p>
            </div>
            <button onClick={loadNext}
              className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400">
              <Target className="size-4" aria-hidden /> {t("leakTrainer.lesson.start")}
            </button>
          </div>
        )}

        {phase === "loading" && (
          <div className="flex flex-col items-center gap-4 py-16">
            <Loader2 className="size-8 animate-spin text-amber-400" aria-hidden />
            <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest">{t("loading")}</p>
          </div>
        )}

        {phase === "empty" && (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-border bg-hud-surface p-10 text-center">
            <Target className="size-10 text-muted-foreground" aria-hidden />
            <p className="text-sm text-muted-foreground max-w-md">{t("leakTrainer.empty")}</p>
          </div>
        )}

        {phase === "error" && (
          <div className="flex flex-col items-center gap-4 rounded-xl border border-destructive/30 bg-destructive/5 p-8">
            <XCircle className="size-10 text-destructive" aria-hidden />
            <p className="text-sm text-muted-foreground">{t("loadError")}</p>
            <button onClick={loadNext} className="inline-flex items-center gap-2 rounded-lg border border-border bg-hud-surface px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground hover:bg-amber-500/5 transition-colors">
              <RefreshCw className="size-3.5" aria-hidden /> {t("retry")}
            </button>
          </div>
        )}

        {phase === "summary" && (() => {
          const acc = accuracy ?? 0;
          const tier = primaryMastery?.tier ?? "bronze";
          const tm = _TIER_META[tier] ?? _TIER_META.bronze;
          const mStart = Math.round(primaryMastery?.start ?? 0);
          const mNow = Math.round(primaryMastery?.now ?? 0);
          const mGain = Math.max(0, mNow - mStart);
          return (
          <div className="mx-auto w-full max-w-md">
            <div className="relative overflow-hidden rounded-3xl border border-primary/30 bg-gradient-to-b from-primary/[0.10] via-card to-card p-7 shadow-elevated animate-in fade-in zoom-in-95 duration-300">
              {/* Header comemorativo */}
              <div className="flex flex-col items-center gap-2 text-center">
                <div className={cn("flex size-16 items-center justify-center rounded-2xl bg-primary/15 ring-1 ring-primary/40", tm.glow)}>
                  <Trophy className="size-8 text-primary" aria-hidden />
                </div>
                <h2 className="font-heading text-2xl font-bold text-foreground">{t("leakTrainer.summary.lessonDone")}</h2>
                {primaryLabel && <p className="text-sm text-muted-foreground">{primaryLabel}</p>}
              </div>

              {/* 3 stats */}
              <div className="mt-6 grid grid-cols-3 gap-2">
                {[
                  { v: String(totalDone), l: t("stats.done"), c: "text-foreground" },
                  { v: `${acc}%`, l: t("stats.accuracy"), c: acc >= 70 ? "text-emerald-400" : "text-amber-400" },
                  { v: `+${xpEarned}`, l: "XP", c: "text-primary" },
                ].map((s, i) => (
                  <div key={i} className="rounded-2xl bg-background/60 px-2 py-3 text-center ring-1 ring-border">
                    <p className={cn("font-mono text-2xl font-bold tabular-nums", s.c)}>{s.v}</p>
                    <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">{s.l}</p>
                  </div>
                ))}
              </div>

              {/* DOMÍNIO da categoria (antes→depois) — o eixo de treino, honesto */}
              {primaryMastery && (
                <div className="mt-4 space-y-2 rounded-2xl bg-background/60 p-4 ring-1 ring-border">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("leakTrainer.summary.mastery")}</span>
                    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold uppercase", tm.text)} style={{ borderColor: tm.ring }}>
                      {tm.label}
                    </span>
                  </div>
                  <div className="h-3 w-full overflow-hidden rounded-full bg-muted/30">
                    <div className="h-full rounded-full transition-[width] duration-700 ease-out" style={{ width: `${mNow}%`, backgroundColor: tm.ring }} />
                  </div>
                  <div className="flex items-center justify-between font-mono text-[11px]">
                    <span className="text-muted-foreground">{mStart}% → <span className="font-bold text-foreground">{mNow}%</span></span>
                    {mGain > 0 && <span className="font-bold text-emerald-400">+{mGain}</span>}
                  </div>
                </div>
              )}

              {/* streak + categoria mais difícil */}
              <div className="mt-4 flex items-center gap-2">
                {streak >= 1 && (
                  <div className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-amber-500/10 px-3 py-2 ring-1 ring-amber-500/25">
                    <Flame className="size-4 text-amber-400" aria-hidden />
                    <span className="font-mono text-xs font-bold text-amber-300">{streak}</span>
                  </div>
                )}
                {toughCat && (
                  <div className="min-w-0 flex-[2] rounded-xl bg-background/60 px-3 py-2 ring-1 ring-border">
                    <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">{t("leakTrainer.summary.tough")}</p>
                    <p className="truncate text-xs font-bold text-foreground">{toughCat.label}</p>
                  </div>
                )}
              </div>

              {/* Conquistas de treino desbloqueadas nesta lição */}
              {unlockedAch.length > 0 && (
                <div className="mt-4 rounded-2xl bg-amber-500/10 p-3 ring-1 ring-amber-500/30">
                  <p className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-amber-400">
                    <Trophy className="size-3.5" aria-hidden /> {t("leakTrainer.summary.unlocked")}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {unlockedAch.map((k) => (
                      <span key={k} className="inline-flex items-center gap-1 rounded-full bg-background/60 px-2.5 py-1 text-[11px] font-bold text-foreground ring-1 ring-amber-500/30">
                        <Trophy className="size-3 text-amber-400" aria-hidden /> {t(`trainAch.${k.replace(/:/g, "_")}.title`)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* CTAs: Continuar (nova lição) + Finalizar (dashboard) */}
              <div className="mt-6 space-y-2">
                <button onClick={newSession} className="w-full rounded-xl bg-primary px-4 py-3.5 font-mono text-sm font-bold uppercase tracking-widest text-primary-foreground shadow-lg transition-transform hover:bg-primary/90 active:scale-[0.98]">
                  {t("leakTrainer.summary.continue")}
                </button>
                <button onClick={() => navigate("/dashboard")} className="flex w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground">
                  <Home className="size-4" aria-hidden /> {t("leakTrainer.summary.finish")}
                </button>
              </div>

              {/* loop honesto: liga ao jogo real (sem fingir delta de ELO) */}
              <p className="mt-3 text-center text-[11px] leading-relaxed text-muted-foreground/80">{t("leakTrainer.summary.loopHint")}</p>
            </div>
          </div>
          );
        })()}

        {(phase === "question" || phase === "feedback") && spot && table && (
          <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row lg:items-stretch">

            <div className="flex min-h-0 min-w-0 flex-1 items-center justify-center">
              <div className="aspect-[16/10] h-full max-h-full w-auto max-w-full">
                <PokerTableV3 step={table.step} hero="Hero" heroCards={table.heroCards} bb={table.bb} betUnit="bb" transparentBg />
              </div>
            </div>

            <aside className="flex w-full shrink-0 flex-col gap-3 lg:min-h-0 lg:w-72 lg:overflow-y-auto">

              {totalDone > 0 && (
                <div className="flex items-center justify-around rounded-lg border border-border bg-hud-surface px-3 py-2">
                  <div className="text-center">
                    <p className="font-mono text-base font-bold tabular-nums text-foreground">{totalDone}/{LESSON_SIZE}</p>
                    <p className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">{t("stats.done")}</p>
                  </div>
                  <div className="h-6 w-px bg-border" />
                  <div className="text-center">
                    <p className={cn("font-mono text-base font-bold tabular-nums", accuracy !== null && accuracy >= 70 ? "text-emerald-400" : "text-amber-400")}>{accuracy}%</p>
                    <p className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">{t("stats.accuracy")}</p>
                  </div>
                  <div className="h-6 w-px bg-border" />
                  <div className="text-center">
                    <p className={cn("font-mono text-base font-bold tabular-nums", streak >= 3 ? "text-amber-400" : "text-foreground")}>{streak}🔥</p>
                    <p className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">{t("stats.streak")}</p>
                  </div>
                </div>
              )}

              {/* Categoria de leak treinada agora */}
              <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 space-y-1">
                <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-amber-400">
                  <Target className="size-3" aria-hidden /> {t("leakTrainer.weakSpot")}
                </span>
                <p className="text-sm font-bold text-foreground leading-snug">{catLabel}</p>
                <p className="font-mono text-[10px] text-muted-foreground">{spot.stack_bb}bb</p>
              </div>

              {/* Consultar a tabela de ranges (abertura/call/raise) do spot */}
              <button
                onClick={() => setShowRange(true)}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-3 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:border-amber-500/50 hover:text-amber-400"
              >
                <LayoutGrid className="size-3.5" aria-hidden />
                {t("gtoPreflop.showRange")}
              </button>

              {phase === "question" && (
                <div className="space-y-2">
                  <p className="font-mono text-xs uppercase tracking-wider text-amber-400">{t("leakTrainer.prompt")}</p>
                  <div className="grid grid-cols-1 gap-2">
                    {spot.options.map((a) => (
                      <button
                        key={a}
                        onClick={() => submit(a)}
                        disabled={submitting}
                        className={cn(
                          "flex min-h-[48px] items-center justify-between rounded-lg border px-4 py-3 font-mono text-sm font-bold uppercase tracking-wider transition-all active:scale-95",
                          "border-border bg-hud-surface text-foreground ring-1 ring-border hover:border-amber-500/60 hover:bg-amber-500/5 hover:text-amber-400",
                          "disabled:opacity-40 disabled:cursor-not-allowed",
                          submitting && selected === a && "border-amber-500/60 bg-amber-500/5 text-amber-400",
                        )}
                      >
                        <span>{actLabel(a)}</span>
                        {/* hint de tecla só em telas com teclado (escondido em touch/mobile) */}
                        <kbd className="hidden rounded border border-border/60 bg-background/60 px-1.5 py-0.5 font-mono text-[9px] font-normal text-muted-foreground md:inline-block">
                          {a === "fold" ? "F" : a === "call" ? "C" : "R"}
                        </kbd>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {phase === "feedback" && verdictCard && (
                <div className="flex flex-col gap-3">{verdictCard}</div>
              )}
            </aside>
          </div>
        )}
        </div>
      </main>

      {/* Overlay: tabela de ranges (abertura/call/raise) do spot */}
      {showRange && table && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setShowRange(false)}>
          <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <RangePanel step={table.step} hero="Hero" heroCards={table.heroCards} onClose={() => setShowRange(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
