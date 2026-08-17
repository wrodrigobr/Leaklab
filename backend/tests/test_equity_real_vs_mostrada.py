# -*- coding: utf-8 -*-
"""Equity REAL vs a mão mostrada no card do replay (item 2 da deliberação de 17/08).

Fato do showdown, não estimativa — e CONTEXTO de revisão, nunca veredito (julgar a decisão
pela mão que apareceu é resulting). Pareamento estrito: só com UM revelador além do herói.
"""
import os
import sys
import types
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from api.app import _attach_equity_real_vs_mostrada          # noqa: E402
from leaklab.equity_real import (                            # noqa: E402
    cartas, equity_exata, equity_real_por_street, revelador_unico)


def test_ancoras_do_calculo():
    """Prova que o cálculo detecta (regra 1): nuts = 1.0, drawing dead = 0.0."""
    assert equity_exata(['As', 'Ad'], ['Kh', 'Ks'], ['Ac', 'Ah', '2d', '2s', '9h']) == 1.0
    assert equity_exata(['2c', '3d'], ['Ah', 'As'], ['Ac', 'Ad', '9h', '9s', 'Kh']) == 0.0
    # carta repetida entre hero e board = dado podre → silêncio, nunca palpite
    assert equity_exata(['As', 'Ad'], ['Kh', 'Ks'], ['As', '7d', '9h']) is None


def test_tres_dialetos_de_cartas():
    """hero_cards COLADO, reveals em lista, board em string JSON — os 3 dialetos reais."""
    assert cartas('Jd6d') == ['Jd', '6d']
    assert cartas(['Jd', '6d']) == ['Jd', '6d']
    assert cartas('["Kh", "Qh", "Kc"]') == ['Kh', 'Qh', 'Kc']


def test_por_street_para_onde_o_board_acaba():
    r = equity_real_por_street('AsAd', ['Kh', 'Ks'], ['2c', '7d', '9h', '2d'])
    assert set(r) == {'preflop', 'flop', 'turn'}, set(r)   # sem river: board de 4
    assert r['turn'] > 0.85


def test_attach_exige_um_revelador_e_marca_so_steps_do_heroi():
    hand = types.SimpleNamespace(
        hero_cards='AsAd', board=['2c', '7d', '9h'],
        reveals={'vilao1': ['Kh', 'Ks'], 'HeroZinho': ['As', 'Ad']})
    replay = {'hero': 'HeroZinho', 'timeline': [
        {'is_hero': True, 'street': 'preflop'},
        {'is_hero': False, 'street': 'flop'},
        {'is_hero': True, 'street': 'flop'},
    ]}
    _attach_equity_real_vs_mostrada(replay, hand)
    t0, t1, t2 = replay['timeline']
    assert t0.get('real_equity_vs_shown', {}).get('villain') == 'vilao1'
    assert 'real_equity_vs_shown' not in t1, 'step de vilao nao ganha o fato'
    assert t2['real_equity_vs_shown']['equity'] > 0.85
    assert t2['real_equity_vs_shown']['villain_cards'] == ['Kh', 'Ks']


def test_dois_reveladores_nao_pareia():
    """Vs 2+ mãos mostradas o número não significa nada — nada é anexado."""
    hand = types.SimpleNamespace(
        hero_cards='AsAd', board=['2c', '7d', '9h'],
        reveals={'vilao1': ['Kh', 'Ks'], 'vilao2': ['Qh', 'Qs']})
    replay = {'hero': 'HeroZinho', 'timeline': [{'is_hero': True, 'street': 'flop'}]}
    _attach_equity_real_vs_mostrada(replay, hand)
    assert 'real_equity_vs_shown' not in replay['timeline'][0]
    assert revelador_unico(hand.reveals, 'HeroZinho') is None


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
