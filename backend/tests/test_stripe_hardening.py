"""
PAY-03 — Rotina PESADA de testes anti-fraude do Stripe.

Garante que o fluxo de pagamento do aluno é à prova de manipulação pelo cliente:
o backend deriva TUDO do PaymentIntent real (metadata + amount), nunca do body.

Cobre:
  - ownership: não dá pra ativar o PI de outra pessoa
  - ciclo/valor vêm do PI, não do body (pagar mensal e reivindicar anual → bloqueado)
  - valor cobrado tem de bater com a tabela de preços (amount tampering → bloqueado)
  - status do PI (succeeded/processing) obrigatório
  - idempotência: activate 2x / activate+webhook / retry de webhook → 1 pagamento
  - webhook: assinatura inválida rejeitada; metadata define ciclo/vigência
  - /subscription/upgrade agora é admin-only (era self-grant grátis)
  - cancel/checkout exigem auth
Todos mockam o Stripe via unittest.mock.
"""
import sys, os, json, traceback, sqlite3, tempfile, datetime
from unittest.mock import patch
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
    _TEST_DB = tempfile.mktemp(suffix='_hardening.db')
    def gc():
        conn = sqlite3.connect(_TEST_DB, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON'); conn.execute('PRAGMA busy_timeout=10000')
        return conn
    schema.get_conn = repositories.get_conn = gc
    schema.init_db()


def _teardown_db():
    if _TEST_DB and os.path.exists(_TEST_DB):
        try: os.unlink(_TEST_DB)
        except OSError: pass


def _client():
    _setup_db()
    from api.app import app
    app.config['TESTING'] = True
    return app.test_client()


def _player(c, suffix=''):
    email = f'hard{suffix}@t.com'
    r = c.post('/auth/register', json={'username': f'hard{suffix}', 'email': email, 'password': 'pass1234'},
               content_type='application/json')
    if r.status_code == 409:
        r = c.post('/auth/login', json={'email': email, 'password': 'pass1234'}, content_type='application/json')
    tok = r.get_json().get('token', '')
    uid = c.get('/auth/me', headers={'Authorization': f'Bearer {tok}'}).get_json().get('user_id')
    return tok, uid


def _auth(tok):
    return {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}


def _pi(pi_id='pi_T', status='succeeded', user_id=1, billing='monthly', amount=None, plan='pro'):
    cents = amount if amount is not None else (99000 if billing == 'annual' else 9900)
    return {'id': pi_id, 'status': status, 'amount': cents, 'currency': 'brl',
            'metadata': {'user_id': str(user_id), 'plan_name': plan, 'billing_cycle': billing}}


def _plan_of(c, tok):
    return c.get('/auth/me', headers={'Authorization': f'Bearer {tok}'}).get_json().get('plan')


def _invoices(c, tok):
    return c.get('/subscription/invoices', headers={'Authorization': f'Bearer {tok}'}).get_json()['invoices']


# ── Ownership ─────────────────────────────────────────────────────────────────

def test_activate_rejects_foreign_pi():
    """Vetor A: usuário não pode ativar o PI de OUTRA conta (metadata.user_id diverge)."""
    c = _client()
    tokA, uidA = _player(c, 'A')
    tokB, uidB = _player(c, 'B')
    # PI pertence a A; B tenta ativar
    with patch('api.app.get_payment', return_value=_pi('pi_A', 'succeeded', user_id=uidA)):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_A', 'subscription_id': 'pi_A'},
                   headers=_auth(tokB))
    assert r.status_code == 403, f"esperava 403, veio {r.status_code}"
    assert _plan_of(c, tokB) == 'free', "B não pode virar pro com o pagamento de A"
    print("OK  test_activate_rejects_foreign_pi")


def test_activate_owner_succeeds():
    c = _client()
    tok, uid = _player(c, 'own')
    with patch('api.app.get_payment', return_value=_pi('pi_own', 'succeeded', user_id=uid)):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_own', 'subscription_id': 'pi_own'},
                   headers=_auth(tok))
    assert r.status_code == 200 and _plan_of(c, tok) == 'pro'
    print("OK  test_activate_owner_succeeds")


