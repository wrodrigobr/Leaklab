"""
Testes do motor de stats de oponente (opponent_stats.py) — Fase 1 do HUD.

Valida a mecânica de cada stat no nível de UMA mão (_process_hand, incrementos 0/1)
em cenários forjados conhecidos, + a tipagem de arquétipo no finalize.
"""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.models import ParsedHand, ParsedAction
from leaklab.opponent_stats import _process_hand, accumulate, finalize, build_profiles


def _h(players, acts):
    """acts: list de (player, street, action[, amount])."""
    actions = [ParsedAction(player=a[0], street=a[1], action=a[2],
                            amount=(a[3] if len(a) > 3 else None)) for a in acts]
    return ParsedHand(hand_id='1', players=list(players), actions=actions)


def test_vpip_pfr():
    h = _h(['A', 'B', 'C'], [
        ('A', 'preflop', 'raises', 3),
        ('B', 'preflop', 'calls', 3),
        ('C', 'preflop', 'folds'),
    ])
    o = _process_hand(h)
    assert o['A']['vpip'] == 1 and o['A']['pfr'] == 1
    assert o['B']['vpip'] == 1 and o['B']['pfr'] == 0
    assert o['C']['vpip'] == 0
    assert o['A']['hands'] == 1 and o['C']['hands'] == 1
    print("OK  test_vpip_pfr")


def test_bb_check_not_vpip():
    # limp (call) é VPIP; check de opção do BB NÃO é
    h = _h(['A', 'BB'], [
        ('A', 'preflop', 'calls', 1),
        ('BB', 'preflop', 'checks'),
    ])
    o = _process_hand(h)
    assert o['A']['vpip'] == 1 and o['A']['pfr'] == 0
    assert o['BB']['vpip'] == 0
    print("OK  test_bb_check_not_vpip")


def test_3bet_and_fold_to_3bet():
    h = _h(['A', 'B'], [
        ('A', 'preflop', 'raises', 3),    # open
        ('B', 'preflop', 'raises', 9),    # 3-bet
        ('A', 'preflop', 'folds'),        # opener folda ao 3-bet
    ])
    o = _process_hand(h)
    assert o['B']['threebet_opp'] == 1 and o['B']['threebet'] == 1
    assert o['A']['fold3bet_opp'] == 1 and o['A']['fold3bet'] == 1
    print("OK  test_3bet_and_fold_to_3bet")


def test_3bet_opp_but_called():
    h = _h(['A', 'B'], [
        ('A', 'preflop', 'raises', 3),
        ('B', 'preflop', 'calls', 3),     # enfrentou open, só pagou → opp sem 3bet
    ])
    o = _process_hand(h)
    assert o['B']['threebet_opp'] == 1 and o['B']['threebet'] == 0
    assert o['A']['fold3bet_opp'] == 0
    print("OK  test_3bet_opp_but_called")


def test_cbet_and_fold_to_cbet():
    h = _h(['A', 'B'], [
        ('A', 'preflop', 'raises', 3),    # A = agressor preflop
        ('B', 'preflop', 'calls', 3),
        ('B', 'flop', 'checks'),
        ('A', 'flop', 'bets', 4),         # c-bet
        ('B', 'flop', 'folds'),
    ])
    o = _process_hand(h)
    assert o['A']['cbet_opp'] == 1 and o['A']['cbet'] == 1
    assert o['B']['foldcbet_opp'] == 1 and o['B']['foldcbet'] == 1
    assert o['B']['saw_flop'] == 1 and o['B']['wtsd'] == 0   # foldou postflop
    print("OK  test_cbet_and_fold_to_cbet")


def test_no_cbet_when_aggressor_checks():
    h = _h(['A', 'B'], [
        ('A', 'preflop', 'raises', 3),
        ('B', 'preflop', 'calls', 3),
        ('B', 'flop', 'checks'),
        ('A', 'flop', 'checks'),          # agressor deu check → sem c-bet
    ])
    o = _process_hand(h)
    assert o['A']['cbet_opp'] == 1 and o['A']['cbet'] == 0
    print("OK  test_no_cbet_when_aggressor_checks")


def test_wtsd_and_af():
    h = _h(['A', 'B'], [
        ('A', 'preflop', 'raises', 3),
        ('B', 'preflop', 'calls', 3),
        ('A', 'flop', 'bets', 4),         # c-bet (aggr)
        ('B', 'flop', 'calls', 4),        # call (foldcbet_opp, não foldou)
        ('A', 'turn', 'checks'),
        ('B', 'turn', 'checks'),
        ('A', 'river', 'checks'),
        ('B', 'river', 'checks'),
    ])
    o = _process_hand(h)
    assert o['A']['wtsd'] == 1 and o['B']['wtsd'] == 1     # ninguém foldou postflop
    assert o['A']['saw_flop'] == 1 and o['B']['saw_flop'] == 1
    assert o['A']['pf_aggr'] == 1 and o['A']['pf_calls'] == 0   # 1 bet
    assert o['B']['pf_calls'] == 1 and o['B']['pf_aggr'] == 0   # 1 call
    assert o['B']['foldcbet_opp'] == 1 and o['B']['foldcbet'] == 0
    print("OK  test_wtsd_and_af")


def test_finalize_gates_low_sample():
    # poucas mãos → taxas None (abaixo do gate) e arquétipo unknown
    acc = accumulate([_h(['A', 'B'], [('A', 'preflop', 'raises', 3), ('B', 'preflop', 'folds')])])
    prof = finalize(acc)
    assert prof['A']['vpip_pct'] is None        # 1 mão < gate 15
    assert prof['A']['archetype'] == 'unknown'
    assert prof['A']['confidence'] == 'insufficient'
    print("OK  test_finalize_gates_low_sample")


def test_finalize_calling_station():
    # 30 mãos de um vilão que paga muito, agride pouco, vai a showdown → calling_station
    hands = []
    for i in range(30):
        hands.append(_h(['STN', 'X'], [
            ('STN', 'preflop', 'calls', 3),     # VPIP alto, PFR 0
            ('X', 'preflop', 'raises', 3),
            ('X', 'flop', 'bets', 4),
            ('STN', 'flop', 'calls', 4),        # não folda c-bet
            ('X', 'turn', 'checks'),
            ('STN', 'turn', 'checks'),
            ('X', 'river', 'checks'),
            ('STN', 'river', 'checks'),         # vai a showdown
        ]))
    prof = build_profiles(hands)
    s = prof['STN']
    assert s['vpip_pct'] == 1.0 and s['pfr_pct'] == 0.0
    assert s['foldcbet_pct'] == 0.0 and s['wtsd_pct'] == 1.0
    assert s['archetype'] == 'calling_station', s['archetype']
    assert s['confidence'] == 'high'
    print("OK  test_finalize_calling_station")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
