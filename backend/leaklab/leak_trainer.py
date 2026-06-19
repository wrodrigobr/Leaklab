"""
Leak Trainer — treinador adaptativo de leaks (substitui o Sparring de replay).

Identifica ONDE o jogador perde EV (get_leak_categories, baseado em gto_label) e
apresenta SPOTS GTO CANÔNICOS dessas categorias — cenários representativos limpos,
NÃO as mãos reais do jogador. Cada spot é resolvido/avaliado 100% por dado
pré-capturado (analyze_preflop) — ZERO solve ao vivo (política AGPL).

Generaliza o blueprint de academy_gto_preflop: gera spot sintético, valida cobertura
via analyze_preflop, ecoa um `spot` stateless e gradeia no servidor. As respostas
nunca vão ao cliente até o /grade.

MVP = preflop (rfi / vs_rfi / vs_3bet — totalmente cobertos pelas ranges). Postflop
fica para a Fase 2 (catálogo canônico pré-solvado offline).
"""
from __future__ import annotations

import random

from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.academy_gto_preflop import _HANDS, _hand_to_cards, _ACTION_ORDER

# Tiers de frequência (mesma régua do drill em app.py player_drill_submit).
CORRECT_FREQ = 0.30   # ação GTO primária
MIN_FREQ     = 0.10   # ação ainda na mistura GTO (defensável)

# Stacks "profundos" — evitam o fallback push/fold (jam) e mantêm fold/call/raise limpos.
_STACKS = [30, 40, 50, 75, 100]

# Cenários cobertos no MVP e o sizing/contexto canônico de cada um.
_SCENARIOS = ('rfi', 'vs_rfi', 'vs_3bet')

# Rótulo da ação "raise" por cenário (abrir / 3-bet / 4-bet) — só display.
_RAISE_LABEL = {'rfi': 'raise', 'vs_rfi': 'raise', 'vs_3bet': 'raise'}


# ── Normalização de ação ────────────────────────────────────────────────────────
def _norm_action(a: str) -> str:
    a = (a or '').strip().lower()
    if a in ('shove', 'jam', 'allin', 'all-in', 'all_in'):
        return 'jam'
    if a.startswith('raise') or a in ('3bet', '4bet'):
        return 'raise'
    if a.startswith('bet'):
        return 'raise'   # preflop não existe "bet": abrir é raise
    return a


def _norm_freqs(hand_freq: dict) -> dict:
    """{call,raise,allin,fold} → chaves do vocabulário dos botões (allin→jam)."""
    out: dict = {}
    for k, v in (hand_freq or {}).items():
        nk = _norm_action(k)
        out[nk] = out.get(nk, 0.0) + float(v or 0)
    return out


# ── Setup de cada cenário p/ analyze_preflop ────────────────────────────────────
def _scenario_inputs(scenario: str, position: str, vs_position: str) -> dict:
    """Parâmetros canônicos de analyze_preflop por cenário (sizing fixo + flags)."""
    if scenario == 'vs_rfi':
        return dict(position=position, vs_position=vs_position, facing_size=2.2,
                    is_3bet_pot=False, hero_was_aggressor=False, facing_raises=1)
    if scenario == 'vs_3bet':
        # hero ABRIU (opener=position) e enfrenta um 3-bet de vs_position. Precisa
        # hero_was_aggressor=True senão analyze_preflop cai em vs_rfi (range errado).
        return dict(position=position, vs_position=vs_position, facing_size=8.0,
                    is_3bet_pot=True, hero_was_aggressor=True, facing_raises=1)
    # rfi
    return dict(position=position, vs_position='', facing_size=0.0,
                is_3bet_pot=False, hero_was_aggressor=False, facing_raises=0)


def _scenario_of(category: dict) -> str | None:
    """Deriva o cenário canônico de uma linha de get_leak_categories (best-effort;
    a cobertura real é confirmada por analyze_preflop em generate_canonical_spot)."""
    rf = int(category.get('raises_faced') or 0)
    vp = (category.get('vs_position') or '').strip()
    if rf <= 0:
        return 'rfi'
    if rf == 1:
        return 'vs_3bet' if (vp and int(category.get('is_3bet') or 0)) else 'vs_rfi'
    if rf >= 2:
        return 'vs_3bet' if vp else None   # faces_squeeze (rf>=2 sem aggressor) não é coberto
    return None


def _stack_bucket(avg_stack: float) -> int:
    """Snap p/ o bucket profundo mais próximo (mantém opções limpas)."""
    s = float(avg_stack or 30)
    return min(_STACKS, key=lambda b: abs(b - s))


