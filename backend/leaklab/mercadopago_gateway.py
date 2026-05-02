"""
mercadopago_gateway.py — Wrapper para Mercado Pago Payments API (Checkout Transparente).
Usa requests diretamente, sem SDK oficial.
Cobrança via /v1/payments (one-time); renovação mensal é responsabilidade do backend.
"""
from __future__ import annotations
import os
import hmac
import hashlib
import logging
import uuid
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

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type":  "application/json",
    }



def create_subscription(
    plan_name: str,
    payer_email: str,
    card_token: str,
    user_id: int,
    payment_method_id: str | None = None,
    issuer_id: str | None = None,
    identification_type: str | None = None,
    identification_number: str | None = None,
) -> dict:
    """
    Cobra o cartão via /v1/payments (Checkout Transparente).
    Retorna dict com id e status do pagamento.
    """
    amount = PLAN_AMOUNTS[plan_name]
    payer: dict = {"email": payer_email}
    if identification_type and identification_number:
        payer["identification"] = {
            "type":   identification_type,
            "number": identification_number,
        }
    body: dict = {
        "transaction_amount": amount,
        "token":              card_token,
        "description":        f"LeakLabs {plan_name.title()} — 30 dias",
        "installments":       1,
        "payer":              payer,
        "external_reference":   f"user_{user_id}_{plan_name}",
        "statement_descriptor": "LEAKLABS",
        "metadata": {
            "user_id":   user_id,
            "plan_name": plan_name,
        },
    }
    if payment_method_id:
        body["payment_method_id"] = payment_method_id
    if issuer_id:
        body["issuer_id"] = int(issuer_id) if str(issuer_id).isdigit() else issuer_id

    log.info("MP /v1/payments payload: amount=%s method=%s email=%s id_type=%s",
             amount, payment_method_id, payer_email, identification_type)
    resp = _req.post(
        f"{MP_BASE}/v1/payments",
        json=body,
        headers={**_headers(), "X-Idempotency-Key": str(uuid.uuid4())},
        timeout=30,
    )
    if not resp.ok:
        log.error("MP create_subscription error %s: %s", resp.status_code, resp.text)
        # Propaga a mensagem MP para que o handler do app.py possa exibi-la em debug
        try:
            mp_msg = resp.json().get("message") or resp.text[:300]
        except Exception:
            mp_msg = resp.text[:300]
        raise Exception(f"MP {resp.status_code}: {mp_msg}")
    data = resp.json()
    # Normaliza para o formato esperado pelo app.py (id + status)
    return {
        "id":     str(data.get("id", "")),
        "status": data.get("status", "pending"),
        "raw":    data,
    }


def cancel_subscription(sub_id: str) -> bool:
    """
    Para pagamentos avulsos não existe cancelamento na API MP.
    Aqui apenas marcamos como cancelado no nosso banco (retorna True).
    """
    log.info("MP cancel_subscription: pagamento %s marcado como cancelado localmente", sub_id)
    return True


def get_subscription(sub_id: str) -> dict | None:
    """Busca dados de um pagamento MP (usado no contexto de subscription)."""
    return get_payment(sub_id)


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
