"""
session_context.py — analisa o CONTEXTO DE SESSÃO (multi-tabling, fadiga, horário) cruzando
a janela de tempo de cada torneio (tournaments.started_at/ended_at) com a qualidade das
decisões (avg_score, menor = melhor). Objetivo, sem auto-relato: mede o efeito no jogo, não
o sentimento. Estende a filosofia do Cognitive Failure Mapper para o nível de SESSÃO.
"""
from datetime import datetime
from collections import defaultdict

_FMT = "%Y-%m-%d %H:%M:%S"
_SESSION_GAP_H = 2.0          # gap > 2h entre torneios = nova sessão
_MIN_TOURNAMENTS = 8          # amostra mínima total para não devolver ruído
_MIN_BUCKET = 2               # tornaments mínimos num balde para ele contar


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.strptime(str(ts)[:19], _FMT)
    except Exception:
        return None


def _wavg(pairs):
    """Média de score ponderada por nº de decisões. pairs = [(score, weight), ...]."""
    num = den = 0.0
    for sc, w in pairs:
        num += sc * w
        den += w
    return round(num / den, 4) if den else None


def _bucketize(rows, key_fn, order):
    """Agrupa rows por balde (key_fn) e devolve [{bucket, tournaments, decisions, avg_score}]
    na ordem `order`, só com baldes que têm amostra suficiente."""
    groups = defaultdict(list)
    for r in rows:
        groups[key_fn(r)].append(r)
    out = []
    for b in order:
        g = groups.get(b, [])
        if len(g) < _MIN_BUCKET:
            continue
        out.append({
            "bucket": b,
            "tournaments": len(g),
            "decisions": sum(r["dc"] for r in g),
            "avg_score": _wavg([(r["score"], r["dc"]) for r in g]),
        })
    return out


def analyze_session_context(tournaments: list) -> dict:
    """tournaments: dicts com started_at, ended_at, avg_score, decisions_count.
    Retorna {insufficient_data, multitabling[], time_of_day[], fatigue[]}."""
    rows = []
    for t in tournaments:
        s, e = _parse(t.get("started_at")), _parse(t.get("ended_at"))
        sc, dc = t.get("avg_score"), t.get("decisions_count") or 0
        if s and e and e >= s and sc is not None and dc > 0:
            rows.append({"s": s, "e": e, "score": float(sc), "dc": int(dc)})

    if len(rows) < _MIN_TOURNAMENTS:
        return {"insufficient_data": True, "sample": len(rows),
                "multitabling": [], "time_of_day": [], "fatigue": []}

    # ── Multi-tabling: nº de torneios cujas janelas se sobrepõem no tempo ──
    for i, a in enumerate(rows):
        overlaps = sum(1 for j, b in enumerate(rows)
                       if j != i and a["s"] <= b["e"] and b["s"] <= a["e"])
        lvl = 1 + overlaps
        a["mt"] = "1" if lvl == 1 else ("2-3" if lvl <= 3 else "4+")

    # ── Horário: faixa pela hora de início ──
    def _tod(r):
        h = r["s"].hour
        return "madrugada" if h < 6 else "manha" if h < 12 else "tarde" if h < 18 else "noite"

    # ── Fadiga: horas dentro da sessão (blocos contínuos, gap > 2h separa) ──
    ordered = sorted(rows, key=lambda r: r["s"])
    sess_start = ordered[0]["s"]
    prev_end = ordered[0]["e"]
    for r in ordered:
        if (r["s"] - prev_end).total_seconds() / 3600.0 > _SESSION_GAP_H:
            sess_start = r["s"]
        elapsed = (r["s"] - sess_start).total_seconds() / 3600.0
        r["fat"] = "0-1h" if elapsed < 1 else "1-2h" if elapsed < 2 else "2-3h" if elapsed < 3 else "3h+"
        prev_end = max(prev_end, r["e"])

    return {
        "insufficient_data": False,
        "sample": len(rows),
        "multitabling": _bucketize(rows, lambda r: r["mt"], ["1", "2-3", "4+"]),
        "time_of_day":  _bucketize(rows, _tod, ["madrugada", "manha", "tarde", "noite"]),
        "fatigue":      _bucketize(rows, lambda r: r["fat"], ["0-1h", "1-2h", "2-3h", "3h+"]),
    }
