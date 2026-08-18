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

import logging
import os
import random

log = logging.getLogger(__name__)

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
    # Postflop MIRADO no leak real; só cai no piloto único quando não há leak postflop medido.
    pf = postflop_leak_cats(user_id, days=days)
    return base + (pf if pf else _postflop_pilot_cats())


def _postflop_pilot_cats() -> list[dict]:
    """Fase 2 (piloto): categorias postflop do catálogo validado. Peso modesto — fundamentos OOP
    úteis a todos. Servem de PISO quando o jogador ainda não tem leak postflop medido.

    Duas metades do mesmo confronto BB vs BTN: DEFESA (enfrentar o c-bet no SRP) e INICIATIVA
    (decidir o c-bet no pote 3-BET — a categoria de 17/08, onde vivem AK/AQ/QQ+)."""
    return [
        {'kind': 'postflop', 'catalog': 'bb_defense', 'scenario': 'pf_bb_defense',
         'position': 'BB', 'vs_position': 'BTN', 'stack_bb': 40.0,
         'ev_loss_bb': 0.0, 'n': 0, 'weight': 2.0, 'key': 'pf:bb_defense'},
        {'kind': 'postflop', 'catalog': 'bb_3bet_pot', 'scenario': 'pf_bb_3bet',
         'position': 'BB', 'vs_position': 'BTN', 'stack_bb': 29.0,
         'ev_loss_bb': 0.0, 'n': 0, 'weight': 1.5, 'key': 'pf:bb_3bet_pot'},
    ]


def postflop_leak_cats(user_id: int, days: int = 90) -> list[dict]:
    """Categorias postflop MIRADAS no leak real do jogador (#41, 2ª metade).

    Antes existia uma categoria postflop só, igual para todo mundo (BB defesa vs BTN, 40bb, flop) —
    ou seja, o treino postflop ignorava onde o jogador de fato erra. Agora cada par (street ×
    posição) com erro medido vira uma categoria, e o acervo é filtrado por ela.

    Medido em produção antes de ligar: os 12 pares de leak postflop mais frequentes têm de 149 a
    1.026 nós no acervo. Mirar por leak não passa fome — que era o risco real de filtrar.

    Peso = número de ERROS, na mesma moeda em que a categoria foi ranqueada. Piso 0.5 para uma
    categoria de erro baixo não sumir da rotação.
    """
    try:
        from database.repositories import get_postflop_leak_categories
        brutos = get_postflop_leak_categories(user_id, days=days)
    except Exception:
        log.exception('leaks postflop indisponíveis; treino postflop cai no piloto')
        return []
    cats = []
    for r in brutos:
        stack = r.get('avg_stack_bb')
        iniciativa = bool(r.get('iniciativa'))
        # A chave da DEFESA fica a antiga (`pf:street:pos`) de proposito: `progression_attempts`
        # e chaveado por ela, e a categoria agregada de antes era 76% defesa por volume — o
        # historico de treino existente descreve majoritariamente defesa, entao ele fica onde
        # esta. A INICIATIVA e categoria NOVA (`:ini`) e comeca do zero, o que tambem e verdade:
        # ninguem treinou pool de c-bet antes, porque ele nao existia.
        chave = (f"pf:{r['street']}:{r['position']}:ini" if iniciativa
                 else f"pf:{r['street']}:{r['position']}")
        cats.append({
            'kind':        'postflop',
            'catalog':     'bb_defense',           # piso, se o acervo não render
            'scenario':    'pf_leak',
            'street':      r['street'],
            'position':    r['position'],
            'vs_position': '',
            'iniciativa':  iniciativa,
            'stack_bb':    _snap_stack(stack),
            'stack_measured': stack is not None,
            'ev_loss_bb':  0.0,
            'n':           int(r.get('n') or 0),
            'erros':       int(r.get('erros') or 0),
            'weight':      max(0.5, float(r.get('erros') or 0)),
            'key':         chave,
        })
    return cats


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


# ── Catálogo de TREINOS NOMEADOS (Fase 1, 17/08) ──────────────────────────────────────────────
#
# A lacuna medida em [[project_catalogo_de_treinos]] era de AGÊNCIA, não de motor: quem sabe o
# que quer treinar não conseguia pedir na linguagem dele. Cada entrada mapeia um focus roteável
# para um treino NOMEADO (nome/descrição são i18n do frontend, chaveados pelo `id` — texto não
# mora no backend). O adaptativo continua sendo o padrão e o diferencial; isto é a porta de quem
# chega sabendo o que quer.
#
# A ESTATÍSTICA por treino não é nova: `training_skill_progress` (EMA + decaimento + tiers) já
# persistia por category_key — o catálogo só AGREGA por entrada. Memória atrás do código, de
# novo: o backlog listava "persistência por treino" como faltante.
CATALOGO_TREINOS = [
    # grupo 'recomendado' — o fisioterapeuta: o sistema escolhe pelo leak medido
    {'id': 'adaptive',      'focus': 'adaptive',          'grupo': 'recomendado', 'free': False},
    # grupo 'preflop' — fundamentos nomeados (cobertura gold, 36 pares × 9 profundidades)
    {'id': 'fund_rfi',      'focus': 'fund:rfi',          'grupo': 'preflop',     'free': True},
    {'id': 'fund_vs_rfi',   'focus': 'fund:vs_rfi',       'grupo': 'preflop',     'free': True},
    {'id': 'fund_vs_3bet',  'focus': 'fund:vs_3bet',      'grupo': 'preflop',     'free': True},
    {'id': 'bvb',           'focus': 'cat:bvb',           'grupo': 'preflop',     'free': True},
    {'id': 'short',         'focus': 'cat:short',         'grupo': 'preflop',     'free': True},
    # grupo 'postflop' — catálogos pré-solvados (45 spots validados em prod)
    {'id': 'pf_bb_defense', 'focus': 'cat:pf_bb_defense', 'grupo': 'postflop',    'free': False},
    {'id': 'pf_bb_3bet',    'focus': 'cat:pf_bb_3bet',    'grupo': 'postflop',    'free': False},
    # Fase 3: mão INTEIRA heads-up — replay real, decisão por street. O focus 'fh:' não passa
    # pelo /next: o frontend roteia para /full-hand/next (fluxo próprio, multi-decisão).
    {'id': 'full_hand',     'focus': 'fh:full_hand',      'grupo': 'postflop',    'free': False},
    # grupo 'memorizacao' — fronteira da range na grade (placar próprio do SRS)
    {'id': 'range_grid',    'focus': 'fund:range_grid',   'grupo': 'memorizacao', 'free': True},
]

