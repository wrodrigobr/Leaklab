"""
Desafio do Dia (#42) — geração de CANDIDATOS por faixa de DIFICULDADE.

O padrão é `dificil`: o desafio existe pra separar quem sabe, e spot de resposta unânime é
respondido no automático. As faixas saem da frequência da ação líder do GTO (ver DOMINANT_FREQ
/ MEDIUM_FREQ / HARD_FREQ). O admin aprova cada candidato antes de virar desafio.

O que garante que um spot MISTO ainda vale como pergunta é `_discriminates`: tem que sobrar
alguma ação claramente errada no menu. Se toda opção fosse creditável, qualquer resposta viraria
"aceitável" e o desafio ensinaria que tanto faz. Punir a ação de 40% que o solver joga quase
metade das vezes seria o erro oposto — por isso quem corrige é `grade_challenge`, mixed-aware,
que responde "Aceitável (o GTO mistura aqui)".

A arquitetura de CERTEZA tem 5 camadas, e nada vai ao ar sem passar por todas:
  1. nó limpo (filtro anti-degenerado)          — `_certainty` via grade_canonical_spot
  2. ação com frequência conhecida               — as faixas DOMINANT/MEDIUM/HARD
  3. concordância entre fontes (só no fácil)     — solver == heurística local
  4. voto adversarial do LLM (N refutadores)     — `verify_challenge`
  5. aprovação humana do admin                   — status 'pending' no pool

Fase 2 restante (fora daqui): spots postflop do gto_nodes (#41).
"""
from __future__ import annotations
import json
import logging
import random as _random

_log = logging.getLogger(__name__)

from leaklab.leak_trainer import (CORRECT_FREQ, generate_canonical_spot,
                                  grade_canonical_spot)
from leaklab.preflop_range_evaluator import _recommended_action

# ── Dificuldade ──────────────────────────────────────────────────────────────────────────────
# O desafio nascia sempre FÁCIL por construção: só entrava spot com a ação top ≥85% E com a
# heurística local concordando com a range. Sobreviviam os spots mais óbvios do jogo.
#
# O medo original ("coin-flip é impossível gradear com certeza") está obsoleto: `grade_challenge`
# já é mixed-aware e responde "Aceitável (o GTO mistura aqui)". Dá pra usar spot misto sem punir
# quem escolhe a ação de 40%.
#
# O que um spot misto AINDA precisa ter pra valer como desafio: uma ação claramente ERRADA no
# menu. Se todas as opções são creditáveis, qualquer resposta é "aceitável" e a pergunta não
# mede nada. É esse o filtro que substitui a exigência de unanimidade.
DOMINANT_FREQ  = 0.85    # fácil: resposta praticamente unânime
MEDIUM_FREQ    = 0.60    # médio: existe uma ação líder, mas o GTO mistura de verdade
HARD_FREQ      = 0.40    # difícil: abaixo disso nenhuma ação lidera de forma útil
MIN_CREDITABLE = 0.10    # mesma régua do StrategyProvider (MIN_STRATEGY_FREQ)

DIFFICULTIES = ('facil', 'medio', 'dificil')
# Padrão DIFÍCIL: o desafio existe pra separar quem sabe. Spot de resposta unânime
# ("K5o no BTN vs open do CO") é respondido no automático e não mede nada — o nível
# fácil segue disponível, mas sob pedido explícito do admin.
DEFAULT_DIFFICULTY = 'dificil'

# Stack curto entrou: é onde a decisão de MTT vira difícil de verdade (a mesma mão é shove a
# 12bb e fold a 40bb). A grade antiga só tinha profundidade média, onde quase tudo é padrão.
_CH_STACKS = [12, 17, 20, 30, 40, 50]


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


