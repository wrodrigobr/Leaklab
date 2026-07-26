import { decisionSeverity, type VerdictLevel } from "@/lib/cardLogic";
import type { TournamentDecision } from "@/lib/api";

/**
 * Régua ÚNICA de agrupamento/classificação de mãos para os filtros.
 *
 * Por que existe: a lista de mãos (TournamentDetail) e a navegação do Replayer precisam
 * concordar sobre "esta mão é um erro?". Se cada tela reimplementasse a regra, o filtro
 * "erros" da lista abriria um replay que pula mãos diferentes — a mesma classe de bug
 * (duas fontes divergentes) que já mordeu o menu do trainer e a legenda de ranges.
 *
 * A severidade vem de `decisionSeverity` (cardLogic), que honra multiway=informativo.
 */

export type HandResultFilter = "all" | "correct" | "attention" | "error" | "pending";

/** Resumo por mão — o mínimo que os filtros precisam. */
export interface HandFilterSummary {
  id: string;
  category: VerdictLevel;        // correct | acceptable | error (severidade EFETIVA)
  hasPostflop: boolean;
  gtoLabel: string | null;
  worst: TournamentDecision;     // a decisão "pior" da mão (fonte dos demais campos)
  decisions: TournamentDecision[];
}

const SEV_RANK: Record<VerdictLevel, number> = { correct: 0, acceptable: 1, error: 2 };

/**
 * Agrupa decisões por mão e elege a decisão "pior" pela severidade EFETIVA (desempate por
 * score/magnitude). É a mesma eleição que a lista de mãos usa para o chip de veredito.
 * Preserva a ordem de 1ª aparição das mãos (ordem cronológica do torneio).
 */
export function summarizeHandsForFilter(decisions: TournamentDecision[]): HandFilterSummary[] {
  const map = new Map<string, TournamentDecision[]>();
  decisions.forEach((d) => {
    const key = d.hand_id || `hand-${d.id}`;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(d);
  });

  const out: HandFilterSummary[] = [];
  map.forEach((decs, id) => {
    const worstEntry = [...decs]
      .map((d) => ({ d, sev: decisionSeverity(d) }))
      .sort((a, b) => (SEV_RANK[b.sev] - SEV_RANK[a.sev]) || (b.d.score - a.d.score))[0];
    out.push({
      id,
      category: worstEntry.sev,
      hasPostflop: decs.some((d) => d.street === "flop" || d.street === "turn" || d.street === "river"),
      gtoLabel: worstEntry.d.gto_label ?? null,
      worst: worstEntry.d,
      decisions: decs,
    });
  });
  return out;
}

/**
 * A mão passa no filtro de resultado?
 *
 * "pending" = postflop analisado pelo ENGINE e não pelo solver (multiway, stack curto,
 * fora da cobertura). NÃO é "aguardando solver" — a maioria nunca será solvada por design.
 */
export function matchesResultFilter(
  h: Pick<HandFilterSummary, "category" | "hasPostflop" | "gtoLabel">,
  filter: HandResultFilter,
): boolean {
  switch (filter) {
    case "all":       return true;
    case "correct":   return h.category === "correct";
    case "attention": return h.category === "acceptable";
    case "error":     return h.category === "error";
    case "pending":   return h.hasPostflop && !h.gtoLabel;
    default:          return true;
  }
}

/** Ids das mãos que passam no filtro, em ordem cronológica. Usado pela navegação do Replayer. */
export function filterHandIds(decisions: TournamentDecision[], filter: HandResultFilter): string[] {
  if (filter === "all") {
    const seen = new Set<string>();
    const ids: string[] = [];
    decisions.forEach((d) => {
      if (d.hand_id && !seen.has(d.hand_id)) { seen.add(d.hand_id); ids.push(d.hand_id); }
    });
    return ids;
  }
  return summarizeHandsForFilter(decisions)
    .filter((h) => matchesResultFilter(h, filter))
    .map((h) => h.id);
}

/** Um filtro válido? (sanitiza o parâmetro que vem da URL) */
export function parseResultFilter(raw: string | null | undefined): HandResultFilter {
  const v = (raw ?? "").toLowerCase();
  return (["correct", "attention", "error", "pending"] as const).includes(v as never)
    ? (v as HandResultFilter)
    : "all";
}
