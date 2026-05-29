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
from .icm import hero_icm_equity

# Stack por assento — cobre PokerStars/GGPoker ("(1500 in chips)") e o dialeto
# PartyGaming/888/PartyPoker ("( 500 )" / "( $826.51 )" / "( 86,425 )").
_SEAT_STACK_PSGG_RE = re.compile(r'^Seat \d+: (.+?) \(([0-9.]+) in chips\)', re.MULTILINE)
_SEAT_STACK_PG_RE   = re.compile(r'^Seat \d+: (.+?) \(\s*\$?([0-9,]+(?:\.[0-9]+)?)\s*\)\s*$', re.MULTILINE)

# Só calcula ICM em estágios de mesa final (custo combinatório + relevância).
_ICM_MAX_PLAYERS = 9

# ── Regex ─────────────────────────────────────────────────────────────────────
_LEVEL_RE  = re.compile(r'Level\s+([IVXLCDM]+)\s+\((\d+)/(\d+)\)')

_ROMAN = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
def _roman_to_int(s: str) -> int:
    result, prev = 0, 0
    for ch in reversed(s.upper()):
        v = _ROMAN.get(ch, 0)
        result += v if v >= prev else -v
        prev = v
    return result
_ANTE_RE   = re.compile(r'posts the ante (\d+)')
_SEAT_RE   = re.compile(r'^Seat \d+: .+ \([0-9.]+ in chips\)')
_STACK_RE  = re.compile(r'Seat \d+: {hero} \(([0-9.]+) in chips\)')
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

    # PKO context (bounty tournaments)
    is_pko: bool                   # detectado em hand.is_pko (bounties no seat / nome do torneio)

    # Extras
    level_sb:  float               # SB do nível atual (pode diferir do hand.sb)
    level_bb:  float
    level_num: int                 # número do nível (ex: XIV → 14)

    # ICM equity real (mesa final) — via calculate_icm vendorizado do PokerKit.
    # None fora de mesa final ou quando os stacks não são extraíveis.
    # payouts reais não vêm no HH → usa curva padrão normalizada (aproxima a
    # *forma* da pressão, não o valor monetário). Ver leaklab/icm.py.
    icm_equity_pct: Optional[float] = None   # equity ICM do hero (% do prize pool)
    icm_chip_pct:   Optional[float] = None   # fração de fichas do hero (%)
    icm_tax_pct:    Optional[float] = None   # chip% − equity% (prêmio de risco/sobrevivência)


def build_mtt_context(hand: ParsedHand) -> MTTContext:
    """Extrai contexto MTT completo de uma mão."""
    raw = hand.raw_text
    hero = hand.hero or ''

    # ── Blinds do nível ──────────────────────────────────────────────────────
    m = _LEVEL_RE.search(raw)
    level_num = _roman_to_int(m.group(1)) if m else 0
    level_sb  = float(m.group(2)) if m else (hand.sb or 0.0)
    level_bb  = float(m.group(3)) if m else (hand.bb or 1.0)
    bb = level_bb or 1.0

    # ── Ante ─────────────────────────────────────────────────────────────────
    antes = _ANTE_RE.findall(raw)
    ante = float(antes[0]) if antes else 0.0

    # ── Jogadores ativos ──────────────────────────────────────────────────────
    active_players = sum(
        1 for line in raw.splitlines()
        if _SEAT_RE.match(line.strip())
    )
    if active_players == 0:
        # Fallback dialeto PartyGaming (888/PartyPoker): "Seat 4: Hero ( 500 )"
        active_players = len(_SEAT_STACK_PG_RE.findall(raw))

    # ── Stack do hero ─────────────────────────────────────────────────────────
    hero_stack_chips: Optional[float] = None
    pattern = re.compile(
        r'Seat \d+: ' + re.escape(hero) + r' \(([0-9.]+) in chips\)'
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

    # ── PKO flag (vem do parser via hand.is_pko) ─────────────────────────────
    is_pko = bool(getattr(hand, 'is_pko', False))

    # ── ICM pressure ─────────────────────────────────────────────────────────
    # PKO alivia bubble pressure pré-bolha (bounty incentiva agressão).
    # Artigo GW: bubble factors menores para covering players em PKO.
    icm_pressure = _detect_icm_pressure(m_ratio, active_players, is_pko=is_pko)

    # ── ICM equity real (mesa final) ─────────────────────────────────────────
    icm_equity_pct = icm_chip_pct = icm_tax_pct = None
    if 2 <= active_players <= _ICM_MAX_PLAYERS:
        stacks, hero_idx = _extract_all_stacks(raw, hero)
        if hero_idx is not None and len(stacks) >= 2 and all(s > 0 for s in stacks):
            eq = hero_icm_equity(stacks, hero_idx)
            if eq:
                icm_equity_pct = eq['equity_pct']
                icm_chip_pct   = eq['chip_pct']
                icm_tax_pct    = eq['tax_pct']

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
        is_pko=is_pko,
        level_sb=level_sb,
        level_bb=level_bb,
        level_num=level_num,
        icm_equity_pct=icm_equity_pct,
        icm_chip_pct=icm_chip_pct,
        icm_tax_pct=icm_tax_pct,
    )


