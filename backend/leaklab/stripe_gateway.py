"""
stripe_gateway.py — Stripe Billing integration (Checkout Transparente).
Assinaturas recorrentes via Stripe Subscriptions API + confirmação no frontend.
"""
from __future__ import annotations
import os
import logging
import stripe as _stripe

log = logging.getLogger(__name__)

_stripe.api_key       = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# PAY-04: Prices RECORRENTES do Stripe (por ciclo). Quando configurados, o checkout
# cria uma Subscription de verdade (cobrança automática/recorrente). Sem eles, cai no
# fallback de PaymentIntent único (modelo legado PAY-02, sem auto-renovação).
PLAN_PRICES: dict[tuple[str, str], str] = {
    ("pro", "monthly"): os.environ.get("STRIPE_PRICE_PRO_MONTHLY", os.environ.get("STRIPE_PRICE_PRO", "")),
    ("pro", "annual"):  os.environ.get("STRIPE_PRICE_PRO_ANNUAL", ""),
}


def price_id(plan_name: str, billing_cycle: str = "monthly") -> str:
    return PLAN_PRICES.get((plan_name, billing_cycle), "")

PLAN_AMOUNTS: dict[str, float] = {
    "pro": 99.00,
}

# PAY-02: ciclo anual com desconto (2 meses grátis → paga 10, leva 12).
PLAN_AMOUNTS_ANNUAL: dict[str, float] = {
    "pro": 990.00,   # 99 × 10 (≈ 17% off vs 1.188 cheio)
}

# Dias de vigência por ciclo (define plan_expires_at).
BILLING_DAYS: dict[str, int] = {
    "monthly": 30,
    "annual":  365,
}


def plan_amount(plan_name: str, billing_cycle: str = "monthly") -> float:
    """Valor (R$) do plano no ciclo. Fonte única de preço p/ checkout/ativação."""
    if billing_cycle == "annual":
        return PLAN_AMOUNTS_ANNUAL[plan_name]
    return PLAN_AMOUNTS[plan_name]


def _get_or_create_customer(user_id: int, email: str) -> str:
    result = _stripe.Customer.search(query=f"metadata['user_id']:'{user_id}'")
    if result.data:
        return result.data[0].id
    customer = _stripe.Customer.create(
        email=email,
        metadata={"user_id": str(user_id)},
    )
    return customer.id


def create_subscription(plan_name: str, payer_email: str, user_id: int,
                        billing_cycle: str = "monthly") -> dict:
    """
    PAY-04: cria uma **Subscription recorrente** do Stripe (cobrança automática) quando há
    Price recorrente configurado para o ciclo; senão cai no PaymentIntent único (legado).

    Subscription (recorrente): cobra sozinho a cada ciclo, com dunning/retry do Stripe.
    Retorna o client_secret do PaymentIntent da 1ª fatura para confirmação no frontend.
    PaymentIntent (fallback): cobrança única, sem auto-renovação (vence via plan_expires_at).

    Retorna: {subscription_id, client_secret, status, billing_cycle, recurring}.
    """
    customer_id = _get_or_create_customer(user_id, payer_email)
    pid = price_id(plan_name, billing_cycle)
    meta = {"user_id": str(user_id), "plan_name": plan_name, "billing_cycle": billing_cycle}

    if pid:
        # A API atual do Stripe expõe o client_secret da 1ª fatura em
        # latest_invoice.confirmation_secret (o antigo latest_invoice.payment_intent
        # foi removido). Mantemos um fallback p/ contas em API mais antiga.
        sub = _stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": pid}],
            payment_behavior="default_incomplete",
            payment_settings={"save_default_payment_method": "on_subscription"},
            expand=["latest_invoice.confirmation_secret"],
            metadata=meta,
        )
        inv = sub.latest_invoice
        cs  = getattr(inv, "confirmation_secret", None)
        client_secret = getattr(cs, "client_secret", None) if cs else None
        if not client_secret:                      # fallback (API antiga)
            pi = getattr(inv, "payment_intent", None)
            client_secret = getattr(pi, "client_secret", None) if pi else None
        if not client_secret:
            raise RuntimeError("Stripe: não obtive o client_secret da assinatura")
        log.info("Stripe Subscription created: sub=%s status=%s cycle=%s", sub.id, sub.status, billing_cycle)
        return {
            "subscription_id": sub.id,
            "client_secret":   client_secret,
            "status":          sub.status,
            "billing_cycle":   billing_cycle,
            "recurring":       True,
        }

    # Fallback legado: PaymentIntent único (sem recorrência) — dev/sem Price configurado.
    amount_cents = int(plan_amount(plan_name, billing_cycle) * 100)
    label = "anual" if billing_cycle == "annual" else "mensal"
    pi = _stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="brl",
        customer=customer_id,
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        metadata=meta,
        description=f"GrindLab {plan_name.title()} — {label}",
    )
    log.info("Stripe PaymentIntent created (fallback): pi=%s amount=%s cycle=%s", pi.id, amount_cents, billing_cycle)
    return {
        "subscription_id": pi.id,
        "client_secret":   pi.client_secret,
        "status":          pi.status,
        "billing_cycle":   billing_cycle,
        "recurring":       False,
    }


def create_billing_portal_session(user_id: int, return_url: str) -> dict | None:
    """PAY-04: sessão do Billing Portal hospedado do Stripe (cliente gerencia cartão,
    faturas e cancelamento self-service). Retorna {url} ou None se não houver customer."""
    cid = get_customer_id(user_id)
    if not cid:
        return None
    sess = _stripe.billing_portal.Session.create(customer=cid, return_url=return_url)
    return {"url": sess.url}


def get_customer_id(user_id: int) -> str | None:
    res = _stripe.Customer.search(query=f"metadata['user_id']:'{user_id}'")
    return res.data[0].id if res.data else None


def cancel_subscription(subscription_id: str, at_period_end: bool = False) -> bool:
    """Cancela a assinatura no Stripe.

    `at_period_end=True`: agenda cancelamento p/ o fim do período (mantém Pro até lá).
    `at_period_end=False`: cancela imediatamente.

    PAY-01: ids `pi_...` (PaymentIntent legado, sem recorrência) não têm o que cancelar
    no Stripe — cancelamento é só local (downgrade). Só chamamos o Stripe para `sub_...`.
    """
    if not subscription_id or not subscription_id.startswith("sub_"):
        log.info("cancel_subscription: non-subscription id %r — downgrade local apenas", subscription_id)
        return True
    try:
        if at_period_end:
            _stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        else:
            _stripe.Subscription.cancel(subscription_id)
        log.info("Stripe subscription cancelled (at_period_end=%s): %s", at_period_end, subscription_id)
        return True
    except Exception as e:
        log.error("Stripe cancel error %s: %s", subscription_id, e)
        raise


def get_subscription(subscription_id: str) -> dict | None:
    try:
        return _stripe.Subscription.retrieve(subscription_id).to_dict()
    except Exception as e:
        log.error("Failed to fetch Stripe subscription %s: %s", subscription_id, e)
        return None


def get_payment(payment_intent_id: str) -> dict | None:
    try:
        return _stripe.PaymentIntent.retrieve(payment_intent_id).to_dict()
    except Exception as e:
        log.error("Failed to fetch Stripe PaymentIntent %s: %s", payment_intent_id, e)
        return None


def validate_webhook(payload: bytes, sig_header: str):
    """Valida assinatura Stripe e retorna o evento."""
    return _stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
