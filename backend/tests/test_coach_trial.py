"""COACH-02 — Pro de cortesia do coach: trial de 3 meses ao aprovar, meta de 15
indicados pagantes, promoção p/ 'coach_earned', expiração (downgrade), status e MRR."""
import sys, os, tempfile, sqlite3, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TEST_DB = tempfile.mktemp(suffix='_coachtrial.db')
import database.schema as sch
import database.repositories as repo


def _setup():
    if os.path.exists(TEST_DB):
        os.unlink(TEST_DB)
    sch.DB_PATH = repo.DB_PATH = TEST_DB
    def gc():
        conn = sqlite3.connect(TEST_DB, timeout=10); conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON'); conn.execute('PRAGMA busy_timeout=10000'); return conn
    sch.get_conn = repo.get_conn = gc
    sch.init_db()


_setup()


def _clean():
    conn = sch.get_conn()
    for t in ('decisions', 'tournaments', 'coach_invites', 'coach_applications', 'coach_profiles', 'users'):
        conn.execute(f'DELETE FROM {t}')
    conn.commit(); conn.close()


def _approve_new_coach(suffix='1'):
    """Cria coach_pending + application e aprova → devolve o user_id do coach."""
    uid = repo.create_user(f'coach{suffix}', f'coach{suffix}@t.com', 'pass', role='coach_pending')
    repo.create_coach_application(uid, '@ig', 'bio', 'mtt', 5, 'results')
    app_id = [a for a in repo.get_coach_applications('pending') if a['user_id'] == uid][0]['id']
    repo.approve_coach_application(app_id)
    return uid


def _make_paying_referred(coach_id, n):
    """Cria n alunos indicados+aprovados+pro vinculados ao coach.

    Cria os usuários primeiro (cada um na sua conexão), só depois abre UMA conexão
    para os UPDATEs — nunca segura uma conexão com transação aberta enquanto chama
    create_user (isso causaria deadlock de write-lock entre as duas conexões)."""
    base = repo.get_coach_paying_referred_count(coach_id)  # evita colisão de username entre chamadas
    sids = [repo.create_user(f'stu{coach_id}_{base + i}', f'stu{coach_id}_{base + i}@t.com', 'pass', role='player')
            for i in range(n)]
    conn = sch.get_conn()
    for sid in sids:
        # invite resgatado (id fictício basta ser NOT NULL — usa o próprio sid)
        conn.execute("UPDATE users SET coach_id=?, invited_via_invite_id=?, link_status='approved', plan='pro' "
                     "WHERE id=?", (coach_id, sid, sid))
    conn.commit(); conn.close()


def _set_trial_end(coach_id, when):
    conn = sch.get_conn()
    conn.execute("UPDATE users SET coach_trial_ends_at=? WHERE id=?", (when, coach_id))
    conn.commit(); conn.close()


def test_approval_grants_trial():
    _clean()
    cid = _approve_new_coach()
    conn = sch.get_conn()
    u = conn.execute("SELECT role, plan, plan_source, coach_trial_ends_at FROM users WHERE id=?", (cid,)).fetchone()
    conn.close()
    assert u['role'] == 'coach' and u['plan'] == 'pro' and u['plan_source'] == 'coach_trial'
    assert u['coach_trial_ends_at'] is not None
    # ~90 dias à frente
    ends = datetime.datetime.strptime(u['coach_trial_ends_at'], '%Y-%m-%d %H:%M:%S')
    delta = (ends - datetime.datetime.utcnow()).days
    assert 88 <= delta <= 90, delta
    print("OK  test_approval_grants_trial")


def test_paying_referred_count():
    _clean()
    cid = _approve_new_coach()
    _make_paying_referred(cid, 3)
    # ruído: 1 indicado pendente + 1 indicado free não contam
    conn = sch.get_conn()
    p = repo.create_user('pend', 'pend@t.com', 'pass'); f = repo.create_user('fr', 'fr@t.com', 'pass')
    conn.execute("UPDATE users SET coach_id=?, invited_via_invite_id=?, link_status='pending', plan='pro' WHERE id=?", (cid, p, p))
    conn.execute("UPDATE users SET coach_id=?, invited_via_invite_id=?, link_status='approved', plan='free' WHERE id=?", (cid, f, f))
    conn.commit(); conn.close()
    assert repo.get_coach_paying_referred_count(cid) == 3
    print("OK  test_paying_referred_count")


