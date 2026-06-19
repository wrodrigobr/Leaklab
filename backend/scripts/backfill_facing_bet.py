"""
backfill_facing_bet.py — recomputa decisions.facing_bet usando facingToBb (BB correto).

O save_decisions antigo gravava facing_bet = facingSize/level_bb, que dava valores
errados (ex.: 0.2bb) e ainda contaminava o hash do nó GTO no drill (lookup errado →
veredito errado). O pipeline já computa facingToBb (facing_to_total/bb) corretamente.
Este backfill re-parseia os torneios, recomputa facingToBb por decisão e corrige o
facing_bet onde diverge. Ver project_replay_facing_bet_node.

Postgres-safe: sem PRAGMA no PG, acesso de linha por nome, placeholders ? adaptados.

Uso:
    python scripts/backfill_facing_bet.py            # dry-run (só relata)
    python scripts/backfill_facing_bet.py --apply    # grava
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand

ap = argparse.ArgumentParser(description="Backfill de decisions.facing_bet via facingToBb.")
ap.add_argument("--apply", action="store_true", help="grava no banco (default: dry-run)")
APPLY = ap.parse_args().apply
print("== APLICANDO ==" if APPLY else "== DRY-RUN — nada será gravado ==")

conn = get_conn()
if not getattr(conn, '_pg', False):   # PRAGMA é só SQLite
    try:
        conn.execute('PRAGMA busy_timeout=30000')
    except Exception:
        pass

tournaments = conn.execute(
    "SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id"
).fetchall()
print(f"Processando {len(tournaments)} torneios com raw_text...")

checked = 0
updated = 0
for trow in tournaments:
    tid = trow['id']
    rt = conn.execute("SELECT raw_text FROM tournaments WHERE id = ?", (tid,)).fetchone()
    if not rt or not rt['raw_text']:
        continue
    try:
        hands = parse_hand_history(rt['raw_text'])
    except Exception as e:
        print(f"  [SKIP] parse tid={tid}: {e}")
        continue

    seen = set()
    hand_updated = 0
    for hand in hands:
        try:
            dis = build_decision_inputs_for_hand(hand)
        except Exception:
            continue
        for di in dis:
            street  = di.get('street')
            hand_id = di.get('hand_id', '')
            spot    = di.get('spot', {})
            act     = (spot.get('actionTaken') or di.get('player_action', '')).lower()
            if not hand_id or not act or not street:
                continue
            key = (hand_id, street, act)
            if key in seen:
                continue
            seen.add(key)

            new_face = spot.get('facingToBb')
            if new_face is None:
                continue
            new_face = round(float(new_face), 1)

            row = conn.execute(
                "SELECT id, facing_bet FROM decisions "
                "WHERE hand_id = ? AND street = ? AND action_taken = ? LIMIT 1",
                (hand_id, street, act)
            ).fetchone()
            if not row:
                continue

            checked += 1
            old_face = row['facing_bet']
            old_f = round(float(old_face), 1) if old_face is not None else None
            if old_f != new_face:
                if APPLY:
                    conn.execute("UPDATE decisions SET facing_bet = ? WHERE id = ?",
                                 (new_face, row['id']))
                    hand_updated += 1
                updated += 1
                if updated <= 30:
                    print(f"  tid={tid} {hand_id} {street}/{act}: {old_f} -> {new_face}")
    if APPLY and hand_updated:
        conn.commit()

print(f"\nConcluido. Verificadas: {checked} | "
      f"{'Atualizadas' if APPLY else 'Mudariam'}: {updated}")
if not APPLY:
    print("== DRY-RUN — nada foi gravado ==")
conn.close()
