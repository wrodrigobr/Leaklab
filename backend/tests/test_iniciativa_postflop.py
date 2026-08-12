# -*- coding: utf-8 -*-
"""`hero_was_aggressor` no postflop e INICIATIVA — e ate 12/08 era zero em 2.903 de 2.903 linhas.

── As duas semanticas, e por que nenhuma engole a outra ──────────────────────────────────────

PREFLOP: "o hero JA agrediu nesta street" (qualquer raise). E o que o roteamento exige — hero
abre, vilao 3-beta, decisao do hero: True, mesmo com o ultimo raise sendo do vilao. Este arquivo
GUARDA essa semantica com teste proprio, porque o conserto do postflop nao pode muda-la (106
decisoes ja foram parar no no errado quando esse sinal se perdeu).

POSTFLOP: a ultima acao agressiva da mao ate a decisao e do hero? Quem abriu preflop tem a
iniciativa no flop; quem c-betou a mantem no turn; o check-raise do vilao a toma. A distincao
"foi o PRIMEIRO a agredir" seria errada de proposito: no check-raise o hero apostou primeiro e
quem chega ao turn com a iniciativa e o vilao.

── Por que as maos sao TEXTO parseado, nao dicts montados ────────────────────────────────────

O caminho vivo e parse -> build_decision_inputs -> spot. Fixture de dict ja passou pelo motivo
errado nesta sessao (AKs 7.85bb); texto real percorre o mesmo codigo que producao.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand

CABECALHO = """PokerStars Hand #%d: Tournament #900, $1+$0 USD Hold'em No Limit - Level I (10/20)
Table '900 1' 6-max Seat #1 is the button
Seat 1: villain (2000 in chips)
Seat 2: hero (2000 in chips)
Seat 3: outro (2000 in chips)
hero: posts small blind 10
outro: posts big blind 20
*** HOLE CARDS ***
Dealt to hero [Ah Kd]
"""


def _spots(corpo, n=1):
    """Parseia a mao e devolve {(street, acao): heroWasAggressor} das decisoes do hero."""
    hands = parse_hand_history(CABECALHO % n + corpo)
    assert len(hands) == 1, f'parse devolveu {len(hands)} maos'
    out = {}
    for di in build_decision_inputs_for_hand(hands[0]):
        chave = (di['street'], (di.get('player_action') or '').lower())
        out[chave] = bool(di['spot'].get('heroWasAggressor'))
    assert out, 'nenhuma decisao do hero — a fixture nao exercita nada'
    return out


def test_quem_abriu_preflop_tem_a_iniciativa_no_flop():
    s = _spots("""villain: folds
hero: raises 40 to 60
outro: calls 40
*** FLOP *** [2h 7c 9d]
outro: checks
hero: bets 80
outro: folds
Uncalled bet (80) returned to hero
hero collected 130 from pot
*** SUMMARY ***
Total pot 130 | Rake 0
""", n=1)
    assert s[('flop', 'bet')] is True, s
    print('OK  test_quem_abriu_preflop_tem_a_iniciativa_no_flop')


def test_donk_bet_do_vilao_toma_a_iniciativa():
    s = _spots("""villain: folds
hero: raises 40 to 60
outro: calls 40
*** FLOP *** [2h 7c 9d]
outro: bets 100
hero: folds
Uncalled bet (100) returned to outro
outro collected 130 from pot
*** SUMMARY ***
Total pot 130 | Rake 0
""", n=2)
    assert s[('flop', 'fold')] is False, s
    print('OK  test_donk_bet_do_vilao_toma_a_iniciativa')


def test_cbet_mantem_a_iniciativa_no_turn():
    s = _spots("""villain: folds
hero: raises 40 to 60
outro: calls 40
*** FLOP *** [2h 7c 9d]
outro: checks
hero: bets 80
outro: calls 80
*** TURN *** [2h 7c 9d] [Qs]
outro: checks
hero: bets 200
outro: folds
Uncalled bet (200) returned to hero
hero collected 290 from pot
*** SUMMARY ***
Total pot 290 | Rake 0
""", n=3)
    assert s[('turn', 'bet')] is True, s
    print('OK  test_cbet_mantem_a_iniciativa_no_turn')


def test_check_raise_do_vilao_TOMA_a_iniciativa():
    """A distincao ULTIMO-vs-primeiro: o hero apostou primeiro no flop, o vilao raisou por
    cima. Quem carrega a iniciativa dali em diante e o vilao — 'primeiro a agredir' daria o
    resultado errado exatamente aqui."""
    s = _spots("""villain: folds
