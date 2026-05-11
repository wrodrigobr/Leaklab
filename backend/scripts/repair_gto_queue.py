"""
Repara gto_solver_queue:
- Reseta done-sem-node para pending (hash mismatch do bug anterior)
- Mantém failed como failed (dados corrompidos — não vale retentar)
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.schema import init_db, get_conn

init_db()
conn = get_conn()

# done entries with no matching gto_nodes row (hash mismatch from old bug)
r1 = conn.execute(
    "UPDATE gto_solver_queue SET status='pending' "
    "WHERE status='done' AND spot_hash NOT IN (SELECT spot_hash FROM gto_nodes)"
)
conn.commit()

# Validate pending spots — discard ones with obviously bad data
rows = conn.execute(
    "SELECT spot_hash, spot_json FROM gto_solver_queue WHERE status='pending'"
).fetchall()

discarded = 0
for spot_hash, spot_json in rows:
    try:
        spot = json.loads(spot_json)
        board = spot.get('board', [])
        street = spot.get('street', '')
        pot = float(spot.get('pot_bb', 0))

        bad = False
        # river needs 5 cards, turn needs 4, flop needs 3
        expected = {'flop': 3, 'turn': 4, 'river': 5}.get(street, 3)
        if len(board) < expected:
            bad = True
        # pot > 500bb is almost certainly a parsing artifact
        if pot > 500:
            bad = True

        if bad:
            conn.execute(
                "UPDATE gto_solver_queue SET status='failed' WHERE spot_hash=?",
                (spot_hash,)
            )
            discarded += 1
    except Exception:
        pass

conn.commit()

stats = {r[0]: r[1] for r in conn.execute(
    'SELECT status, COUNT(*) FROM gto_solver_queue GROUP BY status'
).fetchall()}
conn.close()

print('Resetados done-sem-no para pending: ' + str(r1.rowcount))
print('Descartados por dados invalidos: ' + str(discarded))
print('Fila final: ' + str(stats))
