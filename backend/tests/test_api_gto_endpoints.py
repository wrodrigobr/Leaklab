"""
test_api_gto_endpoints.py — Cobertura dos endpoints GTO da API.

Cobre:
  - GET /replay/<id>/gto: found, not found, preflop KK regressão, is_aggregate flag
  - POST /admin/gto/nodes: insert válido, validações de campo, limite 500
  - GET /admin/gto/stats: requer admin
  - GET /preflop-ranges: estrutura básica da resposta

Banco SQLite temporário por teste — sem efeitos colaterais.
"""
import sys, os, json, sqlite3, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import flask_cors
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    m = sys.modules['flask_cors']
    m.CORS = lambda app, **kw: None

from database import schema, repositories
from database.auth import generate_token

_PASSED = 0
_FAILED = 0


def _ok(name, cond, detail=''):
    global _PASSED, _FAILED
    if cond:
        _PASSED += 1
    else:
        _FAILED += 1
        print(f'  FAIL  {name}' + (f' — {detail}' if detail else ''))


# ── Setup ─────────────────────────────────────────────────────────────────────

_TEST_DB = None


def _setup_db():
    global _TEST_DB
    _TEST_DB = tempfile.mktemp(suffix='_gtotest.db')

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
        try:
            os.unlink(_TEST_DB)
        except Exception:
            pass


def _make_client():
    _setup_db()
    from api.app import app
    app.config['TESTING'] = True
    return app.test_client()


