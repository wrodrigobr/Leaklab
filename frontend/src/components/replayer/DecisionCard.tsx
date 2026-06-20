import React from "react";
import { useTranslation } from "react-i18next";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * DecisionCard — template único de notificação de jogada.
 *
 * Sempre visível (visão profissional):
 *   1. Verdict bar       — icon + label + source badge + toggle
 *   2. Action comparison — Você jogou (+ Recomendado se diverge)
 *   3. Evidence          — 1 widget primário (range bar | math card | solver bars | equity bar)
 *   4. Indicators        — chips/rows secundários (audit chain, SPR, Sizing) — DADOS, não texto
 *   5. Context footer    — Stack · M · ICM
 *
 * Toggle (👁 — visão didática para iniciantes):
 *   - Why (1 frase explicativa do veredict)
 *   - pro_notes (notas profissionais longas)
 *
 * Princípio: profissional não precisa de prosa, precisa de números.
 * Toggle reveals explicação narrativa; indicadores ficam sempre à vista.
 */

export type DecisionSourceVariant =
  | "gto"        // Solver: autoridade máxima (roxo/primary)
  | "preflop"    // Preflop GTO Solver, autoridade média (foreground)
  | "engine"     // Heurística do engine, autoridade baixa (muted)
  | "heuristic"  // Sem cobertura GTO, fallback (cinza)
  | "pushfold"   // Push/Fold zone, modo binário (amber)
  | "multiway"   // Estimativa multiway (equity vs range), solver é HU (teal/amber)
  | "na";        // Spot incompatível: sem dado válido (orange)

export interface DecisionVerdict {
  icon: string;
  label: string;
  cls: string;
  borderCls: string;
  hdrCls: string;
}

export interface DecisionSource {
  label: string;
  tooltip: string;
  variant: DecisionSourceVariant;
}

export interface DecisionFooter {
  stackBb?: number | null;
  mRatio?: number | null;
  icmPressure?: string | null;
  icmTaxPct?: number | null;   // mesa final: chip% − equity ICM% (None fora dela)
}

// Badge direcional de ICM (mesa final) — rótulos vêm localizados do Replayer (i18n).
export interface IcmBadge {
  label: string;
  tooltip: string;
  tone: "risk" | "survival" | "neutral";  // risk=pilha grande, survival=short stack
}

interface Props {
  verdict: DecisionVerdict;
  source: DecisionSource;
  playedAction: string;
  idealAction?: string | null;
  idealLabel?: string;              // "Recomendado" (default) | "GTO recomenda" | etc
  isActionOk: boolean;
  evidence?: React.ReactNode;        // slot 3, 1 widget primário (sempre visível)
  indicators?: React.ReactNode;      // slot 4, chips/rows numéricos secundários (sempre visíveis)
  footer?: DecisionFooter;
  icmBadge?: IcmBadge | null;        // badge direcional ICM (mesa final), substitui o chip "ICM alto"
  why?: string;                      // texto explicativo, escondido por padrão (toggle)
  proNotes?: React.ReactNode;        // notas longas profissionais, escondidas por padrão (toggle)
  showDetails: boolean;
  onToggleDetails: () => void;
  verdictTooltip?: string;
  evLossBb?: number | null;          // #24, bb perdidos vs a melhor ação (preflop)
  fmtAction: (a: string) => string;
}

const SOURCE_VARIANT_CLS: Record<DecisionSourceVariant, string> = {
  gto:       "text-primary bg-primary/10 ring-primary/30",
  preflop:   "text-foreground/80 bg-background/60 ring-border",
  engine:    "text-muted-foreground bg-background/40 ring-border/50",
  heuristic: "text-muted-foreground bg-muted/40 ring-border/60",
  pushfold:  "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  multiway:  "text-teal-300 bg-teal-500/10 ring-teal-500/30",
  na:        "text-orange-400 bg-orange-500/10 ring-orange-500/30",
};

