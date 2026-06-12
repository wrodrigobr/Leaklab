import { useTranslation } from "react-i18next";
import { Crosshair, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { HudTooltip } from "./HudTooltip";
import type { StrategicTwinProfile, TwinSpot } from "@/lib/api";

/**
 * V2TwinCard — UX-2 onda 4. Versão V2 do StrategicTwinCard: casca V2, barras de
 * erro com gradiente vermelho e tick teal na média pessoal. SEM narrativa (vive
 * no carrossel de IA do V2 — dedup da onda 3). Clássico segue com o antigo.
 */
function spotLabel(spot: TwinSpot, t: (key: string) => string): string {
  const raw    = (k: string, fb: string) => { const v = t(k); return v === k ? fb : v; };
  const action = raw(`strategicTwin.actions.${spot.best_action}`, spot.best_action);
  const street = raw(`strategicTwin.streets.${spot.street}`,     spot.street);
  const icm    = raw(`strategicTwin.icm.${spot.icm_pressure}`,   spot.icm_pressure);
  return `${action} ${street} · ${icm}`;
}

function DeltaIcon({ delta }: { delta: number }) {
  if (delta > 0.05)  return <TrendingUp   className="size-3 text-red-400 shrink-0" />;
  if (delta < -0.05) return <TrendingDown className="size-3 text-emerald-400 shrink-0" />;
  return <Minus className="size-3 text-muted-foreground shrink-0" />;
}

function SpotRow({ spot, avgRate, t }: { spot: TwinSpot; avgRate: number; t: (k: string) => string }) {
  const errPct   = Math.round(spot.error_rate * 100);
  const deltaPct = Math.round(spot.delta_from_avg * 100);
  const isAbove  = spot.delta_from_avg > 0.05;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-foreground truncate">{spotLabel(spot, t)}</span>
        <span className={`font-mono text-[11px] font-bold tabular-nums shrink-0 ${isAbove ? "text-red-400" : "text-muted-foreground"}`}>
          {errPct}%
        </span>
      </div>

      <div className="relative h-2.5 rounded-full bg-muted/15 overflow-hidden">
        <div
          className="absolute left-0 top-0 h-full rounded-full transition-all"
          style={{
            width: `${Math.min(100, Math.max(2, errPct))}%`,
            background: "linear-gradient(90deg, #f8717199, #f87171)",
          }}
        />
        <div
          className="absolute top-0 h-full w-px bg-teal-300/70"
          style={{ left: `${Math.min(100, Math.round(avgRate * 100))}%` }}
          title={t("strategicTwin.avgLine")}
        />
      </div>

      <div className="flex items-center gap-1">
        <DeltaIcon delta={spot.delta_from_avg} />
        <span className={`font-mono text-[9px] tabular-nums ${isAbove ? "text-red-400/80" : "text-muted-foreground"}`}>
          {deltaPct > 0 ? `+${deltaPct}` : deltaPct}% {t("strategicTwin.vsAvg")}
        </span>
        <span className="text-[9px] text-muted-foreground/60 ml-auto">
          {t("strategicTwin.nDecisions", { n: spot.total })}
        </span>
      </div>
    </div>
  );
}

export function V2TwinCard({ data }: { data: StrategicTwinProfile }) {
  const { t } = useTranslation("dashboard");

  if (data.insufficient_data) {
    return (
      <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Crosshair className="size-4 text-primary" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("strategicTwin.title")}</span>
          <HudTooltip content={t("strategicTwin.tooltip")} />
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{t("strategicTwin.noData")}</p>
      </div>
    );
  }

  const avgPct   = Math.round((data.player_avg_error_rate ?? 0) * 100);
  const costly   = data.costly_spots ?? [];
  const hasSpots = costly.length > 0;

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Crosshair className="size-4 text-primary" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("strategicTwin.title")}</span>
          <HudTooltip content={t("strategicTwin.tooltip")} />
        </div>
        <span className="font-mono text-[9px] text-muted-foreground/70">
          {t("strategicTwin.avgLabel")} <span className="font-bold text-foreground/80">{avgPct}%</span>
        </span>
      </div>

      {!hasSpots ? (
        <p className="text-xs text-muted-foreground leading-relaxed">{t("strategicTwin.noPatterns")}</p>
      ) : (
        <>
          <p className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/70 mb-3">
            {t("strategicTwin.costlyTitle")}
          </p>
          <div className="space-y-4">
            {costly.slice(0, 3).map((spot, i) => (
              <SpotRow key={i} spot={spot} avgRate={data.player_avg_error_rate ?? 0} t={t} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
