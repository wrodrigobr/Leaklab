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
    # Stacks >= 60bb usam '60-100bb' como bucket de referência. As soluções
    # do arquivo de ranges (preflop_gto_ranges) e do solver postflop são
    # calibradas até 100bb — stacks acima usam 100bb como profundidade
    # efetiva (cap implícito). Evita criar bucket '100bb+' sem cobertura
    # e mantém lookup consistente para cash deep + MTT early stages.
    (60,  float("inf"), "60-100bb"),
]

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_IDX = {r: i for i, r in enumerate(RANKS)}

VALID_POSITIONS = {'UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'}

_ACTION_NORM: dict[str, str] = {
    'shove': 'jam', 'allin': 'jam', 'all-in': 'jam', 'all_in': 'jam', 'all in': 'jam',
    'open': 'raise', 'openraise': 'raise',
    'x': 'check', 'limp': 'call',
}
VALID_GTO_ACTIONS = {'fold', 'check', 'call', 'bet', 'raise', 'jam'}


def normalize_gto_action(action: str) -> str:
    """Normaliza string de ação GTO para o conjunto canônico {fold,check,call,bet,raise,jam}."""
    a = (action or '').lower().strip()
    return _ACTION_NORM.get(a, a)


def stack_bucket(bb: float) -> str:
    """Converte stack em BBs para bucket discreto. Stacks >= 60bb cap em '60-100bb'."""
    for lo, hi, label in STACK_BUCKETS:
        if lo <= bb < hi:
            return label
    return "60-100bb"


BET_BUCKETS = [
    (0,    0,    "no_bet"),
    (0,    3,    "0-3bb"),
    (3,    8,    "3-8bb"),
    (8,    20,   "8-20bb"),
    (20,   40,   "20-40bb"),
    (40,   float("inf"), "40bb+"),
]


def bet_bucket(facing_size_bb: float) -> str:
    """Converte aposta enfrentada em bucket discreto. 0 = spot sem aposta."""
    if facing_size_bb <= 0:
        return "no_bet"
    for lo, hi, label in BET_BUCKETS[1:]:
        if lo < facing_size_bb <= hi:
            return label
    return "40bb+"


def compute_spot_hash(
    street: str,
    position: str,
    board: list[str],
    hero_hand: list[str],
    hero_stack_bb: float,
    facing_size_bb: float = 0.0,
) -> str:
    """
    Retorna hash SHA256[:16] determinístico do spot.
    Normalização: street minúsculo, position maiúsculo, listas ordenadas.
    facing_size_bb distingue spots "sem aposta" de "facing bet" e seus tamanhos.
    """
    canonical = {
        "street":       street.lower(),
        "position":     position.upper(),
        "board":        sorted(board),
        "hand":         sorted(hero_hand),
        "stack_bucket": stack_bucket(hero_stack_bb),
        "bet_bucket":   bet_bucket(facing_size_bb),
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
