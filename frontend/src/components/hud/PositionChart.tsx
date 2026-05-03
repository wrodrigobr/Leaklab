import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";

interface PosStat {
  n: number;
  avg_score: number;
  standard_rate: number;
}

interface Props {
  byPosition?: Record<string, PosStat>;
}

const POS_ORDER = ["BTN", "CO", "HJ", "MP", "UTG", "UTG+1", "UTG+2", "SB", "BB"];

function rateColor(rate: number) {
  if (rate >= 0.80) return "bg-primary";
  if (rate >= 0.65) return "bg-yellow-500";
  if (rate >= 0.50) return "bg-orange-500";
  return "bg-destructive";
}
function rateText(rate: number) {
  if (rate >= 0.80) return "text-primary";
  if (rate >= 0.65) return "text-yellow-500";
  if (rate >= 0.50) return "text-orange-500";
  return "text-destructive";
}

export function PositionChart({ byPosition }: Props) {
  const { t } = useTranslation("dashboard");

  const positions = byPosition
    ? POS_ORDER.filter((p) => byPosition[p]).map((p) => ({ pos: p, ...byPosition[p] }))
    : [];

  const extras = byPosition
    ? Object.keys(byPosition).filter((p) => !POS_ORDER.includes(p)).map((p) => ({ pos: p, ...byPosition[p] }))
    : [];

  const rows = [...positions, ...extras];

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5">
      <div className="flex items-center gap-1.5 mb-4">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
          {t("positions.title")}
        </span>
        <HudTooltip content={t("positions.tooltip")} />
      </div>

      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("positions.noData")}</p>
      ) : (
        <div className="space-y-2.5">
          {rows.map(({ pos, standard_rate, n }) => {
            const pct = standard_rate * 100;
            return (
              <div key={pos} className="flex items-center gap-3">
                <span className="w-10 font-mono text-[10px] font-bold text-muted-foreground shrink-0">{pos}</span>
                <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all", rateColor(standard_rate))}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className={cn("w-12 text-right font-mono text-[11px] font-bold tabular-nums", rateText(standard_rate))}>
                    {pct.toFixed(0)}%
                  </span>
                  <span className="font-mono text-[9px] text-muted-foreground/50">({n})</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
