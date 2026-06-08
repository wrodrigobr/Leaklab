from __future__ import annotations
from typing import Dict, Any
import logging as _logging

_gto_log = _logging.getLogger('leaklab.gto')

_GTO_VALID_POSITIONS = {'UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'}
_VALID_CARD_RANKS    = set('AKQJT98765432')
_VALID_CARD_SUITS    = set('shdc')


def _log_gto_miss(scope: str, street: str, position: str, reason: str) -> None:
    _gto_log.debug('GTO %s miss — street=%s pos=%s reason=%s', scope, street, position, reason)


def _validate_decision_input(inp: dict) -> list:
    """
    Valida campos numéricos e enumerados antes do GTO lookup.
    Retorna lista de warning strings (não bloqueia avaliação).
    """
    warnings = []
    spot    = inp.get('spot') or {}
    street  = (inp.get('street') or '').strip()
    pos     = (spot.get('position') or '').upper().strip()

    stack = spot.get('effectiveStackBb')
    if stack is not None:
        try:
            s = float(stack)
            if not (0 < s < 10_000) or s != s:
                warnings.append(f'stack_bb inválido: {stack!r}')
        except (TypeError, ValueError):
            warnings.append(f'stack_bb não numérico: {stack!r}')

    facing = spot.get('facingSize')
    if facing is not None:
        try:
            f = float(facing)
            if f < 0 or f != f:
                warnings.append(f'facing_size negativo/NaN: {facing!r}')
        except (TypeError, ValueError):
            warnings.append(f'facing_size não numérico: {facing!r}')

    if pos and pos not in _GTO_VALID_POSITIONS:
        warnings.append(f'position desconhecida: {pos!r}')

    if street and street != 'preflop':
        board = spot.get('board') or []
        if isinstance(board, list):
            for card in board:
                if not isinstance(card, str) or len(card) != 2:
                    warnings.append(f'card inválida no board: {card!r}')
                    break
                if card[0].upper() not in _VALID_CARD_RANKS or card[1].lower() not in _VALID_CARD_SUITS:
                    warnings.append(f'card inválida: {card!r}')
                    break

    return warnings


# ── GTO helpers ───────────────────────────────────────────────────────────────

def _norm_gto_action(a: str) -> str:
    """Normaliza ação para comparação: shove/jam/allin → 'allin'."""
    a = (a or '').lower()
    if a in ('shove', 'jam', 'allin', 'all-in', 'all in'):
        return 'allin'
    return a


def _gto_action_matches(player_action: str, gto_action: str) -> bool:
    """Verifica se a ação do jogador corresponde à ação GTO primária."""
    p = _norm_gto_action(player_action)
    g = _norm_gto_action(gto_action)
    if p == g:
        return True
    aggressive = {'bet', 'raise', 'shove', 'jam', 'allin'}
    if g.startswith('bet') or g.startswith('raise'):
        return p in aggressive
    return p.startswith(g) or g.startswith(p)


def _gto_classify_from_strategy(player_action: str, strategy: list) -> tuple:
    """
    Classifica usando frequência real + EV diff da ação jogada.

    Frequência isolada penaliza estratégias mistas legítimas (ex: call 15% com
    ev_diff = 0.02bb não é desvio crítico). A combinação freq + ev_diff evita
    isso: só sobe a severidade quando o custo de EV é significativo.

    Retorna (gto_label, played_freq).
    """
    played_norm = _norm_gto_action(player_action)
    played_freq = 0.0
    played_ev: float | None = None

    for s in strategy:
        act  = _norm_gto_action(s.get('action', ''))
        freq = float(s.get('frequency') or 0.0)
        if act == played_norm or played_norm.startswith(act) or act.startswith(played_norm):
            if freq > played_freq:
                played_freq = freq
                ev = s.get('ev_bb')
                played_ev = float(ev) if ev is not None else None

    # EV diff vs top action (positivo = jogador perdeu EV)
    ev_diff: float | None = None
    if strategy and played_ev is not None:
        top_ev = strategy[0].get('ev_bb')
        if top_ev is not None:
            ev_diff = float(top_ev) - played_ev

    # Tier 1: GTO joga isso a maioria do tempo → correto
    if played_freq >= 0.60:
        return 'gto_correct', played_freq

    # Tier 2: parte significativa do range GTO → misto por definição
    if played_freq >= 0.25:
        return 'gto_mixed', played_freq

    # Tier 3: 10-25% — decide pelo custo de EV
    if played_freq >= 0.10:
        # EV diff < 0.15bb: dentro do ruído de estratégia mista
        if ev_diff is None or ev_diff < 0.15:
            return 'gto_mixed', played_freq
        return 'gto_minor_deviation', played_freq

    # Tier 4: < 10% — frequência baixa, severidade pelo custo real
    # Se a ação aparece no mix GTO (>=3%), evita 'gto_critical' sem evidência de EV alto:
    # 7% de bet num check-heavy spot ainda é parte do range; não merece "Desvio Crítico".
    if ev_diff is not None:
        if ev_diff < 0.30:
            return 'gto_minor_deviation', played_freq
        # Custo de EV alto E freq baixa
        return 'gto_critical', played_freq
    # Sem ev_diff: usa freq como proxy. Frequência >=3% = ação faz parte do range GTO.
    if played_freq >= 0.03:
        return 'gto_minor_deviation', played_freq
    return 'gto_critical', played_freq


