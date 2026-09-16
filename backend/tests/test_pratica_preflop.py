# -*- coding: utf-8 -*-
"""Modo Pratica: as N mesas, e a mesa sintetica que cada spot desenha.

O que este arquivo defende, e por que cada guarda existe:

1. A mesa conta a MESMA historia que o texto do spot. Se o texto diz "UTG abre e voce esta no
   BTN" e a mesa mostra a aposta no assento do CO, o exercicio ensina o spot errado. Foi assim que
   o `buildDrillStep` do Ghost Table aproximava: ele punha a aposta enfrentada no assento
   imediatamente ANTERIOR ao heroi, que so por acaso e o abridor.
2. Nenhuma mesa aberta repete o spot de outra. Quatro mesas iguais na tela nao e treino.
3. A Academia continua identica. O Pratica abriu tres argumentos no gerador dela, e default que
   muda comportamento silenciosamente e o defeito mais barato de evitar e mais caro de achar.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab import pratica_preflop as pr                      # noqa: E402
from leaklab.academy_gto_preflop import _ACTION_ORDER          # noqa: E402


def _mesa(cenario, heroi, vilao, stack=20, facing=2.2, open_size=None):
    spot = {'scenario': cenario, 'position': heroi, 'vs_position': vilao,
            'stack_bb': stack, 'facing_size': facing}
    if open_size:
        spot['open_size'] = open_size
    return pr.mesa_do_spot(spot, hero_cards='AKs')


def _por_pos(mesa):
    return {s['pos']: s for s in mesa['seats']}


def test_a_mesa_tem_os_nove_assentos_e_o_botao_no_BTN():
    m = _mesa('rfi', 'BTN', '')
    assert len(m['seats']) == 9, len(m['seats'])
    assert [s['pos'] for s in m['seats']] == _ACTION_ORDER
    # o botao e o ASSENTO do BTN, nao o indice dele na lista: errar isso gira a mesa inteira
    assert m['button'] == _por_pos(m)['BTN']['seat'], m['button']
    assert m['street'] == 'preflop' and m['board'] == []


def test_os_blinds_ficam_postados_e_o_pote_e_a_soma():
    m = _mesa('rfi', 'CO', '')
    p = _por_pos(m)
    bb = m['bb_chips']
    assert p['SB']['bet'] == bb * 0.5, p['SB']['bet']
    assert p['BB']['bet'] == bb * 1.0, p['BB']['bet']
    assert m['pot'] == bb * 1.5, m['pot']
    # e o stack MOSTRADO ja desconta o que foi postado, como na sala
    assert p['BB']['stack'] == round(20 * bb - bb), p['BB']['stack']
    assert p['CO']['stack'] == round(20 * bb), p['CO']['stack']


def test_no_RFI_todos_os_anteriores_foldaram_e_ninguem_mais():
    m = _mesa('rfi', 'HJ', '')
    p = _por_pos(m)
    # a historia do RFI e "foldaram ate voce"
    for pos in ('UTG', 'UTG+1', 'UTG+2', 'LJ'):
        assert p[pos]['folded'], pos
    # quem fala DEPOIS do heroi ainda esta na mao: mesa que folda todo mundo ensina que o spot e
    # heads-up quando ele e de 4 jogadores por agir
    for pos in ('CO', 'BTN', 'SB', 'BB'):
        assert not p[pos]['folded'], pos
    assert not p['HJ']['folded'] and p['HJ']['hero']


def test_no_vs_RFI_a_aposta_fica_no_assento_de_QUEM_ABRIU():
    """O guarda principal. UTG abre, heroi no BTN: a aposta e do UTG, e nao do CO."""
    m = _mesa('vs_rfi', 'BTN', 'UTG', stack=30, facing=2.2)
    p = _por_pos(m)
    bb = m['bb_chips']
    # round: `100 * 2.2` da 220.00000000000003 em float, e a mesa grava 220.0
    assert p['UTG']['bet'] == round(bb * 2.2, 1), p['UTG']['bet']
    assert not p['UTG']['folded'], 'quem abriu nao esta fora da mao'
    assert p['CO']['bet'] == 0 and p['CO']['folded'], 'o vizinho do heroi foldou, nao abriu'
    # o heroi ainda nao agiu
    assert p['BTN']['bet'] == 0 and p['BTN']['hero']
    # pote = blinds + a abertura
    assert m['pot'] == round(bb * (0.5 + 1 + 2.2), 1), m['pot']


def test_no_vs_3bet_as_DUAS_apostas_ficam_na_mesa():
    """O heroi abriu e levou 3-bet. Sem a aposta dele na mesa o pote fica menor do que e, e o
    jogador decide se paga com o preco errado na tela."""
    m = _mesa('vs_3bet', 'CO', 'BTN', stack=50, facing=8.0, open_size=2.3)
    p = _por_pos(m)
    bb = m['bb_chips']
    assert p['CO']['bet'] == round(bb * 2.3, 1), p['CO']['bet']
    assert p['BTN']['bet'] == round(bb * 8.0, 1), p['BTN']['bet']
    assert m['pot'] == round(bb * (0.5 + 1 + 2.3 + 8.0), 1), m['pot']
    # quem esta ENTRE os dois foldou; quem fala antes do heroi tambem nao esta na mao
    assert not p['BTN']['folded'] and not p['CO']['folded']


def test_as_mesas_abertas_NUNCA_repetem_o_spot():
    """A primeira versao deste guarda era CEGA, e o controle pegou.

    Ela pedia 4 mesas e conferia que os 4 ids eram distintos. Com o pool real (centenas de nos x
    169 maos) duas mesas praticamente nunca colidem, entao o teste passava 12/12 mesmo com a
    deduplicacao ARRANCADA. Teste que nao falha quando deveria conta como cobertura sem dar
    cobertura.

    Agora o gerador e preso num spot unico. Sem deduplicacao, `mesas(4)` devolveria a mesma mesa
    quatro vezes; com ela, devolve UMA e para, porque nao existe segunda mesa distinta.
    """
    original = pr.generate_gto_preflop_question
    fixo = {
        'type': 'gto_rfi', 'scenario': 'rfi', 'context': 'x', 'prompt': 'x', 'hand': 'A5s',
        'hero_cards': [], 'options': [{'action': 'fold', 'label': 'Fold'}], 'xp_value': 20,
        'spot': {'position': 'BTN', 'vs_position': '', 'stack_bb': 50, 'facing_size': 0.0,
                 'is_3bet_pot': False, 'hand': 'A5s', 'scenario': 'rfi',
                 'hero_was_aggressor': False, 'facing_raises': 0},
    }
    pr.generate_gto_preflop_question = lambda *a, **k: dict(fixo)
    try:
        presas = pr.mesas(4)
    finally:
        pr.generate_gto_preflop_question = original
    assert len(presas) == 1, 'com um spot so, veio %d mesas: a deduplicacao nao esta agindo' % len(presas)

    # e com o pool real as 4 vem inteiras
    m = pr.mesas(4)
    assert len(m) == 4, len(m)
    assert len(set(x['id'] for x in m)) == 4, [x['id'] for x in m]
    for x in m:
        assert x['options'] and x['table']['seats'], x['id']


def test_a_mesa_manda_CARTAS_e_nao_a_classe_da_mao():
    """O defeito que este arquivo CONGELOU, e o dono viu na tela (16/09).

    A versao anterior deste guarda afirmava `table['hero_cards'] == x['hand']`, ou seja, exigia
    que a mesa mandasse a CLASSE (`'K7s'`). O front le as cartas com uma regex de `rank + naipe`,
    entao `'K7s'` casava so o `'7s'`: uma carta em vez de duas, e a mao do heroi nao aparecia na
    mesa. O teste passava verde afirmando exatamente o erro -- cobertura a favor do defeito.

    Agora o guarda exige o que o front consegue LER: duas cartas com naipe.
    """
    import re
    CARTA = re.compile(r'[2-9TJQKA][shdc]')
    for x in pr.mesas(4):
        cartas = x['table']['hero_cards']
        achadas = CARTA.findall(cartas or '')
        assert len(achadas) == 2, ('a mesa precisa de DUAS cartas legiveis', x['hand'], cartas)
        # e elas sao a mao do spot: ranks iguais, na mesma ordem
        ranks_mao = [c for c in x['hand'] if c in '23456789TJQKA']
        assert [c[0] for c in achadas] == ranks_mao, (x['hand'], cartas)
        # suited = MESMO naipe; offsuit e par = naipes diferentes
        mesmo_naipe = achadas[0][1] == achadas[1][1]
        assert mesmo_naipe == x['hand'].endswith('s'), (x['hand'], cartas)


def test_as_cartas_saem_da_MESMA_fonte_da_academia():
    """`cartas_da_mao` usa `_hand_to_cards`, e nao naipes proprios: naipe sorteado aqui faria a
    mesma mao aparecer com naipes diferentes entre a lista de exercicios e a mesa."""
    assert pr.cartas_da_mao('K7s') == 'Ks7s', pr.cartas_da_mao('K7s')
    assert pr.cartas_da_mao('K7o') == 'Ks7h', pr.cartas_da_mao('K7o')
    assert pr.cartas_da_mao('TT') == 'Ts Th'.replace(' ', ''), pr.cartas_da_mao('TT')
    import inspect
    assert '_hand_to_cards' in inspect.getsource(pr.cartas_da_mao)


def test_o_teto_de_mesas_e_quatro():
    assert len(pr.mesas(99)) <= pr.MAX_MESAS
    assert len(pr.mesas(0)) == 1, 'zero mesa nao e uma tela, e um erro'


def test_a_resposta_NUNCA_vem_junto_com_a_mesa():
    """A regra da casa: o gabarito so sai no submit. Se ele viesse aqui, bastaria abrir o
    inspetor para o treino inteiro virar decorativo."""
    proibidos = ('gto_action', 'best_action', 'correct', 'action_quality', 'hand_freq',
                 'recommended', 'recommended_actions', 'explanation', 'frequencies')
    for x in pr.mesas(4):
        achatado = repr(x)
        for k in proibidos:
            assert k not in achatado, (x['id'], k)


def test_o_stack_curto_ENTRA_e_o_jam_deixa_de_ser_descartado():
    """A Academia so sorteia de 30 a 100bb e joga fora spot cuja acao dominante e all-in. Num
    treino de MTT isso apagaria justamente a faixa que o grinder mais joga."""
    m = pr.mesas(4, stacks=[10, 12, 14])
    assert m, 'nenhuma mesa a 10-14bb: a faixa curta ficou de fora'
    for x in m:
        assert float(x['spot']['stack_bb']) <= 14, x['spot']['stack_bb']
    # e nessa faixa o menu tem de oferecer all-in em ALGUMA das mesas, senao o jam segue vetado
    tem_allin = any(any(o['action'] == 'allin' for o in x['options']) for x in pr.mesas(4, stacks=[10]))
    assert tem_allin, 'a 10bb nenhuma mesa ofereceu all-in'


def test_o_filtro_de_posicao_e_respeitado():
    m = pr.mesas(3, posicoes=['BTN', 'SB'])
    assert m, 'filtro de posicao zerou o sorteio'
    for x in m:
        assert x['spot']['position'] in ('BTN', 'SB'), x['spot']['position']


def test_a_ACADEMIA_continua_identica():
    """CONTROLE da mudanca que o Pratica fez no gerador compartilhado. Os tres argumentos novos
    tem default, e default que muda comportamento por descuido e o defeito mais caro de achar.
    """
    import inspect

    from leaklab import academy_gto_preflop as ac
    sig = inspect.signature(ac.generate_gto_preflop_question)
    assert sig.parameters['stacks'].default is None
    assert sig.parameters['permitir_allin'].default is False
    assert sig.parameters['posicoes'].default is None
    # e a Academia, chamada como sempre, segue nos stacks profundos e sem jam dominante
    for _ in range(12):
        q = ac.generate_gto_preflop_question('mixed')
        assert q['spot']['stack_bb'] in ac._STACKS, q['spot']['stack_bb']


def test_a_correcao_e_a_MESMA_da_academia():
    import inspect
    fonte = inspect.getsource(pr.corrigir)
    assert 'grade_gto_preflop_answer' in fonte, fonte
    # e ela corrige de verdade: um fold com AA no BTN a 50bb nao pode passar por correto
    res = pr.corrigir({'position': 'BTN', 'hand': 'AA', 'stack_bb': 50, 'scenario': 'rfi',
                       'facing_size': 0.0, 'is_3bet_pot': False}, 'fold')
    assert res is not None
    assert res.get('is_correct') is not True, res


if __name__ == '__main__':
    passed = failed = 0
    for nome, fn in sorted(list(globals().items())):
        if not nome.startswith('test_') or not callable(fn):
            continue
        try:
            fn()
            print('OK  %s' % nome)
            passed += 1
        except AssertionError as e:
            print('FALHOU  %s: %s' % (nome, e))
            failed += 1
        except Exception as e:
            import traceback
            print('ERRO    %s: %s: %s' % (nome, type(e).__name__, e))
            traceback.print_exc()
            failed += 1
    print('\nTotal: %d | Passed: %d | Failed: %d' % (passed + failed, passed, failed))
    sys.exit(1 if failed else 0)
