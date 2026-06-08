import { Info, Crosshair } from "lucide-react";
import { useTranslation } from "react-i18next";
import { HudTooltip } from "./HudTooltip";
import type { LeakFinderData, LeakFinderLeak } from "@/lib/api";

interface Props {
  data?: LeakFinderData | null;
}

// Cor por severidade (EV perdido). Termos de poker (posição/street/ação) em inglês.
const SEV_CLR: Record<LeakFinderLeak["severity"], string> = {
  high:   "#e52020",
  medium: "#f59e0b",
  low:    "#fbbf24",
};

/**
 * Leak Finder consolidado (#25) — carro-chefe "GrindLab".
 * Vazamentos priorizados pelo EV PERDIDO (bb deixados na mesa), não por contagem
 * de erros. Reusa get_ev_leaks (#24). Cada leak linka pro estudo/drill do spot.
 */
export function LeakFinderCard({ data }: Props) {
  const { t } = useTranslation("dashboard");

  const empty = !data || !data.has_ev;

  return (
    <div className="rounded-xl border border-border bg-hud-surface p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Crosshair className="size-3.5 text-primary" />
        <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          {t("leakFinder.title")}
        </span>
        <HudTooltip content={t("leakFinder.tooltip")} />
      </div>

      {empty ? (
        <div className="flex items-start gap-2 text-[11px] text-muted-foreground">
          <Info className="size-3.5 mt-0.5 shrink-0 text-primary/50" />
          <span>{t("gtoNotice.needMoreData")}</span>
        </div>
      ) : (
        <>
          {/* Headline: total de bb deixados na mesa */}
          <div className="flex items-end gap-3">
            <span className="font-mono text-3xl font-bold leading-none text-foreground">
              −{data!.total_ev_loss_bb.toFixed(1)}
              <span className="text-base text-muted-foreground"> bb</span>
            </span>
            <span className="text-[11px] leading-tight text-muted-foreground pb-1">
              {t("leakFinder.headline_label", { n: data!.n_leaks })}
            </span>
          </div>

          {/* Lista priorizada dos top leaks por EV */}
          <div className="space-y-1.5">
            <div className="font-mono text-[9px] font-semibold uppercase tracking-wider text-foreground/60">
              {t("leakFinder.spots_title")}
            </div>
            <div className="space-y-1">
              {data!.leaks.map((l, i) => (
                <div key={i} className="flex items-center justify-between gap-2 text-[11px]">
                  <span className="font-mono text-foreground/80 truncate">
                    <span className="text-primary/70">{l.position}</span>
                    {" · "}{l.street}{" · "}
                    <span className="text-muted-foreground">{t("leakFinder.idealPrefix")} {l.ideal_action}</span>
                    <span className="text-muted-foreground/60"> ×{l.n}</span>
                  </span>
                  <span
                    className="font-mono font-bold tabular-nums shrink-0"
                    style={{ color: SEV_CLR[l.severity] }}
                    title={t(`leakFinder.sev_${l.severity}`)}
                  >
                    −{l.total_ev_loss_bb.toFixed(1)} bb
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Coaching: priorize o topo */}
          <p className="text-[10px] leading-snug text-muted-foreground border-t border-border/40 pt-2">
            {t("leakFinder.coaching")}
          </p>
        </>
      )}
    </div>
  );
}
