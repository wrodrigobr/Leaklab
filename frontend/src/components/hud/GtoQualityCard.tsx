import { Loader2, Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { GtoQualityData } from "@/lib/api";

interface Props {
  data?: GtoQualityData | null;
  pendingGto?: number;
}

function GtoCardShell({ title, tooltip, children }: { title: string; tooltip: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{title}</span>
        <HudTooltip content={tooltip} />
      </div>
      {children}
    </div>
  );
}

export function GtoQualityCard({ data, pendingGto = 0 }: Props) {
  const { t } = useTranslation("dashboard");

  if (!data || data.total_with_gto < 10) {
    return (
      <GtoCardShell title={t("gtoQuality.title")} tooltip={t("gtoQuality.tooltip")}>
        <div className="flex items-start gap-2 text-[11px] text-muted-foreground">
          <Info className="size-3.5 mt-0.5 shrink-0 text-primary/50" />
          <span>{t("gtoNotice.needMoreData")}</span>
        </div>
      </GtoCardShell>
    );
  }

  const segments = [
    { key: "gto_correct_pct",  pct: data.gto_correct_pct,  color: "#10b981", labelKey: "gtoQuality.correct"  },
    { key: "gto_mixed_pct",    pct: data.gto_mixed_pct,    color: "#3b82f6", labelKey: "gtoQuality.mixed"    },
    { key: "gto_minor_pct",    pct: data.gto_minor_pct,    color: "#f59e0b", labelKey: "gtoQuality.minor"    },
    { key: "gto_critical_pct", pct: data.gto_critical_pct, color: "#e52020", labelKey: "gtoQuality.critical" },
  ];

  const alignedColor = data.aligned_pct >= 70 ? "#10b981" : data.aligned_pct >= 50 ? "#f59e0b" : "#e52020";

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
            {t("gtoQuality.title")}
          </span>
          <HudTooltip content={t("gtoQuality.tooltip")} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {t("gtoQuality.coverage", { n: data.total_with_gto, pct: data.coverage_pct })}
        </span>
      </div>


      {/* Aligned % — big number */}
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold font-mono" style={{ color: alignedColor }}>
          {data.aligned_pct.toFixed(0)}%
        </span>
        <span className="text-xs text-muted-foreground">{t("gtoQuality.alignedLabel")}</span>
      </div>

      {/* Stacked bar */}
      <div className="h-2.5 w-full flex rounded-full overflow-hidden gap-px">
        {segments.map((s) =>
          s.pct > 0 ? (
            <div
              key={s.key}
              style={{ width: `${s.pct}%`, backgroundColor: s.color }}
              title={`${t(s.labelKey)}: ${s.pct.toFixed(1)}%`}
            />
          ) : null
        )}
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {segments.map((s) => (
          <div key={s.key} className="flex items-center gap-1.5 min-w-0">
            <span className="size-2 rounded-sm shrink-0" style={{ backgroundColor: s.color }} />
            <span className="text-[10px] text-muted-foreground truncate">{t(s.labelKey)}</span>
            <span className="ml-auto font-mono text-[10px] text-foreground/70 shrink-0">
              {s.pct.toFixed(1)}%
            </span>
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
