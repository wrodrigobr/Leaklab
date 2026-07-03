"""
Auditoria da heurística preflop (_recommended_action): roda uma MATRIZ de spots
(posição × zona de mão × stack × facing) e trava INVARIANTES de teoria. Pega bugs
silenciosos como o do AKs na BB (recomendava 'call'/'fold' onde deveria raise/check).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_range_evaluator import _recommended_action as rec

_POS = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
_HANDS = {'core': 'KhAh', 'core_pair': 'AhAd', 'borderline': 'KsJd',
          'borderline_pair': '5h5d', 'weak': '7s2d'}
_STACKS = [8.0, 12.0, 18.0, 25.0, 45.0]
_FACING = [0.0, 2.5, 6.0]   # 0 = RFI/limp · 2.5 = vs open · 6 = vs 3-bet


def _matrix():
    for p in _POS:
        for hz, cards in _HANDS.items():
            for s in _STACKS:
                for f in _FACING:
                    yield p, hz, cards, s, f, rec(cards, p, f, stack_bb=s)


def test_no_call_at_facing_zero_except_sb():
    """Sem aposta a pagar (facing 0), 'call' não faz sentido — EXCETO o SB, que
    completando o BB está de fato dando call. Todos os outros: check/raise/fold/jam."""
    bad = [(p, hz, s, r) for p, hz, _, s, f, r in _matrix()
           if f == 0.0 and r == 'call' and p != 'SB']
    assert not bad, f"'call' em facing 0 (não-SB): {bad}"
    print("OK  test_no_call_at_facing_zero_except_sb")


def test_bb_never_folds_a_free_check():
    """BB com facing 0 (pote limpado/walk) vê o flop de graça: NUNCA folda."""
    bad = [(hz, s, r) for p, hz, _, s, f, r in _matrix()
           if p == 'BB' and f == 0.0 and r == 'fold']
    assert not bad, f"BB foldou uma opção livre: {bad}"
    print("OK  test_bb_never_folds_a_free_check")


def test_pushfold_zone_is_binary_offblind():
    """Stack curto (≤14bb) fora dos blinds e facing 0: só jam ou fold (nada de call/check)."""
    bad = [(p, hz, s, r) for p, hz, _, s, f, r in _matrix()
           if s <= 14.0 and f == 0.0 and p not in ('BB', 'SB') and r not in ('jam', 'fold')]
    assert not bad, f"push/fold não-binário: {bad}"
    print("OK  test_pushfold_zone_is_binary_offblind")


def test_known_spots():
    """Âncoras de teoria que não podem regredir."""
    assert rec('KhAh', 'BB', 0.0, stack_bb=20.6) == 'raise'    # AKs iso sobre limp
    assert rec('KhAh', 'BB', 0.0, stack_bb=8.0) == 'jam'       # AKs BB curto isola com jam
    assert rec('7s2d', 'BB', 0.0, stack_bb=8.0) == 'check'     # lixo na BB vê flop grátis
    assert rec('KhAh', 'CO', 0.0, stack_bb=30.0) == 'raise'    # RFI padrão
    assert rec('KhAh', 'BB', 6.0, stack_bb=25.0) == 'call'     # vs raise real: flat/set-mine
    assert rec('AhAd', 'UTG', 0.0, stack_bb=45.0) == 'raise'   # AA sempre abre
    print("OK  test_known_spots")


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
