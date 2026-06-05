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


def test_pko_vsrfi_fallback_below_floor():
    # vs_RFI também respeita o floor de 45bb → abaixo dele cai no Classic
    r = analyze_preflop(position='BTN', hero_hand_type='99', stack_bb=30,
                        action_taken='call', facing_size=2.0, vs_position='CO',
                        n_players=8, is_pko=True)
    assert r['scenario'] == 'vs_rfi'
    assert not r.get('pko')  # <45bb → Classic
    print("OK  test_pko_vsrfi_fallback_below_floor")


def test_pko_vsrfi_applied():
    # vs_RFI: BTN defende vs UTG open, em PKO usa a fonte PKO
    r = analyze_preflop(position='BTN', hero_hand_type='AKs', stack_bb=100,
                        action_taken='raise', facing_size=2.1, vs_position='UTG',
                        n_players=8, is_pko=True)
    assert r['scenario'] == 'vs_rfi'
    assert r['pko'] is True and r['source'] == 'pko_gto'
    assert r['available'] is True and r['in_range'] is True
    print("OK  test_pko_vsrfi_applied")


def test_pko_squeeze_applied():
    # squeeze: BTN squeeza vs UTG-open + caller, em PKO usa a fonte PKO
    r = analyze_preflop(position='BTN', hero_hand_type='AKs', stack_bb=100,
                        action_taken='raise', facing_size=2.1, vs_position='UTG',
                        caller_position='CO', is_3bet_pot=True, n_players=8, is_pko=True)
    assert r['scenario'] == 'squeeze'
    assert r['pko'] is True and r['source'] == 'pko_gto'
    assert r['available'] is True and r['in_range'] is True
    print("OK  test_pko_squeeze_applied")


def test_pko_squeeze_adds_coverage():
    # Em alguns spots o Classic não tem squeeze[hero][opener] (NULL); o PKO cobre.
    cls = analyze_preflop(position='BTN', hero_hand_type='AKs', stack_bb=100,
                          action_taken='raise', facing_size=2.1, vs_position='UTG',
                          caller_position='CO', is_3bet_pot=True, n_players=8, is_pko=False)
    pko = analyze_preflop(position='BTN', hero_hand_type='AKs', stack_bb=100,
                          action_taken='raise', facing_size=2.1, vs_position='UTG',
                          caller_position='CO', is_3bet_pot=True, n_players=8, is_pko=True)
    assert pko['available'] is True and pko['pko'] is True
    assert cls['available'] is False  # Classic sem cobertura aqui — PKO acrescenta
    print("OK  test_pko_squeeze_adds_coverage")


def test_pko_uncovered_below_floor():
    # Re-raise (vs_3bet) abaixo do floor 45bb → sem PKO, cai no Classic
    r = analyze_preflop(position='UTG', hero_hand_type='AKs', stack_bb=30,
                        action_taken='raise', facing_size=8.0, vs_position='BTN',
                        hero_was_aggressor=True, facing_raises=1, n_players=8, is_pko=True)
    assert r['scenario'] == 'vs_3bet'
    assert not r.get('pko'), "PKO aplicado abaixo do floor"
    print("OK  test_pko_uncovered_below_floor")


def test_pko_vs3bet_applied():
    # vs_3bet: UTG abriu, BTN 3betou, UTG decide — PKO aplicado
    r = analyze_preflop(position='UTG', hero_hand_type='AKs', stack_bb=100,
                        action_taken='raise', facing_size=8.0, vs_position='BTN',
                        hero_was_aggressor=True, facing_raises=1, n_players=8, is_pko=True)
    assert r['scenario'] == 'vs_3bet'
    assert r['pko'] is True and r['source'] == 'pko_gto' and r['available'] is True
    print("OK  test_pko_vs3bet_applied")


def test_pko_vs4bet_applied():
    # vs_4bet: BTN 3betou, UTG 4betou, BTN decide — PKO aplicado
    r = analyze_preflop(position='BTN', hero_hand_type='AKs', stack_bb=100,
                        action_taken='raise', facing_size=21.0, vs_position='UTG',
                        hero_was_aggressor=True, facing_raises=2, n_players=8, is_pko=True)
    assert r['scenario'] == 'vs_4bet'
    assert r['pko'] is True and r['source'] == 'pko_gto' and r['available'] is True
    print("OK  test_pko_vs4bet_applied")


def test_pko_faces_squeeze_applied():
    # faces_squeeze: CO cold-callou, BTN squeezou, CO decide — PKO aplicado
    r = analyze_preflop(position='CO', hero_hand_type='AKs', stack_bb=100,
                        action_taken='call', facing_size=8.0, vs_position='BTN',
                        facing_raises=2, hero_was_aggressor=False, n_players=8, is_pko=True)
    assert r['scenario'] == 'faces_squeeze'
    assert r['pko'] is True and r['source'] == 'pko_gto' and r['available'] is True
    print("OK  test_pko_faces_squeeze_applied")


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
