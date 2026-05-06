import { Swords, ChevronRight, Target, Clock } from "lucide-react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import type { DrillStats, DrillSpot } from "@/lib/api";
import { HudTooltip } from "./HudTooltip";

interface Props {
  stats: DrillStats | null;
  pendingSpots?: DrillSpot[];
}

export function GhostDrillCard({ stats, pendingSpots }: Props) {
  const { t } = useTranslation("dashboard");
  const hasActivity = stats && stats.total > 0;
  const overdueCount = (pendingSpots ?? []).filter(
    (s) => s.days_overdue != null && s.days_overdue > 0
  ).length;

  return (
    <section
      aria-labelledby="ghost-drill-heading"
      className="rounded-xl border border-border bg-hud-surface overflow-hidden"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2
          id="ghost-drill-heading"
          className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground"
        >
          <Swords className="size-3" aria-hidden />
          {t("ghost.title")}
          <HudTooltip content={t("ghost.tooltip")} />
        </h2>
        <div className="flex items-center gap-2">
          {overdueCount > 0 && (
            <span className="flex items-center gap-1 font-mono text-[10px] text-warning">
              <Clock className="size-3" aria-hidden />
              {overdueCount} atrasado{overdueCount > 1 ? "s" : ""}
            </span>
          )}
          <span className="font-mono text-[10px] text-muted-foreground">30d</span>
        </div>
      </div>

      {hasActivity ? (
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="font-mono text-xl font-bold tabular-nums text-foreground">
                {stats.total}
              </p>
              <p className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                {t("ghost.spots")}
              </p>
            </div>
            <div>
              <p className={cn(
                "font-mono text-xl font-bold tabular-nums",
                stats.accuracy != null && stats.accuracy >= 60 ? "text-primary" : "text-muted-foreground"
              )}>
                {stats.accuracy != null ? `${stats.accuracy}%` : "—"}
              </p>
              <p className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                {t("ghost.accuracy")}
              </p>
            </div>
            <div>
              <p className={cn(
                "font-mono text-xl font-bold tabular-nums",
                stats.avg_delta != null && stats.avg_delta < 0 ? "text-success" : "text-muted-foreground"
              )}>
                {stats.avg_delta != null
                  ? (stats.avg_delta < 0
                    ? stats.avg_delta.toFixed(3)
                    : `+${stats.avg_delta.toFixed(3)}`)
                  : "—"}
              </p>
              <p className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                Δ avg
              </p>
            </div>
          </div>

          <Link
            to="/ghost"
            className="flex items-center justify-between w-full rounded-lg border border-border px-3 py-2 font-mono text-xs text-muted-foreground hover:border-primary/40 hover:text-primary hover:bg-primary/5 transition-colors"
          >
            {t("ghost.continueStudy")}
            <ChevronRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      ) : (
        <div className="p-5 flex flex-col items-center gap-3 text-center">
          <p className="text-xs text-muted-foreground">{t("ghost.noActivity")}</p>
          <Link
            to="/ghost"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-mono text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-glow transition-colors"
          >
            <Target className="size-3.5" aria-hidden />
            {t("ghost.startNow")}
          </Link>
        </div>
      )}
    </section>
  );
}