# Focos de catálogo que são FUNDAMENTOS por natureza (preflop, sem leak medido) — liberados no
# Free como os fund:*. Postflop e adaptativo seguem o gate normal do plano.
FREE_CATALOG_FOCUSES = {e['focus'] for e in CATALOGO_TREINOS
                        if e['free'] and e['focus'].startswith('cat:')}


def curriculo_do_catalogo(cat_id: str, user_id: int | None = None) -> list[dict]:
    """Currículo de uma entrada `cat:<id>` do catálogo. Lista vazia = id desconhecido (o /next
    cai no fallback de fundamentos, nunca 500)."""
    if cat_id == 'bvb':
        # Blind vs Blind: SB abre (RFI de SB é o confronto BvB por definição) + o par SB×BB
        # da defesa. É filtro sobre o fundamento — cobertura idêntica.
        rfi = [c for c in fundamentals_catalog('rfi') if c['position'] == 'SB']
        vs = [c for c in fundamentals_catalog('vs_rfi')
              if {c['position'], c['vs_position']} == {'SB', 'BB'}]
        return rfi + vs
    if cat_id == 'short':
        # Stack curto: os mesmos fundamentos a 12bb — zona de shove/reshove. A escada do
        # next_spot ainda pode endurecer para 10bb com 3 acertos seguidos.
        return fundamentals_catalog('rfi', stack=12) + fundamentals_catalog('vs_rfi', stack=12)
    if cat_id == 'pf_bb_defense':
        return [c for c in _postflop_pilot_cats() if c['catalog'] == 'bb_defense']
    if cat_id == 'pf_bb_3bet':
        return [c for c in _postflop_pilot_cats() if c['catalog'] == 'bb_3bet_pot']
    return []


def _chaves_da_entrada(entry_id: str, key: str) -> bool:
    """A category_key pertence à entrada do catálogo? (agregação de estatística)."""
    if entry_id == 'adaptive':
        return True
    if entry_id == 'fund_rfi':
        return key.startswith('rfi:')
    if entry_id == 'fund_vs_rfi':
        return key.startswith('vs_rfi:')
    if entry_id == 'fund_vs_3bet':
        return key.startswith('vs_3bet:')
    if entry_id == 'full_hand':
        return key.startswith('fh:')
    if entry_id == 'bvb':
        return (key.startswith('rfi:SB') or key.startswith('vs_rfi:SB:BB')
                or key.startswith('vs_rfi:BB:SB'))
    if entry_id == 'short':
        # 'cenario:pos:vs:stack' — curto = 15bb ou menos
        try:
            return (key.split(':')[0] in ('rfi', 'vs_rfi')
                    and float(key.rsplit(':', 1)[1]) <= 15)
        except (ValueError, IndexError):
            return False
    if entry_id == 'pf_bb_defense':
        return key == 'pf:bb_defense'
    if entry_id == 'pf_bb_3bet':
        return key == 'pf:bb_3bet_pot'
    return False


