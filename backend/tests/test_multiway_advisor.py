"""Conselheiro multiway (leaklab/multiway_advisor) — fallback independente do solver HU.

Ancora na mão 5 (A2c 3-way → fold, batendo o coach) + controles de força e determinismo.
"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.multiway_advisor import advise_multiway as A, _HAS_EVAL7

NS = 4000  # sims menores no teste (ação é estável; números aproximados)


def test_mao5_a2c_3way_e_fold():
    """A2c no flop 9c4d4h, pote 13, pagar 4, 2 vilões, OOP → FOLD (equity realizada
    abaixo das pot odds). É o caso que o solver HU errava (raise 93%) e o coach acertou."""
    v = A('Ac2c', ['9c', '4d', '4h'], 13, 4, 2, is_in_position=False, n_sims=NS)
    assert v is not None
    assert v['action'] == 'fold', v
    assert v['required_eq'] and abs(v['required_eq'] - 0.2353) < 0.01
    assert v['realized_eq'] < v['required_eq']
    assert v['confidence'] == 'estimate'
    print(f"OK  test_mao5_a2c_3way_e_fold (eq={v['equity']:.0%} real={v['realized_eq']:.0%})")


def test_set_e_raise():
    """Trips de 4 (mão muito forte) multiway → raise por valor."""
    v = A('4s4c', ['9c', '4d', '4h'], 13, 4, 2, is_in_position=False, n_sims=NS)
    assert v['action'] == 'raise', v
    assert v['equity'] > 0.8
    print("OK  test_set_e_raise")


def test_overpair_aa_raise():
    v = A('AsAd', ['9c', '4d', '4h'], 13, 4, 2, is_in_position=False, n_sims=NS)
    assert v['action'] == 'raise', v
    print("OK  test_overpair_aa_raise")


def test_draw_forte_paga_nao_raise():
    """Draw de flush nut (KcQc) multiway → call, NÃO blefe-raise (multiway tem pouca
    fold equity). Princípio Galfond: não blefa-raise contra vários."""
    v = A('KcQc', ['9c', '4d', '2c'], 13, 4, 2, is_in_position=True, n_sims=NS)
    assert v['action'] == 'call', v
    print("OK  test_draw_forte_paga_nao_raise")


def test_ar_primeiro_a_agir_check():
    """Q-alto sem nada, primeiro a agir, 2 vilões → check (sem valor claro multiway)."""
    v = A('Qh3s', ['9c', '4d', '4h'], 8, 0, 2, is_in_position=False, n_sims=NS)
    assert v['action'] == 'check', v
    assert v['required_eq'] is None
    print("OK  test_ar_primeiro_a_agir_check")


def test_valor_primeiro_a_agir_bet():
    """Set primeiro a agir multiway → aposta por valor."""
    v = A('9s9h', ['9c', '4d', '4h'], 8, 0, 2, is_in_position=True, n_sims=NS)
    assert v['action'] == 'bet', v
    print("OK  test_valor_primeiro_a_agir_bet")


def test_hu_e_invalidos_retornam_none():
    assert A('Ac2c', ['9c', '4d', '4h'], 13, 4, 1, n_sims=NS) is None   # HU: deixa pro solver
    assert A('Ac2c', ['9c', '4d', '4h'], 13, 4, 0, n_sims=NS) is None
    assert A('', ['9c', '4d', '4h'], 13, 4, 2, n_sims=NS) is None       # hero inválido
    assert A('Ac2c', [], 13, 4, 2, n_sims=NS) is None                   # sem board (preflop)
    assert A('Ac2c', ['9c', '4d'], 13, 4, 2, n_sims=NS) is None         # board < 3
    print("OK  test_hu_e_invalidos_retornam_none")


def test_determinismo():
    """Mesmo spot → mesmo resultado (seed derivada de hero+board+n_opp)."""
    a = A('Ac2c', ['9c', '4d', '4h'], 13, 4, 2, is_in_position=False, n_sims=NS)
    b = A('Ac2c', ['9c', '4d', '4h'], 13, 4, 2, is_in_position=False, n_sims=NS)
    assert a == b, (a, b)
    print("OK  test_determinismo")


def test_pot_odds_grandes_forcam_fold():
    """Pagar caro (aposta grande) com mão fraca → fold mesmo com alguma equity."""
    v = A('Ac2c', ['9c', '4d', '4h'], 10, 10, 2, is_in_position=False, n_sims=NS)  # 50% req
    assert v['action'] == 'fold', v
    print("OK  test_pot_odds_grandes_forcam_fold")


if __name__ == '__main__':
    if not _HAS_EVAL7:
        print("SKIP: eval7 ausente"); sys.exit(0)
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
