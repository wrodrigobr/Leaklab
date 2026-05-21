"""Diagnóstico de spots que retornam SEM RESPOSTA."""
import sys, os, requests
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

base = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
key  = os.environ.get("GTO_SOLVER_API_KEY", "")

spots = [
    ("SB 15bb 2p HU",    "flop",  "SB",    ["Ad","6c","2h"],        15, 0, 2),
    ("SB 45bb 3p",       "turn",  "SB",    ["6d","7h","8s","4h"],   45, 0, 3),
    ("SB 38bb 4p",       "flop",  "SB",    ["Ks","8s","8d"],        38, 0, 4),
    ("BTN 13bb 4p",      "flop",  "BTN",   ["Ad","8h","Jc"],        13, 0, 4),
    ("BTN 23bb 5p turn", "turn",  "BTN",   ["2h","6s","7c","9d"],   23, 0, 5),
    ("BB 8bb 7p",        "flop",  "BB",    ["6s","7c","2s"],         8, 0, 7),
    ("BB 34bb 7p",       "flop",  "BB",    ["Qs","7c","4d"],        34, 0, 7),
    ("CO 34bb 8p",       "flop",  "CO",    ["4s","9h","7c"],        34, 0, 8),
    ("UTG+2 24bb 8p",    "flop",  "UTG+2", ["As","4h","6s"],        24, 0, 8),
    ("LJ 24bb 8p",       "flop",  "LJ",    ["As","4h","6s"],        24, 0, 8),
    ("SB 37bb 8p turn",  "turn",  "SB",    ["6c","Ad","7h","7d"],   37, 0, 8),
    ("UTG+2 24bb 8p turn", "turn","UTG+2", ["5h","4s","3h","2c"],   24, 0, 8),
]

for lbl, st, pos, board, stk, fc, np_ in spots:
    r = requests.post(f"{base}/gto-wizard", json={
        "street": st, "position": pos, "board": board,
        "hero_stack_bb": stk, "facing_size_bb": fc, "pot_bb": 4,
        "num_players": np_,
    }, headers={"x-api-key": key}, timeout=15)
    d = r.json() if r.content else {}
    err = d.get("error", "found" if d.get("found") else "?")
    print(f"{lbl}: HTTP {r.status_code} -> {err}")
