#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reenfileira os spots postflop cujas decisoes estao SEM COBERTURA e que nunca chegaram ao solver.

SECO POR PADRAO. Sem `--enfileirar` nao escreve nada, so mede.

── O diagnostico que originou (medido em producao, 2026-07-30) ────────────────────────────────────

    decisoes postflop sem gabarito ........ 1066
      ja passaram pela fila do solver .....  178
      NUNCA foram enfileiradas ............  888   <-- este script
    fila do solver ........................ 4522 done, 196 failed, ZERO pendente

Ou seja: nao e backlog nem capacidade. A fila esta vazia porque o pedido nunca foi feito.

**Todas as 888 passariam pelo gate HOJE.** Zero recusadas. Duas causas, e as duas ja foram
consertadas em outro lugar:

  · 481 sao de heroi IP. O gate `vale_enfileirar_postflop` recusa esse caso enquanto
    `TEXAS_HERO_IP` estiver desligada — e essa flag ficou SETE SEMANAS em zero por ter se perdido
    numa migracao de infra. Hoje esta em 1 (medido no processo, nao no arquivo).
  · 407 sao de heroi OOP, que o gate sempre aceitou. A causa provavel e o bug do board no hash:
    foram enfileiradas sob a chave de 5 cartas antes do conserto de 28/07, entao a fila tem
    linha, mas sob um hash que ninguem mais consulta.

Nos dois casos o conserto e o mesmo, e e este script.

── O que ele NAO faz ──────────────────────────────────────────────────────────────────────────────

Nao monta payload proprio: chama `gto_solver.montar_payload_postflop`, a mesma funcao que o
enfileiramento do upload usa. Isso importa porque a montagem ja existiu em tres copias e elas ja
discordaram — uma mandava as ranges trocadas, e o no gravado descrevia a decisao do VILAO.

Nao apaga nada. Nao toca `gto_nodes` nem as ranges preflop.

Uso:
    python scripts/reenfileirar_postflop_sem_cobertura.py                    # so mede
    python scripts/reenfileirar_postflop_sem_cobertura.py --enfileirar
    python scripts/reenfileirar_postflop_sem_cobertura.py --enfileirar --limite 50
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from database.schema import get_conn                              # noqa: E402
from database.repositories import _adapt, enqueue_solver_spot     # noqa: E402
from leaklab.gto_solver import montar_payload_postflop, _priority  # noqa: E402


def _board(valor):
    if not valor:
        return []
    if isinstance(valor, list):
        return valor
    try:
        v = json.loads(valor)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--enfileirar', action='store_true', help='grava (sem isto, so mede)')
    ap.add_argument('--limite', type=int, default=0, help='0 = todos')
    args = ap.parse_args()

    conn = get_conn()
    try:
        rows = conn.execute(_adapt(
            "SELECT d.id, d.street, d.position, d.vs_position, d.board, d.hero_cards, "
            "       d.stack_bb, d.facing_bet, d.pot_size, d.tournament_id "
            "  FROM decisions d "
            " WHERE d.street IN (?,?,?) "
            "   AND (d.gto_label IS NULL OR d.gto_label = ?) "
            "   AND NOT EXISTS (SELECT 1 FROM gto_solver_queue s WHERE s.spot_hash = d.spot_hash) "
            " ORDER BY d.id"), ('flop', 'turn', 'river', 'uncovered')).fetchall()
    finally:
        conn.close()

    print(f'decisoes postflop sem cobertura e sem passagem pela fila: {len(rows)}')

    # Dedup por spot: varias decisoes distintas caem no MESMO spot, e enfileirar o mesmo hash N
    # vezes so enche a fila. O que se conta e SPOT, nao decisao — reportar decisao daria a
    # impressao de um trabalho maior do que existe.
    porspot = {}
    motivos = Counter()
    for r in rows:
        d = dict(r)
        montado = montar_payload_postflop(
            street=d['street'], position=d['position'], vs_position=d['vs_position'],
            board=_board(d['board']), hero_cards=d['hero_cards'],
            stack_bb=d['stack_bb'], facing_bb=d['facing_bet'], pot_bb=d['pot_size'])
        if not montado:
            motivos['recusado pelo gate ou sem insumo (cartas/posicao)'] += 1
            continue
        h, payload = montado
        if h not in porspot:
            porspot[h] = (payload, d['street'], d['tournament_id'])

    print(f'  spots DISTINTOS a enfileirar: {len(porspot)}')
    for k, v in motivos.most_common():
        print(f'    fora: {k}: {v}')
    por_street = Counter(v[1] for v in porspot.values())
    for st, n in por_street.most_common():
        print(f'    {st}: {n} spots')

    if not args.enfileirar:
        print('\nSECO — nada enfileirado. Rode com --enfileirar para escrever.')
        return 0

    itens = list(porspot.items())
    if args.limite:
        itens = itens[:args.limite]

    ok = 0
    for h, (payload, street, tid) in itens:
        if enqueue_solver_spot(h, payload, priority=_priority(street), tournament_id=tid):
            ok += 1

    # CONFERENCIA EXPLICITA: `enqueue_solver_spot` devolve False silenciosamente quando o spot ja
    # existe na fila. Sem reler o banco, "enfileirei N" seria a mesma frase para sucesso e para
    # nao ter feito nada.
    conn = get_conn()
    try:
        pend = conn.execute(
            "SELECT COUNT(*) AS n FROM gto_solver_queue WHERE status = 'pending'").fetchone()['n']
    finally:
        conn.close()
    print(f'\nENFILEIRADOS {ok} de {len(itens)}. Conferido no banco: {pend} pendente(s) na fila.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
