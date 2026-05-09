"""
gto_utils.py — Hashing determinístico de spots + normalização de mãos GTO.

Contrato compartilhado entre o engine e o bot externo que popula gto_nodes.
Mesmo input → mesmo hash em Python e em qualquer linguagem que implemente
json.dumps com sort_keys=True + sha256.
"""
from __future__ import annotations
import hashlib
import json
from typing import Optional

STACK_BUCKETS = [
    (0,   10,  "0-10bb"),
    (10,  20,  "10-20bb"),
    (20,  35,  "20-35bb"),
    (35,  60,  "35-60bb"),
    (60,  100, "60-100bb"),
    (100, float("inf"), "100bb+"),
]

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_IDX = {r: i for i, r in enumerate(RANKS)}


def stack_bucket(bb: float) -> str:
    """Converte stack em BBs para bucket discreto."""
    for lo, hi, label in STACK_BUCKETS:
        if lo <= bb < hi:
            return label
    return "100bb+"


def compute_spot_hash(
    street: str,
    position: str,
    board: list[str],
    hero_hand: list[str],
    hero_stack_bb: float,
) -> str:
    """
    Retorna hash SHA256[:16] determinístico do spot.
    Normalização: street minúsculo, position maiúsculo, listas ordenadas.
    """
    canonical = {
        "street":       street.lower(),
        "position":     position.upper(),
        "board":        sorted(board),
        "hand":         sorted(hero_hand),
        "stack_bucket": stack_bucket(hero_stack_bb),
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True).encode()
    ).hexdigest()[:16]


# ── Hand normalization ─────────────────────────────────────────────────────────

def hand_to_type(cards: list[str]) -> Optional[str]:
    """
    Converte uma mão específica (ex: ['Ac', 'Kd']) para hand_type (ex: 'AKo').

    Retorna:
      'AA'  — par
      'AKs' — suited
      'AKo' — offsuit
      None  — entrada inválida
    """
    if not cards or len(cards) < 2:
        return None
    c1, c2 = cards[0], cards[1]
    if len(c1) < 2 or len(c2) < 2:
        return None

    r1, s1 = c1[0].upper(), c1[1].lower()
    r2, s2 = c2[0].upper(), c2[1].lower()

    # Garante ordem decrescente por rank
    if RANK_IDX.get(r1, -1) < RANK_IDX.get(r2, -1):
        r1, r2 = r2, r1
        s1, s2 = s2, s1

    if r1 == r2:
        return f"{r1}{r2}"       # par: "AA"
    if s1 == s2:
        return f"{r1}{r2}s"     # suited: "AKs"
    return f"{r1}{r2}o"         # offsuit: "AKo"


def expand_range_notation(notation: str) -> list[str]:
    """
    Expande notação de range poker para lista de hand_types.

    Suporta:
      'AA'       → ['AA']
      'TT+'      → ['TT','JJ','QQ','KK','AA']
      'ATs+'     → ['ATs','AJs','AQs','AKs']
      'ATo+'     → ['ATo','AJo','AQo','AKo']
      'ATs-AJs'  → ['ATs','AJs']
      'KTs+'     → ['KTs','KJs','KQs']
    """
    notation = notation.strip()
    hands: list[str] = []

    if '-' in notation and notation[-1] != '+':
        # range: ATs-AJs
        lo_str, hi_str = notation.split('-', 1)
        lo_r, lo_k, lo_s = _parse_hand_str(lo_str)
        hi_r, hi_k, hi_s = _parse_hand_str(hi_str)
        if lo_r is None or hi_r is None:
            return []
        start = min(RANK_IDX.get(lo_k, 0), RANK_IDX.get(hi_k, 0))
        end   = max(RANK_IDX.get(lo_k, 0), RANK_IDX.get(hi_k, 0))
        for i in range(start, end + 1):
            hands.append(f"{lo_r}{RANKS[i]}{lo_s}")
        return hands

    if notation.endswith('+'):
        base = notation[:-1]
        r1, r2, suit = _parse_hand_str(base)
        if r1 is None:
            return []
        if r1 == r2:
            # par+: TT+ → TT,JJ,QQ,KK,AA
            start = RANK_IDX.get(r1, 0)
            for i in range(start, len(RANKS)):
                hands.append(f"{RANKS[i]}{RANKS[i]}")
        else:
            # connector+: ATs+ → ATs,AJs,AQs,AKs
            start = RANK_IDX.get(r2, 0)
            end   = RANK_IDX.get(r1, 0) - 1
            for i in range(start, end + 1):
                hands.append(f"{r1}{RANKS[i]}{suit}")
        return hands

    # single hand
    r1, r2, suit = _parse_hand_str(notation)
    if r1 is None:
        return []
    return [notation]


def _parse_hand_str(s: str):
    """Retorna (high_rank, low_rank_or_same, suit_suffix) ou (None,None,None)."""
    s = s.strip()
    if len(s) == 2:
        # par: 'AA'
        return s[0].upper(), s[1].upper(), ''
    if len(s) == 3:
        r1, r2, c = s[0].upper(), s[1].upper(), s[2].lower()
        if c in ('s', 'o'):
            return r1, r2, c
    return None, None, None