def stats_do_catalogo(skills: list[dict]) -> dict:
    """{entry_id: {attempts, correct, mastery, tier, last_practiced_at}} agregado das skills
    persistidas (que já chegam com o domínio DECAÍDO pelo tempo — get_training_skills).
    Média ponderada por tentativas: 200 mãos a 80% pesam mais que 3 a 100%."""
    from database.repositories import _mastery_tier
    out = {}
    for e in CATALOGO_TREINOS:
        if e['id'] == 'range_grid':
            continue        # placar próprio (SRS das cartas de range), já exposto no /options
        pertence = [s for s in (skills or []) if _chaves_da_entrada(e['id'], s['category_key'])]
        attempts = sum(int(s.get('attempts') or 0) for s in pertence)
        correct = sum(int(s.get('correct') or 0) for s in pertence)
        if attempts > 0:
            mastery = round(sum(float(s.get('mastery') or 0) * int(s.get('attempts') or 0)
                                for s in pertence) / attempts, 1)
        else:
            mastery = 0.0
        last = max((s.get('last_practiced_at') or '' for s in pertence), default=None) or None
        out[e['id']] = {'attempts': attempts, 'correct': correct, 'mastery': mastery,
                        'tier': _mastery_tier(mastery), 'last_practiced_at': last}
    return out


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
        # `tipo`/`dificuldade` para a saida ser observavel junto com o catalogo novo. Sem eles a
        # sondagem era indistinguivel de "nenhuma pergunta" em qualquer contagem.
        'tipo': 'largura_do_vilao', 'dificuldade': 'intermediaria',
        # DE QUEM a pergunta fala. A tela abre a tabela de ranges nesta posição depois que o
        # jogador responde — ver `_POSICAO_DA_PERGUNTA` em `perguntas_de_range.py`.
        'posicao': vs_pos,
        'stack': float(stack),
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
            # Duas fontes, e a ordem importa.
            #
            # A sondagem ESPECIFICA DO SPOT ("que fatia das maos o vilao tem AQUI?") e a mais forte
            # pedagogicamente, porque fala da mao que o aluno esta prestes a jogar. Ela so existe em
            # cenario com vilao a ler.
            #
            # O catalogo (`perguntas_de_range`) entra nos dois casos que a sondagem nao cobria: os
            # spots `rfi`, que ate agora NAO tinham pergunta nenhuma, e a variedade nos demais — o
            # usuario reportou que a sondagem sozinha "ficou basica e repetitiva", e a medicao
            # confirmou: era um molde so.
            #
            # `excluir_mao` e obrigatorio: sem ele um spot "UTG a 30bb, o que fazer com KTo?"
            # poderia vir precedido de "UTG abre KTo a 30bb?", que E a resposta.
            _sonda = None
            if rng.random() < _COTA_SONDAGEM:
                if scenario != 'rfi' and vs_pos and rng.random() < 0.5:
                    _sonda = _sondagem_de_range(vs_pos, float(stack), rng)
                if _sonda is None:
                    try:
                        from leaklab.perguntas_de_range import gerar as _gerar_pergunta
                        _sonda = _gerar_pergunta(rng, pos=(vs_pos or pos), stack=float(stack),
                                                 excluir_mao=_hand)
                    except Exception:
                        _sonda = None
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
        # Spot do ACERVO (#41) corrige pelo próprio nó, e não por `lookup_gto`: o lookup re-deriva
        # o hash a partir dos parâmetros, e a reconstrução não reproduz o mesmo nó — no teste ele
        # resolveu OUTRO e respondeu "o certo era fold" numa tela que oferecia check/bet.
        if spot.get('origem') == 'pool' and spot.get('tree_hash'):
            from leaklab.trainer_pool import corrigir as _corrige_pool
            g = _corrige_pool(spot, action)
            if g is not None:
                return g
            # nó deixou de ser gradeável entre servir e corrigir: não pune
            return {'is_correct': True, 'gto_tier': 'correct', 'mixed': False, 'gto_freq': 1.0,
                    'gto_strategy': [], 'best_action': '', 'new_action': _norm_action(action),
                    'recommended': [], 'validation_source': 'gto_pool_postflop', 'xp_value': 0,
                    'new_score': 0.0, 'original_score': 0.0, 'delta': 0.0,
                    'next_drill_at': None, 'srs_interval_days': 0, 'ungradeable': True}
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
# Categoria BB 3-BET POT (17/08): BTN abre 2,5 → BB 3-beta p/ 11 → BTN paga. Pote 22,5bb,
# 29bb atrás (SPR ~1,3), BB PRIMEIRO a agir com iniciativa — decisão de c-bet (facing 0).
# É o espelho da bb_defense e o lar de AK/AQ/QQ+, que 3-betam preflop e por isso nunca
# chegam ao catálogo SRP (range-aware, não bug). pot_type='3bet' entra no HASH do nó —
# sem ele o grade leria o nó SRP de outra árvore (a família do RC-3).
_BB3BET_PARAMS = {
    'position': 'BB', 'vs_position': 'BTN', 'stack_bb': 29.0,
    'facing_size_bb': 0.0, 'pot_bb': 22.5, 'street': 'flop',
    'pot_type': '3bet', 'opener': 'BTN', 'threebettor': 'BB',
}
_CATALOG_PARAMS = {'bb_defense': _BBDEF_PARAMS, 'bb_3bet_pot': _BB3BET_PARAMS}
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
    # ── BB 3-BET POT (17/08): BB 3-betou, BTN pagou; decisão de c-bet (facing 0) ──────────────
    # 14/14 validados pelo seed --pote-3bet em prod (expl 0,60-1,43%, zero reprovados). Onde
    # vivem AK/AQ/QQ+, que 3-betam preflop e nunca chegam ao catálogo SRP. Parâmetros em
    # _BB3BET_PARAMS (pote 22,5bb, 29bb atrás, pot_type='3bet' no hash).
    'bb_3bet_pot': [
        {'board': ['Kd', '7c', '2s'], 'hand': ['Ah', 'Kc']},   # top pair top kicker
        {'board': ['Kd', '7c', '2s'], 'hand': ['Qh', 'Qc']},   # under pair ao K
        {'board': ['Kd', '7c', '2s'], 'hand': ['Ah', '5d']},   # blefe da range
        {'board': ['9h', '8h', '5c'], 'hand': ['Th', 'Tc']},   # overpair-ish
        {'board': ['9h', '8h', '5c'], 'hand': ['Ah', 'Kd']},   # overs air
        {'board': ['9h', '8h', '5c'], 'hand': ['Ts', '9s']},   # top pair + draw
        {'board': ['Ah', 'Tc', '5h'], 'hand': ['Ad', 'Qd']},   # top pair
        {'board': ['Ah', 'Tc', '5h'], 'hand': ['Kd', 'Qd']},   # gutshot + over
        {'board': ['Ah', 'Tc', '5h'], 'hand': ['9c', '8c']},   # air
        {'board': ['7d', '6s', '4h'], 'hand': ['Ac', 'Ad']},   # overpair
        {'board': ['7d', '6s', '4h'], 'hand': ['9h', '8d']},   # OESD
        {'board': ['Qd', '7s', '4h'], 'hand': ['Ac', 'Qh']},   # top pair
        {'board': ['Qd', '7s', '4h'], 'hand': ['Kh', 'Kd']},   # overpair
        {'board': ['Qd', '7s', '4h'], 'hand': ['Jh', '9d']},   # blefe gutshot
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


def generate_postflop_spot(category: dict, rng: random.Random | None = None,
                           servidos: set | None = None) -> dict | None:
    """Retorna um spot postflop (stateless, sem revelar a resposta).

    **Backlog #41:** tenta primeiro o ACERVO de nós já solvados (`trainer_pool`) e só cai no
    catálogo estático se ele não render. O catálogo tem 31 spots com parâmetros fixos (BB vs BTN,
    40bb, flop); o acervo tinha 5.139 nós servíveis quando isto foi escrito, e cresce sozinho a
    cada torneio mandado solvar.

    A ordem é essa e não o contrário: o catálogo é o PISO, não a fonte. Se o acervo falhar por
    qualquer razão, o treino continua funcionando com o que sempre funcionou — e por isso a
    exceção é engolida aqui, não propagada.

    Desligável sem deploy por `TRAINER_POOL_POSTFLOP=0`, porque a qualidade do acervo depende de
    dado que entra sozinho e a válvula precisa existir antes de precisarmos dela.
    """
    rng = rng or random
    if os.getenv('TRAINER_POOL_POSTFLOP', '1') != '0':
        try:
            from leaklab.trainer_pool import proximo_spot as _pool
            # Mira o LEAK: street e posição vêm da categoria. Se a categoria não os traz (o piloto
            # antigo não traz), cai no acervo inteiro — que é o comportamento anterior, não um erro.
            # `enfrentando` traduz a iniciativa para a forma do POOL: categoria de iniciativa
            # treina decisoes SEM aposta na frente (c-bet/barrel — o hero age), defesa treina
            # ENFRENTANDO. Categoria sem o campo (piloto/legado) nao filtra — comportamento
            # anterior. E uma aproximacao declarada: OOP primeiro-a-agir sem iniciativa tambem
            # nao enfrenta aposta, mas o pool nao guarda quem agrediu por ultimo — guarda o
            # `facing_size_bb`, e essa e a forma treinavel da distincao.
            _enfrentando = (not category['iniciativa']) if 'iniciativa' in category else None
            s = _pool(rng=rng, evitar=servidos or set(),
                      street=category.get('street'), position=category.get('position'),
                      enfrentando=_enfrentando)
            if s is None and (category.get('street') or category.get('position')):
                # Leak sem nó no acervo: melhor um spot postflop de outro recorte do que nenhum.
                # Registrado porque um leak que nunca encontra spot é buraco de cobertura, e
                # buraco silencioso não vira trabalho.
                log.info('acervo sem nó para o leak %s/%s; servindo de outro recorte',
                         category.get('street'), category.get('position'))
                s = _pool(rng=rng, evitar=servidos or set())
            if s:
                # Só herda o rótulo da categoria quando o spot REALMENTE é dela. O fallback acima
                # pode servir outro recorte, e sobrescrever a chave fazia o painel anunciar
                # "BB defende vs c-bet de CO (flop)" com um board de turn na mesa. Rótulo que não
                # descreve o que está na tela é pior que rótulo genérico: o jogador confia nele.
                mesma = (not category.get('street') or s.get('street') == category.get('street')) \
                    and (not category.get('position') or s.get('position') == category.get('position'))
                if mesma:
                    s['category'] = category.get('key') or s.get('category')
                return s
        except Exception:
            log.exception('acervo de treino postflop indisponível; caindo no catálogo estático')
    _catalogo = category.get('catalog', 'bb_defense')
    spots = POSTFLOP_CATALOG.get(_catalogo) or []
    if not spots:
        return None
    s = rng.choice(spots)
    # Parâmetros POR CATÁLOGO (17/08): o bb_3bet_pot tem pote/stack/facing próprios e carrega
    # pot_type no spot — usar _BBDEF_PARAMS para todos era exatamente o furo que faria o grade
    # ler o nó da árvore errada.
    p = _CATALOG_PARAMS.get(_catalogo, _BBDEF_PARAMS)
    # Menu pela FORMA do spot: enfrentando aposta → fold/call/raise; primeiro a agir (facing 0)
    # → check/bet. Oferecer 'raise' sem aposta na mesa é pedir para aumentar o que ninguém fez
    # (a mesma lição do menu do pool).
    _opts = list(_POSTFLOP_OPTIONS) if float(p.get('facing_size_bb') or 0) > 0 else ['check', 'bet']
    return {
        'kind':           'postflop',
        'street':         p['street'],
        'category':       category['key'],
        'position':       p['position'],
        'vs_position':    p['vs_position'],
        'stack_bb':       p['stack_bb'],
        'facing_size_bb': p['facing_size_bb'],
        'pot_bb':         p['pot_bb'],
        # Variante do nó (hash): sem isto o grade leria a árvore SRP num pote 3-bet.
        'pot_type':       p.get('pot_type', ''),
        'opener':         p.get('opener', ''),
        'threebettor':    p.get('threebettor', ''),
        'board':          s['board'],
        'board_cards':    _cards_to_objs(s['board']),
        'hand':           ''.join(s['hand']),
        'hero_hand':      s['hand'],
        'hero_cards':     _cards_to_objs(s['hand']),
        'options':        _opts,
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


def _lookup_do_spot(spot: dict) -> dict:
    """O mapeamento spot→lookup_gto do catálogo postflop, numa porta só. Corretor E painel de
    range leem por aqui — duas cópias deste mapeamento seria gravar o hash com uma chave e
    procurar com outra (regra 5)."""
    from leaklab.gto_solver import lookup_gto
    # `facing_size_bb=0.0` é LEGÍTIMO (pote 3-bet: BB decide o c-bet, primeiro a agir) e um
    # `or 1.65` o engoliria — o hash sairia com facing 1.65 e nunca acharia o nó semeado com
    # facing 0. A mesma armadilha do `?? vs ||` já paga no front; só None cai no default.
    _facing = spot.get('facing_size_bb')
    _facing = 1.65 if _facing is None else float(_facing)
    return lookup_gto(
        street=spot.get('street', 'flop'), position=spot.get('position', 'BB'),
        board=spot.get('board') or [], hero_hand=spot.get('hero_hand') or [],
        hero_stack_bb=float(spot.get('stack_bb', 40) or 40),
        vs_position=spot.get('vs_position', 'BTN'),
        facing_size_bb=_facing,
        pot_bb=float(spot.get('pot_bb', 5.0) or 5.0), bb_chips=1.0,
        # Variante do nó (17/08): o spot de pote 3-bet carrega pot_type/opener/threebettor.
        # Sem repassar, o hash cai na árvore SRP — o RC-3 com outra roupa.
        pot_type=spot.get('pot_type', ''),
        opener=spot.get('opener', ''), threebettor=spot.get('threebettor', ''),
        require_hand_aware=True, block_remote=False, allow_remote_solve=False,
    )


def arvore_do_spot(spot: dict) -> str | None:
    """tree_hash da árvore que corrige este spot. Spot do pool já viaja com ele; spot do
    catálogo estático re-deriva pelo MESMO lookup da correção — nunca por um hash paralelo."""
    th = spot.get('tree_hash')
    if th:
        return th
    if spot.get('kind') != 'postflop' and not spot.get('board'):
        return None
    return _lookup_do_spot(spot).get('tree_hash')


def grade_postflop_spot(spot: dict, action: str) -> dict | None:
    """Lê o nó pré-solvado (NUNCA solva ao vivo) e gradeia a mão. None se sem tabela por-mão."""
    res = _lookup_do_spot(spot)
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


# ── Treino de FRONTEIRA na grade: marcar a família inteira ────────────────────────────────────
#
# Os outros exercícios perguntam "o que você faz com ESTA mão". Este pergunta "até onde vai a
# range" — recordação ativa da fronteira, que é o fato âncora que dá para memorizar. Reconhecer
# uma mão servida é bem mais fácil que reconstruir onde a linha para.
#
# UMA FAMÍLIA POR VEZ, e não a grade inteira. Marcar 169 células é inviável na prática e, pior,
# dilui: 130 delas são fold óbvio em qualquer posição. Uma família tem 12 ou 13 casas e a
# resposta É a fronteira ("o UTG abre Ás suited até onde?").
#
# A correção NÃO é porcentagem de células certas. Numa família em que o UTG abre 5 de 12, marcar
# nada acerta 58% — o número premiaria não responder. O que o exercício reporta é o que FALTOU e
# o que SOBROU, que é o formato em que o erro se corrige.

_FAMILIAS = [
    ('as_suited',    'Áses suited',        [f'A{r}s' for r in 'KQJT98765432']),
    ('as_offsuit',   'Áses offsuit',       [f'A{r}o' for r in 'KQJT98765432']),
    ('reis_suited',  'Reis suited',        [f'K{r}s' for r in 'QJT98765432']),
    ('pares',        'Pares',              [f'{r}{r}' for r in 'AKQJT98765432']),
    ('conectores',   'Conectores suited',  ['JTs', 'T9s', '98s', '87s', '76s', '65s', '54s', '43s', '32s']),
    ('broadway_off', 'Broadways offsuit',  ['KQo', 'KJo', 'KTo', 'QJo', 'QTo', 'JTo']),
]

# ── Os três estratos, por FREQUÊNCIA ────────────────────────────────────────────────
#
# A primeira versão deste exercício era binária: `hand_in_open_range`, cujo corte é
# MIN_PREMISE_OPEN_FREQ = 0.05. Serve ao propósito para o qual foi escrita (validar a PREMISSA de
# um spot vs_3bet: "o vilão podia ter aberto isto?") e é péssima como gabarito.
#
# Medido no UTG a 50bb, família conectores: quem marcava exatamente as mãos que o GTO abre >=90%
# das vezes (JTs, T9s) era REPROVADO, e o exercício cobrava 98s/87s/76s/65s/54s como faltantes.
# 54s o UTG abre 12% das vezes. Ou seja: o exercício reprovava a resposta certa e ensinava uma
# range mais larga que a real — num produto cujo veredito é de 3 níveis justamente para não
# chamar frequência mista de erro.
#
# Agora são três faixas, a mesma régua do resto do sistema (`_discriminates` usa 10% como "ação
# claramente errada"; `_LIMIAR_MISTO`, 90% como "resposta clara"):
#
#   núcleo    >= 90%  — tem que marcar. Não marcar é erro de verdade.
#   fronteira 10–90%  — o GTO MISTURA. Marcar ou não, ambas passam; a frequência aparece no
#                       feedback, e é ali que está o aprendizado.
#   lixo      < 10%   — não pode marcar. Marcar é erro de verdade.
#
# A fronteira em palavras deixou de ser "a mão mais fraca que entra com >=5%" e passou a ser a
# mais fraca do NÚCLEO. É uma afirmação que o jogador pode levar para a mesa sem ressalva.
POSICOES_DE_ABERTURA = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB']

# Profundidades treinadas. A range de abertura MUDA com a profundidade (a 20bb o BTN abre bem
# mais que a 75bb), entao o mesmo par posicao/familia em stacks diferentes sao cartas DISTINTAS
# de memorizacao, nao repeticao.
STACKS_DE_ABERTURA = [20, 30, 50, 75]


def card_key_de_range(pos: str, familia: str, stack) -> str:
    """Identidade da carta no SRS. Fonte unica: o gerador, o agendador e a correcao tem que
    concordar em o que e a mesma carta, senao o intervalo e gravado numa chave e procurado
    noutra (o mesmo defeito que custou tres meses no hash de board)."""
    return 'grid:%s:%s:%d' % (pos, familia, int(float(stack)))


_FREQ_NUCLEO = 0.90
_FREQ_LIXO   = 0.10

# "Entrar na range" e NAO FOLDAR, e nao "raise+allin".
#
# Reportado na tela: o exercicio dizia que o SB abre AKo so 19% das vezes a 20bb, tratando a mao
# como fronteira, enquanto cobrava A2o como obrigatoria. Medido, o SB faz AKo `call` 81% /
# `raise` 19% — e `call` sem aposta na frente e o LIMP. A mao esta 100% na range; o que varia e
# a ACAO. Somar so raise+allin classificava a mao mais forte da familia como duvidosa e a mais
# fraca como certa, ou seja, ensinava o inverso da verdade.
#
# So o SB limpa (medido: 47 a 62 maos por profundidade; nenhuma outra posicao tem `call` com
# facing 0), entao a mudanca nao mexe em nenhuma das outras 7 posicoes.
_ACOES_DE_ENTRADA = ('raise', 'allin', 'call')


def familias_de_range() -> list[dict]:
    """Catálogo das famílias treináveis (para o front listar, se precisar)."""
    return [{'key': k, 'label': lab, 'hands': hs} for k, lab, hs in _FAMILIAS]


def _freq_de_entrada(pos: str, hand: str, stack: float):
    """Com que frequência o GTO coloca esta mão na range. None = sem cobertura (a mão sai do
    exercício em vez de virar um 'fora' falso)."""
    from leaklab.preflop_gto_ranges import analyze_preflop
    from leaklab.strategy_provider import normalize_freq_map
    try:
        res = analyze_preflop(position=pos, hero_hand_type=hand, stack_bb=float(stack),
                              action_taken='raise', facing_size=0.0, vs_position='')
    except Exception:
        return None
    if not res.get('available'):
        return None
    hf = normalize_freq_map(res.get('hand_freq'))
    # Calculado como 1 - fold, e nao como a soma das acoes: se a arvore ganhar uma acao nova
    # (ou renomear uma), a soma passa a subestimar em silencio e o exercicio volta a punir. O
    # complemento do fold nao tem como ficar desatualizado.
    entra = 1.0 - hf.get('fold', 0.0)
    soma  = sum(hf.get(a, 0.0) for a in _ACOES_DE_ENTRADA)
    return max(entra, soma)


def _estratos(pos: str, hands: list, stack: float) -> dict:
    """Classifica a família inteira. O gerador e o corretor usam a MESMA função — senão o
    gerador escolhe a família por um critério e o corretor cobra por outro."""
    nucleo, fronteira, lixo, freqs = [], [], [], {}
    for h in hands:
        f = _freq_de_entrada(pos, h, stack)
        if f is None:
            continue
        freqs[h] = round(f, 3)
        if f >= _FREQ_NUCLEO:
            nucleo.append(h)
        elif f >= _FREQ_LIXO:
            fronteira.append(h)
        else:
            lixo.append(h)
    return {'nucleo': nucleo, 'fronteira': fronteira, 'lixo': lixo, 'freqs': freqs}


def generate_range_grid_spot(rng=None,
                             position: str = None,
                             stack: int = 50,
                             familia: str = None):
    """Spot de marcação: uma família, uma posição, e quais mãos dela entram na range.

    A resposta NÃO viaja no spot — o cliente marca e o servidor corrige, igual ao resto do
    trainer. Mandar o gabarito junto tornaria o exercício decorativo.
    """
    rng = rng or random
    pos = position or rng.choice(POSICOES_DE_ABERTURA)

    escolhidas = [f for f in _FAMILIAS if f[0] == familia] if familia else list(_FAMILIAS)
    if not escolhidas:
        return None
    key, label, hands = rng.choice(escolhidas)

    # Só serve a família se a fronteira estiver DENTRO dela. Família toda no núcleo ou toda no
    # lixo não ensina fronteira nenhuma: vira "marque tudo" ou "marque nada", e o jogador acerta
    # sem saber. A régua é o NÚCLEO, a mesma que a correção cobra.
    est = _estratos(pos, hands, float(stack))
    if not est['freqs'] or not est['nucleo'] or len(est['nucleo']) == len(est['freqs']):
        return None

    # E a família não pode ser MAJORITARIAMENTE mista. Visto na tela: um exercício saiu com 6 de
    # 9 mãos misturando (JTs 57%, T9s 59%, 98s 83%, 87s 87%, 65s 66%, 32s 55%) — sobravam 3
    # células com resposta e o feedback virava um muro de percentuais. Não há fronteira a
    # memorizar onde quase tudo é "tanto faz".
    #
    # A régua é só "mistas não dominam", e não um mínimo de núcleo E de lixo: medido, a regra
    # dura deixaria 81 cartas contra 122, e apagaria SB e BTN quase inteiros — posições cuja
    # range o jogador precisa saber tanto quanto as outras.
    if len(est['fronteira']) > len(est['nucleo']) + len(est['lixo']):
        return None

    return {
        'kind': 'range_grid',
        'category': card_key_de_range(pos, key, stack),
        'card_key': card_key_de_range(pos, key, stack),
        'position': pos,
        'stack_bb': stack,
        'familia': key,
        'familia_label': label,
        'hands': hands,
        'xp_value': 30,
    }


def grade_range_grid_spot(spot: dict, marcadas: list) -> dict:
    """Corrige a marcação. Reporta o que faltou, o que sobrou e onde o GTO mistura.

    NÃO é porcentagem de células certas: numa família em que a posição abre 5 de 12, quem não
    marca nada 'acerta' 58% — o número premiaria não responder.

    E NÃO cobra a fronteira. Mão que o GTO abre 37% das vezes não tem resposta certa; exigi-la
    seria punir a jogada defensável, que é o erro que este produto evita em toda superfície.
    """
    pos      = spot.get('position') or ''
    stack    = float(spot.get('stack_bb') or 50)
    hands    = list(spot.get('hands') or [])
    if not pos or not hands:
        return {'erro': 'spot invalido'}

    est      = _estratos(pos, hands, stack)
    nucleo   = set(est['nucleo'])
    lixo     = set(est['lixo'])
    marcadas = {h for h in (marcadas or []) if h in hands}

    faltaram = sorted(nucleo - marcadas, key=hands.index)        # núcleo esquecido = erro
    sobraram = sorted(marcadas & lixo,    key=hands.index)       # lixo marcado     = erro
    acertou  = not faltaram and not sobraram

    # A fronteira em palavras: a mão mais fraca que o GTO joga SEMPRE. É o fato âncora, e agora
    # é uma afirmação sem ressalva — antes apontava uma mão de 12% de frequência.
    fronteira = None
    for h in reversed(hands):
        if h in nucleo:
            fronteira = h
            break

    # As mistas viajam com a frequência: é o que transforma "errei" em "aqui não há resposta".
    mistas = [{'hand': h, 'freq': est['freqs'].get(h, 0.0)} for h in est['fronteira']]

    return {
        'acertou': acertou,
        'certas': sorted(nucleo, key=hands.index),
        'faltaram': faltaram,
        'sobraram': sobraram,
        'mistas': mistas,
        'fronteira': fronteira,
        'xp': spot.get('xp_value', 30) if acertou else 0,
    }


# ── Agendamento SRS das cartas de range ────────────────────────────────────────
#
# Range é MEMORIZAÇÃO, e memorização sem reencontro programado é só exposição. Sorteio solto,
# que era o comportamento anterior, tem dois defeitos que se somam: repete o que o jogador já
# sabe (a chance de cair na mesma carta é igual para a dominada e para a que ele nunca viu) e
# nunca traz de volta o que ele errou na hora em que estaria esquecendo.
#
# A ordem de serviço é, nesta prioridade:
#   1. VENCIDAS — a mais atrasada primeiro. É o único jeito de o esquecimento ser combatido.
#   2. NOVAS — começando pelas do alvo (a posição em que os torneios dele mostram erro).
#   3. A mais próxima de vencer — para uma sessão longa não terminar em beco quando o jogador
#      já viu tudo e nada venceu ainda.
#
# Dentro da mesma sessão nada se repete: `servidas` chega do cliente. Não dá para deduzir isso do
# banco, porque a carta só ganha linha DEPOIS de corrigida — e servir de novo a mesma carta que
# ainda está na tela seria o defeito mais óbvio possível.


def universo_de_cartas() -> list:
    """Todas as combinações (posição × família × profundidade) que o exercício pode servir.

    Não filtra por ensinabilidade aqui: isso custa uma consulta de range por mão, e o filtro real
    acontece ao montar a carta (família sem fronteira devolve None e a próxima é tentada).
    """
    return [(pos, fam, st)
            for pos in POSICOES_DE_ABERTURA
            for fam, _lab, _hs in _FAMILIAS
            for st in STACKS_DE_ABERTURA]


def proximo_card_de_range(user_id: int, servidas=None, alvo: str = None,
                          rng=None) -> dict:
    """A próxima carta de memorização, pelo SRS. None se nenhuma combinação for ensinável."""
    from datetime import datetime
    from database.repositories import cartas_de_range_do_usuario

    rng      = rng or random
    servidas = set(servidas or [])
    agora    = datetime.utcnow().isoformat()

    estado   = {c['card_key']: c for c in cartas_de_range_do_usuario(user_id)}
    universo = [c for c in universo_de_cartas()
                if card_key_de_range(c[0], c[1], c[2]) not in servidas]
    if not universo:
        return None

    def chave(c):
        return card_key_de_range(c[0], c[1], c[2])

    vencidas = [c for c in universo
                if chave(c) in estado and (estado[chave(c)]['due_at'] or '') <= agora]
    vencidas.sort(key=lambda c: estado[chave(c)]['due_at'] or '')

    novas = [c for c in universo if chave(c) not in estado]
    # Alvo primeiro: se os torneios dele mostram erro abrindo do LJ, a carta nova a servir é do
    # LJ, e não uma sorteada entre 192. O resto embaralha para não virar sempre a mesma ordem.
    rng.shuffle(novas)
    if alvo:
        novas.sort(key=lambda c: 0 if c[0] == alvo else 1)

    resto = [c for c in universo if chave(c) in estado and c not in vencidas]
    resto.sort(key=lambda c: estado[chave(c)]['due_at'] or '')

    for pos, fam, st in (vencidas + novas + resto):
        spot = generate_range_grid_spot(position=pos, familia=fam, stack=st)
        if spot:
            info = estado.get(card_key_de_range(pos, fam, st))
            spot['srs'] = {
                'revisao':  bool(info),
                'seen':     (info or {}).get('seen', 0),
                'interval': (info or {}).get('interval_days', 0),
            }
            return spot
    return None


# ── Quando o produto SUGERE memorizar range ────────────────────────────────────
#
# O exercício estava escondido atrás de "Treinar outra coisa", o que o deixava disponível para
# quem já sabe que precisa dele — exatamente quem menos precisa. Quem erra a abertura do LJ não
# sabe que o problema é não ter a range na cabeça; ele acha que errou aquela mão.
#
# SÓ sugere para leak PREFLOP, e a mira depende do cenário:
#   rfi     → a posição DELE. Ele abre errado do LJ, então o que falta é a range do LJ.
#   vs_rfi  → a posição do VILÃO. Ele defende mal contra o open do LJ; o que falta é saber O QUE
#             O LJ ABRE. Sugerir a range dele próprio aí seria a ferramenta errada.
#
# Não sugere por leak postflop: marcar a range de abertura não conserta um c-bet ruim, e sugerir
# ali seria ruído com cara de conselho.
_MIN_MAOS_PARA_SUGERIR = 6


def sugerir_memorizacao_de_range(user_id: int, days: int = 90) -> dict:
    """O jogador precisa memorizar alguma range? Devolve o alvo, ou None.

    A amostra mínima existe porque duas mãos ruins não são um buraco de conhecimento; são duas
    mãos ruins. Sugerir estudo a partir de ruído gasta a credibilidade da sugestão.
    """
    try:
        cats = build_curriculum(user_id, days=days)
    except Exception:
        return None

    candidatos = []
    for c in cats:
        if c.get('kind') == 'postflop':
            continue
        cen = c.get('scenario')
        if cen == 'rfi':
            alvo = c.get('position') or ''
        elif cen == 'vs_rfi':
            alvo = c.get('vs_position') or ''      # a range que falta é a de QUEM ABRIU
        else:
            continue
        if not alvo or alvo not in POSICOES_DE_ABERTURA:
            continue
        if int(c.get('n') or 0) < _MIN_MAOS_PARA_SUGERIR or float(c.get('ev_loss_bb') or 0) <= 0:
            continue
        candidatos.append((float(c.get('ev_loss_bb') or 0), alvo, cen, c))

    if not candidatos:
        return None
    ev, alvo, cen, cat = max(candidatos, key=lambda x: x[0])
    return {
        'position':   alvo,
        'scenario':   cen,
        'ev_loss_bb': round(ev, 2),
        'hands':      int(cat.get('n') or 0),
        'stack_bb':   int(_snap_para_treino(cat.get('stack_bb'))),
        # De quem é a range: muda a frase na tela ("você abre" vs "o LJ abre").
        'de_quem':    'heroi' if cen == 'rfi' else 'vilao',
    }


def _snap_para_treino(stack) -> int:
    """A profundidade medida cai na mais próxima das treinadas — a carta tem que existir."""
    try:
        s = float(stack or 50)
    except (TypeError, ValueError):
        s = 50.0
    return min(STACKS_DE_ABERTURA, key=lambda x: abs(x - s))
