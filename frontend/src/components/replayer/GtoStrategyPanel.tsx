import { CheckCircle2 } from "lucide-react";
import { GtoStrategyAction } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  strategy: GtoStrategyAction[];
  playedAction?: string | null;
  compact?: boolean;
}

function fmtEv(ev: number | null | undefined): string | null {
  if (ev == null) return null;
  const sign = ev >= 0 ? "+" : "";
  return `${sign}${ev.toFixed(2)} BB`;
}

function normalizeAction(a: string): string {
  return (a ?? "").toLowerCase().replace(/[-_ ]/g, "");
}

export function GtoStrategyPanel({ strategy, playedAction, compact }: Props) {
  if (!strategy || strategy.length === 0) return null;

  const sorted = [...strategy].sort((a, b) => b.frequency - a.frequency);
  const topEv = sorted[0]?.ev_bb ?? null;

  const playedNorm = playedAction ? normalizeAction(playedAction) : null;
  const playedRow = playedNorm
    ? sorted.find(r => normalizeAction(r.action) === playedNorm || normalizeAction(r.label) === playedNorm)
    : null;
  const playedEv = playedRow?.ev_bb ?? null;

  const opportunityCost =
    topEv != null && playedEv != null && topEv > playedEv
      ? topEv - playedEv
      : null;

  return (
    <div className="space-y-1.5">
      {sorted.map(row => {
        const isPlayed =
          playedNorm != null &&
          (normalizeAction(row.action) === playedNorm || normalizeAction(row.label) === playedNorm);
        const pct = Math.round(row.frequency * 100);
        const evStr = fmtEv(row.ev_bb);

        return (
          <div key={row.action} className={cn("space-y-0.5", isPlayed && "opacity-100")}>
            <div className="flex items-center gap-2">
              {/* bar */}
              <div className="flex-1 h-1.5 rounded-full bg-muted/30 overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    isPlayed ? "bg-primary" : "bg-muted-foreground/40"
                  )}
                  style={{ width: `${pct}%` }}
                />
              </div>
              {/* label */}
              <span className={cn(
                "font-mono shrink-0",
                compact ? "text-[8px]" : "text-[9px]",
                isPlayed ? "text-primary font-bold" : "text-muted-foreground"
              )}>
                {row.label || row.action}
              </span>
              {/* frequency */}
              <span className={cn(
                "font-mono shrink-0 w-7 text-right",
                compact ? "text-[8px]" : "text-[9px]",
                isPlayed ? "text-foreground font-bold" : "text-muted-foreground"
              )}>
                {pct}%
              </span>
              {/* ev */}
              {evStr && (
                <span className={cn(
                  "font-mono shrink-0",
                  compact ? "text-[7px]" : "text-[8px]",
                  (row.ev_bb ?? 0) >= 0 ? "text-emerald-400/70" : "text-red-400/70"
                )}>
                  {evStr}
                </span>
              )}
              {/* played checkmark */}
              {isPlayed && (
                <CheckCircle2 className={cn("shrink-0 text-primary", compact ? "size-2.5" : "size-3")} />
              )}
            </div>
          </div>
        );
      })}

      {/* Opportunity cost footer */}
      {opportunityCost != null && opportunityCost > 0.01 && !compact && (
        <p className="font-mono text-[8px] text-amber-400/80 pt-0.5">
          Custo de oportunidade: -{opportunityCost.toFixed(2)} BB vs linha ótima
        </p>
      )}
    </div>
  );
}
