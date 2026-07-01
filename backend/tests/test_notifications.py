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


def test_coach_message_produces_notification():
    coach = _new_user("notif_coach")
    student = _new_user("notif_student")
    # coach → aluno: notifica o aluno
    repo.send_coach_message(coach, student, "boa linha!", sender_role="coach")
    assert any(i["type"] == "coach_message" for i in repo.get_notifications(student))
    assert repo.get_unread_notification_count(student) >= 1
    # aluno → coach: notifica o coach
    repo.send_coach_message(coach, student, "valeu", sender_role="student")
    assert any(i["type"] == "student_message" for i in repo.get_notifications(coach))
    print("OK  test_coach_message_produces_notification")


def test_message_links_open_chat():
    coach = _new_user("notif_lc"); student = _new_user("notif_ls")
    repo.send_coach_message(coach, student, "oi", sender_role="coach")
    n = [i for i in repo.get_notifications(student) if i["type"] == "coach_message"][0]
    assert n["link"] == "/dashboard?chat=1", n["link"]
    repo.send_coach_message(coach, student, "oi de volta", sender_role="student")
    m = [i for i in repo.get_notifications(coach) if i["type"] == "student_message"][0]
    assert m["link"] == "/coach-dashboard?tab=mensagens", m["link"]
    print("OK  test_message_links_open_chat")


def test_annotation_link_opens_replayer():
    coach = _new_user("notif_ac"); student = _new_user("notif_as")
    conn = repo.get_conn()
    try:
        conn.execute("INSERT INTO tournaments (user_id, tournament_id, site, hero) VALUES (?,?,?,?)",
                     (student, "T999PUB", "PokerStars", "hero"))
        tdb = conn.execute("SELECT id FROM tournaments WHERE tournament_id='T999PUB'").fetchone()["id"]
        conn.execute("INSERT INTO decisions (tournament_id, hand_id, street, action_taken, best_action, label, score) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (tdb, "HAND777", "flop", "bet", "bet", "standard", 0.0))
        did = conn.execute("SELECT id FROM decisions WHERE hand_id='HAND777'").fetchone()["id"]
        conn.commit()
    finally:
        conn.close()
    repo.upsert_annotation(coach, student, did, "boa linha", mode="complement")
    n = [i for i in repo.get_notifications(student) if i["type"] == "coach_annotation"][0]
    assert n["link"] == "/replayer?t=T999PUB&h=HAND777", n["link"]
    assert n["payload"]["decision_id"] == did
    print("OK  test_annotation_link_opens_replayer")


def test_dismiss_one():
    uid = _new_user("notif_dis1")
    n1 = repo.create_notification(uid, "t", payload={})
    n2 = repo.create_notification(uid, "t", payload={})
    assert repo.dismiss_notification(uid, n1) is True
    ids = [n["id"] for n in repo.get_notifications(uid)]
    assert n1 not in ids and n2 in ids
    # dispensar de novo (já removida) → False
    assert repo.dismiss_notification(uid, n1) is False
    print("OK  test_dismiss_one")


def test_dismiss_only_own():
    a = _new_user("notif_da"); b = _new_user("notif_db")
    nid = repo.create_notification(a, "t", payload={})
    assert repo.dismiss_notification(b, nid) is False   # b não remove a de a
    assert len(repo.get_notifications(a)) == 1
    print("OK  test_dismiss_only_own")


def test_dismiss_all():
    uid = _new_user("notif_dall")
    for _ in range(3):
        repo.create_notification(uid, "t", payload={})
    assert repo.dismiss_all_notifications(uid) == 3
    assert repo.get_notifications(uid) == []
    assert repo.get_unread_notification_count(uid) == 0
    print("OK  test_dismiss_all")


def test_admin_message_and_broadcast():
    """#35: DM (create_notification admin_message) + broadcast (get_all_user_ids + broadcast_notification)."""
    a = _new_user("adm_a")
    b = _new_user("adm_b")
    ids = repo.get_all_user_ids(role="player")
    assert a in ids and b in ids
    n = repo.broadcast_notification([a, b], "admin_broadcast",
                                    payload={"title": "Aviso", "body": "Manutenção às 22h"}, link="/x")
    assert n == 2
    ia = repo.get_notifications(a)
    assert any(x["type"] == "admin_broadcast" and x["payload"]["title"] == "Aviso" for x in ia), ia
    # DM com título+corpo
    repo.create_notification(b, "admin_message", payload={"title": "Oi", "body": "Mensagem direta"})
    ib = repo.get_notifications(b)
    assert any(x["type"] == "admin_message" and x["payload"]["body"] == "Mensagem direta" for x in ib), ib
    # broadcast vazio = 0
    assert repo.broadcast_notification([], "admin_broadcast", payload={"title": "x"}) == 0
    print("OK  test_admin_message_and_broadcast")


def test_email_recipients_optin_and_unsub_token():
    """Espelho por email respeita opt-out (email_opt_in) e o token de unsubscribe é válido/único."""
    from leaklab.email_digest import _email_unsub_token, verify_email_unsub_token
    a = _new_user("mail_a")
    b = _new_user("mail_b")
    # ambos começam opt-in (default 1) e com email preenchido
    recips = {r["id"]: r for r in repo.get_email_recipients([a, b])}
    assert a in recips and b in recips, recips
    assert recips[a]["email"] == "mail_a@test.local"
    # descadastra b → some da lista, a permanece
    repo.update_email_opt_in(b, False)
    ids2 = {r["id"] for r in repo.get_email_recipients([a, b])}
    assert a in ids2 and b not in ids2, ids2
    # lista vazia = []
    assert repo.get_email_recipients([]) == []
    # token HMAC: válido pro próprio uid, inválido cruzado
    tok_a = _email_unsub_token(a)
    assert verify_email_unsub_token(a, tok_a)
    assert not verify_email_unsub_token(b, tok_a)
    print("OK  test_email_recipients_optin_and_unsub_token")


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
