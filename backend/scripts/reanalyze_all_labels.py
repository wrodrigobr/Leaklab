"""
Re-analisa labels de TODAS as decisões (preflop + postflop) usando o pipeline completo.

Reusa o padrão de scripts/reanalyze_preflop_labels.py mas sem filtro de street,
para que o guard novo de apply_anti_rules (fold com eq >= po + 3pp) seja aplicado
às decisões postflop existentes no banco.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision

conn = get_conn()

tournaments = conn.execute(
    "SELECT id, tournament_id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id"
).fetchall()

print(f"Processando {len(tournaments)} torneios com raw_text...")
total_checked = 0
total_updated = 0
affected_tournament_ids = set()

for row in tournaments:
    tid, t_ext_id = row['id'], row['tournament_id']

    raw_text = conn.execute(
        "SELECT raw_text FROM tournaments WHERE id = ?", (tid,)
    ).fetchone()
    if not raw_text or not raw_text[0]:
        continue

    try:
        hands = parse_hand_history(raw_text[0])
    except Exception as e:
        print(f"  [SKIP] Erro parse tid={tid}: {e}")
        continue

    hand_updated = 0
    seen_decisions: set = set()  # (hand_id, street, position, action) — evita DIs duplicados

    for hand in hands:
        try:
            decision_inputs = build_decision_inputs_for_hand(hand)
        except Exception:
            continue

        for di in decision_inputs:
            street  = di.get('street')
            hand_id = di.get('hand_id', '')
            spot    = di.get('spot', {})
            act     = (spot.get('actionTaken') or di.get('player_action', '')).lower()
            pos     = (di.get('position') or spot.get('position') or '').upper()
            if not hand_id or not act or not street:
                continue

            dedup_key = (hand_id, street, pos, act)
            if dedup_key in seen_decisions:
                continue
            seen_decisions.add(dedup_key)

            db_row = conn.execute(
                """SELECT id, label, best_action FROM decisions
                   WHERE hand_id = ? AND street = ? AND action_taken = ?
                   LIMIT 1""",
                (hand_id, street, act)
            ).fetchone()
            if not db_row:
                continue

            did, old_label, old_best = db_row['id'], db_row['label'], db_row['best_action']

            try:
                result    = evaluate_decision(di)
                new_label = (result.get('evaluation') or {}).get('label') or old_label
                new_best  = result.get('bestAction') or old_best
            except Exception:
                continue

            total_checked += 1
            if new_label != old_label or new_best != old_best:
                conn.execute(
                    "UPDATE decisions SET label = ?, best_action = ? WHERE id = ?",
                    (new_label, new_best, did)
                )
                hand_updated += 1
                total_updated += 1
                affected_tournament_ids.add(tid)
                if total_updated <= 30 or total_updated % 50 == 0:
                    print(f"  tid={tid} hand={hand_id} {street}/{act}: "
                          f"{old_label}->{new_label} | best {old_best}->{new_best}")

    if hand_updated:
        conn.commit()

# Recalcular standard_pct nos torneios afetados
if affected_tournament_ids:
    print(f"\nRecalculando standard_pct de {len(affected_tournament_ids)} torneios...")
    for tid in sorted(affected_tournament_ids):
        std_row = conn.execute(
            """SELECT
                 COUNT(CASE WHEN label = 'standard' THEN 1 END) * 100.0 / COUNT(*) AS std_pct,
                 AVG(score) AS avg_score
               FROM decisions WHERE tournament_id = ?""",
            (tid,)
        ).fetchone()
        if std_row:
            conn.execute(
                "UPDATE tournaments SET standard_pct = ?, avg_score = ? WHERE id = ?",
                (round(std_row[0], 2), round(std_row[1] or 0, 4), tid)
            )
    conn.commit()
    print("  standard_pct recalculado.")

conn.close()
print(f"\nConcluido. Verificadas: {total_checked} | Atualizadas: {total_updated}")