def _gto_classify(player_action: str, gto_action: str, gto_freq: float, hero_equity: float | None) -> str:
    """
    Classificação simplificada (fallback quando strategy_json não disponível).
    Usa apenas top action + frequência estimada da alternativa.
    """
    if _gto_action_matches(player_action, gto_action):
        return 'gto_correct'

    alt_freq = 1.0 - gto_freq

    if alt_freq >= 0.40:
        return 'gto_mixed'
    if alt_freq >= 0.15:
        if hero_equity is not None and hero_equity >= 0.60:
            return 'gto_mixed'
        return 'gto_minor_deviation'
    return 'gto_critical'


def _gto_label_cap(label: str, gto_label: str) -> str:
    """
    Reconcilia label heuristico com sinal do solver:
      - gto_correct/gto_mixed: acao validada pelo GTO -> cap em 'marginal'
        (nunca pode ser small/clear mistake)
      - gto_minor_deviation: solver classifica como desvio leve -> cap em
        'small_mistake' (impede clear_mistake quando proprio solver diz
        que e leve)
      - gto_critical: solver diz erro grave -> floor em 'small_mistake'
        (impede engine de dar pass como 'standard'/'marginal' quando
        solver classifica como critico)
    """
    if gto_label in ('gto_correct', 'gto_mixed'):
        if label in ('small_mistake', 'clear_mistake'):
            return 'marginal'
    elif gto_label == 'gto_minor_deviation':
        if label == 'clear_mistake':
            return 'small_mistake'
    elif gto_label == 'gto_critical':
        if label in ('standard', 'marginal'):
            return 'small_mistake'
    return label


def _enrich_preflop_gto(input_data: Dict[str, Any]) -> dict:
    """Range GTO preflop — lookup por posição, stack e cenário. Silencioso em caso de erro."""
    if input_data.get('street') != 'preflop':
        return {'available': False}

    spot       = input_data.get('spot', {})
    ctx        = input_data.get('context', {})
    hero_cards = input_data.get('hero_cards', [])
    if not hero_cards:
        return {'available': False}

    try:
        from leaklab.gto_utils import hand_to_type
        from leaklab.preflop_gto_ranges import analyze_preflop
        h_type = hand_to_type(hero_cards)
        if not h_type:
            return {'available': False}
        return analyze_preflop(
            position       = spot.get('position', ''),
            hero_hand_type = h_type,
            stack_bb       = float(spot.get('effectiveStackBb') or ctx.get('heroStackBb') or 20),
            action_taken   = input_data.get('player_action', ''),
            facing_size    = float(spot.get('facingSize') or 0),
            vs_position    = spot.get('villainPosition', ''),
            is_3bet_pot    = bool(input_data.get('is_3bet', False)),
            n_players      = spot.get('nPlayers'),
            facing_raises      = int(spot.get('preflopRaisesFaced') or 0),
            hero_was_aggressor = bool(spot.get('heroWasAggressor', False)),
            is_pko             = bool(ctx.get('isPko')),
            facing_to_bb       = float(spot.get('facingToBb') or 0),
        )
    except Exception as exc:
        _log_gto_miss('preflop', input_data.get('street'), spot.get('position'), str(exc)[:120])
        return {'available': False}


_LABEL_SEV = {'standard': 0, 'marginal': 1, 'small_mistake': 2, 'clear_mistake': 3}
_SEV_LABEL = {0: 'standard', 1: 'marginal', 2: 'small_mistake', 3: 'clear_mistake'}


def _preflop_gto_label_adjust(label: str, quality: str) -> str:
    """
    Ajusta label preflop pelo range GTO.

    correct    → sempre 'standard'  (ação confirmada pelo GTO)
    acceptable → cap em 'marginal'  (subótimo mas defensável)
    leak       → floor em 'small_mistake' (não capeia clear_mistake)
    major_leak → floor em 'small_mistake' (não capeia clear_mistake)
    """
    cur = _LABEL_SEV.get(label, 1)
    if quality == 'correct':
        return 'standard'
    if quality == 'acceptable':
        return _SEV_LABEL[min(cur, _LABEL_SEV['marginal'])]
    if quality in ('leak', 'major_leak'):
        return _SEV_LABEL[max(cur, _LABEL_SEV['small_mistake'])]
    return label


