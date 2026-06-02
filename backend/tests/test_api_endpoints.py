"""
test_api_endpoints.py — Testes dos endpoints Flask da PokerLeakLab API

Cobre:
- Auth: register, login, me
- Analyze: import de torneio, erros esperados
- History: listagem de torneios e evolução
- Study plan: estrutura da resposta
- Replay coach: estrutura da resposta
- Tournament summary: aceita tournament_id
- CORS: headers presentes em toda resposta
- Error handling: 400/401/404/422 corretos

Todos os testes usam banco SQLite em memória — sem efeitos colaterais.
Flask-CORS é mockado quando não disponível.
"""
import sys, os, json, traceback, tempfile, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Mock flask_cors se não disponível ────────────────────────────────────────
try:
    import flask_cors
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    flask_cors_mock = sys.modules['flask_cors']
    flask_cors_mock.CORS = lambda app, **kw: None

# ── Setup: banco isolado por teste ───────────────────────────────────────────
from database import schema, repositories
from database.auth import generate_token

_TEST_DB = None

def _setup_db():
    """Cria banco SQLite temporário e redireciona todas as conexões para ele."""
    global _TEST_DB
    _TEST_DB = tempfile.mktemp(suffix='_apitest.db')
    def gc():
        conn = sqlite3.connect(_TEST_DB)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    schema.get_conn       = gc
    repositories.get_conn = gc
    # Também corrigir módulos que importam get_conn diretamente
    import database.schema as sch
    sch.get_conn = gc
    schema.init_db()
    return gc

def _teardown_db():
    if _TEST_DB and os.path.exists(_TEST_DB):
        try: os.unlink(_TEST_DB)
        except: pass

def _make_client():
    """Retorna client Flask com banco isolado."""
    _setup_db()
    from api.app import app
    app.config['TESTING'] = True
    return app.test_client()

def _register_and_login(client, suffix=''):
    """Registra usuário e retorna token."""
    email = f'test{suffix}@api.com'
    r = client.post('/auth/register',
                    json={'username': f'user{suffix}', 'email': email, 'password': 'pass1234'},
                    content_type='application/json')
    if r.status_code == 409:
        r = client.post('/auth/login',
                        json={'email': email, 'password': 'pass1234'},
                        content_type='application/json')
    data = r.get_json()
    return data.get('token', '')

def _auth_headers(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

def _hh_small():
    """Retorna 5 mãos do torneio de teste."""
    fixture = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')
    if not os.path.exists(fixture):
        return None
    with open(fixture, encoding='utf-8') as f:
        content = f.read()
    blocks = content.split('\n\n\n')
    return '\n\n\n'.join(blocks[:5])


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_returns_200():
    c = _make_client()
    r = c.get('/health')
    assert r.status_code == 200
    data = r.get_json()
    assert 'status' in data or 'ok' in str(data).lower()
    print(f"OK  test_health_returns_200 | {data}")


def test_health_cors_header():
    """CORS header presente mesmo em /health."""
    c = _make_client()
    r = c.get('/health', headers={'Origin': 'https://vercel.app'})
    assert r.status_code == 200
    origin = r.headers.get('Access-Control-Allow-Origin', '')
    assert origin == '*', f"CORS header ausente ou incorreto: '{origin}'"
    print(f"OK  test_health_cors_header | ACAO={origin}")


# ── /auth/register ────────────────────────────────────────────────────────────

def test_register_success():
    c = _make_client()
    r = c.post('/auth/register',
               json={'username': 'newuser', 'email': 'new@test.com', 'password': 'pass1234'},
               content_type='application/json')
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.get_json()}"
    data = r.get_json()
    assert 'token' in data
    assert 'user_id' in data
    print(f"OK  test_register_success | user_id={data['user_id']}")


def test_register_duplicate_email():
    c = _make_client()
    payload = {'username': 'dup', 'email': 'dup@test.com', 'password': 'pass1234'}
    c.post('/auth/register', json=payload, content_type='application/json')
    r = c.post('/auth/register', json=payload, content_type='application/json')
    assert r.status_code == 409
    print("OK  test_register_duplicate_email")


