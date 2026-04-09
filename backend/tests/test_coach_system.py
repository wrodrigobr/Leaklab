"""
Testes do sistema de coaches — chave de convite, perfil, impacto, recomendações.
"""
import sys, os, traceback, tempfile, sqlite3, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TEST_DB = tempfile.mktemp(suffix='_coach.db')

import database.schema as sch
import database.repositories as repo

def _setup():
    # Remover banco anterior para garantir schema limpo
    if os.path.exists(TEST_DB):
        os.unlink(TEST_DB)
    sch.DB_PATH = repo.DB_PATH = TEST_DB
    def gc():
        conn = sqlite3.connect(TEST_DB)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    sch.get_conn = repo.get_conn = gc
    sch.init_db()

_setup()

def _clean():
    conn = sch.get_conn()
    conn.execute('DELETE FROM decisions')
    conn.execute('DELETE FROM tournaments')
    conn.execute('DELETE FROM coach_profiles')
    conn.execute('DELETE FROM users')
    conn.commit()
    conn.close()

def _coach(suffix='1'):
    return repo.create_user(f'coach{suffix}', f'coach{suffix}@t.com', 'pass', role='coach')

def _student(suffix='1', coach_id=None):
    return repo.create_user(f'student{suffix}', f's{suffix}@t.com', 'pass',
                            role='player', coach_id=coach_id)

def _metrics():
    return {'total_hands':100,'total_decisions':120,'avg_mistake_score':.08,
            'label_pct':{'standard':75,'marginal':10,'small_mistake':10,'clear_mistake':5}}


# ── Chave de convite ──────────────────────────────────────────────────────────

def test_generate_invite_key_format():
    _clean()
    cid = _coach()
    key = repo.assign_invite_key(cid)
    assert key.startswith('COACH-'), f"Formato errado: {key}"
    assert len(key) == 12  # COACH- (6) + 6 hex uppercase
    print(f"OK  test_generate_invite_key_format | key={key}")


def test_invite_key_idempotent():
    _clean()
    cid = _coach()
    k1 = repo.assign_invite_key(cid)
    k2 = repo.assign_invite_key(cid)
    assert k1 == k2
    print("OK  test_invite_key_idempotent")


def test_invite_key_unique_per_coach():
    _clean()
    c1 = _coach('1'); c2 = _coach('2')
    k1 = repo.assign_invite_key(c1)
    k2 = repo.assign_invite_key(c2)
    assert k1 != k2
    print("OK  test_invite_key_unique_per_coach")


def test_get_coach_by_invite_key():
    _clean()
    cid = _coach()
    key = repo.assign_invite_key(cid)
    coach = repo.get_coach_by_invite_key(key)
    assert coach is not None
    assert coach['id'] == cid
    print("OK  test_get_coach_by_invite_key")


def test_get_coach_invalid_key():
    result = repo.get_coach_by_invite_key('INVALID-KEY')
    assert result is None
    print("OK  test_get_coach_invalid_key")


# ── Vínculo aluno/coach ───────────────────────────────────────────────────────

def test_link_student_to_coach():
    _clean()
    cid = _coach(); sid = _student()
    key = repo.assign_invite_key(cid)
    # Criar perfil do coach para definir limite
    repo.upsert_coach_profile(cid, max_students=10)
    result = repo.link_student_to_coach(sid, key)
    assert result['ok'], result.get('error')
    # Verificar vínculo no banco
    students = repo.get_students(cid)
    assert any(s['id'] == sid for s in students)
    print("OK  test_link_student_to_coach")


def test_link_student_invalid_key():
    _clean()
    sid = _student()
    result = repo.link_student_to_coach(sid, 'COACH-ZZZZZZ')
    assert not result['ok']
    assert 'inválida' in result['error'].lower()
    print("OK  test_link_student_invalid_key")


def test_link_student_self_link_blocked():
    _clean()
    cid = _coach()
    key = repo.assign_invite_key(cid)
    result = repo.link_student_to_coach(cid, key)
    assert not result['ok']
    print("OK  test_link_student_self_link_blocked")


def test_link_student_max_limit():
    _clean()
    cid = _coach()
    key = repo.assign_invite_key(cid)
    repo.upsert_coach_profile(cid, max_students=2)
    # Vincular 2 alunos (ok)
    s1 = _student('limit1'); s2 = _student('limit2'); s3 = _student('limit3')
    r1 = repo.link_student_to_coach(s1, key)
    r2 = repo.link_student_to_coach(s2, key)
    assert r1['ok'] and r2['ok']
    # Terceiro deve falhar
    r3 = repo.link_student_to_coach(s3, key)
    assert not r3['ok']
    assert 'limite' in r3['error'].lower()
    print("OK  test_link_student_max_limit")


# ── Perfil do coach ───────────────────────────────────────────────────────────

def test_upsert_coach_profile():
    _clean()
    cid = _coach()
    profile = repo.upsert_coach_profile(
        cid, display_name='Coach Pro', bio='Especialista em MTT',
        specialties=['preflop', 'icm', 'turn'], is_public=True
    )
    assert profile['display_name'] == 'Coach Pro'
    assert 'preflop' in profile['specialties']
    assert profile['is_public'] == 1
    print("OK  test_upsert_coach_profile")


def test_coach_profile_update():
    _clean()
    cid = _coach()
    repo.upsert_coach_profile(cid, display_name='Nome Antigo', specialties=['preflop'])
    repo.upsert_coach_profile(cid, display_name='Nome Novo', specialties=['turn','river'])
    profile = repo.get_coach_profile(cid)
    assert profile['display_name'] == 'Nome Novo'
    assert 'turn' in profile['specialties']
    print("OK  test_coach_profile_update")


