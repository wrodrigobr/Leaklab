"""
leaderboard.py — Ranking de alunos por APRENDIZADO (não por $). Item #15, Sprint 1
(fundação: motor de pontuação puro + ranqueamento; UI/cron/opt-in deferidos).

Dimensões (pesos do backlog):
  A. Aderência GTO   (40%) — aligned_pct (gto_correct + gto_mixed) sobre os spots com solver.
  B. Evolução        (30%) — melhora de aderência (metade recente vs. inicial das decisões).
  C. Engajamento     (20%) — drills completados + torneios importados no período.
  D. Volume (guarda) (10%) — escala com mãos analisadas (anti micro-amostra).

Guarda de elegibilidade (não entra no ranking sem isto): mín. de mãos, torneios e
decisões com cobertura GTO — evita gaming com amostra minúscula.

Funções PURAS (sem DB) — o assembler de dados e o endpoint ficam em repositories/app.
"""
from __future__ import annotations

from .elo_engine import expected_score, INITIAL_ELO

# ── Pesos das dimensões (somam 1.0) ───────────────────────────────────────────
# Calibração skill-first: aderência GTO domina (metade do score) — o melhor
# jogador (maior aderência) fica no topo, sem que volume/engajamento o ultrapassem.
# Evolução ainda pesa (incentiva melhora); engajamento/volume são guardas menores.
W_GTO = 0.60
W_EVO = 0.20
W_ENG = 0.10
W_VOL = 0.10

# ── Guarda de elegibilidade ───────────────────────────────────────────────────
MIN_HANDS         = 500   # mãos analisadas
MIN_TOURNAMENTS   = 10    # torneios importados
MIN_GTO_DECISIONS = 100   # decisões com gto_label (cobertura mínima p/ aderência confiável)

# ── Alvos de normalização (valor que satura a dimensão em 1.0) ────────────────
TARGET_DRILLS      = 20.0
TARGET_TOURNAMENTS = 20.0
TARGET_HANDS       = 2000.0
EVO_SCALE          = 2.5   # ±0.2 de melhora de aderência → ±0.5 → satura a banda


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _norm(value: float, target: float) -> float:
    """Normaliza para 0..1 saturando em `target`."""
    if target <= 0:
        return 0.0
    return _clamp(value / target)


def eligibility(m: dict) -> tuple[bool, str | None]:
    """(elegível, motivo). Motivo None quando elegível."""
    if (m.get("hands") or 0) < MIN_HANDS:
        return False, "insufficient_hands"
    if (m.get("tournaments") or 0) < MIN_TOURNAMENTS:
        return False, "insufficient_tournaments"
    if (m.get("gto_decisions") or 0) < MIN_GTO_DECISIONS:
        return False, "insufficient_gto_coverage"
    return True, None


def score_player(m: dict) -> dict:
    """Calcula score (0..100) e o breakdown das 4 dimensões para um jogador.

    `m`: {user_id, display_name?, aligned_pct, aligned_early, aligned_recent,
          drills, tournaments, hands, gto_decisions}
    Retorna o dict de entrada enriquecido com {eligible, reason, score, dimensions}.
    """
    eligible, reason = eligibility(m)

    # A — aderência GTO via ELO: expected_score(elo) = prob. de bater o jogador
    # médio (par 1500). Mais principiado que aligned_pct cru (o ELO já pondera
    # dificuldade por K-factor e é auto-calibrado). aligned_pct segue no dict
    # para a evolução (B) e o desempate.
    a = expected_score(float(m.get("player_elo") or INITIAL_ELO))        # A — aderência GTO (ELO)
    evo_delta = float(m.get("aligned_recent") or 0.0) - float(m.get("aligned_early") or 0.0)
    b = _clamp(0.5 + evo_delta * EVO_SCALE)                              # B — evolução
    c = (_norm(m.get("drills") or 0, TARGET_DRILLS)
         + _norm(m.get("tournaments") or 0, TARGET_TOURNAMENTS)) / 2.0   # C — engajamento
    d = _norm(m.get("hands") or 0, TARGET_HANDS)                         # D — volume

    score = 100.0 * (W_GTO * a + W_EVO * b + W_ENG * c + W_VOL * d)

    return {
        **m,
        "eligible": eligible,
        "reason":   reason,
        "score":    round(score, 1),
        "dimensions": {
            "gto":        round(a * 100, 1),
            "evolution":  round(b * 100, 1),
            "engagement": round(c * 100, 1),
            "volume":     round(d * 100, 1),
        },
    }


