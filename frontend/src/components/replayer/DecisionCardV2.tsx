import React from "react";
import { useTranslation } from "react-i18next";
import { Eye, EyeOff, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  DecisionVerdict, DecisionSource, DecisionFooter, IcmBadge, DecisionSourceVariant,
} from "./DecisionCard";

/**
 * DecisionCardV2 — UX-3 (specs/ux-proposal-2026.html).
 *
 * Mesma interface de props do DecisionCard (drop-in, troca via toggle no
 * Replayer; o v1 permanece intacto). Filosofia INVERTIDA:
 *   v1: dados sempre visíveis, prosa atrás do toggle (visão profissional)
 *   v2: história primeiro — CUSTO em bb como manchete, "por quê" sempre
 *       visível, matemática (indicators/proNotes) atrás do toggle.
 *
 * Hierarquia: 1. Veredito + custo (manchete) → 2. Você vs Melhor (1 linha)
 *             → 3. Evidência (range + sua mão) → 4. Por quê → 5. Contexto.
 */

interface Props {
  verdict: DecisionVerdict;
  source: DecisionSource;
  playedAction: string;
  idealAction?: string | null;
  idealLabel?: string;
  isActionOk: boolean;
  evidence?: React.ReactNode;
  indicators?: React.ReactNode;
  footer?: DecisionFooter;
  icmBadge?: IcmBadge | null;
  why?: string;
  proNotes?: React.ReactNode;
  showDetails: boolean;
  onToggleDetails: () => void;
  verdictTooltip?: string;
  evLossBb?: number | null;
  fmtAction: (a: string) => string;
}

const SOURCE_VARIANT_CLS: Record<DecisionSourceVariant, string> = {
  gto:       "text-primary bg-primary/10 ring-primary/30",
  preflop:   "text-foreground/80 bg-background/60 ring-border",
  engine:    "text-muted-foreground bg-background/40 ring-border/50",
  heuristic: "text-muted-foreground bg-muted/40 ring-border/60",
  pushfold:  "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  na:        "text-orange-400 bg-orange-500/10 ring-orange-500/30",
};

const ICM_TONE_CLS: Record<IcmBadge["tone"], string> = {
  risk:     "text-amber-400 bg-amber-500/10 ring-amber-500/30",
  survival: "text-sky-400 bg-sky-500/10 ring-sky-500/30",
  neutral:  "text-muted-foreground bg-background/40 ring-border/50",
};

