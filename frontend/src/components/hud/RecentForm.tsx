import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { HudTooltip } from "./HudTooltip";
import type { EvolutionPoint } from "@/lib/api";

interface Props {
  evolution?: EvolutionPoint[];
}

export function RecentForm({ evolution }: Props) {
  const { t } = useTranslation("dashboard");
  const recent = (evolution ?? []).slice(-10).reverse();

  function scoreDot(score: number) {
    if (score <= 0.08) return { bg: "bg-primary",     ring: "ring-primary/40",     label: t("form.standard") };
    if (score <= 0.18) return { bg: "bg-yellow-500",  ring: "ring-yellow-500/40",  label: t("form.marginal") };
    if (score <= 0.36) return { bg: "bg-orange-500",  ring: "ring-orange-500/40",  label: t("form.smallMistake") };
    return              { bg: "bg-destructive",   ring: "ring-destructive/40", label: t("form.clearError") };
  }

  const legend = [
    { label: t("form.standard"),    bg: "bg-primary" },
    { label: t("form.marginal"),    bg: "bg-yellow-500" },
    { label: t("form.error"),       bg: "bg-orange-500" },
    { label: t("form.clearError"),  bg: "bg-destructive" },
  ];

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("form.title")}
          </span>
          <HudTooltip content={t("form.tooltip")} />
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">{t("form.tournaments", { n: recent.length })}</span>
      </div>

      {recent.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("form.noData")}</p>
      ) : (
        <div className="flex items-center gap-2 flex-wrap">
          {recent.map((pt, i) => {
            const score = pt.avg_score ?? 0;
            const { bg, ring, label } = scoreDot(score);
            const id = pt.tournament_id ?? i;
            return (
              <div key={id} className="flex flex-col items-center gap-1" title={`Score: ${score.toFixed(3)} · ${label}`}>
                <div className={cn("size-4 rounded-full ring-2 transition-transform hover:scale-125 cursor-default", bg, ring)} />
                {i === 0 && (
                  <span className="font-mono text-[8px] text-muted-foreground/60">{t("form.now")}</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {recent.length > 0 && (
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          {legend.map(({ label, bg }) => (
            <div key={label} className="flex items-center gap-1">
              <span className={cn("size-2 rounded-full", bg)} />
              <span className="font-mono text-[9px] text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
