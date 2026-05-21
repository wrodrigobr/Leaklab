"""Mapeia depths válidos para MTTHUGeneral (2p)."""
import sys, os, requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

base = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
key  = os.environ.get("GTO_SOLVER_API_KEY", "")

valid = []
for stack in range(7, 131):
    r = requests.post(f"{base}/gto-wizard", json={
        "street": "flop", "position": "BTN",
        "board": ["Ah", "Kd", "7c"],
        "hero_stack_bb": stack, "facing_size_bb": 0, "pot_bb": 3,
        "num_players": 2,
    }, headers={"x-api-key": key}, timeout=15)
    ok = r.status_code == 200
    if ok:
        valid.append(stack)
    print(f"{stack:3d}bb: {'OK' if ok else 'X '}", end="   ")
    if stack % 10 == 0:
        print()

print()
print("Valid HU depths:", valid)
