import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from database.repositories import get_conn

conn = get_conn()
queue = {r[0]: r[1] for r in conn.execute('SELECT status, COUNT(*) FROM gto_solver_queue GROUP BY status').fetchall()}
hands = {r[0]: r[1] for r in conn.execute('SELECT status, COUNT(*) FROM gto_hand_requests GROUP BY status').fetchall()}
nodes = conn.execute('SELECT COUNT(*) FROM gto_nodes').fetchone()[0]
mismatch = conn.execute("""
    SELECT COUNT(*) FROM decisions
    WHERE gto_action IS NOT NULL
      AND ((best_action = 'call' AND gto_action IN ('check','bet'))
        OR (best_action != 'call' AND gto_action = 'call'))
""").fetchone()[0]
conn.close()
print('solver_queue :', queue)
print('hand_requests:', hands)
print('gto_nodes    :', nodes)
print('mismatches   :', mismatch)
