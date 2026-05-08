"""
gto_utils.py — Hashing determinístico de spots para integração GTO.

Contrato compartilhado entre o engine e o bot externo que popula gto_nodes.
Mesmo input → mesmo hash em Python e em qualquer linguagem que implemente
json.dumps com sort_keys=True + sha256.
"""
from __future__ import annotations
import hashlib
import json

STACK_BUCKETS = [
    (0,   10,  "0-10bb"),
    (10,  20,  "10-20bb"),
    (20,  35,  "20-35bb"),
    (35,  60,  "35-60bb"),
    (60,  100, "60-100bb"),
    (100, float("inf"), "100bb+"),
]


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
