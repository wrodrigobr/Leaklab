from __future__ import annotations
from typing import Dict, Any


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round4(value: float) -> float:
    return round(value, 4)


decision_engine_config = {
    "labels": {"standardMax": 0.08, "marginalMax": 0.18, "smallMistakeMax": 0.36},
    "streetCaps": {"preflop": 0.04, "flop": 0.05, "turn": 0.06, "river": 0.06},
    "streetMultipliers": {"preflop": 0.95, "flop": 1.0, "turn": 1.08, "river": 1.12},
}


def calc_realization_adjustment(is_in_position: bool | None, reverse_implied_odds_factor: float | None, effective_stack_bb: float | None, range_zone: str, hand_class: str | None) -> float:
    adj = 0.0
    if is_in_position is False:
        adj += 0.01
    if (reverse_implied_odds_factor or 0) > 0.5:
        adj += 0.01
    if (effective_stack_bb or 0) > 40 and range_zone == "outside_range":
        adj += 0.01
    if hand_class and "dominated" in hand_class:
        adj += 0.01
    return clamp(adj, 0.0, 0.04)


def calc_pressure_adjustment(street: str, pressure_score: float | None, is_multiway: bool | None, icm_pressure: str | None) -> float:
    adj = 0.0
    p = pressure_score or 0.0
    if 0.35 <= p < 0.65:
        adj += 0.01
    if p >= 0.65:
        adj += 0.02
    if is_multiway:
        adj += 0.01
    if icm_pressure == "high" and street in {"turn", "river"}:
        adj += 0.01
    return clamp(adj, 0.0, 0.03)


def calc_adjusted_required_equity(street: str, pot_odds_equity: float | None, realization_adjustment: float, pressure_adjustment: float):
    if pot_odds_equity is None:
        return {"adjustedRequiredEquity": None, "streetCapApplied": decision_engine_config["streetCaps"][street], "totalAdjustment": 0.0}
    cap = decision_engine_config["streetCaps"][street]
    total = clamp(realization_adjustment + pressure_adjustment, 0.0, cap)
    return {"adjustedRequiredEquity": round4(pot_odds_equity + total), "streetCapApplied": cap, "totalAdjustment": round4(total)}


def calc_base_action_gap(player_action: str, recommended_primary_action: str, alternative_actions: list[str] | None = None) -> float:
    alternatives = alternative_actions or []
    if player_action == recommended_primary_action:
        return 0.0
    if player_action in alternatives:
        return 0.08
    aggressive_mismatch = player_action in {"jam", "raise"} and recommended_primary_action == "fold"
    if aggressive_mismatch:
        return 0.35
    if player_action == "fold" and recommended_primary_action == "call":
        return 0.14
    if player_action == "call" and recommended_primary_action == "fold":
        return 0.22
    return 0.18


def calc_math_penalty(player_action: str, estimated_hand_equity: float | None, adjusted_required_equity: float | None) -> float:
    if estimated_hand_equity is None or adjusted_required_equity is None:
        return 0.0
    diff = round4(estimated_hand_equity - adjusted_required_equity)
    if player_action == "call":
        if diff >= 0: return 0.0
        if diff > -0.02: return 0.05
        if diff > -0.04: return 0.11
        if diff > -0.07: return 0.18
        return 0.28
    if player_action == "fold":
        if diff <= 0: return 0.0
        if diff < 0.02: return 0.04
        if diff < 0.04: return 0.09
        if diff < 0.07: return 0.15
        return 0.22
    return 0.0


def calc_range_penalty(range_zone: str, player_action: str, recommended_primary_action: str) -> float:
    if player_action == recommended_primary_action:
        return 0.0
    if range_zone == "borderline_range":
        return 0.03
    if range_zone == "core_range":
        return 0.08
    if range_zone == "outside_range":
        return 0.12
    return 0.0


def calc_context_penalty(street: str, is_multiway: bool | None, is_in_position: bool | None, icm_pressure: str | None, player_action: str, recommended_primary_action: str) -> float:
    penalty = 0.0
    if player_action != recommended_primary_action:
        if street == "turn": penalty += 0.02
        if street == "river": penalty += 0.04
    if is_multiway: penalty += 0.01
    if is_in_position is False and street != "preflop": penalty += 0.01
    if icm_pressure == "high": penalty += 0.01
    return penalty


def calc_tolerance_credit(range_zone: str, player_action: str, recommended_primary_action: str, alternative_actions: list[str] | None, estimated_hand_equity: float | None, adjusted_required_equity: float | None) -> float:
    credit = 0.0
    alternatives = alternative_actions or []
    if range_zone == "borderline_range":
        credit += 0.05
    if player_action in alternatives:
        credit += 0.04
    if estimated_hand_equity is not None and adjusted_required_equity is not None:
        diff = abs(estimated_hand_equity - adjusted_required_equity)
        if diff <= 0.02:
            credit += 0.03
        elif diff <= 0.03:
            credit += 0.015
    return credit


def classify_mistake_score(score: float) -> str:
    if score <= 0.08: return "standard"
    if score <= 0.18: return "marginal"
    if score <= 0.36: return "small_mistake"
    return "clear_mistake"


def apply_anti_rules(player_action: str, estimated_hand_equity: float | None, adjusted_required_equity: float | None, provisional_label: str, best_action: str | None = None) -> str:
    # Se o jogador fez exatamente a ação recomendada, não há anti-rule a aplicar
    if best_action is not None and player_action == best_action:
        return provisional_label
    if estimated_hand_equity is None or adjusted_required_equity is None:
        return provisional_label
    diff = round4(estimated_hand_equity - adjusted_required_equity)
    if player_action == "fold":
        if 0 <= diff <= 0.03 and provisional_label == "clear_mistake":
            return "small_mistake"
    if player_action == "call":
        if diff <= -0.07:
            return "clear_mistake"
        if diff <= -0.04 and provisional_label == "marginal":
            return "small_mistake"
    return provisional_label


