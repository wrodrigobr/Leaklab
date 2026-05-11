import sqlite3, os

db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'leaklab.db')
print('DB:', db)
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute("UPDATE gto_hand_requests SET status='pending', decisions_done=0 WHERE status='solver_queued'")
print('Updated:', c.rowcount)
conn.commit()
c.execute('SELECT id, hand_id, status, decisions_found, decisions_done FROM gto_hand_requests ORDER BY id DESC LIMIT 5')
for r in c.fetchall():
    print(f'  id={r[0]} hand={r[1]} status={r[2]} found={r[3]} done={r[4]}')
conn.close()
