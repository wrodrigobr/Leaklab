import sqlite3, os
db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'leaklab.db')
conn = sqlite3.connect(db)
c = conn.cursor()

print("=== Decisions por tournament ===")
c.execute(
    "SELECT d.id, d.tournament_id, d.hand_id, d.street, d.action_taken, d.gto_label, d.gto_action"
    " FROM decisions d"
    " WHERE d.hand_id IN ('257045919085', '257045965983')"
    " AND d.street IN ('flop','turn','river')"
    " ORDER BY d.tournament_id, d.hand_id, d.id"
)
for r in c.fetchall():
    label_info = f"gto_label={r[5]} gto_action={r[6]}" if r[5] else "sem GTO"
    print(f"  tid={r[1]} id={r[0]} {r[3]} action={r[4]} -> {label_info}")

print()
print("=== gto_hand_requests ===")
c.execute("SELECT id, tournament_id, hand_id, status FROM gto_hand_requests ORDER BY id")
for r in c.fetchall():
    print(f"  req={r[0]} tournament_id={r[1]} hand={r[2]} status={r[3]}")

conn.close()
