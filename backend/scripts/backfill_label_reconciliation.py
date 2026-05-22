"""
backfill_label_reconciliation.py — Roda reconcile_tournament_labels para
todos os torneios do banco (ou de um usuario), garantindo que `label` esteja
alinhado com `gto_label` quando este existir.

Tambem chama sync_gto_labels_from_ranges.sync_tournament antes do reconcile,
para popular gto_label preflop a partir do JSON estatico.

Uso:
    python scripts/backfill_label_reconciliation.py                # todos torneios
    python scripts/backfill_label_reconciliation.py --user-id 1    # so user 1
    python scripts/backfill_label_reconciliation.py --dry-run      # so reporta
    python scripts/backfill_label_reconciliation.py --no-sync      # pula sync
    python scripts/backfill_label_reconciliation.py --since 2026-01-01
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / 'scripts'))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / '.env')

from database.schema import get_conn
from database.repositories import _reconcile_label, reconcile_tournament_labels


def _list_tournaments(user_id: int | None, since: str | None) -> list:
    conn = get_conn()
    try:
        sql = "SELECT id, tournament_id, user_id, imported_at, labels_reconciled_at FROM tournaments WHERE 1=1"
        params: list = []
        if user_id is not None:
            sql += " AND user_id = ?"; params.append(user_id)
        if since:
            sql += " AND imported_at >= ?"; params.append(since)
        sql += " ORDER BY imported_at ASC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _count_pending(t_id: int) -> int:
    """Quantas decisions teriam label alterado se reconcile rodasse agora."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT label, gto_label FROM decisions WHERE tournament_id=? "
            "AND gto_label IS NOT NULL AND gto_label != '' "
            "AND label IS NOT NULL AND label != ''", (t_id,)
        ).fetchall()
        n = 0
        for r in rows:
            if _reconcile_label(r['label'], r['gto_label']) != r['label']:
                n += 1
        return n
    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--user-id', type=int, default=None)
    p.add_argument('--since', type=str, default=None, help='ISO date filter on imported_at')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--no-sync', action='store_true', help='Pula sync_gto_labels_from_ranges')
    args = p.parse_args()

    tournaments = _list_tournaments(args.user_id, args.since)
    print(f"Encontrados {len(tournaments)} torneios para processar")
    if args.dry_run:
        print("[DRY-RUN] Nada sera escrito.\n")

    total_pending_before = 0
    total_reconciled = 0
    total_synced = 0

    for t in tournaments:
        pending = _count_pending(t['id'])
        total_pending_before += pending

        if args.dry_run:
            stamp = t['labels_reconciled_at'] or '(nunca)'
            print(f"  t={t['id']:>5}  user={t['user_id']:>4}  tid={t['tournament_id']:<14}  "
                  f"pending={pending:>3}  last_reconciled={stamp}")
            continue

        if not args.no_sync:
            try:
                from sync_gto_labels_from_ranges import sync_tournament
                synced = sync_tournament(t['id']) or 0
                total_synced += synced
            except Exception as e:
                print(f"  [WARN] sync falhou tid={t['id']}: {e}")

        try:
            n = reconcile_tournament_labels(t['id'])
            total_reconciled += n
            if pending > 0 or n > 0:
                print(f"  t={t['id']:>5}  reconciled={n:>3}  (pending_before={pending})")
        except Exception as e:
            print(f"  [ERR] reconcile falhou tid={t['id']}: {e}")

    print()
    print(f"Total decisions com reconciliacao pendente: {total_pending_before}")
    if not args.dry_run:
        print(f"Total decisions reconciliadas: {total_reconciled}")
        print(f"Total decisions com gto_label populado via sync: {total_synced}")


if __name__ == '__main__':
    main()
