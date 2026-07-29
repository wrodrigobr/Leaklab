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

from leaklab.academy_gto_preflop import _HANDS, _hand_to_cards, _ACTION_ORDER
# Fonte ÚNICA de estratégia + menu de ações. NÃO montar menu por conta própria aqui: o menu
# DERIVA da estratégia (invariante menu ⊇ ações creditáveis). Ver strategy_provider e a
# memória do projeto [[project_strategy_provider_single_source]].
from leaklab.strategy_provider import (
    preflop_strategy, normalize_action, MIN_STRATEGY_FREQ, POSTFLOP_FACING_BET_MENU,
    hand_in_open_range,
)

# Tiers de frequência (mesma régua do Ghost Table drill — player_drill_submit).
CORRECT_FREQ = 0.30   # ação jogada com freq GTO ≥ isto → acerto pleno
MIN_FREQ     = MIN_STRATEGY_FREQ   # ≥ isto (e < CORRECT) → aceitável (GTO mistura aqui). Fonte única.

# Profundidades treináveis — alinhadas 1:1 aos buckets do JSON de ranges
# (preflop_gto_ranges._DEFAULT_BUCKETS), pra não treinar num bucket interpolado.
#
# Fase 0.3 do Protocolo: o grid começava em 30bb "pra evitar o fallback push/fold", mas
# medimos que 44% do EV perdido acontece ABAIXO de 30bb — o jogador treinava longe de onde
# perde. As ranges curtas JÁ existem no JSON (código RAI = all-in): a 10bb o BTN abre AKs
# 98% all-in, e o BB defendendo vs SB passa de 100% shove (9-14bb) a 98% call (25bb+).
# Não é preciso popular a seção `push_fold` morta; basta deixar o treino alcançar essas
# profundidades — que é onde o MTT realmente acontece.
_STACKS = [10, 14, 17, 20, 30, 40, 50, 75, 100]

# facing_size por cenário (espelha academy_gto_preflop._random_setup).
_FACING = {'rfi': 0.0, 'vs_rfi': 2.2, 'vs_3bet': 8.0}
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


# Profundidade assumida quando a categoria não tem NENHUMA decisão com stack medido.
# 50bb é o meio da grade treinável — é um chute, e por isso a categoria carrega
# stack_coverage=0 para o PIP poder dizer "profundidade estimada" em vez de fingir precisão.
_STACK_FALLBACK_BB = 50


