"""
test_postgres_smoke.py — smoke test das funções de agregação + de TODOS os endpoints GET
contra o banco REAL.

No CI roda em **Postgres** (DATABASE_URL setado) e pega a classe de bug que o SQLite
esconde e o usuário sente em produção:
  - float * Decimal  (NUMERIC vem decimal.Decimal no psycopg2)
  - ROUND(real, int) (Postgres só tem ROUND(numeric, int))
  - Decimal não-serializável em json.dumps / jsonify
  - HAVING não enxerga aliases de SELECT
  - lastrowid None, INSERT OR REPLACE, etc.
  - COLUNA FALTANDO por migração abortada (ex.: drill_sessions.correct → 500 no Ghost Table)
  - text >= timestamp (coluna TEXT comparada a NOW()/interval → 500 no /admin/finance/dunning)

Duas camadas de cobertura:
  1. Funções de risco (analytics, drill, admin, financeiro) chamadas + json.dumps SEM default.
  2. Sweep HTTP: cada rota GET preenchível é batida com um admin via test client (app.testing=True,
     então a exceção real propaga). Auto-cobre endpoints novos sem manutenção da lista.
A lacuna que deixou 7 bugs SQLite↔PG chegarem em prod era a ausência das camadas drill/admin/HTTP.

Não faz parte das suítes do run_all_tests (que são SQLite). É um script standalone:
  - CI:   DATABASE_URL=postgres://... python tests/test_postgres_smoke.py
  - local validação da lógica: SMOKE_FORCE_SQLITE=1 python tests/test_postgres_smoke.py

Cada função é chamada e o resultado passa por json.dumps SEM default — assim qualquer
Decimal/tipo não-serializável estoura aqui (no CI) antes do usuário.
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import database.schema as schema  # noqa: E402

FORCE_SQLITE = os.environ.get("SMOKE_FORCE_SQLITE") == "1"

if not schema.USE_POSTGRES and not FORCE_SQLITE:
    print("SKIP — sem DATABASE_URL (Postgres). Use SMOKE_FORCE_SQLITE=1 p/ validar a lógica.")
    print("\nTotal: 0  Passed: 0  Failed: 0")
    sys.exit(0)

# Banco isolado quando rodando em SQLite local (não polui o dev nem outras suítes).
if not schema.USE_POSTGRES:
    import tempfile
    _tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    _tmp.close()
    schema.SQLITE_PATH = _tmp.name

from database import repositories as repo          # noqa: E402
from database.repositories import _adapt           # noqa: E402

BACKEND = "POSTGRES" if schema.USE_POSTGRES else "SQLite (validação local)"
print(f"== smoke test contra {BACKEND} ==")

schema.init_db()

# ── Seed: 1 user + 1 torneio (com buy_in) + decisions variadas ──────────────────
uid = repo.create_user(f"smoke_{os.getpid()}", f"smoke_{os.getpid()}@test.local", "x" * 10)
assert uid, "create_user devolveu id vazio (lastrowid/RETURNING?)"

conn = schema.get_conn()
conn.execute(_adapt("""
    INSERT INTO tournaments (user_id, tournament_id, hero, buy_in, hands_count, decisions_count, avg_score)
    VALUES (?,?,?,?,?,?,?)
