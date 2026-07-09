"""
academy.py — Gerador de exercícios para a Academia LeakLab.

Dois módulos iniciais:
  - Matemática Intuitiva: pot odds, EV, call/fold decisions
  - Força de Mão no Board: classificação de hand strength e texturas

Exercícios são gerados a partir do histórico real do jogador quando
possível — spots familiares têm retenção pedagógica muito maior.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from typing import Optional

from database.schema import get_conn
from database.repositories import _adapt

# ── Card utilities ─────────────────────────────────────────────────────────────

RANK_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14,
}
RANK_NAMES = {v: k for k, v in RANK_VALUES.items()}


def _parse_cards(raw: Optional[str]) -> list[tuple[str, str]]:
    """Parse '[As,Kh]' or 'As Kh' or JSON array → list of (rank, suit)."""
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith('['):
        try:
            tokens = json.loads(raw)
        except Exception:
            tokens = []
    else:
        tokens = raw.replace(',', ' ').split()

    result = []
    for t in tokens:
        t = t.strip()
        if len(t) < 2:
            continue
        rank = t[:-1].upper()
        suit = t[-1].lower()
        if rank in RANK_VALUES and suit in ('s', 'h', 'd', 'c'):
            result.append((rank, suit))
    return result


def _hand_bucket(hero: list[tuple[str, str]], board: list[tuple[str, str]]) -> int:
    """
    Classifies hero hand strength given the board.
    Returns 0–4:
      4 = Monster  (set / straight / flush / full house / quads)
      3 = Strong   (two pair, top pair, overpair)
      2 = Medium   (middle pair / weak top pair / bottom pair)
      1 = Draw     (flush draw 4+ / OESD / gutshot with nut equity)
      0 = Air      (no pair, no significant draw)
    """
    if not hero or not board:
        return 0

    def rv(c):  return RANK_VALUES.get(c[0], 0)
    def sv(c):  return c[1]

    h_rv = [rv(c) for c in hero]
    h_sv = [sv(c) for c in hero]
    b_rv = [rv(c) for c in board]
    all_rv = h_rv + b_rv
    all_sv = h_sv + [sv(c) for c in board]

    rank_cnt = Counter(all_rv)
    suit_cnt = Counter(all_sv)

    # Quads
    if max(rank_cnt.values()) >= 4:
        return 4

    # Full house
    sorted_vals = sorted(rank_cnt.values(), reverse=True)
    if len(sorted_vals) >= 2 and sorted_vals[0] >= 3 and sorted_vals[1] >= 2:
        return 4

    # Flush involving hero
    for s in ('s', 'h', 'd', 'c'):
        if all_sv.count(s) >= 5 and h_sv.count(s) >= 1:
            return 4

    # Straight involving hero
    unique = sorted(set(all_rv))
    check_list = unique + ([1] if 14 in unique else [])
    check_list = sorted(set(check_list))
    for i in range(len(check_list) - 4):
        window = check_list[i:i + 5]
        if window[4] - window[0] == 4 and len(set(window)) == 5:
            hero_in = any(
                (hr == 14 and 1 in window) or hr in window
                for hr in h_rv
            )
            if hero_in:
                return 4

    # Set / trips
    for hr in set(h_rv):
        if rank_cnt.get(hr, 0) >= 3:
            return 4

    # Two pair (hero involved)
    pairs = [r for r, cnt in rank_cnt.items() if cnt >= 2]
    hero_in_pairs = [r for r in h_rv if r in pairs]
    if len(pairs) >= 2 and hero_in_pairs:
        return 3

    # Overpair (pocket pair > all board cards)
    if len(h_rv) == 2 and h_rv[0] == h_rv[1]:
        if b_rv and h_rv[0] > max(b_rv):
            return 3

    # Top pair
    board_max = max(b_rv) if b_rv else 0
    if board_max and (h_rv[0] == board_max or (len(h_rv) > 1 and h_rv[1] == board_max)):
        return 3

    # Middle / bottom pair
    for hr in h_rv:
        if hr in b_rv:
            return 2

    # Flush draw (4 to a flush, hero contributes)
    if len(h_sv) == 2 and h_sv[0] == h_sv[1]:
        if all_sv.count(h_sv[0]) >= 4:
            return 1

    # Straight draw (4 to a straight including hero)
    ext = sorted(set(all_rv + ([1] if 14 in all_rv else [])))
    for i in range(len(ext) - 3):
        window4 = ext[i:i + 4]
        if window4[3] - window4[0] <= 4 and len(set(window4)) == 4:
            hero_in = any(
                (hr == 14 and 1 in window4) or hr in window4
                for hr in h_rv
            )
            if hero_in:
                return 1

    return 0


def _board_texture(board: list[tuple[str, str]]) -> str:
    """Returns 'dry', 'semi_wet', or 'wet'."""
    if not board:
        return 'dry'
    suits = [c[1] for c in board]
    ranks = sorted([RANK_VALUES.get(c[0], 0) for c in board])
    suit_cnt = max(Counter(suits).values())

    # Flush draw present on board
    flush_draw = suit_cnt >= 2

    # Straight draw potential: count gaps ≤ 1 in sorted ranks
    connectedness = 0
    for i in range(len(ranks) - 1):
        gap = ranks[i + 1] - ranks[i]
        if gap <= 2:
            connectedness += 1

    if flush_draw and connectedness >= 1:
        return 'wet'
    if flush_draw or connectedness >= 1:
        return 'semi_wet'
    return 'dry'


def _board_texture_label_pt(texture: str) -> str:
    return {'dry': 'Seco', 'semi_wet': 'Semi-úmido', 'wet': 'Úmido / coordenado'}.get(texture, texture)


# ── Math drill ─────────────────────────────────────────────────────────────────

# Realistic pot/bet sizes for synthetic question generation.
# Bets are expressed as fractions of pot for natural variety.
_POT_SIZES        = [3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40]
_BET_FRACS        = [0.25, 0.33, 0.40, 0.50, 0.60, 0.67, 0.75, 1.00, 1.25, 1.50]
_STREETS          = ['flop', 'turn', 'river']      # postflop only — preflop excluded
_STREETS_WITH_DRAWS = ['flop', 'turn']             # streets where rule-of-2/4 applies
_POSITIONS        = ['IP', 'OOP']


def _random_pot_bet() -> tuple[float, float]:
    """Generate a fresh random realistic pot/bet pair (in BBs)."""
    pot = float(random.choice(_POT_SIZES))
    bet = round(pot * random.choice(_BET_FRACS), 1)
    bet = max(1.0, bet)
    return pot, bet


def _fetch_math_decision(user_id: int) -> Optional[dict]:
    """Returns a random postflop decision from user history (context only — NOT for pot/bet values).
    Preflop decisions are excluded: the rule of 2/4 and draw concepts don't apply there."""
    conn = get_conn()
    try:
        row = conn.execute(_adapt("""
            SELECT d.label, d.action_taken, d.best_action, d.street, d.position
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND d.facing_bet IS NOT NULL AND d.facing_bet > 0
              AND d.street IN ('flop', 'turn', 'river')
            ORDER BY RANDOM()
            LIMIT 1
        """), (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _context_or_default(decision: Optional[dict]) -> dict:
    """Returns a context dict with street/position, using defaults when no history."""
    if decision:
        return decision
    return {
        'label': 'standard',
        'action_taken': random.choice(['call', 'fold']),
        'best_action': random.choice(['call', 'fold']),
        'street': random.choice(_STREETS),
        'position': random.choice(_POSITIONS),
    }


def generate_math_question(user_id: int, level: str = 'beginner') -> dict:
    """
    Generates math exercise questions by level.

    Beginner:     pot_odds_calc, call_or_fold, outs_count
    Intermediate: equity_estimate, odds_vs_equity, ev_direction

    pot/bet values are ALWAYS synthetic (random from realistic pools) to
    guarantee variety. History is used only for pedagogical context
    (street, position, label) so questions feel grounded in real spots.
    """
    ctx = _context_or_default(_fetch_math_decision(user_id))
    pot, bet = _random_pot_bet()
    min_equity_pct = round(bet / (pot + bet) * 100, 1)

    if level == 'intermediate':
        qtype = random.choices(
            ['equity_estimate', 'odds_vs_equity', 'ev_direction'],
            weights=[0.40, 0.35, 0.25],
        )[0]
        if qtype == 'equity_estimate':
            return _equity_estimate_question()
        if qtype == 'odds_vs_equity':
            return _odds_vs_equity_question(pot, bet, ctx)
        return _ev_direction_question(pot, bet, min_equity_pct, ctx)

    # Beginner (default)
    qtype = random.choices(
        ['pot_odds_calc', 'call_or_fold', 'outs_count'],
        weights=[0.35, 0.35, 0.30],
    )[0]
    if qtype == 'outs_count':
        return _outs_count_question()
    if qtype == 'pot_odds_calc':
        return _pot_odds_calc_question(pot, bet, min_equity_pct, ctx)
    return _call_or_fold_question(pot, bet, min_equity_pct, ctx)


def _pot_odds_calc_question(pot: float, bet: float, correct_pct: float, d: dict) -> dict:
    """Qual % mínima de equity para call ser +EV?"""
    # Round to nearest integer for clean options
    correct = round(correct_pct)

    # Distractors: bet/pot (forgetting to include call), and a third plausible wrong
    distractor1 = round(bet / pot * 100) if pot else correct + 15
    distractor2 = round((pot / (pot + bet)) * 100)

    options = _make_options(correct, [distractor1, distractor2])

    explanation = (
        f"Fórmula: bet ÷ (pot + bet) = {bet} ÷ {pot + bet:.1f} ≈ **{correct_pct:.1f}%**.\n\n"
        f"Você precisa de pelo menos essa equity para o call ser matematicamente justificado. "
        f"Abaixo disso, fold preserva mais equity de stack a longo prazo."
    )

    total_after_call = pot + 2 * bet
    return {
        'type': 'pot_odds_calc',
        'concept': '**Pot odds** são o preço do call: o que você paga em relação ao tamanho do pote. Definem a equity mínima para o call valer a pena.',
        'question': f'Pot: **{pot} BB**. Villain aposta **{bet} BB**.\nQual a equity mínima necessária para o call ser +EV?',
        'options': [f'{o}%' for o in options['values']],
        'correct_index': options['correct_index'],
        'explanation': explanation,
        'mental_tip': (
            f"**Fórmula:** call ÷ (pot + call) = {bet} ÷ {total_after_call:.0f} ≈ **{correct_pct:.0f}%**. "
            "Tabela de referência rápida: "
            "¼ pot → 20% | ½ pot → **25%** | ⅔ pot → **28%** | pot → **33%** | 1,5× pot → 37% | 2× pot → **40%**. "
            "Decore estas âncoras — a maioria das apostas cai nestes intervalos."
        ),
        'context': {'street': d.get('street'), 'position': d.get('position')},
        'xp_value': 15,
    }


def _call_or_fold_question(pot: float, bet: float, min_equity_pct: float, d: dict) -> dict:
    """Dado equity e pot odds, call ou fold?"""
    # Invent an estimated equity slightly above or below pot odds
    # If the label says mistake, use the user's error as the scenario
    if d.get('label') in ('small_mistake', 'clear_mistake') and d.get('action_taken') == 'call':
        # They called incorrectly → estimated equity was below pot odds
        estimated_equity = round(min_equity_pct * random.uniform(0.65, 0.85))
        correct_action   = 'fold'
    elif d.get('label') in ('small_mistake', 'clear_mistake') and d.get('action_taken') == 'fold':
        # They folded incorrectly → estimated equity was above pot odds
        estimated_equity = round(min_equity_pct * random.uniform(1.10, 1.30))
        correct_action   = 'call'
    else:
        # Standard spot: randomly generate a clear scenario
        if random.random() < 0.5:
            estimated_equity = round(min_equity_pct * random.uniform(1.15, 1.40))
            correct_action   = 'call'
        else:
            estimated_equity = round(min_equity_pct * random.uniform(0.60, 0.85))
            correct_action   = 'fold'

    options = ['Call', 'Fold']
    correct_index = 0 if correct_action == 'call' else 1

    diff = estimated_equity - round(min_equity_pct)
    sign = '+' if diff >= 0 else ''

    explanation = (
        f"Pot odds exigem **{min_equity_pct:.1f}%** de equity.\n\n"
        f"Com **{estimated_equity}%** de equity estimada, você tem "
        f"**{sign}{diff} pp** {'a mais' if diff >= 0 else 'a menos'} do que o break-even — "
        f"por isso **{correct_action.upper()}** é a linha correta."
    )

    return {
        'type': 'call_or_fold',
        'concept': 'Pagar ou desistir é uma **comparação**: a sua equity estimada contra as pot odds exigidas pelo tamanho da aposta.',
        'question': (
            f'Pot: **{pot} BB**. Villain aposta **{bet} BB**.\n'
            f'Sua equity estimada neste spot: **{estimated_equity}%**.\n'
            f'Qual é a ação correta?'
        ),
        'options': options,
        'correct_index': correct_index,
        'explanation': explanation,
        'mental_tip': (
            "**Atalho:** equity estimada vs pot odds — dois números, uma comparação. "
            "Equity > pot odds → call. Equity < pot odds → fold. "
            "Referência de pot odds por sizing: ½ pot → 25% | ⅔ pot → 28% | pot → 33% | 1,5× → 37%. "
            "Para estimar equity: use outs × 2 (turn) ou outs × 4 (flop)."
        ),
        'context': {'street': d.get('street'), 'position': d.get('position')},
        'xp_value': 15,
    }


def _ev_direction_question(pot: float, bet: float, min_equity_pct: float, d: dict) -> dict:
    """Esta ação é +EV ou -EV?"""
    label = d.get('label', 'standard')
    action = d.get('action_taken', 'call')

    # Derive EV direction from label + action
    if label in ('small_mistake', 'clear_mistake'):
        ev_positive = False
        equity_used = round(min_equity_pct * random.uniform(0.55, 0.80))
    else:
        ev_positive = True
        equity_used = round(min_equity_pct * random.uniform(1.15, 1.45))

    options = ['+EV (boa jogada)', '−EV (jogada negativa)', 'Breakeven (±0 EV)']
    correct_index = 0 if ev_positive else 1

    diff = equity_used - round(min_equity_pct)
    sign = '+' if diff >= 0 else ''

    explanation = (
        f"Pot odds exigem **{min_equity_pct:.1f}%**. "
        f"Com **{equity_used}%** de equity, o déficit/superávit é **{sign}{diff} pp**.\n\n"
        f"Quando sua equity {'supera' if ev_positive else 'fica abaixo d'} o break-even, "
        f"a ação é {'**+EV**' if ev_positive else '**−EV**'} e deve ser "
        f"{'executada' if ev_positive else 'evitada'} a longo prazo."
    )

    return {
        'type': 'ev_direction',
        'concept': '**EV (valor esperado)** é o lucro ou prejuízo médio de uma jogada repetida infinitas vezes — +EV ganha no longo prazo, −EV perde.',
        'question': (
            f'Pot: **{pot} BB**. Bet: **{bet} BB**.\n'
            f'Equity estimada do hero: **{equity_used}%**.\n'
            f'O call é…'
        ),
        'options': options,
        'correct_index': correct_index,
        'explanation': explanation,
        'mental_tip': (
            "**Atalho mental:** equity > pot odds = **+EV sempre**, sem cálculo adicional. "
            "Quer estimar quanto? Diferença em pp × pot = EV aproximado. "
            "Ex: equity 5 pp acima do break-even, pot = 20 BB → ~+1 BB por call."
        ),
        'context': {'street': d.get('street'), 'position': d.get('position')},
        'xp_value': 15,
    }


def _synthetic_pot_odds_question() -> dict:
    """Fallback when user has no history with facing_bet data."""
    scenarios = [
        (12, 6),   # 33%
        (10, 5),   # 33%
        (8,  4),   # 33%
        (15, 10),  # 40%
        (20, 5),   # 20%
        (10, 10),  # 50%
        (12, 8),   # 40%
    ]
    pot, bet = random.choice(scenarios)
    correct_pct = round(bet / (pot + bet) * 100)
    distractor1 = round(bet / pot * 100)
    distractor2 = round((pot / (pot + bet)) * 100)
    options = _make_options(correct_pct, [distractor1, distractor2])

    total_after_call = pot + 2 * bet
    return {
        'type': 'pot_odds_calc',
        'concept': '**Pot odds** são o preço do call: o que você paga em relação ao tamanho do pote. Definem a equity mínima para o call valer a pena.',
        'question': f'Pot: **{pot} BB**. Villain aposta **{bet} BB**.\nQual a equity mínima necessária para o call ser +EV?',
        'options': [f'{o}%' for o in options['values']],
        'correct_index': options['correct_index'],
        'explanation': (
            f"Fórmula: bet ÷ (pot + bet) = {bet} ÷ {pot + bet} ≈ **{correct_pct}%**.\n\n"
            "Você precisa de pelo menos essa equity para o call ser matematicamente justificado."
        ),
        'mental_tip': (
            f"**Atalho mental:** call ÷ pot_total = {bet} ÷ {total_after_call} ≈ **{correct_pct}%**. "
            "Referências rápidas: aposta ½ pot → ~25%; aposta ⅔ pot → ~29%; aposta pot → ~33%; aposta 2× pot → ~40%."
        ),
        'context': {},
        'xp_value': 15,
    }


def _make_options(correct: int, distractors: list[int]) -> dict:
    """Builds 3 shuffled options, returns values list + correct_index."""
    # De-dupe distractors that equal correct
    distractors = [d for d in distractors if d != correct]
    # Add extra distractor if needed
    while len(distractors) < 2:
        offset = random.choice([-10, -15, 10, 15, 20])
        candidate = max(5, min(95, correct + offset))
        if candidate != correct:
            distractors.append(candidate)
    distractors = distractors[:2]

    pool = [correct] + distractors
    random.shuffle(pool)
    return {'values': pool, 'correct_index': pool.index(correct)}


# ── Board Strength drill ───────────────────────────────────────────────────────

BUCKET_LABELS = {
    4: 'Mão muito forte (set / straight / flush / boat)',
    3: 'Mão forte (2 pares / top pair / overpair)',
    2: 'Par médio ou fraco',
    1: 'Draw (flush draw, OESD ou gutshot — sem par)',
    0: 'Air (sem par, sem draw relevante)',
}

BUCKET_LABELS_SHORT = {
    4: 'Mão muito forte',
    3: 'Mão forte',
    2: 'Par médio/fraco',
    1: 'Draw (sem par feito)',
    0: 'Air (nada)',
}

TEXTURE_LABELS = {
    'dry':      'Seco (sem flush/straight draw relevante)',
    'semi_wet': 'Semi-úmido (um draw presente)',
    'wet':      'Úmido / coordenado (múltiplos draws)',
}


def _fetch_board_decision(user_id: int, street: str = None) -> Optional[dict]:
    """Returns a random postflop decision with hero_cards and board."""
    streets = f"AND d.street = '{street}'" if street else "AND d.street IN ('flop','turn','river')"
    conn = get_conn()
    try:
        row = conn.execute(_adapt(f"""
            SELECT d.id, d.hero_cards, d.board, d.street, d.draw_profile,
                   d.label, d.action_taken, d.best_action, d.position,
                   d.score, d.stack_bb, d.m_ratio
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              {streets}
              AND d.hero_cards IS NOT NULL AND LENGTH(d.hero_cards) > 2
              AND d.board      IS NOT NULL AND LENGTH(d.board) > 2
            ORDER BY RANDOM()
            LIMIT 1
        """), (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def generate_board_strength_question(user_id: int) -> dict:
    """
    Gera (sintético — variedade infinita) um de 4 tipos de exercício de board:
      - hand_classify : força da mão em 5 buckets (flop/turn/river)
      - made_vs_draw  : mão feita / draw / nada
      - identify_draw : que projeto a mão tem (flush / straight / combo)
      - board_texture : textura do flop (seco / semi / úmido)

    `user_id` mantido por compatibilidade de assinatura — as cartas são sorteadas,
    não vêm do histórico (que causava repetição).
    """
    qtype = random.choices(
        ['hand_classify', 'made_vs_draw', 'identify_draw', 'board_texture'],
        weights=[0.34, 0.26, 0.20, 0.20],
    )[0]

    if qtype == 'board_texture':
        _, board = _deal_spot(3)
        return _board_texture_question(board, {})

    if qtype == 'identify_draw':
        # Sorteia até obter um projeto puro (bucket == 1, sem par feito) — flop ou turn.
        for _ in range(200):
            hero, board = _deal_spot(random.choice([3, 4]))
            if _hand_bucket(hero, board) == 1:
                return _identify_draw_question(hero, board)
        hero, board = _deal_spot(3)
        return _hand_classify_question(hero, board, {})

    if qtype == 'made_vs_draw':
        hero, board = _deal_spot(random.choice([3, 4, 5]))
        return _made_vs_draw_question(hero, board)

    hero, board = _deal_spot(random.choice([3, 3, 4, 5]))
    return _hand_classify_question(hero, board, {})


def _hand_classify_question(
    hero: list[tuple[str, str]],
    board: list[tuple[str, str]],
    d: dict,
) -> dict:
    correct_bucket = _hand_bucket(hero, board)
    correct_label  = BUCKET_LABELS_SHORT[correct_bucket]

    # Build 4 options: correct + 3 distinct distractors
    all_buckets = [0, 1, 2, 3, 4]
    other = [b for b in all_buckets if b != correct_bucket]
    random.shuffle(other)
    distractor_buckets = other[:3]
    pool = [correct_bucket] + distractor_buckets
    random.shuffle(pool)
    correct_index = pool.index(correct_bucket)

    options = [BUCKET_LABELS_SHORT[b] for b in pool]

    # Explanation based on bucket
    explanations = {
        4: 'Esta mão forma uma combinação muito forte: set, straight, flush ou melhor. Na maioria dos spots, a linha correta é construir o pote.',
        3: 'Top pair, overpair ou dois pares — mão forte mas vulnerável a overCards e boards coordenados. Proteção e bet sizing adequados são críticos.',
        2: 'Par médio ou fraco: você tem showdown value mas está em terreno contestável. Pot control é a postura padrão.',
        1: 'Você tem um **draw** (sem par feito): equity presente mas dependente de melhorar. Decisões envolvem comparar equity estimada vs pot odds para justificar continuar.',
        0: 'Sem par e sem draw relevante — air. Qualquer linha de continuação precisa de um objetivo claro (bluff bem selecionado com blockers).',
    }

    hero_str  = ' '.join(f'{r}{s}' for r, s in hero)
    board_str = ' '.join(f'{r}{s}' for r, s in board)

    return {
        'type': 'hand_classify',
        'question': f'Board: **{board_str}**\nSuas cartas: **{hero_str}**\nComo você classificaria esta mão?',
        'hero_cards':  [{'rank': r, 'suit': s} for r, s in hero],
        'board_cards': [{'rank': r, 'suit': s} for r, s in board],
        'options': options,
        'correct_index': correct_index,
        'explanation': explanations[correct_bucket],
        'mental_tip': (
            "**Atalho:** verifique em ordem: (1) suas cartas formam par com o board? → par médio/forte; "
            "(2) seu bolso bate as cartas do board? → overpair/set; "
            "(3) 4 do mesmo naipe = flush draw; 4 cartas em sequência (gap ≤1) = straight draw. "
            "Sem nada → air."
        ),
        'context': {
            'street':   d.get('street'),
            'position': d.get('position'),
            'stack_bb': d.get('stack_bb'),
        },
        'xp_value': 20,
    }


def _board_texture_question(
    board: list[tuple[str, str]],
    d: dict,
) -> dict:
    texture        = _board_texture(board[:3])  # Always classify 3-card flop
    correct_label  = TEXTURE_LABELS[texture]

    options = list(TEXTURE_LABELS.values())
    correct_index  = options.index(correct_label)
    random.shuffle(options)
    correct_index  = options.index(correct_label)

    texture_exp = {
        'dry': (
            'Board seco: poucos draws presentes. O aggressor tem mais vantagem de range — '
            'c-bets pequenas (~25-33% pot) com alta frequência são a norma.'
        ),
        'semi_wet': (
            'Board semi-úmido: um draw presente (flush OU straight). '
            'C-bets de tamanho médio (~50-66% pot), selecionando mãos que se beneficiam de fold equity.'
        ),
        'wet': (
            'Board úmido/coordenado: múltiplos draws e outs para o oponente. '
            'Hands fortes apostam grande (75-100% pot) para negar equity. Bluffs são menos frequentes.'
        ),
    }

    board_str = ' '.join(f'{r}{s}' for r, s in board[:3])

    return {
        'type': 'board_texture',
        'question': f'Board: **{board_str}**\nComo você classificaria a textura deste flop?',
        'hero_cards':  [],
        'board_cards': [{'rank': r, 'suit': s} for r, s in board[:3]],
        'options': options,
        'correct_index': correct_index,
        'explanation': texture_exp[texture],
        'mental_tip': (
            "**Atalho:** conte naipes e gaps. "
            "2+ cartas do mesmo naipe = flush draw presente. "
            "2+ cartas com rank consecutivo (gap ≤1, ex: 7-8 ou 9-J) = straight draw presente. "
            "Ambos = úmido; um só = semi-úmido; nenhum = seco."
        ),
        'context': {'street': 'flop', 'position': d.get('position')},
        'xp_value': 20,
    }


# ── Board sintético: dealer + detecção de draws ─────────────────────────────────

_DECK_RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
_DECK_SUITS = ['s', 'h', 'd', 'c']


def _deal_spot(board_size: int) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Sorteia hero(2) + board(board_size) cartas distintas de um baralho embaralhado."""
    deck = [(r, s) for r in _DECK_RANKS for s in _DECK_SUITS]
    random.shuffle(deck)
    return deck[:2], deck[2:2 + board_size]


def _has_flush_draw(hero, board) -> bool:
    hsv = [c[1] for c in hero]
    allsv = hsv + [c[1] for c in board]
    return any(allsv.count(s) == 4 and hsv.count(s) >= 1 for s in _DECK_SUITS)


def _has_straight_draw(hero, board) -> bool:
    """4-para-straight (janela de 4 ranks distintos com span <= 4), hero participando."""
    h_rv = [RANK_VALUES[c[0]] for c in hero]
    all_rv = h_rv + [RANK_VALUES[c[0]] for c in board]
    ext = sorted(set(all_rv + ([1] if 14 in all_rv else [])))
    for i in range(len(ext) - 3):
        w = ext[i:i + 4]
        if w[3] - w[0] <= 4 and len(set(w)) == 4:
            if any((hr == 14 and 1 in w) or hr in w for hr in h_rv):
                return True
    return False


def _shuffled_options(labels: dict, order: list, correct_key: str):
    pool = order[:]
    random.shuffle(pool)
    return [labels[k] for k in pool], pool.index(correct_key)


def _made_vs_draw_question(hero, board) -> dict:
    bucket = _hand_bucket(hero, board)
    cat = 'feita' if bucket >= 2 else ('draw' if bucket == 1 else 'air')
    labels = {
        'feita': 'Mão feita (par ou melhor)',
        'draw':  'Draw (projeto, sem par)',
        'air':   'Nada (air)',
    }
    options, correct_index = _shuffled_options(labels, ['feita', 'draw', 'air'], cat)
    expl = {
        'feita': 'Você já tem par ou melhor — mão feita com showdown value.',
        'draw':  'Sem par, mas com projeto (flush e/ou straight): equity que depende de melhorar.',
        'air':   'Sem par e sem projeto relevante — air.',
    }
    hero_str  = ' '.join(f'{r}{s}' for r, s in hero)
    board_str = ' '.join(f'{r}{s}' for r, s in board)
    return {
        'type': 'made_vs_draw',
        'question': f'Board: **{board_str}**\nSuas cartas: **{hero_str}**\nVocê tem mão feita, draw ou nada?',
        'hero_cards':  [{'rank': r, 'suit': s} for r, s in hero],
        'board_cards': [{'rank': r, 'suit': s} for r, s in board],
        'options': options,
        'correct_index': correct_index,
        'explanation': expl[cat],
        'mental_tip': '**Atalho:** par com o board ou bolso = mão feita; sem par mas 4 do mesmo naipe / 4 em sequência = draw; nenhum = nada.',
        'xp_value': 20,
    }


def _identify_draw_question(hero, board) -> dict:
    fd = _has_flush_draw(hero, board)
    sd = _has_straight_draw(hero, board)
    cat = 'combo' if (fd and sd) else ('flush' if fd else ('straight' if sd else 'none'))
    labels = {
        'flush':    'Flush draw',
        'straight': 'Straight draw (sequência)',
        'combo':    'Combo (flush + straight)',
        'none':     'Sem draw',
    }
    options, correct_index = _shuffled_options(labels, ['flush', 'straight', 'combo', 'none'], cat)
    expl = {
        'flush':    '4 cartas do mesmo naipe com você participando = flush draw (~9 outs).',
        'straight': '4 cartas em sequência = straight draw (8 outs se open-ended, 4 se gutshot).',
        'combo':    'Flush draw + straight draw ao mesmo tempo — projeto enorme (até ~15 outs).',
        'none':     'Sem projeto relevante.',
    }
    hero_str  = ' '.join(f'{r}{s}' for r, s in hero)
    board_str = ' '.join(f'{r}{s}' for r, s in board)
    return {
        'type': 'identify_draw',
        'question': f'Board: **{board_str}**\nSuas cartas: **{hero_str}**\nQue projeto (draw) esta mão tem?',
        'hero_cards':  [{'rank': r, 'suit': s} for r, s in hero],
        'board_cards': [{'rank': r, 'suit': s} for r, s in board],
        'options': options,
        'correct_index': correct_index,
        'explanation': expl[cat],
        'mental_tip': '**Atalho:** conte naipes (4 iguais = flush draw) e ranks (4 em sequência, gap ≤1 = straight draw). Os dois juntos = combo.',
        'xp_value': 20,
    }


def _synthetic_board_question() -> dict:
    """Fallback with hand-crafted teaching example."""
    scenarios = [
        {
            'hero': [('A', 's'), ('K', 'h')],
            'board': [('A', 'd'), ('7', 's'), ('2', 'c')],
            'bucket': 3,
            'texture': 'dry',
        },
        {
            'hero': [('J', 'h'), ('T', 'h')],
            'board': [('9', 'h'), ('8', 'd'), ('K', 'h')],
            'bucket': 1,
            'texture': 'wet',
        },
        {
            'hero': [('6', 's'), ('6', 'd')],
            'board': [('6', 'h'), ('A', 'c'), ('3', 's')],
            'bucket': 4,
            'texture': 'dry',
        },
        {
            'hero': [('Q', 'c'), ('J', 'd')],
            'board': [('T', 's'), ('9', 'h'), ('2', 'c')],
            'bucket': 1,
            'texture': 'semi_wet',
        },
    ]
    s = random.choice(scenarios)
    hero, board, bucket = s['hero'], s['board'], s['bucket']

    all_buckets = [0, 1, 2, 3, 4]
    other = [b for b in all_buckets if b != bucket]
    random.shuffle(other)
    pool = [bucket] + other[:3]
    random.shuffle(pool)
    correct_index = pool.index(bucket)

    return {
        'type': 'hand_classify',
        'question': 'Board: **{}**\nSuas cartas: **{}**\nComo você classificaria esta mão?'.format(
            ' '.join(f'{r}{su}' for r, su in board),
            ' '.join(f'{r}{su}' for r, su in hero),
        ),
        'hero_cards':  [{'rank': r, 'suit': su} for r, su in hero],
        'board_cards': [{'rank': r, 'suit': su} for r, su in board],
        'options': [BUCKET_LABELS_SHORT[b] for b in pool],
        'correct_index': correct_index,
        'explanation': 'Este é um exemplo de referência para treinar a classificação básica de força de mão.',
        'mental_tip': (
            "**Atalho:** verifique em ordem: (1) suas cartas formam par com o board? → par médio/forte; "
            "(2) seu bolso bate as cartas do board? → overpair/set; "
            "(3) 4 do mesmo naipe = flush draw; 4 cartas em sequência (gap ≤1) = straight draw. "
            "Sem nada → air."
        ),
        'context': {},
        'xp_value': 20,
    }


# ── Beginner: Outs Count ────────────────────────────────────────────────────────

# Each entry: (outs, draw_name, question_variants, explanation, mental_tip, distractors)
_OUTS_SCENARIOS = [
    (9, 'flush draw',
     ['Você tem um **flush draw** (4 cartas do mesmo naipe). Quantos outs para completar o flush?',
      'No flop, você flopped um **flush draw** com 4 cartas do mesmo naipe. Quantos outs você tem?',
      'Villain aposta. Você tem um **flush draw** — 4 cartas do mesmo naipe no board + mão. Quantos outs?'],
     '**9 outs**: há 13 cartas de cada naipe no deck. Você vê 4 delas, restam **9** que completam o flush.',
     'Flush draw = **sempre 9 outs**. Memorize: 13 − 4 = 9.',
     [6, 12]),
    (8, 'OESD',
     ['Você tem um **OESD** — sequência aberta pelos dois lados (ex: 7-8-9-T, precisa do 6 ou do J). Quantos outs?',
      'Board de flop com um **OESD** nos seus hole cards (ex: 8-9-T-J, open-ended). Quantos outs para a sequência?',
      'Você tem uma sequência aberta pelos dois lados (**OESD**). Quantos outs você tem para completar?'],
     '**8 outs**: 4 cartas completam pela parte inferior + 4 pela superior da sequência = 8 total.',
     'OESD = **8 outs**. Dois "lados" × 4 naipes = 8.',
     [6, 9]),
    (4, 'gutshot',
     ['Você tem um **gutshot** (sequência com gap no meio, ex: 7-8-T-J precisando do 9). Quantos outs?',
      'Você tem uma sequência com apenas uma rank que a fecha — um **gutshot**. Quantos outs?',
      'No turn você tem um **gutshot**: só um rank específico completa a sua sequência. Quantos outs restam?'],
     '**4 outs**: só uma rank específica fecha, em 4 naipes diferentes.',
     'Gutshot = **4 outs**. Metade de um OESD. Sozinho raramente justifica calls grandes.',
     [6, 8]),
    (12, 'flush draw + gutshot',
     ['Você tem **flush draw + gutshot** ao mesmo tempo. Qual o total aproximado de outs?',
      'Combo draw: **flush draw** (4 ao flush) e **gutshot** simultaneamente. Quantos outs aproximados?',
      'Você flopped **flush draw + gutshot** combinados. Estimando outs (descontando overlap), quantos você tem?'],
     '**~12 outs**: 9 de flush + 4 de gutshot − 1 overlap (carta que completaria ambos conta só uma vez) ≈ 12.',
     'Draws combinados: **some e subtraia ~1 de overlap**. Flush + gutshot ≈ 12.',
     [9, 15]),
    (15, 'flush draw + OESD',
     ['Você tem o combo máximo: **flush draw + OESD**. Quantos outs aproximados?',
      'Monster draw: **flush draw** + **OESD** no flop. Qual o total aproximado de outs?',
      'Você flopped **flush draw e OESD** ao mesmo tempo. Quantos outs você tem (descontando overlap)?'],
     '**~15 outs**: 9 de flush + 8 de OESD − 2 overlaps ≈ 15. Com ~15 outs você está quase no flip.',
     'Flush + OESD ≈ **15 outs**. 15 × 4 = ~60% equity no flop — quase favorito!',
     [12, 9]),
    (6, 'duas overcards',
     ['Você não tem par, mas suas duas cartas são maiores que o board inteiro (**duas overcards**). Quantos outs?',
      'Você tem **duas overcards** — ambas as suas cartas superam todas as cartas do board. Quantos outs para virar par?',
      'Sem par no flop, mas com **duas overcards**. Quantos outs você tem para pegar par?'],
     '**6 outs**: cada overcard tem 3 outs (4 no deck − 1 já visível no board) × 2 cartas = 6.',
     'Duas overcards = **6 outs**. Bom como equity adicional combinada com draws.',
     [4, 9]),
    (15, 'flush draw + duas overcards',
     ['Você tem **flush draw + duas overcards** (sem par feito). Quantos outs aproximados?',
      'Combo: **flush draw** com as duas cartas na mão também sendo overcards. Quantos outs?',
      'Você tem um **flush draw** e suas duas cartas são overcards do board. Quantos outs no total?'],
     '**~15 outs**: 9 de flush + 6 de overcards = 15. Com ~60% equity no flop, você frequentemente é favorito.',
     '15 outs × 4 = **~60%** — isso é flip ou melhor contra muitas mãos feitas!',
     [12, 9]),
    (2, 'backdoor flush draw',
     ['Você tem um **backdoor flush draw** (precisa de 2 cartas do mesmo naipe em turn + river). Quantos outs práticos tem?',
      'Você tem apenas um **backdoor flush draw** — precisa que tanto o turn quanto o river sejam do mesmo naipe. Quantos outs?',
      'Sua mão tem **backdoor flush draw** mas nenhum draw direto. Quantos outs isso representa?'],
     '**~2 outs equivalentes**: a probabilidade (~4%) equivale a ter ~2 outs "reais". Não é draw para depender sozinho.',
     'Backdoor draw = **~2 outs equivalentes** ou ~4%. Nunca chame bets grandes só por isso — use como equity adicional.',
     [4, 6]),
    (5, 'três overcards (flop A-alto)',
     ['Em um flop com um Ás, você não tem par mas tem **três overcards** ao restante do board. Quantos outs para par?',
      'Board tem um Ás. Você não pareou, mas suas cartas fazem **três overcards** ao segundo e terceiro card. Quantos outs?'],
     '**~5 outs**: ~3 do overcard mais alto + ~2 do segundo overcard (já descontando o Ás do board). Estimativa aproximada.',
     'Três overcards em board com Ás = **~5 outs** para pegar par. Não é muita equity — combine com outro draw.',
     [4, 6]),
]


_OUTS_CONTEXT_PREFIXES = [
    '',
    'Você está **IP** e villain fez c-bet. ',
    'Você está **OOP**, villain aposta após seu check. ',
    'Multiway pot (3 jogadores). ',
    'Blind vs blind, hero está OOP. ',
    'Você está no **BTN** contra o BB. ',
    f'Stack curto (~{random.choice([18, 22, 25, 30])} BB efetivos). ',  # evaluated once at import — intentional snapshot
    'Heads-up no turn após call no flop. ',
]


def _outs_count_question() -> dict:
    """Quantos outs você tem com este tipo de draw?"""
    outs, draw_name, questions, explanation, mental_tip, distractors = random.choice(_OUTS_SCENARIOS)
    question_text = random.choice(questions)
    prefix = random.choice(_OUTS_CONTEXT_PREFIXES)
    pool = [outs] + [d for d in distractors if d != outs][:2]
    random.shuffle(pool)
    return {
        'type': 'outs_count',
        'concept': '**Outs** são as cartas que ainda podem vir e que transformam a sua mão na melhor. Contá-las é a base de toda estimativa de equity.',
        'question': f'{prefix}{question_text}' if prefix else question_text,
        'options': [f'{o} outs' for o in pool],
        'correct_index': pool.index(outs),
        'explanation': explanation,
        'mental_tip': mental_tip,
        'context': {},
        'xp_value': 15,
    }


# ── Intermediate: Equity Estimate (Regra 2/4) ───────────────────────────────────

def _equity_estimate_question() -> dict:
    """Dado X outs, calcule equity aproximada usando regra 2/4."""
    draws = [
        {'name': 'flush draw', 'outs': 9},
        {'name': 'OESD', 'outs': 8},
        {'name': 'gutshot', 'outs': 4},
        {'name': 'flush draw + gutshot', 'outs': 12},
        {'name': 'flush draw + OESD', 'outs': 15},
        {'name': 'duas overcards', 'outs': 6},
        {'name': 'flush draw + duas overcards', 'outs': 15},
        {'name': 'OESD + duas overcards', 'outs': 14},
        {'name': 'set (três outs para quads ou full house)', 'outs': 7},
        {'name': 'duas overcards + gutshot', 'outs': 10},
        {'name': 'backdoor flush draw', 'outs': 2},
    ]
    draw = random.choice(draws)
    streets = random.choice(['turn', 'flop'])
    multiplier = 2 if streets == 'turn' else 4
    streets_label = 'turn (1 street restante)' if streets == 'turn' else 'flop (2 streets restantes)'
    correct = draw['outs'] * multiplier

    distractor1 = draw['outs'] * (4 if multiplier == 2 else 2)  # multiplicador errado
    distractor2 = max(4, correct + random.choice([-6, 8, -8, 6]))
    options = _make_options(correct, [distractor1, distractor2])

    # Scenario context adds variety without changing the math
    stack_bb = random.choice([15, 18, 22, 25, 28, 32, 38, 45, 55])
    position = random.choice(['IP', 'OOP', 'BTN', 'CO', 'BB', 'SB'])
    scenario_prefixes = [
        f'Stack efetivo: **{stack_bb} BB**. ',
        f'Você está **{position}** no {streets_label.split()[0]}. ',
        f'Pote formado por c-bet no {streets_label.split()[0]}. ',
        f'Villain apostou após check do herói no {streets_label.split()[0]}. ',
        f'Situação de **{position}** com {stack_bb} BB efetivos. ',
        '',  # sem contexto extra
    ]
    prefix = random.choice(scenario_prefixes)

    return {
        'type': 'equity_estimate',
        'concept': '**Equity** é a sua fatia do pote: a % de vezes que a sua mão venceria se fosse até o river. A Regra 2/4 a estima a partir dos outs.',
        'question': (
            f'{prefix}Você está no **{streets_label}** com um **{draw["name"]}** ({draw["outs"]} outs).\n'
            f'Usando a Regra 2/4, qual sua equity **aproximada**?'
        ),
        'options': [f'~{v}%' for v in options['values']],
        'correct_index': options['correct_index'],
        'explanation': (
            f'Regra 2/4: {draw["outs"]} outs × **{multiplier}** = **~{correct}%** de equity.\n\n'
            f'Com {1 if multiplier == 2 else 2} street{"" if multiplier == 2 else "s"} restante{"" if multiplier == 2 else "s"}, '
            f'use o multiplicador **{multiplier}**. Este é um atalho mental — o valor real pode variar ±2pp.'
        ),
        'mental_tip': (
            '**Regra 2/4:** outs × 2 no **turn** | outs × 4 no **flop**. '
            'Ajuste para > 8 outs no flop: subtraia 1 (ex: 9 outs × 4 − 1 = **35%** em vez de 36%). '
            'Referências decoradas: flush draw (9) → 35% flop / 18% turn | '
            'OESD (8) → 32% / 16% | gutshot (4) → 16% / 8% | flush+OESD (15) → ~60% flop.'
        ),
        'context': {},
        'xp_value': 20,
    }


# ── Intermediate: Odds vs Equity ────────────────────────────────────────────────

def _odds_vs_equity_question(pot: float, bet: float, d: dict) -> dict:
    """Combine outs + pot odds: call ou fold?"""
    draws = [
        {'name': 'flush draw', 'outs': 9},
        {'name': 'OESD', 'outs': 8},
        {'name': 'gutshot', 'outs': 4},
        {'name': 'duas overcards', 'outs': 6},
        {'name': 'flush draw + gutshot', 'outs': 12},
        {'name': 'flush draw + OESD', 'outs': 15},
        {'name': 'OESD + duas overcards', 'outs': 14},
        {'name': 'duas overcards + gutshot', 'outs': 10},
    ]
    draw = random.choice(draws)
    # Rule of 2/4 only applies on flop (2 cards to come) or turn (1 card to come).
    # Preflop and river are invalid for this question type.
    street = d.get('street') if d.get('street') in _STREETS_WITH_DRAWS else random.choice(_STREETS_WITH_DRAWS)
    multiplier = 4 if street == 'flop' else 2
    draw_equity = draw['outs'] * multiplier
    pot_odds_pct = round(bet / (pot + bet) * 100)
    correct_action = 'call' if draw_equity > pot_odds_pct else 'fold'

    diff = draw_equity - pot_odds_pct
    sign = '+' if diff >= 0 else ''

    return {
        'type': 'odds_vs_equity',
        'concept': 'Esta é a decisão completa: estime a sua **equity** pelos outs (Regra 2/4) e compare com as **pot odds** do tamanho da aposta.',
        'question': (
            f'No **{street}**: pot = **{pot} BB**, villain aposta **{bet} BB**.\n'
            f'Você tem um **{draw["name"]}** ({draw["outs"]} outs).\n'
            f'Usando regra ×{"4" if multiplier == 4 else "2"}, o call é correto?'
        ),
        'options': ['Call', 'Fold'],
        'correct_index': 0 if correct_action == 'call' else 1,
        'explanation': (
            f'{draw["outs"]} outs × {multiplier} = **{draw_equity}%** de equity estimada.\n\n'
            f'Pot odds mínimas: {bet} ÷ {pot + bet:.1f} = **{pot_odds_pct}%**.\n\n'
            f'{draw_equity}% {">  →" if draw_equity > pot_odds_pct else "< →"} **{correct_action.upper()}** '
            f'(margem: {sign}{diff} pp).'
        ),
        'mental_tip': (
            '**Processo:** (1) conte os outs, (2) multiplique por 2 ou 4, '
            '(3) compare com pot odds (call ÷ total_pot). '
            'Equity > pot odds → call. Não precisa de calculadora.'
        ),
        'context': {'street': street, 'position': d.get('position')},
        'xp_value': 20,
    }


# ── Advanced: SPR Commitment — parametric ──────────────────────────────────────

# (hand_label, commitment_threshold_spr, explanation_template)
# Committed when SPR < threshold
_SPR_HANDS = [
    ('set, straight ou flush', 99.0,
     'Sets e mãos feitas muito fortes ficam **committed em qualquer SPR**. Você tem equity alta demais para abandonar.',
     'Sets e melhor ficam committed em **qualquer SPR**.'),
    ('dois pares fortes', 6.5,
     'Com SPR < 6.5 e dois pares fortes você está **committed** — equity sólida mesmo em boards coordenados.',
     'Dois pares fortes → committed com SPR < ~6.'),
    ('overpair forte (AA/KK)', 5.5,
     'AA/KK no flop com SPR < 5.5: você está **committed**. Fold equity de villain é alto demais para ceder o pot.',
     'Overpairs fortes (AA/KK) → committed com SPR < ~5.5.'),
    ('overpair médio (QQ-TT)', 4.2,
     'Overpairs médios ficam committed com SPR < ~4.2 — equity ainda domina ranges amplamente.',
     'Overpairs médios → committed com SPR < ~4.'),
    ('top pair top kicker', 3.0,
     'TPTK com SPR < 3: você está **committed**. O pot é muito grande para dobrar — a equity justifica.',
     'TPTK → committed com SPR < ~3.'),
    ('top pair kicker médio', 2.0,
     'Top pair kicker médio com SPR < 2: **committed**. Mas com SPR maior, considere pot control.',
     'Top pair kicker médio → committed com SPR < ~2.'),
    ('top pair kicker fraco', 1.5,
     'Top pair kicker fraco com SPR < 1.5: ainda **committed** pelo tamanho do pot. SPR maior → pot control obrigatório.',
     'Top pair kicker fraco → committed apenas com SPR < ~1.5.'),
    ('segunda par (second pair)', 1.0,
     'Segunda par com SPR < 1: o pot já é tão grande que **committed** por pot odds implícitas.',
     'Segunda par → committed apenas com SPR < ~1. Com mais stack, controle o pot.'),
    ('bottom pair', 0.6,
     'Bottom pair exige SPR muito baixo (< 0.6) para estar committed. Acima disso, **controle o pot** estritamente.',
     'Bottom pair = quase nunca committed. Apenas com micro-stack.'),
    ('flush draw (sem par)', 0.0,
     'Draws sem par **nunca estão committed por SPR** — você depende de melhorar para ter valor. Avalie apenas por pot odds.',
     'Draws sem par = nunca committed por SPR. Avalie só por pot odds.'),
    ('gutshot (sem par feito)', 0.0,
     'Gutshot sem par tem equity insuficiente para commitment em qualquer SPR. Avalie exclusivamente por pot odds.',
     'Draws (gutshot sem par) = nunca committed. Chame apenas quando pot odds justificam.'),
]

# SPR values to sample from — realistic poker distribution
_SPR_VALUES = [0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 2.8,
               3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0]


def _spr_commitment_question() -> dict:
    """Parametric SPR commitment — infinite variety from threshold table."""
    spr = random.choice(_SPR_VALUES)

    # Find hands clearly committed (threshold > spr + 0.4) and clearly not (threshold < spr - 0.4)
    committed_pool = [(h, t, exp, tip) for h, t, exp, tip in _SPR_HANDS if t > spr + 0.4]
    not_committed_pool = [(h, t, exp, tip) for h, t, exp, tip in _SPR_HANDS if t < spr - 0.4]

    # Ensure we have both options; fall back to boundary if one pool is empty
    if not committed_pool:
        committed_pool = [(h, t, exp, tip) for h, t, exp, tip in _SPR_HANDS if t > spr]
    if not not_committed_pool:
        not_committed_pool = [(h, t, exp, tip) for h, t, exp, tip in _SPR_HANDS if t < spr]

    is_committed = random.random() < 0.5
    if is_committed and committed_pool:
        hand, threshold, exp_template, tip = random.choice(committed_pool)
    elif not_committed_pool:
        hand, threshold, exp_template, tip = random.choice(not_committed_pool)
        is_committed = False
    else:
        hand, threshold, exp_template, tip = random.choice(_SPR_HANDS)
        is_committed = threshold > spr

    options = ['Sim — jogo por todo o stack', 'Não — controlo o pot']
    return {
        'type': 'spr_commitment',
        'question': (
            f'No flop. SPR = **{spr}**. Sua mão: **{hand}**.\n'
            f'Você está committed para stackar aqui?'
        ),
        'options': options,
        'correct_index': 0 if is_committed else 1,
        'explanation': exp_template,
        'mental_tip': (
            '**Guia SPR rápido:** '
            'SPR < 1 → committed c/ qualquer par. '
            'SPR 1–3 → top pair+ committed. '
            'SPR 3–5 → overpair / TPTK. '
            'SPR > 5 → set e melhor. '
            'Draws sem par: **nunca committed por SPR**.'
        ),
        'context': {},
        'xp_value': 25,
    }


# ── Advanced: ICM Spot ──────────────────────────────────────────────────────────

_ICM_CONTEXTS = [
    {
        'ctx': 'bolha do torneio — você é stack médio, villain é chip leader',
        'correct': 'fold',
        'edge_range': (3, 6),
        'pot_odds_range': (29, 36),
        'exp_template': (
            'Na bolha com stack médio, **perder = eliminação sem prêmio**. '
            'Edge de apenas +{edge}pp não compensa o risco de 0 em equity de torneio. '
            'ICM dita fold mesmo sendo +EV em chips.'
        ),
    },
    {
        'ctx': 'bolha — você tem micro-stack (M-ratio < 4), já quase eliminado',
        'correct': 'call',
        'edge_range': (5, 10),
        'pot_odds_range': (33, 42),
        'exp_template': (
            'Com micro-stack na bolha, a diferença entre call e fold é pequena em equity de torneio. '
            'Com +{edge}pp de edge você **chama** — de qualquer forma está quase eliminado.'
        ),
    },
    {
        'ctx': 'mesa final — você é big stack, villain é short stack',
        'correct': 'call',
        'edge_range': (6, 12),
        'pot_odds_range': (24, 34),
        'exp_template': (
            'Como big stack na final, **eliminar short stacks aumenta seu equity de torneio**. '
            'Edge de +{edge}pp contra um stack que não te ameaça → call correto.'
        ),
    },
    {
        'ctx': 'bolha — você é chip leader, villain é segundo colocado',
        'correct': 'fold',
        'edge_range': (3, 7),
        'pot_odds_range': (30, 38),
        'exp_template': (
            'Como chip leader na bolha, seu equity de torneio é **máximo** — qualquer confronto de alto risco é desnecessário. '
            'Fold preserva posição dominante com edge de apenas +{edge}pp.'
        ),
    },
    {
        'ctx': 'final table com 3 jogadores — pay jump enorme para 2º lugar',
        'correct': 'fold',
        'edge_range': (2, 6),
        'pot_odds_range': (28, 36),
        'exp_template': (
            'Com pay jump enorme para 2º, o custo de eliminação é desproporcional. '
            'Mesmo com edge de +{edge}pp, **ICM justifica fold** para garantir o prêmio.'
        ),
    },
    {
        'ctx': 'bolha — stack médio enfrenta reshove do pequeno stack isolado',
        'correct': 'call',
        'edge_range': (8, 14),
        'pot_odds_range': (35, 44),
        'exp_template': (
            'Reshove de pequeno stack isolado não ameaça sua sobrevivência de forma crítica. '
            'Com +{edge}pp de edge contra um range amplo de push, **chip EV prevalece** aqui.'
        ),
    },
    {
        'ctx': 'torneio — ITM recente, você é médio stack, villain é big stack agressivo',
        'correct': 'fold',
        'edge_range': (3, 5),
        'pot_odds_range': (31, 37),
        'exp_template': (
            'Recém no dinheiro com stack médio contra um big stack, seu equity de torneio cresce ao sobreviver. '
            'Edge marginal de +{edge}pp não justifica exposição total contra o chip leader.'
        ),
    },
    {
        'ctx': 'mesa final — você é short stack crítico (M < 3), qualquer um pode te eliminar',
        'correct': 'call',
        'edge_range': (4, 9),
        'pot_odds_range': (36, 46),
        'exp_template': (
            'Com M < 3, seu equity de torneio já é mínimo independente de fold. '
            'Com +{edge}pp de edge, **chame e tente dobrar** — esperar só piora sua situação.'
        ),
    },
]


def _icm_spot_question() -> dict:
    """ICM pressure: pot odds normais ainda se aplicam?"""
    ctx = random.choice(_ICM_CONTEXTS)
    pot_odds = random.randint(*ctx['pot_odds_range'])
    edge = random.randint(*ctx['edge_range'])
    equity = pot_odds + edge
    exp = ctx['exp_template'].format(edge=edge)
    options = ['Call (pot odds justificam)', 'Fold (ICM neutraliza o edge)']
    correct_index = 0 if ctx['correct'] == 'call' else 1
    return {
        'type': 'icm_spot',
        'question': (
            f'**{ctx["ctx"]}**.\n'
            f'Pot odds exigem **{pot_odds}%**. Sua equity estimada: **{equity}%**.\n'
            f'Considerando ICM, qual a linha correta?'
        ),
        'options': options,
        'correct_index': correct_index,
        'explanation': exp,
        'mental_tip': (
            '**Regra ICM prática:** edge pequeno (+3 a +5pp) na bolha com stack médio/grande → fold. '
            'Micro-stack ou big stack eliminando curtos → chip EV prevalece. '
            'Pay jump enorme próximo → seja mais conservador do que pot odds sugerem.'
        ),
        'context': {},
        'xp_value': 25,
    }


# ── Advanced: Bubble over-defense (o MDF morre sob ICM) ─────────────────────────

def _bubble_defense_question() -> dict:
    """Defesa na bolha: perto do prêmio você defende o BB MENOS, não mais, porque
    perder pode significar eliminação. Conceito contra-intuitivo e de alto valor pra
    iniciante (o instinto é 'não deixar roubar')."""
    opener   = random.choice(['BTN', 'CO', 'SB'])
    wide_pct = random.randint(55, 68)   # defesa larga que a conta em fichas pediria
    return {
        'type': 'bubble_defense',
        'question': (
            f'**Bolha do torneio.** Você está no **BB** com stack médio e o **{opener}** '
            f'abre um min-raise tentando roubar. Contando só fichas, valeria a pena defender '
            f'bem largo (uns **{wide_pct}%** das mãos). Considerando o ICM, o que você faz?'
        ),
        'options': [
            'Defendo MENOS: perder aqui pode me eliminar',
            'Defendo IGUAL: a conta não muda na bolha',
            'Defendo MAIS: não posso deixar ele roubar',
        ],
        'correct_index': 0,
        'explanation': (
            'Defender largo só compensa quando perder o pote custa **apenas fichas**. Na bolha, '
            'perder pode significar sair sem prêmio, então o custo de defender e errar dispara. '
            'Resultado: você defende **menos** que o normal, não mais. Contra o mesmo min-raise, '
            'a frequência de fold do BB, que giraria em torno de ~20% contando fichas, sobe para '
            'perto de ~35% perto do prêmio. Insistir em defender largo na bolha é um dos '
            'vazamentos mais caros do torneio.'
        ),
        'mental_tip': (
            '**Ideia-chave:** perto do prêmio, sobreviver vale mais do que ter razão. Você folda '
            'mais, até contra alguém que rouba muito, porque ser eliminado dói mais do que ganhar '
            'o potinho ajuda. Quanto maior o salto de prêmio à frente, mais você aperta. Única '
            'exceção: micro-stack já comprometido, aí voltar a caçar fichas faz sentido.'
        ),
        'context': {},
        'xp_value': 25,
    }


# ── Advanced: 3-Bet Pot Equity ──────────────────────────────────────────────────

_3BET_OPEN_SIZES  = [2.0, 2.2, 2.5, 2.5, 2.5, 2.8, 3.0, 3.0, 3.5]   # weighted toward 2.5/3.0
_3BET_MULTIPLIERS = [3.0, 3.2, 3.3, 3.5, 3.5, 3.7, 4.0, 4.0, 4.2, 4.5]


def _3bet_pot_question() -> dict:
    """Em um pote de 3-bet, qual equity mínima para flat call? Parametric."""
    open_bb = random.choice(_3BET_OPEN_SIZES)
    mult    = random.choice(_3BET_MULTIPLIERS)
    # round 3-bet to nearest 0.5 BB for realism
    threbet_bb  = round(open_bb * mult * 2) / 2
    call_amount = round((threbet_bb - open_bb) * 10) / 10
    # pot = SB(0.5) + BB(1) + hero_open + villain_threbet + hero_call
    # = 1.5 + open + threbet + call = 1.5 + open + threbet + (threbet - open) = 1.5 + 2*threbet
    pot_after   = round((1.5 + 2 * threbet_bb) * 10) / 10
    correct_pct = round(call_amount / pot_after * 100)

    # distractors: one using call/threbet (common mistake), one offset
    distractor1 = round(call_amount / threbet_bb * 100)
    offset = random.choice([-9, -7, 8, 10])
    distractor2 = max(20, min(55, correct_pct + offset))
    options = _make_options(correct_pct, [distractor1, distractor2])

    open_fmt    = f'{open_bb:.1f}'.rstrip('0').rstrip('.')
    threbet_fmt = f'{threbet_bb:.1f}'.rstrip('0').rstrip('.')
    call_fmt    = f'{call_amount:.1f}'.rstrip('0').rstrip('.')
    pot_fmt     = f'{pot_after:.1f}'.rstrip('0').rstrip('.')

    return {
        'type': '3bet_pot',
        'question': (
            f'Você abre **{open_fmt} BB**, villain 3-bet para **{threbet_fmt} BB**.\n'
            f'Qual a equity mínima necessária para o **flat call** ser matematicamente válido?'
        ),
        'options': [f'{v}%' for v in options['values']],
        'correct_index': options['correct_index'],
        'explanation': (
            f'Você chama **{call_fmt} BB**. Pot total após o call: ~**{pot_fmt} BB**.\n\n'
            f'Fórmula: {call_fmt} ÷ {pot_fmt} ≈ **{correct_pct}%** mínimo.'
        ),
        'mental_tip': (
            '**3-bet pots:** você geralmente precisa de **~30–35% de equity** para flat callar. '
            'Aplique a fórmula: call ÷ total_pot_após_call. '
            'Combos abaixo de ~30% vs a range de 3-bet → fold ou 4-bet (não flat). '
            'Combinatória útil: par específico (ex: AA) = **6 combos** | mão não-pareada (ex: AK) = **16 combos** '
            '(AKs=4, AKo=12). Use isso para estimar a range do oponente rapidamente.'
        ),
        'context': {},
        'xp_value': 25,
    }


# ── Tournament module dispatcher ────────────────────────────────────────────────

def generate_tournament_question(user_id: int) -> dict:
    """
    Advanced tournament context questions:
      spr_commitment, icm_spot, bubble_defense, 3bet_pot
    """
    qtype = random.choices(
        ['spr_commitment', 'icm_spot', 'bubble_defense', '3bet_pot'],
        weights=[0.30, 0.25, 0.20, 0.25],
    )[0]
    if qtype == 'spr_commitment':
        return _spr_commitment_question()
    if qtype == 'icm_spot':
        return _icm_spot_question()
    if qtype == 'bubble_defense':
        return _bubble_defense_question()
    return _3bet_pot_question()


# ── Multiway: treino da aula "Pote com 3+ jogadores" ─────────────────────────────
# Reforça os 3 conceitos da aula: blefe puro despenca, aposte menor, o assento do meio.
# PT-only (padrão dos geradores); rótulos de tipo vão pro i18n (qtypes).

_MW_BLUFF_HANDS = [
    'uma mão fraca sem projeto (tipo J-alto)',
    'carta alta solta, sem par nem projeto',
    'um K-7 offsuit que não conectou nada',
    'uma mão que errou o board, sem projeto de melhora',
]
_MW_VALUE_HANDS = [
    'um par bom, mas longe dos nuts',
    'top par com kicker médio',
    'dois pares num board molhado (não é a nut)',
]
_MW_OPENERS = ['o UTG', 'o jogador de posição inicial', 'quem abriu na frente']


def _mw_bluff_question() -> dict:
    n = random.choice([2, 3, 4])
    hand = random.choice(_MW_BLUFF_HANDS)
    return {
        'type': 'mw_bluff',
        'question': (
            f'Pote multiway com **{n} adversários**. Você tem {hand} e a ação está com você. '
            f'Qual a jogada?'
        ),
        'options': ['Blefar grande', 'Blefar pequeno', 'Desistir (check ou fold)'],
        'correct_index': 2,
        'explanation': (
            f'Para o blefe lucrar, os {n} adversários teriam de foldar ao mesmo tempo, e a '
            f'chance de pelo menos um pagar cresce rápido com mais gente. Sem projeto, desista barato.'
        ),
        'mental_tip': '**Multiway:** quanto mais gente, menos você blefa. Blefe puro 3+ way é ~zero.',
        'context': {}, 'xp_value': 20,
    }


def _mw_sizing_question() -> dict:
    n = random.choice([3, 4])
    hand = random.choice(_MW_VALUE_HANDS)
    return {
        'type': 'mw_sizing',
        'question': (
            f'Pote com **{n} jogadores**. Você tem {hand} e quer apostar por valor. '
            f'Comparado a um pote heads-up, o tamanho ideal é:'
        ),
        'options': ['Maior', 'Igual ao heads-up', 'Menor'],
        'correct_index': 2,
        'explanation': (
            'O pote já está maior e há mais gente para pagar, então uma aposta menor extrai '
            'valor e cobra os projetos sem te expor. Overbet sem os nuts só é pago quando você está atrás.'
        ),
        'mental_tip': '**Sem os nuts, aposte menor no multiway.** Grande demais só te paga quem já te venceu.',
        'context': {}, 'xp_value': 20,
    }


def _mw_middle_question() -> dict:
    seat = random.choice(['HJ', 'CO', 'LJ'])
    opener = random.choice(_MW_OPENERS)
    return {
        'type': 'mw_middle',
        'question': (
            f'Multiway: {opener} apostou, você está no **{seat}** (no meio) e ainda há '
            f'jogadores para agir depois. Ensanduichado, a postura correta é:'
        ),
        'options': ['Pagar largo', 'Jogar apertado', 'Aumentar como blefe quase sempre'],
        'correct_index': 1,
        'explanation': (
            'No meio você ainda pode levar um aumento de quem está atrás e enfrenta duas mãos '
            'desconhecidas. Siga só com mãos fortes; pagar largo aqui vaza fichas.'
        ),
        'mental_tip': '**Assento do meio = o pior lugar.** Aperte: você joga sem informação e sob risco de raise.',
        'context': {}, 'xp_value': 20,
    }


def generate_multiway_question(user_id: int = None) -> dict:
    """Treino da aula de Multiway: mw_bluff, mw_sizing, mw_middle."""
    qtype = random.choice(['mw_bluff', 'mw_sizing', 'mw_middle'])
    if qtype == 'mw_bluff':
        return _mw_bluff_question()
    if qtype == 'mw_sizing':
        return _mw_sizing_question()
    return _mw_middle_question()


def generate_icm_question(user_id: int = None) -> dict:
    """Treino da aula de ICM: reusa os geradores focados em ICM (call/fold sob pressão
    + defesa na bolha), sem o 3bet_pot do módulo de torneio."""
    if random.random() < 0.5:
        return _icm_spot_question()
    return _bubble_defense_question()


# ── Postflop: treino da aula "C-bet, barrel e texturas" ──────────────────────────

_DRY_BOARDS = ['K-7-2 arco-íris', 'A-8-3 arco-íris', 'Q-6-2 arco-íris', 'K-9-4 arco-íris']
_WET_BOARDS = ['9-8-7 de dois naipes', 'J-T-8 de dois naipes', '7-6-5 de dois naipes', 'Q-J-9 de dois naipes']


def _cbet_dry_question() -> dict:
    board = random.choice(_DRY_BOARDS)
    return {
        'type': 'cbet_dry',
        'question': (
            f'Você abriu no pré (é o agressor) e vê um flop SECO, {board}, heads-up e em '
            f'posição. Qual a melhor jogada?'
        ),
        'options': ['C-bet pequeno, na maioria das mãos', 'Check com quase tudo', 'Overbet só com os nuts'],
        'correct_index': 0,
        'explanation': (
            'Board seco favorece o agressor: você tem mais mãos fortes na sua range e o vilão '
            'errou muito. C-bet pequeno (cerca de 1/3 do pote) e frequente lucra barato, negando '
            'equity das cartas altas dele.'
        ),
        'mental_tip': '**Seco e você é o agressor:** c-bet pequeno e frequente.',
        'context': {}, 'xp_value': 20,
    }


def _cbet_wet_question() -> dict:
    board = random.choice(_WET_BOARDS)
    return {
        'type': 'cbet_wet',
        'question': (
            f'Flop MOLHADO e conectado, {board}. Você é o agressor. Qual a abordagem certa?'
        ),
        'options': [
            'C-bet em quase tudo, pequeno',
            'Apostar menos vezes e mais seletivo (maior com valor e projeto)',
            'Overbet de blefe sempre',
        ],
        'correct_index': 1,
        'explanation': (
            'Board molhado ajuda o range do vilão (mais pares, dois pares e projetos). Aposte com '
            'menos frequência e de forma mais polarizada, maior com valor e projetos fortes; boa '
            'parte das suas mãos prefere check.'
        ),
        'mental_tip': '**Molhado favorece quem defende:** c-bet menos e mais seletivo.',
        'context': {}, 'xp_value': 20,
    }


def _barrel_question() -> dict:
    if random.random() < 0.5:
        card = random.choice(['um Ás', 'um Rei', 'uma Dama'])
        return {
            'type': 'barrel',
            'question': (
                f'Você deu c-bet no flop e o turn traz {card} alto, que combina com o seu range '
                f'de agressor. Como seguir?'
            ),
            'options': ['Apostar de novo (barrel)', 'Checar e desistir', 'Nunca apostar no turn'],
            'correct_index': 0,
            'explanation': (
                'Cartas altas costumam bater mais o range de quem abriu do que o de quem defendeu. '
                'Seguir apostando (double barrel) pressiona os pares médios do vilão e ganha muitos potes.'
            ),
            'mental_tip': '**Turn que ajuda o SEU range:** siga apostando.',
            'context': {}, 'xp_value': 20,
        }
    card = random.choice(['um 5 que fecha projetos', 'um 8 que conecta o board', 'uma carta baixa que completa desenhos'])
    return {
        'type': 'barrel',
        'question': (
            f'Você deu c-bet no flop e o turn traz {card}, que ajuda mais o range do vilão. Como seguir?'
        ),
        'options': ['Apostar grande sempre', 'Frear: apostar menos e controlar o pote', 'Dar all-in de blefe'],
        'correct_index': 1,
        'explanation': (
            'Quando o turn favorece quem defendeu, o seu blefe perde valor e você é pago pelas mãos '
            'melhores. Freie: aposte com menos frequência, faça mais check e controle o tamanho do pote.'
        ),
        'mental_tip': '**Turn que ajuda o vilão:** freie e controle o pote.',
        'context': {}, 'xp_value': 20,
    }


def generate_postflop_question(user_id: int = None) -> dict:
    """Treino da aula de Postflop: cbet_dry, cbet_wet, barrel."""
    qtype = random.choice(['cbet_dry', 'cbet_wet', 'barrel'])
    if qtype == 'cbet_dry':
        return _cbet_dry_question()
    if qtype == 'cbet_wet':
        return _cbet_wet_question()
    return _barrel_question()


# ── Bet Sizing: treino da aula "Bet Sizing 101" ──────────────────────────────────

def _open_size_question() -> dict:
    pos = random.choice(['UTG', 'MP', 'CO', 'BTN'])
    return {
        'type': 'open_size',
        'question': (
            f'Torneio, stack de ~40 BB. Você vai abrir no {pos}. Qual o tamanho padrão do '
            f'open (raise inicial)?'
        ),
        'options': ['2 a 2,5 BB', '4 a 5 BB', 'All-in'],
        'correct_index': 0,
        'explanation': (
            'Em stacks de torneio (20 a 50 BB), o open padrão é pequeno, cerca de 2 a 2,5 BB. '
            'Abrir grande arrisca mais fichas sem necessidade e não aumenta o seu fold equity de '
            'forma proporcional ao custo.'
        ),
        'mental_tip': '**Open de torneio:** pequeno, ~2 a 2,5 BB.',
        'context': {}, 'xp_value': 20,
    }


def _threebet_size_question() -> dict:
    if random.random() < 0.5:
        return {
            'type': 'threebet_size',
            'question': (
                'O CO abre para 2,5 BB e você quer dar 3-bet no BTN, em posição. Qual o bom '
                'tamanho de 3-bet?'
            ),
            'options': ['~3x o open (7 a 8 BB)', 'Só um pouco acima (4 BB)', '~6x o open'],
            'correct_index': 0,
            'explanation': (
                'Em posição, o 3-bet padrão é cerca de 3x o open. Menor que isso dá odds boas '
                'demais para o vilão pagar; muito maior compromete fichas à toa.'
            ),
            'mental_tip': '**3-bet em posição:** ~3x o open.',
            'context': {}, 'xp_value': 20,
        }
    return {
        'type': 'threebet_size',
        'question': (
            'O BTN abre para 2,5 BB e você quer dar 3-bet no BB, fora de posição. Qual o bom tamanho?'
        ),
        'options': ['~4x o open (10 BB)', '~3x o open (7,5 BB)', 'Min 3-bet (5 BB)'],
        'correct_index': 0,
        'explanation': (
            'Fora de posição você cobra mais: cerca de 4x o open. O tamanho maior compensa a '
            'desvantagem de jogar as próximas ruas sem posição e nega odds ao vilão.'
        ),
        'mental_tip': '**3-bet fora de posição:** ~4x o open (maior que em posição).',
        'context': {}, 'xp_value': 20,
    }


def _spr_question() -> dict:
    return {
        'type': 'spr_size',
        'question': (
            'Você chega ao flop com SPR baixo (cerca de 2) segurando top par bom. O que o SPR '
            'baixo indica?'
        ),
        'options': ['Você está comprometido: jogue por stacks', 'Dá para foldar fácil se apostarem', 'Nunca aposte com SPR baixo'],
        'correct_index': 0,
        'explanation': (
            'SPR (relação entre o stack efetivo e o pote) baixo significa que sobra pouco atrás em '
            'relação ao pote. Com uma mão forte como top par bom e SPR ~2, você está comprometido: '
            'o plano é colocar as fichas, não desistir de uma aposta.'
        ),
        'mental_tip': '**SPR baixo + mão forte = comprometido:** jogue por stacks.',
        'context': {}, 'xp_value': 20,
    }


def generate_sizing_question(user_id: int = None) -> dict:
    """Treino da aula de Bet Sizing: open_size, threebet_size, spr_size."""
    qtype = random.choice(['open_size', 'threebet_size', 'spr_size'])
    if qtype == 'open_size':
        return _open_size_question()
    if qtype == 'threebet_size':
        return _threebet_size_question()
    return _spr_question()


# ── MDF & Alpha: treino da aula "Quanto defender vs. quanto blefar" ──────────────
# MDF = pote / (pote + aposta) = com quanto você defende. Alpha = aposta / (pote + aposta)
# = fold mínimo que o seu blefe precisa. Aposta menor: defende MAIS, blefa mais barato.

_MDF_ITEMS = [
    ('mdf', 'o pote inteiro', ['~50%', '~67%', '~33%'], 0,
     'MDF = pote / (pote + aposta). Com aposta do tamanho do pote, você defende ~50% das mãos '
     'para o blefe do vilão não lucrar de graça.'),
    ('mdf', 'meio pote', ['~50%', '~67%', '~40%'], 1,
     'MDF = pote / (pote + aposta). Com aposta de meio pote, você defende ~67%: apostas menores '
     'exigem que você defenda MAIS.'),
    ('mdf', 'dois terços do pote', ['~60%', '~50%', '~75%'], 0,
     'MDF = pote / (pote + aposta). Com aposta de 2/3 do pote, você defende ~60%.'),
    ('alpha', 'o pote inteiro', ['~50%', '~33%', '~25%'], 0,
     'Alpha = aposta / (pote + aposta). Um blefe do tamanho do pote precisa fazer o vilão foldar '
     '~50% para empatar.'),
    ('alpha', 'meio pote', ['~50%', '~33%', '~67%'], 1,
     'Alpha = aposta / (pote + aposta). Um blefe de meio pote precisa de ~33% de fold: apostas '
     'menores blefam mais barato.'),
    ('alpha', 'dois terços do pote', ['~40%', '~50%', '~33%'], 0,
     'Alpha = aposta / (pote + aposta). Um blefe de 2/3 do pote precisa de ~40% de fold.'),
]


def generate_mdf_question(user_id: int = None) -> dict:
    """Treino da aula de MDF & Alpha: mdf (defesa) e alpha (frequência de blefe)."""
    kind, size, options, ci, expl = random.choice(_MDF_ITEMS)
    if kind == 'mdf':
        q = (f'O vilão aposta {size}. Pela defesa mínima (MDF), com cerca de quantas das suas '
             f'mãos você deve continuar (call ou raise)?')
        tip = '**MDF = pote / (pote + aposta).** Aposta menor, você defende mais.'
    else:
        q = (f'Você blefa apostando {size}. Para o blefe empatar, ele precisa fazer o vilão foldar '
             f'pelo menos:')
        tip = '**Alpha = aposta / (pote + aposta).** É o fold mínimo que o seu blefe precisa.'
    return {
        'type': kind, 'question': q, 'options': options, 'correct_index': ci,
        'explanation': expl, 'mental_tip': tip, 'context': {}, 'xp_value': 20,
    }


# ── Combinatória: treino da aula "Contar combos e blockers" ──────────────────────
# Par = 6 combos; não-par = 16 (4 suited + 12 offsuit). Uma carta conhecida bloqueia
# combos: com um Ás na mão, sobram C(3,2)=3 combos de AA.

_COMBO_PAIRS = ['A', 'K', 'Q', 'J', 'T', '9']
_COMBO_HI = [('A', 'K'), ('A', 'Q'), ('K', 'Q'), ('K', 'J'), ('Q', 'J')]


def _combo_pair_question() -> dict:
    r = random.choice(_COMBO_PAIRS)
    return {
        'type': 'combo_pair',
        'question': f'Sem nenhuma carta conhecida, quantas combinações uma mão pareada como {r}{r} tem?',
        'options': ['6', '4', '16'],
        'correct_index': 0,
        'explanation': (
            f'Um par tem 6 combinações: são 4 cartas do valor {r} e você escolhe 2, o que dá '
            f'C(4,2) = 6. Todo par (AA, KK, 22) tem sempre 6 combos.'
        ),
        'mental_tip': '**Par = 6 combos.** Sempre 6, para qualquer par.',
        'context': {}, 'xp_value': 20,
    }


def _combo_unpaired_question() -> dict:
    a, b = random.choice(_COMBO_HI)
    return {
        'type': 'combo_unpaired',
        'question': f'Quantas combinações uma mão não-pareada como {a}{b} tem no total (suited + offsuit)?',
        'options': ['16', '12', '6'],
        'correct_index': 0,
        'explanation': (
            f'Uma mão não-pareada tem 16 combinações: 4 suited (uma por naipe) + 12 offsuit '
            f'(4 x 3). Todo {a}{b}, AK, KQ e afins tem 16 combos no total.'
        ),
        'mental_tip': '**Não-par = 16 combos** (4 suited + 12 offsuit).',
        'context': {}, 'xp_value': 20,
    }


def _combo_split_question() -> dict:
    a, b = random.choice(_COMBO_HI)
    if random.random() < 0.5:
        return {
            'type': 'combo_split',
            'question': f'Das combinações de {a}{b}, quantas são suited (do mesmo naipe)?',
            'options': ['4', '12', '6'],
            'correct_index': 0,
            'explanation': 'São 4 combinações suited, uma para cada naipe (copas, ouros, paus, espadas).',
            'mental_tip': '**Suited = 4 combos** (um por naipe).',
            'context': {}, 'xp_value': 20,
        }
    return {
        'type': 'combo_split',
        'question': f'Das combinações de {a}{b}, quantas são offsuit (naipes diferentes)?',
        'options': ['12', '4', '16'],
        'correct_index': 0,
        'explanation': 'São 12 combinações offsuit: 4 naipes da primeira carta x 3 naipes restantes da segunda.',
        'mental_tip': '**Offsuit = 12 combos** (4 x 3).',
        'context': {}, 'xp_value': 20,
    }


def _combo_blocker_question() -> dict:
    r = random.choice(['A', 'K', 'Q'])
    return {
        'type': 'combo_blocker',
        'question': (
            f'Você tem um {r} na sua mão. Quantas combinações de {r}{r} o vilão ainda pode ter?'
        ),
        'options': ['3', '6', '1'],
        'correct_index': 0,
        'explanation': (
            f'Com um {r} na sua mão, sobram só 3 cartas desse valor no baralho, então o vilão tem '
            f'C(3,2) = 3 combinações de {r}{r} (em vez das 6 normais). É assim que um blocker corta combos.'
        ),
        'mental_tip': '**Segurar 1 carta de um par derruba os combos dele de 6 para 3.**',
        'context': {}, 'xp_value': 20,
    }


def generate_combo_question(user_id: int = None) -> dict:
    """Treino da aula de Combinatória: combo_pair, combo_unpaired, combo_split, combo_blocker."""
    qtype = random.choice(['combo_pair', 'combo_unpaired', 'combo_split', 'combo_blocker'])
    if qtype == 'combo_pair':
        return _combo_pair_question()
    if qtype == 'combo_unpaired':
        return _combo_unpaired_question()
    if qtype == 'combo_split':
        return _combo_split_question()
    return _combo_blocker_question()


# ── Blockers: treino da aula "Blockers & Unblockers" ─────────────────────────────
# O melhor blefe BLOQUEIA o valor do vilão e NÃO bloqueia (unblock) os folds dele.
# Para pagar (bluff-catch), tenha o blocker do valor.

def _blocker_bluff_question() -> dict:
    draw = random.choice([('cor de copas', 'o Ás de copas', 'a cor máxima'),
                          ('cor de espadas', 'o Ás de espadas', 'a cor máxima'),
                          ('sequência', 'uma carta da ponta da sequência', 'a sequência máxima')])
    board, card, made = draw
    return {
        'type': 'blocker_bluff',
        'question': (
            f'River num board que completou um projeto de {board}. Você quer blefar. Entre duas '
            f'mãos fracas, qual blefa melhor?'
        ),
        'options': [f'A que tem {card}', 'A que não tem conexão nenhuma com o board', 'Tanto faz'],
        'correct_index': 0,
        'explanation': (
            f'Ter {card} bloqueia {made} do vilão: ele passa a ter menos combos da mão que te paga, '
            f'então o seu blefe faz ele foldar mais. Blefar com o blocker do valor dele é o blefe melhor.'
        ),
        'mental_tip': '**Melhor blefe: o que bloqueia as mãos fortes do vilão.**',
        'context': {}, 'xp_value': 20,
    }


def _blocker_catch_question() -> dict:
    return {
        'type': 'blocker_catch',
        'question': (
            'Você tem uma mão média no river e decide se paga um all-in (bluff-catch). Entre duas '
            'mãos parecidas, qual paga melhor?'
        ),
        'options': ['A que bloqueia as mãos de VALOR do vilão', 'A que bloqueia os BLEFES do vilão', 'Tanto faz'],
        'correct_index': 0,
        'explanation': (
            'Bloquear o valor do vilão significa que ele tem menos combos de valor, então é mais '
            'provável que esteja blefando: melhor para pagar. Bloquear os blefes dele é o contrário, '
            'pior para pagar.'
        ),
        'mental_tip': '**Para pagar (bluff-catch): tenha o blocker do VALOR do vilão.**',
        'context': {}, 'xp_value': 20,
    }


def _blocker_unblock_question() -> dict:
    return {
        'type': 'blocker_unblock',
        'question': (
            'Você quer blefar para o vilão foldar as mãos médias dele. É melhor que a sua mão de blefe:'
        ),
        'options': ['NÃO tenha as cartas das mãos que ele foldaria', 'Tenha as cartas dos folds dele', 'Tanto faz'],
        'correct_index': 0,
        'explanation': (
            'Se você segura as cartas das mãos que o vilão foldaria, ele tem menos dessas mãos para '
            'foldar, e o seu blefe funciona menos. O melhor blefe DESbloqueia (unblock) os folds do vilão: '
            'bloqueia o valor e deixa os folds livres.'
        ),
        'mental_tip': '**Bom blefe: bloqueia o valor e NÃO bloqueia os folds do vilão.**',
        'context': {}, 'xp_value': 20,
    }


def generate_blocker_question(user_id: int = None) -> dict:
    """Treino da aula de Blockers: blocker_bluff, blocker_catch, blocker_unblock."""
    qtype = random.choice(['blocker_bluff', 'blocker_catch', 'blocker_unblock'])
    if qtype == 'blocker_bluff':
        return _blocker_bluff_question()
    if qtype == 'blocker_catch':
        return _blocker_catch_question()
    return _blocker_unblock_question()


# ── Posição: treino da aula "Fundamentos de Posição" ─────────────────────────────
# Em posição = age por último no pós-flop (mais informação). O botão é o melhor
# assento; os blinds os piores. Perto do botão você abre mais mãos.

def _pos_order_question() -> dict:
    return {
        'type': 'pos_order',
        'question': 'Estar "em posição" no pós-flop significa que você age:',
        'options': ['Depois do vilão', 'Antes do vilão', 'Ao mesmo tempo que o vilão'],
        'correct_index': 0,
        'explanation': (
            'Em posição você age por último em cada rua do pós-flop: você vê o que o vilão faz '
            'antes de decidir. Essa informação a mais é o que torna a posição tão valiosa.'
        ),
        'mental_tip': '**Em posição = age por último = mais informação.**',
        'context': {}, 'xp_value': 20,
    }


def _pos_best_question() -> dict:
    return {
        'type': 'pos_best',
        'question': 'Qual é a melhor posição da mesa?',
        'options': ['Button (BTN)', 'Under the gun (UTG)', 'Big blind (BB)'],
        'correct_index': 0,
        'explanation': (
            'O button (BTN) é o melhor assento: no pós-flop você age sempre por último, com a '
            'máxima informação. Por isso é de onde se abre mais mãos e se ganha mais dinheiro.'
        ),
        'mental_tip': '**O botão (BTN) é o melhor assento da mesa.**',
        'context': {}, 'xp_value': 20,
    }


def _pos_range_question() -> dict:
    return {
        'type': 'pos_range',
        'question': 'De qual posição você deve abrir MAIS mãos (uma range mais larga)?',
        'options': ['Do button (BTN)', 'Do under the gun (UTG)', 'Tanto faz'],
        'correct_index': 0,
        'explanation': (
            'Do BTN você abre muito mais mãos que do UTG: há menos gente para agir depois de você e '
            'você jogará em posição. No UTG, com a mesa inteira atrás, abra apertado.'
        ),
        'mental_tip': '**Perto do botão, abra mais; cedo (UTG), abra apertado.**',
        'context': {}, 'xp_value': 20,
    }


def _pos_realization_question() -> dict:
    return {
        'type': 'pos_realization',
        'question': 'A MESMA mão realiza mais equity (aproveita melhor a sua chance) em posição ou fora dela?',
        'options': ['Em posição', 'Fora de posição', 'É igual nos dois'],
        'correct_index': 0,
        'explanation': (
            'A mesma mão vale mais em posição: você controla o tamanho do pote, chega ao showdown '
            'mais barato e blefa com mais eficácia. A equity é a mesma; a realização, não.'
        ),
        'mental_tip': '**A mesma mão vale mais em posição** (realiza mais equity).',
        'context': {}, 'xp_value': 20,
    }


def generate_position_question(user_id: int = None) -> dict:
    """Treino da aula de Posição: pos_order, pos_best, pos_range, pos_realization."""
    qtype = random.choice(['pos_order', 'pos_best', 'pos_range', 'pos_realization'])
    if qtype == 'pos_order':
        return _pos_order_question()
    if qtype == 'pos_best':
        return _pos_best_question()
    if qtype == 'pos_range':
        return _pos_range_question()
    return _pos_realization_question()


# ── Showdown value: treino da aula "Showdown Value" ──────────────────────────────
# Mão média que ganha de blefes no showdown mas perde de valor: geralmente CHECK
# (controla o pote, chega ao showdown barato); contra agressor, serve de bluff-catch.

def _sdv_action_question() -> dict:
    return {
        'type': 'sdv_action',
        'question': (
            'Você tem uma mão média que ganha de blefes no showdown, mas perde das mãos de valor. '
            'Ninguém apostou ainda. Qual a melhor jogada?'
        ),
        'options': ['Check, para chegar ao showdown barato', 'Apostar por valor', 'Blefar grande'],
        'correct_index': 0,
        'explanation': (
            'Mãos de showdown value preferem check: você já ganha das mãos que blefariam, e apostar '
            'só faz as piores foldarem e as melhores pagarem. Check controla o pote e leva você ao '
            'showdown de graça.'
        ),
        'mental_tip': '**Showdown value = check** para ver o showdown barato.',
        'context': {}, 'xp_value': 20,
    }


def _sdv_why_question() -> dict:
    return {
        'type': 'sdv_why',
        'question': 'Por que geralmente NÃO se aposta uma mão de showdown value?',
        'options': [
            'Só as mãos melhores pagam e as piores foldam',
            'Porque a mão é forte demais para apostar por valor',
            'Porque ela nunca ganha no showdown',
        ],
        'correct_index': 0,
        'explanation': (
            'Apostar uma mão média é o pior dos dois mundos: as mãos que te pagam são as que te '
            'batem, e as que você venceria (os blefes) foldam. Você transforma um showdown ganho '
            'num pote perdido. Por isso essas mãos preferem check.'
        ),
        'mental_tip': '**Apostar SDV = só te paga quem te bate.** Prefira check.',
        'context': {}, 'xp_value': 20,
    }


def _sdv_catch_question() -> dict:
    return {
        'type': 'sdv_catch',
        'question': 'Contra um jogador que blefa muito, uma mão de showdown value serve principalmente para:',
        'options': ['Pagar as apostas dele (bluff-catch)', 'Blefar por cima', 'Foldar sempre'],
        'correct_index': 0,
        'explanation': (
            'Se o vilão blefa demais, a sua mão média vira um ótimo bluff-catcher: ela perde de valor, '
            'mas ganha de todos os blefes dele. Contra um agressor, pagar com showdown value é lucrativo.'
        ),
        'mental_tip': '**Contra agressor, SDV vira bluff-catcher:** pague os blefes.',
        'context': {}, 'xp_value': 20,
    }


def generate_sdv_question(user_id: int = None) -> dict:
    """Treino da aula de Showdown Value: sdv_action, sdv_why, sdv_catch."""
    qtype = random.choice(['sdv_action', 'sdv_why', 'sdv_catch'])
    if qtype == 'sdv_action':
        return _sdv_action_question()
    if qtype == 'sdv_why':
        return _sdv_why_question()
    return _sdv_catch_question()


# ── Exploits: treino da aula "Exploits & Leituras (arquétipos)" ──────────────────
# O desvio explora o erro do vilão: station não folda (blefe zero, value fino);
# nit folda demais (blefe mais, respeite as apostas); agressor blefa demais (pague largo).

def _exploit_station_question() -> dict:
    return {
        'type': 'exploit_station',
        'question': (
            'Contra um calling station (paga apostas demais e quase não folda), qual o ajuste certo?'
        ),
        'options': [
            'Blefe zero e aposte só por valor, maior e mais fino',
            'Blefe mais para expulsá-lo',
            'Aposte sempre pequeno',
        ],
        'correct_index': 0,
        'explanation': (
            'O station não folda, então blefe é dinheiro jogado fora. Aposte só por valor, e maior '
            'e mais fino, porque ele paga com muitas mãos piores que o normal.'
        ),
        'mental_tip': '**Vs station: blefe zero, value fino e maior.**',
        'context': {}, 'xp_value': 20,
    }


def _exploit_nit_question() -> dict:
    return {
        'type': 'exploit_nit',
        'question': 'Contra um nit (joga super apertado e folda demais), qual o ajuste?',
        'options': [
            'Blefe e roube mais; mas folde suas marginais quando ELE apostar',
            'Pague largo todas as apostas dele',
            'Nunca blefe contra ele',
        ],
        'correct_index': 0,
        'explanation': (
            'O nit desiste demais, então blefes baratos lucram e você rouba mais os blinds dele. '
            'Mas quando ELE aposta, é valor de verdade: folde suas mãos marginais.'
        ),
        'mental_tip': '**Vs nit: blefe mais, mas respeite as apostas dele.**',
        'context': {}, 'xp_value': 20,
    }


def _exploit_lag_question() -> dict:
    return {
        'type': 'exploit_lag',
        'question': (
            'Contra um jogador muito agressivo que blefa demais (LAG ou maníaco), qual o ajuste?'
        ),
        'options': [
            'Pague mais largo (bluff-catch) e não folde demais à pressão dele',
            'Folde mais para não se expor',
            'Blefe por cima dele sempre',
        ],
        'correct_index': 0,
        'explanation': (
            'Se ele blefa demais, as suas mãos médias viram bluff-catchers: pague mais largo e não '
            'sobre-folde à agressão dele. Deixe-o blefar contra a sua mão em vez de fugir.'
        ),
        'mental_tip': '**Vs agressor: pague mais largo, não sobre-folde.**',
        'context': {}, 'xp_value': 20,
    }


def generate_exploit_question(user_id: int = None) -> dict:
    """Treino da aula de Exploits: exploit_station, exploit_nit, exploit_lag."""
    qtype = random.choice(['exploit_station', 'exploit_nit', 'exploit_lag'])
    if qtype == 'exploit_station':
        return _exploit_station_question()
    if qtype == 'exploit_nit':
        return _exploit_nit_question()
    return _exploit_lag_question()


# ── PKO: treino da aula "Torneios de Bounty (PKO)" ───────────────────────────────
# Só o stack que COBRE captura o bounty; o bounty deixa o call mais largo (vs quem
# você cobre); afrouxa cedo (caçar bounties), aperta perto do dinheiro (ICM).

def _pko_cover_question() -> dict:
    return {
        'type': 'pko_cover',
        'question': (
            'Num torneio PKO (bounty), quem leva o prêmio de recompensa (o bounty) ao eliminar '
            'um jogador?'
        ),
        'options': [
            'Só quem COBRE o eliminado (tinha o stack maior)',
            'Qualquer jogador que estava na mão',
            'Quem tinha menos fichas',
        ],
        'correct_index': 0,
        'explanation': (
            'No PKO, só o jogador que cobre (tem fichas suficientes para eliminar) captura o bounty. '
            'Se você é o short, não leva o bounty mesmo ganhando a mão; por isso a recompensa favorece '
            'os stacks maiores.'
        ),
        'mental_tip': '**Só o stack que COBRE captura o bounty.**',
        'context': {}, 'xp_value': 20,
    }


def _pko_power_question() -> dict:
    return {
        'type': 'pko_power',
        'question': (
            'Você pode eliminar o vilão e capturar o bounty dele (você o cobre). Como isso muda a '
            'sua decisão de call?'
        ),
        'options': [
            'Pague mais largo: o bounty adiciona valor ao call',
            'Aperte mais: o bounty é só risco',
            'Não muda nada',
        ],
        'correct_index': 0,
        'explanation': (
            'O bounty é dinheiro extra que você ganha ao eliminar o vilão. Isso adiciona valor ao '
            'call, então você pode pagar mais largo do que num torneio normal, desde que você o cubra.'
        ),
        'mental_tip': '**Cobre o vilão? O bounty deixa o call mais largo.**',
        'context': {}, 'xp_value': 20,
    }


def _pko_stage_question() -> dict:
    return {
        'type': 'pko_stage',
        'question': 'Como ajustar a agressividade num PKO conforme o estágio do torneio?',
        'options': [
            'Afrouxe cedo para caçar bounties; aperte perto do dinheiro (ICM)',
            'Aperte cedo, afrouxe no fim',
            'Jogue igual o torneio todo',
        ],
        'correct_index': 0,
        'explanation': (
            'Cedo, os bounties valem muito em relação ao seu stack: afrouxe e cace eliminações. Perto '
            'do dinheiro, o ICM volta a pesar e você aperta; ali o valor de sobreviver supera o do bounty.'
        ),
        'mental_tip': '**PKO: afrouxa cedo (bounties), aperta perto do dinheiro (ICM).**',
        'context': {}, 'xp_value': 20,
    }


def generate_pko_question(user_id: int = None) -> dict:
    """Treino da aula de PKO: pko_cover, pko_power, pko_stage."""
    qtype = random.choice(['pko_cover', 'pko_power', 'pko_stage'])
    if qtype == 'pko_cover':
        return _pko_cover_question()
    if qtype == 'pko_power':
        return _pko_power_question()
    return _pko_stage_question()


# ── 5 desequilíbrios: treino da aula "Os 5 desequilíbrios" ───────────────────────
# Polaridade (fortes+blefes), elasticidade (o call muda com o tamanho?), board
# coverage (ter valor em muitos tipos de board).

def _imb_polarity_question() -> dict:
    return {
        'type': 'imb_polarity',
        'question': 'Uma range de aposta POLARIZADA é composta principalmente de:',
        'options': [
            'Mãos muito fortes e blefes, com pouco no meio',
            'Só mãos médias',
            'Só mãos fortes de valor',
        ],
        'correct_index': 0,
        'explanation': (
            'Polarizar é apostar as pontas: mãos muito fortes (valor) e blefes, deixando as mãos '
            'médias no check. Ranges polarizadas costumam usar tamanhos maiores.'
        ),
        'mental_tip': '**Polarizada = fortes + blefes, pouco no meio.**',
        'context': {}, 'xp_value': 20,
    }


def _imb_elasticity_question() -> dict:
    return {
        'type': 'imb_elasticity',
        'question': (
            'Contra um vilão INELÁSTICO (paga igual, não importa o tamanho da sua aposta), você deve:'
        ),
        'options': [
            'Apostar MAIOR por valor (o tamanho não muda o call dele)',
            'Apostar sempre pequeno',
            'Nunca apostar',
        ],
        'correct_index': 0,
        'explanation': (
            'Elasticidade mede o quanto o call do vilão muda com o tamanho. Se ele é inelástico (paga '
            'qualquer tamanho), aposte maior por valor: você cobra mais sem perder o call.'
        ),
        'mental_tip': '**Vilão inelástico: aposte maior por valor.**',
        'context': {}, 'xp_value': 20,
    }


def _imb_board_question() -> dict:
    return {
        'type': 'imb_board',
        'question': "'Board coverage' (cobertura de board) significa:",
        'options': [
            'Ter mãos fortes na sua range em vários tipos de board',
            'Cobrir o pote com fichas',
            'Só jogar boards secos',
        ],
        'correct_index': 0,
        'explanation': (
            'Board coverage é ter mãos fortes distribuídas por muitos tipos de flop, para não ficar '
            "'descoberto' quando o board te desfavorece. Ranges bem construídas cobrem boards altos e baixos."
        ),
        'mental_tip': '**Board coverage = ter valor em muitos tipos de flop.**',
        'context': {}, 'xp_value': 20,
    }


def generate_imbalance_question(user_id: int = None) -> dict:
    """Treino da aula dos 5 desequilíbrios: imb_polarity, imb_elasticity, imb_board."""
    qtype = random.choice(['imb_polarity', 'imb_elasticity', 'imb_board'])
    if qtype == 'imb_polarity':
        return _imb_polarity_question()
    if qtype == 'imb_elasticity':
        return _imb_elasticity_question()
    return _imb_board_question()


# ── Push/Fold: treino da aula "Stack curto: shove ou fold" ───────────────────────
# Regras corretas (batem com o solver): em stack curto o min-raise some (shove-or-fold);
# a POSIÇÃO domina o quão largo se shova (early tight, late largo); paga-se um shove quando
# a mão ganha de mais da metade do range de shove do vilão.

def _pf_action_question() -> dict:
    return {
        'type': 'pf_action',
        'question': (
            'Você tem 6bb, primeira a agir com uma mão que quer jogar. Qual a ação padrão a este stack?'
        ),
        'options': [
            'Shove (all-in): curto demais para abrir e foldar depois',
            'Min-raise para ver o flop barato',
            'Limpar (call) e jogar pós-flop',
        ],
        'correct_index': 0,
        'explanation': (
            'A ~6bb não sobra stack para abrir pequeno e desistir depois: um raise já compromete quase '
            'tudo. O shove resolve tudo de uma vez e ainda maximiza a fold equity (a chance de levar os '
            'blinds sem disputa). Por isso, em stack curto o padrão é shove ou fold, não min-raise.'
        ),
        'mental_tip': '**Stack curto: shove ou fold. O min-raise some.**',
        'context': {}, 'xp_value': 20,
    }


def _pf_position_question() -> dict:
    return {
        'type': 'pf_position',
        'question': 'A 8bb, de qual posição você pode shovar MAIS mãos?',
        'options': [
            'Do botão / posições finais (menos gente atrás = mais fold equity)',
            'Do UTG (primeira posição)',
            'É igual em qualquer posição',
        ],
        'correct_index': 0,
        'explanation': (
            'Quanto mais tarde a sua posição, menos jogadores faltam agir atrás, então é menos provável '
            'que alguém acorde com uma mão forte. Mais fold equity = você shova mais largo. No UTG, com a '
            'mesa toda atrás, o range de shove segue apertado mesmo com stack curto.'
        ),
        'mental_tip': '**A posição manda: botão shova largo, UTG segue tight.**',
        'context': {}, 'xp_value': 20,
    }


def _pf_call_question() -> dict:
    return {
        'type': 'pf_call',
        'question': 'Alguém deu shove e a decisão é sua. Você deve pagar quando:',
        'options': [
            'Sua mão ganha de mais da metade do range de shove dele',
            'Você tem qualquer Ás',
            'Você ainda tem fichas de sobra',
        ],
        'correct_index': 0,
        'explanation': (
            'Pagar um shove é um confronto direto: a régua é a equity da sua mão contra o range inteiro '
            'que ele shova. Se você ganha de mais da metade desse range (mais o preço barato do pote), o '
            'call é lucrativo. "Ter um Ás" não basta: um Ás fraco perde para boa parte de um range de shove.'
        ),
        'mental_tip': '**Pague se ganhar de mais da metade do range de shove dele.**',
        'context': {}, 'xp_value': 20,
    }


def generate_pushfold_question(user_id: int = None) -> dict:
    """Treino da aula de push/fold: pf_action, pf_position, pf_call."""
    qtype = random.choice(['pf_action', 'pf_position', 'pf_call'])
    if qtype == 'pf_action':
        return _pf_action_question()
    if qtype == 'pf_position':
        return _pf_position_question()
    return _pf_call_question()


# ── Projetos / semi-blefe: treino da aula "Jogar projetos" ───────────────────────
# O semi-blefe ganha de dois jeitos (fold equity + equity de acertar); rende com fold
# equity (HU, board assustador) e morre sem ela (multiway/station); combo draw ~15 outs
# é quase favorito e pode raisar.

def _draw_why_question() -> dict:
    return {
        'type': 'draw_why',
        'question': (
            'Você tem um flush draw no flop e o vilão aposta. Por que semi-blefar (raisar) '
            'costuma bater só pagar passivo?'
        ),
        'options': [
            'Ganha de dois jeitos: leva o pote agora se ele foldar, e ainda acerta o flush depois',
            'Porque raise é sempre melhor que call',
            'Porque assim você vê as próximas cartas de graça',
        ],
        'correct_index': 0,
        'explanation': (
            'O semi-blefe tem duas fontes de lucro: a fold equity (o vilão desiste na hora) somada '
            'à sua equity de acertar o draw se for pago. Só pagar passivo abre mão da primeira e te '
            'deixa dependente de completar a mão.'
        ),
        'mental_tip': '**Semi-blefe = fold equity + equity de acertar. Ganha de dois jeitos.**',
        'context': {}, 'xp_value': 20,
    }


def _draw_when_question() -> dict:
    return {
        'type': 'draw_when',
        'question': 'O semi-blefe com um projeto rende MAIS quando:',
        'options': [
            'Você está heads-up, em board assustador, contra quem folda (há fold equity)',
            'O pote é multiway contra uma calling station',
            'Você tem só um gutshot e ninguém vai foldar',
        ],
        'correct_index': 0,
        'explanation': (
            'O semi-blefe depende de fold equity. Heads-up, board que assusta e vilão que respeita '
            'apostas = ele desiste muito. Multiway contra quem não folda mata a fold equity: ali o '
            'projeto quer é PREÇO para pagar, não blefar.'
        ),
        'mental_tip': '**Sem fold equity (multiway/station), semi-blefe vira queima. Blefe onde te foldam.**',
        'context': {}, 'xp_value': 20,
    }


def _draw_combo_question() -> dict:
    return {
        'type': 'draw_combo',
        'question': (
            'Você tem flush draw + sequência aberta (~15 outs) no flop, heads-up. Diante de uma aposta, você é:'
        ),
        'options': [
            'Quase favorito: dá até para raisar (semi-blefe forte)',
            'Underdog grande, melhor foldar',
            'Obrigado a só pagar e torcer',
        ],
        'correct_index': 0,
        'explanation': (
            '~15 outs no flop valem perto de 55% de equity até o river, você é favorito mesmo se pago. '
            'Com um monstro-draw desses, raisar é ótimo: muita fold equity E você ainda ganha o showdown '
            'boa parte das vezes.'
        ),
        'mental_tip': '**Combo draw (~15 outs) = quase favorito. Pode raisar, não só pagar.**',
        'context': {}, 'xp_value': 20,
    }


def generate_draws_question(user_id: int = None) -> dict:
    """Treino da aula de projetos/semi-blefe: draw_why, draw_when, draw_combo."""
    qtype = random.choice(['draw_why', 'draw_when', 'draw_combo'])
    if qtype == 'draw_why':
        return _draw_why_question()
    if qtype == 'draw_when':
        return _draw_when_question()
    return _draw_combo_question()


# ── 3-bet: treino da aula "3-bet: re-raise por valor e blefe" ────────────────────
# Range de 3-bet é polarizada (valor forte + blefes com blocker); blefes equilibram e
# disfarçam o valor; A5s/A4s são ótimos blefes (bloqueiam AA/AK e fazem flush/straight).

def _tb_purpose_question() -> dict:
    return {
        'type': 'tb_purpose',
        'question': 'Além das mãos premium, por que incluir alguns blefes no seu range de 3-bet?',
        'options': [
            'Para não ficar previsível: com só premium o vilão te lê e desiste; o blefe leva o pote quando ele folda',
            'Porque blefar é sempre mais lucrativo que apostar por valor',
            'Para ver mais flops baratos',
        ],
        'correct_index': 0,
        'explanation': (
            'Se você só 3-beta AA/KK/AK, o vilão percebe e nunca te paga: seu valor não lucra. Adicionar '
            'blefes deixa o range equilibrado, o vilão precisa continuar com mãos piores, e os blefes ainda '
            'ganham o pote na hora quando ele desiste.'
        ),
        'mental_tip': '**Só 3-betar premium é previsível. Blefes equilibram e disfarçam o valor.**',
        'context': {}, 'xp_value': 20,
    }


def _tb_polar_question() -> dict:
    return {
        'type': 'tb_polar',
        'question': 'Um bom range de 3-bet costuma ser:',
        'options': [
            'Polarizado: mãos fortes (valor) + alguns blefes, com pouca coisa no meio',
            'Só as mãos premium (AA, KK, AK)',
            'As 15% melhores mãos, todas juntas',
        ],
        'correct_index': 0,
        'explanation': (
            'As mãos médias (AQo, TT, AJs) muitas vezes preferem só pagar (call), porque jogam bem num pote '
            'menor. O 3-bet pega as pontas: o valor forte que quer o pote grande e os blefes com blocker. '
            'Isso é uma range polarizada.'
        ),
        'mental_tip': '**3-bet é polarizado: pontas (valor + blefe); o meio (AQo, TT) muitas vezes só paga.**',
        'context': {}, 'xp_value': 20,
    }


def _tb_blocker_question() -> dict:
    return {
        'type': 'tb_blocker',
        'question': 'Qual é um ótimo candidato a blefe de 3-bet?',
        'options': [
            'A5s: bloqueia os AA/AK do vilão e ainda faz flush e sequência',
            '72o: é lixo, dá pra blefar com qualquer coisa',
            'KK: você quer valor com ela, não blefe',
        ],
        'correct_index': 0,
        'explanation': (
            'Um bom blefe de 3-bet tem blocker (o Ás reduz as combinações de AA e AK do vilão, então ele '
            'continua menos) e jogabilidade (A5s faz flush e sequência quando é pago). 72o não bloqueia nada '
            'e joga mal; KK é valor puro.'
        ),
        'mental_tip': '**Blefe de 3-bet bom = blocker (A5s bloqueia AA/AK) + jogabilidade, não lixo.**',
        'context': {}, 'xp_value': 20,
    }


def generate_3bet_question(user_id: int = None) -> dict:
    """Treino da aula de 3-bet: tb_purpose, tb_polar, tb_blocker."""
    qtype = random.choice(['tb_purpose', 'tb_polar', 'tb_blocker'])
    if qtype == 'tb_purpose':
        return _tb_purpose_question()
    if qtype == 'tb_polar':
        return _tb_polar_question()
    return _tb_blocker_question()


# ── Turn & River / barrels: treino da aula "Depois do flop" ──────────────────────
# Double barrel nas cartas que melhoram a SUA range; freia quando ajuda a do vilão;
# river é polarizado (não há mais carta: valor ou blefe, sem semi-blefe).

def _tr_turn_question() -> dict:
    return {
        'type': 'tr_turn',
        'question': (
            'Você fez c-bet no flop e foi pago. Qual turn é o melhor para apostar de novo (double barrel)?'
        ),
        'options': [
            'Uma carta que melhora a SUA range (overcard, completa um draw seu), não a do vilão',
            'Qualquer carta: você já apostou o flop, tem que continuar',
            'Uma carta que ajuda o vilão, para ele pagar mais',
        ],
        'correct_index': 0,
        'explanation': (
            'O bom turn para barrelar é o que melhora as suas mãos ou te deixa representar mais valor, e '
            'que NÃO ajuda a range de call do vilão. Cartas que completam os projetos dele ou dão par às '
            'mãos que te pagaram são cartas para frear, não para apostar.'
        ),
        'mental_tip': '**Double barrel nas cartas que melhoram a SUA range, não a do vilão.**',
        'context': {}, 'xp_value': 20,
    }


def _tr_giveup_question() -> dict:
    return {
        'type': 'tr_giveup',
        'question': 'Quando é hora de desistir do barril no turn (parar de apostar)?',
        'options': [
            'Quando o turn ajuda a range de call do vilão e você não tem equity nem como representar valor',
            'Nunca: quem aposta o flop tem que apostar todas as ruas',
            'Sempre que o vilão pagou o flop',
        ],
        'correct_index': 0,
        'explanation': (
            'Barrelar sem equity e sem uma história crível é só queimar fichas. Se o turn favorece o vilão '
            'e você não tem draw nem uma carta que represente uma mão forte, freie: pegue o showdown barato '
            'ou controle o pote. Nem toda mão que apostou o flop deve apostar o turn.'
        ),
        'mental_tip': '**Sem equity e sem história, freie o barril. Nem todo flop bet vira turn bet.**',
        'context': {}, 'xp_value': 20,
    }


def _tr_river_question() -> dict:
    return {
        'type': 'tr_river',
        'question': 'Por que o river muda a natureza da aposta?',
        'options': [
            'Não há mais cartas: a aposta vira polarizada (valor ou blefe), o semi-blefe deixa de existir',
            'Porque o pote está maior',
            'Porque no river todo mundo folda mais',
        ],
        'correct_index': 0,
        'explanation': (
            'No flop e no turn você pode semi-blefar: apostar um draw que ainda pode acertar. No river não '
            'há próxima carta, então a mão é o que é. A aposta fica polarizada: ou você tem valor (quer ser '
            'pago por pior) ou blefa (sem valor, quer que ele folde). Não existe meio-termo.'
        ),
        'mental_tip': '**River é polarizado: valor ou blefe. Sem carta pra vir, o semi-blefe some.**',
        'context': {}, 'xp_value': 20,
    }


def generate_barrel_question(user_id: int = None) -> dict:
    """Treino da aula de turn & river / barrels: tr_turn, tr_giveup, tr_river."""
    qtype = random.choice(['tr_turn', 'tr_giveup', 'tr_river'])
    if qtype == 'tr_turn':
        return _tr_turn_question()
    if qtype == 'tr_giveup':
        return _tr_giveup_question()
    return _tr_river_question()


# ── Termos & Conceitos: treino de vocabulário ────────────────────────────────────

def _tm_street_question() -> dict:
    return {
        'type': 'tm_street',
        'question': "No poker, o que é uma 'street'?",
        'options': [
            'Cada rodada de apostas: preflop, flop, turn e river',
            'A ordem em que os jogadores sentam na mesa',
            'O tamanho padrão de uma aposta',
        ],
        'correct_index': 0,
        'explanation': (
            'Cada mão tem quatro streets (rodadas de aposta): preflop (antes das cartas comunitárias), '
            'flop, turn e river. "Jogar as streets" é planejar a mão rodada a rodada.'
        ),
        'mental_tip': '**Street = rodada de aposta: preflop, flop, turn, river.**',
        'context': {}, 'xp_value': 20,
    }


def _tm_draw_question() -> dict:
    return {
        'type': 'tm_draw',
        'question': "O que é um 'draw'?",
        'options': [
            'Uma mão que ainda não venceu, mas pode virar a melhor (ex.: flush draw)',
            'Uma mão feita e já vencedora',
            'Um empate no showdown',
        ],
        'correct_index': 0,
        'explanation': (
            'Draw é um projeto: uma mão incompleta que fica forte se a carta certa aparecer, como um '
            'flush draw (falta uma carta do naipe) ou uma sequência aberta.'
        ),
        'mental_tip': '**Draw = mão que ainda não é, mas pode virar (flush draw, straight draw).**',
        'context': {}, 'xp_value': 20,
    }


def _tm_ip_question() -> dict:
    return {
        'type': 'tm_ip',
        'question': "Estar 'em posição' (IP) significa:",
        'options': [
            'Agir por último no pote, com a vantagem de ver o vilão agir antes',
            'Estar sentado à esquerda do dealer',
            'Ter o maior stack da mesa',
        ],
        'correct_index': 0,
        'explanation': (
            'Estar em posição (in position, IP) é agir depois do vilão em todas as streets pós-flop. '
            'Você decide com mais informação, é uma das maiores vantagens do jogo.'
        ),
        'mental_tip': '**Em posição (IP) = você age por último, com mais informação.**',
        'context': {}, 'xp_value': 20,
    }


def generate_terms_question(user_id: int = None) -> dict:
    """Treino de vocabulário da aula de Termos & Conceitos: tm_street, tm_draw, tm_ip."""
    qtype = random.choice(['tm_street', 'tm_draw', 'tm_ip'])
    if qtype == 'tm_street':
        return _tm_street_question()
    if qtype == 'tm_draw':
        return _tm_draw_question()
    return _tm_ip_question()
