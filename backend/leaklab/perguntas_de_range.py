# -*- coding: utf-8 -*-
"""
Perguntas de RANGE do treino: um catalogo com dificuldade, no lugar de um molde so.

── O que o usuario reportou ───────────────────────────────────────────────────────────────────────

*"Estes desafios de range no treino estao muito basicos e repetitivos. Temos que criar mais opcoes,
algumas mais basicas, outras mais avancadas, sempre com a explicacao apos escolha do usuario."*

Medido antes de propor: existia **um unico tipo**, "que fatia das maos {pos} tem aqui?", com tres
percentuais. Ele varia posicao e stack, mas a FORMA e sempre a mesma, entao a segunda vez ja e
reconhecivel e a terceira e automatica. Repetitivo por construcao, nao por acaso.

── A regra que todas seguem ───────────────────────────────────────────────────────────────────────

Toda pergunta sai de dado REAL das ranges capturadas (`_freq_de_entrada`, `_estratos`,
`_larguras_por_posicao`). Nenhuma inventa numero, e nenhuma pergunta algo que a cobertura nao
sustenta: quando falta dado a geradora devolve None e o chamador tenta outra, em vez de produzir
uma alternativa falsa. Alternativa falsa e pior que exercicio repetido — ela ensina errado.

Todas devolvem `explicacao`, porque a pergunta so vale se o aluno entender POR QUE errou. Sem isso
o exercicio vira sorteio com feedback binario.

── Dificuldade ────────────────────────────────────────────────────────────────────────────────────

`basica`      — reconhecer: a mao entra? quem abre mais?
`intermediaria` — comparar: onde fica a borda? o que o stack faz?
`avancada`    — frequencia: o que e MISTO e o que e sempre? (o conceito que separa quem decorou
                range de quem entendeu range)
"""
from __future__ import annotations

import random

DIFICULDADES = ('basica', 'intermediaria', 'avancada')

# Posicoes com range de abertura, na ordem de acao. `SB` entra porque a range dela e limp-heavy e
# isso e justamente o que o aluno erra.
_POSICOES = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']


# ── De QUEM a pergunta fala ───────────────────────────────────────────────────────────────────────
#
# **Pedido do usuário, olhando um print:** a pergunta era *"qual destas **BTN** joga de dois jeitos a
# 17bb?"* e o botão "tabela de ranges" abria a matriz do **SB** — a posição do SPOT. Ele conferiu
# 86s, viu que ali não folda nunca, e concluiu que o produto tinha errado. Conferido no dado: BTN a
# 17bb tem 86s na fronteira entrando 32%; SB a 17bb tem 86s no núcleo, entrando 100%. **A pergunta
# estava certa e a referência que o próprio produto abriu é que não respondia a pergunta feita.**
#
# Por isso toda pergunta declara `posicao`/`stack`: a tela abre a matriz nessas condições enquanto a
# pergunta está em cena, e volta às do spot quando as cartas do herói aparecem.
#
# **`None` quando a pergunta não tem UMA posição.** `quem_abre_mais` compara duas — abrir uma delas
# seria apontar para metade das alternativas. `efeito_do_stack` tem uma posição e DUAS profundidades,
# então declara a posição e omite o stack. Declarar condição errada é pior que não declarar: foi
# exatamente isso que gerou o relato.

def _condicoes(pos: str | None, stack: float | None) -> dict:
    """As condições que a tabela de ranges deve mostrar para esta pergunta. Chaves ausentes = a
    tela mantém o que já usava (as do spot)."""
    saida = {}
    if pos:
        saida['posicao'] = pos
    if stack is not None:
        saida['stack'] = float(stack)
    return saida


def _larguras(stack: float) -> dict:
    from leaklab.academy_questions import _larguras_por_posicao
    try:
        return _larguras_por_posicao(float(stack)) or {}
    except Exception:
        return {}


def _faixa(v: float) -> str:
    from leaklab.academy_questions import _faixa as f
    return f(v)


