import type { EscopoDoDashboard, Tournament } from "@/lib/api";

/** Eixo de tempo de um torneio: data de JOGO, e a de importação só quando o histórico não
 *  traz a de jogo. O mesmo `COALESCE(played_at, imported_at)` que o backend usa em
 *  `_build_tournament_filter` (AY-4): os KPIs do dashboard e os cards têm de cortar o MESMO
 *  conjunto quando o filtro diz "últimos N". */
export function dataDoTorneio(t: Pick<Tournament, "played_at" | "imported_at">): string {
  return t.played_at || t.imported_at || "";
}

/**
 * Os torneios que o ESCOPO seleciona, mais recentes primeiro.
 *
 * ── O que ela espelha ─────────────────────────────────────────────────────────────────────────
 *
 * É o gêmeo no cliente de `_build_tournament_filter` do servidor: a LISTA de torneios da tela e
 * os CARDS têm de cortar o mesmo conjunto, senão a página mostra dois escopos sob uma faixa que
 * declara um. Por isso as três dimensões existem aqui também, com as mesmas regras.
 *
 * `n` cru ainda é aceito porque era o contrato antigo (número de torneios, `0` = todos).
 *
 * ── As cicatrizes que ela carrega ─────────────────────────────────────────────────────────────
 *
 * Substitui `tourns.slice(-n)` (06/09): a lista chega ordenada por importação DESC, então o FIM
 * dela são os mais antigos — o filtro "últimos 30" somava os 30 mais VELHOS. E como a lista vinha
 * capada em 50, "Histórico" eram 50.
 *
 * No escopo de MÃOS o torneio que cruza o teto entra INTEIRO, igual ao servidor: cortar mão no
 * meio de um torneio quebraria a soma por torneio que toda tela faz.
 */
// `hands_count` OPCIONAL no tipo: o escopo de maos precisa dele, mas fixture de teste e
// chamador antigo passam so as datas. Exigir quebraria chamador que nao usa a dimensao nova.
export function ultimosTorneios<
  T extends Pick<Tournament, "played_at" | "imported_at"> & { hands_count?: number | null },
>(
  tourns: T[],
  escopo: EscopoDoDashboard | number | null | undefined,
): T[] {
  const ordenados = [...tourns].sort((a, b) => dataDoTorneio(b).localeCompare(dataDoTorneio(a)));
  if (escopo == null) return ordenados;
  if (typeof escopo === "number") return escopo ? ordenados.slice(0, escopo) : ordenados;

  if (escopo.tipo === "torneios") return escopo.n ? ordenados.slice(0, escopo.n) : ordenados;

  if (escopo.tipo === "maos") {
    const saida: T[] = [];
    let antes = 0;
    for (const t of ordenados) {
      if (antes >= escopo.n) break;
      saida.push(t);
      antes += t.hands_count ?? 0;
    }
    return saida;
  }

  // a faixa é inclusiva nos dois extremos, e o eixo é o mesmo `COALESCE` do servidor
  return ordenados.filter((t) => {
    const d = dataDoTorneio(t).slice(0, 10);
    return !!d && d >= escopo.de && d <= escopo.ate;
  });
}
