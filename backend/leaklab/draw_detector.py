"""
draw_detector.py — Sprint 3 do Ciclo 2
Detecta draws de flush e straight para ajustar equity estimada no postflop.

Draws reconhecidos e seus ajustes de equity:
  Flush draw (FD):                +0.15  (9 outs ≈ 19% num street)
  Open-ended straight draw (OESD):+0.17  (8 outs ≈ 17%)
  Gutshot (GSSD):                 +0.08  (4 outs ≈ 9%)
  Backdoor flush draw (BDFD):     +0.06  (realiza em 2 streets)
  Backdoor straight draw (BDSD):  +0.04

Limitações documentadas (Ciclo 3):
  - Não detecta draws combinados (FD + OESD = semi-bluff poderoso)
  - Não ajusta por posição na mão (mais outs têm menos valor no river)
  - Não detecta draws bloqueados pelo board (ex: board paired)
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

RANKS = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
    '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14,
}

# Ajuste de equity por tipo de draw
EQUITY_BOOST = {
    'flush_draw':             0.15,
    'oesd':                   0.17,
    'gutshot':                0.08,
    'backdoor_flush_draw':    0.06,
    'backdoor_straight_draw': 0.04,
}


@dataclass
class DrawProfile:
    flush_draw:             bool = False
    oesd:                   bool = False
    gutshot:                bool = False
    backdoor_flush_draw:    bool = False
    backdoor_straight_draw: bool = False

    @property
    def has_any_draw(self) -> bool:
        return any([self.flush_draw, self.oesd, self.gutshot,
                    self.backdoor_flush_draw, self.backdoor_straight_draw])

    @property
    def equity_adjustment(self) -> float:
        total = 0.0
        if self.flush_draw:             total += EQUITY_BOOST['flush_draw']
        if self.oesd:                   total += EQUITY_BOOST['oesd']
        if self.gutshot:                total += EQUITY_BOOST['gutshot']
        if self.backdoor_flush_draw:    total += EQUITY_BOOST['backdoor_flush_draw']
        if self.backdoor_straight_draw: total += EQUITY_BOOST['backdoor_straight_draw']
        # Cap: não pode exceder +0.25 (evita super-inflar mãos marginais)
        return min(total, 0.25)

    def __str__(self) -> str:
        draws = []
        if self.flush_draw:             draws.append('FD')
        if self.oesd:                   draws.append('OESD')
        if self.gutshot:                draws.append('GUT')
        if self.backdoor_flush_draw:    draws.append('BDFD')
        if self.backdoor_straight_draw: draws.append('BDSD')
        return '+'.join(draws) if draws else 'none'


def detect_draws(hero_cards: str, board: List[str]) -> DrawProfile:
    """
    Detecta draws dado as cartas do hero e o board atual.

    hero_cards: string de 4 chars ex 'AsKh'
    board: lista de cartas ex ['Ac','Jc','5c']
    """
    if not hero_cards or len(hero_cards) < 4 or not board:
        return DrawProfile()

    # Parsear hero cards
    h1_rank, h1_suit = hero_cards[0], hero_cards[1]
    h2_rank, h2_suit = hero_cards[2], hero_cards[3]

    # Parsear board
    board_parsed = []
    for card in board:
        if len(card) >= 2:
            board_parsed.append((card[0], card[-1]))

    all_cards = [(h1_rank, h1_suit), (h2_rank, h2_suit)] + board_parsed

    profile = DrawProfile()
    profile.flush_draw, profile.backdoor_flush_draw = _detect_flush_draws(all_cards)
    profile.oesd, profile.gutshot, profile.backdoor_straight_draw = _detect_straight_draws(all_cards)

    return profile


def adjust_equity_for_draws(base_equity: float,
                             hero_cards: str,
                             board: List[str],
                             street: str) -> tuple[float, DrawProfile]:
    """
    Retorna (equity ajustada, DrawProfile).
    No river não há mais draws para realizar — não ajusta.
    """
    if street == 'river' or not board:
        return base_equity, DrawProfile()

    profile = detect_draws(hero_cards, board)
    if not profile.has_any_draw:
        return base_equity, profile

    adjusted = min(base_equity + profile.equity_adjustment, 0.95)
    return round(adjusted, 4), profile


# ── Flush draws ───────────────────────────────────────────────────────────────

def _detect_flush_draws(all_cards: list) -> tuple[bool, bool]:
    """Retorna (flush_draw, backdoor_flush_draw)."""
    suits = Counter(suit for _, suit in all_cards)
    max_count = max(suits.values()) if suits else 0

    if max_count >= 5:
        return False, False  # Já fez flush — não é draw
    if max_count == 4:
        return True, False
    if max_count == 3:
        return False, True
    return False, False


# ── Straight draws ────────────────────────────────────────────────────────────

def _detect_straight_draws(all_cards: list) -> tuple[bool, bool, bool]:
    """Retorna (oesd, gutshot, backdoor_straight_draw)."""
    ranks_raw = [rank for rank, _ in all_cards]
    rank_vals = sorted(set(RANKS.get(r, 0) for r in ranks_raw if r in RANKS))

    if not rank_vals:
        return False, False, False

    # Incluir Ace como 1 para straights A-2-3-4-5
    if 14 in rank_vals:
        rank_vals_low = sorted(set([1] + [r for r in rank_vals if r != 14]))
    else:
        rank_vals_low = rank_vals

    oesd = _has_oesd(rank_vals) or _has_oesd(rank_vals_low)
    gut  = not oesd and (_has_gutshot(rank_vals) or _has_gutshot(rank_vals_low))
    bdsd = not oesd and not gut and (_has_backdoor_straight(rank_vals) or _has_backdoor_straight(rank_vals_low))

    return oesd, gut, bdsd


def _has_oesd(ranks: list) -> bool:
    """4 cartas consecutivas (open-ended)."""
    for i in range(len(ranks) - 3):
        window = ranks[i:i+4]
        if window[-1] - window[0] == 3 and len(window) == 4:
            return True
    return False


def _has_gutshot(ranks: list) -> bool:
    """4 cartas em janela de 5 com 1 gap (gutshot)."""
    for i in range(len(ranks) - 2):
        for j in range(i+2, min(i+5, len(ranks))):
            window = ranks[i:j+1]
            span = window[-1] - window[0]
            if span == 4 and len(window) >= 3:
                # Precisa de exatamente 1 carta para completar
                needed = set(range(window[0], window[-1]+1))
                present = set(window)
                missing = needed - present
                if len(missing) == 1 and len(present) >= 3:
                    return True
    return False


def _has_backdoor_straight(ranks: list) -> bool:
    """3 cartas em janela de 5 (precisa de 2 cartas)."""
    for i in range(len(ranks) - 1):
        for j in range(i+1, min(i+5, len(ranks))):
            window = ranks[i:j+1]
            span = window[-1] - window[0]
            if span <= 4 and len(window) >= 2:
                needed = set(range(window[0], window[-1]+1))
                missing = len(needed - set(window))
                if missing == 2:
                    return True
    return False
