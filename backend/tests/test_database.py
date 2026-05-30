"""
Testes da camada de persistência — schema, repositories e auth.
"""
import sys, os, traceback, tempfile, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Usar banco em memória para testes
TEST_DB = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo

def _setup():
    sch.DB_PATH  = TEST_DB
    repo.DB_PATH = TEST_DB
    def get_conn_test():
        conn = sqlite3.connect(TEST_DB)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    sch.get_conn  = get_conn_test
    repo.get_conn = get_conn_test
    sch.init_db()

_setup()

def _clean():
    """Limpar dados entre testes."""
    conn = sch.get_conn()
    conn.execute('DELETE FROM decisions')
    conn.execute('DELETE FROM tournaments')
    conn.execute('DELETE FROM users')
    conn.commit()
    conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────

def test_init_db_creates_tables():
    conn = sch.get_conn()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert 'users'       in tables
    assert 'tournaments' in tables
    assert 'decisions'   in tables
    print("OK  test_init_db_creates_tables")


# ── Users ─────────────────────────────────────────────────────────────────────

def test_create_user():
    _clean()
    uid = repo.create_user('player1', 'p1@test.com', 'pass123')
    assert isinstance(uid, int) and uid > 0
    print(f"OK  test_create_user | id={uid}")


def test_verify_password_correct():
    _clean()
    repo.create_user('player2', 'p2@test.com', 'mypassword')
    user = repo.verify_password('p2@test.com', 'mypassword')
    assert user is not None
    assert user['username'] == 'player2'
    print("OK  test_verify_password_correct")


def test_verify_password_wrong():
    _clean()
    repo.create_user('player3', 'p3@test.com', 'correct')
    user = repo.verify_password('p3@test.com', 'wrong')
    assert user is None
    print("OK  test_verify_password_wrong")


def test_get_user_by_email():
    _clean()
    repo.create_user('player4', 'p4@test.com', 'pass')
    user = repo.get_user_by_email('p4@test.com')
    assert user is not None and user['email'] == 'p4@test.com'
    print("OK  test_get_user_by_email")


def test_duplicate_email_raises():
    _clean()
    repo.create_user('p5a', 'p5@test.com', 'pass')
    try:
        repo.create_user('p5b', 'p5@test.com', 'pass')
        assert False, "Deveria ter lançado erro"
    except Exception:
        pass
    print("OK  test_duplicate_email_raises")


def test_coach_student_relationship():
    _clean()
    coach_id = repo.create_user('coach1', 'coach@test.com', 'pass', role='coach')
    s1 = repo.create_user('student1', 's1@test.com', 'pass', role='player', coach_id=coach_id)
    s2 = repo.create_user('student2', 's2@test.com', 'pass', role='player', coach_id=coach_id)
    students = repo.get_students(coach_id)
    assert len(students) == 2
    print(f"OK  test_coach_student_relationship | {len(students)} alunos")


# ── Tournaments ───────────────────────────────────────────────────────────────

def _metrics():
    return {
        'total_hands': 400, 'total_decisions': 485,
        'avg_mistake_score': 0.0721,
        'label_pct': {'standard':79.8,'marginal':4.9,'small_mistake':6.4,'clear_mistake':8.5},
    }

def test_save_and_get_tournament():
    _clean()
    uid = repo.create_user('u1', 'u1@t.com', 'p')
    t_id = repo.save_tournament(uid, 'T001', 'phpro', _metrics(), 'pokerstars', '2025-07-22')
    assert t_id > 0
    tournaments = repo.get_tournaments(uid)
    assert len(tournaments) == 1
    assert tournaments[0]['tournament_id'] == 'T001'
    assert abs(tournaments[0]['avg_score'] - 0.0721) < 0.001
    print(f"OK  test_save_and_get_tournament | id={t_id}")


def test_tournament_upsert():
    _clean()
    uid = repo.create_user('u2', 'u2@t.com', 'p')
    t1 = repo.save_tournament(uid, 'T002', 'phpro', _metrics())
    t2 = repo.save_tournament(uid, 'T002', 'phpro', {**_metrics(), 'avg_mistake_score': 0.05})
    assert t1 == t2  # mesmo ID — upsert
    t = repo.get_tournament(uid, 'T002')
    assert abs(t['avg_score'] - 0.05) < 0.001
    print("OK  test_tournament_upsert")


def test_save_and_get_decisions():
    _clean()
    uid = repo.create_user('u3', 'u3@t.com', 'p')
    t_id = repo.save_tournament(uid, 'T003', 'phpro', _metrics())
    decisions = [
        {'handId':'H1','street':'preflop','actionTaken':'fold','bestAction':'fold',
         'hero_cards':'AsKh','board':[],'draw_profile':'none',
         'evaluation':{'label':'standard','mistakeScore':.05,'scoreBreakdown':{'mathPenalty':0,'rangePenalty':0}},
         'context':{'icmPressure':'low','mRatio':12.0,'heroStackBb':30.0}},
        {'handId':'H1','street':'flop','actionTaken':'call','bestAction':'fold',
         'hero_cards':'AsKh','board':['Kc','7d','2h'],'draw_profile':'none',
         'evaluation':{'label':'clear_mistake','mistakeScore':.55,'scoreBreakdown':{'mathPenalty':.28,'rangePenalty':.08}},
         'context':{'icmPressure':'medium','mRatio':9.5,'heroStackBb':22.0}},
    ]
    repo.save_decisions(t_id, decisions)
    saved = repo.get_decisions(t_id)
    assert len(saved) == 2
    assert saved[0]['label'] == 'standard'
    assert saved[1]['label'] == 'clear_mistake'
    print(f"OK  test_save_and_get_decisions | {len(saved)} decisões")


