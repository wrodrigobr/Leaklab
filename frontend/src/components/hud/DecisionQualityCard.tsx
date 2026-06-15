import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";

interface Props {
  byLabel?: Record<string, number>;
}

// FEAT-20: breakdown em 3 níveis (Correto/Aceitável/Erro). Erro = small + clear (severidade).
// Paleta idêntica ao card: correct=emerald, acceptable=sky, error=red.
const LABEL_COLORS = [
  { key: "correct",    color: "bg-emerald-400", text: "text-emerald-400" },
  { key: "acceptable", color: "bg-sky-400",     text: "text-sky-400" },
  { key: "error",      color: "bg-red-400",     text: "text-red-400" },
] as const;

export function DecisionQualityCard({ byLabel }: Props) {
  const { t } = useTranslation("dashboard");
  const { t: tc } = useTranslation("common");
  // colapsa as 4 severidades internas em 3 contagens de display.
  const by3 = {
    correct:    byLabel?.standard ?? 0,
    acceptable: byLabel?.marginal ?? 0,
    error:      (byLabel?.small_mistake ?? 0) + (byLabel?.clear_mistake ?? 0),
  };
  const total = by3.correct + by3.acceptable + by3.error;

  const LABELS = [
    { key: "correct",    label: tc("verdict.correct"),    color: "bg-emerald-400", text: "text-emerald-400" },
    { key: "acceptable", label: tc("verdict.acceptable"), color: "bg-sky-400",     text: "text-sky-400" },
    { key: "error",      label: tc("verdict.error"),      color: "bg-red-400",     text: "text-red-400" },
  ];

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("decisions.title")}
          </span>
          <HudTooltip content={t("decisions.tooltip")} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{total > 0 ? t("decisions.total", { n: total }) : "—"}</span>
      </div>

      {total === 0 ? (
        <p className="text-xs text-muted-foreground">{t("decisions.noData")}</p>
      ) : (
        <>
          <div className="flex h-3 w-full overflow-hidden rounded-full gap-px mb-4">
            {LABEL_COLORS.map(({ key, color }) => {
              const n = by3[key] ?? 0;
              const pct = total > 0 ? (n / total) * 100 : 0;
              if (pct === 0) return null;
              return (
                <div
                  key={key}
                  className={`${color} transition-all`}
                  style={{ width: `${pct}%` }}
                  title={`${pct.toFixed(1)}%`}
                />
              );
            })}
          </div>

          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            {LABELS.map(({ key, label, text }) => {
              const n = by3[key as keyof typeof by3] ?? 0;
              const pct = total > 0 ? (n / total) * 100 : 0;
              return (
                <div key={key} className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground truncate">{label}</span>
                  <span className={`font-mono text-[11px] font-bold tabular-nums ${text}`}>
                    {pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
