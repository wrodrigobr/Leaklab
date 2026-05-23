"""
Testa leaklab.revalidation.differ.classify -- categorização de divergência.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = ':memory:'

from leaklab.revalidation.differ import classify, DivergenceRecord
from leaklab.revalidation.oracle import OracleDecision


def _engine(best, alts=None, gto_label=None, gto_action=None, action_taken=None):
    return {
        'bestAction':  best,
        'actionTaken': action_taken or best,
        'gto':         {'gto_label': gto_label, 'gto_action': gto_action,
                        'available': gto_label is not None},
        'debug':       {'alternativeActions': alts or []},
    }


def _oracle(action, alternatives=None, confidence='high', source='postflop_strategy',
            opp_cost=None):
    return OracleDecision(
        action=action, alternatives=alternatives or [],
        confidence=confidence, source=source, opp_cost_bb=opp_cost,
    )


# -- Categorias positivas -----------------------------------------------------

def test_aligned_same_action():
    r = classify(_engine('bet'), _oracle('bet'))
    assert r.category == 'aligned'
    assert r.severity_score == 0
    print("OK  test_aligned_same_action")


def test_aligned_after_norm_jam_shove():
    r = classify(_engine('shove'), _oracle('jam'))
    assert r.category == 'aligned', f"esperado aligned, recebi {r.category}"
    print("OK  test_aligned_after_norm_jam_shove")


def test_acceptable_alt_in_oracle_alternatives():
    r = classify(_engine('raise'), _oracle('call', alternatives=['raise', 'fold']))
    assert r.category == 'acceptable_alt'
    print(f"OK  test_acceptable_alt_in_oracle_alternatives (reasons={r.reasons})")


def test_acceptable_alt_via_gto_mixed():
    r = classify(_engine('call', gto_label='gto_mixed'), _oracle('raise'))
    assert r.category == 'acceptable_alt'
    print("OK  test_acceptable_alt_via_gto_mixed")


def test_acceptable_alt_via_gto_correct():
    r = classify(_engine('check', gto_label='gto_correct'), _oracle('bet'))
    assert r.category == 'acceptable_alt'
    print("OK  test_acceptable_alt_via_gto_correct")


# -- Minor mismatch ------------------------------------------------------------

def test_minor_mismatch_low_opp_cost():
    r = classify(_engine('check'), _oracle('call', opp_cost=0.10))
    assert r.category == 'minor_mismatch'
    assert 0.40 <= r.severity_score < 0.85
    print(f"OK  test_minor_mismatch_low_opp_cost (severity={r.severity_score})")


def test_minor_mismatch_via_gto_minor_deviation():
    r = classify(_engine('call', gto_label='gto_minor_deviation'),
                 _oracle('raise', opp_cost=0.05))
    assert r.category == 'minor_mismatch'
    print("OK  test_minor_mismatch_via_gto_minor_deviation")


def test_minor_when_oracle_low_confidence_no_opp_cost():
    r = classify(_engine('check'), _oracle('call', confidence='low',
                                            source='heuristic_potodds'))
    assert r.category == 'minor_mismatch'
    print(f"OK  test_minor_when_oracle_low_confidence_no_opp_cost (reasons={r.reasons})")


# -- Major mismatch ------------------------------------------------------------

def test_major_mismatch_fold_vs_jam():
    r = classify(_engine('fold'), _oracle('jam'))
    assert r.category == 'major_mismatch'
    print(f"OK  test_major_mismatch_fold_vs_jam (severity={r.severity_score})")


def test_major_mismatch_call_vs_fold_high_opp_cost():
    r = classify(_engine('call'), _oracle('fold', opp_cost=0.50))
    assert r.category == 'major_mismatch'
    print("OK  test_major_mismatch_call_vs_fold_high_opp_cost")


def test_major_via_gto_critical_even_if_passive_swap():
    r = classify(_engine('call', gto_label='gto_critical'),
                 _oracle('check'))
    assert r.category == 'major_mismatch'
    assert 'gto_label=gto_critical' in ' '.join(r.reasons)
    print("OK  test_major_via_gto_critical_even_if_passive_swap")


def test_major_severity_scales_with_opp_cost():
    r_low  = classify(_engine('fold'), _oracle('raise', opp_cost=0.30))
    r_high = classify(_engine('fold'), _oracle('raise', opp_cost=2.50))
    assert r_low.category == r_high.category == 'major_mismatch'
    assert r_high.severity_score > r_low.severity_score
    print(f"OK  test_major_severity_scales_with_opp_cost ({r_low.severity_score} < {r_high.severity_score})")


# -- Edge cases ----------------------------------------------------------------

def test_no_oracle_data_returns_unverifiable():
    r = classify(_engine('bet'), _oracle(None, confidence='unavailable',
                                          source='unavailable'))
    assert r.category == 'no_oracle_data'
    assert r.oracle_action is None
    print("OK  test_no_oracle_data_returns_unverifiable")


def test_engine_no_data_when_best_empty():
    r = classify({'bestAction': None, 'actionTaken': 'check', 'gto': {}, 'debug': {}},
                 _oracle('check'))
    assert r.category == 'engine_no_data'
    print("OK  test_engine_no_data_when_best_empty")


def test_to_dict_has_all_fields():
    r = classify(_engine('fold'), _oracle('raise', opp_cost=0.40))
    d = r.to_dict()
    for k in ('category', 'severity_score', 'engine_best', 'oracle_action',
              'gto_action', 'action_taken', 'opp_cost_bb', 'oracle_source',
              'oracle_confidence', 'reasons'):
        assert k in d, f"chave {k} faltando em to_dict()"
    print("OK  test_to_dict_has_all_fields")


def test_action_taken_propagated():
    r = classify(_engine('bet', action_taken='check'), _oracle('bet'))
    assert r.action_taken == 'check'
    print("OK  test_action_taken_propagated")


def test_engine_alts_not_used_for_acceptable_alt():
    # Spec atual: só oracle.alternatives + gto_label desencadeiam acceptable_alt.
    # engine.debug.alternativeActions é informativo mas não promove a categoria.
    r = classify(_engine('check', alts=['bet']), _oracle('bet'))
    assert r.category != 'acceptable_alt'
    print(f"OK  test_engine_alts_not_used_for_acceptable_alt (category={r.category})")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(0 if failed == 0 else 1)
