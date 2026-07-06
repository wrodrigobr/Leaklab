"""
Gate freemium do módulo de treino (média): Free treina fundamentos genéricos com cap
diário; treino MIRADO no leak e Ghost são Pro. Pro passa livre. Via endpoints.
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')
os.environ['TRAINING_GATE_START'] = '2020-01-01'   # gate ATIVO nos testes (fora da rampa suave)

try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

import database.schema as sch
import database.repositories as repo
sch.init_db()
import api.app as A
from database.auth import generate_token
client = A.app.test_client()


def _u(name, plan='free'):
    uid = repo.create_user(name, f'{name}@t.com', 'pass1234', 'player')
    if plan != 'free':
        repo.update_user_plan(uid, plan, None)
    return uid, {'Authorization': f'Bearer {generate_token(uid, "player")}'}


def test_free_training_is_generic_pro_is_targeted():
    _f, hf = _u('free_gen')
    _p, hp = _u('pro_gen', 'pro')
    rf = client.post('/player/leaktrainer/next', headers=hf, json={'focus': 'adaptive'}).get_json()
    assert rf['targeted_locked'] is True, "Free deveria cair em fundamentos (mirado é Pro)"
    assert rf['spot'] and rf['spot'].get('kind', 'preflop') != 'postflop', "Free não treina postflop"
    rp = client.post('/player/leaktrainer/next', headers=hp, json={'focus': 'adaptive'}).get_json()
    assert rp['targeted_locked'] is False and rp['spot'], "Pro treina mirado sem trava"
    print("OK  test_free_training_is_generic_pro_is_targeted")


def test_ghost_is_pro_only():
    _f, hf = _u('free_ghost')
    _p, hp = _u('pro_ghost', 'pro')
    assert client.get('/player/spots/drill', headers=hf).get_json().get('requires_pro') is True
    assert not client.get('/player/spots/drill', headers=hp).get_json().get('requires_pro')
    print("OK  test_ghost_is_pro_only")


def test_free_daily_cap_blocks_pro_unlimited():
    fid, hf = _u('free_cap')
    _p, hp = _u('pro_cap', 'pro')
    cap = repo.PLAN_LIMITS['free']['training_spots_per_day']
    for _ in range(cap):
        repo.record_daily_mission_progress(fid, True)
    rc = client.post('/player/leaktrainer/next', headers=hf, json={'focus': 'adaptive'}).get_json()
    assert rc.get('limit_reached') is True and rc.get('requires_pro') is True, rc
    # Pro no mesmo volume não trava
    pid = repo.create_user('pro_cap2', 'pc2@t.com', 'pass1234', 'player'); repo.update_user_plan(pid, 'pro', None)
    for _ in range(cap):
        repo.record_daily_mission_progress(pid, True)
    hp2 = {'Authorization': f'Bearer {generate_token(pid, "player")}'}
    rp = client.post('/player/leaktrainer/next', headers=hp2, json={'focus': 'adaptive'}).get_json()
    assert not rp.get('limit_reached'), "Pro não deveria ter cap diário"
    print("OK  test_free_daily_cap_blocks_pro_unlimited")


def test_grace_period_bypasses_gate():
    """Rampa suave: durante o período de transição (TRAINING_GATE_START no futuro) o Free
    treina como Pro (mirado, sem cap) e a resposta traz grace_until pro aviso."""
    os.environ['TRAINING_GATE_START'] = '2099-01-01'
    try:
        fid, hf = _u('free_grace')
        for _ in range(repo.PLAN_LIMITS['free']['training_spots_per_day'] + 5):
            repo.record_daily_mission_progress(fid, True)   # passa do cap
        r = client.post('/player/leaktrainer/next', headers=hf, json={'focus': 'adaptive'}).get_json()
        assert not r.get('limit_reached'), "na graça não há cap"
        assert r.get('targeted_locked') is False, "na graça o Free treina mirado"
        assert r.get('grace_until') == '2099-01-01', r
        assert not client.get('/player/spots/drill', headers=hf).get_json().get('requires_pro'), "Ghost liberado na graça"
    finally:
        os.environ['TRAINING_GATE_START'] = '2020-01-01'
    print("OK  test_grace_period_bypasses_gate")


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
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
