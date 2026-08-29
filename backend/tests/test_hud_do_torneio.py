# -*- coding: utf-8 -*-
"""HUD do herói num torneio só: descreve a sessão, declara a amostra, nunca esconde.

── O que originou (29/08) ───────────────────────────────────────────────────────────────────

Pedido do dono: nos detalhes do torneio, os indicadores DELE naquele torneio, "mesmo que o
número de amostras seja baixo". `finalize()` do HUD de oponente aplica gates (VPIP 100+,
3-bet 750+) e devolveria uma tela vazia para qualquer torneio real.

── O contrato que estes testes fixam ───────────────────────────────────────────────────────

1. Taxa SEM gate, mas SEMPRE com numerador/denominador e banda — `low_sample` quando a régua
   de comparação não vale ([[project_opponent_hud]]: nenhum read sem amostra; aqui não é read,
   é descrição, e a banda separa as duas coisas).
2. Sem oportunidade não há taxa: `no_opportunity`, nunca 0 mudo (a regra da célula cinza).
3. Arquétipo continua atrás do gate de 100 mãos: rótulo é comparação, não descrição.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.models import ParsedAction, ParsedHand
from leaklab.hud_do_torneio import hud_do_heroi


def _mao(hid, players, acts, hero='Heroi'):
    actions = [ParsedAction(player=a[0], street=a[1], action=a[2],
                            amount=(a[3] if len(a) > 3 else None)) for a in acts]
    return ParsedHand(hand_id=hid, players=list(players), actions=actions, hero=hero)


def _sessao_curta():
    """5 mãos: herói abre 2, paga 1, folda 2. VPIP 3/5, PFR 2/5."""
    maos = []
    for i in range(2):
        maos.append(_mao('r%d' % i, ['Heroi', 'V1'], [
            ('Heroi', 'preflop', 'raises', 3), ('V1', 'preflop', 'folds')]))
    maos.append(_mao('c1', ['V1', 'Heroi'], [
        ('V1', 'preflop', 'raises', 3), ('Heroi', 'preflop', 'calls', 3)]))
    for i in range(2):
        maos.append(_mao('f%d' % i, ['V1', 'Heroi'], [
            ('V1', 'preflop', 'raises', 3), ('Heroi', 'preflop', 'folds')]))
    return maos


def test_taxa_sai_MESMO_com_amostra_curta():
    """O motivo do módulo existir: 5 mãos já descrevem a sessão."""
    hud = hud_do_heroi(_sessao_curta(), 'Heroi')
    assert hud and hud['hands'] == 5
    v = hud['stats']['vpip']
    assert v['value'] == 60.0 and v['num'] == 3 and v['den'] == 5, v
    p = hud['stats']['pfr']
    assert p['value'] == 40.0 and p['num'] == 2 and p['den'] == 5, p
    print('OK  test_taxa_sai_MESMO_com_amostra_curta')


def test_amostra_curta_e_DECLARADA_na_banda():
    """O número aparece, mas carimbado: 5 mãos não sustentam comparação com a referência."""
    hud = hud_do_heroi(_sessao_curta(), 'Heroi')
    assert hud['stats']['vpip']['band'] == 'low_sample', hud['stats']['vpip']
    print('OK  test_amostra_curta_e_DECLARADA_na_banda')


def test_sem_oportunidade_nao_vira_zero():
    """Ninguém deu 3-bet no herói: fold-to-3bet é ausência, não 0%. A regra da célula cinza."""
    hud = hud_do_heroi(_sessao_curta(), 'Heroi')
    f3 = hud['stats']['fold3bet']
    assert f3['value'] is None and f3['band'] == 'no_opportunity', f3
    print('OK  test_sem_oportunidade_nao_vira_zero')


def test_com_amostra_a_banda_compara_com_a_referencia():
    """Contraprova do low_sample: com 120 mãos a banda deixa de ser carimbo e vira leitura
    (VPIP 60% em amostra cheia = above/loose)."""
    maos = []
    for i in range(72):
        maos.append(_mao('a%d' % i, ['Heroi', 'V1'], [
            ('Heroi', 'preflop', 'raises', 3), ('V1', 'preflop', 'folds')]))
    for i in range(48):
        maos.append(_mao('b%d' % i, ['V1', 'Heroi'], [
            ('V1', 'preflop', 'raises', 3), ('Heroi', 'preflop', 'folds')]))
    hud = hud_do_heroi(maos, 'Heroi')
    assert hud['hands'] == 120
    assert hud['stats']['vpip']['band'] == 'above', hud['stats']['vpip']
    assert hud['stats']['vpip']['healthy'], 'a faixa saudavel nao viajou junto'
    print('OK  test_com_amostra_a_banda_compara_com_a_referencia')


def test_arquetipo_fica_atras_do_gate():
    """Rótulo é comparação: 5 mãos não têm arquétipo, nem 'unknown' maquiado."""
    assert hud_do_heroi(_sessao_curta(), 'Heroi')['archetype'] is None
    print('OK  test_arquetipo_fica_atras_do_gate')


def test_heroi_ausente_devolve_None():
    assert hud_do_heroi(_sessao_curta(), 'NaoJoguei') is None
    assert hud_do_heroi([], 'Heroi') is None
    assert hud_do_heroi(_sessao_curta(), '') is None
    print('OK  test_heroi_ausente_devolve_None')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
