"""Test GTO lookup for pending hand requests."""
import sys, os, json, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(name)s: %(message)s')

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

import os
print("GTO_SOLVER_URL:", os.environ.get('GTO_SOLVER_URL', 'NOT SET'))

from database.repositories import get_conn, _fetchall, _adapt
from leaklab.gto_solver import lookup_gto, _call_remote_solver

conn = get_conn()

# Get decisions for hand 257045919085 without gto_label
rows = _fetchall(conn, _adapt("""
    SELECT d.id, d.hand_id, d.street, d.action_taken, d.gto_label, d.gto_action,
           d.pot_size, d.stack_bb, d.position, d.facing_bet,
           d.board, d.hero_cards
    FROM decisions d
    JOIN tournaments t ON d.tournament_id = t.id
    WHERE d.hand_id = ?
    ORDER BY d.id
"""), ('257045919085',))

print(f"\nDecisions for hand 257045919085: {len(rows)}")
for r in rows:
    print(f"  id={r['id']} street={r['street']} action={r['action_taken']} "
          f"gto_label={r['gto_label']} stack={r['stack_bb']}")

print("\n--- Testing lookup_gto for decisions without label ---")
for r in rows:
    if r['street'] == 'preflop':
        continue
    if r['gto_label']:
        print(f"  [{r['street']}] already has label={r['gto_label']} -- skip")
        continue

    try:
        board = json.loads(r['board']) if r['board'] else []
        hero_hand = json.loads(r['hero_cards']) if r['hero_cards'] else []
    except Exception:
        board, hero_hand = [], []

    print(f"\n  Testing [{r['street']}] action={r['action_taken']} stack={r['stack_bb']}")
    print(f"    board={board} hand={hero_hand} pos={r['position']} facing={r['facing_bet']}")

    result = lookup_gto(
        street=r['street'] or 'flop',
        position=r['position'] or 'BTN',
        board=board,
        hero_hand=hero_hand,
        hero_stack_bb=float(r['stack_bb'] or 20),
        facing_size_bb=float(r['facing_bet'] or 0),
        pot_bb=float(r['pot_size'] or 4),
    )
    print(f"    -> found={result['found']} source={result['source']} queued={result['queued']}")
    if result.get('strategy'):
        print(f"    -> strategy: {result['strategy'][:2]}")

conn.close()
