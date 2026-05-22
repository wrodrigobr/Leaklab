from __future__ import annotations
from .models import HandState, SpotClassification, RangeEvaluation


def evaluate_preflop_range(state: HandState, spot: SpotClassification) -> RangeEvaluation:
    cards = state.hero_cards or ""
    zone = _classify_range_zone(cards)
    facing_size = float(getattr(state, 'facing_size', 0) or 0)
    recommended = _recommended_action(cards, state.position, facing_size)
    alternatives = []
    if zone == "borderline_range":
        base_alts = ["call", "fold"] if recommended == "call" else ["raise", "fold"]
        # BB pode check grátis — fold não é alternativa válida sem aposta
        alternatives = [a for a in base_alts if not (a == "fold" and facing_size == 0 and state.position == "BB")]
    elif zone == "core_range":
        alternatives = [recommended]
    return RangeEvaluation(
        recommended_primary_action=recommended,
        alternative_actions=list(dict.fromkeys(alternatives)),
        range_zone=zone,
        confidence=0.72,
        mix_weight=0.25 if zone == "borderline_range" else 0.05,
    )


def _classify_range_zone(cards: str) -> str:
    if len(cards) < 4:
        return "outside_range"
    r1, s1, r2, s2 = cards[0], cards[1], cards[2], cards[3]
    pair = r1 == r2
    suited = s1 == s2
    broadway = r1 in "TJQKA" and r2 in "TJQKA"
    if pair and r1 in "89TJQKA":
        return "core_range"
    if pair and r1 in "4567":
        return "borderline_range"
    if broadway and suited:
        return "core_range"
    if broadway or suited:
        return "borderline_range"
    return "outside_range"


def _recommended_action(cards: str, position: str, facing_size: float = 0.0) -> str:
    """Recomenda ação preflop usando classificação por zona + posição + facing_size.

    Regra crítica (FIX 2026-05-22): quando facing_size > 3bb (hero enfrenta 3-bet
    ou maior), borderline hands não devem 4-bet — preferem call (set-mine para
    pares, implied odds para suited connectors). Antes o heurístico recomendava
    raise para todo borderline em não-blind, o que sobreestimava agressão em
    spots multiway com 3-bet.
    """
    zone = _classify_range_zone(cards)
    is_pair = len(cards) >= 4 and cards[0] == cards[2]
    r1      = cards[0] if len(cards) >= 1 else ""
    is_small_pair = is_pair and r1 in "234567"

    # Facing 3-bet+ (>= 3bb): tighter logic — set-mine / call em vez de 4-bet
    if facing_size >= 3.0:
        if zone == "core_range":
            # Pares 88-AA + broadway suited → call ou 4-bet conforme posição
            # Em IP, premium pode 4-bet; OOP prefere call
            return "raise" if position not in {"BB", "SB", "UTG", "UTG+1", "UTG1"} else "call"
        if zone == "borderline_range":
            # Borderline facing 3-bet: call (set-mine, implied odds) ou fold
            return "call"
        return "fold"

    # Sem facing ou facing pequeno (steal/limp): lógica RFI/vs_limp original
    if zone == "core_range":
        return "raise" if position not in {"BB"} else "call"
    if zone == "borderline_range":
        return "call" if position in {"BB", "SB"} else "raise"
    # Mão fraca: BB pode check grátis; demais posições estão escolhendo não abrir — fold é correto.
    if facing_size == 0 and position == "BB":
        return "check"
    return "fold"
