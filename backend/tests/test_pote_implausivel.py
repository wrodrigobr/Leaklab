# -*- coding: utf-8 -*-
"""A peneira do pote: dado quebrado barra SEMPRE; dinheiro morto em HU passa.

Duas populações moravam na mesma regra "pot > 2.5*2*stack" (13/08):
  · pote em FICHAS (1.653bb, 67.750bb) — a 5ª encarnação do bug mais recorrente;
  · pote multiway LEGÍTIMO inflado por dinheiro morto — 13 de 17 decisões barradas tinham UM
    vilão ativo na decisão (HU com pote grande, modelo válido), e uma delas estava ACUSADA de
    small_mistake por pagar 0,8bb num pote de 50bb (odds de 1,5%).

Os casos deste arquivo são os MEDIDOS no acervo, não inventados.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.gto_solver import pote_implausivel


def test_pote_em_fichas_barra_sempre():
    assert pote_implausivel(1653.0, 5.0, 1) is True, 'a 5a encarnacao passou pela peneira'
    assert pote_implausivel(67750.0, 15.5, 1) is True
    assert pote_implausivel(306.0, 2.6, 1) is True, 'acima do teto fisico de 150bb'
    print('OK  test_pote_em_fichas_barra_sempre')


def test_dinheiro_morto_com_UM_vilao_ativo_passa():
    # t120: hero 0,8bb pagando em pote de 50,6bb — o caso acusado injustamente
    assert pote_implausivel(50.6, 0.8, 1) is False
    # t42: pote 120,2bb com stack 8,8bb — o maior pote legitimo do acervo
    assert pote_implausivel(120.2, 8.8, 1) is False
    print('OK  test_dinheiro_morto_com_UM_vilao_ativo_passa')


def test_multiway_ATIVO_segue_barrado():
    """2+ vilões ativos: o solver é HU-only; dinheiro morto não muda isso."""
    assert pote_implausivel(44.9, 5.2, 2) is True   # t125
    assert pote_implausivel(68.4, 12.0, 2) is True  # t113
    print('OK  test_multiway_ATIVO_segue_barrado')


def test_CONTROLE_pote_normal_nunca_barra():
    """Sem esta âncora, 'barrar tudo' passaria nos testes de fichas."""
    assert pote_implausivel(6.0, 20.0, 1) is False
    assert pote_implausivel(6.0, 20.0, 2) is False   # multiway com pote normal também passa
    assert pote_implausivel(0.0, 20.0, None) is False
    print('OK  test_CONTROLE_pote_normal_nunca_barra')


def test_sem_info_de_ativos_usa_a_regra_conservadora():
    """n_ativos None (caminho legado sem o campo): comporta como antes — barra."""
    assert pote_implausivel(50.6, 0.8, None) is True
    print('OK  test_sem_info_de_ativos_usa_a_regra_conservadora')


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