def _embaralhar(rng, opcoes: list, idx_certa: int) -> tuple:
    """Embaralha mantendo o rastro da correta. Sem isto a resposta certa fica sempre na 1a posicao
    e o quiz fica venciivel sem ler — foi exatamente o bug que ficou meses num teste deste projeto
    com o comentario 'a opcao certa e sempre a 1a'."""
    ordem = list(range(len(opcoes)))
    rng.shuffle(ordem)
    return [opcoes[i] for i in ordem], ordem.index(idx_certa)


# ── BASICA: a mao entra na range? ─────────────────────────────────────────────────────────────────

def p_mao_entra(rng, pos: str, stack: float, excluir_mao: str | None = None):
    """Reconhecimento puro. Usa so maos do NUCLEO (>=90%) ou do LIXO (<10%): perguntar 'entra?'
    sobre uma mao mista nao tem resposta certa, e cobrar uma seria ensinar errado."""
    from leaklab.leak_trainer import _estratos, _HANDS
    est = _estratos(pos, list(_HANDS), float(stack))
    if not est or len(est.get('nucleo') or []) < 1 or len(est.get('lixo') or []) < 1:
        return None
    entra = rng.random() < 0.5
    pool = [h for h in (est['nucleo'] if entra else est['lixo']) if h != excluir_mao]
    if not pool:
        return None
    mao = rng.choice(pool)
    opcoes, certa = _embaralhar(rng, ['Sim, quase sempre', 'Nao, folda quase sempre'],
                                0 if entra else 1)
    return {
        'tipo': 'mao_entra', 'dificuldade': 'basica',
        **_condicoes(pos, stack),
        'pergunta': f'{pos} abre {mao} a {int(stack)}bb?',
        'opcoes': opcoes, 'correta': certa,
        'explicacao': (
            f'{mao} esta {"dentro" if entra else "fora"} da range de abertura de {pos} a '
            f'{int(stack)}bb. Saber o que entra e o que nao entra e a base: sem isso voce nao tem '
            f'como julgar se a mao do vilao e forte, porque nao sabe com o que ele chegou ali.'),
    }


# ── BASICA: quem abre mais ────────────────────────────────────────────────────────────────────────

def p_quem_abre_mais(rng, stack: float):
    """A ordem das larguras e o esqueleto do preflop. Duas posicoes distantes o bastante para a
    resposta nao depender de arredondamento."""
    larg = _larguras(stack)
    disp = [(p, v) for p, v in larg.items() if p in _POSICOES]
    if len(disp) < 2:
        return None
    rng.shuffle(disp)
    par = None
    for i in range(len(disp)):
        for j in range(i + 1, len(disp)):
            if abs(disp[i][1] - disp[j][1]) >= 6:
                par = (disp[i], disp[j])
                break
        if par:
            break
    if not par:
        return None
    (pa, va), (pb, vb) = par
    maior = pa if va > vb else pb
    opcoes, certa = _embaralhar(rng, [pa, pb], 0 if maior == pa else 1)
    return {
        'tipo': 'quem_abre_mais', 'dificuldade': 'basica',
        # DUAS posicoes comparadas: abrir uma seria apontar para metade das alternativas.
        **_condicoes(None, stack),
        'pergunta': f'A {int(stack)}bb, quem abre MAIS maos: {pa} ou {pb}?',
        'opcoes': opcoes, 'correta': certa,
        'explicacao': (
            f'{maior} abre mais. {pa} chega com {_faixa(va)} e {pb} com {_faixa(vb)}. Quanto menos '
            f'gente falta agir atras de voce, mais larga a range pode ser, porque ha menos chance '
            f'de alguem acordar com mao forte.'),
    }


# ── INTERMEDIARIA: o que o stack faz com a range ──────────────────────────────────────────────────

def p_efeito_do_stack(rng, pos: str, stack_a: float, stack_b: float):
    la, lb = _larguras(stack_a).get(pos), _larguras(stack_b).get(pos)
    if la is None or lb is None or abs(la - lb) < 4:
        return None
    mais_larga = stack_a if la > lb else stack_b
    opcoes, certa = _embaralhar(rng, [f'A {int(stack_a)}bb', f'A {int(stack_b)}bb'],
                                0 if mais_larga == stack_a else 1)
    return {
        'tipo': 'efeito_do_stack', 'dificuldade': 'intermediaria',
        # Uma posicao, DUAS profundidades: declara a posicao e omite o stack.
        **_condicoes(pos, None),
        'pergunta': f'A range de abertura de {pos} e mais LARGA com qual profundidade?',
        'opcoes': opcoes, 'correta': certa,
        'explicacao': (
            f'{pos} abre {_faixa(la)} a {int(stack_a)}bb e {_faixa(lb)} a {int(stack_b)}bb. '
            f'Profundidade muda o preco do erro: stack curto favorece maos que resolvem a mao '
            f'antes do flop, stack profundo pede maos que jogam bem depois dele.'),
    }


