import { Info, Trophy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { ResultsVsGtoData } from "@/lib/api";

/**
 * V2ResultsCard — UX-2 onda 4. Versão V2 do ResultsVsGtoCard ("ganhei mas
 * joguei errado"): headline + os dois percentuais como barras de gradiente
 * (linguagem das barras do V2) em vez de caixinhas. Clássico segue com o antigo.
 */
function StatBar({ pct, color, label }: { pct: number; color: string; label: string }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] leading-tight text-muted-foreground">{label}</span>
        <span className="font-mono text-[12px] font-bold tabular-nums shrink-0" style={{ color }}>
          {pct}%
        </span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-muted/15 overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${Math.min(100, pct)}%`, background: `linear-gradient(90deg, ${color}99, ${color})` }}
        />
      </div>
    </div>
  );
}

export function V2ResultsCard({ data }: { data?: ResultsVsGtoData | null }) {
  const { t } = useTranslation("dashboard");

  if (!data || data.won_evaluated < 10) {
    return (
      <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("resultsVsGto.title")}</span>
          <HudTooltip content={t("resultsVsGto.tooltip")} />
        </div>
        <div className="flex items-start gap-2 text-[11px] text-muted-foreground">
          <Info className="size-3.5 mt-0.5 shrink-0 text-primary/50" />
          <span>{t("gtoNotice.needMoreData")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Trophy className="size-3.5 text-amber-400" />
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("resultsVsGto.title")}</span>
        <HudTooltip content={t("resultsVsGto.tooltip")} />
      </div>

      <div className="flex items-end gap-3">
        <span className="font-mono text-3xl font-bold tabular-nums leading-none text-red-400">
          {data.won_critical}
        </span>
        <span className="text-[11px] leading-tight text-muted-foreground pb-0.5">
          {t("resultsVsGto.headline_label")}
        </span>
      </div>

      <div className="space-y-2.5">
        <StatBar pct={data.pct_won_were_critical} color="#f87171" label={t("resultsVsGto.stat_won_were_critical")} />
        <StatBar pct={data.pct_critical_hidden} color="#fbbf24" label={t("resultsVsGto.stat_critical_hidden")} />
      </div>

      {data.top_spots.length > 0 && (
        <div className="space-y-1.5 border-t border-border/30 pt-2.5">
          <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/70">
            {t("resultsVsGto.spots_title")}
          </div>
          <div className="space-y-1">
            {data.top_spots.map((s, i) => (
              <div key={i} className="flex items-center justify-between text-[11px]">
                <span className="font-mono text-foreground/80">
                  <span className="text-teal-300/80">{s.position}</span>
                  {" · "}{s.street}{" · "}{s.action}
                </span>
                <span className="font-mono tabular-nums text-muted-foreground">×{s.n}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[10px] leading-snug text-muted-foreground/80 border-t border-border/30 pt-2">
        {t("resultsVsGto.coaching")}
      </p>
    </div>
  );
}
