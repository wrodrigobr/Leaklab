/**
 * As salas suportadas, em UM lugar.
 *
 * Antes de 11/09 esta lista existia copiada em QUATRO pontos do front (o guia de exportação, os
 * chips do dropzone, a faixa de redes da landing e a tabela de `/docs`) e só dois tinham guarda.
 * Quando o PartyPoker entrou, o logotipo e o filtro de torneios já funcionavam sozinhos e a copy
 * ficou para trás em três idiomas — que é como o produto passa a dizer que não suporta uma sala
 * que ele suporta.
 *
 * Sala nova entra AQUI. Os guardas em `EmptyDashboard.test`, `HandExportGuide.test` e
 * `landingNetworks.test` leem este arquivo e cobram a copy nas três locales.
 */

/** Ordem de exibição: é a ordem em que a lista aparece no guia e nos chips. */
export const SALAS_SUPORTADAS = ["pokerstars", "ggpoker", "acr", "coinpoker", "partypoker"] as const;

export type Sala = (typeof SALAS_SUPORTADAS)[number];

/**
 * Salas que NÃO oferecem o resumo do torneio para download.
 *
 * Sem o resumo não há colocação, prêmio, ROI, número de inscritos nem detecção de mesa final
 * (que é onde o ICM muda a decisão certa). A tela DECLARA isso na coluna de prêmio em vez de
 * deixar um traço sem explicação, e não oferece um upload que não existe.
 *
 * PartyPoker: o fluxo de export da sala é `My Game -> Export Hands` e entrega só mãos. Conferido
 * também no arquivo real do Rullian: zero linha de colocação ou prêmio em 157 mil linhas.
 */
export const SALAS_SEM_RESULTADO = ["partypoker"] as const;

export const salaSemResultado = (site: string | null | undefined): boolean =>
  (SALAS_SEM_RESULTADO as readonly string[]).includes((site ?? "").toLowerCase());
