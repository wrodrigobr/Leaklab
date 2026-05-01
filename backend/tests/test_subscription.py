"""
test_subscription.py — Testes dos endpoints de assinatura (BACK-015)

Cobre:
- /subscription/checkout  (POST) — validação, auth, cenários MP
- /subscription/invoices  (GET)  — auth, resposta vazia
- /subscription/cancel    (POST) — auth, sem assinatura ativa, cancelamento
- /subscription/webhook   (POST) — assinatura e pagamento

Os testes mockam o gateway Mercado Pago via unittest.mock para não depender
de rede real. Os cenários refletem os cartões/titulares de teste do MP:
  APRO → authorized   FUND → cc_rejected_insufficient_amount
  SECU → cc_rejected_bad_filled_security_code  EXPI → cc_rejected_bad_filled_date
  OTHE → cc_rejected_other_reason  CALL → cc_rejected_call_for_authorize
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

# ── /subscription/checkout — validação ───────────────────────────────────────

def test_checkout_requires_auth():
    c = _make_client()
    r = c.post('/subscription/checkout', json={'plan': 'starter', 'card_token': 'tok'})
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    print("OK  test_checkout_requires_auth")


def test_checkout_missing_plan():
    c = _make_client()
    token = _register_and_login(c, 'mp1')
    r = c.post('/subscription/checkout',
               json={'card_token': 'tok_test'},
               headers=_auth(token))
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    print("OK  test_checkout_missing_plan")


def test_checkout_invalid_plan():
    c = _make_client()
    token = _register_and_login(c, 'mp2')
    r = c.post('/subscription/checkout',
               json={'plan': 'ultra', 'card_token': 'tok_test'},
               headers=_auth(token))
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    print("OK  test_checkout_invalid_plan")


def test_checkout_missing_card_token():
    c = _make_client()
    token = _register_and_login(c, 'mp3')
    r = c.post('/subscription/checkout',
               json={'plan': 'starter'},
               headers=_auth(token))
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    print("OK  test_checkout_missing_card_token")


# ── /subscription/checkout — cenários MP mockados ────────────────────────────

def _mock_sub(status='authorized', sub_id='SUBTEST001'):
    """Retorna dict simulando resposta do MP preapproval."""
    return {'id': sub_id, 'status': status, 'preapproval_plan_id': 'PLAN001'}


def test_checkout_starter_approved():
    """APRO — assinatura Starter aprovada."""
    c = _make_client()
    token = _register_and_login(c, 'apro1')
    with patch('api.app.create_subscription', return_value=_mock_sub('authorized', 'SUB_STARTER')) as mock_cs:
        r = c.post('/subscription/checkout',
                   json={'plan': 'starter', 'card_token': 'tok_apro'},
                   headers=_auth(token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.get_data(as_text=True)}"
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('plan') == 'starter'
    assert data.get('subscription_id') == 'SUB_STARTER'
    mock_cs.assert_called_once()
    print(f"OK  test_checkout_starter_approved | plan={data['plan']} sub={data['subscription_id']}")


def test_checkout_pro_approved():
    """APRO — assinatura Pro aprovada."""
    c = _make_client()
    token = _register_and_login(c, 'apro2')
    with patch('api.app.create_subscription', return_value=_mock_sub('authorized', 'SUB_PRO')):
        r = c.post('/subscription/checkout',
                   json={'plan': 'pro', 'card_token': 'tok_apro_pro'},
                   headers=_auth(token))
    assert r.status_code == 200
    data = r.get_json()
    assert data['plan'] == 'pro'
    print(f"OK  test_checkout_pro_approved | plan={data['plan']}")


def test_checkout_approved_updates_user_plan():
    """Verifica que o plano do usuário é atualizado no banco após aprovação."""
    c = _make_client()
    token = _register_and_login(c, 'planupd')
    with patch('api.app.create_subscription', return_value=_mock_sub('authorized', 'SUB_PLANUPD')):
        c.post('/subscription/checkout',
               json={'plan': 'pro', 'card_token': 'tok_planupd'},
               headers=_auth(token))
    me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    user_data = me.get_json()
    assert user_data.get('plan') == 'pro', f"Plan not updated: {user_data.get('plan')}"
    print(f"OK  test_checkout_approved_updates_user_plan | plan={user_data['plan']}")


def test_checkout_forwards_identification():
    """identification_type/number do form são repassados ao gateway MP."""
    c = _make_client()
    token = _register_and_login(c, 'ident')
    with patch('api.app.create_subscription', return_value=_mock_sub('authorized', 'SUB_ID')) as mock_cs:
        r = c.post('/subscription/checkout',
                   json={'plan': 'starter', 'card_token': 'tok_id',
                         'identification_type': 'CPF', 'identification_number': '12345678909'},
                   headers=_auth(token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.get_data(as_text=True)}"
    call_kwargs = mock_cs.call_args[1] if mock_cs.call_args[1] else {}
    call_args   = mock_cs.call_args[0] if mock_cs.call_args[0] else ()
    # identification fields deve ter chegado ao gateway
    assert call_kwargs.get('identification_type') == 'CPF' or (len(call_args) > 6 and call_args[6] == 'CPF'), \
        f"identification_type not forwarded: kwargs={call_kwargs} args={call_args}"
    print("OK  test_checkout_forwards_identification")


def test_checkout_payer_email_override():
    """payer_email do form substitui o email do usuário logado."""
    c = _make_client()
    token = _register_and_login(c, 'emailov')
    with patch('api.app.create_subscription', return_value=_mock_sub('authorized', 'SUB_EM')) as mock_cs:
        r = c.post('/subscription/checkout',
                   json={'plan': 'starter', 'card_token': 'tok_em',
                         'payer_email': 'test_buyer@testuser.com'},
                   headers=_auth(token))
    assert r.status_code == 200
    # payer_email customizado deve ter chegado ao gateway
    call_kwargs = mock_cs.call_args[1] if mock_cs.call_args[1] else {}
    assert call_kwargs.get('payer_email') == 'test_buyer@testuser.com' or \
           'test_buyer@testuser.com' in str(mock_cs.call_args), \
        f"payer_email override not forwarded: {mock_cs.call_args}"
    print("OK  test_checkout_payer_email_override")


def test_checkout_mp_error_returns_502():
    """OTHE/FUND/SECU — MP recusa o cartão → backend retorna 502."""
    c = _make_client()
    token = _register_and_login(c, 'mperr')
    with patch('api.app.create_subscription', side_effect=Exception("cc_rejected_insufficient_amount")):
        r = c.post('/subscription/checkout',
                   json={'plan': 'starter', 'card_token': 'tok_fund'},
                   headers=_auth(token))
    assert r.status_code == 502, f"Expected 502, got {r.status_code}"
    data = r.get_json()
    assert 'error' in data
    print(f"OK  test_checkout_mp_error_returns_502 | error={data['error'][:60]}")


def test_checkout_rejected_insufficient_funds():
    """FUND — saldo insuficiente."""
    c = _make_client()
    token = _register_and_login(c, 'fund')
    with patch('api.app.create_subscription',
               side_effect=Exception("cc_rejected_insufficient_amount")):
        r = c.post('/subscription/checkout',
                   json={'plan': 'pro', 'card_token': 'tok_fund'},
                   headers=_auth(token))
    assert r.status_code == 502
    print("OK  test_checkout_rejected_insufficient_funds")


def test_checkout_rejected_bad_cvv():
    """SECU — CVV inválido."""
    c = _make_client()
    token = _register_and_login(c, 'secu')
    with patch('api.app.create_subscription',
               side_effect=Exception("cc_rejected_bad_filled_security_code")):
        r = c.post('/subscription/checkout',
                   json={'plan': 'starter', 'card_token': 'tok_secu'},
                   headers=_auth(token))
    assert r.status_code == 502
    print("OK  test_checkout_rejected_bad_cvv")


def test_checkout_rejected_expired_card():
    """EXPI — data de vencimento inválida."""
    c = _make_client()
    token = _register_and_login(c, 'expi')
    with patch('api.app.create_subscription',
               side_effect=Exception("cc_rejected_bad_filled_date")):
        r = c.post('/subscription/checkout',
                   json={'plan': 'starter', 'card_token': 'tok_expi'},
                   headers=_auth(token))
    assert r.status_code == 502
    print("OK  test_checkout_rejected_expired_card")


def test_checkout_rejected_call_for_authorize():
    """CALL — requer autorização manual."""
    c = _make_client()
    token = _register_and_login(c, 'call')
    with patch('api.app.create_subscription',
               side_effect=Exception("cc_rejected_call_for_authorize")):
        r = c.post('/subscription/checkout',
                   json={'plan': 'pro', 'card_token': 'tok_call'},
                   headers=_auth(token))
    assert r.status_code == 502
    print("OK  test_checkout_rejected_call_for_authorize")


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
    assert 'invoices' in data
    assert isinstance(data['invoices'], list)
    print(f"OK  test_invoices_empty_for_new_user | count={len(data['invoices'])}")


def test_invoices_after_payment():
    """Pagamento salvo no banco aparece em /invoices."""
    c = _make_client()
    token = _register_and_login(c, 'invpay')
    with patch('api.app.create_subscription', return_value=_mock_sub('authorized', 'SUB_INV')):
        c.post('/subscription/checkout',
               json={'plan': 'starter', 'card_token': 'tok_inv'},
               headers=_auth(token))
    r = c.get('/subscription/invoices', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    data = r.get_json()
    assert len(data['invoices']) >= 1
    inv = data['invoices'][0]
    assert inv.get('plan') == 'starter'
    assert inv.get('status') in ('authorized', 'approved')
    print(f"OK  test_invoices_after_payment | invoices={len(data['invoices'])}")


# ── /subscription/cancel ─────────────────────────────────────────────────────

def test_cancel_requires_auth():
    c = _make_client()
    r = c.post('/subscription/cancel')
    assert r.status_code == 401
    print("OK  test_cancel_requires_auth")


def test_cancel_no_active_subscription():
    """Usuário sem assinatura → 400."""
    c = _make_client()
    token = _register_and_login(c, 'canc0')
    r = c.post('/subscription/cancel', headers=_auth(token))
    assert r.status_code in (400, 404), f"Expected 400/404, got {r.status_code}"
    print(f"OK  test_cancel_no_active_subscription | status={r.status_code}")


def test_cancel_active_subscription():
    """Assina e depois cancela — plano volta para free."""
    c = _make_client()
    token = _register_and_login(c, 'cancact')
    with patch('api.app.create_subscription', return_value=_mock_sub('authorized', 'SUB_CANCEL')):
        c.post('/subscription/checkout',
               json={'plan': 'pro', 'card_token': 'tok_cancel'},
               headers=_auth(token))
    with patch('api.app.cancel_subscription', return_value=True):
        r = c.post('/subscription/cancel', headers=_auth(token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.get_data(as_text=True)}"
    data = r.get_json()
    assert data.get('ok') is True
    assert data.get('plan') == 'free'
    me = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.get_json().get('plan') == 'free'
    print(f"OK  test_cancel_active_subscription | plan_after={data['plan']}")


# ── /subscription/webhook ────────────────────────────────────────────────────

def test_webhook_no_signature_allowed_without_secret():
    """Sem MP_WEBHOOK_SECRET configurado, webhook passa sem validar assinatura."""
    c = _make_client()
    payload = {'type': 'subscription_preapproval', 'data': {'id': 'SUB_WH001'}}
    with patch('api.app.get_subscription', return_value={'id': 'SUB_WH001', 'status': 'authorized',
                                                          'external_reference': 'user_1_starter',
                                                          'preapproval_plan_id': 'PLAN001'}):
        with patch('api.app.get_user_by_external_ref', return_value=(None, 'starter')):
            r = c.post('/subscription/webhook',
                       json=payload,
                       content_type='application/json')
    assert r.status_code == 200
    print(f"OK  test_webhook_no_signature_allowed_without_secret")


def test_webhook_payment_event_approved():
    """Evento payment approved → save_payment chamado."""
    c = _make_client()
    token = _register_and_login(c, 'wh_pay')
    with patch('api.app.create_subscription', return_value=_mock_sub('authorized', 'SUB_WHPAY')):
        c.post('/subscription/checkout',
               json={'plan': 'starter', 'card_token': 'tok_whpay'},
               headers=_auth(token))
    payment_data = {
        'id': 'PAY001', 'status': 'approved',
        'external_reference': 'user_1_starter',
        'transaction_amount': 19.00, 'currency_id': 'BRL',
        'date_approved': '2026-04-28T00:00:00Z',
    }
    payload = {'type': 'payment', 'data': {'id': 'PAY001'}}
    with patch('api.app.get_payment', return_value=payment_data):
        with patch('api.app.get_user_by_external_ref', return_value=({'id': 1}, 'starter')):
            r = c.post('/subscription/webhook',
                       json=payload,
                       content_type='application/json')
    assert r.status_code == 200
    print(f"OK  test_webhook_payment_event_approved")


def test_webhook_invalid_signature_rejected():
    """Webhook com secret configurado e assinatura inválida → 400."""
    import os
    c = _make_client()
    original = os.environ.get('MP_WEBHOOK_SECRET', '')
    os.environ['MP_WEBHOOK_SECRET'] = 'test_secret_key_abc'
    try:
        import leaklab.mercadopago_gateway as gw
        gw.MP_WEBHOOK_SECRET = 'test_secret_key_abc'
        payload = json.dumps({'type': 'payment', 'data': {'id': '999'}}).encode()
        r = c.post('/subscription/webhook',
                   data=payload,
                   content_type='application/json',
                   headers={'x-signature': 'ts=000,v1=invalidsignature'})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        print("OK  test_webhook_invalid_signature_rejected")
    finally:
        os.environ['MP_WEBHOOK_SECRET'] = original
        gw.MP_WEBHOOK_SECRET = original


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
