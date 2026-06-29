"""Gate de robustez multiway (leaklab/multiway_safety) — #30 Fase 1.

Garante a invariante de SEGURANÇA: só entra na cauda gradeável (safe_fold/safe_value)
quem sobrevive ao canto adversário das premissas. O meio ambíguo fica 'informative'
(NÃO gradeado). Ancora em spots calibrados + propriedades (monotonicidade, determinismo).
"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.multiway_safety import classify_safe as C, is_safe_leak, _HAS_EVAL7

NS = 4000  # margens da cauda segura são grandes; buckets são estáveis com poucos sims


def test_monster_set_safe_value():
    """Trips de 4 (mão monstro) 3-way → valor garantido mesmo vs range apertada."""
    v = C('4s4c', ['9c', '4d', '4h'], 2, 8, 0, street='flop', n_sims=NS)
    assert v['bucket'] == 'safe_value', v
    assert v['recommended'] == 'bet'
    assert v['eq_lo'] >= 0.62
    print("OK  test_monster_set_safe_value")


def test_overpair_safe_value():
    """AA overpair 3-way em board pareado baixo → valor claro vs range apertada."""
    v = C('AsAd', ['9c', '4d', '4h'], 2, 8, 0, street='flop', n_sims=NS)
    assert v['bucket'] == 'safe_value', v
    print("OK  test_overpair_safe_value")


def test_pricedout_safe_fold():
    """72o em AKQ enfrentando aposta grande 3-way → priced-out mesmo vs range larga."""
    v = C('7d2c', ['Ah', 'Ks', 'Qc'], 2, 10, 8, street='flop', n_sims=NS)
    assert v['bucket'] == 'safe_fold', v
    assert v['recommended'] == 'fold'
    assert v['eq_hi'] < v['required_eq']
    print("OK  test_pricedout_safe_fold")


def test_marginal_stays_informative():
    """A2c em 944 enfrentando aposta pequena: o ADVISOR folda (equity realizada), mas
    o GATE NÃO grada — sob a premissa de equity máxima (vilão largo) A2c não está
    priced-out. É o gate sendo mais conservador que o advisor: o meio fica informativo."""
    v = C('Ac2c', ['9c', '4d', '4h'], 2, 13, 4, street='flop', n_sims=NS)
    assert v['bucket'] == 'informative', v
    assert v['recommended'] is None
    print("OK  test_marginal_stays_informative")


def test_hu_and_invalid_na():
    assert C('Ac2c', ['9c', '4d', '4h'], 1, 13, 4, n_sims=NS)['bucket'] == 'n/a'  # HU
    assert C('Ac2c', ['9c', '4d'], 2, 13, 4, n_sims=NS)['bucket'] == 'n/a'        # board curto
    assert C('', ['9c', '4d', '4h'], 2, 13, 4, n_sims=NS)['bucket'] == 'n/a'      # hero inválido
    print("OK  test_hu_and_invalid_na")


def test_monotonic_equity_drops_with_opponents():
    """Mais vilões ⇒ menos equity (vs a mesma range). Propriedade que sustenta o gate."""
    eq2 = C('AsAd', ['9c', '4d', '4h'], 2, 8, 0, n_sims=NS)['eq_lo']
    eq4 = C('AsAd', ['9c', '4d', '4h'], 4, 8, 0, n_sims=NS)['eq_lo']
    assert eq2 > eq4, (eq2, eq4)
    print("OK  test_monotonic_equity_drops_with_opponents")


def test_board_sliced_by_street():
    """DB guarda board completo; o gate fatia pela street. Passar 5 cartas com
    street='flop' tem que dar idêntico a passar só as 3 do flop (mesmo seed/equity)."""
    full = C('4s4c', ['9c', '4d', '4h', '2s', '7s'], 2, 8, 0, street='flop', n_sims=NS)
    flop = C('4s4c', ['9c', '4d', '4h'], 2, 8, 0, street='flop', n_sims=NS)
    assert full == flop, (full, flop)
    print("OK  test_board_sliced_by_street")


def test_determinismo():
    a = C('7d2c', ['Ah', 'Ks', 'Qc'], 2, 10, 8, street='flop', n_sims=NS)
    b = C('7d2c', ['Ah', 'Ks', 'Qc'], 2, 10, 8, street='flop', n_sims=NS)
    assert a == b, (a, b)
    print("OK  test_determinismo")


def test_is_safe_leak_truth_table():
    assert is_safe_leak({'bucket': 'safe_fold'}, 'call') is True
    assert is_safe_leak({'bucket': 'safe_fold'}, 'raise') is True
    assert is_safe_leak({'bucket': 'safe_fold'}, 'fold') is False
    assert is_safe_leak({'bucket': 'safe_value'}, 'check') is True
    assert is_safe_leak({'bucket': 'safe_value'}, 'fold') is True
    assert is_safe_leak({'bucket': 'safe_value'}, 'bet') is False
    assert is_safe_leak({'bucket': 'safe_value'}, 'shove') is False  # shove = extrai valor
    assert is_safe_leak({'bucket': 'informative'}, 'call') is None   # fora da cauda: defere
    assert is_safe_leak(None, 'call') is None
    print("OK  test_is_safe_leak_truth_table")


if __name__ == '__main__':
    if not _HAS_EVAL7:
        print("SKIP: eval7 ausente"); sys.exit(0)
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