def rank_leaderboard(players: list[dict]) -> dict:
    """Pontua todos, separa elegíveis × inelegíveis, ordena e atribui rank.

    Retorna {ranked: [...rank 1..N], ineligible: [...com reason]}.
    Ordenação determinística: score desc, depois aderência desc, depois user_id asc.
    """
    scored = [score_player(p) for p in players]
    eligible = [p for p in scored if p["eligible"]]
    ineligible = [p for p in scored if not p["eligible"]]

    eligible.sort(
        key=lambda p: (-p["score"], -float(p.get("aligned_pct") or 0.0), p.get("user_id", 0))
    )
    for i, p in enumerate(eligible, start=1):
        p["rank"] = i

    return {"ranked": eligible, "ineligible": ineligible}


# ── Opt-in / privacidade (#15) ────────────────────────────────────────────────
def _public_name(p: dict) -> str:
    """Nome exibido publicamente: handle (anonimato) quando definido, senão username."""
    return (p.get("handle") or "").strip() or p.get("username") or p.get("display_name") or "—"


def _strip_private(p: dict) -> dict:
    """Linha pública: troca o nome pelo handle e remove campos sensíveis (username
    cru, handle, flag de opt-in) para não vazar identidade de quem usou apelido."""
    pub = {k: v for k, v in p.items() if k not in ("username", "handle", "opt_in")}
    pub["display_name"] = _public_name(p)
    return pub


def public_view(result: dict, viewer_id: int | None = None) -> dict:
    """Aplica opt-in/privacidade ao resultado de `rank_leaderboard`:

      - `ranked` / `ineligible` só incluem quem **optou** (opt_in=True),
        re-ranqueados 1..N de forma contígua (sem expor que há jogadores ocultos),
        com nome via handle (anonimização).
      - `me`: a linha do **próprio viewer** sempre (com nome real e suas prefs),
        com `rank` = posição no ranking público se estiver lá, senão None — assim o
        usuário vê seu score mesmo fora do ranking público, com um empurrão pra optar.

    Função pura (sem DB) — testável isoladamente.
    """
    ranked_all     = result.get("ranked", [])
    ineligible_all = result.get("ineligible", [])

    pub_ranked = [p for p in ranked_all if p.get("opt_in")]
    out_ranked = []
    for i, p in enumerate(pub_ranked, start=1):
        row = _strip_private(p)
        row["rank"] = i
        out_ranked.append(row)

    out_ineligible = [_strip_private(p) for p in ineligible_all if p.get("opt_in")]

    me = None
    if viewer_id is not None:
        rank_by_uid = {p["user_id"]: i for i, p in enumerate(pub_ranked, start=1)}
        for p in [*ranked_all, *ineligible_all]:
            if p.get("user_id") == viewer_id:
                me = {
                    **p,
                    "is_self":      True,
                    "display_name": p.get("username") or p.get("display_name"),
                    "opt_in":       bool(p.get("opt_in")),
                    "handle":       (p.get("handle") or "").strip() or None,
                    "rank":         rank_by_uid.get(viewer_id),  # None se não está no público
                    "overall_rank": p.get("rank"),               # posição entre TODOS os elegíveis (base do delta)
                }
                break

    return {"ranked": out_ranked, "ineligible": out_ineligible, "me": me}
