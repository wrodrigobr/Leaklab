#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preenche `decisions.spot_assinatura` nas decisoes ja gravadas e, opcionalmente, grava o veredito
PROVISORIO por semelhanca dos torneios recentes que ainda esperam o solver (AY-28 passo 2).

SECO POR PADRAO. Sem `--aplicar` nao escreve nada, so mede.

Chama `leaklab.assinatura_do_spot.assinatura`, a MESMA funcao que `save_decisions` usa. Duas
rotinas de chave e a base fica com duas populacoes que nao casam (foi o bug do board no hash).

Uso:
    python scripts/backfill_spot_assinatura.py                      # so mede
    python scripts/backfill_spot_assinatura.py --aplicar            # grava as assinaturas
    python scripts/backfill_spot_assinatura.py --aplicar --provisorios 14
        # alem disso, grava o provisorio dos torneios importados nos ultimos 14 dias que
        # ainda tem spot pendente na fila: e o que faz a curva do admin comecar a andar
        # antes do proximo upload.
"""
import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from database.schema import get_conn                       # noqa: E402
from database.repositories import _adapt, _fetchall        # noqa: E402
from leaklab.assinatura_do_spot import assinatura          # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--aplicar', action='store_true', help='grava (sem isto, so mede)')
    ap.add_argument('--refazer', action='store_true', help='recalcula tambem as que ja tem assinatura')
    ap.add_argument('--provisorios', type=int, default=0, metavar='DIAS',
                    help='grava o veredito provisorio dos torneios importados nos ultimos DIAS com solve pendente')
    ap.add_argument('--lote', type=int, default=5000)
    args = ap.parse_args()

    conn = get_conn()
    try:
        cond = '' if args.refazer else ' AND spot_assinatura IS NULL'
        rows = _fetchall(conn, "SELECT id, street, position, stack_bb, facing_bet, board, hero_cards FROM decisions "
                               "WHERE street <> 'preflop' AND board IS NOT NULL" + cond) or []
        print('decisoes pos-flop candidatas: %d' % len(rows))
        motivos = Counter()
        pares = []
        for r in rows:
            a = assinatura(r['street'], r['position'], r['stack_bb'], r['facing_bet'], r['board'], r['hero_cards'])
            if a:
                pares.append((a, r['id']))
            else:
                motivos['sem board completo ou sem cartas'] += 1
        print('com assinatura: %d | sem: %s' % (len(pares), dict(motivos) or 0))
        if args.aplicar and pares:
            for i in range(0, len(pares), args.lote):
                conn.executemany(_adapt("UPDATE decisions SET spot_assinatura = ? WHERE id = ?"), pares[i:i + args.lote])
                conn.commit()
                print('  gravadas %d/%d' % (min(i + args.lote, len(pares)), len(pares)))
        elif pares:
            print('(seco: nada gravado; use --aplicar)')

        if args.provisorios:
            desde = (datetime.utcnow() - timedelta(days=args.provisorios)).strftime('%Y-%m-%d %H:%M:%S')
            tids = [r['tid'] for r in _fetchall(conn, _adapt("""
                SELECT DISTINCT t.id AS tid FROM tournaments t
                JOIN gto_tournament_queue gtq ON gtq.tournament_id = t.id
                JOIN gto_solver_queue sq ON sq.spot_hash = gtq.spot_hash
                WHERE t.imported_at >= ? AND sq.status IN ('pending', 'running')
            """), (desde,)) or []]
            print('torneios recentes com solve pendente: %d' % len(tids))
    finally:
        conn.close()

    if args.provisorios and args.aplicar:
        from leaklab.semelhanca import gravar_provisorios
        total = 0
        for tid in tids:
            n = gravar_provisorios(tid)
            total += n
        print('provisorios gravados: %d em %d torneios' % (total, len(tids)))
    elif args.provisorios:
        print('(seco: provisorios nao gravados; use --aplicar)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