def _discriminates(spot: dict, strat: list) -> bool:
    """O menu oferece ao menos uma ação claramente ERRADA?

    É o que faz um spot misto continuar valendo como pergunta. Se todas as opções são
    creditáveis (freq ≥ MIN_CREDITABLE), qualquer resposta vira "aceitável" e o desafio não
    mede nada — pior, ensina que tanto faz.
    """
    freq = {_norm(s.get('action')): float(s.get('freq') or 0) for s in strat}
    menu = [_norm(a) for a in (spot.get('options') or [])]
    if not menu:
        return False
    return any(freq.get(a, 0.0) < MIN_CREDITABLE for a in menu)


def _certainty(spot: dict, difficulty: str = 'dificil'):
    """Retorna (answer, top_freq, strategy, difficulty) se o spot serve de desafio.

    `facil`   — ação top ≥85% E a heurística local concorda (triangulação: é a rede de
                segurança da promessa "não erramos o gabarito").
    `medio`   — 60-85%: existe líder, mas o GTO mistura; a alternativa é creditada como
                aceitável pelo grader.
    `dificil` — 40-60%: nenhuma ação domina. Só entra se ainda houver ação claramente errada.

    Nos níveis médio/difícil a triangulação com a heurística NÃO é exigida: o gabarito é o
    StrategyProvider (fonte única). Exigir que uma segunda fonte concorde é justamente o que
    varria do pool todo spot interessante.
    """
    g = grade_canonical_spot(spot, 'fold')          # grade só pra ler a estratégia GTO
    strat = g.get('gto_strategy') or []
    if not strat:
        return None
    top = strat[0]
    top_action = _norm(top.get('action'))
    top_freq = float(top.get('freq') or 0)

    faixa = ('facil'   if top_freq >= DOMINANT_FREQ
             else 'medio'   if top_freq >= MEDIUM_FREQ
             else 'dificil' if top_freq >= HARD_FREQ
             else None)
    if faixa is None or faixa != difficulty:
        return None
    # Sem ação errada no menu, a pergunta não discrimina — vale para qualquer faixa.
    if not _discriminates(spot, strat):
        return None

    if difficulty == 'facil':
        # Triangulação: range GW == heurística local. Só no nível fácil.
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
    return top_action, round(top_freq, 4), strat, faixa


def _note(spot: dict, answer: str, freq: float) -> str:
    """Descrição legível pro admin curar."""
    sc = spot.get('scenario'); pos = spot.get('position'); vs = spot.get('vs_position')
    ctx = {'rfi': f"{pos} abre", 'vs_rfi': f"{pos} vs open de {vs}",
           'vs_3bet': f"{pos} abre e enfrenta 3-bet de {vs}"}.get(sc, sc)
    faixa = ('fácil' if freq >= DOMINANT_FREQ
             else 'médio' if freq >= MEDIUM_FREQ else 'difícil')
    return (f"[{faixa}] {ctx} · {spot.get('stack_bb')}bb · mão {spot.get('hand')} "
            f"→ GTO {answer} {round(freq*100)}%")


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


# ── Voto adversarial (camada 4 da arquitetura de certeza) ────────────────────────────────────
# O gabarito vem do solver e o admin aprova no fim. Entre os dois faltava um perito INDEPENDENTE
# perguntando "essa resposta é absurda?".
#
# A calibragem é o ponto delicado: um refutador agressivo mata justamente o spot DIFÍCIL, que
# parece errado de propósito. Por isso a barra é alta — só derruba o que é insustentável ou
# malformado, nunca o que é meramente contraintuitivo. E não pedimos frequência ao modelo (aí ele
# alucina número): pedimos juízo binário com motivo.
#
# N votos INDEPENDENTES com maioria, porque um voto único de LLM é ruidoso demais para vetar.
REFUTE_VOTES    = 3     # peritos independentes por candidato
REFUTE_MAJORITY = 2     # refutações necessárias para descartar
_REFUTE_CACHE: dict = {}


