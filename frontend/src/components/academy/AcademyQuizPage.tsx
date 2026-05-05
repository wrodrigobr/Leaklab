import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { HudLayout } from "@/components/hud/HudLayout";
import { PlayingCard } from "@/components/hud/PlayingCard";
import type { CardData } from "@/components/hud/PlayingCard";
import type { AcademyQuestion } from "@/lib/api";
import { cn } from "@/lib/utils";

type Phase = "loading" | "question" | "feedback" | "error";

export function MdText({ children }: { children: string }) {
  return (
    <span>
      {children.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
        part.startsWith("**") && part.endsWith("**")
          ? <strong key={i}>{part.slice(2, -2)}</strong>
          : part.split("\n").map((line, j, arr) => (
              <span key={`${i}-${j}`}>{line}{j < arr.length - 1 && <br />}</span>
            ))
      )}
    </span>
  );
}

function toCardData(c: { rank: string; suit: string }): CardData {
  return { rank: c.rank, suit: c.suit as CardData["suit"] };
}

interface ThemeColors {
  icon: string;
  badge: string;
  nextBtn: string;
  hover: string;
}

const THEMES: Record<string, ThemeColors> = {
  emerald: {
    icon:    "bg-emerald-500/10 ring-1 ring-emerald-500/30 text-emerald-400",
    badge:   "text-emerald-400",
    nextBtn: "bg-emerald-500 hover:bg-emerald-400 text-black",
    hover:   "hover:border-emerald-500/40 hover:bg-emerald-500/5 hover:text-emerald-400",
  },
  primary: {
    icon:    "bg-primary/10 ring-1 ring-primary/30 text-primary",
    badge:   "text-primary",
    nextBtn: "bg-primary hover:bg-primary/90 text-primary-foreground",
    hover:   "hover:border-primary/40 hover:bg-primary/5 hover:text-primary",
  },
  amber: {
    icon:    "bg-amber-500/10 ring-1 ring-amber-500/30 text-amber-400",
    badge:   "text-amber-400",
    nextBtn: "bg-amber-500 hover:bg-amber-400 text-black",
    hover:   "hover:border-amber-500/40 hover:bg-amber-500/5 hover:text-amber-400",
  },
  violet: {
    icon:    "bg-violet-500/10 ring-1 ring-violet-500/30 text-violet-400",
    badge:   "text-violet-400",
    nextBtn: "bg-violet-500 hover:bg-violet-400 text-white",
    hover:   "hover:border-violet-500/40 hover:bg-violet-500/5 hover:text-violet-400",
  },
};

interface Props {
  eyebrow: string;
  title: string;
  description: string;
  theme?: keyof typeof THEMES;
  Icon: React.ElementType;
  loadFn: () => Promise<AcademyQuestion>;
  submitFn: (idx: number, correctIdx: number, xp: number) => void;
  showCards?: boolean;
}

