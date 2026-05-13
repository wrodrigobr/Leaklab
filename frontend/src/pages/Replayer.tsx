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

function fmtAction(a: string): string {
  if (!a) return a;
  const s = a.toLowerCase();
  if (s === "fold")    return "Fold";
  if (s === "call")    return "Call";
  if (s === "check")   return "Check";
  if (s === "allin" || s === "all-in") return "All-in";
  if (s === "bet")     return "Bet";
  if (s === "raise")   return "Raise";
  if (s.startsWith("bet_"))   return `Bet ${s.replace("bet_", "").replace("pct", "%")}`;
  if (s.startsWith("raise_")) return `Raise ${s.replace("raise_", "").replace("pct", "%")}`;
  return a.toUpperCase();
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
  const hasGto     = !!step.gto_label;
  const isPostflop = step.street !== 'preflop';
  const handHasPostflopAction = replayData.timeline.some(
    (s) => s.is_hero && s.type === "action" && s.street !== 'preflop'
  );
  const pg = step.preflop_gto ?? null;

  // ── Unified verdict: GTO Solver > Range > Engine ────────────────────────────
  type VInfo = { icon: string; label: string; cls: string; borderCls: string; hdrCls: string; source: string };
  const verdict = ((): VInfo | null => {
    if (!step.is_hero || step.type !== "action") return null;
    if (hasGto) {
      const m: Record<string, VInfo> = {
        gto_correct:         { icon: "✓", label: "Correto",        cls: "text-emerald-400", borderCls: "border-emerald-500/30", hdrCls: "bg-emerald-500/8", source: "GTO Solver" },
        gto_mixed:           { icon: "◎", label: "Misto",          cls: "text-sky-400",     borderCls: "border-sky-500/30",     hdrCls: "bg-sky-500/8",     source: "GTO Solver" },
        gto_minor_deviation: { icon: "⚠", label: "Desvio Leve",   cls: "text-amber-400",   borderCls: "border-amber-500/30",   hdrCls: "bg-amber-500/8",   source: "GTO Solver" },
        gto_critical:        { icon: "✗", label: "Desvio Crítico", cls: "text-red-400",     borderCls: "border-red-500/30",     hdrCls: "bg-red-500/8",     source: "GTO Solver" },
      };
      if (step.gto_label && m[step.gto_label]) return m[step.gto_label];
    }
    if (!isPostflop && pg?.available) {
      const m: Record<string, VInfo> = {
        correct:    { icon: "✓", label: "Correto",      cls: "text-emerald-400", borderCls: "border-emerald-500/30", hdrCls: "bg-emerald-500/8", source: "Range" },
        acceptable: { icon: "◎", label: "Aceitável",    cls: "text-sky-400",     borderCls: "border-sky-500/30",     hdrCls: "bg-sky-500/8",     source: "Range" },
        leak:       { icon: "⚠", label: "Leak",         cls: "text-amber-400",   borderCls: "border-amber-500/30",   hdrCls: "bg-amber-500/8",   source: "Range" },
        major_leak: { icon: "✗", label: "Leak Grave",   cls: "text-red-400",     borderCls: "border-red-500/30",     hdrCls: "bg-red-500/8",     source: "Range" },
        unknown:    { icon: "·", label: "Sem dados",    cls: "text-muted-foreground", borderCls: "border-border",   hdrCls: "bg-hud-surface",   source: "Range" },
      };
      return m[pg.action_quality] ?? m.unknown;
    }
    if (isError) return { icon: "✗", label: "Erro", cls: "text-destructive", borderCls: "border-destructive/40", hdrCls: "bg-destructive/5", source: "Análise" };
    if (isCorrect || step.hand_equity != null || step.pot_odds_equity != null)
      return { icon: "✓", label: "Correto", cls: "text-primary", borderCls: "border-primary/30", hdrCls: "bg-primary/5", source: "Análise" };
    return null;
  })();
  const showDecision = !!verdict && (studentId !== null || coachAnnotation?.mode !== "replace");

  // Action comparison
  const playedAction  = (!isPostflop && pg?.available) ? pg.action_taken : (step.action ?? "—");
  const isActionOk    = hasGto
    ? (step.gto_label === "gto_correct" || step.gto_label === "gto_mixed")
    : (!isPostflop && pg?.available
        ? (pg.action_quality === "correct" || pg.action_quality === "acceptable")
        : isCorrect);
  const idealAction   = hasGto
    ? (step.gto_action ?? null)
    : (!isPostflop && pg?.available ? pg.recommended_actions.join(" / ") : (step.best_action ?? null));
  const showTwoCols   = !isActionOk && !!idealAction &&
    idealAction.toLowerCase() !== playedAction.toLowerCase();

  // GTO strategy
  const stratSorted = step.gto_strategy
    ? [...step.gto_strategy].sort((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0))
    : [];
  const isPlayedAct = (action: string) => {
    const a = action.toLowerCase(); const p = playedAction.toLowerCase();
    return a === p || p.startsWith(a) || a.startsWith(p);
  };
  const topFreqPct = stratSorted.length > 0
    ? ((stratSorted[0].frequency ?? 0) * 100).toFixed(0) : null;
  const evDiff = (() => {
    if (!stratSorted.length) return null;
    const top = stratSorted[0].ev_bb;
    if (top == null) return null;
    const playerEv = stratSorted.find(s => isPlayedAct(s.action))?.ev_bb ?? null;
    if (playerEv == null) return null;
    const d = top - playerEv;
    return Math.abs(d) >= 0.05 ? d : null;
  })();
  const actionBarColor = (action: string) => {
    const a = action.toLowerCase();
    if (a === "fold")                                  return "bg-blue-500";
    if (a === "check")                                 return "bg-sky-400";
    if (a === "call")                                  return "bg-emerald-500";
    if (a.startsWith("bet") || a.startsWith("raise")) return "bg-red-500";
    if (a === "allin" || a.startsWith("allin"))        return "bg-red-600";
    return "bg-purple-500";
  };
  const actionTextColor = (action: string) => {
    const a = action.toLowerCase();
    if (a === "fold")                                  return "text-blue-400";
    if (a === "check")                                 return "text-sky-400";
    if (a === "call")                                  return "text-emerald-400";
    if (a.startsWith("bet") || a.startsWith("raise")) return "text-red-400";
    if (a === "allin" || a.startsWith("allin"))        return "text-red-400";
    return "text-purple-400";
  };
  const scenarioLabel: Record<string, string> = { rfi: "RFI", vs_rfi: "vs Open", vs_3bet: "vs 3-Bet" };
  const DRAW_LABELS: Record<string, string> = {
    flush_draw: "Flush Draw", straight_draw: "Straight Draw",
    combo_draw: "Combo Draw", gutshot: "Gutshot",
  };

  return (
    <div className="flex flex-col gap-2">

      {/* ── Decision Card — painel unificado por ação do hero ── */}
      {showDecision && verdict && (
        <section className={cn("rounded-xl border overflow-hidden", verdict.borderCls)}>

          {/* Banner: veredito + fonte */}
          <div className={cn("flex items-center justify-between px-3 py-2.5", verdict.hdrCls)}>
            <span className={cn("font-mono text-sm font-bold uppercase tracking-wide", verdict.cls)}>
              {verdict.icon} {verdict.label}
            </span>
            <span className="font-mono text-[9px] text-muted-foreground/45 uppercase tracking-wider">
              {verdict.source}
            </span>
          </div>

          <div className="p-3 space-y-3">

            {/* Comparação: Você vs Ideal */}
            <div className={cn("grid gap-2", showTwoCols ? "grid-cols-2" : "grid-cols-1")}>
              <div className={cn("rounded-lg px-2.5 py-2 ring-1",
                isActionOk ? "bg-background/60 ring-border/50" : "bg-background/60 ring-border/50")}>
                <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">Você jogou</div>
                <div className={cn("font-mono text-sm font-bold uppercase",
                  isActionOk ? verdict.cls : "text-foreground")}>
                  {fmtAction(playedAction)}
                  {isActionOk && <span className="ml-1.5 opacity-80">✓</span>}
                </div>
              </div>
              {showTwoCols && (
                <div className="rounded-lg px-2.5 py-2 ring-1 bg-background/60 ring-border/50">
                  <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground mb-0.5">
                    {hasGto ? "GTO recomenda" : "Ideal"}
                  </div>
                  <div className={cn("font-mono text-sm font-bold uppercase", verdict.cls)}>
                    {fmtAction(idealAction!)}
                  </div>
                </div>
              )}
            </div>

            {/* Preflop: badges + range% + pro notes */}
            {!isPostflop && pg?.available && (
              <>
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[10px] text-muted-foreground bg-background/40 ring-1 ring-border/50">
                    {scenarioLabel[pg.scenario] ?? pg.scenario}
                  </span>
                  <span className={cn(
                    "inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[10px] font-bold ring-1",
                    pg.in_range
                      ? "text-emerald-400 ring-emerald-500/30 bg-emerald-500/8"
                      : "text-red-400 ring-red-500/30 bg-red-500/8"
                  )}>
                    {pg.in_range ? "✓ No range" : "✗ Fora do range"}
                  </span>
                  {pg.hand_type && (
                    <span className="inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[10px] font-bold text-foreground bg-background/60 ring-1 ring-border">
                      {pg.hand_type}
                    </span>
                  )}
                  <span className="inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[10px] text-muted-foreground bg-background/40 ring-1 ring-border/50">
                    {pg.stack_bb}BB
                  </span>
                </div>
                {pg.range_pct > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">Range de abertura</span>
                      <span className="font-mono text-[11px] font-bold tabular-nums text-foreground">{(pg.range_pct * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-border/50 overflow-hidden">
                      <div className="h-full rounded-full bg-primary/60 transition-all duration-500"
                        style={{ width: `${Math.min(100, pg.range_pct * 100).toFixed(0)}%` }} />
                    </div>
                  </div>
                )}
                {pg.pro_notes.length > 0 && (
                  <div className="space-y-1 pt-1 border-t border-border/30">
                    {pg.pro_notes.map((note, i) => (
                      <p key={i} className="text-[11px] text-muted-foreground leading-relaxed">{note}</p>
                    ))}
                  </div>
                )}
              </>
            )}

            {/* Postflop: equity bar + pot odds + draw */}
            {isPostflop && step.hand_equity != null && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground w-12 shrink-0">Equity</span>
                  <div className="flex-1 h-1.5 rounded-full bg-border/50 overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all",
                        step.hand_equity >= (step.pot_odds_equity ?? 0) ? "bg-emerald-500" : "bg-destructive")}
                      style={{ width: `${(step.hand_equity * 100).toFixed(1)}%` }}
                    />
                  </div>
                  <span className={cn("font-mono text-sm font-bold tabular-nums shrink-0",
                    step.hand_equity >= (step.pot_odds_equity ?? 0) ? "text-emerald-400" : "text-destructive")}>
                    {(step.hand_equity * 100).toFixed(0)}%
                  </span>
                  {step.pot_odds_equity != null && (
                    <span className="font-mono text-[10px] text-muted-foreground shrink-0 tabular-nums">
                      / {(step.pot_odds_equity * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
                {step.draw_profile && step.draw_profile !== "none" && step.draw_profile !== "made_hand" && (
                  <span className="inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[10px] font-bold ring-1 text-amber-400 ring-amber-500/30 bg-amber-500/8">
                    {DRAW_LABELS[step.draw_profile] ?? step.draw_profile.replace(/_/g, " ")}
                  </span>
                )}
              </div>
            )}

            {/* Estratégia do Solver */}
            {!step.gto_spot_mismatch && stratSorted.length >= 1 && (
              <div className="space-y-2">
                <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/50 border-t border-border/30 pt-2">
                  Estratégia do Solver
                </div>
                {stratSorted.map((s) => {
                  const isP = isPlayedAct(s.action);
                  const freq = (s.frequency ?? 0) * 100;
                  return (
                    <div key={s.action} className="flex items-center gap-2">
                      <span className={cn("font-mono text-[11px] font-bold w-14 shrink-0 uppercase truncate",
                        isP ? "text-amber-400" : actionTextColor(s.action))}>
                        {fmtAction(s.action)}
                      </span>
                      <div className="flex-1 h-[5px] rounded-full bg-border/50 overflow-hidden">
                        <div className={cn("h-full rounded-full transition-all duration-500",
                          isP ? "bg-amber-400" : actionBarColor(s.action))}
                          style={{ width: `${freq}%` }} />
                      </div>
                      <span className={cn("font-mono text-[11px] font-bold w-8 text-right tabular-nums shrink-0",
                        isP ? "text-amber-400" : "text-muted-foreground")}>
                        {freq.toFixed(0)}%
                      </span>
                      <span className={cn("font-mono text-[9px] w-2 shrink-0 select-none",
                        isP ? "text-amber-400" : "invisible")}>←</span>
                    </div>
                  );
                })}
                {evDiff !== null && (
                  <p className={cn("font-mono text-[10px] tabular-nums pt-0.5",
                    evDiff > 0 ? "text-destructive/70" : "text-emerald-400/70")}>
                    {evDiff > 0
                      ? `EV perdida: −${evDiff.toFixed(2)} BB vs ótimo`
                      : `EV acima do ótimo: +${Math.abs(evDiff).toFixed(2)} BB`}
                  </p>
                )}
              </div>
            )}

            {/* Spot incompatível */}
            {step.gto_spot_mismatch && (
              <div className="flex items-start gap-1.5 rounded-lg bg-orange-500/5 border border-orange-500/25 px-2.5 py-2">
                <span className="text-orange-400 text-[10px] mt-px shrink-0">⚠</span>
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  {step.engine_best === "call"
                    ? "Spot GTO incompatível: você enfrentava uma aposta, mas o solver foi consultado para um spot sem aposta."
                    : "Spot GTO incompatível: não havia aposta a enfrentar, mas o solver foi consultado para um spot com aposta."}
                </p>
              </div>
            )}

            {/* Conflito engine vs GTO — footnote compacto */}
            {!step.gto_spot_mismatch && step.engine_best && step.gto_action &&
             step.engine_best !== step.gto_action && isError && (
              <p className="text-[10px] text-muted-foreground/55 leading-relaxed">
                Engine→ <span className="font-mono text-foreground/65">{fmtAction(step.engine_best)}</span>
                {" · "}Solver→ <span className="font-mono text-foreground/65">{fmtAction(step.gto_action)}</span>
                {" · "}Priorizando GTO.
              </p>
            )}

            {/* Rodapé: M-Ratio + ICM */}
            {(step.m_ratio != null || (step.icm_pressure && step.icm_pressure !== "low")) && (
              <div className="flex items-center gap-3 pt-1 border-t border-border/30">
                {step.m_ratio != null && (
                  <span className="font-mono text-[10px]">
                    <span className="text-muted-foreground/50">M </span>
                    <span className={cn("font-bold tabular-nums",
                      step.m_ratio <= 5 ? "text-destructive" : step.m_ratio <= 10 ? "text-amber-400" : "text-muted-foreground")}>
                      {step.m_ratio.toFixed(1)}
                    </span>
                  </span>
                )}
                {step.icm_pressure && step.icm_pressure !== "low" && (
                  <span className={cn("font-mono text-[10px] font-bold uppercase",
                    step.icm_pressure === "critical" ? "text-destructive" :
                    step.icm_pressure === "high" ? "text-amber-400" : "text-sky-400")}>
                    ICM {step.icm_pressure}
                  </span>
                )}
              </div>
            )}

          </div>
        </section>
      )}

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