def evaluate_decision(input_data: Dict[str, Any]) -> Dict[str, Any]:
    street = input_data["street"]
    spot = input_data["spot"]
    hand_profile = input_data["hand_profile"]
    math = input_data["math"]
    range_eval = input_data["range_evaluation"]
    context = input_data.get("context", {})

    realization_adjustment = calc_realization_adjustment(
        spot.get("isInPosition"),
        math.get("reverseImpliedOddsFactor"),
        spot.get("effectiveStackBb"),
        range_eval.get("rangeZone"),
        hand_profile.get("handClass"),
    )
    pressure_adjustment = calc_pressure_adjustment(
        street,
        math.get("pressureScore"),
        spot.get("isMultiway"),
        context.get("icmPressure"),
    )
    threshold_pack = calc_adjusted_required_equity(
        street,
        math.get("potOddsEquity"),
        realization_adjustment,
        pressure_adjustment,
    )
    base_action_gap = calc_base_action_gap(
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
        range_eval.get("alternativeActions") or [],
    )
    # Math penalty só se aplica quando a ação diverge da recomendada
    # Se o jogador fez exatamente o bestAction, não há penalidade matemática
    _best_action = range_eval.get("recommendedPrimaryAction")
    math_penalty = calc_math_penalty(
        input_data["player_action"],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
    ) if input_data["player_action"] != _best_action else 0.0
    range_penalty = calc_range_penalty(
        range_eval.get("rangeZone"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
    )
    context_penalty = calc_context_penalty(
        street,
        spot.get("isMultiway"),
        spot.get("isInPosition"),
        context.get("icmPressure"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
    )
    tolerance_credit = calc_tolerance_credit(
        range_eval.get("rangeZone"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
        range_eval.get("alternativeActions") or [],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
    )
    raw_score = clamp(base_action_gap + math_penalty + range_penalty + context_penalty - tolerance_credit, 0.0, 1.0)
    street_multiplier = decision_engine_config["streetMultipliers"][street]
    final_score = clamp(raw_score * street_multiplier, 0.0, 1.0)
    label = classify_mistake_score(final_score)
    label = apply_anti_rules(
        input_data["player_action"],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
        label,
        best_action=_best_action,
    )
    interpretation = build_interpretation(input_data, label, threshold_pack["adjustedRequiredEquity"])
    return {
        "handId": input_data["hand_id"],
        "bestAction": range_eval.get("recommendedPrimaryAction"),
        "actionTaken": input_data["player_action"],
        "evaluation": {
            "mistakeScore": round4(final_score),
            "label": label,
            "scoreBreakdown": {
                "baseActionGap": round4(base_action_gap),
                "mathPenalty": round4(math_penalty),
                "rangePenalty": round4(range_penalty),
                "contextPenalty": round4(context_penalty),
                "toleranceCredit": round4(tolerance_credit),
                "streetMultiplier": round4(street_multiplier),
            },
        },
        "thresholds": {
            "potOddsEquity": math.get("potOddsEquity"),
            "realizationAdjustment": round4(realization_adjustment),
            "pressureAdjustment": round4(pressure_adjustment),
            "adjustedRequiredEquity": threshold_pack["adjustedRequiredEquity"],
            "streetCapApplied": threshold_pack["streetCapApplied"],
        },
        "interpretation": interpretation,
        "debug": {
            "rangeZone": range_eval.get("rangeZone"),
            "alternativeActions": range_eval.get("alternativeActions") or [],
            "rawFlags": [],
        },
    }


def build_interpretation(input_data: Dict[str, Any], label: str, adjusted_required_equity: float | None):
    summary_map = {
        "standard": "Linha sólida para o spot, compatível com a faixa esperada de decisão.",
        "marginal": "Ação defensável, mas ligeiramente inferior à linha preferida.",
        "small_mistake": "Pequena perda estratégica, relevante no longo prazo.",
        "clear_mistake": "Ação claramente inferior no contexto do spot, com erro estratégico relevante.",
    }
    math_explanation = ""
    strategic_explanation = ""
    est = input_data["math"].get("estimatedHandEquity")
    if est is not None and adjusted_required_equity is not None:
        diff = round4(est - adjusted_required_equity)
        if diff > 0.02:
            math_explanation = "A mão tinha equity suficiente para continuar com mais conforto."
        elif 0 <= diff <= 0.02:
            math_explanation = "O spot estava próximo do threshold, indicando uma decisão relativamente close."
        elif diff > -0.04:
            math_explanation = "A equity estimada ficou levemente abaixo da exigência ajustada."
        else:
            math_explanation = "A equity estimada ficou materialmente abaixo da exigência ajustada do spot."
    zone = input_data["range_evaluation"].get("rangeZone")
    if zone == "borderline_range":
        strategic_explanation = "A mão está em região de borda do range, então a decisão exige mais nuance do que um julgamento binário."
    elif zone == "outside_range":
        strategic_explanation = "A ação escolhida força uma linha fora da banda mais defensável do range estimado."
    else:
        strategic_explanation = "A decisão deve seguir a estrutura principal esperada para esse spot."
    return {"summary": summary_map[label], "mathExplanation": math_explanation, "strategicExplanation": strategic_explanation}
