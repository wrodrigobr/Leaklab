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

Rating separado por street + agregado total. Bandas (fonte: BANDS abaixo):
    < 1570       : Iniciante   (<60% aderência GTO)
    1570 - 1646  : Estudante   (60-70%)
    1647 - 1709  : Grinder     (70-77%)
    1710 - 1815  : Regular     (77-86%)
    1816 - 1923  : Sólido      (86-92%)
    1924 - 2052  : Expert      (92-96%)
    >= 2053      : Elite       (>=96%)
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

# Decay por inatividade (Sprint 2). O ELO "esfria" enquanto o jogador não
# importa torneios, incentivando consistência. Aplicado na LEITURA (cresce com o
# tempo parado, sem precisar de novo upload). Padrões: −2/semana, carência de 1
# semana (não pune logo), cap total −20 (≈10 semanas), piso no INITIAL_ELO
# (nunca rebaixa abaixo do par nem decai quem já está no/abaixo dele).
DECAY_PER_WEEK    = 2.0
DECAY_GRACE_WEEKS = 1.0
DECAY_MAX         = 20.0

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

# Bandas = os 7 níveis de carreira (UNIFICADO 2026-05-28). Os thresholds de ELO
# foram derivados dos thresholds de aderência GTO históricos do sistema de
# níveis, via a fórmula de equilíbrio ELO (benchmark 1500):
#     ELO(S) = 1500 - 400 * log10((1-S)/S)
# Mapeamento aderência → ELO:
#     60% → 1570 | 70% → 1647 | 77% → 1710 | 86% → 1816 | 92% → 1924 | 96% → 2053
# (icon, label, hex_color) por threshold.
BANDS: list[tuple[int, str, str, str]] = [
    (0,    "🎯", "Iniciante", "#94a3b8"),  # slate-400   (<60% aderência)
    (1570, "📖", "Estudante", "#60a5fa"),  # blue-400    (60-70%)
    (1647, "⚙️", "Grinder",   "#fbbf24"),  # amber-400   (70-77%)
    (1710, "📈", "Regular",   "#34d399"),  # emerald-400 (77-86%)
    (1816, "🔷", "Sólido",    "#22d3ee"),  # cyan-400    (86-92%)
    (1924, "♠",  "Expert",    "#a78bfa"),  # violet-400  (92-96%)
    (2053, "👑", "Elite",     "#facc15"),  # yellow-400  (≥96%)
]


def band_full(elo: float) -> tuple[str, str, str]:
    """Retorna (icon, label, hex_color) do nível do ELO dado."""
    chosen = BANDS[0]
    for entry in BANDS:
        if elo >= entry[0]:
            chosen = entry
    return chosen[1], chosen[2], chosen[3]


def band_for(elo: float) -> tuple[str, str]:
    """Retorna (label, hex_color) — compat. Use band_full pra incluir icon."""
    _icon, label, color = band_full(elo)
    return label, color


def next_band_for(elo: float) -> Optional[dict]:
    """Próximo nível + progresso (0..1) + ELO faltante. None se já no topo (Elite)."""
    for i, entry in enumerate(BANDS):
        if elo < entry[0]:
            prev = BANDS[i - 1] if i > 0 else BANDS[0]
            span = entry[0] - prev[0]
            prog = (elo - prev[0]) / span if span > 0 else 1.0
            return {
                "label":     entry[2],
                "icon":      entry[1],
                "threshold": entry[0],
                "progress":  round(max(0.0, min(1.0, prog)), 3),
                "elo_to_go": round(entry[0] - elo, 1),
            }
    return None


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


def apply_inactivity_decay(elo: float, weeks_inactive: float) -> tuple[float, float]:
    """Aplica decay por inatividade. Retorna (elo_ajustado, pontos_decaídos).

    Só "esfria" ratings acima do par (INITIAL_ELO): quem já está no/abaixo dele
    não decai. Carência de DECAY_GRACE_WEEKS antes de começar; −DECAY_PER_WEEK por
    semana; cap total DECAY_MAX; piso no INITIAL_ELO.
    """
    if elo <= INITIAL_ELO or weeks_inactive <= DECAY_GRACE_WEEKS:
        return round(elo, 1), 0.0
    decayable = weeks_inactive - DECAY_GRACE_WEEKS
    penalty   = min(decayable * DECAY_PER_WEEK, DECAY_MAX)
    decayed   = max(elo - penalty, float(INITIAL_ELO))
    return round(decayed, 1), round(elo - decayed, 1)


# ── Cálculo agregado por player ───────────────────────────────────────────────

