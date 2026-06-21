"""test_ghost_table_invariants.py — trava de regressão do Ghost Table.

Codifica as invariantes confirmadas em auditorias adversariais (Fases 1-4) para que
mudanças futuras não reintroduzam as falhas corrigidas. CI-portável: usa mãos sintéticas
(ParsedHand) e a regex de ante, sem depender do banco de produção.

Invariantes travadas:
  - Raise grava o TO-TOTAL no bet do assento ('raises 48 to 88' => 88), não o incremento.
  - O matcher de target_facing PARA antes da ação do hero (hero nunca aparece já tendo agido).
  - Postflop first-to-act tem pote > 0 (carried_pot dos streets anteriores).
  - Antes entram no pote (dead money) e reduzem o stack; all-in pelo ante é capado em min(ante, stack).
  - ANTE_LINE_RE captura per-player, BB-ante (linha única), wording GG e separador de milhar.
  - legalActions: sem fold/call quando é grátis; sem check enfrentando aposta; sem bet preflop.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.models import ParsedHand, ParsedAction
from leaklab.hand_state_builder import build_table_state_at_decision
from leaklab.parser import ANTE_LINE_RE

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


# ── Port de legalActions (frontend GhostTable.tsx:43-59) — ação mecanicamente possível ──
def legal_actions(street, facing_bet, position):
    is_preflop = (street or "preflop") == "preflop"
    facing = float(facing_bet or 0) > 0
    pos = (position or "").upper()
    if is_preflop:
        if facing:
            return {"fold", "call", "raise", "jam"}
        if pos == "BB":
            return {"check", "raise", "jam"}      # free play: sem fold/call
        return {"fold", "call", "raise", "jam"}    # abrindo: sem check/bet
    if facing:
        return {"fold", "call", "raise", "jam"}
    return {"check", "bet", "jam"}                  # postflop first-to-act: sem fold/call/raise


# ── INV: raise grava to-total; hero não é ultrapassado (BUG B) ────────────────
hand_raise = ParsedHand(
    hand_id="R1", hero="Hero", button_seat=4, sb=20.0, bb=40.0,
    seats=[
        {"seat": 1, "name": "A", "stack": 2000.0},
        {"seat": 2, "name": "B", "stack": 2000.0},
        {"seat": 3, "name": "V", "stack": 2000.0},
        {"seat": 4, "name": "Hero", "stack": 2000.0},
    ],
    # botão seat4 (Hero) => SB=1, BB=2, UTG=3. V abre raise 48 to 88; hero enfrenta.
    actions=[
        ParsedAction("V", "preflop", "raises", 48.0, raw="V: raises 48 to 88"),
        ParsedAction("Hero", "preflop", "calls", 88.0, raw="Hero: calls 88"),  # após a decisão
    ],
)
stR = build_table_state_at_decision(hand_raise, "preflop", target_facing=88.0 / 40.0)
sR = {s["seat"]: s for s in stR["seats"]}
check(sR[3]["bet"] == 88.0, "raise grava TO-TOTAL (88), não incremento (48)")
check(sR[4]["hero"] is True and sR[4]["bet"] == 0.0 and sR[4]["folded"] is False,
      "hero não ultrapassado: bet 0, não foldado, é a vez dele")
check(any((not s["hero"]) and (not s["folded"]) for s in stR["seats"]),
      "há adversário ativo na mesa")

# ── INV: postflop first-to-act tem pote > 0 (BUG A — carried_pot) ─────────────
hand_pf = ParsedHand(
    hand_id="PF1", hero="Hero", button_seat=2, sb=20.0, bb=40.0,
    seats=[
        {"seat": 1, "name": "Hero", "stack": 2000.0},
        {"seat": 2, "name": "V", "stack": 2000.0},
    ],
    # HU: botão seat2 = SB = V; seat1 = BB = Hero. Preflop V call, Hero check; flop Hero age 1º.
    actions=[
        ParsedAction("V", "preflop", "calls", 20.0, raw="V: calls 20"),
        ParsedAction("Hero", "preflop", "checks", None, raw="Hero: checks"),
        ParsedAction("Hero", "flop", "checks", None, raw="Hero: checks"),  # decisão (1ª ação flop)
    ],
)
stPF = build_table_state_at_decision(hand_pf, "flop", target_facing=None)
check(stPF["pot"] > 0, f"postflop first-to-act: pote > 0 (carried), veio {stPF['pot']}")
check(stPF["pot"] == 80.0, f"pote = 2*BB (40+40) = 80, veio {stPF['pot']}")

# ── INV: antes no pote + reduzem stack (per-player) ──────────────────────────
hand_ante = ParsedHand(
    hand_id="AN1", hero="Hero", button_seat=1, sb=10.0, bb=20.0,
    seats=[
        {"seat": 1, "name": "Hero", "stack": 1000.0},
        {"seat": 2, "name": "A", "stack": 1000.0},
        {"seat": 3, "name": "B", "stack": 1000.0},
    ],
    antes={"Hero": 5.0, "A": 5.0, "B": 5.0},
    actions=[ParsedAction("Hero", "preflop", "raises", 40.0, raw="Hero: raises 40 to 60")],
)
stAN = build_table_state_at_decision(hand_ante, "preflop", target_facing=None)
sAN = {s["seat"]: s for s in stAN["seats"]}
# botão seat1 (Hero) => HU? n=3 => SB=seat2(A), BB=seat3(B). pote = 3 antes(15) + sb10 + bb20 = 45
check(stAN["pot"] == 45.0, f"pote = antes 15 + blinds 30 = 45, veio {stAN['pot']}")
check(sAN[1]["stack"] == 995.0, "stack do hero reduzido pelo ante (1000-5)")

# ── INV: all-in pelo ante é capado em min(ante, stack) ───────────────────────
hand_cap = ParsedHand(
    hand_id="CAP1", hero="Hero", button_seat=1, sb=10.0, bb=20.0,
    seats=[
        {"seat": 1, "name": "Hero", "stack": 5000.0},
        {"seat": 2, "name": "Shorty", "stack": 120.0},
        {"seat": 3, "name": "C", "stack": 5000.0},
    ],
    antes={"Hero": 200.0, "Shorty": 200.0, "C": 200.0},
    actions=[ParsedAction("Hero", "preflop", "raises", 40.0, raw="Hero: raises 40 to 60")],
)
stCAP = build_table_state_at_decision(hand_cap, "preflop", target_facing=None)
sCAP = {s["name"]: s for s in stCAP["seats"]}
check(sCAP["Shorty"]["stack"] == 0.0, "shorty all-in pelo ante: stack 0")
# Shorty contribui no máximo 120 no total (SB 10 + ante 110). pote = Hero200 + Shorty120 + C200 + BB20 = 540
check(stCAP["pot"] == 540.0, f"ante capado, sem overcount: pote 540, veio {stCAP['pot']}")

# ── INV: ANTE_LINE_RE captura os formatos reais ──────────────────────────────
def ante_amt(line):
    m = ANTE_LINE_RE.match(line)
    return float(m.group("amount").replace(",", "")) if m else None

check(ante_amt("phpro: posts the ante 40") == 40.0, "ante per-player 'posts the ante 40'")
check(ante_amt("Carol: posts the ante 200") == 200.0, "BB-ante linha única 'posts the ante 200'")
check(ante_amt("c6d33e12: posts ante 12") == 12.0, "wording GG 'posts ante 12'")
check(ante_amt("X: posts the ante 1,200") == 1200.0, "ante com separador de milhar")
check(ante_amt("V: raises 48 to 88") is None, "linha de raise NÃO é ante")
check(ante_amt("Y: calls 88") is None, "linha de call NÃO é ante")

# ── INV: mãos SEM ante são no-op (antes={} não altera nada) ──────────────────
hand_noante = ParsedHand(
    hand_id="NA1", hero="Hero", button_seat=1, sb=10.0, bb=20.0,
    seats=[{"seat": 1, "name": "Hero", "stack": 1000.0}, {"seat": 2, "name": "A", "stack": 1000.0}],
    actions=[ParsedAction("A", "preflop", "calls", 20.0, raw="A: calls 20")],
)
stNA = build_table_state_at_decision(hand_noante, "preflop", target_facing=None)
sNA = {s["seat"]: s for s in stNA["seats"]}
check(sNA[1]["stack"] == 990.0, "sem ante: stack só reduzido pelo blind (BB? HU botão=SB)")

# ── INV: legalActions — sem fold quando é grátis; sem check enfrentando aposta ──
check("fold" not in legal_actions("preflop", 0, "BB"), "BB grátis: NÃO oferece fold")
check("call" not in legal_actions("preflop", 0, "BB"), "BB grátis: NÃO oferece call")
check(legal_actions("preflop", 0, "BB") == {"check", "raise", "jam"}, "BB grátis: check/raise/jam")
check("fold" not in legal_actions("flop", 0, "BTN"), "postflop first-to-act: NÃO oferece fold")
check(legal_actions("flop", 0, "BTN") == {"check", "bet", "jam"}, "postflop livre: check/bet/jam")
check("check" not in legal_actions("flop", 4.0, "BTN"), "enfrentando aposta: NÃO oferece check")
check("bet" not in legal_actions("preflop", 0, "CO"), "preflop abrindo: NÃO oferece bet (é raise)")

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