def test_activate_allows_legacy_pi_without_metadata():
    """PI legado sem metadata.user_id → permitido (back-compat), tratado como mensal."""
    c = _client()
    tok, uid = _player(c, 'leg')
    legacy = {'id': 'pi_leg', 'status': 'succeeded', 'amount': 9900, 'currency': 'brl', 'metadata': {}}
    with patch('api.app.get_payment', return_value=legacy):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_leg', 'subscription_id': 'pi_leg'},
                   headers=_auth(tok))
    assert r.status_code == 200 and _plan_of(c, tok) == 'pro'
    print("OK  test_activate_allows_legacy_pi_without_metadata")


# ── Ciclo/valor derivados do PI, não do body ─────────────────────────────────

def test_billing_cycle_comes_from_pi_not_body():
    """Vetor B: PI é MENSAL (R$99); body pede 'annual'. Servidor concede MENSAL (30d, R$99)."""
    c = _client()
    tok, uid = _player(c, 'cyc')
    with patch('api.app.get_payment', return_value=_pi('pi_cyc', 'succeeded', user_id=uid, billing='monthly')):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_cyc', 'subscription_id': 'pi_cyc',
                         'billing': 'annual'},   # ← tentativa de fraude, deve ser ignorada
                   headers=_auth(tok))
    assert r.status_code == 200
    data = r.get_json()
    assert data['billing'] == 'monthly', data
    exp = datetime.datetime.strptime(data['expires_at'], '%Y-%m-%d %H:%M:%S')
    assert (exp - datetime.datetime.utcnow()).days <= 31
    assert _invoices(c, tok)[0]['amount_cents'] == 9900   # valor real, não R$990
    print("OK  test_billing_cycle_comes_from_pi_not_body")


def test_activate_rejects_amount_mismatch():
    """PI diz 'annual' no metadata mas o amount é 9900 (mensal) → inconsistente → 400."""
    c = _client()
    tok, uid = _player(c, 'mm')
    bad = _pi('pi_mm', 'succeeded', user_id=uid, billing='annual', amount=9900)  # anual deveria ser 99000
    with patch('api.app.get_payment', return_value=bad):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_mm', 'subscription_id': 'pi_mm'},
                   headers=_auth(tok))
    assert r.status_code == 400, r.get_json()
    assert _plan_of(c, tok) == 'free'
    print("OK  test_activate_rejects_amount_mismatch")


def test_activate_ignores_tampered_body_amount():
    """Valor no body é irrelevante — grava o amount REAL do PI."""
    c = _client()
    tok, uid = _player(c, 'tamp')
    with patch('api.app.get_payment', return_value=_pi('pi_tamp', 'succeeded', user_id=uid, billing='annual')):
        c.post('/subscription/activate',
               json={'plan': 'pro', 'payment_intent_id': 'pi_tamp', 'subscription_id': 'pi_tamp', 'amount': 1},
               headers=_auth(tok))
    assert _invoices(c, tok)[0]['amount_cents'] == 99000
    print("OK  test_activate_ignores_tampered_body_amount")


# ── Status do pagamento ──────────────────────────────────────────────────────

def test_activate_rejects_unsucceeded():
    c = _client()
    tok, uid = _player(c, 'uns')
    with patch('api.app.get_payment', return_value=_pi('pi_u', 'requires_payment_method', user_id=uid)):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_u', 'subscription_id': 'pi_u'},
                   headers=_auth(tok))
    assert r.status_code == 400 and _plan_of(c, tok) == 'free'
    print("OK  test_activate_rejects_unsucceeded")


def test_activate_rejects_not_found_pi():
    c = _client()
    tok, uid = _player(c, 'nf')
    with patch('api.app.get_payment', return_value=None):
        r = c.post('/subscription/activate',
                   json={'plan': 'pro', 'payment_intent_id': 'pi_x', 'subscription_id': 'pi_x'},
                   headers=_auth(tok))
    assert r.status_code == 400 and _plan_of(c, tok) == 'free'
    print("OK  test_activate_rejects_not_found_pi")


def test_activate_rejects_non_pro_plan():
    c = _client()
    tok, uid = _player(c, 'np')
    r = c.post('/subscription/activate',
               json={'plan': 'free', 'payment_intent_id': 'pi_x', 'subscription_id': 'pi_x'},
               headers=_auth(tok))
    assert r.status_code == 400
    print("OK  test_activate_rejects_non_pro_plan")


