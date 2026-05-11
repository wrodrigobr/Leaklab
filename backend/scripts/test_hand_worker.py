"""Simulate exactly what _process_gto_hand_request does for hand 257045919085."""
import sys, os, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s: %(message)s')

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

import os
print("GTO_SOLVER_URL:", os.environ.get('GTO_SOLVER_URL', 'NOT SET'))

from database.repositories import get_conn, _fetchall, _fetchone, _adapt
from database.schema import get_conn as _gc
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.parser import parse_pokerstars_file_from_text

HAND_ID = '257045919085'

conn = _gc()
# Get the request info
req = _fetchone(conn, _adapt(
    "SELECT * FROM gto_hand_requests WHERE hand_id = ? ORDER BY id DESC LIMIT 1"
), (HAND_ID,))
if not req:
    print("No hand request found for hand", HAND_ID)
    sys.exit(1)

print(f"Request: id={req['id']} status={req['status']} tournament_id={req['tournament_id']}")

# Get tournament raw_text
t = _fetchone(conn, _adapt("SELECT * FROM tournaments WHERE id = ?"), (req['tournament_id'],))
if not t or not t.get('raw_text'):
    print("Tournament not found or no raw_text")
    sys.exit(1)

raw_text = t['raw_text']
print(f"raw_text length: {len(raw_text)}")

# Parse hands
hands = parse_pokerstars_file_from_text(raw_text)
target = next((h for h in hands if str(h.hand_id) == str(HAND_ID)), None)
if not target:
    print(f"Hand {HAND_ID} not found in raw_text!")
    sys.exit(1)

print(f"Found hand: {target.hand_id}")

# Get DB decisions
db_decisions = [d for d in _fetchall(conn, _adapt(
    "SELECT * FROM decisions WHERE tournament_id = ?"
), (req['tournament_id'],))
                if str(d.get('hand_id')) == str(HAND_ID)]

print(f"DB decisions for this hand: {len(db_decisions)}")
for d in db_decisions:
    print(f"  id={d['id']} street={d['street']} action={d['action_taken']} gto_label={d['gto_label']}")

def _norm(a):
    return a.rstrip('s') if a and a.endswith('s') else (a or '')

db_index = {(_norm(d.get('street', '')), _norm(d.get('action_taken', ''))): d
            for d in db_decisions}

print("\n--- build_decision_inputs_for_hand output ---")
for di in build_decision_inputs_for_hand(target):
    street = di['street']
    if street not in ('flop', 'turn', 'river'):
        continue

    ctx = di.get('context', {})
    key = (_norm(street), _norm(di.get('player_action', '') or ''))
    db_dec = db_index.get(key)

    spot = di.get('spot', {})
    board = spot.get('board', [])
    hero_hand = di.get('hero_cards', [])
    position = spot.get('position', ctx.get('position', ''))
    stack = spot.get('effectiveStackBb', ctx.get('heroStackBb', 20.0))
    facing = float(spot.get('facingSize', 0) or 0)
    pot = float(spot.get('potSize', 0) or 4)

    print(f"\n  street={street} action={di.get('player_action')} key={key}")
    print(f"    board={board} hand={hero_hand} pos={position} stack={stack} facing={facing} pot={pot}")
    print(f"    db_dec match: {'YES id='+str(db_dec['id']) if db_dec else 'NO'}")
    if db_dec and db_dec.get('gto_label'):
        print(f"    already has label={db_dec['gto_label']} -> would skip")
    elif not db_dec:
        print(f"    no DB match -> would skip")
    else:
        print(f"    -> would call lookup_gto with board={board}")

conn.close()
