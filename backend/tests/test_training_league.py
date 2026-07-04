"""
Liga de Treino (#32): agrega esforço da semana (training_daily), ranqueia por acertos
(NÃO por ELO), reusa opt-in/handle do #15, e o viewer sempre vê `me`.
"""
import sys, os, tempfile
from datetime import datetime, timedelta

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
from leaklab.leaderboard import rank_training_league, public_view
client = A.app.test_client()

_TODAY = datetime.utcnow().date()
_MONDAY = (_TODAY - timedelta(days=_TODAY.weekday())).strftime('%Y-%m-%d')


def _seed_training(user_id, day, spots, correct):
    conn = repo.get_conn()
    try:
        conn.execute(repo._adapt(
            "INSERT INTO training_daily (user_id, day, spots, correct, claimed) VALUES (?,?,?,?,'')"
        ), (user_id, day, spots, correct))
        conn.commit()
    finally:
        conn.close()


def test_rank_by_effort_not_skill():
    """Ordena por points (acertos) desc, spots desc — ELO não entra."""
    players = [
        {"user_id": 1, "username": "a", "opt_in": True, "points": 5, "spots": 8, "streak": 2},
        {"user_id": 2, "username": "b", "opt_in": True, "points": 9, "spots": 10, "streak": 5},
        {"user_id": 3, "username": "c", "opt_in": True, "points": 0, "spots": 3, "streak": 0},
    ]
    res = rank_training_league(players)
    assert [p["user_id"] for p in res["ranked"]] == [2, 1], res["ranked"]
    assert res["ranked"][0]["rank"] == 1
    assert [p["user_id"] for p in res["ineligible"]] == [3]  # 0 acertos → treine pra entrar
    print("OK  test_rank_by_effort_not_skill")


def test_get_training_league_aggregates_week():
    u1 = repo.create_user('tl1', 'tl1@test.com', 'pass1234', 'player')
    u2 = repo.create_user('tl2', 'tl2@test.com', 'pass1234', 'player')
    repo.set_leaderboard_prefs(u1, True, 'sharky')
    repo.set_leaderboard_prefs(u2, True, None)
    # u1 treina 2 dias na semana; u2 um dia
    _seed_training(u1, _MONDAY, spots=6, correct=4)
    _seed_training(u1, (_TODAY).strftime('%Y-%m-%d'), spots=3, correct=3)
    _seed_training(u2, _MONDAY, spots=10, correct=7)
    sunday = (_TODAY - timedelta(days=_TODAY.weekday()) + timedelta(days=6)).strftime('%Y-%m-%d')
    players = {p['user_id']: p for p in repo.get_training_league(_MONDAY, sunday)}
    assert players[u1]['points'] == 7 and players[u1]['spots'] == 9, players[u1]  # 4+3, 6+3
    assert players[u2]['points'] == 7 and players[u2]['spots'] == 10, players[u2]
    print("OK  test_get_training_league_aggregates_week")


def test_endpoint_me_always_present():
    uid = repo.create_user('tl3', 'tl3@test.com', 'pass1234', 'player')  # não treinou
    tok = generate_token(uid, 'player')
    r = client.get('/metrics/training-league', headers={'Authorization': f'Bearer {tok}'})
    assert r.status_code == 200, (r.status_code, r.get_json())
    j = r.get_json()
    assert 'ranked' in j and j['me'] is not None
    assert j['me']['rank'] is None and j['me']['points'] == 0  # sem treino → sem rank, mas vê a linha
    assert j['week_start'] == _MONDAY
    print("OK  test_endpoint_me_always_present")


def test_opt_out_hidden_but_self_sees():
    uid = repo.create_user('tl4', 'tl4@test.com', 'pass1234', 'player')
    repo.set_leaderboard_prefs(uid, False, None)  # fora do público
    _seed_training(uid, _MONDAY, spots=5, correct=5)
    tok = generate_token(uid, 'player')
    j = client.get('/metrics/training-league', headers={'Authorization': f'Bearer {tok}'}).get_json()
    # não aparece na lista pública (opt-out), mas se vê em `me` com o score real
    assert all(row.get('user_id') != uid for row in j['ranked'])
    assert j['me']['points'] == 5 and j['me']['rank'] is None
    print("OK  test_opt_out_hidden_but_self_sees")


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
