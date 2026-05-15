"""Lido pelo watch_gto_queue.ps1 — imprime status das filas GTO."""
import sqlite3, datetime, sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "data/leaklab.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

sq = {r["status"]: r["n"] for r in conn.execute(
    "SELECT status, COUNT(*) n FROM gto_solver_queue GROUP BY status").fetchall()}
hr = {r["status"]: r["n"] for r in conn.execute(
    "SELECT status, COUNT(*) n FROM gto_hand_requests GROUP BY status").fetchall()}

sq_pending = sq.get("pending", 0)
sq_done    = sq.get("done", 0)
sq_failed  = sq.get("failed", 0)
hr_pending = hr.get("pending", 0)
hr_done    = hr.get("done", 0)

last = conn.execute("""
    SELECT hand_id, status, processed_at, error_msg
    FROM gto_hand_requests ORDER BY id DESC LIMIT 1
""").fetchone()

total_pf = conn.execute(
    "SELECT COUNT(*) n FROM decisions WHERE street IN ('flop','turn','river')"
).fetchone()["n"]

no_gto = conn.execute("""
    SELECT COUNT(*) n FROM decisions
    WHERE street IN ('flop','turn','river') AND gto_label IS NULL
""").fetchone()["n"]

wizard_pending = conn.execute("""
    SELECT COUNT(*) n FROM decisions
    WHERE street IN ('flop','turn','river') AND gto_label = 'wizard_pending'
""").fetchone()["n"]

conn.close()

now = datetime.datetime.now().strftime("%H:%M:%S")
print(f"[{now}]")
print(f"  solver_queue   pending={sq_pending}  done={sq_done}  failed={sq_failed}")
print(f"  hand_requests  pending={hr_pending}  done={hr_done}")
print(f"  wizard_pending (aguardando fallback): {wizard_pending}")

if no_gto == 0 and wizard_pending == 0:
    print(f"  decisoes sem GTO: 0/{total_pf}  -- CONCLUIDO")
else:
    print(f"  decisoes sem GTO: {no_gto}/{total_pf}  |  aguardando wizard: {wizard_pending}")

if last:
    err = f"  ERRO: {last['error_msg']}" if last['error_msg'] else ""
    print(f"  ultima hand: {last['hand_id']}  [{last['status']}]  {last['processed_at'] or ''}{err}")
