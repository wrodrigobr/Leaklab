from __future__ import annotations


def build_recommendation(decision_output: dict) -> dict:
    label = decision_output["evaluation"]["label"]
    templates = {
        "standard": "Linha sólida e consistente para o spot.",
        "marginal": "A decisão é defensável, mas a linha preferida tende a performar melhor.",
        "small_mistake": "A linha escolhida perde um pouco de valor e tende a ser custosa se repetida com frequência.",
        "clear_mistake": "A decisão se afasta de forma importante da linha recomendada e tende a gerar perda relevante.",
    }
    return {
        "handId": decision_output["handId"],
        "label": label,
        "summary": templates[label],
        "details": decision_output.get("interpretation", {}),
    }
