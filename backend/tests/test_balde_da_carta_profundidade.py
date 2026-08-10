# -*- coding: utf-8 -*-
"""A carta de 10bb nao fala por quem tem 0,2bb.

── O defeito ──────────────────────────────────────────────────────────────────────────────────

`villain_open_range` e `villain_reraise_range` escolhiam o bloco de ranges com
`_load()['ranges'][_stack_bucket(stack_bb)]`, cru. E `_stack_bucket` PARTICIONA a reta: o balde
mais raso e `[0, 12)` e o mais fundo `[87.5, 9999)`. Nas duas pontas ele **satura em silencio** —
um jogador de 0,2bb recebia a carta de 10bb, um de 195bb recebia a de 100bb, e nada no retorno
dizia que a carta era de outra profundidade.

Essas duas funcoes alimentam o `villain_range` do `pipeline`, que decide se a equity do produto e
medida contra a RANGE do vilao ou contra MAO ALEATORIA. Range da profundidade errada e o caso que
o proprio codigo ja tinha nomeado em outro lugar: **pior que aleatoria, porque parece precisa.**

── O conserto ─────────────────────────────────────────────────────────────────────────────────

A regra ja existia, escrita a mao dentro de `_hu_no_mais_proximo`: janela RELATIVA de 25%. Virou
`_profundidade_compativel`, e agora os TRES caminhos passam por ela — o no HU, a range de open e a
range de re-raise. `_balde_da_carta` e o seletor de balde que a consome.

Quem nao passa cai no vs-random, que e exatamente o que esses spots tinham antes de existir range
nenhuma: nao e perda de veredito, e parar de fingir precisao.

── Medido no acervo (18 torneios, 2.366 decisoes), A/B com a mesma reconstrucao ────────────────

    perderam a range   67   (57 com stack < 7,5bb, 10 com stack > 133bb)
    label mudou         0
    acusacoes         141 -> 141
    bestAction mudou    2   (BB a 5,7bb e 6,7bb, fold -> call; label seguiu `standard`)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import (      # noqa: E402
    _DEFAULT_BUCKETS, _balde_da_carta, _hu_no_mais_proximo, _profundidade_compativel,
    _stack_bucket, villain_open_range, villain_reraise_range,
)

# Fronteiras que a janela de 25% impoe sobre os baldes extremos: 10/1.25 = 8 nao, porque a conta e
# `|d-s| / max(d,s)` — a 7,5bb da exatamente 0,25, e a 133,33bb tambem. Sao os dois unicos cortes.
_PISO = 7.5
_TETO = 400.0 / 3.0


def test_a_regra_e_relativa_e_vale_nos_dois_sentidos():
    """5bb de distancia a 10bb e outra estrategia; 5bb a 100bb e ruido. Se a janela fosse
    ABSOLUTA os dois casos seriam iguais, que era o erro que a versao relativa existe pra evitar."""
    assert _profundidade_compativel(10, 10) is True
    assert _profundidade_compativel(10, 7.5) is True        # exatamente na borda: cabe
    assert _profundidade_compativel(10, 7.49) is False
    assert _profundidade_compativel(100, 95) is True        # mesma distancia absoluta, outro regime
    assert _profundidade_compativel(100, 134) is False
    # degenerados nao explodem nem passam calados
    assert _profundidade_compativel(10, 0) is False
    assert _profundidade_compativel(0, 10) is False
    assert _profundidade_compativel(0, 0) is False


def test_o_balde_so_e_recusado_nas_duas_pontas_que_saturam():
    """Controle do conserto: os baldes do MEIO tem fronteiras dentro da janela, entao nenhum deles
    pode perder cobertura. Se este teste falhar, o guarda esta cortando quem nao devia."""
    for label, lo, hi in _DEFAULT_BUCKETS:
        for s in (lo + 1e-6, (lo + min(hi, 250.0)) / 2, min(hi, 250.0) - 1e-6):
            esperado = None if (s < _PISO or s > _TETO) else _stack_bucket(s)
            assert _balde_da_carta(s) == esperado, (
                f'balde {label} em {s:.4f}bb: esperava {esperado}, veio {_balde_da_carta(s)}')


def test_range_de_open_some_no_stack_raso_e_no_profundo_e_fica_no_meio():
    """O caso do relatorio (0,2bb) e o simetrico dele (195bb). Com o controle no meio, porque um
    guarda que zera TUDO tambem passaria nas duas primeiras assercoes."""
    assert villain_open_range('BTN', 0.2, 9) == {}
    assert villain_open_range('BTN', 5.0, 9) == {}
    assert villain_open_range('BTN', 195.0, 9) == {}
    for s in (7.6, 10.0, 30.0, 100.0, 133.0):
        assert villain_open_range('BTN', s, 9), f'perdeu a range de open a {s}bb'


def test_range_de_reraise_segue_o_mesmo_seletor():
    """Nao adianta consertar so uma das duas: as duas alimentam o mesmo `villain_range`."""
    assert villain_reraise_range('BB', 'BTN', 0.2, 9) == {}
    assert villain_reraise_range('BB', 'BTN', 195.0, 9) == {}
    for s in (7.6, 10.0, 30.0, 100.0, 133.0):
        assert villain_reraise_range('BB', 'BTN', s, 9), f'perdeu a range de 3-bet a {s}bb'


def test_o_caminho_hu_continua_recusando_a_profundidade_vizinha():
    """A extracao nao pode ter afrouxado a origem da regra. O caso e o do comentario dela: SB a
    14,8bb NAO pode ser gradeado pelo no de 10bb (a 10bb o SB e jam/limp; a 15bb ha raise normal).
    Funcao pura, entao da pra amostrar direto."""
    nos = {10.0: {'x': 1}, 25.0: {'x': 2}}
    assert _hu_no_mais_proximo(nos, 14.8) == (None, None)
    assert _hu_no_mais_proximo(nos, 10.0)[0] == 10.0
    assert _hu_no_mais_proximo({}, 10.0) == (None, None)
    # A escolha do no continua RELATIVA, nao absoluta — e aqui os dois criterios discordam de um
    # jeito visivel no retorno: a 20bb o absoluto escolheria 15,5 (dist 4,5 < 5) e o relativo
    # escolhe 25 (0,200 < 0,225). Os dois passariam na janela, entao o que este caso distingue e o
    # CRITERIO, nao a aprovacao.
    assert _hu_no_mais_proximo({15.5: {'x': 1}, 25.0: {'x': 2}}, 20.0)[0] == 25.0


def test_uma_regra_um_lugar():
    """CLAUDE.md #5: regra aplicada em N lugares vira funcao. Se alguem reintroduzir a janela na
    mao em vez de chamar `_profundidade_compativel`, esta varredura acusa."""
    import inspect

    from leaklab import preflop_gto_ranges as mod

    fonte = inspect.getsource(mod)
    n = fonte.count('0.25')
    assert n == 1, (
        f'a janela de 25% aparece {n}x no modulo (esperado: 1). Ela mora em '
        '`_profundidade_compativel`; os consumidores chamam a funcao, nao recopiam o numero — '
        'e se o numero mudou, mude tambem este teste, de proposito')
    for nome in ('villain_open_range', 'villain_reraise_range'):
        corpo = inspect.getsource(getattr(mod, nome))
        assert '_balde_da_carta' in corpo, f'{nome} nao passa pelo seletor unico'
        assert '_stack_bucket' not in corpo, f'{nome} voltou ao lookup cru de balde'


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