export default function AcademyQuizPage({
  eyebrow,
  title,
  description,
  theme = "emerald",
  Icon,
  loadFn,
  submitFn,
  showCards = false,
}: Props) {
  const { t } = useTranslation("academy");
  const c = THEMES[theme];

  const [phase, setPhase]               = useState<Phase>("loading");
  const [question, setQuestion]         = useState<AcademyQuestion | null>(null);
  const [selected, setSelected]         = useState<number | null>(null);
  const [isCorrect, setIsCorrect]       = useState<boolean | null>(null);
  const [streak, setStreak]             = useState(0);
  const [totalDone, setTotalDone]       = useState(0);
  const [totalCorrect, setTotalCorrect] = useState(0);

  const loadQuestion = useCallback(async () => {
    setPhase("loading");
    setSelected(null);
    setIsCorrect(null);
    try {
      const timeout = new Promise<never>((_, rej) =>
        setTimeout(() => rej(new Error("timeout")), 12000)
      );
      const q = await Promise.race([loadFn(), timeout]);
      setQuestion(q);
      setPhase("question");
    } catch {
      setPhase("error");
    }
  }, [loadFn]);

  useEffect(() => { loadQuestion(); }, [loadQuestion]);

  const submitAnswer = (idx: number) => {
    if (!question || phase !== "question") return;
    const correct = idx === question.correct_index;
    setSelected(idx);
    setIsCorrect(correct);
    setTotalDone((n) => n + 1);
    if (correct) {
      setStreak((s) => s + 1);
      setTotalCorrect((n) => n + 1);
    } else {
      setStreak(0);
    }
    setPhase("feedback");
    submitFn(idx, question.correct_index, question.xp_value);
  };

  const accuracy = totalDone > 0 ? Math.round((totalCorrect / totalDone) * 100) : null;
  const heroCards  = question?.hero_cards?.map(toCardData)  ?? [];
  const boardCards = question?.board_cards?.map(toCardData) ?? [];

  return (
    <HudLayout eyebrow={eyebrow} title={title} description={description}>
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
            <Loader2 className="size-8 animate-spin text-primary" aria-hidden />
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
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-hud-surface px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-foreground hover:bg-primary/5 transition-colors"
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
            phase === "feedback"
              ? "grid grid-cols-1 md:grid-cols-[1fr_260px]"
              : "flex flex-col",
          )}>

            {/* Left column: question card + options */}
            <div className="space-y-4 min-w-0">

              {/* Question card */}
              <div className="rounded-xl border border-border bg-hud-surface p-6 space-y-5">
                <div className="flex items-center gap-2">
                  <div className={cn("flex size-8 items-center justify-center rounded-lg", c.icon)}>
                    <Icon className="size-4" aria-hidden />
                  </div>
                  <span className={cn("font-mono text-[9px] uppercase tracking-widest", c.badge)}>
                    {t(`qtypes.${question.type}`, question.type)}
                  </span>
                </div>

                {/* Board cards (only for board-strength modules) */}
                {showCards && boardCards.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">{t("board.boardLabel")}</p>
                    <div className="flex gap-1.5">
                      {boardCards.map((c, i) => <PlayingCard key={i} card={c} size="md" />)}
                      {Array.from({ length: Math.max(0, 5 - boardCards.length) }).map((_, i) => (
                        <PlayingCard key={`ph-${i}`} size="md" hidden />
                      ))}
                    </div>
                  </div>
                )}

                {showCards && heroCards.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/60">{t("board.heroLabel")}</p>
                    <div className="flex gap-1.5">
                      {heroCards.map((cd, i) => <PlayingCard key={i} card={cd} size="md" />)}
                    </div>
                  </div>
                )}

                {/* Question text */}
                <div className={showCards && (boardCards.length > 0 || heroCards.length > 0) ? "border-t border-border pt-4" : ""}>
                  <p className="text-sm text-foreground leading-relaxed">
                    <MdText>{showCards ? (question.question.split('\n').pop() ?? question.question) : question.question}</MdText>
                  </p>
                </div>
              </div>

              {/* Options */}
              <div className="space-y-2">
                {question.options.map((opt, idx) => {
                  const isSelected = selected === idx;
                  const isRight    = idx === question.correct_index;
                  const showResult = phase === "feedback";
                  return (
                    <button
                      key={idx}
                      onClick={() => submitAnswer(idx)}
                      disabled={phase === "feedback"}
                      className={cn(
                        "w-full rounded-lg border px-5 py-3.5 text-left font-mono text-sm font-semibold transition-all",
                        phase === "question" && `border-border bg-hud-surface ${c.hover}`,
                        showResult && isRight    && "border-emerald-500/60 bg-emerald-500/10 text-emerald-400",
                        showResult && isSelected && !isRight && "border-destructive/60 bg-destructive/10 text-destructive",
                        showResult && !isSelected && !isRight && "border-border/40 opacity-40",
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-current font-mono text-[10px]">
                          {String.fromCharCode(65 + idx)}
                        </span>
                        <span className="text-xs">{opt}</span>
                        {showResult && isRight    && <CheckCircle2 className="ml-auto size-4 text-emerald-400 shrink-0" aria-hidden />}
                        {showResult && isSelected && !isRight && <XCircle className="ml-auto size-4 text-destructive shrink-0" aria-hidden />}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Right column: feedback + next button (feedback phase only) */}
            {phase === "feedback" && (
              <div className="flex flex-col gap-3">

                {/* Feedback box */}
                <div className={cn(
                  "flex-1 rounded-xl border p-5 space-y-3",
                  isCorrect ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5",
                )}>
                  <div className="flex items-center gap-2">
                    {isCorrect
                      ? <CheckCircle2 className="size-5 text-emerald-400 shrink-0" aria-hidden />
                      : <XCircle      className="size-5 text-amber-400 shrink-0" aria-hidden />}
                    <span className={cn("font-mono text-xs font-bold uppercase tracking-wider",
                      isCorrect ? "text-emerald-400" : "text-amber-400")}>
                      {isCorrect ? t("feedback.correct") : t("feedback.wrong")}
                    </span>
                    {isCorrect && (
                      <span className="ml-auto font-mono text-[10px] text-emerald-400">
                        +{question.xp_value} XP
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    <MdText>{question.explanation}</MdText>
                  </p>
                  {!isCorrect && question.mental_tip && (
                    <div className="rounded-lg border border-sky-500/30 bg-sky-500/5 px-4 py-3 space-y-1">
                      <p className="font-mono text-[9px] uppercase tracking-widest text-sky-400">{t("feedback.mentalTip")}</p>
                      <p className="text-xs text-sky-300/90 leading-relaxed">
                        <MdText>{question.mental_tip}</MdText>
                      </p>
                    </div>
                  )}
                </div>

                {/* Next button */}
                <button
                  onClick={loadQuestion}
                  className={cn(
                    "w-full inline-flex items-center justify-center gap-2 rounded-lg px-4 py-3 font-mono text-sm font-bold uppercase tracking-widest transition-colors",
                    c.nextBtn,
                  )}
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
