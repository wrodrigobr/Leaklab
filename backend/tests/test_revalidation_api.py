"""
Testa os endpoints admin da revalidação:
  POST /admin/revalidation/run
  GET  /admin/revalidation/runs
  GET  /admin/revalidation/runs/<id>
  GET  /admin/revalidation/runs/<id>/findings
"""
import sys, os, json, tempfile, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


# Mock flask_cors quando ausente
try:
    import flask_cors  # noqa: F401
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'revalidation_mini.txt')


_TEST_DB = None


def _setup_db():
    global _TEST_DB
    _TEST_DB = tempfile.mktemp(suffix='_revaltest.db')

    def gc():
        conn = sqlite3.connect(_TEST_DB)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    from database import schema, repositories
    schema.get_conn = gc
    repositories.get_conn = gc
    schema.init_db()
    return gc


def _make_admin_client_with_fixture():
    gc = _setup_db()
    # Carrega Flask app
    from api.app import app
    app.config['TESTING'] = True
    client = app.test_client()

    # Registra admin direto via SQL (auth padrão registra como player)
    from database.auth import generate_token
    from database.repositories import _hash_password
    conn = gc()
    conn.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        ('admin', 'admin@test.com', _hash_password('pass1234'), 'admin'),
    )
    uid = conn.execute("SELECT id FROM users WHERE username = ?", ('admin',)).fetchone()['id']
    # Insere torneio com fixture
    with open(FIXTURE, 'r', encoding='utf-8') as f:
        raw = f.read()
    conn.execute(
        "INSERT INTO tournaments (user_id, tournament_id, hero, raw_text, site) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, '999900001', 'HeroPlayer', raw, 'pokerstars'),
    )
    conn.commit()
    conn.close()
    token = generate_token(uid, 'admin')
    return client, token, uid


def _hdr(tok):
    return {'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'}


# -- Testes ------------------------------------------------------------------

def test_run_sync_returns_run_id_and_counts():
    client, tok, _ = _make_admin_client_with_fixture()
    r = client.post('/admin/revalidation/run',
                    data=json.dumps({'scope': 'all', 'sync': True,
                                     'output_dir': tempfile.mkdtemp(prefix='reval_api_')}),
                    headers=_hdr(tok))
    assert r.status_code == 200, f"esperado 200, recebi {r.status_code}: {r.get_data(as_text=True)}"
    d = r.get_json()
    assert d['run_id'] is not None
    assert d['status'] == 'done'
    assert d['total_decisions'] > 0
    assert sum(d['category_counts'].values()) == d['total_decisions']
    print(f"OK  test_run_sync_returns_run_id_and_counts (run_id={d['run_id']}, counts={d['category_counts']})")


def test_run_requires_admin():
    """Sem token de admin, deve retornar 401/403."""
    client, _, _ = _make_admin_client_with_fixture()
    r = client.post('/admin/revalidation/run',
                    data=json.dumps({'sync': True}),
                    content_type='application/json')
    assert r.status_code in (401, 403)
    print(f"OK  test_run_requires_admin (status={r.status_code})")


def test_list_runs():
    client, tok, _ = _make_admin_client_with_fixture()
    # cria dois runs
    client.post('/admin/revalidation/run',
                data=json.dumps({'sync': True}), headers=_hdr(tok))
    client.post('/admin/revalidation/run',
                data=json.dumps({'sync': True}), headers=_hdr(tok))
    r = client.get('/admin/revalidation/runs?limit=10', headers=_hdr(tok))
    assert r.status_code == 200
    d = r.get_json()
    assert 'runs' in d
    assert len(d['runs']) >= 2
    for run in d['runs']:
        assert 'category_counts' in run
        assert isinstance(run['category_counts'], dict)
    print(f"OK  test_list_runs (n={len(d['runs'])})")


def test_run_detail_returns_404_when_missing():
    client, tok, _ = _make_admin_client_with_fixture()
    r = client.get('/admin/revalidation/runs/99999', headers=_hdr(tok))
    assert r.status_code == 404
    print("OK  test_run_detail_returns_404_when_missing")


def test_run_detail_and_findings_pagination():
    client, tok, _ = _make_admin_client_with_fixture()
    r = client.post('/admin/revalidation/run',
                    data=json.dumps({'sync': True}), headers=_hdr(tok))
    run_id = r.get_json()['run_id']

    r2 = client.get(f'/admin/revalidation/runs/{run_id}', headers=_hdr(tok))
    assert r2.status_code == 200
    detail = r2.get_json()
    assert detail['id'] == run_id
    assert detail['total_decisions'] > 0

    r3 = client.get(f'/admin/revalidation/runs/{run_id}/findings?limit=2&offset=0',
                    headers=_hdr(tok))
    assert r3.status_code == 200
    page = r3.get_json()
    assert page['run_id'] == run_id
    assert page['limit'] == 2
    assert page['offset'] == 0
    assert len(page['findings']) <= 2
    assert page['total'] >= len(page['findings'])
    for f in page['findings']:
        assert 'category' in f
        assert 'severity_score' in f
        assert isinstance(f.get('reasons'), list)
    print(f"OK  test_run_detail_and_findings_pagination (total={page['total']})")


def test_findings_filter_by_category():
    client, tok, _ = _make_admin_client_with_fixture()
    r = client.post('/admin/revalidation/run',
                    data=json.dumps({'sync': True}), headers=_hdr(tok))
    run_id = r.get_json()['run_id']

    r2 = client.get(f'/admin/revalidation/runs/{run_id}/findings?category=aligned&limit=100',
                    headers=_hdr(tok))
    assert r2.status_code == 200
    d = r2.get_json()
    for f in d['findings']:
        assert f['category'] == 'aligned'
    print(f"OK  test_findings_filter_by_category (n_aligned={len(d['findings'])})")


def test_findings_severity_desc_default_order():
    client, tok, _ = _make_admin_client_with_fixture()
    r = client.post('/admin/revalidation/run',
                    data=json.dumps({'sync': True}), headers=_hdr(tok))
    run_id = r.get_json()['run_id']

    r2 = client.get(f'/admin/revalidation/runs/{run_id}/findings?limit=50',
                    headers=_hdr(tok))
    scores = [f['severity_score'] for f in r2.get_json()['findings']]
    assert scores == sorted(scores, reverse=True), f"ordem não é desc: {scores}"
    print("OK  test_findings_severity_desc_default_order")


def test_background_task_status():
    client, tok, _ = _make_admin_client_with_fixture()
    r = client.post('/admin/revalidation/run',
                    data=json.dumps({'sync': False}), headers=_hdr(tok))
    assert r.status_code == 200
    d = r.get_json()
    assert d['status'] == 'started'
    assert d['task_id'] >= 1
    task_id = d['task_id']
    # Aguarda a thread finalizar
    import time
    for _ in range(20):
        s = client.get(f'/admin/revalidation/tasks/{task_id}', headers=_hdr(tok))
        if s.get_json()['status'] in ('done', 'error'):
            break
        time.sleep(0.1)
    final = client.get(f'/admin/revalidation/tasks/{task_id}', headers=_hdr(tok)).get_json()
    assert final['status'] == 'done', f"esperado done, recebi {final}"
    assert final['run_id'] is not None
    print(f"OK  test_background_task_status (run_id={final['run_id']})")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(0 if failed == 0 else 1)
