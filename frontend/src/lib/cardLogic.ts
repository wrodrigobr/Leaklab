// Regras PURAS de display do Decision Card, extraídas do Replayer.tsx para serem
// testáveis (vitest). Cada uma codifica um fix das varreduras — travar contra
// regressão silenciosa. O Replayer importa e usa estas funções (não duplica).
export { computeEffectiveGtoLabel } from "./gtoUtils";

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
