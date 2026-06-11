import { useTranslation } from "react-i18next";
import { EvSummary } from "@/lib/api";

/**
 * V2CoverageCard — UX-2 onda 1. Anéis radiais (conic-gradient puro, sem lib)
 * para a cobertura do solver por street group — substitui o chip de texto.
 * Postflop cresce sozinho (fila SJF + dedup) → nota "em análise".
 */
function Ring({ pct, color, label }: { pct: number | null | undefined; color: string; label: string }) {
  const v = pct ?? 0;
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className="size-[84px] rounded-full grid place-items-center"
        style={{ background: `conic-gradient(${color} ${v}%, #151D33 ${v}% 100%)` }}
      >
        <div className="size-[64px] rounded-full bg-card grid place-items-center font-mono text-base font-bold">
          {pct != null ? `${Math.round(v)}%` : "—"}
        </div>
      </div>
      <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{label}</span>
    </div>
  );
}

export function V2CoverageCard({ evSummary }: { evSummary: EvSummary | null }) {
  const { t } = useTranslation("dashboard");
  const cov = evSummary?.coverage;
  if (!cov || (cov.preflop_pct == null && cov.postflop_pct == null)) return null;

  return (
    <div className="rounded-xl ring-1 ring-border bg-card/60 p-4">
      <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground mb-3">
        {t("v2.covTitle")}
      </div>
      <div className="flex items-center justify-around gap-3">
        <Ring pct={cov.preflop_pct} color="#2DD4BF" label={t("v2.covPre")} />
        <Ring pct={cov.postflop_pct} color="#60A5FA" label={t("v2.covPost")} />
      </div>
      {(cov.postflop_pct ?? 100) < 95 && (
        <p className="mt-3 text-[11px] text-muted-foreground leading-snug">{t("v2.covNote")}</p>
      )}
    </div>
  );
}
