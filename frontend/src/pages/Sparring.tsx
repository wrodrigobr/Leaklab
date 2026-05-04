import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Loader2,
  Swords,
  TrendingUp,
  XCircle,
  Zap,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PlayingCard } from "@/components/hud/PlayingCard";
import type { CardData } from "@/components/hud/PlayingCard";
import { sparring, drill } from "@/lib/api";
import type { SparringHand, SparringStep, DrillSubmitResult } from "@/lib/api";
import { cn, formatAction } from "@/lib/utils";

type Phase = "idle" | "loading" | "playing" | "feedback" | "summary";

const ACTION_KEYS = ["fold", "check", "call", "bet", "raise", "jam"] as const;

// ── Card parser (same logic as GhostTable) ────────────────────────────────────

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

// ── History strip ─────────────────────────────────────────────────────────────

interface StepResult { step: SparringStep; result: DrillSubmitResult | null }

function HistoryStrip({ history, t }: { history: StepResult[]; t: (k: string) => string }) {
  if (!history.length) return null;
  return (
    <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-hud-surface px-3 py-2">
      <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground self-center shrink-0">
        {t("historyLabel")}
      </span>
      {history.map(({ step, result }, i) => (
        <span
          key={i}
          className={cn(
            "inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono text-[10px] font-bold",
            result?.is_correct
              ? "bg-emerald-500/15 text-emerald-400"
              : "bg-destructive/15 text-destructive"
          )}
        >
          {t(`street.${step.street}`).slice(0, 3).toUpperCase()}
          {result?.is_correct
            ? <CheckCircle2 className="size-2.5" />
            : <XCircle className="size-2.5" />
          }
        </span>
      ))}
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

  return (
    <div className="mx-auto max-w-lg space-y-5">
      <div className="rounded-xl border border-primary/30 bg-primary/5 p-6 space-y-3 text-center">
        <Swords className="mx-auto size-10 text-primary" aria-hidden />
        <h2 className="text-xl font-bold text-foreground">{t("summary.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("summary.subtitle")}</p>
        {hand.tournament_name && (
          <p className="font-mono text-[10px] text-muted-foreground">{hand.tournament_name}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-border bg-hud-surface p-5 text-center">
          <p className="font-mono text-3xl font-bold tabular-nums text-primary">{pct}%</p>
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
          <div
            key={i}
            className={cn(
              "flex items-center justify-between rounded-lg border px-4 py-2.5",
              result?.is_correct
                ? "border-emerald-500/20 bg-emerald-500/5"
                : "border-destructive/20 bg-destructive/5"
            )}
          >
            <div className="flex items-center gap-2">
              {result?.is_correct
                ? <CheckCircle2 className="size-4 text-emerald-400 shrink-0" />
                : <XCircle className="size-4 text-destructive shrink-0" />
              }
              <span className="font-mono text-xs text-foreground">
                {t("summary.step", { n: i + 1 })} — {t(`street.${step.street}`)}
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[10px]">
              <span className="text-muted-foreground">
                {formatAction(result?.new_action ?? step.action_taken).toUpperCase()}
              </span>
              {!result?.is_correct && (
                <span className="text-emerald-400">
                  → {formatAction(step.best_action).toUpperCase()}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-3">
        <button
          onClick={onNewHand}
          className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors"
        >
          <Swords className="size-4" aria-hidden />
          {t("newHand")}
        </button>
        <Link
          to="/ghost"
          className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-6 py-3 font-mono text-sm text-muted-foreground hover:border-primary/40 hover:text-primary transition-colors"
        >
          {t("backGhost")}
        </Link>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Sparring() {
  const { t } = useTranslation("sparring");

  const [phase, setPhase]       = useState<Phase>("idle");
  const [hand, setHand]         = useState<SparringHand | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [history, setHistory]   = useState<StepResult[]>([]);
  const [currentResult, setCurrentResult] = useState<DrillSubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [error, setError]       = useState("");

  const steps   = hand?.steps ?? [];
  const current = steps[stepIndex] ?? null;

  const loadHand = async () => {
    setPhase("loading");
    setError("");
    setHistory([]);
    setStepIndex(0);
    setCurrentResult(null);
    setAnalysis(null);
    try {
      const data = await sparring.hand();
      if (data.insufficient_data) {
        setError(t("noData"));
        setPhase("idle");
        return;
      }
      setHand(data);
      setPhase("playing");
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
    } catch {
      // keep playing on error
    } finally {
      setSubmitting(false);
    }
  };

  const nextStep = () => {
    setAnalysis(null);
    const next = stepIndex + 1;
    if (next >= steps.length) {
      setPhase("summary");
    } else {
      setStepIndex(next);
      setCurrentResult(null);
      setPhase("playing");
    }
  };

  const requestAnalysis = async () => {
    if (!current || analysisLoading) return;
    setAnalysisLoading(true);
    try {
      const res = await drill.analysis(current.decision_id);
      setAnalysis(res.analysis);
    } catch {
      setAnalysis(t("result.analysisError"));
    } finally {
      setAnalysisLoading(false);
    }
  };

  const isLastStep = stepIndex >= steps.length - 1;

  return (
    <HudLayout eyebrow="Sparring Mode" title={t("title")} description={t("subtitle")}>

      {/* ── IDLE / LOADING ───────────────────────────────────────────────────── */}
      {(phase === "idle" || phase === "loading") && (
        <div className="mx-auto max-w-lg space-y-5">
          {error && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-6 space-y-3 text-center">
            <Swords className="mx-auto size-10 text-primary" aria-hidden />
            <p className="text-sm text-muted-foreground leading-relaxed">{t("subtitle")}</p>
          </div>
          <button
            onClick={loadHand}
            disabled={phase === "loading"}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow disabled:opacity-60 transition-colors"
          >
            {phase === "loading"
              ? <><Loader2 className="size-4 animate-spin" aria-hidden /> {t("loading")}</>
              : <><Swords className="size-4" aria-hidden /> {t("startBtn")}</>
            }
          </button>
          <Link
            to="/ghost"
            className="block text-center font-mono text-[11px] text-muted-foreground hover:text-foreground transition-colors"
          >
            {t("backGhost")}
          </Link>
        </div>
      )}

      {/* ── PLAYING ──────────────────────────────────────────────────────────── */}
      {phase === "playing" && current && (
        <div className="mx-auto max-w-2xl space-y-4">

          {/* Progress */}
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-muted-foreground shrink-0">
              {t("stepOf", { n: stepIndex + 1, total: steps.length })}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${((stepIndex + 1) / steps.length) * 100}%` }}
              />
            </div>
          </div>

          {/* History strip */}
          <HistoryStrip history={history} t={t} />

          {/* Situation box */}
          <div className="rounded-xl border border-primary/50 bg-primary/5 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Zap className="size-4 shrink-0 text-primary" aria-hidden />
              <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-primary">
                {t(`street.${current.street}`)}
              </p>
              {hand?.tournament_name && (
                <span className="ml-auto font-mono text-[9px] text-muted-foreground truncate">
                  {hand.tournament_name}
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/60 pt-2">
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
                  M-Ratio: <span className="text-foreground font-semibold">{current.m_ratio.toFixed(1)}</span>
                </span>
              )}
              {current.num_players !== null && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  {t("context.players", { n: current.num_players })}
                </span>
              )}
              {current.is_3bet && (
                <span className="font-mono text-[11px] font-semibold text-warning">{t("context.is3bet")}</span>
              )}
              {current.pot_size !== null && current.pot_size > 0 && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  {t("context.pot")}: <span className="text-foreground font-semibold">{t("context.bb", { n: current.pot_size.toFixed(1) })}</span>
                </span>
              )}
              {current.facing_bet !== null && current.facing_bet > 0 && (
                <span className="font-mono text-[11px] text-warning font-semibold">
                  {t("context.facing")}: {t("context.bb", { n: current.facing_bet.toFixed(1) })}
                </span>
              )}
              {current.icm_pressure && current.icm_pressure !== "none" && (
                <span className="font-mono text-[11px] text-muted-foreground">
                  ICM: <span className={cn("font-semibold", {
                    "text-destructive": current.icm_pressure === "high",
                    "text-warning":     current.icm_pressure === "medium",
                    "text-primary":     current.icm_pressure === "low",
                  })}>{t(`icmLabel.${current.icm_pressure}`)}</span>
                </span>
              )}
            </div>
          </div>

          {/* Cards */}
          <article className="rounded-xl border border-border bg-hud-surface p-4 space-y-4">
            {(() => {
              const boardLimit = { preflop: 0, flop: 3, turn: 4, river: 5 }[current.street] ?? 5;
              const visibleBoard = parseCards(current.board).slice(0, boardLimit);
              return (
                <div className="flex gap-6 flex-wrap">
                  {current.hero_cards && (
                    <div>
                      <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {t("heroCards")}
                      </p>
                      <div className="flex gap-2">
                        {parseCards(current.hero_cards).length > 0
                          ? parseCards(current.hero_cards).map((card, i) => (
                              <PlayingCard key={i} card={card} size="md" />
                            ))
                          : <span className="font-mono text-xs text-muted-foreground">—</span>
                        }
                      </div>
                    </div>
                  )}
                  {visibleBoard.length > 0 && (
                    <div>
                      <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {t("board")}
                      </p>
                      <div className="flex gap-2">
                        {visibleBoard.map((card, i) => (
                          <PlayingCard key={i} card={card} size="md" />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}
          </article>

          {/* Question + action buttons */}
          <p className="text-center text-sm font-semibold text-foreground">{t("question")}</p>
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
            {ACTION_KEYS.map((action) => (
              <button
                key={action}
                onClick={() => submitAction(action)}
                disabled={submitting}
                className="rounded-lg border border-border bg-hud-surface px-3 py-3 font-mono text-xs font-bold uppercase tracking-wider text-foreground ring-1 ring-border hover:border-primary/60 hover:bg-primary/5 hover:text-primary hover:ring-primary/40 disabled:opacity-60 transition-all active:scale-95"
              >
                {t(`actions.${action}`)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── FEEDBACK ─────────────────────────────────────────────────────────── */}
      {phase === "feedback" && currentResult && current && (
        <div className="mx-auto max-w-lg space-y-4">

          {/* History strip */}
          <HistoryStrip history={history} t={t} />

          {/* Result banner */}
          <div className={cn(
            "flex items-center gap-4 rounded-xl border p-5",
            currentResult.is_correct
              ? "border-emerald-500/40 bg-emerald-500/5"
              : "border-destructive/40 bg-destructive/5"
          )}>
            {currentResult.is_correct
              ? <CheckCircle2 className="size-9 shrink-0 text-emerald-400" aria-hidden />
              : <XCircle     className="size-9 shrink-0 text-destructive" aria-hidden />
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

          {/* Your action vs best */}
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

          {/* Delta */}
          <div className={cn(
            "flex items-center justify-between rounded-lg border p-4",
            currentResult.delta < 0 ? "border-emerald-500/30 bg-emerald-500/5" : "border-border bg-hud-surface"
          )}>
            <div className="flex items-center gap-2">
              <TrendingUp className="size-4 text-muted-foreground" aria-hidden />
              <span className="text-sm text-muted-foreground">
                {currentResult.delta < 0
                  ? t("result.improvement", { delta: Math.abs(currentResult.delta).toFixed(3) })
                  : t("result.noImprovement")
                }
              </span>
            </div>
            <span className={cn("font-mono text-sm font-bold tabular-nums", currentResult.delta < 0 ? "text-emerald-400" : "text-destructive")}>
              {currentResult.delta > 0 ? "+" : ""}{currentResult.delta.toFixed(3)}
            </span>
          </div>

          {/* SRS */}
          {currentResult.srs_interval_days && (
            <div className={cn(
              "flex items-center gap-2 rounded-lg border px-4 py-2.5",
              currentResult.is_correct
                ? "border-primary/30 bg-primary/5 text-primary"
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
            <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-2">
              <p className="font-mono text-[9px] uppercase tracking-widest text-primary">{t("result.engineNote")}</p>
              <p className="text-sm leading-relaxed text-foreground whitespace-pre-line">{analysis}</p>
            </div>
          ) : (
            <button
              onClick={requestAnalysis}
              disabled={analysisLoading}
              className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-5 py-3 font-mono text-sm font-semibold text-muted-foreground hover:border-primary/40 hover:text-primary hover:bg-primary/5 disabled:opacity-60 transition-colors"
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
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors"
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
