# -*- coding: utf-8 -*-
"""test_coinpoker_allin.py — o CoinPoker escreve `ALLIN`, e nós perdíamos o all-in inteiro.

**Como apareceu:** investigando por que 46 decisões de BB ficavam sem gabarito. A memória do projeto
dizia que era falta de range de `vs_3bet` com abridor BB/SB; a medição derrubou isso (valia 2
decisões). Sobrou um balde de decisões marcadas como "ninguém subiu", e ao ler a MÃO CRUA:

    ed737bcf: ALLIN 8,826.54
    e3ae7fac: calls 8,526.54
    Hero: folds

O `ACTION_LINE_RE` aceitava `all-in` COM hífen (PS/GG) e não `ALLIN` (CoinPoker). A linha não casava
com nada e **o all-in desaparecia da mão**, em silêncio.

**O estrago não parava aí.** Sem o all-in, o herói ficava com `preflop_raises_faced=0` e
`facing_bet=0` — "ninguém subiu". Consequências em cadeia: `vs_position` saía `unknown`, o spot não
roteava para `vs_rfi`, ficava SEM GABARITO, e o `calls` seguinte (que era o call de um all-in) era
classificado como **LIMP**. Uma decisão contra 14,7bb aparecia como pote limpado.

Medido antes do conserto: **206 linhas `ALLIN` em 164 mãos** — todo all-in de CoinPoker importado.

**Lição de método:** cheguei aqui depois de derrubar quatro hipóteses minhas (falta de range
vs_3bet, `num_players<=1`, `_level_bb or 1`, "fold com check grátis"). A que valeu foi a única em
que parei de teorizar e li o texto da mão. E mesmo assim errei antes: meu primeiro recorte do raw
pegou a mão VIZINHA, e eu quase concluí sobre cartas que não eram as do spot.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.parser import ACTION_LINE_RE, parse_hand_history

# A mão REAL que expôs o bug (CoinPoker, torneio 72561, mão 92891200070), com os nicks que o
# proprio site ja anonimiza. Preservada literalmente: reescrever "para ficar legivel" e como se
# perde a caracteristica que quebrou.
_MAO = """CoinPoker Hand #92891200070: NLH (300/600/90) 2026/07/03 05:40:20 -05
Tournament '1.10 Asia Rapid Fire PKO [Turbo]' '72561' 7-max Seat #3 is the button
Seat 1: ac99a633 (1,898 in chips)
Seat 2: 733820d0 (9,953.90 in chips)
Seat 3: ed737bcf (8,916.54 in chips)
Seat 4: e3ae7fac (30,406.70 in chips)
Seat 5: Hero (3,301 in chips)
Seat 6: 79cc334b (13,816.72 in chips)
Seat 7: 7741f448 (59,496.20 in chips)
ac99a633: posts ante 90
733820d0: posts ante 90
ed737bcf: posts ante 90
e3ae7fac: posts ante 90
Hero: posts ante 90
79cc334b: posts ante 90
7741f448: posts ante 90
e3ae7fac: posts small blind 300
Hero: posts big blind 600
*** HOLE CARDS ***
Dealt to Hero [9h 5c]
79cc334b: folds
7741f448: folds
ac99a633: folds
733820d0: folds
ed737bcf: ALLIN 8,826.54
e3ae7fac: calls 8,526.54
Hero: folds
*** SUMMARY ***
Total pot 18,582.54
"""


def _acoes(hand):
    return [(a.player, a.action, a.amount) for a in (hand.actions or []) if a.street == 'preflop']


def test_a_regex_reconhece_ALLIN():
    """O ponto exato do defeito."""
    m = ACTION_LINE_RE.match('ed737bcf: ALLIN 8,826.54')
    assert m, 'a linha ALLIN nao casa com nenhuma acao'
    assert m.group('amount') == '8,826.54', m.group('amount')
    print('OK  test_a_regex_reconhece_ALLIN')


def test_as_formas_com_e_sem_hifen_viram_a_MESMA_acao():
    """Quem consome ação não pode precisar saber de qual site a mão veio."""
    h1 = parse_hand_history(_MAO)[0]
    h2 = parse_hand_history(_MAO.replace('ALLIN 8,826.54', 'all-in 8,826.54'))[0]
    a1 = [(p, a) for p, a, _ in _acoes(h1)]
    a2 = [(p, a) for p, a, _ in _acoes(h2)]
    assert a1 == a2, f'ALLIN e all-in produziram acoes diferentes:\n  {a1}\n  {a2}'
    assert ('ed737bcf', 'all-in') in a1, a1
    print('OK  test_as_formas_com_e_sem_hifen_viram_a_MESMA_acao')


def test_o_all_in_aparece_na_mao_com_o_valor_certo():
    """Antes ele sumia inteiro — e um all-in de 8.826 desaparecer muda o pote, o stack efetivo e
    quem era o agressor."""
    h = parse_hand_history(_MAO)[0]
    allins = [(p, v) for p, a, v in _acoes(h) if a == 'all-in']
    assert allins, f'o all-in nao aparece nas acoes: {_acoes(h)}'
    assert allins[0][0] == 'ed737bcf', allins
    assert abs((allins[0][1] or 0) - 8826.54) < 0.01, allins
    print('OK  test_o_all_in_aparece_na_mao_com_o_valor_certo')


def test_o_heroi_ENFRENTA_agressao_e_nao_um_pote_limpado():
    """**O dano de verdade.** Sem o all-in, o motor via "ninguem subiu": o call de 8.526 virava
    LIMP e a decisao do heroi (fold contra 14,7bb) aparecia como pote limpado — sem gabarito.

    Aqui se mede a CONSEQUENCIA, e nao so a regex: um teste que conferisse apenas o casamento da
    linha passaria mesmo se a acao fosse descartada logo depois.
    """
    h = parse_hand_history(_MAO)[0]
    acoes = _acoes(h)
    agressivas = [a for _, a, _ in acoes if a in ('all-in', 'raises', 'bets')]
    assert agressivas, f'nenhuma acao agressiva no preflop: {acoes}'
    # e o call que vem DEPOIS do all-in nao pode ser lido como limp: ele paga 8.526, nao 1bb
    calls = [(p, v) for p, a, v in acoes if a == 'calls']
    assert calls and (calls[0][1] or 0) > 8000, f'o call do all-in sumiu ou veio errado: {calls}'
    print('OK  test_o_heroi_ENFRENTA_agressao_e_nao_um_pote_limpado')


def test_nao_quebrou_as_outras_acoes():
    """O contraponto: alargar a alternância da regex podia engolir outra ação."""
    h = parse_hand_history(_MAO)[0]
    acoes = dict(((p, a) for p, a, _ in _acoes(h)))
    assert acoes.get('79cc334b') == 'folds', acoes
    assert acoes.get('Hero') == 'folds', acoes
    assert acoes.get('e3ae7fac') == 'calls', acoes
    for linha, esperado in (('x: raises 300 to 400', 'raises'), ('x: calls 50', 'calls'),
                            ('x: folds', 'folds'), ('x: checks', 'checks'),
                            ('x: bets 120', 'bets'), ('x: all-in 500', 'all-in')):
        m = ACTION_LINE_RE.match(linha)
        assert m and m.group('action').lower() == esperado, (linha, m.group('action') if m else None)
    print('OK  test_nao_quebrou_as_outras_acoes')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
    raise SystemExit(1 if fail else 0)
