"""Testes do sizing_advisor — Fase 1 (open preflop) + Fase 2 (postflop vs nó GTO)."""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from leaklab.sizing_advisor import (analyze_open_sizing as A,
                                    gto_main_bet_size_pct as G,
                                    analyze_postflop_sizing as P,
                                    _size_label_to_pct as L)


def test_std_open_ok():
    r = A(to_bb=2.2, position='BTN')
    assert r['key'] == 'open_ok' and r['status'] == 'ok'
    print("OK  test_std_open_ok")


def test_std_open_too_big():
    r = A(to_bb=3.0, position='UTG')
    assert r['key'] == 'open_big' and r['status'] == 'warn'
    print("OK  test_std_open_too_big")


def test_std_open_min_is_ok():
    r = A(to_bb=2.0, position='CO')
    assert r['key'] == 'open_ok'
    print("OK  test_std_open_min_is_ok")


def test_sb_open_too_small():
    # SB abrindo min vs BB → suba (open_sb_small)
    r = A(to_bb=2.0, position='SB')
    assert r['key'] == 'open_sb_small' and r['status'] == 'warn'
    print("OK  test_sb_open_too_small")


def test_sb_open_sized_up_ok():
    r = A(to_bb=3.0, position='SB')
    assert r['key'] == 'open_ok'
    print("OK  test_sb_open_sized_up_ok")


def test_iso_over_limp_too_small():
    r = A(to_bb=2.5, position='CO', facing_limp=True)
    assert r['key'] == 'open_iso_small'
    print("OK  test_iso_over_limp_too_small")


def test_iso_over_limp_ok():
    r = A(to_bb=4.0, position='CO', facing_limp=True)
    assert r['key'] == 'open_ok'
    print("OK  test_iso_over_limp_ok")


def test_none_when_no_size():
    assert A(to_bb=None, position='BTN') is None
    assert A(to_bb=0, position='BTN') is None
    print("OK  test_none_when_no_size")


# ── Fase 2: postflop vs nó GTO ───────────────────────────────────────────────

def test_label_pct_parse():
    assert L('bet_50pct', None) == 50.0
    assert L('raise_119pct', None) == 119.0
    assert abs(L('bet_6.4bb', 8.0) - 80.0) < 1e-6   # 6.4/8 = 80% do pote
    assert L('bet_1.5x', None) == 150.0             # x = x vezes o pote
    assert L('check', None) is None and L('allin', None) is None
    print("OK  test_label_pct_parse")


def test_gto_main_picks_highest_freq_bet():
    strat = [{'action': 'check', 'frequency': 0.5},
             {'action': 'bet_33pct', 'frequency': 0.4},
             {'action': 'bet_75pct', 'frequency': 0.1}]
    assert G(strat) == 33                       # bet de maior freq, ignora o check
    print("OK  test_gto_main_picks_highest_freq_bet")


def test_gto_main_none_when_no_bet():
    assert G([{'action': 'check', 'frequency': 0.7}, {'action': 'call', 'frequency': 0.3}]) is None
    print("OK  test_gto_main_none_when_no_bet")


def test_postflop_ok():
    r = P(hero_pct=70, gto_pct=66)
    assert r['key'] == 'postflop_ok' and r['status'] == 'ok' and r['params']['gto'] == 66
    print("OK  test_postflop_ok")


def test_postflop_too_big():
    r = P(hero_pct=100, gto_pct=33)             # 3x o size do solver
    assert r['key'] == 'postflop_too_big' and r['status'] == 'warn'
    print("OK  test_postflop_too_big")


def test_postflop_too_small():
    r = P(hero_pct=20, gto_pct=66)              # ~0.3x
    assert r['key'] == 'postflop_too_small' and r['status'] == 'warn'
    print("OK  test_postflop_too_small")


def test_postflop_none_when_missing():
    assert P(hero_pct=None, gto_pct=50) is None
    assert P(hero_pct=50, gto_pct=None) is None
    assert P(hero_pct=50, gto_pct=0) is None
    print("OK  test_postflop_none_when_missing")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
