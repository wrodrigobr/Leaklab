"""
icm.py — Independent Chip Model (ICM).

`calculate_icm()` é **vendorizado verbatim** do PokerKit
(https://github.com/uoftcprg/pokerkit — `pokerkit/analysis.py`), biblioteca
da University of Toronto Computer Poker Research Group, sob licença **MIT**.
Mantido idêntico ao upstream (inclusive os doctests) para facilitar auditoria
e futuras atualizações.

    PokerKit © University of Toronto Computer Poker Research Group — MIT License

`hero_icm_equity()` é nosso wrapper: dado os stacks de todos os jogadores e a
posição do hero, devolve a equity ICM do hero (fração do prize pool), sua
fração de fichas e a "ICM tax" (chip% − equity%).
"""
from __future__ import annotations

from collections.abc import Iterable
from itertools import permutations
from typing import Optional


# ── Vendorizado do PokerKit (MIT) — NÃO modificar; manter sincronizado ────────
def calculate_icm(
        payouts: Iterable[float],
        chips: Iterable[float],
) -> tuple[float, ...]:
    """Calculate the independent chip model (ICM) values.

    >>> calculate_icm([70, 30], [50, 30, 20])  # doctest: +ELLIPSIS
    (45.17..., 32.25, 22.57...)
    >>> calculate_icm([50, 30, 20], [25, 87, 88])  # doctest: +ELLIPSIS
    (25.69..., 37.08..., 37.21...)
    >>> calculate_icm([50, 30, 20], [21, 89, 90])  # doctest: +ELLIPSIS
    (24.85..., 37.51..., 37.63...)
    >>> calculate_icm([50, 30, 20], [198, 1, 1])  # doctest: +ELLIPSIS
    (49.79..., 25.10..., 25.10...)

    :param payouts: The payouts.
    :param chips: The players' chips.
    :return: The ICM values.
    """
    payouts = tuple(payouts)
    chips = tuple(chips)
    chip_sum = sum(chips)
    chip_percentages = [chip / chip_sum for chip in chips]
    icms = [0.0] * len(chips)

    for player_indices in permutations(range(len(chips)), len(payouts)):
        probability = 1.0
        denominator = 1.0

        for player_index in player_indices:
            chip_percentage = chip_percentages[player_index]
            probability *= chip_percentage / denominator
            denominator -= chip_percentage

        for payout, player_index in zip(payouts, player_indices):
            icms[player_index] += payout * probability

    return tuple(icms)
# ── fim do trecho vendorizado ─────────────────────────────────────────────────


# Curva de pagamento padrão (top-heavy) para a mesa final. Pesos relativos;
# normalizados em runtime. payouts reais não vêm no hand history — esta curva é
# uma aproximação razoável para estimar a *forma* da pressão ICM (stack grande
# vs. short stack), não o valor monetário exato.
_FT_PAYOUT_WEIGHTS = [30.0, 20.0, 14.5, 11.0, 8.5, 6.5, 4.5, 3.0, 2.0]

# Teto de pagamentos modelados — limita o custo combinatório de
# permutations(P, K) no hot path (top-6 já captura ~toda a equity ICM).
_MAX_PAID = 6


def standard_payouts(n_players: int) -> list[float]:
    """Curva de pagamento padrão normalizada (soma 1.0) para `n_players`
    pagos, limitada a `_MAX_PAID` casas (custo combinatório)."""
    k = max(1, min(n_players, _MAX_PAID))
    weights = _FT_PAYOUT_WEIGHTS[:k]
    total = sum(weights)
    return [w / total for w in weights]


def hero_icm_equity(
        chips: list[float],
        hero_index: int,
        payouts: Optional[list[float]] = None,
) -> Optional[dict]:
    """ICM equity do hero dada a distribuição de fichas da mesa.

    Sem `payouts`, usa a curva padrão normalizada (`standard_payouts`).
    Devolve `{equity_pct, chip_pct, tax_pct}` (em %), ou None se os dados
    forem insuficientes.
    """
    if not chips or hero_index < 0 or hero_index >= len(chips):
        return None
    chip_sum = sum(chips)
    if chip_sum <= 0:
        return None
    if payouts is None:
        payouts = standard_payouts(len(chips))

    icms = calculate_icm(payouts, chips)          # soma == soma(payouts) == 1.0
    equity_pct = icms[hero_index] * 100.0
    chip_pct = chips[hero_index] / chip_sum * 100.0
    return {
        'equity_pct': round(equity_pct, 2),
        'chip_pct':   round(chip_pct, 2),
        # tax_pct = chip% − equity%:
        #   >0 (equity < fichas): típico de big stacks — fichas valem menos que a
        #      fração por retornos decrescentes (risk premium ao arriscar a pilha);
        #   <0 (equity > fichas): típico de short stacks — prêmio de sobrevivência
        #      (o piso de premiação faz a equity superar a fração de fichas).
        'tax_pct':    round(chip_pct - equity_pct, 2),
    }
