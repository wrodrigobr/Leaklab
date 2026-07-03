"""GGPoker em níveis altos escreve o blind com separador de milhar: "Level14(1,500/3,000(350))".
O SB_RE usava \\d+ e parava no "1,500" → sb/bb=None → potBb/stack_bb caíam em FICHAS (fallback
pot/1) → nós GTO degenerados (all-in fake, exploit≈0.01). Regressão: o parser tem que extrair
1500/3000 e o pipeline normalizar o pote em BB.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.parser import SB_RE, _pg_num, parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand


def test_sb_re_accepts_thousands_separator():
    cases = {
        '(1,500/3,000(350))': (1500.0, 3000.0, 350.0),   # GG milhar + ante
        '(10/20)':            (10.0, 20.0, None),         # PokerStars
        '(400/800(120))':     (400.0, 800.0, 120.0),      # GG sem milhar
        '(2 000/4 000)':      (2000.0, 4000.0, None),     # separador espaço
        '(1,500/3,000)':      (1500.0, 3000.0, None),     # milhar sem ante
    }
    for s, (esb, ebb, eante) in cases.items():
        m = SB_RE.search(s)
        assert m, f"não casou: {s}"
        assert _pg_num(m.group(1)) == esb, (s, m.group(1))
        assert _pg_num(m.group(2)) == ebb, (s, m.group(2))
        got_ante = _pg_num(m.group(3)) if m.group(3) else None
        assert got_ante == eante, (s, got_ante)
    print("OK  test_sb_re_accepts_thousands_separator")


_GG_HAND = """Poker Hand #TM6113122845: Tournament #293241904, Fifty Stack $5.50 Hold'em No Limit - Level14(1,500/3,000(350)) - 2026/06/25 08:02:53
Table '293241904 12' 9-max Seat #1 is the button
Seat 1: Hero (90000 in chips)
Seat 2: villain2 (85000 in chips)
Seat 3: villain3 (120000 in chips)
Hero: posts small blind 1,500
villain2: posts big blind 3,000
Seat 1: Hero posts the ante 350
Seat 2: villain2 posts the ante 350
Seat 3: villain3 posts the ante 350
*** HOLE CARDS ***
Dealt to Hero [Ah Kh]
villain3: folds
Hero: raises 3,000 to 6,000
villain2: calls 3,000
*** FLOP *** [Qs 2h 9s]
villain2: checks
Hero: bets 4,000
villain2: calls 4,000
*** SUMMARY ***
"""


def test_parser_extracts_bb_from_gg_hand():
    hands = parse_hand_history(_GG_HAND)
    assert hands, "não parseou nenhuma mão"
    h = hands[0]
    assert h.bb == 3000.0, f"bb={h.bb} (esperado 3000)"
    assert h.sb == 1500.0, f"sb={h.sb} (esperado 1500)"
    print("OK  test_parser_extracts_bb_from_gg_hand")


def test_potbb_is_in_bb_not_chips():
    """Com o bb correto, o potBb do spot postflop fica em BB (ordem de grandeza baixa),
    não em fichas (milhares) — que era o que estourava o SPR e degenerava o nó."""
    h = parse_hand_history(_GG_HAND)[0]
    dis = build_decision_inputs_for_hand(h)
    post = [d for d in dis if (d.get('street') or '').lower() == 'flop']
    assert post, "sem decisão de flop"
    pot_bb = float(post[0].get('spot', {}).get('potBb') or 0)
    # pote real no flop ~ 15bb (6000+6000 pre + antes/blinds). Em fichas seria ~15000.
    assert 0 < pot_bb < 100, f"potBb={pot_bb} parece estar em fichas, não BB"
    print(f"OK  test_potbb_is_in_bb_not_chips (potBb={pot_bb})")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
