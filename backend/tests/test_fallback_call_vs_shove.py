# -*- coding: utf-8 -*-
"""O fallback call-vs-shove perguntava a coisa errada.

── O caso ─────────────────────────────────────────────────────────────────────────────────────

Print do usuario: `33` no SB heads-up, 15,2bb efetivos, pagando um shove de 17,2 com **53,8% de
equity contra 43,8% de pot odds**. O card cravou **ERRO** — e o proprio retorno do fallback se
contradizia: `in_range=True` junto de `recommended_actions=['fold']`.

Contexto que fecha o caso: o banco guardava `standard` para essa decisao, e o motor recomputado
tambem devolvia `standard`. **Quem inventou o erro foi o fallback**, no caminho do `/replay`.

── A causa ────────────────────────────────────────────────────────────────────────────────────

O proxy media a qualidade de uma consulta feita com `action_taken='raise'`:

    rq = analyze_preflop(..., action_taken='raise')['action_quality']
    q  = 'correct' if rq == 'correct' else ... else 'leak'

Em stack curto o GTO abre as maos fortes com **JAM**, nao com raise. Entao "raise" volta como leak
e o fallback conclui *"mao fora do range de abertura — folde ao shove"* para uma mao que abre
**100% das vezes**. Ou seja: quanto MAIS forte a mao em stack curto, mais provavel a acusacao
falsa.

A pergunta certa nunca foi "o raise esta certo?", e sim **"a mao abre?"** — que e a frequencia de
nao-fold no proprio range.

── O guarda ───────────────────────────────────────────────────────────────────────────────────

Alem do caso, uma invariante: `in_range` e `recommended_actions` saem da MESMA conta e nao podem
mais se contradizer. Era esse par, exibido lado a lado, que o usuario viu no card.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.strategy_provider import preflop_call_vs_shove_fallback as _fb


def test_mao_que_ABRE_com_jam_nao_e_mandada_foldar():
    """O caso do print. A 15-16bb o SB abre `33` com all-in 100%: pagar um shove com ela nao pode
    ser 'leak' so porque o RAISE nao e a forma de abrir ali."""
    aberta = analyze_preflop(position='SB', hero_hand_type='33', stack_bb=15.2,
                             action_taken='raise', facing_size=0.0, vs_position='')
    assert aberta.get('available'), 'o teste precisa de cobertura de RFI nessa profundidade'
    freq = aberta.get('hand_freq') or {}
    assert sum(v for k, v in freq.items() if k != 'fold') >= 0.8, (
        f'premissa quebrada: 33 deveria abrir quase sempre a 15bb — {freq}')

    f = _fb('SB', '33', 15.2, action_taken='call')
    assert f and f['action_quality'] != 'leak', f
    assert f['recommended_actions'] == ['call'], f['recommended_actions']


def test_lixo_continua_sendo_fold():
    """CONTROLE NEGATIVO. Sem ele o conserto viraria anistia geral de call contra shove."""
    f = _fb('SB', '72o', 15.2, action_taken='call')
    assert f and f['action_quality'] == 'leak', f
    assert f['recommended_actions'] == ['fold']


def test_in_range_e_recomendacao_nunca_se_contradizem():
    """A invariante. Era o par `in_range=True` + `['fold']` que aparecia no card, lado a lado."""
    vistos = 0
    for pos in ('SB', 'BTN', 'CO'):
        for mao in ('AA', 'KK', 'AQo', '33', '72o', 'J4o', 'A5s', 'K9o'):
            for st in (9.0, 12.0, 15.2, 20.0):
                f = _fb(pos, mao, st, action_taken='call')
                if not f:
                    continue
                vistos += 1
                assert f['in_range'] == (f['recommended_actions'] != ['fold']), (
                    f'{pos} {mao} {st}bb: in_range={f["in_range"]} '
                    f'rec={f["recommended_actions"]}')
    assert vistos >= 20, f'so {vistos} combinacoes cobertas — o teste virou vacuo'


def test_sem_cobertura_de_RFI_o_fallback_se_cala():
    """Sem range de abertura para a posicao, nao ha proxy honesto a fazer: devolve None e o
    caminho de cima decide. Inventar aqui seria pior que calar."""
    assert _fb('XX', 'AA', 15.0, action_taken='call') is None


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
