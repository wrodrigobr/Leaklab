"""
resync_postflop_gto.py -- Reconcilia decisions POSTFLOP (label, best_action,
gto_label, gto_action) com o recompute FRESCO do engine.

Contexto: o gto postflop em `decisions` foi gravado contra a tabela `gto_nodes`
ANTES da limpeza desta sessão (delete de nodes corrompidos, recuperação via
bet_bucket, fix do normalize_cards no insert + no compute_spot_hash). Como o
produto serve o gto_label/gto_action ARMAZENADO, decisões antigas ficaram stale:
verditos sem node de respaldo (vanished), verditos recuperáveis não exibidos
(appeared) e labels divergentes (incl. falsos gto_critical super-penalizando).

Pós-limpeza, o lookup on-demand (evaluate_decision) é AUTORITATIVO. Este script
regrava os 4 campos JUNTOS (do mesmo recompute) — nunca só o label, evitando
inconsistência label↔gto (label_gto_conflict). Diferente do sync_label_bestaction
(que preserva gto de propósito), aqui o objetivo é justamente sincronizar o gto.

Só postflop. Preflop é range-backed e tratado em separado. Matching inequívoco
(hand_id, street, action_taken) LIMIT 1 — multi-decision ambíguo é PULADO.

Uso:
    python scripts/resync_postflop_gto.py            # dry-run
    python scripts/resync_postflop_gto.py --apply
"""
import sys, os, argparse
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, init_db
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


def _norm(v):
    """'' e None são equivalentes (sem cobertura)."""
    return v if v else None


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

    changes = Counter()           # por campo
    kinds = Counter()             # vanished/appeared/label_drift/action_only
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
                st = (di.get("street") or "").lower()
                if st == "preflop":
                    continue
                hid = di.get("hand_id", "")
                act = (di.get("player_action") or "").lower()
                if not hid or not st or not act:
                    continue
                try:
                    r = evaluate_decision(di)
                except Exception:
                    continue
                g = r.get("gto") or {}
                fresh[(hid, st, act)].append({
                    "label":      (r.get("evaluation") or {}).get("label") or None,
                    "best":       r.get("bestAction") or None,
                    "gto_label":  _norm(g.get("gto_label")),
                    "gto_action": _norm(g.get("gto_action")),
                })

        stored = defaultdict(list)
        for r in conn.execute(
            "SELECT id, hand_id, street, action_taken, label, best_action, "
            "gto_label, gto_action FROM decisions "
            "WHERE tournament_id=? AND lower(street)!='preflop'", (tid,)).fetchall():
            d = dict(r)
            stored[(d['hand_id'], (d['street'] or '').lower(),
                    (d['action_taken'] or '').lower())].append(d)

        for key, srows in stored.items():
            frows = fresh.get(key, [])
            if len(srows) != 1 or len(frows) != 1:
                skipped += len(srows)
                continue
            s, f = srows[0], frows[0]
            s_gl, s_ga = _norm(s['gto_label']), _norm(s['gto_action'])
            diffs = []
            if f['label'] != s['label']:      diffs.append('label')
            if f['best'] != s['best_action']: diffs.append('best_action')
            if f['gto_label'] != s_gl:        diffs.append('gto_label')
            if f['gto_action'] != s_ga:       diffs.append('gto_action')
            if not diffs:
                continue
            updated += 1
            for d in diffs:
                changes[d] += 1
            # classifica a natureza da mudança de gto
            if s_gl and not f['gto_label']:        kinds['vanished'] += 1
            elif not s_gl and f['gto_label']:      kinds['appeared'] += 1
            elif s_gl != f['gto_label']:           kinds['label_drift'] += 1
            elif 'gto_action' in diffs:            kinds['action_only'] += 1
            if len(examples) < 20:
                examples.append(
                    f"  t{tid} {key[0]} {key[1]}/{key[2]} | "
                    f"label {s['label']}->{f['label']} | best {s['best_action']}->{f['best']} | "
                    f"gto {s_gl}/{s_ga}->{f['gto_label']}/{f['gto_action']}")
            if args.apply:
                conn.execute(
                    "UPDATE decisions SET label=?, best_action=?, gto_label=?, gto_action=? "
                    "WHERE id=?",
                    (f['label'], f['best'], f['gto_label'], f['gto_action'], s['id']))

    if args.apply:
        conn.commit()
    conn.close()
    print(f"\nReconciliados: {updated} | pulados (ambíguo): {skipped}")
    print("Por campo:", dict(changes))
    print("Natureza :", dict(kinds))
    if examples:
        print("Exemplos:\n" + "\n".join(examples))
    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN (use --apply)'}")


if __name__ == "__main__":
    main()
