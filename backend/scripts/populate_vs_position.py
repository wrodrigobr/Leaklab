"""
Populates decisions.vs_position for existing vs_RFI spots by re-parsing
the hand history text stored in tournaments.raw_text.

For each decision where facing_bet > 0 AND is_3bet = 0 AND vs_position IS NULL,
this script:
  1. Loads the tournament's raw_text
  2. Finds the hand matching decision.hand_id
  3. Finds the first preflop raises/all-in action that isn't the hero
  4. Maps that player's name to their position via the same logic as hand_state_builder
  5. Updates decisions.vs_position

Usage:
    cd backend
    python scripts/populate_vs_position.py [--dry-run] [--limit N]
"""
import sys
import re
import argparse
sys.path.insert(0, ".")

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.hand_state_builder import _infer_position


def _find_rfi_position(hand, hero_name: str) -> str | None:
    """
    Find the position of the first preflop raiser that is not the hero.
    Returns position string or None if not found.
    """
    for action in hand.actions:
        if action.street != 'preflop':
            break
        if action.player == hero_name:
            continue
        if action.action in ('raises', 'all-in'):
            return _infer_position(hand, action.player)
    return None


def populate(dry_run: bool = False, limit: int = 0):
    conn = get_conn()
    try:
        # Ensure column exists (migration may not have run yet on this connection)
        try:
            conn.execute("ALTER TABLE decisions ADD COLUMN vs_position TEXT")
            conn.commit()
        except Exception:
            pass

        query = """
            SELECT d.id, d.hand_id, d.position, d.tournament_id,
                   t.raw_text, t.hero
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.street = 'preflop'
              AND COALESCE(d.facing_bet, 0) > 0
              AND COALESCE(d.is_3bet, 0) = 0
              AND d.vs_position IS NULL
              AND t.raw_text IS NOT NULL
        """
        if limit:
            query += f" LIMIT {limit}"

        rows = conn.execute(query).fetchall()
        print(f"Found {len(rows)} decisions to process")

        # Group by tournament_id to avoid re-parsing the same text repeatedly
        by_tournament: dict[int, list] = {}
        for row in rows:
            tid = row['tournament_id']
            by_tournament.setdefault(tid, []).append(row)

        total_updated = 0
        total_failed = 0

        for tid, decisions in by_tournament.items():
            raw_text = decisions[0]['raw_text']
            hero = decisions[0]['hero'] or ''

            try:
                hands = parse_hand_history(raw_text)
            except Exception as e:
                print(f"  [WARN] tournament {tid}: parse error — {e}")
                total_failed += len(decisions)
                continue

            hand_by_id = {h.hand_id: h for h in hands}

            for dec in decisions:
                hand_id = dec['hand_id']
                hand = hand_by_id.get(hand_id)
                if not hand:
                    total_failed += 1
                    continue

                vs_pos = _find_rfi_position(hand, hero)
                if not vs_pos:
                    total_failed += 1
                    continue

                if not dry_run:
                    conn.execute(
                        "UPDATE decisions SET vs_position = ? WHERE id = ?",
                        (vs_pos, dec['id'])
                    )
                total_updated += 1

        if not dry_run:
            conn.commit()

        mode = "[DRY RUN] " if dry_run else ""
        print(f"\n{mode}Updated: {total_updated}  |  Failed/skipped: {total_failed}")

    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    populate(dry_run=args.dry_run, limit=args.limit)
