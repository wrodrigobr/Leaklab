import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Target, Flame, ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import { metrics, DailyFocusAction } from "@/lib/api";
import { cn } from "@/lib/utils";

function timeUntilMidnight(): string {
  const now = new Date();
  const midnight = new Date(now);
  midnight.setHours(24, 0, 0, 0);
  const diff = midnight.getTime() - now.getTime();
  const h = Math.floor(diff / 3_600_000);
  const m = Math.floor((diff % 3_600_000) / 60_000);
  return `${h}h ${m}m`;
}

function ActionItem({
  action,
  primary,
}: {
  action: DailyFocusAction;
  primary?: boolean;
}) {
  const navigate = useNavigate();

  if (action.type === "none") return null;

  const handleClick = () => {
    if (action.link.startsWith("/")) navigate(action.link);
  };

  return (
    <button
      onClick={handleClick}
      className={cn(
        "w-full text-left rounded-lg border transition-colors",
        primary
          ? "border-primary/40 bg-primary/5 hover:bg-primary/10 px-4 py-3.5"
          : "border-border bg-background hover:border-border/80 hover:bg-muted/30 px-3 py-2.5"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-0.5 flex-1 min-w-0">
          <p
            className={cn(
              "font-semibold truncate",
              primary ? "text-sm text-foreground" : "text-xs text-foreground"
            )}
          >
            {action.label}
          </p>
          <p
            className={cn(
              "truncate",
              primary
                ? "text-xs text-muted-foreground"
                : "text-[11px] text-muted-foreground"
            )}
          >
            {action.description}
          </p>
        </div>
        <ArrowRight
          className={cn(
            "shrink-0 text-muted-foreground",
            primary ? "size-4 mt-0.5" : "size-3.5 mt-0.5"
          )}
        />
      </div>
    </button>
  );
}

export function DailyFocusCard() {
  const queryClient = useQueryClient();
  const [countdown, setCountdown] = useState(timeUntilMidnight());

  useEffect(() => {
    const id = setInterval(() => setCountdown(timeUntilMidnight()), 60_000);
    return () => clearInterval(id);
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["daily-focus"],
    queryFn: metrics.dailyFocus,
    staleTime: 5 * 60_000,
  });

  const complete = useMutation({
    mutationFn: metrics.completeDailyFocus,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["daily-focus"] }),
  });

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-5 flex items-center justify-center h-32">
        <Loader2 className="size-5 text-muted-foreground animate-spin" />
      </div>
    );
  }

  if (!data) return null;

  if (data.completed) {
    return (
      <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <CheckCircle2 className="size-4 text-primary shrink-0" />
          <div>
            <p className="text-sm font-medium text-foreground">Foco diário concluído</p>
            <p className="text-[11px] text-muted-foreground">
              {data.streak > 1 && (
                <span className="text-amber-400 font-semibold">{data.streak}🔥 </span>
              )}
              Próximo em {countdown}
            </p>
          </div>
        </div>
        {data.streak > 0 && (
          <div className="flex items-center gap-1 text-amber-400">
            <Flame className="size-4" />
            <span className="font-mono text-sm font-bold">{data.streak}</span>
          </div>
        )}
      </div>
    );
  }

  const secondaries = (data.secondary ?? []).filter((a) => a.type !== "none");

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5 space-y-3">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground flex items-center gap-1.5">
          <Target className="size-3" /> Foco de hoje
        </p>
        <div className="flex items-center gap-2">
          {data.streak > 1 && (
            <span className="flex items-center gap-1 font-mono text-[10px] text-amber-400">
              <Flame className="size-3" /> {data.streak} dias
            </span>
          )}
          <span className="font-mono text-[10px] text-muted-foreground">
            expira em {countdown}
          </span>
        </div>
      </div>

      {data.primary.type !== "none" && (
        <ActionItem action={data.primary} primary />
      )}

      {secondaries.length > 0 && (
        <div className="space-y-1.5">
          <p className="font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground">
            Também recomendado
          </p>
          <div className="space-y-1.5">
            {secondaries.map((a, i) => (
              <ActionItem key={i} action={a} />
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => complete.mutate()}
        disabled={complete.isPending}
        className="w-full flex items-center justify-center gap-1.5 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-xs font-medium text-primary hover:bg-primary/10 transition-colors disabled:opacity-50"
      >
        {complete.isPending ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <CheckCircle2 className="size-3.5" />
        )}
        Marcar como concluído
      </button>
    </div>
  );
}
