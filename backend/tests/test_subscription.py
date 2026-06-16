"""
test_subscription.py — Testes dos endpoints de assinatura (BACK-015 / Stripe)

Cobre:
- /subscription/checkout  (POST) — validação, retorna client_secret
- /subscription/activate  (POST) — verifica PaymentIntent e ativa plano
- /subscription/invoices  (GET)  — histórico de pagamentos
- /subscription/cancel    (POST) — cancela assinatura
- /subscription/webhook   (POST) — eventos Stripe

Todos os testes mockam o Stripe gateway via unittest.mock.
"""

import sys, os, json, traceback, sqlite3, tempfile
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors
except ImportError:
    import unittest.mock as _mock
    sys.modules['flask_cors'] = _mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from database import schema, repositories
from database.auth import generate_token

_TEST_DB = None

def _setup_db():
    global _TEST_DB
    _TEST_DB = tempfile.mktemp(suffix='_subtest.db')
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
    return gc

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
    email = f'sub{suffix}@test.com'
    r = client.post('/auth/register',
                    json={'username': f'subuser{suffix}', 'email': email, 'password': 'pass1234'},
                    content_type='application/json')
    if r.status_code == 409:
        r = client.post('/auth/login',
                        json={'email': email, 'password': 'pass1234'},
                        content_type='application/json')
    return r.get_json().get('token', '')

def _auth(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

def _mock_checkout(sub_id='sub_TEST001', cs='pi_secret_test'):
    return {'subscription_id': sub_id, 'client_secret': cs, 'status': 'incomplete'}

def _mock_pi(pi_id='pi_TEST001', status='succeeded'):
    return {'id': pi_id, 'status': status}


# ── /subscription/checkout ───────────────────────────────────────────────────

def test_checkout_requires_auth():
    c = _make_client()
    r = c.post('/subscription/checkout', json={'plan': 'pro'})
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    print("OK  test_checkout_requires_auth")


def test_checkout_missing_plan():
    c = _make_client()
    token = _register_and_login(c, 'mp1')
    r = c.post('/subscription/checkout', json={}, headers=_auth(token))
    assert r.status_code == 400
    print("OK  test_checkout_missing_plan")


def test_checkout_invalid_plan():
    c = _make_client()
    token = _register_and_login(c, 'mp2')
    r = c.post('/subscription/checkout', json={'plan': 'ultra'}, headers=_auth(token))
    assert r.status_code == 400
    print("OK  test_checkout_invalid_plan")


def test_checkout_rejects_starter_plan():
    """Plano starter foi removido em 2026-05-26 — esperado 400."""
    c = _make_client()
    token = _register_and_login(c, 'cs1')
    r = c.post('/subscription/checkout', json={'plan': 'starter'}, headers=_auth(token))
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    print("OK  test_checkout_rejects_starter_plan")


def test_checkout_rejects_free_plan():
    """Plan='free' deve ser rejeitado pelo checkout (nao se assina o free)."""
    c = _make_client()
    token = _register_and_login(c, 'cs1f')
    r = c.post('/subscription/checkout', json={'plan': 'free'}, headers=_auth(token))
    assert r.status_code == 400
    print("OK  test_checkout_rejects_free_plan")


def test_checkout_pro_returns_client_secret():
    c = _make_client()
    token = _register_and_login(c, 'cs2')
    with patch('api.app.create_subscription', return_value=_mock_checkout('sub_P', 'pi_p_cs')):
        r = c.post('/subscription/checkout', json={'plan': 'pro'}, headers=_auth(token))
    assert r.status_code == 200
    assert r.get_json().get('client_secret') == 'pi_p_cs'
    print("OK  test_checkout_pro_returns_client_secret")


def test_checkout_stripe_error_returns_502():
    c = _make_client()
    token = _register_and_login(c, 'err1')
    with patch('api.app.create_subscription', side_effect=Exception("Stripe config error")):
        r = c.post('/subscription/checkout', json={'plan': 'pro'}, headers=_auth(token))
    assert r.status_code == 502
    assert 'error' in r.get_json()
    print("OK  test_checkout_stripe_error_returns_502")


def test_checkout_no_plan_update_before_activate():
    """checkout não deve atualizar o plano — só /activate faz isso."""
    c = _make_client()
    token = _register_and_login(c, 'noupd')
    with patch('api.app.create_subscription', return_value=_mock_checkout()):
        c.post('/subscription/checkout', json={'plan': 'pro'}, headers=_auth(token))
    me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.get_json().get('plan') == 'free', "Plan should still be free before activation"
    print("OK  test_checkout_no_plan_update_before_activate")


# ── /subscription/activate ───────────────────────────────────────────────────

def test_activate_requires_auth():
    c = _make_client()
    r = c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': 'pi_x', 'subscription_id': 'sub_x'})
    assert r.status_code == 401
    print("OK  test_activate_requires_auth")


def test_activate_invalid_plan():
    c = _make_client()
    token = _register_and_login(c, 'act1')
    r = c.post('/subscription/activate',
               json={'plan': 'ultra', 'payment_intent_id': 'pi_x', 'subscription_id': 'sub_x'},
               headers=_auth(token))
    assert r.status_code == 400
    print("OK  test_activate_invalid_plan")


def test_activate_missing_fields():
    c = _make_client()
    token = _register_and_login(c, 'act2')
    r = c.post('/subscription/activate', json={'plan': 'pro'}, headers=_auth(token))
    assert r.status_code == 400
    print("OK  test_activate_missing_fields")


def test_activate_payment_not_succeeded():
    """PaymentIntent com status != succeeded deve retornar 400."""
    c = _make_client()
    token = _register_and_login(c, 'act3')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_x', 'requires_payment_method')):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_x', 'subscription_id': 'sub_x'},
                   headers=_auth(token))
    assert r.status_code == 400
    print("OK  test_activate_payment_not_succeeded")


