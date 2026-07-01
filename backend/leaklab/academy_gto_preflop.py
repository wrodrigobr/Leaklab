"""
Academia — Exercícios GTO Preflop.

Gera spots preflop (RFI / vs RFI / vs 3-bet) a partir das ranges GTO 9-max e
avalia a resposta do usuário NO SERVIDOR via preflop_gto_ranges.analyze_preflop.

A resposta correta NUNCA é enviada ao cliente: o endpoint /question manda só o
contexto do spot (posição, stack, mão, ação dos vilões) e as opções de ação;
o veredito (ação GTO, frequências, explicação) só volta no /submit. Isso mantém
as ranges no servidor — alinhado à política de não expor a lógica interna.
"""
from __future__ import annotations

import random

from leaklab.preflop_gto_ranges import analyze_preflop

# Ordem de ação preflop 9-max (early → late). SB abre; BB nunca dá RFI.
_ACTION_ORDER = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
_RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

# Stacks "profundos" — evitam o fallback push/fold (jam) e mantêm as opções
# fold/call/raise limpas para o treino de ranges.
_STACKS = [30, 40, 50, 75, 100]

_SCENARIOS_BY_FILTER = {
    'rfi':     ['rfi'],
    'vs_rfi':  ['vs_rfi'],
    'vs_3bet': ['vs_3bet'],
    'mixed':   ['rfi', 'vs_rfi', 'vs_3bet'],
}
_TYPE_BY_SCENARIO = {'rfi': 'gto_rfi', 'vs_rfi': 'gto_vs_rfi', 'vs_3bet': 'gto_vs_3bet'}
_XP_BY_SCENARIO   = {'rfi': 20, 'vs_rfi': 25, 'vs_3bet': 30}

# Rótulo da ação "raise" muda por cenário (3-bet vs 4-bet).
_OPTIONS = {
    'rfi':     [('fold', 'Fold'), ('raise', 'Raise (abrir)')],
    'vs_rfi':  [('fold', 'Fold'), ('call', 'Call'), ('raise', '3-Bet')],
    'vs_3bet': [('fold', 'Fold'), ('call', 'Call'), ('raise', '4-Bet')],
}

# Rótulo PT por ação, para a explicação.
_ACT_LABEL = {
    'fold': 'fold', 'call': 'call', 'raise': 'raise', 'jam': 'all-in', 'allin': 'all-in',
}


def _all_hands() -> list[str]:
    """169 hand types: pares (XX), suited (AKs) e offsuit (AKo)."""
    hands: set[str] = set()
    for i, hi in enumerate(_RANKS):
        for j, lo in enumerate(_RANKS):
            if i == j:
                hands.add(hi + lo)            # par
            elif i < j:
                hands.add(hi + lo + 's')      # suited (hi tem rank maior)
            else:
                hands.add(lo + hi + 'o')      # offsuit
    return sorted(hands)


_HANDS = _all_hands()


def _hand_to_cards(hand: str) -> list[dict]:
    """Cartas representativas para exibição. 'AKs'→A♠K♠, 'AKo'→A♠K♥, 'TT'→T♠T♥."""
    if len(hand) == 2:                                  # par
        r = hand[0]
        return [{'rank': r, 'suit': 's'}, {'rank': r, 'suit': 'h'}]
    hi, lo, kind = hand[0], hand[1], hand[2]
    second_suit = 's' if kind == 's' else 'h'
    return [{'rank': hi, 'suit': 's'}, {'rank': lo, 'suit': second_suit}]


def _random_setup(scenario: str):
    """Retorna (position, vs_position, facing_size, is_3bet_pot) para o cenário."""
    n = len(_ACTION_ORDER)
    if scenario == 'rfi':
        pos = random.choice(_ACTION_ORDER[:-1])          # qualquer um, menos BB
        return pos, '', 0.0, False
    if scenario == 'vs_rfi':
        oi = random.randint(0, n - 2)                    # opener (não BB)
        di = random.randint(oi + 1, n - 1)               # defensor em seat posterior
        return _ACTION_ORDER[di], _ACTION_ORDER[oi], 2.2, False
    # vs_3bet: hero abriu (pos), vilão deu 3-bet de um seat posterior / blind
    oi = random.randint(0, n - 3)
    ti = random.randint(oi + 1, n - 1)
    return _ACTION_ORDER[oi], _ACTION_ORDER[ti], 8.0, True


def _context_text(scenario: str, pos: str, vs_pos: str, stack: int) -> str:
    if scenario == 'rfi':
        return (f"Ação foldada até você — primeiro a agir no pote. "
                f"Você está em {pos} com {stack}bb efetivos.")
    if scenario == 'vs_rfi':
        return f"{vs_pos} abre. Você está em {pos} com {stack}bb efetivos."
    return f"Você abriu de {pos} e {vs_pos} deu 3-bet. {stack}bb efetivos."


