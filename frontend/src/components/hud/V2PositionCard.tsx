import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { GtoPositionData } from "@/lib/api";

/**
 * V2PositionCard — UX-2 onda 3. Versão V2 do GtoPositionCard: barras horizontais
 * de alinhamento por posição (mesma linguagem do V2StreetEvCard), cor pela faixa
 * de alinhado% e marcador de crítico% na ponta. Clássico segue com o card antigo.
 */
function barColor(aligned: number): string {
  if (aligned >= 70) return "#10b981";
  if (aligned >= 50) return "#f59e0b";
  return "#e52020";
}

export function V2PositionCard({ data }: { data?: GtoPositionData | null }) {
  const { t } = useTranslation("dashboard");
  const rows = (data?.by_position ?? []).filter((r) => r.with_gto >= 5);

  if (!data || data.total_with_gto < 10 || rows.length === 0) {
    return (
      <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("gtoPosition.title")}</span>
          <HudTooltip content={t("gtoPosition.tooltip")} />
        </div>
        <div className="flex items-start gap-2 text-[11px] text-muted-foreground">
          <Info className="size-3.5 mt-0.5 shrink-0 text-primary/50" />
          <span>{t("gtoNotice.needMoreData")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("gtoPosition.title")}</span>
          <HudTooltip content={t("gtoPosition.tooltip")} />
        </div>
        <span className="font-mono text-[9px] text-muted-foreground/70">
          {t("gtoPosition.coverage", { n: data.total_with_gto, pct: data.overall_coverage_pct })}
        </span>
      </div>

      <div className="space-y-2.5">
        {rows.map((r) => {
          const color = barColor(r.aligned_pct);
          return (
            <div key={r.position} className="flex items-center gap-3">
              <span className="font-mono text-[10px] font-bold uppercase text-muted-foreground w-12 shrink-0">
                {r.position}
              </span>
              <div className="flex-1 h-2.5 rounded-full bg-muted/15 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.max(2, r.aligned_pct)}%`,
                    background: `linear-gradient(90deg, ${color}99, ${color})`,
                  }}
                />
              </div>
              <span className="font-mono text-[11px] font-bold tabular-nums w-10 text-right shrink-0" style={{ color }}>
                {r.aligned_pct.toFixed(0)}%
              </span>
              <span
                className={`font-mono text-[9px] tabular-nums w-14 text-right shrink-0 ${
                  r.critical_pct > 0 ? "text-red-400/80" : "text-muted-foreground/40"
                }`}
              >
                {r.critical_pct > 0 ? t("v2.posCritical", { pct: r.critical_pct.toFixed(0) }) : "—"}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-3 pt-2 border-t border-border/30 font-mono text-[9px] text-muted-foreground/70">
        {t("v2.posHint")}
      </div>
    </div>
  );
}
