"""Testa gametypes menores diretamente no servidor GW para diagnosticar 403."""
import sys, os, requests
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

GW_SPOT_SOL = "https://api.gtowizard.com/v1/solutions/spot/"
GW_APP      = "https://app.gtowizard.com"

# Obter headers de auth do servidor local
base = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
key  = os.environ.get("GTO_SOLVER_API_KEY", "")
status = requests.get(f"{base}/gw-status", headers={"x-api-key": key}, timeout=5).json()
print("Auth:", status)

# Pegar headers via endpoint interno - precisamos dos headers reais
# Vamos testar com diferentes configs de gametype
configs = [
    # (gametype, n, positions_sample, open_size)
    ("MTTHUGeneral",   2, ["BTN","BB"],                             2.5),
    ("MTTGeneral_3m",  3, ["BTN","SB","BB"],                        2.0),
    ("MTTGeneral_4m",  4, ["CO","BTN","SB","BB"],                   2.0),
    ("MTTGeneral_5m",  5, ["HJ","CO","BTN","SB","BB"],              2.0),
    ("MTT6mSimple",    6, ["LJ","HJ","CO","BTN","SB","BB"],         2.0),
    ("MTTGeneral_7m",  7, ["UTG","LJ","HJ","CO","BTN","SB","BB"],   2.0),
    ("MTTGeneral_8m",  8, ["UTG","UTG+1","LJ","HJ","CO","BTN","SB","BB"], 2.0),
    ("MTTGeneralV2",   9, ["UTG","UTG+1","UTG+2","LJ","HJ","CO","BTN","SB","BB"], 2.0),
]

for gametype, n, positions, open_s in configs:
    btn_idx = positions.index("BTN") if "BTN" in positions else n-3
    bb_idx  = positions.index("BB")
    # BTN opens, all others fold except BB calls
    actions = []
    for i, p in enumerate(positions):
        if p == "BTN":
            actions.append(f"R{int(open_s)}")
        elif p == "BB":
            actions.append("C")
        elif i < btn_idx:
            actions.append("F")
    preflop = "-".join(actions[:-1])  # exclude BB call for now — just preflop_actions up to BB

    # Correct: full sequence BTN vs BB
    seq_parts = []
    for p in positions[:-1]:  # exclude BB
        if p == "BTN":
            seq_parts.append(f"R{int(open_s)}")
        else:
            seq_parts.append("F")
    seq_parts.append("C")  # BB calls
    full_seq = "-".join(seq_parts)

    # Use BTN for IP, BB for OOP
    stacks = "-".join([f"20.125"] * n)
    params = {
        "gametype": gametype,
        "depth": "20.125",
        "stacks": stacks,
        "preflop_actions": full_seq,
        "flop_actions": "",
        "turn_actions": "",
        "river_actions": "",
        "board": "AhKd7c",
    }
    # Direct to GW API would require auth headers - test via our server proxy instead
    r = requests.post(f"{base}/gto-wizard", json={
        "street": "flop", "position": "BTN",
        "board": ["Ah","Kd","7c"],
        "hero_stack_bb": 20, "facing_size_bb": 0, "pot_bb": 4,
        "num_players": n,
    }, headers={"x-api-key": key}, timeout=15)
    d = r.json() if r.content else {}
    err = d.get("error", "found" if d.get("found") else "?")
    print(f"{gametype} ({n}p) BTN 20bb flop: HTTP {r.status_code} -> {err}")
