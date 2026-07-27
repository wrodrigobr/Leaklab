"""
Consumidor das filas GTO (produção) — serviço dedicado, no lugar dos crons.

São DUAS filas, e este processo cuida das duas:

  · `gto_solver_queue`   — spots do solver postflop. Loop EVENT-DRIVEN
    (`_solver_queue_worker_loop`): acorda no instante que um spot é enfileirado, drena até
    esvaziar e resolve com concorrência = GTO_SOLVER_CONCURRENCY (casar com o MAX_SOLVES do
    solver). Sem ociosidade entre lotes.

  · `gto_hand_requests`  — pedidos de "resolver esta mão" (o botão do replay). Loop
    `_gto_hand_worker_loop`, em thread própria.

Por que a fila de MÃOS está aqui: os dois workers só sobem dentro do `if __name__ == '__main__'`
do app, que roda em `python api/app.py` (dev). Produção roda gunicorn, que IMPORTA o módulo e
nunca executa o `__main__` — então o pedido era enfileirado a cada request e ninguém drenava. O
jogador via "N spots ainda sendo validados pelo solver, suas estatísticas serão recomputadas
automaticamente" e nunca concluíam. Alguém já havia resolvido isso para a fila do solver com
este serviço; a fila de mãos ficou para trás e voltou a travar quatro vezes.

Podia ser mais um cron no host, mas cron pendente é o que já falhou aqui — este serviço, ao
contrário, JÁ roda. Pendurar o worker nele faz a correção valer com um deploy, sem configuração
manual, que é a diferença entre resolver e lembrar de resolver.

Aqui, e não no `web`: gunicorn sobe vários workers, e cada um rodaria a própria cópia do loop,
processando o mesmo pedido em paralelo. Um consumidor, um lugar.

Uso:
    python run_solver_consumer.py

Env relevantes:
    DATABASE_URL             Postgres de prod (sem isto usa SQLite local)
    GTO_SOLVER_URL           URL do solver_api (ex.: http://10.0.0.3:8765)
    GTO_SOLVER_CONCURRENCY   solves em paralelo (default 2, casar com MAX_SOLVES do solver)
    GTO_HAND_WORKER          '0' desliga o worker da fila de mãos (default: ligado)
"""
import os
import logging
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

if __name__ == '__main__':
    # Importa os loops do app (define as rotas no import, mas o bloco __main__ do app NÃO roda).
    from api.app import _solver_queue_worker_loop, _gto_hand_worker_loop
    log = logging.getLogger(__name__)

    if os.environ.get('GTO_HAND_WORKER', '1') != '0':
        # Thread separada de propósito: se a fila de mãos falhar, o solver segue drenando.
        threading.Thread(target=_gto_hand_worker_loop, daemon=True,
                         name='gto-hand-worker').start()
        log.info("solver-consumer: worker da fila de MÃOS (gto_hand_requests) iniciado")
    else:
        log.warning("solver-consumer: worker da fila de mãos DESLIGADO (GTO_HAND_WORKER=0) — "
                    "o aviso 'spots sendo validados' vai ficar preso no dashboard")

    log.info("solver-consumer: iniciando consumidor event-driven da fila do SOLVER")
    _solver_queue_worker_loop()