def _category_key(scenario: str, position: str, vs_position: str, stack: int) -> str:
    return f"{scenario}:{position}:{vs_position or '-'}:{stack}"


def _category_label(scenario: str, position: str, vs_position: str) -> str:
    if scenario == 'rfi':
        return f"{position} RFI"
    if scenario == 'vs_rfi':
        return f"{position} vs {vs_position} open"
    return f"{position} (opener) vs {vs_position} 3-bet"


# ── Currículo (categorias de leak ranqueadas) ───────────────────────────────────
def build_curriculum(user_id: int, days: int = 90) -> list[dict]:
    """Ranqueia as categorias canônicas onde o jogador mais perde EV. Sem dados →
    currículo de fundamentos (RFI por posição) p/ usuário novo."""
    from database.repositories import get_leak_categories
    rows = get_leak_categories(user_id, days)

    cats: list[dict] = []
    seen: set = set()
    for r in rows:
        scenario = _scenario_of(r)
        if scenario not in _SCENARIOS:
            continue
        position    = (r.get('position') or '').strip()
        vs_position = (r.get('vs_position') or '').strip()
        if scenario != 'rfi' and not vs_position:
            continue
        stack = _stack_bucket(r.get('avg_stack_bb'))
        key   = _category_key(scenario, position, vs_position, stack)
        if key in seen:
            continue
        seen.add(key)
        cats.append({
            'key':          key,
            'scenario':     scenario,
            'position':     position,
            'vs_position':  vs_position,
            'stack_bucket': stack,
            'weight':       float(r.get('priority_score') or 0.0),
            'n':            int(r.get('n') or 0),
            'label':        _category_label(scenario, position, vs_position),
        })

    if not cats:
        cats = _fundamentals()
    return cats


def _fundamentals() -> list[dict]:
    """Currículo padrão (RFI por posição) quando não há leaks suficientes."""
    out = []
    for pos in ['UTG', 'HJ', 'CO', 'BTN', 'SB']:
        out.append({
            'key':          _category_key('rfi', pos, '', 50),
            'scenario':     'rfi', 'position': pos, 'vs_position': '',
            'stack_bucket': 50, 'weight': 1.0, 'n': 0,
            'label':        _category_label('rfi', pos, ''),
        })
    return out


# ── Geração de spot canônico ────────────────────────────────────────────────────
def generate_canonical_spot(category: dict, max_tries: int = 40) -> dict | None:
    """Gera um spot concreto da categoria: fixa position/vs_position/stack, sorteia
    a MÃO, e VALIDA cobertura via analyze_preflop. None se a categoria não produz
    spot coberto (caller pula). Não revela a resposta."""
    scenario = category['scenario']
    position = category['position']
    vs_pos   = category.get('vs_position') or ''
    stack    = int(category.get('stack_bucket') or 50)
    inp      = _scenario_inputs(scenario, position, vs_pos)

    for _ in range(max_tries):
        hand = random.choice(_HANDS)
        res = analyze_preflop(position, hand, float(stack), 'fold',
                              facing_size=inp['facing_size'], vs_position=inp['vs_position'],
                              is_3bet_pot=inp['is_3bet_pot'],
                              hero_was_aggressor=inp['hero_was_aggressor'],
                              facing_raises=inp['facing_raises'])
        if not res.get('available') or res.get('scenario') != scenario:
            continue
        rec = res.get('recommended_actions') or []
        # evita spots cuja ação dominante caiu em jam (fora das opções limpas)
        if rec and _norm_action(rec[0]) == 'jam':
            continue
        return _build_spot(category, scenario, position, vs_pos, stack, hand, inp, res)
    return None


def _build_spot(category, scenario, position, vs_pos, stack, hand, inp, res) -> dict:
    facing = inp['facing_size']
    # pote em bb pra display (blinds + facing): aproximação leve, só visual.
    pot_bb = round(1.5 + (facing if facing else (1.0 if scenario == 'rfi' else 0.0)), 1)
    return {
        'street':       'preflop',
        'hero_cards':   _hand_to_cards(hand),
        'board':        None,
        'position':     position,
        'vs_position':  vs_pos or None,
        'num_players':  9,
        'stack_bb':     stack,
        'pot_size':     pot_bb,
        'facing_bet':   round(facing, 1) if facing else 0.0,
        'is_3bet':      bool(inp['is_3bet_pot']),
        'm_ratio':      None,
        'icm_pressure': None,
        'best_action':  _norm_action((res.get('recommended_actions') or ['fold'])[0]),
        'category_label': category.get('label'),
        # echo stateless p/ o /grade (sem decision_id; range fica no servidor)
        'spot': {
            'scenario':           scenario,
            'category':           category['key'],
            'position':           position,
            'vs_position':        vs_pos,
            'stack_bb':           stack,
            'facing_size':        facing,
            'is_3bet_pot':        inp['is_3bet_pot'],
            'hero_was_aggressor': inp['hero_was_aggressor'],
            'facing_raises':      inp['facing_raises'],
            'hand':               hand,
        },
    }


