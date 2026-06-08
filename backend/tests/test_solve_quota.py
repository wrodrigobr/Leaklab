"""
Testa a cota de solves on-demand (#26): can_request_solve / increment_solves /
get_quota_status + reset mensal. DB isolado (LEAKLAB_DB temp) — subprocesso próprio.
"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name

from database.schema import init_db, get_conn
from database.repositories import (can_request_solve, increment_solves, get_quota_status,
                                   PLAN_LIMITS)
init_db()


def _mk_user(plan='free'):
    c = get_conn()
    c.execute("DELETE FROM users")
    c.execute("INSERT INTO users (username,email,password_hash,plan) VALUES (?,?,?,?)",
              ('squ', 'squ@t', 'x', plan))
    uid = dict(c.execute("SELECT id FROM users WHERE username='squ'").fetchone())['id']
    c.commit(); c.close()
    return uid


def test_free_limit_blocks():
    lim = PLAN_LIMITS['free']['solves']
    assert lim and lim > 0
    uid = _mk_user('free')
    for i in range(lim):
        allowed, rem = can_request_solve(uid)
        assert allowed, f"devia permitir o solve {i} (rem={rem})"
        increment_solves(uid)
    allowed, rem = can_request_solve(uid)
    assert allowed is False and rem == 0
    assert get_quota_status(uid)['solves_used'] == lim
    print(f"OK  test_free_limit_blocks (free={lim})")


def test_pro_monthly_unlimited_daily_capped():
    # Fase 2: Pro é ilimitado no MÊS, mas tem teto DIÁRIO de 20 solves (fair-use anti-abuso).
    uid = _mk_user('pro')
    for _ in range(5):
        increment_solves(uid)
    allowed, rem = can_request_solve(uid)
    assert allowed is True and rem == 15     # 20/dia − 5 usados
    for _ in range(15):
        increment_solves(uid)
    allowed, rem = can_request_solve(uid)
    assert allowed is False and rem == 0     # 20/20 no dia → bloqueia
    print("OK  test_pro_monthly_unlimited_daily_capped")


def test_monthly_reset_zeroes_solves():
    uid = _mk_user('free')
    increment_solves(uid); increment_solves(uid)
    assert get_quota_status(uid)['solves_used'] == 2
    # força o mês anterior no quota_reset_at → próximo acesso reseta
    c = get_conn()
    c.execute("UPDATE users SET quota_reset_at='2000-01-01' WHERE id=?", (uid,))
    c.commit(); c.close()
    allowed, rem = can_request_solve(uid)   # dispara _maybe_reset_quota
    assert get_quota_status(uid)['solves_used'] == 0
    assert allowed is True
    print("OK  test_monthly_reset_zeroes_solves")


def test_status_exposes_solves():
    uid = _mk_user('free')
    qs = get_quota_status(uid)
    assert 'solves_used' in qs and qs['limits'].get('solves') == PLAN_LIMITS['free']['solves']
    print("OK  test_status_exposes_solves")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    try:
        os.unlink(_TMPDB.name)
    except Exception:
        pass
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
