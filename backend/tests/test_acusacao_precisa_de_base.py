# -*- coding: utf-8 -*-
"""Acusação precisa de base: um número que valha, e um nome.

── Os dois casos que originaram (27/08, rodada 2 de auditoria) ────────────────────────────

**1. "Pague" apoiado em equity contra mão ALEATÓRIA.** Um juiz de poker leu o sintoma: nove-alto
sem projeto recebendo *"pague, 32% > 27,7% exigidos"* — e contra o range que aposta 57% do pote
essa mão tem uns 10%. Depois de duas rodadas de conserto, **5 das 35 acusações** do torneio 72
ainda eram dessa forma: recomendam `call`, sem custo medido, com a equity vindo de `vs_random`.
Três preflop e duas no turn.

Esta regra é irmã de `equity_vs_random_nao_condena_fold`: aquela pergunta "o hero foldou e a
equity condena?", esta pergunta "o produto manda PAGAR apoiado em quê?". Vale em qualquer street
porque o defeito não é de street — é da comparação.

**2. Erro sem nome.** `error_label` fica `None` quando o advisor multiway assume, e `is_error`
seguia `True`: o card marcava "Erro" sem uma palavra que dissesse QUAL erro. Quatro casos, três
com custo medido de 0,00bb. O aluno não tem o que fazer com um erro sem nome.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_pagar_apoiado_em_vs_random_sem_custo_nao_acusa():
    from leaklab.verdict import acusacao_de_call_sem_custo_com_equity_vs_random as regra
    assert regra('small_mistake', 'call', 'vs_random', False) == 'marginal', (
        'voltou a acusar recomendando PAGAR com equity medida contra mão aleatória e sem custo')
    assert regra('clear_mistake', 'call', 'vs_random', False) == 'marginal'
    print('OK  test_pagar_apoiado_em_vs_random_sem_custo_nao_acusa')


def test_com_custo_ou_com_vs_range_nada_muda():
    """As duas contraprovas. Com custo há um número que não veio do estimador; com `vs_range` a
    conta está contra quem apostou. Uma regra que rebaixasse os dois viraria peneira."""
    from leaklab.verdict import acusacao_de_call_sem_custo_com_equity_vs_random as regra
    assert regra('small_mistake', 'call', 'vs_random', True) == 'small_mistake', (
        'acusação COM custo medido foi rebaixada')
    assert regra('small_mistake', 'call', 'vs_range', False) == 'small_mistake', (
        'acusação com equity contra o RANGE foi rebaixada — essa conta é honesta')
    print('OK  test_com_custo_ou_com_vs_range_nada_muda')


def test_a_regra_e_do_CALL_e_de_mais_nada():
    """A direção importa: inflar equity ABSOLVE quem paga e CONDENA quem folda. Esta regra cuida
    da recomendação de pagar; o fold tem a irmã dela."""
    from leaklab.verdict import acusacao_de_call_sem_custo_com_equity_vs_random as regra
    for best in ('fold', 'raise', 'jam', 'check', 'bet'):
        assert regra('small_mistake', best, 'vs_random', False) == 'small_mistake', (
            'a regra passou a pegar recomendação de %s' % best)
    assert regra('standard', 'call', 'vs_random', False) == 'standard'
    print('OK  test_a_regra_e_do_CALL_e_de_mais_nada')


def test_o_motor_aplica_a_regra_do_call():
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    assert 'acusacao_de_call_sem_custo_com_equity_vs_random(' in codigo, (
        'o motor parou de aplicar a regra: volta a mandar pagar apoiado em vs_random')
    print('OK  test_o_motor_aplica_a_regra_do_call')


def test_erro_sem_nome_deixa_de_ser_erro():
    """Fiação no `/replay`: `error_label` None com `is_error` True marcava "Erro" sem dizer qual."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    assert 'if _el_efetivo is None:' in codigo and 'is_error = False' in codigo, (
        'o card voltou a poder marcar "Erro" sem rótulo — erro sem nome não é veredito')
    print('OK  test_erro_sem_nome_deixa_de_ser_erro')


def test_a_classe_da_mao_tambem_vale_AQUI():
    """A condição compartilhada, terceiro consumidor — e os mesmos três guardas antigos me pegaram
    de novo. Com par+ o estimador SUBvaloriza, e ali a acusação pode ser legítima; sem cartas ou
    sem board não dá para AFIRMAR que o hero não tem nada."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'decision_engine_v11.py')
    with open(caminho, encoding='utf-8') as fh:
        codigo = chr(10).join(l.split('#')[0] for l in fh.read().split(chr(10)))
    i = codigo.index('acusacao_de_call_sem_custo_com_equity_vs_random(')
    trecho = codigo[max(0, i - 300):i + 60]
    assert 'estimador_infla_a_equity(' in trecho, (
        'a regra do call voltou a valer sem olhar a classe da mão: rebaixa o fold de top pair')
    n = codigo.count('estimador_infla_a_equity(')
    assert n >= 3, (
        'a condição de classe de mão tem %d consumidores, esperados 3 (sem gabarito, fold '
        'vs_random, call vs_random)' % n)
    print('OK  test_a_classe_da_mao_tambem_vale_AQUI')


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
