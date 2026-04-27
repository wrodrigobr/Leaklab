"""
mercadopago_gateway.py — Wrapper para Mercado Pago Subscriptions API (preapproval).
Usa requests diretamente, sem SDK oficial.
"""
from __future__ import annotations
import os
import hmac
import hashlib
import logging
import requests as _req

log = logging.getLogger(__name__)

MP_BASE           = "https://api.mercadopago.com"
MP_ACCESS_TOKEN   = os.environ.get("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.environ.get("MP_WEBHOOK_SECRET", "")
MP_BACK_URL       = os.environ.get("MP_BACK_URL", "https://leaklab.ai/dashboard")

PLAN_AMOUNTS: dict[str, float] = {
    "starter": 19.00,
    "pro":     39.00,
}

# Cache em memória para preapproval_plan IDs (criados uma vez por processo)
_plan_id_cache: dict[str, str] = {}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type":  "application/json",
    }


def get_or_create_plan(plan_name: str) -> str:
    """Retorna o ID do preapproval_plan MP, criando se ainda não existir."""
    if plan_name in _plan_id_cache:
        return _plan_id_cache[plan_name]

    # Verificar se já existe via search
    resp = _req.get(
        f"{MP_BASE}/preapproval_plan/search",
        params={"status": "active", "limit": 50},
        headers=_headers(),
        timeout=30,
    )
    if resp.ok:
        reason_label = f"LeakLabs {plan_name.title()}"
        for plan in resp.json().get("results", []):
            if plan.get("reason") == reason_label:
                _plan_id_cache[plan_name] = plan["id"]
                log.info("Found existing MP plan %s for %s", plan["id"], plan_name)
                return plan["id"]

    # Criar novo plano
    amount = PLAN_AMOUNTS[plan_name]
    resp = _req.post(
        f"{MP_BASE}/preapproval_plan",
        json={
            "reason":   f"LeakLabs {plan_name.title()}",
            "back_url": MP_BACK_URL,
            "auto_recurring": {
                "frequency":                1,
                "frequency_type":           "months",
                "transaction_amount":       amount,
                "currency_id":              "BRL",
                "billing_day":              10,
                "billing_day_proportional": True,
            },
        },
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    plan_id = resp.json()["id"]
    _plan_id_cache[plan_name] = plan_id
    log.info("Created MP preapproval_plan %s for plan=%s", plan_id, plan_name)
    return plan_id


def create_subscription(
    plan_name: str,
    payer_email: str,
    card_token: str,
    user_id: int,
) -> dict:
    """Cria assinatura recorrente MP. Retorna dict com id e status."""
    plan_id = get_or_create_plan(plan_name)
    resp = _req.post(
        f"{MP_BASE}/preapproval",
        json={
            "preapproval_plan_id": plan_id,
            "reason":              f"LeakLabs {plan_name.title()} — usuário {user_id}",
            "external_reference":  f"user_{user_id}_{plan_name}",
            "payer_email":         payer_email,
            "card_token_id":       card_token,
            "status":              "authorized",
        },
        headers=_headers(),
        timeout=30,
    )
    if not resp.ok:
        log.error("MP create_subscription error %s: %s", resp.status_code, resp.text[:300])
    resp.raise_for_status()
    return resp.json()


def cancel_subscription(sub_id: str) -> bool:
    """Pausa/cancela uma assinatura MP."""
    resp = _req.put(
        f"{MP_BASE}/preapproval/{sub_id}",
        json={"status": "cancelled"},
        headers=_headers(),
        timeout=30,
    )
    if not resp.ok:
        log.error("MP cancel error %s: %s", resp.status_code, resp.text[:200])
    return resp.ok


def get_subscription(sub_id: str) -> dict | None:
    """Busca dados de uma assinatura MP."""
    try:
        resp = _req.get(f"{MP_BASE}/preapproval/{sub_id}", headers=_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error("Failed to fetch MP subscription %s: %s", sub_id, e)
        return None


def get_payment(payment_id: str) -> dict | None:
    """Busca dados de um pagamento MP."""
    try:
        resp = _req.get(f"{MP_BASE}/v1/payments/{payment_id}", headers=_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error("Failed to fetch MP payment %s: %s", payment_id, e)
        return None


def validate_webhook_signature(body: bytes, x_signature: str, data_id: str) -> bool:
    """
    Valida assinatura HMAC-SHA256 do webhook MP.
    x-signature: ts=<timestamp>,v1=<hash>
    Mensagem assinada: id:<data_id>;request-date:<ts>;
    """
    if not MP_WEBHOOK_SECRET:
        # Em dev/test sem secret configurado, apenas loga e permite
        log.warning("MP_WEBHOOK_SECRET não configurado — validação de webhook desativada")
        return True
    try:
        parts = dict(p.split("=", 1) for p in x_signature.split(","))
        ts    = parts.get("ts", "")
        v1    = parts.get("v1", "")
        template = f"id:{data_id};request-date:{ts};"
        expected = hmac.new(
            MP_WEBHOOK_SECRET.encode(), template.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, v1)
    except Exception as e:
        log.error("Webhook signature validation error: %s", e)
        return False
