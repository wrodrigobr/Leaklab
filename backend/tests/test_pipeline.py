import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaphunter.models import ParsedHand, ParsedAction
from gaphunter.hand_state_builder import build_hand_state
from gaphunter.pipeline import build_decision_input
from gaphunter.decision_engine_v11 import evaluate_decision
from gaphunter.recommendation_engine import build_recommendation
from gaphunter.leak_correlator import correlate_leaks
from gaphunter.session_metrics import build_session_metrics


def _make_hand(hand_id='1', hero_cards='AsJs', hero='Hero',
               villain_action='raises', villain_amount=250,
               hero_action='calls', hero_amount=250, bb=100):
    return ParsedHand(
        hand_id=hand_id, hero=hero, bb=bb, hero_cards=hero_cards,
        players=[hero, 'Villain'],
        actions=[
            ParsedAction(player='Villain', street='preflop', action=villain_action, amount=villain_amount),
            ParsedAction(player=hero, street='preflop', action=hero_action, amount=hero_amount),
        ],
    )


def test_pipeline_smoke_call():
    hand = _make_hand()
    state = build_hand_state(hand)
    di = build_decision_input(state)
    out = evaluate_decision(di)
    assert out['handId'] == '1'
    assert out['evaluation']['label'] in {'standard', 'marginal', 'small_mistake', 'clear_mistake'}
    assert 0.0 <= out['evaluation']['mistakeScore'] <= 1.0
    print("OK  test_pipeline_smoke_call")


def test_pipeline_smoke_fold():
    hand = _make_hand(hero_action='folds', hero_amount=None)
    state = build_hand_state(hand)
    di = build_decision_input(state)
    out = evaluate_decision(di)
    assert out['evaluation']['label'] in {'standard', 'marginal', 'small_mistake', 'clear_mistake'}
    print("OK  test_pipeline_smoke_fold")


def test_pipeline_smoke_jam():
    hand = _make_hand(hero_action='all-in', hero_amount=1000)
    state = build_hand_state(hand)
    di = build_decision_input(state)
    out = evaluate_decision(di)
    assert out['evaluation']['label'] in {'standard', 'marginal', 'small_mistake', 'clear_mistake'}
    print("OK  test_pipeline_smoke_jam")


def test_recommendation_engine():
    hand = _make_hand()
    state = build_hand_state(hand)
    di = build_decision_input(state)
    out = evaluate_decision(di)
    rec = build_recommendation(out)
    assert 'handId' in rec
    assert 'label' in rec
    assert 'summary' in rec
    assert isinstance(rec['summary'], str) and len(rec['summary']) > 5
    print("OK  test_recommendation_engine")


def test_recommendation_all_labels():
    labels = ['standard', 'marginal', 'small_mistake', 'clear_mistake']
    for label in labels:
        mock_out = {'handId': 'x', 'evaluation': {'label': label}, 'interpretation': {}}
        rec = build_recommendation(mock_out)
        assert rec['label'] == label
        assert len(rec['summary']) > 0
    print("OK  test_recommendation_all_labels")


def test_leak_correlator_weights():
    results = [
        {'evaluation': {'label': 'standard'},     'bestAction': 'fold', 'street': 'preflop', 'handId': '1'},
        {'evaluation': {'label': 'marginal'},     'bestAction': 'fold', 'street': 'preflop', 'handId': '2'},
        {'evaluation': {'label': 'small_mistake'},'bestAction': 'call', 'street': 'flop',    'handId': '3'},
        {'evaluation': {'label': 'clear_mistake'},'bestAction': 'call', 'street': 'flop',    'handId': '4'},
    ]
    leaks = correlate_leaks(results)
    # by_action: fold=0.15, call=1.55
    assert abs(leaks['by_action']['fold']['weight'] - 0.15) < 0.001
    assert abs(leaks['by_action']['call']['weight'] - 1.55) < 0.001
    print("OK  test_leak_correlator_weights")


def test_session_metrics():
    results = [
        {'evaluation': {'label': 'standard',     'mistakeScore': 0.05}, 'handId': '1'},
        {'evaluation': {'label': 'clear_mistake','mistakeScore': 0.50}, 'handId': '2'},
    ]
    m = build_session_metrics(results)
    assert m['total_decisions'] == 2
    assert m['total_hands'] == 2
    assert abs(m['avg_mistake_score'] - 0.275) < 0.001
    assert m['label_distribution']['standard'] == 1
    assert m['label_distribution']['clear_mistake'] == 1
    print("OK  test_session_metrics")


def test_pipeline_multiple_hands():
    cards = ['AsJs', 'KhQh', '2c7d', 'ThTd', 'AhAd']
    results = []
    for i, c in enumerate(cards):
        hand = _make_hand(hand_id=str(i), hero_cards=c)
        state = build_hand_state(hand)
        di = build_decision_input(state)
        out = evaluate_decision(di)
        results.append(out)
    assert len(results) == 5
    for r in results:
        assert r['evaluation']['label'] in {'standard', 'marginal', 'small_mistake', 'clear_mistake'}
    print("OK  test_pipeline_multiple_hands")


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
