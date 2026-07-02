"""
Win-back de inativos: elegibilidade por estágio (7/21/45d), cooldown, opt-out,
verificação e reset por atividade. DB SQLite temporário isolado; SMTP mockado.
"""
import sys, os, tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo
sch.init_db()

import leaklab.email_digest as ed
_SENT = []
ed.send_transactional_email = lambda to, subject, html: (_SENT.append((to, subject)) or True)


def _mk(name, days_ago, *, verified=1, opt_in=1, stage=0, sent_days_ago=None):
    uid = repo.create_user(name, f"{name}@test.com", "pass1234", email_verified=verified)
    ts = (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
    conn = repo.get_conn()
    conn.execute("UPDATE users SET last_login=?, email_opt_in=?, winback_stage=? WHERE id=?",
                 (ts, opt_in, stage, uid))
    if sent_days_ago is not None:
        sts = (datetime.utcnow() - timedelta(days=sent_days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE users SET winback_sent_at=? WHERE id=?", (sts, uid))
    conn.commit(); conn.close()
    return uid


def _in_preview(res, uid, email):
    return any(p['email'] == email for p in res.get('preview', []))


def test_active_user_not_targeted():
    _mk('wb_active', 0)
    res = ed.run_winback(dry_run=True)
    assert not _in_preview(res, None, 'wb_active@test.com'), res
    print("OK  test_active_user_not_targeted")


def test_stage1_due_at_8_days():
    _mk('wb_s1', 8, stage=0)
    res = ed.run_winback(dry_run=True)
    p = [x for x in res['preview'] if x['email'] == 'wb_s1@test.com']
    assert p and p[0]['next_stage'] == 1, res
    print("OK  test_stage1_due_at_8_days")


def test_not_due_before_threshold():
    # 10 dias inativo mas já no estágio 1 → próximo (estágio 2) só aos 21 dias
    _mk('wb_early', 10, stage=1, sent_days_ago=8)
    res = ed.run_winback(dry_run=True)
    assert not _in_preview(res, None, 'wb_early@test.com'), res
    print("OK  test_not_due_before_threshold")


def test_optout_and_unverified_excluded():
    _mk('wb_optout', 30, opt_in=0)
    _mk('wb_unver', 30, verified=0)
    res = ed.run_winback(dry_run=True)
    assert not _in_preview(res, None, 'wb_optout@test.com'), "opt-out deveria ser excluído"
    assert not _in_preview(res, None, 'wb_unver@test.com'), "não verificado deveria ser excluído"
    print("OK  test_optout_and_unverified_excluded")


def test_cooldown_blocks_recent_send():
    # inativo 30d, estágio 1, mas enviou há 3 dias (< cooldown 7) → bloqueado
    _mk('wb_cool', 30, stage=1, sent_days_ago=3)
    res = ed.run_winback(dry_run=True)
    assert not _in_preview(res, None, 'wb_cool@test.com'), res
    print("OK  test_cooldown_blocks_recent_send")


def test_exhausted_stage3_stops():
    _mk('wb_done', 90, stage=3, sent_days_ago=30)
    res = ed.run_winback(dry_run=True)
    assert not _in_preview(res, None, 'wb_done@test.com'), "estágio 3 esgotado não recebe mais"
    print("OK  test_exhausted_stage3_stops")


def test_real_send_marks_stage_and_touch_resets():
    uid = _mk('wb_real', 9, stage=0)
    _SENT.clear()
    res = ed.run_winback(dry_run=False, limit=50)
    assert res['sent'] >= 1 and any(s[0] == 'wb_real@test.com' for s in _SENT), res
    u = repo.get_user_by_email('wb_real@test.com')
    assert int(u['winback_stage']) == 1 and u['winback_sent_at'], u
    # atividade reseta o ciclo
    repo.touch_activity(uid)
    u2 = repo.get_user_by_email('wb_real@test.com')
    assert int(u2['winback_stage']) == 0 and not u2['winback_sent_at'], u2
    print("OK  test_real_send_marks_stage_and_touch_resets")


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
    try: os.unlink(os.environ['LEAKLAB_DB'])
    except Exception: pass
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
