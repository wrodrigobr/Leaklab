# -*- coding: utf-8 -*-
"""Leitura de range DEPOIS do flop: quanto da range dele sobrevive a este board?

── O que originou (28/08) ──────────────────────────────────────────────────────────────────

O concorrente tem um treino "leia o vilão street a street". Conferindo o que nós tínhamos, a
surpresa foi que **já temos leitura de range e mais rica que a deles** — `_sondagem_de_range` mais
cinco formatos em `perguntas_de_range`. Só que todos PRÉ-FLOP.

Esta é a metade que faltava, e o motor dela apareceu por acidente no dia anterior:
`range_de_continuacao` nasceu para consertar o board pareado e é, literalmente, "quem continua
neste board".

── O que estes guardas protegem ────────────────────────────────────────────────────────────

A pergunta só ensina se o número for verdadeiro E se as alternativas forem números que o jogo
produz. Distrator inventado em volta da resposta ensina a estimar de um jeito que o jogo nunca
confirma — e é indetectável olhando a tela, porque parece uma pergunta normal.
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_board_seco_corta_MAIS_que_board_conectado():
    """A afirmação pedagógica inteira da pergunta. Se a ordem inverter, o treino ensina o contrário
    do que o poker faz, com cara de número medido."""
    from leaklab.perguntas_de_board import fracao_que_continua
    seco      = fracao_que_continua('CO', 30.0, ['Kd', '7c', '2h'])
    conectado = fracao_que_continua('CO', 30.0, ['Qh', 'Jh', 'Th'])
    trinca    = fracao_que_continua('CO', 30.0, ['2s', '2d', '2h'])
    for nome, v in (('seco', seco), ('conectado', conectado), ('trinca', trinca)):
        assert v is not None, 'sem carta para o board %s' % nome
    assert conectado > seco, (
        'board conectado (%.1f%%) deixou passar MENOS que o seco (%.1f%%)' % (conectado, seco))
    assert seco > trinca, (
        'board seco (%.1f%%) deixou passar menos que uma trinca no board (%.1f%%)' % (seco, trinca))
    print('OK  test_board_seco_corta_MAIS_que_board_conectado (%.0f%% < %.0f%% < %.0f%%)'
          % (trinca, seco, conectado))


def test_as_cartas_do_BOARD_saem_da_contagem():
    """Uma mão que usa uma carta do board não existe naquele spot. Contá-la infla o denominador e
    o número sai errado para baixo, de um jeito que ninguém percebe olhando.

    A 1ª versão deste teste comparava dois boards DIFERENTES e passou verde com o filtro removido:
    boards diferentes divergem de qualquer jeito. Ancorava no efeito, não na condição — o viés que
    já me custou quatro guardas cegos. Aqui eu olho as mãos que a contagem de fato visitou.
    """
    import leaklab.perguntas_de_board as mod
    from leaklab.range_de_continuacao import continua as _real

    vistas = []

    def espiao(mao, board, cat, com_draws=True):
        vistas.append({str(mao[0]), str(mao[1])})
        return _real(mao, board, cat, com_draws=com_draws)

    import leaklab.range_de_continuacao as rc
    rc.continua = espiao
    try:
        f = mod.fracao_que_continua('BTN', 30.0, ['As', 'Ad', '7c'])
    finally:
        rc.continua = _real

    assert f is not None and vistas, 'a contagem não visitou mão nenhuma'
    mortas = {'As', 'Ad', '7c'}
    sujas = [v for v in vistas if v & mortas]
    assert not sujas, (
        '%d de %d combos contados usam uma carta que está no board (ex.: %s) — o denominador está '
        'inflado' % (len(sujas), len(vistas), sorted(sujas[0])))
    print('OK  test_as_cartas_do_BOARD_saem_da_contagem (%d combos, nenhum com carta do board)'
          % len(vistas))


def test_os_distratores_sao_fracoes_REAIS_de_outros_boards():
    """A regra que mantém a pergunta honesta, e a mais fácil de perder num refactor.

    Alternativa inventada em volta da resposta (ex.: certa±10) ensina a estimar de um jeito que o
    jogo não confirma. Aqui toda opção tem de ser a fração medida de ALGUM board da lista.
    """
    from leaklab.perguntas_de_board import (p_quanto_sobra_no_flop, fracao_que_continua, _BOARDS)
    rng = random.Random(11)
    reais = set()
    for _n, cartas, _t in _BOARDS:
        for pos in ('UTG', 'HJ', 'CO', 'BTN', 'SB'):
            f = fracao_que_continua(pos, 30.0, cartas)
            if f is not None:
                reais.add('%.0f%%' % f)
    achou = 0
    for _ in range(12):
        q = p_quanto_sobra_no_flop(rng, rng.choice(['UTG', 'HJ', 'CO', 'BTN', 'SB']), 30.0)
        if not q:
            continue
        achou += 1
        for opcao in q['opcoes']:
            assert opcao in reais, (
                'a opção %r não é a fração de nenhum board real — distrator inventado' % opcao)
    assert achou >= 5, 'só %d perguntas geradas: o teste não exercitou nada' % achou
    print('OK  test_os_distratores_sao_fracoes_REAIS_de_outros_boards (%d perguntas)' % achou)


def test_alternativas_nao_colidem_no_arredondamento():
    """Duas opções que arredondam para o mesmo número dão uma pergunta com duas respostas certas."""
    from leaklab.perguntas_de_board import p_quanto_sobra_no_flop
    rng = random.Random(3)
    vistas = 0
    for _ in range(15):
        q = p_quanto_sobra_no_flop(rng, rng.choice(['UTG', 'CO', 'BTN']), 30.0)
        if not q:
            continue
        vistas += 1
        assert len(set(q['opcoes'])) == len(q['opcoes']), 'opções repetidas: %s' % q['opcoes']
    assert vistas >= 5, 'só %d perguntas: o teste não exercitou nada' % vistas
    print('OK  test_alternativas_nao_colidem_no_arredondamento (%d perguntas)' % vistas)


def test_a_resposta_marcada_e_a_do_BOARD_perguntado():
    """O embaralhamento é onde `correta` se perde. Aqui a opção marcada tem de ser a fração do
    board que a pergunta cita — não a de outro."""
    from leaklab.perguntas_de_board import p_quanto_sobra_no_flop, fracao_que_continua
    rng = random.Random(5)
    conferidas = 0
    for _ in range(15):
        pos = rng.choice(['UTG', 'HJ', 'CO', 'BTN'])
        q = p_quanto_sobra_no_flop(rng, pos, 30.0)
        if not q:
            continue
        conferidas += 1
        esperada = fracao_que_continua(q['posicao'], q['stack'], q['board'])
        assert q['opcoes'][q['correta']] == '%.0f%%' % esperada, (
            'a alternativa marcada (%s) não é a fração do board perguntado (%.0f%%)'
            % (q['opcoes'][q['correta']], esperada))
    assert conferidas >= 5, 'só %d perguntas conferidas' % conferidas
    print('OK  test_a_resposta_marcada_e_a_do_BOARD_perguntado (%d perguntas)' % conferidas)


def test_sem_cobertura_devolve_None_em_vez_de_inventar():
    """Profundidade sem carta não vira pergunta com número chutado. É a mesma regra do resto do
    produto: ausência declara ausência."""
    from leaklab.perguntas_de_board import fracao_que_continua, gerar
    assert fracao_que_continua('CO', 999.0, ['Kd', '7c', '2h']) is None, (
        'inventou uma fração para uma profundidade sem carta')
    assert gerar(random.Random(1), pos='POSICAO_QUE_NAO_EXISTE', stack=30.0) is None
    print('OK  test_sem_cobertura_devolve_None_em_vez_de_inventar')


def test_a_pergunta_respeita_o_contrato_das_outras():
    """Ela é renderizada pela MESMA tela das perguntas de range. Campo faltando = tela quebrada."""
    from leaklab.perguntas_de_board import gerar
    q = gerar(random.Random(2), pos='CO', stack=30.0)
    assert q, 'não gerou pergunta nenhuma'
    for campo in ('tipo', 'dificuldade', 'pergunta', 'opcoes', 'correta', 'explicacao'):
        assert campo in q, 'falta o campo %r do contrato' % campo
    assert 0 <= q['correta'] < len(q['opcoes'])
    assert len(q['opcoes']) >= 2
    print('OK  test_a_pergunta_respeita_o_contrato_das_outras')


def test_a_sondagem_SE_CALA_em_pote_3bet():
    """A regra que limita o alcance, e a mais fácil de perder.

    Em pote 3-bet o BB 3-betou e o BTN pagou: a range do BTN ali é "paga um 3-bet", muito mais
    estreita que a de abertura. Contar a RFI e chamar de "a range dele" seria afirmar um número
    verdadeiro sobre a pergunta errada — que é pior que não perguntar, porque tem cara de medido.
    """
    import random as _r
    from leaklab.perguntas_de_board import sondagem_do_board, spot_e_elegivel
    import leaklab.leak_trainer as lt

    rng = _r.Random(4)
    tres_bet = [c for c in lt._postflop_pilot_cats() if c['key'] == 'pf:bb_3bet_pot']
    assert tres_bet, 'não achei a categoria de pote 3-bet: o teste não exercita nada'
    vistos = 0
    for cat in tres_bet:
        for _ in range(10):
            spot = lt.generate_postflop_spot(cat, rng)
            if not spot:
                continue
            vistos += 1
            assert spot.get('pot_type') == '3bet', 'a categoria mudou de forma'
            assert not spot_e_elegivel(spot), 'pote 3-bet passou pela elegibilidade'
            assert sondagem_do_board(spot, rng) is None, (
                'perguntou a range de ABERTURA num pote 3-bet, onde ela não é a range dele')
    assert vistos >= 5, 'só %d spots de pote 3-bet: o teste não exercitou nada' % vistos
    print('OK  test_a_sondagem_SE_CALA_em_pote_3bet (%d spots)' % vistos)


def test_a_sondagem_SE_CALA_quando_o_HEROI_foi_quem_abriu():
    """A outra metade da elegibilidade, e ela passou verde na 1ª rodada de mutação.

    As categorias-piloto têm o herói sempre no BB, então nenhum teste exercitava um herói que
    ABRIU — e remover a guarda não quebrava nada. O spot aqui é FORJADO de propósito: é o único
    jeito de exercitar uma condição que os dados de hoje nunca produzem, mas que o acervo real
    produz (`postflop_leak_cats` gera categorias em qualquer posição).

    Se o herói abriu, o vilão é quem DEFENDEU: a range dele é de defesa, não de abertura, e a
    conta responderia outra pergunta.
    """
    import random as _r
    from leaklab.perguntas_de_board import sondagem_do_board, spot_e_elegivel

    base = {'kind': 'postflop', 'pot_type': '', 'stack_bb': 30.0,
            'board': ['Kd', '7c', '2h'], 'street': 'flop'}

    defende = dict(base, position='BB', vs_position='BTN')     # BTN abriu, BB defende
    # UTG abre, CO paga. O vilão NÃO está nos blinds de propósito: a 1ª versão deste spot usava
    # `vs_position='BB'` e a mutação passou verde, porque quem o barrava era a OUTRA regra. Guarda
    # que exercita a condição errada é cobertura sem dar cobertura.
    abriu   = dict(base, position='UTG', vs_position='CO')     # o HERÓI abriu; CO defendeu

    assert spot_e_elegivel(defende), 'o caso legítimo parou de ser elegível: o teste cegou'
    assert sondagem_do_board(defende, _r.Random(1)) is not None, (
        'o caso legítimo não gera pergunta: o controle não prova nada')

    assert not spot_e_elegivel(abriu), 'herói que ABRIU passou pela elegibilidade'
    assert sondagem_do_board(abriu, _r.Random(1)) is None, (
        'perguntou a range de ABERTURA do BB, que ali é range de DEFESA')
    print('OK  test_a_sondagem_SE_CALA_quando_o_HEROI_foi_quem_abriu')


def test_a_sondagem_SE_CALA_com_o_BB_como_vilao_e_declara_o_SB():
    """Duas exclusões com razões DIFERENTES, e o teste separa as duas.

    BB é estrutural: ele é o último a agir pré-flop e nunca abre, então a range dele ali é de
    defesa. SB é DECLARADA: ele abre de verdade e o caso seria legítimo, mas é a linha onde mora o
    limp — e a mesma em que `rangeStats` divergia. Enquanto o limp não entra na continuação, a
    fração do SB não é afirmável.

    Sem este guarda a 1ª mutação passou verde: nenhum teste exercitava vilão nos blinds.
    """
    import random as _r
    from leaklab.perguntas_de_board import sondagem_do_board, spot_e_elegivel

    base = {'kind': 'postflop', 'pot_type': '', 'stack_bb': 30.0,
            'board': ['Kd', '7c', '2h'], 'street': 'flop'}
    legitimo = dict(base, position='BB', vs_position='BTN')
    assert spot_e_elegivel(legitimo), 'o controle parou de ser elegível: o teste cegou'

    for vil, razao in (('BB', 'estrutural: o BB nunca abre'),
                       ('SB', 'declarada: o limp do SB não entra na conta')):
        spot = dict(base, position='BB', vs_position=vil)
        assert not spot_e_elegivel(spot), 'vilão %s passou (%s)' % (vil, razao)
        assert sondagem_do_board(spot, _r.Random(1)) is None, (
            'perguntou a range de abertura do %s (%s)' % (vil, razao))
    print('OK  test_a_sondagem_SE_CALA_com_o_BB_como_vilao_e_declara_o_SB')


def test_a_sondagem_SAI_pelas_duas_portas_do_gerador():
    """`generate_postflop_spot` tem duas saídas: o acervo e o catálogo estático. Anexar a sondagem
    só numa deixaria a pergunta viva ou morta conforme a origem do spot — a regra 5 inteira.

    Este guarda varre o FONTE porque as duas portas nem sempre são alcançáveis num teste (o acervo
    depende do banco). Contar `return` crus é o que pega uma porta nova esquecida amanhã.
    """
    import io as _io
    import os as _os
    import re as _re
    fonte = _io.open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..',
                                   'leaklab', 'leak_trainer.py'), encoding='utf-8').read()
    ini = fonte.index('def generate_postflop_spot(')
    fim = fonte.index(chr(10) + 'def ', ini + 10)
    corpo = fonte[ini:fim]
    # Toda saída que devolve um spot tem de passar pela função. `return None` é saída sem spot.
    cruas = [l.strip() for l in corpo.split(chr(10))
             if _re.match(r'return\s+', l.strip())
             and 'None' not in l
             and '_com_sondagem_de_board' not in l]
    assert not cruas, (
        'saída de spot sem passar por _com_sondagem_de_board: %s' % cruas)
    assert corpo.count('_com_sondagem_de_board') >= 2, (
        'só %d chamada(s): o gerador tem duas portas' % corpo.count('_com_sondagem_de_board'))
    print('OK  test_a_sondagem_SAI_pelas_duas_portas_do_gerador (%d chamadas)'
          % corpo.count('_com_sondagem_de_board'))


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
