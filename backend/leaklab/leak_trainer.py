"""
Leak Trainer — treinador adaptativo de leaks (spots GTO canônicos).

Substitui o Sparring (que replayava as mãos reais do jogador, confuso). Aqui:
  - o LEAK vem dos dados do jogador (get_leak_categories), mas
  - o SPOT é um cenário canônico/sintético limpo daquela categoria (não a mão real),
  - a correção é NO SERVIDOR contra a range GTO (reusa preflop_gto_ranges.analyze_preflop),
  - o próximo spot ADAPTA à performance (erra → super-representa; acerta → recua).

MVP preflop-only: 100% coberto pelas ranges GTO (sem solver, sem buracos de cobertura).
Só serve spots que consegue corrigir com autoridade — nunca um spot sem solução. A resposta
correta NUNCA vai ao cliente: /next manda só o contexto; o veredito só volta no /grade.

Postflop fica para a Fase 2 (catálogo pré-solvado offline). A arquitetura (categoria → gerar →
gradear → adaptar) já é desenhada para encaixar postflop só adicionando o branch + o catálogo.
"""
from __future__ import annotations

import random

from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.academy_gto_preflop import _HANDS, _hand_to_cards, _ACTION_ORDER

# Tiers de frequência (mesma régua do Ghost Table drill — player_drill_submit).
CORRECT_FREQ = 0.30   # ação jogada com freq GTO ≥ isto → acerto pleno
MIN_FREQ     = 0.10   # ≥ isto (e < CORRECT) → aceitável (GTO mistura aqui)

# Stacks limpos do treino (evitam o fallback push/fold). Espelha o academy.
_STACKS = [30, 40, 50, 75, 100]

# facing_size por cenário (espelha academy_gto_preflop._random_setup).
_FACING = {'rfi': 0.0, 'vs_rfi': 2.2, 'vs_3bet': 8.0}
_OPTIONS = {
    'rfi':     ['fold', 'raise'],
    'vs_rfi':  ['fold', 'call', 'raise'],
    'vs_3bet': ['fold', 'call', 'raise'],
}
_XP_BY_SCENARIO = {'rfi': 20, 'vs_rfi': 25, 'vs_3bet': 30}


def _leak_scenario(is_3bet: int, raises_faced: int) -> str | None:
    """Mapeia o contexto de um leak preflop para um dos 3 cenários treináveis.
      raises_faced 0           → rfi  (primeiro a agir)
      raises_faced 1, sem 3bet → vs_rfi (enfrenta 1 open)
      is_3bet OU raises_faced ≥2 → vs_3bet (enfrenta 3-bet/squeeze)
    """
    if is_3bet or raises_faced >= 2:
        return 'vs_3bet'
    if raises_faced == 1:
        return 'vs_rfi'
    if raises_faced == 0:
        return 'rfi'
    return None


def _snap_stack(avg_stack: float) -> int:
    """Snap pro stack treinável mais próximo (mantém o spot dentro da cobertura limpa)."""
    return min(_STACKS, key=lambda s: abs(s - (avg_stack or 50)))


def _category_key(cat: dict) -> str:
    return f"{cat['scenario']}:{cat['position']}:{cat.get('vs_position', '')}:{cat['stack_bb']}"


def build_curriculum(user_id: int, days: int = 90) -> list[dict]:
    """Currículo = categorias de leak do jogador mapeadas para cenários treináveis, com peso por EV
    perdido. Sem dados (usuário novo) → fundamentos (RFI por posição). Cada item:
      {scenario, position, vs_position, stack_bb, weight, ev_loss_bb, n, key}
    """
    from database.repositories import get_leak_categories
    raw = get_leak_categories(user_id, days=days)
    cats: list[dict] = []
    for r in raw:
        scenario = _leak_scenario(int(r.get('is_3bet') or 0), int(r.get('raises_faced') or 0))
        if scenario is None:
            continue
        ev = float(r.get('total_ev_loss_bb') or 0)
        cat = {
            'scenario':    scenario,
            'position':    r['position'],
            'vs_position': (r.get('vs_position') or '') if scenario != 'rfi' else '',
            'stack_bb':    _snap_stack(float(r.get('avg_stack_bb') or 50)),
            'ev_loss_bb':  round(ev, 2),
            'n':           int(r.get('n') or 0),
            # peso base = EV perdido (impacto), piso 0.5 p/ não zerar categorias de EV baixo
            'weight':      max(0.5, ev),
        }
        cat['key'] = _category_key(cat)
        cats.append(cat)
    base = cats if cats else _fundamentals_curriculum()
    return base + _postflop_pilot_cats()