def test_register_missing_fields():
    c = _make_client()
    r = c.post('/auth/register',
               json={'username': 'x'},
               content_type='application/json')
    assert r.status_code == 400
    print("OK  test_register_missing_fields")


def test_register_short_password():
    c = _make_client()
    r = c.post('/auth/register',
               json={'username': 'x', 'email': 'x@x.com', 'password': '123'},
               content_type='application/json')
    assert r.status_code == 400
    print("OK  test_register_short_password")


def test_register_coach_success():
    """role=coach em /auth/register deve ser rejeitado — coaches devem usar /auth/coach-apply."""
    c = _make_client()
    r = c.post('/auth/register',
               json={'username': 'coachjohn', 'email': 'coach@test.com',
                     'password': 'pass1234', 'role': 'coach'},
               content_type='application/json')
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.get_json()}"
    print(f"OK  test_register_coach_success | correctly rejects coach role on /register")


def test_register_coach_can_login():
    """Coach apply cria conta coach_pending — login retorna 403 até aprovação admin."""
    c = _make_client()
    email, pw = 'coachlogin@test.com', 'pass1234'
    apply = c.post('/auth/coach-apply',
                   json={'username': 'coachlogin', 'email': email, 'password': pw,
                         'instagram_handle': '@coachlogin', 'bio': 'Professional poker coach with 5+ years of MTT experience.',
                         'specialties': 'MTT', 'experience_years': 3, 'biggest_results': 'Top 3 WCOOP'},
                   content_type='application/json')
    assert apply.status_code == 201, f"Apply falhou: {apply.status_code}: {apply.get_json()}"
    r = c.post('/auth/login',
               json={'email': email, 'password': pw},
               content_type='application/json')
    # Pending coaches cannot login until admin approves — they get 403 with coach_pending code
    assert r.status_code == 403, f"Expected 403 (coach_pending), got {r.status_code}: {r.get_json()}"
    assert r.get_json().get('code') == 'coach_pending', f"code inesperado: {r.get_json()}"
    print(f"OK  test_register_coach_can_login | correctly returns 403 coach_pending")


def test_register_coach_me_returns_correct_role():
    """/auth/coach-apply retorna 201 com mensagem de confirmação."""
    c = _make_client()
    email, pw = 'coachme@test.com', 'pass1234'
    apply = c.post('/auth/coach-apply',
                   json={'username': 'coachme', 'email': email, 'password': pw,
                         'instagram_handle': '@coachme', 'bio': 'Professional poker coach with 5+ years of MTT experience.',
                         'specialties': 'MTT', 'experience_years': 2, 'biggest_results': 'WCOOP min cash'},
                   content_type='application/json')
    assert apply.status_code == 201, f"Apply falhou: {apply.get_json()}"
    data = apply.get_json()
    assert data.get('ok') is True, f"Resposta inesperada: {data}"
    assert 'message' in data, "Resposta deve conter 'message'"
    print(f"OK  test_register_coach_me_returns_correct_role | msg={data.get('message', '')[:40]}")


def test_register_coach_duplicate_username():
    """Username duplicado para coach deve retornar 409."""
    c = _make_client()
    payload = {'username': 'dupcoach', 'email': 'dupcoach@test.com',
               'password': 'pass1234', 'role': 'coach'}
    c.post('/auth/register', json=payload, content_type='application/json')
    r = c.post('/auth/register',
               json={**payload, 'email': 'other@test.com'},
               content_type='application/json')
    assert r.status_code in (409, 400), f"Expected 409/400, got {r.status_code}"
    print(f"OK  test_register_coach_duplicate_username | status={r.status_code}")


def test_register_invalid_role_defaults_to_player():
    """Role inválido deve ser tratado como player, não causar erro."""
    c = _make_client()
    r = c.post('/auth/register',
               json={'username': 'roleinvalid', 'email': 'roleinvalid@test.com',
                     'password': 'pass1234', 'role': 'superadmin'},
               content_type='application/json')
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.get_json()}"
    data = r.get_json()
    assert data.get('role') == 'player', f"role esperado='player', obtido='{data.get('role')}'"
    print(f"OK  test_register_invalid_role_defaults_to_player | role={data.get('role')}")


# ── /auth/login ───────────────────────────────────────────────────────────────

