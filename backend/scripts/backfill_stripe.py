"""backfill_stripe.py — popula subscription_status + MRR a partir do Stripe.

Para cada usuário com assinatura Stripe (users.mp_subscription_id começando com 'sub_'):
  1. busca a Subscription no Stripe (status, vigência, motivo de cancelamento);
  2. reaplica via apply_stripe_subscription → grava subscription_status / plan_expires_at /
     past_due_since / canceled_at / cancel_reason (mesma lógica do webhook);
  3. para assinaturas ativas, grava UMA linha de payments aprovada com o valor real (preço do
     Stripe) e o span do período (mensal/anual) — assim o MRR real (_real_mrr_cents) popula.
     Idempotente: save_payment deduplica por (gateway_id=latest_invoice, status).

Requer no ambiente: STRIPE_SECRET_KEY e DATABASE_URL (Neon em prod). Rode no servidor:
    docker compose exec web python scripts/backfill_stripe.py            # aplica
    docker compose exec web python scripts/backfill_stripe.py --dry-run  # só mostra
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import apply_stripe_subscription, save_payment, _adapt
from leaklab.stripe_gateway import get_subscription


def _ts(v):
    try:
        return datetime.utcfromtimestamp(int(v)).isoformat() if v else None
    except Exception:
        return None


def _amount_and_span(sub):
    """(amount_cents, currency, interval) do 1º item da assinatura."""
    try:
        item = (sub.get('items', {}).get('data') or [])[0]
        price = item.get('price') or {}
        amt = int(price.get('unit_amount') or 0)
        cur = (price.get('currency') or 'brl').upper()
        interval = (price.get('recurring') or {}).get('interval', 'month')
        return amt, cur, interval
    except Exception:
        return 0, 'BRL', 'month'


def main() -> int:
    dry = '--dry-run' in sys.argv
    if not os.environ.get('STRIPE_SECRET_KEY'):
        print('STRIPE_SECRET_KEY não setada — rode no servidor (docker compose exec web ...).')
        return 2
    backend = 'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite (dev)'
    conn = get_conn()
    try:
        rows = conn.execute(_adapt(
            "SELECT id, username, mp_subscription_id FROM users "
            "WHERE mp_subscription_id LIKE 'sub_%'")).fetchall()
    finally:
        conn.close()
    rows = [dict(r) for r in rows]
    print(f"[{backend}] {len(rows)} usuários com assinatura Stripe{' (DRY-RUN)' if dry else ''}")

    applied = paid = skipped = errors = 0
    for u in rows:
        uid, sub_id = u['id'], u['mp_subscription_id']
        sub = get_subscription(sub_id)
        if not sub:
            print(f"  user {uid} @{u['username']}: assinatura {sub_id} não encontrada no Stripe — skip")
            errors += 1
            continue
        status = sub.get('status')
        per_end = _ts(sub.get('current_period_end'))
        per_start = _ts(sub.get('current_period_start'))
        reason = (sub.get('cancellation_details') or {}).get('reason') if status == 'canceled' else None
        amt, cur, interval = _amount_and_span(sub)
        print(f"  user {uid} @{u['username']}: status={status} valor={amt}{cur}/{interval} vig={per_end}")
        if dry:
            continue
        # 1) status/vigência/churn
        apply_stripe_subscription(uid, status, per_end, sub_id, cancel_reason=reason)
        applied += 1
        # 2) linha de pagamento real (só ativa/trial) → MRR popula
        if status in ('active', 'trialing') and amt > 0:
            inv = sub.get('latest_invoice')
            inv_id = inv.get('id') if isinstance(inv, dict) else (inv or f"{sub_id}:{per_start}")
            save_payment(uid, 'pro', amt, 'approved', gateway_id=inv_id, gateway_sub_id=sub_id,
                         period_start=per_start, period_end=per_end, currency=cur, gateway='stripe')
            paid += 1
        else:
            skipped += 1

    print(f"\n{'(dry-run) ' if dry else ''}status aplicado: {applied} · pagamentos gravados: {paid} · "
          f"sem pgto: {skipped} · erros: {errors}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
