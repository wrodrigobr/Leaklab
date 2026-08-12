# -*- coding: utf-8 -*-
"""Purga ESCOPADA dos nós solver_cli com strategy_json vazia + reset da fila para re-solve.

Achado no ataque aos 7 vanished (12/08): 45 nós `done` com strategy_json NULL — solves que
falharam e foram gravados como prontos. O nó vazio ocupa o hash (reenqueue diz "coberto") e o
lookup pode cair num nó vizinho errado. O guarda novo em insert_gto_nodes impede a reentrada;
este script remove o estoque e devolve os spots à fila.

Escopo: SÓ nós source='solver_cli' com strategy_json NULL/''. Nunca toca gto_wizard nem nós
com estratégia. As árvores hand-aware órfãs desses nós vão junto (tree_hash sem outro dono).

Uso:
    python -m scripts.cleanup_empty_solver_nodes           # dry-run
    python -m scripts.cleanup_empty_solver_nodes --apply
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn

APPLY = '--apply' in sys.argv


def main():
    conn = get_conn()
    alvos = [dict(r) for r in conn.execute(
        "SELECT spot_hash, tree_hash FROM gto_nodes "
        "WHERE source = 'solver_cli' AND (strategy_json IS NULL OR strategy_json = '')"
    ).fetchall()]
    print(f'nós vazios: {len(alvos)}')
    if not alvos:
        conn.close()
        return

    hashes = [a['spot_hash'] for a in alvos]
    # Árvores órfãs: tree_hash referenciado SÓ por nós da lista.
    trees = {a['tree_hash'] for a in alvos if a.get('tree_hash')}
    orfas = []
    for th in trees:
        donos = conn.execute(
            "SELECT COUNT(*) AS n FROM gto_nodes WHERE tree_hash = ? AND spot_hash NOT IN (%s)"
            % ','.join('?' * len(hashes)), tuple([th] + hashes)).fetchone()
        if not dict(donos)['n']:
            orfas.append(th)

    fila = conn.execute(
        "SELECT status, COUNT(*) AS n FROM gto_solver_queue WHERE spot_hash IN (%s) GROUP BY status"
        % ','.join('?' * len(hashes)), tuple(hashes)).fetchall()
    print('fila dos alvos:', {dict(r)['status']: dict(r)['n'] for r in fila})
    print(f'árvores órfãs a remover: {len(orfas)}')

    if not APPLY:
        print('\nDRY-RUN (use --apply)')
        conn.close()
        return

    ph = ','.join('?' * len(hashes))
    conn.execute(f"DELETE FROM gto_nodes WHERE spot_hash IN ({ph}) "
                 "AND source = 'solver_cli' AND (strategy_json IS NULL OR strategy_json = '')",
                 tuple(hashes))
    if orfas:
        pht = ','.join('?' * len(orfas))
        conn.execute(f"DELETE FROM gto_tree_strategies WHERE tree_hash IN ({pht})", tuple(orfas))
    # Reset da fila: o spot volta a pending e o consumer re-solva com o guarda novo.
    conn.execute(f"UPDATE gto_solver_queue SET status = 'pending' WHERE spot_hash IN ({ph})",
                 tuple(hashes))
    conn.commit()

    sobrou = dict(conn.execute(
        "SELECT COUNT(*) AS n FROM gto_nodes "
        "WHERE source = 'solver_cli' AND (strategy_json IS NULL OR strategy_json = '')"
    ).fetchone())['n']
    pend = dict(conn.execute(
        f"SELECT COUNT(*) AS n FROM gto_solver_queue WHERE status='pending' AND spot_hash IN ({ph})",
        tuple(hashes)).fetchone())['n']
    print(f'APLICADO: nós vazios restantes={sobrou} (esperado 0), re-enfileirados={pend}')
    conn.close()

    # Acorda o consumer sem esperar o timer de 60s.
    try:
        from leaklab.solver_signals import solver_queue_event
        solver_queue_event.set()
    except Exception:
        pass


if __name__ == '__main__':
    main()
