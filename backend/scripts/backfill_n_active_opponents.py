"""
Backfill da coluna decisions.n_active_opponents — oponentes vivos NO MOMENTO da decisão
do hero (não no início da street). Reusa o pipeline (hand_state_builder já corrigido) e
casa por (hand_id, street, action_taken), igual ao reanalyze_all_labels. Read-only exceto
a coluna n_active_opponents (não toca labels/gto).

Uso: python -m scripts.backfill_n_active_opponents
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand

conn = get_conn()
try:
    conn.execute('PRAGMA busy_timeout=30000')
except Exception:
    pass

tournaments = conn.execute(
    "SELECT id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id").fetchall()
print(f"Processando {len(tournaments)} torneios...")

checked = updated = 0
for row in tournaments:
    tid = row['id']
    raw = conn.execute("SELECT raw_text FROM tournaments WHERE id = ?", (tid,)).fetchone()
    if not raw or not raw[0]:
        continue
    try:
        hands = parse_hand_history(raw[0])
    except Exception as e:
        print(f"  [SKIP] parse tid={tid}: {e}")
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
            if not hand_id or not act or not street:
                continue
            key = (hand_id, street, act)
            if key in seen:
                continue
            seen.add(key)
            nopp = spot.get('nActiveOpponents')
            if nopp is None:
                continue
            # ESCOPAR por tournament_id: hand_id NÃO é único entre usuários — dois jogadores que
            # importam o MESMO torneio têm o mesmo hand_id. Sem o filtro por torneio, o LIMIT 1
            # casava só a cópia de menor id (um usuário) e a do outro ficava NULL (bug: T#4002072836,
            # tid 198 do user 13 nunca era populada). Com tid, cada cópia é atualizada.
            r = conn.execute(
                "SELECT id, n_active_opponents FROM decisions "
                "WHERE tournament_id = ? AND hand_id = ? AND street = ? AND action_taken = ? LIMIT 1",
                (tid, hand_id, street, act)).fetchone()
            if not r:
                continue
            checked += 1
            if r['n_active_opponents'] != nopp:
                conn.execute("UPDATE decisions SET n_active_opponents = ? WHERE id = ?",
                             (nopp, r['id']))
                updated += 1
    conn.commit()

conn.close()
print(f"Concluido. Verificadas: {checked} | Atualizadas: {updated}")