def _postflop_pilot_cats() -> list[dict]:
    """Fase 2 (piloto): categoria postflop BB-defesa do catálogo validado. Peso modesto — fundamento de
    defesa OOP útil a todos. O leak-driven postflop (só se o user tem o leak) é refinamento futuro."""
    cat = {'kind': 'postflop', 'catalog': 'bb_defense', 'scenario': 'pf_bb_defense',
           'position': 'BB', 'vs_position': 'BTN', 'stack_bb': 40.0,
           'ev_loss_bb': 0.0, 'n': 0, 'weight': 2.0, 'key': 'pf:bb_defense'}
    return [cat]


def _fundamentals_curriculum() -> list[dict]:
    """Fallback p/ usuário sem leaks medidos: RFI por posição (fundamentos de abertura)."""
    cats = []
    for pos in ['UTG', 'HJ', 'CO', 'BTN', 'SB']:
        cat = {'scenario': 'rfi', 'position': pos, 'vs_position': '', 'stack_bb': 50,
               'ev_loss_bb': 0.0, 'n': 0, 'weight': 1.0}
        cat['key'] = _category_key(cat)
        cats.append(cat)
    return cats


def generate_canonical_spot(category: dict, rng: random.Random | None = None) -> dict | None:
    """Gera um spot canônico da categoria: FIXA position/vs_position/stack e randomiza só a MÃO
    (de _HANDS). Valida cobertura via analyze_preflop (available + scenario bate). Retorna o spot
    stateless (sem resposta) ou None se a categoria não produz spot coberto (caller pula)."""
    rng = rng or random
    if category.get('kind') == 'postflop':           # Fase 2: catálogo postflop pré-solvado
        return generate_postflop_spot(category, rng)
    scenario = category['scenario']
    pos      = category['position']
    vs_pos   = category.get('vs_position', '') or ''
    stack    = int(category.get('stack_bb', 50) or 50)
    facing   = _FACING.get(scenario, 0.0)
    is_3b    = scenario == 'vs_3bet'
    opts     = _OPTIONS.get(scenario, ['fold', 'raise'])

    hands = _HANDS[:]
    rng.shuffle(hands)
    for hand in hands[:40]:
        res = analyze_preflop(pos, hand, float(stack), 'fold',
                              facing_size=facing, vs_position=vs_pos, is_3bet_pot=is_3b)
        if not res.get('available') or res.get('scenario') != scenario:
            continue
        rec = res.get('recommended_actions') or []
        if rec and rec[0] not in opts:   # ação dominante fora das opções limpas (ex.: jam)
            continue
        return {
            'scenario':    scenario,
            'category':    category['key'],
            'position':    pos,
            'vs_position': vs_pos,
            'stack_bb':    stack,
            'facing_size': facing,
            'is_3bet_pot': is_3b,
            'hand':        hand,
            'hero_cards':  _hand_to_cards(hand),
            'options':     opts,
            'xp_value':    _XP_BY_SCENARIO.get(scenario, 20),
        }
    return None


def _norm_action(a: str) -> str:
    a = (a or '').strip().lower()
    return 'allin' if a in ('jam', 'shove', 'all-in', 'allin') else a


