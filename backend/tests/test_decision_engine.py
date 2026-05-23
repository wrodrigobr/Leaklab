import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import (
    classify_mistake_score, apply_anti_rules, calc_math_penalty,
    calc_base_action_gap, calc_range_penalty,
    calc_realization_adjustment, calc_pressure_adjustment,
    calc_adjusted_required_equity, evaluate_decision
)

# ── Labels ────────────────────────────────────────────────────────────────────
def test_label_boundaries():
    assert classify_mistake_score(0.00) == 'standard'
    assert classify_mistake_score(0.08) == 'standard'
    assert classify_mistake_score(0.09) == 'marginal'
    assert classify_mistake_score(0.18) == 'marginal'
    assert classify_mistake_score(0.19) == 'small_mistake'
    assert classify_mistake_score(0.36) == 'small_mistake'
    assert classify_mistake_score(0.37) == 'clear_mistake'
    assert classify_mistake_score(1.00) == 'clear_mistake'
    print("OK  test_label_boundaries")

# ── Anti-rules ────────────────────────────────────────────────────────────────
def test_anti_overfold_downgrades():
    assert apply_anti_rules('fold', 0.33, 0.31, 'clear_mistake') == 'small_mistake'
    assert apply_anti_rules('fold', 0.30, 0.28, 'clear_mistake') == 'small_mistake'
    print("OK  test_anti_overfold_downgrades")

def test_anti_overfold_does_not_downgrade_far():
    assert apply_anti_rules('fold', 0.50, 0.20, 'clear_mistake') == 'clear_mistake'
    print("OK  test_anti_overfold_does_not_downgrade_far")

def test_anti_fold_plus_ev_promotes_standard():
    """Fold com equity >= pot_odds + 3pp deve promover label de standard para small_mistake.
    Sem isso, verdict 'Correto' pode contradizer o indicador 'Call lucrativo'."""
    # caso real do user: eq=37%, po=33% → margem 4pp → small_mistake
    assert apply_anti_rules('fold', 0.37, 0.33, 'standard') == 'small_mistake'
    # margem exata de 3pp → ainda promove
    assert apply_anti_rules('fold', 0.33, 0.30, 'standard') == 'small_mistake'
    # margem 2pp → permanece standard (noise dentro da tolerância)
    assert apply_anti_rules('fold', 0.34, 0.32, 'standard') == 'standard'
    # equity < required → fold correto, permanece standard
    assert apply_anti_rules('fold', 0.30, 0.33, 'standard') == 'standard'
    print("OK  test_anti_fold_plus_ev_promotes_standard")

def test_anti_soft_call_escalates_marginal():
    assert apply_anti_rules('call', 0.20, 0.26, 'marginal') == 'small_mistake'
    print("OK  test_anti_soft_call_escalates_marginal")

def test_anti_soft_call_escalates_to_clear():
    assert apply_anti_rules('call', 0.20, 0.30, 'marginal') == 'clear_mistake'
    assert apply_anti_rules('call', 0.20, 0.30, 'small_mistake') == 'clear_mistake'
    print("OK  test_anti_soft_call_escalates_to_clear")

def test_anti_rules_other_actions_unchanged():
    assert apply_anti_rules('raise', 0.20, 0.30, 'marginal') == 'marginal'
    assert apply_anti_rules('check', 0.20, 0.30, 'small_mistake') == 'small_mistake'
    print("OK  test_anti_rules_other_actions_unchanged")

def test_anti_rules_none_equity():
    assert apply_anti_rules('fold', None, 0.30, 'clear_mistake') == 'clear_mistake'
    assert apply_anti_rules('call', 0.20, None, 'marginal') == 'marginal'
    print("OK  test_anti_rules_none_equity")

# ── Math penalty ──────────────────────────────────────────────────────────────
def test_math_penalty_call_ok():
    assert calc_math_penalty('call', 0.40, 0.30) == 0.0
    print("OK  test_math_penalty_call_ok")

