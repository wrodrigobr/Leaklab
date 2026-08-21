# -*- coding: utf-8 -*-
"""Vocabulário da copy ESTÁTICA que o jogador lê.

── O caso que originou (21/08) ────────────────────────────────────────────────────────────

O card "Conceito do spot" de BB vs SB dizia:

    Você já tem 1bb no pote e paga barato pra ver o flop, mas joga a mão inteira
    fora de posição.
    > Defenda o BB largo em preço bom, e aperte quando for jogar SEM POSIÇÃO.

Duas frases, dois termos para a mesma coisa — e o certo aparecia primeiro. Varrendo o
backend achei **quatro** ocorrências de "sem posição", e em DUAS delas o texto usava os dois
termos na mesma frase ("Fora de posição se 3-beta maior… por jogar sem posição"). Não era
escolha de estilo: era deslize repetido.

── Por que um teste, e não só o conserto ──────────────────────────────────────────────────

O `revisor_pt` existe, mas revisa o texto GERADO PELO LLM. Esta copy é estática, escrita à
mão, e nunca passa por ele — some do radar exatamente por ser confiável. É o mesmo tipo de
guarda do `test_board_slice_hash`: o que falha não é a lógica, é lembrar da regra num lugar
novo.

**A lista é curta de propósito.** Termo consagrado varia por região e por autor; travar
vocabulário demais transformaria o teste num revisor de estilo, e revisor que acusa o certo
é desligado. Aqui só entra o que tem UM termo correto e um errado inequívoco.
"""
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Arquivos que produzem copy DIDÁTICA lida pelo jogador (não log, não comentário de código).
#
# A lista começou com DOIS, e essa foi a falha: consertei o vocabulário no backend, declarei
# fechado, e depois achei 100 ocorrências nos locales do frontend e 17 nas perguntas do quiz.
# Regra 5 do CLAUDE.md: a regra vale nos N lugares, então o teste varre os N+1. Ao criar uma
# superfície nova de copy, ELA ENTRA AQUI.
_ARQUIVOS = [
    os.path.join('leaklab', 'progression.py'),
    os.path.join('leaklab', 'academy.py'),
    os.path.join('leaklab', 'academy_questions.py'),
]

# A copy do frontend vive em JSON, no mesmo repositório. Só o pt-BR: "largo plazo" é correto
# em espanhol e "wide"/"loose" são os termos certos em inglês, então varrer es/en com a régua
# do português seria o revisor gritando no lugar certo.
_LOCALES_PT = os.path.abspath(
    os.path.join(_BACKEND, '..', 'frontend', 'src', 'i18n', 'locales', 'pt-BR'))

# (padrão proibido, o que usar, por quê)
_PROIBIDOS = [
    (r'sem\s+posi[çc][ãa]o', 'fora de posição',
     'o termo consagrado é "fora de posição" (OOP); "sem posição" não é usado em português '
     'de poker, e os MESMOS arquivos já usam o certo em outros trechos'),
    (r'\blarg[oa]s?\b|largu[íi]ssim[oa]', 'amplo / mais mãos',
     'decalque de "wide". E não é troca de palavra: em "pague mais largo" o termo é ADVÉRBIO, '
     'e "pague mais amplo" está errado — o certo é "pague com um range mais amplo" ou '
     '"pague mais mãos", conforme o espaço da frase'),
]


def test_copy_nao_usa_termo_fora_do_vocabulario():
    violacoes = []
    varridas = 0
    for rel in _ARQUIVOS:
        caminho = os.path.join(_BACKEND, rel)
        if not os.path.exists(caminho):
            continue
        # MESMO detector do travessão (AST). Ter dois filtros no mesmo arquivo, um por linha e
        # outro por árvore, me fez acusar uma DOCSTRING como se fosse copy — o mesmo erro que
        # eu já tinha cometido ao aplicar a correção dos travessões por linha.
        for n, txt in _copy_do_arquivo(caminho):
            varridas += 1
            for padrao, certo, porque in _PROIBIDOS:
                if re.search(padrao, txt, re.IGNORECASE):
                    violacoes.append(
                        f'  {rel}:{n} → use "{certo}". {porque}\n    {" ".join(txt.split())[:90]}')

    assert varridas > 300, (
        f'só {varridas} strings de copy varridas, o filtro parou de casar, e um teste que '
        'não lê nada passa sempre')
    assert not violacoes, 'vocabulário fora do padrão na copy:\n' + '\n'.join(violacoes)
    print(f'OK  test_copy_nao_usa_termo_fora_do_vocabulario ({varridas} strings)')