def grade_canonical_spot(spot: dict, action: str) -> dict:
    """Avalia a ação NO SERVIDOR via analyze_preflop e devolve no formato que o CoachCard lê
    (gto_strategy = mix por ação; gto_freq = freq da AÇÃO JOGADA; gto_tier = correct/mixed/error)."""
    if spot.get('kind') == 'postflop' or spot.get('board'):   # Fase 2: lê nó pré-solvado (não solva)
        g = grade_postflop_spot(spot, action)
        if g is not None:
            return g
        # sem tabela por-mão (não deveria no catálogo validado) → não pune
        return {'is_correct': True, 'gto_tier': 'correct', 'mixed': False, 'gto_freq': 1.0,
                'gto_strategy': [], 'best_action': '', 'new_action': _norm_action(action),
                'recommended': [], 'validation_source': 'gto_solver_postflop', 'xp_value': 0,
                'new_score': 0.0, 'original_score': 0.0, 'delta': 0.0,
                'next_drill_at': None, 'srs_interval_days': 0, 'ungradeable': True}
    played = _norm_action(action)
    res = analyze_preflop(
        spot.get('position', ''),
        spot.get('hand', ''),
        float(spot.get('stack_bb', 50) or 50),
        played if played != 'allin' else 'allin',
        facing_size=float(spot.get('facing_size', 0) or 0),
        vs_position=spot.get('vs_position', '') or '',
        is_3bet_pot=bool(spot.get('is_3bet_pot', False)),
    )
    hf = res.get('hand_freq') or {}
    # mix de estratégia (% por ação não-zero), ordenado por freq desc
    gto_strategy = [
        {'action': ('allin' if k == 'jam' else k), 'freq': round(float(v), 4)}
        for k, v in sorted(hf.items(), key=lambda x: -x[1]) if v and v > 0.01
    ]
    # freq da AÇÃO JOGADA (normaliza jam→allin pros dois lados)
    played_freq = 0.0
    for k, v in hf.items():
        if _norm_action(k) == played:
            played_freq = float(v or 0)
            break
    # Contrato do DrillSubmitResult (que o CoachCard consome): gto_tier correct/error + mixed bool.
    # mixed = acerto numa linha co-ótima (freq ≥ MIN mas < CORRECT) — não é a ação #1, mas o GTO mistura.
    if played_freq >= CORRECT_FREQ:
        tier, is_correct, mixed = 'correct', True, False
    elif played_freq >= MIN_FREQ:
        tier, is_correct, mixed = 'correct', True, True
    else:
        tier, is_correct, mixed = 'error', False, False
    rec = res.get('recommended_actions') or ['fold']
    return {
        'is_correct':       is_correct,
        'gto_tier':         tier,
        'mixed':            mixed,
        'gto_freq':         round(played_freq, 4),
        'gto_strategy':     gto_strategy,
        'best_action':      ('allin' if rec[0] == 'jam' else rec[0]),
        'new_action':       played,
        'recommended':      rec,
        'hand_freq':        hf,
        'range_pct':        res.get('range_pct'),
        'validation_source': 'gto_range',   # preflop = range GTO (não solver hand-aware)
        'xp_value':         spot.get('xp_value', 20),
        # campos SRS no-op (spot sintético não está em drill_sessions) — só p/ o contrato do CoachCard
        'new_score':        0.0,
        'original_score':   0.0,
        'delta':            0.0,
        'next_drill_at':    None,
        'srs_interval_days': 0,
    }


def next_spot(curriculum: list[dict], session_state: dict | None = None,
              rng: random.Random | None = None) -> dict | None:
    """Escolhe a próxima categoria por peso adaptativo e gera o spot canônico. Peso efetivo =
    base × adapt, adapt = clamp(1 + 2*misses − 0.5*hits, ≥0.1) (erra → super-representa; acerta →
    recua). Streak de 3 acertos numa categoria → sobe pra um stack mais raso (mais difícil)."""
    rng = rng or random
    state = session_state or {}
    if not curriculum:
        return None

    pool = []
    for cat in curriculum:
        st = state.get(cat['key'], {})
        misses = int(st.get('misses', 0))
        hits   = int(st.get('hits', 0))
        adapt  = max(0.1, 1.0 + 2.0 * misses - 0.5 * hits)
        # 3 acertos seguidos → endurece (stack mais raso), uma vez
        cat2 = dict(cat)
        if hits >= 3 and cat2['stack_bb'] in _STACKS:
            i = _STACKS.index(cat2['stack_bb'])
            cat2['stack_bb'] = _STACKS[max(0, i - 1)]
        pool.append((cat2, cat['weight'] * adapt))

    total = sum(w for _, w in pool) or 1.0
    pick = rng.uniform(0, total)
    acc = 0.0
    chosen = pool[0][0]
    for cat, w in pool:
        acc += w
        if pick <= acc:
            chosen = cat
            break

    # tenta gerar; se a categoria escolhida não der spot coberto, tenta as outras por peso desc
    spot = generate_canonical_spot(chosen, rng)
    if spot:
        return spot
    for cat, _ in sorted(pool, key=lambda x: -x[1]):
        if cat is chosen:
            continue
        spot = generate_canonical_spot(cat, rng)
        if spot:
            return spot
    return None