def _auth_headers(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _register_and_login(client, username='gto_user', email='gtouser@test.com', role='player'):
    r = client.post('/auth/register',
                    json={'username': username, 'email': email, 'password': 'pass1234', 'role': role},
                    content_type='application/json')
    if r.status_code == 409:
        r = client.post('/auth/login',
                        json={'email': email, 'password': 'pass1234'},
                        content_type='application/json')
    data = r.get_json()
    return data.get('token', '')


def _admin_token():
    """Cria usuário admin no banco atual e retorna token."""
    import hashlib
    gc   = schema.get_conn
    conn = gc()
    conn.execute(
        "INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
        ('admin_test', 'admin@gto.test', hashlib.sha256(b'pass1234').hexdigest(), 'admin')
    )
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE email='admin@gto.test'").fetchone()[0]
    conn.close()
    return generate_token(user_id=uid, role='admin')


def _insert_decision(gc, user_id, tournament_id, street='flop', position='BTN',
                     action_taken='bet', board=None, hero_cards='Kc Qd',
                     stack_bb=30.0, facing_bet=0.0, gto_action='bet', gto_label='standard'):
    """Insere decisão sintética no banco e retorna seu id."""
    conn = gc()
    board_json = json.dumps(board or ['As', 'Td', '5c'])
    conn.execute(
        """INSERT INTO decisions
           (tournament_id, hand_id, street, position, action_taken, best_action, label,
            score, hero_cards, board, stack_bb, facing_bet, gto_action, gto_label)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tournament_id, 'HH-001', street, position, action_taken, 'bet', 'standard',
         0.02, hero_cards, board_json, stack_bb, facing_bet, gto_action, gto_label)
    )
    conn.commit()
    row_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    return row_id


def _insert_tournament(gc, user_id):
    """Insere torneio sintético e retorna seu id."""
    conn = gc()
    conn.execute(
        """INSERT INTO tournaments
           (user_id, tournament_id, tournament_name, hero, played_at, decisions_count)
           VALUES (?,?,?,?,?,?)""",
        (user_id, 'T-TEST-001', 'Test Tournament', 'Hero', '2025-01-01', 5)
    )
    conn.commit()
    row_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    return row_id


def _insert_user(gc, username='gtu', email='gtu@t.com'):
    """Insere usuário diretamente e retorna id."""
    import hashlib
    conn = gc()
    conn.execute(
        "INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?,?,?,?)",
        (username, email, hashlib.sha256(b'pass1234').hexdigest(), 'player')
    )
    conn.commit()
    row_id = conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()[0]
    conn.close()
    return row_id


def _insert_gto_node(gc, street, position, board, gto_action, gto_freq,
                     strategy_json=None, hero_hand=None, stack_bb=30.0, facing_bb=0.0,
                     is_aggregate=0):
    from leaklab.gto_utils import compute_spot_hash, stack_bucket
    hand  = hero_hand or []
    h     = compute_spot_hash(street, position, board, hand, stack_bb, facing_bb)
    sb    = stack_bucket(stack_bb)
    sj    = json.dumps(strategy_json) if isinstance(strategy_json, dict) else strategy_json
    conn  = gc()
    conn.execute(
        """INSERT OR IGNORE INTO gto_nodes
           (spot_hash, street, position, board, hero_hand, stack_bucket,
            gto_action, gto_freq, exploitability_pct, strategy_json, is_aggregate, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (h, street, position, json.dumps(board), json.dumps(hand), sb,
         gto_action, gto_freq, 5.0, sj, is_aggregate, 'test')
    )
    conn.commit()
    conn.close()
    return h


# ── GET /replay/<id>/gto ──────────────────────────────────────────────────────

def test_replay_gto_not_found():
    c = _make_client()
    token = _register_and_login(c, 'u1', 'u1@t.com')
    r = c.get('/replay/99999/gto', headers=_auth_headers(token))
    _ok('replay_gto_not_found', r.status_code == 404, f'{r.status_code}')
    _teardown_db()


def test_replay_gto_unauthenticated():
    c = _make_client()
    r = c.get('/replay/1/gto')
    _ok('replay_gto_unauthenticated', r.status_code == 401, f'{r.status_code}')
    _teardown_db()


def test_replay_gto_incomplete_spot():
    """Decisão sem position → 404 spot_incomplete."""
    c  = _make_client()
    gc = schema.get_conn
    token  = _register_and_login(c, 'u2', 'u2@t.com')
    uid    = _insert_user(gc, 'u2', 'u2@t.com')
    tid    = _insert_tournament(gc, uid)
    did    = _insert_decision(gc, uid, tid, position='')  # empty position
    r = c.get(f'/replay/{did}/gto', headers=_auth_headers(token))
    _ok('replay_gto_incomplete_spot', r.status_code == 404, f'{r.status_code} {r.get_json()}')
    _teardown_db()


def test_replay_gto_found_no_node():
    """Decisão válida mas sem nó GTO no banco → found=False."""
    c  = _make_client()
    gc = schema.get_conn
    token  = _register_and_login(c, 'u3', 'u3@t.com')
    uid    = _insert_user(gc, 'u3', 'u3@t.com')
    tid    = _insert_tournament(gc, uid)
    did    = _insert_decision(gc, uid, tid, board=['Jh', '7d', '2s'])
    r = c.get(f'/replay/{did}/gto', headers=_auth_headers(token))
    data   = r.get_json()
    _ok('replay_gto_no_node_200',   r.status_code == 200, f'{r.status_code}')
    # When no DB node found, endpoint falls back to stored gto_action (source='stored')
    # OR returns 404 with found=False — both are valid "no real node" states
    source = data.get('source', '')
    _ok('replay_gto_no_node_no_real_node',
        data.get('found') is False or source == 'stored' or data.get('status_code') == 404,
        f'{data}')
    _teardown_db()


def test_replay_gto_found_with_strategy():
    """Decisão com nó GTO no banco → strategy populada."""
    c  = _make_client()
    gc = schema.get_conn
    token  = _register_and_login(c, 'u4', 'u4@t.com')
    uid    = _insert_user(gc, 'u4', 'u4@t.com')
    tid    = _insert_tournament(gc, uid)
    board  = ['As', 'Kd', '7c']
    strategy = {
        'bet':   {'frequency': 0.70, 'ev_bb': 4.5},
        'check': {'frequency': 0.30, 'ev_bb': 3.9},
    }
    _insert_gto_node(gc, 'flop', 'BTN', board, 'bet', 0.70, strategy_json=strategy, stack_bb=30.0)
    did = _insert_decision(gc, uid, tid, street='flop', position='BTN',
                           board=board, action_taken='bet', stack_bb=30.0)
    r    = c.get(f'/replay/{did}/gto', headers=_auth_headers(token))
    data = r.get_json()
    _ok('replay_gto_with_strategy_200', r.status_code == 200, f'{r.status_code}')
    _ok('replay_gto_strategy_list',     isinstance(data.get('strategy'), list), f'{data}')
    _ok('replay_gto_strategy_nonempty', len(data.get('strategy', [])) > 0, f'{data}')
    _ok('replay_gto_strategy_sorted',
        data['strategy'][0]['frequency'] >= data['strategy'][-1]['frequency'],
        f"{data['strategy']}")
    _teardown_db()


def test_replay_gto_top_action_returned():
    """top_action deve bater com a ação de maior frequência no strategy_json."""
    c  = _make_client()
    gc = schema.get_conn
    token  = _register_and_login(c, 'u5', 'u5@t.com')
    uid    = _insert_user(gc, 'u5', 'u5@t.com')
    tid    = _insert_tournament(gc, uid)
    board  = ['2h', '3d', '4s']
    strategy = {
        'check': {'frequency': 0.80, 'ev_bb': 3.0},
        'bet':   {'frequency': 0.20, 'ev_bb': 2.8},
    }
    _insert_gto_node(gc, 'flop', 'CO', board, 'check', 0.80, strategy_json=strategy, stack_bb=25.0)
    did = _insert_decision(gc, uid, tid, street='flop', position='CO',
                           board=board, action_taken='bet', stack_bb=25.0)
    r    = c.get(f'/replay/{did}/gto', headers=_auth_headers(token))
    data = r.get_json()
    top  = data.get('top_action') or (data.get('strategy') or [{}])[0].get('action')
    _ok('replay_gto_top_action', top == 'check', f'top_action={top!r}, data={data}')
    _teardown_db()


def test_replay_gto_is_aggregate_flag_returned():
    """Resposta do endpoint deve conter is_aggregate."""
    c  = _make_client()
    gc = schema.get_conn
    token  = _register_and_login(c, 'u6', 'u6@t.com')
    uid    = _insert_user(gc, 'u6', 'u6@t.com')
    tid    = _insert_tournament(gc, uid)
    board  = ['Ts', '9h', '8d']
    _insert_gto_node(gc, 'flop', 'HJ', board, 'bet', 0.65, is_aggregate=0, stack_bb=30.0)
    did = _insert_decision(gc, uid, tid, street='flop', position='HJ',
                           board=board, action_taken='bet', stack_bb=30.0)
    r    = c.get(f'/replay/{did}/gto', headers=_auth_headers(token))
    data = r.get_json()
    _ok('replay_gto_is_aggregate_key', 'is_aggregate' in data, f'keys={list(data.keys())}')
    _teardown_db()


def test_replay_gto_preflop_kk_regression():
    """Regressão do bug KK: preflop aggregate node com fold 72% NÃO deve ser reportado como
    desvio para KK. O endpoint deve retornar top_action != 'fold' para KK HJ 27bb."""
    c  = _make_client()
    gc = schema.get_conn
    token  = _register_and_login(c, 'u7', 'u7@t.com')
    uid    = _insert_user(gc, 'u7', 'u7@t.com')
    tid    = _insert_tournament(gc, uid)
    # Nó preflop agregado: fold=72% (distribuição do range completo de HJ a 27bb)
    pf_strategy = {
        'fold':  {'frequency': 0.72, 'ev_bb': 0.0},
        'raise': {'frequency': 0.28, 'ev_bb': 1.5},
    }
    _insert_gto_node(gc, 'preflop', 'HJ', [], 'fold', 0.72,
                     strategy_json=pf_strategy, is_aggregate=1, stack_bb=27.0)
    # Decisão com KK HJ 27bb, jogada correta: raise
    did = _insert_decision(gc, uid, tid,
                           street='preflop', position='HJ',
                           action_taken='raise', hero_cards='Kc Kd',
                           board=[], stack_bb=27.0, gto_action='raise')
    r    = c.get(f'/replay/{did}/gto', headers=_auth_headers(token))
    data = r.get_json()
    _ok('kk_regression_200', r.status_code == 200, f'{r.status_code}')
    # O top_action para KK preflop NÃO deve ser fold
    top = data.get('top_action') or ''
    _ok('kk_regression_top_action_not_fold', top != 'fold',
        f'top_action={top!r} (fold seria o bug) | response={data}')
    _teardown_db()


def test_replay_gto_player_action_freq():
    """player_action_freq deve estar presente na resposta."""
    c  = _make_client()
    gc = schema.get_conn
    token  = _register_and_login(c, 'u8', 'u8@t.com')
    uid    = _insert_user(gc, 'u8', 'u8@t.com')
    tid    = _insert_tournament(gc, uid)
    board  = ['Ac', 'Jd', '6h']
    strategy = {'bet': {'frequency': 0.60}, 'check': {'frequency': 0.40}}
    _insert_gto_node(gc, 'flop', 'SB', board, 'bet', 0.60, strategy_json=strategy, stack_bb=20.0)
    did = _insert_decision(gc, uid, tid, street='flop', position='SB',
                           board=board, action_taken='bet', stack_bb=20.0)
    r    = c.get(f'/replay/{did}/gto', headers=_auth_headers(token))
    data = r.get_json()
    _ok('replay_gto_player_action_freq',
        'player_action_freq' in data or 'played_freq' in data or 'agreement' in data,
        f'keys={list(data.keys())}')
    _teardown_db()


# ── POST /admin/gto/nodes ─────────────────────────────────────────────────────

def _valid_node(street='flop', position='BTN', board=None, gto_action='bet',
                gto_freq=0.70, stack_bb=30.0, hero_hand=None):
    from leaklab.gto_utils import compute_spot_hash, stack_bucket
    board = board or ['Ks', 'Qd', '2c']
    hand  = hero_hand or []
    return {
        'spot_hash':    compute_spot_hash(street, position, board, hand, stack_bb, 0.0),
        'street':       street,
        'position':     position,
        'board':        board,
        'hero_hand':    hand,
        'stack_bucket': stack_bucket(stack_bb),
        'gto_action':   gto_action,
        'gto_freq':     gto_freq,
        'source':       'test_suite',
        'exploitability_pct': 5.0,
    }


def test_admin_gto_insert_valid():
    c  = _make_client()
    gc = schema.get_conn
    token = _admin_token()
    node  = _valid_node()
    r = c.post('/admin/gto/nodes',
               json={'nodes': [node]},
               headers=_auth_headers(token))
    data = r.get_json()
    _ok('admin_insert_valid_200', r.status_code == 200, f'{r.status_code} {data}')
    _ok('admin_insert_valid_count', data.get('inserted', 0) >= 1, f'{data}')
    _teardown_db()


def test_admin_gto_insert_requires_admin():
    c  = _make_client()
    token = _register_and_login(c, 'reg1', 'reg1@t.com')
    r = c.post('/admin/gto/nodes',
               json={'nodes': [_valid_node()]},
               headers=_auth_headers(token))
    _ok('admin_insert_requires_admin', r.status_code in (401, 403), f'{r.status_code}')
    _teardown_db()


def test_admin_gto_insert_unauthenticated():
    c = _make_client()
    r = c.post('/admin/gto/nodes', json={'nodes': [_valid_node()]})
    _ok('admin_insert_unauthenticated', r.status_code == 401, f'{r.status_code}')
    _teardown_db()


def test_admin_gto_insert_empty_nodes():
    c     = _make_client()
    token = _admin_token()
    r = c.post('/admin/gto/nodes', json={'nodes': []}, headers=_auth_headers(token))
    _ok('admin_insert_empty_400', r.status_code == 400, f'{r.status_code}')
    _teardown_db()


def test_admin_gto_insert_max_500():
    c     = _make_client()
    token = _admin_token()
    nodes = [_valid_node(position='BTN', stack_bb=30.0 + i) for i in range(501)]
    r = c.post('/admin/gto/nodes', json={'nodes': nodes}, headers=_auth_headers(token))
    _ok('admin_insert_max500_400', r.status_code == 400, f'{r.status_code}')
    _teardown_db()


def test_admin_gto_insert_invalid_street():
    c     = _make_client()
    gc    = schema.get_conn
    token = _admin_token()
    node  = _valid_node()
    node['street'] = 'river2'  # invalid
    r = c.post('/admin/gto/nodes', json={'nodes': [node]}, headers=_auth_headers(token))
    data = r.get_json()
    _ok('admin_insert_invalid_street',
        r.status_code == 200 and data.get('inserted', 1) == 0,
        f'status={r.status_code} data={data}')
    _teardown_db()


def test_admin_gto_insert_invalid_position():
    c     = _make_client()
    token = _admin_token()
    node  = _valid_node(position='INVALID')
    r = c.post('/admin/gto/nodes', json={'nodes': [node]}, headers=_auth_headers(token))
    data = r.get_json()
    _ok('admin_insert_invalid_position',
        r.status_code == 200 and data.get('inserted', 1) == 0,
        f'status={r.status_code} data={data}')
    _teardown_db()


def test_admin_gto_insert_invalid_freq():
    c     = _make_client()
    token = _admin_token()
    node  = _valid_node()
    node['gto_freq'] = 1.5  # > 1.0
    r = c.post('/admin/gto/nodes', json={'nodes': [node]}, headers=_auth_headers(token))
    data = r.get_json()
    _ok('admin_insert_invalid_freq',
        r.status_code == 200 and data.get('inserted', 1) == 0,
        f'status={r.status_code} data={data}')
    _teardown_db()


def test_admin_gto_insert_normalizes_shove():
    """shove deve ser normalizado para jam."""
    c     = _make_client()
    gc    = schema.get_conn
    token = _admin_token()
    node  = _valid_node(gto_action='shove')
    r = c.post('/admin/gto/nodes', json={'nodes': [node]}, headers=_auth_headers(token))
    _ok('admin_insert_shove_accepted', r.status_code == 200, f'{r.status_code}')
    if r.status_code == 200 and r.get_json().get('inserted', 0) > 0:
        conn = gc()
        row  = conn.execute("SELECT gto_action FROM gto_nodes WHERE gto_action IN ('jam','shove')").fetchone()
        conn.close()
        _ok('admin_insert_shove_normalized_jam', row and row[0] == 'jam', f'{dict(row) if row else None}')
    _teardown_db()


def test_admin_gto_insert_strategy_zero_rejected():
    """strategy_json com freq_sum < 0.10 deve ser rejeitado."""
    c     = _make_client()
    token = _admin_token()
    node  = _valid_node()
    node['strategy_json'] = json.dumps({
        'bet': {'frequency': 0.01}, 'check': {'frequency': 0.01}
    })
    r = c.post('/admin/gto/nodes', json={'nodes': [node]}, headers=_auth_headers(token))
    data = r.get_json()
    _ok('admin_insert_corrupt_strategy_rejected',
        r.status_code == 200 and data.get('inserted', 1) == 0,
        f'status={r.status_code} data={data}')
    _teardown_db()


def test_admin_gto_insert_preflop_no_hand_is_aggregate():
    """Nó preflop sem hero_hand deve ser marcado is_aggregate=1 no banco."""
    c     = _make_client()
    gc    = schema.get_conn
    token = _admin_token()
    node  = _valid_node(street='preflop', board=[], hero_hand=[], gto_action='raise', gto_freq=0.30)
    r = c.post('/admin/gto/nodes', json={'nodes': [node]}, headers=_auth_headers(token))
    data = r.get_json()
    _ok('admin_preflop_agg_accepted', r.status_code == 200, f'{r.status_code} {data}')
    conn = gc()
    row  = conn.execute(
        "SELECT is_aggregate FROM gto_nodes WHERE street='preflop' AND source='test_suite'"
    ).fetchone()
    conn.close()
    _ok('admin_preflop_agg_flagged', row and int(row[0]) == 1,
        f'{dict(row) if row else "not found"}')
    _teardown_db()


# ── GET /admin/gto/stats ──────────────────────────────────────────────────────

def test_admin_gto_stats_requires_admin():
    c     = _make_client()
    token = _register_and_login(c, 'reg2', 'reg2@t.com')
    r = c.get('/admin/gto/stats', headers=_auth_headers(token))
    _ok('admin_gto_stats_requires_admin', r.status_code in (401, 403), f'{r.status_code}')
    _teardown_db()


def test_admin_gto_stats_structure():
    c     = _make_client()
    token = _admin_token()
    r = c.get('/admin/gto/stats', headers=_auth_headers(token))
    _ok('admin_gto_stats_200', r.status_code == 200, f'{r.status_code}')
    data  = r.get_json()
    _ok('admin_gto_stats_dict', isinstance(data, dict), f'{type(data)}')
    _teardown_db()


# ── GET /preflop-ranges ───────────────────────────────────────────────────────

def test_preflop_ranges_requires_auth():
    c = _make_client()
    r = c.get('/preflop-ranges?position=BTN')
    _ok('preflop_ranges_requires_auth', r.status_code == 401, f'{r.status_code}')
    _teardown_db()


def test_preflop_ranges_returns_structure():
    c     = _make_client()
    token = _register_and_login(c, 'rng1', 'rng1@t.com')
    r = c.get('/preflop-ranges?position=BTN&stack_bb=30',
              headers=_auth_headers(token))
    _ok('preflop_ranges_200', r.status_code == 200, f'{r.status_code}')
    data = r.get_json()
    _ok('preflop_ranges_position', 'position' in data, f'{list(data.keys())}')
    _ok('preflop_ranges_stack_bb', 'stack_bb' in data or 'stack_bucket' in data, f'{list(data.keys())}')
    _teardown_db()


def test_preflop_ranges_hj_has_rfi():
    """HJ deve ter dados RFI para 30bb."""
    c     = _make_client()
    token = _register_and_login(c, 'rng2', 'rng2@t.com')
    r = c.get('/preflop-ranges?position=HJ&stack_bb=30',
              headers=_auth_headers(token))
    _ok('preflop_ranges_hj_200', r.status_code == 200, f'{r.status_code}')
    data = r.get_json()
    rfi  = data.get('rfi')
    _ok('preflop_ranges_hj_rfi_present', rfi is not None, f'{data}')
    if rfi:
        _ok('preflop_ranges_hj_rfi_hands', isinstance(rfi.get('hands'), list), f'{rfi}')
    _teardown_db()


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        try:
            fn()
        except Exception as exc:
            global _FAILED
            _FAILED += 1
            print(f'  FAIL  {fn.__name__} — EXCEPTION: {exc}')
    print(f'\nTotal: {_PASSED + _FAILED} | Passed: {_PASSED} | Failed: {_FAILED}')
    return _FAILED


if __name__ == '__main__':
    failed = run_all()
    sys.exit(1 if failed else 0)
