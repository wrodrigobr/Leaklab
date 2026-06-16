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
    for t in ('decisions', 'tournaments', 'coach_invites', 'coach_profiles', 'users'):
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


def _make_pro_active(student_id):
    import datetime
    conn = sch.get_conn()
    conn.execute("UPDATE users SET plan='pro' WHERE id=?", (student_id,))
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("INSERT INTO tournaments (user_id, tournament_id, site, hero, imported_at) VALUES (?,?,?,?,?)",
                 (student_id, f'T{student_id}', 'PokerStars', 'hero', now))
    conn.commit(); conn.close()


def test_comp_counts_only_referred_active():
    """A comp conta só INDICADO via convite (invited_via_invite_id) + pro + import 30d.
    Aluno legado (coach_id setado sem convite) NÃO conta, mesmo pro+ativo."""
    _clean()
    coach = _coach(); s_ref = _student('ref'); s_leg = _student('leg')
    # legado: vinculado direto (sem convite)
    conn = sch.get_conn(); conn.execute("UPDATE users SET coach_id=? WHERE id=?", (coach, s_leg)); conn.commit(); conn.close()
    # indicado: resgata convite (entra pendente na fase 2) e o coach aprova
    assert repo.redeem_coach_invite(s_ref, repo.create_coach_invite(coach)['code'])['ok']
    assert repo.approve_link_request(coach, s_ref) is True
    _make_pro_active(s_ref); _make_pro_active(s_leg)
    summ = repo.get_coach_finance_summary(coach)
    assert summ['total_students'] == 2
    assert summ['referred_count'] == 1, summ          # só o resgatado é indicado
    assert summ['active_students'] == 1, summ         # só o indicado+aprovado+ativo conta na comp
    print("OK  test_comp_counts_only_referred_active")


def test_redeem_enters_pending_and_blocks_comp():
    """SEC-01 fase 2: o resgate entra PENDENTE — não conta na comp até o coach aprovar."""
    _clean()
    coach = _coach(); stud = _student()
    res = repo.redeem_coach_invite(stud, repo.create_coach_invite(coach)['code'])
    assert res['ok'] and res.get('pending') is True
    conn = sch.get_conn()
    ls = conn.execute("SELECT link_status FROM users WHERE id=?", (stud,)).fetchone()['link_status']
    conn.close()
    assert ls == 'pending', ls
    # aparece na fila de aprovação do coach
    reqs = repo.list_pending_link_requests(coach)
    assert len(reqs) == 1 and reqs[0]['student_id'] == stud
    # pendente + pro + ativo ainda NÃO conta na comp
    _make_pro_active(stud)
    assert repo.get_coach_finance_summary(coach)['active_students'] == 0
    print("OK  test_redeem_enters_pending_and_blocks_comp")


def test_approve_link_request():
    _clean()
    coach = _coach(); stud = _student()
    repo.redeem_coach_invite(stud, repo.create_coach_invite(coach)['code'])
    assert repo.approve_link_request(coach, stud) is True
    conn = sch.get_conn()
    u = conn.execute("SELECT coach_id, link_status FROM users WHERE id=?", (stud,)).fetchone()
    conn.close()
    assert u['link_status'] == 'approved' and u['coach_id'] == coach
    assert repo.list_pending_link_requests(coach) == []
    # idempotente: aprovar de novo (já approved) → False
    assert repo.approve_link_request(coach, stud) is False
    print("OK  test_approve_link_request")


def test_reject_link_request_unlinks():
    _clean()
    coach = _coach(); stud = _student()
    repo.redeem_coach_invite(stud, repo.create_coach_invite(coach)['code'])
    assert repo.reject_link_request(coach, stud) is True
    conn = sch.get_conn()
    u = conn.execute("SELECT coach_id, invited_via_invite_id, link_status FROM users WHERE id=?", (stud,)).fetchone()
    conn.close()
    assert u['coach_id'] is None and u['invited_via_invite_id'] is None and u['link_status'] == 'rejected'
    assert repo.list_pending_link_requests(coach) == []
    print("OK  test_reject_link_request_unlinks")


def test_approve_reject_scoped_to_coach():
    """Um coach não aprova/rejeita vínculo pendente de outro coach."""
    _clean()
    c1 = _coach('1'); c2 = _coach('2'); stud = _student()
    repo.redeem_coach_invite(stud, repo.create_coach_invite(c1)['code'])
    assert repo.approve_link_request(c2, stud) is False
    assert repo.reject_link_request(c2, stud) is False
    # segue pendente sob c1
    assert len(repo.list_pending_link_requests(c1)) == 1
    print("OK  test_approve_reject_scoped_to_coach")


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
