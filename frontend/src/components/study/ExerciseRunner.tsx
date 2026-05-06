import { useMemo, useState } from "react";
import { CheckCircle2, XCircle, RotateCcw, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { AiText } from "@/components/ui/AiText";
import type { Exercise } from "./types";

interface Props {
  exercises: Exercise[];
  onProgressChange?: (correctCount: number, total: number) => void;
}

type State = Record<string, { selected?: string; revealed: boolean }>;

export function ExerciseRunner({ exercises, onProgressChange }: Props) {
  const [state, setState] = useState<State>({});

  const stats = useMemo(() => {
    let correct = 0;
    for (const ex of exercises) {
      const s = state[ex.id];
      if (s?.revealed && s.selected === ex.correctChoiceId) correct++;
    }
    return { correct, total: exercises.length };
  }, [state, exercises]);

  const submit = (exId: string) => {
    setState((prev) => {
      const next = { ...prev, [exId]: { ...prev[exId], revealed: true } };
      const correct = exercises.reduce(
        (acc, ex) => acc + (next[ex.id]?.revealed && next[ex.id]?.selected === ex.correctChoiceId ? 1 : 0),
        0
      );
      onProgressChange?.(correct, exercises.length);
      return next;
    });
  };

  const reset = (exId: string) =>
    setState((prev) => ({ ...prev, [exId]: { revealed: false } }));

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between rounded-md border border-border bg-hud-surface px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary/15 text-primary">
            <Sparkles className="size-3.5" aria-hidden />
          </span>
          <div>
            <p className="text-xs font-semibold text-foreground">Exercícios táticos</p>
            <p className="font-mono text-[10px] text-muted-foreground">
              Correção determinística · feedback imediato
            </p>
          </div>
        </div>
        <div className="font-mono text-[11px] tabular-nums text-foreground">
          <span className="text-primary">{stats.correct}</span>
          <span className="text-muted-foreground">/{stats.total}</span>
          <span className="ml-2 text-[10px] uppercase tracking-widest-2 text-muted-foreground">acertos</span>
        </div>
      </header>

      <ol className="space-y-4">
        {exercises.map((ex, idx) => {
          const s = state[ex.id] ?? { revealed: false };
          const isCorrect = s.revealed && s.selected === ex.correctChoiceId;
          return (
            <li key={ex.id} className="rounded-xl border border-border bg-hud-surface p-5">
              <div className="mb-3 flex items-center justify-between">
                <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
                  Exercício {String(idx + 1).padStart(2, "0")}
                </span>
                {s.revealed && (
                  <span className={cn(
                    "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ring-1",
                    isCorrect
                      ? "bg-success/10 text-success ring-success/30"
                      : "bg-destructive/10 text-destructive ring-destructive/30"
                  )}>
                    {isCorrect
                      ? <CheckCircle2 className="size-3" aria-hidden />
                      : <XCircle className="size-3" aria-hidden />}
                    {isCorrect ? "Correto" : "Errado"}
                  </span>
                )}
              </div>

              <p className="text-sm font-medium text-foreground leading-relaxed">{ex.prompt}</p>
              {ex.context && (
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">{ex.context}</p>
              )}

              <fieldset className="mt-4 space-y-2" disabled={s.revealed}>
                <legend className="sr-only">Alternativas</legend>
                {ex.choices.map((c) => {
                  const selected   = s.selected === c.id;
                  const isAnswer   = c.id === ex.correctChoiceId;
                  const showCorrect = s.revealed && isAnswer;
                  const showWrong  = s.revealed && selected && !isAnswer;
                  return (
                    <label key={c.id} className={cn(
                      "flex cursor-pointer items-start gap-3 rounded-md border bg-background p-3 text-xs leading-relaxed transition-colors",
                      selected && !s.revealed && "border-primary/60 bg-primary/5",
                      !selected && !s.revealed && "border-border hover:border-primary/40",
                      showCorrect && "border-success/60 bg-success/10 text-foreground",
                      showWrong   && "border-destructive/60 bg-destructive/10 text-foreground",
                      s.revealed && !showCorrect && !showWrong && "border-border opacity-60"
                    )}>
                      <input
                        type="radio"
                        name={`ex-${ex.id}`}
                        value={c.id}
                        checked={selected}
                        onChange={() =>
                          setState((prev) => ({
                            ...prev,
                            [ex.id]: { ...prev[ex.id], selected: c.id, revealed: false },
                          }))
                        }
                        className="mt-0.5 size-3.5 accent-[hsl(var(--primary))]"
                      />
                      <span className="flex-1">{c.label}</span>
                    </label>
                  );
                })}
              </fieldset>

              <div className="mt-4 flex items-start gap-3">
                {s.revealed ? (
                  <button
                    onClick={() => reset(ex.id)}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-sm bg-secondary px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-foreground hover:bg-muted"
                  >
                    <RotateCcw className="size-3" aria-hidden />
                    Refazer
                  </button>
                ) : (
                  <button
                    onClick={() => submit(ex.id)}
                    disabled={!s.selected}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-sm bg-primary px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-glow disabled:opacity-40"
                  >
                    Verificar resposta
                  </button>
                )}
                {s.revealed && (
                  <div className="flex-1 rounded-md border border-border bg-background p-3">
                    <p className="mb-1 font-mono text-[10px] font-bold uppercase tracking-wider text-primary">
                      Análise
                    </p>
                    <AiText size="xs">{ex.explanation}</AiText>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