hero: raises 40 to 60
outro: calls 40
*** FLOP *** [2h 7c 9d]
outro: checks
hero: bets 80
outro: raises 160 to 240
hero: calls 160
*** TURN *** [2h 7c 9d] [Qs]
outro: bets 300
hero: folds
Uncalled bet (300) returned to outro
outro collected 610 from pot
*** SUMMARY ***
Total pot 610 | Rake 0
""", n=4)
    assert s[('flop', 'call')] is False, s   # enfrentando o check-raise
    assert s[('turn', 'fold')] is False, s   # a iniciativa ficou com o vilao
    print('OK  test_check_raise_do_vilao_TOMA_a_iniciativa')


def test_pote_sem_agressao_nao_tem_agressor():
    s = _spots("""villain: folds
hero: calls 10
outro: checks
*** FLOP *** [2h 7c 9d]
outro: checks
hero: checks
*** TURN *** [2h 7c 9d] [Qs]
outro: checks
hero: bets 40
outro: folds
Uncalled bet (40) returned to hero
hero collected 40 from pot
*** SUMMARY ***
Total pot 40 | Rake 0
""", n=5)
    assert s[('turn', 'bet')] is False, s   # ate a decisao, ninguem agrediu
    assert s[('flop', 'check')] is False, s
    print('OK  test_pote_sem_agressao_nao_tem_agressor')


def test_REGRESSAO_semantica_preflop_intocada():
    """Hero abre, vilao 3-beta, decisao do hero: True — 'ja agrediu', NAO 'ultimo agressor'.
    O roteamento vs_3bet depende disto; se este teste quebrar, 106 decisoes voltam ao no errado."""
    s = _spots("""villain: raises 40 to 60
hero: raises 120 to 180
outro: folds
villain: raises 300 to 480
hero: folds
Uncalled bet (300) returned to villain
villain collected 400 from pot
*** SUMMARY ***
Total pot 400 | Rake 0
""", n=6)
    assert s[('preflop', 'fold')] is True, s   # semantica antiga: hero JA raisou
    print('OK  test_REGRESSAO_semantica_preflop_intocada')


def _spots_entrada(corpo, n):
    """{(street, acao): iniciativaDaStreet} — o sinal da ENTRADA da street, nao o da decisao."""
    hands = parse_hand_history(CABECALHO % n + corpo)
    out = {}
    for di in build_decision_inputs_for_hand(hands[0]):
        out[(di['street'], (di.get('player_action') or '').lower())] =             di['spot'].get('iniciativaDaStreet')
    return out


def test_iniciativa_da_ENTRADA_distingue_cbet_de_donk():
    """`hero_was_aggressor` na decisao e False nos DOIS casos (a ultima agressao e a aposta do
    vilao). O sinal que distingue e quem tinha a iniciativa quando a street COMECOU."""
    # c-bet: o VILAO (outro) abriu pre e c-beta o flop — na entrada do flop a iniciativa e dele.
    s = _spots("""villain: folds
outro: raises 40 to 60
hero: calls 50
*** FLOP *** [2h 7c 9d]
outro: bets 80
hero: folds
Uncalled bet (80) returned to outro
outro collected 130 from pot
*** SUMMARY ***
Total pot 130 | Rake 0
""", n=7)
    e = _spots_entrada("""villain: folds
outro: raises 40 to 60
hero: calls 50
*** FLOP *** [2h 7c 9d]
outro: bets 80
hero: folds
Uncalled bet (80) returned to outro
outro collected 130 from pot
*** SUMMARY ***
Total pot 130 | Rake 0
""", n=7)
    assert s[('flop', 'fold')] is False               # na decisao: a aposta e a ultima agressao
    assert e[('flop', 'fold')] == 'vilao', e          # na entrada: c-bet — o vilao a MANTEVE

    # donk: o HERO abriu pre; o vilao aposta no flop CONTRA o agressor.
    e2 = _spots_entrada("""villain: folds
hero: raises 40 to 60
outro: calls 40
*** FLOP *** [2h 7c 9d]
outro: bets 100
hero: folds
Uncalled bet (100) returned to outro
outro collected 130 from pot
*** SUMMARY ***
Total pot 130 | Rake 0
""", n=8)
    assert e2[('flop', 'fold')] == 'hero', e2         # na entrada: a iniciativa era do HERO
    print('OK  test_iniciativa_da_ENTRADA_distingue_cbet_de_donk')


def test_iniciativa_da_entrada_pote_passivo_e_None_e_preflop_nao_tem():
    e = _spots_entrada("""villain: folds
hero: calls 10
outro: checks
*** FLOP *** [2h 7c 9d]
outro: bets 40
hero: folds
Uncalled bet (40) returned to outro
outro collected 40 from pot
*** SUMMARY ***
Total pot 40 | Rake 0
""", n=9)
    assert e[('flop', 'fold')] is None, e             # limpado: ninguem agrediu antes do flop
    assert e[('preflop', 'call')] is None, e          # preflop nao tem street anterior
    print('OK  test_iniciativa_da_entrada_pote_passivo_e_None_e_preflop_nao_tem')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FAIL    %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
