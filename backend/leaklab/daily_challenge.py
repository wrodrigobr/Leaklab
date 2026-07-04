"""
Desafio do Dia (#42) — geração de CANDIDATOS com filtro de CERTEZA.

Não podemos falhar no gabarito. Um candidato só é proposto (pra aprovação do admin)
se o GTO tem uma resposta DOMINANTE (não coin-flip) E nossa heurística CONCORDA com
o range GW. O admin ainda aprova antes de virar desafio (o carimbo final). Coin-flip
50/50 é descartado de propósito (impossível gradear com certeza).

Fase 2 (fora daqui): spots postflop do gto_nodes (#41), voto adversarial do LLM.
"""
from __future__ import annotations
import json
import random as _random

from leaklab.leak_trainer import generate_canonical_spot, grade_canonical_spot
from leaklab.preflop_range_evaluator import _recommended_action

# Resposta dominante: a ação top do GTO com freq ≥ isto → temos certeza do gabarito.
DOMINANT_FREQ = 0.85
_CH_STACKS = [30, 40, 50]


def _norm(a: str) -> str:
    a = (a or '').strip().lower()
    return 'allin' if a in ('jam', 'shove', 'all-in', 'allin') else a


def _categories() -> list[dict]:
    """Grade de categorias (scenario × posição × vs × stack). generate_canonical_spot
    valida a cobertura (combos inválidos viram None e são pulados)."""
    cats: list[dict] = []
    for pos in ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB']:
        cats.append({'key': f'rfi:{pos}', 'scenario': 'rfi', 'position': pos, 'vs_position': ''})
    for defe in ['BB', 'SB', 'BTN', 'CO', 'HJ']:
        for opener in ['UTG', 'LJ', 'HJ', 'CO', 'BTN']:
            if defe != opener:
                cats.append({'key': f'vs_rfi:{defe}:{opener}', 'scenario': 'vs_rfi',
                             'position': defe, 'vs_position': opener})
    for opener in ['UTG', 'LJ', 'CO', 'BTN']:
        for tb in ['CO', 'BTN', 'SB', 'BB']:
            if opener != tb:
                cats.append({'key': f'vs_3bet:{opener}:{tb}', 'scenario': 'vs_3bet',
                             'position': opener, 'vs_position': tb})
    return cats


def _cards_str(hero_cards) -> str:
    """[{'rank':'A','suit':'s'},...] → 'AsKs' (formato do _recommended_action)."""
    try:
        return ''.join(f"{c['rank']}{c['suit']}" for c in hero_cards)
    except Exception:
        return str(hero_cards or '')


def _certainty(spot: dict):
    """Retorna (answer, top_freq, strategy) se o spot tem gabarito CERTO:
    GTO dominante (top freq ≥ DOMINANT_FREQ) E heurística concorda com o range.
    Senão None (descarta — não temos certeza)."""
    g = grade_canonical_spot(spot, 'fold')          # grade só pra ler a estratégia GTO
    strat = g.get('gto_strategy') or []
    if not strat:
        return None
    top = strat[0]
    top_action = _norm(top.get('action'))
    top_freq = float(top.get('freq') or 0)
    if top_freq < DOMINANT_FREQ:                     # coin-flip / misto → sem certeza
        return None
    # Heurística tem que concordar (triangulação: range GW == heurística local).
    try:
        h = _norm(_recommended_action(
            _cards_str(spot.get('hero_cards')), spot.get('position', ''),
            float(spot.get('facing_size', 0) or 0),
            stack_bb=float(spot.get('stack_bb', 50) or 50),
            faces_3bet=bool(spot.get('is_3bet_pot')),
        ))
    except Exception:
        return None
    if h != top_action:
        return None
    return top_action, round(top_freq, 4), strat


def _note(spot: dict, answer: str, freq: float) -> str:
    """Descrição legível pro admin curar."""
    sc = spot.get('scenario'); pos = spot.get('position'); vs = spot.get('vs_position')
    ctx = {'rfi': f"{pos} abre", 'vs_rfi': f"{pos} vs open de {vs}",
           'vs_3bet': f"{pos} abre e enfrenta 3-bet de {vs}"}.get(sc, sc)
    return f"{ctx} · {spot.get('stack_bb')}bb · mão {spot.get('hand')} → GTO {answer} {round(freq*100)}%"


def build_candidates(n: int = 10, rng: _random.Random | None = None) -> list[dict]:
    """Gera até `n` candidatos que passam no filtro de certeza. Cada candidato:
    {spot_json, answer, note}. O admin aprova antes de qualquer um virar desafio."""
    rng = rng or _random.Random()
    cats = _categories()
    rng.shuffle(cats)
    out: list[dict] = []
    seen: set = set()
    for cat in cats:
        if len(out) >= n:
            break
        c = dict(cat)
        c['stack_bb'] = rng.choice(_CH_STACKS)
        spot = generate_canonical_spot(c, rng)
        if not spot:
            continue
        cert = _certainty(spot)
        if not cert:
            continue
        answer, freq, _strat = cert
        sig = (spot.get('scenario'), spot.get('position'), spot.get('vs_position'),
               spot.get('stack_bb'), spot.get('hand'))
        if sig in seen:
            continue
        seen.add(sig)
        out.append({
            'spot_json': json.dumps(spot),
            'answer':    answer,
            'note':      _note(spot, answer, freq),
        })
    return out


def grade_challenge(spot_json: str, action: str) -> dict:
    """Grada a ação do jogador contra o spot vetado. Reusa o grader do trainer
    (mixed-aware). Retorna o dict de veredito + uma explicação determinística."""
    spot = json.loads(spot_json) if isinstance(spot_json, str) else spot_json
    g = grade_canonical_spot(spot, action)
    strat = g.get('gto_strategy') or []
    best = g.get('best_action') or (strat[0]['action'] if strat else '')
    mix = ', '.join(f"{s['action']} {round(float(s['freq'])*100)}%" for s in strat[:3])
    played = _norm(action)
    if g.get('is_correct'):
        head = "Correto." if not g.get('mixed') else "Aceitável (o GTO mistura aqui)."
    else:
        head = f"Erro. O GTO joga {best} aqui."
    explanation = f"{head} Estratégia GTO: {mix}." if mix else head
    return {
        'is_correct': bool(g.get('is_correct')),
        'gto_tier':   g.get('gto_tier'),
        'mixed':      bool(g.get('mixed')),
        'best_action': best,
        'gto_strategy': strat,
        'played':     played,
        'explanation': explanation,
    }
