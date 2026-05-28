"""
elo_engine.py — Sistema de rating ELO adaptado pra poker.

Conceito: cada decisão do hero é uma "partida" contra o solver GTO (rating
fixo = SOLVER_ELO). O score real S é derivado do gto_label:

    gto_correct          → 1.0  (mão jogada como solver indica; ganhou a partida)
    gto_mixed            → 0.7  (mão jogada como solver indica numa das ações mistas)
    gto_minor_deviation  → 0.4  (desvio pequeno; empate técnico)
    gto_critical         → 0.0  (desvio grave; perdeu a partida)

Para decisões sem gto_label (cobertura faltante), usa fallback baseado em label:
    standard/marginal → 0.6
    small_mistake     → 0.3
    clear_mistake     → 0.0

Fórmula clássica:
    R' = R + K * (S - E)
    E  = 1 / (1 + 10^((R_solver - R) / 400))
    K  = 32 (< 100 decisões), 16 (100-1000), 8 (>1000)

Aplica-se SEQUENCIALMENTE — cada decisão atualiza o rating, que afeta o cálculo
da próxima. Decisões processadas em ordem cronológica (created_at).

Rating separado por street + agregado total. Bandas:
    < 1200       : Iniciante
    1200 - 1499  : Casual
    1500 - 1799  : Em desenvolvimento
    1800 - 2099  : Sólido
    2100 - 2399  : Avançado
    >= 2400      : Elite
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

# BENCHMARK_ELO = rating de referência ("par") contra o qual cada decisão é
# pontuada. Calibrado em 1500 = jogador médio. Acertar GTO (S alto) empurra o
# rating acima do par; errar empurra abaixo. NÃO é "a força do solver" — é o
# baseline da plataforma. Com 1500, a escala fica espalhada: ~70% aderência →
# ~1680, ~85% → ~1800, ~99% → 2400+. (Antes era 3000, comprimia todo mundo no
# topo: avg S 0.71 estabilizava em ~3060 = todos "Elite".)
SOLVER_ELO    = 1500
INITIAL_ELO   = 1500
ELO_DIVISOR   = 400.0   # diff de 400 = razão 10:1 esperada

# Score real (S) por classificação GTO
GTO_LABEL_SCORE: dict[str, float] = {
    "gto_correct":         1.0,
    "gto_mixed":           0.7,
    "gto_minor_deviation": 0.4,
    "gto_critical":        0.0,
}

# NOTA: decisões SEM gto_label são EXCLUÍDAS do rating (não usamos fallback
# heurístico). Decisão de produto (2026-05-28): o ELO só conta spots com
# análise de solver GTO — garante que o rating reflete aderência real ao
# equilíbrio, sem ruído do engine heurístico. Spots sem cobertura GTO são
# pulados (não afetam o rating pra cima nem pra baixo).

# K-factor dinâmico por experiência (n_decisions processadas)
def k_factor(n_decisions: int) -> int:
    if n_decisions < 100:   return 32
    if n_decisions < 1000:  return 16
    return 8

# Bandas (cor e label). Acima de 2700 = jogadores que vencem o solver em
# acuracia (raro; geralmente players preflop-puristas com base grande de
# decisoes preflop bem cobertas).
BANDS: list[tuple[int, str, str]] = [
    (0,    "Iniciante",         "#94a3b8"),  # slate-400
    (1200, "Casual",             "#fbbf24"),  # amber-400
    (1500, "Em desenvolvimento", "#38bdf8"),  # sky-400
    (1800, "Sólido",             "#34d399"),  # emerald-400
    (2100, "Avançado",           "#a78bfa"),  # violet-400
    (2400, "Elite",              "#f472b6"),  # pink-400
    (2700, "Master",             "#ef4444"),  # red-500
    (3000, "Grandmaster",        "#facc15"),  # yellow-400
]


def band_for(elo: float) -> tuple[str, str]:
    """Retorna (label, hex_color) da banda do ELO dado."""
    chosen = BANDS[0]
    for threshold, label, color in BANDS:
        if elo >= threshold:
            chosen = (threshold, label, color)
    return chosen[1], chosen[2]


# ── Núcleo ELO ────────────────────────────────────────────────────────────────

def expected_score(player_elo: float, opponent_elo: float = SOLVER_ELO) -> float:
    """Probabilidade esperada de ganhar contra o oponente, formula ELO clássica."""
    return 1.0 / (1.0 + 10.0 ** ((opponent_elo - player_elo) / ELO_DIVISOR))


def decision_score(gto_label: Optional[str], engine_label: Optional[str] = None) -> Optional[float]:
    """
    Retorna S (score real) pra decisão. None quando NÃO há gto_label —
    essas decisões são excluídas do rating (sem fallback heurístico).
    `engine_label` mantido na assinatura por compat, mas não usado.
    """
    if gto_label and gto_label in GTO_LABEL_SCORE:
        return GTO_LABEL_SCORE[gto_label]
    return None


def apply_decision(current_elo: float, score_S: float, n_decisions: int) -> float:
    """Atualiza ELO após uma decisão. Retorna novo ELO (float)."""
    E = expected_score(current_elo, SOLVER_ELO)
    K = k_factor(n_decisions)
    return current_elo + K * (score_S - E)


# ── Cálculo agregado por player ───────────────────────────────────────────────

@dataclass
class StreetElo:
    elo:               float
    n_decisions:       int
    band_label:        str
    band_color:        str


@dataclass
class PlayerEloSnapshot:
    user_id:           int
    overall:           StreetElo
    by_street:         dict[str, StreetElo]   # 'preflop'/'flop'/'turn'/'river'
    total_decisions:   int
    calculated_at:     str


def compute_player_elo_from_decisions(
    user_id: int, decisions: list[dict]
) -> PlayerEloSnapshot:
    """
    Calcula ELO de um jogador processando lista de decisions em ordem.

    `decisions`: lista de dicts com pelo menos {street, gto_label, label, created_at}.
    Decisões SEM score derivável (sem gto_label nem label classificável) são
    puladas (não afetam ELO).

    Retorna snapshot com ELO agregado + per-street + total processado.
    """
    # ELO independente por street + agregado overall
    elo_by_street: dict[str, float] = {}
    n_by_street:   dict[str, int]   = {}
    elo_overall = INITIAL_ELO
    n_overall   = 0

    # Ordena por created_at (defensive — assumindo já vem ordenado por caller)
    decisions_sorted = sorted(
        decisions,
        key=lambda d: (str(d.get("created_at") or ""), int(d.get("id") or 0)),
    )

    for d in decisions_sorted:
        street = str(d.get("street") or "").lower()
        if street not in ("preflop", "flop", "turn", "river"):
            continue
        score = decision_score(d.get("gto_label"), d.get("label"))
        if score is None:
            continue

        # Update street-specific
        cur_s = elo_by_street.get(street, INITIAL_ELO)
        n_s   = n_by_street.get(street, 0)
        elo_by_street[street] = apply_decision(cur_s, score, n_s)
        n_by_street[street]   = n_s + 1

        # Update overall
        elo_overall = apply_decision(elo_overall, score, n_overall)
        n_overall  += 1

    import datetime
    now_iso = datetime.datetime.utcnow().isoformat()

    overall_band = band_for(elo_overall)
    overall = StreetElo(
        elo=round(elo_overall, 1),
        n_decisions=n_overall,
        band_label=overall_band[0],
        band_color=overall_band[1],
    )

    by_street_out: dict[str, StreetElo] = {}
    for st in ("preflop", "flop", "turn", "river"):
        if st in elo_by_street:
            b = band_for(elo_by_street[st])
            by_street_out[st] = StreetElo(
                elo=round(elo_by_street[st], 1),
                n_decisions=n_by_street[st],
                band_label=b[0],
                band_color=b[1],
            )

    return PlayerEloSnapshot(
        user_id=user_id,
        overall=overall,
        by_street=by_street_out,
        total_decisions=n_overall,
        calculated_at=now_iso,
    )


def snapshot_to_dict(s: PlayerEloSnapshot) -> dict:
    """Serializa snapshot pra dict JSON-friendly (resposta de API)."""
    return {
        "user_id":         s.user_id,
        "overall": {
            "elo":          s.overall.elo,
            "n_decisions":  s.overall.n_decisions,
            "band_label":   s.overall.band_label,
            "band_color":   s.overall.band_color,
        },
        "by_street": {
            st: {
                "elo":         v.elo,
                "n_decisions": v.n_decisions,
                "band_label":  v.band_label,
                "band_color":  v.band_color,
            }
            for st, v in s.by_street.items()
        },
        "total_decisions": s.total_decisions,
        "calculated_at":   s.calculated_at,
        "bands": [
            {"threshold": t, "label": l, "color": c}
            for (t, l, c) in BANDS
        ],
        "solver_elo":      SOLVER_ELO,
        "initial_elo":     INITIAL_ELO,
    }