# ── Grading ─────────────────────────────────────────────────────────────────────
def grade_canonical_spot(spot: dict, action: str) -> dict:
    """Avalia a ação JOGADA via analyze_preflop, no formato DrillSubmitResult (o
    CoachCard consome direto). gto_freq = frequência da ação JOGADA."""
    played = _norm_action(action)
    res = analyze_preflop(
        spot.get('position', ''),
        spot.get('hand', ''),
        float(spot.get('stack_bb', 50) or 50),
        played,
        facing_size=float(spot.get('facing_size', 0) or 0),
        vs_position=spot.get('vs_position', '') or '',
        is_3bet_pot=bool(spot.get('is_3bet_pot', False)),
        hero_was_aggressor=bool(spot.get('hero_was_aggressor', False)),
        facing_raises=int(spot.get('facing_raises', 0) or 0),
    )
    freqs = _norm_freqs(res.get('hand_freq') or {})
    strategy = sorted(
        ({'action': k, 'frequency': round(v, 4)} for k, v in freqs.items() if v > 0.001),
        key=lambda x: -x['frequency'],
    )
    best_action = _norm_action((res.get('recommended_actions') or ['fold'])[0])
    gto_freq    = freqs.get(played, 0.0)

    if not res.get('available'):
        # spot sem cobertura (não deveria acontecer p/ spot validado) — neutro/honesto
        return {
            'is_correct': False, 'best_action': best_action, 'new_action': played,
            'gto_freq': 0.0, 'mixed': False, 'gto_tier': 'error',
            'gto_strategy': strategy, 'validation_source': 'heuristic',
            'delta': 0.0, 'new_score': 0.0, 'original_score': 0.0,
            'next_drill_at': None, 'srs_interval_days': None,
        }

    is_correct = gto_freq >= MIN_FREQ
    gto_tier   = 'correct' if gto_freq >= CORRECT_FREQ else ('deviation' if is_correct else 'error')
    mixed      = is_correct and played != best_action
    return {
        'is_correct':        is_correct,
        'best_action':       best_action,
        'new_action':        played,
        'gto_freq':          round(gto_freq, 4),
        'mixed':             mixed,
        'gto_tier':          gto_tier,
        'gto_strategy':      strategy,
        'validation_source': 'gto_range',
        'delta':             0.0,
        'new_score':         0.0,
        'original_score':    0.0,
        'next_drill_at':     None,
        'srs_interval_days': None,
    }


# ── Seleção adaptativa do próximo spot ──────────────────────────────────────────
def _adapt_factor(state: dict) -> float:
    hits   = int((state or {}).get('hits', 0))
    misses = int((state or {}).get('misses', 0))
    return max(0.1, 1.0 + 2.0 * misses - 0.5 * hits)


def next_spot(curriculum: list[dict], session_state: dict | None = None,
              rng: random.Random | None = None) -> dict | None:
    """Escolhe a próxima categoria (peso base × fator adaptativo da sessão) e gera o
    spot. Streak de acertos ≥3 numa categoria sobe o stack_bucket (mais raso/difícil)."""
    if not curriculum:
        return None
    rng = rng or random
    ss = session_state or {}

    weights = []
    for cat in curriculum:
        st = ss.get(cat['key'], {})
        weights.append(max(0.01, cat.get('weight', 1.0) * _adapt_factor(st)))

    # weighted pick (tenta gerar; se a categoria não produz spot coberto, tenta a próxima)
    order = sorted(range(len(curriculum)), key=lambda i: -weights[i] * (0.5 + rng.random()))
    for i in order:
        cat = dict(curriculum[i])
        st  = ss.get(cat['key'], {})
        if int(st.get('hit_streak', 0)) >= 3:
            harder = [b for b in _STACKS if b < cat['stack_bucket']]
            if harder:
                cat['stack_bucket'] = max(harder)
        spot = generate_canonical_spot(cat)
        if spot:
            return spot
    return None
