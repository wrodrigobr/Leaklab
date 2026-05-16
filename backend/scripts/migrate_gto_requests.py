"""
One-shot migration: enqueue gto_hand_requests for all postflop hero decisions
that still don't have a gto_label.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.repositories import get_conn, bulk_request_gto_for_hands

conn = get_conn()

# Stats first
cur = conn.execute(
    "SELECT COUNT(*) FROM decisions WHERE street IN ('flop','turn','river') AND gto_label IS NULL AND hero_cards IS NOT NULL"
)
total_decisions = cur.fetchone()[0]

cur = conn.execute(
    "SELECT COUNT(DISTINCT hand_id) FROM decisions WHERE street IN ('flop','turn','river') AND gto_label IS NULL AND hero_cards IS NOT NULL"
)
total_hands = cur.fetchone()[0]

cur = conn.execute("SELECT COUNT(*) FROM gto_hand_requests WHERE status = 'pending'")
pending = cur.fetchone()[0]

cur = conn.execute("SELECT COUNT(*) FROM gto_hand_requests")
total_reqs = cur.fetchone()[0]

print(f"Hero postflop decisions without gto_label: {total_decisions}")
print(f"Distinct hands without gto_label:          {total_hands}")
print(f"Pending gto_hand_requests (before):        {pending}")
print(f"Total gto_hand_requests (before):          {total_reqs}")

# Get all (tournament_id, hand_id) pairs grouped by tournament
cur = conn.execute("""
    SELECT DISTINCT d.tournament_id, d.hand_id, t.user_id
    FROM decisions d
    JOIN tournaments t ON t.id = d.tournament_id
    WHERE d.street IN ('flop','turn','river')
      AND d.gto_label IS NULL
      AND d.hero_cards IS NOT NULL
    ORDER BY d.tournament_id
""")
rows = cur.fetchall()
conn.close()

# Group by (tournament_id, user_id)
from collections import defaultdict
groups = defaultdict(lambda: {'user_id': None, 'hand_ids': []})
for tournament_id, hand_id, user_id in rows:
    key = tournament_id
    groups[key]['user_id'] = user_id
    groups[key]['hand_ids'].append(hand_id)

total_enqueued = 0
for t_id, info in groups.items():
    n = bulk_request_gto_for_hands(t_id, info['hand_ids'], info['user_id'])
    print(f"  tournament_id={t_id} user={info['user_id']}: {n} new requests")
    total_enqueued += n

print(f"\nTotal new gto_hand_requests created: {total_enqueued}")
