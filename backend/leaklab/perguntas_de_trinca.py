# -*- coding: utf-8 -*-
"""Set mining: quando pagar um aumento com par de bolso vale pela trinca.

── Por que existe (28/08) ──────────────────────────────────────────────────────────────────

Do benchmark do concorrente, o "treino de trinca". Medindo o que já tínhamos antes de construir:
a Academia **já ensina** implied odds (capítulo inteiro numa aula, com as reverse implied odds
junto) e `academy_questions` já tem uma pergunta sobre quando elas NÃO valem.

O que não existia era o treino repetível, com os números mudando. Texto de aula ensina o conceito;
o reflexo de "isto fecha ou não fecha" só nasce fazendo a conta muitas vezes com valores
diferentes.

── Por que este treino é diferente do resto do produto ─────────────────────────────────────

Aqui existe **resposta exata**. A frequência de flopar trinca não é estimativa nem depende de
solver, de carta capturada ou de tamanho de amostra: é combinatória.

    P(trinca ou melhor no flop) = 1 - C(48,3)/C(50,3) = 11,7551%

Conferido por dois caminhos independentes: a fórmula e a enumeração dos 19.600 flops possíveis
(2.304 acertam). Onde quase tudo neste produto carrega procedência e incerteza, aqui dá para
afirmar sem ressalva -- e o teste refaz as duas contas, para o número nunca virar literal
copiado.

── A parte que NÃO é exata, e é declarada ──────────────────────────────────────────────────

Empatar exige ganhar **8,5x** o custo do call. Mas ninguém recebe o stack inteiro toda vez que
acerta: o vilão folda, o board assusta, e às vezes a trinca perde. Por isso a regra de mesa pede
folga, e as folgas usadas na literatura ficam entre 15x e 20x.

Esta é uma REGRA PRÁTICA, não um teorema, e as perguntas dizem isso. Vender 15x como se fosse
matemática seria o mesmo erro que este produto passou o dia consertando: número com cara de
medido que na verdade é convenção.
"""
from __future__ import annotations

import random
from math import comb

#: P(flopar trinca ou melhor) com um par de bolso. CALCULADO, e não escrito à mão -- um literal
#: aqui envelheceria calado se alguém "arredondasse" para 12% num refactor.
P_TRINCA = 1 - comb(48, 3) / comb(50, 3)

#: Quanto o call precisa render para EMPATAR, contando só a trinca. Também derivado.
RETORNO_DE_EMPATE = 1 / P_TRINCA          # ~8,5x

#: Folga prática: o vilão nem sempre paga, e a trinca nem sempre ganha. NÃO é teorema.
MULTIPLICADOR_PRATICO = 15

_PARES = ['22', '33', '44', '55', '66', '77', '88', '99']
_POSICOES = ['UTG', 'HJ', 'CO', 'BTN']


def stack_minimo(custo_bb: float) -> float:
    """Stack efetivo ATRÁS que o set mining pede, pela regra prática."""
    return round(custo_bb * MULTIPLICADOR_PRATICO, 1)


def fecha_a_conta(custo_bb: float, stack_atras_bb: float) -> bool:
    """A conta fecha? `stack_atras` é o que sobra DEPOIS de pagar -- é o que a trinca pode cobrar."""
    return stack_atras_bb >= stack_minimo(custo_bb)


def p_paga_ou_folda(rng: random.Random):
    """O treino principal: com este par, este aumento e este stack, o set mining fecha?

    Os casos são gerados nos dois lados da fronteira de propósito, e nunca colados nela: um caso a
    1% do limite ensina a decorar o número em vez de entender a folga.
    """
    par = rng.choice(_PARES)
    pos = rng.choice(_POSICOES)
    custo = rng.choice([2.0, 2.5, 3.0, 3.5, 4.0])
    minimo = stack_minimo(custo)
    # Longe da fronteira nos dois sentidos: ou sobra folga, ou falta claramente.
    if rng.random() < 0.5:
        stack_atras = round(minimo * rng.uniform(1.35, 2.6), 1)
    else:
        stack_atras = round(minimo * rng.uniform(0.30, 0.70), 1)
    fecha = fecha_a_conta(custo, stack_atras)

    opcoes = ['Pagar', 'Foldar']
    certa = 0 if fecha else 1
    if rng.random() < 0.5:
        opcoes.reverse()
        certa = 1 - certa
    return {
        'tipo': 'set_mining', 'dificuldade': 'basica',
        'posicao': pos, 'stack': round(stack_atras + custo, 1),
        'pergunta': ('%s abre para %sbb e você tem %s. Sobram %sbb atrás. Vale pagar pela trinca?'
                     % (pos, _n(custo), par, _n(stack_atras))),
        'opcoes': opcoes, 'correta': certa,
        'explicacao': (
            'Você floppa trinca em %.1f%% das vezes, ou 1 em %.1f. Só isso já exige ganhar %.1fx '
            'o que você paga, e na mesa pede mais, porque o vilão nem sempre paga e a trinca nem '
            'sempre ganha: a régua prática é %dx. Aqui você paga %sbb, então precisaria de %sbb '
            'atrás e tem %sbb. %s'
            % (P_TRINCA * 100, RETORNO_DE_EMPATE, RETORNO_DE_EMPATE, MULTIPLICADOR_PRATICO,
               _n(custo), _n(minimo), _n(stack_atras),
               'Sobra folga.' if fecha else 'Falta stack para a trinca cobrar.')),
    }


