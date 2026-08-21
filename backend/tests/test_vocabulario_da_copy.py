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
