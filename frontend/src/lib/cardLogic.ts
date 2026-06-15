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
export const VERDICT_META: Record<VerdictLevel, { icon: string; textCls: string; chipCls: string; i18nKey: string }> = {
  correct:    { icon: "✓", textCls: "text-emerald-400", chipCls: "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/30", i18nKey: "verdict.correct" },
  acceptable: { icon: "◎", textCls: "text-sky-400",     chipCls: "bg-sky-500/10 text-sky-400 ring-1 ring-sky-500/30",         i18nKey: "verdict.acceptable" },
  error:      { icon: "✗", textCls: "text-red-400",     chipCls: "bg-red-500/10 text-red-400 ring-1 ring-red-500/30",         i18nKey: "verdict.error" },
};

/**
 * Severidade interna (`label`) → nível de display **clampando** para "error" quando não
 * classificável mas marcado como erro. Conveniência p/ superfícies que só têm o `label`.
 */
export function verdictLevelOrError(label: string | null | undefined): VerdictLevel {
  return verdictLevel(label) ?? "error";
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
