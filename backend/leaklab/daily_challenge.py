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


# ── Explicação didática do veredito (gerada na criação, vetada pelo admin) ────────
# Um "professor de MTT" explicando POR QUE a decisão é essa. Gerada UMA vez por spot,
# guardada no pool e revisada pelo admin ANTES de ir ao ar (mesma lógica de vetar o
# gabarito). Ancorada nos dados REAIS (mix GTO + contexto), não inventa números/cartas.
_EXPLAIN_CACHE: dict = {}

_SCENARIO_PT = {
    'rfi':     "abertura (RFI): a ação foldou até o herói e ele decide se rouba os blinds",
    'vs_rfi':  "defesa contra um open (RFI): alguém abriu e o herói decide como reagir",
    'vs_3bet': "o herói abriu e agora enfrenta um 3-bet",
}


def _explain_prompt(spot: dict, ctx: dict) -> dict:
    """Monta o payload do LLM. System = persona + regras de ancoragem; user = os fatos
    REAIS do spot (cenário, posição, stack, mão, mix GTO). O modelo só EXPLICA, não decide."""
    from leaklab.llm_explainer import _POKER_TERMS_EN
    mix = ', '.join(f"{l['action']} {round(l['freq'] * 100)}%" for l in ctx.get('gto_strategy') or [])
    facts = (
        f"Cenário: {_SCENARIO_PT.get(spot.get('scenario'), spot.get('scenario'))}.\n"
        f"Posição do herói: {spot.get('position')}.\n"
        + (f"Posição do vilão: {spot.get('vs_position')}.\n" if spot.get('vs_position') else "")
        + f"Stack efetivo: {spot.get('stack_bb')}bb.\n"
        f"Mão do herói: {spot.get('hand')} ({ctx.get('hand_class')}).\n"
        f"Decisão GTO (gabarito): {ctx.get('best_action')}.\n"
        f"Estratégia GTO completa (frequências): {mix}.\n"
        f"É contraintuitivo (a aparência da mão engana): {'sim' if ctx.get('counterintuitive') else 'não'}.\n"
        f"Resumo estratégico interno (semente, pode reescrever): {ctx.get('why')}"
    )
    system = (
        "Você é um coach de poker de torneios (MTT) de altíssimo nível explicando um spot para "
        "um aluno intermediário, no tom de um bom professor: claro, direto, motivador e concreto. "
        "Sua tarefa é EXPLICAR por que a decisão GTO informada é a correta, para o aluno entender "
        "o RACIOCÍNIO, não só o resultado.\n"
        "REGRAS DE ANCORAGEM (obrigatórias):\n"
        "- Use SOMENTE os fatos fornecidos. NUNCA invente cartas, board, posições, números, stack "
        "ou frequências diferentes dos informados. Você não recebe o board (é preflop).\n"
        "- Explique o PORQUÊ estratégico com os fatores certos: posição e quantos jogadores faltam "
        "agir, profundidade do stack (fold equity e playability mudam com a profundidade), força e "
        "playability da mão, o range do vilão, blockers quando fizer sentido. Conecte à profundidade "
        "do stack sempre que ela for decisiva (a mesma mão pode mudar de decisão em outro stack).\n"
        "- Se a estratégia GTO for MISTA (mais de uma ação com frequência relevante), explique a "
        "tensão: por que o GTO não faz sempre a mesma coisa aqui.\n"
        "- Se for contraintuitivo, aponte a ARMADILHA: por que a mão engana e o erro típico do "
        "jogador nesse spot.\n"
        "CONTEÚDO E FORMA:\n"
        "- 3 a 5 frases, um único parágrafo corrido. Sem títulos, sem bullets, sem markdown.\n"
        "- Linguagem intuitiva, sem despejar jargão. Explique o conceito, não a fórmula interna.\n"
        "- Não comece com 'Correto'/'Erro' nem repita o gabarito seco; vá direto ao raciocínio.\n"
        f"{_POKER_TERMS_EN} "
        "Responda em português do Brasil. Devolva SOMENTE o parágrafo, sem aspas."
    )
    return {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 500,
        'system':     system,
        'messages':   [{'role': 'user', 'content': facts}],
    }


def _fallback_explanation(spot: dict, ctx: dict) -> str:
    """Sem LLM (sem API key / erro): explicação determinística a partir do contexto.
    Honesta e útil, só menos fluida que a do modelo."""
    return ctx.get('why') or ''


