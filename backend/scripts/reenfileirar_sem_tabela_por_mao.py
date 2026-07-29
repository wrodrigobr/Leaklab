# -*- coding: utf-8 -*-
"""Reenfileira no solver os spots postflop cujo nó existe mas NÃO tem tabela por mão.

── Por que existe ────────────────────────────────────────────────────────────────────────────

Medido em 2026-07-29: das decisões postflop sem `ev_loss_bb`, 131 spots DISTINTOS têm um nó em
`gto_nodes` mas sem `tree_hash` — foram solvados antes de o binário que popula
`gto_tree_strategies` existir, ou com o parâmetro antigo. Re-solvar esses 131 (e não os outros
411, cuja causa é a mão do herói estar fora da range modelada — resolver não muda isso) é o que
de fato preenche EV que falta hoje.

Usa o MESMO caminho de payload de `_enfileirar_spot_da_decisao` (api/app.py): mesma resolução de
ranges (`resolve_solver_ranges`), mesmo corte de board por street, mesma prioridade por street.
Reimplementar aqui seria a duplicação que este projeto já pagou caro uma vez.

    python scripts/reenfileirar_sem_tabela_por_mao.py                # seco: mede e lista
    python scripts/reenfileirar_sem_tabela_por_mao.py --enfileirar   # enfileira de verdade
    python scripts/reenfileirar_sem_tabela_por_mao.py --enfileirar --limite 20   # lote pequeno
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _cartas(v):
    if isinstance(v, (list, tuple)):
        return list(v)
    s = str(v or '')
    return [s[:2], s[2:]] if len(s) == 4 else []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--enfileirar', action='store_true')
    ap.add_argument('--limite', type=int, default=1000)
    args = ap.parse_args()

    from database.schema import get_conn
    from database.repositories import _adapt, enqueue_solver_spot
    from leaklab.gto_utils import compute_spot_hash, board_for_street
    from leaklab.gto_solver import (_priority, _solver_params_for_stack,
                                    resolve_solver_ranges, vale_enfileirar_postflop)

    conn = get_conn()
    try:
        rows = conn.execute(_adapt(
            "SELECT id, street, position, vs_position, board, hero_cards, stack_bb, "
            "       facing_bet, pot_size, action_taken "
            "  FROM decisions "
            " WHERE street IN (?,?,?) AND gto_label IS NOT NULL AND ev_loss_bb IS NULL"),
            ('flop', 'turn', 'river')).fetchall()
    finally:
        conn.close()

    vistos = {}   # spot_hash -> payload já montado (dedup: várias decisões, o mesmo spot)
    sem_no = mao_provavel_fora = ja_tem_tabela = gate_recusa = 0

    for row in rows:
        d = dict(row)
        board = d['board']
        if isinstance(board, str):
            try:
                board = json.loads(board)
            except ValueError:
                board = []
        hero = _cartas(d.get('hero_cards'))
        if not hero or not board:
            continue

        street = d['street']
        b = board_for_street(board, street)
        pos = (d.get('position') or '').upper()
        vs = (d.get('vs_position') or '').upper()
        stack = float(d.get('stack_bb') or 0)
        facing = float(d.get('facing_bet') or 0)
        h = compute_spot_hash(street, pos, b, hero, stack, facing)

        conn = get_conn()
        try:
            node = conn.execute(_adapt(
                "SELECT tree_hash FROM gto_nodes WHERE spot_hash = ? LIMIT 1"), (h,)).fetchone()
        finally:
            conn.close()
        if not node:
            sem_no += 1
            continue
        if dict(node).get('tree_hash'):
            ja_tem_tabela += 1   # sem EV por outro motivo (mão fora da range) — não é este script
            continue

        if h in vistos:
            continue   # já montado por outra decisão do mesmo spot

        if not vale_enfileirar_postflop(pos, vs, facing):
            gate_recusa += 1
            continue

        prm = _solver_params_for_stack(stack)
        ipr, oopr, hip = resolve_solver_ranges(pos, vs, stack)
        payload = json.dumps({
            'street': street, 'board': b, 'position': pos,
            'hero_hand': hero, 'hero_stack_bb': stack, 'facing_size_bb': facing,
            'oop_range': oopr, 'ip_range': ipr, 'hero_is_ip': hip,
            'pot_bb': float(d.get('pot_size') or facing * 2 + 2 or 4.0),
            'effective_stack_bb':        prm['effective_stack_bb'],
            'max_iterations':            prm['max_iterations'],
            'target_exploitability_pct': prm['target_exploitability_pct'],
        }, sort_keys=True)
        vistos[h] = (payload, _priority(street))

    print('spots distintos sem tabela por mão : %d' % len(vistos))
    print('  sem nó (fora deste script)       : %d' % sem_no)
    print('  já tem tabela (fora deste script): %d' % ja_tem_tabela)
    print('  recusados pelo gate hero-IP       : %d' % gate_recusa)

    if not args.enfileirar:
        print('\nmodo seco: nada enfileirado (use --enfileirar)')
        return 0

    lote = list(vistos.items())[:args.limite]
    entrou = 0
    for h, (payload, prio) in lote:
        if enqueue_solver_spot(h, payload, priority=prio):
            entrou += 1
    print('\nenfileirados: %d de %d (limite=%d)' % (entrou, len(lote), args.limite))
    return 0


if __name__ == '__main__':
    sys.exit(main())
