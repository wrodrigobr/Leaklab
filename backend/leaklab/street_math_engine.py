from __future__ import annotations
from .models import HandState, MathSnapshot

# Equity preflop de cada mão canônica vs UMA mão aleatória (all-in até o river).
# Gerado por Monte Carlo exato (eval7, 100k amostras/mão) —
# scripts/gen_preflop_vs_random_equity.py. Substitui o antigo bucket de 6 tiers,
# que dava o mesmo valor pra todo par alto (JJ=QQ=AA=0.64) e não era de fato
# "vs random". Agora o card mostra o número que o label promete.
PREFLOP_EQ_VS_RANDOM = {
    'AA': 0.8512, 'KK': 0.8236, 'QQ': 0.7995, 'JJ': 0.7749, 'TT': 0.7498, '99': 0.7204,
    '88': 0.6908, 'AKs': 0.6715, '77': 0.663, 'AQs': 0.663, 'AKo': 0.6531, 'AJs': 0.6529,
    'AQo': 0.644, 'ATs': 0.6418, 'AJo': 0.6366, '66': 0.6356, 'KQs': 0.6313, 'A9s': 0.6288,
    'ATo': 0.6279, 'KJs': 0.6257, 'A8s': 0.6183, 'KTs': 0.6178, 'KQo': 0.6164, 'A7s': 0.6119,
    'A9o': 0.6064, 'KJo': 0.6054, '55': 0.6044, 'QJs': 0.6012, 'A8o': 0.5999, 'A6s': 0.5998,
    'K9s': 0.5989, 'A5s': 0.598, 'KTo': 0.5979, 'QTs': 0.5927, 'A4s': 0.5915, 'A7o': 0.5899,
    'QJo': 0.5842, 'K8s': 0.5837, 'A6o': 0.5801, 'K9o': 0.5794, 'A3s': 0.5792, 'K7s': 0.577,
    'Q9s': 0.5766, 'A5o': 0.5757, 'QTo': 0.5749, 'JTs': 0.5733, 'A2s': 0.5725, '44': 0.5709,
    'A4o': 0.5673, 'K6s': 0.5639, 'Q8s': 0.5598, 'K8o': 0.5582, 'J9s': 0.558, 'A3o': 0.5571,
    'K5s': 0.5571, 'Q9o': 0.5548, 'JTo': 0.554, 'K7o': 0.553, 'A2o': 0.5498, 'K4s': 0.5462,
    'K3s': 0.5438, 'J8s': 0.5436, 'Q7s': 0.5414, 'K6o': 0.5405, 'T9s': 0.5394, 'Q8o': 0.5382,
    '33': 0.5378, 'Q6s': 0.5368, 'J9o': 0.5325, 'K5o': 0.5323, 'K2s': 0.5292, 'Q5s': 0.5259,
    'J7s': 0.5251, 'K4o': 0.5238, 'T8s': 0.5225, 'Q7o': 0.5189, 'Q4s': 0.5176, 'T9o': 0.5168,
    'J8o': 0.5155, 'K3o': 0.5137, 'Q6o': 0.5097, '98s': 0.5078, 'Q3s': 0.5077, 'T7s': 0.5077,
    'J6s': 0.5073, 'K2o': 0.5044, 'Q2s': 0.502, '22': 0.5016, 'Q5o': 0.5016, 'J5s': 0.4998,
    'J7o': 0.4953, 'T8o': 0.4946, '97s': 0.4924, 'J4s': 0.4918, 'Q4o': 0.4912, 'T6s': 0.4898,
    'Q3o': 0.4829, 'J3s': 0.4821, '98o': 0.4814, 'J6o': 0.4813, '87s': 0.4796, 'T7o': 0.4789,
    'J2s': 0.4738, 'Q2o': 0.4733, '96s': 0.4728, 'J5o': 0.4727, 'T5s': 0.4726, 'T4s': 0.4675,
    '97o': 0.4624, 'J4o': 0.4624, '86s': 0.4623, 'T6o': 0.4623, 'T3s': 0.4558, '95s': 0.4552,
    '76s': 0.4525, 'J3o': 0.4522, '87o': 0.4517, 'T2s': 0.4482, '85s': 0.4468, 'J2o': 0.4448,
    'T5o': 0.4432, '96o': 0.4426, '94s': 0.4387, 'T4o': 0.4353, '75s': 0.4349, '86o': 0.4334,
    '93s': 0.4328, '65s': 0.4324, '95o': 0.4281, '84s': 0.4271, '76o': 0.4236, 'T3o': 0.4228,
    '92s': 0.4201, 'T2o': 0.4193, '74s': 0.4191, '54s': 0.4157, '85o': 0.415, '64s': 0.4135,
    '94o': 0.4087, '83s': 0.4075, '75o': 0.4049, '82s': 0.4028, '73s': 0.4005, '93o': 0.4003,
    '84o': 0.398, '53s': 0.3964, '65o': 0.3959, '63s': 0.3936, '92o': 0.3889, '74o': 0.3854,
    '43s': 0.3837, '54o': 0.3835, '64o': 0.3811, '72s': 0.3809, '52s': 0.378, '62s': 0.3773,
    '83o': 0.3743, '82o': 0.3689, '42s': 0.3665, '73o': 0.3657, '53o': 0.3629, '63o': 0.3612,
    '32s': 0.3585, '43o': 0.3493, '72o': 0.3473, '52o': 0.3418, '62o': 0.341, '42o': 0.3329,
    '32o': 0.3237,
}
_RANK_ORD = '23456789TJQKA'


