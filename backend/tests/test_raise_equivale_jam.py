# -*- coding: utf-8 -*-
"""Raise que COMPROMETE o stack efetivo é o jam com outro nome — porta única do preflop.

O caso real (mão 259090801366, t3960586609): AJs no BB, vilão de 12bb efetivos abre 2bb, o
herói 3-beta para 10bb — deixa 2bb atrás, mesma fold equity e mesmo commit do jam. A carta só
tem fold/call/jam nessa profundidade; gradear a PALAVRA "raise" dava freq 0 e `gto_critical`
recomendando exatamente a jogada equivalente. Mesma família do shove≡call do postflop.

O colapso mora em `preflop_strategy` (porta única) e dispara com `hero_raise_to_bb >= 0.8 ×
stack efetivo`. A mão de teste é TEXTO parseado — o caminho vivo do motor, não dict montado.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision

# A mão real, com os nomes trocados. Level IX 200/400, vilão (MP) 4.880 fichas = 12,2bb.
MAO = """PokerStars Hand #900000001: Tournament #900, $1+$0 USD Hold'em No Limit - Level IX (200/400) - 2026/01/01 12:00:00 BRT
Table '900 1' 8-max Seat #2 is the button
Seat 1: p1 (12904 in chips)
Seat 2: p2 (3427 in chips)
Seat 3: p3 (4020 in chips)
Seat 5: hero (18759 in chips)
Seat 6: p6 (12644 in chips)
Seat 7: vilao (4880 in chips)
Seat 8: p8 (17577 in chips)
p1: posts the ante 60
p2: posts the ante 60
p3: posts the ante 60
hero: posts the ante 60
p6: posts the ante 60
vilao: posts the ante 60
p8: posts the ante 60
p3: posts small blind 200
hero: posts big blind 400
*** HOLE CARDS ***
Dealt to hero [Jh Ah]
p6: folds
vilao: raises 400 to 800
p8: folds
p1: folds
p2: folds
p3: folds
hero: raises 3200 to 4000
vilao: raises 820 to 4820 and is all-in
hero: calls 820
*** FLOP *** [5h 8c 5d]
*** TURN *** [5h 8c 5d] [6c]
*** RIVER *** [5h 8c 5d 6c] [4c]
*** SHOW DOWN ***
hero: shows [Jh Ah] (a pair of Fives)
vilao: shows [Kh Jd] (a pair of Fives - lower kicker)
hero collected 10260 from pot
*** SUMMARY ***
Total pot 10260 | Rake 0
Board [5h 8c 5d 6c 4c]
"""


def _decisao_do_raise():
    hands = parse_hand_history(MAO)
    assert len(hands) == 1
    for di in build_decision_inputs_for_hand(hands[0]):
        if di.get('street') == 'preflop' and (di.get('player_action') or '').lower() == 'raise':
            return di
    raise AssertionError('a fixture nao produziu a decisao de raise')


def test_raise_que_compromete_o_efetivo_e_gradeado_como_jam():
    di = _decisao_do_raise()
    spot = di['spot']
    eff = float(spot.get('effectiveStackBb') or 0)
    rt = float(spot.get('heroRaiseToBb') or 0)
    assert rt >= 0.8 * eff > 0, f'a fixture perdeu o commit (raise_to={rt}, eff={eff})'
    r = evaluate_decision(di)
    pf = r.get('preflop_gto') or {}
    assert pf.get('available'), 'preflop sem cobertura — a fixture nao exercita a carta'
    # O jam de AJs no BB vs open de 12bb e padrao: o colapso tem de absolver.
    assert pf.get('action_quality') in ('correct', 'acceptable'), (
        f"raise-commit ainda punido pela palavra: quality={pf.get('action_quality')}")
    assert (r.get('evaluation') or {}).get('label') in ('standard', 'marginal'), r['evaluation']
    print('OK  test_raise_que_compromete_o_efetivo_e_gradeado_como_jam')


def test_call_do_excesso_nunca_e_pior_que_marginal():
    """A SEGUNDA decisão da mesma mão: pagar os 2bb de excesso do 4-bet-jam depois do próprio
    3-bet-commit (65% vs-random contra ~9% exigidos). O veredito DESENHADO é 'marginal': a
    equity é vs-random e não dá base para absolver ('standard') um call vs squeeze — guarda da
    recalibração do coach (#27). Houve por uma hora um piso que forçava 'standard' aqui; ele
    absolveria também squeeze-calls ruins e foi revertido. O invariante real: o call forçado
    NUNCA vira acusação (small/clear), e a recomendação é o próprio call."""
    hands = parse_hand_history(MAO)
    di_call = None
    for di in build_decision_inputs_for_hand(hands[0]):
        if di.get('street') == 'preflop' and (di.get('player_action') or '').lower() == 'call':
            di_call = di
    assert di_call, 'a fixture nao produziu o call do excesso'
    assert bool(di_call['spot'].get('facingAllin')) is True
    r = evaluate_decision(di_call)
    ev = r.get('evaluation') or {}
    assert ev.get('label') in ('standard', 'marginal'), (
        f"call forcado do excesso virou ACUSACAO: {ev.get('label')}")
    assert (r.get('bestAction') or '').lower() in ('call', 'calls'), r.get('bestAction')
    print('OK  test_call_do_excesso_nunca_e_pior_que_marginal')


def test_CONTROLE_raise_pequeno_em_stack_fundo_nao_colapsa():
    """Sem esta ancora, 'colapsar tudo' passaria: um 3-bet de 10bb a 47bb efetivos NAO e jam."""
    from leaklab.strategy_provider import preflop_strategy
    com = preflop_strategy('BB', hero_hand_type='AJs', stack_bb=47.0, action_taken='raise',
                           facing_size=2.0, vs_position='HJ', facing_raises=1,
                           facing_to_bb=2.0, hero_raise_to_bb=10.0)
    sem = preflop_strategy('BB', hero_hand_type='AJs', stack_bb=47.0, action_taken='raise',
                           facing_size=2.0, vs_position='HJ', facing_raises=1,
                           facing_to_bb=2.0)
    assert com['raw'] == sem['raw'], 'o colapso vazou para raise que NAO compromete o stack'
    print('OK  test_CONTROLE_raise_pequeno_em_stack_fundo_nao_colapsa')


def test_fold_nunca_colapsa():
    from leaklab.strategy_provider import preflop_strategy
    com = preflop_strategy('BB', hero_hand_type='72o', stack_bb=12.0, action_taken='fold',
                           facing_size=2.0, vs_position='HJ', facing_raises=1,
                           facing_to_bb=2.0, hero_raise_to_bb=11.0)
    sem = preflop_strategy('BB', hero_hand_type='72o', stack_bb=12.0, action_taken='fold',
                           facing_size=2.0, vs_position='HJ', facing_raises=1,
                           facing_to_bb=2.0)
    assert com['raw'] == sem['raw'], 'fold colapsou — critica legitima seria apagada'
    print('OK  test_fold_nunca_colapsa')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FALHOU  %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
