# -*- coding: utf-8 -*-
"""`range_pct` sai na MESMA unidade por todos os caminhos.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

O card exibiu **"33 está no range hu_rfi (9880%) @ 17bb"**. O caminho HU devolvia `range_pct` em
PORCENTAGEM (98.8) e todo o resto do sistema em FRAÇÃO (0.86); os consumidores — o front e o
`llm_explainer` — multiplicam por 100 para exibir. Resultado: 98,8 × 100.

E o mesmo defeito de unidade que ja custou caro neste projeto em fichas × bb, agora em fracao ×
porcentagem.

── Por que demorou a aparecer ─────────────────────────────────────────────────────────────────

Enquanto o numero so alimentava a LARGURA de uma barra, o erro era invisivel: `width: 9880%` satura
em 100% e a barra ficava cheia — plausivel para um range de 98,8%. Ele so virou visivel no dia em
que a explicacao textual passou a ser exibida no card.

**Numero que so alimenta pixel nao e numero verificado.**

── O guarda ───────────────────────────────────────────────────────────────────────────────────

Comparar os DOIS produtores exigindo a mesma faixa. Um teste que olhasse so um caminho passaria
com o bug presente — foi exatamente essa a situacao durante meses.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import analyze_preflop


def _hu():
    return analyze_preflop(position='SB', hero_hand_type='33', stack_bb=17.0,
                           action_taken='raise', n_players=2, hero_was_aggressor=False,
                           facing_raises=0, facing_size=0.0, facing_to_bb=0.0)


def _ring():
    return analyze_preflop(position='BB', hero_hand_type='JJ', stack_bb=20.0,
                           action_taken='call', facing_size=2.0, vs_position='CO',
                           facing_raises=1, hero_was_aggressor=False, facing_to_bb=2.0,
                           n_players=8)


def test_os_dois_caminhos_devolvem_FRACAO():
    """0..1 em ambos. Se um voltar a 0..100, o card imprime 9880%."""
    for nome, r in (('HU', _hu()), ('ring', _ring())):
        assert r.get('available') is True, f'{nome}: o teste precisa de um spot COBERTO'
        pct = r.get('range_pct')
        assert pct is not None, nome
        assert 0.0 <= pct <= 1.0, f'{nome}: range_pct={pct} fora de 0..1 (voltou a porcentagem?)'


def test_o_numero_continua_significando_a_MESMA_coisa():
    """Controle de sentido, nao so de faixa: dividir por 100 sem querer tambem cairia em 0..1 e
    passaria no teste acima. O SB abrindo heads-up a 17bb joga a quase totalidade das maos."""
    pct = _hu()['range_pct']
    assert 0.90 <= pct <= 1.0, f'SB heads-up a 17bb deveria continuar com quase tudo: {pct}'
    # e o ring, num spot de defesa, fica bem abaixo disso
    assert _ring()['range_pct'] < 0.95


def test_exibicao_nao_estoura_100():
    """O que o usuario ve. Multiplicar por 100 (o que front e llm_explainer fazem) tem que dar
    um numero de porcentagem plausivel."""
    for nome, r in (('HU', _hu()), ('ring', _ring())):
        exibido = (r['range_pct'] or 0) * 100
        assert 0 <= exibido <= 100, f'{nome}: o card exibiria {exibido:.0f}%'


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