# ── Fase 2: POSTFLOP (catálogo pré-solvado + validado offline) ────────────────────────────────
# Spots VALIDADOS por scripts/seed_leaktrainer_postflop.py (hero OOP, ranges reais do GW, exploitability
# <3%, estratégia POR MÃO coerente). NUNCA solva ao vivo no request path — o grade só LÊ o nó pré-solvado
# (lookup_gto block_remote=False). Nó/hand_strategy ausente → spot não-gradeável (pulado, nunca servido
# errado). BB defesa vs BTN open, flop SRP, 40bb, c-bet ~33% (1.65bb).
_BBDEF_PARAMS = {
    'position': 'BB', 'vs_position': 'BTN', 'stack_bb': 40.0,
    'facing_size_bb': 1.65, 'pot_bb': 5.0, 'street': 'flop',
}
POSTFLOP_CATALOG = {
    'bb_defense': [
        {'board': ['Kd', '7c', '2s'], 'hand': ['Kh', 'Qc']},   # top pair bom kicker
        {'board': ['Kd', '7c', '2s'], 'hand': ['Kh', 'Ts']},   # top pair fraco
        {'board': ['Kd', '7c', '2s'], 'hand': ['7h', '6d']},   # par medio
        {'board': ['Ad', '6c', '3s'], 'hand': ['Kh', 'Qd']},   # overs (air)
        {'board': ['Ad', '6c', '3s'], 'hand': ['6h', '5d']},   # par medio + gutshot
        {'board': ['Qd', '7s', '4h'], 'hand': ['Kh', 'Qc']},   # top pair
        {'board': ['Qd', '7s', '4h'], 'hand': ['Js', 'Td']},   # overs + gutshot
        {'board': ['Qd', '7s', '4h'], 'hand': ['Ac', '4d']},   # bottom pair + A
        {'board': ['9h', '8h', '5c'], 'hand': ['Th', '9c']},   # par + draw
        {'board': ['9h', '8h', '5c'], 'hand': ['Jd', 'Tc']},   # OESD
        {'board': ['9h', '8h', '5c'], 'hand': ['7d', '6c']},   # straight feita
        {'board': ['Js', 'Ts', '4c'], 'hand': ['Qh', 'Jd']},   # top pair + OESD
        {'board': ['Js', 'Ts', '4c'], 'hand': ['Kd', 'Qc']},   # OESD
        {'board': ['Th', '9d', '6c'], 'hand': ['Qs', 'Jd']},   # OESD
        {'board': ['Th', '9d', '6c'], 'hand': ['Ah', 'Td']},   # top pair
        {'board': ['Kc', 'Kd', '4h'], 'hand': ['Js', 'Td']},   # air + gutshot (board pareado)
    ],
}
_POSTFLOP_OPTIONS = ['fold', 'call', 'raise']


def _cards_to_objs(cards):
    return [{'rank': c[0], 'suit': c[1].lower()} for c in cards if len(c) >= 2]


def _action_family(label: str) -> str:
    """Família da ação (agrega sizes): bet/raise/jam/allin → 'raise'; check → 'check'; fold/call iguais."""
    a = (label or '').strip().lower().split('_')[0]
    return {'bet': 'raise', 'jam': 'raise', 'allin': 'raise', 'shove': 'raise',
            'all-in': 'raise'}.get(a, a)


