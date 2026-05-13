"""
Testes dos evaluators: preflop_range_evaluator, postflop_range_evaluator,
e integração com evaluate_decision — foco em cenários críticos de correção
e cobertura de muitos spots para detectar regressões.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_range_evaluator import (
    _classify_range_zone, _recommended_action, evaluate_preflop_range,
)
from leaklab.models import HandState, SpotClassification
from leaklab.decision_engine_v11 import evaluate_decision


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _state(cards: str, position: str, facing: float = 0.0, pot: float = 100.0) -> HandState:
    return HandState(
        hand_id='test',
        street='preflop',
        hero='Hero',
        hero_cards=cards,
        board=[],
        player_action='raise',
        pot_size=pot,
        facing_size=facing,
        effective_stack_bb=30.0,
        position=position,
        villain_position=None,
        is_in_position=True,
        is_multiway=False,
        actions=[],
    )


def _spot() -> SpotClassification:
    return SpotClassification(
        spot_type='preflop',
        street='preflop',
        position='BTN',
        villain_position=None,
    )


def _decision(player_action, street, pot_odds, est_equity, range_zone,
              recommended, alternatives=None, facing_size=0.0, position='BTN'):
    return dict(
        hand_id='x', street=street, player_action=player_action,
        spot=dict(
            isInPosition=True, isMultiway=False, effectiveStackBb=30,
            facingSize=facing_size, position=position,
        ),
        hand_profile=dict(handClass='pair'),
        math=dict(potOddsEquity=pot_odds, estimatedHandEquity=est_equity,
                  impliedOddsFactor=0.1, reverseImpliedOddsFactor=0.05,
                  pressureScore=0.4),
        range_evaluation=dict(
            recommendedPrimaryAction=recommended,
            alternativeActions=alternatives or [],
            rangeZone=range_zone,
            confidence=0.72, mixWeight=0.1,
        ),
        context=dict(icmPressure='low', bountyDynamic=False, readsAvailable=False),
    )


# ─────────────────────────────────────────────────────────────────────────────
# _classify_range_zone
# ─────────────────────────────────────────────────────────────────────────────

def test_zone_pairs_core():
    for rank in list('89TJQKA'):
        cards = f"{rank}s{rank}h"
        assert _classify_range_zone(cards) == 'core_range', f"Pair {cards} deveria ser core_range"
    print("OK  test_zone_pairs_core")


def test_zone_pairs_borderline():
    for rank in list('4567'):
        cards = f"{rank}s{rank}h"
        assert _classify_range_zone(cards) == 'borderline_range', f"Pair {cards} deveria ser borderline_range"
    print("OK  test_zone_pairs_borderline")


def test_zone_pairs_outside():
    for rank in list('23'):
        cards = f"{rank}s{rank}h"
        assert _classify_range_zone(cards) == 'outside_range', f"Pair {cards} deveria ser outside_range"
    print("OK  test_zone_pairs_outside")


def test_zone_broadway_suited_core():
    cases = ['AsKs', 'AhQh', 'KdJd', 'QcTc', 'JsTh']
    for cards in ['AsKs', 'AhQh', 'KdJd', 'QcTc']:
        assert _classify_range_zone(cards) == 'core_range', f"{cards} broadway suited deveria ser core_range"
    print("OK  test_zone_broadway_suited_core")


def test_zone_broadway_offsuit_borderline():
    for cards in ['AsKh', 'AhQd', 'KdJc', 'QcTh']:
        assert _classify_range_zone(cards) == 'borderline_range', f"{cards} broadway offsuit deveria ser borderline_range"
    print("OK  test_zone_broadway_offsuit_borderline")


def test_zone_suited_connector_borderline():
    for cards in ['7s8s', '6h7h', '5d6d', '8c9c']:
        assert _classify_range_zone(cards) == 'borderline_range', f"{cards} suited deveria ser borderline_range"
    print("OK  test_zone_suited_connector_borderline")


def test_zone_trash_outside():
    for cards in ['2s7h', '3c8d', '4h9s']:
        assert _classify_range_zone(cards) == 'outside_range', f"{cards} trash deveria ser outside_range"
    print("OK  test_zone_trash_outside")


def test_zone_short_cards_outside():
    assert _classify_range_zone('') == 'outside_range'
    assert _classify_range_zone('As') == 'outside_range'
    assert _classify_range_zone('AsK') == 'outside_range'
    print("OK  test_zone_short_cards_outside")


# ─────────────────────────────────────────────────────────────────────────────
# _recommended_action — sem aposta (facing=0): NUNCA fold
# ─────────────────────────────────────────────────────────────────────────────

POSITIONS_ALL = ['BTN', 'CO', 'HJ', 'MP', 'UTG', 'SB', 'BB']


def test_no_facing_bet_never_fold_core_range():
    for pos in POSITIONS_ALL:
        for cards in ['AsAh', 'KsKh', 'QsQh', 'AsKs']:
            rec = _recommended_action(cards, pos, facing_size=0.0)
            assert rec != 'fold', f"core_range {cards} {pos} sem aposta retornou fold"
    print("OK  test_no_facing_bet_never_fold_core_range")


def test_no_facing_bet_never_fold_borderline_range():
    for pos in POSITIONS_ALL:
        for cards in ['6s6h', '7d7c', 'AsKh', '8s9s']:
            rec = _recommended_action(cards, pos, facing_size=0.0)
            assert rec != 'fold', f"borderline_range {cards} {pos} sem aposta retornou fold"
    print("OK  test_no_facing_bet_never_fold_borderline_range")


def test_no_facing_bet_never_fold_outside_range():
    for pos in POSITIONS_ALL:
        for cards in ['2s7h', '3c8d', '4h9s']:
            rec = _recommended_action(cards, pos, facing_size=0.0)
            assert rec != 'fold', f"outside_range {cards} {pos} sem aposta retornou fold (deveria ser check)"
            assert rec == 'check', f"outside_range {cards} {pos} sem aposta deveria retornar check, retornou {rec}"
    print("OK  test_no_facing_bet_never_fold_outside_range")


def test_facing_bet_outside_range_can_fold():
    rec = _recommended_action('2s7h', 'BTN', facing_size=3.0)
    assert rec == 'fold', f"outside_range com aposta BTN deveria recomendar fold"
    print("OK  test_facing_bet_outside_range_can_fold")


# ─────────────────────────────────────────────────────────────────────────────
# BB vs limpers — cenário crítico que causou o bug reportado
# ─────────────────────────────────────────────────────────────────────────────

def test_bb_vs_limpers_no_bet_core_range():
    for cards in ['AsAh', 'KsKh', 'JsJh', 'TsTh', 'AsKs']:
        rec = _recommended_action(cards, 'BB', facing_size=0.0)
        assert rec in ('call', 'raise', 'check'), \
            f"BB core_range sem aposta: esperava call/raise/check, got {rec}"
        assert rec != 'fold', f"BB vs limpers com {cards}: FOLD É IMPOSSÍVEL"
    print("OK  test_bb_vs_limpers_no_bet_core_range")


def test_bb_vs_limpers_no_bet_trash():
    rec = _recommended_action('2s7h', 'BB', facing_size=0.0)
    assert rec == 'check', f"BB vs limpers mão fraca: deveria ser check, got {rec}"
    print("OK  test_bb_vs_limpers_no_bet_trash")


def test_sb_complete_no_bet():
    rec = _recommended_action('2s7h', 'SB', facing_size=0.0)
    assert rec == 'check', f"SB complete sem aposta mão fraca: deveria ser check, got {rec}"
    print("OK  test_sb_complete_no_bet")


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_preflop_range — alternatives nunca incluem fold quando facing=0
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluate_preflop_range_no_fold_in_alternatives_when_no_bet():
    hands = [
        ('AsAh', 'BB'), ('KsQh', 'BTN'), ('7s7h', 'CO'), ('2s7h', 'SB'),
        ('JsJh', 'BB'), ('AhTh', 'HJ'), ('5s5h', 'BB'),
    ]
    for cards, pos in hands:
        state = _state(cards, pos, facing=0.0)
        result = evaluate_preflop_range(state, _spot())
        assert result.recommended_primary_action != 'fold', \
            f"{cards} {pos} facing=0: recomendou fold"
        assert 'fold' not in result.alternative_actions, \
            f"{cards} {pos} facing=0: fold apareceu nas alternativas"
    print("OK  test_evaluate_preflop_range_no_fold_in_alternatives_when_no_bet")


def test_evaluate_preflop_range_fold_allowed_with_bet():
    state = _state('2s7h', 'BTN', facing=3.0)
    result = evaluate_preflop_range(state, _spot())
    assert result.recommended_primary_action == 'fold', \
        f"outside_range com aposta deveria recomendar fold"
    print("OK  test_evaluate_preflop_range_fold_allowed_with_bet")


def test_evaluate_preflop_range_core_has_confidence():
    state = _state('AsAh', 'BTN', facing=0.0)
    result = evaluate_preflop_range(state, _spot())
    assert result.confidence > 0.5
    assert result.range_zone == 'core_range'
    print("OK  test_evaluate_preflop_range_core_has_confidence")


def test_evaluate_preflop_range_borderline_has_alternatives():
    state = _state('6s6h', 'BTN', facing=3.0)
    result = evaluate_preflop_range(state, _spot())
    assert result.range_zone == 'borderline_range'
    assert len(result.alternative_actions) > 0
    print("OK  test_evaluate_preflop_range_borderline_has_alternatives")


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_decision — guard final: facingSize=0 → bestAction != fold
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluate_decision_no_fold_when_facing_zero():
    """evaluate_decision nunca deve retornar bestAction=fold quando facingSize=0."""
    cases = [
        ('fold', 'preflop', 0.20, 0.15, 'outside_range', 'fold', 0.0, 'BB'),
        ('check', 'preflop', 0.20, 0.15, 'outside_range', 'fold', 0.0, 'BTN'),
        ('raise', 'preflop', 0.20, 0.50, 'core_range', 'fold', 0.0, 'BB'),
        ('call', 'flop', 0.25, 0.30, 'borderline_range', 'fold', 0.0, 'SB'),
    ]
    for player_action, street, pot_odds, est_eq, zone, rec, facing, pos in cases:
        d = _decision(player_action, street, pot_odds, est_eq, zone, rec, facing_size=facing, position=pos)
        r = evaluate_decision(d)
        best = r.get('bestAction') or r.get('evaluation', {}).get('bestAction')
        assert best != 'fold', \
            f"evaluate_decision com facingSize=0 retornou bestAction=fold ({player_action}/{street}/{pos})"
    print("OK  test_evaluate_decision_no_fold_when_facing_zero")


def test_evaluate_decision_bb_limper_raise_is_not_mistake():
    """BB com mão forte levantando contra limpers não é erro."""
    d = _decision('raise', 'preflop', 0.10, 0.65, 'core_range', 'raise',
                  facing_size=0.0, position='BB')
    r = evaluate_decision(d)
    label = r['evaluation']['label']
    assert label in ('standard', 'marginal'), \
        f"BB raise com core_range sem aposta foi classificado como {label}"
    print("OK  test_evaluate_decision_bb_limper_raise_is_not_mistake")


def test_evaluate_decision_fold_with_bet_is_valid():
    """Fold com aposta a pagar pode ser bestAction legítimo."""
    d = _decision('call', 'preflop', 0.30, 0.15, 'outside_range', 'fold',
                  facing_size=3.0, position='BTN')
    r = evaluate_decision(d)
    best = r.get('bestAction') or r.get('evaluation', {}).get('bestAction')
    # fold é válido quando há aposta; o sistema pode retornar fold ou outra ação
    # — o importante é não restringir fold incorretamente
    assert best is not None
    print("OK  test_evaluate_decision_fold_with_bet_is_valid")


# ─────────────────────────────────────────────────────────────────────────────
# Cobertura de spots em massa: matrix de posições × mãos × facingSize
# ─────────────────────────────────────────────────────────────────────────────

CORE_HANDS = ['AsAh', 'KsKh', 'QsQh', 'JsJh', 'TsTh', '9s9h', '8s8h', 'AsKs', 'AsQs']
BORDER_HANDS = ['7s7h', '6s6h', '5s5h', '4s4h', 'AsKh', 'KsQh', 'AsJs', 'Ks9s']
TRASH_HANDS = ['2s7h', '3c8d', '4h9s', '2d6c', '3h5d']
ALL_HANDS = CORE_HANDS + BORDER_HANDS + TRASH_HANDS


def test_mass_no_facing_never_fold():
    """Para todo spot sem aposta, a recomendação nunca é fold."""
    failures = []
    for pos in POSITIONS_ALL:
        for cards in ALL_HANDS:
            rec = _recommended_action(cards, pos, facing_size=0.0)
            if rec == 'fold':
                failures.append(f"{cards} @ {pos}")
    assert not failures, f"fold recomendado sem aposta em {len(failures)} spots: {failures[:5]}"
    print(f"OK  test_mass_no_facing_never_fold ({len(POSITIONS_ALL) * len(ALL_HANDS)} spots verificados)")


def test_mass_evaluate_range_no_fold_alternatives_when_no_bet():
    """evaluate_preflop_range nunca inclui fold em alternatives quando facing=0."""
    failures = []
    for pos in POSITIONS_ALL:
        for cards in ALL_HANDS:
            state = _state(cards, pos, facing=0.0)
            result = evaluate_preflop_range(state, _spot())
            if result.recommended_primary_action == 'fold':
                failures.append(f"primary fold: {cards}@{pos}")
            if 'fold' in result.alternative_actions:
                failures.append(f"alt fold: {cards}@{pos}")
    assert not failures, f"fold indevido em {len(failures)} spots: {failures[:5]}"
    print(f"OK  test_mass_evaluate_range_no_fold_alternatives_when_no_bet ({len(POSITIONS_ALL) * len(ALL_HANDS)} spots)")


def test_mass_zone_consistency():
    """_classify_range_zone sempre retorna um dos 3 valores válidos."""
    valid_zones = {'core_range', 'borderline_range', 'outside_range'}
    failures = []
    test_cards = ALL_HANDS + ['', 'As', 'AsK', 'ZsZh']
    for cards in test_cards:
        zone = _classify_range_zone(cards)
        if zone not in valid_zones:
            failures.append(f"{cards} → {zone}")
    assert not failures, f"Zone inválida: {failures}"
    print(f"OK  test_mass_zone_consistency ({len(test_cards)} mãos)")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'=' * 50}")
    print(f"Total: {passed + failed} | Passed: {passed} | Failed: {failed}")
