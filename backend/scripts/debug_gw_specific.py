"""Testa spots especificos com combinacoes para diagnosticar 403."""
import sys, os, requests
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

base = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
key  = os.environ.get("GTO_SOLVER_API_KEY", "")

def test(label, **kwargs):
    r = requests.post(f"{base}/gto-wizard", json=kwargs,
                      headers={"x-api-key": key}, timeout=15)
    d = r.json() if r.content else {}
    err = d.get("error", "found" if d.get("found") else "?")
    print(f"{label}: {r.status_code} -> {err}")

# SB em gametypes menores
test("SB 20bb 3p flop",  street="flop", position="SB", board=["Ah","Kd","7c"], hero_stack_bb=20, facing_size_bb=0, pot_bb=4, num_players=3)
test("SB 20bb 4p flop",  street="flop", position="SB", board=["Ah","Kd","7c"], hero_stack_bb=20, facing_size_bb=0, pot_bb=4, num_players=4)
test("SB 20bb 5p flop",  street="flop", position="SB", board=["Ah","Kd","7c"], hero_stack_bb=20, facing_size_bb=0, pot_bb=4, num_players=5)
test("BB 20bb 7p flop",  street="flop", position="BB", board=["Ah","Kd","7c"], hero_stack_bb=20, facing_size_bb=0, pot_bb=4, num_players=7)

# Stacks problematicos em 8p
test("SB 37bb 8p turn",  street="turn", position="SB", board=["6c","Ad","7h","7d"], hero_stack_bb=37, facing_size_bb=0, pot_bb=6, num_players=8)
test("SB 38bb 8p turn",  street="turn", position="SB", board=["6c","Ad","7h","7d"], hero_stack_bb=38, facing_size_bb=0, pot_bb=6, num_players=8)
test("CO 34bb 8p flop",  street="flop", position="CO", board=["4s","9h","7c"], hero_stack_bb=34, facing_size_bb=0, pot_bb=5, num_players=8)
test("CO 35bb 8p flop",  street="flop", position="CO", board=["4s","9h","7c"], hero_stack_bb=35, facing_size_bb=0, pot_bb=5, num_players=8)

# UTG+2 24bb 8p (maps to LJ)
test("LJ 24bb 8p flop",  street="flop", position="LJ",    board=["As","4h","6s"], hero_stack_bb=24, facing_size_bb=0, pot_bb=4, num_players=8)
test("LJ 25bb 8p flop",  street="flop", position="LJ",    board=["As","4h","6s"], hero_stack_bb=25, facing_size_bb=0, pot_bb=4, num_players=8)
test("UTG+2 24bb 8p flop",street="flop", position="UTG+2",board=["As","4h","6s"], hero_stack_bb=24, facing_size_bb=0, pot_bb=4, num_players=8)

# BB turn em 7p
test("BB 34bb 7p flop",  street="flop", position="BB", board=["Qs","7c","4d"], hero_stack_bb=34, facing_size_bb=0, pot_bb=5, num_players=7)
test("BB 35bb 7p flop",  street="flop", position="BB", board=["Qs","7c","4d"], hero_stack_bb=35, facing_size_bb=0, pot_bb=5, num_players=7)

# MTTHUGeneral
test("BTN 20bb 2p flop", street="flop", position="BTN", board=["Ah","Kd","7c"], hero_stack_bb=20, facing_size_bb=0, pot_bb=3, num_players=2)
test("BB 20bb 2p flop",  street="flop", position="BB",  board=["Ah","Kd","7c"], hero_stack_bb=20, facing_size_bb=0, pot_bb=3, num_players=2)
test("SB 20bb 2p flop",  street="flop", position="SB",  board=["Ah","Kd","7c"], hero_stack_bb=20, facing_size_bb=0, pot_bb=3, num_players=2)
