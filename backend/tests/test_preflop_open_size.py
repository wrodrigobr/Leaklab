"""
#23 — Vereditos preflop sensíveis ao tamanho do open. Quando o vilão abre OFF-TREE
(maior que o sizing canônico do GTO), a range de defesa mostrada é vs o open mínimo;
foldar uma mão marginal vs um open maior é DEFENSÁVEL e não deve virar gto_critical.
O engine rebaixa o fold (leak/major_leak → acceptable) e anexa a flag open_size_mismatch.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.preflop_gto_ranges import analyze_preflop, _canonical_open_bb, _load, _stack_bucket
from leaklab.hand_state_builder import _facing_to_total_at
from leaklab.models import ParsedAction


def _vs_rfi(action, facing_to_bb, hand='75o', pos='BB', vs='CO', stack=30):
    # facing_size>0 (chips) roteia pro vs_rfi; facing_to_bb é o tamanho do open em bb
    return analyze_preflop(position=pos, hero_hand_type=hand, stack_bb=stack,
                           action_taken=action, facing_size=200, vs_position=vs,
                           facing_raises=1, n_players=9, facing_to_bb=facing_to_bb)


def test_canonical_open_bb_reads_rcode():
    bk = _load()['ranges'][_stack_bucket(30)]
    co = _canonical_open_bb(bk, 'CO')
    assert co and 1.8 <= co <= 2.6, f"CO open canônico esperado ~2bb, veio {co}"
    # posição inexistente → None
    assert _canonical_open_bb(bk, 'ZZ') is None
    print(f"OK  test_canonical_open_bb_reads_rcode (CO={co})")


def test_offtree_fold_downgraded():
    base = _vs_rfi('fold', facing_to_bb=2.0)   # open normal
    off  = _vs_rfi('fold', facing_to_bb=3.3)   # open off-tree (1.65×)
    assert base['action_quality'] in ('leak', 'major_leak'), base['action_quality']
    assert base.get('open_size_mismatch') is None
    assert off['action_quality'] == 'acceptable', off['action_quality']
    assert off['open_size_mismatch'] == {'facing_bb': 3.3, 'canonical_bb': 2.0}
    print("OK  test_offtree_fold_downgraded")


def test_premium_fold_stays_critical_offtree():
    # Foldar mão de VALUE (que o GTO 3beta) é SEMPRE crítico, mesmo vs open maior —
    # o rebaixamento só vale pra defesa marginal (call-dominada).
    for h in ('AA', 'KK', 'QQ', 'AKs', '99'):
        r = _vs_rfi('fold', facing_to_bb=3.3, hand=h)
        assert r['action_quality'] in ('leak', 'major_leak'), f"{h}: {r['action_quality']}"
        assert r.get('open_size_mismatch') is not None  # flag anexada mesmo sem rebaixar
    print("OK  test_premium_fold_stays_critical_offtree")


def test_offtree_only_fold_softened():
    # call/raise vs open off-tree NÃO é rebaixado (só o fold falso-crítico)
    c = _vs_rfi('call', facing_to_bb=3.3)
    assert c['action_quality'] == 'correct', c['action_quality']
    # mas a flag fica anexada pra transparência no card
    assert c.get('open_size_mismatch') is not None
    print("OK  test_offtree_only_fold_softened")


def test_no_downgrade_without_facing_to_bb():
    # sem o sinal (dado antigo / caller não threada) → comportamento inalterado
    r = _vs_rfi('fold', facing_to_bb=0.0)
    assert r['action_quality'] in ('leak', 'major_leak')
    assert r.get('open_size_mismatch') is None
    print("OK  test_no_downgrade_without_facing_to_bb")


def test_slightly_bigger_open_not_offtree():
    # open 2.5bb vs canônico 2.0 = 1.25× (< 1.4) → dentro da variação, não rebaixa
    r = _vs_rfi('fold', facing_to_bb=2.5)
    assert r.get('open_size_mismatch') is None, r.get('open_size_mismatch')
    assert r['action_quality'] in ('leak', 'major_leak')
    print("OK  test_slightly_bigger_open_not_offtree")


def test_facing_to_total_parses_raise_to():
    # PokerStars 'raises 546 to 626' → captura o TOTAL 626 (não o incremento 546)
    acts = [ParsedAction(player='v', street='preflop', action='raises', amount=546.0,
                         raw='petretudor: raises 546 to 626')]
    assert _facing_to_total_at(acts, 1, 'preflop') == 626.0
    # GG 'raises to 1500' (amount=1500, sem incremento no raw) → usa amount
    acts2 = [ParsedAction(player='v', street='preflop', action='raises', amount=1500.0,
                          raw='Hero: raises to 1500')]
    assert _facing_to_total_at(acts2, 1, 'preflop') == 1500.0
    print("OK  test_facing_to_total_parses_raise_to")


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