def generate_postflop_spot(category: dict, rng: random.Random | None = None) -> dict | None:
    """Retorna um spot do catálogo postflop (stateless, sem revelar a resposta)."""
    rng = rng or random
    spots = POSTFLOP_CATALOG.get(category.get('catalog', 'bb_defense')) or []
    if not spots:
        return None
    s = rng.choice(spots)
    p = _BBDEF_PARAMS
    return {
        'kind':           'postflop',
        'street':         p['street'],
        'category':       category['key'],
        'position':       p['position'],
        'vs_position':    p['vs_position'],
        'stack_bb':       p['stack_bb'],
        'facing_size_bb': p['facing_size_bb'],
        'pot_bb':         p['pot_bb'],
        'board':          s['board'],
        'board_cards':    _cards_to_objs(s['board']),
        'hand':           ''.join(s['hand']),
        'hero_hand':      s['hand'],
        'hero_cards':     _cards_to_objs(s['hand']),
        'options':        list(_POSTFLOP_OPTIONS),
        'xp_value':       30,
    }


def grade_from_hand_strategy(hand_strategy: dict, action: str) -> dict:
    """Gradeia a ação contra a estratégia DA MÃO (hand_strategy do solver). Tolerância de MÃO-FEITA:
    quando o GTO quase nunca folda (fold<5%), call E raise são ambos corretos (só fold é erro) — o
    solver capado (1 bet size) tende a estratégias puras (raise 100%), e punir 'call' num top pair seria
    injusto. Draws/air usam o tier normal (freq≥30% correto · ≥10% aceitável · <10% erro)."""
    acts = (hand_strategy or {}).get('actions') or {}
    fam: dict = {}
    for label, d in acts.items():
        b = _action_family(label)
        fam[b] = fam.get(b, 0.0) + float((d or {}).get('frequency') or 0)
    played = _action_family(action)
    played_freq = fam.get(played, 0.0)
    fold_freq = fam.get('fold', 0.0)
    gto_strategy = [{'action': b, 'freq': round(f, 4)}
                    for b, f in sorted(fam.items(), key=lambda x: -x[1]) if f > 0.01]

    made_hand = fold_freq < 0.05      # GTO praticamente nunca folda = mão que defende
    if made_hand and played in ('call', 'raise'):
        tier, is_correct, mixed = 'correct', True, (played_freq < CORRECT_FREQ)
    elif played_freq >= CORRECT_FREQ:
        tier, is_correct, mixed = 'correct', True, False
    elif played_freq >= MIN_FREQ:
        tier, is_correct, mixed = 'correct', True, True
    else:
        tier, is_correct, mixed = 'error', False, False
    best = (hand_strategy or {}).get('best_action') or (gto_strategy[0]['action'] if gto_strategy else 'fold')
    return {
        'is_correct':        is_correct,
        'gto_tier':          tier,
        'mixed':             mixed,
        'gto_freq':          round(played_freq, 4),
        'gto_strategy':      gto_strategy,
        'hand_freq':         {b: round(f, 4) for b, f in fam.items() if f > 0.001},
        'best_action':       _action_family(best),
        'new_action':        played,
        'recommended':       [b for b, _ in sorted(fam.items(), key=lambda x: -x[1])],
        'validation_source': 'gto_solver_postflop',
        'xp_value':          30,
        'new_score':         0.0, 'original_score': 0.0, 'delta': 0.0,
        'next_drill_at':     None, 'srs_interval_days': 0,
    }


def grade_postflop_spot(spot: dict, action: str) -> dict | None:
    """Lê o nó pré-solvado (NUNCA solva ao vivo) e gradeia a mão. None se sem tabela por-mão."""
    from leaklab.gto_solver import lookup_gto
    res = lookup_gto(
        street=spot.get('street', 'flop'), position=spot.get('position', 'BB'),
        board=spot.get('board') or [], hero_hand=spot.get('hero_hand') or [],
        hero_stack_bb=float(spot.get('stack_bb', 40) or 40),
        vs_position=spot.get('vs_position', 'BTN'),
        facing_size_bb=float(spot.get('facing_size_bb', 1.65) or 1.65),
        pot_bb=float(spot.get('pot_bb', 5.0) or 5.0), bb_chips=1.0,
        require_hand_aware=True, block_remote=False, allow_remote_solve=False,
    )
    hs = res.get('hand_strategy')
    if not hs or not hs.get('actions'):
        return None
    g = grade_from_hand_strategy(hs, action)
    g['exploitability_pct'] = res.get('exploitability_pct')
    return g
