export type GtoLabel = 'gto_correct' | 'gto_mixed' | 'gto_minor_deviation' | 'gto_critical';

function normAction(a: string): string {
  const s = (a ?? '').toLowerCase().replace(/[-_ ]/g, '');
  // shove / jam / all-in são a MESMA ação. A strategy do solver usa 'allin',
  // mas a ação jogada vem como 'shove' — sem unificar, um shove correto não
  // casa com 'allin 96%' e cai em gto_critical (falso "DESVIO CRÍTICO").
  if (s === 'shove' || s === 'jam' || s === 'allin') return 'allin';
  return s;
}

/**
 * Derives the effective GTO label from live strategy frequencies.
 * When strategy is available it takes precedence over the stored gto_label
 * (stored value may be stale if the solver node was updated after import).
 */
export function computeEffectiveGtoLabel(
  strategy: Array<{ action: string; frequency: number }> | null | undefined,
  storedGtoLabel: string | null | undefined,
  playedAction: string | null | undefined,
): GtoLabel | null {
  if (!strategy?.length) return (storedGtoLabel as GtoLabel) ?? null;
  const playedNorm = normAction(playedAction ?? '');
  const freq =
    strategy.find(s => {
      const n = normAction(s.action);
      return n === playedNorm || playedNorm.startsWith(n) || n.startsWith(playedNorm);
    })?.frequency ?? 0;
  if (freq >= 0.60) return 'gto_correct';
  if (freq >= 0.30) return 'gto_mixed';
  if (freq >= 0.10) return 'gto_minor_deviation';
  return 'gto_critical';
}
