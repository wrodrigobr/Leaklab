"""test_admin_finance.py — cockpit financeiro admin (entradas/saídas, net, dunning, despesas).

Trava: expenses CRUD; net = entradas − (coach payouts + despesas); MRR real (não proxy);
dunning lista atrasados; calendário e timeseries respondem.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['LEAKLAB_DB'] = '_admin_fin_test.db'
if os.path.exists('_admin_fin_test.db'):
    os.remove('_admin_fin_test.db')

import database.schema as schema
schema.init_db()
from database.repositories import (
    get_conn, create_expense, list_expenses, update_expense, delete_expense,
    admin_cockpit_summary, admin_finance_calendar, admin_dunning,
    admin_revenue_timeseries, _current_month, _month_bounds,
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


mon = _current_month()
c = get_conn()
c.execute("INSERT INTO users (id,username,email,password_hash,plan,plan_source,subscription_status) "
          "VALUES (1,'pay','p@e','h','pro','stripe_sub','active')")
c.execute("INSERT INTO users (id,username,email,password_hash,plan,plan_source,subscription_status,past_due_since) "
          "VALUES (2,'late','l@e','h','pro','stripe_sub','past_due','2026-06-01')")
c.execute("INSERT INTO payments (user_id,plan,amount_cents,currency,status,gateway,created_at,period_start,period_end) "
          "VALUES (1,'pro',9900,'BRL','approved','stripe',?,?,?)", (mon + '-10T00:00:00', mon + '-10', mon + '-10'))
c.commit()
c.close()

# ── despesas CRUD ────────────────────────────────────────────────────────────
e1 = create_expense('infra', 'Hetzner', 12000, 'monthly', 5)
e2 = create_expense('llm', 'Anthropic', 30000, 'monthly', 1)
e3 = create_expense('domain', 'Cloudflare', 12000, 'annual', 15)  # anual -> /12 = 1000/mês
check(len(list_expenses()) == 3, "3 despesas criadas")
update_expense(e3, amount_cents=24000)  # anual 24000 -> 2000/mês
check([x for x in list_expenses() if x['id'] == e3][0]['amount_cents'] == 24000, "update_expense aplica")

# ── cockpit: net = entradas − (coach + despesas) ─────────────────────────────
s = admin_cockpit_summary(mon)
# despesas mensais equiv = 12000 + 30000 + (24000/12=2000) = 44000
check(s['expenses_cents'] == 44000, f"despesa mensal equiv (anual/12) = 44000, veio {s['expenses_cents']}")
check(s['gross_in_cents'] == 9900, "entradas do mês = 9900")
check(s['cash_out_cents'] == 44000, "saídas = coach 0 + despesas 44000")
check(s['net_cents'] == 9900 - 44000, "net = entradas − saídas")
check(s['mrr_cents'] == 9900, "MRR real = 9900 (só quem tem pagamento), não proxy 2x9900")
check(s['paying_pro'] == 2, "2 pagantes pro")
check(s['past_due_count'] == 1, "1 em atraso (em risco)")
check(s['arpu_cents'] == round(9900 / 2), "ARPU = bruto / pagantes")

# ── dunning ──────────────────────────────────────────────────────────────────
d = admin_dunning()
check(len(d['past_due']) == 1 and d['past_due'][0]['username'] == 'late', "dunning lista o atrasado")
check('duplicates' in d and 'recent_failed' in d, "dunning tem duplicates + recent_failed")

# ── calendário + timeseries ──────────────────────────────────────────────────
cal = admin_finance_calendar(mon)
check(len(cal['expenses_due']) == 3, "calendário lista as 3 despesas com vencimento")
check(set(['renewals_in', 'payouts_out', 'expenses_due']) <= set(cal.keys()), "calendário tem as 3 streams")
ts = admin_revenue_timeseries(3)
check(len(ts) == 3 and ts[-1]['month'] == mon, "timeseries 3 meses terminando no mês atual")

# ── delete ───────────────────────────────────────────────────────────────────
delete_expense(e1)
check(len(list_expenses()) == 2, "delete_expense remove")

if os.path.exists('_admin_fin_test.db'):
    try:
        os.remove('_admin_fin_test.db')
    except Exception:
        pass

print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
sys.exit(1 if failed else 0)
