"""
#23 — Vereditos preflop sensíveis ao tamanho do open. Quando o vilão abre OFF-TREE
(maior que o sizing canônico do GTO), a range de defesa mostrada é vs o open mínimo.

── A política mudou em 09/08, e estes testes mudaram com ela ─────────────────────────────────

A regra original REBAIXAVA o fold da mão marginal (leak/major_leak → acceptable) e mantinha a
recomendação na tela. O problema é que a recomendação também vinha do preço errado: no mesmo card
que dizia "seu fold é aceitável" continuava impresso "GTO joga Call" — call derivado de um open de
2bb, num spot em que o vilão abriu 3,3bb. E do lado do CALL o rebaixamento não fazia nada: pagar
com uma mão que a carta paga a 2bb saía `correct` a qualquer preço, que é a ABSOLVIÇÃO falsa.

Agora, quando o tamanho enfrentado sai da tolerância de 1,4x e a resposta da carta para AQUELA mão
depende do preço, não há veredito: `available=False`, `coverage_reason='open_size_off_tree'`. Sem
gabarito não é erro.

O que NÃO mudou, e é o coração do #23: mão que a carta defende AGREDINDO (raise+allin > call)
continua sendo gradeada, porque foldar AA nunca é defensável por o open ter vindo maior. É a mesma
definição de "mão de value" de antes, agora numa função só (`_defesa_e_de_valor`), consumida pelo
rebaixamento E pelo teto de tamanho.
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


def test_offtree_fold_sem_veredito():
    """Antes: fold rebaixado para `acceptable`. Agora: sem veredito — a carta defende 75o com
    call 100%, e a 3,3bb (1,65x) essa resposta pode ser outra. O CONTROLE do open normal, que
    prova que o guarda não comeu a cobertura inteira, é a metade que importa aqui."""
    base = _vs_rfi('fold', facing_to_bb=2.0)   # open normal
    off  = _vs_rfi('fold', facing_to_bb=3.3)   # open off-tree (1.65×)
    assert base['action_quality'] in ('leak', 'major_leak'), base['action_quality']
    assert base.get('open_size_mismatch') is None
    assert off['available'] is False, off['action_quality']
    assert off.get('coverage_reason') == 'open_size_off_tree', off.get('coverage_reason')
    print("OK  test_offtree_fold_sem_veredito")


def test_premium_fold_stays_critical_offtree():
    # Foldar mão de VALUE (que o GTO 3beta) é SEMPRE crítico, mesmo vs open maior —
    # o rebaixamento só vale pra defesa marginal (call-dominada).
    for h in ('AA', 'KK', 'QQ', 'AKs', '99'):
        r = _vs_rfi('fold', facing_to_bb=3.3, hand=h)
        assert r['action_quality'] in ('leak', 'major_leak'), f"{h}: {r['action_quality']}"
        assert r.get('open_size_mismatch') is not None  # flag anexada mesmo sem rebaixar
    print("OK  test_premium_fold_stays_critical_offtree")


def test_offtree_call_nao_e_mais_absolvido():
    """O lado que o #23 nunca cobriu. A regra antiga só mexia no fold, então pagar 3,3bb com 75o
    saía `correct` — a carta larga demais ABSOLVENDO quem paga, que é a metade cara do erro de
    preço. Agora cala dos dois lados."""
    c = _vs_rfi('call', facing_to_bb=3.3)
    assert c['available'] is False, c['action_quality']
    assert c.get('coverage_reason') == 'open_size_off_tree', c.get('coverage_reason')
    # CONTROLE: no tamanho que o nó modela, o call segue gradeado
    ok = _vs_rfi('call', facing_to_bb=2.0)
    assert ok['available'] is True and ok['action_quality'] == 'correct', ok['action_quality']
    print("OK  test_offtree_call_nao_e_mais_absolvido")


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
