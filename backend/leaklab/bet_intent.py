"""Classificação de INTENÇÃO de aposta/raise postflop do herói — value / blefe / proteção.

Por que apostar (enquadramento do poker, ver pokerbrasil.com.br/porque-apostar):
  1. VALUE — quer call de pior. Subdivide em:
     a) showdown — mão madura, aposta pra extrair.
     b) PROTEÇÃO — mão forte mas vulnerável a draw; aposta nega equity. Só flop/turn
        (no river não há carta pra proteger → aposta é showdown ou blefe, nunca proteção).
  2. BLEFE — pior mão, quer fold de melhor (semi-blefe = blefe COM draw que melhora).
  3. "O MEIO" (leak): mão mediana COM showdown value que GTO dá CHECK — apostar
     value-corta (só pior folda, só melhor paga). É o erro de "apostar pra saber onde estou".

Reusa os thresholds GTO-calibrados do postflop_range_evaluator (value >= 0.65–0.72 conforme
stack, +0.06 OOP; draw forte = equity_adjustment >= 0.15) e, quando há nó, a frequência de
aposta do GTO como árbitro autoritativo (`justified`).
"""
from typing import Optional

_AGGR_ACTIONS = {'bet', 'bets', 'raise', 'raises', 'allin', 'all-in', 'all_in', 'jam', 'shove'}
_RANKS = '23456789TJQKA'


def _ranks_of(cards) -> list:
    return [str(c)[0].upper() for c in (cards or []) if c]


def _suits_of(cards) -> list:
    return [str(c)[1].lower() for c in (cards or []) if c and len(str(c)) >= 2]


def _rv(r) -> int:
    return _RANKS.index(r) + 2 if r in _RANKS else 0


def is_monster_hand(hero_cards, board) -> bool:
    """Mão MONSTRO do herói: quads / full house / flush (herói) / straight (herói) /
    set-trips. Subconjunto do tier 'value' de made_hand_category — usado pelo engine
    como guard de sanidade (apostar/raisar monstro por valor nunca é erro grave)."""
    hr = [_rv(r) for r in _ranks_of(hero_cards)]
    br = [_rv(r) for r in _ranks_of(board)]
    hs = _suits_of(hero_cards)
    bs = _suits_of(board)
    if not hr or not br:
        return False
    all_rv = hr + br
    from collections import Counter
    rank_cnt = Counter(all_rv)
    sorted_cnt = sorted(rank_cnt.values(), reverse=True)

    # quads / full house
    if sorted_cnt and sorted_cnt[0] >= 4:
        return True
    if len(sorted_cnt) >= 2 and sorted_cnt[0] >= 3 and sorted_cnt[1] >= 2:
        return True
    # flush com carta do herói
    all_sv = hs + bs
    for s in set(all_sv):
        if all_sv.count(s) >= 5 and hs.count(s) >= 1:
            return True
    # straight com carta do herói (Ace low incluso)
    uniq = sorted(set(all_rv) | ({1} if 14 in all_rv else set()))
    for i in range(len(uniq) - 4):
        w = uniq[i:i + 5]
        if w[4] - w[0] == 4 and len(set(w)) == 5 and any((h == 14 and 1 in w) or h in w for h in hr):
            return True
    # set / trips
    if any(rank_cnt.get(h, 0) >= 3 for h in set(hr)):
        return True
    return False


def made_hand_category(hero_cards, board) -> str:
    """Tier de força da mão FEITA do herói (não conta draws): 'value' | 'middle' | 'air'.
    Espelha a lógica do academy._hand_bucket, mas separa o bucket-3 (two-pair/overpair/set =
    value sempre) do top-pair (depende do kicker) e do par médio/fraco (middle).

      value  — set/straight/flush/boat/quads, dois pares, overpair, top pair kicker forte (≥Q).
      middle — top pair kicker fraco, par médio/baixo, underpair (showdown value marginal).
      air    — sem par feito.
    """
    hr = [_rv(r) for r in _ranks_of(hero_cards)]
    br = [_rv(r) for r in _ranks_of(board)]
    if not hr or not br:
        return 'air'
    all_rv = hr + br
    from collections import Counter
    rank_cnt = Counter(all_rv)

    # Monster: quads / full house / flush (herói) / straight (herói) / set
    if is_monster_hand(hero_cards, board):
        return 'value'

    # Dois pares REAIS do herói: ele precisa segurar carta em ≥2 pares distintos.
    # (Par totalmente no board — ex. KK em K-Q-K — é compartilhado: não conta pro herói.)
    pairs = [r for r, c in rank_cnt.items() if c >= 2]
    pairs_with_hero = [r for r in pairs if r in hr]
    if len(pairs_with_hero) >= 2:
        return 'value'

    board_max = max(br)
    # Pocket pair: overpair (value) vs underpair (middle)
    if len(hr) == 2 and hr[0] == hr[1]:
        return 'value' if hr[0] > board_max else 'middle'

    # Top pair: kicker forte (≥Q=12) = value; fraco = middle
    if board_max in hr:
        kicker = max((h for h in hr if h != board_max), default=0)
        return 'value' if kicker >= 12 else 'middle'

    # Par médio/baixo
    if any(h in br for h in hr):
        return 'middle'

    return 'air'


