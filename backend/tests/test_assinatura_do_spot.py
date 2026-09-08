# -*- coding: utf-8 -*-
"""Assinatura do spot: textura do board e relacao da mao (AY-28, 08/09).

O que este arquivo defende: cada classe de textura e de relacao sai como o coach a chamaria;
boards diferentes com a mesma estrutura tem a mesma assinatura; a mesma mao em boards de
estrutura diferente nao; preflop e board incompleto nao tem assinatura; entradas nos tres
formatos (lista, string colada, JSON) dao o mesmo resultado.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.assinatura_do_spot import textura, relacao_da_mao, assinatura   # noqa: E402


def test_textura_nomeia_carta_alta_par_naipes_e_conexao():
    assert textura(['Ah', '7h', '2c']) == '3-A-seco-2tone-desconectado'
    assert textura(['Ks', 'Kd', '4c']) == '3-K-par-rainbow-desconectado'
    assert textura(['9s', '8s', '7s']) == '3-T9-seco-mono-conectado'
    assert textura(['Qd', 'Jc', '4h', '4s']) == '4-QJ-par-rainbow-semi'
    assert textura(['6c', '5d', '3h', '2s', '2d']) == '5-baixo-par-2tone-conectado'    # dois ouros
    assert textura(['7c', '7d', '7h']) == '3-baixo-trinca-rainbow-desconectado'   # 7 alto e board baixo
    assert textura(['Ah', '7h']) is None and textura(None) is None


def test_relacao_da_mao_nomeia_feita_flush_e_straight():
    assert relacao_da_mao(['Ah', '7h', '2c'], ['Ad', 'Kd']) == 'top_pair-sem_flush-sem_straight'
    assert relacao_da_mao(['Ah', '7h', '2c'], ['Kh', 'Qh']) == 'nada-flush_draw-sem_straight'
    assert relacao_da_mao(['Ah', '7h', '2c'], ['Qc', 'Tc']) == 'nada-bd_flush-sem_straight'
    assert relacao_da_mao(['Ah', '7h', '2c'], ['Kc', 'Kd']) == 'par_no_meio-sem_flush-sem_straight'   # KK abaixo do as: nao e overpair
    assert relacao_da_mao(['Th', '7h', '2c'], ['Kc', 'Kd']) == 'overpair-sem_flush-sem_straight'
    assert relacao_da_mao(['Ah', '7h', '2c'], ['7d', '7s']) == 'set-sem_flush-sem_straight'
    assert relacao_da_mao(['Ah', '7h', '2c'], ['7d', '6s']) == 'par_medio-sem_flush-sem_straight'
    assert relacao_da_mao(['Ah', '7h', '2c'], ['2d', '3s']) == 'par_baixo-sem_flush-sem_straight'
    assert relacao_da_mao(['Ah', '7h', '2c'], ['Ad', '7s']) == 'dois_pares-sem_flush-sem_straight'
    assert relacao_da_mao(['9s', '8d', '2c'], ['Jh', 'Th']) == 'duas_overcards-sem_flush-straight_draw'
    assert relacao_da_mao(['9s', '8d', '2c', '7h'], ['Jh', 'Th']) == 'duas_overcards-sem_flush-straight'
    assert relacao_da_mao(['Ks', 'Kd', '4c'], ['Kh', 'Qh']) == 'trinca-sem_flush-sem_straight'
    assert relacao_da_mao(['5s', '4d', '3c'], ['Ah', '2h']) == 'uma_overcard-sem_flush-straight'   # roda: o as e o 1 (e a unica overcard)
    assert relacao_da_mao(['Ah', '7h', '2c', '9h', '3h'], ['Kh', 'Qd']) == 'nada-flush-sem_straight'
    assert relacao_da_mao(['Ah', '7h'], ['Kh', 'Qh']) is None and relacao_da_mao(['Ah', '7h', '2c'], ['Kh']) is None


def test_assinatura_junta_estrutura_e_ignora_a_carta_exata():
    a = assinatura('flop', 'CO', 28.0, 0.0, ['Ah', '7h', '2c'], ['Kh', 'Qh'])
    b = assinatura('flop', 'CO', 31.0, 0.0, ['As', '8s', '3d'], ['Js', 'Ts'])     # outro board, mesma estrutura
    assert a == 'flop|CO|20-35bb|no_bet|3-A-seco-2tone-desconectado|nada-flush_draw-sem_straight'
    assert a == b
    assert assinatura('flop', 'CO', 28.0, 0.0, ['Ah', '7h', '2c'], ['Kd', 'Qc']) != a      # sem o draw
    assert assinatura('flop', 'CO', 28.0, 5.0, ['Ah', '7h', '2c'], ['Kh', 'Qh']) != a      # enfrentando aposta
    assert assinatura('flop', 'CO', 28.0, 0.0, ['Ah', '7h', '2c']) == 'flop|CO|20-35bb|no_bet|3-A-seco-2tone-desconectado'
    assert assinatura('preflop', 'CO', 28.0, 0.0, [], ['Kh', 'Qh']) is None
    assert assinatura('flop', 'CO', 28.0, 0.0, ['Ah', '7h'], ['Kh', 'Qh']) is None


def test_a_assinatura_corta_o_board_na_street_da_decisao():
    """O banco guarda o board COMPLETO em toda decisao (59% das linhas de flop em dev tem 4 ou 5
    cartas). Sem cortar, duas decisoes no MESMO flop teriam assinaturas diferentes conforme a mao
    tenha ido ao river, e a textura descreveria um board que o heroi nao viu. Achado em 08/09
    validando o passo 2 com acervo real: uma decisao de FLOP com 5 cartas virou '5-QJ-par-2tone'
    e nao achou nenhum vizinho. Mesma familia do bug de 28/07 (ver gto_utils.board_for_street)."""
    completo = ['Ah', '7h', '2c', '9d', 'Js']
    assert assinatura('flop', 'CO', 28.0, 0.0, completo, ['Kh', 'Qh']) == assinatura('flop', 'CO', 28.0, 0.0, ['Ah', '7h', '2c'], ['Kh', 'Qh'])
    assert assinatura('turn', 'CO', 28.0, 0.0, completo, ['Kh', 'Qh']) == assinatura('turn', 'CO', 28.0, 0.0, ['Ah', '7h', '2c', '9d'], ['Kh', 'Qh'])
    assert assinatura('flop', 'CO', 28.0, 0.0, completo, ['Kh', 'Qh']).split('|')[4].startswith('3-')   # 3 cartas, nao 5
    assert assinatura('turn', 'CO', 28.0, 0.0, completo, ['Kh', 'Qh']).split('|')[4].startswith('4-')
    assert assinatura('river', 'CO', 28.0, 0.0, completo, ['Kh', 'Qh']).split('|')[4].startswith('5-')
    # e a relacao da mao tambem olha so o board da street: KQ de copas e draw no flop, nao no river
    assert 'flush_draw' in assinatura('flop', 'CO', 28.0, 0.0, completo, ['Kh', 'Qh'])
    assert 'flush_draw' not in assinatura('river', 'CO', 28.0, 0.0, completo, ['Kh', 'Qh'])


def test_os_tres_formatos_de_cartas_dao_o_mesmo():
    assert relacao_da_mao('Ah7h2c', 'KhQh') == relacao_da_mao(['Ah', '7h', '2c'], ['Kh', 'Qh']) == relacao_da_mao('["Ah","7h","2c"]', '["Kh","Qh"]')
    assert textura('["ah","7H","2c"]') == textura(['Ah', '7h', '2c'])


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
