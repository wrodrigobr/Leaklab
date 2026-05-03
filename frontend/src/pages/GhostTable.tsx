import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  Swords,
  Target,
  TrendingUp,
  XCircle,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PlayingCard } from "@/components/hud/PlayingCard";
import type { CardData } from "@/components/hud/PlayingCard";
import { drill } from "@/lib/api";
import type { DrillSpot, DrillStats, DrillSubmitResult } from "@/lib/api";
import { cn } from "@/lib/utils";

type Phase = "intro" | "loading" | "active" | "result" | "done";

const ACTION_KEYS = ["fold", "check", "call", "bet", "raise", "jam"] as const;

const ICM_COLORS: Record<string, string> = {
  high:   "text-destructive bg-destructive/10 ring-destructive/30",
  medium: "text-warning bg-warning/10 ring-warning/30",
  low:    "text-primary bg-primary/10 ring-primary/30",
  none:   "text-muted-foreground bg-secondary ring-border",
};

function parseCards(raw: string | null): CardData[] {
  if (!raw) return [];
  return raw.trim().split(/\s+/).flatMap((token) => {
    if (token.length < 2) return [];
    const rank = token.slice(0, -1);
    const suit = token.slice(-1).toLowerCase() as "s" | "h" | "d" | "c";
    if (!["s", "h", "d", "c"].includes(suit)) return [];
    return [{ rank, suit }];
  });
}

function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-border bg-hud-surface p-4 text-center">
      <p className="font-mono text-2xl font-bold tabular-nums text-foreground">{value}</p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
    </div>
  );
}

