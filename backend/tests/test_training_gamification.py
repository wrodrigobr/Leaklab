"""Gamificação de treino (Fase 1) — domínio por categoria (eixo SEPARADO do ELO).

Valida a matemática do mastery (EMA × fator de volume), os tiers, o delta antes→depois
e a listagem. DB isolado (LEAKLAB_DB temp).
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
from database.repositories import (
    record_training_attempt, get_training_skills, _mastery_tier, get_all_achievements,
)
init_db()


def _mk_user():
    c = get_conn()
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM training_skill_progress")
    c.execute("INSERT INTO users (username,email,password_hash,plan) VALUES (?,?,?,?)",
              ('tg', 'tg@t', 'x', 'free'))
    uid = dict(c.execute("SELECT id FROM users WHERE username='tg'").fetchone())['id']
    c.commit(); c.close()
    return uid


def test_tier_boundaries():
    assert _mastery_tier(0) == 'bronze'
    assert _mastery_tier(39.9) == 'bronze'
    assert _mastery_tier(40) == 'silver'
    assert _mastery_tier(69.9) == 'silver'
    assert _mastery_tier(70) == 'gold'
    assert _mastery_tier(89.9) == 'gold'
    assert _mastery_tier(90) == 'diamond'
    print("OK  test_tier_boundaries")


def test_first_attempt_low_mastery_volume_gated():
    """1 acerto não vira Ouro: o fator de volume (1/20) segura — exige reps."""
    uid = _mk_user()
    r = record_training_attempt(uid, 'rfi:BB::50', True)
    assert r['attempts'] == 1 and r['correct'] == 1
    assert abs(r['mastery'] - 5.0) < 0.01, r          # ema=1 × 1/20 × 100
    assert r['tier'] == 'bronze'
    assert r['mastery_prev'] == 0.0 and r['mastery_delta'] == 5.0
    print("OK  test_first_attempt_low_mastery_volume_gated")


def test_sustained_correct_reaches_diamond():
    """20 acertos seguidos → volume satura (1.0) + ema=1 → mastery 100 → diamante."""
    uid = _mk_user()
    last = None
    for _ in range(20):
        last = record_training_attempt(uid, 'rfi:BB::50', True)
    assert last['attempts'] == 20
    assert abs(last['mastery'] - 100.0) < 0.01, last
    assert last['tier'] == 'diamond'
    print("OK  test_sustained_correct_reaches_diamond")


def test_wrong_attempt_lowers_mastery():
    uid = _mk_user()
    for _ in range(20):
        record_training_attempt(uid, 'rfi:BB::50', True)
    before = get_training_skills(uid)[0]['mastery']
    after = record_training_attempt(uid, 'rfi:BB::50', False)
    assert after['mastery'] < before, (before, after['mastery'])
    assert after['mastery_delta'] < 0
    print("OK  test_wrong_attempt_lowers_mastery")


def test_get_training_skills_lists_categories():
    uid = _mk_user()
    record_training_attempt(uid, 'rfi:BB::50', True)
    record_training_attempt(uid, 'pf:bb_defense', True)
    skills = get_training_skills(uid)
    keys = {s['category_key'] for s in skills}
    assert keys == {'rfi:BB::50', 'pf:bb_defense'}, skills
    assert all('tier' in s and 'mastery' in s for s in skills)
    print("OK  test_get_training_skills_lists_categories")


def test_isolation_by_category():
    """Acertar uma categoria não move o domínio de outra."""
    uid = _mk_user()
    record_training_attempt(uid, 'rfi:BB::50', True)
    r2 = record_training_attempt(uid, 'pf:bb_defense', True)
    assert r2['attempts'] == 1, r2   # categoria nova começa do zero
    print("OK  test_isolation_by_category")


def test_all_achievements_path_locked_then_unlocked():
    """Catálogo completo de conquistas: tudo travado no início; ao ganhar uma, vira unlocked."""
    uid = _mk_user()
    allac = get_all_achievements(uid)
    assert len(allac) > 0 and all(not a['unlocked'] for a in allac), "tudo travado no início"
    key = allac[0]['key']
    c = get_conn()
    c.execute("INSERT INTO achievements (user_id, achievement_key, earned_at) VALUES (?,?,datetime('now'))",
              (uid, key))
    c.commit(); c.close()
    allac2 = get_all_achievements(uid)
    unlocked = [a for a in allac2 if a['unlocked']]
    assert len(unlocked) == 1 and unlocked[0]['key'] == key, allac2
    assert len(allac2) == len(allac), "o catálogo não muda de tamanho, só o flag"
    print("OK  test_all_achievements_path_locked_then_unlocked")


if __name__ == '__main__':
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
