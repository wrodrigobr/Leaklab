"""Verifica distribuição de labels preflop pós-migração."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database.schema import get_conn

conn = get_conn()

print("=== Distribuição geral de labels preflop ===")
rows = conn.execute(
    "SELECT label, COUNT(*) FROM decisions WHERE street='preflop' GROUP BY label ORDER BY COUNT(*) DESC"
).fetchall()
for label, cnt in rows:
    print(f"  {label}: {cnt}")

print("\n=== Calls preflop com facing_bet > 0 (decisões de defesa) ===")
rows = conn.execute(
    "SELECT label, COUNT(*) FROM decisions "
    "WHERE street='preflop' AND action_taken='call' AND facing_bet > 0 "
    "GROUP BY label ORDER BY COUNT(*) DESC"
).fetchall()
for label, cnt in rows:
    print(f"  {label}: {cnt}")

print("\n=== Mão 257045919085 ===")
row = conn.execute(
    "SELECT id, label, action_taken, position, hero_cards FROM decisions WHERE hand_id='257045919085' AND street='preflop'"
).fetchone()
if row:
    print(f"  id={row[0]} label={row[1]} action={row[2]} pos={row[3]} cards={row[4]}")
else:
    print("  Nao encontrada")

conn.close()
