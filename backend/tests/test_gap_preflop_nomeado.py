# -*- coding: utf-8 -*-
"""O null preflop tem que dizer POR QUE, e nomear nao pode mexer em veredito.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Depois do reprocesso de 05/08 sobraram 284 decisoes preflop sem `gto_label`. Elas voltavam do
provider com `available=False` e `coverage_reason=None` — um null MUDO, que nao distingue
"o no nao existe em arvore nenhuma" de "o no existe e nos e que nao temos".

A separacao importa porque as duas pedem coisas opostas: a primeira nao tem conserto (e o gap se
fecha aceitando-o), a segunda se fecha reabastecendo a base.

Medido no acervo de producao, das 284:
  89   hero LIMPOU e levou raise de quem age depois dele  (o par mais comum: SB limp + BB iso, 29)
  148  par [hero][vilao] sem cobertura em faces_squeeze / vs_4bet
  46   BB sem opener detectado
  38   dessas 284 estao ACUSADAS de erro sem gabarito nenhum

── Por que `limp_then_raise` e estrutural ─────────────────────────────────────────────────────

Se o vilao age DEPOIS do hero e mesmo assim o hero esta pagando um raise dele, so ha um caminho:
hero limpou. Foldado estaria fora da mao; aberto viraria `vs_3bet`. Nossas arvores sao
raise-first e o GTO nao open-limpa de posicao nao-blind, entao esse no nao existe para capturar.

── O guarda que mais importa ──────────────────────────────────────────────────────────────────

`test_nomear_nao_muda_veredito`: `coverage_reason` so pode aparecer com `available=False`. Uma
anotacao que mudasse grade seria a pior versao deste conserto — trocaria resposta onde antes so
faltava explicacao, que e o oposto do que a regra 7 do CLAUDE.md manda.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import analyze_preflop, _age_depois


def _spot(pos, vs, mao='KQo', eff=25.0, facing=2.5, raises=1, acao='call'):
    return analyze_preflop(position=pos, hero_hand_type=mao, stack_bb=eff, action_taken=acao,
                           facing_size=facing, vs_position=vs, is_3bet_pot=False,
                           facing_raises=raises, hero_was_aggressor=False, facing_to_bb=facing)


def test_age_depois_reconhece_o_par_impossivel():
    """A tabela verdade da funcao — incluindo os blinds, que agem por ULTIMO preflop."""
    assert _age_depois('UTG+1', 'HJ') is True      # hero cedo, "opener" tardio => limpou
    assert _age_depois('SB', 'BB') is True         # SB completa, BB iso-raisa
    assert _age_depois('CO', 'SB') is True
    assert _age_depois('HJ', 'UTG+1') is False     # open normal: opener age antes
    assert _age_depois('BB', 'SB') is False        # SB abre, BB defende — no legitimo
    assert _age_depois('BTN', 'UTG') is False
    assert _age_depois('CO', 'CO') is False        # mesma posicao nao e "depois"


def test_posicao_desconhecida_nao_classifica():
    """Na duvida nao rotula: rotulo errado e pior que rotulo ausente."""
    assert _age_depois('UTG', 'UNKNOWN') is False
    assert _age_depois('', 'BB') is False
    assert _age_depois('LUGAR-NENHUM', 'BTN') is False


def test_limp_seguido_de_raise_e_nomeado():
    """Os tres casos reais de producao que motivaram isto (t41, t42, t91)."""
    for pos, vs, mao, eff, facing in (('UTG+1', 'HJ', '97s', 46.3, 3.0),
                                      ('MP1', 'BTN', 'KJo', 18.9, 2.0),
                                      ('CO', 'SB', 'K8s', 3.0, 4.0)):
        r = _spot(pos, vs, mao, eff, facing)
        assert r.get('available') is False, f'{pos} vs {vs} nao deveria ter gabarito'
        assert r.get('coverage_reason') == 'limp_then_raise', (
            f'{pos} vs {vs}: null mudo, motivo={r.get("coverage_reason")!r}')


def test_par_sem_cobertura_e_nomeado_e_nao_se_confunde_com_o_estrutural():
    """faces_squeeze [SB][BB]: o no EXISTE (open, SB paga, BB squeeza) — falta na nossa base."""
    r = analyze_preflop(position='SB', hero_hand_type='A5s', stack_bb=18.2, action_taken='call',
                        facing_size=2.8, vs_position='BB', is_3bet_pot=False, facing_raises=2,
                        hero_was_aggressor=False, facing_to_bb=2.8)
    assert r.get('available') is False
    # SB age antes do BB, entao o estrutural tem precedencia — e ele e mesmo o motivo aqui:
    # para o SB seguir na mao com DOIS raises atras, ele pagou o primeiro.
    assert r.get('coverage_reason') in ('limp_then_raise', 'pairing_uncovered')

    # Um par sem cobertura SEM a marca estrutural: hero BTN, squeezer HJ (age antes do BTN).
    r2 = analyze_preflop(position='BTN', hero_hand_type='QJs', stack_bb=25.0, action_taken='call',
                         facing_size=8.0, vs_position='HJ', is_3bet_pot=False, facing_raises=2,
                         hero_was_aggressor=False, facing_to_bb=8.0)
    if not r2.get('available'):
        assert r2.get('coverage_reason') == 'pairing_uncovered', (
            f'par sem cobertura voltou mudo: {r2.get("coverage_reason")!r}')


def test_nomear_nao_muda_veredito():
    """O invariante. `coverage_reason` e explicacao de AUSENCIA — nunca acompanha um gabarito.

    Se um spot coberto passasse a carregar motivo de lacuna, seria sinal de que a anotacao
    vazou para o caminho que grada, e a proxima coisa a vazar seria o veredito.
    """
    MATRIZ = [
        ('HJ', 'UTG+1', 'AQs', 25.0, 2.5, 1, 'call'),    # vs_rfi legitimo
        ('BB', 'SB',    'KTo', 20.0, 3.0, 1, 'call'),    # SB abre, BB defende
        ('BTN', 'CO',   'AA',  50.0, 2.3, 1, 'raise'),
        ('CO', 'UTG',   '77',  30.0, 2.2, 1, 'fold'),
        ('UTG', '',     'AKo', 40.0, 0.0, 0, 'raise'),   # RFI
        ('SB', 'BB',    '97s', 18.0, 2.8, 2, 'call'),    # o estrutural
        ('UTG+1', 'HJ', 'T9s', 46.0, 3.0, 1, 'call'),    # o estrutural
    ]
    vistos = 0
    for pos, vs, mao, eff, fac, raises, acao in MATRIZ:
        r = _spot(pos, vs, mao, eff, fac, raises, acao)
        if r.get('coverage_reason'):
            vistos += 1
            assert r.get('available') is False, (
                f'{pos} vs {vs} tem gabarito E motivo de lacuna ({r["coverage_reason"]}) — '
                f'a anotacao vazou para o caminho que grada')
            assert r.get('action_quality') == 'unknown', (
                f'{pos} vs {vs}: lacuna nomeada mas com veredito {r["action_quality"]!r}')
    assert vistos >= 2, 'a matriz precisa exercitar pelo menos dois spots sem cobertura'


def test_spots_cobertos_seguem_com_gabarito():
    """Controle negativo: se isto cair junto com os outros, o conserto quebrou a cobertura."""
    r = _spot('HJ', 'UTG+1', 'AQs', 25.0, 2.5)
    assert r.get('available') is True, 'HJ defendendo open de UTG+1 perdeu o gabarito'
    assert r.get('coverage_reason') is None
    r2 = analyze_preflop(position='UTG', hero_hand_type='AKo', stack_bb=40.0,
                         action_taken='raise', facing_size=0.0, vs_position='',
                         facing_raises=0, hero_was_aggressor=False, facing_to_bb=0.0)
    assert r2.get('available') is True, 'RFI de UTG perdeu o gabarito'


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
