"""test_table_state.py — reconstrução do estado por assento (Ghost Table visual).

Valida build_table_state_at_decision: folds e botão fiéis, blinds postados,
bets/stacks por assento no ponto da decisão do hero.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.models import ParsedHand, ParsedAction
from leaklab.hand_state_builder import build_table_state_at_decision

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


# ── Cenário: 5-handed, botão seat6, blinds 20/40, UTG (seat3) all-in 260 ──────
hand = ParsedHand(
    hand_id="T1", hero="Hero", button_seat=6, sb=20.0, bb=40.0,
    seats=[
        {"seat": 1, "name": "A", "stack": 665.0},
        {"seat": 2, "name": "B", "stack": 370.0},
        {"seat": 3, "name": "C", "stack": 300.0},
        {"seat": 4, "name": "Hero", "stack": 120.0},
        {"seat": 6, "name": "D", "stack": 345.0},
    ],
    actions=[
        ParsedAction("C", "preflop", "all-in", 260.0),
        ParsedAction("Hero", "preflop", "calls", 120.0),   # após o ponto da decisão
    ],
)

st = build_table_state_at_decision(hand, "preflop")
seats = {s["seat"]: s for s in st["seats"]}

check(st["button"] == 6, "botão deve ser seat6")
check(seats[1]["bet"] == 20.0, "seat1 = SB com bet 20")
check(seats[1]["stack"] == 645.0, "seat1 stack 665-20=645")
check(seats[2]["bet"] == 40.0, "seat2 = BB com bet 40")
check(seats[3]["bet"] == 260.0, "seat3 (UTG) all-in bet 260")
check(seats[3]["stack"] == 40.0, "seat3 stack 300-260=40")
check(seats[4]["hero"] is True, "seat4 = hero")
check(seats[4]["bet"] == 0.0, "hero ainda não agiu (bet 0)")
check(all(not s["folded"] for s in st["seats"]), "ninguém foldou antes da decisão")

# ── Folds antes da decisão marcam folded ──────────────────────────────────────
hand2 = ParsedHand(
    hand_id="T2", hero="Hero", button_seat=4, sb=10.0, bb=20.0,
    seats=[
        {"seat": 1, "name": "A", "stack": 500.0},
        {"seat": 2, "name": "B", "stack": 500.0},
        {"seat": 3, "name": "C", "stack": 500.0},
        {"seat": 4, "name": "Hero", "stack": 500.0},
    ],
    # botão seat4 (Hero) → SB=seat1, BB=seat2, UTG=seat3. O raiser é o UTG (não-blind).
    actions=[
        ParsedAction("C", "preflop", "raises", 60.0),     # UTG abre (bet limpo = 60)
        ParsedAction("A", "preflop", "folds", None),       # SB folda
        ParsedAction("B", "preflop", "folds", None),       # BB folda
        ParsedAction("Hero", "preflop", "calls", 60.0),    # após o ponto da decisão
    ],
)
st2 = build_table_state_at_decision(hand2, "preflop")
s2 = {s["seat"]: s for s in st2["seats"]}
check(s2[1]["folded"] is True, "seat1 (SB) foldou antes da decisão")
check(s2[2]["folded"] is True, "seat2 (BB) foldou antes da decisão")
check(s2[3]["folded"] is False and s2[3]["bet"] == 60.0, "seat3 (UTG raiser) ativo bet 60")
check(s2[4]["hero"] is True and s2[4]["folded"] is False, "hero ativo")

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
