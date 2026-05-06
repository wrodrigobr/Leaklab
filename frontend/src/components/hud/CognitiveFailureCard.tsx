import { useTranslation } from "react-i18next";
import { Brain, AlertCircle, AlertTriangle, Info } from "lucide-react";
import { AiText } from "@/components/ui/AiText";
import { HudTooltip } from "./HudTooltip";
import type { CognitiveFailureData, CognitivePattern } from "@/lib/api";

const SEVERITY_BADGE: Record<string, string> = {
  high:   "bg-destructive/15 text-destructive",
  medium: "bg-orange-500/15 text-orange-400",
  low:    "bg-yellow-500/15 text-yellow-400",
};

const SEVERITY_BAR: Record<string, string> = {
  high:   "bg-destructive",
  medium: "bg-orange-500",
  low:    "bg-yellow-500",
};

const SEVERITY_ICON_COLOR: Record<string, string> = {
  high:   "text-destructive",
  medium: "text-orange-400",
  low:    "text-yellow-400",
};

function SeverityIcon({ severity }: { severity: string }) {
  const cls = `size-3 shrink-0 ${SEVERITY_ICON_COLOR[severity] ?? "text-muted-foreground"}`;
  if (severity === "high")   return <AlertCircle className={cls} />;
  if (severity === "medium") return <AlertTriangle className={cls} />;
  return <Info className={cls} />;
}

function PatternRow({ pattern }: { pattern: CognitivePattern }) {
  const { t } = useTranslation("dashboard");
  const barWidth = Math.min(100, Math.round(pattern.frequency * 200));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <SeverityIcon severity={pattern.severity} />
          <span className="text-xs font-medium text-foreground truncate">
            {t(`cognitiveFailure.patterns.${pattern.type}`)}
          </span>
        </div>
        <span className={`inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase shrink-0 ${SEVERITY_BADGE[pattern.severity] ?? ""}`}>
          {t(`cognitiveFailure.severity.${pattern.severity}`)}
        </span>
      </div>

      <div className="flex items-center gap-2 pl-5">
        <div className="h-1 flex-1 rounded-full bg-border overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${SEVERITY_BAR[pattern.severity] ?? "bg-primary"}`}
            style={{ width: `${barWidth}%` }}
          />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground shrink-0 w-7 text-right">
          {Math.round(pattern.frequency * 100)}%
        </span>
      </div>

      <p className="text-[11px] text-muted-foreground pl-5 leading-snug">
        {t(`cognitiveFailure.descriptions.${pattern.type}`)}
      </p>
    </div>
  );
}

export function CognitiveFailureCard({ data }: { data: CognitiveFailureData }) {
  const { t } = useTranslation("dashboard");

  if (data.insufficient_data || data.patterns.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
        <div className="flex items-center gap-1.5 mb-3">
          <Brain className="size-4 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("cognitiveFailure.title")}
          </span>
          <HudTooltip content={t("cognitiveFailure.tooltip")} />
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {data.insufficient_data
            ? t("cognitiveFailure.noData")
            : t("cognitiveFailure.noPatterns")}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-hud-surface hud-glare overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-1.5">
          <Brain className="size-4 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("cognitiveFailure.title")}
          </span>
          <HudTooltip content={t("cognitiveFailure.tooltip")} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {t("cognitiveFailure.decisions", { count: data.total_decisions })}
        </span>
      </div>

      <div className="p-4 space-y-4">
        {data.patterns.map((p) => (
          <PatternRow key={p.type} pattern={p} />
        ))}

        {data.narrative && (
          <div className="border-t border-border/50 pt-3">
            <AiText size="xs">{data.narrative}</AiText>
          </div>
        )}
      </div>
    </div>
  );
}
