import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Target, Flame, ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import { metrics, DailyFocusAction } from "@/lib/api";
import { cn } from "@/lib/utils";

export function DailyFocusCard() {
  const navigate    = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["daily-focus"],
    queryFn:  metrics.dailyFocus,
    staleTime: 5 * 60_000,
  });

  const complete = useMutation({
    mutationFn: metrics.completeDailyFocus,
    onSuccess:  () => queryClient.invalidateQueries({ queryKey: ["daily-focus"] }),
  });

  if (isLoading) return null;
  if (!data)     return null;

  const primary: DailyFocusAction = data.primary;

  // Concluído: mostrar confirmação mínima
  if (data.completed) {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-primary/20 bg-primary/5 px-4 py-2.5">
        <CheckCircle2 className="size-3.5 text-primary shrink-0" />
        <span className="text-xs font-medium text-foreground">Foco diário concluído</span>
        {data.streak > 1 && (
          <span className="flex items-center gap-1 font-mono text-[10px] text-amber-400 ml-auto">
            <Flame className="size-3" /> {data.streak}
          </span>
        )}
      </div>
    );
  }

  if (!primary || primary.type === "none") return null;

  const handleClick = () => {
    if (primary.link?.startsWith("/")) navigate(primary.link);
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-hud-surface px-4 py-2.5">
      {/* Label */}
      <Target className="size-3.5 text-primary shrink-0" />
      <span className="font-mono text-[9px] font-bold uppercase tracking-widest text-muted-foreground shrink-0 hidden sm:block">
        Foco
      </span>

      {/* Ação primária */}
      <button
        onClick={handleClick}
        className="flex-1 min-w-0 text-left flex items-center gap-2 group"
      >
        <span className="text-sm font-medium text-foreground truncate group-hover:text-primary transition-colors">
          {primary.label}
        </span>
        {primary.description && (
          <span className="hidden md:block text-xs text-muted-foreground truncate shrink-0">
            · {primary.description}
          </span>
        )}
        <ArrowRight className="size-3.5 text-muted-foreground/50 group-hover:text-primary shrink-0 transition-colors" />
      </button>

      {/* Streak + concluir */}
      <div className="flex items-center gap-2 shrink-0">
        {data.streak > 1 && (
          <span className="flex items-center gap-1 font-mono text-[10px] text-amber-400">
            <Flame className="size-3" /> {data.streak}
          </span>
        )}
        <button
          onClick={() => complete.mutate()}
          disabled={complete.isPending}
          title="Marcar foco de hoje como concluído"
          className={cn(
            "flex items-center justify-center size-6 rounded-md border transition-colors",
            "border-border text-muted-foreground/50 hover:border-primary/40 hover:text-primary",
            "disabled:opacity-40"
          )}
        >
          {complete.isPending
            ? <Loader2 className="size-3 animate-spin" />
            : <CheckCircle2 className="size-3" />}
        </button>
      </div>
    </div>
  );
}
