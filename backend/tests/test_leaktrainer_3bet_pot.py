# -*- coding: utf-8 -*-
"""Categoria BB 3-BET POT do Leak Trainer (17/08): BB 3-betou, BTN pagou, BB decide o c-bet.

O lar de AK/AQ/QQ+, que 3-betam preflop e nunca chegam ao catálogo SRP (range-aware). Três
contratos que já morderam em outros lugares:
- parâmetros POR CATÁLOGO (usar _BBDEF_PARAMS para todos poria pote de SRP num pote 3-bet);
- `pot_type='3bet'` viaja do spot até o lookup (senão o grade lê a árvore SRP — RC-3);
- `facing_size_bb=0.0` é LEGÍTIMO e não pode cair em default (a armadilha do `or`).
"""
import os
import random
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab import leak_trainer as lt


def _spot_3bet():
    cat = {'kind': 'postflop', 'catalog': 'bb_3bet_pot', 'key': 'pf:bb_3bet_pot'}
    os.environ['TRAINER_POOL_POSTFLOP'] = '0'   # catálogo estático, sem acervo
    try:
        return lt.generate_postflop_spot(cat, rng=random.Random(7))
    finally:
        os.environ.pop('TRAINER_POOL_POSTFLOP', None)


def test_spot_3bet_carrega_parametros_do_proprio_catalogo():
    s = _spot_3bet()
    assert s is not None, 'catálogo bb_3bet_pot vazio'
    assert s['pot_bb'] == 22.5 and s['stack_bb'] == 29.0, (s['pot_bb'], s['stack_bb'])
    assert s['facing_size_bb'] == 0.0, 'pote 3-bet: BB é o primeiro a agir, ninguém apostou'
    assert s['pot_type'] == '3bet' and s['opener'] == 'BTN' and s['threebettor'] == 'BB'
    # menu pela FORMA: sem aposta na mesa, check/bet — nunca fold/call/raise
    assert s['options'] == ['check', 'bet'], s['options']


def test_bb_defense_continua_com_os_parametros_de_sempre():
    os.environ['TRAINER_POOL_POSTFLOP'] = '0'
    try:
        s = lt.generate_postflop_spot({'kind': 'postflop', 'catalog': 'bb_defense',
                                       'key': 'pf:bb_defense'}, rng=random.Random(7))
    finally:
        os.environ.pop('TRAINER_POOL_POSTFLOP', None)
    assert s['pot_bb'] == 5.0 and s['facing_size_bb'] == 1.65 and s['pot_type'] == ''
    assert 'fold' in s['options'], s['options']


def test_grade_repassa_pot_type_e_nao_engole_o_facing_zero():
    s = _spot_3bet()
    capturado = {}

    def _fake_lookup(**kw):
        capturado.update(kw)
        return {'hand_strategy': None}          # None → grade devolve None, e está ok

    with mock.patch('leaklab.gto_solver.lookup_gto', side_effect=lambda **kw: _fake_lookup(**kw)):
        lt.grade_postflop_spot(s, 'check')
    assert capturado.get('pot_type') == '3bet', 'pot_type não chegou ao lookup — árvore SRP (RC-3)'
    assert capturado.get('opener') == 'BTN' and capturado.get('threebettor') == 'BB'
    assert capturado.get('facing_size_bb') == 0.0, \
        f"facing 0 engolido por default: {capturado.get('facing_size_bb')} (a armadilha do or)"
    assert capturado.get('pot_bb') == 22.5


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
