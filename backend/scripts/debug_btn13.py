"""Diagnóstico do spot BTN 13bb 4p facing_bet=1.6."""
import sys, os, requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

base = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
key  = os.environ.get("GTO_SOLVER_API_KEY", "")

board = ["Ad", "8h", "Jc"]

# facing_bet variants com timeout maior
for facing in [1.6, 0.0, 1.0, 2.0]:
    r = requests.post(f"{base}/gto-wizard", json={
        "street": "flop", "position": "BTN", "board": board,
        "hero_stack_bb": 13.2, "facing_size_bb": facing,
        "pot_bb": 4.6, "num_players": 4,
    }, headers={"x-api-key": key}, timeout=45)
    d = r.json() if r.content else {}
    if d.get("found"):
        strat = d["strategy"]
        top = max(strat, key=lambda x: x["frequency"])
        print(f"facing={facing:.1f}bb: OK -> {top['action']} {top['frequency']*100:.0f}%")
    else:
        print(f"facing={facing:.1f}bb: FALHOU -> {d.get('error')}")
