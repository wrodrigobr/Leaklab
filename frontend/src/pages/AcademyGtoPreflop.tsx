import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Shield,
  XCircle,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PlayingCard } from "@/components/hud/PlayingCard";
import type { CardData } from "@/components/hud/PlayingCard";
import { gtoPreflop } from "@/lib/api";
import type { GtoPreflopQuestion, GtoPreflopVerdict } from "@/lib/api";
import { cn } from "@/lib/utils";

type Phase = "loading" | "question" | "feedback" | "error";
type Scenario = "mixed" | "rfi" | "vs_rfi" | "vs_3bet";

const FREQ_LABEL: Record<string, string> = {
  raise: "raise", call: "call", allin: "all-in", fold: "fold",
};
const FREQ_COLOR: Record<string, string> = {
  raise: "bg-emerald-500", call: "bg-sky-500", allin: "bg-violet-500", fold: "bg-muted-foreground/40",
};

export default function AcademyGtoPreflop() {
  const { t } = useTranslation("academy");
  const [params] = useSearchParams();
  const scenario = ((params.get("scenario") as Scenario) || "mixed");

  const [phase, setPhase]               = useState<Phase>("loading");
  const [question, setQuestion]         = useState<GtoPreflopQuestion | null>(null);
  const [verdict, setVerdict]           = useState<GtoPreflopVerdict | null>(null);
  const [selected, setSelected]         = useState<string | null>(null);
  const [streak, setStreak]             = useState(0);
  const [totalDone, setTotalDone]       = useState(0);
  const [totalCorrect, setTotalCorrect] = useState(0);

  const loadQuestion = useCallback(async () => {
    setPhase("loading");
    setSelected(null);
    setVerdict(null);
    try {
      const timeout = new Promise<never>((_, rej) =>
        setTimeout(() => rej(new Error("timeout")), 12000)
      );
      const q = await Promise.race([gtoPreflop.question(scenario), timeout]);
      setQuestion(q);
      setPhase("question");
    } catch {
      setPhase("error");
    }
  }, [scenario]);

  useEffect(() => { loadQuestion(); }, [loadQuestion]);

  const submitAnswer = async (action: string) => {
    if (!question || phase !== "question") return;
    setSelected(action);
    setPhase("loading");
    try {
      const v = await gtoPreflop.submit(question.spot, action, question.xp_value);
      setVerdict(v);
      setTotalDone((n) => n + 1);
      if (v.is_correct) {
        setStreak((s) => s + 1);
        setTotalCorrect((n) => n + 1);
      } else {
        setStreak(0);
      }
      setPhase("feedback");
    } catch {
      setPhase("error");
    }
  };

  const accuracy   = totalDone > 0 ? Math.round((totalCorrect / totalDone) * 100) : null;
  const heroCards: CardData[] =
    question?.hero_cards?.map((c) => ({ rank: c.rank, suit: c.suit as CardData["suit"] })) ?? [];

  const freqEntries = verdict
    ? Object.entries(verdict.hand_freq || {}).filter(([, v]) => v && v > 0.01).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <HudLayout
      eyebrow={t("gtoPreflop.eyebrow")}
      title={t("gtoPreflop.title")}
      description={t("gtoPreflop.subtitle")}
    >
      <div className="mx-auto max-w-3xl space-y-6">

        {/* Stats bar */}
        {totalDone > 0 && (
          <div className="flex items-center justify-center gap-6 rounded-lg border border-border bg-hud-surface px-5 py-3">
            <div className="text-center">
              <p className="font-mono text-lg font-bold tabular-nums text-foreground">{totalDone}</p>
              <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">{t("stats.done")}</p>
            </div>
            <div className="h-6 w-px bg-border" />
            <div className="text-center">
              <p className={cn("font-mono text-lg font-bold tabular-nums", accuracy !== null && accuracy >= 70 ? "text-emerald-400" : "text-amber-400")}>
                {accuracy}%
              </p>
              <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">{t("stats.accuracy")}</p>
            </div>
            <div className="h-6 w-px bg-border" />
            <div className="text-center">
              <p className={cn("font-mono text-lg font-bold tabular-nums", streak >= 3 ? "text-amber-400" : "text-foreground")}>
                {streak}🔥
              </p>
              <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">{t("stats.streak")}</p>
            </div>
          </div>
        )}

        {/* Loading */}
        {phase === "loading" && (
          <div className="flex flex-col items-center gap-4 py-16">
            <Loader2 className="size-8 animate-spin text-amber-400" aria-hidden />
            <p className="font-mono text-xs text-muted-foreground uppercase tracking-widest">{t("loading")}</p>
          </div>
        )}

        {/* Error */}
        {phase === "error" && (
          <div className="flex flex-col items-center gap-4 rounded-xl border border-destructive/30 bg-destructive/5 p-8">
            <XCircle className="size-10 text-destructive" aria-hidden />
            <p className="text-sm text-muted-foreground">{t("loadError")}</p>
            <button
              onClick={loadQuestion}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-hud-surface px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground hover:bg-amber-500/5 transition-colors"
            >
              <RefreshCw className="size-3.5" aria-hidden />
              {t("retry")}
            </button>
          </div>
        )}

        {/* Question + Feedback */}
        {(phase === "question" || phase === "feedback") && question && (
          <div className={cn(
            "gap-5",
            phase === "feedback" ? "grid grid-cols-1 md:grid-cols-[1fr_280px]" : "flex flex-col",
          )}>

            {/* Left: spot card + options */}
            <div className="space-y-4 min-w-0">
              <div className="rounded-xl border border-border bg-hud-surface p-6 space-y-5">
                <div className="flex items-center gap-2">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-amber-500/10 ring-1 ring-amber-500/30 text-amber-400">
                    <Shield className="size-4" aria-hidden />
                  </div>
                  <span className="font-mono text-[9px] uppercase tracking-widest text-amber-400">
                    {t(`qtypes.${question.type}`, question.type)}
                  </span>
                </div>

                {/* Hero cards */}
                {heroCards.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">{t("board.heroLabel")}</p>
                    <div className="flex gap-1.5">
                      {heroCards.map((cd, i) => <PlayingCard key={i} card={cd} size="md" />)}
                    </div>
                  </div>
                )}

                {/* Context + prompt */}
                <div className="border-t border-border pt-4 space-y-2">
                  <p className="text-sm text-foreground leading-relaxed">{question.context}</p>
                  <p className="font-mono text-xs uppercase tracking-wider text-amber-400">{question.prompt}</p>
                </div>
              </div>

              {/* Options */}
              <div className="space-y-2">
                {question.options.map((opt) => {
                  const isSelected = selected === opt.action;
                  const showResult = phase === "feedback" && verdict;
                  const isBest     = showResult && verdict!.best_action === opt.action;
                  const isRec      = showResult && (verdict!.recommended || []).includes(opt.action);
                  return (
                    <button
                      key={opt.action}
                      onClick={() => submitAnswer(opt.action)}
                      disabled={phase !== "question"}
                      className={cn(
                        "w-full rounded-lg border px-5 py-3.5 text-left font-mono text-sm font-semibold transition-all",
                        phase === "question" && "border-border bg-hud-surface hover:border-amber-500/40 hover:bg-amber-500/5 hover:text-amber-400",
                        showResult && isRec      && "border-emerald-500/60 bg-emerald-500/10 text-emerald-400",
                        showResult && isSelected && !isRec && "border-destructive/60 bg-destructive/10 text-destructive",
                        showResult && !isSelected && !isRec && "border-border/40 opacity-40",
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-xs">{opt.label}</span>
                        {showResult && isBest && <CheckCircle2 className="ml-auto size-4 text-emerald-400 shrink-0" aria-hidden />}
                        {showResult && isSelected && !isRec && <XCircle className="ml-auto size-4 text-destructive shrink-0" aria-hidden />}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Right: feedback */}
            {phase === "feedback" && verdict && (
              <div className="flex flex-col gap-3">
                <div className={cn(
                  "flex-1 rounded-xl border p-5 space-y-3",
                  verdict.is_correct ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5",
                )}>
                  <div className="flex items-center gap-2">
                    {verdict.is_correct
                      ? <CheckCircle2 className="size-5 text-emerald-400 shrink-0" aria-hidden />
                      : <XCircle className="size-5 text-amber-400 shrink-0" aria-hidden />}
                    <span className={cn("font-mono text-xs font-bold uppercase tracking-wider",
                      verdict.is_correct ? "text-emerald-400" : "text-amber-400")}>
                      {verdict.is_correct ? t("feedback.correct") : t("feedback.wrong")}
                    </span>
                    {verdict.xp_awarded > 0 && (
                      <span className="ml-auto font-mono text-[10px] text-emerald-400">+{verdict.xp_awarded} XP</span>
                    )}
                  </div>

                  {/* GTO frequency breakdown for the hand */}
                  {freqEntries.length > 0 && (
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
                  )}

                  <p className="text-sm text-muted-foreground leading-relaxed">{verdict.explanation}</p>
                </div>

                <button
                  onClick={loadQuestion}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-3 font-mono text-sm font-bold uppercase tracking-widest text-black transition-colors hover:bg-amber-400"
                >
                  <ArrowRight className="size-4" aria-hidden />
                  {t("nextQuestion")}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </HudLayout>
  );
}
