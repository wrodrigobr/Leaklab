"""
Regex de bounty PKO no parser (parser.py). Regressão do torneio 4010762312 (PokerStars),
cujo formato real "(chips, $0.50 bounty)" não casava com nenhuma das 2 regex antigas.
Cobre os 3 formatos: PS antigo, GGPoker, PS real.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from leaklab.parser import SEAT_BOUNTY_PS_RE, SEAT_BOUNTY_GG_RE, SEAT_BOUNTY_PS2_RE


def _match(line):
    return (SEAT_BOUNTY_PS_RE.match(line) or SEAT_BOUNTY_GG_RE.match(line)
            or SEAT_BOUNTY_PS2_RE.match(line))


def test_ps_old_format():
    # "Seat 3: phpro (1500 in chips) bounty $0.25" — bounty fora dos parênteses
    m = _match("Seat 3: phpro (1500 in chips) bounty $0.25")
    assert m and m.group(1).strip() == 'phpro' and float(m.group(2)) == 0.25
    print("OK  test_ps_old_format")


def test_gg_format():
    # "Seat 3: phpro (1500 in chips, bounty $0.25)" — "bounty" antes da quantia
    m = _match("Seat 3: phpro (1500 in chips, bounty $0.25)")
    assert m and float(m.group(2)) == 0.25
    print("OK  test_gg_format")


def test_ps_real_format():
    # REGRESSÃO 4010762312: "(2735 in chips, $0.50 bounty)" — quantia antes de "bounty", dentro
    m = _match("Seat 1: Jotaninja (2735 in chips, $0.50 bounty) ")
    assert m and m.group(1).strip() == 'Jotaninja' and float(m.group(2)) == 0.50
    print("OK  test_ps_real_format")


def test_ps_real_whole_dollar():
    # bounty inteiro sem decimais: "$1 bounty"
    m = _match("Seat 2: andrejacare (11752 in chips, $1 bounty) ")
    assert m and float(m.group(2)) == 1.0
    print("OK  test_ps_real_whole_dollar")


def test_ps_real_name_with_space():
    m = _match("Seat 3: Neo Eugenio (1530 in chips, $0.50 bounty) ")
    assert m and m.group(1).strip() == 'Neo Eugenio'
    print("OK  test_ps_real_name_with_space")


def test_real_tournament_parse():
    # Integração: o HH real (header + seats) produz bounties não-vazio.
    hh = (
        "PokerStars Hand #261260686273: Tournament #4010762312, $0.48+$0.50+$0.12 USD "
        "Hold'em No Limit - Level V (40/80) - 2026/06/26 18:10:42 ET\n"
        "Table '4010762312 10' 9-max Seat #1 is the button\n"
        "Seat 1: Jotaninja (2735 in chips, $0.50 bounty) \n"
        "Seat 4: phpro (3000 in chips, $0.50 bounty) \n"
        "Jotaninja: posts small blind 40\n"
        "phpro: posts big blind 80\n"
        "*** HOLE CARDS ***\n"
        "Dealt to phpro [Ah Kh]\n"
        "Jotaninja: folds\n"
        "phpro: collected 80\n"
        "*** SUMMARY ***\n"
    )
    from leaklab.parser import parse_hand_history
    hands = parse_hand_history(hh)
    assert hands, "nenhuma mão parseada"
    b = getattr(hands[0], 'bounties', {}) or {}
    assert b.get('phpro') == 0.50 and b.get('Jotaninja') == 0.50, f"bounties não extraídos: {b}"
    print("OK  test_real_tournament_parse")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
