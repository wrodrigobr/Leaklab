"""
Reset de senha via código por email ("esqueci a senha"). DB SQLite temporário isolado,
SMTP mockado p/ ligar o fluxo. Reusa as colunas do 2FA de cadastro.
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['SMTP_HOST'] = 'smtp.test'
os.environ['SMTP_USER'] = 'u'
os.environ['SMTP_PASSWORD'] = 'p'
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo
sch.init_db()

import leaklab.email_digest as ed
_SENT = []
ed.send_transactional_email = lambda to, subject, html: (_SENT.append((to, subject, html)) or True)

import api.app as A
client = A.app.test_client()


def _register(email, username):
    return client.post('/auth/register',
                       json={'username': username, 'email': email, 'password': 'oldpass12'})


def test_forgot_generic_for_unknown_email():
    """Email inexistente: 200 genérico e NENHUM email enviado (não vaza enumeração)."""
    _SENT.clear()
    r = client.post('/auth/forgot-password', json={'email': 'ghost@nope.com'})
    assert r.status_code == 200 and r.get_json().get('ok') is True, r.get_json()
    assert not _SENT, "não devia enviar email para conta inexistente"
    print("OK  test_forgot_generic_for_unknown_email")


def test_forgot_sends_code_and_reset_works():
    _register('r1@test.com', 'r1')
    _SENT.clear()
    r = client.post('/auth/forgot-password', json={'email': 'r1@test.com'})
    assert r.status_code == 200 and r.get_json().get('ok') is True
    assert _SENT, "email de reset deveria ter sido enviado"
    code = repo.get_user_by_email('r1@test.com')['verification_code']
    assert code and len(code) == 6 and code.isdigit()

    # reset com o código correto
    r = client.post('/auth/reset-password',
                    json={'email': 'r1@test.com', 'code': code, 'new_password': 'newpass99'})
    assert r.status_code == 200 and r.get_json().get('ok') is True, r.get_json()

    # senha nova funciona, antiga não; e o código foi limpo + conta verificada
    assert repo.verify_password('r1@test.com', 'newpass99')
    assert not repo.verify_password('r1@test.com', 'oldpass12')
    u = repo.get_user_by_email('r1@test.com')
    assert u['verification_code'] is None and int(u['email_verified']) == 1
    print("OK  test_forgot_sends_code_and_reset_works")


def test_reset_wrong_code_rejected():
    _register('r2@test.com', 'r2')
    client.post('/auth/forgot-password', json={'email': 'r2@test.com'})
    r = client.post('/auth/reset-password',
                    json={'email': 'r2@test.com', 'code': '000000', 'new_password': 'newpass99'})
    assert r.status_code == 400 and r.get_json().get('code') == 'invalid', r.get_json()
    assert repo.verify_password('r2@test.com', 'oldpass12'), "senha não podia ter mudado"
    print("OK  test_reset_wrong_code_rejected")


def test_reset_weak_password_rejected():
    _register('r3@test.com', 'r3')
    client.post('/auth/forgot-password', json={'email': 'r3@test.com'})
    code = repo.get_user_by_email('r3@test.com')['verification_code']
    r = client.post('/auth/reset-password',
                    json={'email': 'r3@test.com', 'code': code, 'new_password': 'short'})
    assert r.status_code == 400 and r.get_json().get('code') == 'weak', r.get_json()
    print("OK  test_reset_weak_password_rejected")


def test_reset_unknown_email_is_generic_invalid():
    """Reset com email inexistente não revela isso — vira 'código inválido'."""
    r = client.post('/auth/reset-password',
                    json={'email': 'ghost2@nope.com', 'code': '123456', 'new_password': 'newpass99'})
    assert r.status_code == 400 and r.get_json().get('code') == 'invalid', r.get_json()
    print("OK  test_reset_unknown_email_is_generic_invalid")


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
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
