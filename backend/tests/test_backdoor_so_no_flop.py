# -*- coding: utf-8 -*-
"""Backdoor exige DUAS cartas por vir — não existe no turn nem no river.

── O caso que originou (25/08, auditoria pré-lançamento) ──────────────────────────────────

Um juiz de poker notou o rótulo `BDSD` numa decisão de turn e apontou o óbvio: backdoor precisa
de duas cartas por vir, e no turn resta uma. Medido no acervo: **639 de 870 decisões de turn
(73%)** carregavam rótulo de backdoor. No river, zero — o defeito era específico do turn.

O caso que mostra o tamanho: `As3s` no board `Qs 8s 9s Ad`. O hero tem **flush máximo feito** num
board monotone de espadas, e a tela descrevia a mão como projeto de sequência backdoor.

── Por que medir antes de consertar ───────────────────────────────────────────────────────

O rótulo não é só texto: cada backdoor dá um boost de equity (+0,06 flush, +0,04 straight).
Tirá-lo poderia mover veredito — o tipo de conserto que precisa de número antes (regra 7).

A primeira medição errou o denominador — olhou só quem ENFRENTA aposta, e o ramo em que o draw
decide a zona de range é o do hero agindo SEM aposta na frente. A segunda estava cega: injetava
`drawProfile` no dict já montado, quando a conta acontece no pipeline. O controle denunciou as
duas, com zero até sob boost forjado de +0,50.

Medição válida (monkeypatch do detector + reprocesso, controle vivo em 2 de 366): **1 veredito
muda em 163 decisões com backdoor (0,6%)**, `marginal` → `small_mistake`, e a acusação nova é
justa — o hero vinha sendo absolvido por 10 pontos de equity de um projeto inexistente.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_backdoor_existe_no_flop():
    """Controle. Sem ele, desligar o detector inteiro passaria no teste seguinte."""
    from leaklab.draw_detector import detect_draws

    p = detect_draws('AhKh', ['2h', '7d', '9s'])
    assert p.backdoor_flush_draw is True, (
        'BDFD sumiu do FLOP: duas espadas do hero mais uma do board, com duas cartas por vir')
    print('OK  test_backdoor_existe_no_flop')


def test_backdoor_NAO_existe_no_turn_nem_no_river():
    from leaklab.draw_detector import detect_draws

    turn = detect_draws('AhKh', ['2h', '7d', '9s', '3c'])
    assert turn.backdoor_flush_draw is False, (
        'BDFD no turn: backdoor exige DUAS cartas por vir e resta uma — 73%% das decisões de '
        'turn do acervo carregavam esse rótulo')
    assert turn.backdoor_straight_draw is False, 'BDSD no turn'

    river = detect_draws('AhKh', ['2h', '7d', '9s', '3c', '4d'])
    assert river.backdoor_flush_draw is False, 'BDFD no river, onde não vem carta nenhuma'
    assert river.backdoor_straight_draw is False, 'BDSD no river'
    print('OK  test_backdoor_NAO_existe_no_turn_nem_no_river')


def test_o_flush_MAXIMO_nao_e_descrito_como_projeto():
    """O caso concreto que a auditoria pegou: `As3s` em `Qs 8s 9s Ad` é flush máximo FEITO."""
    from leaklab.draw_detector import detect_draws

    p = detect_draws('As3s', ['Qs', '8s', '9s', 'Ad'])
    # `str(p)` é o rótulo REAL que vai para a coluna `draw_profile`. A primeira versão chamava
    # `p.to_string()` sob um `hasattr` — método que NÃO existe —, então comparava contra string
    # vazia e passava sempre. Asserção morta é cobertura sem cobrir.
    rotulo = str(p)
    assert 'BD' not in rotulo.upper(), (
        'flush máximo no turn voltou a ser descrito como projeto backdoor: %r' % rotulo)
    assert p.backdoor_straight_draw is False and p.backdoor_flush_draw is False
    print('OK  test_o_flush_MAXIMO_nao_e_descrito_como_projeto')


def test_draws_REAIS_do_turn_sobrevivem():
    """Contraprova, e é ela que dá valor aos testes acima: o corte não pode zerar draw legítimo.

    No turn o OESD e o flush draw continuam existindo — falta uma carta, que é exatamente o que
    esses projetos precisam."""
    from leaklab.draw_detector import detect_draws

    oesd = detect_draws('AhKh', ['2h', '7d', '9s', '3c', '4d'])
    assert oesd.oesd is True, 'o corte zerou um draw REAL: a poda passou do alvo'

    fd = detect_draws('AhKh', ['2h', '7h', '9s', '3c'])
    assert fd.flush_draw is True, 'flush draw do turn sumiu — ele precisa de UMA carta, não duas'
    print('OK  test_draws_REAIS_do_turn_sobrevivem')


def test_o_corte_olha_o_TAMANHO_do_board():
    """Prova de fiação: o corte tem que depender de quantas cartas faltam, não de um parâmetro
    de street que o chamador pode esquecer de passar."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'draw_detector.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    i = fonte.index('def detect_draws')
    corpo = fonte[i:fonte.index(chr(10) + 'def ', i + 10)]
    codigo = chr(10).join(l.split('#')[0] for l in corpo.split(chr(10)))
    assert 'len(board_parsed) >= 4' in codigo, (
        'o corte de backdoor saiu de `detect_draws` ou deixou de olhar o tamanho do board')
    print('OK  test_o_corte_olha_o_TAMANHO_do_board')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
