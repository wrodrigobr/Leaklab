"""
Testes da classificação de INTENÇÃO de aposta postflop (bet_intent.py).

Cobre o tier de força de mão (value / middle / air) — incluindo a correção de
boards pareados (par do board não conta como dois pares do herói) — e a
classificação de intenção (value_showdown / value_protection / semi_bluff /
middle / bluff) com o árbitro GTO (justified / is_leak).
"""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.bet_intent import made_hand_category, classify_bet_intent, _board_wet


# ── Tier de força de mão ────────────────────────────────────────────────────────

def test_cat_overpair_value():
    assert made_hand_category(['Ad', 'Ah'], ['Kh', 'Td', 'Tc']) == 'value'
    print("OK  test_cat_overpair_value")


def test_cat_underpair_middle():
    assert made_hand_category(['8h', '8d'], ['Kc', 'Qh', '2s']) == 'middle'
    print("OK  test_cat_underpair_middle")


def test_cat_top_pair_strong_kicker_value():
    # AK em A-7-2: top pair top kicker → value
    assert made_hand_category(['Ac', 'Kd'], ['Ah', '7c', '2s']) == 'value'
    print("OK  test_cat_top_pair_strong_kicker_value")


def test_cat_top_pair_weak_kicker_middle():
    # JT em 6-9-J: top pair J kicker T (<Q) → middle
    assert made_hand_category(['Jc', 'Th'], ['6s', '9c', 'Jh']) == 'middle'
    print("OK  test_cat_top_pair_weak_kicker_middle")


def test_cat_paired_board_not_two_pair():
    # Q8 em K-Q-K: o KK é do board (compartilhado) — herói tem só par de Q (second pair).
    # NÃO pode virar "dois pares" → middle.
    assert made_hand_category(['Qc', '8c'], ['Kh', 'Qh', 'Kc']) == 'middle'
    print("OK  test_cat_paired_board_not_two_pair")


def test_cat_real_two_pair_value():
    # Q8 em Q-8-2: herói segura AMBOS os pares → dois pares reais → value
    assert made_hand_category(['Qc', '8c'], ['Qd', '8h', '2s']) == 'value'
    print("OK  test_cat_real_two_pair_value")


def test_cat_bottom_pair_paired_board_middle():
    # 94 em Q-4-Q: bottom pair (4) + QQ do board → middle, não value
    assert made_hand_category(['9s', '4h'], ['Qs', '4d', 'Qc']) == 'middle'
    print("OK  test_cat_bottom_pair_paired_board_middle")


def test_cat_set_value():
    assert made_hand_category(['7h', '7d'], ['7s', 'Kc', '2d']) == 'value'
    print("OK  test_cat_set_value")


def test_cat_straight_value():
    assert made_hand_category(['Kc', 'Qd'], ['Js', 'Ts', '9h']) == 'value'
    print("OK  test_cat_straight_value")


def test_cat_flush_value():
    assert made_hand_category(['Ah', '5h'], ['Kh', 'Qh', '2h']) == 'value'
    print("OK  test_cat_flush_value")


def test_cat_air():
    assert made_hand_category(['2h', '7d'], ['Ac', 'Kh', '9s']) == 'air'
    print("OK  test_cat_air")


def test_cat_flush_draw_no_pair_is_air():
    # Nut flush draw mas SEM par feito: mão feita = air (o draw vira semi-blefe via equity_adj)
    assert made_hand_category(['As', '5s'], ['Ks', 'Qs', '2h']) == 'air'
    print("OK  test_cat_flush_draw_no_pair_is_air")


# ── _board_wet (proteção só faz sentido em board molhado) ────────────────────────

def test_board_wet_two_suited():
    assert _board_wet(['Kh', 'Qh', '2s']) is True
    print("OK  test_board_wet_two_suited")


def test_board_dry_rainbow_disconnected():
    assert _board_wet(['Kh', '7c', '2s']) is False
    print("OK  test_board_dry_rainbow_disconnected")


# ── classify_bet_intent: gating ─────────────────────────────────────────────────