# ── AVANCADA: nucleo x fronteira ──────────────────────────────────────────────────────────────────

def p_qual_e_mista(rng, pos: str, stack: float, excluir_mao: str | None = None):
    """O conceito que separa quem decorou range de quem entendeu range: a mao que o GTO joga de
    dois jeitos. Sem ele, o aluno le toda range como uma lista de sim/nao."""
    from leaklab.leak_trainer import _estratos, _HANDS
    est = _estratos(pos, list(_HANDS), float(stack))
    if not est:
        return None
    fronteira, nucleo, lixo = est.get('fronteira') or [], est.get('nucleo') or [], est.get('lixo') or []
    if not fronteira or len(nucleo) < 1 or len(lixo) < 1:
        return None
    fronteira = [h for h in fronteira if h != excluir_mao]
    nucleo    = [h for h in nucleo if h != excluir_mao]
    lixo      = [h for h in lixo if h != excluir_mao]
    if not fronteira or not nucleo or not lixo:
        return None
    mista = rng.choice(fronteira)
    freq = (est.get('freqs') or {}).get(mista)
    opcoes, certa = _embaralhar(rng, [mista, rng.choice(nucleo), rng.choice(lixo)], 0)
    pct = f'{round(float(freq) * 100)}%' if freq is not None else 'parte das vezes'
    return {
        'tipo': 'qual_e_mista', 'dificuldade': 'avancada',
        **_condicoes(pos, stack),
        'pergunta': f'Qual destas {pos} joga de DOIS jeitos a {int(stack)}bb, as vezes entrando e '
                    f'as vezes foldando?',
        'opcoes': opcoes, 'correta': certa,
        'explicacao': (
            f'{mista} entra {pct} das vezes: e uma mao de FRONTEIRA. As outras duas o GTO joga '
            f'sempre do mesmo jeito. Range nao e uma lista de sim e nao, e uma lista de '
            f'frequencias, e e por isso que o vilao nao consegue te ler.'),
    }


def gerar(rng: random.Random | None = None, dificuldade: str | None = None,
          pos: str | None = None, stack: float = 30.0, tentativas: int = 6,
          excluir_mao: str | None = None):
    """Uma pergunta de range, opcionalmente filtrando por dificuldade.

    Tenta varias vezes porque geradora sem cobertura devolve None de proposito. Devolve None se
    nenhuma produzir — o chamador cai no exercicio antigo em vez de mostrar pergunta inventada.

    `excluir_mao` e OBRIGATORIO quando a pergunta antecede um exercicio sobre a mesma posicao: sem
    ele, um spot "UTG a 30bb, o que voce faz com KTo?" poderia vir precedido de "UTG abre KTo a
    30bb?", que E a resposta. A pergunta que da a resposta do proprio exercicio nao e so inutil,
    ela ensina que o produto nao presta atencao.
    """
    rng = rng or random
    candidatas = [
        ('basica',        lambda: p_mao_entra(rng, pos or rng.choice(_POSICOES), stack, excluir_mao)),
        ('basica',        lambda: p_quem_abre_mais(rng, stack)),
        ('intermediaria', lambda: p_efeito_do_stack(rng, pos or rng.choice(_POSICOES), 20.0, 50.0)),
        ('avancada',      lambda: p_qual_e_mista(rng, pos or rng.choice(_POSICOES), stack, excluir_mao)),
    ]
    if dificuldade:
        candidatas = [c for c in candidatas if c[0] == dificuldade]
    if not candidatas:
        return None
    for _ in range(tentativas):
        _, fn = candidatas[rng.randrange(len(candidatas))]
        try:
            q = fn()
        except Exception:
            q = None
        if q:
            return q
    return None
