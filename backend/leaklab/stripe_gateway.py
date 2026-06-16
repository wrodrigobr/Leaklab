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

PLAN_PRICES: dict[str, str] = {
    "pro": os.environ.get("STRIPE_PRICE_PRO", ""),
}

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
    Cria PaymentIntent Stripe e retorna client_secret para confirmação no frontend.
    Usa PaymentIntent direto (sem Subscription) para evitar complexidade da
    Invoice.payments API que mudou em 2025-03-31.
    `billing_cycle`: 'monthly' (R$99/30d) ou 'annual' (R$990/365d).
    Retorna dict com subscription_id (= pi_id), client_secret e status.
    """
    amount_cents = int(plan_amount(plan_name, billing_cycle) * 100)
    customer_id  = _get_or_create_customer(user_id, payer_email)
    label = "anual" if billing_cycle == "annual" else "mensal"

    pi = _stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="brl",
        customer=customer_id,
        # allow_redirects=never: só métodos não-redirect (cartão), permite confirmar sem return_url
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        metadata={"user_id": str(user_id), "plan_name": plan_name, "billing_cycle": billing_cycle},
        # description aparece no recibo/fatura do cliente → usa a marca visível (GrindLab).
        description=f"GrindLab {plan_name.title()} — {label}",
    )

    log.info("Stripe PaymentIntent created: pi=%s amount=%s cycle=%s", pi.id, amount_cents, billing_cycle)
    return {
        "subscription_id": pi.id,   # usamos o pi_id como referência de cobrança
        "client_secret":   pi.client_secret,
        "status":          pi.status,
        "billing_cycle":   billing_cycle,
    }


def cancel_subscription(subscription_id: str) -> bool:
    """Cancela a assinatura no Stripe.

    PAY-01: o modelo atual cobra um PaymentIntent único de 30 dias (`pi_...`), NÃO uma
    Subscription recorrente — não há nada a cancelar no Stripe nesses casos (chamar
    Subscription.cancel(pi_...) lança erro). Só chamamos o Stripe para ids de assinatura
    de verdade (`sub_...`); para `pi_...` o cancelamento é apenas local (downgrade).
    """
    if not subscription_id or not subscription_id.startswith("sub_"):
        log.info("cancel_subscription: non-subscription id %r — downgrade local apenas", subscription_id)
        return True
    try:
        _stripe.Subscription.cancel(subscription_id)
        log.info("Stripe subscription cancelled: %s", subscription_id)
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
