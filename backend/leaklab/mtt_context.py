"""
mtt_context.py — Sprint 2
Calcula contexto MTT real a partir do HH bruto:
  - Stack do hero em chips e em BBs
  - Custo de órbita
  - M ratio (Harrington)
  - ICM pressure (low / medium / high)
  - Tournament stage
  - Número de jogadores ativos
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional
from .models import ParsedHand

# ── Regex ─────────────────────────────────────────────────────────────────────
_LEVEL_RE  = re.compile(r'Level\s+[IVXLCDM]+\s+\((\d+)/(\d+)\)')
_ANTE_RE   = re.compile(r'posts the ante (\d+)')
_SEAT_RE   = re.compile(r'^Seat \d+: .+ \(\d+ in chips\)')
_STACK_RE  = re.compile(r'Seat \d+: {hero} \((\d+) in chips\)')
_FINISH_RE = re.compile(r'finished the tournament in (\d+)(?:st|nd|rd|th) place')


@dataclass
class MTTContext:
    # Stack
    hero_stack_chips: Optional[float]
    hero_stack_bb:    Optional[float]

    # Blinds
    sb:   float
    bb:   float
    ante: float

    # Órbita e M
    orbit_cost: float
    m_ratio:    Optional[float]   # M de Harrington

    # Stage
    active_players: int
    tournament_stage: str          # early / middle / late / final_table / heads_up

    # ICM pressure
    icm_pressure: str              # low / medium / high

    # Extras
    level_sb: float                # SB do nível atual (pode diferir do hand.sb)
    level_bb: float


def build_mtt_context(hand: ParsedHand) -> MTTContext:
    """Extrai contexto MTT completo de uma mão."""
    raw = hand.raw_text
    hero = hand.hero or ''

    # ── Blinds do nível ──────────────────────────────────────────────────────
    m = _LEVEL_RE.search(raw)
    level_sb = float(m.group(1)) if m else (hand.sb or 0.0)
    level_bb = float(m.group(2)) if m else (hand.bb or 1.0)
    bb = level_bb or 1.0

    # ── Ante ─────────────────────────────────────────────────────────────────
    antes = _ANTE_RE.findall(raw)
    ante = float(antes[0]) if antes else 0.0

    # ── Jogadores ativos ──────────────────────────────────────────────────────
    active_players = sum(
        1 for line in raw.splitlines()
        if _SEAT_RE.match(line.strip())
    )

    # ── Stack do hero ─────────────────────────────────────────────────────────
    hero_stack_chips: Optional[float] = None
    pattern = re.compile(
        r'Seat \d+: ' + re.escape(hero) + r' \((\d+) in chips\)'
    )
    mp = pattern.search(raw)
    if mp:
        hero_stack_chips = float(mp.group(1))

    hero_stack_bb = (
        round(hero_stack_chips / bb, 1)
        if hero_stack_chips is not None else None
    )

    # ── Custo de órbita e M ───────────────────────────────────────────────────
    orbit_cost = level_sb + level_bb + ante * active_players
    m_ratio: Optional[float] = None
    if hero_stack_chips is not None and orbit_cost > 0:
        m_ratio = round(hero_stack_chips / orbit_cost, 1)

    # ── Tournament stage ──────────────────────────────────────────────────────
    tournament_stage = _detect_stage(active_players, m_ratio)

    # ── ICM pressure ─────────────────────────────────────────────────────────
    icm_pressure = _detect_icm_pressure(m_ratio, active_players)

    return MTTContext(
        hero_stack_chips=hero_stack_chips,
        hero_stack_bb=hero_stack_bb,
        sb=level_sb,
        bb=level_bb,
        ante=ante,
        orbit_cost=orbit_cost,
        m_ratio=m_ratio,
        active_players=active_players,
        tournament_stage=tournament_stage,
        icm_pressure=icm_pressure,
        level_sb=level_sb,
        level_bb=level_bb,
    )


def _detect_stage(active_players: int, m_ratio: Optional[float]) -> str:
    """
    Detecta o estágio do torneio combinando jogadores e M ratio.
    Para single-table (9-max como nesse torneio):
      9-7 players → early/middle
      6-4 players → late
      3   players → final_table
      2   players → heads_up
    """
    if active_players <= 2:
        return 'heads_up'
    if active_players <= 3:
        return 'final_table'
    if active_players <= 5:
        return 'late'
    if active_players <= 7:
        return 'middle'
    return 'early'


def _detect_icm_pressure(m_ratio: Optional[float],
                          active_players: int) -> str:
    """
    ICM pressure baseado no M ratio e posição no torneio.
    
    Regras:
      - Final table (≤3 players): sempre high
      - M crítico (≤6): high
      - M curto (≤10) ou late stage: medium
      - Resto: low
    """
    if active_players <= 3:
        return 'high'
    if m_ratio is None:
        return 'low'
    if m_ratio <= 6:
        return 'high'
    if m_ratio <= 10 or active_players <= 5:
        return 'medium'
    return 'low'


def context_to_dict(ctx: MTTContext) -> dict:
    """Converte MTTContext para o formato esperado pelo Decision Engine."""
    return {
        'tournamentStage': ctx.tournament_stage,
        'icmPressure':     ctx.icm_pressure,
        'bountyDynamic':   False,
        'readsAvailable':  False,
        # Extras para auditoria / relatório
        'mRatio':          ctx.m_ratio,
        'heroStackBb':     ctx.hero_stack_bb,
        'activePlayers':   ctx.active_players,
    }