# ── Idempotência (não duplica receita) ───────────────────────────────────────

def test_double_activate_single_payment():
    c = _client()
    tok, uid = _player(c, 'dbl')
    with patch('api.app.get_payment', return_value=_pi('pi_d', 'succeeded', user_id=uid)):
        c.post('/subscription/activate', json={'plan': 'pro', 'payment_intent_id': 'pi_d', 'subscription_id': 'pi_d'}, headers=_auth(tok))
        c.post('/subscription/activate', json={'plan': 'pro', 'payment_intent_id': 'pi_d', 'subscription_id': 'pi_d'}, headers=_auth(tok))
    rows = [p for p in _invoices(c, tok) if p['gateway_id'] == 'pi_d' and p['status'] == 'approved']
    assert len(rows) == 1, f"esperava 1, achou {len(rows)}"
    print("OK  test_double_activate_single_payment")


def test_activate_then_webhook_single_payment():
    c = _client()
    tok, uid = _player(c, 'aw')
    with patch('api.app.get_payment', return_value=_pi('pi_aw', 'succeeded', user_id=uid)):
        c.post('/subscription/activate', json={'plan': 'pro', 'payment_intent_id': 'pi_aw', 'subscription_id': 'pi_aw'}, headers=_auth(tok))
    payload = json.dumps({'type': 'payment_intent.succeeded',
                          'data': {'object': {'id': 'pi_aw', 'amount': 9900,
                                              'metadata': {'user_id': str(uid), 'plan_name': 'pro', 'billing_cycle': 'monthly'}}}}).encode()
    with patch('api.app.STRIPE_WEBHOOK_SECRET', ''):
        c.post('/subscription/webhook', data=payload, content_type='application/json')
    rows = [p for p in _invoices(c, tok) if p['gateway_id'] == 'pi_aw' and p['status'] == 'approved']
    assert len(rows) == 1
    print("OK  test_activate_then_webhook_single_payment")


# ── Webhook ──────────────────────────────────────────────────────────────────

def test_webhook_invalid_signature_rejected():
    c = _client()
    import leaklab.stripe_gateway as gw
    orig = gw.STRIPE_WEBHOOK_SECRET
    gw.STRIPE_WEBHOOK_SECRET = 'whsec_test'
    try:
        with patch('api.app.STRIPE_WEBHOOK_SECRET', 'whsec_test'):
            with patch('api.app.validate_webhook', side_effect=Exception("bad sig")):
                r = c.post('/subscription/webhook', data=json.dumps({'type': 'ping'}).encode(),
                           content_type='application/json', headers={'stripe-signature': 'bad'})
        assert r.status_code == 400
        print("OK  test_webhook_invalid_signature_rejected")
    finally:
        gw.STRIPE_WEBHOOK_SECRET = orig


def test_webhook_annual_sets_year_expiry():
    c = _client()
    tok, uid = _player(c, 'wa')
    payload = json.dumps({'type': 'payment_intent.succeeded',
                          'data': {'object': {'id': 'pi_wa', 'amount': 99000,
                                              'metadata': {'user_id': str(uid), 'plan_name': 'pro', 'billing_cycle': 'annual'}}}}).encode()
    with patch('api.app.STRIPE_WEBHOOK_SECRET', ''):
        c.post('/subscription/webhook', data=payload, content_type='application/json')
    st = repositories.get_quota_status(uid)
    assert st['plan'] == 'pro' and st['plan_expires_at']
    exp = datetime.datetime.strptime(st['plan_expires_at'], '%Y-%m-%d %H:%M:%S')
    assert (exp - datetime.datetime.utcnow()).days >= 360
    print("OK  test_webhook_annual_sets_year_expiry")


# ── /subscription/upgrade agora é admin-only ─────────────────────────────────

def test_upgrade_blocked_for_player():
    """Era @require_auth → self-grant grátis. Agora player recebe 401/403."""
    c = _client()
    tok, uid = _player(c, 'up')
    r = c.post('/subscription/upgrade', json={'plan': 'pro'}, headers=_auth(tok))
    assert r.status_code in (401, 403), r.status_code
    assert _plan_of(c, tok) == 'free', "player não pode se auto-conceder pro"
    print("OK  test_upgrade_blocked_for_player")


