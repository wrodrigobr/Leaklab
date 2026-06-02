import { Info, Trophy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { ResultsVsGtoData } from "@/lib/api";

interface Props {
  data?: ResultsVsGtoData | null;
}

const CRIT = "#e52020";

/**
 * Results × GTO (#5) — "ganhei mas joguei errado".
 * Erros CLAROS de GTO (gto_critical) cometidos em mãos que o hero GANHOU: o
 * resultado mascara o erro de processo. Coaching: vencer não valida a jogada.
 * Posições/streets/ações ficam em inglês (termos de poker, não traduzir).
 */
export function ResultsVsGtoCard({ data }: Props) {
  const { t } = useTranslation("dashboard");

  if (!data || data.won_evaluated < 10) {
    return (
      <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
            {t("resultsVsGto.title")}
          </span>
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
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Trophy className="size-3.5 text-amber-400" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          {t("resultsVsGto.title")}
        </span>
        <HudTooltip content={t("resultsVsGto.tooltip")} />
      </div>

      {/* Headline: erros claros escondidos atrás de vitórias */}
      <div className="flex items-end gap-3">
        <span className="font-mono text-3xl font-bold leading-none" style={{ color: CRIT }}>
          {data.won_critical}
        </span>
        <span className="text-[11px] leading-tight text-muted-foreground pb-0.5">
          {t("resultsVsGto.headline_label")}
        </span>
      </div>

      {/* Dois stats de contexto */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-md border border-border/60 bg-background/40 px-2.5 py-2">
          <div className="font-mono text-lg font-bold" style={{ color: CRIT }}>
            {data.pct_won_were_critical}%
          </div>
          <div className="text-[10px] leading-tight text-muted-foreground">
            {t("resultsVsGto.stat_won_were_critical")}
          </div>
        </div>
        <div className="rounded-md border border-border/60 bg-background/40 px-2.5 py-2">
          <div className="font-mono text-lg font-bold text-amber-400">
            {data.pct_critical_hidden}%
          </div>
          <div className="text-[10px] leading-tight text-muted-foreground">
            {t("resultsVsGto.stat_critical_hidden")}
          </div>
        </div>
      </div>

      {/* Spots recorrentes (won + critical) — termos de poker em inglês */}
      {data.top_spots.length > 0 && (
        <div className="space-y-1.5">
          <div className="font-mono text-[9px] font-semibold uppercase tracking-wider text-foreground/60">
            {t("resultsVsGto.spots_title")}
          </div>
          <div className="space-y-1">
            {data.top_spots.map((s, i) => (
              <div key={i} className="flex items-center justify-between text-[11px]">
                <span className="font-mono text-foreground/80">
                  <span className="text-primary/70">{s.position}</span>
                  {" · "}{s.street}{" · "}{s.action}
                </span>
                <span className="font-mono text-muted-foreground">×{s.n}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mensagem de coaching */}
      <p className="text-[10px] leading-snug text-muted-foreground border-t border-border/40 pt-2">
        {t("resultsVsGto.coaching")}
      </p>
    </div>
  );
}
