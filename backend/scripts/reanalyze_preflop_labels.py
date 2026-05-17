"""
Re-analisa labels preflop usando o pipeline completo (parse → evaluate).

Por que é necessário:
  facing_size e villain_position não ficam gravados na tabela decisions —
  só estão disponíveis ao re-rodar o pipeline com raw_text. Com os 5 bugs
  corrigidos em preflop_gto_ranges.py (v0.101.x), muitas decisões que
  receberam label 'marginal' deveriam ter recebido 'small_mistake' ou
  'clear_mistake', e vice-versa.

O que faz:
  1. Para cada torneio com raw_text, re-parseia as mãos
  2. Reconstrói os decision inputs via pipeline (inclui facingSize,
     villainPosition, is_3bet)
  3. Re-executa evaluate_decision para cada decisão preflop
  4. Atualiza decisions.label onde o novo valor difere do antigo
  5. Recalcula tournaments.standard_pct para os torneios afetados
     (para que KPIs e RecentForm também reflitam a correção)

O que NÃO faz:
  - Não recria decisions — preserva gto_label, gto_action, score, etc.
  - Não apaga dados existentes
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
    seen_decisions: set = set()  # (hand_id, position, action) — evita processar DIs duplicados

    for hand in hands:
        try:
            decision_inputs = build_decision_inputs_for_hand(hand)
        except Exception:
            continue

        for di in decision_inputs:
            if di.get('street') != 'preflop':
                continue

            hand_id = di.get('hand_id', '')
            spot    = di.get('spot', {})
            act     = (spot.get('actionTaken') or di.get('player_action', '')).lower()
            pos     = (di.get('position') or spot.get('position') or '').upper()
            if not hand_id or not act:
                continue

            dedup_key = (hand_id, pos, act)
            if dedup_key in seen_decisions:
                continue
            seen_decisions.add(dedup_key)

            db_row = conn.execute(
                """SELECT id, label FROM decisions
                   WHERE hand_id = ? AND street = 'preflop' AND action_taken = ?
                   LIMIT 1""",
                (hand_id, act)
            ).fetchone()
            if not db_row:
                continue

            did, old_label = db_row['id'], db_row['label']
            total_checked += 1

            try:
                result    = evaluate_decision(di)
                new_label = (result.get('evaluation') or {}).get('label') or old_label
            except Exception:
                continue

            if new_label != old_label:
                conn.execute("UPDATE decisions SET label = ? WHERE id = ?", (new_label, did))
                hand_updated += 1
                total_updated += 1
                affected_tournament_ids.add(tid)
                print(f"  tid={tid} hand={hand_id} act={act}: {old_label} -> {new_label}")

    if hand_updated:
        conn.commit()

# Recalcular standard_pct nos torneios afetados para que KPIs e RecentForm
# também reflitam os labels corrigidos (tournaments.standard_pct é lido pelo
# endpoint /player/evolution e pelo cálculo de nível/gamificação)
if affected_tournament_ids:
    print(f"\nRecalculando standard_pct de {len(affected_tournament_ids)} torneios afetados...")
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
