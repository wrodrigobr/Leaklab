"""
Testa a integração PKO no engine de preflop (preflop_gto_ranges.py):
- _pko_ranges_for: seleção de estágio por depth + floor (sem PKO raso)
- analyze_preflop(is_pko=True): aplica ranges PKO no RFI quando cobertos
- fallback: abaixo do floor, fora de RFI, ou is_pko=False → Classic
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.preflop_gto_ranges import analyze_preflop, _pko_ranges_for, _load_pko


def test_pko_json_loads():
    pko = _load_pko().get('pko_ranges', {})
    assert '200p' in pko, "leaklab_pko_ranges.json sem field 200p"
    assert 'START' in pko['200p'] and 'PCT50' in pko['200p']
    print("OK  test_pko_json_loads")


def test_stage_selection_by_depth():
    assert _pko_ranges_for(100)[1] == 'START'
    assert _pko_ranges_for(90)[1] == 'PCT90'
    assert _pko_ranges_for(70)[1] == 'PCT70'
    assert _pko_ranges_for(55)[1] == 'PCT50'
    # floor: abaixo de 45bb não há range PKO (GW não resolve PKO raso)
    assert _pko_ranges_for(40)[0] is None
    assert _pko_ranges_for(20)[0] is None
    print("OK  test_stage_selection_by_depth")


def test_pko_applied_on_rfi():
    r = analyze_preflop(position='UTG', hero_hand_type='99', stack_bb=100,
                        action_taken='raise', n_players=8, is_pko=True)
    assert r['pko'] is True
    assert r['pko_stage'] == 'START'
    assert r['source'] == 'pko_gto'
    assert r['available'] is True and r['in_range'] is True
    print("OK  test_pko_applied_on_rfi")


def test_classic_when_not_pko():
    r = analyze_preflop(position='UTG', hero_hand_type='99', stack_bb=100,
                        action_taken='raise', n_players=8, is_pko=False)
    assert not r.get('pko')
    assert r.get('source') != 'pko_gto'
    assert r['available'] is True
    print("OK  test_classic_when_not_pko")


def test_pko_differs_from_classic():
    # O range PKO abre mais largo que o chipEV (bounty). UTG open% deve diferir.
    pko = analyze_preflop(position='UTG', hero_hand_type='99', stack_bb=100,
                          action_taken='raise', n_players=8, is_pko=True)
    cls = analyze_preflop(position='UTG', hero_hand_type='99', stack_bb=100,
                          action_taken='raise', n_players=8, is_pko=False)
    assert pko['raise_pct'] != cls['raise_pct'], "PKO e Classic com mesmo open% (overlay não aplicou?)"
    print(f"OK  test_pko_differs_from_classic (PKO open={pko['raise_pct']:.3f} vs Classic={cls['raise_pct']:.3f})")


def test_fallback_below_floor():
    # PKO mas stack 30bb (< floor 45) → sem range PKO, cai no Classic
    r = analyze_preflop(position='UTG', hero_hand_type='99', stack_bb=30,
                        action_taken='raise', n_players=8, is_pko=True)
    assert not r.get('pko')
    print("OK  test_fallback_below_floor")


def test_pko_only_rfi_not_vsrfi():
    # vs_RFI (facing open) com is_pko=True NÃO deve usar PKO (só RFI coberto)
    r = analyze_preflop(position='BTN', hero_hand_type='99', stack_bb=100,
                        action_taken='call', facing_size=2.5, vs_position='CO',
                        n_players=8, is_pko=True)
    assert r['scenario'] == 'vs_rfi'
    assert not r.get('pko'), "PKO aplicado fora de RFI"
    print("OK  test_pko_only_rfi_not_vsrfi")


def test_out_of_range_hand_folds():
    # 72o nunca abre UTG, nem em PKO
    r = analyze_preflop(position='UTG', hero_hand_type='72o', stack_bb=100,
                        action_taken='fold', n_players=8, is_pko=True)
    assert r['pko'] is True
    assert r['in_range'] is False
    print("OK  test_out_of_range_hand_folds")


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
