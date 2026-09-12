"""Re-enfileira as 6 decisions com facing_bet para reprocessamento GTO correto."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from database.repositories import get_conn
from database.rowutil import first_value

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
    # Por NOME, nao desempacotando: no Postgres a linha e um dict e o desempacotamento itera as
    # CHAVES (a classe de bug numero 8 de "SQLite tolera, Postgres rejeita").
    _d = dict(row)
    dec_id, tourn_id, user_id = _d['id'], _d['tournament_id'], _d['user_id']
    street, position, stack_bb = _d['street'], _d['position'], _d['stack_bb']
    facing_bet, pot_size = _d['facing_bet'], _d['pot_size']
    board, hero_cards, best_action = _d['board'], _d['hero_cards'], _d['best_action']
    print(f"  dec={dec_id} street={street} pos={position} facing_bet={facing_bet}bb stack={stack_bb}bb")

    hand_id = first_value(conn.execute(
        "SELECT hand_id AS h FROM decisions WHERE id=?", (dec_id,)).fetchone())

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