"""), (uid, "SMOKE-T1", "Hero", 5.50, 10, 16, 0.31))
conn.commit()
_t = conn.execute(_adapt("SELECT id FROM tournaments WHERE user_id=? AND tournament_id=?"),
                  (uid, "SMOKE-T1")).fetchone()
t_id = _t["id"]

# (street, position, vs_position, best_action, action_taken, label, score, stack_bb,
#  facing_bet, is_3bet, preflop_raises_faced, gto_label, ev_loss_bb)
_seed = [
    ("preflop", "BB",  "BTN", "call",  "fold",  "clear_mistake", 0.42, 22, 2.2, 0, 1, "gto_critical",       1.8),
    ("preflop", "BB",  "BTN", "call",  "fold",  "clear_mistake", 0.38, 18, 2.0, 0, 1, "gto_critical",       1.1),
    ("preflop", "BB",  "BTN", "call",  "raise", "small_mistake",   0.21, 25, 2.5, 0, 1, "gto_minor_deviation", 0.4),
    ("preflop", "SB",  "CO",  "raise", "fold",  "clear_mistake", 0.45, 14, 0.5, 0, 1, "gto_critical",       2.6),
    ("preflop", "UTG", "",    "raise", "raise", "standard",   0.05, 40, 0.0, 0, 0, "gto_correct",        0.0),
    ("preflop", "BTN", "",    "raise", "call",  "small_mistake",   0.24, 30, 0.0, 0, 0, "gto_minor_deviation", 0.6),
    ("flop",    "BB",  "BTN", "check", "bet",   "clear_mistake", 0.36, 20, 4.0, 0, 1, "gto_critical",       3.1),
    ("flop",    "BTN", "BB",  "bet",   "check", "small_mistake",   0.22, 28, 0.0, 0, 0, "gto_minor_deviation", 0.7),
    ("turn",    "BB",  "BTN", "call",  "fold",  "clear_mistake", 0.40, 16, 6.0, 0, 1, "gto_critical",       4.2),
    ("turn",    "CO",  "",    "bet",   "bet",   "standard",   0.06, 35, 0.0, 0, 0, "gto_correct",        0.0),
    ("river",   "BB",  "BTN", "check", "check", "standard",   0.04, 12, 0.0, 0, 1, "gto_correct",        0.0),
    ("preflop", "CO",  "",    "raise", "raise", "standard",   0.07, 38, 0.0, 0, 0, "gto_correct",        0.0),
    ("preflop", "BB",  "SB",  "raise", "call",  "small_mistake",   0.26, 24, 1.0, 1, 1, "gto_minor_deviation", 0.9),
    ("preflop", "BB",  "SB",  "raise", "call",  "clear_mistake", 0.39,  9, 1.0, 1, 1, "gto_critical",       1.4),
    ("flop",    "BB",  "BTN", "check", "bet",   "small_mistake",   0.23, 21, 3.0, 0, 1, "gto_minor_deviation", 0.8),
    ("turn",    "UTG", "",    "check", "bet",   "clear_mistake", 0.41, 17, 5.0, 0, 0, "gto_critical",       2.3),
]
cols = ("tournament_id, hand_id, street, hero_cards, board, action_taken, best_action, label, "
        "score, position, vs_position, num_players, stack_bb, facing_bet, is_3bet, m_ratio, "
        "icm_pressure, preflop_raises_faced, gto_label, ev_loss_bb")
ph = "(" + ",".join("?" * 20) + ")"
# 3× o seed (48 decisões) → passa do mínimo de 30 do cognitivo (detecção completa roda).
for rep in range(3):
    for i, (street, pos, vspos, best, taken, label, score, stack, facing,
            is3, prf, gto, evloss) in enumerate(_seed):
        conn.execute(_adapt(f"INSERT INTO decisions ({cols}) VALUES {ph}"), (
            t_id, f"H{rep}_{i}", street, "AhKs", "" if street == "preflop" else "2c7d9h",
            taken, best, label, score, pos, vspos, 6, stack, facing, bool(is3),
            12.0, "medium", prf, gto, evloss,
        ))
conn.commit()

# ── Seed extra p/ drill + admin + financeiro (exercita colunas correct/canceled_at/payments
#    que faltavam em prod) ─────────────────────────────────────────────────────────────────
_dec = conn.execute(_adapt("SELECT id FROM decisions WHERE tournament_id=? LIMIT 1"), (t_id,)).fetchone()
dec_id = _dec["id"]
# drill_session com a coluna `correct` — se a migração não a criou, o INSERT estoura aqui (= o bug do Ghost Table)
conn.execute(_adapt(
    "INSERT INTO drill_sessions (user_id, decision_id, new_action, new_score, original_score, delta, "
    "correct, next_drill_at, srs_interval_days) VALUES (?,?,?,?,?,?,?,?,?)"),
    (uid, dec_id, "call", 0.10, 0.40, -0.30, 1, "2099-01-01T00:00:00", 3))
conn.execute(_adapt(
    "INSERT INTO payments (user_id, plan, amount_cents, currency, status, gateway) VALUES (?,?,?,?,?,?)"),
    (uid, "pro", 9900, "BRL", "failed", "stripe"))
# usuário cancelado + perfil demográfico (admin_dunning / demographics)
conn.execute(_adapt(
    "UPDATE users SET subscription_status='canceled', canceled_at=?, cancel_reason='payment_failure', "
    "plan='pro', country='BR', main_game_type='mtt', usual_buyin_range='1-5', profile_completed_at=? WHERE id=?"),
    ("2099-01-01T00:00:00", "2099-01-01T00:00:00", uid))
conn.commit()
conn.close()

# ── Exercita as funções de risco + json.dumps (pega Decimal/ROUND/float*Decimal) ──
passed = failed = 0


def check(label, fn):
    global passed, failed
    try:
        result = fn()
        json.dumps(result)   # SEM default=str → Decimal não-serializável estoura aqui
        passed += 1
        print(f"OK   {label}")
    except Exception as e:
        failed += 1
        print(f"FAIL {label}: {type(e).__name__}: {e}")


check("get_player_stats",          lambda: repo.get_player_stats(uid, 90))
check("get_ev_leaks",              lambda: repo.get_ev_leaks(uid, 90))
check("get_gto_leak_ranking",      lambda: repo.get_gto_leak_ranking(uid, 90))
check("get_leak_ranking_gto_first", lambda: repo.get_leak_ranking_gto_first(uid, 90))
check("get_leak_roi_impact",       lambda: repo.get_leak_roi_impact(uid, 90))
check("get_evolution_metrics",     lambda: repo.get_evolution_metrics(uid, 90))
check("get_icm_performance",       lambda: repo.get_icm_performance(uid, 90))
check("get_leak_graph_data",       lambda: repo.get_leak_graph_data(uid, 90, "pt-BR"))
check("get_cognitive_failure_report", lambda: repo.get_cognitive_failure_report(uid, 90))

# ── Drill + Admin + Financeiro (a lacuna que deixou os 7 bugs de prod passarem) ──────────────
check("get_drill_stats",           lambda: repo.get_drill_stats(uid, 30))
check("get_drill_spots",           lambda: repo.get_drill_spots(uid, 10))
check("admin_revenue_summary",     lambda: repo.admin_revenue_summary())
check("admin_cockpit_summary",     lambda: repo.admin_cockpit_summary())
check("admin_finance_calendar",    lambda: repo.admin_finance_calendar())
check("admin_dunning",             lambda: repo.admin_dunning())
check("admin_revenue_timeseries",  lambda: repo.admin_revenue_timeseries(6))
check("admin_detect_duplicate_payments", lambda: repo.admin_detect_duplicate_payments())
check("get_demographics_aggregate", lambda: repo.get_demographics_aggregate())
check("get_all_users",             lambda: repo.get_all_users(50, 0))
check("get_all_users_count",       lambda: repo.get_all_users_count())
check("get_students",              lambda: repo.get_students(uid))
check("get_students_attention_signals", lambda: repo.get_students_attention_signals(uid))

# ── Sweep HTTP: cada rota GET preenchível, com admin, via test client. Auto-cobre endpoints
#    novos (incl. os que quebraram: /player/spots/drill, /admin/finance/dunning, /admin/demographics).
#    app.testing=True → exceção propaga e o erro real (psycopg2.*) é capturado por endpoint. ──────
import re as _re  # noqa: E402

_c2 = schema.get_conn()
_c2.execute(_adapt("UPDATE users SET role='admin' WHERE id=?"), (uid,))
_c2.commit()
_c2.close()

from api.app import app as _flask_app          # noqa: E402
from database.auth import generate_token       # noqa: E402

_flask_app.testing = True                       # propaga exceções (pego o erro real, não um 500 mudo)
_tok = generate_token(uid, "admin")
_cli = _flask_app.test_client()
_hdr = {"Authorization": f"Bearer {_tok}"}
_fill = {
    "decision_id": dec_id, "tournament_id": t_id, "tid": t_id, "db_id": t_id,
    "student_id": uid, "user_id": uid, "coach_id": uid, "hand_id": "H0_0",
}
_SKIP = ("/static", "/stripe", "/webhook", "/export", "/download", "/auth/logout", "/health", "/ping")


def _http(url):
    def _do():
        r = _cli.get(url, headers=_hdr)
        if r.status_code == 500:
            raise AssertionError(f"HTTP 500: {r.get_data(as_text=True)[:160]}")
        return {"status": r.status_code}
    return _do


_swept = 0
for _rule in _flask_app.url_map.iter_rules():
    if "GET" not in (_rule.methods or set()):
        continue
    if any(s in _rule.rule for s in _SKIP):
        continue
    if any(a not in _fill for a in _rule.arguments):   # param que não sei preencher → pula
        continue
    _url = _re.sub(r"<[^>]+>", lambda m: str(_fill[m.group(0).strip("<>").split(":")[-1]]), _rule.rule)
    check(f"GET {_url}", _http(_url))
    _swept += 1
print(f"(sweep HTTP: {_swept} rotas GET)")

print(f"\nTotal: {passed + failed}  Passed: {passed}  Failed: {failed}")
sys.exit(1 if failed else 0)
