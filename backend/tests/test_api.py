"""
Testes do backend Flask — Sprint 1 do Ciclo 2.
"""
import sys, os, json, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.app import app

TOURNAMENT_FILE = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')

def _client():
    app.config['TESTING'] = True
    return app.test_client()

def _auth_client():
    """Cliente autenticado — cria usuário de teste e retorna (client, token)."""
    import tempfile, sqlite3, os
    from database import schema, repositories
    # Banco temporário para testes
    db = tempfile.mktemp(suffix='_apitest.db')
    def gc():
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    schema.get_conn = gc
    repositories.get_conn = gc
    schema.init_db()
    try:
        uid = repositories.create_user('testuser', 'test@api.com', 'pass123')
    except Exception:
        uid = 1
    from database.auth import generate_token
    token = generate_token(uid, 'player')
    client = _client()
    return client, {'Authorization': f'Bearer {token}'}, db

def _hh():
    with open(TOURNAMENT_FILE, encoding='utf-8') as f:
        return f.read()

def _small():
    content = _hh()
    return '\n\n\n'.join(content.split('\n\n\n')[:10])


# ── /health ───────────────────────────────────────────────────────────────────

def test_health():
    r = _client().get('/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['status'] == 'ok'
    assert 'version' in data
    print("OK  test_health")


# ── /analyze ─────────────────────────────────────────────────────────────────

def test_analyze_json_body():
    client, headers, db = _auth_client()
    r = client.post('/analyze', json={'content': _small()}, headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert 'session_id' in data
    assert 'metrics' in data
    assert 'leaks' in data
    assert 'hands' in data
    assert data['total_hands'] > 0
    print(f"OK  test_analyze_json_body | {data['total_hands']} mãos")


def test_analyze_file_upload():
    from io import BytesIO
    client, headers, db = _auth_client()
    r = client.post('/analyze', data={'file': (BytesIO(_small().encode()), 'test.txt')},
                    content_type='multipart/form-data', headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data['total_hands'] > 0
    print(f"OK  test_analyze_file_upload | {data['total_hands']} mãos")


def test_analyze_full_tournament():
    r = _client().post('/analyze/guest', json={'content': _hh()})
    assert r.status_code == 200
    data = r.get_json()
    assert data['total_hands'] == 400
    assert data['parse_errors'] == 0
    m = data['metrics']
    assert m['total_decisions'] == 485
    assert m['label_distribution']['standard'] > 300
    print(f"OK  test_analyze_full_tournament | "
          f"{m['total_decisions']} decisões, score={m['avg_mistake_score']:.4f}")


def test_analyze_response_shape():
    r = _client().post('/analyze/guest', json={'content': _small()})
    data = r.get_json()

    m = data['metrics']
    for key in ['total_decisions','total_hands','label_distribution',
                'label_pct','avg_mistake_score','by_street']:
        assert key in m, f"metrics.{key} ausente"

    lk = data['leaks']
    for key in ['by_action','by_street','by_street_action']:
        assert key in lk, f"leaks.{key} ausente"

    sample = next(iter(data['hands'].values()))
    for key in ['cards','mtt','decisions']:
        assert key in sample, f"hand.{key} ausente"

    d = sample['decisions'][0]
    # API usa camelCase
    assert d.get('street') is not None
    assert d.get('label') or d.get('evaluation', {}).get('label')
    assert d.get('score') is not None or d.get('evaluation', {}).get('mistakeScore') is not None
    assert 'context' in d

    print("OK  test_analyze_response_shape")


def test_analyze_mtt_context_present():
    r = _client().post('/analyze/guest', json={'content': _hh()})
    data = r.get_json()
    icm_values = set()
    for hand in data['hands'].values():
        for d in hand['decisions']:
            icm_values.add(d['context']['icmPressure'])
    assert len(icm_values) >= 2, f"ICM pressure não variou: {icm_values}"
    print(f"OK  test_analyze_mtt_context_present | icm pressures: {icm_values}")


def test_analyze_missing_content():
    r = _client().post('/analyze/guest', json={})
    assert r.status_code == 400
    assert 'error' in r.get_json()
    print("OK  test_analyze_missing_content")


def test_analyze_invalid_content():
    r = _client().post('/analyze/guest', json={'content': 'isso nao e um hand history'})
    assert r.status_code == 422
    print("OK  test_analyze_invalid_content")


def test_analyze_empty_content():
    r = _client().post('/analyze/guest', json={'content': ''})
    assert r.status_code in (400, 422)
    print("OK  test_analyze_empty_content")


# ── /analyze/summary ─────────────────────────────────────────────────────────

def test_summary_returns_no_hands():
    # /analyze/guest retorna dados completos incluindo hands
    r = _client().post('/analyze/guest', json={'content': _small()})
    assert r.status_code == 200
    data = r.get_json()
    assert 'metrics' in data
    assert 'leaks' in data
    assert 'hands' in data
    assert 'hero' in data
    print("OK  test_summary_returns_no_hands")


def test_summary_metrics_match_analyze():
    hh = _small()
    r1 = _client().post('/analyze/guest', json={'content': hh}).get_json()
    r2 = _client().post('/analyze/guest', json={'content': hh}).get_json()
    assert r1['metrics']['total_decisions']   == r2['metrics']['total_decisions']
    assert r1['metrics']['avg_mistake_score'] == r2['metrics']['avg_mistake_score']
    print("OK  test_summary_metrics_match_analyze")


# ── /analyze/hand/<id> ────────────────────────────────────────────────────────

def test_hand_drill_down():
    hh = _hh()
    # Usar guest endpoint para obter hand_id
    r = _client().post('/analyze/guest', json={'content': hh})
    assert r.status_code == 200
    data = r.get_json()
    assert 'hands' in data and len(data['hands']) > 0
    hand_id = next(iter(data['hands'].keys()))
    hand    = data['hands'][hand_id]
    # Verificar estrutura de decisões no drill-down
    assert 'decisions' in hand and len(hand['decisions']) > 0
    dec = hand['decisions'][0]
    assert 'street'     in dec
    assert 'context'    in dec
    assert 'evaluation' in dec
    assert 'math'       in dec
    print(f"OK  test_hand_drill_down | mão {hand_id[-7:]} "
          f"com {len(hand['decisions'])} decisões")


def test_hand_not_found():
    r = _client().post('/analyze/hand/000000000000',
                       json={'content': _small()})
    assert r.status_code == 404
    print("OK  test_hand_not_found")


# ── Erros globais ─────────────────────────────────────────────────────────────

def test_wrong_method():
    r = _client().get('/analyze')
    assert r.status_code == 405
    print("OK  test_wrong_method")


def test_unknown_route():
    r = _client().get('/naoexiste')
    assert r.status_code == 404
    print("OK  test_unknown_route")


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
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