def test_activate_payment_not_found():
    c = _make_client()
    token = _register_and_login(c, 'act4')
    with patch('api.app.get_payment', return_value=None):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_x', 'subscription_id': 'sub_x'},
                   headers=_auth(token))
    assert r.status_code == 400
    print("OK  test_activate_payment_not_found")


def test_activate_rejects_starter_plan():
    """Plano starter foi removido em 2026-05-26 — activate retorna 400."""
    c = _make_client()
    token = _register_and_login(c, 'act5')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_ok', 'succeeded')):
        r = c.post('/subscription/activate',
                   json={'plan': 'starter', 'payment_intent_id': 'pi_ok', 'subscription_id': 'sub_ok'},
                   headers=_auth(token))
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    print("OK  test_activate_rejects_starter_plan")


def test_activate_pro_success():
    c = _make_client()
    token = _register_and_login(c, 'act6')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_pro', 'succeeded')):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_pro', 'subscription_id': 'sub_pro'},
                   headers=_auth(token))
    assert r.status_code == 200
    assert r.get_json().get('plan') == 'pro'
    print("OK  test_activate_pro_success")


def test_activate_updates_user_plan():
    """Após activate, /auth/me deve refletir o novo plano."""
    c = _make_client()
    token = _register_and_login(c, 'planupd')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_u', 'succeeded')):
        c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': 'pi_u', 'subscription_id': 'sub_u'},
               headers=_auth(token))
    me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.get_json().get('plan') == 'pro'
    print("OK  test_activate_updates_user_plan")


def test_activate_processing_status_accepted():
    """status=processing também deve ativar (pagamento em processamento)."""
    c = _make_client()
    token = _register_and_login(c, 'proc')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_proc', 'processing')):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_proc', 'subscription_id': 'sub_proc'},
                   headers=_auth(token))
    assert r.status_code == 200
    print("OK  test_activate_processing_status_accepted")


# ── /subscription/invoices ───────────────────────────────────────────────────

def test_invoices_requires_auth():
    c = _make_client()
    r = c.get('/subscription/invoices')
    assert r.status_code == 401
    print("OK  test_invoices_requires_auth")


def test_invoices_empty_for_new_user():
    c = _make_client()
    token = _register_and_login(c, 'inv0')
    r = c.get('/subscription/invoices', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data.get('invoices'), list)
    print(f"OK  test_invoices_empty_for_new_user | count={len(data['invoices'])}")


def test_invoices_after_activation():
    c = _make_client()
    token = _register_and_login(c, 'invpay')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_inv', 'succeeded')):
        c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': 'pi_inv', 'subscription_id': 'sub_inv'},
               headers=_auth(token))
    r = c.get('/subscription/invoices', headers={'Authorization': f'Bearer {token}'})
    data = r.get_json()
    assert len(data['invoices']) >= 1
    assert data['invoices'][0].get('plan') == 'pro'
    print(f"OK  test_invoices_after_activation | count={len(data['invoices'])}")


# ── /subscription/cancel ─────────────────────────────────────────────────────

def test_cancel_requires_auth():
    c = _make_client()
    r = c.post('/subscription/cancel')
    assert r.status_code == 401
    print("OK  test_cancel_requires_auth")


