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
    "starter": os.environ.get("STRIPE_PRICE_STARTER", ""),
    "pro":     os.environ.get("STRIPE_PRICE_PRO", ""),
}

PLAN_AMOUNTS: dict[str, float] = {
    "starter": 19.00,
    "pro":     39.00,
}


def _get_or_create_customer(user_id: int, email: str) -> str:
    result = _stripe.Customer.search(query=f"metadata['user_id']:'{user_id}'")
    if result.data:
        return result.data[0].id
    customer = _stripe.Customer.create(
        email=email,
        metadata={"user_id": str(user_id)},
    )
    return customer.id


def create_subscription(plan_name: str, payer_email: str, user_id: int) -> dict:
    """
    Cria PaymentIntent Stripe e retorna client_secret para confirmação no frontend.
    Usa PaymentIntent direto (sem Subscription) para evitar complexidade da
    Invoice.payments API que mudou em 2025-03-31.
    Retorna dict com subscription_id (= pi_id), client_secret e status.
    """
    amount_cents = int(PLAN_AMOUNTS[plan_name] * 100)
    customer_id  = _get_or_create_customer(user_id, payer_email)

    pi = _stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="brl",
        customer=customer_id,
        # allow_redirects=never: só métodos não-redirect (cartão), permite confirmar sem return_url
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        metadata={"user_id": str(user_id), "plan_name": plan_name},
        description=f"LeakLabs {plan_name.title()} — 30 dias",
    )

    log.info("Stripe PaymentIntent created: pi=%s amount=%s", pi.id, amount_cents)
    return {
        "subscription_id": pi.id,   # usamos o pi_id como referência de cobrança
        "client_secret":   pi.client_secret,
        "status":          pi.status,
    }


def cancel_subscription(subscription_id: str) -> bool:
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
