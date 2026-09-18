/**
 * O ESCOPO do dashboard: o tipo, os tetos, e a única escrita que o transforma em query.
 *
 * ── Por que ele mora FORA do `api.ts` (18/09) ─────────────────────────────────────────────────
 *
 * Nasceu dentro do `api.ts`, junto das funções que o usam. Quebrou o `Index.onboarding.test.tsx`,
 * que substitui o módulo inteiro da API por um dublê: as funções o dublê resolve, mas as
 * CONSTANTES não -- "No TETO_DE_MAOS_DO_ESCOPO export is defined on the @/lib/api mock".
 *
 * O erro era de lugar, e não do teste. Constante e tipo não são chamada de rede: pô-los no módulo
 * de rede obriga todo dublê da API a conhecê-los, e o próximo teste que mockar a API quebra do
 * mesmo jeito. Aqui eles não dependem de nada, e `api.ts` os reexporta para os imports existentes
 * seguirem valendo.
 *
 * ── Por que a query sai de UMA função ─────────────────────────────────────────────────────────
 *
 * O dashboard tem 23 chamadas que carregam o escopo, e o fragmento `last_n=${...}` estava escrito
 * A MÃO 24 vezes. Se UMA ficar de fora, a tela mostra números de escopos diferentes sob uma faixa
 * que declara um só -- o defeito que o dono pediu para não ter ("Garanta que o Dashboard vai ser
 * atualizado com estes filtros"). Há varredura exigindo que ninguém monte o fragmento por conta.
 */

/**
 * Os tetos do escopo. Eles vivem TAMBÉM no servidor (`TETO_DE_MAOS_DO_ESCOPO` e
 * `MESES_MAXIMOS_DO_ESCOPO`, em `database/repositories.py`), e divergir seria calado: a tela
 * ofereceria uma faixa que o servidor apara sem avisar, e o jogador veria um número que não
 * corresponde ao que pediu. Há guarda em `test_escopo_do_dashboard.py` cruzando os dois lados.
 *
 * O teto é em MÃOS porque é nelas que o custo da consulta cresce: seis meses de um grinder pesam
 * mais que dois anos de um recreativo. O de meses é só para o seletor não oferecer 2019 a quem
 * começou este ano.
 */
export const TETO_DE_MAOS_DO_ESCOPO = 30000;
export const MESES_MAXIMOS_DO_ESCOPO = 12;

export type EscopoDoDashboard =
  /** `n` torneios mais recentes. `0` é HISTÓRICO genuíno, e não "sem filtro". */
  | { tipo: "torneios"; n: number }
  /** as `n` mãos mais recentes. O servidor apara em 30 mil. */
  | { tipo: "maos"; n: number }
  /** a faixa de datas de JOGO, inclusiva nos dois extremos. */
  | { tipo: "periodo"; de: string; ate: string };

/** O escopo em parâmetros de query. Vazio quando não há escopo. */
export function queryDoEscopo(escopo?: EscopoDoDashboard | number | null): string {
  if (escopo == null) return "";
  // número cru ainda é aceito: o `last_n` é contrato antigo e há chamador que passa o número
  if (typeof escopo === "number") return `last_n=${escopo}`;
  if (escopo.tipo === "torneios") return `last_n=${escopo.n}`;
  if (escopo.tipo === "maos") return `maos=${escopo.n}`;
  return `de=${encodeURIComponent(escopo.de)}&ate=${encodeURIComponent(escopo.ate)}`;
}

/** A URL com o escopo pendurado, escolhendo `?` ou `&` pela URL e não pelo chamador. */
export function comEscopo(url: string, escopo?: EscopoDoDashboard | number | null): string {
  const q = queryDoEscopo(escopo);
  if (!q) return url;
  return url + (url.includes("?") ? "&" : "?") + q;
}
