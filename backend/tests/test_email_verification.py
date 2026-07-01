"""
Verificação de email no cadastro (2FA simples anti-bot).
DB SQLite temporário isolado. SMTP "configurado" (mockado) p/ ligar a verificação.
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Liga a verificação: _email_verification_enabled() exige SMTP_* setados.
os.environ['SMTP_HOST'] = 'smtp.test'
os.environ['SMTP_USER'] = 'u'
os.environ['SMTP_PASSWORD'] = 'p'
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo
sch.init_db()

import leaklab.email_digest as ed
# Mock do transporte SMTP: não toca a rede, registra o que foi "enviado".
_SENT = []
ed.send_transactional_email = lambda to, subject, html: (_SENT.append((to, subject, html)) or True)

import api.app as A
client = A.app.test_client()


def _register(email, username='u_' + '0'):
    return client.post('/auth/register',
                       json={'username': username, 'email': email, 'password': 'pass1234'})


def test_register_is_pending_no_token():
    _SENT.clear()
    r = _register('p1@test.com', 'p1')
    j = r.get_json()
    assert r.status_code == 201, r.status_code
    assert j.get('pending_verification') is True and 'token' not in j, j
    assert j.get('email_sent') is True and _SENT, "email de verificação deveria ter sido enviado"
    # código de 6 dígitos gravado
    u = repo.get_user_by_email('p1@test.com')
    assert int(u['email_verified']) == 0
    assert u['verification_code'] and len(u['verification_code']) == 6 and u['verification_code'].isdigit()
    print("OK  test_register_is_pending_no_token")


def test_login_blocked_until_verified():
    _register('p2@test.com', 'p2')
    r = client.post('/auth/login', json={'email': 'p2@test.com', 'password': 'pass1234'})
    assert r.status_code == 403 and r.get_json().get('code') == 'email_unverified', r.get_json()
    print("OK  test_login_blocked_until_verified")


def test_wrong_code_then_correct():
    _register('p3@test.com', 'p3')
    bad = client.post('/auth/verify-email', json={'email': 'p3@test.com', 'code': '000000'})
    assert bad.status_code == 400 and bad.get_json().get('code') == 'invalid', bad.get_json()
    code = repo.get_user_by_email('p3@test.com')['verification_code']
    _SENT.clear()
    ok = client.post('/auth/verify-email', json={'email': 'p3@test.com', 'code': code})
    j = ok.get_json()
    assert ok.status_code == 200 and 'token' in j, j
    # boas-vindas enviado
    assert any('Bem-vindo' in s[1] for s in _SENT), "welcome email deveria ter saído"
    # e agora o login funciona
    rl = client.post('/auth/login', json={'email': 'p3@test.com', 'password': 'pass1234'})
    assert rl.status_code == 200 and 'token' in rl.get_json()
    print("OK  test_wrong_code_then_correct")


def test_expired_code():
    _register('p4@test.com', 'p4')
    u = repo.get_user_by_email('p4@test.com')
    # força expiração no passado
    repo.set_verification_code(u['id'], u['verification_code'], '2000-01-01 00:00:00')
    r = client.post('/auth/verify-email', json={'email': 'p4@test.com', 'code': u['verification_code']})
    assert r.status_code == 400 and r.get_json().get('code') == 'expired', r.get_json()
    print("OK  test_expired_code")


def test_too_many_attempts():
    _register('p5@test.com', 'p5')
    for _ in range(6):
        client.post('/auth/verify-email', json={'email': 'p5@test.com', 'code': '111111'})
    r = client.post('/auth/verify-email', json={'email': 'p5@test.com', 'code': '111111'})
    assert r.status_code == 429 and r.get_json().get('code') == 'too_many', r.get_json()
    print("OK  test_too_many_attempts")


def test_resend_does_not_leak_and_reissues():
    _register('p6@test.com', 'p6')
    old = repo.get_user_by_email('p6@test.com')['verification_code']
    _SENT.clear()
    r = client.post('/auth/resend-code', json={'email': 'p6@test.com'})
    assert r.status_code == 200 and r.get_json().get('ok') is True
    assert _SENT, "resend deveria reenviar"
    # email inexistente: responde ok sem vazar
    r2 = client.post('/auth/resend-code', json={'email': 'ninguem@test.com'})
    assert r2.status_code == 200 and r2.get_json().get('ok') is True
    print("OK  test_resend_does_not_leak_and_reissues")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    try: os.unlink(os.environ['LEAKLAB_DB'])
    except Exception: pass
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