def explain_challenge(spot: dict, ctx: dict | None = None) -> str:
    """Explicação didática do veredito pro spot (gerada na criação). Cache por (mão+spot).
    Fallback determinístico se o LLM estiver indisponível. NUNCA levanta."""
    ctx = ctx or describe_challenge(spot)
    key = f"{spot.get('scenario')}:{spot.get('position')}:{spot.get('vs_position')}:{spot.get('stack_bb')}:{spot.get('hand')}"
    if key in _EXPLAIN_CACHE:
        return _EXPLAIN_CACHE[key]
    try:
        from leaklab.llm_explainer import _call_llm_api
        out = (_call_llm_api(_explain_prompt(spot, ctx)) or '').strip()
        if len(out) >= 2 and out[0] in '"“' and out[-1] in '"”':
            out = out[1:-1].strip()
        out = out or _fallback_explanation(spot, ctx)
    except Exception:
        out = _fallback_explanation(spot, ctx)
    _EXPLAIN_CACHE[key] = out
    return out


def build_candidates(n: int = 10, rng: _random.Random | None = None,
                     with_explanation: bool = True) -> list[dict]:
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
        cand = {
            'spot_json': json.dumps(spot),
            'answer':    answer,
            'note':      _note(spot, answer, freq),
        }
        if with_explanation:
            # explicação didática gerada JÁ na criação (o admin revisa antes de aprovar)
            cand['explanation'] = explain_challenge(spot, describe_challenge(spot))
        out.append(cand)
    return out


_RANKS = '23456789TJQKA'


def _parse_hand(hand: str):
    """'AKs'/'TT'/'76o' → (r1, r2, suited, pair) com r1 >= r2 (índice de rank)."""
    h = (hand or '').strip()
    if len(h) < 2:
        return None
    a, b = h[0].upper(), h[1].upper()
    if a not in _RANKS or b not in _RANKS:
        return None
    ia, ib = _RANKS.index(a), _RANKS.index(b)
    hi, lo = max(ia, ib), min(ia, ib)
    suited = h[2:].lower() == 's' if len(h) > 2 else False
    return hi, lo, suited, (ia == ib)


def _hand_class(hand: str) -> str:
    """Rótulo legível da classe da mão (pro admin entender a 'aparência')."""
    p = _parse_hand(hand)
    if not p:
        return hand
    hi, lo, suited, pair = p
    T = _RANKS.index('T')
    if pair:
        if hi >= T:  return 'par alto'
        if hi >= _RANKS.index('7'): return 'par médio'
        return 'par baixo'
    both_bw = lo >= T
    is_ace = hi == _RANKS.index('A')
    gap = hi - lo
    if suited:
        if both_bw:      return 'broadway suited'
        if is_ace:       return 'ás suited'
        if gap <= 1:     return 'suited connector'
        return 'suited'
    if both_bw:          return 'broadway offsuit'
    if is_ace:           return 'ás offsuit'
    return 'offsuit fraca'


def _looks_strong(hand: str) -> bool:
    """A mão 'parece' forte a olho nu (par alto, dois broadway, AK/AQ)?"""
    p = _parse_hand(hand)
    if not p:
        return False
    hi, lo, _s, pair = p
    T, Q, A = _RANKS.index('T'), _RANKS.index('Q'), _RANKS.index('A')
    if pair and hi >= T:              # TT+
        return True
    if hi == A and lo >= Q:           # AK, AQ
        return True
    return lo >= Q                    # QJ+ dois altos


def _looks_weak(hand: str) -> bool:
    p = _parse_hand(hand)
    if not p:
        return False
    hi, lo, _s, pair = p
    seven = _RANKS.index('7')
    if pair:
        return hi <= _RANKS.index('6')
    return lo <= seven and hi < _RANKS.index('Q')


_PT_ACT = {'fold': 'dá fold', 'call': 'paga', 'allin': 'dá shove'}


def _pt_action(action: str, scenario: str) -> str:
    a = _norm(action)
    if a == 'raise':
        return {'vs_3bet': 'dá 4-bet', 'vs_rfi': 'dá 3-bet'}.get(scenario, 'abre')
    return _PT_ACT.get(a, a)


