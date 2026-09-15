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

    # Multiway postflop nao e medida: o solver e heads-up e o veredito dela nao descreve a
    # decisao. Sai do DENOMINADOR de tudo que julga (label, %, score medio) e continua no que
    # conta (`total_decisions`, maos): a decisao existe, so nao tem nota. E a mesma regra de
    # `recalcula_agregados_do_torneio`, que reescreve estes `*_pct` no resync; sem isto o
    # torneio nascia com um denominador e era reescrito com outro.
    from leaklab.card_verdict import multiway_sem_cobertura
    medidas = [d for d in decision_outputs
               if not multiway_sem_cobertura(d.get('street'),
                                             (d.get('spot') or {}).get('nActiveOpponents'))]

    labels = Counter(d['evaluation']['label'] for d in medidas)
    total = len(decision_outputs)
    n_medidas = len(medidas)
    avg_score = round(
        sum(d['evaluation']['mistakeScore'] for d in medidas) / n_medidas, 4
    ) if n_medidas else 0.0

    # Contagem de mãos únicas
    unique_hands = len(set(d['handId'] for d in decision_outputs))

    # Distribuição por street
    by_street: Dict[str, Dict] = {}
    for d in medidas:
        street = d.get('street', 'unknown')
        if street not in by_street:
            by_street[street] = Counter()
        by_street[street][d['evaluation']['label']] += 1

    # Percentuais
    label_pct = {k: round(v / n_medidas * 100, 1) for k, v in labels.items()}

    return {
        'total_decisions': total,
        'total_hands':     unique_hands,
        'label_distribution': dict(labels),
        'label_pct':          label_pct,
        'avg_mistake_score':  avg_score,
        'by_street':          {s: dict(c) for s, c in by_street.items()},
    }