def test_upgrade_allowed_for_admin():
    c = _client()
    tok, uid = _player(c, 'adm')
    admin_id = repositories.create_user('admin1', 'admin1@t.com', 'pass', role='admin')
    admin_tok = generate_token(admin_id, 'admin')
    # admin concede pro a um aluno
    r = c.post('/subscription/upgrade', json={'plan': 'pro', 'user_id': uid}, headers=_auth(admin_tok))
    assert r.status_code == 200, r.get_json()
    assert _plan_of(c, tok) == 'pro'
    print("OK  test_upgrade_allowed_for_admin")


# ── auth nos endpoints sensíveis ─────────────────────────────────────────────

def test_checkout_and_cancel_require_auth():
    c = _client()
    assert c.post('/subscription/checkout', json={'plan': 'pro'}).status_code == 401
    assert c.post('/subscription/cancel').status_code == 401
    print("OK  test_checkout_and_cancel_require_auth")


# ── Visão financeira administrativa (PAY-03) ─────────────────────────────────

def _admin(c):
    aid = repositories.create_user('fadmin', 'fadmin@t.com', 'pass', role='admin')
    return generate_token(aid, 'admin'), aid


def test_admin_finance_endpoints_require_admin():
    c = _client()
    tok, _ = _player(c, 'naf')
    assert c.get('/admin/finance/overview', headers=_auth(tok)).status_code in (401, 403)
    assert c.get('/admin/payments', headers=_auth(tok)).status_code in (401, 403)
    print("OK  test_admin_finance_endpoints_require_admin")


def test_admin_overview_revenue_and_gateway():
    c = _client()
    tok, uid = _player(c, 'ov')
    with patch('api.app.get_payment', return_value=_pi('pi_ov', 'succeeded', user_id=uid, billing='annual')):
        c.post('/subscription/activate', json={'plan': 'pro', 'payment_intent_id': 'pi_ov', 'subscription_id': 'pi_ov'}, headers=_auth(tok))
    atok, _ = _admin(c)
    ov = c.get('/admin/finance/overview', headers=_auth(atok)).get_json()
    assert ov['revenue']['gross_cents'] == 99000
    assert ov['revenue']['approved_count'] == 1
    assert any(g['gateway'] == 'stripe' for g in ov['revenue']['by_gateway'])
    assert ov['revenue']['mrr_cents'] == 9900   # 1 pagante pro
    assert ov['duplicates'] == []
    print("OK  test_admin_overview_revenue_and_gateway")


def test_admin_payments_list_and_filter():
    c = _client()
    tok, uid = _player(c, 'pl')
    with patch('api.app.get_payment', return_value=_pi('pi_pl', 'succeeded', user_id=uid)):
        c.post('/subscription/activate', json={'plan': 'pro', 'payment_intent_id': 'pi_pl', 'subscription_id': 'pi_pl'}, headers=_auth(tok))
    atok, _ = _admin(c)
    allp = c.get('/admin/payments', headers=_auth(atok)).get_json()
    assert allp['total'] >= 1 and allp['payments'][0]['username'] == 'hardpl'
    # filtro por gateway inexistente → vazio
    mp = c.get('/admin/payments?gateway=mercadopago', headers=_auth(atok)).get_json()
    assert mp['total'] == 0
    # filtro stripe → traz
    st = c.get('/admin/payments?gateway=stripe', headers=_auth(atok)).get_json()
    assert st['total'] >= 1
    print("OK  test_admin_payments_list_and_filter")


def test_admin_detect_duplicate_payments():
    """Insere 2 linhas aprovadas com o mesmo gateway_id (dado anômalo) → detectado."""
    c = _client()
    tok, uid = _player(c, 'dup')
    conn = repositories.get_conn()
    for _ in range(2):
        conn.execute("INSERT INTO payments (user_id, plan, amount_cents, currency, status, gateway, gateway_id) "
                     "VALUES (?,?,?,?,?,?,?)", (uid, 'pro', 9900, 'BRL', 'approved', 'stripe', 'pi_dupe'))
    conn.commit(); conn.close()
    dups = repositories.admin_detect_duplicate_payments()
    assert any(d['gateway_id'] == 'pi_dupe' and d['n'] == 2 for d in dups)
    print("OK  test_admin_detect_duplicate_payments")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}"); traceback.print_exc(); failed += 1
    _teardown_db()
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
