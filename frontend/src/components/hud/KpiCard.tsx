import { ArrowDownRight, ArrowUpRight, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";

export interface KpiCardProps {
  index: string;
  label: string;
  value: string;
  unit?: string;
  delta?: { value: string; trend: "up" | "down" | "flat" };
  hint?: string;
  icon?: LucideIcon;
  highlight?: boolean;
  tooltip?: string;
}

export function KpiCard({ index, label, value, unit, delta, hint, icon: Icon, highlight, tooltip }: KpiCardProps) {
  const trendColor =
    delta?.trend === "up"
      ? "text-primary"
      : delta?.trend === "down"
      ? "text-destructive"
      : "text-muted-foreground";
  const TrendIcon = delta?.trend === "down" ? ArrowDownRight : ArrowUpRight;

  return (
    <article
      className={cn(
        "relative bg-hud-surface p-6 ring-hud overflow-hidden transition-colors",
        highlight && "bg-gradient-glow"
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-medium uppercase tracking-widest-2 text-muted-foreground">
            [{index}] {label}
          </span>
          {tooltip && <HudTooltip content={tooltip} />}
        </div>
        {Icon && <Icon className="size-3.5 text-muted-foreground" aria-hidden />}
      </div>

      <div
        className={cn(
          "font-mono text-3xl font-light tracking-tight tabular-nums text-foreground",
          highlight && "text-primary text-glow"
        )}
      >
        {unit && <span className="text-lg text-muted-foreground mr-0.5">{unit}</span>}
        {value}
        {!unit && delta?.trend === "up" && <span className="text-primary text-lg">%</span>}
      </div>

      {(delta || hint) && (
        <div className="mt-3 flex items-center gap-2">
          {delta && (
            <span className={cn("flex items-center gap-1 font-mono text-[11px] font-medium", trendColor)}>
              <TrendIcon className="size-3" aria-hidden />
              {delta.value}
            </span>
          )}
          {hint && <span className="font-mono text-[11px] text-muted-foreground">{hint}</span>}
        </div>
      )}
    </article>
  );
}
