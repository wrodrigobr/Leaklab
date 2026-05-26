import sqlite3, os
db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'leaklab.db')
conn = sqlite3.connect(db)
c = conn.cursor()
for hid in ['257045919085', '257045965983']:
    print(f'Hand {hid}:')
    c.execute(
        "SELECT id, street, action_taken, gto_label, gto_action FROM decisions"
        " WHERE hand_id=? AND street IN ('flop','turn','river') ORDER BY id",
        (hid,)
    )
    for r in c.fetchall():
        print(f'  {r[1]} action={r[2]} gto_label={r[3]} gto_action={r[4]}')
conn.close()
