import { Info, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { GtoPositionData } from "@/lib/api";

interface Props {
  data?: GtoPositionData | null;
  pendingGto?: number;
}

const COLORS = {
  correct: "#10b981",
  mixed:   "#3b82f6",
  minor:   "#f59e0b",
  critical:"#e52020",
};

function alignedColor(pct: number) {
  if (pct >= 70) return COLORS.correct;
  if (pct >= 50) return COLORS.mixed;
  return COLORS.critical;
}

export function GtoPositionCard({ data, pendingGto = 0 }: Props) {
  const { t } = useTranslation("dashboard");

  if (!data || data.total_with_gto < 10) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
            {t("gtoPosition.title")}
          </span>
          <HudTooltip content={t("gtoPosition.tooltip")} />
        </div>
        <div className="flex items-start gap-2 text-[11px] text-muted-foreground">
          <Info className="size-3.5 mt-0.5 shrink-0 text-primary/50" />
          <span>{t("gtoNotice.needMoreData")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
            {t("gtoPosition.title")}
          </span>
          <HudTooltip content={t("gtoPosition.tooltip")} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {t("gtoPosition.coverage", {
            n: data.total_with_gto,
            pct: data.overall_coverage_pct,
          })}
        </span>
      </div>

      {/* Per-position rows */}
      <div className="space-y-2">
        {data.by_position.map((row) => (
          <div key={row.position} className="space-y-0.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] font-bold text-muted-foreground w-12 shrink-0">
                {row.position}
              </span>
              <div className="flex-1 mx-2 h-1.5 rounded-full bg-border overflow-hidden flex gap-px">
                {row.correct_pct > 0 && (
                  <div style={{ width: `${row.correct_pct}%`, backgroundColor: COLORS.correct }} />
                )}
                {row.mixed_pct > 0 && (
                  <div style={{ width: `${row.mixed_pct}%`, backgroundColor: COLORS.mixed }} />
                )}
                {row.minor_pct > 0 && (
                  <div style={{ width: `${row.minor_pct}%`, backgroundColor: COLORS.minor }} />
                )}
                {row.critical_pct > 0 && (
                  <div style={{ width: `${row.critical_pct}%`, backgroundColor: COLORS.critical }} />
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span
                  className="font-mono text-[11px] font-bold tabular-nums w-9 text-right"
                  style={{ color: alignedColor(row.aligned_pct) }}
                >
                  {row.aligned_pct.toFixed(0)}%
                </span>
                <span className="font-mono text-[9px] text-muted-foreground/50">({row.with_gto})</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1 border-t border-border/40">
        {[
          { color: COLORS.correct,  labelKey: "gtoQuality.correct"  },
          { color: COLORS.mixed,    labelKey: "gtoQuality.mixed"    },
          { color: COLORS.minor,    labelKey: "gtoQuality.minor"    },
          { color: COLORS.critical, labelKey: "gtoQuality.critical" },
        ].map(({ color, labelKey }) => (
          <div key={labelKey} className="flex items-center gap-1.5 min-w-0">
            <span className="size-2 rounded-sm shrink-0" style={{ backgroundColor: color }} />
            <span className="text-[10px] text-muted-foreground truncate">{t(labelKey)}</span>
          </div>
        ))}
      </div>

      {pendingGto > 0 && (
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70 border-t border-border/30 pt-2">
          <Loader2 className="size-3 animate-spin shrink-0 text-primary/50" />
          <span>{t(pendingGto === 1 ? "gtoNotice.processing" : "gtoNotice.processing_plural", { n: pendingGto })}</span>
        </div>
      )}
    </div>
  );
}
