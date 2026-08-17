"""range_classes.py — painel "range por classe de mão" do treino postflop.

A `hand_table` de cada árvore solvada traz TODAS as mãos do board com frequência por ação
(mediana 462/árvore). Este módulo agrupa essas mãos por CLASSE (trinca+, dois pares, top pair,
draw...) e agrega a estratégia ponderada pelo peso de cada combo na range — é o painel que o
jogador usa para entender "o que a range faz aqui", não só "o que a minha mão faz".

Computável do que já existe: nenhum solve novo, nenhuma fonte nova. A leitura é a MESMA da
seleção e da correção (`_tabela_da_arvore`), e a tradução rótulo→família é a MESMA do menu
(`_familias_da_linha`) — se o painel lesse por outra porta, seleção e painel poderiam divergir
sobre a mesma árvore, que é exatamente a família de bug que a regra 5 do CLAUDE.md cobra.

Display-only por contrato: nada daqui alimenta veredito, score ou SRS.
"""
from __future__ import annotations

from typing import Optional

from .street_math_engine import _RANK_ORD

# Ordem de exibição, da mais forte para a mais fraca. Mutuamente exclusivas: toda mão servível
# cai em exatamente UMA — o peso das classes soma 100% e o painel é conferível de cabeça.
CLASSES = ('monster', 'trips', 'two_pair', 'overpair', 'top_pair',
           'middle_pair', 'weak_pair', 'no_made')

# Draws são SOBREPOSTOS de propósito (top pair + flush draw conta nos dois): a pergunta que o
# jogador faz é "quanto da range tem draw", e essa pergunta atravessa as classes de mão feita.
DRAWS = ('flush_draw', 'oesd', 'gutshot')

_MONSTROS = ('Straight Flush', 'Quads', 'Full House', 'Flush', 'Straight')


def classe_da_mao(mao: str, board: list) -> Optional[str]:
    """Classe da mão contra o board, hero-cêntrica: o que os RANKS DO HERO contribuem decide,
    não só o handtype das 5 melhores cartas — num board pareado, o eval7 diz "Two Pair" para
    quem tem um par só, e "Trips" para quem não tem nada. `None` quando não dá para avaliar."""
    try:
        import eval7
    except Exception:
        return None
    try:
        hero = [mao[i:i + 2] for i in range(0, len(mao), 2)][:2]
        brd = [str(c) for c in (board or []) if c and len(str(c)) >= 2][:5]
        if len(hero) != 2 or len(brd) < 3:
            return None
        ht = eval7.handtype(eval7.evaluate([eval7.Card(c) for c in hero + brd]))
        hr = sorted((_RANK_ORD.index(c[0]) for c in hero if c[0] in _RANK_ORD), reverse=True)
        br = sorted((_RANK_ORD.index(c[0]) for c in brd if c[0] in _RANK_ORD), reverse=True)
        if len(hr) < 2 or not br:
            return None
        bmax = br[0]
        pocket = hr[0] == hr[1]
        pareadas = sorted({r for r in hr if r in br}, reverse=True)

        if ht in _MONSTROS:
            return 'monster'
        if ht in ('Trips',):
            # trinca DO HERO (set ou par com board pareado); board com trinca e o hero de
            # kicker não é "trips" na leitura de range
            return 'trips' if (pocket or pareadas) else 'no_made'
        if ht == 'Two Pair':
            if len(pareadas) == 2:
                return 'two_pair'
            # board pareado + par do hero: a leitura de range é a do PAR do hero
            ht = 'Pair'
        if ht == 'Pair' and (pocket or pareadas):
            if pocket and not pareadas:
                return 'overpair' if hr[0] > bmax else (
                    'middle_pair' if len(br) > 1 and hr[0] > br[1] else 'weak_pair')
            if pareadas:
                pr = pareadas[0]
                if pr >= bmax:
                    return 'top_pair'
                return 'middle_pair' if pr > br[-1] else 'weak_pair'
        return 'no_made'
    except Exception:
        return None


def range_por_classe(tree_hash: str, board: list, enfrentando: bool) -> Optional[dict]:
    """Agrega a hand_table da árvore por classe × família de ação, ponderada pelo peso.

    `None` quando a árvore não existe ou não rende linha classificável — o chamador esconde o
    painel em vez de mostrar um painel vazio fingindo ser dado.
    """
    from .trainer_pool import _tabela_da_arvore, _familias_da_linha
    from .draw_detector import detect_draws

    acoes, tabela = _tabela_da_arvore(tree_hash)
    if not acoes or not tabela:
        return None

    cartas_board = {str(c) for c in (board or [])}
    com_draws = len(cartas_board) < 5          # river não tem draw: carta por vir é zero

    familias: list = []                        # ordem de primeira aparição, vocabulário do menu
    por_classe: dict = {c: {'peso': 0.0, 'combos': 0, 'freq': {}} for c in CLASSES}
    por_draw: dict = {d: {'peso': 0.0, 'combos': 0, 'freq': {}} for d in DRAWS}
    peso_total = 0.0

    for linha in tabela:
        mao = linha.get('hand') or ''
        peso = float(linha.get('weight') or 0)
        if len(mao) != 4 or peso <= 0:
            continue
        # combo impossível: carta da mão já está no board (mesma guarda da seleção)
        if {mao[:2], mao[2:]} & cartas_board:
            continue
        fam = _familias_da_linha(linha, acoes, enfrentando)
        if not fam:
            continue
        classe = classe_da_mao(mao, board)
        if not classe:
            continue
        for f in fam:
            if f not in familias:
                familias.append(f)
        peso_total += peso
        alvos = [por_classe[classe]]
        if com_draws:
            perfil = detect_draws(mao, list(board or []))
            if perfil.flush_draw:
                alvos.append(por_draw['flush_draw'])
            if perfil.oesd:
                alvos.append(por_draw['oesd'])
            if perfil.gutshot:
                alvos.append(por_draw['gutshot'])
        for alvo in alvos:
            alvo['peso'] += peso
            alvo['combos'] += 1
            for f, fq in fam.items():
                alvo['freq'][f] = alvo['freq'].get(f, 0.0) + peso * fq

    if peso_total <= 0:
        return None

    def _linha_saida(nome: str, d: dict) -> Optional[dict]:
        if d['peso'] <= 0:
            return None
        return {
            'id': nome,
            'peso_pct': round(100.0 * d['peso'] / peso_total, 1),
            'combos': d['combos'],
            # freq média ponderada pelo peso DENTRO da classe: "o que esta classe faz"
            'freqs': {f: round(100.0 * v / d['peso'], 1) for f, v in d['freq'].items()},
        }

    return {
        'familias': familias,
        'classes': [s for c in CLASSES if (s := _linha_saida(c, por_classe[c]))],
        'draws': ([s for d in DRAWS if (s := _linha_saida(d, por_draw[d]))]
                  if com_draws else []),
    }
