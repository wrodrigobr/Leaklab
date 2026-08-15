# -*- coding: utf-8 -*-
"""Experimento SB x BB: a carta ring atual contra os nos GW recapturados em 15/08.

A politica do overlay ring e preenche-buraco ("onde ja existe carta, este caminho nao
encosta — trocar a fonte mexeria em veredito sem experimento que diga qual esta certa",
`_preenche_buraco_com_ring`). Este script E o experimento: para cada decisao real de BB
contra open unico do SB em mesa cheia, grada pela carta do no GW (com o grader do proprio
motor, nao uma reimplementacao) e compara com o que esta GRAVADO pela carta atual.

Sem --apply nao existe: e medicao pura, nada e escrito.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.schema import get_conn, init_db                      # noqa: E402
from leaklab.preflop_gto_ranges import (                           # noqa: E402
    _grade_por_no_capturado, _hu_no_mais_proximo, _load_ring)

_RANKS = '23456789TJQKA'


def hand_type(cards: str) -> str | None:
    """'JhJs' / 'Jh Js' -> 'JJ'; 'Ah5d' -> 'A5o'. A licao do 28/07: hero_cards pode vir
    COLADO — split() por espaco devolvia a string inteira e todo hash saia errado."""
    s = (cards or '').replace(' ', '')
    if len(s) != 4:
        return None
    r1, n1, r2, n2 = s[0].upper(), s[1], s[2].upper(), s[3]
    if r1 not in _RANKS or r2 not in _RANKS:
        return None
    hi, lo = sorted((r1, r2), key=_RANKS.index, reverse=True)
    if hi == lo:
        return hi + lo
    return hi + lo + ('s' if n1.lower() == n2.lower() else 'o')


def main() -> int:
    init_db()
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT d.id, d.tournament_id, d.hand_id, d.hero_cards, d.action_taken,
               d.label, d.gto_label, d.gto_action, d.best_action,
               d.stack_bb, d.effective_stack_bb, d.num_players
          FROM decisions d
         WHERE d.street = 'preflop'
           AND d.position = 'BB'
           AND d.vs_position = 'SB'
           AND d.num_players > 2
           AND d.preflop_raises_faced = 1
           AND (d.hero_was_aggressor IS NULL OR d.hero_was_aggressor IN (0, false))
           AND (d.facing_limp IS NULL OR d.facing_limp IN (0, false))
        """
    ).fetchall()

    por_depth = _load_ring().get(('vs_rfi', 'BB', 'SB')) or {}
    print(f'decisoes BB vs open de SB (ring): {len(rows)}')
    print(f'nos GW (vs_rfi, BB, SB): {sorted(por_depth)}\n')
    if not por_depth:
        print('SEM NOS — o acervo novo nao esta neste ambiente. Nada a medir.')
        return 1

    sem_no = fora_range = iguais = 0
    divergentes = []
    for r in rows:
        d = dict(r)
        stack = float(d.get('effective_stack_bb') or d.get('stack_bb') or 0)
        depth, no = _hu_no_mais_proximo(por_depth, stack)
        if no is None:
            sem_no += 1
            continue
        mao = hand_type(d.get('hero_cards') or '')
        if not mao:
            fora_range += 1
            continue
        base: dict = {'scenario': 'vs_rfi'}
        _grade_por_no_capturado(base, no, depth, mao, d.get('action_taken') or '',
                                fonte='gw_ring_har')
        if not base.get('available'):
            fora_range += 1
            continue
        gw_top = (base.get('recommended_actions') or [None])[0]
        carta_top = d.get('gto_action') or d.get('best_action')
        gw_quality = base.get('action_quality')
        if gw_top == carta_top:
            iguais += 1
            continue
        divergentes.append({
            'id': d['id'], 'tid': d['tournament_id'], 'hand': d['hand_id'], 'mao': mao,
            'stack': round(stack, 1), 'depth': depth, 'jogou': d.get('action_taken'),
            'carta_diz': carta_top, 'gw_diz': gw_top,
            'label_atual': d.get('label'), 'gto_label_atual': d.get('gto_label'),
            'gw_quality': gw_quality,
        })

    print(f'com no na janela de 25%: {len(rows) - sem_no}  |  sem no (26-37bb etc.): {sem_no}')
    print(f'mao fora da range do no / indecodificavel: {fora_range}')
    print(f'recomendacao IGUAL (carta ~ GW): {iguais}')
    print(f'recomendacao DIVERGE: {len(divergentes)}\n')
    for v in divergentes:
        muda_veredito = ''
        # O flip que importa: a carta atual aprovou o que o GW chama de leak, ou vice-versa.
        if v['jogou'] == v['carta_diz'] and v['gw_quality'] in ('major_leak', 'minor_leak'):
            muda_veredito = '  << carta APROVOU o que o GW acusa'
        if v['jogou'] == v['gw_diz'] and (v['label_atual'] or '') in (
                'small_mistake', 'clear_mistake'):
            muda_veredito = '  << carta ACUSA o que o GW aprova'
        print(f"  tid={v['tid']} hand={v['hand']} {v['mao']:4s} {v['stack']:5.1f}bb "
              f"(no {v['depth']}) jogou={v['jogou']:5s} carta={v['carta_diz']} "
              f"gw={v['gw_diz']} label={v['label_atual']}/{v['gto_label_atual']}"
              f"{muda_veredito}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
