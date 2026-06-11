"""
solver_signals.py — Fase 2 do plano do solver (specs/solver-improvement-plan.md).

Sinal de "fila tem trabalho" entre o enqueue (repositories.enqueue_solver_spot)
e o worker em background (api/app.py::_solver_queue_worker_loop). Substitui o
polling cego de 60s por event-driven: o enqueue acorda o worker na hora; o
timeout do wait vira só uma varredura de segurança.

Módulo separado para evitar import circular (database → leaklab → database).
"""
import threading

solver_queue_event = threading.Event()


def notify_solver_queue() -> None:
    """Acorda o worker do solver (chamado pelo enqueue)."""
    solver_queue_event.set()
