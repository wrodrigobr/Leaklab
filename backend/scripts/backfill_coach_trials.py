"""
COACH-02 P3 — Backfill: concede o Pro de cortesia aos coaches LEGADOS.

Coaches aprovados ANTES da feature ficaram com `plan_source` NULL (plano free, sem trial).
Este script grandfathera essas relações:
  - coach com ≥15 indicados pagantes  → 'coach_earned' (Pro permanente, meta já batida);
  - demais                            → 'coach_trial' de 90 dias a partir de agora.

DECISÃO DE PRODUTO (spec §7): rode se quiser dar a cortesia retroativa aos coaches
existentes. Idempotente (só toca em quem tem plan_source NULL).

Uso:
    cd backend
    python scripts/backfill_coach_trials.py            # aplica
    python scripts/backfill_coach_trials.py --dry-run  # só relata
"""
import sys
import argparse

sys.path.insert(0, ".")

from database.schema import init_db, get_conn
from database.repositories import backfill_coach_trials, _adapt, COACH_PRO_TARGET


def _preview():
    conn = get_conn()
    try:
        rows = conn.execute(_adapt(
            "SELECT id, username FROM users WHERE role='coach' AND plan_source IS NULL")).fetchall()
        out = []
        for r in rows:
            paying = conn.execute(_adapt(
                "SELECT COUNT(*) AS n FROM users WHERE coach_id=? "
                "AND invited_via_invite_id IS NOT NULL AND link_status='approved' AND plan='pro'"),
                (r['id'],)).fetchone()['n']
            out.append((r['id'], r['username'], paying,
                        'earned' if paying >= COACH_PRO_TARGET else 'trial'))
        return out
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Backfill do Pro de cortesia p/ coaches legados (COACH-02).")
    ap.add_argument("--dry-run", action="store_true", help="só relata, não altera")
    args = ap.parse_args()

    init_db()

    if args.dry_run:
        prev = _preview()
        print(f"Coaches legados (plan_source NULL): {len(prev)}")
        for cid, name, paying, dest in prev:
            print(f"  coach#{cid} {name}: {paying}/{COACH_PRO_TARGET} pagantes → {dest}")
        print("DRY-RUN (nada alterado)")
        return

    res = backfill_coach_trials()
    print(f"Backfill: {res['total']} coach(es) | trial: {len(res['trial'])} | earned: {len(res['earned'])}")
    if res['trial']:
        print(f"  trial:  {res['trial']}")
    if res['earned']:
        print(f"  earned: {res['earned']}")


if __name__ == "__main__":
    main()
