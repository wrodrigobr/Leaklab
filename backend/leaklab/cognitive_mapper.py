"""
Detects cognitive-emotional failure patterns from ordered decision sequences.

Patterns are identified by analysing sliding windows over the chronological
sequence of decisions within each tournament. Each pattern captures a specific
emotional reaction (tilt, fear, overconfidence) that manifests as a measurable
deviation in action quality following a trigger event.
"""

from collections import defaultdict
from typing import List, Dict, Any

_AGGRESSIVE = frozenset({"bet", "raise", "jam", "all-in", "all_in"})
_CALL       = frozenset({"call"})
_FOLD       = frozenset({"fold"})
_MISTAKES   = frozenset({"small_mistake", "clear_mistake"})
_STANDARD   = "standard"


def analyze_cognitive_failures(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detect cognitive-emotional failure patterns from an ordered decision list.

    decisions must be sorted by [tournament_id, id] (chronological within each tournament).
    Returns a dict with 'patterns', 'total_decisions', and 'insufficient_data'.
    """
    if len(decisions) < 30:
        return {"insufficient_data": True, "patterns": [], "total_decisions": len(decisions)}

    by_tournament: Dict[Any, List[Dict]] = defaultdict(list)
    for d in decisions:
        by_tournament[d["tournament_id"]].append(d)

    accum = {
        "revenge_aggression":  {"count": 0, "opps": 0},
        "fear_folding":        {"count": 0, "opps": 0},
        "sunk_cost":           {"count": 0, "opps": 0},
        "entitlement_tilt":    {"count": 0, "opps": 0},
        "compensation_call":   {"count": 0, "opps": 0},
    }

    for t_decisions in by_tournament.values():
        if len(t_decisions) < 5:
            continue
        _revenge_aggression(t_decisions, accum["revenge_aggression"])
        _fear_folding(t_decisions, accum["fear_folding"])
        _sunk_cost(t_decisions, accum["sunk_cost"])
        _entitlement_tilt(t_decisions, accum["entitlement_tilt"])
        _compensation_call(t_decisions, accum["compensation_call"])

    patterns = []
    for ptype, a in accum.items():
        if a["opps"] < 3 or a["count"] < 2:
            continue
        freq = a["count"] / a["opps"]
        sev = "high" if freq >= 0.40 else ("medium" if freq >= 0.20 else "low")
        patterns.append({
            "type":      ptype,
            "count":     a["count"],
            "frequency": round(freq, 3),
            "severity":  sev,
        })

    patterns.sort(key=lambda x: x["frequency"], reverse=True)
    return {
        "insufficient_data": False,
        "patterns":          patterns[:5],
        "total_decisions":   len(decisions),
    }


# ── Pattern detectors ─────────────────────────────────────────────────────────

def _revenge_aggression(decisions: List[Dict], a: Dict) -> None:
    """After 3+ consecutive standard folds, next 5 decisions contain 2+ aggressive mistakes."""
    n, i = len(decisions), 0
    while i < n:
        run, j = 0, i
        while j < n and decisions[j]["action_taken"] in _FOLD and decisions[j]["label"] == _STANDARD:
            run += 1
            j += 1
        if run >= 3:
            a["opps"] += 1
            hits = sum(
                1 for d in decisions[j:j + 5]
                if d["action_taken"] in _AGGRESSIVE and d["label"] in _MISTAKES
            )
            if hits >= 2:
                a["count"] += 1
            i = max(j, i + 1)
        else:
            i += 1


def _fear_folding(decisions: List[Dict], a: Dict) -> None:
    """After 2+ consecutive aggressive mistakes (blowup), next 5 decisions contain 2+ fold mistakes."""
    n, i = len(decisions), 0
    while i < n:
        run, j = 0, i
        while j < n and decisions[j]["action_taken"] in _AGGRESSIVE and decisions[j]["label"] in _MISTAKES:
            run += 1
            j += 1
        if run >= 2:
            a["opps"] += 1
            hits = sum(
                1 for d in decisions[j:j + 5]
                if d["action_taken"] in _FOLD and d["label"] in _MISTAKES
            )
            if hits >= 2:
                a["count"] += 1
            i = max(j, i + 1)
        else:
            i += 1


def _sunk_cost(decisions: List[Dict], a: Dict) -> None:
    """Hands where call mistakes occur on 2+ different streets (chasing across streets)."""
    by_hand: Dict[Any, List[Dict]] = defaultdict(list)
    for d in decisions:
        hid = d.get("hand_id") or ""
        by_hand[hid].append(d)

    for hand in by_hand.values():
        if len(hand) < 3:
            continue
        bad_calls = [d for d in hand if d["action_taken"] in _CALL and d["label"] in _MISTAKES]
        streets   = {d.get("street") for d in bad_calls}
        if len(bad_calls) >= 2 and len(streets) >= 2:
            a["opps"] += 1
            if len(bad_calls) >= 3:
                a["count"] += 1


def _entitlement_tilt(decisions: List[Dict], a: Dict) -> None:
    """After 5+ consecutive standard decisions, next 5 decisions contain 3+ mistakes."""
    n, i = len(decisions), 0
    while i < n:
        run, j = 0, i
        while j < n and decisions[j]["label"] == _STANDARD:
            run += 1
            j += 1
        if run >= 5:
            a["opps"] += 1
            hits = sum(1 for d in decisions[j:j + 5] if d["label"] in _MISTAKES)
            if hits >= 3:
                a["count"] += 1
            i = max(j, i + 1)
        else:
            i += 1


def _compensation_call(decisions: List[Dict], a: Dict) -> None:
    """After a correct fold, next 3 decisions contain 2+ call mistakes."""
    n = len(decisions)
    for i in range(n - 3):
        d = decisions[i]
        if d["action_taken"] in _FOLD and d["label"] == _STANDARD:
            a["opps"] += 1
            hits = sum(
                1 for w in decisions[i + 1:i + 4]
                if w["action_taken"] in _CALL and w["label"] in _MISTAKES
            )
            if hits >= 2:
                a["count"] += 1
