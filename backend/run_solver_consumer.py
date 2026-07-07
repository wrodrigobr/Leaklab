"""
Consumidor da fila do solver GTO (produção) — serviço dedicado, no lugar do cron de 5min.

Roda o loop EVENT-DRIVEN (`_solver_queue_worker_loop`): acorda no instante que um spot é
enfileirado, drena a fila até esvaziar e resolve com concorrência = GTO_SOLVER_CONCURRENCY
(casar com o MAX_SOLVES do solver). Sem ociosidade entre lotes.

Diferente do bloco __main__ do app (que só roda em `python api/app.py` e está atrás do gate
LEAKLAB_LOCAL_SOLVER de proteção do PC de dev), este entrypoint sobe o consumidor de propósito,
para rodar como serviço (systemd / docker-compose) num box com acesso ao DB (DATABASE_URL) e ao
solver (GTO_SOLVER_URL).

Uso:
    python run_solver_consumer.py

Env relevantes:
    DATABASE_URL             Postgres de prod (sem isto usa SQLite local)
    GTO_SOLVER_URL           URL do solver_api (ex.: http://10.0.0.3:8765)
    GTO_SOLVER_CONCURRENCY   solves em paralelo (default 2, casar com MAX_SOLVES do solver)
"""
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

if __name__ == '__main__':
    # Importa o loop do app (define as rotas no import, mas o bloco __main__ do app NÃO roda aqui).
    from api.app import _solver_queue_worker_loop
    logging.getLogger(__name__).info("solver-consumer: iniciando consumidor event-driven da fila GTO")
    _solver_queue_worker_loop()
