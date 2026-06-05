"""Re-sincroniza as decisões ARMAZENADAS com o engine corrigido.

Após os fixes desta sessão (vs_4bet, shove↔allin, idealAction, SB-complete,
off-tree, limp push/fold, vs_rfi rec, equity vs-random…), o banco tem decisões
STALE — computadas com o engine antigo. O audit de revalidação achou ~97 drifts.

Recomputa cada decisão (pipeline + evaluate_decision, idêntico ao reanalyze_all_
labels) e ATUALIZA label/best_action/gto_label/gto_action. Diferença do
reanalyze antigo: quando o fresh é SEM cobertura (available=False), zera o
gto_label/gto_action (NULL honesto) em vez de preservar o stale — fecha o gap
'stale→NULL' (ex.: limp/off-tree que antes tinham gto_label falso).

Uso: python -m scripts.resync_stale_decisions          # DRY-RUN (só reporta)
     python -m scripts.resync_stale_decisions --apply  # aplica + commit
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collections import Counter
from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision

APPLY = '--apply' in sys.argv
conn = get_conn()
tournaments = conn.execute(
    "SELECT id, tournament_id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id"
).fetchall()

checked = 0
changes = []            # (did, field, old, new, tid, hand, street, act)
by_field = Counter()
seen_global = set()

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
            # vs_position (villainPosition) desambigua mãos com 2 spots no mesmo
            # (hand,street,action) — ex.: call vs open e depois call vs shove. Sem
            # ele, o LIMIT-1 só toca a 1ª linha e a 2ª fica stale.
            vs      = (spot.get('villainPosition') or '').lower()
            if not hand_id or not act or not street:
                continue
            k = (hand_id, street, act, vs)
            if k in seen:
                continue
            seen.add(k)
            db = conn.execute(
                "SELECT id, label, best_action, gto_label, gto_action FROM decisions "
                "WHERE hand_id=? AND street=? AND action_taken=? "
                "AND LOWER(COALESCE(vs_position,''))=? LIMIT 1",
                (hand_id, street, act, vs)).fetchone()
            if not db:
                continue
            did = db['id']
            old = (db['label'], db['best_action'], db['gto_label'], db['gto_action'])
            try:
                res = evaluate_decision(di)
            except Exception:
                continue
            gto = res.get('gto') or {}
            avail = bool(gto.get('available'))
            new_label = (res.get('evaluation') or {}).get('label') or old[0]
            new_best  = res.get('bestAction') or old[1]
            # FIX do gap: sem cobertura fresh → NULL (não preserva o stale)
            new_gtolbl = (gto.get('gto_label') if avail else None)
            new_gtoact = (gto.get('gto_action') if avail else None)
            new = (new_label, new_best, new_gtolbl, new_gtoact)
            checked += 1
            fields = ['label', 'best_action', 'gto_label', 'gto_action']
            row_changed = False
            for i, f in enumerate(fields):
                if old[i] != new[i]:
                    fkey = f if not (f == 'gto_label' and new[i] is None and old[i]) else 'gto_label:→NULL'
                    by_field[fkey] += 1
                    if len(changes) < 40:
                        changes.append((did, f, old[i], new[i], tid, hand_id, street, act))
                    row_changed = True
            if row_changed and APPLY:
                conn.execute(
                    "UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=? WHERE id=?",
                    (*new, did))
    if APPLY:
        conn.commit()

n_changed = sum(by_field.values())
print('=' * 60)
print(f"RESYNC STALE DECISIONS — {'APLICADO' if APPLY else 'DRY-RUN'}")
print('=' * 60)
print(f"Decisões checadas: {checked}")
print(f"Campos a atualizar: {n_changed}")
print("Por campo:")
for f, c in by_field.most_common():
    print(f"  {f:24} {c}")
print("\nAmostra (até 20):")
for did, f, o, n, tid, h, st, a in changes[:20]:
    print(f"  did={did} tid={tid} {h} {st}/{a}  {f}: {o!r} -> {n!r}")
if not APPLY:
    print("\n(DRY-RUN — nada escrito. Rode com --apply para persistir.)")
else:
    print("\nAplicado + commit.")
