"""
demote_requeued_debt.py — rebaixa a dívida que entrou na fila com prioridade alta por engano.

    python scripts/demote_requeued_debt.py           # SIMULA (padrão)
    python scripts/demote_requeued_debt.py --exec    # aplica

── O que aconteceu ───────────────────────────────────────────────────────────────────────────

`requeue_board_hash_spots.py` enfileirou os spots do conserto com `priority = 9`, sob o
comentário "maior = depois". É o contrário: a fila é drenada com `ORDER BY priority DESC`, então
9 é a prioridade MAIS ALTA que existe na base (a função de prioridade do produto usa 5 a 8).

Resultado: centenas de spots de dívida passaram na frente de todo mundo, inclusive de quem tinha
acabado de subir um torneio e está olhando a tela esperando.

── Por que 9 é seguro de mirar ───────────────────────────────────────────────────────────────

Nada mais na base grava 9: o produto enfileira com 5 (flop), 6 (turn), 7 (river) e 8 (preflop).
Então `priority = 9` identifica exatamente os itens deste conserto, sem precisar de lista de
hashes nem de janela de tempo.

Só mexe no que está `pending`. O que já está `running` fica quieto: mudar prioridade de item em
execução não adianta nada e só arrisca confundir o worker.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _fetchall, _adapt

_ERRADA = 9
_CERTA = 1


def main():
    executar = '--exec' in sys.argv[1:]
    conn = get_conn()
    try:
        antes = _fetchall(conn, _adapt(
            "SELECT status, COUNT(*) AS n FROM gto_solver_queue WHERE priority = ? "
            "GROUP BY status"), (_ERRADA,))
        mapa = {r['status']: r['n'] for r in antes}
        pendentes = mapa.get('pending', 0)

        print(f'itens com prioridade {_ERRADA} (a errada): {mapa or "nenhum"}')
        if not pendentes:
            print('nada pendente para rebaixar.')
            return

        print(f'\na rebaixar: {pendentes} pendentes  {_ERRADA} -> {_CERTA}')
        if not executar:
            print('SIMULAÇÃO. Rode com --exec para aplicar.')
            return

        cur = conn.execute(_adapt(
            "UPDATE gto_solver_queue SET priority = ? WHERE priority = ? AND status = 'pending'"),
            (_CERTA, _ERRADA))
        conn.commit()
        print(f'rebaixados: {cur.rowcount if cur.rowcount is not None else pendentes}')

        depois = _fetchall(conn, _adapt(
            "SELECT priority AS p, COUNT(*) AS n FROM gto_solver_queue WHERE status = 'pending' "
            "GROUP BY priority ORDER BY priority DESC"), ())
        print('\nfila pendente por prioridade (atendida de cima para baixo):')
        for r in depois:
            print(f'  prioridade {r["p"]}: {r["n"]}')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
