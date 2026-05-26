import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, Pause, Play, Rewind, FastForward, AlertOctagon, CheckCircle2, Loader2, ArrowLeft, GraduationCap, PenLine, X, Check, Trash2, LayoutGrid, FlaskConical, Clock, Eye, EyeOff, Info } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { HudLayout } from "@/components/hud/HudLayout";
import { HudHeader } from "@/components/hud/HudHeader";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { RangePanel } from "@/components/replayer/RangePanel";
import { GtoStrategyPanel } from "@/components/replayer/GtoStrategyPanel";
import { DecisionCard, type DecisionSourceVariant } from "@/components/replayer/DecisionCard";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { cn } from "@/lib/utils";
import { computeEffectiveGtoLabel } from "@/lib/gtoUtils";
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
  if (s === "allin" || s === "all-in" || s === "shove" || s === "jam") return "Shove";
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
  const [showDetails, setShowDetails] = useState<boolean>(
    () => localStorage.getItem('replayer_show_details') === 'true'
  );
  const toggleDetails = () => setShowDetails(prev => {
    const next = !prev;
    localStorage.setItem('replayer_show_details', String(next));
    return next;
  });

  const hasGto     = !!step.gto_label;
  const isPostflop = step.street !== 'preflop';
  const pg = step.preflop_gto ?? null;

  // ── Compute these FIRST so verdict can reference live GTO data ───────────────

  const playedAction = (!isPostflop && pg?.available) ? pg.action_taken : (step.action ?? "—");

  const stratSorted = step.gto_strategy
    ? [...step.gto_strategy].sort((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0))
    : [];

  const normalizeGtoAction = (s: string) => {
    const l = s.toLowerCase();
    if (l === 'shove' || l === 'jam' || l === 'allin' || l === 'all-in' || l === 'all in') return 'allin';
    return l;
  };
  const isPlayedAct = (action: string) => {
    const a = normalizeGtoAction(action); const p = normalizeGtoAction(playedAction);
    return a === p || p.startsWith(a) || a.startsWith(p);
  };

  // When live strategy is available, derive the label from actual frequencies.
  // Stored gto_label may be stale if the solver node was updated after import.
  // Exception: for preflop with range data (pg.available), the strategy comes from
  // an aggregate node (fold 72% = entire range folds) — not hand-specific.
  // Using it would mark KK as "Desvio Leve" when the range-based analysis says "Correto".
  const effectiveGtoLabel = hasGto && (isPostflop || !pg?.available)
    ? computeEffectiveGtoLabel(stratSorted, step.gto_label, step.action)
    : null;

  // ── Unified verdict: GTO Solver > Range > Engine ────────────────────────────
  const GTO_LABEL_TOOLTIP: Record<string, string> = {
    gto_correct:         "Ação ótima: frequência GTO ≥ 60% — jogada correta segundo o solver",
    gto_mixed:           "Estratégia mista: frequência GTO 30–60% — ação válida, mas não dominante no range",
    gto_minor_deviation: "Desvio leve: frequência GTO 10–30% — jogada infrequente no GTO, mas defensável",
    gto_critical:        "Desvio crítico: frequência GTO < 10% — jogada raramente justificada pelo solver",
  };

  type VInfo = { icon: string; label: string; cls: string; borderCls: string; hdrCls: string; source: string; sourceTooltip: string };
  const verdict = ((): VInfo | null => {
    if (!step.is_hero || step.type !== "action") return null;
    // Skip non-decision actions (shows, mucks, posts)
    const _actLow = (step.action ?? '').toLowerCase();
    if (_actLow === 'shows' || _actLow === 'show' || _actLow === 'mucks' || _actLow === 'muck' || _actLow === 'posts' || _actLow === 'post') return null;
    if (effectiveGtoLabel) {
      const gtoTooltip = "GTO Solver — frequências de Nash equilibrium calculadas para este spot específico";
      const m: Record<string, VInfo> = {
        gto_correct:         { icon: "✓", label: "Correto",        cls: "text-emerald-400", borderCls: "border-emerald-500/30", hdrCls: "bg-emerald-500/8", source: "Solver", sourceTooltip: gtoTooltip },
        gto_mixed:           { icon: "◎", label: "Misto",          cls: "text-sky-400",     borderCls: "border-sky-500/30",     hdrCls: "bg-sky-500/8",     source: "Solver", sourceTooltip: gtoTooltip },
        gto_minor_deviation: { icon: "⚠", label: "Desvio Leve",   cls: "text-amber-400",   borderCls: "border-amber-500/30",   hdrCls: "bg-amber-500/8",   source: "Solver", sourceTooltip: gtoTooltip },
        gto_critical:        { icon: "✗", label: "Desvio Crítico", cls: "text-red-400",     borderCls: "border-red-500/30",     hdrCls: "bg-red-500/8",     source: "Solver", sourceTooltip: gtoTooltip },
      };
      if (m[effectiveGtoLabel]) return m[effectiveGtoLabel];
    }
    if (!isPostflop && pg?.available) {
      const rangeTooltip = "Preflop — ranges de abertura GTO por posição e stack depth";
      const m: Record<string, VInfo> = {
        correct:    { icon: "✓", label: "Correto",      cls: "text-emerald-400", borderCls: "border-emerald-500/30", hdrCls: "bg-emerald-500/8", source: "Preflop", sourceTooltip: rangeTooltip },
        acceptable: { icon: "◎", label: "Aceitável",    cls: "text-sky-400",     borderCls: "border-sky-500/30",     hdrCls: "bg-sky-500/8",     source: "Preflop", sourceTooltip: rangeTooltip },
        leak:       { icon: "⚠", label: "Leak",         cls: "text-amber-400",   borderCls: "border-amber-500/30",   hdrCls: "bg-amber-500/8",   source: "Preflop", sourceTooltip: rangeTooltip },
        major_leak: { icon: "✗", label: "Leak Grave",   cls: "text-red-400",     borderCls: "border-red-500/30",     hdrCls: "bg-red-500/8",     source: "Preflop", sourceTooltip: rangeTooltip },
        unknown:    { icon: "·", label: "Sem dados",    cls: "text-muted-foreground", borderCls: "border-border",   hdrCls: "bg-hud-surface",   source: "Preflop", sourceTooltip: rangeTooltip },
      };
      return m[pg.action_quality] ?? m.unknown;
    }
    const engineTooltip = "Engine — equity estimada, M-Ratio, pressão ICM e contexto de torneio";
    if (isError) return { icon: "✗", label: "Erro", cls: "text-destructive", borderCls: "border-destructive/40", hdrCls: "bg-destructive/5", source: "Engine", sourceTooltip: engineTooltip };
    if (isCorrect || step.hand_equity != null || step.pot_odds_equity != null)
      return { icon: "✓", label: "Correto", cls: "text-primary", borderCls: "border-primary/30", hdrCls: "bg-primary/5", source: "Engine", sourceTooltip: engineTooltip };
    return null;
  })();
  const showDecision = !!verdict && (studentId !== null || coachAnnotation?.mode !== "replace");

  // Action comparison (playedAction already computed above)
  // gto_minor_deviation (10-30%) = ação válida na estratégia mista do solver — não é erro
  const isActionOk = effectiveGtoLabel
    ? (effectiveGtoLabel === "gto_correct" || effectiveGtoLabel === "gto_mixed" || effectiveGtoLabel === "gto_minor_deviation")
    : (!isPostflop && pg?.available
        ? (pg.action_quality === "correct" || pg.action_quality === "acceptable")
        : isCorrect);
  // idealAction: use live top action when available (overrides stored gto_action which may be stale)
  const liveTopAction = stratSorted.length > 0 ? stratSorted[0].action : null;
  const idealAction = hasGto
    ? (liveTopAction ?? step.gto_action ?? null)
    : (!isPostflop && pg?.available ? pg.recommended_actions.map(fmtAction).join(" / ") : (step.best_action ? fmtAction(step.best_action) : null));
  const showTwoCols = !isActionOk && !!idealAction &&
    idealAction.toLowerCase() !== playedAction.toLowerCase();
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
    if (a === "allin" || a.startsWith("allin") || a === "shove") return "bg-red-600";
    return "bg-purple-500";
  };
  const actionTextColor = (action: string) => {
    const a = action.toLowerCase();
    if (a === "fold")                                  return "text-blue-400";
    if (a === "check")                                 return "text-sky-400";
    if (a === "call")                                  return "text-emerald-400";
    if (a.startsWith("bet") || a.startsWith("raise")) return "text-red-400";
    if (a === "allin" || a.startsWith("allin") || a === "shove") return "text-red-400";
    return "text-purple-400";
  };
  const scenarioLabel: Record<string, string> = {
    rfi: "RFI",
    vs_rfi: "vs Open",
    vs_3bet: "vs 3-Bet",
    vs_shove_fallback: "vs Shove (heurística)",
    squeeze: "Squeeze",
    vs_4bet: "vs 4-Bet",
  };
  return (
    <div className="flex flex-col gap-2">

      {/* ── Decision Card — template único de 5 slots (banner / ação / why / evidence / footer) ── */}
      {showDecision && verdict && (() => {
        // ──────── Source variant (1 só badge, prioridade descendente) ────────
        // Push/Fold zone: só ativa quando hand_freq mostra que jam realmente é GTO dominante.
        // Apenas stack ≤ 12bb não basta (GW v3 mostra que BTN 8bb ainda faz raise sized 96%).
        // Trigger refinado: stack ≤ 12bb E (jam é dominante OU não há freq de raise sized).
        const isPfZone = !isPostflop && step.is_hero && step.type === "action"
          && step.hero_stack_bb != null && step.hero_stack_bb <= 12
          && (() => {
            const hf = step.preflop_gto?.hand_freq;
            if (!hf) return true;  // sem dados: assume push/fold (conservador)
            // Push/fold real = jam > raise (jam é a ação dominante)
            return (hf.allin ?? 0) >= (hf.raise ?? 0);
          })();
        const sourceVariant: DecisionSourceVariant =
          step.gto_spot_mismatch                  ? "na"        :
          effectiveGtoLabel                       ? "gto"       :
          (!isPostflop && pg?.available)          ? "preflop"   :
          isPfZone                                ? "pushfold"  :
          (step.is_hero && !step.gto_label)       ? "heuristic" :
                                                    "engine";
        const SOURCE_LABEL: Record<DecisionSourceVariant, string> = {
          gto: "Solver", preflop: "Preflop", engine: "Engine",
          heuristic: "Heurística", pushfold: "Push/Fold", na: "Spot N/A",
        };
        const SOURCE_TOOLTIP: Record<DecisionSourceVariant, string> = {
          gto: "GTO Solver — frequências de Nash equilibrium calculadas para este spot",
          preflop: "Preflop — ranges de abertura GTO por posição e stack depth",
          engine: "Engine — equity estimada, M-Ratio, pressão ICM e contexto de torneio",
          heuristic: "Análise heurística — solver não tem cobertura para este spot multiway",
          pushfold: "Push/Fold zone — stack ≤12bb, decisão binária shove ou fold",
          na: "Spot incompatível — solver consultado para spot diferente do real",
        };

        // ──────── Pré-cálculos compartilhados (postflop) ────────
        const eq = step.hand_equity ?? null;
        const poRaw = step.pot_odds_equity ?? null;
        // Engine usa adjusted_required_equity (pot_odds + realization_adj + pressure_adj)
        // para classificar. Usamos isso quando disponível — coerência verdict × frase × badge.
        // Fallback para pot_odds bruto preserva compat com decisions antigas sem o campo.
        const req = step.adjusted_required_equity ?? poRaw;
        const profitable = eq != null && req != null && req > 0 ? eq >= req : null;
        const spr = (step.hero_stack_bb != null && step.pot_bb != null && step.pot_bb > 0)
                    ? step.hero_stack_bb / step.pot_bb : null;
        const hasMathEvidence = isPostflop && eq != null && req != null && req > 0;
        const requiredIsAdjusted = step.adjusted_required_equity != null &&
                                   poRaw != null &&
                                   Math.abs(step.adjusted_required_equity - poRaw) >= 0.005;
        const hasEngineGtoConflict = !step.gto_spot_mismatch && step.engine_best && step.gto_action &&
                                     step.engine_best !== step.gto_action && isError;

        // ──────── Why (1 frase dominante, prioridade descendente) ────────
        let why = "";
        if (step.gto_spot_mismatch) {
          why = step.engine_best === "call"
            ? "Solver foi consultado para um spot sem aposta, mas você enfrentava aposta — análise via heurística do engine."
            : "Solver foi consultado para um spot com aposta, mas não havia aposta — análise via heurística do engine.";
        } else if (isPfZone) {
          why = `Stack ${step.hero_stack_bb!.toFixed(1)}bb — push/fold dominante. Verifique a barra de freq pra ação ótima específica desta mão.`;
        } else if (hasEngineGtoConflict) {
          why = `Engine sugere ${fmtAction(step.engine_best!)} mas Solver indica ${fmtAction(step.gto_action!)} — priorizamos GTO.`;
        } else if (hasMathEvidence) {
          // Frase descreve a AÇÃO TOMADA pelo hero, não a alternativa.
          // "Call lucrativo" quando hero foldou confunde — soa como crítica oposta ao verdict.
          const eqPct = Math.round(eq! * 100);
          const reqPct = Math.round(req! * 100);
          const margin = eqPct - reqPct;
          const heroAct = (step.action ?? '').toLowerCase();
          // "necessário" usa adjusted_required quando disponível (engine ajusta por realization
          // e pressão ICM). Quando não há ajuste relevante, é pot odds bruto.
          const reqLabel = requiredIsAdjusted ? "necessário (ajustado)" : "pot odds";
          if (heroAct === 'fold') {
            why = profitable
              ? (margin <= 3
                  ? `Fold defensável — equity ${eqPct}% ≈ ${reqLabel} ${reqPct}% (break-even).`
                  : `Fold deixou EV na mesa — equity ${eqPct}% superava ${reqLabel} ${reqPct}%, call era preferível.`)
              : `Fold correto — equity ${eqPct}% abaixo dos ${reqPct}% ${reqLabel}.`;
          } else if (heroAct === 'call') {
            why = profitable
              ? `Call lucrativo — equity ${eqPct}% supera ${reqLabel} ${reqPct}%.`
              : `Call perdedor — equity ${eqPct}% abaixo dos ${reqPct}% ${reqLabel}.`;
          } else if (heroAct === 'check') {
            why = `Check — equity ${eqPct}% vs ${reqLabel} ${reqPct}% (sem aposta para enfrentar).`;
          } else {
            // bet/raise/shove
            why = profitable
              ? `${fmtAction(heroAct)} com equity ${eqPct}% acima do ${reqLabel} ${reqPct}% — pressão lucrativa.`
              : `${fmtAction(heroAct)} com equity ${eqPct}% abaixo do ${reqLabel} ${reqPct}% — risco alto sem equity.`;
          }
        } else if (!isPostflop && pg?.available) {
          const scen = scenarioLabel[pg.scenario] ?? pg.scenario;
          const pct  = pg.range_pct > 0 ? ` (${(pg.range_pct * 100).toFixed(0)}%)` : '';
          why = pg.in_range
            ? `${pg.hand_type} está no range ${scen}${pct} @ ${pg.stack_bucket}.`
            : `${pg.hand_type} está fora do range ${scen}${pct} @ ${pg.stack_bucket}.`;
        } else if (!hasGto && step.is_hero) {
          why = "Spot multiway sem solução pré-computada no solver — análise heurística com confiança moderada.";
        } else if (isPostflop && eq != null) {
          why = eq >= 0.70 ? "Mão forte — vantagem clara de equity."
              : eq >= 0.50 ? "Equity ligeiramente favorável — jogue com atenção ao sizing."
              : eq >= 0.35 ? "Equity desfavorável — prefira linhas de controle."
              : "Equity fraca — situação difícil, evite inflar o pot.";
        } else {
          why = "Análise baseada em contexto de torneio.";
        }

        // ──────── Evidence (1 widget, escolhido por contexto) ────────
        let evidence: React.ReactNode = null;
        if (!step.gto_spot_mismatch && stratSorted.length >= 1 && (isPostflop || !pg?.available)) {
          // Solver strategy widget (postflop GTO ou preflop sem range)
          evidence = (
            <div className="space-y-2">
              <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                Estratégia do Solver
              </div>
              <GtoStrategyPanel strategy={stratSorted} playedAction={playedAction} />
            </div>
          );
        } else if (hasMathEvidence) {
          // Math card — usa adjusted_required_equity (mesmo critério do engine).
          // Tooltip mostra pot_odds bruto quando há ajuste relevante para didática.
          const mathCallIsEv  = eq! >= req!;
          const mathIsFolding = (step.action ?? '').toLowerCase() === 'fold';
          const mathActionIsEv = mathIsFolding ? !mathCallIsEv : mathCallIsEv;
          const mathActLabel  = step.action ? fmtAction(step.action) : null;
          const mathBadgeCls  = mathActionIsEv
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            : "bg-red-500/10 text-red-400 border border-red-500/20";
          const mathBadgeLabel = `${mathActLabel ?? ''} ${mathActionIsEv ? "+EV" : "−EV"}`.trim();
          const reqHeader = requiredIsAdjusted ? "Equity Necessária" : "Pot Odds";
          const reqTooltip = requiredIsAdjusted
            ? `Equity necessária ajustada por realization e pressão ICM. Pot odds bruto: ${(poRaw! * 100).toFixed(1)}%.`
            : "Equity mínima para call ser break-even (bet ÷ (bet + pot))";
          evidence = (
            <div className="rounded-lg border border-border/40 bg-muted/5 px-3 py-2">
              <div className="flex items-center gap-3 flex-wrap">
                <div title={reqTooltip}>
                  <p className="font-mono text-[10px] text-muted-foreground uppercase cursor-help">{reqHeader}</p>
                  <p className="font-mono text-[13px] font-bold text-foreground/80 tabular-nums">{(req! * 100).toFixed(1)}%</p>
                </div>
                <div className="text-muted-foreground/50 font-mono text-[11px]">vs</div>
                <div>
                  <p className="font-mono text-[10px] text-muted-foreground uppercase">Equity</p>
                  <p className={cn("font-mono text-[13px] font-bold tabular-nums", mathCallIsEv ? "text-emerald-400" : "text-red-400")}>
                    {(eq! * 100).toFixed(1)}%
                  </p>
                </div>
                <div className={cn("ml-auto rounded-md px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wide", mathBadgeCls)}>
                  {mathBadgeLabel}
                </div>
              </div>
            </div>
          );
        } else if (isPostflop && eq != null) {
          // Equity bar (postflop sem pot odds)
          evidence = (
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Equity</span>
                <span className="font-mono text-[13px] font-bold tabular-nums text-sky-400">{(eq * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-border/50 overflow-hidden">
                <div className="h-full rounded-full bg-sky-500 transition-all" style={{ width: `${(eq * 100).toFixed(1)}%` }} />
              </div>
            </div>
          );
        } else if (!isPostflop && pg?.available && pg.range_pct > 0) {
          // Range bar (preflop com cobertura)
          evidence = (
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Range de abertura</span>
                <span className="font-mono text-[13px] font-bold tabular-nums text-foreground">{(pg.range_pct * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-border/50 overflow-hidden">
                <div className="h-full rounded-full bg-primary/60 transition-all duration-500"
                  style={{ width: `${Math.min(100, pg.range_pct * 100).toFixed(0)}%` }} />
              </div>
            </div>
          );
        }

        // ──────── Details (toggle): audit trail + pro_notes + indicadores secundários ────────
        const showAuditPreflop = !isPostflop && pg?.available;
        const showProNotes = showAuditPreflop && (pg!.pro_notes?.length ?? 0) > 0 &&
                             !(effectiveGtoLabel &&
                               ['gto_correct','gto_mixed','gto_minor_deviation'].includes(effectiveGtoLabel) &&
                               ['leak','major_leak'].includes(pg!.action_quality));
        const sprColor = spr == null ? "" : spr < 2 ? "text-amber-400" : spr < 5 ? "text-sky-400" : "text-muted-foreground";
        const sprLabel = spr == null ? null : spr < 2 ? "comprometido" : spr < 5 ? "médio" : "fundo";
        const isBetAct = step.is_hero && (step.action === "bet" || step.action === "raise" || step.action === "shove");
        const bb = step.bb ?? (replayData?.bb ?? 100);
        const amtBb = (isBetAct && step.amount) ? step.amount / bb : null;
        const potBeforeBb = (amtBb != null && step.pot_bb != null) ? step.pot_bb - amtBb : null;
        const sizingPct = (amtBb != null && potBeforeBb != null && potBeforeBb > 0)
                          ? Math.round(amtBb / potBeforeBb * 100) : null;

        // INDICATORS (sempre visíveis — dados, não texto): cenário+mão + barra stacked + SPR + Sizing
        // Stacked bar: prefere frequência EXATA da mão do hero (hand_freq) sobre
        // % globais do range (call_pct/raise_pct). Ex: 88 vs UTG = 85/15 (mão específica)
        // em vez de 13/5 (% do range agregado).
        const useHandFreq = !!pg?.hand_freq && Object.values(pg.hand_freq).some(v => v > 0.001);
        const callPct  = useHandFreq ? pg!.hand_freq!.call  : (pg?.call_pct  ?? 0);
        const raisePct = useHandFreq ? pg!.hand_freq!.raise : (pg?.raise_pct ?? 0);
        const allinPct = useHandFreq ? pg!.hand_freq!.allin : (pg?.allin_pct ?? 0);
        const foldPct  = useHandFreq
          ? pg!.hand_freq!.fold
          : (pg ? Math.max(0, 1 - (pg.range_pct ?? 0)) : 0);
        const hasFreqs = showAuditPreflop && (callPct > 0 || raisePct > 0 || allinPct > 0 || foldPct > 0);

        const indicators = (
          <>
            {showAuditPreflop && (
              <>
                <div className="flex flex-wrap gap-1 items-center">
                  <span className="rounded-md bg-background/60 ring-1 ring-border/50 px-2 py-1 font-mono text-[10px]">
                    <span className="text-muted-foreground mr-1">Cenário</span>
                    <span className="text-foreground font-bold">{scenarioLabel[pg!.scenario] ?? pg!.scenario}</span>
                  </span>
                  <span className="text-muted-foreground/60 text-[10px]">›</span>
                  <span className={cn(
                    "rounded-md ring-1 px-2 py-1 font-mono text-[10px]",
                    pg!.in_range ? "bg-emerald-500/8 ring-emerald-500/30" : "bg-red-500/8 ring-red-500/30"
                  )}>
                    <span className="text-muted-foreground mr-1">Mão</span>
                    <span className={cn("font-bold", pg!.in_range ? "text-emerald-400" : "text-red-400")}>
                      {pg!.hand_type} {pg!.in_range ? '✓' : '✗'}
                    </span>
                  </span>
                </div>
                {hasFreqs && (
                  <div className="space-y-1">
                    {(() => {
                      const isRFI = pg!.scenario === 'rfi';
                      const validVs = pg!.vs_position && pg!.vs_position !== 'UNKNOWN' ? pg!.vs_position : null;
                      // Contexto: RFI mostra "abrindo"; vs_RFI/3bet/etc mostra "vs OPENER"
                      const ctxStr = isRFI
                        ? `${pg!.position} abrindo ${pg!.stack_bucket}`
                        : (validVs ? `vs ${validVs} · ${pg!.stack_bucket}` : `${pg!.position} ${pg!.stack_bucket}`);
                      const title = useHandFreq
                        ? `Frequência GTO específica de ${pg!.hand_type} em ${ctxStr}`
                        : `Range agregado em ${ctxStr}`;
                      const display = useHandFreq
                        ? `Como GTO joga ${pg!.hand_type} · ${ctxStr}`
                        : `Range agregado · ${ctxStr}`;
                      return (
                        <div className="font-mono text-[9px] uppercase tracking-wide text-muted-foreground" title={title}>
                          {display}
                        </div>
                      );
                    })()}
                    <div className="flex h-2 rounded overflow-hidden ring-1 ring-border/30">
                      {foldPct > 0.001 && (
                        <div title={`Fold ${(foldPct*100).toFixed(1)}%`}
                             style={{ width: `${foldPct*100}%`, background: 'rgba(120,120,120,0.25)' }} />
                      )}
                      {callPct > 0.001 && (
                        <div title={`Call ${(callPct*100).toFixed(1)}%`}
                             style={{ width: `${callPct*100}%`, background: '#3b82f6' }} />
                      )}
                      {raisePct > 0.001 && (
                        <div title={`Raise ${(raisePct*100).toFixed(1)}%`}
                             style={{ width: `${raisePct*100}%`, background: '#10b981' }} />
                      )}
                      {allinPct > 0.001 && (
                        <div title={`Allin ${(allinPct*100).toFixed(1)}%`}
                             style={{ width: `${allinPct*100}%`, background: '#ef4444' }} />
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap font-mono text-[10px]">
                      {foldPct > 0.001 && (
                        <span className="text-muted-foreground">
                          <span className="inline-block size-1.5 mr-1 rounded-sm" style={{background:'rgba(120,120,120,0.4)'}}/>Fold {(foldPct*100).toFixed(0)}%
                        </span>
                      )}
                      {callPct > 0.001 && (
                        <span className="text-blue-400">
                          <span className="inline-block size-1.5 mr-1 rounded-sm" style={{background:'#3b82f6'}}/>Call {(callPct*100).toFixed(1)}%
                        </span>
                      )}
                      {raisePct > 0.001 && (
                        <span className="text-emerald-400">
                          <span className="inline-block size-1.5 mr-1 rounded-sm" style={{background:'#10b981'}}/>Raise {(raisePct*100).toFixed(1)}%
                        </span>
                      )}
                      {allinPct > 0.001 && (
                        <span className="text-red-400">
                          <span className="inline-block size-1.5 mr-1 rounded-sm" style={{background:'#ef4444'}}/>Allin {(allinPct*100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
            {isPostflop && spr != null && (
              <div className="flex items-center gap-2 font-mono text-[11px]"
                title="SPR (Stack-to-Pot Ratio): stack efetivo ÷ pot. < 2 = comprometido; 2–5 = médio; > 5 = fundo">
                <span className="w-14 shrink-0 text-muted-foreground uppercase text-[10px]">SPR</span>
                <span className={cn("font-bold tabular-nums", sprColor)}>{spr.toFixed(1)}</span>
                {sprLabel && <span className={cn("uppercase text-[10px]", sprColor)}>{sprLabel}</span>}
              </div>
            )}
            {isPostflop && sizingPct != null && (
              <div className="flex items-center gap-2 font-mono text-[11px]"
                title="Tamanho da sua aposta em relação ao pot antes da ação">
                <span className="w-14 shrink-0 text-muted-foreground uppercase text-[10px]">Sizing</span>
                <span className="font-bold tabular-nums text-foreground">{sizingPct}%</span>
                <span className="text-muted-foreground text-[10px]">do pot</span>
              </div>
            )}
            {eq != null && (
              <div className="flex items-center gap-2 font-mono text-[11px]"
                title="Equity estimada da sua mão vs range provável do villain neste momento">
                <span className="w-14 shrink-0 text-muted-foreground uppercase text-[10px]">Equity</span>
                <span className={cn(
                  "font-bold tabular-nums",
                  eq >= 0.65 ? "text-emerald-400" :
                  eq >= 0.50 ? "text-foreground" :
                  eq >= 0.35 ? "text-amber-400" : "text-red-400"
                )}>{(eq * 100).toFixed(1)}%</span>
                <span className="text-muted-foreground text-[10px]">
                  {eq >= 0.65 ? "forte" : eq >= 0.50 ? "favorável" : eq >= 0.35 ? "marginal" : "fraca"}
                </span>
              </div>
            )}
            {req != null && req > 0 && (
              <div className="flex items-center gap-2 font-mono text-[11px]"
                title={requiredIsAdjusted
                  ? `Equity mínima ajustada por realization e pressão ICM. Pot odds bruto: ${(poRaw! * 100).toFixed(1)}%.`
                  : "Equity mínima para call ser break-even (bet ÷ (bet + pot))"}>
                <span className="w-14 shrink-0 text-muted-foreground uppercase text-[10px]">Necess.</span>
                <span className="font-bold tabular-nums text-foreground/80">{(req * 100).toFixed(1)}%</span>
                {eq != null && (
                  <span className={cn(
                    "text-[10px]",
                    eq >= req ? "text-emerald-400" : "text-red-400"
                  )}>
                    {eq >= req ? `+${((eq - req) * 100).toFixed(1)}pp` : `${((eq - req) * 100).toFixed(1)}pp`}
                  </span>
                )}
              </div>
            )}
          </>
        );

        // PRO_NOTES (toggle — texto longo profissional)
        const proNotes = showProNotes ? (
          <div className="space-y-1">
            {(pg!.pro_notes ?? []).map((note, i) => (
              <p key={i} className="text-[13px] text-muted-foreground leading-relaxed">{note}</p>
            ))}
          </div>
        ) : null;

        const hasIndicators = showAuditPreflop ||
                              (isPostflop && (spr != null || sizingPct != null)) ||
                              eq != null || (req != null && req > 0);

        return (
          <DecisionCard
            verdict={verdict}
            source={{
              label: SOURCE_LABEL[sourceVariant],
              tooltip: SOURCE_TOOLTIP[sourceVariant],
              variant: sourceVariant,
            }}
            playedAction={playedAction}
            idealAction={idealAction}
            idealLabel={hasGto ? "GTO recomenda" : "Recomendado"}
            isActionOk={isActionOk}
            evidence={evidence}
            indicators={hasIndicators ? indicators : undefined}
            why={why}
            proNotes={proNotes}
            footer={{
              stackBb: step.hero_stack_bb,
              mRatio: step.m_ratio,
              icmPressure: step.icm_pressure,
            }}
            showDetails={showDetails}
            onToggleDetails={toggleDetails}
            verdictTooltip={effectiveGtoLabel ? GTO_LABEL_TOOLTIP[effectiveGtoLabel] : undefined}
            fmtAction={fmtAction}
          />
        );
      })()}


      {/* ── GTO em processamento automático (postflop, sem label ainda) ── */}
      {step.is_hero && step.type === "action" && isPostflop && !hasGto
        && step.action !== "shows" && step.action !== "mucks" && (
        <section className="rounded-xl border border-border bg-hud-surface p-3 space-y-2.5">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-4 shrink-0 text-muted-foreground" />
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground flex-1">
              Análise GTO
            </span>
            <span className="font-mono text-[9px] text-muted-foreground/60 uppercase">Processando</span>
          </div>
          {(gtoRequestStatus === "idle" || gtoRequestStatus === "requesting") && (
            <div className="flex items-center gap-2 rounded-lg bg-sky-500/5 border border-sky-500/20 px-2.5 py-2">
              <Loader2 className="size-3.5 text-sky-400 shrink-0 animate-spin" />
              <p className="text-[11px] text-sky-400">
                Analisando este spot automaticamente. Recarregue a página em instantes para ver os resultados.
              </p>
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
                Spot enfileirado para o solver — ainda não temos dados GTO para este cenário. O cálculo pode levar alguns minutos.
              </p>
            </div>
          )}
          {gtoRequestStatus === "done" && hasGto && (
            <div className="flex items-center gap-2 rounded-lg bg-emerald-500/5 border border-emerald-500/20 px-2.5 py-2">
              <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" />
              <p className="text-[11px] text-emerald-400">
                Análise GTO carregada.
              </p>
            </div>
          )}
          {gtoRequestStatus === "done" && !hasGto && (
            <div className="flex items-start gap-2 rounded-lg bg-muted/30 border border-border/60 px-2.5 py-2">
              <Info className="size-3.5 text-muted-foreground shrink-0 mt-px" />
              <p className="text-[11px] text-muted-foreground/85 leading-relaxed">
                Solver processou mas não retornou solução — spot multiway sem cobertura na árvore GTO atual.
              </p>
            </div>
          )}
          {gtoRequestStatus === "error" && (
            <div className="flex items-center gap-2 rounded-lg bg-destructive/5 border border-destructive/20 px-2.5 py-2">
              <AlertOctagon className="size-3.5 text-destructive shrink-0" />
              <p className="text-[11px] text-destructive">Não foi possível calcular GTO para este spot.</p>
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
          {/* Header */}
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary">
              {t("decision.handResult")}
            </span>
            {step.summary.total_pot != null && (
              <span className="font-mono text-[10px] text-muted-foreground">
                Pot: <span className="text-foreground font-medium">
                  {(step.summary.total_pot / (replayData?.bb ?? 100)).toFixed(1)} BB
                </span>
              </span>
            )}
          </div>

          {/* Seats — layout de 2 linhas por jogador */}
          <div className="flex flex-col gap-1.5">
            {step.summary.seats.map((sd, i) => {
              const isWinner = sd.outcome === "won";
              const wonBb    = sd.won ? (sd.won / (replayData?.bb ?? 100)).toFixed(1) : null;
              // Bounty from seat data (PKO tournaments)
              const seatEntry = Object.values(step.seats ?? {}).find(s => s.player === sd.player);
              const bounty    = seatEntry?.bounty ?? null;
              const koEvent   = step.knockout_events?.find(ko => ko.winner === sd.player);
              return (
                <div key={i} className={cn(
                  "rounded-lg px-2.5 py-2 ring-1 space-y-1.5",
                  isWinner ? "bg-primary/10 ring-primary/30" : "ring-border/20 opacity-50"
                )}>
                  {/* Linha 1: nome + ganho */}
                  <div className="flex items-center gap-1.5 min-w-0">
                    {isWinner && <span className="shrink-0 text-sm leading-none">🏆</span>}
                    <span className={cn(
                      "text-xs font-semibold flex-1 min-w-0 truncate",
                      isWinner ? "text-primary" : "text-muted-foreground"
                    )}>
                      {playerAliases[sd.player] ?? sd.player}
                    </span>
                    {bounty != null && bounty > 0 && (
                      <span className="font-mono text-[9px] text-amber-400 shrink-0">
                        💀${bounty.toFixed(2)}
                      </span>
                    )}
                    {koEvent && (
                      <span className="font-mono text-[9px] text-emerald-400 font-bold shrink-0">
                        +💀${koEvent.amount.toFixed(2)}
                      </span>
                    )}
                    {isWinner && wonBb && (
                      <span className="font-mono text-xs font-bold text-primary shrink-0">
                        +{wonBb} BB
                      </span>
                    )}
                  </div>
                  {/* Linha 2: cartas + descrição da mão */}
                  {(sd.cards?.length > 0 || sd.hand_desc) && (
                    <div className="flex items-center gap-2 flex-wrap">
                      {sd.cards?.length > 0 && (
                        <div className="flex gap-0.5 shrink-0">
                          {parseCards(sd.cards).map((c, j) => (
                            <PlayingCard key={j} card={c} size="sm" />
                          ))}
                        </div>
                      )}
                      {sd.hand_desc === "mucked" ? (
                        <span className="font-mono text-[10px] italic text-muted-foreground/40">
                          {t("decision.mucked")}
                        </span>
                      ) : sd.hand_desc && sd.hand_desc !== "collected" ? (
                        <span className={cn(
                          "font-mono text-[10px] leading-snug",
                          isWinner ? "text-primary/70" : "text-muted-foreground/60"
                        )}>
                          {sd.hand_desc}
                        </span>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Knockout events (PKO tournaments) */}
          {step.knockout_events && step.knockout_events.length > 0 && (
            <div className="border-t border-border/30 pt-2 flex flex-col gap-1">
              {step.knockout_events.map((ko, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-400/90 min-w-0">
                  <span className="shrink-0">💀</span>
                  <span className="font-bold shrink-0">{playerAliases[ko.winner] ?? ko.winner}</span>
                  <span className="text-muted-foreground shrink-0">eliminou</span>
                  <span className="truncate">{playerAliases[ko.eliminated] ?? ko.eliminated}</span>
                  <span className="ml-auto font-bold text-emerald-400 shrink-0">+${ko.amount.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}
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
  // Track which hand_id we already auto-requested so we don't spam on step navigation
  const gtoAutoRequestedRef = useRef<string | null>(null);

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

  // Auto-request GTO when navigating to a postflop hero step without GTO data
  useEffect(() => {
    if (!replayData || !handId) return;
    const steps = replayData.timeline ?? [];
    const hasPostflopHeroNoGto = steps.some(s =>
      s.is_hero && s.type === "action" && s.street !== "preflop" && !s.gto_label &&
      s.action !== "shows" && s.action !== "mucks"
    );
    if (!hasPostflopHeroNoGto) return;
    if (gtoAutoRequestedRef.current === handId) return;
    if (gtoRequestStatus !== "idle") return;
    gtoAutoRequestedRef.current = handId;
    handleRequestGto();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replayData, handId]);

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
