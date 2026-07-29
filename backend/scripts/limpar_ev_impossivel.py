# -*- coding: utf-8 -*-
"""Anula `ev_loss_bb` postflop fisicamente impossível: perda maior que o próprio stack.

── Por que existe ────────────────────────────────────────────────────────────────────────────

Ninguém perde mais bb do que tem na mesa. É aritmética, não calibração — não depende de equity,
de pote solvado nem de nenhuma heurística. Um valor assim não é "impreciso", é inválido.

Encontrado ao conferir o backfill do EV (2026-07-29): 9 decisões postflop com `ev_loss_bb`
maior que `stack_bb`, a pior dizendo que foldar custou 41.604bb num spot de 11,7bb. A causa é a
conhecida: o `ev_loss_bb` do solver vem na escala do POTE COM QUE O NÓ FOI SOLVADO, e o
`spot_hash` não inclui o pote — um nó solvado num pote pequeno servido a um spot grande devolve
um número noutra escala.

── Anula, não corrige ────────────────────────────────────────────────────────────────────────

O pote solvado não é gravado em lugar nenhum, então não há como reescalar. NULL é a resposta
honesta: "não sabemos quanto custou". O veredito (`gto_label`) NÃO é tocado — ele não depende
do número, e trocá-lo por dedução de um script de limpeza seria o conserto pior que o bug.

    python scripts/limpar_ev_impossivel.py              # seco
    python scripts/limpar_ev_impossivel.py --escrever
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main() -> int:
    ap = argparse.ArgumentParser(description='Anula EV postflop impossível.')
    ap.add_argument('--escrever', action='store_true')
    args = ap.parse_args()

    from database.schema import get_conn
    from database.repositories import _adapt

    conn = get_conn()
    try:
        alvos = conn.execute(_adapt(
            "SELECT id, street, stack_bb, action_taken, ev_loss_bb, gto_label "
            "  FROM decisions "
            " WHERE street IN (?,?,?) AND ev_loss_bb IS NOT NULL "
            "   AND stack_bb IS NOT NULL AND ev_loss_bb > stack_bb "
            " ORDER BY ev_loss_bb DESC"),
            ('flop', 'turn', 'river')).fetchall()
    finally:
        conn.close()

    print('decisoes com EV maior que o proprio stack: %d' % len(alvos))
    for r in alvos:
        d = dict(r)
        print('   id=%-7s %-6s stack=%-7s acao=%-6s EV=%-11s veredito=%s' % (
            d['id'], d['street'], d['stack_bb'], d['action_taken'], d['ev_loss_bb'],
            d['gto_label']))

    if not args.escrever:
        print('\nmodo seco: nada anulado (use --escrever)')
        return 0

    conn = get_conn()
    try:
        for r in alvos:
            # `ev_loss_source` também volta a NULL: manter 'solver_hand' num campo vazio
            # afirmaria uma procedência para um número que não existe mais.
            conn.execute(_adapt(
                "UPDATE decisions SET ev_loss_bb = NULL, ev_loss_source = NULL WHERE id = ?"),
                (dict(r)['id'],))
        conn.commit()
    finally:
        conn.close()
    print('\n%d anulado(s). Veredito intocado.' % len(alvos))
    return 0


if __name__ == '__main__':
    sys.exit(main())