def _canon_hand(hero_cards: str | None) -> str | None:
    """'AsKh' → 'AKo'; 'AsKs' → 'AKs'; 'TsTh' → 'TT'. None se inválido."""
    if not hero_cards or len(hero_cards) < 4:
        return None
    r1, s1, r2, s2 = hero_cards[0], hero_cards[1], hero_cards[2], hero_cards[3]
    if r1 not in _RANK_ORD or r2 not in _RANK_ORD:
        return None
    if r1 == r2:
        return r1 + r2
    hi, lo = (r1, r2) if _RANK_ORD.index(r1) > _RANK_ORD.index(r2) else (r2, r1)
    return hi + lo + ('s' if s1 == s2 else 'o')


def build_math_snapshot(state: HandState) -> MathSnapshot:
    pot = max(state.pot_size, 0.0)
    facing = max(state.facing_size, 0.0)
    pot_odds_equity = None
    if facing > 0:
        pot_odds_equity = round(facing / (pot + facing), 4) if (pot + facing) > 0 else None

    villain_range = (state.metadata or {}).get('villain_range') if state.street == 'preflop' else None
    estimated_equity = _estimate_hand_equity(state.hero_cards, state.board, state.street, villain_range)
    # Ajuste multiway: equity heuristica eh calibrada vs random HU. Em pote
    # 3+way, equity real cai significativamente. Aplica fator empirico em
    # postflop (preflop ja usa ranges GTO especificos por cenario).
    if estimated_equity is not None and state.street != 'preflop':
        n_opp = (state.metadata or {}).get('n_active_opponents', 1) or 1
        if n_opp > 1:
            # eq_multiway = eq_HU / (1 + 0.3 * (n_opp - 1))
            # 2 opps -> 77% do HU; 3 opps -> 62%; 4 opps -> 53%; 5 opps -> 45%
            factor = 1.0 / (1.0 + 0.3 * (n_opp - 1))
            estimated_equity = round(estimated_equity * factor, 4)
    implied = 0.1 if state.street in {"flop", "turn"} else 0.0
    reverse_implied = 0.15 if (state.hero_cards and len(state.hero_cards) >= 4 and state.hero_cards[0] != state.hero_cards[2]) else 0.05
    pressure = _estimate_pressure(state)
    return MathSnapshot(
        pot_odds_equity=pot_odds_equity,
        estimated_hand_equity=estimated_equity,
        implied_odds_factor=implied,
        reverse_implied_odds_factor=reverse_implied,
        pressure_score=pressure,
    )


