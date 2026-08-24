# -*- coding: utf-8 -*-
"""No river a equity é enumerável — não pode sair de tabela por classe de mão.

── O caso que originou (24/08, auditoria pré-lançamento) ──────────────────────────────────

Quatro juízes de poker independentes apontaram a mesma coisa: os valores de equity de river se
repetiam. Em 25 decisões havia 14 valores distintos, `0.46` aparecia 7 vezes e `0.58` quatro,
em boards e mãos sem nenhuma relação. No flop e no turn a dispersão era normal (89 decisões /
46 valores; 56 / 38), o que localizou o defeito no river.

A causa não era um estimador ruim: `_postflop_made_equity` é uma tabela por CLASSE de mão,
calibrada para ruas com carta por vir. No river não há carta por vir — a mão é o que é, e a
equity sai por enumeração das 1.081 mãos possíveis do vilão em 6 ms.

Medido em 203 decisões de river do acervo: erro médio **0,20** contra a conta exata, nas duas
direções. `AcJc` em `KsKc7dKd7c` exibia 0,92 valendo 0,46; `KcKs` em `9dKdQs4c2h` exibia 0,56
valendo 0,98; um flush máximo aparecia com 79%.

── Por que contra a range de CONTINUAÇÃO, e não vs_random ─────────────────────────────────

Os dois foram medidos antes de escolher (regra 7 — o conserto pode causar dano que o bug não
causava):

    vs_random     → 4 vereditos mudam, dois deles `standard` → `small_mistake`
    continuação   → 0 vereditos mudam

vs_random criaria acusação nova contra quem não errou. A range de continuação corrige o número
exibido sem que o motor passe a acusar ninguém. E o veredito de river quase não depende deste
número: com a equity FORJADA em 0,99, só 4 de 203 decisões mudam de rótulo — o dano era de
exibição, e é assim que ele foi tratado.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_a_conta_do_river_acerta_os_casos_de_resposta_conhecida():
    """Controle (regra 1): sem estes, um número plausível passaria por correto."""
    from leaklab.equity_real import equity_river_vs_continuacao as eq

    # flush máximo, straight flush impossível (os diamantes do board são J, 5, 3)
    nuts = eq(['Ad', '4d'], ['6c', '5d', 'Jd', 'Qs', '3d'])
    assert nuts == 1.0, 'o flush máximo no river não deu 100%%: %s' % nuts

    # Q-high num board A-K-9-4-2: contra quem CONTINUA (par ou melhor), não ganha de ninguém
    lixo = eq(['Qh', '7c'], ['Ad', 'Kd', '9s', '4h', '2c'])
    assert lixo == 0.0, 'Q-high sem par no river não deu 0 contra a range de continuação: %s' % lixo

    # trinca num board sem flush possível: muito alta, mas não 100% (perde para AA/JJ/55/88)
    trinca = eq(['3s', '3h'], ['3c', 'Ad', 'Jc', '5s', '8h'])
    assert 0.90 < trinca < 1.0, 'trinca no river fora da faixa esperada: %s' % trinca

    # board incompleto não é river: tem que recusar em vez de inventar
    assert eq(['3s', '3h'], ['3c', 'Ad', 'Jc']) is None, 'aceitou board de flop como river'
    print('OK  test_a_conta_do_river_acerta_os_casos_de_resposta_conhecida')


def test_o_river_nao_usa_mais_a_tabela_por_classe():
    """Prova de fiação: a conta exata precisa estar NO CAMINHO, não só existir no módulo.

    Duas mãos de força muito diferente no mesmo board recebiam o MESMO valor — era assim que a
    tabela por classe se manifestava. Se o snapshot voltar a servir tabela, os dois valores
    colapsam e este teste acusa."""
    from leaklab.street_math_engine import build_math_snapshot, HandState

    def eq_de(hero, board):
        st = HandState(
            hand_id='t', street='river', hero='HERO', hero_cards=hero, board=board,
            player_action='check', pot_size=1000.0, facing_size=0.0,
            effective_stack_bb=40.0, position='BTN', villain_position='BB',
            is_in_position=True, is_multiway=False, actions=[],
            metadata={'bb': 100.0, 'n_active_opponents': 1})
        return build_math_snapshot(st).estimated_hand_equity

    board = ['9d', 'Kd', 'Qs', '4c', '2h']
    forte = eq_de('KcKs', board)      # trinca de reis
    fraco = eq_de('7c3h', board)      # nada
    assert forte is not None and fraco is not None, 'o snapshot parou de produzir equity no river'
    assert forte > 0.90, 'trinca de reis no river saiu com %s — voltou a tabela por classe' % forte
    assert fraco < 0.15, 'mão sem nada no river saiu com %s' % fraco
    assert forte - fraco > 0.70, (
        'trinca e lixo receberam valores próximos (%s vs %s): a equity de river voltou a ser '
        'carimbada por classe de mão' % (forte, fraco))
    print('OK  test_o_river_nao_usa_mais_a_tabela_por_classe')


def test_a_fonte_da_equity_de_river_nao_se_diz_vs_random():
    """O card muda a frase por `equitySource`. Dizer `vs_random` sobre um número enumerado
    contra range de continuação é rotular errado a própria origem — e foi por acreditar nesse
    rótulo que a auditoria mediu o número contra o oráculo errado."""
    caminho = os.path.join(os.path.dirname(__file__), '..', 'leaklab', 'pipeline.py')
    with open(caminho, encoding='utf-8') as fh:
        fonte = fh.read()
    i = fonte.index("'equitySource'")
    trecho = fonte[i:i + 400]
    # Só as linhas de CÓDIGO: a primeira versão olhava o trecho inteiro, pegava o comentário
    # que menciona `equity_river_exata` logo acima da expressão, e a mutação passou VERDE
    # (regra 8 — comentário não é evidência).
    codigo = chr(10).join(l.split('#')[0] for l in trecho.split(chr(10)))
    assert 'equity_river_exata' in codigo, (
        "`equitySource` voltou a decidir só por `villain_range`: o river enumerado passa a se "
        "declarar `vs_random`")
    print('OK  test_a_fonte_da_equity_de_river_nao_se_diz_vs_random')


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
