/**
 * Data vinda da API — o formato muda com o backend, e o front não pode assumir um.
 *
 * O bug que originou ("Invalid Date" no histórico de relatórios): o Flask serializa `datetime` do
 * Postgres no formato HTTP, `"Tue, 28 Jul 2026 10:21:26 GMT"`, enquanto o SQLite devolve a coluna
 * como string crua, `"2026-07-28 10:21:26"`. O código assumia o segundo e fazia
 * `replace(" ", "T") + "Z"` — que sobre o primeiro produz lixo.
 *
 * Pior: o dev roda SQLite e a produção roda Postgres, então o caminho quebrado é justamente o que
 * não se testa localmente. É a mesma família do `fetchone()[0]` e do bool/int no SQL.
 *
 * A ORDEM importa, e a primeira versão daqui errou nela: tentar `new Date(raw)` primeiro parece
 * seguro, mas o V8 ACEITA `"2026-07-28 10:21:26"` e o interpreta como hora LOCAL. Como o backend
 * grava em UTC, a data saía deslocada pelo fuso — 10:21 em UTC-3 virava 13:21, e perto da
 * meia-noite mostrava o dia errado. Erro silencioso, com número plausível na tela.
 *
 * Por isso o formato ingênuo (sem fuso) é detectado ANTES e tratado como UTC explicitamente. O
 * parse direto fica para RFC 1123 e ISO com fuso, onde a informação de zona está no próprio dado.
 */
const _NAIVE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?$/;

export function parseApiDate(raw: string | null | undefined): Date | null {
  if (!raw) return null;
  const s = String(raw).trim();

  if (_NAIVE.test(s)) {
    // Sem fuso no dado → é UTC por convenção do backend. Microssegundos do Postgres cortados
    // porque `Date` só entende milissegundos.
    const utc = new Date(s.replace(" ", "T").replace(/\.\d+$/, "") + "Z");
    return Number.isNaN(utc.getTime()) ? null : utc;
  }

  const direto = new Date(s);
  return Number.isNaN(direto.getTime()) ? null : direto;
}

/** Data local formatada, ou `null` quando não dá para ler — o chamador decide o que mostrar.
 *  Devolver a string crua aqui esconderia o problema atrás de um texto plausível. */
export function formatApiDate(raw: string | null | undefined, locale?: string): string | null {
  const d = parseApiDate(raw);
  return d ? d.toLocaleDateString(locale) : null;
}
