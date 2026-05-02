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
    Cria assinatura Stripe incompleta e retorna client_secret para confirmação no frontend.
    Retorna dict com subscription_id, client_secret e status.
    """
    price_id = PLAN_PRICES.get(plan_name, "")
    if not price_id:
        raise ValueError(f"STRIPE_PRICE_{plan_name.upper()} não configurado")

    customer_id = _get_or_create_customer(user_id, payer_email)

    sub = _stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        payment_behavior="default_incomplete",
        payment_settings={"save_default_payment_method": "on_subscription"},
        expand=["latest_invoice.payment_intent"],
        metadata={"user_id": str(user_id), "plan_name": plan_name},
    )

    pi = sub["latest_invoice"]["payment_intent"]
    log.info("Stripe subscription created: sub=%s pi=%s status=%s", sub.id, pi["id"], sub.status)
    return {
        "subscription_id": sub.id,
        "client_secret":   pi["client_secret"],
        "status":          sub.status,
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
        return _stripe.Subscription.retrieve(subscription_id)
    except Exception as e:
        log.error("Failed to fetch Stripe subscription %s: %s", subscription_id, e)
        return None


def get_payment(payment_intent_id: str) -> dict | None:
    try:
        return _stripe.PaymentIntent.retrieve(payment_intent_id)
    except Exception as e:
        log.error("Failed to fetch Stripe PaymentIntent %s: %s", payment_intent_id, e)
        return None


def validate_webhook(payload: bytes, sig_header: str):
    """Valida assinatura Stripe e retorna o evento."""
    return _stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