def _snap_stack(avg_stack: float | None) -> int:
    """Snap pro stack treinável mais próximo (mantém o spot dentro da cobertura limpa).
    `None` = categoria sem profundidade medida → cai no fallback explícito."""
    return min(_STACKS, key=lambda s: abs(s - (avg_stack if avg_stack else _STACK_FALLBACK_BB)))


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
        n  = int(r.get('n') or 0)
        _avg_stack = r.get('avg_stack_bb')          # None = nenhuma decisão com profundidade
        cat = {
            'scenario':    scenario,
            'position':    r['position'],
            'vs_position': (r.get('vs_position') or '') if scenario != 'rfi' else '',
            'stack_bb':    _snap_stack(_avg_stack),
            'ev_loss_bb':  round(ev, 2),
            'n':           n,
            # Profundidade: o valor medido e o quanto dele é confiável. `stack_measured=False`
            # significa que o stack_bb acima é FALLBACK, não medição — o PIP tem que dizer isso
            # ao jogador em vez de mandá-lo treinar 50bb como se fosse fato.
            'stack_measured':  _avg_stack is not None,
            'stack_coverage':  float(r.get('stack_coverage') or 0.0),
            'avg_stack_raw':   (round(float(_avg_stack), 1) if _avg_stack is not None else None),
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
    return fundamentals_catalog('rfi')


# Cenários que o gerador sintético serve. vs_3bet LIGADO 2026-06-30 (backlog #31): a range GW v3
# vs_3bet[opener][3bettor] já existia; faltava passar hero_was_aggressor=True (+ facing_raises=1)
# no generate E no grade — sem isso o analyze_preflop rotula como vs_rfi e volta indisponível.
# 36 pares de posição cobertos. Ver [[reference_external_charts_vs3bet]].
TRAINABLE_SCENARIOS = ['rfi', 'vs_rfi', 'vs_3bet']


def fundamentals_catalog(scenario: str, stack: int = 50) -> list[dict]:
    """Catálogo de fundamentos de um CENÁRIO (rfi/vs_rfi/vs_3bet), independente de leak medido —
    pro seletor "explorar fundamentos" (treinar RFI/vs-3bet mesmo sem o leak nos dados). Enumera os
    pares de posição válidos (mesmas regras do academy._random_setup); a cobertura GTO real é
    validada por spot em generate_canonical_spot, e o next_spot pula categoria sem spot coberto."""
    order = _ACTION_ORDER
    n = len(order)

    def mk(pos: str, vs: str) -> dict:
        c = {'scenario': scenario, 'position': pos, 'vs_position': vs, 'stack_bb': stack,
             'ev_loss_bb': 0.0, 'n': 0, 'weight': 1.0}
        c['key'] = _category_key(c)
        return c

    cats: list[dict] = []
    if scenario == 'rfi':
        cats = [mk(pos, '') for pos in order[:-1]]                     # todos menos BB
    elif scenario == 'vs_rfi':
        cats = [mk(order[di], order[oi]) for oi in range(n - 1)        # defensor em seat posterior
                for di in range(oi + 1, n)]
    elif scenario == 'vs_3bet':
        cats = [mk(order[oi], order[ti]) for oi in range(n - 2)        # hero abriu; vilão 3-betou depois
                for ti in range(oi + 1, n)]
    return cats


# ── Amostragem de FRONTEIRA ───────────────────────────────────────────────────────────────────
#
# O sorteio era uniforme (`rng.shuffle(_HANDS)`), então a maioria das perguntas era trivial:
# foldar 32o de UTG não ensina nada, consome uma pergunta e ainda paga XP. O sinal por pergunta
# é baixíssimo, e o jogador aprende a clicar no automático.
#
# O que ensina é a FRONTEIRA — onde a range para. Uma mão é de fronteira quando:
#
#   · o próprio GTO MISTURA nela (frequência da ação dominante abaixo do limiar). Aqui não existe
#     resposta única, e é onde mora a decisão de verdade; ou
#   · ela MUDA de lado entre posições vizinhas: abre do CO e não do UTG. É o "quase", e é
#     exatamente o que o jogador precisa memorizar, porque o miolo ele acerta de olhos fechados.
#
# Não é filtro, é VIÉS. Cem por cento de fronteira seria um treino brutal e sem calibragem: o
# jogador precisa de algumas fáceis para sentir a régua e para não desistir. `_COTA_FRONTEIRA`
# governa a mistura.
_LIMIAR_MISTO = 0.90     # acima disto a estratégia é pura → a mão é memorização, não decisão
_COTA_FRONTEIRA = 0.75   # fatia das perguntas que vem da borda


def _posicao_vizinha(pos: str, passo: int) -> str:
    """Assento `passo` casas depois (mais tarde na ordem de ação). Fora da mesa → ''."""
    try:
        i = _ACTION_ORDER.index(pos)
    except ValueError:
        return ''
    j = i + passo
    return _ACTION_ORDER[j] if 0 <= j < len(_ACTION_ORDER) - 1 else ''   # BB não abre


def e_mao_de_fronteira(pos: str, hand: str, stack: float, hand_freq: dict) -> bool:
    """A mão está na borda da decisão, em vez de no miolo óbvio?"""
    freqs = [float(v or 0) for v in (hand_freq or {}).values()]
    if freqs and max(freqs) < _LIMIAR_MISTO:
        return True                       # o GTO mistura: é decisão, não memória

    # Muda de lado entre assentos vizinhos? Compara com a posição UMA casa depois (que abre mais
    # largo) e UMA antes (que abre mais estreito). Divergência = a mão está na borda desta posição.
    try:
        aqui = hand_in_open_range(pos, hand, stack)
    except Exception:
        return False
    for passo in (1, -1):
        viz = _posicao_vizinha(pos, passo)
        if not viz:
            continue
        try:
            if hand_in_open_range(viz, hand, stack) != aqui:
                return True
        except Exception:
            continue
    return False


# ── Sondagem de RANGE, antes de revelar a mão ─────────────────────────────────────────────────
#
# A ordem em que o jogador recebe a informação decide como ele pensa. Hoje ele vê as próprias
# cartas primeiro e já decidiu antes de considerar o vilão — força de mão vira atributo ("AJo é
# forte") em vez de comparação ("AJo é forte CONTRA ISTO").
#
# A sondagem inverte: mostra o spot SEM as cartas, pergunta que fatia das mãos o vilão tem, e só
# então revela. Duas perguntas, na ordem certa.
#
# Só existe onde HÁ range de vilão para estimar: em `rfi` o herói é o primeiro a agir e não há
# ninguém para ler. Servir a sondagem ali seria inventar uma pergunta sem resposta.
_COTA_SONDAGEM = 0.30    # fatia dos spots elegíveis que vem com sondagem — é tempero, não prato


def _sondagem_de_range(vs_pos: str, stack: float, rng: random.Random) -> dict | None:
    """Pergunta de largura sobre o vilão do spot. `None` quando não há como afirmar o número.

    Reusa a MESMA contagem da Academia (`_larguras_por_posicao`), que lê as ranges capturadas.
    Duas superfícies afirmando larguras diferentes para a mesma posição seria pior que não ter
    a sondagem: o jogador não saberia em qual acreditar.
    """
    if not vs_pos:
        return None
    try:
        from leaklab.academy_questions import _larguras_por_posicao, _faixa
    except Exception:
        return None
    larguras = _larguras_por_posicao(float(stack))
    certa = larguras.get(vs_pos)
    if certa is None or len(larguras) < 3:
        return None

    # Distratores: larguras REAIS de outras posições, afastadas o bastante para não colidirem no
    # arredondamento. Sem a distância, duas alternativas viram o mesmo texto.
    outras = sorted((v for p, v in larguras.items() if p != vs_pos),
                    key=lambda v: -abs(v - certa))
    escolhidas, usadas = [], [certa]
    for v in outras:
        if all(abs(v - u) >= 8 for u in usadas):
            escolhidas.append(v)
            usadas.append(v)
        if len(escolhidas) == 2:
            break
    if len(escolhidas) < 2:
        return None

    opcoes = [_faixa(certa)] + [_faixa(v) for v in escolhidas]
    ordem = list(range(len(opcoes)))
    rng.shuffle(ordem)
    return {
        'pergunta': f'Antes de ver suas cartas: que fatia das mãos {vs_pos} tem aqui?',
        'opcoes': [opcoes[i] for i in ordem],
        'correta': ordem.index(0),
        'explicacao': (
            f'{vs_pos} chega aqui com {_faixa(certa)} das mãos. Estimar isso ANTES de olhar a sua '
            f'mão é o que transforma força em comparação: a mesma mão é forte contra uma range '
            f'estreita e marginal contra uma larga.'),
    }


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
    # vs_3bet: o HERO abriu e agora enfrenta um 3-bet → precisa de hero_was_aggressor=True +
    # facing_raises=1 pro analyze_preflop rotear pra vs_3bet[opener][3bettor] (sem isso cai em vs_rfi
    # e volta indisponível). facing_raises>=2 viraria vs_4bet. Ver [[reference_external_charts_vs3bet]].
    was_aggr = is_3b
    raises   = 1 if is_3b else 0

    hands = _HANDS[:]
    rng.shuffle(hands)
    # Esta rodada quer uma mão de borda? A cota mistura fáceis de propósito (ver o bloco sobre
    # amostragem de fronteira). `reserva` guarda a primeira mão VÁLIDA porém trivial, para não
    # devolver `None` quando as 40 sorteadas não tiverem nenhuma de borda.
    quer_fronteira = rng.random() < _COTA_FRONTEIRA
    reserva: tuple | None = None
    for hand in hands[:40]:
        # Gate de PREMISSA: no vs_3bet a história é "você abriu e levou 3-bet" — a mão TEM que
        # pertencer ao range de abertura da posição. Sem isto, o trainer servia "UTG abriu 84o
        # vs 3-bet" (premissa impossível, induz ao erro). Cobertura sozinha não filtra isso:
        # analyze_preflop devolve available=True (rec=fold) pra mão fora do open.
        if is_3b and not hand_in_open_range(pos, hand, float(stack)):
            continue
        # StrategyProvider = fonte única: cobertura, cenário, freq E o MENU de ações num só lugar.
        # O menu deriva da estratégia (invariante menu ⊇ ações creditáveis) — o que oferece nunca
        # mais diverge do que corrige (o bug do A8s/SB-limp era o menu estático ignorar o call).
        strat = preflop_strategy(pos, hand, float(stack), facing_size=facing, vs_position=vs_pos,
                                 is_3bet_pot=is_3b, hero_was_aggressor=was_aggr, facing_raises=raises)
        if not strat['available'] or strat['scenario'] != scenario:
            continue
        # (Fase 0.3) O shove deixou de ser motivo pra pular o spot. Antes o trainer descartava
        # qualquer spot de linha dominante all-in, porque o grid ia só até 30bb e push/fold era
        # "fora de escopo". Com o grid alcançando 10-20bb, o shove É o conteúdo: é lá que está
        # 44% do EV perdido. O menu já inclui 'allin' sozinho — o invariante do provider garante
        # que toda ação creditável vira botão.
        opts = strat['available_actions']

        def _monta(_hand, _opts, _fronteira):
            # Sondagem só em cenário COM vilão a ler (vs_rfi / vs_3bet). Em `rfi` o herói é o
            # primeiro a agir: não há range de ninguém para estimar.
            _sonda = None
            if scenario != 'rfi' and vs_pos and rng.random() < _COTA_SONDAGEM:
                _sonda = _sondagem_de_range(vs_pos, float(stack), rng)
            return {
                'fronteira':   _fronteira,   # observável: dá para medir se o viés funciona
                'range_probe': _sonda,       # None = tela normal; presente = pergunta antes das cartas
                'scenario':    scenario,
                'category':    category['key'],
                'position':    pos,
                'vs_position': vs_pos,
                'stack_bb':    stack,
                'facing_size': facing,
                'is_3bet_pot': is_3b,
                'hero_was_aggressor': was_aggr,   # grade reusa (senão reclassifica errado)
                'facing_raises': raises,
                'hand':        _hand,
                'hero_cards':  _hand_to_cards(_hand),
                'options':     _opts,
                'xp_value':    _XP_BY_SCENARIO.get(scenario, 20),
            }

        # Nesta rodada queremos borda? Então mão trivial NÃO serve: guarda a primeira como
        # reserva e segue procurando. A primeira versão condicionava o `continue` a
        # `reserva is None`, então só a PRIMEIRA trivial era adiada e da segunda em diante
        # passava direto — o viés media 39% contra a cota de 75%.
        _fronteira = e_mao_de_fronteira(pos, hand, float(stack), strat.get('hand_freq') or {})
        if quer_fronteira and not _fronteira:
            if reserva is None:
                reserva = (hand, opts)
            continue
        return _monta(hand, opts, _fronteira)

    # Nenhuma das 40 sorteadas era de borda. Serve a reserva: melhor spot fácil que spot nenhum.
    if reserva is not None:
        _h, _o = reserva
        return _monta(_h, _o, False)
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
    is_3b  = bool(spot.get('is_3bet_pot', False))
    # MESMA porta do generate (StrategyProvider) — corretor e gerador leem a MESMA estratégia
    # normalizada, então o que foi oferecido é exatamente o que é gradeado.
    strat = preflop_strategy(
        spot.get('position', ''),
        spot.get('hand', ''),
        float(spot.get('stack_bb', 50) or 50),
        facing_size=float(spot.get('facing_size', 0) or 0),
        vs_position=spot.get('vs_position', '') or '',
        is_3bet_pot=is_3b,
        # mesmas flags do generate: sem isto o vs_3bet reclassifica como vs_rfi e a correção mente
        hero_was_aggressor=bool(spot.get('hero_was_aggressor', is_3b)),
        facing_raises=int(spot.get('facing_raises', 1 if is_3b else 0) or 0),
        action_taken=played if played != 'allin' else 'allin',
    )
    hf = strat['hand_freq'] or {}   # chaves já canônicas (fold/call/raise/allin)
    # mix de estratégia (% por ação não-zero), ordenado por freq desc
    gto_strategy = [
        {'action': k, 'freq': round(float(v), 4)}
        for k, v in sorted(hf.items(), key=lambda x: -x[1]) if v and v > 0.01
    ]
    # freq da AÇÃO JOGADA (chaves já normalizadas pelo provider)
    played_freq = float(hf.get(played, 0.0) or 0.0)
    # Contrato do DrillSubmitResult (que o CoachCard consome): gto_tier correct/error + mixed bool.
    # mixed = acerto numa linha co-ótima (freq ≥ MIN mas < CORRECT) — não é a ação #1, mas o GTO mistura.
    if played_freq >= CORRECT_FREQ:
        tier, is_correct, mixed = 'correct', True, False
    elif played_freq >= MIN_FREQ:
        tier, is_correct, mixed = 'correct', True, True
    else:
        tier, is_correct, mixed = 'error', False, False
    rec = strat['recommended'] or ['fold']   # já normalizado (jam→allin) pelo provider
    return {
        'is_correct':       is_correct,
        'gto_tier':         tier,
        'mixed':            mixed,
        'gto_freq':         round(played_freq, 4),
        'gto_strategy':     gto_strategy,
        'best_action':      rec[0],
        'new_action':       played,
        'recommended':      rec,
        'hand_freq':        hf,
        'range_pct':        strat['range_pct'],
        # tamanho GTO do raise (do código 'R2.1') — a camada didática ENSINA o sizing
        'raise_to_bb':      strat.get('raise_to_bb'),
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
        # ── expansão 2026-06-28 (texturas novas, todas validadas expl<3%, fold 0% nas mãos feitas) ──
        {'board': ['9h', '7h', '2c'], 'hand': ['Th', '8h']},   # OESD + flush draw
        {'board': ['9h', '7h', '2c'], 'hand': ['Ad', '9c']},   # top pair
        {'board': ['Kd', 'Qc', 'Js'], 'hand': ['Ah', 'Td']},   # straight nut (broadway)
        {'board': ['Kd', 'Qc', 'Js'], 'hand': ['Ts', '9s']},   # straight + bdfd
        {'board': ['Kd', 'Qc', 'Js'], 'hand': ['9c', '8c']},   # gutshot
        {'board': ['7d', '6s', '4h'], 'hand': ['8c', '7h']},   # par + OESD (low connected)
        {'board': ['7d', '6s', '4h'], 'hand': ['Ac', '4d']},   # bottom pair + A
        {'board': ['7d', '6s', '4h'], 'hand': ['Ts', '9d']},   # overs + gutshot
        {'board': ['9s', '9d', '4c'], 'hand': ['Kh', '9c']},   # trips (pareado)
        {'board': ['9s', '9d', '4c'], 'hand': ['Ah', '5d']},   # ace high air
        {'board': ['Ah', 'Tc', '5h'], 'hand': ['Ad', '8c']},   # top pair (ace two-tone)
        {'board': ['Ah', 'Tc', '5h'], 'hand': ['8h', '7h']},   # flush draw
        {'board': ['Ah', 'Tc', '5h'], 'hand': ['Jd', 'Td']},   # mid pair
        {'board': ['9s', '7s', '4d'], 'hand': ['8h', '6h']},   # OESD (middle two-tone)
        {'board': ['9s', '7s', '4d'], 'hand': ['Kh', '9c']},   # top pair
    ],
}
_POSTFLOP_OPTIONS = list(POSTFLOP_FACING_BET_MENU)   # fonte única (strategy_provider)
# Rede de segurança em tempo de SERVIÇO: nunca gradear contra um nó exploitável (solve ruim).
# O seed só persiste nós com expl < 3%; este teto (5%) é uma defesa-em-profundidade — pega um
# nó patológico/drift sem rejeitar os validados. expl ausente NÃO bloqueia (preserva o legado).
_MAX_SERVE_EXPLOIT_PCT = 5.0


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
    # Gate de exploitability (defesa-em-profundidade): nó exploitável demais → não-gradeável
    # (pulado, nunca pune) em vez de gradear contra um solve ruim. Nós validados (<3%) passam.
    expl = res.get('exploitability_pct')
    if expl is not None and float(expl) > _MAX_SERVE_EXPLOIT_PCT:
        return None
    g = grade_from_hand_strategy(hs, action)
    g['exploitability_pct'] = expl
    return g
