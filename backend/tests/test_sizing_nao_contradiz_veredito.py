# -*- coding: utf-8 -*-
"""Conselho de tamanho nao contradiz o veredito.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Print de producao: o mesmo card dizia **"GTO RECOMENDA: SHOVE"** no topo e **"suba pra 3bb"** na
linha de sizing. Duas recomendacoes diferentes na mesma tela — a terceira contradicao interna de
card achada no mesmo dia, depois do selo `−EV` e da frase que descrevia a mao.

── A causa: proxy no lugar do dado ────────────────────────────────────────────────────────────

O guarda existia e usava `_eff_stack > 12` como aproximacao de "zona de jam-or-fold", com o
comentario certo ("abra 2-2,5bb ali e conselho de deep stack"). Mas 12bb e uma FRONTEIRA
INVENTADA: naquela mao o efetivo era 17bb — passa no guarda — e a carta mandava all-in mesmo
assim, porque a arvore de heads-up a 17bb ja e jam-dominante.

O sinal certo estava a duas linhas de distancia: `reconciled_best`, a recomendacao que o proprio
card exibe. **Se a jogada e all-in, nao existe conselho de tamanho a dar** — o tamanho e forcado.
Perguntar ao sistema em vez de aproximar por profundidade, mais uma vez.

── O guarda ───────────────────────────────────────────────────────────────────────────────────

Varredura sobre o codigo-fonte: a condicao que decide emitir sizing PRECISA olhar a recomendacao.
Um teste de unidade exigiria montar torneio, request e banco; o que se garante barato — e e disso
que o defeito era feito — e que a condicao nao volte a depender so da profundidade.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_APP = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')


def _bloco_do_sizing() -> str:
    """O `if` que decide emitir o conselho de tamanho do open."""
    src = io.open(_APP, encoding='utf-8').read()
    i = src.index('sizing_advice = None')
    j = src.index('analyze_open_sizing', i)
    return src[i:j]


def test_a_varredura_acha_o_bloco():
    """Controle: se o trecho mudar de forma, os testes abaixo passariam por vacuidade."""
    bloco = _bloco_do_sizing()
    assert 'preflopRaisesFaced' in bloco and '_eff_stack' in bloco, bloco[:200]


def test_o_sizing_olha_a_RECOMENDACAO_e_nao_so_a_profundidade():
    bloco = _bloco_do_sizing()
    corpo = '\n'.join(l for l in bloco.splitlines() if not l.lstrip().startswith('#'))
    assert 'reconciled_best' in corpo, (
        'o conselho de tamanho voltou a depender so da profundidade — com jam recomendado, '
        'o card exibe duas recomendacoes diferentes')
    assert re.search(r'not\s+_rec_e_jam', corpo), corpo[-400:]


def test_a_lista_de_jam_cobre_os_apelidos_do_sistema():
    """`jam`, `shove`, `allin` e `all-in` circulam todos no codigo — cobrir so um deixaria o
    defeito vivo pela metade, que e pior que nao cobrir (parece consertado)."""
    src = io.open(_APP, encoding='utf-8').read()
    i = src.index('_rec_e_jam')
    trecho = src[i - 200:i + 200]
    for apelido in ('jam', 'shove', 'allin', 'all-in'):
        assert f"'{apelido}'" in trecho, f'falta {apelido!r} na lista de all-in'


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