def _strings_do_json(caminho):
    """Toda string de valor de um bundle de tradução, com a chave como 'linha'."""
    def desce(no, chave):
        if isinstance(no, dict):
            for k, v in no.items():
                for par in desce(v, f'{chave}.{k}' if chave else k):
                    yield par
        elif isinstance(no, list):
            for i, v in enumerate(no):
                for par in desce(v, f'{chave}[{i}]'):
                    yield par
        elif isinstance(no, str):
            yield chave, no

    with open(caminho, encoding='utf-8') as fh:
        for par in desce(json.load(fh), ''):
            yield par


def test_copy_do_frontend_nao_usa_termo_fora_do_vocabulario():
    """O lugar onde o vocabulário errado estava em MAIOR quantidade, e o último que olhei."""
    assert os.path.isdir(_LOCALES_PT), (
        f'{_LOCALES_PT} não existe. Não é motivo para pular: a copy pt-BR do produto mora aí, '
        'e um teste que não acha o alvo passa sempre')

    violacoes = []
    varridas = 0
    for arq in sorted(os.listdir(_LOCALES_PT)):
        if not arq.endswith('.json'):
            continue
        for chave, txt in _strings_do_json(os.path.join(_LOCALES_PT, arq)):
            varridas += 1
            for padrao, certo, porque in _PROIBIDOS:
                if re.search(padrao, txt, re.IGNORECASE):
                    violacoes.append(f'  {arq}:{chave} → use "{certo}". {porque}\n'
                                     f'    {" ".join(txt.split())[:90]}')

    assert varridas > 2000, f'só {varridas} strings de tradução lidas — o varredor está cego'
    assert not violacoes, ('vocabulário fora do padrão na copy pt-BR do frontend:\n'
                           + '\n'.join(violacoes))
    print(f'OK  test_copy_do_frontend_nao_usa_termo_fora_do_vocabulario ({varridas} strings)')


_FONTE_FRONT = os.path.abspath(os.path.join(_BACKEND, '..', 'frontend', 'src'))

# Comentário de TS/TSX é texto de DESENVOLVEDOR: "largo" ali quase sempre fala de largura de
# tela ("mais largo que alto"), e acusá-lo seria o revisor gritando no lugar errado. Sem um
# parser de TypeScript em Python, o caminho é recortar os comentários antes de varrer.
_COMENTARIO_TS = re.compile(r'/\*.*?\*/|(?<![:\w])//[^\n]*', re.S)


def _codigo_sem_comentario_de_texto(fonte):
    # troca cada comentário por quebras de linha, para que o número da linha continue certo
    return _COMENTARIO_TS.sub(lambda m: '\n' * m.group(0).count('\n'), fonte)


def _codigo_sem_comentario(caminho):
    with open(caminho, encoding='utf-8') as fh:
        return _codigo_sem_comentario_de_texto(fh.read())


def test_copy_hardcoded_no_frontend_nao_usa_termo_fora_do_vocabulario():
    """A QUINTA superfície, e a única que só apareceu ao varrer o bundle PUBLICADO.

    `ranges.ts` tinha `description: 'Sem posição, vs abertura'` escrito direto no código, fora
    do i18n. Nenhum dos guardas anteriores olhava para lá: eu procurava copy onde a copy
    *deveria* estar."""
    assert os.path.isdir(_FONTE_FRONT), f'{_FONTE_FRONT} não existe — o varredor está cego'

    violacoes = []
    arquivos = 0
    for raiz, _, nomes in os.walk(_FONTE_FRONT):
        for nome in sorted(nomes):
            # Arquivo de teste não é copy: lá "pergunta sem posição única" quer dizer "sem uma
            # posição definida", e acusar isso seria o revisor gritando num texto correto.
            if not nome.endswith(('.ts', '.tsx')) or '.test.' in nome or '.spec.' in nome:
                continue
            caminho = os.path.join(raiz, nome)
            arquivos += 1
            texto = _codigo_sem_comentario(caminho)
            for padrao, certo, porque in _PROIBIDOS:
                for m in re.finditer(padrao, texto, re.IGNORECASE):
                    linha = texto.count('\n', 0, m.start()) + 1
                    rel = os.path.relpath(caminho, _FONTE_FRONT)
                    trecho = ' '.join(texto[max(0, m.start() - 45):m.end() + 45].split())
                    violacoes.append(f'  src/{rel}:{linha} → use "{certo}". {porque}\n'
                                     f'    …{trecho}…')

    assert arquivos > 100, f'só {arquivos} arquivos .ts/.tsx lidos — o varredor não achou nada'
    assert not violacoes, ('vocabulário fora do padrão em copy escrita direto no código:\n'
                           + '\n'.join(violacoes))
    print(f'OK  test_copy_hardcoded_no_frontend_nao_usa_termo_fora_do_vocabulario '
          f'({arquivos} arquivos)')