def _refute_prompt(spot: dict, ctx: dict, answer: str) -> dict:
    """Pede um juízo de sanidade sobre o gabarito: o modelo tenta DERRUBAR a resposta proposta.
    Não escolhe a jogada nem estima frequência — só julga se aquilo é defensável."""
    from leaklab.llm_explainer import _POKER_TERMS_EN
    mix = ', '.join(f"{l['action']} {round(l['freq'] * 100)}%" for l in ctx.get('gto_strategy') or [])
    facts = (
        f"Cenário: {_SCENARIO_PT.get(spot.get('scenario'), spot.get('scenario'))}.\n"
        f"Posição do herói: {spot.get('position')}.\n"
        + (f"Posição do vilão: {spot.get('vs_position')}.\n" if spot.get('vs_position') else "")
        + f"Stack efetivo: {spot.get('stack_bb')}bb.\n"
        f"Mão do herói: {spot.get('hand')}.\n"
        f"Ações disponíveis: {', '.join(spot.get('options') or [])}.\n"
        f"RESPOSTA DE REFERÊNCIA (a mais frequente do solver): {answer}.\n"
        f"Frequências do solver: {mix}."
    )
    system = (
        "Você é um jogador profissional de MTT revisando uma questão de treino ANTES de ir ao ar. "
        "Sua função é ADVERSARIAL: tentar derrubar a questão.\n"
        "COMO A QUESTÃO É CORRIGIDA (leia antes de julgar): a correção é MIXED-AWARE. O jogador "
        "que escolhe QUALQUER ação com frequência relevante no solver recebe 'Aceitável', não "
        "'Erro'. A 'resposta de referência' é só a mais frequente, NÃO a única aceita. Num spot "
        "54%/46%, quem escolhe a de 46% é creditado. Portanto a pergunta que você deve responder "
        "NÃO é 'esta é a única jogada certa?', e sim: 'esta questão é JUSTA e o spot é REAL?'\n"
        "BARRA ALTA — refute SOMENTE se: (a) a resposta de referência é indefensável mesmo como "
        "uma das linhas do solver, ou (b) o spot é impossível/malformado (posições incoerentes, "
        "stack impossível, ação fora do menu, frequências incoerentes com o spot).\n"
        "NÃO refute por: o GTO misturar entre ações (isso é NORMAL e já é creditado), ser "
        "contraintuitivo, ser apertado ou largo demais para o seu gosto, ou você preferir outra "
        "linha defensável. Questão difícil é o OBJETIVO: spot que parece errado e não é deve PASSAR.\n"
        "Na dúvida, NÃO refute — existe revisão humana depois de você, e derrubar questão boa "
        "custa mais do que deixar passar uma duvidosa.\n"
        f"{_POKER_TERMS_EN} "
        'Responda APENAS com JSON, sem markdown: {"refuta": true|false, "motivo": "uma frase"}'
    )
    return {
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 200,
        'system':     system,
        'messages':   [{'role': 'user', 'content': facts}],
    }