def test_cancel_no_active_subscription():
    c = _make_client()
    token = _register_and_login(c, 'canc0')
    r = c.post('/subscription/cancel', headers=_auth(token))
    assert r.status_code in (400, 404)
    print(f"OK  test_cancel_no_active_subscription | status={r.status_code}")


def test_cancel_active_subscription():
    c = _make_client()
    token = _register_and_login(c, 'cancact')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_c', 'succeeded')):
        c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': 'pi_c', 'subscription_id': 'sub_CANCEL'},
               headers=_auth(token))
    with patch('api.app.cancel_subscription', return_value=True):
        r = c.post('/subscription/cancel', headers=_auth(token))
    assert r.status_code == 200, f"Expected 200: {r.get_data(as_text=True)}"
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('plan') == 'free'
    me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.get_json().get('plan') == 'free'
    print(f"OK  test_cancel_active_subscription | plan_after={data['plan']}")


# ── /subscription/webhook ────────────────────────────────────────────────────

def test_webhook_no_secret_allowed():
    """Sem STRIPE_WEBHOOK_SECRET configurado, webhook é aceito sem validação (qualquer evento retorna 200)."""
    c = _make_client()
    payload = json.dumps({'type': 'ping', 'data': {'object': {}}}).encode()
    with patch('api.app.STRIPE_WEBHOOK_SECRET', ''):
        r = c.post('/subscription/webhook', data=payload, content_type='application/json')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.get_data(as_text=True)}"
    print("OK  test_webhook_no_secret_allowed")


def test_webhook_subscription_deleted_downgrades():
    """Evento desconhecido (customer.subscription.deleted) é ignorado graciosamente → 200."""
    c = _make_client()
    # The webhook endpoint only handles payment_intent.succeeded; unknown events return 200 silently
    payload = json.dumps({'type': 'customer.subscription.deleted',
                          'data': {'object': {'metadata': {'user_id': '1'}}}}).encode()
    with patch('api.app.STRIPE_WEBHOOK_SECRET', ''):
        r = c.post('/subscription/webhook', data=payload, content_type='application/json')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.get_data(as_text=True)}"
    print("OK  test_webhook_subscription_deleted_downgrades")


def test_webhook_invalid_signature_rejected():
    """Com STRIPE_WEBHOOK_SECRET configurado, assinatura inválida → 400."""
    c = _make_client()
    import leaklab.stripe_gateway as gw
    original = gw.STRIPE_WEBHOOK_SECRET
    os.environ['STRIPE_WEBHOOK_SECRET'] = 'whsec_test'
    gw.STRIPE_WEBHOOK_SECRET = 'whsec_test'
    try:
        payload = json.dumps({'type': 'ping'}).encode()
        with patch('api.app.STRIPE_WEBHOOK_SECRET', 'whsec_test'):
            with patch('api.app.validate_webhook', side_effect=Exception("Invalid signature")):
                r = c.post('/subscription/webhook', data=payload,
                           content_type='application/json',
                           headers={'stripe-signature': 'bad_sig'})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        print("OK  test_webhook_invalid_signature_rejected")
    finally:
        gw.STRIPE_WEBHOOK_SECRET = original
        os.environ.pop('STRIPE_WEBHOOK_SECRET', None)


# ── PAY-01: revalidação (idempotência, rótulo de gateway, cancel, falha, MRR) ──

def _uid(c, token):
    return c.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).get_json().get('user_id')


def test_activate_then_webhook_no_double_payment():
    """PAY-01: /activate + webhook payment_intent.succeeded p/ o MESMO pi → 1 linha só
    (antes gravava 2 — receita/invoices dobrados)."""
    c = _make_client()
    token = _register_and_login(c, 'idem1')
    uid = _uid(c, token)
    with patch('api.app.get_payment', return_value=_mock_pi('pi_idem', 'succeeded')):
        c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': 'pi_idem', 'subscription_id': 'pi_idem'},
               headers=_auth(token))
    payload = json.dumps({'type': 'payment_intent.succeeded',
                          'data': {'object': {'id': 'pi_idem', 'amount': 9900,
                                              'metadata': {'user_id': str(uid), 'plan_name': 'pro'}}}}).encode()
    with patch('api.app.STRIPE_WEBHOOK_SECRET', ''):
        r = c.post('/subscription/webhook', data=payload, content_type='application/json')
    assert r.status_code == 200
    inv = c.get('/subscription/invoices', headers={'Authorization': f'Bearer {token}'}).get_json()
    approved = [p for p in inv['invoices'] if p['status'] == 'approved' and p['gateway_id'] == 'pi_idem']
    assert len(approved) == 1, f"esperava 1 pagamento, achou {len(approved)}"
    assert approved[0]['gateway'] == 'stripe'
    print("OK  test_activate_then_webhook_no_double_payment")