def _board_wet(board) -> bool:
    """Board 'molhado': permite draws (flush com 2+ do mesmo naipe, ou conexão p/ straight).
    Proteção só faz sentido em board molhado (há equity do vilão pra negar)."""
    br = _ranks_of(board)
    bs = _suits_of(board)
    if not br:
        return False
    # flush draw possível: 2+ cartas do mesmo naipe
    if any(bs.count(s) >= 2 for s in set(bs)):
        return True
    # conexão p/ straight: 2 cartas dentro de um span de 4 ranks
    idx = sorted({_RANKS.index(r) for r in br if r in _RANKS})
    for i in range(len(idx) - 1):
        if idx[i + 1] - idx[i] <= 3:
            return True
    return False


def _gto_bet_freq(strategy) -> Optional[float]:
    """Soma a frequência de ações agressivas (bet/raise/allin, inclusive sizes) no strategy
    do nó GTO. None se não há strategy. É o árbitro: GTO aposta essa mão?"""
    if not strategy:
        return None
    total = 0.0
    for s in strategy:
        a = (s.get('action') or '').lower()
        f = float(s.get('frequency') or 0.0)
        if a.startswith('bet') or a.startswith('raise') or 'allin' in a or a.endswith('x') or a.endswith('pct') or 'jam' in a or 'shove' in a:
            total += f
    return total


def classify_bet_intent(*, player_action: str, street: str, hero_cards, board,
                        equity: Optional[float], equity_adj: Optional[float],
                        stack_bb: float, position: str, gto: Optional[dict] = None) -> Optional[dict]:
    """Classifica a intenção de uma APOSTA/RAISE postflop do herói.

    Retorna {intent, justified, is_leak, gto_bet_freq} ou None (não é aposta postflop / sem dados).
      intent: value_showdown | value_protection | semi_bluff | bluff | middle
      justified: GTO (ou heurística) concorda em apostar essa mão.
      is_leak: apostou quando não devia (meio, ou blefe sem fundamento).
    """
    act = (player_action or '').lower().strip()
    st  = (street or '').lower().strip()
    if st not in ('flop', 'turn', 'river') or act not in _AGGR_ACTIONS:
        return None

    equity_adj = float(equity_adj or 0.0)
    pos        = (position or '').upper()

    strong_draw = equity_adj >= 0.15          # FD/OESD (backdoors não contam)
    cat         = made_hand_category(hero_cards, board)   # 'value' | 'middle' | 'air'
    river       = st == 'river'

    # ── intenção (o que a aposta É) — força da MÃO FEITA decide value/meio/ar ─────
    if cat == 'value':
        # proteção só flop/turn + board molhado; river/seco = showdown
        intent = 'value_protection' if (not river and _board_wet(board)) else 'value_showdown'
    elif strong_draw:
        intent = 'semi_bluff'                 # ar/par marginal MAS com draw que melhora
    elif cat == 'middle':
        intent = 'middle'                     # showdown value, mas não forte o bastante
    else:
        intent = 'bluff'                      # ar

    # ── árbitro: GTO aprova essa aposta? ─────────────────────────────────────────
    gto_label    = (gto or {}).get('gto_label')
    gto_bet_freq = _gto_bet_freq((gto or {}).get('strategy')) if (gto and gto.get('available')) else None
    if gto_label in ('gto_correct', 'gto_mixed'):
        # O nó GTO já classifica a ação como parte do range (mesmo que mista/baixa
        # frequência): não é leak — coerente com o selo de avaliação da mão.
        justified = True
    elif gto_bet_freq is not None:
        justified = gto_bet_freq >= 0.25
    else:
        # sem nó: value e semi-blefe são defensáveis; o "meio" raramente.
        justified = intent in ('value_showdown', 'value_protection', 'semi_bluff')

    is_leak = (not justified) and intent in ('middle', 'bluff')
    return {'intent': intent, 'justified': justified, 'is_leak': is_leak, 'gto_bet_freq': gto_bet_freq}