def test_math_penalty_call_slight_miss():
    p = calc_math_penalty('call', 0.29, 0.30)
    assert 0.0 < p <= 0.11
    print("OK  test_math_penalty_call_slight_miss")

def test_math_penalty_call_bad():
    p = calc_math_penalty('call', 0.20, 0.30)
    assert p >= 0.18
    print("OK  test_math_penalty_call_bad")

def test_math_penalty_fold_ok():
    assert calc_math_penalty('fold', 0.25, 0.30) == 0.0
    print("OK  test_math_penalty_fold_ok")

def test_math_penalty_fold_mistake():
    p = calc_math_penalty('fold', 0.40, 0.30)
    assert p > 0
    print("OK  test_math_penalty_fold_mistake")

def test_math_penalty_none_values():
    assert calc_math_penalty('call', None, 0.30) == 0.0
    assert calc_math_penalty('call', 0.30, None) == 0.0
    print("OK  test_math_penalty_none_values")

# ── Base action gap ───────────────────────────────────────────────────────────
def test_base_gap_correct_action():
    assert calc_base_action_gap('call', 'call') == 0.0
    assert calc_base_action_gap('fold', 'fold') == 0.0
    print("OK  test_base_gap_correct_action")

def test_base_gap_alternative():
    assert calc_base_action_gap('fold', 'call', ['fold', 'raise']) == 0.08
    print("OK  test_base_gap_alternative")

def test_base_gap_aggressive_mismatch():
    assert calc_base_action_gap('jam', 'fold') == 0.35
    print("OK  test_base_gap_aggressive_mismatch")

def test_base_gap_fold_vs_call():
    assert calc_base_action_gap('fold', 'call') == 0.14
    print("OK  test_base_gap_fold_vs_call")

def test_base_gap_call_vs_fold():
    assert calc_base_action_gap('call', 'fold') == 0.22
    print("OK  test_base_gap_call_vs_fold")

# ── Range penalty ─────────────────────────────────────────────────────────────
def test_range_penalty_correct_zero():
    assert calc_range_penalty('core_range', 'call', 'call') == 0.0
    print("OK  test_range_penalty_correct_zero")

def test_range_penalty_wrong_action():
    assert calc_range_penalty('borderline_range', 'call', 'fold') == 0.03
    assert calc_range_penalty('core_range', 'fold', 'call') == 0.08
    assert calc_range_penalty('outside_range', 'call', 'fold') == 0.12
    print("OK  test_range_penalty_wrong_action")

# ── Adjustments & caps ────────────────────────────────────────────────────────
def test_realization_adjustment_capped():
    adj = calc_realization_adjustment(False, 0.8, 50, 'outside_range', 'dominated_broadway')
    assert 0 < adj <= 0.04
    print("OK  test_realization_adjustment_capped")

def test_pressure_adjustment_capped():
    adj = calc_pressure_adjustment('river', 0.9, True, 'high')
    assert 0 < adj <= 0.03
    print("OK  test_pressure_adjustment_capped")

def test_street_cap_preflop():
    r = calc_adjusted_required_equity('preflop', 0.30, 0.04, 0.03)
    assert r['streetCapApplied'] == 0.04
    assert r['totalAdjustment'] <= 0.04
    print("OK  test_street_cap_preflop")

def test_street_cap_river():
    r = calc_adjusted_required_equity('river', 0.25, 0.04, 0.03)
    assert r['streetCapApplied'] == 0.06
    assert r['totalAdjustment'] <= 0.06
    print("OK  test_street_cap_river")

def test_adjusted_equity_none():
    r = calc_adjusted_required_equity('flop', None, 0.02, 0.01)
    assert r['adjustedRequiredEquity'] is None
    print("OK  test_adjusted_equity_none")

