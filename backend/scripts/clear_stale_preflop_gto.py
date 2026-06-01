"""
clear_stale_preflop_gto.py -- Limpa gto_label/gto_action STALE de decisões
PREFLOP cujo recompute atual do engine retorna SEM COBERTURA (available=False).

Por que só PREFLOP: no preflop o gto vem de analyze_preflop (ranges) — a MESMA
fonte do resync, então "available=False" é autoritativo (ex.: squeeze enfrentado
a frio, vs_position não detectado). No POSTFLOP o evaluate_decision faz lookup
on-demand de gto_nodes que ERRA (mismatch de spot_hash/hero_hand) → NÃO é fonte
confiável, então NÃO mexemos (os labels postflop são solver-backed, legítimos).

Fecha o gap "clear-stale-on-uncovered" do reanalyze_all_labels (que preserva).
Só dado real (FAKE-% não tem raw_text). Matching seguro (chave inequívoca).

Uso:
    python scripts/clear_stale_preflop_gto.py            # dry-run
    python scripts/clear_stale_preflop_gto.py --apply    # aplica
"""
import sys, os, argparse
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, init_db
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


# Por padrão limpa só labels HARMFUL (dizem "você errou") em spots sem cobertura —
# manter um "gto_critical" falso é o mais nocivo. --all limpa qualquer label stale.
_HARMFUL = ("gto_critical", "gto_minor_deviation")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="limpa QUALQUER gto stale (default: só gto_critical/minor_deviation)")
    args = ap.parse_args()
    harmful_only = not args.all
    init_db()
    conn = get_conn()
    try:
        conn.execute("PRAGMA busy_timeout=8000")
    except Exception:
        pass

    tournaments = conn.execute(
        "SELECT id FROM tournaments WHERE raw_text IS NOT NULL "
        "AND tournament_id NOT LIKE 'FAKE-%' ORDER BY id").fetchall()

    cleared = skipped_ambig = 0
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

        # fresh availability por (hand_id, action) — só preflop
        avail_by_key = defaultdict(list)
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                if (di.get("street") or "").lower() != "preflop":
                    continue
                hid = di.get("hand_id", "")
                act = (di.get("player_action") or "").lower()
                if not hid or not act:
                    continue
                try:
                    gto = (evaluate_decision(di).get("gto") or {})
                except Exception:
                    continue
                avail_by_key[(hid, act)].append(bool(gto.get("available")))

        stored = defaultdict(list)
        sql = ("SELECT id, hand_id, action_taken, gto_label, gto_action FROM decisions "
               "WHERE tournament_id=? AND street='preflop' "
               "AND gto_label IS NOT NULL AND gto_label != ''")
        params = [tid]
        if harmful_only:
            sql += " AND gto_label IN (?, ?)"
            params += list(_HARMFUL)
        for r in conn.execute(sql, tuple(params)).fetchall():
            d = dict(r)
            stored[(d['hand_id'], (d['action_taken'] or '').lower())].append(d)

        for key, srows in stored.items():
            avails = avail_by_key.get(key, [])
            if len(srows) != 1 or len(avails) != 1:
                skipped_ambig += len(srows)
                continue
            if avails[0]:
                continue  # tem cobertura → mantém
            s = srows[0]
            cleared += 1
            if len(examples) < 20:
                examples.append(f"  t{tid} {key[0]} preflop/{key[1]} | gto "
                                f"{s['gto_label']}/{s['gto_action']} -> NULL")
            if args.apply:
                conn.execute("UPDATE decisions SET gto_label=NULL, gto_action=NULL WHERE id=?",
                             (s['id'],))
    if args.apply:
        conn.commit()
    conn.close()

    print(f"\nPreflop gto stale limpos (-> NULL): {cleared} | pulados (ambíguo): {skipped_ambig}")
    if examples:
        print("Exemplos:\n" + "\n".join(examples))
    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN (use --apply)'}")


if __name__ == "__main__":
    main()
