"""
Replay de mão ACR: o _build_replay_data extraía assentos com regex que exigia
"in chips" (PS/GG), mas ACR é "Seat N: nome (29150.00)" (sem "in chips") → seats
vazio → {'error':'Seats não encontrados'} → o Replayer mostrava "Sem Dados".
Regressão: seats + timeline não-vazios pra uma mão ACR.
"""
import sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
sch.init_db()

try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from leaklab.parser import parse_hand_history
from tests.test_acr_parser import ACR_FOLD_HAND
import api.app as A


def test_acr_replay_builds_seats_and_timeline():
    hands = parse_hand_history(ACR_FOLD_HAND)
    assert hands, "não parseou a mão ACR"
    rd = A._build_replay_data(hands[0], [], hands[0].hero)
    assert "error" not in rd, rd.get("error")
    assert len(rd.get("seats", {})) >= 2, rd.get("seats")
    assert len(rd.get("timeline", [])) >= 1, "timeline vazia"
    print("OK  test_acr_replay_builds_seats_and_timeline")


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
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
