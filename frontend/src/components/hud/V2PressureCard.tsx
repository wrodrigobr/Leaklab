import { useTranslation } from "react-i18next";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import type { PressureProfile } from "@/lib/api";

/**
 * V2PressureCard — UX-2 onda 4. Versão V2 do PressureProfileCard: barras com
 * gradiente coloridas pelo delta vs baseline + tick teal marcando o baseline
 * (mesma linguagem do marcador de média do twin). Clássico segue com o antigo.
 */
const PRESSURE_ORDER = ["none", "low", "medium", "high"] as const;

function deltaColor(score: number, baseline: number): string {
  const delta = score - baseline;
  if (delta > 0.08) return "#e52020";
  if (delta > 0.03) return "#f59e0b";
  return "#2DD4BF";
}

export function V2PressureCard({ data }: { data?: PressureProfile | null }) {
  const { t } = useTranslation("dashboard");

  if (!data?.by_pressure || Object.keys(data.by_pressure).length === 0) {
    return (
      <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("pressure.title")}</span>
          <HudTooltip content={t("pressure.tooltip")} />
        </div>
        <p className="text-xs text-muted-foreground">{t("pressure.noData")}</p>
      </div>
    );
  }

  const baseline = data.baseline_score ?? 0;
  const rows = PRESSURE_ORDER
    .filter((k) => data.by_pressure[k])
    .map((k) => ({ key: k, ...data.by_pressure[k] }));
  const maxScore = Math.max(...rows.map((r) => r.avg_score), baseline * 1.5, 0.01);
  const baselinePct = (baseline / maxScore) * 100;

  const LABEL: Record<string, string> = {
    none:   t("pressure.none"),
    low:    t("pressure.low"),
    medium: t("pressure.medium"),
    high:   t("pressure.high"),
  };

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("pressure.title")}</span>
          <HudTooltip content={t("pressure.tooltip")} />
        </div>
        {data.has_collapse ? (
          <span className="inline-flex items-center gap-1 font-mono text-[9px] font-bold uppercase text-red-400 bg-red-500/10 ring-1 ring-red-500/25 rounded-full px-2 py-0.5">
            <AlertTriangle className="size-2.5" aria-hidden />
            {t("pressure.collapseDetected")}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 font-mono text-[9px] uppercase text-teal-300/80 bg-teal-400/10 ring-1 ring-teal-400/20 rounded-full px-2 py-0.5">
            <ShieldCheck className="size-2.5" aria-hidden />
            {t("pressure.solid")}
          </span>
        )}
      </div>

      <div className="space-y-2.5">
        {rows.map(({ key, avg_score, n }) => {
          const pct = (avg_score / maxScore) * 100;
          const color = deltaColor(avg_score, baseline);
          return (
            <div key={key} className="flex items-center gap-3">
              <span className="w-16 font-mono text-[10px] text-muted-foreground shrink-0 leading-tight">
                {LABEL[key] ?? key}
              </span>
              <div className="relative flex-1 h-2.5 rounded-full bg-muted/15 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${Math.max(2, pct)}%`, background: `linear-gradient(90deg, ${color}99, ${color})` }}
                />
                <div
                  className="absolute top-0 h-full w-px bg-teal-300/70"
                  style={{ left: `${baselinePct}%` }}
                  title={t("pressure.title")}
                />
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="w-12 text-right font-mono text-[11px] font-bold tabular-nums" style={{ color }}>
                  {(avg_score * 100).toFixed(1)}
                </span>
                <span className="font-mono text-[9px] text-muted-foreground/50">({n})</span>
              </div>
            </div>
          );
        })}
      </div>

      {data.collapse_delta !== null && (
        <p className={`mt-3 font-mono text-[9px] leading-relaxed ${data.has_collapse ? "text-red-400/70" : "text-muted-foreground/60"}`}>
          {data.has_collapse
            ? t("pressure.collapseSummary", { delta: (data.collapse_delta * 100).toFixed(1) })
            : t("pressure.stableSummary", { delta: Math.abs(data.collapse_delta * 100).toFixed(1) })}
        </p>
      )}
    </div>
  );
}
