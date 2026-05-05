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

def _fetch_math_decision(user_id: int) -> Optional[dict]:
    """Returns a random decision with facing_bet > 0 from user's history."""
    conn = get_conn()
    try:
        row = conn.execute(_adapt("""
            SELECT d.id, d.pot_size, d.facing_bet, d.stack_bb, d.m_ratio,
                   d.label, d.action_taken, d.best_action, d.street,
                   d.position, d.score
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE t.user_id = ?
              AND d.facing_bet IS NOT NULL AND d.facing_bet > 0
              AND d.pot_size   IS NOT NULL AND d.pot_size   > 0
            ORDER BY RANDOM()
            LIMIT 1
        """), (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def generate_math_question(user_id: int) -> dict:
    """
    Generates one of 3 math exercise types:
      - pot_odds_calc  : calcule a % mínima de equity
      - call_or_fold   : dado equity e pot odds, call ou fold?
      - ev_direction   : esta ação é +EV ou -EV?

    Returns a question dict ready to be JSON-serialized.
    """
    decision = _fetch_math_decision(user_id)

    # Fallback to synthetic question if no history
    if not decision:
        return _synthetic_pot_odds_question()

    pot   = round(float(decision['pot_size']), 1)
    bet   = round(float(decision['facing_bet']), 1)
    label = decision.get('label', 'standard')

    # Minimum equity needed (pot odds formula)
    min_equity_exact = bet / (pot + bet)
    min_equity_pct   = round(min_equity_exact * 100, 1)

    # Randomly pick a question type; bias toward pot_odds_calc for beginners
    qtype = random.choices(
        ['pot_odds_calc', 'call_or_fold', 'ev_direction'],
        weights=[0.50, 0.30, 0.20],
    )[0]

    if qtype == 'pot_odds_calc':
        return _pot_odds_calc_question(pot, bet, min_equity_pct, decision)

    if qtype == 'call_or_fold':
        return _call_or_fold_question(pot, bet, min_equity_pct, decision)

    return _ev_direction_question(pot, bet, min_equity_pct, decision)


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

    return {
        'type': 'pot_odds_calc',
        'question': f'Pot: **{pot} BB**. Villain aposta **{bet} BB**.\nQual a equity mínima necessária para o call ser +EV?',
        'options': [f'{o}%' for o in options['values']],
        'correct_index': options['correct_index'],
        'explanation': explanation,
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
        'question': (
            f'Pot: **{pot} BB**. Villain aposta **{bet} BB**.\n'
            f'Sua equity estimada neste spot: **{estimated_equity}%**.\n'
            f'Qual é a ação correta?'
        ),
        'options': options,
        'correct_index': correct_index,
        'explanation': explanation,
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
        'question': (
            f'Pot: **{pot} BB**. Bet: **{bet} BB**.\n'
            f'Equity estimada do hero: **{equity_used}%**.\n'
            f'O call é…'
        ),
        'options': options,
        'correct_index': correct_index,
        'explanation': explanation,
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

    return {
        'type': 'pot_odds_calc',
        'question': f'Pot: **{pot} BB**. Villain aposta **{bet} BB**.\nQual a equity mínima necessária para o call ser +EV?',
        'options': [f'{o}%' for o in options['values']],
        'correct_index': options['correct_index'],
        'explanation': (
            f"Fórmula: bet ÷ (pot + bet) = {bet} ÷ {pot + bet} ≈ **{correct_pct}%**.\n\n"
            "Você precisa de pelo menos essa equity para o call ser matematicamente justificado."
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
    1: 'Projeto (draw)',
    0: 'Air (sem par, sem draw relevante)',
}

BUCKET_LABELS_SHORT = {
    4: 'Mão muito forte',
    3: 'Mão forte',
    2: 'Par médio/fraco',
    1: 'Projeto (draw)',
    0: 'Air',
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
    Generates one of 2 board strength exercise types:
      - hand_classify  : classifique a força da mão neste board
      - board_texture  : classifique a textura deste board

    Returns a question dict ready to be JSON-serialized.
    """
    decision = _fetch_board_decision(user_id)

    if not decision:
        return _synthetic_board_question()

    hero_raw  = decision.get('hero_cards', '')
    board_raw = decision.get('board', '')
    hero  = _parse_cards(hero_raw)
    board = _parse_cards(board_raw)

    if len(hero) < 2 or len(board) < 3:
        return _synthetic_board_question()

    qtype = random.choices(['hand_classify', 'board_texture'], weights=[0.65, 0.35])[0]

    if qtype == 'hand_classify':
        return _hand_classify_question(hero, board, decision)
    return _board_texture_question(board, decision)


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
        1: 'Você tem um projeto (draw): equity presente mas sem par ainda. Decisões envolvem comparar equity vs pot odds para justificar continuar.',
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
        'context': {'street': 'flop', 'position': d.get('position')},
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
        'context': {},
        'xp_value': 20,
    }
