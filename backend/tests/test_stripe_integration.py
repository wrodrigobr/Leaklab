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
    """Verifica que o Price ID do Pro está configurado."""
    pro = os.environ.get("STRIPE_PRICE_PRO", "")
    assert pro.startswith("price_"), f"STRIPE_PRICE_PRO inválido: {pro}"
    print(f"OK  test_stripe_prices_configured | pro={pro}")

# ── O contrato ATUAL: assinatura recorrente, nao PaymentIntent avulso ────────
#
# 05/09: seis destes testes estavam vermelhos, e NENHUM era bug. Todos afirmavam
# `pi_...` (PaymentIntent unico por ciclo) e o codigo cria `sub_...` desde a PAY-04,
# quando o modelo virou Subscription recorrente. Testes congelados na era anterior.
#
# Como o arquivo estava FORA da suite (achado no mesmo dia: 30 de 269 arquivos de
# teste nao rodavam em lugar nenhum), ninguem viu por meses.

def _pi_do_client_secret(client_secret: str) -> str:
    """`pi_xxx_secret_yyy` -> `pi_xxx`. Deriva o PaymentIntent da 1a fatura sem depender da
    versao da API: o campo mudou de `latest_invoice.payment_intent` para
    `latest_invoice.confirmation_secret`, mas o FORMATO do secret nao mudou."""
    return client_secret.split("_secret_")[0]


def test_gateway_cria_ASSINATURA_recorrente():
    """PAY-04: `create_subscription` cria Subscription real, nao PaymentIntent avulso."""
    from leaklab.stripe_gateway import create_subscription
    r = create_subscription(plan_name="pro", payer_email="test@integration.test", user_id=99998)
    assert r["subscription_id"].startswith("sub_"), (
        "esperava assinatura recorrente (sub_), veio: %s" % r["subscription_id"])
    assert r.get("recurring") is True, "assinatura deveria vir marcada como recorrente"
    assert "_secret_" in (r.get("client_secret") or ""), "client_secret da 1a fatura ausente"
    print("OK  test_gateway_cria_ASSINATURA_recorrente | sub=%s" % r["subscription_id"])


def test_gateway_get_subscription_devolve_dict():
    """`get_subscription` devolve dict (nao StripeObject) com o status."""
    from leaklab.stripe_gateway import create_subscription, get_subscription
    sid = create_subscription("pro", "test@integration.test", 99997)["subscription_id"]
    sub = get_subscription(sid)
    assert isinstance(sub, dict), "esperava dict, veio %s" % type(sub)
    assert sub.get("status") == "incomplete", (
        "assinatura nova nasce incomplete, veio %s" % sub.get("status"))
    print("OK  test_gateway_get_subscription_devolve_dict | status=%s" % sub["status"])


def test_confirmar_a_1a_fatura_ATIVA_a_assinatura():
    """O fluxo real do frontend: confirma o PI da 1a fatura e a assinatura vira `active`."""
    from leaklab.stripe_gateway import create_subscription, get_subscription
    r = create_subscription("pro", "test@integration.test", 99996)
    sid = r["subscription_id"]
    _stripe.PaymentIntent.confirm(_pi_do_client_secret(r["client_secret"]),
                                  payment_method="pm_card_visa",
                                  return_url="http://localhost:8080/dashboard")
    sub = get_subscription(sid)
    assert sub["status"] == "active", "esperava active apos pagar, veio %s" % sub["status"]
    print("OK  test_confirmar_a_1a_fatura_ATIVA_a_assinatura | status=%s" % sub["status"])


# ── Endpoint /subscription/checkout ─────────────────────────────────────────

def test_endpoint_checkout_devolve_ASSINATURA():
    c = _make_client()
    token, _ = _register_and_login(c, "1")
    r = c.post("/subscription/checkout", json={"plan": "pro"}, headers=_auth(token))
    assert r.status_code == 200, (
        "esperava 200, veio %s: %s" % (r.status_code, r.get_data(as_text=True)))
    d = r.get_json()
    assert d.get("subscription_id", "").startswith("sub_"), (
        "esperava sub_, veio: %s" % d.get("subscription_id"))
    assert "_secret_" in (d.get("client_secret") or ""), "client_secret ausente"
    print("OK  test_endpoint_checkout_devolve_ASSINATURA | sub=%s" % d["subscription_id"])
    return d


