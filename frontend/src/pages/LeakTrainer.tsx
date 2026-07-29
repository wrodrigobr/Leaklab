import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import confetti from "canvas-confetti";
import { ArrowRight, CheckCircle2, Loader2, RefreshCw, XCircle, Target, Maximize2, Minimize2, LayoutGrid, Flag, RotateCw, Trophy, Flame, Home, Lock } from "lucide-react";
import { HudHeader } from "@/components/hud/HudHeader";
import { RangeFamilyDrill } from "@/components/hud/RangeFamilyDrill";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { RangePanel } from "@/components/replayer/RangePanel";
import { ProLockCard } from "@/components/hud/ProLockCard";
import { MasteryGate } from "@/components/training/MasteryGate";
import { useSpotLabel } from "@/lib/spotLabel";
import { useTableOrientation } from "@/hooks/use-table-orientation";
import { useIsLandscapeMobile } from "@/hooks/use-is-landscape-mobile";
import { leaktrainer, progression } from "@/lib/api";
import type { LeakTrainerSpot, LeakTrainerGrade, LeakTrainerState, ReplayStep,
  ProgressionPlan, SessionSize } from "@/lib/api";
import { cn } from "@/lib/utils";

// `probe` = sondagem de range: a tela pergunta a fatia de mãos do VILÃO antes de revelar as
// cartas do herói. A ordem da informação é o conteúdo aqui — quem vê a própria mão primeiro
// já decidiu antes de considerar o adversário, e força de mão vira atributo em vez de
// comparação. Só aparece quando o backend manda `range_probe` (nunca em `rfi`).
type Phase = "intro" | "loading" | "probe" | "question" | "feedback" | "error" | "empty" | "summary" | "paywall";

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
  const [spotSeq, setSpotSeq]           = useState(0);
  // Cartas de memorizacao ja servidas NESTA sessao. Ref e nao state: so alimenta a proxima
  // requisicao, nunca a renderizacao — como state provocaria um render por spot, a troco de nada.
  const servidasRef                     = useRef<string[]>([]);
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
  // Resposta do jogador na sondagem. `null` = ainda não respondeu; um índice = já respondeu e
  // a tela mostra o acerto antes de revelar as cartas.
  const [probePick, setProbePick]       = useState<number | null>(null);
  const [targetedLocked, setTargetedLocked] = useState(false);        // Free: treino mirado é Pro
  const [gateInfo, setGateInfo]         = useState<{ used?: number; cap?: number } | null>(null);
  const [focus, setFocus]               = useState<string>("adaptive");   // o usuário escolhe o tipo de spot
  const focusRef = useRef<string>("adaptive");
  // ── Protocolo de Progressão: sessão com missão + composição 60/25/15 ──
  // Quando `planRef` tem plano, o loadNext puxa do protocolo (intercalando missão/revisão/
  // contraste) em vez do sorteio adaptativo solto. Refs porque o loadNext é useCallback estável.
  const [plan, setPlan]                 = useState<ProgressionPlan | null>(null);
  const [sizeSel, setSizeSel]           = useState<SessionSize>("media");   // duração escolhida
  const [showOther, setShowOther]       = useState(false);                  // disclosure: outros modos
  const planRef = useRef<ProgressionPlan | null>(null);
  const doneRef = useRef<Record<string, number>>({});   // spots cumpridos por fatia
  const [contrastNote, setContrastNote] = useState<string | null>(null);
  const stateRef = useRef<LeakTrainerState>(loadState());
  // Por onde o aluno CHEGOU (dashboard/sino/email/pos_upload). Lida UMA vez e congelada em
  // ref: o parâmetro some da URL na primeira navegação interna, mas a sessão inteira pertence
  // ao trigger que a originou — é a métrica 1 da spec de cobrança.
  const [urlParams] = useSearchParams();
  const origemRef = useRef<string>(urlParams.get("origem") || "espontanea");
  const focoInicialRef = useRef<string | null>(urlParams.get("foco"));
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
  // Rótulo do spot: fonte ÚNICA e localizada (lib/spotLabel). No spot em treino a profundidade
  // fica de fora — ela já está na mesa, e repetir polui o cabeçalho.
  const spotLabel = useSpotLabel();
  const labelFor = (sp: LeakTrainerSpot) => spotLabel(sp, { stack: false });

  const finishSession = () => setPhase("summary");
  const newSession = () => {
    setSessionStats({}); setTotalDone(0); setTotalCorrect(0); setStreak(0); setXpEarned(0);
    setMasteryByCat({}); setUnlockedAch([]);
    setPhase("intro");   // nova lição começa pela tela de início
  };

  const loadNext = useCallback(async () => {
    // Sobe a cada exercício carregado. Serve de `key` para os drills que guardam estado próprio:
    // a categoria sozinha não serve porque ela REPETE (são ~40 combinações de posição/família), e
    // num repique o React reusaria a instância e o exercício novo nasceria já corrigido.
    setSpotSeq((n) => n + 1);
    setPhase("loading"); setSelected(null); setGrade(null); setShowRange(false);
    setProbePick(null);
    setContrastNote(null);
    // Sessão do Protocolo: o próximo spot vem do PLANO (missão/revisão/contraste intercalados).
    if (planRef.current) {
      try {
        const r = await progression.next(planRef.current, doneRef.current);
        if (!r.spot) { setPhase("summary"); return; }   // plano cumprido = fim da sessão
        setSpot(r.spot);
        setContrastNote(r.contrast_note);
        setPhase(r.spot.range_probe ? "probe" : "question");
      } catch { setPhase("error"); }
      return;
    }
    try {
      const timeout = new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), 12000));
      const r = await Promise.race([
        leaktrainer.next(stateRef.current, 90, focusRef.current, servidasRef.current), timeout]);
      // Gate freemium: cap diário atingido → paywall (não tela vazia)
      if (r.limit_reached || r.requires_pro) { setGateInfo({ used: r.used, cap: r.cap }); setPhase("paywall"); return; }
      if (!r.spot) { setPhase("empty"); return; }
      setTargetedLocked(!!r.targeted_locked);   // Free: treinando fundamentos, mirado é Pro
      if (r.spot?.card_key) servidasRef.current = [...servidasRef.current, r.spot.card_key];
      setSpot(r.spot);
      setPhase(r.spot.range_probe ? "probe" : "question");
    } catch { setPhase("error"); }
  }, []);

  // seletor de tipo de spot: fixa o foco e começa a lição (o usuário escolhe, não é só aleatório)
  const startFocus = (f: string) => {
    planRef.current = null; setPlan(null); doneRef.current = {};   // sai do protocolo
    servidasRef.current = [];                                      // sessao nova, baralho cheio
    focusRef.current = f; setFocus(f); loadNext();
  };

  // Protocolo: abre a sessão com a duração escolhida na hora (curta/média/longa).
  // Duração variável exige que o gate de domínio seja por ACUMULADO, nunca por sessão.
  const startProtocol = async (size: SessionSize) => {
    setPhase("loading");
    try {
      const r = await progression.startSession(size, 365);
      if (!r.plan || !r.plan.mission) { setPhase("empty"); return; }
      planRef.current = r.plan; setPlan(r.plan); doneRef.current = {};
      loadNext();
    } catch { setPhase("error"); }
  };

  // Status do protocolo (missões + estado + gate de domínio) — a tela de início é sobre
  // ONDE VOCÊ ESTÁ antes de ser sobre o que clicar.
  const { data: statusData } = useQuery({
    queryKey: ["progression-status"],
    queryFn: () => progression.status(365),
    enabled: phase === "intro",
  });
  const { data: missionData } = useQuery({
    queryKey: ["progression-missions"],
    queryFn: () => progression.missions(365),
    enabled: phase === "intro",
  });
  const { data: trainOptions } = useQuery({
    queryKey: ["leaktrainer-options"], queryFn: leaktrainer.options, enabled: phase === "intro",
  });
  const leakOptLabel = (l: { scenario: string; position: string; vs_position: string }): string =>
    spotLabel(l, { stack: false });

  // Deep link do próximo passo (?foco=fund:range_grid): quem veio de um CTA cai DIRETO no
  // exercício prescrito. Obrigar a reencontrar o botão dentro de "Treinar outra coisa" seria
  // cobrar e esconder o caixa. Roda uma vez; sem foco na URL, o fluxo é o de sempre.
  useEffect(() => {
    const f = focoInicialRef.current;
    if (f) { focoInicialRef.current = null; startFocus(f); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Não auto-inicia: a lição começa pela tela de "intro" (botão Começar → loadNext).
  // No protocolo o tamanho é o do PLANO (a duração que o jogador escolheu); fora dele, a lição fixa.
  const sessionSize   = plan?.total ?? LESSON_SIZE;
  const lessonComplete = totalDone >= sessionSize;
  const nextOrFinish = () => { if (totalDone >= sessionSize) setPhase("summary"); else loadNext(); };

  const submit = async (action: string) => {
    if (!spot || phase !== "question" || submitting) return;
    setSelected(action); setSubmitting(true);
    try {
      const g = await leaktrainer.grade(spot, action, origemRef.current);
      setGrade(g);
      setTotalDone((n) => n + 1);
      // Protocolo: marca a fatia cumprida pro próximo /next respeitar a composição 60/25/15
      const bk = (spot as { block_kind?: string }).block_kind;
      if (bk) doneRef.current = { ...doneRef.current, [bk]: (doneRef.current[bk] ?? 0) + 1 };
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
        // S = shove (stack curto): sem isso o atalho não alcançava a ação que MAIS aparece
        // abaixo de 20bb. O guard `spot.options.includes(a)` abaixo ignora a tecla quando a
        // ação não existe naquele spot.
        const byLetter: Record<string, string> = { f: "fold", c: "call", r: "raise", s: "allin" };
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
  // O spot de grade NÃO tem mesa: sem assentos, sem cartas do herói. `buildStep` acessa
  // `sp.hero_cards.map(...)` e estourava — a página inteira caía no boundary de erro com
  // "Algo deu errado", sem pista do motivo.
  const table = spot && spot.kind !== "range_grid" ? buildStep(spot) : null;
  // Cartas do herói só aparecem DEPOIS da sondagem. É o conteúdo do exercício: estimar a range
  // do vilão com a mesa à vista (posições, stacks, ação) mas sem saber a própria mão. A mesa
  // desenha verso no assento do herói quando recebe lista vazia.
  const cartasVisiveis = phase === "probe" ? [] : (table?.heroCards ?? []);

  /* ── Sondagem de range: painel LATERAL, com a mesa à vista ───────────────────────────────
     A primeira versão era sobreposição de tela cheia, e estava errada de conceito: pedia para
     estimar a range do vilão ESCONDENDO a mesa — sem posições, stacks nem a ação que aconteceu,
     que é exatamente o contexto de onde a estimativa sai. Perguntar "quanto o LJ abre" sem
     mostrar quem é o LJ e o que ele fez transforma o exercício em decoreba de tabela.

     Agora a mesa fica visível, com o assento do herói de VERSO (a mesa desenha o verso quando
     recebe lista de cartas vazia), e a pergunta ocupa a coluna lateral. No celular vira folha
     inferior, porque coluna lateral em tela estreita esmaga as duas coisas.

     O nome do vilão e a fatia vêm prontos do backend, da MESMA contagem que a Academia usa: a
     tela não calcula largura de range, senão existiriam duas fontes e uma hora divergiriam. */
  const sondagem = spot?.range_probe;
  const montaSondagem = (compacto: boolean) => {
    if (phase !== "probe" || !sondagem) return null;
    const respondeu = probePick !== null;
    const opcoes = (
      <div className={cn(compacto ? "flex flex-wrap justify-center gap-2" : "space-y-2")}>
        {sondagem.opcoes.map((op, i) => {
          const certa = i === sondagem.correta;
          return (
            <button key={op} disabled={respondeu} onClick={() => setProbePick(i)}
              className={cn(
                "rounded-xl border font-mono transition-colors",
                compacto ? "px-4 py-2 text-xs" : "w-full px-4 py-2.5 text-sm",
                !respondeu && "border-border text-foreground hover:border-amber-500/60 hover:text-amber-400",
                respondeu && certa && "border-emerald-500/60 bg-emerald-500/10 text-emerald-400",
                respondeu && !certa && i === probePick && "border-red-500/60 bg-red-500/10 text-red-400",
                respondeu && !certa && i !== probePick && "border-border/40 text-muted-foreground/50",
              )}>
              {op}
            </button>
          );
        })}
      </div>
    );
    return (
      <div className={cn(
        // `min-w-0` + sem largura própria: o painel PREENCHE a coluna, nunca a define.
        // A primeira versão trazia `lg:w-[340px]` e vivia dentro de um `aside` de `lg:w-72`
        // (288px) — 340 dentro de 288 estourava e a coluna ganhava barra de rolagem horizontal,
        // com a pergunta cortada no meio. Componente que fixa a própria largura só funciona
        // enquanto ninguém o coloca noutro lugar.
        "w-full min-w-0 rounded-2xl border border-amber-500/30 bg-background/95 shadow-xl backdrop-blur",
        compacto ? "px-4 py-3" : "p-4",
      )}>
        <p className={cn("font-mono uppercase tracking-widest text-amber-400",
                         compacto ? "text-[9px] text-center" : "text-[10px]")}>
          {t("leakTrainer.probe.eyebrow")}
        </p>
        <h2 className={cn("font-heading font-bold leading-snug text-foreground [overflow-wrap:anywhere]",
                          compacto ? "mt-1 text-center text-[13px]" : "mt-2 text-[15px]")}>
          {sondagem.pergunta}
        </h2>
        <div className={compacto ? "mt-2.5" : "mt-4"}>{opcoes}</div>
        {respondeu && (
          <div className={cn("animate-fade-in", compacto ? "mt-2.5 space-y-2" : "mt-4 space-y-3")}>
            <p className={cn("leading-snug text-muted-foreground",
                             compacto ? "text-[11px] text-center" : "text-[12px]")}>
              {sondagem.explicacao}
            </p>
            <button onClick={() => setPhase("question")}
              className="w-full rounded-xl bg-amber-500/15 px-4 py-2.5 font-mono text-xs font-bold uppercase tracking-wider text-amber-400 ring-1 ring-amber-500/40 transition-colors hover:bg-amber-500/25">
              {t("leakTrainer.probe.reveal")}
            </button>
          </div>
        )}
      </div>
    );
  };
  const painelSondagem = montaSondagem(false);

  const catLabel = spot ? labelFor(spot) : "";
  const blockKind = (spot as { block_kind?: string } | null)?.block_kind;

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
        {/* ── Camada didática (Protocolo): o GATILHO + a nota da classe de mão ──
            Vem ANTES dos números de propósito: o jogador precisa entender POR QUE antes de
            ver quanto. As frequências abaixo são a camada 2 (a quantidade). */}
        {grade.concept && (
          <div className="space-y-1.5 rounded-lg border border-border/60 bg-background/40 px-3 py-2.5">
            <p className="text-[13px] leading-snug text-foreground">{grade.concept.principio}</p>
            {grade.concept.nota_mao && (
              <p className="text-[12px] leading-snug text-muted-foreground">{grade.concept.nota_mao}</p>
            )}
            {/* TAMANHO: o dado carrega o sizing ('R2.1' = raise para 2,1bb). Ensinamos aqui em
                vez de perguntar — cada nó tem UM tamanho GTO, então virar pergunta seria
                decoreba de tabela. O conceito (por que este tamanho) é o que transfere. */}
            {grade.sizing_note && (
              <p className="border-t border-border/50 pt-2 text-[12px] leading-snug text-sky-300/90">
                {grade.sizing_note}
              </p>
            )}
            {grade.concept.regra && (
              <p className="flex items-start gap-1.5 pt-0.5 font-mono text-[10px] uppercase leading-snug tracking-wide text-amber-400/90">
                <span aria-hidden>▸</span><span className="normal-case tracking-normal">{grade.concept.regra}</span>
              </p>
            )}
          </div>
        )}
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
  if (landscapeMobile && (phase === "probe" || phase === "question" || phase === "feedback") && spot && table) {
    return (
      <div ref={rootRef} className="h-dvh relative overflow-hidden hud-scanline"
        style={{ background: "radial-gradient(ellipse at 50% 45%, #14223a 0%, #080f1c 100%)" }}>
        <div className="absolute inset-0 flex items-center justify-center p-0.5">
          <div className="h-full w-auto max-w-full mx-auto" style={{ aspectRatio: "1160 / 710" }}>
            <PokerTableV3 step={table.step} hero="Hero" heroCards={cartasVisiveis} bb={table.bb} betUnit="bb" orientation="landscape" fill />
          </div>
        </div>
        {/* Sondagem no modo imersivo: faixa INFERIOR, não lateral.
            Ancorada à direita, ela cobria o assento do vilão — justamente aquele sobre quem a
            pergunta é feita, o que esvazia o exercício. Embaixo ela ocupa a faixa que fica vazia
            (os botões de ação não existem nesta fase) e nenhum assento é escondido. */}
        {phase === "probe" && sondagem && (
          <div className="absolute bottom-[calc(0.4rem+env(safe-area-inset-bottom))] left-1/2 z-40 w-[min(620px,96vw)] -translate-x-1/2">
            {montaSondagem(true)}
          </div>
        )}
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
              <span className="text-foreground">{totalDone}/{sessionSize}</span>
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

        {phase === "intro" && (() => {
          /* ── TELA DE FOCO ────────────────────────────────────────────────────────────────
             Responde 3 perguntas nesta ordem, em <3s: ONDE ESTOU → O QUE FAÇO → POR QUÊ.
             A versão anterior tinha 12+ pontos de entrada competindo (3 durações + "adaptativo
             RECOMENDADO" + 6 leaks + 3 fundamentos), com a MESMA categoria aparecendo duas
             vezes com nomes diferentes e o status do protocolo invisível. Agora: um bloco de
             status com o gate à vista, UMA ação primária, e todo o resto atrás de disclosure. */
          /* O foco vem do BACKEND (`ativa` = primeira missão que ainda não passou o gate).
             Antes a tela fixava `items[0]` e o leak dominado ficava eternamente em foco:
             o gate acendia 5/5 e nada acontecia. Fallback pro topo da lista só se o backend
             for antigo (deploy defasado) — nunca deixar a tela vazia por isso. */
          const st   = statusData?.ativa ?? statusData?.items?.[0];
          const miss = st ?? missionData?.missions?.[0];
          const outras = statusData?.proximas ?? (statusData?.items ?? []).slice(1);
          const dominadas = statusData?.dominadas ?? [];
          const revisao = !statusData?.ativa && dominadas.length > 0;
          const stateTone = st?.estado === "comprovado_no_jogo"
            ? { text: "text-emerald-400", ring: "ring-emerald-500/30", bg: "bg-emerald-500/10" }
            : st?.estado === "dominado_no_treino"
              ? { text: "text-sky-400", ring: "ring-sky-500/30", bg: "bg-sky-500/10" }
              : { text: "text-amber-400", ring: "ring-amber-500/30", bg: "bg-amber-500/10" };
          const feitos = st?.mastery.criterios.filter((c) => c.ok).length ?? 0;
          const totalCrit = st?.mastery.criterios.length ?? 5;

          return (
          <div className="mx-auto flex w-full max-w-xl flex-col gap-3">
            {/* ── 1. ONDE ESTOU + O QUE FAÇO (o herói da tela) ── */}
            <div className="rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/[0.07] to-transparent p-5 sm:p-6 space-y-4">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                  {revisao
                    ? t("leakTrainer.protocol.reviewMode", "Revisão")
                    : st ? t("leakTrainer.protocol.missionOf", {
                            n: 1,
                            // "+" quando o pool saturou: o número é um teto, não o total
                            total: `${statusData?.restantes ?? 1}${statusData?.restantes_cap ? "+" : ""}`,
                            defaultValue: `Missão 1 de ${statusData?.restantes ?? 1}`,
                          })
                       : t("leakTrainer.protocol.mission", "Missão de hoje")}
                </span>
                {st && (
                  <span className={cn("rounded-md px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider ring-1",
                    stateTone.text, stateTone.ring, stateTone.bg)}>
                    {t(`leakTrainer.state.${st.estado}`, { defaultValue: st.estado_label })}
                  </span>
                )}
              </div>

              {miss ? (
                <div className="space-y-1">
                  <h2 className="font-heading text-2xl font-bold leading-tight text-foreground">{spotLabel(miss, { fallback: miss.titulo })}</h2>
                  <p className="text-[13px] leading-snug text-muted-foreground">
                    <span className="font-semibold text-foreground">{miss.ev_loss_bb}bb</span>{" "}
                    {t("leakTrainer.protocol.lostIn", { hands: miss.hands,
                        defaultValue: `perdidos aqui, em ${miss.hands} mãos reais` })}
                    {!miss.stack_medido && (
                      <span className="text-amber-400/80"> · {t("leakTrainer.protocol.estimated", "(profundidade estimada)")}</span>
                    )}
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <h2 className="font-heading text-xl font-bold text-foreground">{t("leakTrainer.lesson.title")}</h2>
                  <p className="text-sm text-muted-foreground">{t("leakTrainer.empty")}</p>
                </div>
              )}

              {/* ── REABERTURA ──
                  Um leak que já estava dominado voltando ao foco parece bug se ninguém explicar.
                  O motivo é o mais importante do protocolo: o gate serve pra prever o jogo, e o
                  jogo disse o contrário. */}
              {st?.reaberto && st.estado === "em_treino" && (
                <div className="flex gap-2 rounded-xl border border-amber-500/40 bg-amber-500/[0.07] p-3">
                  <RotateCw className="mt-0.5 size-4 shrink-0 text-amber-400" aria-hidden />
                  <div className="space-y-0.5">
                    <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-amber-400">
                      {t("leakTrainer.protocol.reopened", "Leak reaberto")}
                    </p>
                    <p className="text-[12px] leading-snug text-muted-foreground">
                      {t("leakTrainer.protocol.reopenedWhy",
                         "Você tinha dominado isto no treino, mas nos seus torneios recentes o erro voltou. O domínio anterior foi zerado: vale o que você provar daqui pra frente.")}
                    </p>
                  </div>
                </div>
              )}

              {/* ── O GATE, À VISTA ──
                  Sem isto o jogador treina no escuro: não sabe o que falta nem quando acaba. */}
              {st && (
                <div className="rounded-xl border border-border/70 bg-background/40 p-3 space-y-2">
                  <div className="flex items-baseline justify-between">
                    <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                      {revisao ? t("leakTrainer.protocol.keepMastery", "Mantendo o domínio")
                               : t("leakTrainer.protocol.untilMastered", "Até dominar")}
                    </span>
                    <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                      {feitos}/{totalCrit}
                    </span>
                  </div>
                  <MasteryGate criterios={st.mastery.criterios} />
                </div>
              )}

              {/* ── AÇÃO ÚNICA + duração (segmentado, padrão média) ── */}
              {miss && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1 rounded-lg border border-border bg-hud-surface p-1">
                    {([["curta", "12", "4"], ["media", "24", "8"], ["longa", "40", "13"]] as const).map(
                      ([sz, n, min]) => (
                        <button key={sz} onClick={() => setSizeSel(sz as SessionSize)}
                          className={cn("flex-1 rounded-md px-2 py-1.5 font-mono text-[11px] font-bold transition-colors",
                            sizeSel === sz ? "bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/40"
                                           : "text-muted-foreground hover:text-foreground")}>
                          {n} <span className="font-normal opacity-70">· {min}min</span>
                        </button>
                      ))}
                  </div>
                  <button onClick={() => startProtocol(sizeSel)}
                    className="flex w-full items-center justify-center gap-2 rounded-xl bg-amber-500 px-6 py-3.5 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400">
                    <Target className="size-4" aria-hidden />{" "}
                    {revisao ? t("leakTrainer.protocol.review", "Revisar")
                             : t("leakTrainer.protocol.train", "Treinar")}
                  </button>
                </div>
              )}
            </div>

            {/* ── 2. O ARCO: as próximas missões (por que só uma por vez) ── */}
            {outras.length > 0 && (
              <div className="rounded-xl border border-border bg-hud-surface/40 p-3">
                <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  {t("leakTrainer.protocol.nextMissions", "Depois desta")}
                </p>
                <div className="space-y-1">
                  {outras.map((o, i) => (
                    <div key={o.key} className="flex items-center gap-2 text-[12px]">
                      <span className="w-4 shrink-0 text-center font-mono text-[10px] text-muted-foreground">{i + 2}</span>
                      <span className="min-w-0 flex-1 truncate text-muted-foreground">{spotLabel(o, { fallback: o.titulo })}</span>
                      <span className="shrink-0 font-mono text-[9px] uppercase text-muted-foreground/60">{t(`leakTrainer.state.${o.estado}`, { defaultValue: o.estado_label })}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[11px] leading-snug text-muted-foreground/70">
                  {t("leakTrainer.protocol.oneAtATime",
                     "Uma de cada vez: dividir o foco entre leaks faz você não dominar nenhum.")}
                </p>
              </div>
            )}

            {/* ── 2b. O QUE VOCÊ JÁ CONQUISTOU ──
                Passar o gate tem que APARECER, senão o esforço some da tela e o jogador não vê
                que avançou. E tem que ser honesto: dominar no treino não é ter corrigido no
                jogo — o selo só vem quando os uploads confirmarem. */}
            {dominadas.length > 0 && (
              <div className="rounded-xl border border-sky-500/25 bg-sky-500/[0.04] p-3">
                <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-sky-400/90">
                  {t("leakTrainer.protocol.mastered", "Dominados")} · {dominadas.length}
                </p>
                <div className="space-y-2">
                  {dominadas.map((d) => {
                    /* O trilho lento em uma linha: ou o veredito estatístico, ou quantas
                       decisões ainda faltam pra ele existir. Nunca um número solto — "62% → 71%"
                       com 14 mãos não significa nada e o jogador não tem como saber disso. */
                    const v = d.validacao;
                    const falta = v?.veredito === "sem_amostra" ? (v.faltam ?? null) : null;
                    return (
                      <div key={d.key} className="space-y-0.5">
                        <div className="flex items-center gap-2 text-[12px]">
                          <CheckCircle2 className={cn("size-3.5 shrink-0",
                            d.estado === "comprovado_no_jogo" ? "text-emerald-400" : "text-sky-400")} aria-hidden />
                          <span className="min-w-0 flex-1 truncate text-foreground/90">{spotLabel(d, { fallback: d.titulo })}</span>
                          <span className={cn("shrink-0 font-mono text-[9px] uppercase",
                            d.estado === "comprovado_no_jogo" ? "text-emerald-400" : "text-sky-400/80")}>
                            {t(`leakTrainer.state.${d.estado}`, { defaultValue: d.estado_label })}
                          </span>
                        </div>
                        {v && (
                          <p className="pl-[22px] text-[11px] leading-snug text-muted-foreground/70">
                            {falta != null
                              ? t("leakTrainer.protocol.needHands", { n: falta,
                                  defaultValue: `Faltam ${falta} decisões desta situação nos seus torneios para o veredito.` })
                              : v.veredito === "melhorou"
                                ? t("leakTrainer.protocol.provenDrop", {
                                    antes: v.taxa_antes, depois: v.taxa_depois,
                                    defaultValue: `Erro caiu de ${v.taxa_antes}% para ${v.taxa_depois}% nas mãos reais.` })
                                : t("leakTrainer.protocol.noDiff",
                                    "As mãos que você jogou ainda não distinguem melhora de sorte.")}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="mt-2 text-[11px] leading-snug text-muted-foreground/70">
                  {dominadas.some((d) => d.estado === "dominado_no_treino")
                    ? t("leakTrainer.protocol.masteredPending",
                        "Dominado no treino libera o próximo leak. O selo de comprovado só vem quando seus próximos torneios confirmarem a correção na mesa.")
                    : t("leakTrainer.protocol.masteredProven",
                        "Confirmado nos seus torneios: o acerto saiu do treino e chegou na mesa.")}
                </p>
              </div>
            )}

            {/* ── 2c. MEMORIZAR RANGE ──
                Estava só atrás de "Treinar outra coisa", o que o deixava disponível para quem já
                sabe que precisa dele — exatamente quem menos precisa. Quem erra a abertura do LJ
                não pensa "não tenho a range na cabeça"; pensa que errou aquela mão.

                Aparece por DOIS motivos distintos, e a ordem importa: revisão vencida primeiro
                (é o que o SRS existe para forçar), sugestão de leak depois. Sem motivo, não
                aparece — sugerir estudo sem evidência gasta a credibilidade de toda sugestão. */}
            {(() => {
              const memo = trainOptions?.memorizacao;
              const sug = memo?.sugestao;
              const vencidas = memo?.placar?.vencidas ?? 0;
              if (!sug && vencidas <= 0) return null;
              return (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/[0.05] p-3">
                  <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-amber-400">
                    {vencidas > 0
                      ? t("leakTrainer.memo.dueEyebrow", { n: vencidas,
                          defaultValue: `${vencidas} range${vencidas > 1 ? "s" : ""} para revisar` })
                      : t("leakTrainer.memo.eyebrow", "Memorizar range")}
                  </p>
                  <p className="text-[12px] leading-snug text-muted-foreground">
                    {vencidas > 0
                      ? t("leakTrainer.memo.dueWhy",
                          "Você já estudou estas e chegou a hora de reencontrá-las. É o reencontro no tempo certo que fixa, não a repetição seguida.")
                      : sug!.de_quem === "vilao"
                        /* Leak de vs_RFI: a range que falta é a de QUEM ABRIU. Mandá-lo memorizar
                           a range dele mesmo aqui seria a ferramenta errada com cara de conselho. */
                        ? t("leakTrainer.memo.whyVillain", {
                            pos: sug!.position, bb: sug!.ev_loss_bb, hands: sug!.hands,
                            defaultValue: `Você perdeu ${sug!.ev_loss_bb}bb enfrentando aberturas do ${sug!.position}, em ${sug!.hands} mãos. Para decidir contra ele é preciso enxergar o que o ${sug!.position} abre.` })
                        : t("leakTrainer.memo.whyHero", {
                            pos: sug!.position, bb: sug!.ev_loss_bb, hands: sug!.hands,
                            defaultValue: `Você perdeu ${sug!.ev_loss_bb}bb abrindo do ${sug!.position}, em ${sug!.hands} mãos. Marcar a range até onde ela vai é o que fixa a fronteira.` })}
                  </p>
                  <button onClick={() => startFocus("fund:range_grid")}
                    className="mt-2.5 flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500/15 px-4 py-2.5 font-mono text-[11px] font-bold uppercase tracking-wider text-amber-400 ring-1 ring-amber-500/40 transition-colors hover:bg-amber-500/25">
                    <Target className="size-3.5" aria-hidden />
                    {vencidas > 0
                      ? t("leakTrainer.memo.ctaReview", "Revisar ranges")
                      : t("leakTrainer.memo.cta", { pos: sug!.position,
                          defaultValue: `Memorizar a range do ${sug!.position}` })}
                  </button>
                  {/* O placar dá sentido ao esforço: sem ele o jogador marca grades para sempre
                      sem saber se está indo a algum lugar. */}
                  {(memo?.placar?.vistas ?? 0) > 0 && (
                    <p className="mt-1.5 text-center font-mono text-[10px] text-muted-foreground/70">
                      {t("leakTrainer.memo.score", {
                          vistas: memo!.placar.vistas, dominadas: memo!.placar.dominadas,
                          defaultValue: `${memo!.placar.vistas} estudadas · ${memo!.placar.dominadas} na memória` })}
                    </p>
                  )}
                </div>
              );
            })()}

            {/* ── 3. OUTROS MODOS (secundário, atrás de disclosure) ── */}
            <div className="rounded-xl border border-border bg-hud-surface/40">
              <button onClick={() => setShowOther((v) => !v)}
                className="flex w-full items-center justify-between px-3 py-2.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground">
                {t("leakTrainer.protocol.otherModes", "Treinar outra coisa")}
                <span className={cn("transition-transform", showOther && "rotate-180")} aria-hidden>▾</span>
              </button>
              {showOther && (
                <div className="space-y-3 border-t border-border/60 p-3">
                  <button onClick={() => startFocus("adaptive")}
                    className="w-full rounded-lg border border-border bg-background/60 px-3 py-2 text-left text-[13px] text-foreground transition-colors hover:border-amber-500/40">
                    {t("leakTrainer.picker.adaptive")}
                  </button>
                  {trainOptions?.leaks && trainOptions.leaks.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-[11px] font-bold text-foreground">{t("leakTrainer.picker.yourLeaks")}</p>
                      <div className="grid gap-1.5">
                        {trainOptions.leaks.slice(0, 6).map((l) => (
                          <button key={l.category_key} onClick={() => startFocus(`leak:${l.category_key}`)}
                            className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background/60 px-3 py-2 text-left transition-colors hover:border-amber-500/40">
                            <span className="truncate text-[13px] text-foreground">{leakOptLabel(l)}</span>
                            <span className="shrink-0 font-mono text-[10px] text-muted-foreground">−{l.ev_loss_bb}bb</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div>
                    <p className="mb-1.5 text-[11px] font-bold text-foreground">{t("leakTrainer.picker.fundamentals")}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(trainOptions?.scenarios ?? ["rfi", "vs_rfi"]).map((scn) => (
                        <button key={scn} onClick={() => startFocus(`fund:${scn}`)}
                          className="rounded-lg border border-border bg-background/60 px-3 py-1.5 text-[12px] text-foreground transition-colors hover:border-amber-500/40">
                          {t(`leakTrainer.scn.${scn}`)}
                        </button>
                      ))}
                      {/* Memorização, não decisão: marcar até onde a range vai. Fica junto dos
                          fundamentos porque é o alicerce dos outros exercícios — sem saber a
                          fronteira, acertar um spot é reconhecimento, não conhecimento. */}
                      <button onClick={() => startFocus("fund:range_grid")}
                        className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-[12px] text-amber-300 transition-colors hover:border-amber-500/70">
                        {t("leakTrainer.scn.range_grid")}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          );
        })()}

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

        {/* Gate freemium: cap diário atingido → upsell Pro (treino ilimitado + mirado) */}
        {phase === "paywall" && (
          <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-8">
            <p className="text-center text-sm text-muted-foreground">
              {t("leakTrainer.gate.capDone", { used: gateInfo?.used ?? gateInfo?.cap ?? "", cap: gateInfo?.cap ?? "" })}
            </p>
            <ProLockCard feature={t("leakTrainer.gate.capFeature")} />
            <button onClick={newSession} className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground hover:text-foreground">
              {t("leakTrainer.gate.back")}
            </button>
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

              {/* CTAs: Continuar (nova lição) + Finalizar (volta ao hub de Treino p/ ver o status pós-treino) */}
              <div className="mt-6 space-y-2">
                <button onClick={newSession} className="w-full rounded-xl bg-primary px-4 py-3.5 font-mono text-sm font-bold uppercase tracking-widest text-primary-foreground shadow-lg transition-transform hover:bg-primary/90 active:scale-[0.98]">
                  {t("leakTrainer.summary.continue")}
                </button>
                <button onClick={() => navigate("/training")} className="flex w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-3 font-mono text-xs font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground">
                  <Home className="size-4" aria-hidden /> {t("leakTrainer.summary.finish")}
                </button>
              </div>

              {/* loop honesto: liga ao jogo real (sem fingir delta de ELO) */}
              <p className="mt-3 text-center text-[11px] leading-relaxed text-muted-foreground/80">{t("leakTrainer.summary.loopHint")}</p>
            </div>
          </div>
          );
        })()}

        {/* Treino de fronteira: não tem mesa nem botões de ação, então curto-circuita o bloco
            de spot normal. `table` nem é montado para este kind (o spot não tem posições de
            assento), e por isso a condição abaixo já o exclui naturalmente. */}
        {(phase === "question" || phase === "feedback") && spot?.kind === "range_grid" && (
          <div className="flex min-h-0 flex-1 items-start justify-center overflow-y-auto py-4">
            {/* `key` pelo spot: sem ela o React REUSA a instância entre exercícios e o estado
                interno (marcações e correção) atravessa — o spot novo aparecia já corrigido, com
                as células do anterior pintadas. Remontar é o certo aqui: cada exercício é uma
                rodada independente, não uma continuação. */}
            <RangeFamilyDrill key={spotSeq} spot={spot}
              onDone={(acertou, xp) => {
                setTotalDone((n) => n + 1);
                if (acertou) { setTotalCorrect((n) => n + 1); setXpEarned((x) => x + xp); }
                setPhase("feedback");
              }}
              /* O avanço mora AQUI porque este kind não passa pelo painel de spot normal, que é
                 quem carrega o botão de próximo. Sem ele o exercício terminava num beco: o
                 atalho de teclado funcionava, mas na tela só sobrava "finalizar sessão". */
              rodape={
                <button onClick={nextOrFinish}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400">
                  <ArrowRight className="size-4" aria-hidden />
                  {lessonComplete ? t("leakTrainer.lesson.seeResult") : t("leakTrainer.next")}
                  <kbd className="hidden rounded border border-black/20 bg-black/10 px-1.5 py-0.5 text-[9px] font-normal md:inline-block">Enter</kbd>
                </button>
              } />
          </div>
        )}
        {(phase === "probe" || phase === "question" || phase === "feedback") && spot && spot.kind !== "range_grid" && table && (
          <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row lg:items-stretch">

            <div className="flex min-h-0 min-w-0 flex-1 items-center justify-center">
              <div className="aspect-[16/10] h-full max-h-full w-auto max-w-full">
                <PokerTableV3 step={table.step} hero="Hero" heroCards={cartasVisiveis} bb={table.bb} betUnit="bb" transparentBg />
              </div>
            </div>

            <aside className="flex w-full shrink-0 flex-col gap-3 lg:min-h-0 lg:w-72 lg:overflow-y-auto">
              {painelSondagem}

              {totalDone > 0 && (
                <div className="flex items-center justify-around rounded-lg border border-border bg-hud-surface px-3 py-2">
                  <div className="text-center">
                    <p className="font-mono text-base font-bold tabular-nums text-foreground">{totalDone}/{sessionSize}</p>
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

              {/* Categoria de leak treinada agora + a FATIA da sessão (protocolo).
                  Sem dizer que é contraste, o jogador acha que o sistema se perdeu ao mudar
                  de profundidade no meio da sessão. */}
              <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 space-y-1">
                <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-amber-400">
                  <Target className="size-3" aria-hidden />
                  {blockKind === "contrast" ? t("leakTrainer.protocol.blockContrast", "Contraste")
                    : blockKind === "review" ? t("leakTrainer.protocol.blockReview", "Revisão")
                    : t("leakTrainer.weakSpot")}
                </span>
                <p className="text-sm font-bold text-foreground leading-snug">{catLabel}</p>
                <p className="font-mono text-[10px] text-muted-foreground">{spot.stack_bb}bb</p>
                {contrastNote && (
                  <p className="pt-1 text-[11px] leading-snug text-amber-400/90">{contrastNote}</p>
                )}
              </div>

              {/* Progresso da sessão do protocolo (a sessão TEM forma: começo, meio e fim) */}
              {plan && (
                <div className="rounded-xl border border-border bg-hud-surface/50 p-3">
                  <div className="mb-1.5 flex items-baseline justify-between">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      {t("leakTrainer.protocol.progress", "Sessão")}
                    </span>
                    <span className="font-mono text-[10px] tabular-nums text-foreground">
                      {totalDone}/{sessionSize}
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-border">
                    <div className="h-full rounded-full bg-amber-500 transition-all"
                      style={{ width: `${Math.min(100, (totalDone / Math.max(1, sessionSize)) * 100)}%` }} />
                  </div>
                </div>
              )}

              {/* Free: treinando fundamentos genéricos; mirar nos leaks reais é Pro */}
              {targetedLocked && (
                <div className="rounded-xl border border-primary/30 bg-primary/[0.06] p-3">
                  <p className="flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary">
                    <Lock className="size-3" aria-hidden /> {t("leakTrainer.gate.targetedTitle")}
                  </p>
                  <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{t("leakTrainer.gate.targetedDesc")}</p>
                </div>
              )}

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
                          {a === "fold" ? "F" : a === "call" ? "C" : a === "allin" ? "S" : "R"}
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
