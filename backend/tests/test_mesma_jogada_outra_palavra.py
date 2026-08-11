# -*- coding: utf-8 -*-
"""Shove, jam e all-in sao a MESMA jogada. Nenhum ponto do score pode cobrar pela palavra.

── O que acontecia ────────────────────────────────────────────────────────────────────────────

O pipeline grava a acao do hero como 'shove'. O ramo push/fold de `preflop_range_evaluator`
devolve a recomendacao como 'jam'. Tres funcoes do score comparavam as strings CRUAS —
`calc_base_action_gap`, `calc_range_penalty` e `calc_context_penalty` — enquanto o `math_penalty`,
dentro da MESMA expressao, ja normalizava com `_norm_gto_action`. Assimetria no mesmo bloco.

Medido no acervo de producao em 10/08: 160 decisoes em que a acao jogada e a recomendada sao a
mesma jogada com palavra diferente. Nove delas pagaram 0,18 de gap mais 0,08 de range_penalty, e
CINCO viraram acusacao — o card dizia "Acao esperada: ALL-IN" para quem tinha dado all-in.

── Por que a varredura do FONTE, e nao so os tres casos ───────────────────────────────────────

CLAUDE.md, item 5: regra aplicada em N lugares vira funcao com teste que varre os N+1. A funcao
ja existia (`_norm_gto_action`) e mesmo assim tres chamadores nao a usavam. Testar so as tres
provaria o conserto de hoje; a quarta funcao que alguem escrever amanha passa batido. Por isso o
ultimo teste le o ARQUIVO e reprova qualquer comparacao crua nova entre as duas acoes.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import (calc_base_action_gap, calc_context_penalty,
                                         calc_range_penalty, evaluate_decision)

MOTOR = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
SINONIMOS = ('shove', 'jam', 'allin', 'all-in')


def test_gap_nao_cobra_pela_palavra():
    for a in SINONIMOS:
        for b in SINONIMOS:
            assert calc_base_action_gap(a, b) == 0.0, f'{a} vs {b}'
    # CONTROLE: jogadas de verdade diferentes continuam custando.
    assert calc_base_action_gap('fold', 'call') > 0
    assert calc_base_action_gap('shove', 'fold') > 0
    print('OK  test_gap_nao_cobra_pela_palavra')


def test_range_penalty_nao_cobra_pela_palavra():
    for zona in ('core_range', 'borderline_range', 'outside_range'):
        assert calc_range_penalty(zona, 'shove', 'jam') == 0.0, zona
        # CONTROLE: fora da sinonimia a penalidade daquela zona reaparece.
        assert calc_range_penalty(zona, 'fold', 'jam') > 0, zona
    print('OK  test_range_penalty_nao_cobra_pela_palavra')


def test_context_penalty_nao_cobra_pela_palavra():
    args = dict(street='river', is_multiway=False, is_in_position=True, icm_pressure=None)
    assert (calc_context_penalty(player_action='shove', recommended_primary_action='jam', **args)
            == calc_context_penalty(player_action='jam', recommended_primary_action='jam', **args))
    # CONTROLE: o adicional de river existe quando as acoes diferem de verdade.
    assert (calc_context_penalty(player_action='fold', recommended_primary_action='jam', **args)
            > calc_context_penalty(player_action='jam', recommended_primary_action='jam', **args))
    print('OK  test_context_penalty_nao_cobra_pela_palavra')


def _entrada(acao, recomendada):
    """O id=320556 do acervo: BB, KdQd, 4,6bb efetivos, deu all-in, o range manda all-in."""
    return {
        'hand_id': 'H-GRAFIA', 'street': 'preflop', 'player_action': acao,
        'spot': {'position': 'BB', 'heroStackBb': 5.7, 'effectiveStackBb': 4.61875,
                 'facingSize': 0.0, 'potSize': 1.5, 'nPlayers': 9},
        'hand_profile': {'handType': 'KQs', 'category': 'suited_broadway'},
        'math': {'potOddsEquity': 0.0, 'estimatedEquity': 0.55},
        'range_evaluation': {'rangeZone': 'core_range', 'inRange': True,
                             'recommendedPrimaryAction': recomendada,
                             'alternativeActions': []},
        'context': {'mRatio': 5.0, 'icmPressure': 'medium'},
    }


def test_o_score_INTEIRO_nao_muda_com_a_grafia():
    """Testar so as pecas deixaria passar um quarto ponto de comparacao no meio do caminho."""
    a = evaluate_decision(_entrada('shove', 'jam'))
    b = evaluate_decision(_entrada('jam', 'jam'))
    sa = a['evaluation']['mistakeScore']
    sb = b['evaluation']['mistakeScore']
    assert sa == sb, f'shove-vs-jam deu {sa} e jam-vs-jam deu {sb}'
    assert a['evaluation']['label'] == b['evaluation']['label'] == 'standard', \
        (a['evaluation']['label'], b['evaluation']['label'])
    # CONTROLE: o mesmo caminho ainda distingue jogadas de verdade diferentes.
    c = evaluate_decision(_entrada('fold', 'jam'))
    assert c['evaluation']['mistakeScore'] > sa, 'o motor parou de distinguir fold de all-in'
    print('OK  test_o_score_INTEIRO_nao_muda_com_a_grafia')


def test_nenhuma_comparacao_CRUA_sobrou_no_motor():
    """A varredura dos N+1: o proximo chamador tambem tem de normalizar.

    Le o fonte porque nenhum teste de comportamento cobre uma funcao que ainda nao existe.
    """
    fonte = open(MOTOR, encoding='utf-8').read()
    cruas = []
    for i, linha in enumerate(fonte.splitlines(), 1):
        nu = linha.split('#')[0]
        if re.search(r'player_action\s*[!=]=\s*recommended_primary_action', nu) or \
           re.search(r'recommended_primary_action\s*[!=]=\s*player_action', nu):
            cruas.append(f'{i}: {linha.strip()}')
    assert not cruas, ('comparacao crua entre acao jogada e recomendada — passe por '
                       '_norm_gto_action:\n  ' + '\n  '.join(cruas))
    print('OK  test_nenhuma_comparacao_CRUA_sobrou_no_motor')

if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print(f'FAIL    {_t.__name__}: {type(_e).__name__}: {_e}')
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