export function DecisionCard({
  verdict,
  source,
  playedAction,
  idealAction,
  idealLabel,
  isActionOk,
  evidence,
  indicators,
  why,
  proNotes,
  footer,
  icmBadge,
  showDetails,
  onToggleDetails,
  verdictTooltip,
  evLossBb,
  fmtAction,
}: Props) {
  const { t } = useTranslation("replayer");
  const showTwoCols =
    !!idealAction &&
    !isActionOk &&
    idealAction.toLowerCase() !== playedAction.toLowerCase();

  const hasFooter =
    !!icmBadge ||
    (footer &&
      (footer.stackBb != null || footer.mRatio != null || footer.icmPressure != null));

  const ICM_TONE_CLS: Record<IcmBadge["tone"], string> = {
    risk:     "text-amber-400 bg-amber-500/10 ring-amber-500/30",
    survival: "text-sky-400 bg-sky-500/10 ring-sky-500/30",
    neutral:  "text-muted-foreground bg-background/40 ring-border/50",
  };

  return (
    <section className={cn("rounded-xl border overflow-hidden", verdict.borderCls)}>
      {/* ── Slot 1: Verdict bar ──────────────────────────────────────── */}
      <div className={cn("flex items-center justify-between px-3 py-2.5", verdict.hdrCls)}>
        <span
          className={cn("font-mono text-sm font-bold uppercase tracking-wide", verdict.cls)}
          title={verdictTooltip}
        >
          {verdict.icon} {verdict.label}
        </span>
        <div className="flex items-center gap-2">
          {/* #24 — EV-loss: bb perdidos vs a melhor jogada (preflop) */}
          {evLossBb != null && evLossBb > 0.05 && (
            <span
              className={cn(
                "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-wide ring-1 cursor-help",
                evLossBb >= 2
                  ? "text-red-300 bg-red-500/10 ring-red-500/30"
                  : evLossBb >= 0.5
                  ? "text-orange-300 bg-orange-500/10 ring-orange-500/30"
                  : "text-amber-300 bg-amber-500/10 ring-amber-500/30",
              )}
              title={t("card.evLossTip")}
            >
              −{evLossBb.toFixed(evLossBb >= 10 ? 0 : 1)} bb
            </span>
          )}
          <span
            className={cn(
              "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide ring-1 cursor-help",
              SOURCE_VARIANT_CLS[source.variant]
            )}
            title={source.tooltip}
          >
            {source.label}
          </span>
          <button
            onClick={onToggleDetails}
            title={showDetails ? t("card.toggleHide") : t("card.toggleShow")}
            className="text-muted-foreground/60 hover:text-foreground transition-colors"
          >
            {showDetails ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
          </button>
        </div>
      </div>

      <div className="p-3 space-y-3">
        {/* ── Slot 2: Action comparison ────────────────────────────────── */}
        <div className={cn("grid gap-2", showTwoCols ? "grid-cols-2" : "grid-cols-1")}>
          <div className="rounded-lg px-2.5 py-2 ring-1 bg-background/60 ring-border/50">
            <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground mb-0.5">
              {t("card.youPlayed")}
            </div>
            <div className={cn(
              "font-mono text-sm font-bold uppercase",
              isActionOk ? verdict.cls : "text-foreground"
            )}>
              {fmtAction(playedAction)}
            </div>
          </div>
          {showTwoCols && (
            <div className="rounded-lg px-2.5 py-2 ring-1 bg-background/60 ring-border/50">
              <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground mb-0.5">
                {idealLabel ?? t("card.recommended")}
              </div>
              <div className={cn("font-mono text-sm font-bold uppercase", verdict.cls)}>
                {fmtAction(idealAction!)}
              </div>
            </div>
          )}
        </div>

        {/* ── Slot 3: Evidence (widget primário, sempre visível) ──────── */}
        {evidence && <div>{evidence}</div>}

        {/* ── Slot 4: Indicators (chips/rows secundários, sempre visíveis) ── */}
        {indicators && (
          <div className="space-y-1.5 pt-1 border-t border-border/30">
            {indicators}
          </div>
        )}

        {/* ── Toggle (visão didática): Why + pro_notes ──────────────────
            Profissional vê só dados (slots 3 e 4). Toggle revela texto. */}
        {showDetails && (why || proNotes) && (
          <div className="space-y-2 pt-1 border-t border-border/30">
            {why && (
              <p className="text-[13px] text-muted-foreground leading-relaxed">
                {why}
              </p>
            )}
            {proNotes}
          </div>
        )}

        {/* ── Slot 5: Context footer ──────────────────────────────────── */}
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
              <span
                className="font-mono text-[10px]"
                title={t("card.mTip")}
              >
                <span className="text-muted-foreground">M </span>
                <span className={cn(
                  "font-bold tabular-nums",
                  footer.mRatio <= 5 ? "text-destructive" :
                  footer.mRatio <= 10 ? "text-amber-400" : "text-foreground/80"
                )}>
                  {footer.mRatio.toFixed(1)}
                </span>
              </span>
            )}
            {/* Mesa final: badge direcional do ICM (calculate_icm) substitui o chip
                heurístico "ICM alto/médio/baixo", é o sinal mais informativo ali. */}
            {icmBadge ? (
              <span
                className={cn(
                  "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide ring-1 cursor-help",
                  ICM_TONE_CLS[icmBadge.tone]
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
                  footer.icmPressure === "medium"   ? "text-sky-400"     : "text-muted-foreground"
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
