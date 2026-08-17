# -*- coding: utf-8 -*-
"""Equity REAL do herói contra a mão que o vilão MOSTROU — fato do showdown, não estimativa.

Nasceu da validação de 17/08 (`scripts/validar_equity_com_reveals.py`, 1.082 medições):
a equity estimada é calibrada na média mas tem cauda gorda por street (gap p90 river +0,58).
A equity real vs a mão revelada é o antídoto pedagógico na REVISÃO: "você pagou o turn com
5% contra a mão dele". É CONTEXTO de revisão, nunca insumo de veredito — julgar a decisão
pela mão mostrada é resulting, o erro que a plataforma existe para combater. O veredito
continua vindo da range (GTO).

Fonte única do cálculo: o medidor e o /replay importam daqui (regra 5 do CLAUDE.md).
"""
from __future__ import annotations

from itertools import combinations

N_BOARD_POR_STREET = {'preflop': 0, 'flop': 3, 'turn': 4, 'river': 5}


def cartas(txt) -> list:
    """'Jd6d' / 'Jd 6d' / ['Jd','6d'] / '["Kh", "Qh"]' -> lista de cartas.

    Três dialetos REAIS do banco: `hero_cards` vem COLADO (lição de 28/07), `reveals` vem
    lista, e `decisions.board` vem string JSON — descoberto em 17/08, quando 108 decisões
    sumiram caladas do medidor até a contabilidade de descartes apontar o board."""
    if isinstance(txt, list):
        s = ''.join(str(c) for c in txt)
    else:
        s = (txt or '').strip()
        if s.startswith('['):
            try:
                import json
                return [str(c) for c in json.loads(s)]
            except Exception:
                return []
        s = s.replace(' ', '')
    return [s[i:i + 2] for i in range(0, len(s) - 1, 2)]


def equity_exata(hero: list, vilao: list, board: list):
    """Equity EXATA de hero vs UMA mão conhecida, enumerando todos os runouts (eval7).

    None quando o dado não presta (carta repetida, formato inválido) — silêncio honesto,
    nunca palpite. Custo: flop = C(45,2) = 990 runouts, imperceptível em C."""
    import eval7
    conhecidas = list(hero) + list(vilao) + list(board)
    if len(set(conhecidas)) != len(conhecidas):
        return None
    try:
        h = [eval7.Card(c) for c in hero]
        v = [eval7.Card(c) for c in vilao]
        b = [eval7.Card(c) for c in board]
    except Exception:
        return None
    resto = [c for c in eval7.Deck().cards if str(c) not in conhecidas]
    faltam = 5 - len(b)
    ganha = empata = total = 0
    for extra in (combinations(resto, faltam) if faltam else ((),)):
        full = b + list(extra)
        sh, sv = eval7.evaluate(h + full), eval7.evaluate(v + full)
        total += 1
        if sh > sv:
            ganha += 1
        elif sh == sv:
            empata += 1
    return (ganha + 0.5 * empata) / total if total else None


def equity_real_por_street(hero_cards, vilao_cards, board) -> dict:
    """{street: equity} para as streets que o board alcança. Preflop pela matriz 169x169 do
    motor (mesma fonte do resto do sistema); postflop por enumeração exata."""
    from leaklab.equity import equity_vs_hand
    from leaklab.gto_utils import hand_to_type
    hero, vilao, b = cartas(hero_cards), cartas(vilao_cards), cartas(board)
    if len(hero) != 2 or len(vilao) != 2:
        return {}
    out: dict = {}
    pf = equity_vs_hand(hand_to_type(hero) or '', hand_to_type(vilao) or '')
    if pf is not None:
        out['preflop'] = round(float(pf), 4)
    for street, n in (('flop', 3), ('turn', 4), ('river', 5)):
        if len(b) < n:
            break
        e = equity_exata(hero, vilao, b[:n])
        if e is not None:
            out[street] = round(e, 4)
    return out


def revelador_unico(reveals: dict, hero_name: str):
    """(nome, cartas) quando EXATAMENTE UM jogador além do herói revelou — o único
    pareamento em que "vs a mão mostrada" significa alguma coisa. Senão, None."""
    outros = {n: c for n, c in (reveals or {}).items() if n != (hero_name or '') and c}
    if len(outros) != 1:
        return None
    (nome, c), = outros.items()
    c = cartas(c)
    return (nome, c) if len(c) == 2 else None
