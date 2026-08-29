# -*- coding: utf-8 -*-
"""Set mining: o único treino deste produto em que a resposta é EXATA.

── O que originou (28/08) ──────────────────────────────────────────────────────────────────

O "treino de trinca" do benchmark. Medindo antes de construir: a Academia já ensinava implied
odds num capítulo inteiro, e `academy_questions` já tinha uma pergunta sobre quando elas não
valem. O que faltava era o treino REPETÍVEL, com os números mudando -- texto ensina o conceito, o
reflexo só nasce fazendo a conta muitas vezes.

── Por que estes guardas são diferentes dos outros ─────────────────────────────────────────

Quase todo número deste produto é estimativa com procedência: equity, largura de range, custo em
bb. Aqui não. A frequência de flopar trinca é combinatória pura, e por isso os guardas podem
exigir o valor EXATO -- refazendo a conta por dois caminhos independentes, em vez de comparar com
um literal que alguém pode ter arredondado.

E há uma segunda metade, que é convenção e não teorema: o multiplicador de 15x. Os guardas
separam as duas coisas de propósito. Vender convenção como matemática seria o mesmo defeito que
este produto passou o dia consertando.
"""
import os
import random
import sys
from itertools import combinations
from math import comb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_a_frequencia_da_trinca_bate_por_DOIS_caminhos():
    """Fórmula e enumeração exaustiva. Um literal errado passaria por um só."""
    from leaklab.perguntas_de_trinca import P_TRINCA

    por_formula = 1 - comb(48, 3) / comb(50, 3)
    # Enumeração real dos 19.600 flops: as duas cartas que completam o par são {0, 1}.
    baralho = list(range(50))
    faltam = {0, 1}
    acertos = sum(1 for f in combinations(baralho, 3) if faltam & set(f))
    por_enumeracao = acertos / comb(50, 3)

    assert abs(por_formula - por_enumeracao) < 1e-12, (
        'os dois caminhos discordam: %.8f vs %.8f' % (por_formula, por_enumeracao))
    assert abs(P_TRINCA - por_enumeracao) < 1e-12, (
        'P_TRINCA (%.6f) não bate com a enumeração (%.6f)' % (P_TRINCA, por_enumeracao))
    assert 0.117 < P_TRINCA < 0.118, 'valor fora da faixa conhecida: %.4f' % P_TRINCA
    print('OK  test_a_frequencia_da_trinca_bate_por_DOIS_caminhos (%.4f%%, %d de %d flops)'
          % (P_TRINCA * 100, acertos, comb(50, 3)))


def test_o_retorno_de_empate_e_derivado_e_nao_escrito():
    """8,5x sai de 1/P. Se alguém cravar o número, ele e a probabilidade divergem no primeiro
    ajuste e ninguém percebe."""
    from leaklab.perguntas_de_trinca import P_TRINCA, RETORNO_DE_EMPATE
    assert abs(RETORNO_DE_EMPATE - 1 / P_TRINCA) < 1e-12
    assert 8.4 < RETORNO_DE_EMPATE < 8.6
    print('OK  test_o_retorno_de_empate_e_derivado_e_nao_escrito (%.2fx)' % RETORNO_DE_EMPATE)


def test_a_regra_pratica_e_MAIOR_que_o_empate():
    """A afirmação de poker inteira do treino.

    Se a régua prática ficasse abaixo do ponto de empate, o treino ensinaria a pagar em situação
    perdedora -- com número de aparência matemática, que é o pior jeito de errar.
    """
    from leaklab.perguntas_de_trinca import MULTIPLICADOR_PRATICO, RETORNO_DE_EMPATE
    assert MULTIPLICADOR_PRATICO > RETORNO_DE_EMPATE, (
        'a régua prática (%sx) é MENOR que o ponto de empate (%.1fx): o treino estaria mandando '
        'pagar no prejuízo' % (MULTIPLICADOR_PRATICO, RETORNO_DE_EMPATE))
    assert MULTIPLICADOR_PRATICO <= 25, (
        'régua de %sx é exigente demais: fold em spot lucrativo também é leak'
        % MULTIPLICADOR_PRATICO)
    print('OK  test_a_regra_pratica_e_MAIOR_que_o_empate (%dx > %.1fx)'
          % (MULTIPLICADOR_PRATICO, RETORNO_DE_EMPATE))


