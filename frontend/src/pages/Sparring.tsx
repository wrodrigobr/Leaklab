import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Flame,
  Loader2,
  Swords,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import type { CardData } from "@/components/hud/PlayingCard";
import { PokerTable } from "@/components/hud/PokerTable";
import type { Seat } from "@/components/hud/PokerTable";
import { sparring, drill, tournaments } from "@/lib/api";
import type { SparringHand, SparringStep, DrillSubmitResult, ReplayStep } from "@/lib/api";
import { cn, formatAction } from "@/lib/utils";

type Phase = "idle" | "loading" | "playing" | "feedback" | "summary";

const ACTION_KEYS_FACING    = ["fold", "call", "raise", "jam"] as const; // facing a bet
const ACTION_KEYS_NO_FACING = ["fold", "check", "bet",  "jam"] as const; // no bet to face
const ACTION_KEYS_ALL       = ["fold", "check", "call", "bet", "raise", "jam"] as const;

function getActionKeys(step: SparringStep): readonly string[] {
  // Primary signal: facing_bet from the DB
  if (step.facing_bet !== null) {
    return step.facing_bet > 0 ? ACTION_KEYS_FACING : ACTION_KEYS_NO_FACING;
  }
  // Fallback: infer from best_action — doesn't reveal which is correct,
  // only mirrors the game reality the player already sees on the table
  if (["call", "raise"].includes(step.best_action)) return ACTION_KEYS_FACING;
  if (["check", "bet"].includes(step.best_action))  return ACTION_KEYS_NO_FACING;
  return ACTION_KEYS_ALL;
}
const STREETS = ["preflop", "flop", "turn", "river"] as const;

// ── Card parser ───────────────────────────────────────────────────────────────

function parseCards(raw: string | null): CardData[] {
  if (!raw) return [];
  const SUITS = ["s", "h", "d", "c"];
  if (raw.trim().startsWith("[")) {
    try { return (JSON.parse(raw) as string[]).flatMap((t) => parseCards(t)); }
    catch { return []; }
  }
  const tokens: string[] = [];
  const str = raw.replace(/\s+/g, "");
  let i = 0;
  while (i < str.length) {
    const two = str.slice(i, i + 2);
    const three = str.slice(i, i + 3);
    if (three.length === 3 && SUITS.includes(three[2].toLowerCase()) && two === "10") {
      tokens.push(three); i += 3;
    } else if (two.length === 2 && SUITS.includes(two[1].toLowerCase())) {
      tokens.push(two); i += 2;
    } else { i++; }
  }
  return tokens.flatMap((token) => {
    const suit = token.slice(-1).toLowerCase() as "s" | "h" | "d" | "c";
    const rank = token.slice(0, -1).toUpperCase();
    if (!SUITS.includes(suit) || !rank) return [];
    return [{ rank, suit }];
  });
}

// ── Poker table builder ───────────────────────────────────────────────────────
// Hero is index 0 → bottom-center of PokerTable geometry (angle = π/2)
// Villain stacks are estimated at 100 BB (we only have hero's stack from the API)

const DUMMY_CARD: CardData = { rank: "A", suit: "s" };

interface TableState { seats: Seat[]; pot: number; bb: number }