def _parse_refute(raw: str):
    """(refuta, motivo) ou None se a resposta não for interpretável.

    Voto ilegível NÃO conta para nenhum lado: some da apuração. Tratar resposta quebrada como
    veto derrubaria candidato bom por falha de parsing, que é ruído e não avaliação."""
    import re as _re
    if not raw:
        return None
    m = _re.search(r'\{.*\}', raw, _re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(d, dict) or 'refuta' not in d:
        return None
    return bool(d.get('refuta')), str(d.get('motivo') or '')[:180]


def verify_challenge(spot: dict, ctx: dict | None = None, answer: str | None = None,
                     votes: int = REFUTE_VOTES) -> dict:
    """Roda N peritos independentes contra o gabarito. NUNCA levanta.

    Devolve {'veredito', 'refutacoes', 'votos', 'motivos'}:
      · 'aprovado'     — nenhuma maioria derrubou
      · 'refutado'     — maioria derrubou; o candidato não deve ir ao pool
      · 'indisponivel' — sem LLM (chave ausente/erro/ilegível): NÃO bloqueia

    Fail-open é deliberado: esta é a camada 4 de 5, e a 5 é a aprovação humana. Bloquear a
    geração inteira por indisponibilidade do modelo seria parar por um motivo que não é de
    qualidade — e o admin continua revisando cada candidato.
    """
    ctx = ctx or describe_challenge(spot)
    answer = answer or ctx.get('best_action') or ''
    key = (f"{spot.get('scenario')}:{spot.get('position')}:{spot.get('vs_position')}:"
           f"{spot.get('stack_bb')}:{spot.get('hand')}:{answer}")
    if key in _REFUTE_CACHE:
        return _REFUTE_CACHE[key]

    from leaklab.llm_explainer import _call_llm_api
    refutacoes = validos = 0
    motivos: list[str] = []
    for _ in range(max(1, votes)):
        try:
            r = _parse_refute(_call_llm_api(_refute_prompt(spot, ctx, answer)))
        except Exception:
            r = None
        if r is None:
            continue
        validos += 1
        if r[0]:
            refutacoes += 1
            if r[1]:
                motivos.append(r[1])

    if not validos:
        out = {'veredito': 'indisponivel', 'refutacoes': 0, 'votos': 0, 'motivos': []}
    elif refutacoes >= min(REFUTE_MAJORITY, validos):
        out = {'veredito': 'refutado', 'refutacoes': refutacoes, 'votos': validos, 'motivos': motivos}
    else:
        out = {'veredito': 'aprovado', 'refutacoes': refutacoes, 'votos': validos, 'motivos': motivos}
    _REFUTE_CACHE[key] = out
    return out


def build_candidates(n: int = 10, rng: _random.Random | None = None,
                     with_explanation: bool = True,
                     difficulty: str = 'dificil',
                     verify: bool = True) -> list[dict]:
    """Gera até `n` candidatos da faixa de dificuldade pedida. Cada candidato:
    {spot_json, answer, note, difficulty}. O admin aprova antes de virar desafio.

    A grade é varrida VÁRIAS vezes com stacks diferentes: um spot só é fácil/médio/difícil
    para uma combinação de mão e profundidade, então uma passada única encontraria pouca coisa
    fora do nível fácil.

    `verify` liga o voto adversarial (camada 4): candidato refutado por maioria dos peritos NÃO
    entra na lista, e o motivo vai para o log. Custa N chamadas de LLM por candidato — desligue
    em teste, não em produção.
    """
    if difficulty not in DIFFICULTIES:
        difficulty = DEFAULT_DIFFICULTY
    rng = rng or _random.Random()
    out: list[dict] = []
    seen: set = set()
    refutados = 0
    # Varre a grade uma vez por stack: sem isso, sortear a profundidade por categoria descarta
    # a maioria das combinações antes de testá-las.
    tentativas = [(c, s) for s in _CH_STACKS for c in _categories()]
    rng.shuffle(tentativas)
    for cat, stack in tentativas:
        if len(out) >= n:
            break
        c = dict(cat)
        c['stack_bb'] = stack
        spot = generate_canonical_spot(c, rng)
        if not spot:
            continue
        cert = _certainty(spot, difficulty)
        if not cert:
            continue
        answer, freq, _strat, faixa = cert
        sig = (spot.get('scenario'), spot.get('position'), spot.get('vs_position'),
               spot.get('stack_bb'), spot.get('hand'))
        if sig in seen:
            continue
        seen.add(sig)

        # Camada 4: peritos independentes tentam derrubar o gabarito ANTES de gastar a chamada
        # cara da explicação. Refutado por maioria não entra — nem no pool, nem no orçamento.
        nota = _note(spot, answer, freq)
        if verify:
            v = verify_challenge(spot, answer=answer)
            if v['veredito'] == 'refutado':
                refutados += 1
                _log.info("desafio REFUTADO (%s/%s peritos): %s | motivos: %s",
                          v['refutacoes'], v['votos'], nota, '; '.join(v['motivos'])[:200])
                continue
            if v['veredito'] == 'indisponivel':
                # Marca no que o admin lê: sem o voto, a revisão humana é a única barreira.
                nota += "  [sem voto do LLM]"

        # Sela o MIX no spot: e ELE que as 5 camadas vetaram, e e contra ele que o submit
        # grada. Sem isto o grade_challenge re-deriva ao vivo, e quando a fonte de estrategia
        # muda entre a aprovacao e o dia do desafio, o card diz "errou" em cima de um teaching
        # que explica por que a jogada e certa (aconteceu em 29/08, com fold de 54o vs 3-bet).
        spot['gto_strategy_vetada'] = _strat
        cand = {
            'spot_json':  json.dumps(spot),
            'answer':     answer,
            'note':       nota,
            'difficulty': faixa,
        }
        if with_explanation:
            # explicação didática gerada JÁ na criação (o admin revisa antes de aprovar)
            cand['explanation'] = explain_challenge(spot, describe_challenge(spot))
        out.append(cand)

    if verify and refutados:
        _log.info("build_candidates: %s candidato(s) descartado(s) pelo voto adversarial", refutados)
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


def revalidar_pool(aplicar: bool = True) -> dict:
    """Revalida TODO o pool contra os gates de HOJE — e aposenta o que reprovar.

    ── O que originou (30/08) ──────────────────────────────────────────────────────────────
    O desafio servido era "você abriu 54o no LJ e levou 3-bet" — premissa que o GTO nunca
    joga (54o não está no range de abertura do LJ). O gate de premissa EXISTE no gerador,
    mas o candidato nasceu antes dele. Regra do dono: "os desafios têm que ser criados com
    certeza GTO" — e certeza vale para o acervo, não só para o próximo candidato.

    Para cada candidato não-rejeitado, exige:
      1. PREMISSA coerente — em vs_3bet, a mão pertence ao range de abertura da posição;
      2. COBERTURA — o StrategyProvider responde available=True para o spot;
      3. GABARITO creditável — o answer gravado tem freq >= MIN_CREDITABLE na estratégia.
    Reprova → status 'retired_gto' (sai do sorteio; a nota diz qual gate falhou).
    Aprova → SELA `gto_strategy_vetada` no spot_json se ainda não tiver (defesa 1 do
    grade_challenge passa a valer também para o acervo).

    `aplicar=False` = dry-run: só mede, não escreve.
    """
    from database.repositories import (list_challenge_candidates, set_challenge_status,
                                       update_challenge_spot)
    from leaklab.leak_trainer import hand_in_open_range

    res = {'total': 0, 'ok': 0, 'selados': 0, 'aposentados': [], 'dry_run': not aplicar}
    for cand in list_challenge_candidates(status=None, limit=1000):
        if cand.get('status') == 'rejected':
            continue
        res['total'] += 1
        try:
            spot = json.loads(cand['spot_json'])
        except Exception:
            spot = None
        motivo = None
        strat = []
        if not spot:
            motivo = 'spot_json ilegivel'
        else:
            pos = spot.get('position', '')
            hand = spot.get('hand', '')
            stack = float(spot.get('stack_bb', 0) or 0)
            if spot.get('scenario') == 'vs_3bet' and not hand_in_open_range(pos, hand, stack):
                motivo = 'premissa: %s nao abre %s a %sbb' % (pos, hand, int(stack))
            else:
                g = grade_canonical_spot(spot, cand.get('answer') or 'fold')
                strat = g.get('gto_strategy') or []
                if not strat:
                    motivo = 'cobertura: provider nao responde este spot'
                else:
                    freq = {_norm(x['action']): float(x['freq']) for x in strat}
                    if freq.get(_norm(cand.get('answer') or ''), 0.0) < MIN_CREDITABLE:
                        motivo = 'gabarito %r fora do creditavel na fonte de hoje' % cand.get('answer')
        if motivo:
            res['aposentados'].append({'id': cand['id'], 'motivo': motivo,
                                       'era': cand.get('status')})
            if aplicar:
                set_challenge_status(cand['id'], 'retired_gto')
                _log.warning('DESAFIO revalidacao: candidato %s aposentado (%s)',
                             cand['id'], motivo)
            continue
        res['ok'] += 1
        if spot is not None and not spot.get('gto_strategy_vetada') and strat:
            if aplicar:
                spot['gto_strategy_vetada'] = strat
                update_challenge_spot(cand['id'], json.dumps(spot))
            res['selados'] += 1
    return res


def grade_challenge(spot_json: str, action: str, answer: str | None = None) -> dict:
    """Grada a ação do jogador contra o spot VETADO — pelo mix selado na aprovação, quando
    existe; senão pela re-grade ao vivo com o `answer` aprovado como PISO.

    ── O que originou (29/08) ──────────────────────────────────────────────────────────────
    O gabarito passa por 5 camadas (nó limpo, faixa, triangulação, voto adversarial, admin) e
    esta função re-gradava AO VIVO, ignorando tudo. Quando a fonte de estratégia divergiu
    entre ambientes, o jogador foldou 54o contra 3-bet, o card disse "Não foi a melhor" e o
    teaching — escrito para o gabarito vetado — explicou por que fold é óbvio. Duas políticas
    de veredito na mesma tela (a mesma família do lista×card de 26/08).

    Spots aprovados ANTES do selo não têm o mix gravado; para eles vale o piso: quem joga o
    `answer` vetado nunca é marcado errado, e a divergência vai para o log com nome, para a
    re-curadoria — não para a tela do jogador."""
    spot = json.loads(spot_json) if isinstance(spot_json, str) else spot_json
    played = _norm(action)
    vetada = spot.get('gto_strategy_vetada') or None

    if vetada:
        # Fonte ÚNICA com o teaching: o mix que as camadas aprovaram.
        freq = {_norm(s.get('action')): float(s.get('freq') or 0) for s in vetada}
        strat = [{'action': a, 'freq': round(f, 4)}
                 for a, f in sorted(freq.items(), key=lambda x: -x[1]) if f > 0.01]
        pf = freq.get(played, 0.0)
        if pf >= CORRECT_FREQ:
            tier, correct, mixed = 'correct', True, False
        elif pf >= MIN_CREDITABLE:
            tier, correct, mixed = 'correct', True, True
        else:
            tier, correct, mixed = 'error', False, False
        g = {'is_correct': correct, 'gto_tier': tier, 'mixed': mixed}
    else:
        g = grade_canonical_spot(spot, action)
        strat = g.get('gto_strategy') or []
        if answer and _norm(answer) == played and not g.get('is_correct'):
            # PISO: a re-grade contradisse o gabarito que humano+LLM aprovaram. O jogador que
            # jogou o gabarito não paga por isso; o log aciona a re-curadoria do spot.
            #
            # E o rótulo é "Correto.", NÃO "Aceitável" (30/08, o dono pegou na tela): o
            # jogador jogou O GABARITO — "o GTO mistura aqui" seria uma afirmação de fato que
            # ninguém verificou, e o mix da re-grade veio da fonte que acabou de se provar
            # divergente. Por isso o mix ao vivo também SOME do card: melhor não afirmar
            # estratégia nenhuma do que exibir a estratégia da política errada.
            _log.warning(
                'DESAFIO: re-grade ao vivo diverge do gabarito vetado '
                '(pos=%s vs=%s stack=%s hand=%s | answer=%s, live disse %s/%s)',
                spot.get('position'), spot.get('vs_position'), spot.get('stack_bb'),
                spot.get('hand'), _norm(answer), g.get('gto_tier'), g.get('best_action'))
            g = {'is_correct': True, 'gto_tier': 'correct', 'mixed': False,
                 'best_action': _norm(answer)}
            strat = []

    best = (strat[0]['action'] if strat else '') or g.get('best_action') or ''
    mix = ', '.join(f"{s['action']} {round(float(s['freq'])*100)}%" for s in strat[:3])
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
