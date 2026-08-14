# -*- coding: utf-8 -*-
"""Nó de OUTRA ESCALA não sustenta `clear_mistake` — família 1 da revisão do coach (14/08).

O caso real (mão 259091173799, A9o no BTN, fold vs 3,6bb no flop 4c8d2s): o nó postflop dita
score 0,9 e `clear_mistake` pelas frequências (call ~100%), enquanto o EV do MESMO nó marca
+3.588bb num spot de 32bb — fisicamente impossível, ou seja, o nó foi solvado num pote que não
é o deste spot (o pote não entra no spot_hash). As frequências vieram da decisão errada JUNTO
com o número. O coach gradou 'standard'; 29 acusações assim no acervo.

O cap: |ev| > pote + 2·stacks (o MESMO teto físico do ev_loss_trustworthy) e label
`clear_mistake` → `small_mistake` com o score junto. NÃO absolve: o estimador segue dizendo
que o call paga (eq 34% vs preço 25%) — derruba só o tier que exigiria confiar no nó.

A mão é TEXTO parseado (caminho vivo); o nó é dublê via `_enrich_gto` porque o defeito é a
COMBINAÇÃO nó-de-outra-escala + spot, que não dá para forjar no banco de teste com hash real.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
import leaklab.decision_engine_v11 as eng

MAO = """PokerStars Hand #900000002: Tournament #900, $1+$0 USD Hold'em No Limit - Level XIV (500/1000) - 2026/01/01 12:00:00 BRT
Table '900 1' 8-max Seat #5 is the button
Seat 1: p1 (21900 in chips)
Seat 2: p2 (24782 in chips)
Seat 3: p3 (40131 in chips)
Seat 4: p4 (10293 in chips)
Seat 5: hero (32207 in chips)
Seat 6: vilao (15238 in chips)
Seat 7: p7 (9966 in chips)
Seat 8: p8 (50415 in chips)
p1: posts the ante 150
p2: posts the ante 150
p3: posts the ante 150
p4: posts the ante 150
hero: posts the ante 150
vilao: posts the ante 150
p7: posts the ante 150
p8: posts the ante 150
vilao: posts small blind 500
p7: posts big blind 1000
*** HOLE CARDS ***
Dealt to hero [9h Ac]
p8: folds
p1: folds
p2: folds
p3: folds
p4: folds
hero: raises 1000 to 2000
vilao: calls 1500
p7: calls 1000
*** FLOP *** [4c 8d 2s]
vilao: bets 3600
p7: folds
hero: folds
Uncalled bet (3600) returned to vilao
vilao collected 7200 from pot
*** SUMMARY ***
Total pot 7200 | Rake 0
Board [4c 8d 2s]
"""


def _di_do_fold():
    hands = parse_hand_history(MAO)
    for di in build_decision_inputs_for_hand(hands[0]):
        if di.get('street') == 'flop' and (di.get('player_action') or '').lower() == 'fold':
            return di
    raise AssertionError('a fixture nao produziu o fold do flop')


def _no_critico(ev_loss_bb):
    """Dublê do nó: gto_critical com call ~100% (score 0,9 pelo recompute) e o EV dado."""
    return {
        'available': True, 'gto_action': 'call', 'gto_freq': 1.0, 'played_freq': 0.0,
        'strategy': [{'action': 'call', 'frequency': 1.0, 'ev_bb': None},
                     {'action': 'fold', 'frequency': 0.0, 'ev_bb': None}],
        'exploitability': 1.0, 'gto_label': 'gto_critical', 'source': 'postflop_db',
        'depth_capped': False, 'hand_aware': False, 'hand_strategy': None,
        'ev_loss_bb': ev_loss_bb, 'ev_loss_source': 'solver_hand',
    }


def _avalia_com_no(ev_loss_bb):
    di = _di_do_fold()
    original = eng._enrich_gto
    eng._enrich_gto = lambda _d: _no_critico(ev_loss_bb)
    try:
        return eng.evaluate_decision(di)
    finally:
        eng._enrich_gto = original


def test_ev_fora_de_escala_capa_clear_em_small():
    r = _avalia_com_no(3588.36)   # o EV real gravado no caso
    ev = r.get('evaluation') or {}
    assert ev.get('label') == 'small_mistake', (
        f"clear sustentado por EV impossivel sobreviveu: {ev.get('label')}")
    assert float(ev.get('mistakeScore') or 1) <= 0.35, ev
    # a acusacao FICA (nao e absolvicao) e o gto_label do no fica intacto
    assert (r.get('gto') or {}).get('gto_label') == 'gto_critical'
    print('OK  test_ev_fora_de_escala_capa_clear_em_small')


def test_CONTROLE_ev_plausivel_mantem_o_veredito_do_no():
    """Sem esta ancora, 'capar sempre' passaria. EV 2bb cabe no jogo: clear fica."""
    r = _avalia_com_no(2.0)
    ev = r.get('evaluation') or {}
    assert ev.get('label') == 'clear_mistake', (
        f"o cap vazou para no com EV plausivel: {ev.get('label')}")
    print('OK  test_CONTROLE_ev_plausivel_mantem_o_veredito_do_no')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FALHOU  %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