def threebet_strength_tier(hero_cards) -> Optional[str]:
    """Tier de força PREFLOP de uma mão num 3-bet: 'value' | 'merge' | 'light'.

    Enquadra o 3-bet pela sua INTENÇÃO (não pela correção, que é o veredito):
      value  — domina o range que continua e quer fichas no meio: QQ+, AK.
      merge  — valor fino / showdown decente no meio do range: 77–JJ, AQ/AJ, A6s+,
               broadways suited (KQs…JTs? não), KQo. Extrai de pior e nega equity.
      light  — a porção de BLEFE: pouco showdown, 3-beta por fold equity + blocker.
               A2s–A5s (wheel aces), 22–66, suited connectors e qualquer mão fraca.
    """
    ranks = _ranks_of(hero_cards)
    if len(ranks) < 2:
        return None
    a, b = _rv(ranks[0]), _rv(ranks[1])
    if a == 0 or b == 0:
        return None
    hi, lo = max(a, b), min(a, b)
    suits  = _suits_of(hero_cards)
    suited = len(suits) == 2 and suits[0] == suits[1]
    pair   = hi == lo

    # VALUE — QQ+ e AK
    if pair and hi >= 12:
        return 'value'
    if hi == 14 and lo == 13:
        return 'value'

    # MERGE — showdown decente / valor fino no meio do range
    if pair and hi >= 7:                          # 77–JJ
        return 'merge'
    if hi == 14 and lo >= 11:                     # AJ, AQ (s/o)
        return 'merge'
    if hi == 14 and suited and lo >= 6:           # A6s–ATs
        return 'merge'
    if suited and hi >= 12 and lo >= 10:          # KQs/KJs/KTs/QJs/QTs/JTs(=11,10) broadway suited
        return 'merge'
    if hi == 13 and lo == 12:                     # KQo
        return 'merge'

    # LIGHT — porção de blefe (residual): A2s–A5s, 22–66, connectors, mãos fracas
    return 'light'


def classify_3bet_intent(*, hero_cards, gto: Optional[dict] = None) -> Optional[dict]:
    """Intenção de um 3-BET preflop do hero: valor / merge / light(blefe).

    Retorna {intent, tier, justified} ou None (sem cartas).
      intent: value_3bet | merge_3bet | light_3bet
      justified: True/False se há veredito GTO; None se sem cobertura (light precisa de
                 read de fold equity — não dá pra cravar leak sem o range).
    """
    tier = threebet_strength_tier(hero_cards)
    if tier is None:
        return None
    intent = {'value': 'value_3bet', 'merge': 'merge_3bet', 'light': 'light_3bet'}[tier]
    gl = (gto or {}).get('gto_label')
    if gl in ('gto_correct', 'gto_mixed'):
        justified = True
    elif gl in ('gto_minor', 'gto_critical'):
        justified = False
    else:
        justified = None
    return {'intent': intent, 'tier': tier, 'justified': justified}


def explain_recommendation(*, best_action: str, hero_cards, board,
                           equity: Optional[float], equity_adj: Optional[float],
                           position: str, n_opponents: Optional[int],
                           facing_bb: Optional[float], required_equity: Optional[float],
                           street: str) -> Optional[dict]:
    """Racional CONCISO (chave i18n + params) de POR QUE a ação recomendada é essa, em
    spots postflop — sobretudo os heurísticos (sem GTO), onde não há barras de estratégia
    pra explicar. Determinístico, espelha a lógica do engine (força de mão + projeto +
    board + nº de oponentes + pot odds). O frontend renderiza via `card.rationale.<key>`.

    Retorna {key, params} ou None (não-postflop / sem ação)."""
    act = (best_action or '').lower().strip()
    st  = (street or '').lower().strip()
    if st not in ('flop', 'turn', 'river') or not act:
        return None

    cat         = made_hand_category(hero_cards, board)        # value | middle | air
    strong_draw = float(equity_adj or 0.0) >= 0.15
    wet         = _board_wet(board)
    mw          = int(n_opponents or 1) > 1
    params      = {'eq': round(float(equity or 0.0) * 100)}
    if mw:
        params['n'] = int(n_opponents or 1) + 1                 # "3-way" = 3 jogadores
    if required_equity:
        params['req'] = round(float(required_equity) * 100)

    if act in ('check', 'checks'):
        if cat == 'value' and not (wet and st != 'river'):
            key = 'check_strong'
        else:
            key = 'check_marginal_mw' if mw else 'check_marginal'
    elif act in ('bet', 'bets'):
        if cat == 'value':
            key = 'bet_protection' if (wet and st != 'river') else 'bet_value'
        elif strong_draw:
            key = 'bet_semibluff'
        else:
            key = 'bet_thin'
    elif act in ('call', 'calls'):
        key = 'call_odds'
    elif act in ('fold', 'folds'):
        key = 'fold_no_odds'
    elif act in ('raise', 'raises'):
        key = 'raise_semibluff' if (strong_draw and cat != 'value') else 'raise_value'
    elif act in ('allin', 'all-in', 'all_in', 'jam', 'shove'):
        key = 'shove_commit'
    else:
        return None

    return {'key': key, 'params': params, 'action': act}