export default function GhostTable() {
  const { t } = useTranslation("ghost");

  const [phase, setPhase]                   = useState<Phase>("intro");
  const [spots, setSpots]                   = useState<DrillSpot[]>([]);
  const [stats, setStats]                   = useState<DrillStats | null>(null);
  const [index, setIndex]                   = useState(0);
  const [lastResult, setLastResult]         = useState<DrillSubmitResult | null>(null);
  const [sessionCorrect, setSessionCorrect] = useState(0);
  const [sessionTotal, setSessionTotal]     = useState(0);
  const [loadError, setLoadError]           = useState("");
  const [submitting, setSubmitting]         = useState(false);

  const current = spots[index] ?? null;

  const startDrill = async () => {
    setPhase("loading");
    setLoadError("");
    try {
      const data = await drill.spots({ limit: 10 });
      setStats(data.stats);
      if (!data.spots.length) {
        setPhase("intro");
        return;
      }
      setSpots(data.spots);
      setIndex(0);
      setSessionCorrect(0);
      setSessionTotal(0);
      setLastResult(null);
      setPhase("active");
    } catch {
      setLoadError(t("errorLoad"));
      setPhase("intro");
    }
  };

  const submitAction = async (action: string) => {
    if (!current || submitting) return;
    setSubmitting(true);
    try {
      const result = await drill.submit(current.id, action);
      if (result.is_correct) setSessionCorrect((c) => c + 1);
      setSessionTotal((n) => n + 1);
      setLastResult(result);
      setPhase("result");
    } catch {
      // keep active phase on error
    } finally {
      setSubmitting(false);
    }
  };

  const nextSpot = () => {
    const next = index + 1;
    if (next >= spots.length) {
      setPhase("done");
    } else {
      setIndex(next);
      setLastResult(null);
      setPhase("active");
    }
  };

  const resetDrill = () => {
    setPhase("intro");
    setSpots([]);
    setIndex(0);
    setLastResult(null);
    setSessionCorrect(0);
    setSessionTotal(0);
  };

  const accuracy = sessionTotal > 0 ? Math.round((sessionCorrect / sessionTotal) * 100) : 0;

  return (
    <HudLayout eyebrow="Ghost Table" title={t("title")} description={t("subtitle")}>

      {/* ── INTRO / LOADING ──────────────────────────────────────────────────── */}
      {(phase === "intro" || phase === "loading") && (
        <div className="mx-auto max-w-lg space-y-6">
          {stats && (
            <div className="grid grid-cols-3 gap-3">
              <StatTile value={String(stats.total)} label={t("stats.title").replace(/\s*\(.*\)/, "")} />
              <StatTile
                value={stats.accuracy !== null ? `${Math.round(stats.accuracy * 100)}%` : "—"}
                label={t("stats.accuracy", { pct: "" }).split("%")[0].trim().replace("{{pct}}", "").trim() || "Accuracy"}
              />
              <StatTile
                value={stats.avg_delta !== null ? (stats.avg_delta > 0 ? `+${stats.avg_delta.toFixed(2)}` : stats.avg_delta.toFixed(2)) : "—"}
                label="Δ avg"
              />
            </div>
          )}

          {stats && stats.total === 0 && !loadError && (
            <p className="rounded-lg border border-border bg-hud-surface p-5 text-center text-sm text-muted-foreground">
              {t("noSpots")}
            </p>
          )}

          {loadError && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center text-sm text-destructive">
              {loadError}
            </p>
          )}

          <button
            onClick={startDrill}
            disabled={phase === "loading"}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow disabled:opacity-60 transition-colors"
          >
            {phase === "loading"
              ? <><Loader2 className="size-4 animate-spin" aria-hidden /> {t("loading")}</>
              : <><Target className="size-4" aria-hidden /> {t("startBtn")}</>
            }
          </button>
        </div>
      )}

      {/* ── ACTIVE ───────────────────────────────────────────────────────────── */}
      {phase === "active" && current && (
        <div className="mx-auto max-w-2xl space-y-5">
          {/* Progress bar */}
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-muted-foreground shrink-0">
              {t("spot", { n: index + 1, total: spots.length })}
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${((index + 1) / spots.length) * 100}%` }}
              />
            </div>
            <span className="font-mono text-xs text-muted-foreground shrink-0">
              {sessionCorrect}/{sessionTotal}
            </span>
          </div>

          {/* Spot context card */}
          <article className="rounded-xl border border-border bg-hud-surface p-5 space-y-4">
            {/* Badges */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-md bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary ring-1 ring-primary/30">
                {t(`street.${current.street}`)}
              </span>
              {current.icm_pressure && current.icm_pressure !== "none" && (
                <span className={cn(
                  "inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ring-1",
                  ICM_COLORS[current.icm_pressure] ?? ICM_COLORS.none
                )}>
                  {t("context.icm")}: {t(`icmLabel.${current.icm_pressure}`)}
                </span>
              )}
              {current.position && (
                <span className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground ring-1 ring-border">
                  {t("context.position")}: {current.position}
                </span>
              )}
              {current.is_3bet && (
                <span className="inline-flex items-center rounded-md bg-warning/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-warning ring-1 ring-warning/30">
                  {t("context.is3bet")}
                </span>
              )}
            </div>

            {/* Numeric context */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {current.stack_bb !== null && (
                <div className="rounded-md border border-border bg-background p-2.5 text-center">
                  <p className="font-mono text-xs font-bold tabular-nums text-foreground">
                    {t("context.bb", { n: current.stack_bb.toFixed(0) })}
                  </p>
                  <p className="mt-0.5 font-mono text-[9px] uppercase text-muted-foreground">{t("context.stack")}</p>
                </div>
              )}
              {current.m_ratio !== null && (
                <div className="rounded-md border border-border bg-background p-2.5 text-center">
                  <p className="font-mono text-xs font-bold tabular-nums text-foreground">
                    {current.m_ratio.toFixed(1)}
                  </p>
                  <p className="mt-0.5 font-mono text-[9px] uppercase text-muted-foreground">{t("context.mRatio")}</p>
                </div>
              )}
              {current.num_players !== null && (
                <div className="rounded-md border border-border bg-background p-2.5 text-center">
                  <p className="font-mono text-xs font-bold tabular-nums text-foreground">
                    {current.num_players}
                  </p>
                  <p className="mt-0.5 font-mono text-[9px] uppercase text-muted-foreground">{t("context.players", { n: current.num_players })}</p>
                </div>
              )}
              {current.score !== undefined && (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 p-2.5 text-center">
                  <p className="font-mono text-xs font-bold tabular-nums text-destructive">
                    {current.score.toFixed(2)}
                  </p>
                  <p className="mt-0.5 font-mono text-[9px] uppercase text-muted-foreground">Score</p>
                </div>
              )}
            </div>

            {/* Hero cards */}
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
                    : <span className="font-mono text-xs text-muted-foreground">{t("noCards")}</span>
                  }
                </div>
              </div>
            )}

            {/* Board */}
            {current.board && (
              <div>
                <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {t("board")}
                </p>
                <div className="flex gap-2">
                  {parseCards(current.board).map((card, i) => (
                    <PlayingCard key={i} card={card} size="md" />
                  ))}
                </div>
              </div>
            )}

            {/* Original mistake footer */}
            <p className="font-mono text-[10px] text-muted-foreground border-t border-border pt-3">
              {t("result.originalMistake", { action: current.action_taken.toUpperCase(), score: current.score.toFixed(2) })}
            </p>
          </article>

          {/* Question prompt */}
          <p className="text-center text-sm font-semibold text-foreground">{t("question")}</p>

          {/* Action buttons */}
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

      {/* ── RESULT ───────────────────────────────────────────────────────────── */}
      {phase === "result" && lastResult && current && (
        <div className="mx-auto max-w-lg space-y-4">
          {/* Correct / Wrong banner */}
          <div className={cn(
            "flex items-center gap-4 rounded-xl border p-5",
            lastResult.is_correct
              ? "border-success/40 bg-success/5"
              : "border-destructive/40 bg-destructive/5"
          )}>
            {lastResult.is_correct
              ? <CheckCircle2 className="size-9 shrink-0 text-success" aria-hidden />
              : <XCircle className="size-9 shrink-0 text-destructive" aria-hidden />
            }
            <div>
              <p className={cn("text-lg font-bold", lastResult.is_correct ? "text-success" : "text-destructive")}>
                {lastResult.is_correct ? t("result.correct") : t("result.wrong")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("result.bestAction", { action: lastResult.best_action.toUpperCase() })}
              </p>
            </div>
          </div>

          {/* Actions comparison */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-hud-surface p-4">
              <p className="font-mono text-[10px] uppercase text-muted-foreground">{t("result.yourAction", { action: "" }).split(":")[0]}</p>
              <p className="mt-1 font-mono text-xl font-bold text-foreground">{lastResult.new_action.toUpperCase()}</p>
            </div>
            <div className="rounded-lg border border-border bg-hud-surface p-4">
              <p className="font-mono text-[10px] uppercase text-muted-foreground">{t("result.bestAction", { action: "" }).split(":")[0]}</p>
              <p className="mt-1 font-mono text-xl font-bold text-foreground">{lastResult.best_action.toUpperCase()}</p>
            </div>
          </div>

          {/* Delta row */}
          <div className={cn(
            "flex items-center justify-between rounded-lg border p-4",
            lastResult.delta < 0
              ? "border-success/30 bg-success/5"
              : "border-border bg-hud-surface"
          )}>
            <div className="flex items-center gap-2">
              <TrendingUp className="size-4 text-muted-foreground" aria-hidden />
              <span className="text-sm text-muted-foreground">
                {lastResult.delta < 0
                  ? t("result.improvement", { delta: Math.abs(lastResult.delta).toFixed(3) })
                  : t("result.noImprovement")
                }
              </span>
            </div>
            <span className={cn(
              "font-mono text-sm font-bold tabular-nums",
              lastResult.delta < 0 ? "text-success" : "text-destructive"
            )}>
              {lastResult.delta > 0 ? "+" : ""}{lastResult.delta.toFixed(3)}
            </span>
          </div>

          {/* Next button */}
          <button
            onClick={nextSpot}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors"
          >
            {t("next")} <ArrowRight className="size-4" aria-hidden />
          </button>
        </div>
      )}

      {/* ── DONE ─────────────────────────────────────────────────────────────── */}
      {phase === "done" && (
        <div className="mx-auto max-w-lg space-y-5 text-center">
          <div className="rounded-xl border border-primary/30 bg-primary/5 p-8 space-y-3">
            <Swords className="mx-auto size-12 text-primary" aria-hidden />
            <h2 className="text-xl font-bold text-foreground">{t("done")}</h2>
            <p className="text-sm text-muted-foreground">{t("doneSub")}</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-border bg-hud-surface p-5 text-center">
              <p className="font-mono text-3xl font-bold tabular-nums text-primary">{accuracy}%</p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {t("doneAccuracy", { pct: accuracy }).split(":")[0].trim()}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-hud-surface p-5 text-center">
              <p className="font-mono text-3xl font-bold tabular-nums text-foreground">
                {sessionCorrect}/{sessionTotal}
              </p>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {t("doneCorrect", { correct: sessionCorrect, total: sessionTotal })}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              to="/dashboard"
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-hud-surface px-5 py-3 font-mono text-sm font-bold uppercase tracking-wider text-foreground hover:border-primary/40 hover:bg-primary/5 transition-colors"
            >
              {t("backDashboard")}
            </Link>
            <button
              onClick={resetDrill}
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 font-mono text-sm font-bold uppercase tracking-widest-2 text-primary-foreground hover:bg-primary-glow transition-colors"
            >
              <Target className="size-4" aria-hidden /> {t("drillAgain")}
            </button>
          </div>
        </div>
      )}

    </HudLayout>
  );
}
