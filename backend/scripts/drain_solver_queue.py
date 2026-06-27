"""
drain_solver_queue.py — drena a gto_solver_queue chamando run_solver_worker.

Por que existe: os worker-threads de `_solver_queue_worker_loop` (app.py) só sobem
no bloco `if __name__ == '__main__'` (= `python app.py`, dev). Produção roda via
gunicorn, que importa o módulo e NÃO executa o __main__ → o enqueue (por-request)
funciona, mas a drenagem da fila não. Este runner é chamado por cron pra drenar.

Reseta spots presos em 'running' (> 10 min, de restart/crash) antes de drenar.

Uso: python scripts/drain_solver_queue.py [max_jobs=20]
"""
import os
import sys
# Garante /app (raiz do backend) no path — `python scripts/x.py` só põe scripts/ no path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
        # Limpa gto_hand_requests ÓRFÃOS (torneio deletado) — senão erram "Torneio sem raw_text no banco"
        # ao serem processados, poluindo o painel de erros. O delete de torneio já faz cascade; isto
        # recolhe os que ficaram de deletes antigos (antes do cascade).
        conn.execute(
            "DELETE FROM gto_hand_requests WHERE tournament_id NOT IN (SELECT id FROM tournaments)"
        )
        conn.commit()
    finally:
        conn.close()


def _regrade_heuristic():
    """#29: colhe a cobertura nova — re-grada SÓ as decisões heurísticas (heurística→GTO)
    pra as estatísticas (ELO/Leak Finder/alignment) atualizarem sozinhas após o solve.
    Subprocess isola: falha aqui não derruba o drain."""
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reanalyze_all_labels.py')
    print("drain_solver_queue: novos nós → re-gradando heurísticas (#29)...")
    subprocess.run([sys.executable, script, '--only-heuristic'], check=False)


def _finalize_hand_requests(max_reqs: int = 100):
    """Finaliza gto_hand_requests não-terminais. Em prod o _gto_hand_worker_loop (que faz isto) NÃO
    roda em gunicorn — só no __main__. Sem este passo, depois que o drain resolve os spots, o request
    fica 'solver_queued' ETERNO (o "1 spot pendente há tempos"). Aqui re-processa: spots resolvidos →
    'done'; requests velhos (>2h) ainda 'solver_queued' (spots não-solváveis: multiway/deep/HU-only)
    são forçados a 'done' pra não travar fila e UI."""
    from datetime import datetime, timedelta
    try:
        from api.app import _process_gto_hand_request
        from database.repositories import update_gto_hand_request, get_pending_gto_hand_requests
    except Exception as e:
        print(f"drain_solver_queue: finalize indisponível ({e})")
        return
    stale = (datetime.utcnow() - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
    reqs = get_pending_gto_hand_requests(limit=max_reqs)
    fin = 0
    for req in reqs:
        req = dict(req)
        try:
            status, err, n_done, n_queued = _process_gto_hand_request(req)
            if status == 'solver_queued' and str(req.get('created_at') or '') < stale:
                status, err = 'done', (err or 'spots não-solváveis (multiway/deep) — finalizado pelo drain')
            update_gto_hand_request(req['id'], status, decisions_done=n_done, error_msg=err)
            if status == 'done':
                fin += 1
        except Exception as e:
            print(f"drain_solver_queue: req {req.get('id')} finalize falhou: {e}")
    print(f"drain_solver_queue: finalize hand_requests -> {fin}/{len(reqs)} done")


def main():
    max_jobs = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    _reset_stale_running()
    result = run_solver_worker(max_jobs=max_jobs)
    print(f"drain_solver_queue: max_jobs={max_jobs} -> {result}")
    # Só re-grada se fechou/copiou nós novos (senão é desperdício; steady-state = no-op).
    if (result.get('solved', 0) + result.get('copied', 0)) > 0:
        _regrade_heuristic()
    # Finaliza os hand_requests (resolvidos → done; não-solváveis velhos → done). SEMPRE roda — é o
    # que tira o "solver_queued eterno" em prod, independente de ter resolvido spot novo neste ciclo.
    _finalize_hand_requests()


if __name__ == "__main__":
    main()