# Verbo conjugado pra construção "... abre em 85% e folda em 15%" (soa natural em PT).
_PT_VERB = {'fold': 'folda', 'call': 'paga', 'check': 'dá check', 'allin': 'shova'}


def _pt_verb(action: str, scenario: str) -> str:
    a = _norm(action)
    if a == 'raise':
        return {'vs_3bet': 'dá 4-bet', 'vs_rfi': 'dá 3-bet'}.get(scenario, 'abre')
    return _PT_VERB.get(a, a)


def describe_challenge(spot_json) -> dict:
    """Contexto RICO pra curadoria do admin (determinístico, derivado do range GTO):
    mix completo, classe da mão, se é CONTRAINTUITIVO, um score de 'quão desafio é' e
    o 'porquê' em texto. Não vaza pro jogador, é só a tela de aprovação."""
    spot = json.loads(spot_json) if isinstance(spot_json, str) else spot_json
    g = grade_canonical_spot(spot, 'fold')
    legs = [{'action': _norm(s['action']), 'freq': round(float(s['freq']), 4)}
            for s in (g.get('gto_strategy') or []) if float(s.get('freq') or 0) > 0.01]
    scenario = spot.get('scenario', '')
    hand = spot.get('hand', '')
    klass = _hand_class(hand)
    top = legs[0] if legs else {'action': _norm(g.get('best_action') or 'fold'), 'freq': 1.0}
    second = legs[1] if len(legs) > 1 else None
    top_freq = float(top['freq'])
    second_freq = float(second['freq']) if second else 0.0
    answer = top['action']

    # Contraintuitivo = a aparência da mão contradiz o gabarito (onde o jogador erra).
    ci_fold = answer == 'fold' and _looks_strong(hand)
    ci_attack = answer in ('raise', 'allin') and _looks_weak(hand)
    counterintuitive = bool(ci_fold or ci_attack)

    # Score 0-100: quão DESAFIADOR (não quão certo). Dominante+óbvio = baixo; contraintuitivo
    # ou com mistura real = alto. Ajuda o admin a priorizar (o filtro só garante a CERTEZA).
    score = 25.0
    if counterintuitive:
        score += 45
    score += min(30.0, second_freq * 200)          # mistura de 15% → +30
    score += min(15.0, max(0.0, 0.95 - top_freq) * 150)   # perto da borda do range → +15
    score = int(min(100, round(score)))
    interest = 'alto' if score >= 65 else 'medio' if score >= 40 else 'baixo'

    # Frase(s) de contexto — cenário + gabarito + tensão + armadilha.
    ctx = {'rfi': f"Abertura de {spot.get('position')}.",
           'vs_rfi': f"{spot.get('position')} defende o open de {spot.get('vs_position')}.",
           'vs_3bet': f"{spot.get('position')} abriu e enfrenta o 3-bet de {spot.get('vs_position')}."
           }.get(scenario, scenario)
    if second and second_freq >= 0.10:
        # estratégia mista: "o GTO mistura: abre em 85% e folda nos outros 15%"
        parts = [f"{ctx} Com {hand} ({klass}), o GTO mistura: {_pt_verb(answer, scenario)} "
                 f"em {round(top_freq * 100)}% das vezes e {_pt_verb(second['action'], scenario)} "
                 f"nos outros {round(second_freq * 100)}%."]
    else:
        freq_word = "sempre" if top_freq >= 0.97 else "quase sempre"
        parts = [f"{ctx} O GTO {_pt_verb(answer, scenario)} {hand} ({klass}) {freq_word}."]
    if ci_fold:
        parts.append("A mão parece forte demais pra largar, é aí que o jogador paga demais.")
    elif ci_attack:
        parts.append("A mão parece fraca demais pra atacar, o tipo de linha fina que o jogador evita.")
    elif not counterintuitive and top_freq < 0.92 and second_freq < 0.10:
        parts.append("Está na borda do range, uma mão a menos e a decisão viraria.")

    return {
        'gto_strategy':     legs,
        'hand_class':       klass,
        'best_action':      answer,
        'top_freq':         round(top_freq, 4),
        'second_action':    second['action'] if second else None,
        'second_freq':      round(second_freq, 4),
        'counterintuitive': counterintuitive,
        'challenge_score':  score,
        'interest':         interest,
        'why':              ' '.join(parts),
    }


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
