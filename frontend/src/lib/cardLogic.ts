// Regras PURAS de display do Decision Card, extraídas do Replayer.tsx para serem
// testáveis (vitest). Cada uma codifica um fix das varreduras — travar contra
// regressão silenciosa. O Replayer importa e usa estas funções (não duplica).
export { computeEffectiveGtoLabel } from "./gtoUtils";

/**
 * Veredito de DISPLAY em 3 níveis (Correto / Aceitável / Erro) — FEAT-20.
 * Dirigido pela SEVERIDADE (`label`/`error_label`, já EV-capada), NÃO pela frequência
 * (gto_label, que vira contexto). Fonte única no front; espelha `leaklab/verdict.py`.
 *   standard → correct · marginal → acceptable · small/clear_mistake → error · resto → null
 */
export type VerdictLevel = "correct" | "acceptable" | "error";
export function verdictLevel(label: string | null | undefined): VerdictLevel | null {
  switch ((label ?? "").trim().toLowerCase()) {
    case "standard":      return "correct";
    case "marginal":      return "acceptable";
    case "small_mistake":
    case "clear_mistake": return "error";
    default:              return null;
  }
}

/**
 * Meta de DISPLAY dos 3 níveis — FONTE ÚNICA de ícone/cor para TODAS as superfícies
 * (card do replayer, TournamentDetail, views do coach, breakdowns). O texto vem do
 * i18n `common:verdict.<level>` (Correto/Aceitável/Erro). Mantém a paleta idêntica ao
 * card: correct=emerald, acceptable=sky, error=red. `i18nKey` = chave no namespace common.
 */
export const VERDICT_LEVELS: VerdictLevel[] = ["correct", "acceptable", "error"];
export const VERDICT_META: Record<VerdictLevel, { icon: string; textCls: string; chipCls: string; dotCls: string; ringCls: string; i18nKey: string }> = {
  correct:    { icon: "✓", textCls: "text-emerald-400", chipCls: "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/30", dotCls: "bg-emerald-400", ringCls: "ring-emerald-400/40", i18nKey: "verdict.correct" },
  acceptable: { icon: "◎", textCls: "text-sky-400",     chipCls: "bg-sky-500/10 text-sky-400 ring-1 ring-sky-500/30",          dotCls: "bg-sky-400",     ringCls: "ring-sky-400/40",     i18nKey: "verdict.acceptable" },
  error:      { icon: "✗", textCls: "text-red-400",     chipCls: "bg-red-500/10 text-red-400 ring-1 ring-red-500/30",          dotCls: "bg-red-400",     ringCls: "ring-red-400/40",     i18nKey: "verdict.error" },
};

/**
 * Severidade interna (`label`) → nível de display **clampando** para "error" quando não
 * classificável mas marcado como erro. Conveniência p/ superfícies que só têm o `label`.
 */
export function verdictLevelOrError(label: string | null | undefined): VerdictLevel {
  return verdictLevel(label) ?? "error";
}

/**
 * Severidade EFETIVA de UMA decisão para o resumo da mão (lista de mãos), honrando a
 * regra multiway — a MESMA que o card/replay aplica. Postflop com 2+ oponentes ativos é
 * INFORMATIVO (solver é HU-only): não pune, vira "correct". Com a cauda segura gravada
 * (`multiway_safe_verdict`), o veredito DERIVA do próprio safe_verdict + ação — exatamente
 * como o replay/drill (graded_safe_verdict) fazem: hero seguiu a linha segura → correct;
 * divergiu → grade pelo label. A versão anterior gradeava "pelo label" sempre que o veredito
 * existia, e as linhas do backfill SHADOW (label HU intacto por design) saíam "Erro" na lista
 * com o replay absolvendo — a divergência entre as duas telas.
 */
export interface DecisionSeverityInput {
  street: string;
  label: string | null | undefined;
  n_active_opponents?: number | null;
  multiway_safe_verdict?: string | null;
  action_taken?: string | null;
}

const _SAFE_VALUE_ACTS = new Set(["bet", "bets", "raise", "raises", "call", "calls", "jam", "shove", "allin", "all-in"]);

