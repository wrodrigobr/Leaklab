import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, Pause, Play, Rewind, FastForward, AlertOctagon, CheckCircle2, Loader2, ArrowLeft, GraduationCap, PenLine, X, Check, Trash2, LayoutGrid, FlaskConical, Clock, Eye, EyeOff, Info, Maximize2, Minimize2, Lock, Users } from "lucide-react";
import logoHorizontal from "@/assets/brand/grindlab_final_horizontal.svg";
import { useMutation } from "@tanstack/react-query";
import { HudLayout } from "@/components/hud/HudLayout";
import { HudHeader } from "@/components/hud/HudHeader";
import { PokerTableV3 } from "@/components/hud/PokerTableV3";
import { useTableOrientation } from "@/hooks/use-table-orientation";
import { useIsLandscapeMobile } from "@/hooks/use-is-landscape-mobile";
import { RangePanel } from "@/components/replayer/RangePanel";
import { GtoStrategyPanel } from "@/components/replayer/GtoStrategyPanel";
import { DecisionCard, type DecisionSourceVariant } from "@/components/replayer/DecisionCard";
import { PlayingCard, type CardData } from "@/components/hud/PlayingCard";
import { cn } from "@/lib/utils";
import { computeEffectiveGtoLabel } from "@/lib/gtoUtils";
import { livePlayers as computeLivePlayers, isMultiwayPot, isPpMuted, idealActionSource, verdictStrategy, verdictLevel, type VerdictLevel } from "@/lib/cardLogic";
import { VerdictPill } from "@/components/replayer/VerdictPill";
import { ACTION_COLORS } from "@/lib/actionColors";
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
  gtoRequestStatus: "idle" | "requesting" | "queued" | "solver_queued" | "done" | "error" | "quota_exceeded";
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

  const isPostflop = step.street !== 'preflop';
  // Spot multiway postflop: o solver HU não é confiável (backend zera gto_label/strategy).
  // Quando o advisor multiway DEFERE (sem multiway_advice), o veredito vem da SEVERIDADE
  // do engine (error_label EV-capado), não do gto_label de frequência HU. Card = badge.
  const isMultiwayStep = isPostflop && (step.n_active_opponents ?? 0) >= 2;
  const pg = step.preflop_gto ?? null;
  // Cobertura preflop negada explicitamente (ex.: pote limpado "vs Limp"): a análise
  // AO VIVO manda. Um gto_label ARMAZENADO stale (scoring antigo, pré-feature do limp)
  // NÃO pode forjar um veredito/badge que contradiz "sem cobertura".
  const preflopNoCoverage = !isPostflop && !!pg && !pg.available && !!pg.coverage_reason;
  // Call-vs-shove sem dado GTO (heurística): avaliado por POT ODDS (equity vs
  // necessária), NÃO pelo range de abertura. O fallback reusava o chrome do RFI
  // ("Range de abertura", "Fold X% agregado", chip "no range") — referência errada
  // p/ um call. Aqui o card vira uma decisão de math (equity × pot odds), coerente.
  const isShoveFb = !isPostflop && pg?.scenario === 'vs_shove_fallback' && !!pg?.available;
  const _fbEq  = step.hand_equity ?? null;
  const _fbReq = step.adjusted_required_equity ?? step.pot_odds_equity ?? null;
  const _fbCallEv  = (_fbEq != null && _fbReq != null) ? _fbEq >= _fbReq : null;
  const _fbActionOk = _fbCallEv == null ? null
    : ((step.action ?? '').toLowerCase() === 'fold' ? !_fbCallEv : _fbCallEv);
  const hasGto     = !!step.gto_label && !preflopNoCoverage && !isShoveFb;

  // ── Compute these FIRST so verdict can reference live GTO data ───────────────

  const playedAction = (!isPostflop && pg?.available) ? pg.action_taken : (step.action ?? "—");

  const stratSorted = step.gto_strategy
    ? [...step.gto_strategy].sort((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0))
    : [];

  // VEREDITO/RECOMENDAÇÃO postflop: estratégia da MÃO específica do hero (hand_strategy),
  // não o range agregado. Regra pura + testada em cardLogic.verdictStrategy. O widget
  // continua mostrando o range (contexto) + a mão lado a lado; só o veredito vira da mão.
  const verdictStrat = verdictStrategy(isPostflop, step.hand_strategy?.actions, stratSorted);

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
    ? computeEffectiveGtoLabel(verdictStrat, step.gto_label, step.action)
    : null;

  // ── Unified verdict: GTO Solver > Range > Engine ────────────────────────────
  const GTO_LABEL_TOOLTIP: Record<string, string> = {
    gto_correct:         t("card.gtoCorrectTip"),
    gto_mixed:           t("card.gtoMixedTip"),
    gto_minor_deviation: t("card.gtoMinorTip"),
    gto_critical:        t("card.gtoCriticalTip"),
  };

  type VInfo = { icon: string; label: string; cls: string; borderCls: string; hdrCls: string; source: string; sourceTooltip: string };
  const verdict = ((): VInfo | null => {
    if (!step.is_hero || step.type !== "action") return null;
    // Skip non-decision actions (shows, mucks, posts)
    const _actLow = (step.action ?? '').toLowerCase();
    if (_actLow === 'shows' || _actLow === 'show' || _actLow === 'mucks' || _actLow === 'muck' || _actLow === 'posts' || _actLow === 'post') return null;
    // Sem cobertura GTO ao vivo (pote limpado etc.): banner NEUTRO "sem veredito" —
    // não exibe o gto_label armazenado stale (que diria DESVIO CRÍTICO contradizendo
    // o "vs Limp" do corpo). A tag de cobertura abaixo explica o motivo.
    if (preflopNoCoverage) {
      return { icon: "·", label: t("card.vNoCoverage"), cls: "text-muted-foreground",
               borderCls: "border-border", hdrCls: "bg-hud-surface",
               source: "Preflop", sourceTooltip: t("card.tipNoCoverage") };
    }
    // ── FEAT-20: VEREDITO DE 3 NÍVEIS (Correto / Aceitável / Erro) ──────────────
    // Dirigido pela SEVERIDADE (error_label, EV-capada) — a MESMA régua do badge de
    // aderência → card = badge por construção. A frequência (gto_label) deixou de ser
    // veredito; vive só nas barras de estratégia (contexto). Fonte = só p/ o tooltip.
    const _src: { name: string; tip: string } =
        step.multiway_advice          ? { name: t("card.srcMultiway"),  tip: t("card.tipMultiwayEstimate") }
      : isMultiwayStep                 ? { name: "Engine",               tip: t("card.srcEngineTip") }
      : isShoveFb                      ? { name: t("card.srcHeuristic"), tip: t("card.srcHeuristicTip") }
      : effectiveGtoLabel              ? { name: "Solver",               tip: t("card.tipGtoSolver") }
      : (!isPostflop && pg?.available) ? { name: "Preflop",              tip: t("card.tipRange") }
      :                                  { name: "Engine",               tip: t("card.tipEngine") };
    const _hasBasis = isError || !!step.error_label || hasGto || !!pg?.available
      || step.multiway_advice != null || step.hand_equity != null || step.pot_odds_equity != null;
    if (!_hasBasis) return null;
    const _lvl: "correct" | "acceptable" | "error" =
        verdictLevel(step.error_label) ?? (isError ? "error" : "correct");
    const _M: Record<"correct" | "acceptable" | "error", VInfo> = {
      correct:    { icon: "✓", label: t("card.vCorrect"),    cls: "text-emerald-400", borderCls: "border-emerald-500/30", hdrCls: "bg-emerald-500/8", source: _src.name, sourceTooltip: _src.tip },
      acceptable: { icon: "◎", label: t("card.vAcceptable"), cls: "text-sky-400",     borderCls: "border-sky-500/30",     hdrCls: "bg-sky-500/8",     source: _src.name, sourceTooltip: _src.tip },
      error:      { icon: "✗", label: t("card.vError"),      cls: "text-red-400",     borderCls: "border-red-500/30",     hdrCls: "bg-red-500/8",     source: _src.name, sourceTooltip: _src.tip },
    };
    return _M[_lvl];
  })();
  const showDecision = !!verdict && (studentId !== null || coachAnnotation?.mode !== "replace");

  // Action comparison (playedAction already computed above) — FEAT-20: "ação ok" =
  // veredito NÃO-Erro (mesma severidade que dirige o card). Consistente com o badge.
  const isActionOk = verdictLevel(step.error_label) != null
    ? verdictLevel(step.error_label) !== "error"
    : (isShoveFb ? (_fbActionOk ?? false) : !isError);
  // idealAction: use live top action when available (overrides stored gto_action which may be stale)
  const liveTopAction = verdictStrat.length > 0 ? verdictStrat[0].action : null;
  // Fonte da "ação recomendada" por prioridade (idealActionSource, testável). Preflop
  // coberto usa o RANGE (ação dominante do hand_freq) ANTES do gto_action do engine —
  // senão AA squeeze @14bb mostrava "GTO recomenda Call" em vez de Raise 93%.
  const _idealSrc = idealActionSource({
    preflopNoCoverage, isShoveFb, isPostflop, pgAvailable: !!pg?.available, hasGto,
  });
  const idealAction =
      _idealSrc === "none"    ? null
    : _idealSrc === "potodds" ? (_fbCallEv == null ? null : fmtAction(_fbCallEv ? 'call' : 'fold'))
    : _idealSrc === "range"   ? pg!.recommended_actions.map(fmtAction).join(" / ")
    : _idealSrc === "solver"  ? (liveTopAction ?? step.gto_action ?? null)
    : (step.best_action ? fmtAction(step.best_action) : null);  // engine
  const showTwoCols = !isActionOk && !!idealAction &&
    idealAction.toLowerCase() !== playedAction.toLowerCase();
  const topFreqPct = verdictStrat.length > 0
    ? ((verdictStrat[0].frequency ?? 0) * 100).toFixed(0) : null;
  const evDiff = (() => {
    if (!verdictStrat.length) return null;
    const top = verdictStrat[0].ev_bb;
    if (top == null) return null;
    const playerEv = verdictStrat.find(s => isPlayedAct(s.action))?.ev_bb ?? null;
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
    vs_shove_fallback: t("card.scenVsShoveFallback"),
    squeeze: "Squeeze",
    faces_squeeze: "vs Squeeze",
    vs_4bet: "vs 4-Bet",
  };
  // Rótulo do range_pct por cenário: "abertura" só faz sentido no RFI; nos demais
  // é defesa/continuação/squeeze (antes era "Range de abertura" hardcoded p/ todos).
  const rangeLabelKey: Record<string, string> = {
    rfi: "card.rangeOpening", vs_shove_fallback: "card.rangeOpening",
    vs_rfi: "card.rangeDefense",
    vs_3bet: "card.rangeContinue", faces_squeeze: "card.rangeContinue", vs_4bet: "card.rangeContinue",
    squeeze: "card.rangeSqueeze",
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
          step.multiway_advice                    ? "multiway"  :
          (isMultiwayStep && !step.gto_label)     ? "engine"    :  // multiway deferido → severidade do engine
          preflopNoCoverage                       ? "na"        :
          step.gto_spot_mismatch                  ? "na"        :
          isShoveFb                               ? "heuristic" :
          effectiveGtoLabel                       ? "gto"       :
          (!isPostflop && pg?.available)          ? "preflop"   :
          isPfZone                                ? "pushfold"  :
          (step.is_hero && !step.gto_label)       ? "heuristic" :
                                                    "engine";
        const SOURCE_LABEL: Record<DecisionSourceVariant, string> = {
          gto: "Solver", preflop: "Preflop", engine: "Engine",
          heuristic: t("card.srcHeuristic"), pushfold: "Push/Fold",
          multiway: t("card.srcMultiway"), na: "Spot N/A",
        };
        const SOURCE_TOOLTIP: Record<DecisionSourceVariant, string> = {
          gto: t("card.srcGtoTip"),
          preflop: t("card.srcPreflopTip"),
          engine: t("card.srcEngineTip"),
          heuristic: t("card.srcHeuristicTip"),
          pushfold: t("card.srcPushfoldTip"),
          multiway: t("card.tipMultiwayEstimate"),
          na: t("card.srcNaTip"),
        };

        // ──────── Pré-cálculos compartilhados (postflop) ────────
        const eq = step.hand_equity ?? null;
        // #27: equity vs a RFI range real do opener (vs_rfi) — não vs mão aleatória.
        const isVsRange = step.equity_source === "vs_range";
        const poRaw = step.pot_odds_equity ?? null;
        // Engine usa adjusted_required_equity (pot_odds + realization_adj + pressure_adj)
        // para classificar. Usamos isso quando disponível — coerência verdict × frase × badge.
        // Fallback para pot_odds bruto preserva compat com decisions antigas sem o campo.
        const req = step.adjusted_required_equity ?? poRaw;
        const profitable = eq != null && req != null && req > 0 ? eq >= req : null;
        // Implicit required equity para bet/raise próprios:
        // bet ÷ (pot_after_call) = sizing_pct / (1 + 2·sizing_pct).
        // Significado: "mínima equity quando pago para o bet ser +EV". Threshold informativo
        // pra apostas próprias quando não há pot odds tradicional.
        const reqImplicit = (req == null || req <= 0)
          ? (() => {
              const isBetActLocal = step.is_hero && (step.action === "bet" || step.action === "raise" || step.action === "shove");
              const bbLocal = step.bb ?? (replayData?.bb ?? 100);
              const amtBbLocal = (isBetActLocal && step.amount) ? step.amount / bbLocal : null;
              const potBeforeBbLocal = (amtBbLocal != null && step.pot_bb != null) ? step.pot_bb - amtBbLocal : null;
              if (amtBbLocal != null && potBeforeBbLocal != null && potBeforeBbLocal > 0) {
                const s = amtBbLocal / potBeforeBbLocal;
                return s / (1 + 2 * s);
              }
              return null;
            })()
          : null;
        const spr = (step.hero_stack_bb != null && step.pot_bb != null && step.pot_bb > 0)
                    ? step.hero_stack_bb / step.pot_bb : null;
        const hasMathEvidence = (isPostflop || isShoveFb) && eq != null && req != null && req > 0;
        const requiredIsAdjusted = step.adjusted_required_equity != null &&
                                   poRaw != null &&
                                   Math.abs(step.adjusted_required_equity - poRaw) >= 0.005;
        const hasEngineGtoConflict = !step.gto_spot_mismatch && step.engine_best && step.gto_action &&
                                     step.engine_best !== step.gto_action && isError;

        // ──────── Why (1 frase dominante, prioridade descendente) ────────
        let why = "";
        if (step.multiway_advice) {
          // Estimativa multiway: o why HU (ex.: "Call lucrativo 37% ≥ 24%") usa a equity
          // vs aleatória/HU e CONTRADIZ o fold. A frase aqui é a da estimativa multiway.
          why = t("card.whyMultiwayEstimate");
        } else if (preflopNoCoverage) {
          // Sem cobertura GTO (pote limpado etc.): a tag de cobertura abaixo já
          // explica o motivo; não inventar frase de "porquê" baseada em dado stale.
          why = "";
        } else if (step.gto_spot_mismatch) {
          why = step.engine_best === "call"
            ? t("card.whyMismatchFacing")
            : t("card.whyMismatchNoBet");
        } else if (isPfZone) {
          why = t("card.whyPushfold", { stack: step.hero_stack_bb!.toFixed(1) });
        } else if (hasEngineGtoConflict) {
          why = t("card.whyEngineConflict", { engine: fmtAction(step.engine_best!), gto: fmtAction(step.gto_action!) });
        } else if (hasMathEvidence) {
          // Frase descreve a AÇÃO TOMADA pelo hero, não a alternativa.
          // "Call lucrativo" quando hero foldou confunde — soa como crítica oposta ao verdict.
          const eqPct = Math.round(eq! * 100);
          const reqPct = Math.round(req! * 100);
          const margin = eqPct - reqPct;
          const heroAct = (step.action ?? '').toLowerCase();
          // "necessário" usa adjusted_required quando disponível (engine ajusta por realization
          // e pressão ICM). Quando não há ajuste relevante, é pot odds bruto.
          const reqLabel = requiredIsAdjusted ? t("card.reqLabelAdjusted") : t("card.reqLabelPotOdds");
          if (heroAct === 'fold') {
            why = profitable
              ? (margin <= 3
                  ? t("card.whyFoldBreakeven", { eqPct, reqLabel, reqPct })
                  : t("card.whyFoldLeftEv", { eqPct, reqLabel, reqPct }))
              : t("card.whyFoldCorrect", { eqPct, reqPct, reqLabel });
          } else if (heroAct === 'call') {
            why = profitable
              ? t("card.whyCallProfit", { eqPct, reqLabel, reqPct })
              : t("card.whyCallLose", { eqPct, reqPct, reqLabel });
          } else if (heroAct === 'check') {
            why = t("card.whyCheck", { eqPct, reqLabel, reqPct });
          } else {
            // bet/raise/shove
            why = profitable
              ? t("card.whyAggrProfit", { act: fmtAction(heroAct), eqPct, reqLabel, reqPct })
              : t("card.whyAggrRisk", { act: fmtAction(heroAct), eqPct, reqLabel, reqPct });
          }
        } else if (!isPostflop && pg?.available) {
          const scen = scenarioLabel[pg.scenario] ?? pg.scenario;
          const pct  = pg.range_pct > 0 ? ` (${(pg.range_pct * 100).toFixed(0)}%)` : '';
          why = pg.in_range
            ? t("card.whyInRange", { hand: pg.hand_type, scen, pct, bucket: pg.stack_bucket })
            : t("card.whyOutRange", { hand: pg.hand_type, scen, pct, bucket: pg.stack_bucket });
        } else if (!hasGto && step.is_hero) {
          why = t("card.whyMultiway");
        } else if (isPostflop && eq != null) {
          why = eq >= 0.70 ? t("card.whyEqStrong")
              : eq >= 0.50 ? t("card.whyEqFavorable")
              : eq >= 0.35 ? t("card.whyEqUnfavorable")
              : t("card.whyEqWeak");
        } else {
          why = t("card.whyContext");
        }

        // ──────── Evidence (1 widget, escolhido por contexto) ────────
        let evidence: React.ReactNode = null;
        if (step.multiway_advice) {
          // Estimativa multiway (substitui as barras HU, que o backend zerou): equity da
          // mão vs range de continuação + pot odds. Rotulada como estimativa, não GTO.
          const mw = step.multiway_advice;
          const row = (label: string, val: string) => (
            <div className="flex items-center justify-between text-[9px] font-mono">
              <span className="text-muted-foreground">{label}</span>
              <span className="text-foreground/90">{val}</span>
            </div>
          );
          evidence = (
            <div className="space-y-2">
              <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                {t("card.mwTitle")}
              </div>
              <div className="rounded-md border border-border/50 bg-hud-surface/40 p-2 space-y-1.5">
                {row(t("card.mwEquity"), `${Math.round(mw.equity * 100)}%`)}
                {row(t("card.mwRealized"), `${Math.round(mw.realized_eq * 100)}%`)}
                {mw.required_eq != null && row(t("card.mwRequired"), `${Math.round(mw.required_eq * 100)}%`)}
                <p className="font-mono text-[8px] text-muted-foreground/70 pt-0.5">{mw.rationale}</p>
              </div>
              <p className="font-mono text-[8px] text-amber-400/70">{t("card.mwDisclaimer")}</p>
            </div>
          );
        } else if (!step.gto_spot_mismatch && stratSorted.length >= 1 && (isPostflop || !pg?.available)) {
          // Solver strategy widget (postflop GTO ou preflop sem range)
          evidence = (
            <div className="space-y-2">
              <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                {t("card.solverStrategy")}
              </div>
              <GtoStrategyPanel
                strategy={stratSorted}
                playedAction={playedAction}
                handStrategy={step.hand_strategy ?? null}
                handTitle={t("card.handStrat")}
                handTip={t("card.handStratTip")}
              />
            </div>
          );
        } else if (hasMathEvidence) {
          // Math card — usa adjusted_required_equity (mesmo critério do engine).
          // Tooltip mostra pot_odds bruto quando há ajuste relevante para didática.
          const mathCallIsEv  = eq! >= req!;
          // O badge da AÇÃO segue o veredito (isActionOk), não só "equity ≥ pot odds".
          // Numa ação agressiva (bet/raise) que o engine marca ERRO mas é "+EV vs fold",
          // o antigo "RAISE +EV" verde contradizia o "✗ ERRO". Agora bate com o veredito.
          const mathActionIsEv = isActionOk;
          const mathActLabel  = step.action ? fmtAction(step.action) : null;
          const mathBadgeCls  = mathActionIsEv
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            : "bg-red-500/10 text-red-400 border border-red-500/20";
          const mathBadgeLabel = `${mathActLabel ?? ''} ${mathActionIsEv ? "+EV" : "−EV"}`.trim();
          const reqHeader = requiredIsAdjusted ? t("card.reqEquity") : "Pot Odds";
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
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">{t(rangeLabelKey[pg.scenario] ?? "card.rangeOpening")}</span>
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
        const showAuditPreflop = !isPostflop && pg?.available && !isShoveFb;
        const showProNotes = showAuditPreflop && (pg!.pro_notes?.length ?? 0) > 0 &&
                             !(effectiveGtoLabel &&
                               ['gto_correct','gto_mixed','gto_minor_deviation'].includes(effectiveGtoLabel) &&
                               ['leak','major_leak'].includes(pg!.action_quality));
        const sprColor = spr == null ? "" : spr < 2 ? "text-amber-400" : spr < 5 ? "text-sky-400" : "text-muted-foreground";
        const sprLabel = spr == null ? null : spr < 2 ? t("card.sprCommitted") : spr < 5 ? t("card.sprMid") : t("card.sprDeep");
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

        // Multiway: jogadores ainda no pote = dealt − foldados (acumulado até o passo).
        // O solver postflop é resolvido HEADS-UP; em pote 3+ way a estratégia é
        // aproximação (a equity já é ajustada pelo nº de oponentes). Sinaliza no card.
        const livePlayers = computeLivePlayers(step.seats as Record<string, unknown> | undefined, step.folded);
        const isMultiway = isMultiwayPot(isPostflop, livePlayers);

        const indicators = (
          <>
            {/* O perfil/stats do oponente (HUD) saiu do card — agora vive na MESA (box por
                assento, estilo HM). Aqui fica só o AJUSTE exploitativo (acionável). */}
            {/* HUD Fase 3: AJUSTE exploitativo sobre o veredito (só com amostra confiável). */}
            {(() => {
              const ex = (step as { exploit?: { key: string; params: Record<string, unknown>; severity: string } }).exploit;
              if (!ex?.key) return null;
              const high = ex.severity === "high";
              return (
                <div className={cn("rounded-lg ring-1 px-2.5 py-2", high ? "bg-red-500/8 ring-red-500/25" : "bg-amber-500/8 ring-amber-500/25")}>
                  <p className={cn("font-mono text-[9px] font-bold uppercase tracking-wider mb-0.5", high ? "text-red-300/90" : "text-amber-300/90")}>
                    ⚡ {t("card.exploitTitle")}
                  </p>
                  <p className="text-[11.5px] text-foreground/85 leading-relaxed">
                    {t(`card.exploit.${ex.key}`, ex.params)}
                  </p>
                </div>
              );
            })()}
            {/* Sizing do open (Fase 1): tamanho do open preflop do hero vs o padrão. */}
            {(() => {
              const sz = (step as { sizing_advice?: { key: string; status: string; params: Record<string, unknown> } }).sizing_advice;
              if (!sz?.key) return null;
              const ok = sz.status === "ok";
              return (
                <div className="flex items-baseline gap-2.5 font-mono text-[11px]" title={t(`card.sizingAdvice.${sz.key}`, sz.params)}>
                  <span className="w-[74px] shrink-0 uppercase text-[9px] tracking-wider text-muted-foreground/60 pt-px">{t("card.sizingLabel")}</span>
                  <span className="flex-1 min-w-0">
                    <span className={cn("font-bold tabular-nums", ok ? "text-emerald-400/90" : "text-amber-300")}>{String(sz.params.to)}bb</span>
                    <span className="text-muted-foreground/70"> · {t(`card.sizingAdvice.${sz.key}`, sz.params)}</span>
                  </span>
                </div>
              );
            })()}
            {/* Sizing do 3-bet (#3): tamanho do 3-bet do hero como múltiplo do open (IP 3x/OOP 4x). */}
            {(() => {
              const sz = (step as { threebet_sizing?: { key: string; status: string; params: { ratio: number; ideal: string; pos: string } } }).threebet_sizing;
              if (!sz?.key) return null;
              const ok = sz.status === "ok";
              return (
                <div className="flex items-baseline gap-2.5 font-mono text-[11px]" title={t(`card.sizingAdvice.${sz.key}`, sz.params)}>
                  <span className="w-[74px] shrink-0 uppercase text-[9px] tracking-wider text-muted-foreground/60 pt-px">{t("card.sizingLabel")}</span>
                  <span className="flex-1 min-w-0">
                    <span className={cn("font-bold tabular-nums", ok ? "text-emerald-400/90" : "text-amber-300")}>{sz.params.ratio}x</span>
                    <span className="text-muted-foreground/70"> · {t(`card.sizingAdvice.${sz.key}`, sz.params)}</span>
                  </span>
                </div>
              );
            })()}
            {/* Sizing postflop (Fase 2): tamanho da aposta do hero vs o size do próprio nó GTO. */}
            {(() => {
              const sz = (step as { postflop_sizing?: { key: string; status: string; params: { hero: number; gto: number } } }).postflop_sizing;
              if (!sz?.key) return null;
              const ok = sz.status === "ok";
              return (
                <div className="flex items-baseline gap-2.5 font-mono text-[11px]" title={t(`card.sizingAdvice.${sz.key}`, sz.params)}>
                  <span className="w-[74px] shrink-0 uppercase text-[9px] tracking-wider text-muted-foreground/60 pt-px">{t("card.sizingLabel")}</span>
                  <span className="flex-1 min-w-0">
                    <span className={cn("font-bold tabular-nums", ok ? "text-emerald-400/90" : "text-amber-300")}>{sz.params.hero}%</span>
                    <span className="text-muted-foreground/70"> · {t(`card.sizingAdvice.${sz.key}`, sz.params)}</span>
                  </span>
                </div>
              );
            })()}
            {/* Sizing postflop heurístico (Fase 3): spots SEM nó GTO — por textura do board. */}
            {(() => {
              const sz = (step as { postflop_texture_sizing?: { key: string; status: string; params: { hero: number; ideal: string; tex: string } } }).postflop_texture_sizing;
              if (!sz?.key) return null;
              const ok = sz.status === "ok";
              const texLabel = t(`card.sizingTexture.${sz.params.tex}`);
              return (
                <div className="flex items-baseline gap-2.5 font-mono text-[11px]" title={t(`card.sizingTextureTip.${sz.params.tex}`)}>
                  <span className="w-[74px] shrink-0 uppercase text-[9px] tracking-wider text-muted-foreground/60 pt-px">{t("card.sizingLabel")}</span>
                  <span className="flex-1 min-w-0">
                    <span className={cn("font-bold tabular-nums", ok ? "text-emerald-400/90" : "text-amber-300")}>{sz.params.hero}%</span>
                    <span className="text-muted-foreground/70"> · {t(`card.sizingAdvice.${sz.key}`, { ...sz.params, tex: texLabel })}</span>
                  </span>
                </div>
              );
            })()}
            {/* Intenção do 3-BET (preflop): valor / merge / light(blefe) — ensina o PORQUÊ. */}
            {(() => {
              const ti = (step as { threebet_intent?: { intent: string; tier: string; justified: boolean | null } }).threebet_intent;
              if (!ti?.intent) return null;
              const tone = ti.tier === "value" ? "text-emerald-300" : ti.tier === "merge" ? "text-amber-300" : "text-sky-300";
              return (
                <div className="flex items-baseline gap-2.5 font-mono text-[11px]" title={t(`card.threebetTip.${ti.intent}`)}>
                  <span className="w-[74px] shrink-0 uppercase text-[9px] tracking-wider text-muted-foreground/60 pt-px">{t("card.threebetLabel")}</span>
                  <span className="flex-1 min-w-0">
                    <span className={cn("font-bold", tone)}>{t(`card.threebetIntent.${ti.intent}`)}</span>
                    <span className="text-muted-foreground/70"> · {t(`card.threebetGloss.${ti.intent}`)}</span>
                  </span>
                </div>
              );
            })()}
            {/* Racional da jogada recomendada — em spots HEURÍSTICOS (sem barras de
                estratégia GTO pra explicar), diz POR QUE check/bet/call/fold é o ideal.
                Com estimativa multiway, NÃO mostra (o reco_rationale vem do engine HU e
                contradiz o fold: ex.: "mão forte: raise"). A estimativa tem seu racional. */}
            {isPostflop && !hasGto && !step.multiway_advice && (() => {
              const rr = (step as { reco_rationale?: { key: string; params: Record<string, unknown>; action: string } }).reco_rationale;
              if (!rr?.key) return null;
              // Não mostrar "X é a melhor jogada" quando o veredito APROVA a jogada (diferente)
              // do hero — contradiz (ex.: bet ✓, mas o racional argumenta check). O racional só
              // faz sentido como REFORÇO (hero jogou o ideal) ou CORRETIVO (erro), não contra
              // uma jogada aceitável. Em spot marginal multiway, o engine prefere outra ação
              // mas a do hero é OK — aí o texto confunde.
              const _played = (step.action ?? '').toLowerCase().replace(/s$/, '');
              const _rrAct  = (rr.action ?? '').toLowerCase().replace(/s$/, '');
              if (isActionOk && _rrAct && _rrAct !== _played) return null;
              return (
                <div className="rounded-lg bg-primary/5 ring-1 ring-primary/15 px-2.5 py-2">
                  <p className="font-mono text-[9px] font-bold uppercase tracking-wider text-primary/70 mb-0.5">
                    {t("card.rationaleTitle")}
                  </p>
                  <p className="text-[11.5px] text-foreground/85 leading-relaxed">
                    {t(`card.rationale.${rr.key}`, rr.params)}
                  </p>
                </div>
              );
            })()}
            {isMultiway && (
              <div className="flex items-center gap-2 font-mono text-[11px]"
                title={effectiveGtoLabel ? t("card.multiwaySolverTip", { n: livePlayers }) : t("card.multiwayTip", { n: livePlayers })}>
                <span className="rounded-md bg-amber-500/10 ring-1 ring-amber-500/25 px-2 py-1 text-[10px] text-amber-300/90 cursor-help">
                  {t("card.multiway", { n: livePlayers })}
                </span>
              </div>
            )}
            {!step.multiway_advice && (step as { gto_depth_capped?: boolean }).gto_depth_capped && (
              <div className="flex items-center gap-2 font-mono text-[11px]" title={t("card.depthCappedTip")}>
                <span className="rounded-md bg-primary/10 ring-1 ring-primary/25 px-2 py-1 text-[10px] text-primary/90 cursor-help">
                  {t("card.depthCapped")}
                </span>
              </div>
            )}
            {/* POSTFLOP — Slot 4 em 3 blocos que contam a história: SUA MÃO → CUSTO → GEOMETRIA.
                (preflop mantém o layout próprio abaixo; equity/req ficam gated em !isPostflop) */}
            {isPostflop && (eq != null || spr != null || sizingPct != null) && (() => {
              const bi = (step as { bet_intent?: { intent: string; is_leak: boolean; gto_bet_freq: number | null } }).bet_intent;
              const intentTone = !bi?.intent ? "" : bi.is_leak ? "text-red-300"
                : bi.intent.startsWith("value") ? "text-emerald-300"
                : bi.intent === "semi_bluff" ? "text-sky-300" : "text-amber-300";
              const eqColor = eq == null ? "" : eq >= 0.65 ? "text-emerald-400" : eq >= 0.50 ? "text-foreground" : eq >= 0.35 ? "text-amber-400" : "text-red-400";
              const eqQual = eq == null ? "" : eq >= 0.65 ? t("card.eqStrong") : eq >= 0.50 ? t("card.eqFavorable") : eq >= 0.35 ? t("card.eqMarginal") : t("card.eqWeak");
              const reqShown = (req != null && req > 0) ? req : reqImplicit;
              const pp = (eq != null && reqShown != null) ? (eq - reqShown) * 100 : null;
              const ppMuted = pp == null ? true : isPpMuted({ showAuditPreflop: false, effectiveGtoLabel, eq: eq!, reqShown: reqShown!, isActionOk });
              const costQual = effectiveGtoLabel === "gto_critical" ? t("card.costCritical")
                : effectiveGtoLabel === "gto_minor_deviation" ? t("card.costMinor")
                : (effectiveGtoLabel === "gto_correct" || effectiveGtoLabel === "gto_mixed") ? t("card.costAligned")
                : (pp != null && pp >= 0) ? t("card.costPlus") : t("card.costMinus");
              const lblCls = "w-[74px] shrink-0 uppercase text-[9px] tracking-wider text-muted-foreground/60 pt-px";
              return (
                <div className="space-y-1">
                  {/* SUA MÃO — intenção + equity (a leitura que explica o porquê).
                      Com estimativa multiway, oculto: a equity HU (vs aleatória/range HU)
                      diverge da estimativa multiway (ex.: 37% vs 27%) e confunde. */}
                  {!step.multiway_advice && (eq != null || bi?.intent) && (
                    <div className="flex items-baseline gap-2.5 font-mono text-[11px]"
                      title={bi?.intent ? t(`card.betIntentTip.${bi.intent}`) : t("card.equityTip")}>
                      <span className={lblCls}>{t("card.blockHand")}</span>
                      <span className="flex-1 min-w-0">
                        {bi?.intent && <span className={cn("font-bold", intentTone)}>{t(`card.betIntent.${bi.intent}`)}</span>}
                        {bi?.intent && eq != null && <span className="text-muted-foreground/40"> · </span>}
                        {eq != null && (
                          <>
                            <span className={cn("font-bold tabular-nums", eqColor)}>{(eq * 100).toFixed(0)}%</span>
                            <span className="text-muted-foreground/70"> {eqQual}</span>
                          </>
                        )}
                      </span>
                    </div>
                  )}
                  {/* CUSTO — o desvio importa? (promovido: é a punchline de um 'Desvio Leve').
                      Com estimativa multiway, oculto: a margem +pp usa equity/req HU e
                      contradiz o fold ("+13pp com folga" vs realiza 19% < 24%). */}
                  {!step.multiway_advice && pp != null && (
                    <div className="flex items-baseline gap-2.5 font-mono text-[11px]"
                      title={effectiveGtoLabel ? t("card.reqSolverContextTip") : t("card.reqTipImplicit")}>
                      <span className={lblCls}>{pp >= 0 ? t("card.blockMargin") : t("card.blockCost")}</span>
                      <span className="flex-1 min-w-0">
                        <span className={cn("font-bold tabular-nums", ppMuted ? "text-muted-foreground/60" : pp >= 0 ? "text-emerald-400" : "text-red-400")}>
                          {pp >= 0 ? `+${pp.toFixed(1)}` : pp.toFixed(1)}pp
                        </span>
                        <span className="text-muted-foreground/70"> · {costQual}</span>
                      </span>
                    </div>
                  )}
                  {/* GEOMETRIA — SPR + sizing (a forma da aposta/pote; contexto) */}
                  {(spr != null || sizingPct != null) && (
                    <div className="flex items-baseline gap-2.5 font-mono text-[11px]" title={t("card.sprTip")}>
                      <span className={lblCls}>{t("card.blockGeo")}</span>
                      <span className="flex-1 min-w-0">
                        {spr != null && (
                          <>
                            <span className={cn("font-bold tabular-nums", sprColor)}>SPR {spr.toFixed(1)}</span>
                            {sprLabel && <span className={cn(sprColor)}> {sprLabel}</span>}
                          </>
                        )}
                        {spr != null && sizingPct != null && <span className="text-muted-foreground/40"> · </span>}
                        {sizingPct != null && (
                          <span className="text-foreground/80"><span className="font-bold tabular-nums">{sizingPct}%</span> <span className="text-muted-foreground/70">{t("card.ofPot")}</span></span>
                        )}
                      </span>
                    </div>
                  )}
                </div>
              );
            })()}
            {showAuditPreflop && (
              <>
                <div className="flex flex-wrap gap-1 items-center">
                  <span className="rounded-md bg-background/60 ring-1 ring-border/50 px-2 py-1 font-mono text-[10px]">
                    <span className="text-muted-foreground mr-1">{t("card.indScenario")}</span>
                    <span className="text-foreground font-bold">{scenarioLabel[pg!.scenario] ?? pg!.scenario}</span>
                  </span>
                  <span className="text-muted-foreground/60 text-[10px]">›</span>
                  <span className={cn(
                    "rounded-md ring-1 px-2 py-1 font-mono text-[10px]",
                    pg!.in_range ? "bg-emerald-500/8 ring-emerald-500/30" : "bg-red-500/8 ring-red-500/30"
                  )} title={t("card.handRangeTip")}>
                    <span className="text-muted-foreground mr-1">{t("card.indHand")}</span>
                    <span className={cn("font-bold", pg!.in_range ? "text-emerald-400" : "text-red-400")}>
                      {pg!.hand_type}
                    </span>
                    {/* ✓/✗ é sobre estar NO RANGE (não sobre a ação — isso é o veredito acima).
                        Rótulo de texto + tooltip pra não confundir verde com "correto". */}
                    <span className={cn("ml-1", pg!.in_range ? "text-emerald-400/80" : "text-red-400/80")}>
                      · {pg!.in_range ? t("card.handInRangeTag") : t("card.handOutRangeTag")}
                    </span>
                  </span>
                </div>
                {pg!.limp_dead_money && (
                  <div className="font-mono text-[10px] text-amber-300/80" title={t("card.limpDeadMoneyTip")}>
                    {t("card.limpDeadMoney")}
                  </div>
                )}
                {hasFreqs && (
                  <div className="space-y-1">
                    {(() => {
                      const isRFI = pg!.scenario === 'rfi';
                      const validVs = pg!.vs_position && pg!.vs_position !== 'UNKNOWN' ? pg!.vs_position : null;
                      // Depth de referência: o GTO resolve em depths discretos (10/14/.../50/75/100bb).
                      // Quando o bucket diverge do stack real, prefixa "≈" pra não parecer erro
                      // (ex.: stack 61,9bb → solver usa o depth resolvido mais próximo, ≈50bb).
                      const bucketNum = parseFloat(pg!.stack_bucket);
                      const stackRef = (!isNaN(bucketNum) && Math.abs(bucketNum - pg!.stack_bb) > 2)
                        ? `≈${pg!.stack_bucket}` : pg!.stack_bucket;
                      // Contexto: RFI mostra "abrindo"; vs_RFI/3bet/etc mostra "vs OPENER"
                      const ctxStr = isRFI
                        ? t("card.ctxOpening", { position: pg!.position, stack: stackRef })
                        : (validVs ? t("card.ctxVs", { vs: validVs, stack: stackRef })
                                   : t("card.ctxPlain", { position: pg!.position, stack: stackRef }));
                      const title = useHandFreq
                        ? t("card.freqTitleHand", { hand: pg!.hand_type, ctx: ctxStr })
                        : t("card.freqTitleAggr", { ctx: ctxStr });
                      const display = useHandFreq
                        ? t("card.freqDisplayHand", { hand: pg!.hand_type, ctx: ctxStr })
                        : t("card.freqDisplayAggr", { ctx: ctxStr });
                      return (
                        <div className="font-mono text-[9px] uppercase tracking-wide text-muted-foreground" title={title}>
                          {display}
                        </div>
                      );
                    })()}
                    {/* Uma barra independente por ação — facilita leitura visual
                        de cada %, em vez de uma stacked bar com cores coladas. */}
                    {(() => {
                      const rows: { key: string; label: string; pct: number; color: string }[] = [];
                      if (foldPct  > 0.001) rows.push({ key: 'fold',  label: 'Fold',  pct: foldPct,  color: ACTION_COLORS.fold  });
                      if (callPct  > 0.001) rows.push({ key: 'call',  label: 'Call',  pct: callPct,  color: ACTION_COLORS.call  });
                      if (raisePct > 0.001) rows.push({ key: 'raise', label: 'Raise', pct: raisePct, color: ACTION_COLORS.raise });
                      if (allinPct > 0.001) rows.push({ key: 'allin', label: 'Allin', pct: allinPct, color: ACTION_COLORS.allin });
                      rows.sort((a, b) => b.pct - a.pct);
                      return (
                        <div className="space-y-1">
                          {rows.map((r) => (
                            <div key={r.key} className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 rounded-full bg-muted/20 overflow-hidden">
                                <div className="h-full rounded-full transition-all"
                                     style={{ width: `${r.pct*100}%`, background: r.color }} />
                              </div>
                              <span className="font-mono text-[10px] shrink-0 w-10" style={{ color: r.color }}>
                                {r.label}
                              </span>
                              <span className="font-mono text-[10px] shrink-0 w-10 text-right text-foreground">
                                {(r.pct*100).toFixed(1)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      );
                    })()}
                  </div>
                )}
              </>
            )}
            {!isPostflop && pg && !pg.available && pg.coverage_reason === 'limped_pot' && (
              <div className="flex flex-wrap gap-1 items-center" title={t("card.limpedPotTip")}>
                <span className="rounded-md bg-muted/30 ring-1 ring-border/50 px-2 py-1 font-mono text-[10px] text-muted-foreground">
                  {t("card.limpedPot", { pos: pg.position })}
                </span>
              </div>
            )}
            {/* SPR/Sizing/Equity/Mín.EV de postflop migraram pro bloco de 3 (acima).
                Aqui ficam só os de PREFLOP (gated !isPostflop). */}
            {!isPostflop && eq != null && (
              <div className="flex items-center gap-2 font-mono text-[11px] flex-wrap"
                title={showAuditPreflop ? (isVsRange ? t("card.reqVsRangeTip") : t("card.reqVsRandomTip")) : t("card.equityTip")}>
                <span className="w-14 shrink-0 text-muted-foreground uppercase text-[10px]">Equity</span>
                <span className={cn(
                  "font-bold tabular-nums",
                  eq >= 0.65 ? "text-emerald-400" :
                  eq >= 0.50 ? "text-foreground" :
                  eq >= 0.35 ? "text-amber-400" : "text-red-400"
                )}>{(eq * 100).toFixed(1)}%</span>
                <span className="text-muted-foreground text-[10px] whitespace-nowrap">
                  {eq >= 0.65 ? t("card.eqStrong") : eq >= 0.50 ? t("card.eqFavorable") : eq >= 0.35 ? t("card.eqMarginal") : t("card.eqWeak")}
                  {(showAuditPreflop || isShoveFb) && <span className="text-muted-foreground/60"> · {isVsRange ? t("card.vsRange") : t("card.vsRandom")}</span>}
                </span>
              </div>
            )}
            {!isPostflop && ((req != null && req > 0) || reqImplicit != null) && (() => {
              const reqShown = (req != null && req > 0) ? req : reqImplicit!;
              const isImplicit = !(req != null && req > 0);
              const tooltip = isImplicit
                ? t("card.reqTipImplicit")
                : requiredIsAdjusted
                  ? t("card.reqTipAdjusted", { potOdds: (poRaw! * 100).toFixed(1) })
                  : t("card.reqTipRaw");
              const label = isImplicit ? t("card.reqMinEv") : t("card.reqNeeded");
              // Quando o veredito vem do SOLVER (range preflop OU estratégia postflop),
              // a conta simples equity×necessária NÃO é o veredito — e pode contradizê-lo:
              // ex.: "DESVIO CRÍTICO" ao apostar com 62% de equity, porque o solver dá
              // check 100% (range / ruas futuras). Verde/vermelho ali pareceria que a
              // ação foi +EV. Neutraliza o +pp (cinza) + tooltip contextual. Cor só fica
              // quando pot odds É a base do veredito (postflop sem solver, vs_shove).
              // Também neutraliza quando a margem ficaria VERDE (eq ≥ necessária) mas o
              // veredito diz que a ação foi ERRO (ex.: heurística "RAISE +EV vs fold"
              // num spot que o engine manda CALL) — senão o +pp verde contradiz o "ERRO".
              const ppMuted = isPpMuted({ showAuditPreflop: !!showAuditPreflop, effectiveGtoLabel, eq, reqShown, isActionOk });
              // A linha de equity NECESSÁRIA explica a equity necessária / margem — NÃO
              // reusa reqVsRandom/Range (que descrevem a equity ESTIMADA, já na linha acima).
              // Antes, em modo audit ambas as linhas mostravam o MESMO texto (vs random/range).
              const ppTip = effectiveGtoLabel ? t("card.reqSolverContextTip") : tooltip;
              return (
                <div className="flex items-center gap-2 font-mono text-[11px]"
                  title={ppTip}>
                  <span className="w-14 shrink-0 text-muted-foreground uppercase text-[10px]">{label}</span>
                  <span className="font-bold tabular-nums text-foreground/80">{(reqShown * 100).toFixed(1)}%</span>
                  {eq != null && (
                    <span className={cn(
                      "text-[10px]",
                      ppMuted ? "text-muted-foreground/50"
                        : eq >= reqShown ? "text-emerald-400" : "text-red-400"
                    )}>
                      {eq >= reqShown ? `+${((eq - reqShown) * 100).toFixed(1)}pp` : `${((eq - reqShown) * 100).toFixed(1)}pp`}
                    </span>
                  )}
                </div>
              );
            })()}
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

        const hasIndicators = showAuditPreflop || isMultiway ||
                              (isPostflop && (spr != null || sizingPct != null)) ||
                              eq != null || (req != null && req > 0) || reqImplicit != null;

        // #23: ressalva de open off-tree — o vilão abriu maior que o GTO, então a
        // range de defesa mostrada (vs open mínimo) é mais larga que a correta.
        const osm = !isPostflop ? pg?.open_size_mismatch : null;
        const whyFull = osm
          ? `${why ? why + " " : ""}${t("card.openOversizeCaveat", { facing: osm.facing_bb, canonical: osm.canonical_bb })}`
          : why;

        const CardImpl = DecisionCard;   // layout clássico fixo (sem toggle de v2)
        return (
          <>
          <CardImpl
            verdict={verdict}
            source={{
              label: SOURCE_LABEL[sourceVariant],
              tooltip: SOURCE_TOOLTIP[sourceVariant],
              variant: sourceVariant,
            }}
            playedAction={playedAction}
            idealAction={idealAction}
            idealLabel={hasGto ? t("card.gtoRecommends") : t("card.recommended")}
            isActionOk={isActionOk}
            evidence={evidence}
            indicators={hasIndicators ? indicators : undefined}
            why={whyFull}
            proNotes={proNotes}
            footer={{
              stackBb: step.hero_stack_bb,
              mRatio: step.m_ratio,
              icmPressure: step.icm_pressure,
              icmTaxPct: step.icm_tax_pct,
            }}
            icmBadge={(() => {
              // Mesa final: badge direcional pelo sinal contínuo do ICM (calculate_icm).
              // |tax| ≥ 5pp = direção clara; entre −5 e 5 = neutro. None fora da FT.
              const tax = step.icm_tax_pct;
              if (tax == null) return null;
              const tone = tax >= 5 ? "risk" : tax <= -5 ? "survival" : "neutral";
              return {
                tone,
                label: t(`icm.${tone}Label`),
                tooltip: t(`icm.${tone}Tip`),
              };
            })()}
            showDetails={showDetails}
            onToggleDetails={toggleDetails}
            verdictTooltip={effectiveGtoLabel ? GTO_LABEL_TOOLTIP[effectiveGtoLabel] : undefined}
            evLossBb={step.ev_loss_bb}
            fmtAction={fmtAction}
          />
          </>
        );
      })()}


      {/* ── Cobertura GTO postflop ──────────────────────────────────────
          Spots que o solver heads-up NÃO cobre (multiway, deep>60bb, hero IP
          enfrentando aposta, sem vilão) mostram uma nota HONESTA estática, não
          "Processando" (que sugere que vai resolver) nem auto-solve inútil.
          Só 'pending' (solvável, nó ainda não existe) mostra o fluxo de solve. */}
      {step.is_hero && step.type === "action" && isPostflop && !hasGto && !isMultiwayStep
        && step.action !== "shows" && step.action !== "mucks"
        && (() => {
          const cov = (step as { gto_coverage?: string }).gto_coverage;
          if (cov && ["multiway", "deep", "ip_facing_bet", "no_villain"].includes(cov)) {
            return (
              <section className="rounded-xl border border-border/60 bg-hud-surface p-3">
                <div className="flex items-start gap-2">
                  <Info className="size-3.5 text-muted-foreground/70 shrink-0 mt-px" />
                  <div className="space-y-0.5">
                    <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70">
                      {t("card.noCoverageTitle")}
                    </p>
                    <p className="text-[11px] text-muted-foreground/85 leading-relaxed">
                      {t(`card.noCoverage.${cov}`)}
                    </p>
                  </div>
                </div>
              </section>
            );
          }
          return (
        <section className="rounded-xl border border-border bg-hud-surface p-3 space-y-2.5">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-4 shrink-0 text-muted-foreground" />
            <span className="font-mono text-[10px] font-bold uppercase tracking-widest-2 text-muted-foreground flex-1">
              {t("card.gtoSectionTitle")}
            </span>
            <span className="font-mono text-[9px] text-muted-foreground/60 uppercase">{t("card.processing")}</span>
          </div>
          {(gtoRequestStatus === "idle" || gtoRequestStatus === "requesting") && (
            <div className="flex items-center gap-2 rounded-lg bg-sky-500/5 border border-sky-500/20 px-2.5 py-2">
              <Loader2 className="size-3.5 text-sky-400 shrink-0 animate-spin" />
              <p className="text-[11px] text-sky-400">
                {t("card.statusRequesting")}
              </p>
            </div>
          )}
          {gtoRequestStatus === "queued" && (
            <div className="flex items-center gap-2 rounded-lg bg-sky-500/5 border border-sky-500/20 px-2.5 py-2">
              <Loader2 className="size-3.5 text-sky-400 shrink-0 animate-spin" />
              <p className="text-[11px] text-sky-400">
                {t("card.statusQueued")}
              </p>
            </div>
          )}
          {gtoRequestStatus === "solver_queued" && (
            <div className="flex items-start gap-2 rounded-lg bg-amber-500/5 border border-amber-500/20 px-2.5 py-2">
              <Loader2 className="size-3.5 text-amber-400 shrink-0 mt-px animate-spin" />
              <p className="text-[11px] text-amber-400 leading-relaxed">
                {t("card.statusSolverQueued")}
              </p>
            </div>
          )}
          {gtoRequestStatus === "done" && hasGto && (
            <div className="flex items-center gap-2 rounded-lg bg-emerald-500/5 border border-emerald-500/20 px-2.5 py-2">
              <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" />
              <p className="text-[11px] text-emerald-400">
                {t("card.statusDoneLoaded")}
              </p>
            </div>
          )}
          {gtoRequestStatus === "done" && !hasGto && (
            <div className="flex items-start gap-2 rounded-lg bg-muted/30 border border-border/60 px-2.5 py-2">
              <Info className="size-3.5 text-muted-foreground shrink-0 mt-px" />
              <p className="text-[11px] text-muted-foreground/85 leading-relaxed">
                {t("card.statusDoneNoSolution")}
              </p>
            </div>
          )}
          {gtoRequestStatus === "error" && (
            <div className="flex items-center gap-2 rounded-lg bg-destructive/5 border border-destructive/20 px-2.5 py-2">
              <AlertOctagon className="size-3.5 text-destructive shrink-0" />
              <p className="text-[11px] text-destructive">{t("card.statusError")}</p>
            </div>
          )}
          {/* #26 — cota de solves estourada: upsell, não erro */}
          {gtoRequestStatus === "quota_exceeded" && (
            <div className="flex items-start gap-2 rounded-lg bg-amber-500/5 border border-amber-500/20 px-2.5 py-2">
              <Lock className="size-3.5 text-amber-400 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="text-[11px] font-semibold text-amber-300">{t("card.quotaExceeded")}</p>
                <p className="text-[10px] text-amber-300/70">{t("card.quotaUpgradeHint")}</p>
              </div>
            </div>
          )}
        </section>
          );
        })()}


      {/* ── Coach annotation (coach editing student hand) ── */}
      {studentId && step?.is_hero && currentDecisionId && (
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
              {coachAnnotation.coach_action && <p className="font-mono text-[11px] text-primary">→ {t("card.coachCorrect")}: {coachAnnotation.coach_action}</p>}
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
                    {/* FEAT-20: veredito do coach em 3 níveis (Erro → clear_mistake interno). */}
                    <option value="">{t("annotation.noVerdict")}</option>
                    <option value="standard">{t("card.vCorrect")}</option>
                    <option value="marginal">{t("card.vAcceptable")}</option>
                    <option value="clear_mistake">{t("card.vError")}</option>
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

// Module-scoped cache de replays (sobrevive re-renders). Chave: `t|h|student?`.
// TTL 5 min — alinhado com backend cache. Permite prefetch da próxima mão em
// background pra navegação fluida durante review de torneio.
type ReplayCacheEntry = { ts: number; data: ReplayData };
const REPLAY_CACHE = new Map<string, ReplayCacheEntry>();
const REPLAY_CACHE_TTL = 5 * 60 * 1000;
const REPLAY_CACHE_MAX = 64;

function replayCacheKey(t: string, h: string, student: number | null): string {
  return `${t}|${h}|${student ?? ""}`;
}

function replayCacheGet(key: string): ReplayData | null {
  const e = REPLAY_CACHE.get(key);
  if (!e) return null;
  if (Date.now() - e.ts > REPLAY_CACHE_TTL) {
    REPLAY_CACHE.delete(key);
    return null;
  }
  return e.data;
}

function replayCacheSet(key: string, data: ReplayData) {
  if (REPLAY_CACHE.size >= REPLAY_CACHE_MAX) {
    // Evict mais antigo
    let oldestKey: string | null = null;
    let oldestTs = Infinity;
    REPLAY_CACHE.forEach((v, k) => { if (v.ts < oldestTs) { oldestTs = v.ts; oldestKey = k; } });
    if (oldestKey) REPLAY_CACHE.delete(oldestKey);
  }
  REPLAY_CACHE.set(key, { ts: Date.now(), data });
}

const Replayer = () => {
  const [params]   = useSearchParams();
  const navigate   = useNavigate();
  const { t } = useTranslation("replayer");
  const tableOrientation = useTableOrientation();
  const landscapeMobile = useIsLandscapeMobile();
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
  const [showAnalysis, setShowAnalysis] = useState(false);   // mobile: bottom-sheet do card de análise
  const [showHud, setShowHud]       = useState<boolean>(
    () => localStorage.getItem('replayer_show_hud') !== 'false'   // HUD HM-style: ligado por padrão
  );
  // Tooltip completo do HUD (hover) por jogador — todas as stats rotuladas. Termos de
  // poker (VPIP/PFR/3-bet/c-bet/AF/WTSD) não se traduzem; só os conectivos são i18n.
  const hudTips = useMemo<Record<string, string>>(() => {
    const profs = replayData?.opponent_profiles ?? {};
    const pp = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)}%`);
    const out: Record<string, string> = {};
    for (const [name, p] of Object.entries(profs)) {
      const s = p.stats ?? {};
      const af = s.af == null ? "–" : (typeof s.af === "number" ? s.af.toFixed(1) : String(s.af));
      const low = p.confidence === "insufficient" || p.archetype === "unknown";
      const arch = low ? t("card.villainSampleLow") : t(`card.archetype.${p.archetype}`, p.archetype);
      out[name] =
        `${name} · ${arch} · ${p.hands} ${t("hudHands")}\n` +
        `VPIP ${pp(s.vpip_pct)}   PFR ${pp(s.pfr_pct)}   3-bet ${pp(s.threebet_pct)}\n` +
        `c-bet ${pp(s.cbet_pct)}   fold→c-bet ${pp(s.foldcbet_pct)}\n` +
        `AF ${af}   WTSD ${pp(s.wtsd_pct)}`;
    }
    return out;
  }, [replayData?.opponent_profiles, t]);
  const [decisions, setDecisions]   = useState<TournamentDecision[]>([]);
  const [showRange, setShowRange]           = useState(false);
  const [annotating, setAnnotating]         = useState(false);
  const [annComment, setAnnComment]         = useState("");
  const [annMode, setAnnMode]               = useState<"complement" | "replace">("complement");
  const [annAction, setAnnAction]           = useState("");
  const [annOverride, setAnnOverride]       = useState<CoachOverrideLabel>(null);
  const [gtoRequestStatus, setGtoRequestStatus] = useState<"idle" | "requesting" | "queued" | "solver_queued" | "done" | "error" | "quota_exceeded">("idle");
  // Track which hand_id we already auto-requested so we don't spam on step navigation
  const gtoAutoRequestedRef = useRef<string | null>(null);

  // Modo foco / tela cheia (#replayer) — coach revisa o torneio sem o chrome do app.
  // Mantém mesa, controles e o painel de decisão; some o HudHeader (nav/upload/etc).
  const rootRef = useRef<HTMLDivElement>(null);
  const [focusMode, setFocusMode] = useState(false);
  const enterFocus = () => {
    setFocusMode(true);
    rootRef.current?.requestFullscreen?.().catch(() => {}); // degrada p/ modo foco CSS se negado
  };
  const exitFocus = () => {
    setFocusMode(false);
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  };
  // Sai do modo foco quando o usuário deixa o fullscreen nativo (ex.: tecla ESC).
  useEffect(() => {
    const onFsChange = () => { if (!document.fullscreenElement) setFocusMode(false); };
    document.addEventListener("fullscreenchange", onFsChange);
    return () => document.removeEventListener("fullscreenchange", onFsChange);
  }, []);

  // Floating Range panel drag state
  const [rangePos, setRangePos]         = useState({ x: 24, y: 96 });
  const isDraggingRange                 = useRef(false);
  const rangeDragStart                  = useRef({ mouseX: 0, mouseY: 0, panelX: 0, panelY: 0 });

  useEffect(() => {
    if (!tournamentId || !handId) return;
    setError("");
    setStepIdx(0);
    setPlaying(false);
    setGtoRequestStatus("idle");

    // Cache hit local: zero latência percebida
    const cacheKey = replayCacheKey(tournamentId, handId, studentId);
    const cached = replayCacheGet(cacheKey);
    if (cached) {
      setReplayData(cached);
      setLoading(false);
      // Ainda precisa do tournament data se nao tem (primeiro load)
      if (handList.length === 0) {
        const tournamentFn = studentId
          ? coachDashboard.studentTournament(studentId, tournamentId)
              .then((r) => ({ decisions: r.decisions }))
              .catch(() => null)
          : tournamentsApi.get(tournamentId).catch(() => null);
        tournamentFn.then((tournamentData) => {
          if (tournamentData) {
            const seen = new Set<string>();
            const ids: string[] = [];
            tournamentData.decisions.forEach((d) => {
              if (d.hand_id && !seen.has(d.hand_id)) { seen.add(d.hand_id); ids.push(d.hand_id); }
            });
            setHandList(ids);
            setDecisions(tournamentData.decisions);
          }
        });
      }
      return;
    }

    setLoading(true);
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
        replayCacheSet(cacheKey, replay);
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

  // Prefetch das mãos adjacentes (próxima + anterior) em background.
  // Dispara quando handList chega; cada uma só se ainda não está no cache.
  useEffect(() => {
    if (!tournamentId || handList.length === 0) return;
    const idx = handList.indexOf(handId);
    if (idx < 0) return;
    const toPrefetch: string[] = [];
    if (idx + 1 < handList.length) toPrefetch.push(handList[idx + 1]);
    if (idx - 1 >= 0)               toPrefetch.push(handList[idx - 1]);
    toPrefetch.forEach((h) => {
      const k = replayCacheKey(tournamentId, h, studentId);
      if (replayCacheGet(k)) return;
      const fn = studentId
        ? coachDashboard.studentReplay(studentId, tournamentId, h)
        : tournamentsApi.replay(tournamentId, h);
      fn.then((replay) => replayCacheSet(k, replay)).catch(() => {});
    });
  }, [tournamentId, handId, studentId, handList]);

  const steps = replayData?.timeline ?? [];
  const step  = steps[stepIdx] as ReplayStep | undefined;

  // Hand navigation
  const handIdx  = handList.indexOf(handId);
  const prevHand = handIdx > 0 ? handList[handIdx - 1] : null;
  const nextHand = handIdx >= 0 && handIdx < handList.length - 1 ? handList[handIdx + 1] : null;

  // Alias map: todos os jogadores com nomes reais
  const playerAliases = useMemo<Record<string, string>>(() => {
    if (!replayData?.seats) return {};
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
    // Anotações disponíveis em QUALQUER spot do hero — não só nos erros. O coach
    // pode comentar uma jogada correta/marginal também (reforço, contexto, leak fino).
    if (!annotations) return null;
    return Object.values(annotations).find(
      (a) => a.street === step?.street && a.action_taken === step?.action
    ) ?? null;
  }, [replayData?.coach_annotations, step?.street, step?.action]);

  // decision_id for annotation save/delete (coaches only) — todo spot do hero, não só erro
  const currentDecisionId = useMemo(() => {
    if (!studentId || !step?.is_hero) return null;
    if (coachAnnotation) return coachAnnotation.decision_id;
    return decisions.find(
      (d) => d.hand_id === handId && d.street === step.street && d.action_taken === step.action
    )?.id ?? null;
  }, [studentId, step?.is_hero, step?.street, step?.action, coachAnnotation, decisions, handId]);

  const saveAnn = useMutation({
    mutationFn: () => coachDashboard.upsertAnnotation(studentId!, {
      decision_id: currentDecisionId!,
      comment: annComment,
      mode: annMode,
      coach_action: annAction || undefined,
      coach_override_label: annOverride,
    }),
    onSuccess: (saved: CoachAnnotation) => {
      // A resposta da API NÃO traz street/action_taken (são da tabela decisions, não da
      // anotação); o match do card é por (street, action). Sem isso, a anotação recém-salva
      // "sumia" até o refresh (que re-busca com esses campos). Injeta os do step atual.
      const enriched = { ...saved, street: step?.street, action_taken: step?.action };
      setReplayData((prev) => prev ? {
        ...prev,
        coach_annotations: { ...prev.coach_annotations, [String(saved.decision_id)]: enriched },
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
      // #26 — cota de solves estourada (402) → upsell, não erro genérico
      if (err instanceof Error && err.message === "solve_quota_exceeded") {
        setGtoRequestStatus("quota_exceeded");
      } else {
        setGtoRequestStatus("error");
      }
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
    // Só auto-solva spots SOLVÁVEIS sem nó ainda ('pending'). Multiway, deep>60bb,
    // hero IP enfrentando aposta e sem-vilão são heurísticos por design (o solver é
    // heads-up) — nunca terão cobertura, então não dispara requisição inútil.
    const hasPostflopHeroNoGto = steps.some(s => {
      const cov = (s as { gto_coverage?: string }).gto_coverage;
      return s.is_hero && s.type === "action" && s.street !== "preflop" && !s.gto_label &&
        s.action !== "shows" && s.action !== "mucks" &&
        (cov === "pending" || cov === undefined);
    });
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

  // ── Celular DEITADO: mesa FULLSCREEN edge-to-edge + controles/logo/pill flutuando ──
  if (landscapeMobile) {
    return (
      <div ref={rootRef} className="h-dvh relative overflow-hidden hud-scanline"
        style={{ background: "radial-gradient(ellipse at 50% 45%, #14223a 0%, #080f1c 100%)" }}>
        {/* Mesa (dimensões boas, height-bound, sem cortar pods) com fundo TRANSPARENTE: o
            gradiente acima é único na tela → sem caixa/borda dando impressão de sobreposição. */}
        <div className="absolute inset-0 flex items-center justify-center p-0.5">
          <div className="h-full w-auto max-w-full mx-auto" style={{ aspectRatio: "1160 / 710" }}>
            <PokerTableV3
              step={step} hero={replayData.hero} heroCards={replayData.hero_cards}
              bb={replayData.bb} betUnit={betUnit} playerAliases={playerAliases}
              revealedCards={revealedCards} profiles={replayData.opponent_profiles}
              showHud={showHud} hudTips={hudTips} orientation="landscape" fill
            />
          </div>
        </div>

        {/* Voltar — topo-esquerda */}
        <button onClick={() => navigate(-1)}
          className="absolute top-2 left-2 z-30 inline-flex items-center gap-1.5 rounded-full bg-background/70 backdrop-blur px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest-2 text-muted-foreground ring-1 ring-border transition-colors hover:text-primary">
          <ArrowLeft className="size-3.5" /> {t("back")}
        </button>

        {/* Logo GrindLab + contador de mão — topo-direita */}
        <div className="absolute top-2 right-2 z-30 flex items-center gap-2.5 rounded-full bg-background/70 backdrop-blur px-3 py-1.5 ring-1 ring-border">
          {handList.length > 1 && handIdx >= 0 && (
            <span className="font-mono text-[10px] text-muted-foreground tabular-nums">{handIdx + 1}/{handList.length}</span>
          )}
          <img src={logoHorizontal} alt="GrindLab" className="h-5 w-auto" />
        </div>

        {/* Verdict pill / Análise — canto inferior-direito */}
        <div className="absolute bottom-2 right-2 z-30">
          <VerdictPill
            level={verdictLevel(step.error_label) ?? (step.is_hero && step.type === "action" ? ((isError ? "error" : isCorrect ? "correct" : null) as VerdictLevel | null) : null)}
            evLossBb={step.ev_loss_bb}
            onClick={() => setShowAnalysis(true)}
          />
        </div>

        {/* Controles — extrema inferior-esquerda */}
        <div className="absolute bottom-2 left-2 z-30 flex items-center gap-1 rounded-full bg-background/80 backdrop-blur px-2 py-1 ring-1 ring-border shadow-lg">
          <button onClick={() => { if (stepIdx > 0) setStepIdx(0); else if (prevHand) navigate(`/replayer?t=${tournamentId}&h=${prevHand}${studentId ? `&student=${studentId}` : ""}`); }}
            disabled={stepIdx === 0 && !prevHand}
            className="inline-flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"><Rewind className="size-4" /></button>
          <button onClick={() => setStepIdx((i) => Math.max(0, i - 1))} disabled={stepIdx === 0}
            className="inline-flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"><ChevronLeft className="size-5" /></button>
          <button onClick={() => setPlaying((p) => !p)}
            className="inline-flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary-glow">
            {playing ? <Pause className="size-4" /> : <Play className="size-4" />}</button>
          <button onClick={() => setStepIdx((i) => Math.min(steps.length - 1, i + 1))} disabled={stepIdx === steps.length - 1}
            className="inline-flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"><ChevronRight className="size-5" /></button>
          <button onClick={() => { if (stepIdx < steps.length - 1) setStepIdx(steps.length - 1); else if (nextHand) navigate(`/replayer?t=${tournamentId}&h=${nextHand}${studentId ? `&student=${studentId}` : ""}`); }}
            disabled={stepIdx === steps.length - 1 && !nextHand}
            className="inline-flex size-9 items-center justify-center rounded-full text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-30"><FastForward className="size-4" /></button>
          <span className="px-1.5 font-mono text-[10px] text-muted-foreground tabular-nums">{stepIdx + 1}/{steps.length}</span>
        </div>

        {/* Sheet de análise (on-demand, tap na pill) */}
        {showAnalysis && (
          <div className="fixed inset-0 z-50 flex flex-col justify-end">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowAnalysis(false)} />
            <div className="relative max-h-[90vh] overflow-y-auto rounded-t-2xl bg-background p-3 pb-6 shadow-2xl ring-1 ring-border">
              <button onClick={() => setShowAnalysis(false)} aria-label={t("close")}
                className="absolute right-2.5 top-2.5 z-10 rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"><X className="size-4" /></button>
              <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border" onClick={() => setShowAnalysis(false)} />
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
        )}
      </div>
    );
  }

  return (
    <div ref={rootRef} className="h-dvh flex flex-col overflow-hidden bg-background hud-scanline">
      {!focusMode && <HudHeader />}

      {/* ── Outer wrapper: top-bar + [table | side-panel] + controls ── */}
      <div className={cn(
        "flex-1 min-h-0 flex flex-col px-3 md:px-5 pt-2 pb-20 md:pb-2 mx-auto w-full",
        focusMode ? "max-w-none" : "max-w-[1600px]",
      )}>

        {/* Top bar */}
        <div className="shrink-0 grid grid-cols-3 items-center mb-2">
          <div className="flex items-center gap-3 min-w-0">
            {/* Logo GrindLab — presença de marca no modo foco (HudHeader fica oculto) */}
            {focusMode && (
              <img src={logoHorizontal} alt="GrindLab" className="h-7 w-auto shrink-0" />
            )}
            <button
              onClick={() => navigate(-1)}
              className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest-2 text-muted-foreground transition-colors hover:text-primary"
            >
              <ArrowLeft className="size-3.5" /> {t("back")}
            </button>
          </div>

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

          <div className="flex items-center justify-end gap-2">
            {replayData?.is_pko && (
              <span
                className="inline-flex items-center rounded-md bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider ring-1 ring-amber-500/30 text-amber-300"
                title="Progressive Knockout (PKO), torneio com bounties. Ranges e thresholds GTO específicos podem divergir do MTT clássico."
              >
                PKO
              </span>
            )}
            <button
              onClick={focusMode ? exitFocus : enterFocus}
              aria-label={focusMode ? t("focus.exit") : t("focus.enter")}
              title={focusMode ? t("focus.exit") : t("focus.enter")}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {focusMode ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
              <span className="hidden sm:inline">{focusMode ? t("focus.exit") : t("focus.enter")}</span>
            </button>
          </div>
        </div>

        {/* ── Main row: table (flex-1) + side panel (w-72, desktop only) ── */}
        {/* Mobile: 3 faixas em h-dvh sem scroll (mesa flex-1); desktop: row de altura fixa */}
        <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-3">

          {/* Table column */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col gap-2">
            {/* Mesa — height-bound: cabe SEMPRE na faixa flex-1 (acima dos controles), nunca
                rola pra baixo do menu. Aspect troca por orientação (portrait vertical). */}
            <div className="flex-1 min-h-0 overflow-hidden flex items-center justify-center">
              <div
                className="h-full w-auto max-w-full max-h-full mx-auto"
                style={{ aspectRatio: tableOrientation === "portrait" ? "728 / 932" : "16 / 10" }}
              >
                <PokerTableV3
                  step={step}
                  hero={replayData.hero}
                  heroCards={replayData.hero_cards}
                  bb={replayData.bb}
                  betUnit={betUnit}
                  playerAliases={playerAliases}
                  revealedCards={revealedCards}
                  profiles={replayData.opponent_profiles}
                  showHud={showHud}
                  hudTips={hudTips}
                  orientation={tableOrientation}
                />
              </div>
            </div>

            {/* Mobile: barra de veredito (3 níveis, fonte única VERDICT_META) que abre o sheet de análise */}
            <VerdictPill
              level={
                verdictLevel(step.error_label)
                ?? (step.is_hero && step.type === "action"
                      ? (isError ? "error" : isCorrect ? "correct" : null) as VerdictLevel | null
                      : null)
              }
              evLossBb={step.ev_loss_bb}
              onClick={() => setShowAnalysis(true)}
            />

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
                {/* HUD HM-style: liga/desliga os boxes de stats dos vilões na mesa.
                    Só aparece quando há perfis (torneio com nomes reais rastreados). */}
                {replayData.opponent_profiles && Object.keys(replayData.opponent_profiles).length > 0 && (
                  <button
                    onClick={() => setShowHud(v => { const n = !v; localStorage.setItem('replayer_show_hud', String(n)); return n; })}
                    title={t("hudToggleTip")}
                    className={cn(
                      "flex items-center gap-1 rounded-sm px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors ring-1 focus-visible:outline-none",
                      showHud ? "bg-primary/15 text-primary ring-primary/30" : "text-muted-foreground ring-border hover:text-foreground"
                    )}>
                    <Users className="size-3" /> HUD
                  </button>
                )}
              </div>
            </div>

            {/* Mobile: card de análise como bottom-sheet sobreposto (página não rola) */}
            {showAnalysis && (
              <div className="lg:hidden fixed inset-0 z-50 flex flex-col justify-end">
                <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowAnalysis(false)} />
                <div className="relative max-h-[82vh] overflow-y-auto rounded-t-2xl bg-background p-3 pb-6 shadow-2xl ring-1 ring-border">
                  <button
                    onClick={() => setShowAnalysis(false)}
                    aria-label={t("close")}
                    className="absolute right-2.5 top-2.5 z-10 rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                  >
                    <X className="size-4" />
                  </button>
                  <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border" onClick={() => setShowAnalysis(false)} />
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
            )}
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
