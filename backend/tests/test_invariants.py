"""
test_invariants.py — Guarda os INVARIANTES de docs/specs/invariants.md.

Cada teste mapeia um INV-N. Se um destes falha, um CONTRATO CRÍTICO quebrou — o
sistema corromperia vereditos silenciosamente (sem erro). Ao mudar comportamento
coberto por um invariante, atualize o teste E o spec juntos (mesmo commit).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.preflop_gto_ranges import analyze_preflop


def test_inv_faces_squeeze_routing():
    """INV-1: faces_squeeze exige facing_raises>=2 + not hero_was_aggressor.
    Omitir os sinais muda o roteamento (faces_squeeze → vs_rfi) → 'call vs squeeze'.
    Todo path de display DEVE passar os sinais."""
    base = dict(position='BB', hero_hand_type='54s', stack_bb=29.7, action_taken='fold',
                facing_size=9.0, vs_position='SB', is_3bet_pot=True, n_players=9)
    com = analyze_preflop(**base, facing_raises=2, hero_was_aggressor=False)
    sem = analyze_preflop(**base)  # caller que esquece os sinais (o bug)
    assert com['scenario'] == 'faces_squeeze', com['scenario']
    assert sem['scenario'] == 'vs_rfi', sem['scenario']
    assert com['scenario'] != sem['scenario'], "os sinais DEVEM alterar o roteamento"
    print("OK  test_inv_faces_squeeze_routing")


def test_inv_squeeze_offrange_folds():
    """INV-1/INV-3: mão fora do range de defesa vs squeeze → fold, NUNCA call largo."""
    r = analyze_preflop(position='BB', hero_hand_type='54s', stack_bb=29.7,
                        action_taken='fold', facing_size=9.0, vs_position='SB',
                        is_3bet_pot=True, n_players=9, facing_raises=2, hero_was_aggressor=False)
    assert r['scenario'] == 'faces_squeeze'
    assert r['in_range'] is False
    assert 'call' not in r['recommended_actions'], r['recommended_actions']
    print("OK  test_inv_squeeze_offrange_folds")


def test_inv_null_honesty():
    """INV-3: não-decisão (BB check em pote não-contestado) → available=False,
    sem veredito fabricado."""
    r = analyze_preflop(position='BB', hero_hand_type='72o', stack_bb=30,
                        action_taken='check', facing_size=0.0, vs_position='',
                        is_3bet_pot=False, n_players=9, facing_raises=0, hero_was_aggressor=False)
    assert r['scenario'] == 'rfi'
    assert r['available'] is False, r
    print("OK  test_inv_null_honesty")


def test_inv_gw_valid_depths():
    """INV-4: 70bb NÃO é depth válido na árvore simétrica do GW; snap pro mais
    próximo (60/80). Ter 70 fazia stacks ~70bb snaparem pro inexistente."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(here, 'gto_bot', 'solver_api'))
    import server as gs
    assert 70 not in gs._GW_VALID_DEPTHS, "70bb não existe na árvore simétrica do GW"
    assert 60 in gs._GW_VALID_DEPTHS and 80 in gs._GW_VALID_DEPTHS
    assert gs._snap_to_valid_depth(75) == 80, gs._snap_to_valid_depth(75)
    assert gs._snap_to_valid_depth(60) == 60
    assert gs._snap_to_valid_depth(32) == 32
    print("OK  test_inv_gw_valid_depths")


