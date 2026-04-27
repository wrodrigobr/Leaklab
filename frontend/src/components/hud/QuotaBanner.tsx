import { useEffect, useState } from "react";
import { AlertTriangle, Zap } from "lucide-react";
import { subscription, QuotaStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

function QuotaBar({ used, limit, label }: { used: number; limit: number; label: string }) {
  const pct = Math.min(100, Math.round((used / limit) * 100));
  const nearLimit = pct >= 80;
  const atLimit   = pct >= 100;

  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between font-mono text-[10px] text-muted-foreground">
        <span>{label}</span>
        <span className={cn(atLimit ? "text-destructive" : nearLimit ? "text-amber-400" : "")}>
          {used}/{limit}
        </span>
      </div>
      <div className="h-1 rounded-full bg-secondary overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            atLimit ? "bg-destructive" : nearLimit ? "bg-amber-400" : "bg-primary"
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function QuotaBanner() {
  const [status, setStatus] = useState<QuotaStatus | null>(null);

  useEffect(() => {
    subscription.status().then(setStatus).catch(() => {});
  }, []);

  if (!status || status.plan !== "free") return null;

  const { tournaments_used, ai_calls_used, limits } = status;
  const tLimit  = limits.tournaments ?? 0;
  const aiLimit = limits.ai_calls   ?? 0;
  const nearAny = tournaments_used / tLimit >= 0.8 || ai_calls_used / aiLimit >= 0.8;
  const atAny   = tournaments_used >= tLimit || ai_calls_used >= aiLimit;

  if (!nearAny) return null;

  return (
    <div className={cn(
      "rounded-xl border px-4 py-3 space-y-2.5",
      atAny
        ? "border-destructive/40 bg-destructive/5"
        : "border-amber-400/30 bg-amber-400/5"
    )}>
      <div className="flex items-center gap-2">
        <AlertTriangle className={cn("size-3.5 shrink-0", atAny ? "text-destructive" : "text-amber-400")} />
        <p className="text-xs font-medium text-foreground">
          {atAny ? "Limite mensal atingido" : "Limite mensal próximo"}
        </p>
      </div>

      <div className="space-y-1.5">
        <QuotaBar used={tournaments_used} limit={tLimit}  label="Torneios este mês" />
        <QuotaBar used={ai_calls_used}   limit={aiLimit} label="Análises IA este mês" />
      </div>

      <a
        href="mailto:rodrigo.phpro@gmail.com?subject=Upgrade%20PokerLeakLab%20Pro"
        className="flex items-center gap-1.5 w-full justify-center rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 transition-opacity"
      >
        <Zap className="size-3" />
        Fazer upgrade para Pro
      </a>
    </div>
  );
}