function buildSparringTable(
  step: SparringStep,
  heroCards: CardData[],
  replayStep: ReplayStep | null,
): TableState {
  // ── Real data path: replay step available ────────────────────────────────
  if (replayStep) {
    const foldedSet = new Set(replayStep.folded ?? []);
    const heroName  = replayStep.hero;
    const entries   = Object.entries(replayStep.seats)
      .sort(([a], [b]) => parseInt(a) - parseInt(b));
    const heroEntry = entries.find(([, sd]) => sd.player === heroName);

    if (heroEntry) {
      const [heroSeatNum] = heroEntry;
      const seats: Seat[] = [];

      // Hero always first → bottom-center of PokerTable geometry
      seats.push({
        id: 0,
        name: step.position ? `You (${step.position})` : "You",
        stack: heroEntry[1].stack_bb,
        hero: true,
        active: true,
        cards: heroCards.length >= 2 ? heroCards : undefined,
      });

      // Villains in seat-number order (clockwise from hero perspective)
      let idx = 1;
      for (const [seatNum, sd] of entries) {
        if (seatNum === heroSeatNum) continue;
        const betChips = replayStep.bets?.[seatNum];
        seats.push({
          id: idx++,
          name: sd.pos || `V${idx}`,
          stack: sd.stack_bb,
          cards: [DUMMY_CARD, DUMMY_CARD],
          revealed: false,
          folded: foldedSet.has(sd.player),
          bet: betChips ? betChips / replayStep.bb : undefined,
        });
      }

      // pot_bb is already in BB; bb=1 so PokerTable fmt works correctly
      return { seats, pot: replayStep.pot_bb ?? replayStep.pot / replayStep.bb, bb: 1 };
    }
  }

  // ── Fallback: approximation from sparring step only ──────────────────────
  const numPlayers  = Math.max(2, step.num_players ?? 6);
  const aggressorIdx = Math.floor(numPlayers / 2);
  const facingBet   = step.facing_bet && step.facing_bet > 0 ? step.facing_bet : undefined;
  const seats: Seat[] = [
    {
      id: 0,
      name: step.position ? `You (${step.position})` : "You",
      stack: step.stack_bb ?? 100,
      hero: true,
      active: true,
      cards: heroCards.length >= 2 ? heroCards : undefined,
    },
    ...Array.from({ length: numPlayers - 1 }, (_, i) => ({
      id: i + 1,
      name: `V${i + 1}`,
      stack: 100,
      cards: [DUMMY_CARD, DUMMY_CARD] as CardData[],
      revealed: false,
      bet: i + 1 === aggressorIdx ? facingBet : undefined,
    })),
  ];
  return { seats, pot: step.pot_size ?? 0, bb: 1 };
}

// ── Street timeline ───────────────────────────────────────────────────────────

interface StepResult { step: SparringStep; result: DrillSubmitResult | null }

