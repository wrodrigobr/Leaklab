"""
Testa a infra de notificações in-app (genérica): create/get/unread/mark.
DB SQLite temporário isolado (mesmo padrão do test_database).
"""
import sys, os, tempfile, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TEST_DB = tempfile.mktemp(suffix='.db')
import database.schema as sch
import database.repositories as repo


def _setup():
    sch.DB_PATH = TEST_DB
    repo.DB_PATH = TEST_DB
    def get_conn_test():
        conn = sqlite3.connect(TEST_DB)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn
    sch.get_conn = get_conn_test
    repo.get_conn = get_conn_test
    sch.init_db()


_setup()


def _new_user(name):
    return repo.create_user(name, f"{name}@test.local", "x12345678")


def test_create_and_get():
    uid = _new_user("notif_u1")
    repo.create_notification(uid, "elo_band_up",
                             payload={"band": "Sólido", "delta": 12.3}, link="/rating")
    items = repo.get_notifications(uid)
    assert len(items) == 1
    n = items[0]
    assert n["type"] == "elo_band_up"
    assert n["payload"]["band"] == "Sólido" and n["payload"]["delta"] == 12.3  # JSON parseado
    assert n["link"] == "/rating"
    assert n["read"] is False and n["read_at"] is None
    print("OK  test_create_and_get")


def test_unread_count_and_mark_read():
    uid = _new_user("notif_u2")
    n1 = repo.create_notification(uid, "elo_band_up", payload={"band": "Regular"})
    repo.create_notification(uid, "elo_band_down", payload={"band": "Estudante"})
    assert repo.get_unread_notification_count(uid) == 2
    repo.mark_notification_read(uid, n1)
    assert repo.get_unread_notification_count(uid) == 1
    # a marcada vira read=True
    items = repo.get_notifications(uid)
    marked = [i for i in items if i["id"] == n1][0]
    assert marked["read"] is True and marked["read_at"] is not None
    print("OK  test_unread_count_and_mark_read")


def test_mark_all_read():
    uid = _new_user("notif_u3")
    for i in range(3):
        repo.create_notification(uid, "elo_band_up", payload={"i": i})
    assert repo.get_unread_notification_count(uid) == 3
    repo.mark_all_notifications_read(uid)
    assert repo.get_unread_notification_count(uid) == 0
    print("OK  test_mark_all_read")


def test_isolation_and_order():
    a = _new_user("notif_a")
    b = _new_user("notif_b")
    repo.create_notification(a, "t1", payload={"k": 1})
    repo.create_notification(a, "t2", payload={"k": 2})
    repo.create_notification(b, "t3", payload={"k": 3})
    # b não vê as de a
    assert len(repo.get_notifications(b)) == 1
    # ordem: mais nova primeiro (t2 antes de t1)
    ai = repo.get_notifications(a)
    assert [n["type"] for n in ai] == ["t2", "t1"]
    print("OK  test_isolation_and_order")


def test_mark_read_only_own():
    a = _new_user("notif_owner")
    b = _new_user("notif_other")
    nid = repo.create_notification(a, "t", payload={})
    repo.mark_notification_read(b, nid)   # b tenta marcar a de a → no-op
    assert repo.get_unread_notification_count(a) == 1
    print("OK  test_mark_read_only_own")


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
    try: os.unlink(TEST_DB)
    except Exception: pass
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