def _enrich_gto(input_data: Dict[str, Any]) -> dict:
    """
    Lookup GTO postflop usando o mesmo hash que lookup_gto() — mesmos nós do banco.
    Tenta 3 variantes (exact → sem hand → sem facing) para maximizar cobertura.
    Usa strategy_json completo quando disponível para classificação precisa por frequência.
    """
    street = input_data.get('street', '')
    if street not in ('flop', 'turn', 'river'):
        return {'available': False}

    spot          = input_data.get('spot', {})
    board         = spot.get('board', [])
    position      = spot.get('position', '')
    hero_hand     = input_data.get('hero_cards', [])
    stack_bb      = float(spot.get('effectiveStackBb') or 20.0)
    facing_bb     = float(spot.get('facingSize') or 0.0)
    player_action = input_data.get('player_action', '')
    equity        = input_data.get('math', {}).get('estimatedHandEquity')

    if not board or not position:
        return {'available': False}

    try:
        import json as _json
        from leaklab.gto_utils import compute_spot_hash
        from database.repositories import get_gto_node

        # Mesmas variantes de hash que lookup_gto() usa
        hashes = [
            compute_spot_hash(street, position, board, hero_hand, stack_bb, facing_bb),
            compute_spot_hash(street, position, board, [],        stack_bb, facing_bb),
        ]
        if facing_bb == 0.0:
            hashes.append(compute_spot_hash(street, position, board, [], stack_bb, 0.0))

        # Nós do solver Texas (source='solver_cli') REATIVADOS no postflop, COM TRAVA de
        # depth: o solve agora roda no stack REAL (cap 60bb), não mais capado a 20bb. Só
        # confia em solver_cli quando o spot é ≤60bb (acima seria aproximação do cap → cai
        # no GW/heurístico). O guard de SPR abaixo ainda rejeita jams indevidos de qualquer
        # fonte. GTO Wizard segue preferido quando existir (precisão maior).
        def _ok(n):
            if not n:
                return False
            if n.get('source') == 'solver_cli':
                return stack_bb <= 60.0
            return True

        # Prioridade 1: nó GW com strategy_json (dados completos)
        node = None
        for h in hashes:
            n = get_gto_node(h)
            if _ok(n) and n.get('strategy_json'):
                node = n
                break

        # Prioridade 2: nó GW parcial (só top action)
        if not node:
            for h in hashes:
                n = get_gto_node(h)
                if _ok(n):
                    node = n
                    break

        if not node:
            return {'available': False}

        top_action = node['gto_action']
        top_freq   = float(node.get('gto_freq') or 0.0)

        # Desserializar strategy_json completo
        strategy = []
        if node.get('strategy_json'):
            try:
                raw = _json.loads(node['strategy_json'])
                for k, v in raw.items():
                    if isinstance(v, dict):
                        freq  = float(v.get('frequency', 0.0))
                        ev_bb = v.get('ev_bb')
                        ev_bb = float(ev_bb) if ev_bb is not None else None
                    else:
                        freq, ev_bb = float(v), None
                    strategy.append({'action': k, 'frequency': freq, 'ev_bb': ev_bb})
                strategy.sort(key=lambda s: s['frequency'], reverse=True)
                if strategy:
                    top_action = strategy[0]['action']
                    top_freq   = strategy[0]['frequency']
            except Exception as exc:
                _log_gto_miss('postflop', street, position, f'strategy_json parse error: {exc!s:.80}')
                strategy = []

        # Guard: strategy com freq_sum ≈ 0 indica nó corrompido
        if strategy:
            freq_sum = sum(s['frequency'] for s in strategy)
            if freq_sum < 0.10:
                _log_gto_miss('postflop', street, position, f'strategy freq_sum={freq_sum:.3f} (corrompido)')
                strategy = []
                node = None

        # Guard: jam/allin de nó postflop é INVÁLIDO quando o SPR é alto (stack >> pote).
        # O solver postflop roda capped a stack curto (~20bb), onde jogar all-in no flop
        # pode ser top; servido pra um spot FUNDO (ex.: 150bb, SPR ~9) vira "shove de
        # 150bb", que nunca é GTO. Rejeita e cai no heurístico em vez de recomendar shove.
        if _norm_gto_action(top_action) == 'allin':
            pot_bb = float(spot.get('potBb') or 0.0)
            spr = (stack_bb / pot_bb) if pot_bb > 0 else 0.0
            if spr > 3.0:
                _log_gto_miss('postflop', street, position,
                              f'jam rejeitado: SPR={spr:.1f} (stack {stack_bb:.0f}bb / pote {pot_bb:.1f}bb)')
                return {'available': False}

        # Classificação: usa frequência real da ação jogada quando possível
        if strategy:
            gto_label, played_freq = _gto_classify_from_strategy(player_action, strategy)
        else:
            gto_label  = _gto_classify(player_action, top_action, top_freq, equity)
            played_freq = top_freq if _gto_action_matches(player_action, top_action) else (1.0 - top_freq)

        return {
            'available':    True,
            'gto_action':   top_action,
            'gto_freq':     top_freq,
            'played_freq':  played_freq,
            'strategy':     strategy,
            'exploitability': node.get('exploitability_pct'),
            'gto_label':    gto_label,
            'source':       node.get('source', 'postflop_db'),
        }

    except Exception as exc:
        _log_gto_miss('postflop', input_data.get('street', ''),
                      (input_data.get('spot') or {}).get('position', ''), str(exc)[:120])
        return {'available': False}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round4(value: float) -> float:
    return round(value, 4)


decision_engine_config = {
    "labels": {"standardMax": 0.08, "marginalMax": 0.18, "smallMistakeMax": 0.36},
    "streetCaps": {"preflop": 0.04, "flop": 0.05, "turn": 0.06, "river": 0.06},
    "streetMultipliers": {"preflop": 0.95, "flop": 1.0, "turn": 1.08, "river": 1.12},
}


