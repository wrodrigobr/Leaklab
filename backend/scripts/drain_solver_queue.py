"""
drain_solver_queue.py — drena a gto_solver_queue chamando run_solver_worker.

Por que existe: os worker-threads de `_solver_queue_worker_loop` (app.py) só sobem
no bloco `if __name__ == '__main__'` (= `python app.py`, dev). Produção roda via
gunicorn, que importa o módulo e NÃO executa o __main__ → o enqueue (por-request)
funciona, mas a drenagem da fila não. Este runner é chamado por cron pra drenar.

Reseta spots presos em 'running' (> 10 min, de restart/crash) antes de drenar.

Uso: python scripts/drain_solver_queue.py [max_jobs=20]
"""
import sys
from datetime import datetime, timedelta
from leaklab.gto_solver import run_solver_worker
from database.schema import get_conn


def _reset_stale_running():
    # cutoff em Python (não `datetime('now','-10 minutes')`: o adapter só converte
    # 'days' p/ Postgres, não 'minutes' — quebraria no Neon).
    cutoff = (datetime.utcnow() - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE gto_solver_queue SET status='pending' "
            "WHERE status='running' AND requested_at < ?",
            (cutoff,)
        )
        conn.commit()
    finally:
        conn.close()


def main():
    max_jobs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    _reset_stale_running()
    result = run_solver_worker(max_jobs=max_jobs)
    print(f"drain_solver_queue: max_jobs={max_jobs} -> {result}")


if __name__ == "__main__":
    main()
