from __future__ import annotations
from collections import Counter
from typing import List, Dict


def build_session_metrics(decision_outputs: List[dict]) -> Dict:
    """
    Recebe lista de resultados do Decision Engine (pode conter múltiplas
    decisões por mão) e retorna métricas agregadas da sessão.
    """
    if not decision_outputs:
        return {
            'total_decisions': 0,
            'total_hands': 0,
            'label_distribution': {},
            'label_pct': {},
            'avg_mistake_score': 0.0,
            'by_street': {},
        }

    labels = Counter(d['evaluation']['label'] for d in decision_outputs)
    total = len(decision_outputs)
    avg_score = round(
        sum(d['evaluation']['mistakeScore'] for d in decision_outputs) / total, 4
    )

    # Contagem de mãos únicas
    unique_hands = len(set(d['handId'] for d in decision_outputs))

    # Distribuição por street
    by_street: Dict[str, Dict] = {}
    for d in decision_outputs:
        street = d.get('street', 'unknown')
        if street not in by_street:
            by_street[street] = Counter()
        by_street[street][d['evaluation']['label']] += 1

    # Percentuais
    label_pct = {k: round(v / total * 100, 1) for k, v in labels.items()}

    return {
        'total_decisions': total,
        'total_hands':     unique_hands,
        'label_distribution': dict(labels),
        'label_pct':          label_pct,
        'avg_mistake_score':  avg_score,
        'by_street':          {s: dict(c) for s, c in by_street.items()},
    }