def test_decisions_cleared_on_reimport():
    _clean()
    uid = repo.create_user('u4', 'u4@t.com', 'p')
    t_id = repo.save_tournament(uid, 'T004', 'phpro', _metrics())
    d = {'handId':'H1','street':'preflop','actionTaken':'fold','bestAction':'fold',
         'hero_cards':'AsKh','board':[],'draw_profile':'',
         'evaluation':{'label':'standard','mistakeScore':.05,'scoreBreakdown':{'mathPenalty':0,'rangePenalty':0}},
         'context':{'icmPressure':'low','mRatio':12.0,'heroStackBb':30.0}}
    repo.save_decisions(t_id, [d, d])
    repo.save_decisions(t_id, [d])  # reimportar com menos decisões
    saved = repo.get_decisions(t_id)
    assert len(saved) == 1  # deve ter limpado e salvo só 1
    print("OK  test_decisions_cleared_on_reimport")


# ── Auth JWT ──────────────────────────────────────────────────────────────────

def test_jwt_generate_and_decode():
    from database.auth import generate_token, decode_token
    token = generate_token(42, 'player')
    payload = decode_token(token)
    assert payload is not None
    assert payload['user_id'] == 42
    assert payload['role'] == 'player'
    print("OK  test_jwt_generate_and_decode")


def test_jwt_invalid_token():
    from database.auth import decode_token
    result = decode_token('not.a.valid.token')
    assert result is None
    print("OK  test_jwt_invalid_token")


# ── Evolution queries ──────────────────────────────────────────────────────────

def test_evolution_metrics_empty():
    _clean()
    uid = repo.create_user('u5', 'u5@t.com', 'p')
    evo = repo.get_evolution_metrics(uid, 30)
    assert isinstance(evo, list)
    print("OK  test_evolution_metrics_empty")


def test_leak_summary_requires_2_occurrences():
    _clean()
    uid = repo.create_user('u6', 'u6@t.com', 'p')
    t_id = repo.save_tournament(uid, 'T005', 'phpro', _metrics())
    # Só 1 decisão de erro — não deve aparecer no leak summary
    d = {'handId':'H1','street':'turn','actionTaken':'call','bestAction':'fold',
         'hero_cards':'AsKh','board':[],'draw_profile':'',
         'evaluation':{'label':'clear_mistake','mistakeScore':.55,'scoreBreakdown':{'mathPenalty':.28,'rangePenalty':0}},
         'context':{'icmPressure':'medium','mRatio':8.0,'heroStackBb':20.0}}
    repo.save_decisions(t_id, [d])
    leaks = repo.get_leak_summary(uid, 30)
    assert len(leaks) == 0  # só 1 ocorrência, mínimo é 2
    print("OK  test_leak_summary_requires_2_occurrences")


def test_update_llm_summary():
    _clean()
    uid  = repo.create_user('u7', 'u7@t.com', 'p')
    t_id = repo.save_tournament(uid, 'T006', 'phpro', _metrics())
    repo.update_llm_summary(t_id, 'Resumo gerado pelo LLM.')
    t = repo.get_tournament(uid, 'T006')
    assert t['llm_summary'] == 'Resumo gerado pelo LLM.'
    print("OK  test_update_llm_summary")


def test_leaderboard_prefs_default_and_roundtrip():
    # Default: fora do ranking público (opt-in é consentido, não automático).
    _clean()
    uid = repo.create_user('lbprefs', 'lbprefs@t.com', 'p')
    assert repo.get_leaderboard_prefs(uid) == {"opt_in": False, "handle": None}
    # Liga opt-in com handle → persiste e sanitiza (trim).
    repo.set_leaderboard_prefs(uid, True, "  shark_river  ")
    p = repo.get_leaderboard_prefs(uid)
    assert p["opt_in"] is True and p["handle"] == "shark_river"
    # Handle vazio → NULL (cai pro username quando opta por participar).
    repo.set_leaderboard_prefs(uid, True, "   ")
    assert repo.get_leaderboard_prefs(uid) == {"opt_in": True, "handle": None}
    # Desliga.
    repo.set_leaderboard_prefs(uid, False, None)
    assert repo.get_leaderboard_prefs(uid)["opt_in"] is False
    print("OK  test_leaderboard_prefs_default_and_roundtrip")


def test_leaderboard_handle_unique_case_insensitive():
    _clean()
    a = repo.create_user('lbA', 'lba@t.com', 'p')
    b = repo.create_user('lbB', 'lbb@t.com', 'p')
    repo.set_leaderboard_prefs(a, True, "Shark")
    # b tenta o mesmo apelido com case diferente → bloqueado
    try:
        repo.set_leaderboard_prefs(b, True, "shark")
        assert False, "deveria ter levantado handle_taken"
    except ValueError as e:
        assert str(e) == "handle_taken"
    # b não ficou com o handle e a manteve o dele
    assert repo.get_leaderboard_prefs(b)["handle"] is None
    assert repo.get_leaderboard_prefs(a)["handle"] == "Shark"
    # a pode re-salvar o próprio handle (mesmo case) sem conflito consigo mesmo
    repo.set_leaderboard_prefs(a, True, "Shark")
    assert repo.get_leaderboard_prefs(a)["handle"] == "Shark"
    # b com apelido livre funciona
    repo.set_leaderboard_prefs(b, True, "Whale")
    assert repo.get_leaderboard_prefs(b)["handle"] == "Whale"
    print("OK  test_leaderboard_handle_unique_case_insensitive")


if __name__ == '__main__':
    tests = [(k,v) for k,v in sorted(globals().items()) if k.startswith('test_')]
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
    # Limpar banco de teste
    try: os.unlink(TEST_DB)
    except: pass
