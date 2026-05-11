import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, Pause, Play, Rewind, FastForward, AlertOctagon, CheckCircle2, Loader2, ArrowLeft, GraduationCap, PenLine, X, Check, Trash2, LayoutGrid, Sigma, FlaskConical, Clock } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { HudLayout } from "@/components/hud/HudLayout";
import { HudHeader } from "@/components/hud/HudHeader";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { RangePanel } from "@/components/replayer/RangePanel";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { cn } from "@/lib/utils";
import { tournaments as tournamentsApi, coachDashboard, ReplayData, ReplayStep, TournamentDecision, CoachAnnotation, CoachOverrideLabel } from "@/lib/api";

// ── Card parsing ──────────────────────────────────────────────────────────────

function parseCard(raw: string): CardData {
  return {
    rank: raw.slice(0, -1) as CardData["rank"],
    suit: raw.slice(-1).toLowerCase() as CardData["suit"],
  };
}

function parseCards(arr: string[]): CardData[] {
  return arr.map(parseCard);
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function anonymizeDesc(desc: string, aliases: Record<string, string>): string {
  let result = desc;
  for (const [name, alias] of Object.entries(aliases)) {
    if (name !== alias) result = result.replace(new RegExp(escapeRegex(name), "g"), alias);
  }
  return result;
}

// ── SidePanels — AI Coach + GTO + Coach annotation + Showdown ────────────────

interface SidePanelsProps {
  step: ReplayStep;
  isError: boolean;
  isCorrect: boolean;
  coachAnnotation: CoachAnnotation | null;
  studentId: number | null;
  currentDecisionId: number | null;
  annotating: boolean;
  annComment: string;
  annMode: "complement" | "replace";
  annAction: string;
  annOverride: CoachOverrideLabel;
  saveAnn: ReturnType<typeof import("@tanstack/react-query").useMutation>;
  deleteAnn: ReturnType<typeof import("@tanstack/react-query").useMutation>;
  replayData: ReplayData;
  playerAliases: Record<string, string>;
  setAnnotating: (v: boolean) => void;
  setAnnComment: (v: string) => void;
  setAnnMode: (v: "complement" | "replace") => void;
  setAnnAction: (v: string) => void;
  setAnnOverride: (v: CoachOverrideLabel) => void;
  openAnnotationForm: () => void;
  t: (key: string, opts?: Record<string, unknown>) => string;
  gtoRequestStatus: "idle" | "requesting" | "queued" | "done" | "error";
  onRequestGto: () => void;
  tournamentId: string;
  handId: string;
}

function SidePanels({
  step, isError, isCorrect, coachAnnotation, studentId, currentDecisionId,
  annotating, annComment, annMode, annAction, annOverride,
  saveAnn, deleteAnn, replayData, playerAliases,
  setAnnotating, setAnnComment, setAnnMode, setAnnAction, setAnnOverride,
  openAnnotationForm, t,
  gtoRequestStatus, onRequestGto,
}: SidePanelsProps) {
  const hasGto    = !!step.gto_label;
  const isPostflop = step.street !== 'preflop';
  // True if the hand already has GTO analysis on at least one postflop hero action
  const handHasAnyGto = replayData.timeline.some(
    (s) => s.is_hero && s.type === "action" && s.street !== 'preflop' && !!s.gto_label
  );
  // True if this hand has at least one postflop hero action (GTO is applicable)
  const handHasPostflopAction = replayData.timeline.some(
    (s) => s.is_hero && s.type === "action" && s.street !== 'preflop'
  );
  const hasTech   = step.is_hero && step.type === "action" &&
                    (isError || hasGto || step.hand_equity != null);
  const totalPenalty = (step.math_penalty ?? 0) + (step.range_penalty ?? 0) + (step.context_penalty ?? 0);

  // GTO label display helpers
  const gtoMeta: Record<string, { label: string; cls: string; border: string }> = {
    gto_correct:         { label: "GTO Correto",      cls: "text-emerald-400", border: "border-emerald-500/30 bg-emerald-500/5" },
    gto_mixed:           { label: "GTO Misto",        cls: "text-sky-400",     border: "border-sky-500/30 bg-sky-500/5" },
    gto_minor_deviation: { label: "Desvio Leve",      cls: "text-amber-400",   border: "border-amber-500/30 bg-amber-500/5" },
    gto_critical:        { label: "Desvio Crítico",   cls: "text-red-400",     border: "border-red-500/30 bg-red-500/5" },
  };
  const gto = step.gto_label ? gtoMeta[step.gto_label] : null;

  return (
    <div className="flex flex-col gap-2">

      {/* ── Análise técnica — aparece para qualquer ação hero com dados ── */}
      {hasTech && (studentId !== null || coachAnnotation?.mode !== "replace") && (
        <section className={cn(
          "rounded-xl border p-3 space-y-3",
          isError ? "border-destructive/40 bg-destructive/5"
          : hasGto && step.gto_label === "gto_critical" ? "border-red-500/30 bg-red-500/5"
          : isCorrect ? "border-primary/30 bg-primary/5"
          : "border-border bg-hud-surface"
        )}>

          {/* Header: veredito engine */}
          <div className="flex items-center gap-2">
            {isError
              ? <AlertOctagon className="size-4 shrink-0 text-destructive" />
              : <CheckCircle2 className="size-4 shrink-0 text-primary" />}
            <span className={cn("font-mono text-[10px] font-bold uppercase tracking-widest-2 flex-1",
              isError ? "text-destructive" : "text-primary")}>
              {isError ? (step.error_label?.replace(/_/g," ") ?? "erro") : "decisão ok"}
            </span>
            {step.error_score != null && (
              <span className={cn("font-mono text-xs font-bold tabular-nums",
                step.error_score > 0.25 ? "text-destructive" : step.error_score > 0.08 ? "text-amber-400" : "text-primary")}>
                score {step.error_score.toFixed(3)}
              </span>
            )}
          </div>

          {/* Ação jogada vs recomendada */}
          {(step.action || step.best_action) && (
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-background/60 px-2.5 py-2 ring-1 ring-border/50">
                <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Jogou</div>
                <div className="font-mono text-sm font-bold text-foreground uppercase">{step.action ?? "—"}</div>
              </div>
              {step.best_action && (
                <div className="rounded-lg bg-primary/5 px-2.5 py-2 ring-1 ring-primary/20">
                  <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Ideal</div>
                  <div className="font-mono text-sm font-bold text-primary uppercase">{step.best_action}</div>
                </div>
              )}
            </div>
          )}

          {/* Equity */}
          {step.hand_equity != null && (
            <div className="space-y-1.5">
              <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Equity</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 rounded-full bg-border overflow-hidden">
                  <div
                    className={cn("h-full rounded-full transition-all",
                      step.hand_equity >= (step.pot_odds_equity ?? 0) ? "bg-primary" : "bg-destructive")}
                    style={{ width: `${(step.hand_equity * 100).toFixed(1)}%` }}
                  />
                </div>
                <span className={cn("font-mono text-sm font-bold tabular-nums shrink-0",
                  step.hand_equity >= (step.pot_odds_equity ?? 0) ? "text-primary" : "text-destructive")}>
                  {(step.hand_equity * 100).toFixed(1)}%
                </span>
              </div>
              {step.pot_odds_equity != null && (
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Equity necessária para call</span>
                  <span className="font-mono font-medium text-foreground">{(step.pot_odds_equity * 100).toFixed(1)}%</span>
                </div>
              )}
              {step.draw_profile && step.draw_profile !== "none" && (
                <div className="font-mono text-[10px] text-amber-400 uppercase tracking-wider">
                  Draw: {step.draw_profile.replace(/_/g, " ")}
                </div>
              )}
            </div>
          )}

          {/* Score breakdown */}
          {totalPenalty > 0 && (
            <div className="space-y-1.5">
              <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">Breakdown do score</div>
              {[
                { label: "Matemática", val: step.math_penalty ?? 0, color: "bg-red-500" },
                { label: "Range",      val: step.range_penalty ?? 0, color: "bg-amber-500" },
                { label: "Contexto",   val: step.context_penalty ?? 0, color: "bg-orange-500" },
              ].filter(r => r.val > 0).map((row) => (
                <div key={row.label} className="flex items-center gap-2">
                  <span className="w-16 font-mono text-[10px] text-muted-foreground">{row.label}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
                    <div className={cn("h-full rounded-full", row.color)}
                      style={{ width: `${Math.min(100, row.val * 400).toFixed(0)}%` }} />
                  </div>
                  <span className="font-mono text-[10px] tabular-nums text-muted-foreground w-10 text-right">
                    {row.val.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* M-Ratio / ICM */}
          {step.m_ratio != null && (
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span>M-Ratio: <span className="font-mono text-foreground font-medium">{step.m_ratio}</span></span>
              {step.icm_pressure && step.icm_pressure !== "low" && (
                <span className="text-amber-400 font-medium">ICM {step.icm_pressure}</span>
              )}
            </div>
          )}
        </section>
      )}

      {/* ── Preflop Range GTO — aparece apenas para hero actions preflop ── */}
      {step.is_hero && step.type === "action" && !isPostflop && step.preflop_gto?.available && (() => {
        const pg = step.preflop_gto!;
        const scenarioLabel: Record<string, string> = {
          rfi: "RFI — Raise First In",
          vs_rfi: "vs RFI — Defendendo",
          vs_3bet: "vs 3bet — Respondendo",
        };
        const qualityMeta: Record<string, { label: string; cls: string; border: string }> = {
          correct:    { label: "Correto",       cls: "text-emerald-400", border: "border-emerald-500/30 bg-emerald-500/5" },
          acceptable: { label: "Aceitável",     cls: "text-sky-400",     border: "border-sky-500/30 bg-sky-500/5" },
          leak:       { label: "Leak",          cls: "text-amber-400",   border: "border-amber-500/30 bg-amber-500/5" },
          major_leak: { label: "Leak Grave",    cls: "text-red-400",     border: "border-red-500/30 bg-red-500/5" },
          unknown:    { label: "Desconhecido",  cls: "text-muted-foreground", border: "border-border bg-hud-surface" },
        };
        const qm = qualityMeta[pg.action_quality] ?? qualityMeta.unknown;
        return (
          <section className={cn("rounded-xl border p-3 space-y-3", qm.border)}>
            {/* Header */}
            <div className="flex items-center gap-2">
              <Sigma className="size-4 shrink-0" />
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 flex-1 text-muted-foreground">
                Range GTO · Preflop
              </span>
              <span className={cn("font-mono text-[9px] font-bold uppercase", qm.cls)}>{qm.label}</span>
            </div>

            {/* Scenario + In Range */}
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] text-muted-foreground">{scenarioLabel[pg.scenario] ?? pg.scenario}</span>
              <span className={cn("font-mono text-[10px] font-bold", pg.in_range ? "text-emerald-400" : "text-red-400")}>
                {pg.in_range ? "✓ No range" : "✗ Fora do range"}
              </span>
            </div>

            {/* Jogou / Recomendado */}
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-background/60 px-2.5 py-2 ring-1 ring-border/50">
                <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Jogou</div>
                <div className="font-mono text-sm font-bold text-foreground uppercase">{pg.action_taken}</div>
              </div>
              <div className={cn("rounded-lg px-2.5 py-2 ring-1",
                pg.action_quality === "correct" ? "bg-emerald-500/10 ring-emerald-500/30" : "bg-background/60 ring-border/50")}>
                <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">GTO</div>
                <div className={cn("font-mono text-sm font-bold uppercase", qm.cls)}>
                  {pg.recommended_actions.join(" / ")}
                </div>
              </div>
            </div>

            {/* Range % */}
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Range abertura</span>
              <span className="font-mono font-medium text-foreground">{(pg.range_pct * 100).toFixed(0)}% das mãos</span>
            </div>

            {/* Stack bucket */}
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Stack depth</span>
              <span className="font-mono font-medium text-foreground">{pg.stack_bb} BB ({pg.stack_bucket})</span>
            </div>

            {/* Professional notes */}
            {pg.pro_notes.length > 0 && (
              <div className="space-y-1.5 pt-1 border-t border-border/40">
                {pg.pro_notes.map((note, i) => (
                  <p key={i} className="text-[11px] text-muted-foreground leading-relaxed">{note}</p>
                ))}
              </div>
            )}
          </section>
        );
      })()}

      {/* ── GTO não disponível — solicitar análise (apenas postflop) ── */}
      {step.is_hero && step.type === "action" && isPostflop && !hasGto && handHasPostflopAction && (
        <section className="rounded-xl border border-border bg-hud-surface p-3 space-y-2.5">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-4 shrink-0 text-muted-foreground" />
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground flex-1">
              Análise GTO
            </span>
            <span className="font-mono text-[9px] text-muted-foreground/60 uppercase">Não disponível</span>
          </div>
          {gtoRequestStatus === "idle" && (
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              Esta ação ainda não possui análise GTO. Solicite para que o solver calcule a estratégia ótima para este spot.
            </p>
          )}
          {gtoRequestStatus === "idle" && (
            <button
              onClick={onRequestGto}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary/10 hover:bg-primary/20 border border-primary/30 px-3 py-2 text-[11px] font-semibold text-primary transition-colors"
            >
              <Sigma className="size-3.5" />
              Solicitar Análise GTO
            </button>
          )}
          {gtoRequestStatus === "requesting" && (
            <div className="flex items-center justify-center gap-2 py-1.5 text-[11px] text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" />
              Enviando solicitação...
            </div>
          )}
          {gtoRequestStatus === "queued" && (
            <div className="flex items-center gap-2 rounded-lg bg-sky-500/5 border border-sky-500/20 px-2.5 py-2">
              <Loader2 className="size-3.5 text-sky-400 shrink-0 animate-spin" />
              <p className="text-[11px] text-sky-400">
                Na fila — verificando a cada 4s. Os resultados aparecerão automaticamente.
              </p>
            </div>
          )}
          {gtoRequestStatus === "solver_queued" && (
            <div className="flex items-start gap-2 rounded-lg bg-amber-500/5 border border-amber-500/20 px-2.5 py-2">
              <Loader2 className="size-3.5 text-amber-400 shrink-0 mt-px animate-spin" />
              <p className="text-[11px] text-amber-400 leading-relaxed">
                Spot enfileirado para o solver — ainda não temos dados GTO para este cenário. O cálculo pode levar alguns minutos. Volte mais tarde para ver os resultados.
              </p>
            </div>
          )}
          {gtoRequestStatus === "done" && (
            <div className="flex items-start gap-2 rounded-lg bg-amber-500/5 border border-amber-500/20 px-2.5 py-2">
              <Loader2 className="size-3.5 text-amber-400 shrink-0 mt-px animate-spin" />
              <p className="text-[11px] text-amber-400 leading-relaxed">
                Spot enfileirado para o solver — o cálculo pode levar alguns minutos. Volte mais tarde ou recarregue a página para ver os resultados.
              </p>
            </div>
          )}
          {gtoRequestStatus === "error" && (
            <div className="flex items-center gap-2 rounded-lg bg-destructive/5 border border-destructive/20 px-2.5 py-2">
              <AlertOctagon className="size-3.5 text-destructive shrink-0" />
              <p className="text-[11px] text-destructive">Erro ao solicitar. Tente novamente.</p>
            </div>
          )}
        </section>
      )}

      {/* ── GTO Analysis — seção dedicada ── */}
      {step.is_hero && step.type === "action" && hasGto && (
        <section className={cn("rounded-xl border p-3 space-y-3", gto?.border ?? "border-border bg-hud-surface")}>
          <div className="flex items-center gap-2">
            <Sigma className="size-4 shrink-0" style={{ color: gto?.cls?.replace("text-", "") }} />
            <span className={cn("font-mono text-[10px] font-bold uppercase tracking-widest-2 flex-1", gto?.cls)}>
              Análise GTO · {gto?.label}
            </span>
          </div>

          {/* Cards Jogou/GTO — ocultos quando o spot GTO não corresponde ao contexto */}
          {step.gto_action && !step.gto_spot_mismatch && (
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-background/60 px-2.5 py-2 ring-1 ring-border/50">
                <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Jogou</div>
                <div className="font-mono text-sm font-bold text-foreground uppercase">{step.action ?? "—"}</div>
              </div>
              <div className={cn("rounded-lg px-2.5 py-2 ring-1",
                step.gto_label === "gto_correct" ? "bg-emerald-500/10 ring-emerald-500/30"
                : "bg-background/60 ring-border/50")}>
                <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">GTO</div>
                <div className={cn("font-mono text-sm font-bold uppercase", gto?.cls)}>{step.gto_action}</div>
              </div>
            </div>
          )}

          {!step.gto_spot_mismatch && (
            <div className="text-xs text-muted-foreground leading-relaxed">
              {step.gto_label === "gto_correct" &&
                "Sua ação está alinhada com a estratégia GTO — frequência primária do solver."}
              {step.gto_label === "gto_mixed" &&
                "O solver mistura esta ação com outras opções. Não é um erro — ambas são válidas neste spot."}
              {step.gto_label === "gto_minor_deviation" &&
                "Desvio leve do GTO. Ação alternativa tem frequência baixa mas não é negligenciável."}
              {step.gto_label === "gto_critical" &&
                "Desvio crítico do GTO. O solver raramente (ou nunca) toma esta ação neste spot."}
            </div>
          )}

          {/* Spot incompatível — ação do GTO não faz sentido no contexto */}
          {step.gto_spot_mismatch && (
            <div className="flex items-start gap-1.5 rounded-lg bg-orange-500/5 border border-orange-500/25 px-2.5 py-2">
              <span className="text-orange-400 text-[10px] mt-px shrink-0">⚠</span>
              <p className="text-[10px] text-muted-foreground leading-relaxed">
                Spot GTO incompatível com esta situação:{" "}
                {step.engine_best === "call"
                  ? "você enfrentava uma aposta, mas o solver foi consultado para um spot sem aposta."
                  : "não havia aposta a enfrentar, mas o solver foi consultado para um spot com aposta."}
                {" "}A análise GTO desta mão precisa ser reprocessada para o contexto correto.
              </p>
            </div>
          )}

          {/* Conflito engine vs GTO — só exibe quando heurístico diverge do GTO */}
          {!step.gto_spot_mismatch && step.engine_best && step.gto_action &&
           step.engine_best !== step.gto_action && isError && (
            <div className="flex items-start gap-1.5 rounded-lg bg-amber-500/5 border border-amber-500/20 px-2.5 py-2">
              <span className="text-amber-400 text-[10px] mt-px shrink-0">⚠</span>
              <p className="text-[10px] text-muted-foreground leading-relaxed">
                O motor heurístico sugeriu{" "}
                <span className="font-mono font-bold text-foreground uppercase">{step.engine_best}</span>{" "}
                com base em equity e posição. O solver GTO é a fonte mais autoritativa.
              </p>
            </div>
          )}
          {/* Consenso engine + GTO — reforça a recomendação quando ambos concordam */}
          {!step.gto_spot_mismatch && step.engine_best && step.gto_action &&
           step.engine_best === step.gto_action && isError && (
            <div className="flex items-start gap-1.5 rounded-lg bg-emerald-500/5 border border-emerald-500/20 px-2.5 py-2">
              <span className="text-emerald-400 text-[10px] mt-px shrink-0">✓</span>
              <p className="text-[10px] text-muted-foreground leading-relaxed">
                Motor heurístico e solver GTO concordam:{" "}
                <span className="font-mono font-bold text-foreground uppercase">{step.gto_action}</span>{" "}
                era a jogada correta neste spot.
              </p>
            </div>
          )}
        </section>
      )}

      {/* ── Coach annotation (coach editing student hand) ── */}
      {studentId && step?.is_hero && step?.is_error && currentDecisionId && (
        <section className="rounded-xl border border-primary/30 bg-primary/5 p-3 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <GraduationCap className="size-4 text-primary" />
              <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
                {t("annotation.coachLabel")} · {coachAnnotation ? (coachAnnotation.mode === "replace" ? t("annotation.exclusive") : t("annotation.complement")) : t("annotation.title")}
              </span>
            </div>
            {!annotating && (
              <div className="flex items-center gap-2">
                <button onClick={openAnnotationForm} className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-primary transition-colors">
                  <PenLine className="size-3" />
                  {coachAnnotation ? t("annotation.edit") : t("annotation.annotate")}
                </button>
                {coachAnnotation && (
                  <button onClick={() => deleteAnn.mutate()} disabled={deleteAnn.isPending} className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-destructive transition-colors disabled:opacity-50">
                    {deleteAnn.isPending ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                  </button>
                )}
              </div>
            )}
          </div>
          {!annotating && coachAnnotation && (
            <div className="space-y-1">
              <p className="text-sm text-foreground leading-relaxed">{coachAnnotation.comment}</p>
              {coachAnnotation.coach_action && <p className="font-mono text-[11px] text-primary">→ Correto: {coachAnnotation.coach_action}</p>}
            </div>
          )}
          {!annotating && !coachAnnotation && <p className="text-xs text-muted-foreground">{t("annotation.noAnnotation")}</p>}
          {annotating && (
            <div className="space-y-3">
              <div className="flex gap-2">
                {(["complement", "replace"] as const).map((m) => (
                  <button key={m} type="button" onClick={() => setAnnMode(m)}
                    className={`flex-1 py-1.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest-2 border transition-colors ${annMode === m ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/50"}`}>
                    {m === "complement" ? t("annotation.complementMode") : t("annotation.replaceMode")}
                  </button>
                ))}
              </div>
              <textarea value={annComment} onChange={(e) => setAnnComment(e.target.value)} rows={3} placeholder={t("annotation.commentPlaceholder")}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40 resize-none" />
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">{t("annotation.correctAction")}</label>
                  <select value={annAction} onChange={(e) => setAnnAction(e.target.value)} className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40">
                    {["", "fold", "check", "call", "bet", "raise", "re-raise", "all-in"].map((a) => <option key={a} value={a}>{a || t("annotation.noSpecify")}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="font-mono text-[9px] uppercase tracking-widest-2 text-muted-foreground">{t("annotation.classification")}</label>
                  <select value={annOverride ?? ""} onChange={(e) => setAnnOverride((e.target.value || null) as CoachOverrideLabel)} className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40">
                    <option value="">{t("annotation.noVerdict")}</option>
                    <option value="standard">{t("annotation.overrideStandard")}</option>
                    <option value="marginal">{t("annotation.overrideMarginal")}</option>
                    <option value="small_mistake">{t("annotation.overrideSmall")}</option>
                    <option value="clear_mistake">{t("annotation.overrideClear")}</option>
                  </select>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => saveAnn.mutate()} disabled={!annComment.trim() || saveAnn.isPending}
                  className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 font-mono text-[10px] font-bold uppercase text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
                  {saveAnn.isPending ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                  {t("annotation.saveBtn")}
                </button>
                <button onClick={() => setAnnotating(false)} className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 font-mono text-[10px] text-muted-foreground hover:text-foreground">
                  <X className="size-3" /> {t("annotation.cancel")}
                </button>
                {coachAnnotation && (
                  <button onClick={() => deleteAnn.mutate()} disabled={deleteAnn.isPending} className="ml-auto inline-flex items-center gap-1.5 font-mono text-[10px] text-destructive hover:underline disabled:opacity-50">
                    <Trash2 className="size-3" /> {t("annotation.delete")}
                  </button>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {/* ── Coach annotation (student reading coach comment) ── */}
      {!studentId && coachAnnotation && (
        <section className={cn("rounded-xl border p-3 space-y-2", coachAnnotation.mode === "replace" ? "border-primary/50 bg-primary/8" : "border-primary/20 bg-primary/5")}>
          <div className="flex items-center gap-2 flex-wrap">
            <GraduationCap className="size-4 text-primary" />
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
              {t("annotation.coachLabel")} · {coachAnnotation.mode === "replace" ? t("annotation.exclusive") : t("annotation.complementTitle")}
            </span>
            {coachAnnotation.coach_override_label && (
              <span className={cn("font-mono text-[9px] font-bold px-1.5 py-0.5 rounded ring-1",
                coachAnnotation.coach_override_label === "standard" ? "text-primary ring-primary/30 bg-primary/10"
                : coachAnnotation.coach_override_label === "marginal" ? "text-yellow-500 ring-yellow-500/30 bg-yellow-500/10"
                : coachAnnotation.coach_override_label === "small_mistake" ? "text-amber-400 ring-amber-400/30 bg-amber-400/10"
                : "text-destructive ring-destructive/30 bg-destructive/10")}>
                {coachAnnotation.coach_override_label === "standard" ? t("annotation.overrideStandard")
                  : coachAnnotation.coach_override_label === "marginal" ? t("annotation.overrideMarginal")
                  : coachAnnotation.coach_override_label === "small_mistake" ? t("annotation.overrideSmall")
                  : t("annotation.overrideClear")}
              </span>
            )}
          </div>
          <p className="text-sm text-foreground leading-relaxed">{coachAnnotation.comment}</p>
          {coachAnnotation.coach_action && <p className="font-mono text-[11px] text-primary">→ Ação: {coachAnnotation.coach_action}</p>}
        </section>
      )}

      {/* ── Showdown result ── */}
      {step.type === "showdown" && step.summary && (
        <section className="rounded-xl border border-primary/30 bg-primary/5 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">{t("decision.handResult")}</span>
            {step.summary.total_pot != null && (
              <span className="text-xs text-muted-foreground">
                {t("decision.totalPot")}: <span className="font-mono font-medium text-foreground">{(step.summary.total_pot / (replayData?.bb ?? 100)).toFixed(1)} BB</span>
              </span>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            {step.summary.seats.map((sd, i) => (
              <div key={i} className={cn("flex items-center gap-2 text-xs rounded-lg px-2.5 py-1.5 ring-1",
                sd.outcome === "won" ? "bg-primary/10 ring-primary/30 text-primary font-semibold" : "ring-border/30 text-muted-foreground opacity-60")}>
                {sd.outcome === "won" && <span>🏆</span>}
                <span className="truncate flex-1">{playerAliases[sd.player] ?? sd.player}</span>
                {sd.hand_desc === "mucked" ? (
                  <span className="font-mono text-[10px] shrink-0 opacity-40 italic">{t("decision.mucked")}</span>
                ) : sd.cards?.length > 0 ? (
                  <div className="flex gap-0.5 shrink-0">
                    {parseCards(sd.cards).map((c, j) => <PlayingCard key={j} card={c} size="sm" />)}
                  </div>
                ) : null}
                {sd.hand_desc && sd.hand_desc !== "mucked" && sd.hand_desc !== "collected" && (
                  <span className="font-mono text-[10px] shrink-0">{sd.hand_desc}</span>
                )}
                {sd.outcome === "won" && <span className="font-mono font-bold shrink-0">+{sd.won}</span>}
              </div>
            ))}
          </div>
        </section>
      )}

    </div>
  );
}

// ── Replayer ──────────────────────────────────────────────────────────────────

const Replayer = () => {
  const [params]   = useSearchParams();
  const navigate   = useNavigate();
  const { t } = useTranslation("replayer");
  const tournamentId = params.get("t") ?? "";
  const handId       = params.get("h") ?? "";
  const studentId    = params.get("student") ? Number(params.get("student")) : null;

  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");
  const [stepIdx, setStepIdx]       = useState(0);
  const [playing, setPlaying]       = useState(false);
  const [speed, setSpeed]           = useState(1);
  const [handList, setHandList]     = useState<string[]>([]);
  const [betUnit, setBetUnit]       = useState<"chips" | "bb">("bb");
  const [decisions, setDecisions]   = useState<TournamentDecision[]>([]);
  const [showRange, setShowRange]           = useState(false);
  const [annotating, setAnnotating]         = useState(false);
  const [annComment, setAnnComment]         = useState("");
  const [annMode, setAnnMode]               = useState<"complement" | "replace">("complement");
  const [annAction, setAnnAction]           = useState("");
  const [annOverride, setAnnOverride]       = useState<CoachOverrideLabel>(null);
  const [gtoRequestStatus, setGtoRequestStatus] = useState<"idle" | "requesting" | "queued" | "solver_queued" | "done" | "error">("idle");

  // Floating Range panel drag state
  const [rangePos, setRangePos]         = useState({ x: 24, y: 96 });
  const isDraggingRange                 = useRef(false);
  const rangeDragStart                  = useRef({ mouseX: 0, mouseY: 0, panelX: 0, panelY: 0 });

  useEffect(() => {
    if (!tournamentId || !handId) return;
    setLoading(true);
    setError("");
    setStepIdx(0);
    setPlaying(false);
    setGtoRequestStatus("idle");

    const replayFn = studentId
      ? coachDashboard.studentReplay(studentId, tournamentId, handId)
      : tournamentsApi.replay(tournamentId, handId);

    const tournamentFn = studentId
      ? coachDashboard.studentTournament(studentId, tournamentId)
          .then((r) => ({ decisions: r.decisions }))
          .catch(() => null)
      : tournamentsApi.get(tournamentId).catch(() => null);

    Promise.all([replayFn, tournamentFn])
      .then(([replay, tournamentData]) => {
        setReplayData(replay);
        if (tournamentData) {
          const seen = new Set<string>();
          const ids: string[] = [];
          tournamentData.decisions.forEach((d) => {
            if (d.hand_id && !seen.has(d.hand_id)) { seen.add(d.hand_id); ids.push(d.hand_id); }
          });
          setHandList(ids);
          setDecisions(tournamentData.decisions);
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar replay"))
      .finally(() => setLoading(false));
  }, [tournamentId, handId, studentId]);

  const steps = replayData?.timeline ?? [];
  const step  = steps[stepIdx] as ReplayStep | undefined;

  // Hand navigation
  const handIdx  = handList.indexOf(handId);
  const prevHand = handIdx > 0 ? handList[handIdx - 1] : null;
  const nextHand = handIdx >= 0 && handIdx < handList.length - 1 ? handList[handIdx + 1] : null;

  // Alias map: todos os jogadores com nomes reais
  const playerAliases = useMemo<Record<string, string>>(() => {
    if (!replayData) return {};
    const aliases: Record<string, string> = {};
    Object.values(replayData.seats).forEach(({ player }) => {
      aliases[player] = player;
    });
    return aliases;
  }, [replayData]);

  // Cartas reveladas na mesa: mid-hand all-in shows + showdown
  // seat_str → cards (array vazio = muck, sem cartas exibidas)
  const revealedCards = useMemo<Record<string, string[]>>(() => {
    if (!step) return {};
    const rc: Record<string, string[]> = { ...(step.revealed_cards ?? {}) };
    if (step.type === "showdown" && step.summary?.seats) {
      for (const sd of step.summary.seats) {
        const seatKey = Object.keys(step.seats ?? {}).find(
          (k) => (step.seats as Record<string, { player: string }>)[k]?.player === sd.player
        );
        if (!seatKey) continue;
        if (sd.hand_desc === "mucked") {
          rc[seatKey] = [];         // muck: assento existe mas sem cartas
        } else if (sd.cards?.length >= 2) {
          rc[seatKey] = sd.cards;   // mostrou cartas
        }
      }
    }
    return rc;
  }, [step]);

  // Auto-play
  useEffect(() => {
    if (!playing || !step) return;
    const t = setTimeout(() => {
      setStepIdx((i) => {
        if (i < steps.length - 1) return i + 1;
        setPlaying(false);
        return i;
      });
    }, 1600 / speed);
    return () => clearTimeout(t);
  }, [playing, stepIdx, speed, steps.length, step]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") { e.preventDefault(); setPlaying((p) => !p); }
      if (e.code === "ArrowRight") setStepIdx((i) => Math.min(steps.length - 1, i + 1));
      if (e.code === "ArrowLeft")  setStepIdx((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [steps.length]);

  // Draggable Range panel
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDraggingRange.current) return;
      setRangePos({
        x: rangeDragStart.current.panelX + (e.clientX - rangeDragStart.current.mouseX),
        y: rangeDragStart.current.panelY + (e.clientY - rangeDragStart.current.mouseY),
      });
    };
    const onUp = () => { isDraggingRange.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const handleRangeDragStart = (e: React.MouseEvent<HTMLDivElement>) => {
    isDraggingRange.current = true;
    rangeDragStart.current = { mouseX: e.clientX, mouseY: e.clientY, panelX: rangePos.x, panelY: rangePos.y };
  };

  // Reset annotation form when step changes
  useEffect(() => { setAnnotating(false); }, [stepIdx]);

  // Coach annotation for current step — must be before early returns (Rules of Hooks)
  const coachAnnotation = useMemo(() => {
    const annotations = replayData?.coach_annotations;
    if (!annotations || !step?.is_error) return null;
    return Object.values(annotations).find(
      (a) => a.street === step.street && a.action_taken === step.action
    ) ?? null;
  }, [replayData?.coach_annotations, step?.is_error, step?.street, step?.action]);

  // decision_id for annotation save/delete (coaches only)
  const currentDecisionId = useMemo(() => {
    if (!studentId || !step?.is_error || !step.is_hero) return null;
    if (coachAnnotation) return coachAnnotation.decision_id;
    return decisions.find(
      (d) => d.hand_id === handId && d.street === step.street && d.action_taken === step.action
    )?.id ?? null;
  }, [studentId, step?.is_error, step?.is_hero, step?.street, step?.action, coachAnnotation, decisions, handId]);

  const saveAnn = useMutation({
    mutationFn: () => coachDashboard.upsertAnnotation(studentId!, {
      decision_id: currentDecisionId!,
      comment: annComment,
      mode: annMode,
      coach_action: annAction || undefined,
      coach_override_label: annOverride,
    }),
    onSuccess: (saved: CoachAnnotation) => {
      setReplayData((prev) => prev ? {
        ...prev,
        coach_annotations: { ...prev.coach_annotations, [String(saved.decision_id)]: saved },
      } : prev);
      setAnnotating(false);
    },
  });

  const deleteAnn = useMutation({
    mutationFn: () => coachDashboard.deleteAnnotation(studentId!, currentDecisionId!),
    onSuccess: () => {
      setReplayData((prev) => {
        if (!prev || !currentDecisionId) return prev;
        const anns = { ...prev.coach_annotations };
        delete anns[String(currentDecisionId)];
        return { ...prev, coach_annotations: anns };
      });
      setAnnotating(false);
    },
  });

  const openAnnotationForm = () => {
    setAnnComment(coachAnnotation?.comment ?? "");
    setAnnMode(coachAnnotation?.mode ?? "complement");
    setAnnAction(coachAnnotation?.coach_action ?? "");
    setAnnOverride(coachAnnotation?.coach_override_label ?? null);
    setAnnotating(true);
  };

  const handleRequestGto = async () => {
    if (!tournamentId || !handId) {
      console.warn("[GTO] handId ou tournamentId vazio", { tournamentId, handId });
      return;
    }
    console.log("[GTO] solicitando análise", { tournamentId, handId });
    setGtoRequestStatus("requesting");
    try {
      const res = await tournamentsApi.requestGtoAnalysis(tournamentId, handId);
      console.log("[GTO] resposta:", res);
      if (res.status === "done") {
        const replayFn = studentId
          ? coachDashboard.studentReplay(studentId, tournamentId, handId)
          : tournamentsApi.replay(tournamentId, handId);
        const fresh = await replayFn;
        setReplayData(fresh);
        setGtoRequestStatus("done");
      } else {
        setGtoRequestStatus("queued");
      }
    } catch (err) {
      console.error("[GTO] erro na solicitação:", err);
      setGtoRequestStatus("error");
    }
  };

  // Polling: enquanto status é "queued", verifica a cada 4s
  // Quando "done" ou "solver_queued", recarrega o replay
  useEffect(() => {
    if (gtoRequestStatus !== "queued") return;
    if (!tournamentId || !handId) return;

    const poll = setInterval(async () => {
      try {
        const s = await tournamentsApi.getGtoRequestStatus(handId);
        if (s.status === "done" || s.status === "solver_queued") {
          clearInterval(poll);
          const replayFn = studentId
            ? coachDashboard.studentReplay(studentId, tournamentId, handId)
            : tournamentsApi.replay(tournamentId, handId);
          const fresh = await replayFn;
          setReplayData(fresh);
          setGtoRequestStatus(s.status === "solver_queued" ? "solver_queued" : "done");
        } else if (s.status === "error") {
          clearInterval(poll);
          setGtoRequestStatus("error");
        }
      } catch {
        // ignora erros transitórios de rede
      }
    }, 4000);

    return () => clearInterval(poll);
  }, [gtoRequestStatus, tournamentId, handId, studentId]);

  // ── No params: show placeholder ──────────────────────────────────────────────
  if (!tournamentId || !handId) {
    return (
      <HudLayout eyebrow={t("eyebrow")} title={t("title")} description={t("description")}>
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-muted-foreground">
          <p className="text-sm">{t("noParams")}</p>
          <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 font-mono text-xs text-primary hover:underline">
            <ArrowLeft className="size-3.5" /> {t("back")}
          </button>
        </div>
      </HudLayout>
    );
  }

  if (loading) {
    return (
      <HudLayout eyebrow={t("eyebrow")} title={t("loading")} description="">
        <div className="flex items-center justify-center py-24 gap-3 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" />
          <span className="font-mono text-xs uppercase tracking-wider">{t("loadingHand")}</span>
        </div>
      </HudLayout>
    );
  }

  if (error) {
    return (
      <HudLayout eyebrow={t("eyebrow")} title={t("error")} description="">
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <p className="text-sm text-destructive">{error}</p>
          <button onClick={() => navigate(-1)} className="inline-flex items-center gap-2 font-mono text-xs text-primary hover:underline">
            <ArrowLeft className="size-3.5" /> {t("back")}
          </button>
        </div>
      </HudLayout>
    );
  }

  if (!replayData || !step) {
    return (
      <HudLayout eyebrow={t("eyebrow")} title="—" description="">
        <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">{t("noData")}</div>
      </HudLayout>
    );
  }

  const isError   = step.is_error ?? false;
  const isCorrect = step.is_hero && !isError && step.type === "action";

  return (
    <div className="h-dvh flex flex-col overflow-hidden bg-background hud-scanline">
      <HudHeader />

      {/* ── Outer wrapper: top-bar + [table | side-panel] + controls ── */}
      <div className="flex-1 min-h-0 flex flex-col px-3 md:px-5 pt-2 pb-14 md:pb-2 mx-auto w-full max-w-[1600px]">

        {/* Top bar */}
        <div className="shrink-0 grid grid-cols-3 items-center mb-2">
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary"
          >
            <ArrowLeft className="size-3.5" /> {t("back")}
          </button>

          {handList.length > 1 && handIdx >= 0 ? (
            <div className="flex items-center justify-center gap-2.5">
              <div className="flex items-baseline gap-1 font-mono tabular-nums">
                <span className="text-[9px] uppercase tracking-widest text-muted-foreground">{t("navigation.handLabel")}</span>
                <span className="text-sm font-bold text-foreground">{handIdx + 1}</span>
                <span className="text-[11px] text-muted-foreground">/{handList.length}</span>
              </div>
              <div className="hidden sm:block h-1 w-28 overflow-hidden rounded-full bg-border">
                <div
                  className="h-full rounded-full bg-primary/70 transition-all duration-500 ease-out"
                  style={{ width: `${Math.max(4, ((handIdx + 1) / handList.length) * 100)}%` }}
                />
              </div>
            </div>
          ) : <div />}

          <div />
        </div>

        {/* ── Main row: table (flex-1) + side panel (w-72, desktop only) ── */}
        <div className="flex-1 min-h-0 flex gap-3">

          {/* Table column */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col gap-2">
            {/* Mesa — cresce pela altura disponível */}
            <div className="flex-1 min-h-0 overflow-hidden">
              <div className="h-full mx-auto aspect-[16/10] max-w-full">
                <PokerTableV3
                  step={step}
                  hero={replayData.hero}
                  heroCards={replayData.hero_cards}
                  bb={replayData.bb}
                  betUnit={betUnit}
                  playerAliases={playerAliases}
                  revealedCards={revealedCards}
                />
              </div>
            </div>

            {/* Controls */}
            <div className="shrink-0 border border-border rounded-xl bg-hud-surface p-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    if (stepIdx > 0) setStepIdx(0);
                    else if (prevHand) navigate(`/replayer?t=${tournamentId}&h=${prevHand}${studentId ? `&student=${studentId}` : ""}`);
                  }}
                  disabled={stepIdx === 0 && !prevHand}
                  className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={stepIdx === 0 && prevHand ? t("navigation.prevHand") : "Reiniciar"}
                ><Rewind className="size-4" /></button>
                <button onClick={() => setStepIdx((i) => Math.max(0, i - 1))} disabled={stepIdx === 0}
                  className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="Anterior"><ChevronLeft className="size-5" /></button>
                <button onClick={() => setPlaying((p) => !p)}
                  className="inline-flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground hover:bg-primary-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={playing ? t("controls.pause") : t("controls.play")}>
                  {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
                </button>
                <button onClick={() => setStepIdx((i) => Math.min(steps.length - 1, i + 1))} disabled={stepIdx === steps.length - 1}
                  className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="Próximo"><ChevronRight className="size-5" /></button>
                <button
                  onClick={() => {
                    if (stepIdx < steps.length - 1) setStepIdx(steps.length - 1);
                    else if (nextHand) navigate(`/replayer?t=${tournamentId}&h=${nextHand}${studentId ? `&student=${studentId}` : ""}`);
                  }}
                  disabled={stepIdx === steps.length - 1 && !nextHand}
                  className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={stepIdx === steps.length - 1 && nextHand ? t("navigation.nextHand") : "Final"}
                ><FastForward className="size-4" /></button>
              </div>

              <div className="flex flex-1 items-center gap-3">
                <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                  {stepIdx + 1}/{steps.length}
                </span>
                <div className="flex-1 flex gap-0.5">
                  {steps.map((s, i) => (
                    <button key={i} onClick={() => setStepIdx(i)}
                      className={cn(
                        "h-1.5 flex-1 rounded-sm transition-colors focus-visible:outline-none",
                        i <= stepIdx
                          ? (s.is_error ? "bg-destructive" : "bg-primary")
                          : "bg-border"
                      )}
                      aria-label={`Passo ${i + 1}`}
                    />
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowRange(s => !s)}
                  disabled={step.street !== 'preflop'}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider ring-1 transition-colors focus-visible:outline-none',
                    showRange && step.street === 'preflop'
                      ? 'bg-primary/15 text-primary ring-primary/30'
                      : step.street !== 'preflop'
                      ? 'cursor-not-allowed text-muted-foreground/30 ring-border/30'
                      : 'text-muted-foreground ring-border hover:text-foreground',
                  )}
                >
                  <LayoutGrid className="size-3" /> Range
                </button>
                <div className="flex items-center gap-1">
                  {[0.5, 1, 2].map((s) => (
                    <button key={s} onClick={() => setSpeed(s)}
                      className={cn(
                        "rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none",
                        speed === s ? "bg-primary/15 text-primary ring-1 ring-primary/30" : "text-muted-foreground hover:text-foreground"
                      )}>{s}x</button>
                  ))}
                </div>
                <div className="flex items-center rounded-sm ring-1 ring-border overflow-hidden">
                  {(["chips", "bb"] as const).map((u) => (
                    <button key={u} onClick={() => setBetUnit(u)}
                      className={cn(
                        "px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors focus-visible:outline-none",
                        betUnit === u ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground"
                      )}>{u}</button>
                  ))}
                </div>
              </div>
            </div>

            {/* Mobile-only: contextual panels below controls */}
            <div className="lg:hidden shrink-0">
              <SidePanels
                step={step} isError={isError} isCorrect={isCorrect}
                coachAnnotation={coachAnnotation} studentId={studentId}
                currentDecisionId={currentDecisionId} annotating={annotating}
                annComment={annComment} annMode={annMode} annAction={annAction}
                annOverride={annOverride} saveAnn={saveAnn} deleteAnn={deleteAnn}
                replayData={replayData} playerAliases={playerAliases}
                setAnnotating={setAnnotating} setAnnComment={setAnnComment}
                setAnnMode={setAnnMode} setAnnAction={setAnnAction}
                setAnnOverride={setAnnOverride} openAnnotationForm={openAnnotationForm}
                t={t}
                gtoRequestStatus={gtoRequestStatus} onRequestGto={handleRequestGto}
                tournamentId={tournamentId} handId={handId}
              />
            </div>
          </div>

          {/* Side panel — desktop only, fixed width */}
          <aside className="hidden lg:flex w-[288px] shrink-0 flex-col gap-2 overflow-y-auto">
            <SidePanels
              step={step} isError={isError} isCorrect={isCorrect}
              coachAnnotation={coachAnnotation} studentId={studentId}
              currentDecisionId={currentDecisionId} annotating={annotating}
              annComment={annComment} annMode={annMode} annAction={annAction}
              annOverride={annOverride} saveAnn={saveAnn} deleteAnn={deleteAnn}
              replayData={replayData} playerAliases={playerAliases}
              setAnnotating={setAnnotating} setAnnComment={setAnnComment}
              setAnnMode={setAnnMode} setAnnAction={setAnnAction}
              setAnnOverride={setAnnOverride} openAnnotationForm={openAnnotationForm}
              t={t}
              gtoRequestStatus={gtoRequestStatus} onRequestGto={handleRequestGto}
              tournamentId={tournamentId} handId={handId}
            />
          </aside>
        </div>

      </div>

      {/* ── Range panel — floating (desktop) / bottom sheet (mobile) ── */}
      {showRange && step.street === 'preflop' && (
        <>
          <div
            className="hidden lg:block fixed z-50 w-[360px] rounded-xl shadow-2xl ring-1 ring-primary/25"
            style={{ left: rangePos.x, top: rangePos.y }}
          >
            <RangePanel key={stepIdx} step={step} hero={replayData.hero} heroCards={replayData.hero_cards} onClose={() => setShowRange(false)} onHeaderMouseDown={handleRangeDragStart} />
          </div>
          <div className="lg:hidden fixed inset-0 z-50 flex flex-col justify-end">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowRange(false)} />
            <div className="relative max-h-[72vh] overflow-y-auto rounded-t-2xl">
              <RangePanel key={`mobile-${stepIdx}`} step={step} hero={replayData.hero} heroCards={replayData.hero_cards} onClose={() => setShowRange(false)} />
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Replayer;
