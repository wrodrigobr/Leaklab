import React from "react";
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
  | "gto"        // Solver — autoridade máxima (roxo/primary)
  | "preflop"    // Preflop RegLife — autoridade média (foreground)
  | "engine"     // Heurística do engine — autoridade baixa (muted)
  | "heuristic"  // Sem cobertura GTO — fallback (cinza)
  | "pushfold"   // Push/Fold zone — modo binário (amber)
  | "na";        // Spot incompatível — sem dado válido (orange)

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
}

interface Props {
  verdict: DecisionVerdict;
  source: DecisionSource;
  playedAction: string;
  idealAction?: string | null;
  idealLabel?: string;              // "Recomendado" (default) | "GTO recomenda" | etc
  isActionOk: boolean;
  evidence?: React.ReactNode;        // slot 3 — 1 widget primário (sempre visível)
  indicators?: React.ReactNode;      // slot 4 — chips/rows numéricos secundários (sempre visíveis)
  footer?: DecisionFooter;
  why?: string;                      // texto explicativo — escondido por padrão (toggle)
  proNotes?: React.ReactNode;        // notas longas profissionais — escondidas por padrão (toggle)
  showDetails: boolean;
  onToggleDetails: () => void;
  verdictTooltip?: string;
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

export function DecisionCard({
  verdict,
  source,
  playedAction,
  idealAction,
  idealLabel = "Recomendado",
  isActionOk,
  evidence,
  indicators,
  why,
  proNotes,
  footer,
  showDetails,
  onToggleDetails,
  verdictTooltip,
  fmtAction,
}: Props) {
  const showTwoCols =
    !!idealAction &&
    !isActionOk &&
    idealAction.toLowerCase() !== playedAction.toLowerCase();

  const hasFooter =
    footer &&
    (footer.stackBb != null || footer.mRatio != null || footer.icmPressure != null);

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
            title={showDetails ? "Ocultar detalhes" : "Mostrar detalhes"}
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
              Você jogou
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
                {idealLabel}
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
            {footer!.stackBb != null && (
              <span className="font-mono text-[10px]" title="Stack efetivo do hero em big blinds">
                <span className="text-muted-foreground">Stack </span>
                <span className="font-bold tabular-nums text-foreground/80">
                  {footer!.stackBb.toFixed(1)}bb
                </span>
              </span>
            )}
            {footer!.mRatio != null && (
              <span
                className="font-mono text-[10px]"
                title="M-Ratio: stack / custo médio de uma órbita. M < 10 = pressão, M < 5 = zona crítica"
              >
                <span className="text-muted-foreground">M </span>
                <span className={cn(
                  "font-bold tabular-nums",
                  footer!.mRatio <= 5 ? "text-destructive" :
                  footer!.mRatio <= 10 ? "text-amber-400" : "text-foreground/80"
                )}>
                  {footer!.mRatio.toFixed(1)}
                </span>
              </span>
            )}
            {footer!.icmPressure != null && (
              <span
                className={cn(
                  "font-mono text-[10px] font-bold uppercase",
                  footer!.icmPressure === "critical" ? "text-destructive" :
                  footer!.icmPressure === "high"     ? "text-amber-400"   :
                  footer!.icmPressure === "medium"   ? "text-sky-400"     : "text-muted-foreground"
                )}
                title="Pressão ICM: impacto das eliminações no valor esperado em torneio"
              >
                ICM {
                  footer!.icmPressure === "low" ? "baixo" :
                  footer!.icmPressure === "medium" ? "médio" :
                  footer!.icmPressure === "high" ? "alto" : footer!.icmPressure
                }
              </span>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
