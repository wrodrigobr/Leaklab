/**
 * Regra de exibição do alerta de drift — marca d'água MONOTÔNICA.
 *
 * O modelo anterior guardava o dismiss numa chave derivada do `max(tournament_id)` das sessões
 * marcadas. O problema: a detecção roda numa janela de 30 dias por `imported_at`, e essa janela
 * DESLIZA sozinha. Quando o torneio mais novo da lista envelhece e sai, o `max` muda, a chave
 * muda, e o banner reaparece sem que nada tenha sido detectado — o jogador fecha hoje e o alerta
 * volta amanhã, o que ensina a ignorar o aviso (e aí ele deixa de servir pra qualquer coisa).
 *
 * Aqui guardamos UM número por usuário: o maior id de sessão em drift já dispensado. O alerta só
 * volta quando aparece uma sessão marcada com id MAIOR que esse — ou seja, um torneio importado
 * DEPOIS do dismiss. Como ids só crescem, a janela deslizar nunca reabre o alerta.
 */
export const DRIFT_SEEN_PREFIX = "leaklab_drift_seen_";

export const driftSeenKey = (userId: number | string) => `${DRIFT_SEEN_PREFIX}${userId}`;

/** Decisão pura: mostrar o alerta? `seen` é a marca d'água já dispensada (0 = nunca dispensou). */
export function shouldShowDrift(
  detected: boolean,
  latestFlaggedId: number | null | undefined,
  seen: number,
): boolean {
  if (!detected) return false;
  // Sem id (backend antigo ou sessão sem id): mostra. Perder um aviso real é pior que repeti-lo,
  // e este caminho some assim que o backend novo sobe.
  if (latestFlaggedId == null || latestFlaggedId <= 0) return true;
  return latestFlaggedId > seen;
}

export function readDriftSeen(userId: number | string | undefined): number {
  if (userId == null) return 0;
  try {
    return Number(localStorage.getItem(driftSeenKey(userId)) ?? 0) || 0;
  } catch {
    return 0;
  }
}

/** Marca como visto até `latestFlaggedId`. Nunca REGRIDE a marca d'água: se o jogador dispensou
 *  um id maior antes, um alerta antigo não pode reabrir o que já foi fechado. */
export function writeDriftSeen(userId: number | string | undefined, latestFlaggedId: number | null | undefined): void {
  if (userId == null) return;
  try {
    const atual = readDriftSeen(userId);
    const novo = Math.max(atual, Number(latestFlaggedId) || 0);
    localStorage.setItem(driftSeenKey(userId), String(novo));
  } catch { /* localStorage indisponível — o alerta reaparece, sem quebrar a página */ }
}
