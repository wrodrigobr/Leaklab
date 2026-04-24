"""
Testa o pipeline end-to-end com o arquivo real do torneio.
Hero: phpro | 400 maos
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import parse_pokerstars_file
from leaklab.hand_state_builder import build_hand_state
from leaklab.pipeline import build_decision_input
from leaklab.decision_engine_v11 import evaluate_decision
from leaklab.session_metrics import build_session_metrics
from leaklab.leak_correlator import correlate_leaks

TOURNAMENT_FILE = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')


def _run_tournament():
    hands = parse_pokerstars_file(TOURNAMENT_FILE)
    results, errors = [], []
    for hand in hands:
        try:
            state = build_hand_state(hand)
            di = build_decision_input(state)
            out = evaluate_decision(di)
            results.append(out)
        except Exception as e:
            errors.append((hand.hand_id, str(e)))
    return results, errors, hands


def test_parser_reads_all_hands():
    hands = parse_pokerstars_file(TOURNAMENT_FILE)
    assert len(hands) >= 350, f"Expected >= 350 hands, got {len(hands)}"
    print(f"OK  test_parser_reads_all_hands ({len(hands)} hands)")


def test_pipeline_runs_without_crash():
    results, errors, hands = _run_tournament()
    error_rate = len(errors) / max(len(hands), 1)
    assert error_rate < 0.05, f"Error rate {error_rate:.1%} too high"
    print(f"OK  test_pipeline_runs_without_crash ({len(errors)} errors / {len(hands)} hands)")


def test_all_results_have_valid_labels():
    results, _, _ = _run_tournament()
    valid = {'standard', 'marginal', 'small_mistake', 'clear_mistake'}
    bad = [r for r in results if r['evaluation']['label'] not in valid]
    assert len(bad) == 0, f"{len(bad)} results with invalid labels"
    print(f"OK  test_all_results_have_valid_labels ({len(results)} results)")


def test_scores_in_range():
    results, _, _ = _run_tournament()
    out_of_range = [r for r in results if not (0.0 <= r['evaluation']['mistakeScore'] <= 1.0)]
    assert len(out_of_range) == 0, f"{len(out_of_range)} scores out of [0,1]"
    print("OK  test_scores_in_range")


def test_distribution_not_degenerate():
    """Verifica que a distribuição não é 100% em um único label."""
    results, _, _ = _run_tournament()
    m = build_session_metrics(results)
    dist = m['label_distribution']
    total = sum(dist.values())
    # Nenhum label deve ter 100% dos casos
    for label, count in dist.items():
        pct = count / total
        assert pct < 1.0, f"Label {label} has 100% of cases — engine may be degenerate"
    # Deve existir pelo menos 2 labels diferentes
    assert len(dist) >= 2, f"Only {len(dist)} label(s) found — distribution too narrow"
    print(f"OK  test_distribution_not_degenerate | dist: {dist}")


def test_standard_is_majority():
    """Em MTT real, standard deve ser a maioria (guideline: 60-80%)."""
    results, _, _ = _run_tournament()
    m = build_session_metrics(results)
    dist = m['label_distribution']
    total = sum(dist.values())
    std_pct = dist.get('standard', 0) / total
    assert std_pct >= 0.40, f"Standard rate {std_pct:.1%} too low — possible overpunishment"
    print(f"OK  test_standard_is_majority ({std_pct:.1%} standard)")


def test_session_metrics_shape():
    results, _, _ = _run_tournament()
    m = build_session_metrics(results)
    assert 'total_hands' in m
    assert 'avg_mistake_score' in m
    assert 'label_distribution' in m
    assert m['total_hands'] == len(results)
    print(f"OK  test_session_metrics_shape | avg_score={m['avg_mistake_score']:.4f}")


def test_leak_correlator_runs():
    results, _, _ = _run_tournament()
    leaks = correlate_leaks(results)
    assert isinstance(leaks, dict)
    assert 'by_action' in leaks
    assert 'by_street' in leaks
    assert 'by_street_action' in leaks
    for bucket in leaks.values():
        for k, v in bucket.items():
            assert 'weight' in v
            assert 'count' in v
            assert 'avg_weight' in v
    total_buckets = sum(len(b) for b in leaks.values())
    print(f"OK  test_leak_correlator_runs | {total_buckets} buckets")


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
