"""
test_stripe_integration.py — Testes de integração reais com Stripe API (test mode).

Requer variáveis de ambiente configuradas em backend/.env:
  STRIPE_SECRET_KEY, STRIPE_PRICE_STARTER, STRIPE_PRICE_PRO

Usa pm_card_visa (payment method de teste do Stripe) para confirmar pagamentos
sem necessidade de formulário no frontend.

Uso:
    python tests/test_stripe_integration.py
"""

import sys, os, traceback, sqlite3, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

import stripe as _stripe
_stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

try:
    import flask_cors
except ImportError:
    import unittest.mock as _mock
    sys.modules['flask_cors'] = _mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from database import schema, repositories

_TEST_DB = None

def _setup_db():
    global _TEST_DB
    _TEST_DB = tempfile.mktemp(suffix='_stripe_int.db')
    def gc():
        conn = sqlite3.connect(_TEST_DB)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    schema.get_conn       = gc
    repositories.get_conn = gc
    import database.schema as sch
    sch.get_conn = gc
    schema.init_db()

def _teardown_db():
    if _TEST_DB and os.path.exists(_TEST_DB):
        try: os.unlink(_TEST_DB)
        except: pass

def _make_client():
    _setup_db()
    from api.app import app
    app.config['TESTING'] = True
    return app.test_client()

def _register_and_login(client, suffix=''):
    email = f'stripe{suffix}@integration.test'
    r = client.post('/auth/register',
                    json={'username': f'stripeuser{suffix}', 'email': email, 'password': 'pass1234'},
                    content_type='application/json')
    if r.status_code == 409:
        r = client.post('/auth/login',
                        json={'email': email, 'password': 'pass1234'},
                        content_type='application/json')
    return r.get_json().get('token', ''), email