@dataclass
class StreetElo:
    elo:               float
    n_decisions:       int
    band_icon:         str
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

    oi, ol, oc = band_full(elo_overall)
    overall = StreetElo(
        elo=round(elo_overall, 1),
        n_decisions=n_overall,
        band_icon=oi,
        band_label=ol,
        band_color=oc,
    )

    by_street_out: dict[str, StreetElo] = {}
    for st in ("preflop", "flop", "turn", "river"):
        if st in elo_by_street:
            bi, bl, bc = band_full(elo_by_street[st])
            by_street_out[st] = StreetElo(
                elo=round(elo_by_street[st], 1),
                n_decisions=n_by_street[st],
                band_icon=bi,
                band_label=bl,
                band_color=bc,
            )

    return PlayerEloSnapshot(
        user_id=user_id,
        overall=overall,
        by_street=by_street_out,
        total_decisions=n_overall,
        calculated_at=now_iso,
    )


# ── Stake bracket (Sprint 2 #19) ──────────────────────────────────────────────
# Faixas por buy-in ($). ELO segmentado: jogar bem em micro ≠ em high-stakes.
STAKE_BRACKETS = [
    ("micro", 0.0,   5.0),            # ≤ $5
    ("low",   5.0,   25.0),           # $5–25
    ("mid",   25.0,  100.0),          # $25–100
    ("high",  100.0, float("inf")),   # > $100
]
# Mínimo de decisões com gto_label numa faixa pra ela ser exibida (evita ruído).
MIN_STAKE_DECISIONS = 20


def bracket_for(buy_in: Optional[float]) -> Optional[str]:
    """Faixa de stake do buy-in. None quando ausente/≤0 (ex.: freeroll/sem dado)."""
    if buy_in is None or buy_in <= 0:
        return None
    for name, lo, hi in STAKE_BRACKETS:
        if lo < buy_in <= hi:
            return name
    return None


def compute_player_elo_by_stake(user_id: int, decisions: list[dict]) -> dict[str, PlayerEloSnapshot]:
    """ELO segmentado por faixa de stake. `decisions` precisam ter `buy_in`.
    Retorna {bracket: snapshot} só para faixas com ≥ MIN_STAKE_DECISIONS scored."""
    by_bracket: dict[str, list[dict]] = {}
    for d in decisions:
        b = bracket_for(d.get("buy_in"))
        if b:
            by_bracket.setdefault(b, []).append(d)

    out: dict[str, PlayerEloSnapshot] = {}
    for b, decs in by_bracket.items():
        snap = compute_player_elo_from_decisions(user_id, decs)
        if snap.total_decisions >= MIN_STAKE_DECISIONS:
            out[b] = snap
    return out


def compute_elo_curve(decisions: list[dict]) -> list[dict]:
    """
    Calcula a curva de ELO torneio-a-torneio: processa decisions em ordem e
    grava o ELO overall ao FINAL de cada torneio.

    `decisions`: dicts com {tournament_id, street, gto_label, created_at} já
    ordenados cronologicamente (por imported_at do torneio + ordem da decisão).

    Retorna [{tournament_id, elo, n_decisions}] — um ponto por torneio que
    teve ao menos 1 decisão com gto_label.
    """
    elo = INITIAL_ELO
    n   = 0
    curve: list[dict] = []
    cur_tid = None
    tid_had_decision = False

    def _flush(tid):
        if tid is not None and tid_had_decision:
            curve.append({"tournament_id": tid, "elo": round(elo, 1), "n_decisions": n})

    for d in decisions:
        tid = d.get("tournament_id")
        if tid != cur_tid:
            _flush(cur_tid)
            cur_tid = tid
            tid_had_decision = False
        score = decision_score(d.get("gto_label"), d.get("label"))
        if score is None:
            continue
        elo = apply_decision(elo, score, n)
        n  += 1
        tid_had_decision = True

    _flush(cur_tid)
    return curve


def snapshot_to_dict(s: PlayerEloSnapshot) -> dict:
    """Serializa snapshot pra dict JSON-friendly (resposta de API)."""
    return {
        "user_id":         s.user_id,
        "overall": {
            "elo":          s.overall.elo,
            "n_decisions":  s.overall.n_decisions,
            "band_icon":    s.overall.band_icon,
            "band_label":   s.overall.band_label,
            "band_color":   s.overall.band_color,
        },
        "next_band":       next_band_for(s.overall.elo),
        "by_street": {
            st: {
                "elo":         v.elo,
                "n_decisions": v.n_decisions,
                "band_icon":   v.band_icon,
                "band_label":  v.band_label,
                "band_color":  v.band_color,
            }
            for st, v in s.by_street.items()
        },
        "total_decisions": s.total_decisions,
        "calculated_at":   s.calculated_at,
        "bands": [
            {"threshold": t, "icon": ic, "label": l, "color": c}
            for (t, ic, l, c) in BANDS
        ],
        "solver_elo":      SOLVER_ELO,
        "initial_elo":     INITIAL_ELO,
    }
