import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, type UseMutationResult } from "@tanstack/react-query";
import { AlertOctagon, Check, CheckCircle2, FlaskConical, GraduationCap, Info, Loader2, Lock, PenLine, Sparkles, Trash2, X } from "lucide-react";
import { GtoStrategyPanel } from "@/components/replayer/GtoStrategyPanel";
import { DecisionCard, type DecisionSourceVariant } from "@/components/replayer/DecisionCard";
import { DecisionCardV2 } from "@/components/replayer/DecisionCardV2";
import { metricasDoCard } from "@/lib/cardV2Metricas";
import { PlayingCard } from "@/components/hud/PlayingCard";
import { parseCards, fmtAction } from "@/components/replayer/replayerFormat";
import { cn } from "@/lib/utils";
import { computeEffectiveGtoLabel } from "@/lib/gtoUtils";
import { livePlayers as computeLivePlayers, isMultiwayPot, isPpMuted, idealActionSource, verdictStrategy, verdictLevel, clampVerdict, equityLowConfidence, EQUITY_GAP_P90, qualificadorDeCusto, mostraQualidadeEstatica } from "@/lib/cardLogic";
import { leituraDaIniciativa, selectWhy } from "@/lib/replayWhy";
import { ACTION_COLORS } from "@/lib/actionColors";
import { coachDashboard, ReplayData, ReplayStep, CoachAnnotation, CoachOverrideLabel } from "@/lib/api";

/**
 * Painel de ANÁLISE de uma decisão: Decision Card (veredito, ação, evidência, rodapé),
 * cobertura GTO, anotação do coach e showdown.
 *
 * Ele morava dentro de `pages/Replayer.tsx`. Saiu de lá inteiro, sem uma linha reescrita, porque
 * o exemplo de análise mostrado a quem ainda não subiu arquivo nenhum precisa ser renderizado
 * pelo MESMO componente que renderiza a análise de verdade. O exemplo anterior era um card
 * escrito à mão: quem o via não via o produto, via uma maquete dele — e uma vitrine copiada
 * envelhece em silêncio, que é o padrão que este projeto já pagou caro para aprender.
 *
 * A composição depende quase só do `step`. As props de coach (`studentId`, `coachAnnotation`,
 * as mutations) governam apenas os blocos de anotação, que ficam ocultos sem elas.
 */
export interface SidePanelsProps {
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
  saveAnn: UseMutationResult<CoachAnnotation, Error, void>;
  deleteAnn: UseMutationResult<{ ok: boolean }, Error, void>;
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
  /** Layout enxuto p/ bottom-sheet mobile (sem scroll; 2 colunas em landscape). Default false = desktop intocado. */
  compact?: boolean;
  /** Padrão do layout v2 quando o navegador NÃO tem preferência salva. A vitrine da landing
   *  passa true (visitante vê o card novo); quem escolheu o clássico continua respeitado. */
  defaultCardV2?: boolean;
}