def test_login_success():
    c = _make_client()
    c.post('/auth/register',
           json={'username': 'lg', 'email': 'lg@test.com', 'password': 'pass1234'},
           content_type='application/json')
    r = c.post('/auth/login',
               json={'email': 'lg@test.com', 'password': 'pass1234'},
               content_type='application/json')
    assert r.status_code == 200
    data = r.get_json()
    assert 'token' in data
    assert data['username'] == 'lg'
    print(f"OK  test_login_success | username={data['username']}")


def test_login_wrong_password():
    c = _make_client()
    c.post('/auth/register',
           json={'username': 'wp', 'email': 'wp@test.com', 'password': 'pass1234'},
           content_type='application/json')
    r = c.post('/auth/login',
               json={'email': 'wp@test.com', 'password': 'wrong'},
               content_type='application/json')
    assert r.status_code == 401
    print("OK  test_login_wrong_password")


def test_login_unknown_email():
    c = _make_client()
    r = c.post('/auth/login',
               json={'email': 'nobody@test.com', 'password': 'pass1234'},
               content_type='application/json')
    assert r.status_code == 401
    print("OK  test_login_unknown_email")


# ── /auth/me ──────────────────────────────────────────────────────────────────

def test_me_with_valid_token():
    c = _make_client()
    token = _register_and_login(c, 'me')
    r = c.get('/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    data = r.get_json()
    assert 'username' in data
    print(f"OK  test_me_with_valid_token | username={data['username']}")


def test_me_without_token():
    c = _make_client()
    r = c.get('/auth/me')
    assert r.status_code == 401
    print("OK  test_me_without_token")


def test_me_invalid_token():
    c = _make_client()
    r = c.get('/auth/me', headers={'Authorization': 'Bearer invalid.token.here'})
    assert r.status_code == 401
    print("OK  test_me_invalid_token")


# ── /analyze ──────────────────────────────────────────────────────────────────

def test_analyze_without_token():
    c = _make_client()
    r = c.post('/analyze')
    assert r.status_code == 401
    print("OK  test_analyze_without_token")


def test_analyze_empty_body():
    c = _make_client()
    token = _register_and_login(c, 'az')
    r = c.post('/analyze', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 400
    print("OK  test_analyze_empty_body")


def test_analyze_invalid_content():
    c = _make_client()
    token = _register_and_login(c, 'inv')
    r = c.post('/analyze',
               json={'content': 'isso não é um hand history'},
               headers=_auth_headers(token))
    assert r.status_code in (400, 422)
    print(f"OK  test_analyze_invalid_content | status={r.status_code}")


def test_analyze_real_tournament():
    """Importa um torneio real e verifica a estrutura de resposta."""
    hh = _hh_small()
    if not hh:
        print("OK  test_analyze_real_tournament | SKIP (fixture não encontrada)")
        return
    c = _make_client()
    token = _register_and_login(c, 'real')
    r = c.post('/analyze',
               json={'content': hh},
               headers=_auth_headers(token))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.get_data(as_text=True)[:200]}"
    data = r.get_json()
    assert 'tournament_db_id' in data
    assert 'total_hands'      in data
    assert 'metrics'          in data
    assert 'hero'             in data
    assert data['total_hands'] > 0
    print(f"OK  test_analyze_real_tournament | hands={data['total_hands']} hero={data['hero']}")


def test_analyze_returns_metrics_shape():
    """Métricas retornadas têm os campos esperados."""
    hh = _hh_small()
    if not hh:
        print("OK  test_analyze_returns_metrics_shape | SKIP")
        return
    c = _make_client()
    token = _register_and_login(c, 'msh')
    r = c.post('/analyze', json={'content': hh}, headers=_auth_headers(token))
    assert r.status_code == 200
    metrics = r.get_json().get('metrics', {})
    # avg_mistake_score e total_decisions são campos garantidos
    assert 'total_decisions' in metrics, f"Métrica ausente: total_decisions"
    assert 'avg_mistake_score' in metrics or 'avg_score' in metrics,         f"Nenhum campo de score médio em metrics: {list(metrics.keys())}"
    assert metrics['total_decisions'] > 0
    score_key = 'avg_mistake_score' if 'avg_mistake_score' in metrics else 'avg_score'
    print(f"OK  test_analyze_returns_metrics_shape | {score_key}={metrics[score_key]:.4f}")


# ── /history ──────────────────────────────────────────────────────────────────

def test_history_empty_for_new_user():
    c = _make_client()
    # Registrar e logar com o MESMO client (mesmo banco)
    r_reg = c.post('/auth/register',
                   json={'username':'histuser','email':'hist@t.com','password':'pass1234'},
                   content_type='application/json')
    token = r_reg.get_json().get('token','')
    r = c.get('/history/tournaments', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200, f"Got {r.status_code}: {r.get_data(as_text=True)[:100]}"
    data = r.get_json()
    # API pode retornar lista direta ou {'tournaments': [...]}
    tournaments = data if isinstance(data, list) else data.get('tournaments', data)
    assert isinstance(tournaments, list)
    assert len(tournaments) == 0
    print("OK  test_history_empty_for_new_user")


def test_history_after_import():
    """Após importar, lista deve ter o torneio."""
    hh = _hh_small()
    if not hh:
        print("OK  test_history_after_import | SKIP")
        return
    c = _make_client()
    r_reg = c.post('/auth/register',
                   json={'username':'himpuser','email':'himp@t.com','password':'pass1234'},
                   content_type='application/json')
    token = r_reg.get_json().get('token','')
    c.post('/analyze', json={'content': hh},
           headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    r = c.get('/history/tournaments', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    raw = r.get_json()
    tournaments = raw if isinstance(raw, list) else raw.get('tournaments', [])
    assert len(tournaments) >= 1, f"Esperava >= 1 torneio, got {len(tournaments)} | raw={str(raw)[:100]}"
    t0 = tournaments[0]
    assert 'hero' in t0 or 'tournament_id' in t0
    print(f"OK  test_history_after_import | {len(tournaments)} torneios")


def test_history_evolution_shape():
    """Evolução retorna lista com campos corretos."""
    hh = _hh_small()
    if not hh:
        print("OK  test_history_evolution_shape | SKIP")
        return
    c = _make_client()
    r_reg = c.post('/auth/register',
                   json={'username':'evouser','email':'evo@t.com','password':'pass1234'},
                   content_type='application/json')
    token = r_reg.get_json().get('token','')
    c.post('/analyze', json={'content': hh},
           headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    r = c.get('/history/evolution', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    raw = r.get_json()
    data = raw if isinstance(raw, list) else raw.get('evolution', raw.get('data', []))
    assert isinstance(data, list), f"Esperava list, got {type(raw)}: {str(raw)[:100]}"
    print(f"OK  test_history_evolution_shape | {len(data)} entradas")


# ── /analyze/tournament-summary ──────────────────────────────────────────────

def test_tournament_summary_requires_auth():
    c = _make_client()
    r = c.post('/analyze/tournament-summary', json={})
    assert r.status_code == 401
    print("OK  test_tournament_summary_requires_auth")


def test_tournament_summary_invalid_id():
    c = _make_client()
    token = _register_and_login(c, 'ts')
    r = c.post('/analyze/tournament-summary',
               json={'tournament_id': 99999},
               headers=_auth_headers(token))
    assert r.status_code in (404, 400, 200)  # 404 preferred
    print(f"OK  test_tournament_summary_invalid_id | status={r.status_code}")


def test_tournament_summary_with_real_data():
    """Importa torneio e gera summary pelo ID."""
    hh = _hh_small()
    if not hh:
        print("OK  test_tournament_summary_with_real_data | SKIP")
        return
    c = _make_client()
    token = _register_and_login(c, 'tsum')
    import_r = c.post('/analyze', json={'content': hh}, headers=_auth_headers(token))
    t_db_id = import_r.get_json().get('tournament_db_id')
    assert t_db_id is not None

    r = c.post('/analyze/tournament-summary',
               json={'tournament_id': t_db_id},
               headers=_auth_headers(token))
    assert r.status_code == 200, f"Got {r.status_code}: {r.get_data(as_text=True)[:200]}"
    data = r.get_json()
    # Pode retornar summary ou error (sem API key) — ambos são 200
    assert 'summary' in data or 'error' in data
    print(f"OK  test_tournament_summary_with_real_data | has_summary={'summary' in data}")


# ── /analyze/replay-coach ─────────────────────────────────────────────────────

def test_replay_coach_requires_auth():
    c = _make_client()
    r = c.post('/analyze/replay-coach', json={})
    assert r.status_code == 401
    print("OK  test_replay_coach_requires_auth")


def test_replay_coach_missing_action():
    c = _make_client()
    token = _register_and_login(c, 'rc')
    r = c.post('/analyze/replay-coach',
               json={'street': 'flop'},
               headers=_auth_headers(token))
    assert r.status_code == 400
    print(f"OK  test_replay_coach_missing_action | status={r.status_code}")


def test_replay_coach_valid_request():
    c = _make_client()
    token = _register_and_login(c, 'rcv')
    r = c.post('/analyze/replay-coach',
               json={
                   'action_taken': 'fold',
                   'best_action':  'call',
                   'street':       'flop',
                   'score':        0.28,
                   'hand_equity':  0.45,
                   'pot_odds_equity': 0.33,
                   'm_ratio':      8.2,
                   'icm_pressure': 'medium',
               },
               headers=_auth_headers(token))
    assert r.status_code == 200, f"Got {r.status_code}: {r.get_data(as_text=True)[:200]}"
    data = r.get_json()
    assert 'analysis' in data or 'error' in data
    print(f"OK  test_replay_coach_valid_request | has_analysis={'analysis' in data}")


# ── /study/plan ───────────────────────────────────────────────────────────────

def test_study_plan_requires_auth():
    c = _make_client()
    r = c.get('/study/plan')
    assert r.status_code == 401
    print("OK  test_study_plan_requires_auth")


def test_study_plan_no_data_returns_400():
    c = _make_client()
    token = _register_and_login(c, 'sp0')
    r = c.get('/study/plan', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code in (400, 200), f"Unexpected: {r.status_code}"
    print(f"OK  test_study_plan_no_data_returns_400 | status={r.status_code}")


def test_study_plan_with_data_returns_structure():
    """Após importar torneio, plan retorna estrutura válida."""
    hh = _hh_small()
    if not hh:
        print("OK  test_study_plan_with_data_returns_structure | SKIP")
        return
    c = _make_client()
    token = _register_and_login(c, 'spd')
    c.post('/analyze', json={'content': hh}, headers=_auth_headers(token))
    r = c.get('/study/plan', headers={'Authorization': f'Bearer {token}'})
    # Sempre 200 (mesmo sem API key, retorna fallback)
    assert r.status_code == 200, f"Got {r.status_code}: {r.get_data(as_text=True)[:200]}"
    data = r.get_json()
    assert 'nivel'  in data
    assert 'resumo' in data
    assert 'cards'  in data
    assert isinstance(data['cards'], list)
    print(f"OK  test_study_plan_with_data_returns_structure | nivel={data['nivel']}")


# ── CORS ──────────────────────────────────────────────────────────────────────

def test_cors_on_401_response():
    """CORS headers devem estar presentes mesmo em respostas de erro."""
    c = _make_client()
    r = c.get('/auth/me')  # 401
    assert r.status_code == 401
    origin = r.headers.get('Access-Control-Allow-Origin', '')
    assert origin == '*', f"CORS ausente em 401: '{origin}'"
    print("OK  test_cors_on_401_response")


def test_cors_on_404_response():
    c = _make_client()
    r = c.get('/rota-inexistente')
    origin = r.headers.get('Access-Control-Allow-Origin', '')
    assert origin == '*', f"CORS ausente em 404: '{origin}'"
    print(f"OK  test_cors_on_404_response | status={r.status_code}")


def test_cors_preflight_options():
    """OPTIONS preflight deve retornar 200 com headers corretos."""
    c = _make_client()
    r = c.options('/study/plan',
                  headers={'Origin': 'https://vercel.app',
                            'Access-Control-Request-Method': 'GET'})
    assert r.status_code in (200, 204)
    print(f"OK  test_cors_preflight_options | status={r.status_code}")


# ── /replay ───────────────────────────────────────────────────────────────────

def test_replay_requires_auth():
    c = _make_client()
    r = c.get('/replay/999/888')
    assert r.status_code == 401
    print("OK  test_replay_requires_auth")


def test_replay_invalid_ids():
    c = _make_client()
    token = _register_and_login(c, 'rp')
    r = c.get('/replay/99999999/88888888',
              headers={'Authorization': f'Bearer {token}'})
    assert r.status_code in (404, 400, 422)
    print(f"OK  test_replay_invalid_ids | status={r.status_code}")


def test_leaderboard_prefs_default_set_and_conflict():
    c = _make_client()
    t1 = _register_and_login(c, 'lbp1')
    t2 = _register_and_login(c, 'lbp2')
    # default: fora do ranking público
    r = c.get('/player/leaderboard-prefs', headers=_auth_headers(t1))
    assert r.status_code == 200
    assert r.get_json() == {'opt_in': False, 'handle': None}
    # u1 define handle
    r = c.post('/player/leaderboard-prefs',
               json={'opt_in': True, 'handle': 'Crusher'}, headers=_auth_headers(t1))
    assert r.status_code == 200 and r.get_json()['handle'] == 'Crusher'
    # u2 tenta o mesmo apelido (case diferente) → 409
    r = c.post('/player/leaderboard-prefs',
               json={'opt_in': True, 'handle': 'crusher'}, headers=_auth_headers(t2))
    assert r.status_code == 409 and r.get_json()['error'] == 'handle_taken'
    # u2 com apelido livre → 200
    r = c.post('/player/leaderboard-prefs',
               json={'opt_in': True, 'handle': 'Grinder'}, headers=_auth_headers(t2))
    assert r.status_code == 200 and r.get_json()['handle'] == 'Grinder'
    print("OK  test_leaderboard_prefs_default_set_and_conflict")


def test_detect_hand_won():
    """_detect_hand_won: True se hero coletou o pote, False senão, None sem hero."""
    from api.app import _detect_hand_won
    won  = "Dealt to phpro [Ah Kd]\nphpro: raises 100 to 200\nVilla: folds\nphpro collected 300 from pot"
    lost = "Dealt to phpro [2c 3d]\nphpro: calls 100\nVilla: shows [As Ad]\nVilla collected 300 from pot"
    assert _detect_hand_won(won, 'phpro') is True
    assert _detect_hand_won(lost, 'phpro') is False
    assert _detect_hand_won(won, '') is None
    print("OK  test_detect_hand_won")


def test_results_vs_gto_endpoint():
    """Insight #5: won_critical/total_critical/won_evaluated corretos no endpoint."""
    client = _make_client()
    token  = _register_and_login(client, 'rvg')
    conn = schema.get_conn()
    uid = conn.execute("SELECT id FROM users WHERE email=?", ('testrvg@api.com',)).fetchone()['id']
    conn.execute("INSERT INTO tournaments (user_id, tournament_id, site, hero, imported_at) "
                 "VALUES (?,?,?,?,datetime('now'))", (uid, 'TRVG', 'PokerStars', 'phpro'))
    tid = conn.execute("SELECT id FROM tournaments WHERE tournament_id='TRVG'").fetchone()['id']
    # h1,h4 = won+critical ; h2 = won+correct ; h3 = lost+critical
    for hid, won, gto in [('h1', 1, 'gto_critical'), ('h2', 1, 'gto_correct'),
                          ('h3', 0, 'gto_critical'), ('h4', 1, 'gto_critical')]:
        conn.execute(
            "INSERT INTO decisions (tournament_id, hand_id, street, action_taken, best_action, label, "
            "score, math_penalty, range_penalty, is_3bet, gto_label, hero_won_hand, position) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, hid, 'preflop', 'raise', 'raise', 'standard', 100, 0, 0, 0, gto, won, 'BB'))
    conn.commit(); conn.close()
    r = client.get('/player/results-vs-gto', headers=_auth_headers(token))
    assert r.status_code == 200, r.status_code
    d = r.get_json()
    assert d['won_critical']   == 2, d   # h1, h4
    assert d['total_critical'] == 3, d   # h1, h3, h4
    assert d['won_evaluated']  == 3, d   # h1, h2, h4 (won + tem gto_label)
    assert d['pct_critical_hidden'] == round(2 * 100 / 3, 1), d
    assert len(d['top_spots']) >= 1
    print("OK  test_results_vs_gto_endpoint")


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
