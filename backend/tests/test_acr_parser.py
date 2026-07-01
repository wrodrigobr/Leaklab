"""Parser ACR / WPN (Americas Cardroom) — dialeto PokerStars-like que QUEBRA o parser PS:
header "Game Hand #", assentos sem "in chips", AÇÕES SEM DOIS-PONTOS ("nome raises X to Y"),
valores em chips decimais, linhas "Main pot" extras. Fixtures = 2 mãos reais do torneio #35409697.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.parser import parse_hand_history, _detect_site, _extract_showdown_result
from leaklab.pipeline import build_decision_inputs_for_hand

# Mão 1 — preflop, open + fold (hero MusashiBR folda), sem showdown.
ACR_FOLD_HAND = """Game Hand #2769798195 - Tournament #35409697 - Holdem (No Limit) - Level 4 (750.00/1500.00) - 2026/06/30 21:10:09 UTC
Table '1' 8-max Seat #8 is the button
Seat 1: 1IrieMonn (25755.00)
Seat 2: swalker2223 (25850.00)
Seat 3: MusashiBR (48799.00)
Seat 4: ibslower (51757.00)
Seat 5: Dudman (25550.00)
Seat 6: elvin6161 (26600.00)
Seat 7: Quenched (76785.00)
Seat 8: UnDERSun (31575.00)
1IrieMonn posts ante 150.00
swalker2223 posts ante 150.00
MusashiBR posts ante 150.00
ibslower posts ante 150.00
Dudman posts ante 150.00
elvin6161 posts ante 150.00
Quenched posts ante 150.00
UnDERSun posts ante 150.00
1IrieMonn posts the small blind 750.00
swalker2223 posts the big blind 1500.00
*** HOLE CARDS ***
Main pot 1200.00
Dealt to MusashiBR [6c 4d]
MusashiBR folds
ibslower folds
Dudman folds
elvin6161 folds
Quenched folds
UnDERSun folds
1IrieMonn raises 4950.00 to 5700.00
swalker2223 folds
Uncalled bet (4200.00) returned to 1IrieMonn
1IrieMonn does not show
*** SUMMARY ***
Total pot 4200.00
Seat 1: 1IrieMonn did not show and won 4200.00
Seat 2: swalker2223 (big blind) folded on the Pre-Flop
Seat 3: MusashiBR folded on the Pre-Flop and did not bet
Seat 4: ibslower folded on the Pre-Flop and did not bet
Seat 5: Dudman folded on the Pre-Flop and did not bet
Seat 6: elvin6161 folded on the Pre-Flop and did not bet
Seat 7: Quenched folded on the Pre-Flop and did not bet
Seat 8: UnDERSun (button) folded on the Pre-Flop"""

# Mão 2 — raise/call/3bet-allin preflop + board completo + showdown (hero folda; Quenched vence).
ACR_SHOWDOWN_HAND = """Game Hand #2769789277 - Tournament #35409697 - Holdem (No Limit) - Level 1 (250.00/500.00) - 2026/06/30 20:48:30 UTC
Table '1' 8-max Seat #4 is the button
Seat 1: AndreaBsAs (29000.00)
Seat 2: JAMESHARPER (32200.00)
Seat 3: MusashiBR (30200.00)
Seat 4: ibslower (7268.00)
Seat 5: xuligangster (29250.00)
Seat 6: Lunyt1st (29750.00)
Seat 7: Quenched (52332.00)
AndreaBsAs posts ante 50.00
JAMESHARPER posts ante 50.00
MusashiBR posts ante 50.00
ibslower posts ante 50.00
xuligangster posts ante 50.00
Lunyt1st posts ante 50.00
Quenched posts ante 50.00
xuligangster posts the small blind 250.00
Lunyt1st posts the big blind 500.00
*** HOLE CARDS ***
Main pot 350.00
Dealt to MusashiBR [8s As]
Quenched raises 1150.00 to 1150.00
AndreaBsAs folds
JAMESHARPER folds
MusashiBR calls 1150.00
ibslower raises 7218.00 to 7218.00 and is all-in
xuligangster folds
Lunyt1st folds
Quenched calls 6068.00
MusashiBR folds
*** FLOP *** [9s 7c Tc]
Main pot 16686.00
*** TURN *** [9s 7c Tc] [4c]
Main pot 16686.00
*** RIVER *** [9s 7c Tc 4c] [2c]
Main pot 16686.00
*** SHOW DOWN ***
Main pot 16686.00
ibslower shows [Ts Th] (three of a kind, Set of Tens [Ts Th Tc 9s 7c])
Quenched shows [Js Ac] (a flush, Ace high [Ac Tc 7c 4c 2c])
Quenched collected 16686.00 from main pot
*** SUMMARY ***
Total pot 16686.00
Board [9s 7c Tc 4c 2c]
Seat 1: AndreaBsAs folded on the Pre-Flop and did not bet
Seat 2: JAMESHARPER folded on the Pre-Flop and did not bet
Seat 3: MusashiBR folded on the Pre-Flop and did not bet
Seat 4: ibslower (button) showed [Ts Th] and lost with three of a kind, Set of Tens [Ts Th Tc 9s 7c]
Seat 5: xuligangster (small blind) folded on the Pre-Flop
Seat 6: Lunyt1st (big blind) folded on the Pre-Flop
Seat 7: Quenched showed [Js Ac] and won 16686.00 with a flush, Ace high [Ac Tc 7c 4c 2c]"""


def test_detect_acr():
    assert _detect_site(ACR_FOLD_HAND) == 'acr'
    assert _detect_site(ACR_SHOWDOWN_HAND) == 'acr'
    print("OK  test_detect_acr")


def test_parse_acr_header_seats_antes():
    h = parse_hand_history(ACR_FOLD_HAND)[0]
    assert h.hand_id == '2769798195'
    assert h.tournament_id == '35409697'
    assert h.hero == 'MusashiBR' and h.hero_cards == '6c4d'
    assert h.button_seat == 8
    assert h.sb == 750.0 and h.bb == 1500.0            # blinds decimais do header
    assert len(h.players) == 8 and len(h.seats) == 8   # assentos SEM "in chips"
    assert h.seats[0] == {'seat': 1, 'name': '1IrieMonn', 'stack': 25755.0}
    assert len(h.antes) == 8 and h.antes['MusashiBR'] == 150.0
    print("OK  test_parse_acr_header_seats_antes")


def test_parse_acr_actions_no_colon():
    """Ações SEM dois-pontos: 'nome raises X to Y' → total Y; call/fold; all-in."""
    h = parse_hand_history(ACR_FOLD_HAND)[0]
    acts = {(a.player, a.action, a.amount) for a in h.actions}
    assert ('1IrieMonn', 'raises', 5700.0) in acts     # "raises 4950 to 5700" → total 5700
    assert ('MusashiBR', 'folds', None) in acts
    assert ('swalker2223', 'folds', None) in acts
    # não vaza a linha "Uncalled bet (...) returned to X" nem "does not show" como ação
    assert not any('Uncalled' in (a.player or '') for a in h.actions)
    print("OK  test_parse_acr_actions_no_colon")


def test_parse_acr_board_allin_showdown():
    h = parse_hand_history(ACR_SHOWDOWN_HAND)[0]
    assert h.board == ['9s', '7c', 'Tc', '4c', '2c']
    # "raises X to X and is all-in" → all-in com valor
    assert any(a.action == 'all-in' and abs((a.amount or 0) - 7218.0) < 0.01 for a in h.actions), h.actions
    assert any(a.player == 'Quenched' and a.action == 'calls' and abs((a.amount or 0) - 6068.0) < 0.01
               for a in h.actions)
    # showdown ACR (summary "showed [..] and won/lost"): won/lost/None por jogador
    assert _extract_showdown_result(ACR_SHOWDOWN_HAND, 'Quenched') == 'won'
    assert _extract_showdown_result(ACR_SHOWDOWN_HAND, 'ibslower') == 'lost'
    assert _extract_showdown_result(ACR_SHOWDOWN_HAND, 'MusashiBR') is None   # foldou, não revelou
    print("OK  test_parse_acr_board_allin_showdown")


def test_acr_multi_hand_same_tournament_and_pipeline():
    """N mãos = MESMO Tournament # (merge no import) e o pipeline constrói decisões com posição."""
    hands = parse_hand_history(ACR_FOLD_HAND + "\n\n" + ACR_SHOWDOWN_HAND)
    assert len(hands) == 2
    assert {h.tournament_id for h in hands} == {'35409697'}
    dis = []
    for h in hands:
        dis += build_decision_inputs_for_hand(h)
    assert dis, "pipeline não construiu nenhuma decisão a partir das mãos ACR"
    pos = [d.get('spot', {}).get('position') for d in dis if d.get('street') == 'preflop']
    assert pos and all(p for p in pos), pos      # toda decisão preflop tem posição resolvida
    print("OK  test_acr_multi_hand_same_tournament_and_pipeline")


if __name__ == '__main__':
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
