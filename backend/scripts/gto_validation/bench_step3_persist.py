"""
bench_step3_persist.py — RODA LOCAL. Lê benchmark_spots.json + benchmark_responses.json,
compara veredicto GW vs gto_label/gto_action armazenado, persiste em gto_nodes,
e gera relatório final.

Uso:
    python scripts/gto_validation/bench_step3_persist.py
    python scripts/gto_validation/bench_step3_persist.py --dry-run
    python scripts/gto_validation/bench_step3_persist.py --report-only  # nao persiste
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from leaklab.gto_utils import stack_bucket as canonical_stack_bucket, compute_spot_hash


def gw_label_from_freq(freq: float) -> str:
    if freq >= 0.60: return "gto_correct"
    if freq >= 0.30: return "gto_mixed"
    if freq >= 0.10: return "gto_minor_deviation"
    return "gto_critical"


def norm_act(a: str) -> str:
    a = (a or "").lower().rstrip("s")
    return {"raise": "bet", "bet": "bet", "all_in": "allin", "allin": "allin",
            "jam": "allin", "fold": "fold", "call": "call", "check": "check"}.get(a, a)


def make_spot_hash(street: str, position: str, hero_hand: str,
                   stack_bucket: str, preflop_actions: str) -> str:
    raw = f"{street}|{position}|{hero_hand}|{stack_bucket}|{preflop_actions}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def upsert_gto_node(conn, spot_hash: str, position: str, hero_hand: str,
                    stack_bucket: str, gto_action: str, gto_freq: float,
                    strategy: dict, preflop_actions: str) -> bool:
    """Insert ou update. Retorna True se foi insert."""
    existing = conn.execute(
        "SELECT id FROM gto_nodes WHERE spot_hash=?", (spot_hash,)
    ).fetchone()
    # Embute preflop_actions no strategy_json para retrievability futura
    strategy_payload = {"strategy": strategy, "preflop_actions": preflop_actions}
    payload = (
        gto_action, gto_freq, "gto_wizard",
        json.dumps(strategy_payload, ensure_ascii=False), 0,
    )
    if existing:
        conn.execute(
            "UPDATE gto_nodes SET gto_action=?, gto_freq=?, source=?, "
            "strategy_json=?, is_aggregate=? WHERE spot_hash=?",
            payload + (spot_hash,),
        )
        return False
    conn.execute(
        "INSERT INTO gto_nodes (spot_hash, street, position, board, hero_hand, "
        "stack_bucket, gto_action, gto_freq, source, strategy_json, is_aggregate) "
        "VALUES (?, 'preflop', ?, '[]', ?, ?, ?, ?, ?, ?, ?)",
        (spot_hash, position, hero_hand, stack_bucket,
         gto_action, gto_freq, "gto_wizard",
         json.dumps(strategy_payload, ensure_ascii=False), 0),
    )
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--spots",     default=str(SCRIPT_DIR / "benchmark_spots.json"))
    p.add_argument("--responses", default=str(SCRIPT_DIR / "benchmark_responses.json"))
    p.add_argument("--report",    default=str(SCRIPT_DIR / "benchmark_report.json"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--report-only", action="store_true",
                   help="Apenas gera relatório; nao persiste em gto_nodes")
    args = p.parse_args()

    spots_by_id = {s["id"]: s for s in json.loads(Path(args.spots).read_text(encoding="utf-8"))}
    responses    = json.loads(Path(args.responses).read_text(encoding="utf-8"))
    print(f"Spots: {len(spots_by_id)}  Responses: {len(responses)}")

    from database.schema import get_conn
    db = get_conn()

    stats = Counter()
    by_type_agree = defaultdict(lambda: {"total": 0, "agree": 0, "disagree": 0, "no_stored": 0})
    by_status     = Counter()
    details = []
    inserted = updated = 0

    for resp in responses:
        spot = spots_by_id.get(resp["id"])
        if not spot:
            continue
        status = resp.get("status", 0)
        by_status[status] += 1
        spot_type = spot.get("spot_type", "?")

        if status != 200:
            by_type_agree[spot_type]["total"] += 1
            details.append({
                "id": spot["id"], "pos": spot["position"], "stack": spot["stack_bb"],
                "preflop_actions": spot["preflop_actions"], "spot_type": spot_type,
                "status": status, "result": "skip", "body": resp.get("body", "")[:120],
            })
            continue

        strategy = resp.get("strategy_aggregated", {})
        if not strategy:
            continue
        gw_top = resp.get("gw_top") or max(strategy, key=lambda k: strategy[k])
        gw_top_freq = strategy[gw_top]

        stored_act = norm_act(spot.get("stored_gto_action") or "")
        stored_lbl = spot.get("stored_gto_label")
        action_taken = norm_act(spot.get("action_taken") or "")

        # Label que GW daria para a ação que o player tomou
        freq_played = strategy.get(action_taken, 0.0)
        gw_label_for_played = gw_label_from_freq(freq_played)

        by_type_agree[spot_type]["total"] += 1
        if not stored_lbl:
            by_type_agree[spot_type]["no_stored"] += 1
            agree = "no_stored"
        elif stored_act == gw_top:
            by_type_agree[spot_type]["agree"] += 1
            agree = "AGREE"
        else:
            by_type_agree[spot_type]["disagree"] += 1
            agree = "DIFF"

        # Persist em gto_nodes — usa compute_spot_hash do projeto (mesma chave do engine)
        # Sem isso, lookup do engine nao acha esses nodes.
        if not (args.dry_run or args.report_only):
            sb = canonical_stack_bucket(float(spot["stack_bb"]))
            # hero_cards no DB e JSON array como '["Kd","9h"]' — parseia
            try:
                import json as _json
                hand_list = _json.loads(spot["hero_cards"]) if spot["hero_cards"].startswith("[") else \
                            [spot["hero_cards"][i:i+2] for i in range(0, len(spot["hero_cards"]), 2)]
            except Exception:
                hand_list = [spot["hero_cards"][:2], spot["hero_cards"][2:4]] if len(spot["hero_cards"]) >= 4 else []
            sh = compute_spot_hash(
                "preflop", spot["position"], [], hand_list,
                float(spot["stack_bb"]), float(spot.get("facing_bet") or 0),
            )
            stack_bucket = sb
            was_new = upsert_gto_node(
                db, sh, spot["position"], spot["hero_cards"], stack_bucket,
                gw_top, gw_top_freq, strategy, spot["preflop_actions"],
            )
            if was_new:
                inserted += 1
            else:
                updated += 1

        details.append({
            "id": spot["id"], "pos": spot["position"], "stack": spot["stack_bb"],
            "hand": spot["hero_cards"], "preflop_actions": spot["preflop_actions"],
            "spot_type": spot_type, "status": 200,
            "stored_label": stored_lbl, "stored_action": stored_act,
            "gw_strategy": strategy, "gw_top": gw_top, "gw_top_freq": gw_top_freq,
            "action_taken": action_taken, "freq_played": freq_played,
            "gw_label_for_played": gw_label_for_played,
            "agreement_top": agree,
        })

    if not (args.dry_run or args.report_only):
        db.commit()
    db.close()

    # Relatorio
    report = {
        "stats": {
            "total_responses": len(responses),
            "by_http_status": dict(by_status),
            "by_spot_type": {k: dict(v) for k, v in by_type_agree.items()},
            "persisted": {"inserted": inserted, "updated": updated},
            "dry_run": args.dry_run or args.report_only,
        },
        "details": details,
    }
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                  encoding="utf-8")

    print("\n=== HTTP status ===")
    for s, n in sorted(by_status.items()):
        print(f"  {s}: {n}")

    print("\n=== Por spot_type (only HTTP 200) ===")
    print(f"{'spot_type':<25} {'total':>6} {'agree':>6} {'disagree':>9} {'no_stored':>10}")
    for t, v in sorted(by_type_agree.items(), key=lambda x: -x[1]["total"]):
        print(f"  {t:<23} {v['total']:>6} {v['agree']:>6} {v['disagree']:>9} {v['no_stored']:>10}")

    print(f"\n=== Persistência em gto_nodes ===")
    print(f"  inserted: {inserted}  updated: {updated}")
    if args.dry_run or args.report_only:
        print(f"  [{'DRY-RUN' if args.dry_run else 'REPORT-ONLY'}] DB nao alterado")

    print(f"\nRelatório: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
