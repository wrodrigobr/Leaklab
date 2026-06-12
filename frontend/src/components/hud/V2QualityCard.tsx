import { Loader2, Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { GtoQualityData } from "@/lib/api";

/**
 * V2QualityCard — UX-2 onda 3. Versão V2 do GtoQualityCard: anel cônico com os
 * 4 segmentos (correta/mixed/desvio leve/crítico) e o alinhado% no centro —
 * mesma linguagem radial do V2CoverageCard. O clássico segue com o card antigo.
 */
const SEGMENTS = [
  { key: "gto_correct_pct",  color: "#10b981", labelKey: "gtoQuality.correct"  },
  { key: "gto_mixed_pct",    color: "#3b82f6", labelKey: "gtoQuality.mixed"    },
  { key: "gto_minor_pct",    color: "#f59e0b", labelKey: "gtoQuality.minor"    },
  { key: "gto_critical_pct", color: "#e52020", labelKey: "gtoQuality.critical" },
] as const;

export function V2QualityCard({ data, pendingGto = 0 }: { data?: GtoQualityData | null; pendingGto?: number }) {
  const { t } = useTranslation("dashboard");

  if (!data || data.total_with_gto < 10) {
    return (
      <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("gtoQuality.title")}</span>
          <HudTooltip content={t("gtoQuality.tooltip")} />
        </div>
        <div className="flex items-start gap-2 text-[11px] text-muted-foreground">
          <Info className="size-3.5 mt-0.5 shrink-0 text-primary/50" />
          <span>{t("gtoNotice.needMoreData")}</span>
        </div>
      </div>
    );
  }

  // Anel cônico: segmentos acumulados na ordem correta→crítico
  let acc = 0;
  const stops = SEGMENTS.map((s) => {
    const pct = (data[s.key] as number) || 0;
    const from = acc;
    acc += pct;
    return `${s.color} ${from}% ${acc}%`;
  }).join(", ");
  const alignedColor = data.aligned_pct >= 70 ? "#10b981" : data.aligned_pct >= 50 ? "#f59e0b" : "#e52020";

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("gtoQuality.title")}</span>
          <HudTooltip content={t("gtoQuality.tooltip")} />
        </div>
        <span className="font-mono text-[9px] text-muted-foreground/70">
          {t("gtoQuality.coverage", { n: data.total_with_gto, pct: data.coverage_pct })}
        </span>
      </div>

      <div className="flex flex-col items-center gap-3">
        <div
          className="size-[120px] rounded-full grid place-items-center"
          style={{ background: `conic-gradient(${stops})` }}
        >
          <div className="size-[92px] rounded-full bg-card grid place-items-center text-center">
            <div>
              <div className="font-mono text-2xl font-bold tabular-nums leading-none" style={{ color: alignedColor }}>
                {data.aligned_pct.toFixed(0)}%
              </div>
              <div className="mt-1 font-mono text-[8px] uppercase tracking-widest text-muted-foreground">
                {t("gtoQuality.alignedLabel")}
              </div>
            </div>
          </div>
        </div>

        <div className="w-full grid grid-cols-2 gap-x-4 gap-y-1">
          {SEGMENTS.map((s) => (
            <div key={s.key} className="flex items-center gap-1.5 min-w-0">
              <span className="size-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
              <span className="text-[10px] text-muted-foreground truncate">{t(s.labelKey)}</span>
              <span className="ml-auto font-mono text-[10px] tabular-nums text-foreground/70 shrink-0">
                {((data[s.key] as number) || 0).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {pendingGto > 0 && (
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70 border-t border-border/30 pt-2 mt-3">
          <Loader2 className="size-3 animate-spin shrink-0 text-primary/50" />
          <span>{t(pendingGto === 1 ? "gtoNotice.processing" : "gtoNotice.processing_plural", { n: pendingGto })}</span>
        </div>
      )}
    </div>
  );
}
