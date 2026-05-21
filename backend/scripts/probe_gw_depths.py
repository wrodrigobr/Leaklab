"""Mapeia os stack depths válidos no GTO Wizard MTT (MTTGeneralV2 9-max)."""
import sys, os
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")
os.environ["GTO_WIZARD_ENABLED"] = "true"

import requests

base = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
key  = os.environ.get("GTO_SOLVER_API_KEY", "")

valid = []
test_range = list(range(7, 131)) + [135, 140, 145, 150, 155, 160, 165, 170, 175, 180, 190, 200]
for stack in test_range:
    r = requests.post(f"{base}/gto-wizard", json={
        "street": "flop", "position": "BTN",
        "board": ["Ah", "Kd", "7c"],
        "hero_stack_bb": stack,
        "facing_size_bb": 0,
        "pot_bb": 4.5,
        "num_players": 9,
    }, headers={"x-api-key": key}, timeout=15)
    ok = r.status_code == 200
    if ok:
        valid.append(stack)
    status = "OK" if ok else "X "
    print(f"{stack:3d}bb: {status}", end="   ")
    if stack % 10 == 0:
        print()

print()
print("Valid depths:", valid)
