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
    Bet recomendado apenas quando equity é suficientemente forte dado o contexto.

    Calibrado contra GTO Wizard MTTGeneralV2: o threshold base 0.55 causava
    over-betting sistemático (88% dos bets eram erros vs GTO). Os thresholds
    corretos dependem de posição e profundidade de stack:

    - OOP (BB/SB): range capado preflop (sem 3-bets), bet raramente lucrativo.
      Threshold +0.06 vs IP.
    - Stack curto (<= 35bb): SPR baixo → bet compromete stack.
      Threshold +0.05 adicional.
    - Semi-bluff: apenas draws fortes (FD/OESD, equity_adj >= 0.10) justificam
      bet. Backdoors (BDFD/BDSD) não — eles são motivo para check-and-realize.
    """
    if equity is None:
        return RangeEvaluation(
            recommended_primary_action='check',
            alternative_actions=['bet'],
            range_zone='borderline_range',
            confidence=0.60,
            mix_weight=0.20,
        )

    draw_profile = state.metadata.get('draw_profile', 'none')
    equity_adj   = float(state.metadata.get('equity_adjustment', 0.0) or 0.0)
    stack_bb     = float(getattr(state, 'effective_stack_bb', 100.0) or 100.0)
    position     = (getattr(state, 'position', '') or '').upper()
    is_oop       = position in ('BB', 'SB')

    # Threshold base para bet (GTO-calibrado)
    # Deep (> 60bb): 0.65  |  Medium (35-60bb): 0.68  |  Short (<= 35bb): 0.72
    if stack_bb <= 35:
        bet_threshold  = 0.72
        draw_threshold = 0.48
    elif stack_bb <= 60:
        bet_threshold  = 0.68
        draw_threshold = 0.44
    else:
        bet_threshold  = 0.65
        draw_threshold = 0.42

    # OOP penalty: range capado → mais checking, menos betting
    if is_oop:
        bet_threshold  += 0.06
        draw_threshold += 0.04

    # Mão forte: bet justificado (top pair forte+, overpair, two pair+, draw combo)
    if equity >= bet_threshold:
        return RangeEvaluation(
            recommended_primary_action='bet',
            alternative_actions=['check'],
            range_zone='core_range',
            confidence=0.65,
            mix_weight=0.25,
        )

    # Semi-bluff: apenas draws fortes (FD=0.15, OESD=0.17).
    # GUT+BDFD (0.14), BDFD+BDSD (0.10) ficam abaixo — check.
    has_strong_draw = equity_adj >= 0.15
    if has_strong_draw and equity >= draw_threshold:
        return RangeEvaluation(
            recommended_primary_action='bet',
            alternative_actions=['check'],
            range_zone='borderline_range',
            confidence=0.55,
            mix_weight=0.40,
        )

    # Mão média ou draw fraco: check defensável
    if equity >= 0.40 or (draw_profile not in ('none', '', None) and equity_adj > 0):
        return RangeEvaluation(
            recommended_primary_action='check',
            alternative_actions=['bet'],
            range_zone='borderline_range',
            confidence=0.60,
            mix_weight=0.35,
        )

    # Mão fraca sem draw relevante: check puro
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
