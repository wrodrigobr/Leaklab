import type { Tournament } from "@/lib/api";

/** Eixo de tempo de um torneio: data de JOGO, e a de importação só quando o histórico não
 *  traz a de jogo. O mesmo `COALESCE(played_at, imported_at)` que o backend usa em
 *  `_build_tournament_filter` (AY-4): os KPIs do dashboard e os cards têm de cortar o MESMO
 *  conjunto quando o filtro diz "últimos N". */
export function dataDoTorneio(t: Pick<Tournament, "played_at" | "imported_at">): string {
  return t.played_at || t.imported_at || "";
}

/**
 * Os N torneios mais RECENTES por data de jogo; `n` 0/null = todos.
 *
 * Substitui `tourns.slice(-n)` (06/09): a lista chega ordenada por importação DESC, então o
 * FIM dela são os mais antigos, não os mais recentes — o filtro "últimos 30" somava os 30
 * mais velhos do que tinha chegado. E como a lista vinha capada em 50, "Histórico" eram 50.
 */
export function ultimosTorneios<T extends Pick<Tournament, "played_at" | "imported_at">>(
  tourns: T[],
  n: number | null | undefined,
): T[] {
  const ordenados = [...tourns].sort((a, b) => dataDoTorneio(b).localeCompare(dataDoTorneio(a)));
  return n ? ordenados.slice(0, n) : ordenados;
}
