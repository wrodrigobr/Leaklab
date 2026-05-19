import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { GtoAlignmentData } from "@/lib/api";

interface Props {
  data?: GtoAlignmentData | null;
}

const STREET_ORDER = ["preflop", "flop", "turn", "river"];

const COLORS = {
  correct: "#10b981",
  mixed:   "#3b82f6",
  minor:   "#f59e0b",
  critical:"#e52020",
};

export function GtoAlignmentCard({ data }: Props) {
  const { t } = useTranslation("dashboard");

  if (!data || data.total_with_gto < 10) return null;

  const streets = STREET_ORDER
    .map(s => data.by_street.find(r => r.street === s))
    .filter(Boolean) as NonNullable<(typeof data.by_street)[number]>[];

  const alignedColor = (pct: number) =>
    pct >= 70 ? COLORS.correct : pct >= 50 ? COLORS.mixed : COLORS.critical;

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
            {t("gtoAlignment.title")}
          </span>
          <HudTooltip content={t("gtoAlignment.tooltip")} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {t("gtoAlignment.coverage", {
            n: data.total_with_gto,
            pct: data.overall_coverage_pct,
          })}
        </span>
      </div>

      {/* Overall aligned % */}
      <div className="flex items-baseline gap-2">
        <span
          className="text-2xl font-bold font-mono"
          style={{ color: alignedColor(data.overall_aligned_pct) }}
        >
          {data.overall_aligned_pct.toFixed(0)}%
        </span>
        <span className="text-xs text-muted-foreground">{t("gtoAlignment.alignedLabel")}</span>
      </div>

      {/* Per-street rows */}
      <div className="space-y-2">
        {streets.map((row) => (
          <div key={row.street} className="space-y-0.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] text-muted-foreground capitalize">
                {t(`gtoAlignment.street_${row.street}`, { defaultValue: row.street })}
              </span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-muted-foreground/60">
                  {row.with_gto} dec
                </span>
                <span
                  className="font-mono text-[10px] font-semibold tabular-nums"
                  style={{ color: alignedColor(row.aligned_pct) }}
                >
                  {row.aligned_pct.toFixed(0)}%
                </span>
              </div>
            </div>

            {/* Mini stacked bar */}
            <div className="h-1.5 w-full flex rounded-full overflow-hidden gap-px">
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
    </div>
  );
}