def test_intent_none_preflop():
    assert classify_bet_intent(player_action='raise', street='preflop', hero_cards=['Ah', 'Kh'],
                               board=[], equity=0.6, equity_adj=0.0, stack_bb=50, position='CO') is None
    print("OK  test_intent_none_preflop")


def test_intent_none_passive():
    assert classify_bet_intent(player_action='check', street='flop', hero_cards=['Ah', 'Kh'],
                               board=['2c', '7d', 'Td'], equity=0.6, equity_adj=0.0, stack_bb=50, position='CO') is None
    print("OK  test_intent_none_passive")


# ── classify_bet_intent: intenção ───────────────────────────────────────────────

def test_intent_value_protection_wet():
    # Overpair em board molhado (flop) → value_protection
    r = classify_bet_intent(player_action='bet', street='flop', hero_cards=['Ad', 'Ah'],
                            board=['Kh', 'Qh', '2s'], equity=0.7, equity_adj=0.0, stack_bb=50, position='CO')
    assert r['intent'] == 'value_protection'
    print("OK  test_intent_value_protection_wet")


def test_intent_value_showdown_river():
    # No river não há proteção — value vira showdown
    r = classify_bet_intent(player_action='bet', street='river', hero_cards=['Ad', 'Ah'],
                            board=['Kh', 'Qh', '2s', '3d', '8c'], equity=0.7, equity_adj=0.0, stack_bb=50, position='CO')
    assert r['intent'] == 'value_showdown'
    print("OK  test_intent_value_showdown_river")


def test_intent_semi_bluff():
    # Nut flush draw, sem par feito, adj forte → semi_bluff
    r = classify_bet_intent(player_action='bet', street='flop', hero_cards=['As', '5s'],
                            board=['Ks', 'Qs', '2h'], equity=0.45, equity_adj=0.20, stack_bb=50, position='CO')
    assert r['intent'] == 'semi_bluff'
    print("OK  test_intent_semi_bluff")


def test_intent_middle_is_leak_without_gto():
    # Top pair fraco, sem nó GTO → "o meio", is_leak True
    r = classify_bet_intent(player_action='bet', street='flop', hero_cards=['Jc', 'Th'],
                            board=['6s', '9c', 'Jh'], equity=0.36, equity_adj=0.04, stack_bb=50, position='CO', gto=None)
    assert r['intent'] == 'middle'
    assert r['is_leak'] is True
    print("OK  test_intent_middle_is_leak_without_gto")


def test_intent_bluff():
    # Ar puro → bluff, is_leak (sem nó)
    r = classify_bet_intent(player_action='bet', street='flop', hero_cards=['2h', '7d'],
                            board=['Ac', 'Kh', '9s'], equity=0.15, equity_adj=0.02, stack_bb=50, position='CO', gto=None)
    assert r['intent'] == 'bluff'
    assert r['is_leak'] is True
    print("OK  test_intent_bluff")


def test_intent_middle_justified_by_gto():
    # Mesmo "meio" deixa de ser leak se o nó GTO aposta a mão com freq >= 0.25
    gto = {'available': True, 'strategy': [
        {'action': 'bet_50pct', 'frequency': 0.4}, {'action': 'check', 'frequency': 0.6}]}
    r = classify_bet_intent(player_action='bet', street='flop', hero_cards=['Jc', 'Th'],
                            board=['6s', '9c', 'Jh'], equity=0.36, equity_adj=0.04, stack_bb=50, position='CO', gto=gto)
    assert r['justified'] is True
    assert r['is_leak'] is False
    assert abs(r['gto_bet_freq'] - 0.4) < 1e-6
    print("OK  test_intent_middle_justified_by_gto")


def test_intent_value_never_leak():
    # Mão de value não é flagada como leak pelo intent (o gto_label cobre isso à parte)
    gto = {'available': True, 'strategy': [{'action': 'check', 'frequency': 1.0}]}
    r = classify_bet_intent(player_action='bet', street='flop', hero_cards=['Ad', 'Ah'],
                            board=['Kh', 'Td', 'Tc'], equity=0.62, equity_adj=0.04, stack_bb=50, position='CO', gto=gto)
    assert r['intent'].startswith('value')
    assert r['is_leak'] is False
    print("OK  test_intent_value_never_leak")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
