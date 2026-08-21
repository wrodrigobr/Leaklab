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
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Arquivos que produzem copy DIDÁTICA lida pelo jogador (não log, não comentário de código).
_ARQUIVOS = [
    os.path.join('leaklab', 'progression.py'),
    os.path.join('leaklab', 'academy.py'),
]

# (padrão proibido, o que usar, por quê)
_PROIBIDOS = [
    (r'sem\s+posi[çc][ãa]o', 'fora de posição',
     'o termo consagrado é "fora de posição" (OOP); "sem posição" não é usado em português '
     'de poker, e os MESMOS arquivos já usam o certo em outros trechos'),
]


def _linhas_de_texto(caminho):
    """Só as linhas que carregam texto para o jogador — strings com espaço e acento.

    Comentário de código fica de fora: `repositories.py` tem 'o cenário, sem posição nem
    profundidade' num docstring técnico, e ali o sentido é literalmente 'sem o campo
    posição'. Acusar isso seria o revisor gritando onde não há problema.
    """
    for n, linha in enumerate(open(caminho, encoding='utf-8'), start=1):
        cru = linha.strip()
        if cru.startswith('#'):
            continue
        # precisa ter aspas (é string) e ao menos um espaço (é frase, não identificador)
        if ('"' in cru or "'" in cru) and ' ' in cru:
            yield n, cru


def test_copy_nao_usa_termo_fora_do_vocabulario():
    violacoes = []
    varridas = 0
    for rel in _ARQUIVOS:
        caminho = os.path.join(_BACKEND, rel)
        if not os.path.exists(caminho):
            continue
        for n, linha in _linhas_de_texto(caminho):
            varridas += 1
            for padrao, certo, porque in _PROIBIDOS:
                if re.search(padrao, linha, re.IGNORECASE):
                    violacoes.append(f'  {rel}:{n} → use "{certo}". {porque}\n    {linha[:90]}')

    assert varridas > 100, (
        f'só {varridas} linhas de texto varridas — o filtro parou de casar, e um teste que '
        'não lê nada passa sempre')
    assert not violacoes, 'vocabulário fora do padrão na copy:\n' + '\n'.join(violacoes)
    print(f'OK  test_copy_nao_usa_termo_fora_do_vocabulario ({varridas} linhas)')


def test_o_varredor_ACHA_o_termo_errado():
    """Prova de detecção (regra 1). Sem isto, o teste acima poderia estar passando porque
    parou de ler os arquivos — e um zero tranquilizador aqui deixaria a copy solta."""
    forjado = 'regra = "Defenda o BB largo e aperte quando for jogar sem posição."'
    achou = any(re.search(p, forjado, re.IGNORECASE) for p, _, _ in _PROIBIDOS)
    assert achou, 'o varredor não acha o termo na frase EXATA que originou este teste'

    # E o contrário: o texto correto não pode ser acusado.
    bom = 'regra = "Com preço bom, defenda o BB com um range mais amplo — fora de posição."'
    assert not any(re.search(p, bom, re.IGNORECASE) for p, _, _ in _PROIBIDOS), \
        'acusou o texto CORRETO — revisor que grita no certo é revisor desligado'
    print('OK  test_o_varredor_ACHA_o_termo_errado')


# ── Travessão: proibido na copy, correto em intervalo numérico ────────────────────────────
#
# `feedback_no_dash_in_text`: a copy do produto não usa travessão. Mas a MEIA-RISCA entre
# números ("SPR 1–3", "~30–35%") é intervalo, e ali o uso é certo — proibir os dois seria o
# revisor gritando no lugar errado.
_INTERVALO = re.compile(r'(\d\s*)[–—](\s*\d)')
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


def test_intervalo_numerico_NAO_e_acusado():
    """Contraprova. "SPR 1–3" e "~30–35%" são intervalos, e a meia-risca ali é correta.
    Sem este caso, a regra acima poderia estar proibindo o certo junto com o errado."""
    for bom in ('SPR 1–3 → top pair+ committed', 'você precisa de ~30–35% de equity'):
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
