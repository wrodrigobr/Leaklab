import { CheckCircle2, Star } from "lucide-react";
import { GtoStrategyAction } from "@/lib/api";
import { cn } from "@/lib/utils";
import { GtoMixedBadge } from "./GtoMixedBadge";

interface Props {
  strategy: GtoStrategyAction[];
  playedAction?: string | null;
  compact?: boolean;
}


function normalizeAction(a: string): string {
  return (a ?? "").toLowerCase().replace(/[-_ ]/g, "");
}

// Base action sem sizing: bet_1.1bb / bet_75pct → "bet", raise_2.5bb → "raise"
function baseAction(action: string, label?: string): string {
  const raw = (label || action || "").trim().toLowerCase();
  const norm = normalizeAction(raw);
  if (norm === "allin" || norm === "allinfold" || norm === "jam" || norm === "shove") return "shove";
  if (norm.startsWith("bet")) return "bet";
  if (norm.startsWith("raise")) return "raise";
  if (norm === "call") return "call";
  if (norm === "fold") return "fold";
  if (norm === "check") return "check";
  return norm;
}

function labelForBase(base: string): string {
  switch (base) {
    case "shove": return "Shove";
    case "bet":   return "Bet";
    case "raise": return "Raise";
    case "call":  return "Call";
    case "fold":  return "Fold";
    case "check": return "Check";
    default:      return base.charAt(0).toUpperCase() + base.slice(1);
  }
}

export function GtoStrategyPanel({ strategy, playedAction, compact }: Props) {
  if (!strategy || strategy.length === 0) return null;

  // Agrega por ação-base (bet_1.1bb + bet_2.5bb → "bet" com freq somada)
  const aggMap = new Map<string, { freq: number; evWeighted: number; evTotal: number }>();
  for (const r of strategy) {
    const b = baseAction(r.action, r.label);
    const slot = aggMap.get(b) ?? { freq: 0, evWeighted: 0, evTotal: 0 };
    slot.freq += r.frequency || 0;
    if (r.ev_bb != null) {
      slot.evWeighted += r.ev_bb * (r.frequency || 0);
      slot.evTotal    += r.frequency || 0;
    }
    aggMap.set(b, slot);
  }
  const sorted = Array.from(aggMap.entries())
    .map(([base, v]) => ({
      action: base,
      label: labelForBase(base),
      frequency: v.freq,
      ev_bb: v.evTotal > 0 ? v.evWeighted / v.evTotal : null,
      combos: null,
      exploitability_pct: null,
    }))
    .sort((a, b) => b.frequency - a.frequency);

  const topRow = sorted[0];
  const topEv = topRow?.ev_bb ?? null;

  const playedBase = playedAction ? baseAction(playedAction) : null;
  const playedRow = playedBase ? sorted.find(r => r.action === playedBase) : null;
  const playedEv = playedRow?.ev_bb ?? null;

  const opportunityCost =
    topEv != null && playedEv != null && topEv > playedEv
      ? topEv - playedEv
      : null;

  return (
    <div className="space-y-2">
      {sorted.map((row, idx) => {
        const isPlayed = playedBase != null && row.action === playedBase;
        const isTop = idx === 0;
        const isTopAndPlayed = isTop && isPlayed;
        const pct = Math.round(row.frequency * 100);
        const displayLabel = row.label;

        // Bar color: top+played → emerald; top only → amber; played only → primary; rest → muted
        const barClass = isTopAndPlayed
          ? "bg-emerald-500"
          : isTop
          ? "bg-amber-400"
          : isPlayed
          ? "bg-primary"
          : "bg-muted-foreground/30";

        // Label color
        const labelClass = isTopAndPlayed
          ? "text-emerald-400 font-bold"
          : isTop
          ? "text-amber-300 font-bold"
          : isPlayed
          ? "text-primary font-bold"
          : "text-muted-foreground";

        return (
          <div
            key={row.action}
            className={cn(
              "rounded-md px-2 py-1 space-y-0.5 transition-colors",
              isTop && "bg-amber-400/8 border border-amber-400/20",
              isTopAndPlayed && "bg-emerald-500/8 border border-emerald-500/25",
              isPlayed && !isTop && "bg-primary/8 border border-primary/20",
              !isTop && !isPlayed && "border border-transparent"
            )}
          >
            <div className="flex items-center gap-2">
              {/* bar */}
              <div className="flex-1 h-1.5 rounded-full bg-muted/20 overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all", barClass)}
                  style={{ width: `${pct}%` }}
                />
              </div>
              {/* top star */}
              {isTop && !compact && (
                <Star className="shrink-0 size-2.5 text-amber-400 fill-amber-400" />
              )}
              {/* label */}
              <span className={cn(
                "font-mono shrink-0",
                compact ? "text-[8px]" : "text-[9px]",
                labelClass
              )}>
                {displayLabel}
              </span>
              {/* frequency */}
              <span className={cn(
                "font-mono shrink-0 w-7 text-right",
                compact ? "text-[8px]" : "text-[9px]",
                isTop || isPlayed ? "text-foreground font-semibold" : "text-muted-foreground"
              )}>
                {pct}%
              </span>
              {/* played checkmark */}
              {isPlayed && (
                <CheckCircle2 className={cn(
                  "shrink-0",
                  compact ? "size-2.5" : "size-3",
                  isTopAndPlayed ? "text-emerald-400" : "text-primary"
                )} />
              )}
            </div>
          </div>
        );
      })}

      {/* Mixed strategy badge — when ≥2 actions have ≥10% frequency.
          Texto "Fold 85% · Raise 15%" removido: redundante com as barras acima. */}
      {sorted.filter(r => r.frequency >= 0.10).length >= 2 && (
        <div className="flex items-center gap-2 pt-0.5">
          <GtoMixedBadge label="spot_mixed" size={compact ? "xs" : "sm"} />
        </div>
      )}

      {/* Opportunity cost footer */}
      {opportunityCost != null && opportunityCost > 0.01 && !compact && (
        <p className="font-mono text-[8px] text-amber-400/80 pt-0.5">
          Custo de oportunidade: -{opportunityCost.toFixed(2)} BB vs linha ótima
        </p>
      )}
    </div>
  );
}
