"""
board_texture.py — Classifica textura de board pós-flop.
"""
from __future__ import annotations
import json

RANK_ORDER = "23456789TJQKA"


def _rank_num(r: str) -> int:
    return RANK_ORDER.index(r) if r in RANK_ORDER else -1


def classify_board_texture(board_json) -> str:
    """
    Recebe board como JSON string ou lista de strings (ex: '["Ah","Kd","2c"]').
    Retorna: 'dry' | 'coordinated' | 'wet' | 'monotone' | 'paired' | 'unknown'
    """
    try:
        cards = json.loads(board_json) if isinstance(board_json, str) else list(board_json)
    except Exception:
        return 'unknown'

    if not cards or len(cards) < 3:
        return 'unknown'

    flop = [str(c) for c in cards[:3]]
    suits = [c[-1].lower() for c in flop if len(c) >= 2]
    ranks = [c[:-1].upper() for c in flop if len(c) >= 2]

    if len(ranks) < 3:
        return 'unknown'

    if len(set(ranks)) < 3:
        return 'paired'

    if len(set(suits)) == 1:
        return 'monotone'

    flush_draw = max(suits.count(s) for s in set(suits)) >= 2

    # Straight draw: all 3 cards span ≤ 4 ranks (fit in a 5-card window)
    # e.g. JT9 (span=2), AKQ (span=2), QJ8 (span=4) → coordinated
    # AK2 (span=12), A72 (span=12) → dry
    nums = sorted(_rank_num(r) for r in ranks if _rank_num(r) >= 0)
    straight_draw = len(nums) == 3 and (nums[-1] - nums[0]) <= 4

    if flush_draw and straight_draw:
        return 'wet'
    if straight_draw:
        return 'coordinated'
    return 'dry'