def test_endpoint_checkout_rejects_invalid_plan():
    """POST /subscription/checkout com plan=free ou plan=starter retorna 400."""
    c = _make_client()
    token, _ = _register_and_login(c, "4")
    for bad_plan in ("free", "starter", "random"):
        r = c.post("/subscription/checkout", json={"plan": bad_plan}, headers=_auth(token))
        assert r.status_code == 400, "Esperado 400 para plan=%s, got %s" % (bad_plan, r.status_code)
    print("OK  test_endpoint_checkout_rejects_invalid_plan")


# ── Endpoint /subscription/activate ─────────────────────────────────────────

def test_activate_com_assinatura_PAGA_concede_pro():
    """Fluxo completo: checkout -> confirma a 1a fatura -> activate -> Pro no banco."""
    c = _make_client()
    token, _ = _register_and_login(c, "2")
    d = c.post("/subscription/checkout", json={"plan": "pro"}, headers=_auth(token)).get_json()
    sid = d["subscription_id"]
    _stripe.PaymentIntent.confirm(_pi_do_client_secret(d["client_secret"]),
                                  payment_method="pm_card_visa",
                                  return_url="http://localhost:8080/dashboard")
    r = c.post("/subscription/activate",
               json={"plan": "pro", "payment_intent_id": sid, "subscription_id": sid},
               headers=_auth(token))
    assert r.status_code == 200, "activate falhou: %s" % r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("plan") == "pro", body
    me = c.get("/auth/me", headers=_auth(token)).get_json()
    assert me.get("plan") == "pro", "plano nao atualizou no banco: %s" % me.get("plan")
    print("OK  test_activate_com_assinatura_PAGA_concede_pro | sub=%s" % sid)


def test_activate_com_assinatura_INCOMPLETE_nao_concede_pro():
    """**O guarda que vale dinheiro.** Assinatura criada e NAO paga nao pode virar Pro.

    O teste antigo exigia HTTP 400 e por isso ficou vermelho: sob assinaturas, "ainda nao
    pagou" e PENDENCIA, nao erro — o frontend precisa distinguir as duas para nao mostrar
    falha num fluxo que esta correto, e o webhook `invoice.paid` confirma depois.

    O que importa nao e o codigo HTTP, e o EFEITO. Conferido em 05/09 rodando o caso: plano
    intacto e ZERO pagamentos gravados. Ancorar no status HTTP era ancorar no efeito colateral
    em vez da condicao, e foi assim que este arquivo passou meses vermelho por nada.
    """
    c = _make_client()
    token, email = _register_and_login(c, "3")
    d = c.post("/subscription/checkout", json={"plan": "pro"}, headers=_auth(token)).get_json()
    sid = d["subscription_id"]

    r = c.post("/subscription/activate",                       # SEM confirmar a fatura
               json={"plan": "pro", "payment_intent_id": sid, "subscription_id": sid},
               headers=_auth(token))
    body = r.get_json() or {}
    assert body.get("pending") is True, "deveria declarar pendencia: %s" % body
    assert body.get("plan") != "pro", "concedeu Pro sem pagamento: %s" % body

    me = c.get("/auth/me", headers=_auth(token)).get_json()
    assert me.get("plan") == "free", (
        "plano virou %s sem pagamento confirmado" % me.get("plan"))

    # Pelo e-mail: `/auth/me` nao devolve `id`, e inventar a chave seria testar o payload
    # em vez do efeito.
    conn = schema.get_conn()
    n = dict(conn.execute(repositories._adapt(
        "SELECT COUNT(*) AS n FROM payments p JOIN users u ON u.id = p.user_id "
        "WHERE u.email = ?"), (email,)).fetchone())["n"]
    conn.close()
    assert n == 0, "gravou %s pagamento(s) sem cobranca confirmada" % n
    print("OK  test_activate_com_assinatura_INCOMPLETE_nao_concede_pro | plano intacto, 0 pagamentos")


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
    raise SystemExit(1 if failed else 0)
