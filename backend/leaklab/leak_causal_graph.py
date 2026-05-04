"""
leak_causal_graph.py — Sprint S (FEAT-06)
Analisa co-ocorrência de leaks entre torneios e constrói grafo causal.
"""
from __future__ import annotations
from collections import defaultdict
from itertools import combinations
from typing import List, Dict, Tuple

_MIN_CORRELATION = 0.35
_MIN_CO_OCCUR    = 2
_MAX_EDGES       = 12
_MAX_NODES       = 10

_STREET_ABBR = {'preflop': 'PF', 'flop': 'FL', 'turn': 'TN', 'river': 'RV'}


def _format_label(spot: str) -> str:
    parts = spot.split('/')
    if len(parts) == 2:
        abbr = _STREET_ABBR.get(parts[0], parts[0][:2].upper())
        return f"{abbr} {parts[1].capitalize()}"
    return spot[:14]


def build_leak_graph(rows: List[dict]) -> Dict:
    """
    rows: lista de {tournament_id, spot, score} — todas as decisions com label
          small_mistake ou clear_mistake do usuário no período.
    Retorna: {nodes: [...], edges: [...]}
    """
    by_tournament: Dict[int, set] = defaultdict(set)
    spot_scores: Dict[str, List[float]] = defaultdict(list)

    for r in rows:
        tid  = r['tournament_id']
        spot = r['spot']
        by_tournament[tid].add(spot)
        spot_scores[spot].append(float(r['score']))

    # Número de torneios em que cada spot aparece
    spot_counts: Dict[str, int] = defaultdict(int)
    for spots in by_tournament.values():
        for spot in spots:
            spot_counts[spot] += 1

    # Co-ocorrências entre pares de leaks no mesmo torneio
    co_occur: Dict[Tuple[str, str], int] = defaultdict(int)
    for spots in by_tournament.values():
        for a, b in combinations(sorted(spots), 2):
            co_occur[(a, b)] += 1

    # Arestas com correlação de Jaccard-like
    edges = []
    for (a, b), count in co_occur.items():
        if count < _MIN_CO_OCCUR:
            continue
        corr = count / min(spot_counts[a], spot_counts[b])
        if corr >= _MIN_CORRELATION:
            edges.append({
                'source':         a,
                'target':         b,
                'co_occurrences': count,
                'correlation':    round(corr, 2),
            })

    edges.sort(key=lambda x: x['correlation'], reverse=True)
    edges = edges[:_MAX_EDGES]

    # Nós: spots presentes em arestas + top-N por frequência
    connected = {e['source'] for e in edges} | {e['target'] for e in edges}
    top_by_count = {s for s, _ in sorted(spot_counts.items(), key=lambda x: -x[1])[:5]}
    all_spots = list((connected | top_by_count))[:_MAX_NODES]

    nodes = []
    for spot in all_spots:
        scores = spot_scores.get(spot, [])
        avg_score = sum(scores) / len(scores) if scores else 0.5
        n = spot_counts.get(spot, 0)
        if avg_score >= 0.65:
            severity = 'critical'
        elif avg_score >= 0.45:
            severity = 'moderate'
        else:
            severity = 'minor'
        degree = sum(1 for e in edges if e['source'] == spot or e['target'] == spot)
        nodes.append({
            'id':        spot,
            'label':     _format_label(spot),
            'n':         n,
            'avg_score': round(avg_score, 3),
            'severity':  severity,
            'degree':    degree,
        })

    nodes.sort(key=lambda x: (-x['degree'], -x['n']))

    return {'nodes': nodes, 'edges': edges}
