# -*- coding: utf-8 -*-
"""test_condicoes_da_pergunta.py — a tabela de ranges tem que responder a pergunta que foi feita.

**Reportado pelo usuário, com print:** a pergunta era *"qual destas BTN joga de DOIS jeitos a 17bb,
às vezes entrando e às vezes foldando?"*, resposta 86s. Ele abriu a TABELA DE RANGES para conferir,
viu 86s sem fold nenhum, e concluiu que o produto tinha errado.

Conferido no dado antes de mexer em qualquer coisa:

    BTN a 17bb -> 86s na FRONTEIRA, entra 32%   (a pergunta estava certa)
    SB  a 17bb -> 86s no NUCLEO,    entra 100%  (a matriz que abriu)

A tabela abria na posição do SPOT (SB, defendendo vs BTN), não na da PERGUNTA (BTN). **O produto se
fez parecer errado com a própria ferramenta de conferência.**

O guarda principal aqui é `test_toda_pergunta_declara_de_quem_fala`: ele varre TODOS os tipos, não
só o do relato. Um teste que cobrisse só `qual_e_mista` deixaria os outros três livres para repetir
exatamente o mesmo defeito.
"""
import os
import random
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.perguntas_de_range import (gerar, _condicoes, _POSICOES,
                                        p_mao_entra, p_quem_abre_mais,
                                        p_efeito_do_stack, p_qual_e_mista)
from leaklab.leak_trainer import _sondagem_de_range

# Quem tem UMA posição, e portanto DEVE declará-la. `quem_abre_mais` compara duas: declarar uma
# seria apontar para metade das alternativas.
_COM_POSICAO = {'mao_entra', 'efeito_do_stack', 'qual_e_mista', 'largura_do_vilao'}
_SEM_POSICAO = {'quem_abre_mais'}
# Quem tem UMA profundidade. `efeito_do_stack` compara duas.
_COM_STACK = {'mao_entra', 'qual_e_mista', 'largura_do_vilao', 'quem_abre_mais'}


def _colher(n=400):
    """Perguntas de verdade, de todos os tipos, variando posição e stack."""
    saida = []
    for i in range(n):
        rng = random.Random(i)
        q = gerar(rng, pos=rng.choice(_POSICOES), stack=rng.choice([17.0, 25.0, 30.0, 50.0]))
        if q:
            saida.append(q)
    for i in range(40):
        rng = random.Random(1000 + i)
        s = _sondagem_de_range(rng.choice(_POSICOES), rng.choice([17.0, 30.0, 50.0]), rng)
        if s:
            saida.append(s)
    return saida


def test_colheu_todos_os_tipos():
    """Sem isto, os testes abaixo passariam medindo dois tipos e ignorando os outros."""
    tipos = {q['tipo'] for q in _colher()}
    faltam = (_COM_POSICAO | _SEM_POSICAO) - tipos
    assert not faltam, f'a amostra nao produziu: {faltam} (os testes seguintes nao os cobririam)'
    print(f'OK  test_colheu_todos_os_tipos ({len(tipos)} tipos)')


def test_toda_pergunta_declara_de_quem_fala():
    """**O guarda do relato, varrendo TODOS os tipos.** Pergunta com uma posição única precisa
    dizer qual — senão a tela abre a do spot e contradiz a pergunta."""
    mudas = [q['tipo'] for q in _colher()
             if q['tipo'] in _COM_POSICAO and not q.get('posicao')]
    assert not mudas, f'perguntas de posicao unica sem declarar posicao: {sorted(set(mudas))}'
    print('OK  test_toda_pergunta_declara_de_quem_fala')


def test_a_posicao_declarada_e_a_que_o_TEXTO_cita():
    """Declarar a posição errada é pior que não declarar: foi exatamente isso que gerou o relato.
    A conferência é contra o texto que o jogador lê."""
    erradas = []
    for q in _colher():
        p = q.get('posicao')
        if not p:
            continue
        if p not in q['pergunta']:
            erradas.append((q['tipo'], p, q['pergunta']))
    assert not erradas, f'posicao declarada nao aparece no enunciado: {erradas[:3]}'
    print('OK  test_a_posicao_declarada_e_a_que_o_TEXTO_cita')


def test_pergunta_de_DUAS_posicoes_nao_declara_nenhuma():
    """"Quem abre mais, LJ ou BTN?" — abrir a matriz de uma das duas seria apontar para metade
    das alternativas. Silêncio aqui é a resposta certa."""
    vazou = [q for q in _colher() if q['tipo'] in _SEM_POSICAO and q.get('posicao')]
    assert not vazou, f'pergunta comparativa declarou posicao: {vazou[0]["pergunta"]!r}'
    print('OK  test_pergunta_de_DUAS_posicoes_nao_declara_nenhuma')


def test_pergunta_de_DUAS_profundidades_nao_declara_stack():
    """`efeito_do_stack` compara 20bb e 50bb: declarar uma faria a tela mostrar metade da
    pergunta como se fosse o contexto inteiro."""
    vazou = [q for q in _colher()
             if q['tipo'] == 'efeito_do_stack' and q.get('stack') is not None]
    assert not vazou, f'pergunta de duas profundidades declarou stack: {vazou[0]}'
    # e ela ainda declara a POSICAO, que e unica
    tem_pos = [q for q in _colher() if q['tipo'] == 'efeito_do_stack']
    assert tem_pos and all(q.get('posicao') for q in tem_pos), \
        'efeito_do_stack tem posicao unica e deveria declara-la'
    print('OK  test_pergunta_de_DUAS_profundidades_nao_declara_stack')


def test_o_stack_declarado_bate_com_o_do_enunciado():
    fora = []
    for q in _colher():
        s = q.get('stack')
        if s is None:
            continue
        if f'{int(s)}bb' not in q['pergunta'] and q['tipo'] != 'largura_do_vilao':
            fora.append((q['tipo'], s, q['pergunta']))
    assert not fora, f'stack declarado nao bate com o enunciado: {fora[:3]}'
    print('OK  test_o_stack_declarado_bate_com_o_do_enunciado')


def test_o_caso_exato_do_relato():
    """BTN a 17bb com 86s na fronteira: a pergunta tem que declarar BTN, nao a posicao do spot."""
    achou = False
    for i in range(600):
        rng = random.Random(i)
        q = p_qual_e_mista(rng, 'BTN', 17.0)
        if not q:
            continue
        achou = True
        assert q.get('posicao') == 'BTN', f'declarou {q.get("posicao")!r} numa pergunta sobre BTN'
        assert q.get('stack') == 17.0, f'declarou stack {q.get("stack")!r}'
        break
    assert achou, 'nao consegui gerar a pergunta do relato — o teste nao mediu nada'
    print('OK  test_o_caso_exato_do_relato')


def test_condicoes_omite_o_que_nao_sabe():
    """A função que centraliza a regra. Chave ausente = a tela mantém o que já usava; chave com
    valor errado = a tela mostra algo que contradiz a pergunta."""
    assert _condicoes(None, None) == {}
    assert _condicoes('BTN', None) == {'posicao': 'BTN'}
    assert _condicoes(None, 17.0) == {'stack': 17.0}
    assert _condicoes('BTN', 17) == {'posicao': 'BTN', 'stack': 17.0}
    assert _condicoes('', 17.0) == {'stack': 17.0}, 'posicao vazia nao pode virar posicao'
    print('OK  test_condicoes_omite_o_que_nao_sabe')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
    raise SystemExit(1 if fail else 0)
