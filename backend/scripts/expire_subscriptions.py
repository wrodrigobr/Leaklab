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

from database.schema import init_db
from database.repositories import expire_subscriptions


def main():
    ap = argparse.ArgumentParser(description="Expira assinaturas Pro vencidas (PAY-02).")
    ap.add_argument("--dry-run", action="store_true", help="só relata, não altera")
    args = ap.parse_args()

    init_db()

    if args.dry_run:
        # MESMA consulta da execucao real (o preview tinha a sua propria, mais frouxa).
        prev = expire_subscriptions(dry_run=True)['alvos']
        print(f"Assinaturas vencidas: {len(prev)}")
        for a in prev:
            print(f"  user#{a['id']} {a['username']}: venceu {a['plan_expires_at']}")
        print("DRY-RUN (nada alterado)")
        return

    res = expire_subscriptions()
    print(f"Downgrade aplicado: {len(res['downgraded'])} (em {res['at']})")
    if res['downgraded']:
        print(f"  ids: {res['downgraded']}")


if __name__ == "__main__":
    main()
