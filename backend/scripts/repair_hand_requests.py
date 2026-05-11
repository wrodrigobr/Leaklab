"""Reset solver_queued hand requests back to pending for reprocessing."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.schema import init_db, get_conn

init_db()
conn = get_conn()

r = conn.execute(
    "UPDATE gto_hand_requests SET status='pending', decisions_done=0 WHERE status='solver_queued'"
)
conn.commit()
print('Resetados hand requests: ' + str(r.rowcount))

rows = conn.execute(
    'SELECT id, hand_id, status, decisions_found, decisions_done FROM gto_hand_requests ORDER BY id DESC LIMIT 5'
).fetchall()
for row in rows:
    print('  id=' + str(row[0]) + ' hand=' + str(row[1]) + ' status=' + str(row[2]) +
          ' found=' + str(row[3]) + ' done=' + str(row[4]))

conn.close()