def _extract_all_stacks(raw: str, hero: str) -> tuple[list[float], Optional[int]]:
    """Extrai (stacks, índice_do_hero) de todos os assentos da mão.

    Cobre o formato PokerStars/GGPoker e o dialeto PartyGaming (888/PartyPoker).
    Retorna a lista de stacks na ordem dos assentos e o índice do hero (ou None).
    """
    matches = _SEAT_STACK_PSGG_RE.findall(raw) or _SEAT_STACK_PG_RE.findall(raw)
    stacks: list[float] = []
    hero_idx: Optional[int] = None
    for name, chips in matches:
        try:
            stacks.append(float(chips.replace(',', '')))
        except ValueError:
            continue
        if hero and name.strip() == hero.strip():
            hero_idx = len(stacks) - 1
    return stacks, hero_idx


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
                          active_players: int,
                          is_pko: bool = False) -> str:
    """
    ICM pressure baseado no M ratio e posição no torneio.

    Regras:
      - Final table (≤3 players): sempre high
      - M crítico (≤6): high
      - M curto (≤10) ou late stage: medium
      - Resto: low

    PKO: bubble factors são menores pré-bolha (bounty incentiva agressão).
    Artigo GW indica que covering players têm bubble factor ~1.22 vs ~1.27
    classic. Pra refletir isso no modelo simplificado, baixamos 1 nível de
    pressure (high→medium, medium→low) APENAS pré-final-table — perto da
    bolha o efeito do bounty atenua ("drown under rising risk premiums").
    """
    if active_players <= 3:
        return 'high'  # final table: PKO mantém pressão alta
    if m_ratio is None:
        return 'low'
    base = 'high' if m_ratio <= 6 else ('medium' if (m_ratio <= 10 or active_players <= 5) else 'low')
    if is_pko:
        # Atenua um nível pré-FT
        if base == 'high':   return 'medium'
        if base == 'medium': return 'low'
    return base


def context_to_dict(ctx: MTTContext) -> dict:
    """Converte MTTContext para o formato esperado pelo Decision Engine."""
    return {
        'tournamentStage': ctx.tournament_stage,
        'icmPressure':     ctx.icm_pressure,
        'bountyDynamic':   ctx.is_pko,  # True em PKO: bounty incentiva agressão
        'isPko':           ctx.is_pko,
        'readsAvailable':  False,
        # Extras para auditoria / relatório
        'mRatio':          ctx.m_ratio,
        'heroStackBb':     ctx.hero_stack_bb,
        'activePlayers':   ctx.active_players,
        'levelSb':         ctx.level_sb,
        'levelBb':         ctx.level_bb,
        'levelNum':        ctx.level_num,
        # ICM equity real (mesa final) — None fora dela. Ver leaklab/icm.py.
        'icmEquityPct':    ctx.icm_equity_pct,
        'icmChipPct':      ctx.icm_chip_pct,
        'icmTaxPct':       ctx.icm_tax_pct,
    }
