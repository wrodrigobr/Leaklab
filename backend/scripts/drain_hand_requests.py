"""
drain_hand_requests.py — drena a `gto_hand_requests` (pedidos de "resolver esta mão").

Por que existe: **o mesmo motivo do `drain_solver_queue.py`**. O worker
`_gto_hand_worker_loop` (app.py) só sobe dentro de `if __name__ == '__main__'`, ou seja em
`python api/app.py` (dev). Produção roda gunicorn, que IMPORTA o módulo e não executa o
`__main__` → o pedido é enfileirado a cada request, mas ninguém drena. O resultado que o
usuário vê: o dashboard anuncia "N spots ainda sendo validados pelo solver, suas estatísticas
serão recomputadas automaticamente conforme concluem" — e nunca concluem.

Alguém já tinha resolvido isso para a fila do SOLVER (`gto_solver_queue`) com um runner de cron;
a fila de MÃOS ficou sem o equivalente. Este script fecha a lacuna.

Sintoma no banco: linha em `gto_hand_requests` com `status='pending'` e
`decisions_found`/`decisions_done` NULOS (o worker nunca tocou nela). Diagnóstico:
`python -m scripts.diag_pending_gto`.

Uso:
    python -m scripts.drain_hand_requests                 # drena até 10
    python -m scripts.drain_hand_requests 25              # drena até 25
    cd ~/app && docker compose exec web python -m scripts.drain_hand_requests

Cron sugerido (ao lado do drain_solver_queue):
    */5 * * * * cd ~/app && docker compose exec -T web python -m scripts.drain_hand_requests
"""
import os
import sys

# Garante a raiz do backend no path — `python scripts/x.py` só põe scripts/ no path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.repositories import get_pending_gto_hand_requests, update_gto_hand_request


def main():
    try:
        limite = int(sys.argv[1])
    except (IndexError, ValueError):
        limite = 10
    limite = max(1, min(limite, 50))

    pendentes = get_pending_gto_hand_requests(limit=limite)
    if not pendentes:
        print("Fila vazia: nenhum pedido pendente em gto_hand_requests.")
        return

    # Import tardio: `api.app` cria o Flask app no import, então só pagamos esse custo quando
    # há trabalho de verdade (o cron roda a cada 5 min e quase sempre encontra fila vazia).
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'api'))
    from app import _process_gto_hand_request

    print(f"{len(pendentes)} pedido(s) pendente(s). Processando...\n")
    ok = enfileirados = falhou = 0
    for req in pendentes:
        rid = req['id']
        try:
            status, err, n_done, n_queued = _process_gto_hand_request(dict(req))
            update_gto_hand_request(rid, status, decisions_done=n_done, error_msg=err)
            # `solver_queued` NÃO é falha: as decisões foram para a `gto_solver_queue`, que tem
            # cron própria drenando. Marcar isso como erro faria a saída do cron mentir e
            # esconderia as falhas de verdade no meio do ruído.
            marca = '✔' if status == 'done' else '→' if status == 'solver_queued' else '✖'
            print(f"  {marca} id={rid} mão={req.get('hand_id')} → {status} "
                  f"(decisões={n_done} enfileiradas={n_queued})"
                  + (f" erro={str(err)[:80]}" if err else ""))
            ok           += 1 if status == 'done' else 0
            enfileirados += 1 if status == 'solver_queued' else 0
            falhou       += 1 if status not in ('done', 'solver_queued') else 0
        except Exception as e:
            # Marca o pedido como erro em vez de deixá-lo pendente para sempre: pedido preso é
            # o que faz o aviso do dashboard mentir. Erro é um estado honesto e visível.
            falhou += 1
            print(f"  ✖ id={rid} exceção: {type(e).__name__}: {str(e)[:100]}")
            try:
                update_gto_hand_request(rid, 'error', error_msg=f"{type(e).__name__}: {e}"[:400])
            except Exception:
                print(f"     (não consegui marcar id={rid} como error)")
    print(f"\nConcluídos: {ok} | enfileirados no solver: {enfileirados} | com erro: {falhou}")
    if enfileirados:
        print("Os enfileirados seguem na gto_solver_queue — quem termina é o "
              "drain_solver_queue (cron).")


if __name__ == '__main__':
    main()
