"""
postflop_range_evaluator.py
Avalia spots postflop (flop/turn/river) com lógica própria,
separada do preflop_range_evaluator.

Princípio central: postflop é sempre contextual.
  - Sem aposta: check é a ação padrão defensável
  - Com aposta: decisão baseada em equity vs pot odds ajustado
  - Range zone reflete força estimada da mão, não tier de range pré-flop
"""
from __future__ import annotations
from .models import HandState, RangeEvaluation


def evaluate_postflop_range(state: HandState) -> RangeEvaluation:
    """
    Retorna RangeEvaluation para spots postflop.
    Recebe HandState com pot_odds_equity e estimated_hand_equity já calculados
    pelo street_math_engine.
    """
    pot_odds = _pot_odds(state)
    equity   = _equity(state)
    facing   = state.facing_size > 0

    if facing:
        return _eval_facing_bet(pot_odds, equity, state)
    else:
        return _eval_no_bet(equity, state)


# ── Cenário: hero enfrenta aposta ─────────────────────────────────────────────

def _eval_facing_bet(pot_odds: float | None,
                     equity: float | None,
                     state: HandState) -> RangeEvaluation:
    """
    Hero recebeu bet/raise. Decide entre call, fold, raise.

    Lógica:
      Se equity bem acima de pot_odds → call
      Se equity bem abaixo de pot_odds → fold
      Se próximo (close spot) → call como rec, fold como alt
    """
    if pot_odds is None or equity is None:
        # Sem dados matemáticos: spot borderline, call defensável
        return RangeEvaluation(
            recommended_primary_action='call',
            alternative_actions=['fold'],
            range_zone='borderline_range',
            confidence=0.50,
            mix_weight=0.30,
        )

    diff = equity - pot_odds

    # Mão forte: equity confortável acima
    if diff >= 0.05:
        zone = _zone_from_equity(equity)
        return RangeEvaluation(
            recommended_primary_action='call',
            alternative_actions=['raise'] if equity > 0.55 else [],
            range_zone=zone,
            confidence=0.75,
            mix_weight=0.05,
        )

    # Mão fraca: equity claramente abaixo
    if diff <= -0.04:
        zone = _zone_from_equity(equity)
        return RangeEvaluation(
            recommended_primary_action='fold',
            alternative_actions=[],
            range_zone=zone,
            confidence=0.70,
            mix_weight=0.05,
        )

    # Close spot: dentro da margem de erro (±4%)
    zone = 'borderline_range'
    return RangeEvaluation(
        recommended_primary_action='call',
        alternative_actions=['fold'],
        range_zone=zone,
        confidence=0.55,
        mix_weight=0.40,
    )


# ── Cenário: sem aposta (hero age primeiro ou após checks) ────────────────────

def _eval_no_bet(equity: float | None,
                 state: HandState) -> RangeEvaluation:
    """
    Sem aposta na street atual. Hero pode check ou bet.

    Princípio: check é sempre defensável quando não há aposta.
    Bet recomendado quando equity forte OU quando há draw presente
    com equity ajustada suficiente para semi-bluff.
    """
    if equity is None:
        return RangeEvaluation(
            recommended_primary_action='check',
            alternative_actions=['bet'],
            range_zone='borderline_range',
            confidence=0.60,
            mix_weight=0.20,
        )

    # Verificar se há draw presente e ajuste de equity
    draw_profile  = state.metadata.get('draw_profile', 'none')
    equity_adj    = state.metadata.get('equity_adjustment', 0.0)
    has_draw      = draw_profile not in ('none', '', None)

    # Mão forte: bet para construir pot / proteger
    if equity >= 0.55:
        return RangeEvaluation(
            recommended_primary_action='bet',
            alternative_actions=['check'],
            range_zone='core_range',
            confidence=0.65,
            mix_weight=0.25,
        )

    # Semi-bluff com draw: bet aceitável se equity ajustada >= 0.38
    if has_draw and equity_adj > 0 and equity >= 0.38:
        return RangeEvaluation(
            recommended_primary_action='bet',
            alternative_actions=['check'],
            range_zone='borderline_range',
            confidence=0.55,
            mix_weight=0.40,
        )

    # Mão média sem draw forte: check defensável
    if equity >= 0.40:
        return RangeEvaluation(
            recommended_primary_action='check',
            alternative_actions=['bet'],
            range_zone='borderline_range',
            confidence=0.60,
            mix_weight=0.35,
        )

    # Mão fraca com draw fraco (BDFD/BDSD apenas): check preferível
    if has_draw and equity_adj > 0:
        return RangeEvaluation(
            recommended_primary_action='check',
            alternative_actions=['bet'],
            range_zone='borderline_range',
            confidence=0.55,
            mix_weight=0.45,
        )

    # Mão fraca sem draw: check é o padrão
    return RangeEvaluation(
        recommended_primary_action='check',
        alternative_actions=[],
        range_zone='outside_range',
        confidence=0.65,
        mix_weight=0.10,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _zone_from_equity(equity: float) -> str:
    """Range zone baseada na força estimada da mão."""
    if equity >= 0.50:
        return 'core_range'
    if equity >= 0.35:
        return 'borderline_range'
    return 'outside_range'


def _pot_odds(state: HandState) -> float | None:
    """Calcula pot odds a partir do HandState."""
    if state.facing_size <= 0:
        return None
    total = state.pot_size + state.facing_size
    if total <= 0:
        return None
    return round(state.facing_size / total, 4)


def _equity(state: HandState) -> float | None:
    """Extrai equity estimada do metadata se disponível, senão None."""
    # O street_math_engine já calculou via build_math_snapshot
    # O valor chega via metadata injetado pelo pipeline
    return state.metadata.get('estimated_equity')