export function decisionSeverity(d: DecisionSeverityInput): VerdictLevel {
  const isPostflop = (d.street || "").toLowerCase() !== "preflop";
  const multiway = isPostflop && d.n_active_opponents != null && d.n_active_opponents >= 2;
  if (multiway && !d.multiway_safe_verdict) return "correct";  // informativo, não pune
  if (multiway && d.multiway_safe_verdict) {
    // Cauda segura: o veredito deriva do PRÓPRIO safe_verdict + ação, como o replay e o drill
    // fazem (graded_safe_verdict vive nas camadas de display; o `label` da linha segue sendo o
    // HU, por design). A versão anterior gradeava "pelo label" e 13 linhas do backfill SHADOW
    // saíam ERRO na lista com o replay absolvendo — safe_fold + hero foldou não é leak.
    const at = (d.action_taken || "").toLowerCase();
    if (d.multiway_safe_verdict === "safe_fold") return at === "fold" || at === "folds" ? "correct" : verdictLevelOrError(d.label);
    if (d.multiway_safe_verdict === "safe_value") return _SAFE_VALUE_ACTS.has(at) ? "correct" : verdictLevelOrError(d.label);
  }
  return verdictLevelOrError(d.label);
}

const _AGGRESSIVE_ACTIONS = new Set(["raise", "bet", "jam", "shove", "allin", "all-in", "3bet", "4bet", "reraise"]);

/**
 * Espelho do sinal canônico de erro do backend (is_verdict_error_signal). True ⇒ erro de direção:
 * o GTO folda a mão (fora do range) mas o hero AGREDIU, ou a ação tem fold ~100%.
 */
export function isVerdictErrorSignal(
  gtoAction: string | null | undefined,
  actionTaken: string | null | undefined,
  foldPct?: number | null,
): boolean {
  const ga = (gtoAction ?? "").toLowerCase().trim();
  const at = (actionTaken ?? "").toLowerCase().trim();
  if (!_AGGRESSIVE_ACTIONS.has(at)) return false;
  if (ga === "fold") return true;                       // GTO descarta a mão; hero agrediu
  if (foldPct != null && foldPct >= 0.9) return true;   // GTO folda ~100% mas hero agrediu
  return false;
}

/**
 * Clamp de veredito (RC-D, defesa-em-profundidade da vitrine): se há sinal de erro, o nível NUNCA
 * pode ser correct/acceptable — força "error". Exclui mix legítimo (gto_mixed/gto_correct), onde a
 * agressão pode ser co-ótima. Garante: o card nunca diz "Correto" enquanto o painel diz "Fold 100%".
 */
export function clampVerdict(
  level: VerdictLevel | null,
  gtoAction: string | null | undefined,
  actionTaken: string | null | undefined,
  gtoLabel?: string | null,
  foldPct?: number | null,
): VerdictLevel | null {
  if (level == null || level === "error") return level;
  if (gtoLabel === "gto_mixed" || gtoLabel === "gto_correct") return level;
  return isVerdictErrorSignal(gtoAction, actionTaken, foldPct) ? "error" : level;
}

/**
 * Score bruto 0..1 (0 = ótimo) → nível de display. Bandas espelham os cortes do engine
 * (standard ≤ 0.08 · marginal ≤ 0.18 · acima = erro). Para superfícies que só têm o score
 * agregado por sessão (RecentForm) e precisam do mesmo veredito de 3 níveis do card.
 */
export function verdictLevelFromScore(score: number | null | undefined): VerdictLevel {
  if (score == null || score <= 0.08) return "correct";
  if (score <= 0.18) return "acceptable";
  return "error";
}

/**
 * Quanto o jogador PAGA para continuar, em bb — que NÃO é o tamanho da aposta do vilão.
 *
 * `facing_bet` é o to-total do vilão e serve para identificar o nó GTO. O custo é
 * `to-total − o que o hero já tem na frente`, e os dois divergem sempre que ele já pôs
 * fichas na street: contra um open de 2bb, o BB paga 1bb. Usar o tamanho como custo
 * inflava as pot odds da tela — numa mão real do acervo, 27,2% de equity exigida numa
 * decisão que custava 5,4%.
 *
 * `??` e não `||`: um custo de 0 é legítimo (ninguém apostou) e com `||` cairia no
 * fallback — a mesma armadilha que já mordeu o `facing_size_bb` do Leak Trainer.
 * Decisão analisada antes de 2026-08-04 tem a coluna NULL e cai no `facing_bet`,
 * preservando o comportamento antigo em vez de zerar.
 */
export function custoDePagar(
  spot: { facing_to_call_bb?: number | null; facing_bet?: number | null },
): number {
  return Number(spot.facing_to_call_bb ?? spot.facing_bet ?? 0);
}

