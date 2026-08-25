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
  | "motor"      // Sem equilíbrio COM custo medido: leitura do motor, NÃO é GTO (âmbar)
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

// Exportado para o `DecisionCardV2` reusar: dois mapas de cor para a MESMA fonte
// divergiriam calados, e a fonte e justamente o que o v2 nao pode perder.
export const SOURCE_VARIANT_CLS: Record<DecisionSourceVariant, string> = {
  gto:       "text-primary bg-primary/10 ring-primary/30",
  preflop:   "text-foreground/80 bg-background/60 ring-border",
  engine:    "text-muted-foreground bg-background/40 ring-border/50",
  heuristic: "text-muted-foreground bg-muted/40 ring-border/60",
  pushfold:  "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  multiway:  "text-teal-300 bg-teal-500/10 ring-teal-500/30",
  na:        "text-orange-400 bg-orange-500/10 ring-orange-500/30",
  // `motor` NÃO pode herdar o visual de `gto` (roxo/primary, autoridade máxima): é justamente a
  // decisão em que o produto admite não ter equilíbrio com custo por trás. Âmbar sóbrio — visível
  // como ressalva, sem alarme de erro.
  motor:     "text-amber-200/90 bg-amber-500/8 ring-amber-500/25",
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
      {/* pr-10 reserva o canto top-right pro X (fechar) do modal de análise — o card só é
          renderizado dentro desse modal, então o grupo (source + toggle "olho") não encosta no X. */}
      <div className={cn("flex items-center justify-between pl-3 pr-10 py-2.5", verdict.hdrCls)}>
        <span
          className={cn("font-mono text-sm font-bold uppercase tracking-wide", verdict.cls)}
          title={verdictTooltip}
        >
          {verdict.icon} {verdict.label}
        </span>
        <div className="flex items-center gap-2">
          {/* Ausência de EV EXPLICADA, não silenciosa (paridade com o card compacto, que já
              fazia isso): o selo simplesmente sumir deixa o jogador sem saber se ele não perdeu
              nada ou se o produto não sabe. Só quando há acusação — em "correto" o EV perto de
              zero não precisa de explicação. */}
          {evLossBb == null && !isActionOk && (
            <span
              className="inline-flex items-center rounded-md bg-muted/20 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground/70 ring-1 ring-border/50 cursor-help"
              title={t("card.evUnavailable")}
            >
              EV ?
            </span>
          )}
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
        {/* ── Slot 4: indicadores, ATRÁS DO OLHO ────────────────────────
            Ao tirar o `why` do toggle, o olho ficou sem trabalho: só restava `proNotes`, que
            quase nunca existe — um controle que não faz nada é pior que controle nenhum.
            A divisão agora segue o que o card se propõe a responder: a LEITURA (veredito, ação,
            custo, porquê) fica sempre visível, e os DADOS de auditoria (equity, pot odds, mín.
            EV, sizing, cadeia) abrem no olho, para quem quer conferir a conta. */}
        {showDetails && indicators && (
          <div className="space-y-1.5 pt-1 border-t border-border/30">
            {indicators}
          </div>
        )}

        {/* ── O PORQUÊ, sempre visível ──────────────────────────────────
            Antes vivia atrás do toggle ("profissional vê só dados"), e o resultado medido era um
            card só de números: o backend GERA a explicação e a tela não mostrava. Um veredito sem
            leitura obriga o jogador a inferir o motivo — que é justamente o que ele veio buscar.
            O toggle continua existindo, agora só para as pro_notes. */}
        {why && (
          <p className="text-[13px] leading-relaxed text-foreground/75 pt-1 border-t border-border/30">
            {why}
          </p>
        )}
        {showDetails && proNotes && (
          <div className="space-y-2 pt-1 border-t border-border/30">
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
