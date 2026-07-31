# -*- coding: utf-8 -*-
"""
Revisor do texto gerado: concordancia dos termos de poker em portugues.

── O que o usuario reportou ───────────────────────────────────────────────────────────────────────

Num texto do desafio do dia:

    "ou ir straight para o shove"     → 'straight' e uma MAO (sequencia). Usado como adverbio
                                        ingles no meio de uma frase em portugues, ele muda de
                                        significado e confunde: o leitor procura a sequencia.
    "ruas de decisao"                 → 'street' traduzido, e street e termo tecnico
    "se shover toda vez"              → conjugacao inventada; a forma consagrada e 'shovou'

── Por que isto existe, sendo que o PROMPT ja proibia ─────────────────────────────────────────────

O `_POKER_TERMS_EN` diz textualmente "NUNCA use 'rua' ou 'ruas', sempre 'street' ou 'streets'", e o
modelo escreveu "ruas de decisao" mesmo assim. Instrucao no prompt e esperanca, nao garantia — e a
regra deste projeto e que guarda precisa ser verificavel. Entao a checagem acontece DEPOIS da
geracao, sobre o texto que vai para a tela.

── O que ele corrige e o que ele apenas ACUSA ─────────────────────────────────────────────────────

Corrigir automaticamente um texto e arriscado: o conserto pode causar dano que o bug nao causava.
"rua"→"street" e substituicao 1 para 1 e nao muda a frase. Ja "se shover toda vez" exigiria
reescrever a oracao, e um remendo cego produziria portugues quebrado — pior do que o termo torto,
porque o termo torto o leitor contorna e a frase quebrada nao.

Entao:
  · GRAVE   → so acusa. Quem chamou decide (regerar, ou publicar com o problema registrado).
  · TROCA   → corrige, porque a substituicao e inequivoca.
"""
from __future__ import annotations

import re

# ── Termos que NAO podem ser traduzidos, com a traducao errada que o modelo tende a usar ──────────
#
# So entram pares em que a palavra portuguesa NAO tem outro uso plausivel num texto de poker. Por
# isso "sequencia" nao esta aqui: ela e a traducao legitima de 'straight' quando se fala da MAO.
_TROCAS = [
    (re.compile(r'\bruas\b', re.I), 'streets'),
    (re.compile(r'\brua\b', re.I),  'street'),
]

# ── Termo de poker usado como palavra comum ───────────────────────────────────────────────────────
#
# O caso do usuario: 'straight' seguido de preposicao e o adverbio ingles ("straight para o shove"),
# nao a mao. Uma mao nunca aparece seguida de "para/pro/ate/em direcao".
_COMO_ADVERBIO = re.compile(
    r'\b(straight|flush|river|turn|check)\s+(para|pro|pra|até|ate|em direção|em direcao)\b', re.I)

# ── Conjugacao inventada ─────────────────────────────────────────────────────────────────────────
#
# Radical ingles com terminacao portuguesa. As formas consagradas do jogador brasileiro ficam de
# fora pela lista de excecao — elas sao o jeito CERTO, e acusa-las treinaria o revisor a mentir.
_CONJUGADO = re.compile(
    r'\b(shov|rais|bett|bet|fold|check|call|limp|barrel|float)'
    r'(er|ando|endo|ar|arem|aria|eia|amos|ei|asse|ava)\b', re.I)
# NAO existe lista de excecao aqui, e a ausencia e deliberada.
#
# A primeira versao tinha uma (`{'foldou', 'shovou', ...}`) e ela era CODIGO MORTO: a lista de
# terminacoes acima nao inclui `-ou`, entao 'shovou' nunca chegava a ser testado contra a excecao.
# O teste que "protegia as formas consagradas" passava por esse motivo, e nao porque a protecao
# funcionava — descobri ao sabotar a excecao e ver o teste continuar verde.
#
# A protecao real e a lista de terminacoes ser FECHADA e nao conter `-ou`: as formas consagradas do
# jogador brasileiro ('shovou', 'foldou', 'limpou') terminam em `-ou` e por isso nao casam. O que
# casa sao as formas que o proprio prompt ja proibe: '-ando', '-endo', '-er', '-ar'.

# ── Rotulo de frequencia em ingles no comeco de frase ────────────────────────────────────────────
_ROTULO_EN = re.compile(r'(?:^|[.\n]\s*)(Weekly|Daily|Monthly|Always|Never|Sometimes)\s*:', re.M)

# Travessao como pontuacao (regra do projeto: soa "IA" na copy visivel).
_TRAVESSAO = re.compile(r'\s—\s')


def problemas(texto: str) -> list:
    """Lista de problemas do texto. Cada item: {tipo, trecho, motivo, grave}.

    `grave=True` significa "nao da para consertar sozinho": quem chamou precisa regerar ou assumir.
    """
    t = texto or ''
    achados = []

    for m in _COMO_ADVERBIO.finditer(t):
        achados.append({
            'tipo': 'termo_como_palavra_comum', 'trecho': m.group(0), 'grave': True,
            'motivo': (f"'{m.group(1)}' e um termo de poker usado aqui como palavra comum. "
                       f"O leitor procura a mao. Escreva em portugues (ex.: 'direto para')."),
        })

    for m in _CONJUGADO.finditer(t):
        achados.append({
            'tipo': 'conjugacao_inventada', 'trecho': m.group(0), 'grave': True,
            'motivo': (f"'{m.group(0)}' e aportuguesamento inventado. Use a forma perifrastica "
                       f"('der shove', 'deu raise') ou a consagrada ('shovou', 'foldou')."),
        })

    for m in _ROTULO_EN.finditer(t):
        achados.append({'tipo': 'rotulo_em_ingles', 'trecho': m.group(1), 'grave': True,
                        'motivo': "rotulo de frequencia em ingles; use 'Semanal:', 'Diario:'."})

    for rx, certo in _TROCAS:
        for m in rx.finditer(t):
            achados.append({'tipo': 'termo_traduzido', 'trecho': m.group(0), 'grave': False,
                            'motivo': f"termo tecnico traduzido; o certo e '{certo}'."})

    for m in _TRAVESSAO.finditer(t):
        achados.append({'tipo': 'travessao', 'trecho': m.group(0).strip(), 'grave': False,
                        'motivo': "travessao como pontuacao; use virgula, dois-pontos ou ponto."})

    return achados


def revisar(texto: str) -> tuple:
    """(texto_corrigido, problemas_graves).

    Aplica so as trocas inequivocas. O que exige reescrever a oracao volta na lista, porque
    remendo cego produz portugues quebrado — e frase quebrada e pior que termo torto: o termo o
    leitor contorna, a frase nao.
    """
    t = texto or ''
    for rx, certo in _TROCAS:
        # preserva a caixa da primeira letra: "Ruas" no inicio de frase nao vira "streets"
        t = rx.sub(lambda m: certo.capitalize() if m.group(0)[:1].isupper() else certo, t)
    t = _TRAVESSAO.sub(', ', t)
    return t, [p for p in problemas(t) if p['grave']]


def instrucao_de_correcao(probs: list) -> str:
    """Texto para reenviar ao modelo numa segunda tentativa, citando o trecho exato.

    Citar o TRECHO importa: "evite anglicismos" o modelo ja recebeu e ignorou. "Voce escreveu
    'ir straight para', corrija" e acionavel.
    """
    if not probs:
        return ''
    linhas = [f"- \"{p['trecho']}\": {p['motivo']}" for p in probs]
    return ("O texto anterior tem os problemas abaixo. Reescreva corrigindo APENAS eles, "
            "mantendo o conteudo e o tamanho:\n" + "\n".join(linhas))
