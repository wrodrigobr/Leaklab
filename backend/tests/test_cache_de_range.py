# -*- coding: utf-8 -*-
"""`_expand_range` e cacheada, e isso so e seguro porque ela e PURA (08/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

O dono perguntou por que a suite demorava 38 minutos. Medindo arquivo a arquivo, metade do
tempo estava em 8 de 286, e o pior (`test_condicoes_da_pergunta`) levava 8,7 min sozinho. O
perfil mostrou onde: 367 mil chamadas a `_expand_range` e **21 milhoes** a
`expand_range_notation` por dentro dela, 358s dos 527s do arquivo.

Nao era custo de teste. O caminho e `analyze_preflop` -> `_in_range` -> `_expand_range`, que
roda por decisao preflop em TODO import: o cache acelera a importacao do jogador tambem. Depois
dele, o arquivo caiu de 521s para 47s.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

O cache so pode existir enquanto a funcao for pura e o resultado for imutavel. Se alguem
devolver `set` de novo, um chamador podera mutar o objeto COMPARTILHADO e corromper todos os
outros — em silencio. Aqui isso e travado: o retorno e `frozenset`, o resultado bate com o
calculo do zero, e a mesma notacao devolve a MESMA instancia.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import _expand_range, _in_range          # noqa: E402
from leaklab.gto_utils import expand_range_notation                      # noqa: E402

NOTACOES = ('TT+,ATs+', 'AA', '22+', 'ATo+', 'ATs-AJs', 'KTs+,QJs', '', 'N/A', 'AKs,AKo')


def _do_zero(notation):
    """Recalcula sem passar pelo cache — a mesma regra, escrita aqui de proposito para o teste
    nao virar 'o cache concorda com o cache'."""
    if not notation or 'N/A' in notation.upper():
        return frozenset()
    fora = set()
    for parte in notation.split(','):
        parte = parte.strip()
        if not parte:
            continue
        for h in expand_range_notation(parte):
            if len(h) == 2:
                fora.add(h)
            elif len(h) >= 3 and h[-1] not in ('s', 'o'):
                fora.add(h + 's'); fora.add(h + 'o')
            else:
                fora.add(h)
    return frozenset(fora)


def test_o_resultado_cacheado_bate_com_o_calculo_do_zero():
    for n in NOTACOES:
        assert _expand_range(n) == _do_zero(n), n


def test_o_retorno_e_imutavel_e_a_instancia_e_reaproveitada():
    a = _expand_range('TT+,ATs+')
    assert isinstance(a, frozenset), type(a).__name__
    assert _expand_range('TT+,ATs+') is a, 'a mesma notacao tem de reusar a instancia (cache)'
    # e ninguem consegue corromper o objeto compartilhado
    try:
        a.add('72o')                                        # type: ignore[attr-defined]
        assert False, 'o retorno tem de ser imutavel: com set, mutar aqui envenenaria o cache'
    except AttributeError:
        pass


def test_notacoes_diferentes_nao_se_misturam():
    assert _expand_range('AA') != _expand_range('KK')
    assert 'AA' in _expand_range('TT+') and 'AA' not in _expand_range('TT-JJ')
    assert _expand_range('') == frozenset() and _expand_range('N/A') == frozenset()
    assert _in_range('AKs', 'ATs+') and not _in_range('72o', 'ATs+')


def test_o_cache_nao_muda_o_veredito_de_uma_decisao_preflop():
    """A porta que interessa: o produto usa isto por `analyze_preflop`. Duas chamadas seguidas
    para a MESMA mao tem de dar o mesmo resultado (e uma diferente, resultado diferente)."""
    from leaklab.preflop_gto_ranges import analyze_preflop
    a1 = analyze_preflop('AKs', 'BTN', 40, 'rfi')
    a2 = analyze_preflop('AKs', 'BTN', 40, 'rfi')
    lixo = analyze_preflop('72o', 'UTG', 40, 'rfi')
    assert a1 == a2, (a1, a2)
    assert a1 != lixo, 'AKs no BTN e 72o no UTG nao podem devolver a mesma coisa'


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