def p_quanto_precisa_atras(rng: random.Random):
    """A mesma conta pelo outro lado: dado o custo, quanto stack o set mining pede?

    Distratores são os mínimos de OUTROS custos reais, nunca números em volta da resposta -- a
    mesma disciplina das perguntas de range e de board.
    """
    custo = rng.choice([2.0, 2.5, 3.0, 3.5, 4.0])
    certa = stack_minimo(custo)
    outros = sorted({stack_minimo(c) for c in (2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)} - {certa},
                    key=lambda v: -abs(v - certa))
    escolhidos, usados = [], [certa]
    for v in outros:
        if all(abs(v - u) >= 5 for u in usados):
            escolhidos.append(v)
            usados.append(v)
        if len(escolhidos) == 2:
            break
    if len(escolhidos) < 2:
        return None

    from leaklab.perguntas_de_range import _embaralhar
    opcoes, idx = _embaralhar(rng, ['%sbb' % _n(v) for v in [certa] + escolhidos], 0)
    return {
        'tipo': 'set_mining_stack', 'dificuldade': 'intermediaria',
        'pergunta': ('Você quer pagar %sbb com um par pequeno só pela trinca. Quanto precisa '
                     'ter ATRÁS para a conta fechar?' % _n(custo)),
        'opcoes': opcoes, 'correta': idx,
        'explicacao': (
            'A trinca vem em %.1f%% dos flops, então empatar já exigiria ganhar %.1fx o custo. A '
            'régua de mesa usa %dx, porque o vilão nem sempre paga: %sbb x %d = %sbb. Abaixo '
            'disso você está pagando por uma mão que não tem o que cobrar quando acerta.'
            % (P_TRINCA * 100, RETORNO_DE_EMPATE, MULTIPLICADOR_PRATICO,
               _n(custo), MULTIPLICADOR_PRATICO, _n(certa))),
    }


def p_frequencia_da_trinca(rng: random.Random):
    """Quantas vezes a trinca vem. O número que sustenta todo o resto.

    Distratores são erros REAIS que jogadores cometem: confundir com a chance de flopar par
    (a mão já é par), ou com a de completar até o river (~19%), que é outra pergunta.
    """
    from leaklab.perguntas_de_range import _embaralhar
    ate_river = 1 - (comb(48, 3) / comb(50, 3)) * (45 / 47) * (44 / 46)
    valores = [P_TRINCA, ate_river, 0.02]
    rotulos = ['%.0f%%' % (v * 100) for v in valores]
    if len(set(rotulos)) < 3:
        return None
    opcoes, idx = _embaralhar(rng, rotulos, 0)
    return {
        'tipo': 'trinca_frequencia', 'dificuldade': 'basica',
        'pergunta': 'Com um par de bolso, quantas vezes você floppa trinca ou melhor?',
        'opcoes': opcoes, 'correta': idx,
        'explicacao': (
            '%.1f%%, ou 1 em %.1f. Sai da combinatória: das %d combinações de flop possíveis, '
            '%d trazem pelo menos uma das duas cartas que faltam. Até o river a chance sobe para '
            '~%.0f%%, mas essa é outra conta: no flop você ainda decide se paga.'
            % (P_TRINCA * 100, RETORNO_DE_EMPATE, comb(50, 3),
               comb(50, 3) - comb(48, 3), ate_river * 100)),
    }


def _n(v: float) -> str:
    """Número sem `.0` pendurado: '3' e não '3.0'."""
    return ('%g' % round(float(v), 1))


def gerar(rng: random.Random | None = None, dificuldade: str | None = None, tentativas: int = 4):
    """Uma pergunta de set mining. `None` quando não dá para montar."""
    rng = rng or random
    # ── Peso, e não sorteio uniforme ────────────────────────────────────────────────────────
    #
    # `p_frequencia_da_trinca` é a mesma pergunta SEMPRE: os números não variam, porque a
    # frequência é uma constante do baralho. Medido num sorteio uniforme, ela saiu 3 vezes em 5 --
    # e pergunta que não muda vira memorização depois da primeira exposição, não treino.
    #
    # Ela continua existindo porque é a âncora: o 11,8% sustenta as outras duas. Só aparece
    # pouco, como fundamento que se relembra, e não como exercício.
    candidatas = [
        ('basica',        p_paga_ou_folda,        5),
        ('intermediaria', p_quanto_precisa_atras, 4),
        ('basica',        p_frequencia_da_trinca, 1),
    ]
    if dificuldade:
        candidatas = [c for c in candidatas if c[0] == dificuldade]
    if not candidatas:
        return None
    _sorteio = [fn for _d, fn, peso in candidatas for _ in range(peso)]
    for _ in range(tentativas):
        fn = rng.choice(_sorteio)
        try:
            q = fn(rng)
        except Exception:                                      # noqa: BLE001
            q = None
        if q:
            return q
    return None
