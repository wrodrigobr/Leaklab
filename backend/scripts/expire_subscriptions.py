"""
PAY-02 — Expira assinaturas Pro vencidas (downgrade p/ Free).

O modelo cobra um PaymentIntent único por ciclo (mensal=30d / anual=365d) e grava
`users.plan_expires_at`. Sem renovação automática, o Pro vence quando passa a data.
O `get_quota_status` já trata como Free na leitura; este job CONSOLIDA o downgrade no
banco (para contadores/MRR corretos). NÃO afeta o Pro de cortesia do coach
(coach_trial/coach_earned — governado por expire_coach_trials).

Pensado para rodar como CRON DIÁRIO (Windows Task Scheduler `LeakLab-SubscriptionExpiry`
ou cron do host).

Uso:
    cd backend
    python scripts/expire_subscriptions.py            # aplica
    python scripts/expire_subscriptions.py --dry-run  # só relata
"""
import sys
import argparse

sys.path.insert(0, ".")

from database.schema import init_db, get_conn
from database.repositories import expire_subscriptions, _adapt, _now_str


def _preview():
    conn = get_conn()
    try:
        now = _now_str()
        rows = conn.execute(_adapt(
            "SELECT id, username, plan_expires_at FROM users WHERE plan='pro' "
            "AND plan_expires_at IS NOT NULL AND plan_expires_at < ? "
            "AND (plan_source IS NULL OR plan_source NOT IN ('coach_trial','coach_earned'))"),
            (now,)).fetchall()
        return [(r['id'], r['username'], r['plan_expires_at']) for r in rows]
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description="Expira assinaturas Pro vencidas (PAY-02).")
    ap.add_argument("--dry-run", action="store_true", help="só relata, não altera")
    args = ap.parse_args()

    init_db()

    if args.dry_run:
        prev = _preview()
        print(f"Assinaturas vencidas: {len(prev)}")
        for uid, name, exp in prev:
            print(f"  user#{uid} {name}: venceu {exp}")
        print("DRY-RUN (nada alterado)")
        return

    res = expire_subscriptions()
    print(f"Downgrade aplicado: {len(res['downgraded'])} (em {res['at']})")
    if res['downgraded']:
        print(f"  ids: {res['downgraded']}")


if __name__ == "__main__":
    main()
