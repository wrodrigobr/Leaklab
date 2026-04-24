"""
Testes do Sprint 1: multi-decisão por mão.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.models import ParsedHand, ParsedAction
from leaklab.hand_state_builder import extract_decision_points
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


def _hand(hand_id, hero, cards, actions_spec, bb=100):
    """Helper: cria ParsedHand a partir de uma lista de (player, street, action, amount)."""
    actions = [
        ParsedAction(player=p, street=s, action=a, amount=amt)
        for p, s, a, amt in actions_spec
    ]
    return ParsedHand(
        hand_id=hand_id, hero=hero, bb=bb,
        hero_cards=cards, players=[hero, 'Villain'],
        actions=actions,
    )


# ── extract_decision_points ───────────────────────────────────────────────────

def test_single_preflop_fold():
    hand = _hand('1', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'folds',  None),
    ])
    points = extract_decision_points(hand)
    assert len(points) == 1
    assert points[0].street == 'preflop'
    assert points[0].player_action == 'fold'
    print("OK  test_single_preflop_fold")


def test_two_streets():
    hand = _hand('2', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Villain', 'flop',    'bets',   200),
        ('Hero',    'flop',    'calls',  200),
    ])
    points = extract_decision_points(hand)
    assert len(points) == 2
    assert points[0].street == 'preflop'
    assert points[0].player_action == 'call'
    assert points[1].street == 'flop'
    assert points[1].player_action == 'call'
    print("OK  test_two_streets")


def test_four_streets():
    hand = _hand('3', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Hero',    'flop',    'checks', None),
        ('Villain', 'flop',    'bets',   200),
        ('Hero',    'flop',    'calls',  200),
        ('Hero',    'turn',    'checks', None),
        ('Villain', 'turn',    'bets',   400),
        ('Hero',    'turn',    'folds',  None),
    ])
    points = extract_decision_points(hand)
    # preflop/call, flop/check, flop/call, turn/check, turn/fold = 5 decisões
    assert len(points) == 5
    streets = [p.street for p in points]
    actions = [p.player_action for p in points]
    assert streets == ['preflop', 'flop', 'flop', 'turn', 'turn']
    assert actions == ['call', 'check', 'call', 'check', 'fold']
    print("OK  test_four_streets")


def test_three_bet_sequence():
    """Hero faz raise, villain 3-bet, hero chama — 2 decisões do hero."""
    hand = _hand('4', 'Hero', 'KhKd', [
        ('Hero',    'preflop', 'raises', 250),
        ('Villain', 'preflop', 'raises', 750),
        ('Hero',    'preflop', 'calls',  500),
    ])
    points = extract_decision_points(hand)
    assert len(points) == 2
    assert points[0].player_action == 'raise'
    assert points[1].player_action == 'call'
    print("OK  test_three_bet_sequence")


def test_excludes_posts_and_shows():
    hand = _hand('5', 'Hero', 'AsJs', [
        ('Hero',    'preflop', 'posts',  100),   # SB post — excluir
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  200),
        ('Hero',    'preflop', 'shows',  None),  # show — excluir
    ])
    points = extract_decision_points(hand)
    assert len(points) == 1
    assert points[0].player_action == 'call'
    print("OK  test_excludes_posts_and_shows")


def test_check_included():
    hand = _hand('6', 'Hero', 'AsJs', [
        ('Hero',    'flop',  'checks', None),
        ('Villain', 'flop',  'checks', None),
    ])
    points = extract_decision_points(hand)
    assert len(points) == 1
    assert points[0].player_action == 'check'
    print("OK  test_check_included")


def test_total_decisions_metadata():
    hand = _hand('7', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Hero',    'flop',    'bets',   200),
    ])
    points = extract_decision_points(hand)
    for p in points:
        assert p.metadata['total_decisions'] == len(points)
    print("OK  test_total_decisions_metadata")


def test_pot_size_accumulates():
    """Pot no flop deve incluir as apostas do preflop."""
    hand = _hand('8', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Hero',    'flop',    'bets',   200),
    ])
    points = extract_decision_points(hand)
    preflop_state = points[0]
    flop_state = points[1]
    # No preflop, hero ainda não colocou nada (pot = villain raise)
    assert preflop_state.pot_size == 300.0
    # No flop, pot inclui preflop raise + hero call
    assert flop_state.pot_size == 600.0
    print("OK  test_pot_size_accumulates")


def test_facing_size_correct():
    hand = _hand('9', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Villain', 'flop',    'bets',   150),
        ('Hero',    'flop',    'calls',  150),
    ])
    points = extract_decision_points(hand)
    assert points[0].facing_size == 300.0  # preflop raise
    assert points[1].facing_size == 150.0  # flop bet
    print("OK  test_facing_size_correct")


def test_empty_hand_no_decisions():
    hand = _hand('10', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Other',   'preflop', 'folds',  None),
    ])
    points = extract_decision_points(hand)
    assert len(points) == 0
    print("OK  test_empty_hand_no_decisions")


# ── Pipeline multi-decisão ────────────────────────────────────────────────────

def test_build_decision_inputs_count():
    hand = _hand('11', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Villain', 'flop',    'bets',   200),
        ('Hero',    'flop',    'folds',  None),
    ])
    inputs = build_decision_inputs_for_hand(hand)
    assert len(inputs) == 2
    print("OK  test_build_decision_inputs_count")


def test_each_input_has_correct_street():
    hand = _hand('12', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Villain', 'flop',    'bets',   200),
        ('Hero',    'flop',    'calls',  200),
        ('Villain', 'turn',    'bets',   500),
        ('Hero',    'turn',    'folds',  None),
    ])
    inputs = build_decision_inputs_for_hand(hand)
    streets = [i['street'] for i in inputs]
    assert streets == ['preflop', 'flop', 'turn']
    print("OK  test_each_input_has_correct_street")


def test_engine_runs_on_all_decisions():
    hand = _hand('13', 'Hero', 'KhQh', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Hero',    'flop',    'checks', None),
        ('Villain', 'flop',    'bets',   200),
        ('Hero',    'flop',    'calls',  200),
        ('Hero',    'turn',    'checks', None),
        ('Villain', 'turn',    'bets',   400),
        ('Hero',    'turn',    'folds',  None),
    ])
    inputs = build_decision_inputs_for_hand(hand)
    results = [evaluate_decision(i) for i in inputs]
    assert len(results) == 5
    valid_labels = {'standard', 'marginal', 'small_mistake', 'clear_mistake'}
    for r in results:
        assert r['evaluation']['label'] in valid_labels
        assert 0.0 <= r['evaluation']['mistakeScore'] <= 1.0
    print("OK  test_engine_runs_on_all_decisions")


def test_backward_compat_build_hand_state():
    """build_hand_state() ainda deve funcionar retornando a última decisão."""
    from leaklab.hand_state_builder import build_hand_state
    hand = _hand('14', 'Hero', 'AsJs', [
        ('Villain', 'preflop', 'raises', 300),
        ('Hero',    'preflop', 'calls',  300),
        ('Villain', 'flop',    'bets',   200),
        ('Hero',    'flop',    'folds',  None),
    ])
    state = build_hand_state(hand)
    assert state.street == 'flop'
    assert state.player_action == 'fold'
    print("OK  test_backward_compat_build_hand_state")


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
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
