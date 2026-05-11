import sqlite3, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'leaklab.db')
print(f'DB: {db_path}')

conn = sqlite3.connect(db_path)
c = conn.cursor()

print('\n=== gto_hand_requests ===')
c.execute('SELECT id, hand_id, status, decisions_found, decisions_done FROM gto_hand_requests ORDER BY id DESC LIMIT 10')
for r in c.fetchall():
    print(f'  id={r[0]} hand={r[1]} status={r[2]} found={r[3]} done={r[4]}')

print('\n=== gto_solver_queue ===')
for status in ('pending', 'running', 'done', 'failed'):
    c.execute(f"SELECT COUNT(*) FROM gto_solver_queue WHERE status=?", (status,))
    print(f'  {status}: {c.fetchone()[0]}')

conn.close()