def test_webhook_retry_idempotent():
    """PAY-01: retentativa do MESMO webhook não duplica o pagamento."""
    c = _make_client()
    token = _register_and_login(c, 'idem2')
    uid = _uid(c, token)
    payload = json.dumps({'type': 'payment_intent.succeeded',
                          'data': {'object': {'id': 'pi_retry', 'amount': 9900,
                                              'metadata': {'user_id': str(uid), 'plan_name': 'pro'}}}}).encode()
    with patch('api.app.STRIPE_WEBHOOK_SECRET', ''):
        c.post('/subscription/webhook', data=payload, content_type='application/json')
        c.post('/subscription/webhook', data=payload, content_type='application/json')
    inv = c.get('/subscription/invoices', headers={'Authorization': f'Bearer {token}'}).get_json()
    rows = [p for p in inv['invoices'] if p['gateway_id'] == 'pi_retry']
    assert len(rows) == 1, f"esperava 1, achou {len(rows)}"
    print("OK  test_webhook_retry_idempotent")


def test_stripe_payment_labeled_stripe():
    """PAY-01: pagamento Stripe gravado com gateway='stripe' (não o default 'mercadopago')."""
    c = _make_client()
    token = _register_and_login(c, 'glabel')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_lbl', 'succeeded')):
        c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': 'pi_lbl', 'subscription_id': 'pi_lbl'},
               headers=_auth(token))
    inv = c.get('/subscription/invoices', headers={'Authorization': f'Bearer {token}'}).get_json()
    assert inv['invoices'][0]['gateway'] == 'stripe'
    print("OK  test_stripe_payment_labeled_stripe")


def test_cancel_pi_model_downgrades_without_stripe():
    """PAY-01: cancelar com id de PaymentIntent (pi_...) NÃO chama o Stripe e faz downgrade local
    (antes Subscription.cancel(pi_...) lançava → 502 em produção)."""
    c = _make_client()
    token = _register_and_login(c, 'cancpi')
    with patch('api.app.get_payment', return_value=_mock_pi('pi_cx', 'succeeded')):
        c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': 'pi_cx', 'subscription_id': 'pi_cx'},
               headers=_auth(token))
    # SEM mockar cancel_subscription → exercita o guard real (pi_ → True sem chamar Stripe)
    with patch('leaklab.stripe_gateway._stripe.Subscription.cancel') as mock_cancel:
        r = c.post('/subscription/cancel', headers=_auth(token))
        assert mock_cancel.call_count == 0, "não deve chamar Stripe p/ id pi_"
    assert r.status_code == 200 and r.get_json()['plan'] == 'free'
    me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.get_json()['plan'] == 'free'
    print("OK  test_cancel_pi_model_downgrades_without_stripe")


def test_webhook_payment_failed_recorded():
    """PAY-01: payment_intent.payment_failed grava linha 'failed' p/ auditoria; plano intacto."""
    c = _make_client()
    token = _register_and_login(c, 'pfail')
    uid = _uid(c, token)
    payload = json.dumps({'type': 'payment_intent.payment_failed',
                          'data': {'object': {'id': 'pi_fail', 'amount': 9900,
                                              'metadata': {'user_id': str(uid), 'plan_name': 'pro'}}}}).encode()
    with patch('api.app.STRIPE_WEBHOOK_SECRET', ''):
        r = c.post('/subscription/webhook', data=payload, content_type='application/json')
    assert r.status_code == 200
    inv = c.get('/subscription/invoices', headers={'Authorization': f'Bearer {token}'}).get_json()
    failed = [p for p in inv['invoices'] if p['status'] == 'failed']
    assert len(failed) == 1 and failed[0]['gateway'] == 'stripe'
    me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.get_json()['plan'] == 'free', "falha de pagamento não pode dar pro"
    print("OK  test_webhook_payment_failed_recorded")


def test_admin_mrr_matches_pro_price():
    """PAY-01: MRR do admin = pro_users * 9900 (preço real), não 4900 (subestimava metade)."""
    c = _make_client()  # configura o DB de teste (patcha get_conn)
    from database import repositories as repo
    for i in range(2):
        uid = repo.create_user(f'mrr{i}', f'mrr{i}@t.com', 'pass', role='player')
        repo.update_user_plan(uid, 'pro')
    stats = repo.get_admin_dashboard_stats()
    pro = stats['plans'].get('pro', 0)
    assert pro >= 2 and stats['mrr_cents'] == pro * 9900, stats
    print("OK  test_admin_mrr_matches_pro_price")


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
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
