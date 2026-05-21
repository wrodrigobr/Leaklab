"""Diagnóstico MTTHUGeneral — testa variações de nome e parametros."""
import sys, os, requests, json
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

base = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
key  = os.environ.get("GTO_SOLVER_API_KEY", "")

# Testar via endpoint /gto-wizard mas passando parametros diretos via query (debug mode)
# Na verdade vamos testar o que o servidor constroi e manda pro GW

# Primeiro: verificar o que o servidor gera para 2p
r = requests.post(f"{base}/gto-wizard", json={
    "street": "flop", "position": "BTN",
    "board": ["Ah","Kd","7c"],
    "hero_stack_bb": 20, "facing_size_bb": 0, "pot_bb": 3,
    "num_players": 2,
}, headers={"x-api-key": key}, timeout=15)
print(f"BTN 20bb 2p: {r.status_code} -> {r.text[:200]}")

# 2p com BB
r = requests.post(f"{base}/gto-wizard", json={
    "street": "flop", "position": "BB",
    "board": ["Ah","Kd","7c"],
    "hero_stack_bb": 20, "facing_size_bb": 0, "pot_bb": 3,
    "num_players": 2,
}, headers={"x-api-key": key}, timeout=15)
print(f"BB 20bb 2p: {r.status_code} -> {r.text[:200]}")

# Testar 2p com open_size 2.5 (HU tipicamente usa 2.5x)
# Vamos checar diretamente o HAR para ver o gametype HU
# Probe varios stacks para BTN 2p
for stack in [8, 10, 15, 20, 25]:
    for pos in ["BTN", "BB"]:
        r = requests.post(f"{base}/gto-wizard", json={
            "street": "flop", "position": pos,
            "board": ["Ah","Kd","7c"],
            "hero_stack_bb": stack, "facing_size_bb": 0, "pot_bb": 3,
            "num_players": 2,
        }, headers={"x-api-key": key}, timeout=15)
        print(f"{pos} {stack}bb 2p: {r.status_code}")
