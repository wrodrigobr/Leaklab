import { useTranslation } from "react-i18next";
import { Crosshair, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import { AiText } from "@/components/ui/AiText";
import type { StrategicTwinProfile, TwinSpot } from "@/lib/api";

function spotLabel(
  spot: TwinSpot,
  t: (key: string) => string
): string {
  const raw    = (k: string, fb: string) => { const v = t(k); return v === k ? fb : v; };
  const action = raw(`strategicTwin.actions.${spot.best_action}`, spot.best_action);
  const street = raw(`strategicTwin.streets.${spot.street}`,     spot.street);
  const icm    = raw(`strategicTwin.icm.${spot.icm_pressure}`,   spot.icm_pressure);
  return `${action} ${street} · ${icm}`;
}

function DeltaIcon({ delta }: { delta: number }) {
  if (delta > 0.05)  return <TrendingUp   className="size-3 text-destructive shrink-0" />;
  if (delta < -0.05) return <TrendingDown  className="size-3 text-emerald-400 shrink-0" />;
  return <Minus className="size-3 text-muted-foreground shrink-0" />;
}

function SpotRow({ spot, avgRate, t }: { spot: TwinSpot; avgRate: number; t: (k: string) => string }) {
  const errPct  = Math.round(spot.error_rate * 100);
  const deltaPct = Math.round(spot.delta_from_avg * 100);
  const barWidth = Math.min(100, errPct);
  const avgWidth = Math.min(100, Math.round(avgRate * 100));
  const isAbove  = spot.delta_from_avg > 0.05;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-foreground truncate">
          {spotLabel(spot, t)}
        </span>
        <span className={`font-mono text-[10px] font-bold shrink-0 ${isAbove ? "text-destructive" : "text-muted-foreground"}`}>
          {errPct}%
        </span>
      </div>

      <div className="relative h-1.5 flex-1 rounded-full bg-border overflow-hidden">
        <div
          className="absolute left-0 top-0 h-full rounded-full bg-destructive/70 transition-all"
          style={{ width: `${barWidth}%` }}
        />
        <div
          className="absolute top-0 h-full w-px bg-primary/60"
          style={{ left: `${avgWidth}%` }}
          title={t("strategicTwin.avgLine")}
        />
      </div>

      <div className="flex items-center gap-1 pl-0">
        <DeltaIcon delta={spot.delta_from_avg} />
        <span className={`font-mono text-[9px] ${isAbove ? "text-destructive/80" : "text-muted-foreground"}`}>
          {deltaPct > 0 ? `+${deltaPct}` : deltaPct}% {t("strategicTwin.vsAvg")}
        </span>
        <span className="text-[9px] text-muted-foreground/60 ml-auto">
          {t("strategicTwin.nDecisions", { n: spot.total })}
        </span>
      </div>
    </div>
  );
}

export function StrategicTwinCard({ data, hideNarrative = false }: { data: StrategicTwinProfile; hideNarrative?: boolean }) {
  const { t } = useTranslation("dashboard");

  if (data.insufficient_data) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-5 hud-glare">
        <div className="flex items-center gap-1.5 mb-3">
          <Crosshair className="size-4 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("strategicTwin.title")}
          </span>
          <HudTooltip content={t("strategicTwin.tooltip")} />
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">
          {t("strategicTwin.noData")}
        </p>
      </div>
    );
  }

  const avgPct    = Math.round((data.player_avg_error_rate ?? 0) * 100);
  const costly    = data.costly_spots ?? [];
  const hasSpots  = costly.length > 0;

  return (
    <div className="rounded-xl border border-border bg-hud-surface hud-glare overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-1.5">
          <Crosshair className="size-4 text-primary" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground">
            {t("strategicTwin.title")}
          </span>
          <HudTooltip content={t("strategicTwin.tooltip")} />
        </div>
        <div className="flex items-center gap-1">
          <span className="font-mono text-[10px] text-muted-foreground">
            {t("strategicTwin.avgLabel")}
          </span>
          <span className="font-mono text-[11px] font-bold text-foreground">
            {avgPct}%
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {!hasSpots ? (
          <p className="text-xs text-muted-foreground leading-relaxed">
            {t("strategicTwin.noPatterns")}
          </p>
        ) : (
          <>
            <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/70">
              {t("strategicTwin.costlyTitle")}
            </p>
            <div className="space-y-4">
              {costly.slice(0, 3).map((spot, i) => (
                <SpotRow
                  key={i}
                  spot={spot}
                  avgRate={data.player_avg_error_rate ?? 0}
                  t={t}
                />
              ))}
            </div>
          </>
        )}

        {data.narrative && !hideNarrative && (
          <div className="border-t border-border/50 pt-3">
            <AiText size="xs">{data.narrative}</AiText>
          </div>
        )}
      </div>
    </div>
  );
}
