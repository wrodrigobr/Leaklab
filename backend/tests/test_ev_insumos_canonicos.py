# -*- coding: utf-8 -*-
"""Os INSUMOS do ev_loss_trustworthy são canônicos: as colunas da linha, em toda porta.

A regra sempre foi fonte única; os insumos não. O card do replayer (`_ev_e_motivo`) passava
pot/equity/facing do spot REPARSEADO (`facingToCallBb` = custo) enquanto coach e agregadores
passavam as colunas do banco (`facing_bet` = tamanho). Num caso limítrofe do teto de fold
(decisão 322182: K9o fold SB, ev 0.895, gw_har) o card dizia "sem confiança" e o badge do
coach mostrava -0.9BB — o MESMO número, duas respostas.

O conserto: `ev_loss_trustworthy_row(d)` é o adaptador canônico (linha do banco), usado pelo
card e pelo coach. O teste central aqui é o de CONCORDÂNCIA: para a mesma linha, as duas
portas respondem igual — e o card responde igual MESMO com um spot envenenado ao lado, porque
ele não lê mais o spot.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

import database.schema as sch
sch.SQLITE_PATH = os.environ['LEAKLAB_DB']
sch.init_db()

from leaklab.decision_engine_v11 import ev_loss_trustworthy, ev_loss_trustworthy_row
from leaklab.coach_replay import _ev_utilizavel
from api.app import _ev_e_motivo

# A linha K9o real (decisão 322182), a que dividiu as telas em 13/08.
LINHA_K9O = {
    'ev_loss_bb': 0.895, 'stack_bb': 54.9, 'ev_loss_source': 'gw_har',
    'action_taken': 'fold', 'estimated_equity': 0.579,
    'pot_size': 1.5, 'facing_bet': 2.0,
}


def test_adaptador_equivale_a_chamada_direta_com_as_colunas():
    esperado = ev_loss_trustworthy(0.895, 54.9, 'gw_har', action='fold', equity=0.579,
                                   pot_bb=1.5, facing_bb=2.0)
    assert ev_loss_trustworthy_row(LINHA_K9O) == esperado
    print('OK  test_adaptador_equivale_a_chamada_direta_com_as_colunas')


def test_CONCORDANCIA_card_e_coach_respondem_igual_para_a_mesma_linha():
    """A prova do conserto: mesma linha, mesma resposta nas duas portas."""
    coach_mostra = _ev_utilizavel(LINHA_K9O)
    ev, motivo = _ev_e_motivo(LINHA_K9O, {}, {})
    card_mostra = motivo is None and ev is not None
    assert coach_mostra == card_mostra, (
        f'as portas divergem de novo: coach={coach_mostra}, card=(ev={ev}, motivo={motivo})')
    print('OK  test_CONCORDANCIA_card_e_coach_respondem_igual_para_a_mesma_linha')


def test_o_card_ignora_o_spot_reparseado():
    """REGRESSÃO: um spot envenenado ao lado da decisão não muda a resposta do card.
    Era exatamente por ler o spot que o card discordava do coach."""
    spot_venenoso = {'effectiveStackBb': 999.0, 'potBb': 0.0, 'facingToCallBb': 999.0}
    ev_sem, motivo_sem = _ev_e_motivo(LINHA_K9O, {}, {})
    ev_com, motivo_com = _ev_e_motivo(LINHA_K9O, {'math': {'estimatedHandEquity': 0.01}},
                                      spot_venenoso)
    assert (ev_sem, motivo_sem) == (ev_com, motivo_com), (
        'o spot reparseado voltou a decidir o EV do card')
    print('OK  test_o_card_ignora_o_spot_reparseado')


def test_fora_de_escala_tambem_usa_a_linha():
    """O motivo 'fora_de_escala' (impossível) sai das MESMAS colunas: ev que não cabe em
    pot_size + 2*stack_bb da linha."""
    linha = dict(LINHA_K9O, ev_loss_bb=9999.0, ev_loss_source='solver_hand', stack_bb=10.0,
                 pot_size=3.0)
    ev, motivo = _ev_e_motivo(linha, {}, {})
    assert ev is None and motivo == 'fora_de_escala', (ev, motivo)
    print('OK  test_fora_de_escala_tambem_usa_a_linha')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FALHOU  %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