def test_o_varredor_de_ts_ignora_comentario():
    """Contraprova do recorte: os comentários sobre LARGURA DE TELA não podem ser acusados."""
    fonte = ('// o emoji renderiza mais largo que o normal\n'
             '/* usado quando a tela é mais larga que alta */\n'
             "const rotulo = 'Fora de posição, vs abertura';\n"
             "const url = 'https://exemplo.com/x';\n")
    limpo = _codigo_sem_comentario_de_texto(fonte)
    assert not any(re.search(p, limpo, re.IGNORECASE) for p, _, _ in _PROIBIDOS), \
        f'acusou um comentário de desenvolvedor: {limpo!r}'
    assert 'https://exemplo.com/x' in limpo, 'o recorte comeu o "//" de uma URL'

    # E o inverso: a copy de verdade continua visível depois do recorte.
    ruim = fonte.replace('Fora de posição', 'Sem posição')
    assert any(re.search(p, _codigo_sem_comentario_de_texto(ruim), re.IGNORECASE)
               for p, _, _ in _PROIBIDOS), 'não achou o termo errado numa string de código'
    print('OK  test_o_varredor_de_ts_ignora_comentario')


def test_o_varredor_ACHA_o_termo_errado():
    """Prova de detecção (regra 1). Sem isto, o teste acima poderia estar passando porque
    parou de ler os arquivos — e um zero tranquilizador aqui deixaria a copy solta."""
    forjado = 'regra = "Defenda o BB largo e aperte quando for jogar sem posição."'
    # `any` não bastaria: a frase original tem OS DOIS problemas, e passar por achar só um
    # deixaria o outro padrão apodrecer sem ninguém notar.
    pegos = {certo for p, certo, _ in _PROIBIDOS if re.search(p, forjado, re.IGNORECASE)}
    assert len(pegos) == 2, (
        f'a frase que originou este teste tem "largo" E "sem posição"; o varredor achou '
        f'{len(pegos)}: {pegos}')

    # E o contrário: o texto correto não pode ser acusado.
    bom = 'regra = "Com preço bom, defenda o BB com um range mais amplo, fora de posição."'
    assert not any(re.search(p, bom, re.IGNORECASE) for p, _, _ in _PROIBIDOS), \
        'acusou o texto CORRETO. Revisor que grita no certo é revisor desligado'
    print('OK  test_o_varredor_ACHA_o_termo_errado')


# ── Travessão: proibido na copy, correto em intervalo numérico ────────────────────────────
#
# `feedback_no_dash_in_text`: a copy do produto não usa travessão. Mas a MEIA-RISCA entre
# números ("SPR 1–3", "~30–35%") é intervalo, e ali o uso é certo — proibir os dois seria o
# revisor gritando no lugar errado.
# O símbolo de moeda entra no lado direito: "Low ($5 – $30)" é intervalo, e sem isto o
# varredor acusava um texto CORRETO — o defeito que mais rápido faz um revisor ser desligado.
_INTERVALO = re.compile(r'(\d\s*)[–—](\s*(?:R\$|US\$|\$|€|£)?\s*\d)')
_TRAVESSAO = re.compile(r'\s+[–—]\s+')


def _copy_do_arquivo(caminho):
    """As strings que viram TEXTO PARA O JOGADOR, via AST.

    Por AST e não por linha, e a razão é uma cicatriz de 21/08: consertando os travessões
    eu apliquei por linha e mudei a docstring do módulo e um comentário inline
    (`# ~4 min — cabe em qualquer dia`). O detector já era AST; a aplicação é que não era.

    Comentário nem entra na árvore, e docstring dá para excluir pela posição — as duas
    fontes de falso positivo somem por construção.
    """
    arvore = ast.parse(open(caminho, encoding='utf-8').read())
    docs = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            corpo = getattr(no, 'body', None) or []
            if corpo and isinstance(corpo[0], ast.Expr) \
                    and isinstance(corpo[0].value, ast.Constant) \
                    and isinstance(corpo[0].value.value, str):
                docs.add((corpo[0].value.lineno, corpo[0].value.col_offset))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str) \
                and (no.lineno, no.col_offset) not in docs:
            yield no.lineno, no.value


