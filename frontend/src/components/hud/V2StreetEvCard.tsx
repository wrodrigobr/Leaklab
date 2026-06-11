import { useTranslation } from "react-i18next";
import { EvSummary } from "@/lib/api";

/**
 * V2StreetEvCard — UX-2 onda 2. "Onde você sangra": bb perdidos por street em
 * barras horizontais com escala compartilhada — 1 olhada mostra a street que
 * mais custa (e onde o estudo rende mais).
 */
const STREET_COLOR: Record<string, string> = {
  preflop: "#A78BFA", flop: "#60A5FA", turn: "#FBBF24", river: "#F87171",
};

export function V2StreetEvCard({ evSummary }: { evSummary: EvSummary | null }) {
  const { t } = useTranslation("dashboard");
  const rows = evSummary?.by_street ?? [];
  if (!rows.length) return null;
  const max = Math.max(...rows.map((r) => r.loss_bb), 0.1);

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-3">
        {t("v2.streetTitle")}
      </div>
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.street} className="flex items-center gap-3">
            <span className="font-mono text-[10px] uppercase w-14 shrink-0 text-muted-foreground">
              {r.street}
            </span>
            <div className="flex-1 h-2.5 rounded-full bg-muted/15 overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${Math.max(4, (r.loss_bb / max) * 100)}%`,
                  background: `linear-gradient(90deg, ${STREET_COLOR[r.street] ?? "#8B96A8"}AA, ${STREET_COLOR[r.street] ?? "#8B96A8"})`,
                }}
              />
            </div>
            <span className="font-mono text-[12px] font-bold tabular-nums text-red-400 w-16 text-right">
              −{r.loss_bb.toFixed(1)}bb
            </span>
            <span className="font-mono text-[9px] text-muted-foreground w-12 text-right">
              {t("v2.streetSpots", { n: r.count })}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
