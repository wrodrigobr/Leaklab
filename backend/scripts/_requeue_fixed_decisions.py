"""Re-enfileira as 6 decisions com facing_bet para reprocessamento GTO correto."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from database.repositories import get_conn

conn = get_conn()

# Busca decisions sem gto_label que deveriam ter (postflop com board)
rows = conn.execute("""
    SELECT d.id, d.tournament_id, t.user_id, d.street, d.position,
           d.stack_bb, d.facing_bet, d.pot_size, d.board, d.hero_cards, d.best_action
    FROM decisions d
    JOIN tournaments t ON t.id = d.tournament_id
    WHERE d.gto_label IS NULL
      AND d.street IN ('flop','turn','river')
      AND d.board IS NOT NULL
      AND d.id IN (21172, 21189, 21233, 21831, 21856, 21872)
""").fetchall()

print(f"Decisions a re-enfileirar: {len(rows)}")
queued = 0
for row in rows:
    dec_id, tourn_id, user_id, street, position, stack_bb, facing_bet, pot_size, board, hero_cards, best_action = row
    print(f"  dec={dec_id} street={street} pos={position} facing_bet={facing_bet}bb stack={stack_bb}bb")

    hand_id = conn.execute(
        "SELECT hand_id FROM decisions WHERE id=?", (dec_id,)
    ).fetchone()[0]

    # Verifica se já existe na fila
    existing = conn.execute(
        "SELECT id FROM gto_hand_requests WHERE hand_id=? AND requested_by=? AND status='pending'",
        (hand_id, user_id)
    ).fetchone()
    if existing:
        print(f"    -> ja na fila")
        continue

    conn.execute("""
        INSERT OR IGNORE INTO gto_hand_requests
            (tournament_id, hand_id, requested_by, status)
        VALUES (?, ?, ?, 'pending')
    """, (tourn_id, hand_id, user_id))
    queued += 1

conn.commit()
conn.close()
print(f"Enfileirados: {queued}")
print("Aguarde o worker GTO processar (60s) ou execute: python scripts/run_gto_worker.py --enqueue --limit 10")
