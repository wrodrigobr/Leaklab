import type { HandResultFilter } from "@/lib/handFilter";

/**
 * A playlist do leak: percorrer no replayer as mãos de UM leak, e não as do torneio.
 *
 * ── O que originou (16/09) ────────────────────────────────────────────────────────────────────
 *
 * A lista do card "Leaks por custo" abria o replayer numa mão, e ali a navegação voltava a ser
 * a do TORNEIO: apertar "próxima" levava para a mão seguinte daquele torneio, que não tem nada a
 * ver com o leak. Quem estudava as 12 mãos de um leak voltava ao dashboard 12 vezes.
 *
 * ── Por que isto é um módulo, e não um `if` dentro do Replayer ────────────────────────────────
 *
 * As mãos de um leak ATRAVESSAM torneios: no leak medido no banco do dono, 12 mãos em 8
 * torneios. A navegação do replayer era presa a um torneio (o `t=` da URL), então cada link de
 * mão precisa levar o torneio DAQUELA mão. A regra de montar esse link é a coisa que, errada,
 * manda o jogador para uma mão que não existe naquele torneio, e o Replayer não tem teste que o
 * monte (1.100 linhas, dez dependências de rede). Aqui ela é pura e coberta.
 */

export interface LeakSpot {
  street: string;
  actionTaken: string;
  bestAction: string;
}

/**
 * `"flop:fold:call"` → o spot. Qualquer outra coisa devolve `null`, e aí a navegação cai na do
 * torneio, que é o comportamento de sempre: URL malformada não pode quebrar o replayer.
 */
export function parseLeakSpot(param: string | null | undefined): LeakSpot | null {
  const partes = (param ?? "").split(":");
  if (partes.length !== 3 || !partes.every((p) => p.trim())) return null;
  return { street: partes[0], actionTaken: partes[1], bestAction: partes[2] };
}

/**
 * A chave do leak na URL. Montada aqui porque ela agora nasce em dois lugares: a lista do
 * dashboard (que abre a playlist) e a navegação ENTRE leaks dentro do replayer. Duas formas de
 * montar a mesma chave é a receita de uma delas escapar um caractere e a outra não.
 */
export function chaveDoLeak(spot: { street: string; action_taken: string; best_action: string }): string {
  return `${spot.street}:${spot.action_taken}:${spot.best_action}`;
}

/** O leak aberto é este? Compara pelos três campos que o identificam, e não pela string. */
export function mesmoLeak(
  a: LeakSpot | null | undefined,
  b: { street: string; action_taken: string; best_action: string } | null | undefined,
): boolean {
  if (!a || !b) return false;
  return a.street === b.street && a.actionTaken === b.action_taken && a.bestAction === b.best_action;
}

/**
 * O link de outra mão do MESMO contexto de navegação.
 *
 * Três coisas que ele não pode esquecer, e cada uma já foi defeito em alguma versão deste
 * replayer: o torneio da mão (na playlist do leak não é o da URL), o modo (coach, aluno) e o
 * filtro `&f=`. E o próprio leak, senão a segunda mão da playlist abre sem playlist e o jogador
 * cai de volta na navegação do torneio no meio do estudo.
 */
export function hrefDaMao(opts: {
  mao: string;
  tournamentId: string;
  /** mão -> torneio de origem; vazio fora da playlist de leak */
  torneioDaMao?: Record<string, number>;
  studentId?: number | null;
  coachMode?: boolean;
  resultFilter?: HandResultFilter;
  leakParam?: string | null;
  leakLastN?: number | null;
}): string {
  const { mao, tournamentId, torneioDaMao = {}, studentId, coachMode,
          resultFilter = "all", leakParam, leakLastN } = opts;
  const leak = parseLeakSpot(leakParam);
  const tid = String(torneioDaMao[mao] ?? tournamentId);
  return `/replayer?t=${tid}&h=${mao}`
    + (studentId ? `&student=${studentId}` : "")
    + (coachMode ? "&coach=1" : "")
    + (resultFilter !== "all" ? `&f=${resultFilter}` : "")
    + (leak && leakParam ? `&leak=${encodeURIComponent(leakParam)}` : "")
    + (leak && leakLastN != null ? `&ln=${leakLastN}` : "");
}

/**
 * Qual lista manda na navegação, e a resposta DECLARADA para a tela dizer.
 *
 * A precedência não é arbitrária: a playlist do leak vem de outra fonte (a rota do leak, entre
 * torneios) e não pode ser interseccionada com o filtro `&f=` do torneio, porque as mãos nem são
 * do mesmo torneio. Então ela manda sozinha, e a tela DIZ que está numa playlist de leak.
 *
 * A playlist do coach, que é de um torneio só, continua se cruzando com o `&f=` como desde
 * 14/08, quando ela substituiu o filtro calada e o jogador pousou numa mão Aceitável com a
 * barra ainda rotulada "só os erros".
 */
export type FonteDaNavegacao = "leak" | "coach" | "torneio";

export function fonteDaNavegacao(opts: { temLeak: boolean; coachMode: boolean }): FonteDaNavegacao {
  if (opts.temLeak) return "leak";
  if (opts.coachMode) return "coach";
  return "torneio";
}
