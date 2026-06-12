import { useTranslation } from "react-i18next";
import { Brain, AlertCircle, AlertTriangle, Info } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import type { CognitiveFailureData, CognitivePattern } from "@/lib/api";

/**
 * V2CognitiveCard — UX-2 onda 4. Versão V2 do CognitiveFailureCard: casca V2 +
 * barras de severidade com gradiente. SEM narrativa (vive no carrossel de IA do
 * V2 — dedup da onda 3). Clássico segue com o card antigo.
 */
const SEVERITY: Record<string, { color: string; badge: string }> = {
  high:   { color: "#e52020", badge: "bg-red-500/10 text-red-400 ring-1 ring-red-500/25" },
  medium: { color: "#f97316", badge: "bg-orange-500/10 text-orange-400 ring-1 ring-orange-500/25" },
  low:    { color: "#eab308", badge: "bg-yellow-500/10 text-yellow-400 ring-1 ring-yellow-500/25" },
};

function SeverityIcon({ severity }: { severity: string }) {
  const color = SEVERITY[severity]?.color ?? "#8B96A8";
  const cls = "size-3 shrink-0";
  if (severity === "high")   return <AlertCircle className={cls} style={{ color }} />;
  if (severity === "medium") return <AlertTriangle className={cls} style={{ color }} />;
  return <Info className={cls} style={{ color }} />;
}

function PatternRow({ pattern }: { pattern: CognitivePattern }) {
  const { t } = useTranslation("dashboard");
  const barWidth = Math.min(100, Math.round(pattern.frequency * 200));
  const sev = SEVERITY[pattern.severity] ?? SEVERITY.low;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <SeverityIcon severity={pattern.severity} />
          <span className="text-xs font-medium text-foreground truncate">
            {t(`cognitiveFailure.patterns.${pattern.type}`)}
          </span>
        </div>
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[9px] font-bold uppercase shrink-0 ${sev.badge}`}>
          {t(`cognitiveFailure.severity.${pattern.severity}`)}
        </span>
      </div>

      <div className="flex items-center gap-2 pl-5">
        <div className="h-1.5 flex-1 rounded-full bg-muted/15 overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${barWidth}%`, background: `linear-gradient(90deg, ${sev.color}99, ${sev.color})` }}
          />
        </div>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground shrink-0 w-7 text-right">
          {Math.round(pattern.frequency * 100)}%
        </span>
      </div>

      <p className="text-[11px] text-muted-foreground pl-5 leading-snug">
        {t(`cognitiveFailure.descriptions.${pattern.type}`)}
      </p>
    </div>
  );
}

export function V2CognitiveCard({ data }: { data: CognitiveFailureData }) {
  const { t } = useTranslation("dashboard");

  if (data.insufficient_data || data.patterns.length === 0) {
    return (
      <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="size-4 text-primary" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("cognitiveFailure.title")}</span>
          <HudTooltip content={t("cognitiveFailure.tooltip")} />
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {data.insufficient_data ? t("cognitiveFailure.noData") : t("cognitiveFailure.noPatterns")}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Brain className="size-4 text-primary" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("cognitiveFailure.title")}</span>
          <HudTooltip content={t("cognitiveFailure.tooltip")} />
        </div>
        <span className="font-mono text-[9px] text-muted-foreground/70">
          {t("cognitiveFailure.decisions", { count: data.total_decisions })}
        </span>
      </div>

      <div className="space-y-4">
        {data.patterns.map((p) => (
          <PatternRow key={p.type} pattern={p} />
        ))}
      </div>
    </div>
  );
}