def test_inv_hand_freq_distribution():
    """INV-10: quando available=True, hand_freq é a distribuição da AÇÃO DA MÃO e
    DEVE somar ~1 (nunca None nem tudo-zero). None/tudo-zero faz o display cair no
    % AGREGADO do range (distribuição da posição) em vez do veredito da carta.
    Cobre out-of-range em todos os cenários: rfi, vs_rfi, faces_squeeze."""
    cases = [
        # (descrição, kwargs) — todas mãos out-of-range (o caso que quebrava)
        ('rfi 83o',          dict(position='LJ', hero_hand_type='83o', stack_bb=15.4, action_taken='fold',
                                  facing_size=0.0, vs_position='', is_3bet_pot=False, n_players=9,
                                  facing_raises=0, hero_was_aggressor=False)),
        ('vs_rfi 82o BTN',   dict(position='BTN', hero_hand_type='82o', stack_bb=12.1, action_taken='fold',
                                  facing_size=2.0, vs_position='HJ', is_3bet_pot=False, n_players=9,
                                  facing_raises=1, hero_was_aggressor=False)),
        ('faces_squeeze TT', dict(position='HJ', hero_hand_type='TT', stack_bb=20, action_taken='call',
                                  facing_size=9.0, vs_position='SB', is_3bet_pot=True, n_players=9,
                                  facing_raises=2, hero_was_aggressor=False)),
    ]
    for desc, kw in cases:
        r = analyze_preflop(**kw)
        if not r.get('available'):
            continue
        hf = r.get('hand_freq')
        assert hf is not None, f"{desc}: hand_freq=None (cairia no agregado)"
        s = sum(hf.values())
        assert s > 0.5, f"{desc}: hand_freq soma {s} (tudo-zero → cairia no agregado): {hf}"
        assert abs(s - 1.0) < 0.05, f"{desc}: hand_freq não normalizado (soma {s}): {hf}"
    print("OK  test_inv_hand_freq_distribution")


def _all_169_hands():
    """Os 169 tipos de mão (13 pares + 78 suited + 78 offsuit)."""
    R = 'AKQJT98765432'
    hs = []
    for i, a in enumerate(R):
        for j, b in enumerate(R):
            if i == j:   hs.append(a + b)
            elif i < j:  hs.append(a + b + 's')
            else:        hs.append(b + a + 'o')
    return hs


def test_inv_no_covered_spot_is_all_fold():
    """INV-11: nenhum spot COBERTO é 100%-fold nas 169 mãos. Guarda o acoplamento
    do qual INV-10 depende: `available=True` ⟹ range realmente carregada (não-vazia).
    Se uma captura parcial gravasse só metade do grid, o spot ficaria available mas
    sem nenhuma mão agindo — e a normalização do INV-10 mostraria 'Fold 100%' até
    para mãos fortes, silenciosamente. Em spot coberto SEMPRE há mãos que agem
    (call/raise/allin). Spots canônicos (rápido); a varredura completa dos 741
    spots reais deu 0 suspeitos."""
    spots = [
        ('rfi LJ 15bb',            dict(position='LJ', stack_bb=15.4, facing_size=0.0,
                                        vs_position='', is_3bet_pot=False, facing_raises=0,
                                        hero_was_aggressor=False)),
        ('vs_rfi BTN vs HJ 12bb',  dict(position='BTN', stack_bb=12.1, facing_size=2.0,
                                        vs_position='HJ', is_3bet_pot=False, facing_raises=1,
                                        hero_was_aggressor=False)),
        ('faces_squeeze CO vs MP1 62bb', dict(position='CO', stack_bb=62.0, facing_size=600.0,
                                        vs_position='MP1', is_3bet_pot=True, facing_raises=2,
                                        hero_was_aggressor=False)),
    ]
    for label, kw in spots:
        loaded = acting = 0
        for hh in _all_169_hands():
            r = analyze_preflop(hero_hand_type=hh, action_taken='fold', n_players=9, **kw)
            if not r.get('available'):
                continue
            loaded += 1
            hf = r.get('hand_freq') or {}
            if (hf.get('call', 0) + hf.get('raise', 0) + hf.get('allin', 0)) > 0.01:
                acting += 1
        assert loaded > 100, f"{label}: só {loaded}/169 available — spot deixou de estar coberto?"
        assert acting > 0, (f"{label}: spot coberto ({loaded}/169) mas 0 mãos agem — "
                            f"range vazia/parcial; INV-10 mostraria 'Fold 100%' para mãos fortes")
    print("OK  test_inv_no_covered_spot_is_all_fold")


def test_inv_3bet_sizing_order():
    """INV-6: 3bet/squeeze é RAI (shove) em stack raso, R6 (raise) em fundo."""
    from leaklab.preflop_autocapture import _3BET_ORDER
    assert _3BET_ORDER['10bb'][0] == 'RAI', _3BET_ORDER['10bb']
    assert _3BET_ORDER['14bb'][0] == 'RAI'
    assert _3BET_ORDER['30bb'][0] == 'R6', _3BET_ORDER['30bb']
    assert _3BET_ORDER['100bb'][0] == 'R6'
    print("OK  test_inv_3bet_sizing_order")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"FAIL {name}: {e}"); failed += 1
    print(f"\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
