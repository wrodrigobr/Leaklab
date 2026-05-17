"""
Re-analisa labels preflop usando o pipeline completo (parse → evaluate).
Necessário porque facing_size e villain_position não ficam gravados na
tabela decisions — só estão disponíveis ao re-rodar o pipeline com raw_text.

Atualiza APENAS o campo `label` das decisions existentes.
Não recria nem apaga registros — preserva gto_label, gto_action, etc.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision

conn = get_conn()

tournaments = conn.execute(
    "SELECT id, tournament_id FROM tournaments WHERE raw_text IS NOT NULL"
).fetchall()

print(f"Processando {len(tournaments)} torneios...")
total_checked = 0
total_updated = 0

for tid, t_ext_id in tournaments:
    raw_text = conn.execute(
        "SELECT raw_text FROM tournaments WHERE id = ?", (tid,)
    ).fetchone()[0]
    if not raw_text:
        continue

    try:
        hands = parse_hand_history(raw_text)
    except Exception as e:
        print(f"  Erro parse tid={tid}: {e}")
        continue

    hand_updated = 0
    for hand in hands:
        try:
            decision_inputs = build_decision_inputs_for_hand(hand)
        except Exception:
            continue

        for di in decision_inputs:
            if di.get('street') != 'preflop':
                continue

            hand_id     = di.get('hand_id', '')
            player_act  = di.get('player_action', '')

            row = conn.execute(
                "SELECT id, label FROM decisions WHERE hand_id = ? AND street = 'preflop' AND action_taken = ?",
                (hand_id, player_act)
            ).fetchone()
            if not row:
                continue

            did, old_label = row
            total_checked += 1

            try:
                result    = evaluate_decision(di)
                new_label = (result.get('evaluation') or {}).get('label') or old_label
            except Exception:
                continue

            if new_label != old_label:
                conn.execute("UPDATE decisions SET label = ? WHERE id = ?", (new_label, did))
                print(f"  tid={tid} hand={hand_id} act={player_act}: {old_label} -> {new_label}")
                total_updated += 1
                hand_updated += 1

    if hand_updated:
        conn.commit()

conn.commit()
conn.close()
print(f"\nConcluído. Verificadas: {total_checked} | Atualizadas: {total_updated}")
