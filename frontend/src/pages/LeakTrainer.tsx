import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, CheckCircle2, Loader2, RefreshCw, XCircle, Target } from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { leaktrainer } from "@/lib/api";
import type { LeakTrainerSpot, LeakTrainerGrade, LeakTrainerState, ReplayStep } from "@/lib/api";
import { cn } from "@/lib/utils";

type Phase = "loading" | "question" | "feedback" | "error" | "empty";

const ORDER = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];
const STATE_KEY = "leaklab_leaktrainer_state";

const FREQ_LABEL: Record<string, string> = { raise: "raise", call: "call", allin: "all-in", fold: "fold" };
const FREQ_COLOR: Record<string, string> = {
  raise: "bg-emerald-500", call: "bg-sky-500", allin: "bg-violet-500", fold: "bg-muted-foreground/40",
};

/** Monta um ReplayStep 9-max sintético a partir do spot (mesma lógica do academy preflop). */
function buildStep(sp: LeakTrainerSpot) {
  const bb = 100;
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

export default function LeakTrainer() {
  const { t } = useTranslation("academy");

  const [phase, setPhase]               = useState<Phase>("loading");
  const [spot, setSpot]                 = useState<LeakTrainerSpot | null>(null);
  const [grade, setGrade]               = useState<LeakTrainerGrade | null>(null);
  const [selected, setSelected]         = useState<string | null>(null);
  const [submitting, setSubmitting]     = useState(false);
  const [streak, setStreak]             = useState(0);
  const [totalDone, setTotalDone]       = useState(0);
  const [totalCorrect, setTotalCorrect] = useState(0);
  const stateRef = useRef<LeakTrainerState>(loadState());

  const loadNext = useCallback(async () => {
    setPhase("loading"); setSelected(null); setGrade(null);
    try {
      const timeout = new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), 12000));
      const r = await Promise.race([leaktrainer.next(stateRef.current), timeout]);
      if (!r.spot) { setPhase("empty"); return; }
      setSpot(r.spot);
      setPhase("question");
    } catch { setPhase("error"); }
  }, []);

  useEffect(() => { loadNext(); }, [loadNext]);

  const submit = async (action: string) => {
    if (!spot || phase !== "question" || submitting) return;
    setSelected(action); setSubmitting(true);
    try {
      const g = await leaktrainer.grade(spot, action);
      setGrade(g);
      setTotalDone((n) => n + 1);
      // atualiza o estado da sessão por categoria (adaptação) + persiste
      const st = stateRef.current;
      const cur = st[spot.category] || { hits: 0, misses: 0, seen: 0 };
      st[spot.category] = {
        hits: cur.hits + (g.is_correct ? 1 : 0),
        misses: cur.misses + (g.is_correct ? 0 : 1),
        seen: cur.seen + 1,
      };
      try { localStorage.setItem(STATE_KEY, JSON.stringify(st)); } catch { /* quota */ }
      if (g.is_correct) { setStreak((s) => s + 1); setTotalCorrect((n) => n + 1); }
      else setStreak(0);
      setPhase("feedback");
    } catch { setPhase("error"); }
    finally { setSubmitting(false); }
  };

  const accuracy = totalDone > 0 ? Math.round((totalCorrect / totalDone) * 100) : null;
  const table = spot ? buildStep(spot) : null;

  // rótulo humano da categoria de leak (localizado a partir do cenário + posições)
  const catLabel = spot ? (
    spot.scenario === "rfi" ? t("leakTrainer.cat.rfi", { pos: spot.position })
    : spot.scenario === "vs_rfi" ? t("leakTrainer.cat.vsRfi", { pos: spot.position, vs: spot.vs_position })
    : t("leakTrainer.cat.vs3bet", { pos: spot.position, vs: spot.vs_position })
  ) : "";

  // rótulo da ação (raise muda por cenário: 3-Bet vs 4-Bet)
  const actLabel = (a: string) => {
    if (a === "raise") return spot?.scenario === "vs_3bet" ? t("leakTrainer.act.raise4") : spot?.scenario === "vs_rfi" ? t("leakTrainer.act.raise3") : t("leakTrainer.act.raiseOpen");
    return t(`leakTrainer.act.${a}`, a);
  };

  const freqEntries = grade
    ? Object.entries(grade.hand_freq || {}).filter(([, v]) => v && v > 0.01).sort((a, b) => b[1] - a[1])
    : [];
  const verdictKind = grade ? (grade.gto_tier === "error" ? "error" : grade.mixed ? "mixed" : "correct") : null;

  return (
    <HudLayout eyebrow={t("leakTrainer.eyebrow")} title={t("leakTrainer.title")} description={t("leakTrainer.subtitle")}>
      <div className="mx-auto w-full max-w-[1500px] space-y-4">

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

        {(phase === "question" || phase === "feedback") && spot && table && (
          <div className="flex flex-col lg:flex-row gap-4 items-stretch">

            <div className="flex-1 min-w-0">
              <div className="w-full aspect-[16/10]">
                <PokerTableV3 step={table.step} hero="Hero" heroCards={table.heroCards} bb={table.bb} betUnit="bb" />
              </div>
            </div>

            <aside className="w-full lg:w-72 shrink-0 flex flex-col gap-3">

              {totalDone > 0 && (
                <div className="flex items-center justify-around rounded-lg border border-border bg-hud-surface px-3 py-2">
                  <div className="text-center">
                    <p className="font-mono text-base font-bold tabular-nums text-foreground">{totalDone}</p>
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
                          "min-h-[48px] rounded-lg border px-4 py-3 text-left font-mono text-sm font-bold uppercase tracking-wider transition-all active:scale-95",
                          "border-border bg-hud-surface text-foreground ring-1 ring-border hover:border-amber-500/60 hover:bg-amber-500/5 hover:text-amber-400",
                          "disabled:opacity-40 disabled:cursor-not-allowed",
                          submitting && selected === a && "border-amber-500/60 bg-amber-500/5 text-amber-400",
                        )}
                      >
                        {actLabel(a)}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {phase === "feedback" && grade && verdictKind && (
                <div className="flex flex-col gap-3">
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

                    {/* "GTO joga {hand} aqui:" + barras de frequência */}
                    {freqEntries.length > 0 && (
                      <>
                        <p className="font-mono text-[10px] text-muted-foreground">{t("leakTrainer.gtoPlays", { hand: spot.hand })}</p>
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

                  <button onClick={loadNext} className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400">
                    <ArrowRight className="size-4" aria-hidden /> {t("leakTrainer.next")}
                  </button>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>
    </HudLayout>
  );
}
