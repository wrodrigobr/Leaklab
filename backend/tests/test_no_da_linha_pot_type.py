# -*- coding: utf-8 -*-
"""RC-3 da auditoria do Ghost Table (25/06, fechado 17/08): o drill e o /replay/<id>/gto
resolviam nó SEM pot_type — pote 3-bet caía no nó da árvore SRP.

Duas defesas, ambas deriváveis da LINHA sem chute:
- `_hashes_da_linha`: variante '3bet' primeiro quando a linha diz is_3bet, legado como
  aproximação (a MESMA ordem do engine);
- `_no_contradiz_o_gravado`: nó vivo cuja ação-topo é de outra FAMÍLIA que o gto_action
  gravado é rejeitado — pega a variante inderivável ('oop_pfr': opener não é coluna, e
  hero_was_aggressor postflop é iniciativa, que um check-raise inverte).
"""
import json
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors  # noqa: F401
except ImportError:
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from api.app import _hashes_da_linha, _no_contradiz_o_gravado    # noqa: E402
from leaklab.gto_utils import compute_spot_hash                  # noqa: E402

_BOARD = ['Kh', '7d', '2c']
_MAO = ['Ah', 'Ad']


def test_linha_3bet_tenta_a_variante_certa_primeiro():
    hs = _hashes_da_linha('flop', 'BB', _BOARD, _MAO, 20.0, 5.0, is_3bet=1)
    assert hs[0] == compute_spot_hash('flop', 'BB', _BOARD, _MAO, 20.0, 5.0, '3bet'), \
        'a variante 3bet nao veio primeiro'
    assert compute_spot_hash('flop', 'BB', _BOARD, _MAO, 20.0, 5.0, '') in hs, \
        'o legado (aproximacao deliberada do engine) sumiu do fallback'


def test_linha_srp_fica_no_legado():
    hs = _hashes_da_linha('flop', 'BB', _BOARD, _MAO, 20.0, 5.0, is_3bet=0)
    assert hs[0] == compute_spot_hash('flop', 'BB', _BOARD, _MAO, 20.0, 5.0, '')
    assert compute_spot_hash('flop', 'BB', _BOARD, _MAO, 20.0, 5.0, '3bet') not in hs, \
        'linha SRP nao pode consultar a arvore 3-bet'


def test_guarda_rejeita_no_de_outra_familia():
    """O caso oop_pfr: o nó legado descreve o confronto com as ranges trocadas — a ação-topo
    dele contradiz o que o engine gravou com o spot completo."""
    no_errado = {'strategy_json': json.dumps(
        {'bet': {'frequency': 0.9}, 'check': {'frequency': 0.1}})}
    assert _no_contradiz_o_gravado(no_errado, 'check') is True
    assert _no_contradiz_o_gravado(no_errado, 'fold') is True


def test_guarda_nao_ve_contradicao_em_rotulo_de_menu_nem_sem_gravado():
    """bet vs raise é rótulo de menu (mesma família de agressão); sem gravado o nó vivo é
    cobertura aditiva; jam/shove/allin são a mesma família."""
    no_bet = {'strategy_json': json.dumps({'bet': {'frequency': 0.9}})}
    assert _no_contradiz_o_gravado(no_bet, 'raise') is False
    assert _no_contradiz_o_gravado(no_bet, None) is False
    assert _no_contradiz_o_gravado(None, 'fold') is False
    no_jam = {'gto_action': 'jam'}
    assert _no_contradiz_o_gravado(no_jam, 'allin') is False
    # CONTROLE do controle: o mesmo nó jam CONTRADIZ um fold gravado
    assert _no_contradiz_o_gravado(no_jam, 'fold') is True


def test_rc5_guard_do_bb_reescreve_freqs_junto():
    """RC-5/6: o guard 'BB pode check grátis' reescrevia best_action fold→check mas deixava
    as freqs do nó intactas — a janela de ≥30% premiava o fold que o guard declarou
    impossível. Agora a freq de fold VIAJA para check (campos-viajantes)."""
    from api import app as _app
    row = {'best_action': 'fold', 'gto_action': 'fold', 'gto_label': 'gto_correct',
           'score': 0.5, 'facing_bet': 0, 'position': 'BB', 'street': 'flop',
           'stack_bb': 30.0, 'pot_size': 2.0, 'n_active_opponents': 1}
    with mock.patch.object(_app, '_resolve_best_action_from_node',
                           return_value=('fold', {'fold': 0.6, 'check': 0.4}, 'gto_hand')):
        r_fold = _app.grade_drill_action(dict(row), 'fold')
        r_check = _app.grade_drill_action(dict(row), 'check')
    assert r_fold['gto_tier'] == 'error', (
        'fold premiado pela freq do nó onde fold é impossível', r_fold['gto_tier'])
    assert r_check['gto_tier'] == 'correct', r_check['gto_tier']
    assert r_check['gto_freqs'].get('fold') is None, 'freq de fold sobreviveu ao guard'
    assert abs(r_check['gto_freqs'].get('check', 0) - 1.0) < 1e-6, r_check['gto_freqs']


def test_rc5_menu_sem_aposta_postflop_nao_pode_ter_fold():
    """Forma do menu: com facing=0 postflop, nó com 'fold' é nó vs-aposta (outra forma).
    O validador do drill rejeita — e o cenário ISOLA este guarda: a ação-topo do nó errado
    ('call') COINCIDE com o gravado, então o guarda de coerência não o pegaria. A primeira
    versão deste teste usava um nó que os dois guardas rejeitavam, e a mutação no guarda de
    menu passou batida — teste que não falha quando deveria (regra 2)."""
    from api import app as _app
    no_vs_bet = {'street': 'flop', 'board': '["Kh", "7d", "2c"]',
                 'strategy_json': json.dumps({'call': {'frequency': 0.6},
                                              'fold': {'frequency': 0.4}})}
    no_ok = {'street': 'flop', 'board': '["Kh", "7d", "2c"]',
             'strategy_json': json.dumps({'check': {'frequency': 0.6},
                                          'bet': {'frequency': 0.4}})}
    row = {'street': 'flop', 'position': 'BB', 'facing_bet': 0, 'stack_bb': 30.0,
           'board': '["Kh", "7d", "2c"]', 'hero_cards': 'AhAd',
           'best_action': 'call', 'score': 0.5}

    def _fake_get_node(h, _mapa={}):
        seq = _mapa.setdefault('seq', [no_vs_bet, no_ok, no_ok, no_ok])
        return seq.pop(0) if seq else no_ok

    # gravado 'call' = mesma família da ação-topo do nó errado → coerência NÃO rejeita;
    # só o guarda de menu separa os dois.
    with mock.patch('database.repositories.get_gto_node', side_effect=_fake_get_node):
        top, freqs, source = _app._resolve_best_action_from_node(
            dict(row, gto_action='call', gto_label='gto_correct'), return_strategy=True)
    assert 'fold' not in (freqs or {}), ('o no vs-aposta passou pelo validador', freqs)


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
