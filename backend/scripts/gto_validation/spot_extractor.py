"""
Extrai spots únicos do banco de dados para comparação com o GTO Wizard.

Gera unique_spots.jsonl com um spot por linha, deduplicado por:
(street, position, villain_position, board_canonical, stack_bucket, facing_bucket)

Uso:
    python spot_extractor.py [--output unique_spots.jsonl] [--limit 100]
"""
from __future__ import annotations
import os, sys, json, argparse, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'leaklab.db')

STACK_BUCKETS = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]
FACING_BUCKETS = [0, 0.25, 0.33, 0.50, 0.67, 0.75, 1.0]  # fraction of pot


def _nearest(value: float, buckets: list[float]) -> float:
    return min(buckets, key=lambda b: abs(b - value))


def _stack_bucket(stack_bb: float) -> float:
    return _nearest(stack_bb, STACK_BUCKETS)


def _facing_bucket(facing_bb: float, pot_bb: float) -> float:
    """Convert facing bet to nearest pot fraction bucket."""
    if facing_bb is None or facing_bb == 0 or pot_bb is None or pot_bb == 0:
        return 0.0
    frac = facing_bb / pot_bb
    return _nearest(frac, FACING_BUCKETS)


def _board_canonical(board: str | None) -> str:
    """Sort board cards for deduplication — handles JSON array or space-separated."""
    if not board:
        return ""
    import json as _json
    try:
        cards = _json.loads(board)  # stored as JSON array: '["Ks","Qd","2c"]'
    except Exception:
        cards = board.replace(",", " ").replace("/", " ").split()
    cards = [c.strip() for c in cards if c.strip()]
    RANKS = "23456789TJQKA"
    def _rank_val(c: str) -> int:
        r = c[0].upper()
        return RANKS.index(r) if r in RANKS else 0
    return "".join(sorted(cards, key=_rank_val))


def extract_spots(limit: int = 0) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT
            d.id,
            d.street,
            d.position,
            NULL AS villain_position,
            d.board,
            d.stack_bb,
            d.facing_bet,
            d.pot_size,
            d.action_taken,
            d.best_action,
            d.score,
            d.label,
            NULL AS tournament_name
        FROM decisions d
        WHERE d.street IS NOT NULL
          AND d.position IS NOT NULL
        ORDER BY d.score DESC
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = conn.execute(query).fetchall()
    conn.close()

    seen: dict[str, dict] = {}

    for r in rows:
        board_canon = _board_canonical(r["board"] or "")
        stack_b = _stack_bucket(float(r["stack_bb"] or 20))
        facing_b = _facing_bucket(
            float(r["facing_bet"] or 0),
            float(r["pot_size"] or 1),
        )
        key = "|".join([
            str(r["street"] or ""),
            str(r["position"] or ""),
            str(r["villain_position"] or ""),
            board_canon,
            str(stack_b),
            str(facing_b),
        ])

        if key not in seen:
            import json as _json
            board_raw = r["board"] or ""
            try:
                board_cards = " ".join(_json.loads(board_raw))
            except Exception:
                board_cards = board_raw
            seen[key] = {
                "spot_id": key.replace("|", "_"),
                "street": r["street"],
                "position": r["position"],
                "villain_position": r["villain_position"],
                "board": board_cards,
                "board_canonical": board_canon,
                "stack_bb": float(r["stack_bb"] or 20),
                "stack_bucket": stack_b,
                "facing_bet": float(r["facing_bet"] or 0),
                "facing_bucket": facing_b,
                "pot_size": float(r["pot_size"] or 0),
                "example_decision_id": r["id"],
                "example_action_taken": r["action_taken"],
                "example_best_action": r["best_action"],
                "our_score": float(r["score"] or 0),
                "our_label": r["label"],
                "occurrences": 1,
            }
        else:
            seen[key]["occurrences"] += 1

    spots = sorted(seen.values(), key=lambda s: -s["occurrences"])
    return spots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="unique_spots.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="Max decisions to scan (0=all)")
    parser.add_argument("--min-occurrences", type=int, default=1)
    args = parser.parse_args()

    print(f"Extracting spots from {DB_PATH}")
    spots = extract_spots(args.limit)

    filtered = [s for s in spots if s["occurrences"] >= args.min_occurrences]
    print(f"Total unique spots: {len(filtered)} (from {sum(s['occurrences'] for s in filtered)} decisions)")

    outpath = os.path.join(os.path.dirname(__file__), args.output)
    with open(outpath, "w", encoding="utf-8") as f:
        for spot in filtered:
            f.write(json.dumps(spot) + "\n")

    print(f"Written to {outpath}")

    # Print top 20 by occurrences
    print(f"\nTop 20 spots by frequency:")
    print(f"{'Street':<8} {'Pos':<6} {'VPos':<6} {'Board':<14} {'Stack':>6} {'Facing':>7} {'N':>4} {'Label':<12}")
    print("-" * 75)
    for s in filtered[:20]:
        board = s["board_canonical"][:14]
        print(f"{s['street']:<8} {s['position']:<6} {str(s['villain_position']):<6} "
              f"{board:<14} {s['stack_bucket']:>6.1f} {s['facing_bucket']:>7.2f} "
              f"{s['occurrences']:>4} {s['our_label']:<12}")


if __name__ == "__main__":
    main()
