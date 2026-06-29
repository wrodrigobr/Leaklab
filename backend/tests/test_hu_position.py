"""Regressão do bug de posição em HEADS-UP: o botão É o small blind.

Antes, `_position_names(2)` devolvia {0:'SB', 1:'BB'} mas a ordenação põe o botão por
ÚLTIMO (ordered[n-1]=botão) → o SB/botão era rotulado BB. Isso gerava best='check'
(impossível pro SB pré-flop), small_mistake FALSO ao foldar, e spot sem cobertura GTO.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.hand_state_builder import (
    _position_names, _infer_position, extract_decision_points,
)
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


# Regressão: assento "out of hand" (jogador movido de outra mesa que só joga após o
# botão) NÃO é jogador desta mão. Contá-lo inflava num_players e o fallback
# seats−folded do card → um spot HU virava "multiway" (e as posições deslocavam).
_OUT_OF_HAND_HAND = """PokerStars Hand #261282988876: Tournament #4012159146, $0.90+$0.10 USD Hold'em No Limit - Level I (10/20) - 2026/06/28 21:10:53 ET
Table '4012159146 2' 8-max Seat #8 is the button
Seat 1: rafaela919 (1500 in chips) out of hand (moved from another table into small blind)
Seat 2: machineninefour (1426 in chips)
Seat 3: MisteriosoPK (1491 in chips)
Seat 4: smokebear97 (1577 in chips)
Seat 5: Nietze94 (376 in chips)
Seat 7: phpro (2787 in chips)
Seat 8: salomao1959 (1358 in chips)
machineninefour: posts small blind 10
MisteriosoPK: posts big blind 20
*** HOLE CARDS ***
Dealt to phpro [Ah Ks]
smokebear97: folds
Nietze94: folds
phpro: raises 40 to 60
salomao1959: folds
machineninefour: folds
MisteriosoPK: calls 40
*** FLOP *** [2d 7c Jh]
MisteriosoPK: checks
phpro: bets 60
MisteriosoPK: folds
phpro collected 140 from pot
*** SUMMARY ***
Total pot 140 | Rake 0
Board [2d 7c Jh]
Seat 7: phpro collected (140)
"""


def test_out_of_hand_seat_excluded_from_players():
    hand = parse_pokerstars_file_from_text(_OUT_OF_HAND_HAND)[0]
    assert 'rafaela919' not in hand.players, "assento 'out of hand' não é jogador"
    assert len(hand.players) == 6, f"6 jogadores ativos, não {len(hand.players)}"
    assert all(s['name'] != 'rafaela919' for s in (hand.seats or [])), \
        "assento 'out of hand' fora de hand.seats (fallback seats−folded do card)"
    print("OK  test_out_of_hand_seat_excluded_from_players")


def test_out_of_hand_position_not_shifted():
    hand = parse_pokerstars_file_from_text(_OUT_OF_HAND_HAND)[0]
    # 6 ativos, botão no Seat 8 → Seat 7 é o CO. Contar a fantasma deslocava a posição.
    assert _infer_position(hand, 'phpro') == 'CO', "posição do hero com a fantasma fora"
    print("OK  test_out_of_hand_position_not_shifted")


def test_out_of_hand_flop_is_heads_up():
    hand = parse_pokerstars_file_from_text(_OUT_OF_HAND_HAND)[0]
    flop = [s for s in extract_decision_points(hand) if s.street == 'flop']
    assert flop, "deve haver decisão no flop"
    # phpro vs MisteriosoPK = HU. A fantasma (nunca agiu) não pode virar 3º jogador.
    assert flop[0].metadata['n_active_opponents'] == 1, "flop é HU, não multiway"
    print("OK  test_out_of_hand_flop_is_heads_up")


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