def test_copy_nao_usa_travessao():
    violacoes = []
    strings = 0
    for rel in _ARQUIVOS:
        caminho = os.path.join(_BACKEND, rel)
        if not os.path.exists(caminho):
            continue
        for n, txt in _copy_do_arquivo(caminho):
            strings += 1
            sem_intervalo = _INTERVALO.sub(lambda m: m.group(1) + '␟' + m.group(2), txt)
            if _TRAVESSAO.search(sem_intervalo):
                violacoes.append(f'  {rel}:{n}  {" ".join(txt.split())[:88]}')

    assert strings > 300, f'só {strings} strings de copy lidas — o varredor parou de enxergar'
    assert not violacoes, (
        'travessão na copy (use vírgula, ponto ou dois pontos):\n' + '\n'.join(violacoes))
    print(f'OK  test_copy_nao_usa_travessao ({strings} strings)')


def test_copy_do_frontend_nao_usa_travessao():
    """Aqui os TRÊS locales, ao contrário do vocabulário: travessão é regra da marca, não do
    idioma, e uma frase em inglês com travessão fica igualmente fora do padrão."""
    raiz = os.path.dirname(_LOCALES_PT)
    assert os.path.isdir(raiz), f'{raiz} não existe — o varredor não tem o que ler'

    violacoes = []
    strings = 0
    for loc in sorted(os.listdir(raiz)):
        pasta = os.path.join(raiz, loc)
        if not os.path.isdir(pasta):
            continue
        for arq in sorted(os.listdir(pasta)):
            if not arq.endswith('.json'):
                continue
            for chave, txt in _strings_do_json(os.path.join(pasta, arq)):
                strings += 1
                sem_intervalo = _INTERVALO.sub(lambda m: m.group(1) + '␟' + m.group(2), txt)
                if _TRAVESSAO.search(sem_intervalo):
                    violacoes.append(f'  {loc}/{arq}:{chave}  {" ".join(txt.split())[:80]}')

    assert strings > 6000, f'só {strings} strings de tradução lidas — o varredor está cego'
    assert not violacoes, ('travessão na copy do frontend (use vírgula, ponto ou dois pontos):\n'
                           + '\n'.join(violacoes))
    print(f'OK  test_copy_do_frontend_nao_usa_travessao ({strings} strings, 3 locales)')


def test_intervalo_numerico_NAO_e_acusado():
    """Contraprova. "SPR 1–3" e "~30–35%" são intervalos, e a meia-risca ali é correta.
    Sem este caso, a regra acima poderia estar proibindo o certo junto com o errado."""
    for bom in ('SPR 1–3 → top pair+ committed', 'você precisa de ~30–35% de equity',
                'Low ($5 – $30)', 'Mid (R$ 30 – R$ 200)'):
        sem = _INTERVALO.sub(lambda m: m.group(1) + '␟' + m.group(2), bom)
        assert not _TRAVESSAO.search(sem), f'acusou intervalo numérico legítimo: {bom}'

    # E o inverso: travessão de pontuação TEM que ser pego.
    ruim = 'Você já tem par ou melhor — mão feita com showdown value.'
    sem = _INTERVALO.sub(lambda m: m.group(1) + '␟' + m.group(2), ruim)
    assert _TRAVESSAO.search(sem), 'não pegou travessão de pontuação'
    print('OK  test_intervalo_numerico_NAO_e_acusado')


def test_o_varredor_ignora_comentario_e_docstring():
    """O erro que este teste existe para não repetir: em 21/08 apliquei a correção por linha
    e mudei a docstring do módulo e um comentário inline. Aqui se prova que o varredor
    enxerga a copy e NÃO enxerga o texto de desenvolvedor."""
    caminho = os.path.join(_BACKEND, _ARQUIVOS[0])
    textos = [t for _, t in _copy_do_arquivo(caminho)]
    junto = '\n'.join(textos)
    assert 'cabe em qualquer dia' not in junto, 'leu um COMENTÁRIO como se fosse copy'
    assert 'Protocolo de Progressão' not in junto, 'leu a DOCSTRING do módulo como copy'
    assert len(textos) > 100, f'só {len(textos)} strings — o varredor não está lendo o arquivo'
    print(f'OK  test_o_varredor_ignora_comentario_e_docstring ({len(textos)} strings de copy)')


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
