import sqlite3, os, json, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from leaklab.gto_utils import compute_spot_hash, bet_bucket, stack_bucket

db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db'))

rows = db.execute(
    "SELECT id, spot_hash, street, board, position, stack_bucket, gto_action, strategy_json "
    "FROM gto_nodes WHERE street IN ('turn','river') ORDER BY id DESC LIMIT 12"
).fetchall()
print("=== EXISTING TURN/RIVER NODES ===")
for r in rows:
    strat = list(json.loads(r[7]).keys()) if r[7] else []
    print(f"  id={r[0]} hash={r[1]} {r[2]} pos={r[4]} stack_bkt={r[5]} action={r[6]} strat={strat}")

board_turn  = ['5c','6c','8h','Ts']
board_river = ['5c','6c','8h','Ts','Qc']
position = 'BB'
stack_bb = 20.1
facing_bb = 1.0

h_turn       = compute_spot_hash('turn',  position, board_turn,  [],  stack_bb, facing_bb)
h_turn_nf    = compute_spot_hash('turn',  position, board_turn,  [],  stack_bb, 0.0)
h_river      = compute_spot_hash('river', position, board_river, [],  stack_bb, facing_bb)
h_river_nf   = compute_spot_hash('river', position, board_river, [],  stack_bb, 0.0)

print(f"\n=== EXPECTED HASHES (stack={stack_bb} facing={facing_bb}bb) ===")
print(f"stack_bucket={stack_bucket(stack_bb)}  bet_bucket={bet_bucket(facing_bb)}")
print(f"turn  +facing  {h_turn}")
print(f"turn  no_facing {h_turn_nf}")
print(f"river +facing  {h_river}")
print(f"river no_facing {h_river_nf}")

print("\n=== LOOKUP RESULTS ===")
for h, label in [(h_turn,'turn+facing'), (h_turn_nf,'turn_nf'), (h_river,'river+facing'), (h_river_nf,'river_nf')]:
    row = db.execute("SELECT id, gto_action, strategy_json FROM gto_nodes WHERE spot_hash=?", (h,)).fetchone()
    if row:
        strat = list(json.loads(row[2]).keys()) if row[2] else []
        print(f"  FOUND {label}: id={row[0]} action={row[1]} strat={strat}")
    else:
        print(f"  NOT FOUND {label}")

# Check solver queue
queue = db.execute(
    "SELECT spot_hash, status, priority FROM solver_queue ORDER BY id DESC LIMIT 10"
).fetchall()
print("\n=== SOLVER QUEUE (last 10) ===")
for q in queue:
    print(f"  hash={q[0]} status={q[1]} priority={q[2]}")

db.close()
