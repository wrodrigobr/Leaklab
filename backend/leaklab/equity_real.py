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

_BARALHO = [r + s for r in '23456789TJQKA' for s in 'shdc']


def equity_river_vs_continuacao(hero, board):
    """Equity EXATA do hero no river contra a range que continua. None se não der para calcular.

    Por que existe (auditoria de 24/08): no river o board está completo, então não há
    "potencial de melhorar" — a mão é o que é, e a equity é ENUMERÁVEL (1.081 mãos de vilão,
    6 ms). O estimador servia uma tabela por classe de mão, calibrada para ruas com carta por
    vir: medido em 203 decisões de river do acervo, ele erra **0,20 em média** contra a conta
    exata, nas duas direções — `AcJc` em `KsKc7dKd7c` saía com 0,92 valendo 0,46, e `KcKs` em
    `9dKdQs4c2h` saía com 0,56 valendo 0,98. O flush máximo aparecia com 79%.

    "Continuação" é critério verificável, não palpite de range: o vilão tem PAR PRÓPRIO ou
    melhor (pareia o board, par de bolso, ou sobe de categoria). Uma primeira versão pedia só
    "melhora o board", o que é verdade para quase toda mão — e o número saía idêntico ao
    vs-random nos três controles, que foi como o defeito apareceu.

    Contra `vs_random` puro o conserto CRIARIA acusações novas (medido: 4 vereditos mudam,
    dois deles `standard` → `small_mistake`). Contra a range de continuação muda **zero** —
    é o número que a tela precisa sem que o motor passe a acusar quem não errou.
    """
    try:
        import eval7
    except Exception:                                          # noqa: BLE001
        return None
    hero = [str(c) for c in (hero or []) if c and len(str(c)) >= 2][:2]
    board = [str(c) for c in (board or []) if c and len(str(c)) >= 2][:5]
    if len(hero) != 2 or len(board) != 5:
        return None
    try:
        def forca(cs):
            return eval7.evaluate([eval7.Card(c) for c in cs])

        from leaklab.range_de_continuacao import categoria_do_board, continua
        mortas = set(hero) | set(board)
        livres = [c for c in _BARALHO if c not in mortas]
        board_cards = [eval7.Card(c) for c in board]
        cat_board = categoria_do_board(board_cards)
        meu = forca(hero + board)
        w = t = n = 0
        for v in combinations(livres, 2):
            # `com_draws=False`: no river nao ha carta por vir, projeto nao existe. O criterio
            # e o mesmo do multiway desde 27/08 (`range_de_continuacao`), que ate entao tinha
            # DUAS copias -- esta certa, e a de la errada em board pareado.
            if not continua((eval7.Card(v[0]), eval7.Card(v[1])), board_cards, cat_board,
                            com_draws=False):
                continue
            dele = forca(list(v) + board)
            n += 1
            if meu > dele:
                w += 1
            elif meu == dele:
                t += 1

        return round((w + 0.5 * t) / n, 4) if n else None
    except Exception:                                          # noqa: BLE001
        return None


# ── Flop e turn: a irmã da conta do river, onde ainda falta carta ───────────────────────────
#
# O river virou conta exata em 24/08 porque lá o board está completo. No flop e no turn ainda
# falta carta, e é por isso que o estimador por classe sobreviveu ali. Mas o defeito é o mesmo: a
# tabela é calibrada contra MÃO ALEATÓRIA, e o vilão que segue apostando não tem mão aleatória.
#
# O que muda em relação ao river:
#
#   • **`com_draws=True`.** No river não há carta por vir, então projeto não existe e continuar é
#     ter par próprio ou melhor. No flop e no turn um projeto de flush é uma mão que continua de
#     verdade, e excluí-la estreitaria a range do vilão para algo que ele não joga.
#
#   • **Turn enumera, flop amostra.** No turn falta uma carta: 44 saídas × os combos que
#     continuam é conta fechada. No flop faltam duas: C(45,2) = 990 saídas pelos mesmos combos
#     passa de um milhão de avaliações por decisão, e o acervo tem milhares. Então o flop é Monte
#     Carlo, com semente ESTÁVEL — `hash()` de string é salgado por processo e já fez a mesma
#     decisão sair `small_mistake` num boot e `standard` no outro.
#
# `None` sempre que não der para afirmar: sem eval7, sem board do tamanho certo, ou com a range de
# continuação vazia. Número ausente é honesto; número inventado com cara de medido não é.

