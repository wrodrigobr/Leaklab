# -*- coding: utf-8 -*-
"""Em stack curto, raise≈allin vale nos DOIS sentidos.

── O caso (09/08) ─────────────────────────────────────────────────────────────────────────────

`_rfi_quality` creditava a adjacencia numa direcao so:

    if act == 'jam' and stack_bb <= 12: freq = hand_freq['allin'] + hand_freq['raise']

Nao existia o simetrico, apesar de o comentario logo acima justificar a regra com "em todo o
bucket curto um open COMPROMETE o stack — raise≈allin". Consequencia: a mao que a carta joga 100%
allin devolvia freq['raise'] = 0 e o min-raise virava `major_leak` → `gto_critical`. Abrir KK/QQ/
AKs com min-raise de CO a 10bb — jogada padrao de regular de MTT — era gravada como leak critico,
que pesa 0,45 no ranking e alimenta o plano de estudo: o aluno era mandado estudar um erro que
nao existe. Jammar a MESMA mao no MESMO spot saia "Correto".

Varredura do bucket 10bb: 326 de 449 pares mao x posicao cujo jam e `correct` tinham o min-raise
marcado `major_leak`. O custo medido pela PROPRIA carta: mediana 0,029bb, e 304 dos 326 abaixo do
limiar de desprezivel que o proprio motor define (`_PREFLOP_EV_MINOR_BB` = 0,12bb).

── Por que o teto e `acceptable`, e nao `correct` ─────────────────────────────────────────────

A mao esta no range; quem tem frequencia zero e o SIZING. E exatamente o veredito que a porta irma
(`_grade_por_no_capturado`, usada por HU e ring) ja da no mesmo caso. `acceptable` capeia o label
em 'marginal' e o gto_label em desvio leve: informa sem acusar.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import _preflop_gto_label_adjust   # noqa: E402
from leaklab.preflop_gto_ranges import analyze_preflop, _load       # noqa: E402


def _rfi(mao, acao, stack=10.0, pos='CO', n=8):
    return analyze_preflop(position=pos, hero_hand_type=mao, stack_bb=stack, action_taken=acao,
                           facing_size=0.0, vs_position='', n_players=n)


def test_min_raise_de_mao_premium_a_10bb_nao_e_desvio_critico():
    for mao in ('KK', 'QQ', 'AKs', '99'):
        r = _rfi(mao, 'raise')
        assert r['action_quality'] == 'acceptable', (mao, r['action_quality'])
        # `acceptable` CAPEIA em 'marginal'; `major_leak` PISAVA em 'small_mistake'. E a diferenca
        # entre "aceitavel" e "Desvio Critico" na tela, e entre entrar ou nao no plano de estudo.
        ev = r.get('ev_loss_bb')
        assert _preflop_gto_label_adjust('standard', r['action_quality'], ev) == 'standard', mao
        assert _preflop_gto_label_adjust('clear_mistake', r['action_quality'], ev) == 'marginal', mao
        assert _preflop_gto_label_adjust('standard', 'major_leak', ev) == 'small_mistake', (
            'o piso de major_leak sumiu — o controle desta comparacao deixou de existir')


def test_CONTROLE_o_jam_da_mesma_mao_segue_correct():
    """O lado que ja funcionava. Se o conserto o rebaixasse, a paridade teria vindo pelo lado
    errado — nivelando por baixo em vez de parar de acusar."""
    for mao in ('KK', 'QQ', 'AKs', '99'):
        assert _rfi(mao, 'jam')['action_quality'] == 'correct', mao


def test_CONTROLE_mao_fora_do_range_continua_acusada_nos_dois_sentidos():
    """A adjacencia empresta a frequencia do VIZINHO; ela nao pode inventar range."""
    for acao in ('raise', 'jam'):
        assert _rfi('72o', acao)['action_quality'] == 'major_leak', acao


def test_CONTROLE_stack_profundo_nao_ganha_a_adjacencia():
    """A 40bb min-raise e jam sao decisoes DIFERENTES — o credito nao pode vazar para fora do
    bucket curto, senao jammar KK a 40bb viraria aceitavel."""
    assert _rfi('KK', 'raise', stack=40.0)['action_quality'] == 'correct'
    assert _rfi('KK', 'jam', stack=40.0)['action_quality'] == 'major_leak'


def test_o_bucket_curto_inteiro_parou_de_acusar_o_min_raise_do_que_ele_jama():
    """A varredura que mediu o defeito, agora como guarda. Mede tambem o CUSTO: se algum par
    acusado tivesse EV alto, o rebaixamento estaria escondendo erro de verdade."""
    d = _load()
    acusados, custos = [], []
    for pos, rfi in d['ranges']['10bb']['RFI'].items():
        for mao in (rfi.get('hand_freqs') or {}):
            if _rfi(mao, 'jam', pos=pos, n=9)['action_quality'] != 'correct':
                continue
            r = _rfi(mao, 'raise', pos=pos, n=9)
            if r['action_quality'] in ('major_leak', 'leak'):
                acusados.append((pos, mao, r['action_quality']))
            if r.get('ev_loss_bb') is not None:
                custos.append(r['ev_loss_bb'])
    assert len(custos) > 200, f'a varredura mediu so {len(custos)} pares — a base mudou'
    assert not acusados, f'{len(acusados)} pares ainda acusados, ex.: {acusados[:5]}'
    assert statistics.median(custos) < 0.12, (
        f'o min-raise do bucket curto passou a custar caro (mediana {statistics.median(custos)}bb)'
        ' — o rebaixamento deixou de ser inocuo e precisa ser remedido')


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
