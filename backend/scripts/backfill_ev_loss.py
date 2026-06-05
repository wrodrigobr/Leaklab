"""backfill_ev_loss.py — preenche decisions.ev_loss_bb / ev_loss_source (#24).

Recomputa cada decisão (pipeline + evaluate_decision) e grava o ev_loss_bb que o
engine preflop devolve (bb perdidos vs a melhor ação, pra a mão do hero). Só
preflop tem ev_loss hoje (postflop é futuro) → demais ficam NULL.

Match desambiguado por (hand_id, street, action, vs_position) — mesma chave do
resync (evita colisão quando o herói age igual em 2 spots preflop).

Uso: python -m scripts.backfill_ev_loss          # DRY-RUN
     python -m scripts.backfill_ev_loss --apply  # grava
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision

APPLY = '--apply' in sys.argv
conn = get_conn()
tournaments = conn.execute(
    "SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id").fetchall()

checked = with_ev = updated = 0
for row in tournaments:
    tid = row['id']
    raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()
    if not raw or not raw[0]:
        continue
    try:
        hands = parse_hand_history(raw[0])
    except Exception:
        continue
    seen = set()
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
            vs      = (spot.get('villainPosition') or '').lower()
            if not hand_id or not act or not street:
                continue
            k = (hand_id, street, act, vs)
            if k in seen:
                continue
            seen.add(k)
            db = conn.execute(
                "SELECT id, ev_loss_bb FROM decisions WHERE hand_id=? AND street=? "
                "AND action_taken=? AND LOWER(COALESCE(vs_position,''))=? LIMIT 1",
                (hand_id, street, act, vs)).fetchone()
            if not db:
                continue
            checked += 1
            try:
                res = evaluate_decision(di)
            except Exception:
                continue
            gto = res.get('gto') or {}
            elb = gto.get('ev_loss_bb')
            esrc = gto.get('ev_loss_source')
            if elb is not None:
                with_ev += 1
            if db['ev_loss_bb'] != elb:
                updated += 1
                if APPLY:
                    conn.execute(
                        "UPDATE decisions SET ev_loss_bb=?, ev_loss_source=? WHERE id=?",
                        (elb, esrc, db['id']))
    if APPLY:
        conn.commit()

print('=' * 56)
print(f"BACKFILL EV-LOSS — {'APLICADO' if APPLY else 'DRY-RUN'}")
print('=' * 56)
print(f"Decisões checadas:     {checked}")
print(f"Com ev_loss (preflop): {with_ev}")
print(f"A atualizar:           {updated}")
if not APPLY:
    print("\n(DRY-RUN — nada gravado. Rode com --apply.)")
else:
    print("\nGravado + commit.")
