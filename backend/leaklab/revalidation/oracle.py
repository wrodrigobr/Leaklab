"""
oracle.py -- Veredicto independente sobre a melhor ação em um spot.

Princípio: NÃO chama decision_engine_v11.evaluate_decision em ponto algum.
Recebe o mesmo decision_input que o engine recebe, mas decide a partir das
fontes primárias (preflop ranges + gto_nodes locais) e cai para heurística
matemática quando não há cobertura GTO. Sem chamadas externas (GTO Wizard,
solver remoto) durante varredura -- quem precisa daquilo é o ingestion path.

Saída padronizada (OracleDecision) usada pelo differ.classify().
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from leaklab.gto_utils import compute_spot_hash, hand_to_type, normalize_gto_action


# -- Tipos públicos -----------------------------------------------------------

@dataclass
class OracleDecision:
    """Veredicto do oráculo para um spot do herói."""
    action: Optional[str]                       # ação recomendada (canônica) ou None
    alternatives: list[str] = field(default_factory=list)
    confidence: str = 'unavailable'             # 'high' | 'medium' | 'low' | 'unavailable'
    source: str = 'unavailable'                 # ver _SOURCE_TAGS
    justification: str = ''
    opp_cost_bb: Optional[float] = None         # ev(top) - ev(played) quando disponível
    strategy_freqs: dict[str, float] = field(default_factory=dict)  # {action: freq}

    def to_dict(self) -> dict:
        return {
            'action':         self.action,
            'alternatives':   list(self.alternatives),
            'confidence':     self.confidence,
            'source':         self.source,
            'justification':  self.justification,
            'opp_cost_bb':    self.opp_cost_bb,
            'strategy_freqs': dict(self.strategy_freqs),
        }


_SOURCE_TAGS = {
    'preflop_ranges_static',  # docs/leaklab_gto_ranges.json via analyze_preflop
    'postflop_strategy',      # gto_nodes.strategy_json com distribuição completa
    'postflop_top_action',    # gto_nodes só com gto_action (sem strategy_json)
    'heuristic_potodds',      # equity vs pot odds
    'heuristic_pushfold',     # M-Ratio < 6 -> push/fold
    'rule_bb_free_check',     # BB pode check grátis sem aposta
    'unavailable',            # sem dados suficientes
}


# -- Entrypoint ---------------------------------------------------------------

def decide(decision_input: dict) -> OracleDecision:
    """
    Recebe o mesmo decision_input produzido por pipeline.build_decision_input()
    e retorna um veredicto independente.

    Ordem de fontes (cai para a próxima quando a anterior não tem cobertura):
      1. Regra fixa: BB check em pot não contestado
      2. Preflop ranges estáticos (analyze_preflop)
      3. Postflop gto_nodes locais (strategy_json > gto_action)
      4. Heurística push/fold (M-Ratio < 6)
      5. Heurística pot-odds vs equity
      6. unavailable
    """
    street = (decision_input.get('street') or '').lower()
    spot   = decision_input.get('spot') or {}
    math   = decision_input.get('math') or {}
    ctx    = decision_input.get('context') or {}
    cards  = decision_input.get('hero_cards') or []
    facing = float(spot.get('facingSize') or 0.0)
    position = (spot.get('position') or '').upper()

    # 1. Regra fixa: BB free check
    if (street == 'preflop' and position == 'BB' and facing == 0.0):
        return OracleDecision(
            action='check', alternatives=[],
            confidence='high', source='rule_bb_free_check',
            justification='BB sem aposta -- check é a única ação válida (não há range).',
        )

    # 2. Preflop ranges estáticos
    if street == 'preflop':
        d = _from_preflop_ranges(decision_input)
        if d is not None:
            return d

    # 3. Postflop nodes locais (sem hit externo)
    if street in ('flop', 'turn', 'river'):
        d = _from_postflop_nodes(decision_input)
        if d is not None:
            return d

    # 4. Push/fold curto preflop (M-Ratio < 6)
    m_ratio = _as_float(ctx.get('mRatio') or ctx.get('m_ratio'))
    if street == 'preflop' and m_ratio is not None and m_ratio < 6 and position not in ('BB',):
        return _heuristic_pushfold(decision_input, m_ratio)

    # 5. Heurística pot-odds vs equity
    d = _heuristic_potodds(decision_input)
    if d is not None:
        return d

    # 6. Sem cobertura
    return OracleDecision(
        action=None, confidence='unavailable', source='unavailable',
        justification='Sem cobertura GTO e sem dados suficientes para heurística determinística.',
    )


# -- Preflop ------------------------------------------------------------------

def _from_preflop_ranges(decision_input: dict) -> Optional[OracleDecision]:
    """Decide preflop a partir dos ranges estáticos. Retorna None se sem cobertura."""
    try:
        from leaklab.preflop_gto_ranges import analyze_preflop
    except Exception:
        return None

    spot   = decision_input.get('spot') or {}
    ctx    = decision_input.get('context') or {}
    cards  = decision_input.get('hero_cards') or []
    h_type = hand_to_type(cards)
    if not h_type:
        return None

    stack_bb = _as_float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20.0) or 20.0
    facing   = _as_float(spot.get('facingSize') or 0.0) or 0.0
    try:
        res = analyze_preflop(
            position       = spot.get('position') or '',
            hero_hand_type = h_type,
            stack_bb       = stack_bb,
            action_taken   = decision_input.get('player_action') or '',
            facing_size    = facing,
            vs_position    = spot.get('villainPosition') or '',
            is_3bet_pot    = bool(decision_input.get('is_3bet', False)),
        )
    except Exception:
        return None

    if not res or not res.get('available'):
        return None

    rec = [normalize_gto_action(a) for a in (res.get('recommended_actions') or []) if a]
    if not rec:
        return None

    action = rec[0]
    alts   = [a for a in rec[1:] if a != action]
    quality = res.get('action_quality', 'unknown')
    in_rng  = bool(res.get('in_range'))
    rng_pct = res.get('range_pct')

    just_parts = [
        f"scenario={res.get('scenario', '?')}",
        f"hand_type={h_type}",
        f"in_range={'yes' if in_rng else 'no'}",
    ]
    if rng_pct is not None:
        just_parts.append(f"range_pct={rng_pct}")
    just_parts.append(f"quality={quality}")

    return OracleDecision(
        action=action,
        alternatives=alts,
        confidence='high',
        source='preflop_ranges_static',
        justification=' | '.join(just_parts),
    )


# -- Postflop -----------------------------------------------------------------

def _from_postflop_nodes(decision_input: dict) -> Optional[OracleDecision]:
    """
    Decide postflop a partir de gto_nodes LOCAIS apenas. Não chama GTO Wizard
    nem solver remoto. Espelha a ordem de fallback de lookup_gto():
      a) hash exato (com hero_hand + facing)
      b) hash genérico (sem hero_hand, mesmo facing)
      c) hash genérico sem facing -- só quando facing == 0
    """
    try:
        from database.repositories import get_gto_node
    except Exception:
        return None

    street   = (decision_input.get('street') or '').lower()
    spot     = decision_input.get('spot') or {}
    cards    = decision_input.get('hero_cards') or []
    board    = spot.get('board') or []
    position = (spot.get('position') or '').upper()
    stack_bb = _as_float(spot.get('effectiveStackBb') or 20.0) or 20.0
    facing   = _as_float(spot.get('facingSize') or 0.0) or 0.0

    if not board or not position:
        return None

    candidates = [
        compute_spot_hash(street, position, board, cards, stack_bb, facing),
        compute_spot_hash(street, position, board, [],    stack_bb, facing),
    ]
    if facing == 0.0:
        candidates.append(compute_spot_hash(street, position, board, [], stack_bb, 0.0))

    seen: set[str] = set()
    nodes = []
    for h in candidates:
        if h in seen:
            continue
        seen.add(h)
        try:
            n = get_gto_node(h)
        except Exception:
            n = None
        if n:
            nodes.append(n)

    if not nodes:
        return None

    # Preferir nó com strategy_json (decisão mais informada).
    node = next((n for n in nodes if n.get('strategy_json')), nodes[0])

    if node.get('strategy_json'):
        d = _decision_from_strategy_json(node, decision_input)
        if d is not None:
            return d

    # Fallback: nó parcial (só gto_action)
    top = node.get('gto_action')
    if not top:
        return None
    return OracleDecision(
        action=normalize_gto_action(top),
        alternatives=[],
        confidence='medium',
        source='postflop_top_action',
        justification=f"node sem strategy_json -- gto_action={top}, gto_freq={node.get('gto_freq')}",
        strategy_freqs={normalize_gto_action(top): float(node.get('gto_freq') or 0.0)},
    )


def _decision_from_strategy_json(node: dict, decision_input: dict) -> Optional[OracleDecision]:
    """
    Parseia strategy_json: pode ser {action: freq} ou {action: {frequency, ev_bb, ...}}.
    Calcula opp_cost_bb = ev(top) - ev(played) quando ambos disponíveis.
    """
    try:
        raw = json.loads(node['strategy_json'])
    except Exception:
        return None
    if not isinstance(raw, dict) or not raw:
        return None

    strategy: list[dict] = []
    for k, v in raw.items():
        if isinstance(v, dict):
            freq  = _as_float(v.get('frequency'))
            ev_bb = _as_float(v.get('ev_bb'))
        else:
            freq  = _as_float(v)
            ev_bb = None
        if freq is None:
            continue
        strategy.append({
            'action':    normalize_gto_action(k),
            'frequency': freq,
            'ev_bb':     ev_bb,
        })
    if not strategy:
        return None

    # Sanidade: estratégias com soma de freq ~= 0 indicam nó corrompido
    freq_sum = sum(s['frequency'] for s in strategy)
    if freq_sum < 0.10:
        return None

    strategy.sort(key=lambda s: (s['frequency'], s['ev_bb'] or 0.0), reverse=True)
    top = strategy[0]
    alts = [s['action'] for s in strategy[1:] if s['frequency'] >= 0.20 and s['action'] != top['action']]

    # opp_cost = ev(top) - ev(played) quando temos EVs e a played action está no range
    played = normalize_gto_action(decision_input.get('player_action') or '')
    opp_cost: Optional[float] = None
    top_ev = top.get('ev_bb')
    if top_ev is not None and played:
        played_ev = None
        for s in strategy:
            if s['action'] == played:
                played_ev = s.get('ev_bb')
                break
        if played_ev is not None:
            opp_cost = round(float(top_ev) - float(played_ev), 4)

    return OracleDecision(
        action=top['action'],
        alternatives=alts,
        confidence='high',
        source='postflop_strategy',
        justification=(
            f"top={top['action']} freq={top['frequency']:.2f} "
            f"alts={alts or '[]'} freq_sum={freq_sum:.2f}"
        ),
        opp_cost_bb=opp_cost,
        strategy_freqs={s['action']: round(s['frequency'], 4) for s in strategy},
    )


# -- Heurísticas determinísticas ---------------------------------------------

def _heuristic_pushfold(decision_input: dict, m_ratio: float) -> OracleDecision:
    """
    M-Ratio < 6 -> push/fold puro. Aplica regra simples:
      equity estimada >= 0.50  -> jam
      equity >= 0.40 e position in {BTN,SB} -> jam (mais larga IP)
      caso contrário -> fold
    """
    math = decision_input.get('math') or {}
    spot = decision_input.get('spot') or {}
    equity = _as_float(math.get('estimatedHandEquity'))
    position = (spot.get('position') or '').upper()

    if equity is None:
        # Sem equity, sem como decidir; cai para low confidence fold (conservador)
        return OracleDecision(
            action='fold', confidence='low', source='heuristic_pushfold',
            justification=f'M={m_ratio:.1f} push/fold sem equity estimada -- fold conservador.',
        )
    if equity >= 0.50 or (equity >= 0.40 and position in {'BTN', 'SB'}):
        return OracleDecision(
            action='jam', alternatives=['fold'],
            confidence='medium', source='heuristic_pushfold',
            justification=f'M={m_ratio:.1f} push/fold | equity={equity:.2f} -> jam.',
        )
    return OracleDecision(
        action='fold', alternatives=['jam'] if equity >= 0.35 else [],
        confidence='medium', source='heuristic_pushfold',
        justification=f'M={m_ratio:.1f} push/fold | equity={equity:.2f} insuficiente -> fold.',
    )


def _heuristic_potodds(decision_input: dict) -> Optional[OracleDecision]:
    """
    Regra simples e independente:
      facing == 0:
        equity >= 0.50 -> bet (value)
        senão        -> check
      facing > 0:
        equity > pot_odds + 0.05 -> call (com margem clara)
        equity < pot_odds - 0.05 -> fold
        |diff| <= 0.05            -> mixed (oracle marca como acceptable_alt entre call/fold)
    """
    math = decision_input.get('math') or {}
    spot = decision_input.get('spot') or {}
    equity   = _as_float(math.get('estimatedHandEquity'))
    pot_odds = _as_float(math.get('potOddsEquity'))
    facing   = _as_float(spot.get('facingSize') or 0.0) or 0.0

    if equity is None and facing == 0.0:
        return OracleDecision(
            action='check', confidence='low', source='heuristic_potodds',
            justification='facing=0 sem equity -- check é o default seguro.',
        )
    if equity is None:
        return None

    if facing == 0.0:
        if equity >= 0.50:
            return OracleDecision(
                action='bet', alternatives=['check'],
                confidence='low', source='heuristic_potodds',
                justification=f'facing=0 equity={equity:.2f} >= 0.50 -> bet (value).',
            )
        return OracleDecision(
            action='check', alternatives=['bet'] if equity >= 0.40 else [],
            confidence='low', source='heuristic_potodds',
            justification=f'facing=0 equity={equity:.2f} < 0.50 -> check.',
        )

    if pot_odds is None:
        return None

    diff = round(equity - pot_odds, 4)
    if diff > 0.05:
        # Quando há equity confortável, raise/aggression é alternativa válida.
        # equity >= 0.55 ≈ mãos premium/strong com fold equity boa → 3-bet/raise defensável.
        # facing é em chips (não bb), por isso só usamos equity como threshold aqui.
        alts: list[str] = ['raise'] if equity >= 0.55 else []
        return OracleDecision(
            action='call', alternatives=alts,
            confidence='low', source='heuristic_potodds',
            justification=f'equity={equity:.2f} - pot_odds={pot_odds:.2f} = +{diff} -> call.',
        )
    if diff < -0.05:
        return OracleDecision(
            action='fold', confidence='low', source='heuristic_potodds',
            justification=f'equity={equity:.2f} - pot_odds={pot_odds:.2f} = {diff} -> fold.',
        )
    return OracleDecision(
        action='call', alternatives=['fold'],
        confidence='low', source='heuristic_potodds',
        justification=f'equity~=pot_odds (diff={diff}) -- call/fold ambos defensáveis.',
    )


# -- Util --------------------------------------------------------------------

def _as_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f
