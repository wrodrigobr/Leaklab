"""SEC-01 — convites single-use do coach: criar/listar/revogar/resgatar, uso único,
expiração, limite de alunos, atribuição de indicação (invited_via_invite_id)."""
import sys, os, tempfile, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TEST_DB = tempfile.mktemp(suffix='_invites.db')
import database.schema as sch
import database.repositories as repo


def _setup():
    if os.path.exists(TEST_DB):
        os.unlink(TEST_DB)
    sch.DB_PATH = repo.DB_PATH = TEST_DB
    def gc():
        conn = sqlite3.connect(TEST_DB); conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON'); return conn
    sch.get_conn = repo.get_conn = gc
    sch.init_db()


_setup()


def _coach(s='1'):
    return repo.create_user(f'coach{s}', f'coach{s}@t.com', 'pass', role='coach')


def _student(s='1'):
    return repo.create_user(f'student{s}', f's{s}@t.com', 'pass', role='player')


def _clean():
    conn = sch.get_conn()
    for t in ('coach_invites', 'coach_profiles', 'users'):
        conn.execute(f'DELETE FROM {t}')
    conn.commit(); conn.close()


def test_create_list_redeem_flow():
    _clean()
    coach = _coach(); stud = _student()
    inv = repo.create_coach_invite(coach, label='João')
    assert inv['code'].startswith('INV-') and inv['status'] == 'active'
    lst = repo.list_coach_invites(coach)
    assert len(lst) == 1 and lst[0]['label'] == 'João'
    res = repo.redeem_coach_invite(stud, inv['code'])
    assert res['ok'] and res['coach']['id'] == coach
    # estado pós-resgate
    conn = sch.get_conn()
    u = conn.execute("SELECT coach_id, invited_via_invite_id, invited_by_key FROM users WHERE id=?", (stud,)).fetchone()
    ci = conn.execute("SELECT status, used_by FROM coach_invites WHERE id=?", (inv['id'],)).fetchone()
    conn.close()
    assert u['coach_id'] == coach and u['invited_via_invite_id'] == inv['id']
    assert ci['status'] == 'redeemed' and ci['used_by'] == stud
    print("OK  test_create_list_redeem_flow")


def test_double_redeem_fails():
    _clean()
    coach = _coach(); s1 = _student('1'); s2 = _student('2')
    inv = repo.create_coach_invite(coach)
    assert repo.redeem_coach_invite(s1, inv['code'])['ok']
    r2 = repo.redeem_coach_invite(s2, inv['code'])
    assert not r2['ok'] and 'utilizado' in r2['error']
    print("OK  test_double_redeem_fails")


def test_revoked_and_invalid():
    _clean()
    coach = _coach(); stud = _student()
    inv = repo.create_coach_invite(coach)
    assert repo.revoke_coach_invite(coach, inv['id']) is True
    assert not repo.redeem_coach_invite(stud, inv['code'])['ok']
    assert not repo.redeem_coach_invite(stud, 'INV-NOPE')['ok']
    # revogar de novo (já revogado) → False
    assert repo.revoke_coach_invite(coach, inv['id']) is False
    print("OK  test_revoked_and_invalid")


def test_expired():
    _clean()
    coach = _coach(); stud = _student()
    inv = repo.create_coach_invite(coach)
    conn = sch.get_conn()
    conn.execute("UPDATE coach_invites SET expires_at='2000-01-01 00:00:00' WHERE id=?", (inv['id'],))
    conn.commit()
    # list deriva 'expired' on-read
    assert repo.list_coach_invites(coach)[0]['status'] == 'expired'
    conn.close()
    r = repo.redeem_coach_invite(stud, inv['code'])
    assert not r['ok'] and 'expirado' in r['error']
    print("OK  test_expired")


def test_self_redeem_blocked():
    _clean()
    coach = _coach()
    inv = repo.create_coach_invite(coach)
    r = repo.redeem_coach_invite(coach, inv['code'])
    assert not r['ok'] and 'próprio' in r['error']
    print("OK  test_self_redeem_blocked")


def test_max_students_guard():
    _clean()
    coach = _coach()
    conn = sch.get_conn()
    conn.execute("INSERT INTO coach_profiles (user_id, max_students) VALUES (?, 1)", (coach,))
    conn.commit(); conn.close()
    s1 = _student('1'); s2 = _student('2')
    assert repo.redeem_coach_invite(s1, repo.create_coach_invite(coach)['code'])['ok']
    inv2 = repo.create_coach_invite(coach)
    r = repo.redeem_coach_invite(s2, inv2['code'])
    assert not r['ok'] and 'limite' in r['error']
    # convite NÃO foi consumido (segue active)
    assert [i for i in repo.list_coach_invites(coach) if i['id'] == inv2['id']][0]['status'] == 'active'
    print("OK  test_max_students_guard")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}"); failed += 1
            import traceback; traceback.print_exc()
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
