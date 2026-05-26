from __future__ import annotations
from .models import HandState, MathSnapshot


def build_math_snapshot(state: HandState) -> MathSnapshot:
    pot = max(state.pot_size, 0.0)
    facing = max(state.facing_size, 0.0)
    pot_odds_equity = None
    if facing > 0:
        pot_odds_equity = round(facing / (pot + facing), 4) if (pot + facing) > 0 else None

    estimated_equity = _estimate_hand_equity(state.hero_cards, state.board, state.street)
    # Ajuste multiway: equity heuristica eh calibrada vs random HU. Em pote
    # 3+way, equity real cai significativamente. Aplica fator empirico em
    # postflop (preflop ja usa ranges GTO especificos por cenario).
    if estimated_equity is not None and state.street != 'preflop':
        n_opp = (state.metadata or {}).get('n_active_opponents', 1) or 1
        if n_opp > 1:
            # eq_multiway = eq_HU / (1 + 0.3 * (n_opp - 1))
            # 2 opps -> 77% do HU; 3 opps -> 62%; 4 opps -> 53%; 5 opps -> 45%
            factor = 1.0 / (1.0 + 0.3 * (n_opp - 1))
            estimated_equity = round(estimated_equity * factor, 4)
    implied = 0.1 if state.street in {"flop", "turn"} else 0.0
    reverse_implied = 0.15 if (state.hero_cards and len(state.hero_cards) >= 4 and state.hero_cards[0] != state.hero_cards[2]) else 0.05
    pressure = _estimate_pressure(state)
    return MathSnapshot(
        pot_odds_equity=pot_odds_equity,
        estimated_hand_equity=estimated_equity,
        implied_odds_factor=implied,
        reverse_implied_odds_factor=reverse_implied,
        pressure_score=pressure,
    )


def _estimate_hand_equity(hero_cards: str | None, board, street: str) -> float | None:
    if not hero_cards:
        return None
    ranks = hero_cards[0] + (hero_cards[2] if len(hero_cards) >= 4 else "")
    pair = len(hero_cards) >= 4 and hero_cards[0] == hero_cards[2]
    broadway = all(r in "TJQKA" for r in ranks)
    suited = len(hero_cards) >= 4 and hero_cards[1] == hero_cards[3]
    if street == "preflop":
        if pair:
            return 0.5 if hero_cards[0] in "23456" else 0.57 if hero_cards[0] in "789T" else 0.64
        if broadway and suited:
            return 0.49
        if broadway:
            return 0.45
        if suited:
            return 0.39
        return 0.33
    # crude postflop heuristic
    if pair:
        return 0.58
    if broadway:
        return 0.41
    return 0.29


def _estimate_pressure(state: HandState) -> float:
    if state.facing_size <= 0:
        return 0.05
    ratio = state.facing_size / max(state.pot_size, 1.0)
    if ratio >= 1.0:
        return 0.8
    if ratio >= 0.66:
        return 0.6
    if ratio >= 0.33:
        return 0.4
    return 0.2