// ── Confiança da equity ESTIMADA, por street (17/08) ──────────────────────────────────────────
//
// Medida contra 1.082 showdowns reais (backend/scripts/validar_equity_com_reveals.py, mão do
// vilão revelada no SUMMARY): a MÉDIA por street é calibrada (gap médio ≈ 0), mas a CAUDA
// cresce — gap p90 do (estimado − real): preflop +0,23 · flop +0,31 · turn +0,49 · river
// +0,58. O número continua na tela (a média presta); turn e river ganham MOLDURA de baixa
// confiança: marcador "≈" e tooltip com o número medido. Regra de DISPLAY, não de veredito —
// o motor já trata equity como insumo secundário (guardas vs-random, teto de fold).
// Se o estimador mudar, re-rodar o medidor e atualizar estas constantes.
export const EQUITY_GAP_P90: Record<string, number> = {
  preflop: 0.23,
  flop: 0.31,
  turn: 0.49,
  river: 0.58,
};

/** true quando a equity estimada desta street merece a moldura de baixa confiança. */
export function equityLowConfidence(street: string | null | undefined): boolean {
  const s = (street ?? "").trim().toLowerCase();
  return s === "turn" || s === "river";
}

/** Pot odds exigidas para pagar, em fração. `potBb` já inclui a aposta enfrentada; o custo
 *  entra por fora porque ainda não foi pago. Devolve null quando não há o que pagar. */
export function potOddsExigidas(
  potBb: number | null | undefined,
  custoBb: number,
): number | null {
  const pot = Number(potBb ?? 0);
  if (!(custoBb > 0) || !(pot + custoBb > 0)) return null;
  return custoBb / (pot + custoBb);
}

/** Jogadores ainda no pote = assentos com cartas − foldados (acumulado no step). */
export function livePlayers(
  seats: Record<string, unknown> | undefined | null,
  folded: string[] | undefined | null,
): number | null {
  if (!seats) return null;
  return Object.keys(seats).length - (folded?.length ?? 0);
}

/** Multiway = postflop com 3+ jogadores no pote (solver é HU → aproximação). */
export function isMultiwayPot(isPostflop: boolean, live: number | null): boolean {
  return isPostflop && live != null && live >= 3;
}

/**
 * O +pp (margem equity − necessária) fica NEUTRO quando o veredito NÃO vem do
 * pot odds: cobertura preflop (range), estratégia do solver (effectiveGtoLabel),
 * OU quando ficaria verde (eq ≥ req) mas a ação foi marcada erro (heurística
 * "RAISE +EV vs fold" num spot que o engine manda CALL). Cor só quando pot odds
 * É a base do veredito (postflop sem solver, vs_shove).
 */
export function isPpMuted(p: {
  showAuditPreflop: boolean;
  effectiveGtoLabel: string | null | undefined;
  eq: number | null | undefined;
  reqShown: number;
  isActionOk: boolean;
}): boolean {
  const contradicts = p.eq != null && p.eq >= p.reqShown && !p.isActionOk;
  return !!p.showAuditPreflop || !!p.effectiveGtoLabel || contradicts;
}

/**
 * Qual estratégia JULGA a decisão do hero. Princípio inviolável: o veredito de UMA
 * mão vem da estratégia DESSA mão (hand_strategy do nó solved), NUNCA da ação modal
 * do range agregado (gto_strategy). O range descreve o CONJUNTO ("fold 63%" = % do
 * range inteiro que desiste); a mão diz o que fazer com ESTAS 2 cartas ("A2s raise
 * 93%"). Num nó multiway aproximado os dois divergem fortemente — julgar pelo range
 * marcava "GTO recomenda Fold" numa mão que o solver LEVANTA 93%. Postflop com
 * hand_strategy → mão; senão (preflop usa range estático; postflop sem mão) → range.
 */
export interface StratAction { action: string; frequency?: number | null; ev_bb?: number | null }
export function verdictStrategy(
  isPostflop: boolean,
  handActions: StratAction[] | null | undefined,
  rangeSorted: StratAction[],
): StratAction[] {
  if (isPostflop && handActions?.length) {
    return [...handActions].sort((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0));
  }
  return rangeSorted;
}

/**
 * De qual FONTE vem a "ação recomendada" (idealAction), por prioridade. O fix do
 * squeeze: preflop COBERTO usa o RANGE (ação dominante do hand_freq) ANTES do
 * gto_action armazenado (engine) — senão um spot coberto mostrava a ação do
 * engine em vez da do range (ex.: AA squeeze "GTO recomenda Call" em vez de Raise).
 */
