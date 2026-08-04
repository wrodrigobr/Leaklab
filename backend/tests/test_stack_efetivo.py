# -*- coding: utf-8 -*-
"""
Stack efetivo e `min(eu, ele)`. O motor usava so o stack do heroi.

── O defeito ──────────────────────────────────────────────────────────────────────────────────────

Quem tem 88bb contra um vilao de 14bb esta jogando um spot de 14bb: a mao se decide ali, nao ha
tres ruas de aposta pela frente. O calculo NUNCA olhava o oponente, e o numero alimenta duas
coisas de uma vez:

    _effective_stack -> state.effective_stack_bb -> spot['effectiveStackBb']
                                                     |-> decisions.stack_bb -> BUCKET da range
                                                     |                         preflop + spot_hash
                                                     `-> payload['hero_stack_bb'] -> PROFUNDIDADE
                                                                                     da arvore CFR

Medido no acervo local: em heads-up o valor muda em 96,4% das decisoes e o bucket em 49% delas.
Casos reais: 88,2bb -> 14,2bb, 64,8bb -> 2,9bb.

── A formula ──────────────────────────────────────────────────────────────────────────────────────

    min(resto_do_hero,  (aposta_dele_na_street - minha_aposta_na_street) + resto_dele)

O segundo termo e o que ele ainda pode cobrar: o que falta pagar agora mais o que sobra atras
dele. Com o vilao ja all-in, `resto_dele` e 0 e o efetivo vira exatamente o que da para pagar.

── O conjunto de vivos, que e onde eu errei primeiro ──────────────────────────────────────────────

A primeira versao usava `still_in_now` (quem ja agiu VOLUNTARIAMENTE). Preflop isso MENTE.
Mao 100000008: UTG+2 vai all-in com 1,25bb e o hero sobe com 31bb -- `still_in_now` via um
heads-up de 1,25bb, mas CO/BTN/SB/BB ainda nao tinham agido e podiam pagar. Vale "sentou e nao
foldou": quem ainda tem cartas conta, tendo agido ou nao. Postflop os dois conjuntos coincidem.

Fora do heads-up NAO EXISTE um efetivo (um curto e um profundo no mesmo pote), e forcar um numero
trocaria um erro por outro. Ali devolve o stack do proprio hero e diz isso em `fonte`.
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.models import ParsedHand, ParsedAction                        # noqa: E402
from leaklab.hand_state_builder import (_effective_stack, _fichas_restantes_de,  # noqa: E402
                                        extract_decision_points)


def _mao(seats, actions, sb=100.0, bb=200.0, button=1, hero='Hero', antes=None):
    raw = ['PokerStars Hand #1: Tournament #1']
    raw += [f'Seat {s}: {n} ({st:,.0f} in chips)' for s, n, st in seats]
    return ParsedHand(
        hand_id='teste', hero=hero, button_seat=button, sb=sb, bb=bb, hero_cards='AsKd',
        seats=[{'seat': s, 'name': n, 'stack': st} for s, n, st in seats],
        players=[n for _, n, _ in seats],
        actions=[ParsedAction(player=p, street=stt, action=a, amount=v, raw=r)
                 for stt, p, a, v, r in actions],
        raw_text='\n'.join(raw), antes=antes or {},
    )


# ── o caso central ─────────────────────────────────────────────────────────────────────────────────

def test_efetivo_e_o_menor_dos_dois():
    """Hero com 88bb contra um vilao de 14bb joga um spot de 14bb, nao de 88bb."""
    h = _mao(
        seats=[(1, 'Hero', 17600), (2, 'Curto', 2800)],
        actions=[('flop', 'Curto', 'checks', None, 'Curto: checks'),
                 ('flop', 'Hero',  'bets',   400.0, 'Hero: bets 400')],
        button=1)
    bb, fonte = _effective_stack(h, 'Hero', h.actions[:1], 'flop', {'Curto'})
    assert fonte == 'heads_up'
    # Curto tem 2.800 - 200 de BB = 2.600 -> 13bb; o hero tem 17.600 - 100 de SB
    assert abs(bb - 13.0) < 0.05, bb


def test_vilao_all_in_deixa_o_efetivo_no_que_da_para_pagar():
    """Com o vilao sem fichas atras, o efetivo e exatamente a aposta que falta pagar."""
    h = _mao(
        seats=[(1, 'Hero', 20000), (2, 'Curto', 3000)],
        actions=[('flop', 'Curto', 'bets', 3000.0, 'Curto: bets 3000 and is all-in'),
                 ('flop', 'Hero',  'calls', 3000.0, 'Hero: calls 3000')],
        button=1)
    bb, fonte = _effective_stack(h, 'Hero', h.actions[:1], 'flop', {'Curto'})
    assert fonte == 'heads_up'
    assert abs(bb - 15.0) < 0.05, f'3.000 fichas a pagar = 15bb, veio {bb}'


def test_multiway_nao_tem_UM_efetivo_e_nao_inventa_um():
    """Um curto e um profundo no mesmo pote: nao existe "o" efetivo. Devolve o do hero."""
    h = _mao(
        seats=[(1, 'Hero', 20000), (2, 'Curto', 2000), (3, 'Fundo', 40000)],
        actions=[('flop', 'Curto', 'checks', None, 'Curto: checks'),
                 ('flop', 'Fundo', 'checks', None, 'Fundo: checks'),
                 ('flop', 'Hero',  'bets',  400.0, 'Hero: bets 400')],
        button=1)
    bb, fonte = _effective_stack(h, 'Hero', h.actions[:2], 'flop', {'Curto', 'Fundo'})
    assert fonte == 'hero_only', fonte
    assert bb > 90, f'devia ser o stack do proprio hero (~99bb), veio {bb}'


def test_quem_ainda_NAO_agiu_conta_como_vivo():
    """O erro que a medicao pegou: `still_in_now` (so quem agiu) via heads-up onde nao havia.

    UTG+2 vai all-in com 1,25bb; o hero sobe. CO/BTN/SB/BB ainda nao agiram e tem 31bb cada --
    o pote pode virar 31bb, entao chamar isso de spot de 1,25bb e falso."""
    seats = [(1, 'BB', 2500), (2, 'UTG', 2500), (4, 'Curto', 100),
             (5, 'Hero', 2500), (6, 'CO', 2500), (7, 'BTN', 2500), (8, 'SB', 2500)]
    h = _mao(
        seats=seats, sb=40.0, bb=80.0, button=7,
        actions=[('preflop', 'UTG',   'folds',  None,  'UTG: folds'),
                 ('preflop', 'Curto', 'all-in', 100.0, 'Curto: raises 100 to 100 and is all-in'),
                 ('preflop', 'Hero',  'raises', 200.0, 'Hero: raises 200 to 200')])
    estados = extract_decision_points(h)
    alvo = [e for e in estados if e.street == 'preflop']
    assert alvo, 'a mao precisa gerar a decisao do hero'
    st = alvo[0]
    assert st.metadata['effective_stack_source'] == 'hero_only', \
        'com 4 jogadores ainda por agir isto NAO e heads-up'
    assert st.effective_stack_bb > 30, \
        f'o hero tem 31bb e pode ser pago por quem esta atras, veio {st.effective_stack_bb}'


def test_heads_up_de_verdade_no_preflop_usa_o_menor():
    """Todos foldaram menos um: agora sim o efetivo e inequivoco."""
    seats = [(1, 'BTN', 20000), (2, 'SB', 20000), (3, 'Hero', 3000)]
    h = _mao(
        seats=seats, sb=100.0, bb=200.0, button=1,
        actions=[('preflop', 'BTN', 'raises', 600.0, 'BTN: raises 400 to 600'),
                 ('preflop', 'SB',  'folds',  None,  'SB: folds'),
                 ('preflop', 'Hero','calls',  400.0, 'Hero: calls 400')])
    st = extract_decision_points(h)[0]
    assert st.metadata['effective_stack_source'] == 'heads_up', st.metadata['effective_stack_source']
    # Hero e o BB com 3.000 - 200 = 2.800 -> 14bb. O BTN tem muito mais.
    assert abs(st.effective_stack_bb - 14.0) < 0.1, st.effective_stack_bb


# ── o resto do PROPRIO hero, que tambem estava errado ──────────────────────────────────────────────

def test_o_que_o_hero_ja_pos_usa_o_TOTAL_do_raise_nao_o_incremento():
    """`raises 200 to 600` de quem tinha 200 de blind custa 600, nao 200. Somar o incremento
    inflava o stack restante -- e ele vai para o bucket da range e para a arvore do CFR."""
    h = _mao(
        seats=[(1, 'Vilao', 50000), (3, 'Hero', 10000)],
        actions=[('preflop', 'Hero',  'raises', 400.0, 'Hero: raises 400 to 600'),
                 ('preflop', 'Vilao', 'calls',  600.0, 'Vilao: calls 600')],
        sb=100.0, bb=200.0, button=1, antes={'Hero': 25.0})
    resto = _fichas_restantes_de(h, 'Hero', h.actions[:1])
    assert resto == 9375.0, f'10.000 - 25 de ante - 600 do raise = 9.375, veio {resto}'


def test_sem_stack_inicial_legivel_cai_no_fallback_de_sempre():
    h = ParsedHand(hand_id='x', hero='Hero', button_seat=1, sb=100.0, bb=200.0,
                   seats=[], actions=[], raw_text='sem linha de Seat')
    bb, fonte = _effective_stack(h, 'Hero', [], 'preflop', None)
    assert (bb, fonte) == (20.0, 'fallback')


def test_a_fonte_chega_ao_spot():
    """Quem consome o numero precisa poder saber se ele e o efetivo ou so o stack do hero."""
    from leaklab.pipeline import build_decision_input
    h = _mao(
        seats=[(1, 'BTN', 20000), (2, 'SB', 20000), (3, 'Hero', 3000)],
        actions=[('preflop', 'BTN', 'raises', 600.0, 'BTN: raises 400 to 600'),
                 ('preflop', 'SB',  'folds',  None,  'SB: folds'),
                 ('preflop', 'Hero','calls',  400.0, 'Hero: calls 400')],
        button=1)
    st = extract_decision_points(h)[0]
    di = build_decision_input(st, h)
    assert di['spot']['effectiveStackBb'] == st.effective_stack_bb
    assert st.metadata['effective_stack_source'] in ('heads_up', 'hero_only', 'fallback')


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
