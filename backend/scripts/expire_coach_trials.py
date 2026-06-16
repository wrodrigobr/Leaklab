"""
COACH-02 — Expira os Pros de cortesia (trial de 3 meses) dos coaches.

Para cada coach cujo trial VENCEU (`plan_source='coach_trial'` e `coach_trial_ends_at < agora`):
  - ≥ 15 indicados pagantes  → `plan_source='coach_earned'` (mantém o Pro, permanente);
  - < 15                      → downgrade p/ Free (`plan='free'`, `plan_source=NULL`).
A comissão (% por aluno pagante) é independente e NÃO é afetada.

Pensado para rodar como CRON DIÁRIO — mesmo padrão de `take_leaderboard_snapshot.py`.
    # Windows Task Scheduler: tarefa diária `LeakLab-CoachTrialExpiry` apontando p/ este script.
    # cron (Linux):  0 4 * * *  cd /app/backend && python scripts/expire_coach_trials.py

Uso:
    cd backend
    python scripts/expire_coach_trials.py            # aplica
    python scripts/expire_coach_trials.py --dry-run  # só relata, não altera
"""
import sys
import argparse

sys.path.insert(0, ".")

from database.schema import init_db, get_conn
from database.repositories import expire_coach_trials, _adapt, _now_str


def _preview():
    """Lista (sem alterar) os trials vencidos e o destino que cada um teria."""
    conn = get_conn()
    try:
        now = _now_str()
        rows = conn.execute(_adapt(
            "SELECT id, username FROM users WHERE role='coach' AND plan_source='coach_trial' "
            "AND coach_trial_ends_at IS NOT NULL AND coach_trial_ends_at < ?"), (now,)).fetchall()
        out = []
        for r in rows:
            cid = r['id']
            paying = conn.execute(_adapt(
                "SELECT COUNT(*) AS n FROM users WHERE coach_id=? "
                "AND invited_via_invite_id IS NOT NULL AND link_status='approved' AND plan='pro'"),
                (cid,)).fetchone()['n']
            out.append((cid, r['username'], paying, 'earned' if paying >= 15 else 'downgrade'))
        return out
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Expira os Pros de cortesia dos coaches (COACH-02).")
    ap.add_argument("--dry-run", action="store_true", help="só relata, não altera")
    args = ap.parse_args()

    init_db()  # garante schema/migrations (idempotente)

    if args.dry_run:
        prev = _preview()
        print(f"Trials vencidos: {len(prev)}")
        for cid, name, paying, dest in prev:
            print(f"  coach#{cid} {name}: {paying}/15 pagantes → {dest}")
        print("DRY-RUN (nada alterado)")
        return

    res = expire_coach_trials()
    print(f"Verificados: {res['checked']} | promovidos (earned): {len(res['promoted'])} "
          f"| downgrade: {len(res['downgraded'])}")
    if res['promoted']:
        print(f"  earned:    {res['promoted']}")
    if res['downgraded']:
        print(f"  downgrade: {res['downgraded']}")


if __name__ == "__main__":
    main()
