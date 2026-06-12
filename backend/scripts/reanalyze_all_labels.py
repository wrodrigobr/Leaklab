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
# DB dev tem o app.py vivo (WAL) — espera o lock em vez de falhar na hora.
try:
    conn.execute('PRAGMA busy_timeout=30000')
except Exception:
    pass

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
                """SELECT id, label, best_action, gto_label, gto_action,
                          ev_loss_bb, ev_loss_source FROM decisions
                   WHERE hand_id = ? AND street = ? AND action_taken = ?
                   LIMIT 1""",
                (hand_id, street, act)
            ).fetchone()
            if not db_row:
                continue

            did       = db_row['id']
            old_label = db_row['label']
            old_best  = db_row['best_action']
            old_gtolbl = db_row['gto_label']
            old_gtoact = db_row['gto_action']

            try:
                result    = evaluate_decision(di)
                new_label = (result.get('evaluation') or {}).get('label') or old_label
                new_best  = result.get('bestAction') or old_best
                gto_dict  = result.get('gto') or {}
                if gto_dict.get('ungradeable_action'):
                    # Ação fora da árvore solvada (ex.: shove em árvore sem branch de
                    # raise): o nó NÃO grade essa ação. Limpa os campos GTO antigos —
                    # mantê-los preservava o 'fold/gto_critical' podre gravado antes
                    # do fix (shove com a wheel no torneio 388).
                    new_gtolbl = None
                    new_gtoact = None
                else:
                    new_gtolbl = gto_dict.get('gto_label') if gto_dict.get('available') else old_gtolbl
                    new_gtoact = gto_dict.get('gto_action') if gto_dict.get('available') else old_gtoact
                    if not new_gtolbl: new_gtolbl = old_gtolbl
                    if not new_gtoact: new_gtoact = old_gtoact
                # Fase 3 / #24 postflop: a re-análise também sincroniza o EV loss —
                # sem isto, decisões antigas nunca ganham ev_loss_bb (só re-upload),
                # e o card "onde você sangra" fica só com o preflop do overlay.
                old_evloss = db_row['ev_loss_bb']
                old_evsrc  = db_row['ev_loss_source']
                new_evloss = gto_dict.get('ev_loss_bb')
                new_evsrc  = gto_dict.get('ev_loss_source')
                if new_evloss is None and not gto_dict.get('ungradeable_action'):
                    new_evloss, new_evsrc = old_evloss, old_evsrc
            except Exception:
                continue

            total_checked += 1
            changed = (new_label != old_label or new_best != old_best or
                       new_gtolbl != old_gtolbl or new_gtoact != old_gtoact or
                       new_evloss != old_evloss)
            if changed:
                conn.execute(
                    "UPDATE decisions SET label = ?, best_action = ?, gto_label = ?, "
                    "gto_action = ?, ev_loss_bb = ?, ev_loss_source = ? WHERE id = ?",
                    (new_label, new_best, new_gtolbl, new_gtoact, new_evloss, new_evsrc, did)
                )
                hand_updated += 1
                total_updated += 1
                affected_tournament_ids.add(tid)
                if total_updated <= 30 or total_updated % 50 == 0:
                    print(f"  tid={tid} hand={hand_id} {street}/{act}: "
                          f"{old_label}->{new_label} | gto {old_gtolbl}->{new_gtolbl}")

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