_AMOSTRAS_FLOP = 8000      # PARES (saída, mão do vilão) sorteados no flop. Ver o teste,
                           # que mede o erro contra a conta densa em vez de confiar na fórmula.


def equity_flop_turn_vs_continuacao(hero, board, amostras: int = _AMOSTRAS_FLOP):
    """Equity do hero no flop/turn contra a range que CONTINUA neste board. `None` se não der."""
    try:
        import eval7
    except Exception:                                          # noqa: BLE001
        return None
    hero = [str(c) for c in (hero or []) if c and len(str(c)) >= 2][:2]
    board = [str(c) for c in (board or []) if c and len(str(c)) >= 2][:5]
    if len(hero) != 2 or len(board) not in (3, 4):
        return None

    try:
        from leaklab.range_de_continuacao import categoria_do_board, continua
        from leaklab.multiway_advisor import semente_estavel

        mortas = set(hero) | set(board)
        livres = [c for c in _BARALHO if c not in mortas]
        board_cards = [eval7.Card(c) for c in board]
        cat_board = categoria_do_board(board_cards)

        # A range do vilão é decidida no board ATUAL, não no board completo: é a informação que
        # ele tem quando decide continuar. Avaliar a continuação já com a saída na mesa seria dar
        # ao vilão uma carta que ele ainda não viu.
        vilao = [v for v in combinations(livres, 2)
                 if continua((eval7.Card(v[0]), eval7.Card(v[1])), board_cards, cat_board,
                             com_draws=True)]
        if not vilao:
            return None

        def forca(cs):
            return eval7.evaluate([eval7.Card(c) for c in cs])

        faltam = 5 - len(board)
        if faltam == 1:
            # Turn: uma carta por vir. 44 saidas x os combos que continuam e conta FECHADA, e
            # conta fechada nao tem erro de amostragem para explicar depois.
            w = t = n = 0
            for saida in livres:
                meu = forca(hero + [saida] + board)
                for v in vilao:
                    if saida in v:
                        continue
                    dele = forca(list(v) + [saida] + board)
                    n += 1
                    if meu > dele:
                        w += 1
                    elif meu == dele:
                        t += 1
        else:
            # Flop: duas cartas por vir. A 1a versao enumerava as saidas e varria TODOS os combos
            # em cada uma -- 1.200 x ~800 = perto de um milhao de avaliacoes, e medido: **8 a 10
            # segundos por decisao**. Com milhares de decisoes no acervo isso nao e lento, e
            # impossivel.
            #
            # Amostrar o PAR (saida, mao do vilao) de uma vez mede a mesma quantidade com duas
            # ordens de grandeza menos trabalho: o erro padrao de uma proporcao com N amostras e
            # ~0,5/raiz(N), entao 8.000 pares dao ~0,006 -- fino demais para mexer num veredito,
            # cujas faixas sao dezenas de vezes mais largas. O teste mede esse erro contra a
            # conta densa em vez de acreditar na formula.
            import random as _r
            rng = _r.Random(semente_estavel(tuple(hero), tuple(board), amostras))
            w = t = n = 0
            tentativas = 0
            while n < amostras and tentativas < amostras * 4:
                tentativas += 1
                saida = rng.sample(livres, 2)
                v = vilao[rng.randrange(len(vilao))]
                if v[0] in saida or v[1] in saida:
                    continue          # a saida pegou uma carta do vilao: esse par nao existe
                meu = forca(hero + saida + board)
                dele = forca(list(v) + saida + board)
                n += 1
                if meu > dele:
                    w += 1
                elif meu == dele:
                    t += 1
        return round((w + t * 0.5) / n, 4) if n else None
    except Exception:                                          # noqa: BLE001
        return None
