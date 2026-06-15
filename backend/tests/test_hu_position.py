"""Regressão do bug de posição em HEADS-UP: o botão É o small blind.

Antes, `_position_names(2)` devolvia {0:'SB', 1:'BB'} mas a ordenação põe o botão por
ÚLTIMO (ordered[n-1]=botão) → o SB/botão era rotulado BB. Isso gerava best='check'
(impossível pro SB pré-flop), small_mistake FALSO ao foldar, e spot sem cobertura GTO.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.hand_state_builder import _position_names, _infer_position
from leaklab.parser import parse_pokerstars_file_from_text

_HU_HAND = """PokerStars Hand #999000111: Tournament #555, $0.85+$0.15 USD Hold'em No Limit - Level VIII (150/300) - 2026/05/20 18:30:24 ET
Table '555 1' 9-max Seat #1 is the button
Seat 1: hero (6000 in chips)
Seat 3: villain (7000 in chips)
hero: posts the ante 25
villain: posts the ante 25
hero: posts small blind 150
villain: posts big blind 300
*** HOLE CARDS ***
Dealt to hero [5d 2s]
hero: folds
Uncalled bet (150) returned to villain
villain collected 350 from pot
villain: doesn't show hand
*** SUMMARY ***
Total pot 350 | Rake 0
Seat 1: hero (button) (small blind) folded before Flop
Seat 3: villain (big blind) collected (350)
"""


def test_position_names_hu_button_is_sb():
    # ordered[0] = não-botão = BB · ordered[1] = botão = SB
    assert _position_names(2) == {0: 'BB', 1: 'SB'}
    print("OK  test_position_names_hu_button_is_sb")


def test_infer_position_hu_button_seat_is_sb():
    hand = parse_pokerstars_file_from_text(_HU_HAND)[0]
    # hero está no Seat 1 = botão → no HU é o SMALL BLIND (posta o SB no HH)
    assert hand.button_seat == 1
    assert _infer_position(hand, 'hero') == 'SB', "botão em HU deve ser SB"
    assert _infer_position(hand, 'villain') == 'BB', "não-botão em HU é BB"
    print("OK  test_infer_position_hu_button_seat_is_sb")


def test_full_ring_positions_unaffected():
    # n>=3 segue o padrão (botão por último, SB primeiro após o botão)
    n6 = _position_names(6)
    assert n6[0] == 'SB' and n6[1] == 'BB' and n6[5] == 'BTN'
    print("OK  test_full_ring_positions_unaffected")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}"); failed += 1
            import traceback; traceback.print_exc()
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