def generate_gto_preflop_question(scenario_filter: str = 'mixed') -> dict:
    """Gera uma questão GTO preflop SEM revelar a resposta."""
    pool = _SCENARIOS_BY_FILTER.get(scenario_filter, _SCENARIOS_BY_FILTER['mixed'])

    chosen = None
    for _ in range(80):
        scenario = random.choice(pool)
        stack    = random.choice(_STACKS)
        pos, vs_pos, facing, is_3b = _random_setup(scenario)
        hand     = random.choice(_HANDS)
        # vs_3bet: hero abriu e enfrenta 3-bet → precisa de hero_was_aggressor=True + facing_raises=1
        # (sem isso analyze_preflop rotula vs_rfi e volta indisponível). Ver leak_trainer/backlog #31.
        res = analyze_preflop(pos, hand, float(stack), 'fold',
                              facing_size=facing, vs_position=vs_pos, is_3bet_pot=is_3b,
                              hero_was_aggressor=is_3b, facing_raises=(1 if is_3b else 0))
        if not res.get('available') or res.get('scenario') != scenario:
            continue
        # Evita spots cuja ação dominante (jam) está fora das nossas opções limpas.
        opt_actions = {a for a, _ in _OPTIONS[scenario]}
        rec = res.get('recommended_actions') or []
        if rec and rec[0] not in opt_actions:
            continue
        chosen = (scenario, stack, pos, vs_pos, facing, is_3b, hand)
        break

    if chosen is None:
        # Fallback determinístico (spot RFI clássico) — raríssimo.
        chosen = ('rfi', 50, 'BTN', '', 0.0, False, 'A5s')

    scenario, stack, pos, vs_pos, facing, is_3b, hand = chosen
    opts = _OPTIONS[scenario]
    return {
        'type':       _TYPE_BY_SCENARIO[scenario],
        'scenario':   scenario,
        'context':    _context_text(scenario, pos, vs_pos, stack),
        'prompt':     'Qual a ação GTO?',
        'hand':       hand,
        'hero_cards': _hand_to_cards(hand),
        'options':    [{'action': a, 'label': l} for a, l in opts],
        'xp_value':   _XP_BY_SCENARIO[scenario],
        # Echo do spot — devolvido no /submit para reavaliar no servidor.
        'spot': {
            'position': pos, 'vs_position': vs_pos, 'stack_bb': stack,
            'facing_size': facing, 'is_3bet_pot': is_3b, 'hand': hand,
            'scenario': scenario,
            'hero_was_aggressor': is_3b, 'facing_raises': (1 if is_3b else 0),
        },
    }


def _build_explanation(spot: dict, res: dict, action: str) -> str:
    hand = spot.get('hand', '')
    hf   = res.get('hand_freq') or {}
    nonzero = {k: v for k, v in hf.items() if v and v > 0.01}
    parts: list[str] = []
    if nonzero:
        freq_str = ', '.join(
            f"{_ACT_LABEL.get(k, k)} {round(v * 100)}%"
            for k, v in sorted(nonzero.items(), key=lambda x: -x[1])
        )
        parts.append(f"GTO joga {hand} aqui como: {freq_str}.")
    else:
        rec = res.get('recommended_actions') or ['fold']
        parts.append(f"GTO recomenda {_ACT_LABEL.get(rec[0], rec[0])} com {hand} neste spot.")

    quality = res.get('action_quality')
    if quality == 'correct':
        parts.append("Sua escolha está alinhada ao GTO.")
    elif quality == 'acceptable':
        parts.append("Sua escolha é defensável — uma das ações que o GTO mistura aqui.")
    else:
        parts.append("Sua escolha desvia do GTO neste spot.")
    return ' '.join(parts)


def grade_gto_preflop_answer(spot: dict, action: str) -> dict:
    """Avalia a ação escolhida via analyze_preflop. correct/acceptable = acerto."""
    is_3b = bool(spot.get('is_3bet_pot', False))
    res = analyze_preflop(
        spot.get('position', ''),
        spot.get('hand', ''),
        float(spot.get('stack_bb', 50) or 50),
        (action or '').lower(),
        facing_size=float(spot.get('facing_size', 0) or 0),
        vs_position=spot.get('vs_position', '') or '',
        is_3bet_pot=is_3b,
        # mesmas flags do generate: sem isto o vs_3bet reclassifica como vs_rfi e a correção mente
        hero_was_aggressor=bool(spot.get('hero_was_aggressor', is_3b)),
        facing_raises=int(spot.get('facing_raises', 1 if is_3b else 0) or 0),
    )
    quality    = res.get('action_quality', 'unknown')
    is_correct = quality in ('correct', 'acceptable')
    rec        = res.get('recommended_actions') or ['fold']
    return {
        'is_correct':     is_correct,
        'action_quality': quality,
        'best_action':    rec[0],
        'recommended':    rec,
        'hand_freq':      res.get('hand_freq') or {},
        'range_pct':      res.get('range_pct'),
        'explanation':    _build_explanation(spot, res, action),
    }
