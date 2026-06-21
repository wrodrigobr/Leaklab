"""test_coach_referral.py — link referral + standing de pagamento + régua de comissão.

Trava:
  - billing_standing classifica free / paying / past_due / perk.
  - signup via link referral cria aluno PENDENTE vinculado ao coach (referral_coach_id).
  - aluno via referral aparece em list_pending_link_requests (via='link').
  - após aprovação, conta na meta de pagantes; past_due NÃO conta (comissão = em dia).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['LEAKLAB_DB'] = '_coach_ref_test.db'
if os.path.exists('_coach_ref_test.db'):
    os.remove('_coach_ref_test.db')

import database.schema as schema
schema.init_db()
from database.repositories import (
    create_user, assign_invite_key, get_coach_by_invite_key, get_students,
    billing_standing, list_pending_link_requests, get_coach_paying_referred_count, get_conn,
)

passed = 0
failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {msg}")


# ── billing_standing ─────────────────────────────────────────────────────────
check(billing_standing('free', None, None) == 'free', "free -> free")
check(billing_standing('pro', 'stripe_sub', 'active') == 'paying', "pro stripe ativo -> paying")
check(billing_standing('pro', 'stripe_sub', 'past_due') == 'past_due', "pro atrasado -> past_due")
check(billing_standing('pro', 'coach_earned', None) == 'perk', "pro perk coach -> perk")
check(billing_standing('pro', None, None) == 'paying', "pro legado (source NULL) -> paying")

# ── signup via link referral ─────────────────────────────────────────────────
coach_id = create_user('coachref', 'coachref@e', 'password1', 'coach')
key = assign_invite_key(coach_id)
check(key.startswith('COACH-'), "coach tem invite_key")
_c = get_coach_by_invite_key(key)
check(_c and _c['id'] == coach_id, "get_coach_by_invite_key resolve o coach")

student_id = create_user('alunoref', 'alunoref@e', 'password1', 'player',
                         coach_id=coach_id, referral_coach_id=coach_id,
                         link_status='pending', invited_by_key=key)
roster = {s['id']: s for s in get_students(coach_id)}
check(student_id in roster, "aluno referral aparece no roster do coach")
check(roster[student_id]['link_status'] == 'pending', "aluno referral nasce PENDENTE")
check(roster[student_id]['referral_coach_id'] == coach_id, "referral_coach_id setado")
check(roster[student_id]['billing_standing'] == 'free', "aluno novo é free")

pend = list_pending_link_requests(coach_id)
pend_ids = {p['student_id']: p for p in pend}
check(student_id in pend_ids, "aluno referral aparece nas solicitações pendentes")
check(pend_ids[student_id]['via'] == 'link', "origem do pendente = 'link'")

# ── régua de comissão: só conta aprovado + pagante EM DIA ────────────────────
check(get_coach_paying_referred_count(coach_id) == 0, "pendente não conta na meta")

conn = get_conn()
# aprova + torna pro pagante em dia
conn.execute("UPDATE users SET link_status='approved', plan='pro', plan_source='stripe_sub', subscription_status='active' WHERE id=?", (student_id,))
conn.commit(); conn.close()
check(get_coach_paying_referred_count(coach_id) == 1, "aprovado + pagante em dia CONTA")

conn = get_conn()
conn.execute("UPDATE users SET subscription_status='past_due' WHERE id=?", (student_id,))
conn.commit(); conn.close()
check(get_coach_paying_referred_count(coach_id) == 0, "atrasado (past_due) NÃO conta na comissão")

# limpeza
import database.schema as _s
try:
    _s.get_conn().close()
except Exception:
    pass
if os.path.exists('_coach_ref_test.db'):
    try:
        os.remove('_coach_ref_test.db')
    except Exception:
        pass

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