def test_a_resposta_do_paga_ou_folda_segue_a_conta():
    """A opção marcada tem de ser a que a regra produz, sempre. O embaralhamento é onde `correta`
    se perde, e aqui perder significa ensinar o contrário."""
    from leaklab.perguntas_de_trinca import p_paga_ou_folda, fecha_a_conta, stack_minimo
    import re
    rng = random.Random(7)
    conferidas = 0
    for _ in range(60):
        q = p_paga_ou_folda(rng)
        custo = float(re.search(r'abre para ([\d.]+)bb', q['pergunta']).group(1))
        atras = float(re.search(r'Sobram ([\d.]+)bb', q['pergunta']).group(1))
        esperado = 'Pagar' if fecha_a_conta(custo, atras) else 'Foldar'
        assert q['opcoes'][q['correta']] == esperado, (
            'com %sbb de custo e %sbb atrás (mínimo %s) a resposta marcada foi %r'
            % (custo, atras, stack_minimo(custo), q['opcoes'][q['correta']]))
        conferidas += 1
    assert conferidas >= 50
    print('OK  test_a_resposta_do_paga_ou_folda_segue_a_conta (%d casos)' % conferidas)


def test_os_casos_NAO_nascem_colados_na_fronteira():
    """CONTRAPROVA do teste acima: casos a 1% do limite passariam nele e ensinariam a decorar o
    número em vez de entender a folga. E gerariam discordância legítima entre bons jogadores."""
    from leaklab.perguntas_de_trinca import p_paga_ou_folda, stack_minimo
    import re
    rng = random.Random(5)
    piores = []
    for _ in range(80):
        q = p_paga_ou_folda(rng)
        custo = float(re.search(r'abre para ([\d.]+)bb', q['pergunta']).group(1))
        atras = float(re.search(r'Sobram ([\d.]+)bb', q['pergunta']).group(1))
        piores.append(abs(atras - stack_minimo(custo)) / stack_minimo(custo))
    assert min(piores) >= 0.25, (
        'caso gerado a %.0f%% da fronteira: perto demais para ter resposta única' % (min(piores) * 100))
    print('OK  test_os_casos_NAO_nascem_colados_na_fronteira (mais próximo: %.0f%% do limite)'
          % (min(piores) * 100))


def test_os_dois_lados_aparecem():
    """Um gerador que só produz 'Pagar' passaria em tudo acima e treinaria um viés."""
    from leaklab.perguntas_de_trinca import p_paga_ou_folda
    rng = random.Random(9)
    respostas = [p_paga_ou_folda(rng) for _ in range(80)]
    pagar = sum(1 for q in respostas if q['opcoes'][q['correta']] == 'Pagar')
    assert 20 <= pagar <= 60, 'de 80 casos, %d são "Pagar": o treino está enviesado' % pagar
    # E a POSIÇÃO da resposta certa também varia -- senão dá para acertar sem ler.
    primeiras = sum(1 for q in respostas if q['correta'] == 0)
    assert 20 <= primeiras <= 60, (
        'a resposta certa é a 1ª opção em %d de 80: dá para vencer sem ler' % primeiras)
    print('OK  test_os_dois_lados_aparecem (%d pagar, %d na 1a posicao, de 80)' % (pagar, primeiras))


def test_a_explicacao_DECLARA_o_que_e_convencao():
    """A régua de 15x é convenção, não teorema. A explicação tem de dizer por quê, senão o
    jogador guarda um número achando que é matemática."""
    from leaklab.perguntas_de_trinca import p_paga_ou_folda
    q = p_paga_ou_folda(random.Random(1))
    texto = q['explicacao'].lower()
    assert 'nem sempre' in texto, (
        'a explicação não diz por que a régua prática é maior que o empate: %r' % q['explicacao'])
    assert '8.5' in q['explicacao'] or '8,5' in q['explicacao'], (
        'a explicação não mostra o ponto de empate, que é a parte EXATA da conta')
    print('OK  test_a_explicacao_DECLARA_o_que_e_convencao')


def test_a_pergunta_respeita_o_contrato_das_outras():
    """Renderizada pela MESMA tela dos outros treinos."""
    from leaklab.perguntas_de_trinca import gerar
    for semente in (1, 2, 3, 4, 5):
        q = gerar(random.Random(semente))
        assert q, 'não gerou pergunta com semente %d' % semente
        for campo in ('tipo', 'dificuldade', 'pergunta', 'opcoes', 'correta', 'explicacao'):
            assert campo in q, 'falta %r' % campo
        assert 0 <= q['correta'] < len(q['opcoes'])
        assert len(set(q['opcoes'])) == len(q['opcoes']), 'opções repetidas: %s' % q['opcoes']
    print('OK  test_a_pergunta_respeita_o_contrato_das_outras')


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
