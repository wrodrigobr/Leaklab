"""Testes do sizing_advisor — Fase 1 (open preflop)."""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from leaklab.sizing_advisor import analyze_open_sizing as A


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


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
