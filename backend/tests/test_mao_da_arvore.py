# -*- coding: utf-8 -*-
"""Fase 2 do catálogo (17/08): servir qualquer mão da hand_table — o destravamento do 0,2%.

Contratos, todos medidos antes em [[project_modo_grind_preflop]]:
- peso < 5% do máximo fica FORA (mão quase fora da range = ensinar exceção);
- a família DOMINANTE da mão obedece o alvo do mix (o quiz vencível no check é a cicatriz
  do CLAUDE.md — o mix é decidido fora, a seleção só obedece);
- viés pró-discriminante (2ª família ≥10%), não filtro: estratégia pura também ensina;
- mão com carta no board é combo impossível e não sai.
"""
import os
import random
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab import trainer_pool as tp

_ACOES = ['check', 'bet_50pct']


def _linha(mao, w, f_check, f_bet):
    return {'hand': mao, 'weight': w, 'freqs': [f_check, f_bet], 'evs': [0, 0]}


_TABELA = [
    _linha('AhAd', 100.0, 0.05, 0.95),   # bet pura (forte)
    _linha('KhQd', 90.0, 0.55, 0.45),    # CHECK dominante, discriminante
    _linha('ThTc', 80.0, 0.98, 0.02),    # check pura
    _linha('2c2d', 1.0, 1.0, 0.0),       # peso ~0: fora da range → nunca sai
    _linha('9h8h', 70.0, 0.40, 0.60),    # BET dominante, discriminante
]


def _com_tabela(fn, tabela=None):
    with mock.patch.object(tp, '_tabela_da_arvore',
                           return_value=(_ACOES, tabela if tabela is not None else _TABELA)):
        return fn()


def test_peso_minimo_exclui_a_excecao():
    for seed in range(30):
        mao = _com_tabela(lambda: tp.mao_da_arvore('t', 'check', False, random.Random(seed)))
        assert mao is not None
        assert ''.join(mao) != '2c2d', 'mão de peso ~0 servida — exercício de exceção'


def test_dominancia_obedece_o_alvo_do_mix():
    for seed in range(30):
        mao = _com_tabela(lambda: tp.mao_da_arvore('t', 'bet', False, random.Random(seed)))
        assert ''.join(mao) in ('AhAd', '9h8h'), f'mão de check servida no alvo bet: {mao}'
        mao = _com_tabela(lambda: tp.mao_da_arvore('t', 'check', False, random.Random(seed)))
        assert ''.join(mao) in ('KhQd', 'ThTc'), f'mão de bet servida no alvo check: {mao}'


def test_vies_discriminante_e_vies_nao_filtro():
    """No alvo check há uma discriminante (KQ 55/45) e uma pura (TT 98/2): as duas têm que
    aparecer, com a discriminante na frente (~70%)."""
    vistos = {'KhQd': 0, 'ThTc': 0}
    for seed in range(200):
        mao = ''.join(_com_tabela(lambda: tp.mao_da_arvore('t', 'check', False, random.Random(seed))))
        vistos[mao] += 1
    assert vistos['KhQd'] > vistos['ThTc'], f'viés discriminante invertido: {vistos}'
    assert vistos['ThTc'] > 0, f'pura sumiu — virou filtro: {vistos}'


def test_carta_no_board_nao_sai():
    for seed in range(30):
        mao = _com_tabela(lambda: tp.mao_da_arvore('t', 'bet', False, random.Random(seed),
                                                   board=['Ah', '7d', '2s']))
        assert ''.join(mao) == '9h8h', f'combo impossível (AhAd com Ah no board): {mao}'


def test_arvore_sem_candidata_devolve_none():
    assert _com_tabela(lambda: tp.mao_da_arvore('t', 'fold', False, random.Random(1))) is None
    assert _com_tabela(lambda: tp.mao_da_arvore('t', 'check', False, random.Random(1)),
                       tabela=[]) is None


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
