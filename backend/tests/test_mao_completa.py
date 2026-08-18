# -*- coding: utf-8 -*-
"""Mão inteira HU (Fase 3): anonimização POR CONSTRUÇÃO do payload servido.

O acervo é compartilhado: a mão de um cliente vira exercício de outro. O guarda natural
(decidido 02/08) é um teste que varre o JSON servido atrás de QUALQUER identificador —
nick, tournament_id, hand_id, data — e falha se achar. Whitelist nos passos: campo novo
no banco não vaza por esquecimento.
"""
import json
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab import mao_completa as mc
from leaklab.models import ParsedAction, ParsedHand

_TID, _HID = 4711, '99887766'
_NICK_HERO, _NICK_VILAO = 'rodrigo_phz', 'Xx_shark_88'

_LINHAS = [
    {'id': 101, 'tournament_id': _TID, 'hand_id': _HID, 'street': 'preflop',
     'position': 'BB', 'stack_bb': 32.0, 'facing_bet': 2.2, 'board': '[]',
     'hero_cards': 'KhQd', 'n_active_opponents': 1},
    {'id': 102, 'tournament_id': _TID, 'hand_id': _HID, 'street': 'flop',
     'position': 'BB', 'stack_bb': 29.8, 'facing_bet': 1.65,
     'board': json.dumps(['Kd', '7c', '2s']), 'hero_cards': 'KhQd',
     'n_active_opponents': 1},
]

_HAND = ParsedHand(
    hand_id=_HID, tournament_id=str(_TID), hero=_NICK_HERO, bb=100.0,
    hero_cards='KhQd', players=[_NICK_HERO, _NICK_VILAO],
    actions=[
        ParsedAction(player=_NICK_VILAO, street='preflop', action='raises', amount=220),
        ParsedAction(player=_NICK_HERO, street='preflop', action='calls', amount=120),
        ParsedAction(player=_NICK_VILAO, street='flop', action='bets', amount=165),
    ],
    raw_text='PokerStars Hand #99887766: 2026/08/17 sujo de data',
)


def _payload():
    with mock.patch.object(mc, '_mao_parseada', return_value=_HAND):
        return mc.montar_mao(_LINHAS, _TID, _HID)


def test_payload_nao_vaza_identificador():
    blob = json.dumps(_payload(), ensure_ascii=False, default=str)
    proibidos = [_NICK_HERO, _NICK_VILAO, _HID, str(_TID), '2026/08', 'PokerStars']
    for p in proibidos:
        assert p not in blob, f'identificador vazou no payload servido: {p!r}'


def test_passos_respeitam_a_whitelist():
    p = _payload()
    for passo in p['passos']:
        extras = set(passo) - mc.CAMPOS_PERMITIDOS_PASSO
        assert not extras, f'campo fora da whitelist no passo: {extras}'


def test_narracao_anonimizada_com_valores_em_bb():
    n = _payload()['narracao']
    assert n['preflop'][0] == {'quem': 'vilao', 'acao': 'raises', 'valor_bb': 2.2}
    assert n['preflop'][1]['quem'] == 'hero'
    assert n['flop'][0] == {'quem': 'vilao', 'acao': 'bets', 'valor_bb': 1.65}


def test_menu_pela_forma_do_facing():
    p = _payload()
    assert p['passos'][0]['options'] == ['fold', 'call', 'raise', 'allin']  # preflop vs open
    assert p['passos'][1]['options'] == ['fold', 'call', 'raise']       # flop vs c-bet
    assert mc._menu_da_linha({'street': 'turn', 'facing_bet': 0}) == ['check', 'bet']


def test_seletor_replica_o_gate_do_corretor():
    """Nó vivo hand-aware NÃO basta: sem gto_action/gto_label gravados o corretor cai em
    'heuristic', e a street não pode ser servida como GTO. Pego em prod no 1º probe."""
    resolver = lambda d, return_strategy=True: ('call', {}, 'gto_hand')
    base = {'gto_action': 'call', 'gto_label': 'gto_correct'}
    assert mc.street_gradeavel_gto(base, resolver)
    assert not mc.street_gradeavel_gto({**base, 'gto_action': None}, resolver)
    assert not mc.street_gradeavel_gto({**base, 'gto_label': 'wizard_pending'}, resolver)
    resolver_range = lambda d, return_strategy=True: ('call', {}, 'gto_range')
    assert not mc.street_gradeavel_gto(base, resolver_range)


def test_mao_de_um_passo_nao_vira_exercicio():
    with mock.patch.object(mc, '_mao_parseada', return_value=_HAND):
        assert mc.montar_mao(_LINHAS[:1], _TID, _HID) is None


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
