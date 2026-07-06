"""
Coach Replay: erros mais caros do torneio (o que o herói fez × GTO + EV) + Pro-gate. Via endpoint.
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

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


def _seed():
    uid = repo.create_user('cr_user', 'cr@t.com', 'pass1234', 'player')
    conn = repo.get_conn()
    conn.execute(repo._adapt("INSERT INTO tournaments (id, user_id, tournament_id, hero, tournament_name) VALUES (?,?,?,?,?)"),
                 (9001, uid, 'T9001', 'Hero', 'MTT Teste'))
    # dois erros criticos com EV diferente (o mais caro vem primeiro)
    for hid, street, pos, cards, taken, gto, ev in [
        ('H1', 'flop', 'CO', 'AhTs', 'fold', 'call', 17.5),
        ('H2', 'turn', 'BB', 'JsAs', 'fold', 'call', 9.2),
    ]:
        conn.execute(repo._adapt(
            "INSERT INTO decisions (tournament_id, hand_id, street, position, hero_cards, "
            "action_taken, best_action, gto_action, gto_label, label, score, ev_loss_bb) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"),
            (9001, hid, street, pos, cards, taken, gto, gto, 'gto_critical', 'clear_mistake', 0.4, ev))
    conn.commit(); conn.close()
    return uid


def test_coach_replay_costliest_and_pro_gate():
    uid = _seed()
    h = {'Authorization': f'Bearer {generate_token(uid, "player")}'}

    # Free → upsell, sem vazar dados
    r_free = client.get('/player/coach-replay/9001', headers=h).get_json()
    assert r_free.get('requires_pro') is True and 'mistakes' not in r_free, r_free

    # Pro → os erros, ordenados pelo mais caro, com nota do coach e EV real
    repo.update_user_plan(uid, 'pro', None)
    r = client.get('/player/coach-replay/9001', headers=h).get_json()
    assert r['tournament']['name'] == 'MTT Teste'
    assert r['intro']['ev_lost_bb'] == 26.7            # 17.5 + 9.2
    ms = r['mistakes']
    assert [m['hand_id'] for m in ms] == ['H1', 'H2'], "erro mais caro primeiro"
    assert ms[0]['ev_loss_bb'] == 17.5 and 'fold' in ms[0]['coach_note'] and '17.5' in ms[0]['coach_note']
    print("OK  test_coach_replay_costliest_and_pro_gate")


def test_coach_replay_not_owner():
    """Só o dono vê o replay do torneio."""
    other = repo.create_user('cr_other', 'cro@t.com', 'pass1234', 'player')
    repo.update_user_plan(other, 'pro', None)
    h = {'Authorization': f'Bearer {generate_token(other, "player")}'}
    assert client.get('/player/coach-replay/9001', headers=h).status_code == 404
    print("OK  test_coach_replay_not_owner")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
