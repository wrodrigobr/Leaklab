import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from database.repositories import get_conn, um_numero

conn = get_conn()
# ALIAS + acesso por NOME: no Postgres a linha e dict e `r[0]` estoura (KeyError: 0).
queue = {dict(r)['st']: dict(r)['n'] for r in conn.execute(
    'SELECT status AS st, COUNT(*) AS n FROM gto_solver_queue GROUP BY status').fetchall()}
hands = {dict(r)['st']: dict(r)['n'] for r in conn.execute(
    'SELECT status AS st, COUNT(*) AS n FROM gto_hand_requests GROUP BY status').fetchall()}
nodes = um_numero(conn, 'SELECT COUNT(*) FROM gto_nodes')
mismatch = um_numero(conn, """
    SELECT COUNT(*) FROM decisions
    WHERE gto_action IS NOT NULL
      AND ((best_action = 'call' AND gto_action IN ('check','bet'))
        OR (best_action != 'call' AND gto_action = 'call'))
""")
conn.close()
print('solver_queue :', queue)
print('hand_requests:', hands)
print('gto_nodes    :', nodes)
print('mismatches   :', mismatch)
