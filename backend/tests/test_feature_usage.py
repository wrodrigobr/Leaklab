"""
Analytics de uso (MVP): record_feature_usage (upsert agregado) + get_feature_usage_report
(ranking por usuários únicos + DAU/WAU/MAU) + endpoint admin gated.
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo
sch.init_db()

try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

import api.app as A
from database.auth import generate_token
client = A.app.test_client()


def test_record_and_report_ranking():
    # user 1 usa ghost_table 3x + dashboard 1x; user 2 usa ghost_table 1x
    for _ in range(3):
        repo.record_feature_usage(1, 'ghost_table')
    repo.record_feature_usage(1, 'dashboard')
    repo.record_feature_usage(2, 'ghost_table')

    rep = repo.get_feature_usage_report(30)
    feats = {f['feature_key']: f for f in rep['features']}
    assert feats['ghost_table']['users'] == 2, feats
    assert feats['ghost_table']['hits'] == 4, feats     # upsert somou (3+1)
    assert feats['dashboard']['users'] == 1
    # ranking: ghost_table (2 users) antes de dashboard (1)
    assert rep['features'][0]['feature_key'] == 'ghost_table'
    assert rep['dau'] == 2 and rep['active_window'] == 2
    print("OK  test_record_and_report_ranking")


def test_endpoint_requires_admin():
    uid = repo.create_user('player_fu', 'player_fu@test.com', 'pass1234', 'player')
    tok = generate_token(uid, 'player')
    r = client.get('/admin/feature-usage', headers={'Authorization': f'Bearer {tok}'})
    assert r.status_code in (401, 403), r.status_code
    print("OK  test_endpoint_requires_admin")


def test_endpoint_admin_ok():
    uid = repo.create_user('admin_fu', 'admin_fu@test.com', 'pass1234', 'admin')
    tok = generate_token(uid, 'admin')
    r = client.get('/admin/feature-usage?days=7', headers={'Authorization': f'Bearer {tok}'})
    assert r.status_code == 200, (r.status_code, r.get_json())
    j = r.get_json()
    assert 'features' in j and 'dau' in j and j['days'] == 7
    print("OK  test_endpoint_admin_ok")


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