function StreetTimeline({
  steps,
  history,
  currentIndex,
  t,
}: {
  steps: SparringStep[];
  history: StepResult[];
  currentIndex: number;
  t: (k: string) => string;
}) {
  const stepStreets = steps.map((s) => s.street);

  return (
    <div className="flex items-center gap-0">
      {stepStreets.map((street, i) => {
        const done     = i < history.length;
        const current  = i === currentIndex;
        const correct  = done && history[i]?.result?.is_correct;
        const incorrect = done && !history[i]?.result?.is_correct;

        return (
          <div key={i} className="flex items-center">
            {/* connector */}
            {i > 0 && (
              <div className={cn(
                "h-px w-8",
                done ? (correct ? "bg-emerald-500/60" : "bg-destructive/60") : "bg-border"
              )} />
            )}
            {/* dot */}
            <div className={cn(
              "flex flex-col items-center gap-1",
            )}>
              <div className={cn(
                "size-7 rounded-full border-2 flex items-center justify-center transition-all",
                current  && "border-amber-400 bg-amber-400/20 ring-2 ring-amber-400/30",
                correct  && "border-emerald-500 bg-emerald-500/20",
                incorrect && "border-destructive bg-destructive/20",
                !done && !current && "border-border bg-background",
              )}>
                {correct   && <CheckCircle2 className="size-3.5 text-emerald-400" />}
                {incorrect && <XCircle      className="size-3.5 text-destructive" />}
                {current   && <Flame        className="size-3.5 text-amber-400 animate-pulse" />}
                {!done && !current && <span className="size-1.5 rounded-full bg-border" />}
              </div>
              <span className={cn(
                "font-mono text-[8px] uppercase tracking-wider",
                current   ? "text-amber-400 font-bold" : "text-muted-foreground"
              )}>
                {t(`street.${street}`).slice(0, 3)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Previous decisions recap ──────────────────────────────────────────────────

function HandRecap({ history, t }: { history: StepResult[]; t: (k: string) => string }) {
  if (!history.length) return null;
  return (
    <div className="rounded-lg border border-border bg-hud-surface/60 px-3 py-2 space-y-1">
      <p className="font-mono text-[8px] uppercase tracking-widest text-muted-foreground/60">
        {t("historyLabel")}
      </p>
      <div className="space-y-0.5">
        {history.map(({ step, result }, i) => (
          <div key={i} className="flex items-center gap-2 font-mono text-[11px]">
            <span className="text-muted-foreground w-12 shrink-0">
              {t(`street.${step.street}`).slice(0, 3).toUpperCase()}
            </span>
            <span className={cn("font-bold", result?.is_correct ? "text-emerald-400" : "text-destructive")}>
              {formatAction(result?.new_action ?? step.action_taken).toUpperCase()}
            </span>
            {!result?.is_correct && (
              <span className="text-muted-foreground/60">
                → {formatAction(step.best_action).toUpperCase()}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Summary ───────────────────────────────────────────────────────────────────

function Summary({
  history,
  hand,
  onNewHand,
  t,
}: {
  history: StepResult[];
  hand: SparringHand;
  onNewHand: () => void;
  t: (k: string, opts?: Record<string, unknown>) => string;
}) {
  const correct = history.filter((h) => h.result?.is_correct).length;
  const total   = history.length;
  const pct     = total > 0 ? Math.round((correct / total) * 100) : 0;
  const allCorrect = correct === total;

  return (
    <div className="mx-auto max-w-lg space-y-5">
      <div className={cn(
        "rounded-xl border p-6 space-y-3 text-center",
        allCorrect ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
      )}>
        <Swords className={cn("mx-auto size-10", allCorrect ? "text-emerald-400" : "text-amber-400")} aria-hidden />
        <h2 className="text-xl font-bold text-foreground">{t("summary.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("summary.subtitle")}</p>
        {hand.tournament_name && (
          <p className="font-mono text-[10px] text-muted-foreground">{hand.tournament_name}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-hud-surface p-5 text-center">
          <p className={cn("font-mono text-3xl font-bold tabular-nums", pct >= 70 ? "text-emerald-400" : "text-amber-400")}>
            {pct}%
          </p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {t("summary.accuracy")}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-hud-surface p-5 text-center">
          <p className="font-mono text-3xl font-bold tabular-nums text-foreground">{correct}/{total}</p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {t("summary.decisions")}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        {history.map(({ step, result }, i) => (
          <div key={i} className={cn(
            "flex items-center justify-between rounded-lg border px-4 py-2.5",
            result?.is_correct
              ? "border-emerald-500/20 bg-emerald-500/5"
              : "border-destructive/20 bg-destructive/5"
          )}>
            <div className="flex items-center gap-2">
              {result?.is_correct
                ? <CheckCircle2 className="size-4 text-emerald-400 shrink-0" />
                : <XCircle      className="size-4 text-destructive shrink-0" />
              }
              <span className="font-mono text-xs text-foreground">
                {t("summary.step", { n: i + 1 })} — {t(`street.${step.street}`)}
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[10px]">
              <span className={result?.is_correct ? "text-emerald-400 font-bold" : "text-muted-foreground"}>
                {formatAction(result?.new_action ?? step.action_taken).toUpperCase()}
              </span>
              {!result?.is_correct && (
                <span className="text-emerald-400">→ {formatAction(step.best_action).toUpperCase()}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-3">
        <button
          onClick={onNewHand}
          className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-black hover:bg-amber-400 transition-colors"
        >
          <Swords className="size-4" aria-hidden />
          {t("newHand")}
        </button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const SPARRING_SEEN_KEY = "sparring_seen_hand_ids";

function getSeenHandIds(): string[] {
  try { return JSON.parse(localStorage.getItem(SPARRING_SEEN_KEY) ?? "[]"); }
  catch { return []; }
}
function saveSeenHandId(handId: string) {
  const seen = getSeenHandIds();
  if (!seen.includes(handId)) localStorage.setItem(SPARRING_SEEN_KEY, JSON.stringify([...seen, handId]));
}
function resetSeenHandIds(firstHandId: string) {
  localStorage.setItem(SPARRING_SEEN_KEY, JSON.stringify([firstHandId]));
}

export default function Sparring() {
  const { t } = useTranslation("sparring");

  const [phase, setPhase]           = useState<Phase>("idle");
  const [hand, setHand]             = useState<SparringHand | null>(null);
  const [stepIndex, setStepIndex]   = useState(0);
  const [history, setHistory]       = useState<StepResult[]>([]);
  const [currentResult, setCurrentResult] = useState<DrillSubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [analysis, setAnalysis]     = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [error, setError]           = useState("");
  // Hero-action steps from the full replay — loaded in parallel, non-blocking
  const [replayHeroSteps, setReplayHeroSteps] = useState<ReplayStep[]>([]);

  const steps   = hand?.steps ?? [];
  const current = steps[stepIndex] ?? null;
  const isLastStep = stepIndex >= steps.length - 1;

  const loadHand = async () => {
    setPhase("loading");
    setError("");
    setHistory([]);
    setStepIndex(0);
    setCurrentResult(null);
    setAnalysis(null);
    setReplayHeroSteps([]);
    try {
      const seen = getSeenHandIds();
      const data = await sparring.hand(undefined, undefined, seen);
      if (data.insufficient_data) { setError(t("noData")); setPhase("idle"); return; }
      if (data.hand_id) {
        if (seen.includes(data.hand_id)) {
          // Backend cycled through all hands — start fresh with just this one
          resetSeenHandIds(data.hand_id);
        } else {
          saveSeenHandId(data.hand_id);
        }
      }
      setHand(data);
      setPhase("playing");

      // Fetch full replay in parallel — non-blocking, enriches PokerTable when ready
      if (data.tournament_id && data.hand_id) {
        tournaments.replay(String(data.tournament_id), data.hand_id)
          .then((replay) => {
            setReplayHeroSteps(
              replay.timeline.filter((s) => s.type === "action" && s.is_hero === true)
            );
          })
          .catch(() => { /* replay failed — PokerTable stays in approximation mode */ });
      }
    } catch {
      setError(t("noData"));
      setPhase("idle");
    }
  };

  const submitAction = async (action: string) => {
    if (!current || submitting) return;
    setSubmitting(true);
    try {
      const result = await drill.submit(current.decision_id, action);
      setCurrentResult(result);
      setHistory((h) => [...h, { step: current, result }]);
      setPhase("feedback");
    } catch { /* keep playing */ }
    finally { setSubmitting(false); }
  };

  const nextStep = () => {
    setAnalysis(null);
    const next = stepIndex + 1;
    if (next >= steps.length) { setPhase("summary"); }
    else { setStepIndex(next); setCurrentResult(null); setPhase("playing"); }
  };

  const requestAnalysis = async () => {
    if (!current || analysisLoading) return;
    setAnalysisLoading(true);
    try {
      const res = await drill.analysis(current.decision_id);
      setAnalysis(res.analysis);
    } catch { setAnalysis(t("result.analysisError")); }
    finally { setAnalysisLoading(false); }
  };

  return (
    <HudLayout eyebrow="Sparring Mode" title={t("title")} description={t("subtitle")}>

      {/* ── IDLE / LOADING ───────────────────────────────────────────────────── */}
      {(phase === "idle" || phase === "loading") && (
        <div className="mx-auto max-w-lg space-y-6">

          {/* Arena card */}
          <div className="relative overflow-hidden rounded-xl border border-amber-500/30 bg-amber-500/5 p-8 text-center space-y-4">
            <div className="absolute inset-0 bg-gradient-to-b from-amber-500/5 to-transparent pointer-events-none" />
            <Swords className="mx-auto size-12 text-amber-400" aria-hidden />
            <div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-amber-400 mb-2">
                {t("arenaLabel")}
              </p>
              <p className="text-sm text-muted-foreground leading-relaxed max-w-sm mx-auto">
                {t("arenaDesc")}
              </p>
            </div>
            {/* Street flow illustration */}
            <div className="flex items-center justify-center gap-2 pt-2">
              {STREETS.map((s, i) => (
                <div key={s} className="flex items-center gap-2">
                  {i > 0 && <div className="h-px w-5 bg-amber-500/30" />}
                  <span className="font-mono text-[9px] uppercase tracking-wider text-amber-400/70 rounded-full border border-amber-500/30 px-2 py-0.5">
                    {t(`street.${s}`).slice(0, 3)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center text-sm text-destructive">
              {error}
            </p>
          )}

          <button
            onClick={loadHand}
            disabled={phase === "loading"}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-black hover:bg-amber-400 disabled:opacity-60 transition-colors"
          >
            {phase === "loading"
              ? <><Loader2 className="size-4 animate-spin" aria-hidden /> {t("loading")}</>
              : <><Swords className="size-4" aria-hidden /> {t("startBtn")}</>
            }
          </button>

        </div>
      )}

      {/* ── PLAYING ──────────────────────────────────────────────────────────── */}
      {phase === "playing" && current && (
        <div className="mx-auto max-w-2xl space-y-4">

          {/* Street timeline */}
          <div className="flex items-start justify-between gap-4">
            <StreetTimeline steps={steps} history={history} currentIndex={stepIndex} t={t} />
            <span className="font-mono text-[10px] text-muted-foreground shrink-0 mt-1">
              {t("stepOf", { n: stepIndex + 1, total: steps.length })}
            </span>
          </div>

          {/* Previous decisions recap */}
          {history.length > 0 && <HandRecap history={history} t={t} />}

          {/* Current situation — amber scheme to distinguish from Ghost Table */}
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Flame className="size-4 shrink-0 text-amber-400" aria-hidden />
              <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-amber-400">
                {t(`street.${current.street}`)}
              </p>
              {hand?.tournament_name && (
                <span className="ml-auto font-mono text-[9px] text-muted-foreground truncate">
                  {hand.tournament_name}
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-amber-500/20 pt-2">
              {current.position && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  {t("context.position")}: <span className="text-foreground font-semibold">{current.position}</span>
                </span>
              )}
              {current.stack_bb !== null && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  Stack: <span className="text-foreground font-semibold">{t("context.bb", { n: current.stack_bb.toFixed(0) })}</span>
                </span>
              )}
              {current.m_ratio !== null && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  M: <span className="text-foreground font-semibold">{current.m_ratio.toFixed(1)}</span>
                </span>
              )}
              {current.num_players !== null && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  {t("context.players", { n: current.num_players })}
                </span>
              )}
              {current.is_3bet && (
                <span className="font-mono text-[11px] font-semibold text-amber-400">{t("context.is3bet")}</span>
              )}
              {current.pot_size !== null && current.pot_size > 0 && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  {t("context.pot")}: <span className="text-foreground font-semibold">{t("context.bb", { n: current.pot_size.toFixed(1) })}</span>
                </span>
              )}
              {current.facing_bet !== null && current.facing_bet > 0 && (
                <span className="font-mono text-[11px] text-amber-400 font-semibold">
                  {t("context.facing")}: {t("context.bb", { n: current.facing_bet.toFixed(1) })}
                </span>
              )}
              {current.icm_pressure && current.icm_pressure !== "none" && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  ICM: <span className={cn("font-semibold", {
                    "text-destructive": current.icm_pressure === "high",
                    "text-amber-400":   current.icm_pressure === "medium",
                    "text-emerald-400": current.icm_pressure === "low",
                  })}>{t(`icmLabel.${current.icm_pressure}`)}</span>
                </span>
              )}
            </div>
          </div>

          {/* Poker table — hero at bottom, real replay data when available */}
          {(() => {
            const boardLimit = { preflop: 0, flop: 3, turn: 4, river: 5 }[current.street] ?? 5;
            const communityCards = parseCards(current.board).slice(0, boardLimit);
            const heroCards      = parseCards(current.hero_cards);
            const replayStep     = replayHeroSteps[stepIndex] ?? null;
            const { seats, pot, bb } = buildSparringTable(current, heroCards, replayStep);
            return (
              <PokerTable
                seats={seats}
                community={communityCards}
                pot={pot}
                street={current.street}
                bb={bb}
                betUnit="bb"
              />
            );
          })()}

          {/* Question */}
          <p className="text-center text-sm font-semibold text-foreground">{t("question")}</p>

          {/* Action buttons — context-aware set derived from facing_bet or best_action */}
          {(() => {
            const actionKeys = getActionKeys(current);
            const cols = actionKeys.length === 4 ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-3 sm:grid-cols-6";
            return (
              <div className={`grid gap-3 ${cols}`}>
                {actionKeys.map((action) => (
                  <button
                    key={action}
                    onClick={() => submitAction(action)}
                    disabled={submitting}
                    className="min-h-[44px] rounded-lg border border-border bg-hud-surface px-3 py-3 font-mono text-xs font-bold uppercase tracking-wider text-foreground ring-1 ring-border hover:border-amber-500/60 hover:bg-amber-500/5 hover:text-amber-400 hover:ring-amber-500/40 disabled:opacity-60 transition-all active:scale-95"
                  >
                    {t(`actions.${action}`)}
                  </button>
                ))}
              </div>
            );
          })()}
        </div>
      )}

      {/* ── FEEDBACK ─────────────────────────────────────────────────────────── */}
      {phase === "feedback" && currentResult && current && (
        <div className="mx-auto max-w-lg space-y-4">

          {/* Timeline still visible */}
          <div className="flex justify-center">
            <StreetTimeline steps={steps} history={history} currentIndex={-1} t={t} />
          </div>

          {/* Frozen table — same hand state, gives context while reading feedback */}
          {(() => {
            const boardLimit = { preflop: 0, flop: 3, turn: 4, river: 5 }[current.street] ?? 5;
            const communityCards = parseCards(current.board).slice(0, boardLimit);
            const heroCards      = parseCards(current.hero_cards);
            const replayStep     = replayHeroSteps[stepIndex] ?? null;
            const { seats, pot, bb } = buildSparringTable(current, heroCards, replayStep);
            return (
              <PokerTable
                seats={seats}
                community={communityCards}
                pot={pot}
                street={current.street}
                bb={bb}
                betUnit="bb"
              />
            );
          })()}

          {/* Result banner */}
          <div className={cn(
            "flex items-center gap-4 rounded-xl border p-5",
            currentResult.is_correct
              ? "border-emerald-500/40 bg-emerald-500/5"
              : "border-destructive/40 bg-destructive/5"
          )}>
            {currentResult.is_correct
              ? <CheckCircle2 className="size-9 shrink-0 text-emerald-400" aria-hidden />
              : <XCircle      className="size-9 shrink-0 text-destructive" aria-hidden />
            }
            <div>
              <p className={cn("text-lg font-bold", currentResult.is_correct ? "text-emerald-400" : "text-destructive")}>
                {currentResult.is_correct ? t("result.correct") : t("result.wrong")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("result.bestAction", { action: formatAction(currentResult.best_action).toUpperCase() })}
              </p>
            </div>
          </div>

          {/* Your vs best */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-hud-surface p-4">
              <p className="font-mono text-[10px] uppercase text-muted-foreground">{t("result.yourAction", { action: "" }).split(":")[0]}</p>
              <p className="mt-1 font-mono text-xl font-bold text-foreground">{formatAction(currentResult.new_action).toUpperCase()}</p>
            </div>
            <div className="rounded-lg border border-border bg-hud-surface p-4">
              <p className="font-mono text-[10px] uppercase text-muted-foreground">{t("result.bestAction", { action: "" }).split(":")[0]}</p>
              <p className="mt-1 font-mono text-xl font-bold text-foreground">{formatAction(currentResult.best_action).toUpperCase()}</p>
            </div>
          </div>

          {/* Delta — label cruzado com is_correct para evitar "Erro mantido" em acertos */}
          <div className={cn(
            "flex items-center justify-between rounded-lg border p-4",
            currentResult.delta < 0 || currentResult.is_correct
              ? "border-emerald-500/30 bg-emerald-500/5"
              : "border-border bg-hud-surface"
          )}>
            <div className="flex items-center gap-2">
              <TrendingUp className="size-4 text-muted-foreground" aria-hidden />
              <span className="text-sm text-muted-foreground">
                {currentResult.delta < 0
                  ? t("result.improvement", { delta: Math.abs(currentResult.delta).toFixed(3) })
                  : currentResult.is_correct
                  ? t("result.residualScore")
                  : t("result.noImprovement")
                }
              </span>
            </div>
            <span className={cn(
              "font-mono text-sm font-bold tabular-nums",
              currentResult.delta < 0 || currentResult.is_correct ? "text-emerald-400" : "text-destructive"
            )}>
              {currentResult.delta > 0 ? "+" : ""}{currentResult.delta.toFixed(3)}
            </span>
          </div>

          {/* SRS */}
          {currentResult.srs_interval_days && (
            <div className={cn(
              "flex items-center gap-2 rounded-lg border px-4 py-2.5",
              currentResult.is_correct
                ? "border-amber-500/30 bg-amber-500/5 text-amber-400"
                : "border-warning/30 bg-warning/5 text-warning"
            )}>
              <span className="font-mono text-[11px]">
                {currentResult.is_correct
                  ? t("result.srsCorrect", { n: currentResult.srs_interval_days })
                  : t("result.srsReset",   { n: currentResult.srs_interval_days })
                }
              </span>
            </div>
          )}

          {/* Analysis */}
          {analysis ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 space-y-2">
              <p className="font-mono text-[9px] uppercase tracking-widest text-amber-400">{t("result.engineNote")}</p>
              <p className="text-sm leading-relaxed text-foreground whitespace-pre-line">{analysis}</p>
            </div>
          ) : (
            <button
              onClick={requestAnalysis}
              disabled={analysisLoading}
              className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-5 py-3 font-mono text-sm font-semibold text-muted-foreground hover:border-amber-500/40 hover:text-amber-400 hover:bg-amber-500/5 disabled:opacity-60 transition-colors"
            >
              {analysisLoading
                ? <><Loader2 className="size-4 animate-spin" aria-hidden /> {t("result.analysisLoading")}</>
                : <><BookOpen className="size-4" aria-hidden /> {t("result.requestAnalysis")}</>
              }
            </button>
          )}

          {/* Next / Summary */}
          <button
            onClick={nextStep}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-black hover:bg-amber-400 transition-colors"
          >
            {isLastStep ? t("viewSummary") : t("next")}
            <ArrowRight className="size-4" aria-hidden />
          </button>
        </div>
      )}

      {/* ── SUMMARY ──────────────────────────────────────────────────────────── */}
      {phase === "summary" && hand && (
        <Summary history={history} hand={hand} onNewHand={loadHand} t={t} />
      )}

    </HudLayout>
  );
}