export function SidePanels({
  step, isError, isCorrect, coachAnnotation, studentId, currentDecisionId,
  annotating, annComment, annMode, annAction, annOverride,
  saveAnn, deleteAnn, replayData, playerAliases,
  setAnnotating, setAnnComment, setAnnMode, setAnnAction, setAnnOverride,
  openAnnotationForm, t,
  gtoRequestStatus, onRequestGto,
  compact = false,
  defaultCardV2 = false,
}: SidePanelsProps) {
  const [showDetails, setShowDetails] = useState<boolean>(
    () => localStorage.getItem('replayer_show_details') === 'true'
  );
  // ── Layout v2, atras de toggle, CLASSICO por padrao ───────────────────────────────────────
  // O v2 nasce do pedido de um card mais simples, mas o exemplo que o originou mostrava o caso
  // facil (decisao correta, cobertura total do solver). Medido, esse e o caso raro: a linha de
  // metricas fica parcialmente vazia em 76% dos cards. Por isso ele entra opt-in, com o classico
  // acessivel — da para comparar os dois nos casos dificeis antes de trocar o padrao, em vez de
  // descobrir na primeira tela do usuario.
  const [usarV2, setUsarV2] = useState<boolean>(() => {
    // Preferência salva manda; sem ela vale o default do chamador (a landing passa true
    // para a vitrine vender o card novo — visitante não tem localStorage).
    const salvo = localStorage.getItem('replayer_card_v2');
    return salvo != null ? salvo === 'true' : defaultCardV2;
  });
  const toggleV2 = () => setUsarV2(prev => {
    const next = !prev;
    localStorage.setItem('replayer_card_v2', String(next));
    return next;
  });

  const toggleDetails = () => setShowDetails(prev => {
    const next = !prev;
    localStorage.setItem('replayer_show_details', String(next));
    return next;
  });

  // "Melhorar com IA" na anotação: pede ao LLM uma versão mais clara/correta do texto do
  // coach (não-destrutivo — vira sugestão que o coach aceita ou descarta). i18n.language
  // dá o idioma; o backend preserva o sentido e mantém os termos de poker em inglês.
  const { i18n } = useTranslation();
  const [improved, setImproved] = useState<string | null>(null);
  const improveAnn = useMutation({
    mutationFn: () => coachDashboard.improveAnnotation(annComment.trim(), i18n.language),
    onSuccess: (r) => setImproved(r.improved || null),
  });

  const isPostflop = step.street !== 'preflop';
  // Posição do hero derivada dos ASSENTOS (cada seat traz `pos` do backend). O código antigo
  // lia `step.position`, campo que o backend nunca envia no step — o replayWhy então caía
  // sempre no ramo "posição ausente" e o BB nunca recebia a frase do check grátis.
  const heroPosition = Object.values(step.seats ?? {})
    .find((s) => s.player === step.hero)?.pos ?? null;
  // Spot multiway postflop: o solver HU não é confiável (backend zera gto_label/strategy).
  // Quando o advisor multiway DEFERE (sem multiway_advice), o veredito vem da SEVERIDADE
  // do engine (error_label EV-capado), não do gto_label de frequência HU. Card = badge.
  const isMultiwayStep = isPostflop && (step.n_active_opponents ?? 0) >= 2;
  const pg = step.preflop_gto ?? null;
  // Cobertura preflop negada explicitamente (ex.: pote limpado "vs Limp"): a análise
  // AO VIVO manda. Um gto_label ARMAZENADO stale (scoring antigo, pré-feature do limp)
  // NÃO pode forjar um veredito/badge que contradiz "sem cobertura".
  const preflopNoCoverage = !isPostflop && !!pg && !pg.available && !!pg.coverage_reason;
  // Pote limpado: NÃO é "sem veredito". O engine tem heurística (passivo OK; iso-raise sobre limp
  // = marginal, não erro grave). Credita-a — veredito de 3 níveis + source "Heurística" — em vez do
  // frio "Spot N/A". Subconjunto de preflopNoCoverage (o gto_label stale segue suprimido).
  const limpedPotHeuristic = preflopNoCoverage && pg?.coverage_reason === 'limped_pot';
  // "strict" = sem-cobertura que DEVE suprimir o veredito (exclui o pote limpado, que é creditado).
  const preflopNoCoverageStrict = preflopNoCoverage && !limpedPotHeuristic;
  // Call-vs-shove sem dado GTO (heurística): avaliado por POT ODDS (equity vs
  // necessária), NÃO pelo range de abertura. O fallback reusava o chrome do RFI
  // ("Range de abertura", "Fold X% agregado", chip "no range") — referência errada
  // p/ um call. Aqui o card vira uma decisão de math (equity × pot odds), coerente.
  const isShoveFb = !isPostflop && pg?.scenario === 'vs_shove_fallback' && !!pg?.available;
  // Spot de SHOVE (stack curto): a range de RFI é jam-dominante (allin_pct > raise_pct). Aí o
  // enquadramento é "shove", não "abertura" (evita mostrar um all-in de 8-10bb como "open X%").
  // Por DOMINÂNCIA, não por stack fixo: a ~9bb ainda há min-raise (ex.: AA), que segue "open".
  const isShoveSpot = !isPostflop && pg?.scenario === 'rfi' && (pg?.allin_pct ?? 0) > (pg?.raise_pct ?? 0);
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
    if (preflopNoCoverageStrict) {
      return { icon: "·", label: t("card.vNoCoverage"), cls: "text-muted-foreground",
               borderCls: "border-border", hdrCls: "bg-hud-surface",
               source: "Preflop", sourceTooltip: t("card.tipNoCoverage") };
    }
    // ── FEAT-20: VEREDITO DE 3 NÍVEIS (Correto / Aceitável / Erro) ──────────────
    // Dirigido pela SEVERIDADE (error_label, EV-capada) — a MESMA régua do badge de
    // aderência → card = badge por construção. A frequência (gto_label) deixou de ser
    // veredito; vive só nas barras de estratégia (contexto). Fonte = só p/ o tooltip.
    // PROCEDÊNCIA (25/08): o backend decide se esta decisão tem direito à linguagem de GTO —
    // exige equilíbrio (nó do solver ou carta) E custo em bb medido. A cascata abaixo deriva a
    // etiqueta de campos locais, e isso é uma SEGUNDA porta para o mesmo fato: quando o gate
    // disser não, ele manda. Medido no acervo: 14,8% das decisões são heurístico puro e 38% das
    // acusações com a carta reprovando saem sem um bb de custo — todas exibidas como equilíbrio.
    const _semEquilibrio = step.pode_falar_como_gto === false;
    const _src: { name: string; tip: string } =
        _semEquilibrio                ? { name: t("card.srcMotor"),     tip: t("card.tipSemEquilibrio") }
      : step.multiway_advice          ? { name: t("card.srcMultiway"),  tip: t("card.tipMultiwayEstimate") }
      : limpedPotHeuristic             ? { name: t("card.srcHeuristic"), tip: t("card.limpedPotTip") }
      : isMultiwayStep                 ? { name: "Engine",               tip: t("card.srcEngineTip") }
      : isShoveFb                      ? { name: t("card.srcHeuristic"), tip: t("card.srcHeuristicTip") }
      : effectiveGtoLabel              ? { name: "Solver",               tip: t("card.tipGtoSolver") }
      : (!isPostflop && pg?.available) ? { name: "Preflop",              tip: t("card.tipRange") }
      :                                  { name: "Engine",               tip: t("card.tipEngine") };
    const _hasBasis = isError || !!step.error_label || hasGto || !!pg?.available
      || step.multiway_advice != null || step.hand_equity != null || step.pot_odds_equity != null;
    if (!_hasBasis) return null;
    // B2: multiway = INFORMATIVO (solver é HU-only; advisor é estimativa). Não grada erro/correto —
    // mostra "≈ Aproximação" neutro + a sugestão do advisor. Consistente com o Ghost Table (opção A).
    if (step.multiway_advice) {
      return { icon: "≈", label: t("card.vApprox"), cls: "text-amber-300", borderCls: "border-amber-400/30", hdrCls: "bg-amber-400/8", source: _src.name, sourceTooltip: _src.tip };
    }
    // Gate zona-ICM: o ChipEV reprova o aperto, mas sob ICM (tight-is-right) foldar é
    // defensável — o grading não modela o risk premium. Mostra "≈ Aproximação chipEV"
    // em vez de "Erro". O engine já rebaixou o label; aqui é só o rótulo honesto do card.
    if (step.icm_zone_approx) {
      return { icon: "≈", label: t("card.vApproxIcm"), cls: "text-amber-300", borderCls: "border-amber-400/30", hdrCls: "bg-amber-400/8", source: t("card.srcIcm"), sourceTooltip: t("card.tipIcmApprox") };
    }
    // RC-D: clamp de defesa-em-profundidade — sinal de erro (GTO folda ↔ hero agride) NUNCA vira
    // correct/acceptable, mesmo se o label vier brando (não-reconciliado/legado).
    const _lvl: "correct" | "acceptable" | "error" = clampVerdict(
        verdictLevel(step.error_label) ?? (isError ? "error" : "correct"),
        step.gto_action, playedAction, effectiveGtoLabel ?? step.gto_label,
        // `hand_freq.fold` (da MAO), nunca `fold_pct` (da GRADE, quanto a posicao folda):
        // UTG folda ~90% das MAOS, e passar esse numero marcaria erro ate com AA.
        pg?.hand_freq?.fold) ?? "correct";
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
  // Usa o veredito CLAMPADO (sinal de erro de direção nunca é "ok").
  const _clampedActionLvl = clampVerdict(verdictLevel(step.error_label), step.gto_action, playedAction,
                                         effectiveGtoLabel ?? step.gto_label, pg?.hand_freq?.fold);
  // B2: multiway é informativo → não marca "ação errada" (a sugestão do advisor aparece à parte).
  const isActionOk = step.multiway_advice ? true
    : _clampedActionLvl != null
    ? _clampedActionLvl !== "error"
    : (isShoveFb ? (_fbActionOk ?? false) : !isError);
  // idealAction: use live top action when available (overrides stored gto_action which may be stale)
  const liveTopAction = verdictStrat.length > 0 ? verdictStrat[0].action : null;
  // Fonte da "ação recomendada" por prioridade (idealActionSource, testável). Preflop
  // coberto usa o RANGE (ação dominante do hand_freq) ANTES do gto_action do engine —
  // senão AA squeeze @14bb mostrava "GTO recomenda Call" em vez de Raise 93%.
  const _idealSrc = idealActionSource({
    // pote limpado é creditado pela heurística → usa best_action do engine (não "none")
    preflopNoCoverage: preflopNoCoverageStrict, isShoveFb, isPostflop, pgAvailable: !!pg?.available, hasGto,
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
  // Nome HUMANO do cenário. O que chega do motor é identificador interno (`hu_rfi`), e o card
  // imprimia isso na cara do jogador: "33 está no range hu_rfi". Os seis cenários de heads-up
  // criados em 07/08 nem tinham entrada aqui — e o fallback era `?? scenKey`, que GARANTE o
  // vazamento de qualquer cenário novo. Agora o fallback é uma palavra em português; sigla
  // interna não chega à tela nem quando esquecemos de mapear.
  const scenarioLabel: Record<string, string> = {
    rfi: "RFI",
    vs_rfi: "vs Open",
    vs_3bet: "vs 3-Bet",
    vs_shove_fallback: t("card.scenVsShoveFallback"),
    squeeze: "Squeeze",
    faces_squeeze: "vs Squeeze",
    vs_4bet: "vs 4-Bet",
    bb_option: t("card.scenBbOption"),
    hu_rfi: t("card.scenHuRfi"),
    hu_vs_rfi: t("card.scenHuVsRfi"),
    hu_bb_vs_limp: t("card.scenHuVsLimp"),
    hu_vs_3bet: t("card.scenHuVs3bet"),
    hu_vs_3bet_jam: t("card.scenHuVs3betJam"),
    hu_vs_4bet: t("card.scenHuVs4bet"),
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
        // PROCEDÊNCIA (25/08): esta é a cascata que CHEGA AO CARD — `SOURCE_LABEL[sourceVariant]`
        // é o que o jogador lê. O primeiro conserto pôs o gate na cascata `_src`, que alimenta
        // `verdict.source`, e esse campo não é renderizado em lugar nenhum: a etiqueta continuava
        // dizendo "Solver" em decisão sem custo medido. Gate desligado por falta de consumidor —
        // a terceira vez que este padrão aparece nesta série.
        // Mesma fonte da outra cascata — `_semEquilibrio` vive noutro escopo, e duplicar a
        // expressão aqui criaria duas leituras do mesmo campo que podem divergir na próxima
        // edição. Uma linha, uma regra.
        const semEquilibrioAqui = step.pode_falar_como_gto === false;
        const sourceVariant: DecisionSourceVariant =
          semEquilibrioAqui                       ? "motor"     :
          step.multiway_advice                    ? "multiway"  :
          (isMultiwayStep && !step.gto_label)     ? "engine"    :  // multiway deferido → severidade do engine
          limpedPotHeuristic                      ? "heuristic" :  // pote limpado → veredito heurístico do engine
          preflopNoCoverageStrict                 ? "na"        :
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
          motor: t("card.srcMotor"),
        };
        const SOURCE_TOOLTIP: Record<DecisionSourceVariant, string> = {
          gto: t("card.srcGtoTip"),
          preflop: t("card.srcPreflopTip"),
          engine: t("card.srcEngineTip"),
          heuristic: t("card.srcHeuristicTip"),
          pushfold: t("card.srcPushfoldTip"),
          multiway: t("card.tipMultiwayEstimate"),
          motor: t("card.tipSemEquilibrio"),
          na: t("card.srcNaTip"),
        };

        // ──────── Pré-cálculos compartilhados (postflop) ────────
        const eq = step.hand_equity ?? null;
        // Moldura de confiança da equity por street (17/08): turn/river = "≈" + tooltip com o
        // gap p90 medido contra showdowns reais. Ver EQUITY_GAP_P90 (cardLogic).
        const eqLowConf = eq != null && equityLowConfidence(step.street);
        const eqGapP90 = Math.round((EQUITY_GAP_P90[(step.street ?? "").toLowerCase()] ?? 0.5) * 100);
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

        // ──────── Equity que NÃO serve de evidência ────────
        // Preflop, quando o hero enfrenta uma aposta e a equity é `vs_random`, a conta
        // equity × pot odds não descreve o spot: `pipeline.py` só injeta a range real do vilão
        // quando `preflop_raises_faced == 1`, então num 3-bet a equity exibida é contra uma mão
        // ALEATÓRIA. Caso real: AQs no SB pagando 3-bet aparecia como "66.3% vs 46.4% · +19.9pp"
        // ao lado de "ERRO / RECOMENDADO FOLD" — a evidência apontava para o lado oposto do
        // veredito (que estava certo: contra a range real AQs tem ~30%). Um número que
        // contradiz o veredito ensina o jogador a desconfiar da análise inteira.
        // Push/fold fica FORA: ali a equity vem da range de shove e o preço É o enquadramento.
        // Pote LIMPADO fica FORA da supressão, e é o ponto do bloco inteiro: a regra existe
        // porque equity vs mão ALEATÓRIA contradizia o veredito. Aqui a equity é multiway de
        // verdade (Monte Carlo por número de jogadores que ainda podem ver o flop), e este é o
        // único spot pré-flop sem carta em fonte nenhuma — o preço é a evidência que sobra.
        // Esconder o número justo onde ele é a única razão do veredito deixa o card afirmando
        // sem mostrar por quê.
        const limpedPotComPreco = !isPostflop && !!step.facing_limp
                                  && (step.n_can_see_flop ?? 0) >= 2;
        const equityNotRangeAware = !isPostflop && !isVsRange && !isShoveFb && !limpedPotComPreco
                                    && eq != null && req != null && req > 0;
        const requiredIsAdjusted = step.adjusted_required_equity != null &&
                                   poRaw != null &&
                                   Math.abs(step.adjusted_required_equity - poRaw) >= 0.005;
        const hasEngineGtoConflict = !step.gto_spot_mismatch && step.engine_best && step.gto_action &&
                                     step.engine_best !== step.gto_action && isError;

        // ──────── Why (1 frase dominante) ────────
        // A ESCOLHA da frase mora em lib/replayWhy (função pura, testada). Aqui fica só a
        // tradução: cascata de prioridade não testada é onde bug se esconde — cada `else if`
        // novo pode roubar o caso de outro sem ninguém perceber, e já mentiu duas vezes
        // (street errada, e evidência contradizendo o veredito).
        const whyChoice = selectWhy({
          isPostflop, isError,
          // O MESMO sinal que decide ✓/◎/✗ no banner. Sem ele a frase era escolhida por uma
          // fonte independente do selo e chegava a dizer "Call lucrativo" embaixo de "✗ Erro".
          isActionOk,
          heroAction: (step.action ?? "").toLowerCase(),
          hasMultiwayAdvice: !!step.multiway_advice,
          limpedPotHeuristic, equityNotRangeAware, preflopNoCoverageStrict,
          // O preco so vai junto quando existe de verdade: o BB tem opcao gratis, e sem
          // custo a frase viraria "voce pagava 0bb", que e pior que nao dizer nada.
          limpedPrice: (limpedPotComPreco && step.facing_to_call_bb && poRaw && eq != null)
            ? { custoBb: step.facing_to_call_bb, exige: poRaw, equity: eq,
                nJogadores: step.n_can_see_flop ?? 0,
                poteBb: step.facing_to_call_bb / poRaw - step.facing_to_call_bb }
            : null,
          gtoSpotMismatch: !!step.gto_spot_mismatch,
          isPfZone, heroStackBb: step.hero_stack_bb,
          heroPosition,
          hasEngineGtoConflict, engineBest: step.engine_best, gtoAction: step.gto_action,
          hasMathEvidence, requiredIsAdjusted, eq, req, profitable,
          hasGto, isHero: !!step.is_hero, pg,
          // A frase precisa poder falar da AÇÃO, não só descrever a mão: o card dizia "33 está
          // no range de abertura" para quem min-raisou onde a carta manda all-in.
          recAction: idealAction ?? null,
          heroActionRaw: step.action ?? null,
        });
        // Leitura de range por iniciativa: uma frase estrutural, SEM alegacao estatistica
        // (derivacao pura em replayWhy — a medicao que limita a copy esta documentada la).
        // Vai como frase adicional, nao substitui a dominante: a dominante fala da DECISAO,
        // esta fala do que a aposta enfrentada costuma ser.
        const leituraIniciativaKey = leituraDaIniciativa(
          isPostflop, (step.facing_to_call_bb ?? 0) > 0, step.street_initiative);
        const why = whyChoice.key
          ? t(whyChoice.key, {
              ...(whyChoice.params ?? {}),
              // params indiretos: a chave do rótulo e o cenário viram texto AQUI, na view
              ...(whyChoice.params?.reqLabelKey
                ? { reqLabel: t(whyChoice.params.reqLabelKey as string) } : {}),
              ...(whyChoice.params?.scenKey
                ? { scen: scenarioLabel[whyChoice.params.scenKey as string] ?? t("card.scenGenerico") } : {}),
              ...Object.fromEntries(
                Object.entries(whyChoice.actionParams ?? {}).map(([k, v]) => [k, fmtAction(v)])),
            })
          : "";
        const whyComLeitura = leituraIniciativaKey
          ? (why ? `${why} ${t(leituraIniciativaKey)}` : t(leituraIniciativaKey))
          : why;

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
              <div className="flex items-center justify-between">
                <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  {t("card.mwTitle")}
                </div>
                <span className="font-mono text-[9px] text-muted-foreground/70">
                  {t("card.mwNway", { n: mw.n_opponents + 1 })}
                </span>
              </div>
              <div className="rounded-md border border-border/50 bg-hud-surface/40 p-2 space-y-1.5">
                {/* decisão do engine heurístico multiway (não-GTO) */}
                <div className="flex items-center justify-between border-b border-border/40 pb-1.5 text-[10px] font-mono">
                  <span className="text-muted-foreground">{t("card.mwRecommended")}</span>
                  <span className="font-bold uppercase text-primary">{fmtAction(mw.action)}</span>
                </div>
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
          // ── O selo fala de PREÇO; o veredito fala de estratégia. Não trocar um pelo outro ──
          // Versão anterior: `mathActionIsEv = isActionOk`, ou seja, o selo repetia o veredito.
          // Isso resolveu uma contradição ("RAISE +EV" verde ao lado de "✗ ERRO") e criou outra,
          // pior: um selo rotulado **EV** que não fala de EV. Reportado com print — a frase dizia
          // "Call lucrativo: equity 54% supera pot odds 44%" e o selo, a dois centímetros,
          // "CALL −EV".
          //
          // Agora o selo diz o que o nome dele promete (o preço fecha ou não), e quando isso
          // DIVERGE do veredito a divergência vira informação explícita em vez de sumir: é o
          // caso em que a range ou o ICM mandam o contrário do que o preço sugere, e é
          // justamente o que o jogador precisa entender.
          const mathActLabel  = step.action ? fmtAction(step.action) : null;
          const precoDiverge  = mathCallIsEv !== isActionOk;
          const mathBadgeCls  = mathCallIsEv
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            : "bg-red-500/10 text-red-400 border border-red-500/20";
          const mathBadgeLabel = `${mathActLabel ?? ''} ${mathCallIsEv ? "+EV" : "−EV"}`.trim();
          const reqHeader = requiredIsAdjusted ? t("card.reqEquity") : "Pot Odds";
          const reqTooltip = requiredIsAdjusted
            ? t("equityAjustada", { bruto: (poRaw! * 100).toFixed(1) })
            : t("equityMinima");
          evidence = (
            <div className="rounded-lg border border-border/40 bg-muted/5 px-3 py-2">
              <div className="flex items-center gap-3 flex-wrap">
                <div title={reqTooltip}>
                  <p className="font-mono text-[10px] text-muted-foreground uppercase cursor-help">{reqHeader}</p>
                  <p className="font-mono text-[13px] font-bold text-foreground/80 tabular-nums">{(req! * 100).toFixed(1)}%</p>
                </div>
                <div className="text-muted-foreground/50 font-mono text-[11px]">vs</div>
                {/* Moldura de confiança por street (17/08): "≈" + tooltip com o gap p90 medido
                    contra 1.082 showdowns reais — turn/river têm cauda gorda. */}
                <div className={cn(eqLowConf && "cursor-help")}
                     title={eqLowConf ? t("card.eqLowConfTip", { p90: eqGapP90 }) : undefined}>
                  <p className="font-mono text-[10px] text-muted-foreground uppercase">Equity</p>
                  <p className={cn("font-mono text-[13px] font-bold tabular-nums", !isActionOk ? "text-muted-foreground/60" : mathCallIsEv ? "text-emerald-400" : "text-red-400")}>
                    {eqLowConf ? "≈ " : ""}{(eq! * 100).toFixed(1)}%
                  </p>
                </div>
                <div className={cn("ml-auto rounded-md px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wide", mathBadgeCls)}>
                  {mathBadgeLabel}
                </div>
              </div>
              {precoDiverge && (
                <p className="mt-2 border-t border-border/40 pt-2 text-[11.5px] leading-snug text-muted-foreground">
                  {/* "o veredito vem da RANGE" só pode ser dito quando HÁ range. Num spot sem
                      cobertura (a mão não chega àquele nó da árvore) o veredito vem da
                      heurística, e afirmar range ali é inventar um motivo — a mesma família do
                      "foi o tamanho" dito onde não era tamanho. */}
                  {!pg?.available
                    ? t("card.precoDivergeHeuristica")
                    : mathCallIsEv
                    ? t("card.precoPagaMasVeredito")
                    : t("card.precoNaoPagaMasVeredito")}
                </p>
              )}
            </div>
          );
        } else if (isPostflop && eq != null) {
          // Equity bar (postflop sem pot odds) — mesma moldura de confiança por street.
          evidence = (
            <div className={cn(eqLowConf && "cursor-help")}
                 title={eqLowConf ? t("card.eqLowConfTip", { p90: eqGapP90 }) : undefined}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">Equity</span>
                <span className="font-mono text-[13px] font-bold tabular-nums text-sky-400">{eqLowConf ? "≈ " : ""}{(eq * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-border/50 overflow-hidden">
                <div className="h-full rounded-full bg-sky-500 transition-all" style={{ width: `${(eq * 100).toFixed(1)}%` }} />
              </div>
            </div>
          );
        } else if (false && !isPostflop && pg?.available && pg.range_pct > 0) {
          // ── DESLIGADA em 08/08: a barra de "range de continuação" ─────────────────────────
          // O numero (ex.: 42%) responde "que fatia do range INTEIRO o GTO nao folda aqui" —
          // pergunta que o jogador nao fez, sobre um range que nao e o dele. Ele quer saber o
          // que fazer com a MAO que tinha, e essa resposta ja esta logo abaixo, na barra de
          // frequencia da propria mao ("Fold 100%"). Duas barras competindo, uma sobre o range
          // e outra sobre a mao, com pesos visuais parecidos: a mais util perdia a disputa.
          //
          // Mantida no codigo, e nao apagada, porque o dado continua correto e util em outra
          // superficie (estudo de range). O que estava errado era o LUGAR.
          // Range bar (preflop com cobertura)
          evidence = (
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">{t(isShoveSpot ? "card.rangeShove" : (rangeLabelKey[pg.scenario] ?? "card.rangeOpening"))}</span>
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
        // Mesma regra do RangePanel, uma função só: as notas que falam de "leak" não aparecem
        // quando o veredito diz que não é erro. O guarda antigo ancorava no rótulo do solver e
        // deixava passar `gto_critical`, que era 25 de 25 das contradições medidas.
        const showProNotes = showAuditPreflop && (pg!.pro_notes?.length ?? 0) > 0 &&
                             mostraQualidadeEstatica({
                               actionQuality: pg!.action_quality,
                               gtoLabel: effectiveGtoLabel,
                               isError: step.is_error,
                               podeFalarComoGto: step.pode_falar_como_gto,
                             });
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

        // Multiway: nº de jogadores no pote. FONTE ÚNICA = n_active_opponents do backend
        // (conta só quem CONTINUOU voluntariamente; ignora assento sentado FORA da mão, ex.:
        // jogador "out of hand" movido de outra mesa que nunca foi distribuído nem foldou).
        // O fallback dealt − foldados contava esse fantasma como vivo → HU virava "multiway".
        // Só cai no fallback em passo legado sem o campo. Alinha o badge com isMultiwayStep (L117).
        const _nOpp = step.n_active_opponents;
        const livePlayers = (_nOpp != null)
          ? _nOpp + 1
          : computeLivePlayers(step.seats as Record<string, unknown> | undefined, step.folded);
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
            {/* Equity REAL vs a mão mostrada (17/08): fato do showdown, não estimativa. É
                contexto de REVISÃO, nunca veredito — julgar a decisão pela mão que apareceu
                é resulting; o veredito continua vindo da range. O tooltip explica isso. */}
            {(() => {
              const re = (step as { real_equity_vs_shown?: { equity: number; villain: string; villain_cards: string[] } }).real_equity_vs_shown;
              if (!re) return null;
              return (
                <div className="rounded-lg ring-1 px-2.5 py-2 bg-sky-500/8 ring-sky-500/25"
                     title={t("card.realEqTip", { villain: re.villain })}>
                  <p className="font-mono text-[9px] font-bold uppercase tracking-wider mb-0.5 text-sky-300/90">
                    {t("card.realEqTitle")}
                  </p>
                  <p className="text-[11.5px] text-foreground/85 leading-relaxed font-mono">
                    {re.villain_cards.join(" ")} · {Math.round(re.equity * 100)}%
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
              // E5: quando o veredito é Erro (!isActionOk), a equity verde contradiz — neutraliza (cinza),
              // igual o +pp já é mutado. A evidência matemática não pode "verdejar" sobre um erro de GTO.
              const eqColor = eq == null ? "" : !isActionOk ? "text-muted-foreground/60" : eq >= 0.65 ? "text-emerald-400" : eq >= 0.50 ? "text-foreground" : eq >= 0.35 ? "text-amber-400" : "text-red-400";
              const eqQual = eq == null ? "" : eq >= 0.65 ? t("card.eqStrong") : eq >= 0.50 ? t("card.eqFavorable") : eq >= 0.35 ? t("card.eqMarginal") : t("card.eqWeak");
              const reqShown = (req != null && req > 0) ? req : reqImplicit;
              const pp = (eq != null && reqShown != null) ? (eq - reqShown) * 100 : null;
              const ppMuted = pp == null ? true : isPpMuted({ showAuditPreflop: false, effectiveGtoLabel, eq: eq!, reqShown: reqShown!, isActionOk });
              // `qualificadorDeCusto` decide; aqui só se traduz. A palavra "caro" precisa de um
              // preço, e `gto_critical` é frequência — ver a função para o caso que originou.
              const costQual = t("card.cost" + ({
                aligned: "Aligned", minor: "Minor", critical: "Critical",
                plus: "Plus", minus: "Minus", unmeasured: "Unmeasured",
              })[qualificadorDeCusto({
                gtoLabel: effectiveGtoLabel, temCusto: step.verdict_has_cost, pp,
              })]);
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
                      // Contexto: RFI mostra "abrindo" (ou "shove" se a range é jam-dominante);
                      // vs_RFI/3bet/etc mostra "vs OPENER"
                      const ctxStr = isRFI
                        ? t(isShoveSpot ? "card.ctxShoving" : "card.ctxOpening", { position: pg!.position, stack: stackRef })
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
            {/* "Sem veredito" precisa dizer POR QUE. O banner neutro ja existia, mas o card
                ficava mudo sobre o motivo, e "nao sei" sem explicacao lê como produto quebrado.
                Cada motivo tem uma frase propria — sao situacoes diferentes, nao um buraco so. */}
            {!isPostflop && pg && !pg.available && pg.coverage_reason
              && pg.coverage_reason !== 'limped_pot' && (
              <p className="text-[12.5px] leading-snug text-muted-foreground border-l-2 border-border/60 pl-2.5">
                {t(`card.semGabarito.${pg.coverage_reason}`)}
              </p>
            )}
            {/* SPR/Sizing/Equity/Mín.EV de postflop migraram pro bloco de 3 (acima).
                Aqui ficam só os de PREFLOP (gated !isPostflop). */}
            {!isPostflop && eq != null && !equityNotRangeAware && (
              <div className="flex items-center gap-2 font-mono text-[11px] flex-wrap"
                title={limpedPotComPreco
                  ? t("card.limpedPriceTip", { n: step.n_can_see_flop })
                  : showAuditPreflop ? (isVsRange ? t("card.reqVsRangeTip")
                                                  : t("card.reqVsRandomTip"))
                                     : t("card.equityTip")}>
                <span className="w-14 shrink-0 text-muted-foreground uppercase text-[10px]">Equity</span>
                <span className={cn(
                  "font-bold tabular-nums",
                  !isActionOk ? "text-muted-foreground/60" :   // E5: equity não verdeja sobre Erro
                  eq >= 0.65 ? "text-emerald-400" :
                  eq >= 0.50 ? "text-foreground" :
                  eq >= 0.35 ? "text-amber-400" : "text-red-400"
                )}>{(eq * 100).toFixed(1)}%</span>
                <span className="text-muted-foreground text-[10px] whitespace-nowrap">
                  {eq >= 0.65 ? t("card.eqStrong") : eq >= 0.50 ? t("card.eqFavorable") : eq >= 0.35 ? t("card.eqMarginal") : t("card.eqWeak")}
                  {(showAuditPreflop || isShoveFb || limpedPotComPreco) && (
                    <span className="text-muted-foreground/60"> · {
                      // Nomear a fonte pelo que ela É. Num pote limpado não é "vs range" (não há
                      // carta) nem "vs aleatória" (o número é multiway) — é contra N jogadores,
                      // e dizer quantos é o que torna o valor lido corretamente.
                      limpedPotComPreco ? t("card.vsMultiway", { n: step.n_can_see_flop })
                        : isVsRange ? t("card.vsRange") : t("card.vsRandom")
                    }</span>
                  )}
                </span>
              </div>
            )}
            {!isPostflop && !equityNotRangeAware && ((req != null && req > 0) || reqImplicit != null) && (() => {
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
        // Encadeia na MESMA variavel que a leitura de iniciativa ja compos: um unico ponto de
        // acumulo de ressalvas, senao cada frase adicional nova cria a sua copia do padrao e
        // uma engole a outra. (osm e preflop; a leitura de iniciativa e postflop — nunca
        // coexistem, mas o encadeamento nao depende disso.)
        const whyFull = osm
          ? `${whyComLeitura ? whyComLeitura + " " : ""}${t("card.openOversizeCaveat", { facing: osm.facing_bb, canonical: osm.canonical_bb })}`
          : whyComLeitura;

        // ── COMPACT (bottom-sheet mobile): só o essencial, sem scroll, 2 cols em landscape ──
        // Reusa TODO o cálculo de veredito/why/evidence acima. NÃO renderiza pro_notes,
        // toggle de detalhes, fluxo de solve GTO nem o formulário do coach (escondidos
        // fora do card). Esquerda = veredito + ação jogada/recomendada + why; direita =
        // evidence (barras GTO/math) + grid de indicadores (stack/M/ICM/posição).
        if (compact) {
          const showRec = !isActionOk && !!idealAction &&
            idealAction.toLowerCase() !== playedAction.toLowerCase();
          const ind: { label: string; value: string; tip: string }[] = [];
          if (step.hero_stack_bb != null) ind.push({ label: t("card.stackBb"), value: `${step.hero_stack_bb.toFixed(1)}bb`, tip: t("card.stackTip") });
          if (step.m_ratio != null)       ind.push({ label: t("card.mRatio"), value: step.m_ratio.toFixed(1), tip: t("card.mTip") });
          if (step.icm_pressure != null)  ind.push({ label: t("card.icm"), value: (step.icm_pressure === "low" ? t("card.icmLow") : step.icm_pressure === "medium" ? t("card.icmMedium") : step.icm_pressure === "high" ? t("card.icmHigh") : step.icm_pressure), tip: t("card.icmTip") });
          if (heroPosition)               ind.push({ label: t("card.position"), value: heroPosition, tip: "" });
          return (
            <section className={cn("rounded-xl border overflow-hidden", verdict.borderCls)}>
              <div className="grid grid-cols-1 landscape:grid-cols-2 gap-3 p-3">
                {/* COLUNA ESQUERDA: veredito + ações + why */}
                <div className="space-y-2 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className={cn("font-mono text-sm font-bold uppercase tracking-wide", verdict.cls)}>
                      {verdict.icon} {verdict.label}
                    </span>
                    {/* Ausência de EV explicada, não silenciosa: o selo simplesmente sumir deixava
                        o jogador sem saber se ele não perdeu nada ou se o produto não sabe. Só em
                        postflop com erro/aceitável — em 'correto' o EV perto de zero não precisa
                        de explicação, e em preflop o EV quase sempre existe (fonte gw_har). */}
                    {step.ev_loss_bb == null && isPostflop && !isActionOk && (
                      <span className="inline-flex items-center rounded-md bg-muted/20 px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground/70 ring-1 ring-border/50 cursor-help"
                        title={t("card.evUnavailable")}>
                        EV ?
                      </span>
                    )}
                    {step.ev_loss_bb != null && step.ev_loss_bb > 0.05 && (
                      <span className={cn(
                        "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold tracking-wide ring-1",
                        step.ev_loss_bb >= 2 ? "text-red-300 bg-red-500/10 ring-red-500/30"
                          : step.ev_loss_bb >= 0.5 ? "text-orange-300 bg-orange-500/10 ring-orange-500/30"
                          : "text-amber-300 bg-amber-500/10 ring-amber-500/30",
                      )}>
                        −{step.ev_loss_bb.toFixed(step.ev_loss_bb >= 10 ? 0 : 1)} bb
                      </span>
                    )}
                  </div>
                  <div className={cn("grid gap-2", showRec ? "grid-cols-2" : "grid-cols-1")}>
                    <div className="rounded-lg px-2.5 py-1.5 ring-1 bg-background/60 ring-border/50">
                      <div className="font-mono text-[9px] uppercase tracking-wide text-muted-foreground">{t("card.youPlayed")}</div>
                      <div className={cn("font-mono text-sm font-bold uppercase", isActionOk ? verdict.cls : "text-foreground")}>{fmtAction(playedAction)}</div>
                    </div>
                    {showRec && (
                      <div className="rounded-lg px-2.5 py-1.5 ring-1 bg-background/60 ring-border/50">
                        <div className="font-mono text-[9px] uppercase tracking-wide text-muted-foreground">{hasGto ? t("card.gtoRecommends") : t("card.recommended")}</div>
                        <div className={cn("font-mono text-sm font-bold uppercase", verdict.cls)}>{fmtAction(idealAction!)}</div>
                      </div>
                    )}
                  </div>
                  {whyFull && (
                    <p className="text-[12px] text-muted-foreground leading-snug">{whyFull}</p>
                  )}
                  {/* Nota do coach (só leitura — nunca o formulário no modo compacto) */}
                  {coachAnnotation?.comment && (
                    <p className="text-[11px] text-primary/90 leading-snug border-t border-border/30 pt-1.5">
                      <GraduationCap className="inline size-3 mr-1 -mt-0.5" />{coachAnnotation.comment}
                    </p>
                  )}
                </div>
                {/* COLUNA DIREITA: evidence (barras GTO/math) + indicadores */}
                <div className="space-y-2 min-w-0">
                  {evidence && <div>{evidence}</div>}
                  {ind.length > 0 && (
                    <div className="grid grid-cols-2 gap-1.5">
                      {ind.map((i) => (
                        <div key={i.label} className="rounded-md ring-1 ring-border/40 bg-background/40 px-2 py-1" title={i.tip}>
                          <div className="font-mono text-[8px] uppercase tracking-wide text-muted-foreground/70">{i.label}</div>
                          <div className="font-mono text-[12px] font-bold tabular-nums text-foreground/85">{i.value}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </section>
          );
        }

        // ── v2: mesmo dado, layout enxuto. As três métricas saem de uma função PURA ────────
        // (`metricasDoCard`), testada à parte — a cascata que decide o motivo de cada ausência
        // não podia morar dentro do JSX.
        if (usarV2) {
          return (
            <>
              <DecisionCardV2
                verdict={verdict}
                source={{ label: SOURCE_LABEL[sourceVariant],
                          tooltip: SOURCE_TOOLTIP[sourceVariant], variant: sourceVariant }}
                playedAction={playedAction}
                idealAction={idealAction}
                isActionOk={isActionOk}
                contexto={step.street ?? null}
                metricas={metricasDoCard({
                  evLossBb: step.ev_loss_bb,
                  evLossMotivo: step.ev_loss_motivo,
                  equity: eq,
                  requerido: req,
                  // Apostou: o preco e o DELE. Sem isto o slot dizia "nao pagou" e o bloco de
                  // auditoria mostrava "min. EV 17,5%" tres linhas abaixo — o card se
                  // contradizendo, reportado num print.
                  requeridoImplicito: reqImplicit,
                  acao: step.action,
                  acaoOk: isActionOk,
                  street: step.street,
                })}
                estrategia={(() => {
                  if (verdictStrat.length)
                    return verdictStrat.map(r => ({
                      acao: r.action, freq: r.frequency ?? 0,
                      jogada: normalizeGtoAction(r.action)
                              === normalizeGtoAction(step.action ?? ''),
                    }));
                  // PREFLOP sem estratégia de solver: as barras vêm do hand_freq (a frequência
                  // da MÃO nas ranges) — o "Como GTO joga X" do layout clássico. Sumiu na v1 do
                  // card novo e era o bloco mais usado do antigo (pedido do usuário, 12/08).
                  const hf = !isPostflop ? pg?.hand_freq : null;
                  if (!hf || !Object.values(hf).some(v => (v ?? 0) > 0.001)) return null;
                  return (["raise", "allin", "call", "fold"] as const)
                    .map(a => ({ acao: a, freq: hf[a] ?? 0,
                                 jogada: normalizeGtoAction(a) === normalizeGtoAction(step.action ?? '') }))
                    .filter(r => r.freq > 0.001)
                    .sort((x, y) => y.freq - x.freq);
                })()}
                // O título diz de QUEM é a estratégia. Num pote multiway o solver é heads-up e
                // não resolve 3-way+: pôr as barras sob "Estratégia do Solver" atribuiria a ele
                // uma resposta que não é dele. No preflop (hand_freq), o título é o do bloco
                // clássico: "Como GTO joga {mão} · {contexto}".
                estrategiaTitulo={verdictStrat.length
                  ? (isMultiwayStep ? t("card.mwTitle") : t("card.solverStrategy"))
                  : (() => {
                      if (isPostflop || !pg?.hand_freq) return t("card.solverStrategy");
                      const validVs = pg.vs_position && pg.vs_position !== 'UNKNOWN' ? pg.vs_position : null;
                      const ctxStr = pg.scenario === 'rfi'
                        ? t(isShoveSpot ? "card.ctxShoving" : "card.ctxOpening", { position: pg.position, stack: pg.stack_bucket })
                        : (validVs ? t("card.ctxVs", { vs: validVs, stack: pg.stack_bucket })
                                   : t("card.ctxPlain", { position: pg.position, stack: pg.stack_bucket }));
                      return t("card.freqDisplayHand", { hand: pg.hand_type ?? '', ctx: ctxStr });
                    })()}
                frase={whyFull}
                showDetails={showDetails}
                onToggleDetails={toggleDetails}
                // ── Auditoria ENXUTA ──────────────────────────────────────────────────
                // A primeira versao reaproveitava o `indicators` do card classico, e o
                // resultado foi o print do usuario: seis rotulos empilhados, a EQUITY
                // repetida (55,3% em cima e embaixo) e o "min. EV" contradizendo o
                // "nao pagou" da linha de metricas.
                //
                // Aqui fica so o que NAO esta na linha de tres: o cenario, se a mao esta no
                // range, e o tamanho. Os numeros ja subiram.
                detalhes={(() => {
                  const cenario = pg?.available ? (scenarioLabel[pg.scenario] ?? pg.scenario) : null;
                  const sz = (step as { sizing_advice?: { key: string; params: Record<string, unknown> } })
                             .sizing_advice;
                  if (!cenario && !sz) return undefined;
                  return (
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1
                                    font-mono text-[11px] text-muted-foreground">
                      {cenario && <span>{cenario}</span>}
                      {pg?.hand_type && (
                        // `in_range`, nao `hand_in_range` — o segundo nao existe no tipo e eu o
                        // inventei. Passou no `tsc --noEmit` da raiz porque aquele comando NAO
                        // CHECA NADA neste repo (o tsconfig raiz so tem project references).
                        <span className={pg.in_range ? undefined : "text-amber-400"}>
                          {pg.hand_type} · {pg.in_range
                            ? t("card.handInRangeTag") : t("card.handOutRangeTag")}
                        </span>
                      )}
                      {sz && <span>{t(`card.sizingAdvice.${sz.key}`, sz.params)}</span>}
                    </div>
                  );
                })()}
                icmBadge={null}
                fmtAction={fmtAction}
                verdictTooltip={verdict.sourceTooltip}
              />
              {/* 30/08, decisao do dono: o layout novo venceu — o toggle "voltar ao
                    classico" saiu do card. O classico segue no codigo para o teste de
                    contrato, sem porta na tela. */}
            </>
          );
        }

        const CardImpl = DecisionCard;
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
            why={step.gto_approx_stack
              ? `${t("card.approxDeep", { n: step.gto_approx_stack })} ${whyFull ?? ""}`.trim()
              : whyFull}
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
          {/* A PORTA DE ENTRADA do v2. A primeira versao so tinha o "voltar ao classico", dentro
              do ramo v2 — um opt-in sem como optar. Achado ao reler, nao por teste. */}
          <button type="button" onClick={toggleV2} title={t("card.v2ToggleTip")}
                  className="mt-1 w-full text-right font-mono text-[10px] text-muted-foreground/50 hover:text-muted-foreground">
            {t("card.v2ToggleOff")}
          </button>
          </>
        );
      })()}


      {/* ── Cobertura GTO postflop ──────────────────────────────────────
          Spots que o solver heads-up NÃO cobre (multiway, deep>60bb, hero IP
          enfrentando aposta, sem vilão) mostram uma nota HONESTA estática, não
          "Processando" (que sugere que vai resolver) nem auto-solve inútil.
          Só 'pending' (solvável, nó ainda não existe) mostra o fluxo de solve. */}
      {!compact && step.is_hero && step.type === "action" && isPostflop && !hasGto && !isMultiwayStep
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
      {!compact && studentId && step?.is_hero && currentDecisionId && (
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
              {/* Melhorar com IA: reescreve o texto do coach (clareza/ortografia/didática), sem salvar */}
              <div className="space-y-2">
                <button type="button" onClick={() => improveAnn.mutate()} disabled={!annComment.trim() || improveAnn.isPending}
                  className="inline-flex items-center gap-1.5 rounded-md border border-primary/40 bg-primary/5 px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-widest-2 text-primary hover:bg-primary/10 disabled:opacity-50">
                  {improveAnn.isPending ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
                  {t("annotation.improveBtn")}
                </button>
                {improveAnn.isError && <p className="text-[11px] text-destructive">{t("annotation.improveError")}</p>}
                {improved && (
                  <div className="rounded-md border border-primary/30 bg-primary/5 p-2.5 space-y-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest-2 text-primary/80">{t("annotation.improveSuggestion")}</p>
                    <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{improved}</p>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => { setAnnComment(improved); setImproved(null); }}
                        className="inline-flex items-center gap-1 rounded bg-primary px-2.5 py-1 font-mono text-[10px] font-bold uppercase text-primary-foreground hover:bg-primary/90">
                        <Check className="size-3" /> {t("annotation.improveUse")}
                      </button>
                      <button type="button" onClick={() => setImproved(null)}
                        className="inline-flex items-center gap-1 rounded border border-border px-2.5 py-1 font-mono text-[10px] text-muted-foreground hover:text-foreground">
                        <X className="size-3" /> {t("annotation.improveDiscard")}
                      </button>
                    </div>
                  </div>
                )}
              </div>
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
      {!compact && !studentId && coachAnnotation && (
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
