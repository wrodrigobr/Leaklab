"""
Salvar perfil (demografia + telefone) não pode dar 500. Regressão do bug: a coluna
`whatsapp_phone` era `ADD COLUMN ... UNIQUE` — o SQLite não aceita UNIQUE via ALTER
(falhava e o except engolia → coluna nunca criada → 500 no /profile/phone). E no PG
ela estava só no bloco regular (abortável). Aqui: init_db cria a coluna e o save passa.
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo
sch.init_db()

# flask_cors pode não estar instalado no ambiente de teste
try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

import api.app as A
client = A.app.test_client()


def _auth():
    r = client.post('/auth/register', json={'username': 'prof1', 'email': 'prof1@test.com', 'password': 'pass1234'})
    j = r.get_json()
    tok = j.get('token')
    if not tok:  # verificação ligada (não deveria em teste sem SMTP), mas por robustez
        u = repo.get_user_by_email('prof1@test.com')
        from database.auth import generate_token
        tok = generate_token(u['id'], 'player')
    return {'Authorization': f'Bearer {tok}'}


def test_whatsapp_phone_column_exists():
    cols = {r[1] for r in repo.get_conn().execute('PRAGMA table_info(users)').fetchall()}
    for c in ('whatsapp_phone', 'birth_year', 'state_province', 'city', 'poker_experience_years'):
        assert c in cols, f"coluna {c} não foi criada pela migração"
    print("OK  test_whatsapp_phone_column_exists")


def test_save_demographics_and_phone_no_500():
    h = _auth()
    r1 = client.patch('/player/profile', headers=h, json={
        'birth_year': 1980, 'country': 'Brasil', 'state_province': 'SP', 'city': 'Osasco',
        'poker_experience_years': 10, 'main_game_type': 'mtt', 'usual_buyin_range': 'micro'})
    assert r1.status_code == 200, (r1.status_code, r1.get_json())
    r2 = client.patch('/profile/phone', headers=h, json={'phone': '+55 11 99999-9999'})
    assert r2.status_code == 200, (r2.status_code, r2.get_json())
    assert r2.get_json().get('phone') == '5511999999999'  # normalizado
    print("OK  test_save_demographics_and_phone_no_500")


def test_phone_invalid_is_400_not_500():
    h = _auth()
    r = client.patch('/profile/phone', headers=h, json={'phone': '123'})
    assert r.status_code == 400, (r.status_code, r.get_json())
    print("OK  test_phone_invalid_is_400_not_500")


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