def calc_realization_adjustment(is_in_position: bool | None, reverse_implied_odds_factor: float | None, effective_stack_bb: float | None, range_zone: str, hand_class: str | None) -> float:
    adj = 0.0
    if is_in_position is False:
        adj += 0.01
    if (reverse_implied_odds_factor or 0) > 0.5:
        adj += 0.01
    if (effective_stack_bb or 0) > 40 and range_zone == "outside_range":
        adj += 0.01
    if hand_class and "dominated" in hand_class:
        adj += 0.01
    return clamp(adj, 0.0, 0.04)


def calc_pressure_adjustment(street: str, pressure_score: float | None, is_multiway: bool | None,
                              icm_pressure: str | None, is_pko: bool = False,
                              icm_tax_pct: float | None = None) -> float:
    adj = 0.0
    p = pressure_score or 0.0
    if 0.35 <= p < 0.65:
        adj += 0.01
    if p >= 0.65:
        adj += 0.02
    if is_multiway:
        adj += 0.01
    # ICM: na mesa final usamos o sinal CONTÍNUO (icm_tax do calculate_icm, ver
    # leaklab/icm.py) — |tax| = intensidade da distorção ICM. Quanto mais a equity
    # ICM se afasta da fração de fichas (big stack pagando risk premium OU short
    # stack com prêmio de sobrevivência), mais equity é exigida para arriscar a
    # pilha (calls finos viram erro maior, folds apertados são perdoados). Fora da
    # mesa final (icm_tax indisponível) caímos no bucket heurístico icm_pressure.
    if icm_tax_pct is not None:
        adj += clamp(abs(icm_tax_pct) / 100.0 * 0.06, 0.0, 0.02)
    elif icm_pressure == "high" and street in {"turn", "river"}:
        adj += 0.01
    # PKO: bounty reduz a equity necessária para stack-off — covering player
    # tem incentivo extra (matar villain = ganha bounty). Artigo GW indica
    # 5.9% adicional vs 14.2% classic. Aplicamos -0.02 (2pp) na adjusted
    # required equity. Apenas pré-final-table — perto da bolha o efeito atenua.
    if is_pko and icm_pressure != 'high':
        adj -= 0.02
    return clamp(adj, -0.03, 0.03)


def calc_adjusted_required_equity(street: str, pot_odds_equity: float | None, realization_adjustment: float, pressure_adjustment: float):
    if pot_odds_equity is None:
        return {"adjustedRequiredEquity": None, "streetCapApplied": decision_engine_config["streetCaps"][street], "totalAdjustment": 0.0}
    cap = decision_engine_config["streetCaps"][street]
    # PKO pode gerar pressure_adjustment negativo (bounty reduz equity necessária).
    # Permite total negativo (cap inferior: -cap).
    total = clamp(realization_adjustment + pressure_adjustment, -cap, cap)
    adjusted = max(0.05, round4(pot_odds_equity + total))  # piso 5% pra evitar absurdos
    return {"adjustedRequiredEquity": adjusted, "streetCapApplied": cap, "totalAdjustment": round4(total)}


def calc_base_action_gap(player_action: str, recommended_primary_action: str, alternative_actions: list[str] | None = None) -> float:
    alternatives = alternative_actions or []
    if player_action == recommended_primary_action:
        return 0.0
    if player_action in alternatives:
        return 0.08
    aggressive_mismatch = player_action in {"shove", "jam", "raise"} and recommended_primary_action == "fold"
    if aggressive_mismatch:
        return 0.35
    if player_action == "fold" and recommended_primary_action == "call":
        return 0.14
    if player_action == "call" and recommended_primary_action == "fold":
        return 0.22
    return 0.18


def calc_math_penalty(player_action: str, estimated_hand_equity: float | None, adjusted_required_equity: float | None) -> float:
    if estimated_hand_equity is None or adjusted_required_equity is None:
        return 0.0
    diff = round4(estimated_hand_equity - adjusted_required_equity)
    if player_action == "call":
        if diff >= 0: return 0.0
        if diff > -0.02: return 0.05
        if diff > -0.04: return 0.11
        if diff > -0.07: return 0.18
        return 0.28
    if player_action == "fold":
        if diff <= 0: return 0.0
        if diff < 0.02: return 0.04
        if diff < 0.04: return 0.09
        if diff < 0.07: return 0.15
        return 0.22
    return 0.0


def calc_range_penalty(range_zone: str, player_action: str, recommended_primary_action: str) -> float:
    if player_action == recommended_primary_action:
        return 0.0
    if range_zone == "borderline_range":
        return 0.03
    if range_zone == "core_range":
        return 0.08
    if range_zone == "outside_range":
        return 0.12
    return 0.0


def calc_context_penalty(street: str, is_multiway: bool | None, is_in_position: bool | None, icm_pressure: str | None, player_action: str, recommended_primary_action: str) -> float:
    penalty = 0.0
    if player_action != recommended_primary_action:
        if street == "turn": penalty += 0.02
        if street == "river": penalty += 0.04
    if is_multiway: penalty += 0.01
    if is_in_position is False and street != "preflop": penalty += 0.01
    if icm_pressure == "high": penalty += 0.01
    return penalty


