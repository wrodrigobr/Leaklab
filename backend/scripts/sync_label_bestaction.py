"""
sync_label_bestaction.py -- Sincroniza decisions.label e decisions.best_action
com o recompute FRESCO do engine (dado real). NÃO toca em gto_label/gto_action
(que são node-backed / range-authoritativos — evita os efeitos colaterais do
lookup postflop on-demand).

Usado após o fix do guard de all-in (unidades fichas×bb), que passou a honrar o
'jam' do GTO em vez de rebaixar para call. Matching seguro (chave inequívoca).

Uso:
    python scripts/sync_label_bestaction.py            # dry-run
    python scripts/sync_label_bestaction.py --apply
"""
import sys, os, argparse
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, init_db
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    init_db()
    conn = get_conn()
    try:
        conn.execute("PRAGMA busy_timeout=8000")
    except Exception:
        pass

    tournaments = conn.execute(
        "SELECT id FROM tournaments WHERE raw_text IS NOT NULL "
        "AND tournament_id NOT LIKE 'FAKE-%' ORDER BY id").fetchall()

    changes = Counter()
    updated = skipped = 0
    examples = []
    for trow in tournaments:
        tid = dict(trow)['id']
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()
        if not raw or not raw[0]:
            continue
        try:
            hands = parse_hand_history(raw[0])
        except Exception:
            continue

        fresh = defaultdict(list)
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                hid = di.get("hand_id", "")
                st = (di.get("street") or "").lower()
                act = (di.get("player_action") or "").lower()
                if not hid or not st or not act:
                    continue
                try:
                    r = evaluate_decision(di)
                except Exception:
                    continue
                fresh[(hid, st, act)].append({
                    "label": (r.get("evaluation") or {}).get("label") or None,
                    "best":  r.get("bestAction") or None,
                })

        stored = defaultdict(list)
        for r in conn.execute(
            "SELECT id, hand_id, street, action_taken, label, best_action "
            "FROM decisions WHERE tournament_id=?", (tid,)).fetchall():
            d = dict(r)
            stored[(d['hand_id'], (d['street'] or '').lower(),
                    (d['action_taken'] or '').lower())].append(d)

        for key, srows in stored.items():
            frows = fresh.get(key, [])
            if len(srows) != 1 or len(frows) != 1:
                skipped += len(srows)
                continue
            s, f = srows[0], frows[0]
            new_label = f['label'] or s['label']
            new_best = f['best'] or s['best_action']
            diffs = []
            if new_label != s['label']: diffs.append('label')
            if new_best != s['best_action']: diffs.append('best_action')
            if not diffs:
                continue
            updated += 1
            for d in diffs:
                changes[d] += 1
            if len(examples) < 15:
                examples.append(f"  t{tid} {key[0]} {key[1]}/{key[2]} | "
                                f"best {s['best_action']}->{new_best} | label {s['label']}->{new_label}")
            if args.apply:
                conn.execute("UPDATE decisions SET label=?, best_action=? WHERE id=?",
                             (new_label, new_best, s['id']))

    if args.apply:
        conn.commit()
    conn.close()
    print(f"\nAtualizados: {updated} | pulados (ambíguo): {skipped}")
    print("Por campo:", dict(changes))
    if examples:
        print("Exemplos:\n" + "\n".join(examples))
    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN (use --apply)'}")


if __name__ == "__main__":
    main()