def _auth(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# ── Pré-requisito ────────────────────────────────────────────────────────────

def test_stripe_key_configured():
    """Verifica que STRIPE_SECRET_KEY está configurada e é test mode."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    assert key, "STRIPE_SECRET_KEY não configurada"
    assert key.startswith("sk_test_"), f"Chave não é de test mode: {key[:12]}..."
    print(f"OK  test_stripe_key_configured | key={key[:20]}...")

def test_stripe_prices_configured():
    """Verifica que os Price IDs estão configurados."""
    starter = os.environ.get("STRIPE_PRICE_STARTER", "")
    pro     = os.environ.get("STRIPE_PRICE_PRO", "")
    assert starter.startswith("price_"), f"STRIPE_PRICE_STARTER inválido: {starter}"
    assert pro.startswith("price_"),     f"STRIPE_PRICE_PRO inválido: {pro}"
    print(f"OK  test_stripe_prices_configured | starter={starter} pro={pro}")

# ── Gateway direto ───────────────────────────────────────────────────────────

def test_gateway_create_payment_intent_starter():
    """create_subscription cria PaymentIntent real no Stripe e retorna client_secret."""
    from leaklab.stripe_gateway import create_subscription
    result = create_subscription(
        plan_name="starter",
        payer_email="test@integration.test",
        user_id=99999,
    )
    assert result["subscription_id"].startswith("pi_"), \
        f"subscription_id deveria ser pi_xxx, got: {result['subscription_id']}"
    assert result["client_secret"], "client_secret vazio"
    assert "_secret_" in result["client_secret"], \
        f"client_secret inválido: {result['client_secret'][:30]}"
    print(f"OK  test_gateway_create_payment_intent_starter | pi={result['subscription_id']}")
    return result["subscription_id"]

def test_gateway_create_payment_intent_pro():
    """create_subscription funciona para plano pro."""
    from leaklab.stripe_gateway import create_subscription
    result = create_subscription(
        plan_name="pro",
        payer_email="test@integration.test",
        user_id=99998,
    )
    assert result["subscription_id"].startswith("pi_")
    assert "_secret_" in result["client_secret"]
    print(f"OK  test_gateway_create_payment_intent_pro | pi={result['subscription_id']}")

def test_gateway_get_payment_returns_dict():
    """get_payment retorna dict (não StripeObject) com campo status."""
    from leaklab.stripe_gateway import create_subscription, get_payment
    pi_id = create_subscription("starter", "test@integration.test", 99997)["subscription_id"]
    pi = get_payment(pi_id)
    assert isinstance(pi, dict), f"get_payment deveria retornar dict, got {type(pi)}"
    assert "status" in pi, f"campo status ausente: {list(pi.keys())[:10]}"
    assert "client_secret" in pi, "campo client_secret ausente"
    print(f"OK  test_gateway_get_payment_returns_dict | status={pi['status']}")

def test_gateway_confirm_and_get_succeeded():
    """Confirma PaymentIntent com pm_card_visa e verifica status=succeeded."""
    from leaklab.stripe_gateway import create_subscription, get_payment
    pi_id = create_subscription("starter", "test@integration.test", 99996)["subscription_id"]

    # Confirma com cartão de teste do Stripe (sempre aprova)
    _stripe.PaymentIntent.confirm(
        pi_id,
        payment_method="pm_card_visa",
        return_url="http://localhost:8080/dashboard",
    )

    pi = get_payment(pi_id)
    assert pi["status"] == "succeeded", f"Esperado succeeded, got: {pi['status']}"
    print(f"OK  test_gateway_confirm_and_get_succeeded | status={pi['status']}")
    return pi_id

# ── Endpoint /subscription/checkout ─────────────────────────────────────────

def test_endpoint_checkout_returns_client_secret():
    """POST /subscription/checkout retorna client_secret e subscription_id reais."""
    c = _make_client()
    token, _ = _register_and_login(c, '1')
    r = c.post('/subscription/checkout', json={'plan': 'starter'}, headers=_auth(token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.get_data(as_text=True)}"
    data = r.get_json()
    assert data.get('client_secret'), "client_secret ausente"
    assert data.get('subscription_id', '').startswith('pi_'), \
        f"subscription_id inválido: {data.get('subscription_id')}"
    print(f"OK  test_endpoint_checkout_returns_client_secret | pi={data['subscription_id']}")
    return data

# ── Endpoint /subscription/activate ─────────────────────────────────────────

def test_endpoint_activate_with_real_pi():
    """Fluxo completo: checkout → confirma PI via Stripe API → activate → plano atualizado."""
    c = _make_client()
    token, _ = _register_and_login(c, '2')

    # 1. Cria intent
    r = c.post('/subscription/checkout', json={'plan': 'pro'}, headers=_auth(token))
    assert r.status_code == 200, f"checkout falhou: {r.get_data(as_text=True)}"
    checkout_data = r.get_json()
    pi_id  = checkout_data['subscription_id']
    sub_id = pi_id

    # 2. Confirma PI direto via Stripe (simula o frontend)
    _stripe.PaymentIntent.confirm(
        pi_id,
        payment_method="pm_card_visa",
        return_url="http://localhost:8080/dashboard",
    )

    # 3. Ativa o plano
    r = c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': pi_id, 'subscription_id': sub_id},
               headers=_auth(token))
    assert r.status_code == 200, f"activate falhou: {r.get_data(as_text=True)}"
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('plan') == 'pro'

    # 4. Verifica que plano foi atualizado no banco
    me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.get_json().get('plan') == 'pro', \
        f"Plano não atualizado: {me.get_json().get('plan')}"

    print(f"OK  test_endpoint_activate_with_real_pi | pi={pi_id} plan=pro")

def test_endpoint_activate_rejects_unconfirmed_pi():
    """activate rejeita PaymentIntent não confirmado (status != succeeded)."""
    c = _make_client()
    token, _ = _register_and_login(c, '3')

    r = c.post('/subscription/checkout', json={'plan': 'starter'}, headers=_auth(token))
    pi_id = r.get_json()['subscription_id']

    # Tenta ativar SEM confirmar o PI
    r = c.post('/subscription/activate',
               json={'plan': 'starter', 'payment_intent_id': pi_id, 'subscription_id': pi_id},
               headers=_auth(token))
    assert r.status_code == 400, f"Deveria rejeitar PI não confirmado, got {r.status_code}"
    print(f"OK  test_endpoint_activate_rejects_unconfirmed_pi | status={r.status_code}")

# ── runner ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    _teardown_db()
    print(f"\n{'='*60}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
