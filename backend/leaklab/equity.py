"""equity.py — equity preflop MÃO-vs-RANGE a partir da matriz 169×169 gerada por
scripts/gen_preflop_equity.py (eval7 Monte Carlo, all-in até o river).

Substitui o proxy "vs random" por equity vs a RANGE GTO real do villain quando ela
é conhecida (ex.: hero defende contra um open → villain tem a RFI range daquela
posição, ~15-45% das mãos, não 100% aleatórias). Sem range conhecida, o caller
deve seguir usando o vs-random (PREFLOP_EQ_VS_RANDOM em street_math_engine).

Asset: leaklab/data/preflop_equity_169.json no formato {hero: {villain: eq}}.
"""
from __future__ import annotations
import json, os
from typing import Optional

_MATRIX_FILE = os.path.join(os.path.dirname(__file__), 'data', 'preflop_equity_169.json')
_matrix: Optional[dict] = None


def _load() -> dict:
    global _matrix
    if _matrix is None:
        try:
            with open(_MATRIX_FILE, 'r', encoding='utf-8') as f:
                _matrix = json.load(f)
        except FileNotFoundError:
            _matrix = {}
    return _matrix


def has_matrix() -> bool:
    return bool(_load())


def equity_vs_hand(hero: str, villain: str) -> Optional[float]:
    """Equity de hero (canônica 'AKs') vs UMA mão canônica do villain. None se a
    matriz não está disponível ou a mão é desconhecida."""
    m = _load()
    row = m.get(hero)
    if not row:
        return None
    v = row.get(villain)
    return float(v) if v is not None else None


def equity_vs_range(hero: str, villain_range: dict) -> Optional[float]:
    """Equity de hero vs uma range ponderada do villain.

    villain_range: {hand_canon: weight}. Retorna a média de equity ponderada pelos
    pesos (combos), respeitando card removal de forma agregada (a matriz já embute
    o card removal mão-a-mão). None se matriz indisponível ou nenhuma mão casa.

    O peso de cada mão é multiplicado pelo nº de combos do tipo (par=6, suited=4,
    offsuit=12) para que a média reflita a frequência real de combos na range —
    sem isso, um par (6 combos) pesaria igual a um offsuit (12 combos)."""
    m = _load()
    row = m.get(hero)
    if not row or not villain_range:
        return None
    num = den = 0.0
    for hand, w in villain_range.items():
        if not w or w <= 0:
            continue
        eq = row.get(hand)
        if eq is None:
            continue
        combos = _combo_count(hand)
        weight = float(w) * combos
        num += eq * weight
        den += weight
    if den <= 0:
        return None
    return round(num / den, 4)


def _combo_count(hand: str) -> int:
    """Nº de combos de uma mão canônica: par=6, suited=4, offsuit=12."""
    if len(hand) == 2:
        return 6
    return 4 if hand.endswith('s') else 12
