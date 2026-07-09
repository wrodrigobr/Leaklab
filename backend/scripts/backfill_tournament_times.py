"""
backfill_tournament_times.py — popula tournaments.started_at / ended_at nos torneios já
importados, extraindo o timestamp da 1ª e da última mão do raw_text (que já está no banco).

Base para as análises de sessão (concorrência/multi-tabling, fadiga, horário). READ do raw,
WRITE só das 2 colunas. Idempotente. Só toca quem tem raw_text e ainda está com started_at NULL
(ou --all para reprocessar todos).

Uso:
    python -m scripts.backfill_tournament_times            # dry-run (conta)
    python -m scripts.backfill_tournament_times --apply
    python -m scripts.backfill_tournament_times --apply --all
"""
import sys, os
_here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
for _cand in (os.path.join(_here, '..'), _here, os.getcwd(), '/app/backend', '/app'):
    if os.path.isdir(os.path.join(_cand, 'database')):
        sys.path.insert(0, _cand)
        break

from database.schema import get_conn, init_db, USE_POSTGRES
from leaklab.parser import extract_session_times


def main():
    apply = '--apply' in sys.argv
    do_all = '--all' in sys.argv
    init_db()
    conn = get_conn()
    if not USE_POSTGRES:
        try:
            conn.execute("PRAGMA busy_timeout=10000")
        except Exception:
            pass

    where = "raw_text IS NOT NULL" + ("" if do_all else " AND started_at IS NULL")
    rows = conn.execute(f"SELECT id, raw_text FROM tournaments WHERE {where}").fetchall()
    total = len(rows)
    updated = skipped = 0
    for r in rows:
        d = dict(r)
        st, en = extract_session_times(d.get('raw_text'))
        if not st:
            skipped += 1
            continue
        if apply:
            conn.execute("UPDATE tournaments SET started_at=?, ended_at=? WHERE id=?",
                         (st, en, d['id']))
        updated += 1
    if apply:
        conn.commit()
    conn.close()
    print(f"torneios candidatos: {total}")
    print(f"  com timestamp (atualizados): {updated}")
    print(f"  sem timestamp no raw (pulados): {skipped}")
    print("APLICADO" if apply else "DRY-RUN (use --apply)")


if __name__ == "__main__":
    main()