# ── Street multiplier order ───────────────────────────────────────────────────
def _make(street, action='call'):
    return dict(
        hand_id='x', street=street, player_action=action,
        spot=dict(isInPosition=True, isMultiway=False, effectiveStackBb=30),
        hand_profile=dict(handClass='unpaired'),
        math=dict(potOddsEquity=0.35, estimatedHandEquity=0.22,
                  impliedOddsFactor=0.1, reverseImpliedOddsFactor=0.05, pressureScore=0.4),
        range_evaluation=dict(recommendedPrimaryAction='fold',
                              alternativeActions=[], rangeZone='core_range',
                              confidence=0.72, mixWeight=0.1),
        context=dict(icmPressure='low', bountyDynamic=False, readsAvailable=False),
    )

def test_street_multipliers_river_gt_preflop():
    pre = evaluate_decision(_make('preflop'))['evaluation']['mistakeScore']
    riv = evaluate_decision(_make('river'))['evaluation']['mistakeScore']
    assert riv > pre
    print("OK  test_street_multipliers_river_gt_preflop")

# ── Curated cases ─────────────────────────────────────────────────────────────
def _hand(player_action, street, pot_odds, est_equity, range_zone, recommended,
          alternatives=None, in_pos=True, multiway=False, icm='low'):
    return dict(
        hand_id='x', street=street, player_action=player_action,
        spot=dict(isInPosition=in_pos, isMultiway=multiway, effectiveStackBb=30),
        hand_profile=dict(handClass='pair'),
        math=dict(potOddsEquity=pot_odds, estimatedHandEquity=est_equity,
                  impliedOddsFactor=0.1, reverseImpliedOddsFactor=0.05, pressureScore=0.4),
        range_evaluation=dict(recommendedPrimaryAction=recommended,
                              alternativeActions=alternatives or [],
                              rangeZone=range_zone, confidence=0.72, mixWeight=0.1),
        context=dict(icmPressure=icm, bountyDynamic=False, readsAvailable=False),
    )

def test_correct_call_is_standard():
    r = evaluate_decision(_hand('call', 'flop', 0.30, 0.45, 'core_range', 'call'))
    assert r['evaluation']['label'] == 'standard'
    print("OK  test_correct_call_is_standard")

def test_clear_fold_error():
    r = evaluate_decision(_hand('fold', 'flop', 0.20, 0.42, 'core_range', 'call'))
    assert r['evaluation']['label'] in ('small_mistake', 'clear_mistake')
    print("OK  test_clear_fold_error")

def test_bad_call_is_mistake():
    r = evaluate_decision(_hand('call', 'flop', 0.35, 0.26, 'outside_range', 'fold'))
    assert r['evaluation']['label'] in ('small_mistake', 'clear_mistake')
    print("OK  test_bad_call_is_mistake")

def test_borderline_fold_not_clear_mistake():
    r = evaluate_decision(_hand('fold', 'preflop', 0.30, 0.32, 'borderline_range', 'call', ['fold']))
    assert r['evaluation']['label'] != 'clear_mistake', f"Got {r['evaluation']['label']}"
    print("OK  test_borderline_fold_not_clear_mistake")

def test_output_required_fields():
    r = evaluate_decision(_hand('call', 'flop', 0.30, 0.40, 'core_range', 'call'))
    assert 'handId' in r
    assert 'evaluation' in r
    assert 'mistakeScore' in r['evaluation']
    assert 'label' in r['evaluation']
    assert 'scoreBreakdown' in r['evaluation']
    assert 'thresholds' in r
    assert 'interpretation' in r
    print("OK  test_output_required_fields")

def test_score_always_0_to_1():
    for action in ['fold', 'call', 'raise', 'jam']:
        r = evaluate_decision(_hand(action, 'river', 0.25, 0.45, 'outside_range', 'fold'))
        s = r['evaluation']['mistakeScore']
        assert 0.0 <= s <= 1.0, f"Score {s} out of bounds for {action}"
    print("OK  test_score_always_0_to_1")

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
