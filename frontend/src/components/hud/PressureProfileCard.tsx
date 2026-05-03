import { useTranslation } from "react-i18next";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";
import type { PressureProfile } from "@/lib/api";

interface Props {
  data?: PressureProfile | null;
}

const PRESSURE_ORDER = ["none", "low", "medium", "high"];

function scoreColor(score: number, baseline: number) {
  const delta = score - baseline;
  if (delta > 0.08) return "text-destructive";
  if (delta > 0.03) return "text-yellow-400";
  return "text-primary";
}

function barColor(score: number, baseline: number) {
  const delta = score - baseline;
  if (delta > 0.08) return "bg-destructive";
  if (delta > 0.03) return "bg-yellow-400";
  return "bg-primary";
}

export function PressureProfileCard({ data }: Props) {
  const { t } = useTranslation("dashboard");

  if (!data?.by_pressure || Object.keys(data.by_pressure).length === 0) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-5">
        <div className="flex items-center gap-1.5 mb-4">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("pressure.title")}
          </span>
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

  const LABEL: Record<string, string> = {
    none:   t("pressure.none"),
    low:    t("pressure.low"),
    medium: t("pressure.medium"),
    high:   t("pressure.high"),
  };

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("pressure.title")}
          </span>
          <HudTooltip content={t("pressure.tooltip")} />
        </div>
        {data.has_collapse ? (
          <span className="inline-flex items-center gap-1 font-mono text-[9px] font-bold uppercase text-destructive bg-destructive/10 ring-1 ring-destructive/20 rounded-sm px-1.5 py-0.5">
            <AlertTriangle className="size-2.5" aria-hidden />
            {t("pressure.collapseDetected")}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 font-mono text-[9px] text-primary/60">
            <ShieldCheck className="size-2.5" aria-hidden />
            {t("pressure.solid")}
          </span>
        )}
      </div>

      <div className="space-y-2.5">
        {rows.map(({ key, avg_score, n }) => {
          const pct = (avg_score / maxScore) * 100;
          return (
            <div key={key} className="flex items-center gap-3">
              <span className="w-16 font-mono text-[10px] text-muted-foreground shrink-0 leading-tight">
                {LABEL[key] ?? key}
              </span>
              <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all", barColor(avg_score, baseline))}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className={cn("w-14 text-right font-mono text-[11px] font-bold tabular-nums", scoreColor(avg_score, baseline))}>
                  {(avg_score * 100).toFixed(1)}
                </span>
                <span className="font-mono text-[9px] text-muted-foreground/50">({n})</span>
              </div>
            </div>
          );
        })}
      </div>

      {data.collapse_delta !== null && (
        <p className={cn(
          "mt-3 font-mono text-[9px] leading-relaxed",
          data.has_collapse ? "text-destructive/70" : "text-muted-foreground/60"
        )}>
          {data.has_collapse
            ? t("pressure.collapseSummary", { delta: (data.collapse_delta * 100).toFixed(1) })
            : t("pressure.stableSummary", { delta: Math.abs(data.collapse_delta * 100).toFixed(1) })}
        </p>
      )}
    </div>
  );
}
