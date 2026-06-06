"""
#27 — Equity preflop range-aware: matriz 169×169 (equity.py) + villain_open_range
+ wiring no street_math_engine (vs RANGE quando há open conhecido, não vs random).

Não depende do asset gerado (preflop_equity_169.json): injeta uma matriz sintética
em equity._matrix pros testes determinísticos. Um teste extra valida o asset real
SE ele existir (gate has_matrix()).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import leaklab.equity as eq
from leaklab.preflop_gto_ranges import villain_open_range


def _set_matrix(m):
    eq._matrix = m


def test_equity_vs_hand_basic():
    _set_matrix({'AA': {'KK': 0.82, 'AA': 0.5}, 'KK': {'AA': 0.18}})
    assert eq.equity_vs_hand('AA', 'KK') == 0.82
    assert eq.equity_vs_hand('KK', 'AA') == 0.18
    assert eq.equity_vs_hand('AA', 'ZZ') is None     # mão desconhecida
    assert eq.equity_vs_hand('QQ', 'AA') is None     # hero desconhecido
    print("OK  test_equity_vs_hand_basic")


def test_equity_vs_range_weighted():
    # hero AA: 0.80 vs KK (par, 6 combos), 0.85 vs AKo (offsuit, 12 combos)
    _set_matrix({'AA': {'KK': 0.80, 'AKo': 0.85}})
    # peso uniforme 1.0 → ponderado por combos: (0.80*6 + 0.85*12)/(6+12)
    expected = round((0.80 * 6 + 0.85 * 12) / 18, 4)
    got = eq.equity_vs_range('AA', {'KK': 1.0, 'AKo': 1.0})
    assert got == expected, f"{got} != {expected}"
    print(f"OK  test_equity_vs_range_weighted (={got})")


def test_equity_vs_range_respects_freq_weight():
    _set_matrix({'AA': {'KK': 0.80, 'AKo': 0.85}})
    # KK com freq 1.0, AKo com freq 0.0 → equity = só KK
    got = eq.equity_vs_range('AA', {'KK': 1.0, 'AKo': 0.0})
    assert got == 0.80, got
    # mão fora da matriz é ignorada
    got2 = eq.equity_vs_range('AA', {'KK': 1.0, 'ZZ': 1.0})
    assert got2 == 0.80, got2
    print("OK  test_equity_vs_range_respects_freq_weight")


def test_equity_vs_range_empty():
    _set_matrix({'AA': {'KK': 0.8}})
    assert eq.equity_vs_range('AA', {}) is None
    assert eq.equity_vs_range('AA', {'KK': 0}) is None    # todos peso 0
    assert eq.equity_vs_range('ZZ', {'KK': 1.0}) is None  # hero ausente
    print("OK  test_equity_vs_range_empty")


def test_villain_open_range_tight_vs_wide():
    # UTG abre tight; BTN abre wide → BTN tem MAIS mãos
    utg = villain_open_range('UTG', 50, 9, False)
    btn = villain_open_range('BTN', 50, 9, False)
    assert utg and btn, "ambos devem ter cobertura @50bb"
    assert len(btn) > len(utg), f"BTN({len(btn)}) deveria ser mais wide que UTG({len(utg)})"
    # AA está em qualquer range de abertura
    assert 'AA' in utg and 'AA' in btn
    # 72o não abre de UTG
    assert '72o' not in utg
    print(f"OK  test_villain_open_range_tight_vs_wide (UTG={len(utg)}, BTN={len(btn)})")


def test_villain_open_range_unknown_returns_empty():
    assert villain_open_range('', 50, 9, False) == {}
    print("OK  test_villain_open_range_unknown_returns_empty")


def test_estimate_equity_uses_range_when_present():
    # injeta matriz: hero AKs tem 0.40 vs KK e 0.60 vs QJo
    _set_matrix({'AKs': {'KK': 0.40, 'QJo': 0.60}})
    from leaklab.street_math_engine import _estimate_hand_equity
    vr = {'KK': 1.0, 'QJo': 1.0}
    eqr = _estimate_hand_equity('AsKs', [], 'preflop', vr)
    expected = round((0.40 * 6 + 0.60 * 12) / 18, 4)
    assert eqr == expected, f"{eqr} != {expected}"
    # sem range → cai no vs-random (≠ do valor range-aware acima na maioria dos casos)
    eqv = _estimate_hand_equity('AsKs', [], 'preflop', None)
    assert eqv is not None and eqv != eqr
    print(f"OK  test_estimate_equity_uses_range_when_present (range={eqr} vs random={eqv})")


def test_real_matrix_if_present():
    """Se o asset real existe, valida invariantes conhecidos."""
    eq._matrix = None  # força reload do arquivo real
    if not eq.has_matrix():
        print("SKIP test_real_matrix_if_present (asset ainda não gerado)")
        return
    assert 0.80 <= eq.equity_vs_hand('AA', 'KK') <= 0.85
    assert 0.10 <= eq.equity_vs_hand('72o', 'AA') <= 0.14
    # equity vs range tight de UTG < equity vs random (AKo)
    from leaklab.street_math_engine import PREFLOP_EQ_VS_RANDOM
    utg = villain_open_range('UTG', 50, 9, False)
    e_range = eq.equity_vs_range('AKo', utg)
    assert e_range is not None and e_range < PREFLOP_EQ_VS_RANDOM['AKo'], \
        f"AKo vs UTG-range ({e_range}) deveria ser < vs-random ({PREFLOP_EQ_VS_RANDOM['AKo']})"
    print(f"OK  test_real_matrix_if_present (AKo vs UTG={e_range} < random={PREFLOP_EQ_VS_RANDOM['AKo']})")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
