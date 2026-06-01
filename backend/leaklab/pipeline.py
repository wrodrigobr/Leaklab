from __future__ import annotations
import re
from typing import List
from .models import HandState, ParsedHand
from .hand_state_builder import extract_decision_points, build_hand_state
from .spot_classifier import classify_spot
from .street_math_engine import build_math_snapshot
from .preflop_range_evaluator import evaluate_preflop_range
from .mtt_context import build_mtt_context, context_to_dict
from .postflop_range_evaluator import evaluate_postflop_range
from .draw_detector import adjust_equity_for_draws


def _parse_cards(raw) -> list:
    """Converte hero_cards para lista de strings de 2 chars: '7s4s' → ['7s','4s']."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        # já é lista — garante que cada item é 2 chars
        return [str(c).strip() for c in raw if str(c).strip()]
    s = str(raw).replace(' ', '')
    # Padrão: rank (A,K,Q,J,T,2-9) + suit (s,h,d,c)
    return re.findall(r'[2-9TJQKAakqjt][shdcSHDC]', s)


def build_decision_input(state: HandState, hand: 'ParsedHand | None' = None) -> dict:
    """Constrói o input do Decision Engine para um HandState."""
    spot      = classify_spot(state)
    math      = build_math_snapshot(state)

    # Injetar equity no metadata — ajustada por draws para postflop
    raw_equity = math.estimated_hand_equity
    if state.street != 'preflop' and raw_equity is not None:
        adjusted_eq, draw_profile = adjust_equity_for_draws(
            raw_equity,
            state.hero_cards or '',
            state.board or [],
            state.street,
        )
        state.metadata['estimated_equity']   = adjusted_eq
        state.metadata['raw_equity']         = raw_equity
        state.metadata['draw_profile']       = str(draw_profile)
        state.metadata['equity_adjustment']  = round(adjusted_eq - raw_equity, 4)
    else:
        state.metadata['estimated_equity'] = raw_equity
        state.metadata['raw_equity']       = raw_equity
        state.metadata['draw_profile']     = 'none'
        state.metadata['equity_adjustment']= 0.0

    # Usar evaluator correto por street
    if state.street == 'preflop':
        range_eval = evaluate_preflop_range(state, spot)
    else:
        range_eval = evaluate_postflop_range(state)

    hand_profile = {
        'handClass':             classify_hand_class(state.hero_cards),
        'showdownValueTier':     classify_showdown_tier(state.hero_cards),
        'drawTier':              classify_draw_tier(state.hero_cards, state.board),
        'blockerProfile':        [],
        'rawEquityEstimate':     math.estimated_hand_equity,
        'realizedEquityEstimate': math.estimated_hand_equity,
    }

    is_3bet = (
        state.street == 'preflop' and
        state.player_action in ('raise', 'shove', 'jam') and
        state.facing_size > 0
    )

    return {
        'hand_id':       state.hand_id,
        'street':        state.street,
        'player_action': state.player_action,
        'hero_cards':    _parse_cards(state.hero_cards),
        'is_3bet':       is_3bet,
        'spot': {
            'spotType':         spot.spot_type,
            'position':         state.position,
            'villainPosition':  state.villain_position,
            'isInPosition':     state.is_in_position,
            'isMultiway':       state.is_multiway,
            'effectiveStackBb': state.effective_stack_bb,
            'potSize':          state.pot_size,
            'facingSize':       state.facing_size,
            'raiseSizeBb':      state.facing_size,
            'board':            state.board or [],
            'nPlayers':         state.metadata.get('n_players'),  # tamanho da mesa
            'nActiveOpponents': state.metadata.get('n_active_opponents', 1),  # opps vivos na street
            'preflopRaisesFaced': state.metadata.get('preflop_raises_faced', 0),  # 3-bet/squeeze faced
            'heroWasAggressor':   state.metadata.get('hero_was_aggressor', False),
        },
        'hand_profile': hand_profile,
        'math': {
            'potOddsEquity':            math.pot_odds_equity,
            'estimatedHandEquity':      state.metadata.get('estimated_equity',
                                            math.estimated_hand_equity),
            'rawEquity':                state.metadata.get('raw_equity',
                                            math.estimated_hand_equity),
            'drawProfile':              state.metadata.get('draw_profile', 'none'),
            'equityAdjustment':         state.metadata.get('equity_adjustment', 0.0),
            'impliedOddsFactor':        math.implied_odds_factor,
            'reverseImpliedOddsFactor': math.reverse_implied_odds_factor,
            'pressureScore':            math.pressure_score,
        },
        'range_evaluation': {
            'recommendedPrimaryAction': range_eval.recommended_primary_action,
            'alternativeActions':       range_eval.alternative_actions,
            'rangeZone':                range_eval.range_zone,
            'confidence':               range_eval.confidence,
            'mixWeight':                range_eval.mix_weight,
        },
        'context': state.metadata.get('mtt_context', {
            'tournamentStage': 'unknown',
            'icmPressure':     'low',
            'bountyDynamic':   False,
            'readsAvailable':  False,
        }),
    }


def build_decision_inputs_for_hand(hand: ParsedHand) -> List[dict]:
    """
    Retorna lista de decision inputs — um por cada decisão do hero na mão.
    Injeta contexto MTT real (M ratio, stage, ICM pressure) em cada decisão.
    """
    states = extract_decision_points(hand)

    # Calcular MTT context uma vez por mão e injetar em todos os estados
    try:
        mtt = build_mtt_context(hand)
        ctx = context_to_dict(mtt)
    except Exception:
        ctx = {'tournamentStage': 'unknown', 'icmPressure': 'low',
               'bountyDynamic': False, 'readsAvailable': False}

    for s in states:
        s.metadata['mtt_context'] = ctx

    return [build_decision_input(s) for s in states]


# ── Hand profile helpers ──────────────────────────────────────────────────────

def classify_hand_class(cards: str | None) -> str:
    if not cards or len(cards) < 4:
        return 'unknown'
    r1, s1, r2, s2 = cards[0], cards[1], cards[2], cards[3]
    if r1 == r2:
        return 'pair'
    if s1 == s2 and r1 in 'TJQKA' and r2 in 'TJQKA':
        return 'suited_broadway'
    if s1 != s2 and (r1 in 'TJQKA' or r2 in 'TJQKA'):
        return 'dominated_broadway'
    return 'unpaired'


def classify_showdown_tier(cards: str | None) -> str:
    if not cards or len(cards) < 4:
        return 'unknown'
    if cards[0] == cards[2]:
        return 'pair'
    if cards[0] in 'TJQKA' and cards[2] in 'TJQKA':
        return 'broadway'
    return 'weak'


def classify_draw_tier(cards: str | None, board: list) -> str:
    if not cards or len(cards) < 4:
        return 'none'
    if cards[1] == cards[3]:
        return 'backdoor_or_fd'
    return 'none'
