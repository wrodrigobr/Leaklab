"""
test_postgres_smoke.py — smoke test das funções de AGREGAÇÃO contra o banco REAL.

No CI roda em **Postgres** (DATABASE_URL setado) e pega a classe de bug que o SQLite
esconde e o usuário sente em produção:
  - float * Decimal  (NUMERIC vem decimal.Decimal no psycopg2)
  - ROUND(real, int) (Postgres só tem ROUND(numeric, int))
  - Decimal não-serializável em json.dumps / jsonify
  - HAVING não enxerga aliases de SELECT
  - lastrowid None, INSERT OR REPLACE, etc.

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
    ("preflop", "BB",  "BTN", "call",  "fold",  "erro_claro", 0.42, 22, 2.2, 0, 1, "gto_critical",       1.8),
    ("preflop", "BB",  "BTN", "call",  "fold",  "erro_claro", 0.38, 18, 2.0, 0, 1, "gto_critical",       1.1),
    ("preflop", "BB",  "BTN", "call",  "raise", "marginal",   0.21, 25, 2.5, 0, 1, "gto_minor_deviation", 0.4),
    ("preflop", "SB",  "CO",  "raise", "fold",  "erro_claro", 0.45, 14, 0.5, 0, 1, "gto_critical",       2.6),
    ("preflop", "UTG", "",    "raise", "raise", "standard",   0.05, 40, 0.0, 0, 0, "gto_correct",        0.0),
    ("preflop", "BTN", "",    "raise", "call",  "marginal",   0.24, 30, 0.0, 0, 0, "gto_minor_deviation", 0.6),
    ("flop",    "BB",  "BTN", "check", "bet",   "erro_claro", 0.36, 20, 4.0, 0, 1, "gto_critical",       3.1),
    ("flop",    "BTN", "BB",  "bet",   "check", "marginal",   0.22, 28, 0.0, 0, 0, "gto_minor_deviation", 0.7),
    ("turn",    "BB",  "BTN", "call",  "fold",  "erro_claro", 0.40, 16, 6.0, 0, 1, "gto_critical",       4.2),
    ("turn",    "CO",  "",    "bet",   "bet",   "standard",   0.06, 35, 0.0, 0, 0, "gto_correct",        0.0),
    ("river",   "BB",  "BTN", "check", "check", "standard",   0.04, 12, 0.0, 0, 1, "gto_correct",        0.0),
    ("preflop", "CO",  "",    "raise", "raise", "standard",   0.07, 38, 0.0, 0, 0, "gto_correct",        0.0),
    ("preflop", "BB",  "SB",  "raise", "call",  "marginal",   0.26, 24, 1.0, 1, 1, "gto_minor_deviation", 0.9),
    ("preflop", "BB",  "SB",  "raise", "call",  "erro_claro", 0.39,  9, 1.0, 1, 1, "gto_critical",       1.4),
    ("flop",    "BB",  "BTN", "check", "bet",   "marginal",   0.23, 21, 3.0, 0, 1, "gto_minor_deviation", 0.8),
    ("turn",    "UTG", "",    "check", "bet",   "erro_claro", 0.41, 17, 5.0, 0, 0, "gto_critical",       2.3),
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
            taken, best, label, score, pos, vspos, 6, stack, facing, is3,
            12.0, "medium", prf, gto, evloss,
        ))
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

print(f"\nTotal: {passed + failed}  Passed: {passed}  Failed: {failed}")
sys.exit(1 if failed else 0)
