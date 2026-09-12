# -*- coding: utf-8 -*-
"""Secao da carta que existe no acervo tem de chegar a TELA, ou ser declarada (12/09).

── O caso ─────────────────────────────────────────────────────────────────────────────────

`docs/leaklab_gto_ranges.json` tem SEIS secoes (`RFI`, `vs_RFI`, `vs_3bet`, `vs_4bet`,
`squeeze`, `faces_squeeze`). O endpoint `/preflop-ranges` servia QUATRO desde que a pagina
`/ranges` nasceu, em 28/08. As **2.520 celulas de `vs_4bet`** — 36 pares fechados em 30, 40, 50,
75 e 100bb, com as maos por acao — estavam no acervo e **nao chegavam a tela**.

Ninguem viu por semanas, e a razao e instrutiva: o defeito estava DOCUMENTADO. O comentario no
topo de `Ranges.tsx` dizia "«vs_4bet» e «faces_squeeze» existem na carta e o endpoint nao os
serve". Comentario nao conserta e nao avisa: ele registra e descansa. Regra 8, de novo, na
direcao menos obvia — nao "comentario nao e evidencia", mas "comentario nao e defesa".

── O que este arquivo defende ─────────────────────────────────────────────────────────────

Le as secoes que EXISTEM no master e exige que cada uma seja servida pelo endpoint, ou apareca em
`_NAO_SERVIDAS` com motivo escrito. Lista de excecao sem motivo e o problema de volta (mesma
politica do `FORA_DA_SUITE` do runner).

`faces_squeeze` esta declarada, e o motivo e honesto: **a semantica dos pares nao fechou.** Em
`faces_squeeze[BB][BTN]` o hero seria o BB enfrentando um squeeze, e ninguem age depois do BB. As
12 maos nao-fold a 30bb (AA, KK, QQ, JJ, AKs, AKo, AQs, KQs, 77, 66, 55, A5s) estao todas contidas
no que o BB joga contra o open do BTN, o que e compativel com mais de uma leitura. Servir grade
cujo PAPEL de cada posicao nao foi estabelecido rotula a tela errado — e esta casa ja gravou
solve no papel errado por supor o significado de um indice.
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))
from leitura_de_fonte import sem_comentarios                                          # noqa: E402

_BACK = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_CARTA = os.path.join(_BACK, 'docs', 'leaklab_gto_ranges.json')
_APP = os.path.join(_BACK, 'api', 'app.py')

#: Secao que existe no master e NAO e servida, com o motivo. Sem motivo, o guarda reprova.
_NAO_SERVIDAS = {
    'faces_squeeze': 'a semantica dos pares nao fechou na medicao de 12/09: em '
                     '`faces_squeeze[BB][BTN]` o hero seria o BB enfrentando squeeze, e ninguem '
                     'age depois do BB. Servir grade com o papel das posicoes indefinido rotula '
                     'a tela errado. Ver o item no BACKLOG com o que falsifica cada hipotese.',
}


def _secoes_do_master():
    if not os.path.exists(_CARTA):
        return None
    d = json.load(io.open(_CARTA, encoding='utf-8'))
    secoes = set()
    for balde, conteudo in (d.get('ranges') or {}).items():
        for sec in conteudo:
            if not sec.startswith('_'):
                secoes.add(sec)
    return secoes


def _corpo_do_endpoint():
    src = io.open(_APP, encoding='utf-8').read()
    i = src.index("@app.route('/preflop-ranges'")
    j = src.index("@app.route('/gto/strategy'", i)
    trecho = src[i:j]
    # SEM COMENTARIOS, mas COM strings: o comentario do endpoint CITA as secoes que faltam para
    # explicar a cicatriz (sem filtrar, o guarda daria as ausentes por servidas — verde pelo
    # texto que denuncia o buraco), e os nomes das secoes vivem em STRING no codigo
    # (`_section_for_pos('vs_4bet')`). Usar `so_codigo` aqui apagaria as duas coisas e o guarda
    # acusou que nem o `RFI` chegava a tela. Ver a docstring de `sem_comentarios`.
    return chr(10).join(sem_comentarios(trecho).values())


def test_toda_secao_do_master_e_servida_ou_declarada():
    secoes = _secoes_do_master()
    if secoes is None:
        print('SKIP  a carta nao esta no disco')
        return
    assert len(secoes) >= 5, ('o master tem menos secoes que o esperado: a varredura nao esta '
                              'vendo o arquivo certo', sorted(secoes))
    codigo = _corpo_do_endpoint()
    faltando = []
    for sec in sorted(secoes):
        if sec in _NAO_SERVIDAS:
            continue
        if ("'%s'" % sec) not in codigo and ('"%s"' % sec) not in codigo:
            faltando.append(sec)
    assert not faltando, (
        'secao existe na carta e NAO chega a tela (nem esta declarada com motivo): %s'
        % ', '.join(faltando))


def test_a_lista_de_excecao_tem_MOTIVO_e_so_secoes_reais():
    for sec, motivo in _NAO_SERVIDAS.items():
        assert len(motivo) > 60, ('excecao sem motivo escrito vira lista de exclusao silenciosa',
                                  sec)
        secoes = _secoes_do_master()
        if secoes is not None:
            assert sec in secoes, ('declarada como nao servida uma secao que nem existe na '
                                   'carta: a lista envelheceu', sec)


def test_vs_4bet_chega_ao_payload():
    """O caso concreto: era a secao maior fora da tela, 2.520 celulas."""
    codigo = _corpo_do_endpoint()
    assert "'vs_4bet':" in codigo, 'o `vs_4bet` saiu do payload do endpoint'
    assert "_section_for_pos('vs_4bet')" in codigo, (
        'o `vs_4bet` aparece no payload mas nao e LIDO da carta: chave servindo None')


def test_o_guarda_le_CODIGO_e_nao_o_comentario_que_denuncia_o_buraco():
    """CONTROLE. O comentario do endpoint cita `faces_squeeze` e `vs_4bet` para explicar a
    cicatriz. Se o guarda lesse texto, daria as duas por servidas — ficaria verde exatamente
    pelo texto que documenta o problema, que foi como o buraco sobreviveu semanas."""
    src = io.open(_APP, encoding='utf-8').read()
    i = src.index("@app.route('/preflop-ranges'")
    j = src.index("@app.route('/gto/strategy'", i)
    bruto = src[i:j]
    codigo = _corpo_do_endpoint()
    assert 'faces_squeeze' in bruto, 'o comentario que explica a decisao desapareceu'
    assert 'faces_squeeze' not in codigo, (
        'o guarda esta lendo comentario: `faces_squeeze` aparece so em texto e vazou para o '
        'codigo filtrado')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
