from __future__ import annotations
from collections import defaultdict
from typing import List, Dict

LABEL_WEIGHTS = {
    'standard':     0.00,
    'marginal':     0.15,
    'small_mistake': 0.55,
    'clear_mistake': 1.00,
}


def correlate_leaks(decision_outputs: List[dict]) -> Dict:
    """
    Agrupa leaks por:
      - best_action (fold/call/raise/bet/jam)
      - street (preflop/flop/turn/river)
      - spot_type (quando disponível)

    Retorna dicionário com peso acumulado, contagem e média por bucket.
    """
    # Por best_action
    by_action: Dict[str, dict] = defaultdict(lambda: {'weight': 0.0, 'count': 0})
    # Por street
    by_street: Dict[str, dict] = defaultdict(lambda: {'weight': 0.0, 'count': 0})
    # Por street + action (combinado)
    by_street_action: Dict[str, dict] = defaultdict(lambda: {'weight': 0.0, 'count': 0})

    for d in decision_outputs:
        label  = d['evaluation']['label']
        weight = LABEL_WEIGHTS[label]
        action = d.get('bestAction', 'unknown')
        street = d.get('street', 'unknown')
        key_sa = f'{street}/{action}'

        by_action[action]['weight'] += weight
        by_action[action]['count']  += 1

        by_street[street]['weight'] += weight
        by_street[street]['count']  += 1

        by_street_action[key_sa]['weight'] += weight
        by_street_action[key_sa]['count']  += 1

    def finalize(raw: dict) -> dict:
        return {
            k: {
                'weight':     round(v['weight'], 4),
                'count':      v['count'],
                'avg_weight': round(v['weight'] / v['count'], 4) if v['count'] else 0.0,
            }
            for k, v in raw.items()
        }

    return {
        'by_action':        finalize(by_action),
        'by_street':        finalize(by_street),
        'by_street_action': finalize(by_street_action),
    }