def _estimate_hand_equity(hero_cards: str | None, board, street: str,
                          villain_range: dict | None = None) -> float | None:
    if not hero_cards:
        return None
    ranks = hero_cards[0] + (hero_cards[2] if len(hero_cards) >= 4 else "")
    pair = len(hero_cards) >= 4 and hero_cards[0] == hero_cards[2]
    broadway = all(r in "TJQKA" for r in ranks)
    suited = len(hero_cards) >= 4 and hero_cards[1] == hero_cards[3]
    if street == "preflop":
        canon = _canon_hand(hero_cards)
        # #27 range-aware: contra um open conhecido, equity vs a RANGE GTO real do
        # villain (tight) — não vs random. Cai no vs-random se não há range/cobertura.
        if canon and villain_range:
            try:
                from leaklab.equity import equity_vs_range
                eq = equity_vs_range(canon, villain_range)
                if eq is not None:
                    return eq
            except Exception:
                pass
        # equity exata vs uma mão aleatória (tabela Monte Carlo). É o que o card
        # rotula "vs random". Fallback no heurístico antigo só se a mão não casar.
        if canon and canon in PREFLOP_EQ_VS_RANDOM:
            return PREFLOP_EQ_VS_RANDOM[canon]
        if pair:
            return 0.5 if hero_cards[0] in "23456" else 0.57 if hero_cards[0] in "789T" else 0.64
        if broadway and suited:
            return 0.49
        if broadway:
            return 0.45
        if suited:
            return 0.39
        return 0.33
    # Postflop: estimar a partir da MÃO FEITA contra o board (não mais cego ao board).
    # O heurístico antigo (pair=0.58 / broadway=0.41 / else=0.29) só enxergava PAR DE
    # BOLSO — qualquer mão que pareava o board (top/middle/bottom pair, dois pares,
    # trinca) caía em 0.29 igual a lixo (bug do par de J em K-6-J marcado fold/erro;
    # mesmo parente do bug da wheel). Agora classifica via eval7 e mapeia pra escala
    # "vs range típica de continuação". Draws e multiway são aplicados por cima
    # (draw_detector + fator multiway em build_math_snapshot), como antes.
    made = _postflop_made_equity(hero_cards, board)
    if made is not None:
        return made
    # Fallback (board incompleto/parse falhou): heurístico antigo conservador.
    if pair:
        return 0.58
    if broadway:
        return 0.41
    return 0.29


def _postflop_made_equity(hero_cards: str | None, board) -> float | None:
    """Equity postflop estimada a partir da força da MÃO FEITA do hero vs uma range
    típica de continuação (HU, pré-ajuste de draws/multiway). eval7 classifica a mão
    de 5–7 cartas; pares são refinados por posição relativa ao board (overpair / top /
    middle / bottom / underpair) porque a equity de um par depende fortemente disso.
    Retorna None se não der pra avaliar (board < 3 cartas, parse inválido, eval7 off)."""
    try:
        import eval7
    except Exception:
        return None
    try:
        if isinstance(hero_cards, str):
            hero = [hero_cards[i:i+2] for i in range(0, len(hero_cards), 2)]
        else:
            hero = list(hero_cards or [])
        hero = [str(c) for c in hero if c and len(str(c)) >= 2][:2]
        brd  = [str(c) for c in (board or []) if c and len(str(c)) >= 2][:5]
        if len(hero) < 2 or len(brd) < 3:
            return None
        ht = eval7.handtype(eval7.evaluate([eval7.Card(c) for c in hero + brd]))
        hr = sorted((_RANK_ORD.index(c[0]) for c in hero if c[0] in _RANK_ORD), reverse=True)
        br = sorted((_RANK_ORD.index(c[0]) for c in brd  if c[0] in _RANK_ORD), reverse=True)
        if len(hr) < 2 or not br:
            return None
        bmax, bmin = br[0], br[-1]

        strong = {'Straight Flush': 0.95, 'Quads': 0.95, 'Full House': 0.92,
                  'Flush': 0.82, 'Straight': 0.80, 'Trips': 0.82, 'Two Pair': 0.72}
        if ht in strong:
            return strong[ht]

        if ht == 'Pair':
            if hero[0][0] == hero[1][0]:                       # par de bolso
                return 0.66 if hr[0] > bmax else 0.42          # overpair vs underpair
            paired = [r for r in hr if r in br]                # par com o board
            if paired:
                pr   = paired[0]
                kick = max((r for r in hr if r != pr), default=0)
                if pr >= bmax:
                    return 0.62 if kick >= _RANK_ORD.index('Q') else 0.56   # top pair
                if pr <= bmin:
                    return 0.42                                             # bottom pair
                return 0.50                                                 # middle pair
            return 0.40                                        # par só no board (joga kicker)

        # High Card: valor por overcards vivos (potencial de melhorar).
        over = sum(1 for r in hr if r > bmax)
        if over >= 2:
            return 0.34
        if over == 1:
            return 0.28
        return 0.20
    except Exception:
        return None


def _estimate_pressure(state: HandState) -> float:
    if state.facing_size <= 0:
        return 0.05
    ratio = state.facing_size / max(state.pot_size, 1.0)
    if ratio >= 1.0:
        return 0.8
    if ratio >= 0.66:
        return 0.6
    if ratio >= 0.33:
        return 0.4
    return 0.2