def test_promote_to_earned_at_target():
    _clean()
    cid = _approve_new_coach()
    _make_paying_referred(cid, 14)
    assert repo.maybe_promote_coach_earned(cid) is False   # 14 < 15
    _make_paying_referred_one_more = _make_paying_referred(cid, 1)  # agora 15
    assert repo.maybe_promote_coach_earned(cid) is True
    conn = sch.get_conn()
    assert conn.execute("SELECT plan_source FROM users WHERE id=?", (cid,)).fetchone()['plan_source'] == 'coach_earned'
    conn.close()
    # idempotente
    assert repo.maybe_promote_coach_earned(cid) is False
    print("OK  test_promote_to_earned_at_target")


def test_approve_link_request_can_promote():
    """Aprovar o 15º indicado pagante pendente fecha a meta e trava o Pro."""
    _clean()
    cid = _approve_new_coach()
    _make_paying_referred(cid, 14)
    # 15º entra pendente + pro
    conn = sch.get_conn()
    sid = repo.create_user('s15', 's15@t.com', 'pass')
    conn.execute("UPDATE users SET coach_id=?, invited_via_invite_id=?, link_status='pending', plan='pro' WHERE id=?", (cid, sid, sid))
    conn.commit(); conn.close()
    assert repo.maybe_promote_coach_earned(cid) is False     # ainda 14 aprovados
    assert repo.approve_link_request(cid, sid) is True       # vira 15 → promove
    conn = sch.get_conn()
    assert conn.execute("SELECT plan_source FROM users WHERE id=?", (cid,)).fetchone()['plan_source'] == 'coach_earned'
    conn.close()
    print("OK  test_approve_link_request_can_promote")


def test_expire_downgrades_below_target():
    _clean()
    cid = _approve_new_coach()
    _make_paying_referred(cid, 5)                    # < 15
    _set_trial_end(cid, '2000-01-01 00:00:00')       # vencido
    res = repo.expire_coach_trials()
    assert cid in res['downgraded'] and cid not in res['promoted']
    conn = sch.get_conn()
    u = conn.execute("SELECT plan, plan_source, coach_trial_ends_at FROM users WHERE id=?", (cid,)).fetchone()
    conn.close()
    assert u['plan'] == 'free' and u['plan_source'] is None and u['coach_trial_ends_at'] is None
    print("OK  test_expire_downgrades_below_target")


def test_expire_keeps_pro_at_target():
    _clean()
    cid = _approve_new_coach()
    _make_paying_referred(cid, 15)
    _set_trial_end(cid, '2000-01-01 00:00:00')       # vencido mas bateu a meta
    res = repo.expire_coach_trials()
    assert cid in res['promoted'] and cid not in res['downgraded']
    conn = sch.get_conn()
    u = conn.execute("SELECT plan, plan_source FROM users WHERE id=?", (cid,)).fetchone()
    conn.close()
    assert u['plan'] == 'pro' and u['plan_source'] == 'coach_earned'
    print("OK  test_expire_keeps_pro_at_target")


def test_expire_ignores_active_trial():
    _clean()
    cid = _approve_new_coach()                        # trial +90d (não vencido)
    res = repo.expire_coach_trials()
    assert cid not in res['promoted'] and cid not in res['downgraded']
    conn = sch.get_conn()
    assert conn.execute("SELECT plan_source FROM users WHERE id=?", (cid,)).fetchone()['plan_source'] == 'coach_trial'
    conn.close()
    print("OK  test_expire_ignores_active_trial")


def test_trial_status_fields():
    _clean()
    cid = _approve_new_coach()
    _make_paying_referred(cid, 4)
    st = repo.get_coach_trial_status(cid)
    assert st['is_pro'] and st['on_trial'] and not st['earned']
    assert st['paying_referred'] == 4 and st['target'] == 15
    assert st['days_left'] is not None and 0 <= st['days_left'] <= 90
    print("OK  test_trial_status_fields")


def test_mrr_excludes_coach_perk():
    """O Pro de cortesia do coach (trial/earned) não entra no MRR."""
    _clean()
    cid = _approve_new_coach()                         # pro de cortesia (trial)
    # 2 alunos pagantes de verdade (plan pro, sem plan_source de perk)
    repo.update_user_plan(repo.create_user('pa', 'pa@t.com', 'pass'), 'pro')
    repo.update_user_plan(repo.create_user('pb', 'pb@t.com', 'pass'), 'pro')
    stats = repo.get_admin_dashboard_stats()
    # coach conta em 'plans' como pro, mas o MRR só vê os 2 pagantes reais
    assert stats['mrr_cents'] == 2 * 9900, stats
    print("OK  test_mrr_excludes_coach_perk")


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
