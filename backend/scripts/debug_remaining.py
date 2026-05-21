import sys, os, requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

base = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
key  = os.environ.get("GTO_SOLVER_API_KEY", "")

spots = [
    ("SB 24bb 2p turn [Jh Ks 9c 4h]",   "turn",  "SB", ["Jh","Ks","9c","4h"],        24, 0, 2),
    ("SB 24bb 2p river [Jh Ks 9c 4h Qc]","river", "SB", ["Jh","Ks","9c","4h","Qc"],   24, 0, 2),
    ("BTN 13bb 4p flop [Ad 8h Jc]",       "flop",  "BTN",["Ad","8h","Jc"],             13, 0, 4),
    # variantes
    ("BTN 14bb 4p flop [Ad 8h Jc]",       "flop",  "BTN",["Ad","8h","Jc"],             14, 0, 4),
    ("SB 24bb 2p flop [Jh Ks 9c]",        "flop",  "SB", ["Jh","Ks","9c"],             24, 0, 2),
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
