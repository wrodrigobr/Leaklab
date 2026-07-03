"""
BB iso-raise sobre limp: mão forte na BB deve RAISE (iso), não "call"; borderline dá check.
Regressão do bug do AKs na BB sobre SB-limp (recomendava call → marcava o iso como erro).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_range_evaluator import _recommended_action as rec


def test_bb_core_iso_raises_over_limp():
    # AKs / pares grandes / broadway suited na BB sobre limp → RAISE (iso), não call
    for cards in ('KhAh', 'AhAd', 'KhKd', 'QhKh'):
        assert rec(cards, 'BB', 0.0, stack_bb=20.6) == 'raise', (cards, rec(cards, 'BB', 0.0, stack_bb=20.6))
    print("OK  test_bb_core_iso_raises_over_limp")


def test_bb_borderline_checks_not_calls():
    # borderline na BB (num pote limpado) VÊ o flop de graça = check, nunca "call"
    for cards in ('KsJd', '8h9h', '5h5d'):
        assert rec(cards, 'BB', 0.0, stack_bb=20.6) == 'check', (cards, rec(cards, 'BB', 0.0, stack_bb=20.6))
    print("OK  test_bb_borderline_checks_not_calls")


def test_bb_weak_checks_free():
    assert rec('7s2d', 'BB', 0.0, stack_bb=20.6) == 'check'
    print("OK  test_bb_weak_checks_free")


def test_facing_real_raise_unchanged():
    # facing um raise DE VERDADE (>=2bb): BB core segue call (set-mine/flat), não afetado pelo fix
    assert rec('KhAh', 'BB', 6.0, stack_bb=25.0) == 'call'
    # RFI de posição não-blind segue raise
    assert rec('KhAh', 'CO', 0.0, stack_bb=25.0) == 'raise'
    # push/fold curto segue jam
    assert rec('KhAh', 'BB', 0.0, stack_bb=8.0) == 'jam'
    print("OK  test_facing_real_raise_unchanged")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