export function DecisionCardV2({
  verdict, source, playedAction, idealAction, idealLabel, isActionOk,
  evidence, indicators, why, proNotes, footer, icmBadge,
  showDetails, onToggleDetails, verdictTooltip, evLossBb, fmtAction,
}: Props) {
  const { t } = useTranslation("replayer");
  const diverges =
    !!idealAction && !isActionOk &&
    idealAction.toLowerCase() !== playedAction.toLowerCase();

  const hasCost  = evLossBb != null && evLossBb > 0.05;
  const isMaxEv  = evLossBb != null && evLossBb <= 0.05 && isActionOk;
  const costCls  = hasCost
    ? (evLossBb! >= 2 ? "text-red-400" : evLossBb! >= 0.5 ? "text-orange-300" : "text-amber-300")
    : "text-emerald-400";

  const hasFooter =
    !!icmBadge ||
    (footer &&
      (footer.stackBb != null || footer.mRatio != null || footer.icmPressure != null));

  return (
    <section className={cn("rounded-xl border overflow-hidden", verdict.borderCls)}>
      {/* ── 1. Veredito + CUSTO como manchete ───────────────────────── */}
      <div className={cn("px-3 py-2.5", verdict.hdrCls)}>
        <div className="flex items-center justify-between">
          <span
            className={cn("font-mono text-xs font-bold uppercase tracking-wide", verdict.cls)}
            title={verdictTooltip}
          >
            {verdict.icon} {verdict.label}
          </span>
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide ring-1 cursor-help",
                SOURCE_VARIANT_CLS[source.variant],
              )}
              title={source.tooltip}
            >
              {source.label}
            </span>
            <button
              onClick={onToggleDetails}
              title={showDetails ? t("card.v2HideMath") : t("card.v2ShowMath")}
              className="text-muted-foreground/60 hover:text-foreground transition-colors"
            >
              {showDetails ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
            </button>
          </div>
        </div>
        {/* manchete: custo da decisão em bb (EV da mão) */}
        {(hasCost || isMaxEv) && (
          <div className="mt-1.5 flex items-baseline gap-2" title={t("card.evLossTip")}>
            <span className={cn("font-mono text-2xl font-bold tabular-nums", costCls)}>
              {hasCost ? `−${evLossBb!.toFixed(evLossBb! >= 10 ? 0 : 1)} bb` : "±0,0 bb"}
            </span>
            <span className="text-[10px] text-muted-foreground leading-tight">
              {hasCost ? t("card.v2CostSub") : t("card.v2MaxEv")}
            </span>
            {isMaxEv && <CheckCircle2 className="size-3.5 text-emerald-400" />}
          </div>
        )}
      </div>

      <div className="p-3 space-y-3">
        {/* ── 2. Você vs Melhor — 1 linha compacta ───────────────────── */}
        <div className="flex items-center gap-2 font-mono text-sm">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {t("card.youPlayed")}
          </span>
          <span className={cn("font-bold uppercase", isActionOk ? verdict.cls : "text-foreground")}>
            {fmtAction(playedAction)}
          </span>
          {diverges && (
            <>
              <span className="text-muted-foreground/50">→</span>
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                {idealLabel ?? t("card.recommended")}
              </span>
              <span className={cn("font-bold uppercase", verdict.cls)}>
                {fmtAction(idealAction!)}
              </span>
            </>
          )}
        </div>

        {/* ── 3. Evidência (range + "Sua mão") ────────────────────────── */}
        {evidence && <div>{evidence}</div>}

        {/* ── 4. Por quê — SEMPRE visível no v2 ───────────────────────── */}
        {why && (
          <div className="rounded-lg bg-background/50 ring-1 ring-border/40 px-2.5 py-2">
            <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-1">
              {t("card.v2WhyTitle")}
            </div>
            <p className="text-[13px] text-foreground/90 leading-relaxed">{why}</p>
          </div>
        )}

        {/* ── Matemática (indicators + proNotes) — atrás do toggle ────── */}
        {showDetails && (indicators || proNotes) && (
          <div className="space-y-2 pt-1 border-t border-border/30">
            {indicators && <div className="space-y-1.5">{indicators}</div>}
            {proNotes}
          </div>
        )}

        {/* ── 5. Contexto ─────────────────────────────────────────────── */}
        {hasFooter && (
          <div className="flex items-center flex-wrap gap-x-3 gap-y-1 pt-1 border-t border-border/30">
            {footer?.stackBb != null && (
              <span className="font-mono text-[10px]" title={t("card.stackTip")}>
                <span className="text-muted-foreground">Stack </span>
                <span className="font-bold tabular-nums text-foreground/80">
                  {footer.stackBb.toFixed(1)}bb
                </span>
              </span>
            )}
            {footer?.mRatio != null && (
              <span className="font-mono text-[10px]" title={t("card.mTip")}>
                <span className="text-muted-foreground">M </span>
                <span className={cn(
                  "font-bold tabular-nums",
                  footer.mRatio <= 5 ? "text-destructive" :
                  footer.mRatio <= 10 ? "text-amber-400" : "text-foreground/80",
                )}>
                  {footer.mRatio.toFixed(1)}
                </span>
              </span>
            )}
            {icmBadge ? (
              <span
                className={cn(
                  "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide ring-1 cursor-help",
                  ICM_TONE_CLS[icmBadge.tone],
                )}
                title={icmBadge.tooltip}
              >
                {icmBadge.label}
              </span>
            ) : footer?.icmPressure != null && (
              <span
                className={cn(
                  "font-mono text-[10px] font-bold uppercase",
                  footer.icmPressure === "critical" ? "text-destructive" :
                  footer.icmPressure === "high"     ? "text-amber-400"   :
                  footer.icmPressure === "medium"   ? "text-sky-400"     : "text-muted-foreground",
                )}
                title={t("card.icmTip")}
              >
                ICM {
                  footer.icmPressure === "low" ? t("card.icmLow") :
                  footer.icmPressure === "medium" ? t("card.icmMedium") :
                  footer.icmPressure === "high" ? t("card.icmHigh") : footer.icmPressure
                }
              </span>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
