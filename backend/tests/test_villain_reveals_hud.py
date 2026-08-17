# -*- coding: utf-8 -*-
"""Consumidor do `ParsedHand.reveals` no HUD (17/08): `replay['villain_reveals']`.

O dado existe desde 05/08 (3.830 revelações capturadas do SUMMARY) e NINGUÉM consumia —
memória [[project_cartas_reveladas_no_summary]]. Mão revelada é FATO, não read inferido,
então entra sem o gate de amostra do HUD; mas a mão ATUAL fica de fora (spoiler do
showdown), o herói fica de fora (a carta dele é o centro do replay) e nome-posição
(anonimizado) fica de fora, como no resto do HUD.
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

from api.app import _attach_opponent_hud  # noqa: E402


def _mao(hand_id, reveals):
    return types.SimpleNamespace(hand_id=hand_id, reveals=reveals)


def _roda(replay, hands, perfis=()):
    with mock.patch('database.repositories.get_opponent_profiles', return_value=list(perfis)):
        _attach_opponent_hud(replay, 999, hands=hands)
    return replay


def test_reveals_viram_mapa_por_jogador():
    hands = [
        _mao('111', {'vilao1': ['Qc', '6c'], 'HeroZinho': ['Ah', 'Ad']}),
        _mao('222', {'vilao1': ['Ks', 'Kd'], 'BB': ['2c', '2d']}),   # 'BB' = nome-posicao
        _mao('333', {'vilao1': ['Jh', 'Jd']}),                        # mao ATUAL: fora
    ]
    r = _roda({'hand_id': '333', 'hero': 'HeroZinho', 'timeline': []}, hands)
    rv = r.get('villain_reveals')
    assert rv is not None, 'reveals capturados nao chegaram ao replay'
    assert list(rv) == ['vilao1'], rv
    assert [x['cards'] for x in rv['vilao1']] == [['Qc', '6c'], ['Ks', 'Kd']], rv['vilao1']
    # herói, nome-posição e a mão atual NUNCA entram
    assert 'HeroZinho' not in rv and 'BB' not in rv
    assert all(x['cards'] != ['Jh', 'Jd'] for x in rv['vilao1']), 'spoiler: a mao atual vazou'


def test_teto_de_8_por_vilao_fica_com_as_recentes():
    hands = [_mao(str(i), {'vilao1': ['A' + 'shdc'[i % 4], str(2 + i % 8) + 'c']})
             for i in range(11)]
    r = _roda({'hand_id': 'outra', 'hero': 'h', 'timeline': []}, hands)
    rv = r['villain_reveals']['vilao1']
    assert len(rv) == 8, len(rv)
    assert rv[-1]['hand'] == '10', 'as recentes (fim do HH) e que ficam'


def test_sem_reveals_nao_inventa_chave():
    r = _roda({'hand_id': '1', 'hero': 'h', 'timeline': []}, [_mao('2', {})])
    assert 'villain_reveals' not in r


def test_reveals_independem_de_perfil_existir():
    """Vilão de poucas mãos não tem arquétipo, mas mão mostrada continua evidência — o mapa
    entra MESMO com opponent_profiles vazio (a ordem do early-return importa)."""
    r = _roda({'hand_id': 'x', 'hero': 'h', 'timeline': []},
              [_mao('1', {'vilao1': ['Qc', '6c']})], perfis=())
    assert r.get('villain_reveals'), 'early-return de perfis engoliu os reveals'
    assert 'opponent_profiles' not in r


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
