# -*- coding: utf-8 -*-
"""Painel range-por-classe (17/08): a hand_table agrupada por classe de mão × ação.

Contratos:
- a classe é HERO-CÊNTRICA: num board pareado, par do board não vira "two pair" nem "trips";
- as classes de mão feita são mutuamente exclusivas e os pesos somam 100%;
- a agregação é ponderada pelo PESO do combo (média simples mentiria sobre a range);
- combo com carta no board não entra (mesma guarda da seleção);
- river não tem linha de draw (não há carta por vir).
"""
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab import range_classes as rc
from leaklab import trainer_pool as tp

_BOARD = ['Kh', '7d', '2s']


def test_classes_hero_centricas():
    casos = [
        ('AhKd', _BOARD, 'top_pair'),
        ('KcQd', _BOARD, 'top_pair'),
        ('AhAd', _BOARD, 'overpair'),
        ('9c9d', _BOARD, 'middle_pair'),   # pocket entre o K e o 7
        ('7h6h', _BOARD, 'middle_pair'),   # pareia a 2ª carta
        ('2h3h', _BOARD, 'weak_pair'),     # bottom pair
        ('3c3d', _BOARD, 'weak_pair'),     # pocket abaixo da 2ª carta
        ('QhJh', _BOARD, 'no_made'),       # air
        ('7c7s', _BOARD, 'trips'),         # set de 7
        ('AhQh', ['Kh', '7h', '2h'], 'monster'),   # flush feito
    ]
    for mao, board, esperado in casos:
        got = rc.classe_da_mao(mao, board)
        assert got == esperado, f'{mao} vs {board}: esperava {esperado}, veio {got}'
    # two pair de verdade: as DUAS cartas do hero pareiam o board
    assert rc.classe_da_mao('Kc7s', _BOARD) == 'two_pair'


def test_board_pareado_nao_infla_classe():
    """Board Q-3-3: eval7 diz "Two Pair" pra quem tem um par só, e "Trips" pra quem não tem
    nada. A leitura de range não pode herdar essa inflação."""
    board = ['Qh', '3d', '3s']
    assert rc.classe_da_mao('QcJd', board) == 'top_pair', 'par de Q + par do board ≠ two pair'
    assert rc.classe_da_mao('7h6h', board) == 'no_made', 'par do board sozinho ≠ made hand'
    assert rc.classe_da_mao('Ah3c', board) == 'trips', 'trinca com carta do hero É trips'
    board5 = ['Qh', '3d', '3s', '3c', '8h']
    assert rc.classe_da_mao('AhKd', board5) == 'no_made', 'trinca do board ≠ trips do hero'


_ACOES = ['check', 'bet_50pct']


def _linha(mao, w, f_check, f_bet):
    return {'hand': mao, 'weight': w, 'freqs': [f_check, f_bet], 'evs': [0, 0]}


_TABELA = [
    _linha('AhAd', 2.0, 0.0, 1.0),    # overpair, bet 100%
    _linha('AcAs', 1.0, 0.6, 0.4),    # overpair, bet 40%
    _linha('QhJh', 1.0, 1.0, 0.0),    # air
    _linha('Kc7s', 0.0, 0.0, 1.0),    # peso 0: fora
    _linha('KhQd', 1.0, 0.5, 0.5),    # carta no board (Kh): combo impossível
]


def _painel(board=_BOARD, tabela=None):
    with mock.patch.object(tp, '_tabela_da_arvore',
                           return_value=(_ACOES, tabela if tabela is not None else _TABELA)):
        return rc.range_por_classe('t', board, enfrentando=False)


def test_agrega_ponderado_pelo_peso():
    p = _painel()
    over = next(c for c in p['classes'] if c['id'] == 'overpair')
    # (2.0*1.0 + 1.0*0.4) / 3.0 = 80% de bet — média simples daria 70% e mentiria
    assert abs(over['freqs']['bet'] - 80.0) < 0.11, f"ponderação errada: {over['freqs']}"
    assert over['combos'] == 2


def test_pesos_das_classes_somam_100():
    p = _painel()
    soma = sum(c['peso_pct'] for c in p['classes'])
    assert abs(soma - 100.0) < 0.3, f'classes não particionam a range: {soma}'


def test_combo_impossivel_e_peso_zero_ficam_fora():
    p = _painel()
    servidos = sum(c['combos'] for c in p['classes'])
    assert servidos == 3, f'KhQd (carta no board) ou Kc7s (peso 0) entraram: {servidos}'
    assert not any(c['id'] == 'two_pair' for c in p['classes'])


def test_river_sem_draws_e_flop_com():
    flop = _painel(board=['Kh', '7h', '2h'],
                   tabela=[_linha('AhQd', 1.0, 1.0, 0.0),      # nut FD (Ah)
                           _linha('9c8c', 1.0, 1.0, 0.0)])
    assert any(d['id'] == 'flush_draw' for d in flop['draws']), 'FD no flop não apareceu'
    river = _painel(board=['Kh', '7h', '2h', '3d', '8s'],
                    tabela=[_linha('AhQd', 1.0, 1.0, 0.0)])
    assert river['draws'] == [], 'draw listado no river — não há carta por vir'


def test_arvore_vazia_devolve_none():
    assert _painel(tabela=[]) is None


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