def calc_tolerance_credit(range_zone: str, player_action: str, recommended_primary_action: str, alternative_actions: list[str] | None, estimated_hand_equity: float | None, adjusted_required_equity: float | None) -> float:
    credit = 0.0
    alternatives = alternative_actions or []
    if range_zone == "borderline_range":
        credit += 0.05
    if player_action in alternatives:
        credit += 0.04
    if estimated_hand_equity is not None and adjusted_required_equity is not None:
        diff = abs(estimated_hand_equity - adjusted_required_equity)
        if diff <= 0.02:
            credit += 0.03
        elif diff <= 0.03:
            credit += 0.015
    return credit


def classify_mistake_score(score: float) -> str:
    if score <= 0.08: return "standard"
    if score <= 0.18: return "marginal"
    if score <= 0.36: return "small_mistake"
    return "clear_mistake"


def apply_anti_rules(player_action: str, estimated_hand_equity: float | None, adjusted_required_equity: float | None, provisional_label: str, best_action: str | None = None) -> str:
    # Se o jogador fez exatamente a ação recomendada, não há anti-rule a aplicar
    if best_action is not None and _norm_gto_action(player_action) == _norm_gto_action(best_action):
        return provisional_label
    if estimated_hand_equity is None or adjusted_required_equity is None:
        return provisional_label
    diff = round4(estimated_hand_equity - adjusted_required_equity)
    if player_action == "fold":
        if 0 <= diff <= 0.03 and provisional_label == "clear_mistake":
            return "small_mistake"
        # Fold com equity >= required + 3pp é leak math claro. Sem essa regra,
        # label pode ficar 'standard' contradizendo o indicador "Call lucrativo".
        if diff >= 0.03 and provisional_label == "standard":
            return "small_mistake"
    if player_action == "call":
        if diff <= -0.07:
            return "clear_mistake"
        if diff <= -0.04 and provisional_label == "marginal":
            return "small_mistake"
    return provisional_label