def test_get_public_coaches():
    _clean()
    c1 = _coach('pub1'); c2 = _coach('pub2'); c3 = _coach('priv')
    repo.upsert_coach_profile(c1, display_name='Coach A', specialties=['preflop'], is_public=True)
    repo.upsert_coach_profile(c2, display_name='Coach B', specialties=['turn'], is_public=True)
    repo.upsert_coach_profile(c3, display_name='Coach C', is_public=False)
    coaches = repo.get_public_coaches()
    ids = [c['user_id'] for c in coaches]
    assert c1 in ids and c2 in ids
    assert c3 not in ids  # privado
    print(f"OK  test_get_public_coaches | {len(coaches)} coaches públicos")


def test_get_public_coaches_by_specialty():
    _clean()
    c1 = _coach('sp1'); c2 = _coach('sp2')
    repo.upsert_coach_profile(c1, specialties=['preflop','icm'], is_public=True)
    repo.upsert_coach_profile(c2, specialties=['turn','river'], is_public=True)
    filtered = repo.get_public_coaches(specialty='preflop')
    assert any(c['user_id'] == c1 for c in filtered)
    assert not any(c['user_id'] == c2 for c in filtered)
    print("OK  test_get_public_coaches_by_specialty")


# ── Impacto do coach ──────────────────────────────────────────────────────────

def test_coach_impact_no_students():
    _clean()
    cid = _coach()
    impact = repo.get_coach_impact_metrics(cid, 30)
    assert impact['students'] == []
    print("OK  test_coach_impact_no_students")


def test_coach_impact_with_students():
    _clean()
    cid = _coach()
    s1 = _student('imp1', coach_id=cid)
    s2 = _student('imp2', coach_id=cid)
    # Salvar torneios para os alunos
    t1 = repo.save_tournament(s1, 'T_IMP1', 'player', _metrics())
    t2 = repo.save_tournament(s2, 'T_IMP2', 'player',
                               {**_metrics(), 'avg_mistake_score': .12})
    impact = repo.get_coach_impact_metrics(cid, 30)
    assert impact['summary']['total_students'] == 2
    assert impact['summary']['active_students'] == 2
    print(f"OK  test_coach_impact_with_students | {impact['summary']}")


# ── Recomendação de coaches ───────────────────────────────────────────────────

def test_recommend_coaches_empty_base():
    _clean()
    sid = _student()
    coaches = repo.recommend_coaches_for_leaks(sid)
    assert isinstance(coaches, list)
    print("OK  test_recommend_coaches_empty_base")


def test_recommend_coaches_by_leak():
    _clean()
    # Coach especialista em turn
    cid = _coach()
    repo.upsert_coach_profile(cid, specialties=['turn', 'icm'], is_public=True)
    # Aluno com leak no turn
    sid = _student()
    tid = repo.save_tournament(sid, 'REC_T', 'hero', _metrics())
    conn = sch.get_conn()
    conn.execute("""INSERT INTO decisions
        (tournament_id, hand_id, street, hero_cards, board, action_taken, best_action,
         label, score, math_penalty, range_penalty)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (tid,'H1','turn','AsKh','[]','call','fold','clear_mistake',.55,.28,.08))
    conn.execute("""INSERT INTO decisions
        (tournament_id, hand_id, street, hero_cards, board, action_taken, best_action,
         label, score, math_penalty, range_penalty)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (tid,'H2','turn','JsQh','[]','call','fold','small_mistake',.30,.10,.05))
    conn.commit(); conn.close()

    coaches = repo.recommend_coaches_for_leaks(sid)
    # O coach de turn deve aparecer
    assert any(c['user_id'] == cid for c in coaches), \
        f"Coach de turn não recomendado. Coaches: {coaches}"
    print(f"OK  test_recommend_coaches_by_leak | {len(coaches)} recomendados")


# ── API endpoints ─────────────────────────────────────────────────────────────

def test_api_invite_key_endpoint():
    from api.app import app
    app.config['TESTING'] = True
    from database.auth import generate_token
    _clean()
    cid = _coach('api')
    token = generate_token(cid, 'coach')
    c = app.test_client()
    r = c.get('/coach/invite-key', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    data = r.get_json()
    assert 'invite_key' in data
    assert data['invite_key'].startswith('COACH-')
    print(f"OK  test_api_invite_key_endpoint | key={data['invite_key']}")


def test_api_link_student():
    from api.app import app
    from database.auth import generate_token
    _clean()
    cid = _coach('lnk'); sid = _student('lnk')
    repo.upsert_coach_profile(cid, max_students=10)
    key = repo.assign_invite_key(cid)
    token = generate_token(sid, 'player')
    c = app.test_client()
    r = c.post('/student/link-coach',
               json={'invite_key': key},
               headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    data = r.get_json()
    assert 'coach' in data
    print(f"OK  test_api_link_student | coach={data['coach']['username']}")


def test_api_public_coaches():
    from api.app import app
    _clean()
    cid = _coach('pub')
    repo.upsert_coach_profile(cid, display_name='Public Coach', is_public=True)
    c = app.test_client()
    r = c.get('/coaches')  # sem auth
    assert r.status_code == 200
    data = r.get_json()
    assert 'coaches' in data
    print(f"OK  test_api_public_coaches | {len(data['coaches'])} coaches")


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
    try: os.unlink(TEST_DB)
    except: pass
