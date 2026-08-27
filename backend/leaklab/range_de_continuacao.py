# -*- coding: utf-8 -*-
"""Quem CONTINUA num board — fonte única do critério, usada pelo river e pelo multiway.

── O defeito que originou (27/08) ─────────────────────────────────────────────────────────

`multiway_advisor._continue_combos` decidia "mão feita" por `eval7.handtype(mão + board) !=
'High Card'`. Num board PAREADO isso é verdade para **toda** mão, porque o par do próprio board
já entra na avaliação de 7 cartas. Resultado medido, sobre a mesma range base de 642 combos:

    board             pareado?    combos    %
    9s,Ah,8s          -              433   67%
    8c,6d,Qh          -              341   53%
    Kd,9c,4s          -              305   48%
    3c,3h,Qd          PAREADO        595   93%
    2d,6h,2s          PAREADO        605   94%
    2h,2d,5s          PAREADO        607   95%

Em board pareado a "range de continuação" era a range inteira, ou seja: equity vs mão aleatória
com nome de equity vs range. E isso vale HOJE, em produção, para todo pote multiway em board
pareado — a equity do herói sai inflada exatamente onde o produto deveria ser mais cauteloso.

Apareceu de lado: medindo o efeito de trocar a equity heurística de flop/turn por esta conta,
as três maiores altas de equity eram `3c,3h,Qd`, `2d,6h,2s` e `5d,6d,5c`. Três boards pareados
em três das maiores diferenças não é coincidência.

── Por que a versão do RIVER estava certa ─────────────────────────────────────────────────

`equity_real.equity_river_vs_continuacao` compara a categoria da mão com a categoria do BOARD
SOZINHO e descarta quem empata com ela. Era a metade correta do projeto, escrita em 24/08 e
nunca compartilhada. É a regra 5 do CLAUDE.md pela sexta vez: o critério vivia em dois lugares,
um certo e um errado, e só o errado recebia board pareado.
"""
from __future__ import annotations

try:
    import eval7
    _HAS_EVAL7 = True
except Exception:                                              # noqa: BLE001
    _HAS_EVAL7 = False


def categoria_do_board(board_cards) -> str | None:
    """A categoria que o board faz SOZINHO. É a régua contra a qual "continuar" se mede."""
    if not _HAS_EVAL7 or not board_cards:
        return None
    return eval7.handtype(eval7.evaluate(list(board_cards)))


def usa_as_proprias_cartas(mao_cards, board_cards, cat_board: str | None) -> bool:
    """A mão sobe de categoria em relação ao que o board já faz sozinho.

    O atalho barato vem do river e vale aqui: quem pareia o board ou tem par de bolso entra sem
    avaliar. O resto precisa BATER a categoria do board — senão está só carregando o par dele.
    """
    if not _HAS_EVAL7 or cat_board is None:
        return False
    c1, c2 = mao_cards[0], mao_cards[1]
    s1, s2 = str(c1), str(c2)
    ranks_board = {str(c)[0] for c in board_cards}
    if s1[0] in ranks_board or s2[0] in ranks_board or s1[0] == s2[0]:
        return True
    return eval7.handtype(eval7.evaluate([c1, c2] + list(board_cards))) != cat_board


def continua(mao_cards, board_cards, cat_board: str | None, com_draws: bool = True) -> bool:
    """Critério completo: mão que usa as próprias cartas, ou projeto real.

    `com_draws=False` no RIVER, onde não há carta por vir e projeto não existe — passar True ali
    contaria como "continuação" mão nenhuma a mais, mas deixaria a intenção ambígua para quem
    ler depois.
    """
    if usa_as_proprias_cartas(mao_cards, board_cards, cat_board):
        return True
    if not com_draws:
        return False
    from leaklab.draw_detector import detect_draws
    dp = detect_draws(str(mao_cards[0]) + str(mao_cards[1]),
                      [str(c) for c in board_cards])
    return bool(dp.flush_draw or dp.oesd or dp.gutshot)
