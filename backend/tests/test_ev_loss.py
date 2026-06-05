"""
Testa o ev_loss_bb (#24) no engine preflop: bb perdidos vs a melhor ação, pra a
mão do hero. Base: overlay docs/leaklab_gto_evs.json (EV por mão/ação do GW).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.preflop_gto_ranges import analyze_preflop, _load_evs, _ev_loss_bb


def test_evs_overlay_loads():
    ev = _load_evs().get('ranges', {})
    assert ev, "overlay leaklab_gto_evs.json vazio/ausente"
    assert '100bb' in ev and 'RFI' in ev['100bb']
    print("OK  test_evs_overlay_loads")


def test_best_action_zero_loss():
    # Jogar a melhor ação = ev_loss ~0
    r = analyze_preflop(position='UTG', hero_hand_type='AA', stack_bb=100,
                        action_taken='raise', n_players=9)
    assert r['ev_loss_bb'] == 0.0
    assert r['ev_loss_source'] == 'gw_har'
    r2 = analyze_preflop(position='UTG', hero_hand_type='72o', stack_bb=100,
                         action_taken='fold', n_players=9)
    assert r2['ev_loss_bb'] == 0.0
    print("OK  test_best_action_zero_loss")


def test_leak_positive_loss():
    # Foldar AA UTG = perda grande; raisear 72o = perda pequena mas > 0
    fold_aa = analyze_preflop(position='UTG', hero_hand_type='AA', stack_bb=100,
                              action_taken='fold', n_players=9)
    assert fold_aa['ev_loss_bb'] > 1.0, fold_aa['ev_loss_bb']
    raise_trash = analyze_preflop(position='UTG', hero_hand_type='72o', stack_bb=100,
                                  action_taken='raise', n_players=9)
    assert raise_trash['ev_loss_bb'] > 0.0
    print(f"OK  test_leak_positive_loss (fold AA={fold_aa['ev_loss_bb']}bb)")


def test_correct_implies_zero_loss():
    # Invariante: gto_correct ⟹ ev_loss ≈ 0 (amostra de spots cobertos)
    cases = [
        dict(position='UTG', hero_hand_type='AA', stack_bb=100, action_taken='raise'),
        dict(position='BTN', hero_hand_type='AKs', stack_bb=100, action_taken='raise',
             facing_size=2.2, vs_position='CO'),
        dict(position='CO', hero_hand_type='AA', stack_bb=50, action_taken='raise'),
    ]
    for kw in cases:
        r = analyze_preflop(n_players=9, **kw)
        if r.get('available') and r.get('action_quality') == 'correct' and r.get('ev_loss_bb') is not None:
            assert r['ev_loss_bb'] <= 0.15, (kw, r['ev_loss_bb'])
    print("OK  test_correct_implies_zero_loss")


def test_null_when_no_coverage():
    # Função direta: bucket/cenário sem entrada → None
    elb, src = _ev_loss_bb('100bb', 'rfi', 'UTG', '', 'ZZ_naoexiste', 'raise')
    assert elb is None and src is None
    print("OK  test_null_when_no_coverage")


def test_no_pko_ev_uses_classic_skip():
    # Em PKO o ev_loss Classic NÃO se aplica (overlay PKO é futuro) → ev_loss None/ausente
    r = analyze_preflop(position='UTG', hero_hand_type='AA', stack_bb=100,
                        action_taken='raise', n_players=8, is_pko=True)
    assert r.get('pko') is True
    assert r.get('ev_loss_bb') is None
    print("OK  test_no_pko_ev_uses_classic_skip")


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