def evaluate_decision(input_data: Dict[str, Any]) -> Dict[str, Any]:
    street = input_data["street"]
    spot = input_data["spot"]
    hand_profile = input_data["hand_profile"]
    math = input_data["math"]
    range_eval = input_data["range_evaluation"]
    context = input_data.get("context", {})

    # BB check em pot não contestado: ação obrigatória/trivial, sem análise de erro
    if (street == 'preflop'
            and spot.get('position') == 'BB'
            and input_data.get('player_action', '').lower() == 'check'
            and float(spot.get('facingSize') or 0) == 0):
        return {
            "handId": input_data["hand_id"],
            "bestAction": "check",
            "actionTaken": "check",
            "evaluation": {"mistakeScore": 0.0, "label": "standard", "scoreBreakdown": {}},
            "thresholds": {},
            "interpretation": {"summary": "BB exerceu o free play — sem análise de range.", "details": []},
            "gto": {"available": False},
            "preflop_gto": None,
            "debug": {"rangeZone": None, "alternativeActions": [], "rawFlags": []},
        }

    realization_adjustment = calc_realization_adjustment(
        spot.get("isInPosition"),
        math.get("reverseImpliedOddsFactor"),
        spot.get("effectiveStackBb"),
        range_eval.get("rangeZone"),
        hand_profile.get("handClass"),
    )
    pressure_adjustment = calc_pressure_adjustment(
        street,
        math.get("pressureScore"),
        spot.get("isMultiway"),
        context.get("icmPressure"),
        is_pko=bool(context.get("isPko")),
        icm_tax_pct=context.get("icmTaxPct"),
    )
    threshold_pack = calc_adjusted_required_equity(
        street,
        math.get("potOddsEquity"),
        realization_adjustment,
        pressure_adjustment,
    )
    base_action_gap = calc_base_action_gap(
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
        range_eval.get("alternativeActions") or [],
    )
    # Math penalty só se aplica quando a ação diverge da recomendada
    # Se o jogador fez exatamente o bestAction, não há penalidade matemática
    _best_action = range_eval.get("recommendedPrimaryAction")
    math_penalty = calc_math_penalty(
        input_data["player_action"],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
    ) if _norm_gto_action(input_data["player_action"]) != _norm_gto_action(_best_action or '') else 0.0
    range_penalty = calc_range_penalty(
        range_eval.get("rangeZone"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
    )
    context_penalty = calc_context_penalty(
        street,
        spot.get("isMultiway"),
        spot.get("isInPosition"),
        context.get("icmPressure"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
    )
    tolerance_credit = calc_tolerance_credit(
        range_eval.get("rangeZone"),
        input_data["player_action"],
        range_eval.get("recommendedPrimaryAction"),
        range_eval.get("alternativeActions") or [],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
    )
    raw_score = clamp(base_action_gap + math_penalty + range_penalty + context_penalty - tolerance_credit, 0.0, 1.0)
    street_multiplier = decision_engine_config["streetMultipliers"][street]
    final_score = clamp(raw_score * street_multiplier, 0.0, 1.0)
    label = classify_mistake_score(final_score)
    label = apply_anti_rules(
        input_data["player_action"],
        math.get("estimatedHandEquity"),
        threshold_pack["adjustedRequiredEquity"],
        label,
        best_action=_best_action,
    )

    # GTO enrichment postflop — fonte primária quando strategy_json disponível
    gto = _enrich_gto(input_data)
    if gto.get('available'):
        if gto.get('strategy'):
            # Strategy completo: recomputar score e label a partir da frequência real
            played_freq  = gto.get('played_freq', 0.0)
            top_freq     = gto.get('gto_freq', 1.0)
            gto_lbl      = gto['gto_label']
            opp_cost     = max(0.0, top_freq - played_freq)
            _score_mult  = {
                'gto_correct':         0.10,
                'gto_mixed':           0.30,
                'gto_minor_deviation': 0.65,
                'gto_critical':        0.90,
            }
            final_score  = clamp(round4(opp_cost * _score_mult.get(gto_lbl, 0.5)), 0.0, 1.0)
            label        = classify_mistake_score(final_score)
            # Aplica cap mesmo no caminho com strategy completo. Score recalculado
            # pode ficar acima de 0.36 (clear_mistake) quando opp_cost e alto,
            # contradizendo o proprio rotulo do solver (gto_minor_deviation/mixed).
            label        = _gto_label_cap(label, gto_lbl)
            _best_action = gto['gto_action']
        else:
            # Nó parcial (sem strategy_json): capeia label e override bestAction
            # quando GTO crítico — não faz sentido recomendar call quando solver diz jam.
            label = _gto_label_cap(label, gto['gto_label'])
            if gto.get('gto_label') == 'gto_critical' and gto.get('gto_action'):
                _best_action = gto['gto_action']

    # Validar inputs antes do GTO enrichment (warnings apenas — não bloqueia)
    _input_warnings = _validate_decision_input(input_data)
    if _input_warnings:
        for _w in _input_warnings:
            _log_gto_miss('input_validation', street, input_data.get('spot', {}).get('position', ''), _w)

    # GTO enrichment preflop: range GTO por posição/stack — ajusta label e best_action
    preflop_gto = _enrich_preflop_gto(input_data)
    if preflop_gto.get('available'):
        quality = preflop_gto.get('action_quality', 'unknown')
        label   = _preflop_gto_label_adjust(label, quality)
        rec     = preflop_gto.get('recommended_actions', [])
        if rec:
            _best_action = rec[0]   # sobrescreve com ação GTO recomendada
        # Consistência score/label: recalcular final_score para bater com novo label
        if quality == 'correct':
            final_score = min(final_score, 0.08)    # cap em 'standard'
        elif quality == 'acceptable':
            final_score = min(final_score, 0.18)    # cap em 'marginal'
        # Persistir gto_label/gto_action preflop no DB (save_decisions lê result['gto'])
        if quality and quality != 'unknown':
            _QUALITY_TO_GTO_LABEL = {
                'correct':             'gto_correct',
                'acceptable':          'gto_mixed',
                'gto_minor_deviation': 'gto_minor_deviation',
                'minor_mistake':       'gto_minor_deviation',
                'leak':                'gto_critical',
                'major_leak':          'gto_critical',
            }
            _gto_lbl = _QUALITY_TO_GTO_LABEL.get(quality, 'gto_critical')
            gto = {'available': True, 'gto_label': _gto_lbl, 'gto_action': rec[0] if rec else None,
                   # #24: bb perdidos vs melhor ação (vem do overlay de EV no analyze_preflop)
                   'ev_loss_bb':     preflop_gto.get('ev_loss_bb'),
                   'ev_loss_source': preflop_gto.get('ev_loss_source')}

    # Guard: BB pode check grátis quando não há aposta — fold é impossível.
    # Outras posições (UTG/HJ/CO/BTN/SB) estão escolhendo não abrir — fold é correto.
    if float(spot.get('facingSize') or 0) == 0 and _best_action == 'fold' and spot.get('position') == 'BB':
        _best_action = 'check'

    # Guard: em POSTFLOP sem aposta anterior, "raise" não é ação válida — normalizar para "bet".
    # Preflop sempre tem BB facing, então "raise" continua válido em RFI preflop.
    if (input_data.get('street') != 'preflop'
        and float(spot.get('facingSize') or 0) == 0 and _best_action == 'raise'):
        _best_action = 'bet'

    # Guard: facing all-in que cobre o hero — raise é impossível. Cai pra call/fold
    # baseado em equity vs required. Cobre o bug onde engine sugeria 'raise' em
    # spots multi-all-in ou facing shove cobrindo o stack do hero.
    # IMPORTANTE: spot.facingSize está em FICHAS; effectiveStackBb em BB. Converter
    # o facing para bb via levelBb antes de comparar (sem isso o guard disparava
    # espúrio — ex.: facing 250 fichas tratado como 250bb — e rebaixava jam do GTO).
    _facing_chips = float(spot.get('facingSize') or 0)
    _bb_chips = float(input_data.get('context', {}).get('levelBb') or 0)
    _facing_bb = (_facing_chips / _bb_chips) if _bb_chips > 0 else 0.0
    _hero_stack_bb = float(spot.get('effectiveStackBb') or input_data.get('context', {}).get('heroStackBb') or 0)
    if (_best_action in ('raise', 'jam') and _facing_bb > 0 and _hero_stack_bb > 0
            and _facing_bb >= _hero_stack_bb * 0.95):
        _eq  = math.get('estimatedHandEquity')
        _req = threshold_pack.get('adjustedRequiredEquity')
        _gto_rec = preflop_gto.get('recommended_actions', []) if preflop_gto.get('available') else []
        if 'jam' in _gto_rec or 'call' in _gto_rec:
            # O range GTO queria comprometer o stack (jam/call). Facing all-in que
            # cobre o hero, 'jam' é impossível mas colapsa em 'call' — mesma decisão
            # de commit. Sem isso o guard caía em fold por equity=None (preflop não
            # computa equity-vs-range), rebaixando calls triviais (AK/AJ vs shove).
            _best_action = 'call'
        elif _eq is not None and _req is not None and _eq >= _req:
            _best_action = 'call'
        else:
            _best_action = 'fold'
        # Reclassifica: score foi computado contra 'raise' invalido. Se player
        # matched o novo best_action, e standard. Caso contrario, mantem severidade.
        if _norm_gto_action(input_data["player_action"]) == _norm_gto_action(_best_action):
            label = 'standard'
            final_score = 0.0

    interpretation = build_interpretation(input_data, label, threshold_pack["adjustedRequiredEquity"])
    return {
        "handId": input_data["hand_id"],
        "bestAction": _best_action,
        "actionTaken": input_data["player_action"],
        "evaluation": {
            "mistakeScore": round4(final_score),
            "label": label,
            "scoreBreakdown": {
                "baseActionGap": round4(base_action_gap),
                "mathPenalty": round4(math_penalty),
                "rangePenalty": round4(range_penalty),
                "contextPenalty": round4(context_penalty),
                "toleranceCredit": round4(tolerance_credit),
                "streetMultiplier": round4(street_multiplier),
            },
        },
        "thresholds": {
            "potOddsEquity": math.get("potOddsEquity"),
            "realizationAdjustment": round4(realization_adjustment),
            "pressureAdjustment": round4(pressure_adjustment),
            "adjustedRequiredEquity": threshold_pack["adjustedRequiredEquity"],
            "streetCapApplied": threshold_pack["streetCapApplied"],
        },
        "interpretation": interpretation,
        "gto": gto,
        "preflop_gto": preflop_gto if preflop_gto.get('available') else None,
        "debug": {
            "rangeZone": range_eval.get("rangeZone"),
            "alternativeActions": range_eval.get("alternativeActions") or [],
            "rawFlags": [],
        },
    }


def build_interpretation(input_data: Dict[str, Any], label: str, adjusted_required_equity: float | None):
    summary_map = {
        "standard":      "Linha sólida para o spot.",
        "marginal":      "Ação defensável, mas existe alternativa levemente melhor.",
        "small_mistake": "Pequena perda estratégica, relevante no longo prazo.",
        "clear_mistake": "Erro claro com impacto relevante em EV.",
    }

    if label not in ("small_mistake", "clear_mistake"):
        return {"summary": summary_map[label], "mathExplanation": "", "strategicExplanation": ""}

    action = input_data.get("player_action", "")
    street = input_data.get("street", "preflop")
    rng    = input_data.get("range_evaluation", {})
    best   = rng.get("recommendedPrimaryAction", "")
    zone   = rng.get("rangeZone", "")
    mt     = input_data.get("math", {})
    spot   = input_data.get("spot", {})
    ctx    = input_data.get("context", {})

    est      = mt.get("estimatedHandEquity")
    pot_odds = mt.get("potOddsEquity")
    draw     = (mt.get("drawProfile") or "none").lower()
    riods    = mt.get("reverseImpliedOddsFactor") or 0

    position = spot.get("position", "")
    facing   = spot.get("facingSize") or 0

    m_ratio  = ctx.get("mRatio")
    icm      = ctx.get("icmPressure", "low")

    _act = {"fold": "fold", "check": "check", "call": "call",
            "bet": "bet", "raise": "raise", "shove": "all-in", "jam": "all-in"}.get
    _str = {"preflop": "pré-flop", "flop": "flop",
            "turn": "turn", "river": "river"}.get

    action_pt = _act(action, action)
    best_pt   = _act(best, best)
    street_pt = _str(street, street)

    parts = []

    # ── Equity analysis ──────────────────────────────────────────────────────
    if est is not None:
        eq_pct = round(est * 100, 1)
        req_pct = (round(adjusted_required_equity * 100, 1)
                   if adjusted_required_equity is not None
                   else (round(pot_odds * 100, 1) if pot_odds is not None else None))

        if req_pct is not None:
            diff = round(eq_pct - req_pct, 1)
            if action == "call" and best == "fold":
                parts.append(f"Equity de {eq_pct}% ficou {abs(diff)}pp abaixo dos {req_pct}% exigidos — sem valor para continuar no pot.")
            elif action == "fold" and best == "call":
                parts.append(f"Com equity de {eq_pct}% vs {req_pct}% exigidos pelo pot, o call tinha valor positivo (+{abs(diff)}pp).")
            elif action == "fold" and best in ("raise", "shove", "jam", "bet"):
                parts.append(f"Equity de {eq_pct}% suporta {best_pt.upper()} neste spot — foldar deixou valor na mesa.")
            elif action in ("raise", "bet", "shove", "jam") and best == "fold":
                parts.append(f"Equity de {eq_pct}% ficou {abs(diff)}pp abaixo dos {req_pct}% necessários — a agressão não tinha suporte matemático.")
            elif action in ("check", "call") and best in ("bet", "raise"):
                parts.append(f"Com equity de {eq_pct}%, {best_pt.upper()} extrai mais valor e protege melhor do que {action_pt.upper()}.")
            elif diff > 0:
                parts.append(f"Equity de {eq_pct}% supera os {req_pct}% exigidos (+{diff}pp) — linha mais agressiva era suportada.")
            else:
                parts.append(f"Equity de {eq_pct}% ficou {abs(diff)}pp abaixo dos {req_pct}% exigidos para o spot.")
        else:
            parts.append(f"Equity estimada da mão: {eq_pct}%.")

    # ── Draw context ─────────────────────────────────────────────────────────
    if draw not in ("none", "no_draw", ""):
        if "combo" in draw:
            parts.append("Draw combinado (flush + straight) adiciona equity implícita significativa ao cálculo.")
        elif "flush" in draw:
            parts.append("Projeto de flush adiciona ~9% de equity implícita não capturada pelos pot odds simples.")
        elif "straight" in draw:
            parts.append("Projeto de straight adiciona equity implícita — relevante para decisões de call/fold no turn.")
        elif "backdoor" in draw:
            parts.append("Draw backdoor contribui marginalmente com equity extra.")

    if riods > 0.3 and action in ("call", "check") and best == "fold":
        parts.append("Reverse implied odds elevados: quando atrás, o pot fica maior; quando frente, os oponentes param de pagar.")

    # ── MTT / Stack ──────────────────────────────────────────────────────────
    if m_ratio is not None:
        mr = round(m_ratio, 1)
        if mr < 6:
            parts.append(f"M-Ratio {mr}: jogo push/fold — sem espaço para linhas especulativas.")
        elif mr < 10:
            parts.append(f"M-Ratio {mr}: zona crítica de pressão — priorize spots com fold equity real.")
        elif mr < 15:
            parts.append(f"M-Ratio {mr}: pressão moderada — stack preservation pesa em spots marginais.")

    # ICM — na mesa final, leitura direcional pelo sinal contínuo (icm_tax);
    # fora dela, o bucket heurístico icm_pressure. Qualitativo (sem número "duro":
    # os payouts reais não vêm no HH, então a forma da pressão é confiável, o valor não).
    icm_tax = ctx.get("icmTaxPct")
    if icm_tax is not None:
        if icm_tax >= 5:        # equity ICM < fração de fichas → pilha grande
            parts.append("Mesa final: você tem das maiores pilhas — pelo ICM, suas fichas valem menos que a fração no prize pool (retornos decrescentes). Arriscar a stack exige mais equity do que o pot odds sugere; evite flips marginais e prefira pressionar os short stacks.")
        elif icm_tax <= -5:     # equity ICM > fração de fichas → pilha curta
            parts.append("Mesa final: pilha curta com prêmio de sobrevivência — pelo ICM sua equity supera a fração de fichas, então sobreviver tem valor real. Seja seletivo ao arriscar a eliminação.")
        else:
            parts.append("Mesa final: stacks equilibrados — a pressão ICM é leve, mas todo all-in carrega risco de eliminação.")
    elif icm == "high":
        parts.append("ICM elevado: risco de eliminação aumenta o threshold de call — sobrevivência tem valor real.")
    elif icm == "medium" and label == "clear_mistake":
        parts.append("ICM médio: equity de fichas subestima o risco de eliminação neste spot.")

    # ── Range zone / position ────────────────────────────────────────────────
    if zone == "outside_range":
        pos_txt = f"em {position}" if position else "nesta posição"
        parts.append(f"A linha {action_pt.upper()} está fora do range defensável {pos_txt} no {street_pt}.")
    elif zone == "borderline_range":
        parts.append("Spot de borda do range — pequena variação de stack ou ICM pode inverter a decisão correta.")

    # ── Facing bet context ───────────────────────────────────────────────────
    if facing and facing > 0 and action == "fold" and best in ("call", "raise"):
        parts.append(f"A aposta/raise que veio representava uma oferta matematicamente atraente para o pot odds da situação.")

    if not parts:
        parts.append(f"A linha {action_pt.upper()} ficou abaixo do esperado para o spot — {best_pt.upper()} era a ação correta.")

    parts.append(f"Ação esperada: {best_pt.upper()}.")

    return {
        "summary": summary_map[label],
        "mathExplanation": "",
        "strategicExplanation": " ".join(parts),
    }
