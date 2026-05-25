import { CheckCircle2, Star } from "lucide-react";
import { GtoStrategyAction } from "@/lib/api";
import { cn } from "@/lib/utils";
import { GtoMixedBadge } from "./GtoMixedBadge";

interface Props {
  strategy: GtoStrategyAction[];
  playedAction?: string | null;
  compact?: boolean;
  potBb?: number | null;
}


function normalizeAction(a: string): string {
  return (a ?? "").toLowerCase().replace(/[-_ ]/g, "");
}

function formatActionLabel(action: string, label?: string, potBb?: number | null): string {
  const raw = (label || action || "").trim();
  const norm = normalizeAction(raw);
  if (norm === "allin" || norm === "allinfold" || norm === "jam" || norm === "shove") return "Shove";
  if (norm === "call") return "Call";
  if (norm === "fold") return "Fold";
  if (norm === "check") return "Check";
  if (norm === "bet") return "Bet";
  if (norm === "raise") return "Raise";
  // bet_1.4bb / raise_2.5bb → converte pra "% pot" se potBb disponível, senão mantém "Bet 1.4bb"
  // bet_75pct / raise_50pct → "Bet 75% pot" / "Raise 50% pot"
  const sized = raw.toLowerCase().match(/^(bet|raise)_(.+)$/);
  if (sized) {
    const verb = sized[1].charAt(0).toUpperCase() + sized[1].slice(1);
    let size = sized[2];
    const bbMatch = size.match(/^([\d.]+)bb$/);
    if (bbMatch && potBb && potBb > 0) {
      const sizeBb = parseFloat(bbMatch[1]);
      if (!Number.isNaN(sizeBb)) {
        const pct = Math.round((sizeBb / potBb) * 100);
        return `${verb} ${pct}% pot`;
      }
    }
    size = size.replace(/pct$/, "% pot");
    return `${verb} ${size}`;
  }
  // jam/shove genérico no fallback
  if (/^(jam|shove|all[- ]?in)$/i.test(raw)) return "Shove";
  // Capitalize first letter, keep the rest
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export function GtoStrategyPanel({ strategy, playedAction, compact, potBb }: Props) {
  if (!strategy || strategy.length === 0) return null;

  const sorted = [...strategy].sort((a, b) => b.frequency - a.frequency);
  const topRow = sorted[0];
  const topEv = topRow?.ev_bb ?? null;

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
    <div className="space-y-2">
      {sorted.map((row, idx) => {
        const isPlayed =
          playedNorm != null &&
          (normalizeAction(row.action) === playedNorm || normalizeAction(row.label) === playedNorm);
        const isTop = idx === 0;
        const isTopAndPlayed = isTop && isPlayed;
        const pct = Math.round(row.frequency * 100);
        const displayLabel = formatActionLabel(row.action, row.label);

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