export type IdealSource = "none" | "potodds" | "range" | "solver" | "engine";
export function idealActionSource(ctx: {
  preflopNoCoverage: boolean;
  isShoveFb: boolean;
  isPostflop: boolean;
  pgAvailable: boolean;
  hasGto: boolean;
}): IdealSource {
  if (ctx.preflopNoCoverage) return "none";
  if (ctx.isShoveFb) return "potodds";
  if (!ctx.isPostflop && ctx.pgAvailable) return "range";  // range ANTES de hasGto
  if (ctx.hasGto) return "solver";
  return "engine";
}

/**
 * Qualificador do bloco "Custo" do card.
 *
 * O card dizia **"desvio caro"** (`card.costCritical`) sempre que `gto_label === "gto_critical"`.
 * Mas `gto_critical` é um sinal de FREQUÊNCIA — o próprio produto já decidiu isso, e
 * `verdictLevel("gto_critical")` devolve `null` com o comentário "frequência NÃO é veredito".
 * Chamar o desvio de *caro* é uma afirmação sobre PREÇO, e ela precisa de um preço.
 *
 * Medido no acervo em 26/08: 47 decisões saíam com o veredito mais duro do produto e
 * `ev_loss_bb` NULL nas 47.
 *
 * Regra: sem custo medido, o bloco diz que o custo não foi medido. Não absolve e não acusa de
 * caro — informa o que se sabe. Com custo medido, nada muda.
 */
export function qualificadorDeCusto(args: {
  gtoLabel: string | null | undefined;
  temCusto: boolean | null | undefined;
  pp: number | null;
}): "aligned" | "minor" | "critical" | "plus" | "minus" | "unmeasured" {
  const { gtoLabel, temCusto, pp } = args;
  const afirmaPreco = gtoLabel === "gto_critical" || gtoLabel === "gto_minor_deviation";
  if (afirmaPreco && !temCusto) return "unmeasured";
  if (gtoLabel === "gto_critical") return "critical";
  if (gtoLabel === "gto_minor_deviation") return "minor";
  if (gtoLabel === "gto_correct" || gtoLabel === "gto_mixed") return "aligned";
  return pp != null && pp >= 0 ? "plus" : "minus";
}

/**
 * A qualidade ESTÁTICA da carta ("leak", "major_leak") pode aparecer no card?
 *
 * Ela é a classificação crua da mão contra a carta. O VEREDITO é outra coisa: passa pelos pisos
 * do motor (custo, direção, ICM, teto de EV) e pode concluir que aquilo não é erro. Quando os
 * dois aparecem lado a lado, o card diz "Aceitável" com um "major leak" do lado.
 *
 * Já havia um guarda para isso, mas ancorado no RÓTULO DO SOLVER (`gto_correct`/`mixed`/`minor`).
 * Ele não cobria `gto_critical` — e medido em 26/08, **as 25 contradições do torneio 72 eram
 * todas `gto_critical`**, ou seja, o guarda não suprimia nenhuma. Ancorar no veredito cobre as
 * duas famílias com uma regra só.
 *
 * (Eu mesmo levei essa contagem de 11 para 25 ao impedir a camada viva de promover verdictos —
 * o conserto certo expôs o vizinho errado.)
 */
export function mostraQualidadeEstatica(args: {
  actionQuality: string | null | undefined;
  gtoLabel: string | null | undefined;
  isError: boolean | null | undefined;
  podeFalarComoGto?: boolean | null;
}): boolean {
  const { actionQuality, gtoLabel, isError, podeFalarComoGto } = args;
  const acusa = ["leak", "major_leak"].includes(actionQuality ?? "");
  if (!acusa) return true;                       // não fala de leak: nada a suprimir
  // A palavra "leak" É linguagem de GTO. O gate que existe para proibi-la não a alcançava:
  // medido em 27/08, 17 decisões traziam `pode_falar_como_gto: false` e `major_leak` no mesmo
  // objeto, e o card mostrava as duas coisas. Um juiz de coerência achou 92 casos da família.
  if (podeFalarComoGto === false) return false;
  if (isError === false) return false;           // o veredito diz que não é erro
  return !["gto_correct", "gto_mixed", "gto_minor_deviation"].includes(gtoLabel ?? "");
}
