"""
PAY-04 — Setup do Stripe Billing (idempotente).

Cria/reutiliza no Stripe tudo que a recorrência precisa e imprime os IDs prontos
para colar nas env vars:
  - Product "GrindLab Pro"
  - 2 Prices RECORRENTES: mensal (R$99/mês) e anual (R$990/ano)  [lookup_key: pro_monthly / pro_annual]
  - Webhook endpoint apontando para a sua API, com os eventos certos
  - Customer Billing Portal (configuração básica: trocar cartão / faturas / cancelar)

Os valores vêm da fonte única `leaklab.stripe_gateway` (PLAN_AMOUNTS / PLAN_AMOUNTS_ANNUAL),
então preço aqui = preço cobrado no app.

PRÉ-REQUISITO: `STRIPE_SECRET_KEY` no ambiente (sk_test_… para testar, sk_live_… para produção).

Uso:
    cd backend
    set STRIPE_SECRET_KEY=sk_test_xxx   # (Windows; export no Linux)
    python scripts/stripe_setup.py --webhook-url https://api.seudominio.com/subscription/webhook            # dry-run
    python scripts/stripe_setup.py --webhook-url https://api.seudominio.com/subscription/webhook --apply     # aplica

Idempotente: rodar de novo reutiliza o que já existe (não duplica).
"""
import os
import sys
import argparse

sys.path.insert(0, ".")

import stripe as _stripe
from leaklab.stripe_gateway import PLAN_AMOUNTS, PLAN_AMOUNTS_ANNUAL

WEBHOOK_EVENTS = [
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
]

# (lookup_key, label, unit_amount_cents, interval)
PRICES = [
    ("pro_monthly", "Pro Mensal", int(PLAN_AMOUNTS["pro"] * 100),        "month"),
    ("pro_annual",  "Pro Anual",  int(PLAN_AMOUNTS_ANNUAL["pro"] * 100), "year"),
]


def _find_product():
    try:
        res = _stripe.Product.search(query="metadata['app']:'grindlab' AND metadata['plan']:'pro'")
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return None


def ensure_product(apply: bool):
    existing = _find_product()
    if existing:
        print(f"  Product já existe: {existing.id} ({existing.name})")
        return existing.id
    if not apply:
        print("  [dry-run] criaria Product 'GrindLab Pro'")
        return "<prod_dryrun>"
    prod = _stripe.Product.create(
        name="GrindLab Pro",
        description="Assinatura Pro do GrindLab — análise ilimitada + AI Coach.",
        metadata={"app": "grindlab", "plan": "pro"},
    )
    print(f"  Product criado: {prod.id}")
    return prod.id


def ensure_price(product_id, lookup_key, label, amount, interval, apply: bool):
    found = _stripe.Price.list(lookup_keys=[lookup_key], limit=1)
    if found.data:
        p = found.data[0]
        print(f"  Price '{lookup_key}' já existe: {p.id} ({p.unit_amount} {p.currency}/{p.recurring['interval']})")
        return p.id
    if not apply:
        print(f"  [dry-run] criaria Price '{lookup_key}': {amount} brl/{interval}")
        return f"<price_{lookup_key}_dryrun>"
    p = _stripe.Price.create(
        product=product_id,
        unit_amount=amount,
        currency="brl",
        recurring={"interval": interval},
        lookup_key=lookup_key,
        nickname=label,
    )
    print(f"  Price criado '{lookup_key}': {p.id}")
    return p.id


def ensure_webhook(url, apply: bool):
    if not url:
        print("  (sem --webhook-url → pulando webhook)")
        return None, None
    for wh in _stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
        if wh.url == url:
            print(f"  Webhook já existe: {wh.id} (secret não é legível em endpoint existente)")
            if apply and set(WEBHOOK_EVENTS) - set(wh.enabled_events):
                _stripe.WebhookEndpoint.modify(wh.id, enabled_events=WEBHOOK_EVENTS)
                print("  Webhook atualizado com os eventos esperados.")
            return wh.id, None
    if not apply:
        print(f"  [dry-run] criaria Webhook → {url} com {len(WEBHOOK_EVENTS)} eventos")
        return "<wh_dryrun>", None
    wh = _stripe.WebhookEndpoint.create(url=url, enabled_events=WEBHOOK_EVENTS)
    print(f"  Webhook criado: {wh.id}")
    return wh.id, wh.get("secret")


def ensure_portal(apply: bool):
    try:
        cfgs = _stripe.billing_portal.Configuration.list(limit=1)
        if cfgs.data:
            print(f"  Billing Portal já configurado: {cfgs.data[0].id}")
            return cfgs.data[0].id
    except Exception as e:
        print(f"  (não consegui listar portal: {e})")
    if not apply:
        print("  [dry-run] criaria configuração do Billing Portal")
        return "<portal_dryrun>"
    cfg = _stripe.billing_portal.Configuration.create(
        business_profile={"headline": "GrindLab — gerencie sua assinatura"},
        features={
            "invoice_history":        {"enabled": True},
            "payment_method_update":  {"enabled": True},
            "subscription_cancel":    {"enabled": True, "mode": "at_period_end"},
        },
    )
    print(f"  Billing Portal configurado: {cfg.id}")
    return cfg.id


def main():
    ap = argparse.ArgumentParser(description="Setup do Stripe Billing (PAY-04).")
    ap.add_argument("--webhook-url", default="", help="URL pública do /subscription/webhook")
    ap.add_argument("--apply", action="store_true", help="aplica de verdade (sem isso = dry-run)")
    args = ap.parse_args()

    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        print("ERRO: defina STRIPE_SECRET_KEY no ambiente (sk_test_… ou sk_live_…).")
        sys.exit(1)
    _stripe.api_key = key
    mode = "LIVE" if key.startswith("sk_live") else "TEST"
    print(f"== Stripe setup ({mode}) {'— APLICANDO' if args.apply else '— DRY-RUN'} ==")
    if mode == "LIVE" and not args.apply:
        print("  (chave LIVE detectada; rode com --apply só quando tiver certeza)")

    prod_id = ensure_product(args.apply)
    price_ids = {}
    for lk, label, amount, interval in PRICES:
        price_ids[lk] = ensure_price(prod_id, lk, label, amount, interval, args.apply)
    wh_id, wh_secret = ensure_webhook(args.webhook_url, args.apply)
    ensure_portal(args.apply)

    print("\n── Cole nas env vars ────────────────────────────────────")
    print(f"STRIPE_PRICE_PRO_MONTHLY={price_ids.get('pro_monthly')}")
    print(f"STRIPE_PRICE_PRO_ANNUAL={price_ids.get('pro_annual')}")
    if wh_secret:
        print(f"STRIPE_WEBHOOK_SECRET={wh_secret}")
    elif wh_id:
        print("STRIPE_WEBHOOK_SECRET=<pegue no Dashboard → Developers → Webhooks → seu endpoint → Signing secret>")
    print("─────────────────────────────────────────────────────────")
    if not args.apply:
        print("\nDRY-RUN: nada foi criado. Rode com --apply para efetivar.")


if __name__ == "__main__":
    main()
