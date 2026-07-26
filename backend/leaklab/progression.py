"""
progression.py — Protocolo de Progressão: missões (PIP), plano de sessão e camada didática.

Este módulo NÃO é um sistema de treino novo. Ele orquestra o que já existe:
  · o diagnóstico real (`get_leak_categories` → `leak_trainer.build_curriculum`)
  · o gerador de spots (`leak_trainer.generate_canonical_spot`)
  · o gabarito (`strategy_provider`, fonte única)
  · o domínio de treino (`training_skill_progress`)

O que ele acrescenta:
  1. MISSÃO (PIP) — o leak escolhido por EV **ponderado por confiança**, com o vínculo ao jogo
     real ("você perdeu 11bb nisso em 9 mãos") e uma definição de pronto explícita.
  2. PLANO DE SESSÃO — composição 60/25/15 (leak ativo / revisão / discriminação) em vez de
     drill blocado. Prática blocada gera domínio APARENTE que não transfere: o jogador aprende
     "neste trainer a resposta é fold", não *quando* foldar. A fatia de discriminação usa a
     família VIZINHA onde a resposta muda (mesma mão, stack diferente).
  3. CAMADA DIDÁTICA — o "porquê" em uma linha, nomeando o GATILHO do spot (o que faz a
     resposta ser essa), não repetindo o gabarito. Determinístico: sem LLM, sem alucinação,
     instantâneo. O aprofundamento (números, ranges) fica nas camadas 2/3 da UI.
"""
from __future__ import annotations

import random

from leaklab.leak_trainer import (
    build_curriculum, generate_canonical_spot, _STACKS, _leak_scenario,
)
from leaklab.strategy_provider import normalize_action

# ── Tamanhos de sessão (o jogador escolhe na hora) ───────────────────────────────────────────
# Sessão TEM forma: começo, meio e fim. Grind infinito cansa e não melhora retenção.
SESSION_SIZES = {
    'curta': 12,    # ~4 min  — cabe em qualquer dia
    'media': 24,    # ~8 min  — padrão
    'longa': 40,    # ~13 min — dia de estudo
}
DEFAULT_SESSION = 'media'

# Composição da sessão (interleaving). Não é enfeite: intercalar parece PIOR durante o treino
# e é muito melhor em retenção e transferência — e a variedade é o que segura a atenção.
MIX_ACTIVE   = 0.60   # leak ativo (a missão)
MIX_REVIEW   = 0.25   # revisão espaçada de leaks já praticados
MIX_CONTRAST = 0.15   # discriminação: família vizinha onde a resposta MUDA


def _confidence(n: int):
    """Convenção ÚNICA de confiança por amostra (mesma do ranking de leaks do plano de estudo).
    Importada em runtime pra não puxar as dependências do módulo de LLM no import."""
    from leaklab.llm_explainer import _ev_confidence
    return _ev_confidence(n)


# ── 1. Missões (PIP) ─────────────────────────────────────────────────────────────────────────

def build_missions(user_id: int, days: int = 90, top: int = 3) -> list[dict]:
    """Top-N leaks como MISSÕES, ranqueadas por EV **ponderado por confiança**.

    Por que ponderado: um leak de −21bb em 3 decisões pode ser variância; −0,46bb/decisão em 24
    é padrão. Ordenar por bb bruto colocaria o ruído no topo do plano — e o jogador passaria 30
    dias corrigindo algo que não existe.

    Cada missão carrega o vínculo com o jogo REAL (bb perdidos, nº de mãos, profundidade) porque
    é isso que dá sentido ao treino: o jogador precisa saber por que ESTE spot, e não outro.
    """
    cats = [c for c in build_curriculum(user_id, days=days) if c.get('kind') != 'postflop']
    missions = []
    for c in cats:
        n     = int(c.get('n') or 0)
        ev    = float(c.get('ev_loss_bb') or 0)
        fator, conf = _confidence(n)
        missions.append({
            'key':            c['key'],
            'scenario':       c['scenario'],
            'position':       c['position'],
            'vs_position':    c.get('vs_position') or '',
            'stack_bb':       c['stack_bb'],
            # diagnóstico real
            'ev_loss_bb':     round(ev, 2),
            'hands':          n,
            'ev_por_mao':     round(ev / n, 2) if n else 0.0,
            'ev_ponderado':   round(ev * fator, 2),
            'confianca':      conf,
            # profundidade: medida ou estimada (a UI precisa poder dizer a diferença)
            'stack_medido':   bool(c.get('stack_measured', True)),
            'stack_real':     c.get('avg_stack_raw'),
            'titulo':         mission_title(c),
        })
    # tiered: confiança ALTA primeiro — amostra pequena nunca lidera o plano
    _rank = {'alta': 0, 'média': 1, 'baixa': 2}
    missions.sort(key=lambda m: (_rank.get(m['confianca'], 3), -m['ev_ponderado']))
    return missions[:top]


# ── Leak de SIZING (dimensão própria) ────────────────────────────────────────────────────────
# Um open de tamanho errado tem a AÇÃO certa, então o ev_loss da range é ~0 e o leak fica
# invisível ao diagnóstico normal. É outra dimensão: custa EV sem ser "decisão errada".
SIZING_MIN_N     = 8      # amostra mínima por posição pra falar de padrão (não de uma mão)
SIZING_OFF_RATIO = 1.35   # mesma régua do sizing_advisor: +35% já é padrão caro
SIZING_MIN_SHARE = 0.40   # % de aberturas fora do tamanho pra virar missão


def build_sizing_missions(user_id: int, days: int = 90) -> list[dict]:
    """Missões de SIZING: posições em que o hero abre sistematicamente fora do tamanho GTO.

    Reporta PADRÃO, não mão avulsa: exige amostra mínima e uma fatia relevante de aberturas
    fora do tamanho. Uma abertura grande é ruído; 60% delas é um hábito que custa fichas.
    """
    from database.repositories import get_open_sizing_rows
    from leaklab.sizing_advisor import gto_open_to_bb
    rows = get_open_sizing_rows(user_id, days=days)
    por_pos: dict[str, list] = {}
    for r in rows:
        por_pos.setdefault((r['position'] or '').upper(), []).append(r)

    missoes = []
    for pos, lista in por_pos.items():
        if len(lista) < SIZING_MIN_N:
            continue
        fora, ratios, alvo = 0, [], None
        for r in lista:
            gto = gto_open_to_bb(pos, r['stack_bb'])
            if not gto:
                continue
            ratio = r['raise_to_bb'] / gto
            ratios.append(ratio)
            alvo = gto if alvo is None else alvo
            if ratio > SIZING_OFF_RATIO or ratio < (1 / SIZING_OFF_RATIO):
                fora += 1
        if not ratios or len(ratios) < SIZING_MIN_N:
            continue
        share = fora / len(ratios)
        if share < SIZING_MIN_SHARE:
            continue
        medio = sum(ratios) / len(ratios)
        grande = medio > 1.0
        missoes.append({
            'key':        f'sizing:rfi:{pos}',
            'tipo':       'sizing',
            'position':   pos,
            'titulo':     f'Tamanho da abertura de {pos}',
            'hands':      len(ratios),
            'fora':       fora,
            'share':      round(share, 2),
            'ratio_medio': round(medio, 2),
            'direcao':    'grande' if grande else 'pequeno',
            'diagnostico': (
                f"{fora} das suas {len(ratios)} aberturas de {pos} saíram fora do tamanho GTO "
                f"(em média {abs(medio - 1) * 100:.0f}% {'acima' if grande else 'abaixo'})."),
            'porque': (
                "Abrir maior que o GTO arrisca mais fichas pra ganhar o mesmo pote: quando dá "
                "errado você perde mais, e quando dá certo ganha igual."
                if grande else
                "Abrir menor que o GTO dá preço barato demais pra quem está atrás defender, e "
                "você joga potes maiores fora de posição com range pior."),
        })
    missoes.sort(key=lambda m: (-m['share'], -m['hands']))
    return missoes


# ── Foco: QUAL missão está ativa agora ───────────────────────────────────────────────────────
# Quantas missões olhar antes de decidir o foco. O painel mostra 3, mas quem domina as 3 precisa
# ter a 4ª pronta — senão o protocolo trava justamente em quem está evoluindo mais rápido.
MISSION_POOL = 8


def missions_with_state(user_id: int, days: int = 90, pool: int = MISSION_POOL) -> dict:
    """Fonte ÚNICA do foco: as missões anotadas com estado e QUAL está ativa.

    Existe porque o gate de domínio só vale se ele de fato abrir a porta. Antes desta função o
    foco era `missions[0]` (maior EV) em dois lugares independentes — painel e plano de sessão —
    e nenhum dos dois lia o estado: o jogador podia bater os 5/5 critérios e continuar sendo
    servido o mesmo leak para sempre, com o selo "Dominado no treino" aceso na tela.

    A missão ATIVA é a primeira, na ordem de EV ponderado, que ainda está `em_treino`. Uma
    missão dominada sai da rotação ativa mas NÃO some: continua viva na fatia de revisão (SRS)
    e reabre sozinha se a janela móvel de 30 tentativas voltar a falhar — o gate é acumulado,
    não um carimbo permanente.
    """
    from database.repositories import get_progression_attempts, get_training_proof

    missions = build_missions(user_id, days=days, top=pool)
    try:
        proofs = {p['category_key']: p for p in (get_training_proof(user_id) or [])}
    except Exception:
        proofs = {}

    itens = []
    for m in missions:
        try:
            att = get_progression_attempts(user_id, m['key'], limit=MASTERY_WINDOW)
        except Exception:
            att = []
        ms = mastery_status(att)
        st = state_for(ms, proofs.get(m['key']))
        itens.append({**m, 'estado': st, 'estado_label': STATE_LABEL.get(st, st),
                      'mastery': ms, 'proof': proofs.get(m['key'])})

    em_treino = [i for i in itens if i['estado'] == 'em_treino']
    dominadas = [i for i in itens if i['estado'] != 'em_treino']
    ativa = em_treino[0] if em_treino else None
    return {
        'ativa':      ativa,
        # o painel mostra o arco curto: o que vem DEPOIS da ativa, não o backlog inteiro
        'proximas':   em_treino[1:3],
        'dominadas':  dominadas,
        'restantes':  len(em_treino),
        'items':      itens,
    }


def mission_title(cat: dict) -> str:
    """Nome humano do spot. O jogador tem que reconhecer a situação na hora."""
    pos, vs = cat.get('position', ''), (cat.get('vs_position') or '')
    stack   = cat.get('stack_bb')
    scen    = cat.get('scenario')
    if scen == 'rfi':
        base = f"Abertura de {pos}"
    elif scen == 'vs_rfi':
        base = f"Defesa de {pos} vs abertura de {vs}" if vs else f"Defesa de {pos}"
    elif scen == 'vs_3bet':
        base = f"{pos} enfrentando 3-bet de {vs}" if vs else f"{pos} enfrentando 3-bet"
    else:
        base = f"{pos} {scen}"
    return f"{base} · {stack}bb"


# ── 2. Plano de sessão (interleaving) ────────────────────────────────────────────────────────

def neighbor_category(cat: dict) -> dict | None:
    """Família VIZINHA para a fatia de discriminação: mesmo spot, **profundidade diferente**.

    É o contraste mais didático que existe em MTT: a mesma mão que é shove a 12bb é call a 30bb.
    Sem isso o jogador decora "neste spot eu shovo" em vez de aprender que **o stack é o gatilho**
    — e o domínio não transfere pro jogo real, onde a profundidade muda a cada mão.
    """
    stack = cat.get('stack_bb')
    if stack not in _STACKS:
        return None
    i = _STACKS.index(stack)
    # Direção: prefere ir pro MAIS CURTO. Aprofundar quase não muda a estratégia (30bb e 50bb
    # jogam parecido), enquanto encurtar vira a resposta (a mão que é call a 30bb é shove a 14bb)
    # — e é a virada que ensina o gatilho. Só sobe quando não há degrau curto disponível.
    j = i - 2 if i - 2 >= 0 else (i + 2 if i + 2 < len(_STACKS) else -1)
    if j < 0 or j == i:
        return None
    out = dict(cat)
    out['stack_bb'] = _STACKS[j]
    out['key'] = f"{cat['scenario']}:{cat['position']}:{cat.get('vs_position','')}:{_STACKS[j]}"
    out['_contrast_of'] = cat['stack_bb']
    return out


def plan_session(user_id: int, size: str = DEFAULT_SESSION, days: int = 90,
                 review_keys: list[str] | None = None,
                 rng: random.Random | None = None) -> dict:
    """Monta a sessão: qual missão, quantos spots e de onde vem cada um.

    Devolve o PLANO (categorias por fatia), não os spots — quem gera spot é o leak_trainer, e
    gerar sob demanda mantém a sessão barata e o gabarito fora do cliente.
    """
    rng = rng or random
    n_total = SESSION_SIZES.get(size, SESSION_SIZES[DEFAULT_SESSION])

    # O foco vem do ESTADO, não da ordem de EV: quem passou o gate sai da rotação ativa.
    # Se a leitura de estado falhar, cair no maior EV é melhor que não abrir sessão nenhuma.
    try:
        estado = missions_with_state(user_id, days=days)
    except Exception:
        estado = None
    missions = (estado or {}).get('items') or build_missions(user_id, days=days, top=3)
    if not missions:
        return {'size': size, 'total': 0, 'mission': None, 'blocks': [], 'reason': 'sem_leaks'}

    # UM leak ativo por vez (foco). Com tudo dominado a sessão não acaba: vira REVISÃO — o selo
    # ainda depende do jogo real, e é o SRS que impede o domínio de apodrecer.
    modo = 'missao'
    if estado and estado.get('ativa'):
        mission = estado['ativa']
    elif estado and estado.get('dominadas'):
        mission, modo = estado['dominadas'][0], 'revisao'
    else:
        mission = missions[0]
    cats = {c['key']: c for c in build_curriculum(user_id, days=days)}
    active_cat = cats.get(mission['key'])
    if not active_cat:
        return {'size': size, 'total': 0, 'mission': None, 'blocks': [], 'reason': 'categoria_ausente'}

    n_active   = max(1, round(n_total * MIX_ACTIVE))
    n_contrast = max(1, round(n_total * MIX_CONTRAST))
    n_review   = max(0, n_total - n_active - n_contrast)

    blocks = [{'kind': 'active', 'n': n_active, 'category': active_cat,
               'label': mission['titulo']}]

    # Revisão: categorias JÁ praticadas (o caller passa as devidas do SRS). Sem histórico,
    # o espaço vira leak ativo — melhor treinar o que importa do que inventar revisão.
    revisar = [cats[k] for k in (review_keys or []) if k in cats and k != mission['key']]
    if revisar and n_review > 0:
        for i in range(n_review):
            blocks.append({'kind': 'review', 'n': 1, 'category': revisar[i % len(revisar)],
                           'label': mission_title(revisar[i % len(revisar)])})
    elif n_review > 0:
        blocks[0]['n'] += n_review

    # Discriminação: o mesmo spot noutra profundidade
    contrast = neighbor_category(active_cat)
    if contrast:
        blocks.append({'kind': 'contrast', 'n': n_contrast, 'category': contrast,
                       'label': mission_title(contrast),
                       'contrast_of': contrast.get('_contrast_of')})
    else:
        blocks[0]['n'] += n_contrast

    return {
        'size':    size,
        'total':   sum(b['n'] for b in blocks),
        'mission': mission,
        'modo':    modo,
        'blocks':  blocks,
        'mix':     {'active': n_active, 'review': n_review, 'contrast': n_contrast},
    }


def next_spot_for_plan(plan: dict, done_by_kind: dict | None = None,
                       rng: random.Random | None = None) -> dict | None:
    """Próximo spot da sessão, respeitando a composição já cumprida.
    Intercala de verdade (não serve os 60% do leak ativo em bloco e depois o resto)."""
    rng = rng or random
    done = done_by_kind or {}
    pendentes = []
    for b in plan.get('blocks', []):
        falta = b['n'] - int(done.get(b['kind'], 0) if b['kind'] != 'active' else done.get('active', 0))
        if falta > 0:
            pendentes.append((b, falta))
    if not pendentes:
        return None
    # sorteia ponderado pelo que FALTA → as fatias se misturam ao longo da sessão
    total = sum(f for _, f in pendentes)
    pick, acc = rng.uniform(0, total), 0.0
    escolhido = pendentes[0][0]
    for b, f in pendentes:
        acc += f
        if pick <= acc:
            escolhido = b
            break
    spot = generate_canonical_spot(escolhido['category'], rng)
    if spot:
        spot['block_kind'] = escolhido['kind']
        spot['block_label'] = escolhido.get('label')
        if escolhido.get('contrast_of'):
            spot['contrast_of'] = escolhido['contrast_of']
        # ATRIBUIÇÃO — só o CONTRASTE é reatribuído à missão. Ele pertence à família vizinha
        # (outra profundidade), mas a tentativa é evidência da MISSÃO: prova que o jogador não
        # decorou e transfere pra outra profundidade. Sem isso, o critério de Transferência
        # ficava eternamente em 0 porque as tentativas caíam na categoria vizinha.
        #
        # REVISÃO **não** é reatribuída: ela é outro leak, e creditá-la à missão inflaria a
        # janela com evidência de outra coisa (o jogador "dominaria" A treinando B).
        # ATIVO não precisa: a categoria dele já É a da missão.
        if escolhido['kind'] == 'contrast':
            mk = (plan.get('mission') or {}).get('key')
            if mk:
                spot['mission_key'] = mk
    return spot


# ── 3. Camada didática: o GATILHO do spot ────────────────────────────────────────────────────
# Regra: a explicação nomeia O QUE FAZ a resposta ser essa. Nunca repete o gabarito
# ("o GTO joga raise 54%") — isso o jogador já vê nas barras. Determinístico de propósito:
# sem LLM no caminho quente = instantâneo, gratuito e impossível de alucinar.

_SHORT_BB   = 15.0    # abaixo disso a mão é decidida antes do flop
_DEEP_BB    = 45.0    # acima disso o pós-flop domina a decisão


def hand_class(hand: str) -> str:
    """Classe da mão a partir do hand_type ('A5s', '77', 'KQo'). Serve pro feedback falar da
    FAMÍLIA de mão, que é o que transfere: o jogador não vai reencontrar 94s, vai reencontrar
    'suited gapper fraco'."""
    h = (hand or '').strip()
    if len(h) < 2:
        return 'desconhecida'
    r1, r2 = h[0].upper(), h[1].upper()
    suited = h.endswith('s')
    ordem  = "23456789TJQKA"
    if r1 == r2:
        return 'par_alto' if ordem.index(r1) >= ordem.index('T') else 'par_baixo'
    hi, lo = max(ordem.index(r1), ordem.index(r2)), min(ordem.index(r1), ordem.index(r2))
    gap = hi - lo
    if r1 == 'A' or r2 == 'A':
        return 'ace_suited' if suited else 'ace_offsuit'
    if lo >= ordem.index('T'):
        return 'broadway_suited' if suited else 'broadway_offsuit'
    if gap <= 2:
        return 'conector_suited' if suited else 'conector_offsuit'
    return 'suited_fraca' if suited else 'lixo'


# Por que ESTA classe de mão se comporta assim. É a parte VARIÁVEL do feedback: sem ela o
# jogador lê a mesma frase 10 vezes numa sessão e para de prestar atenção (o cansaço que o
# protocolo existe pra evitar). Com ela, cada spot ensina uma família de mão.
_HAND_NOTES = {
    'par_alto':         "Par alto já é a mão feita na maioria dos flops: joga por valor direto.",
    'par_baixo':        "Par baixo vale pelo set que ele acerta às vezes, não pela força de agora — e set precisa de stack pra pagar.",
    'ace_suited':       "Ás suited tem o bloqueio do ás mais projeto de flush: continua bem mesmo quando não acerta par.",
    'ace_offsuit':      "Ás offsuit fraco vive de acertar par com kicker ruim, que é justamente onde se perde fichas.",
    'broadway_suited':  "Broadway suited acerta pares fortes e ainda tem projeto: é das mãos que mais gostam de jogar o flop.",
    'broadway_offsuit': "Broadway offsuit depende de acertar par alto; sem projeto, erra o flop e fica sem plano.",
    'conector_suited':  "Conector suited quase nunca acerta na hora, ele vive de implied odds — e implied odds somem quando o stack é curto.",
    'conector_offsuit': "Conector offsuit perde o projeto de flush e fica só com a sequência: é bem mais fraco do que parece.",
    'suited_fraca':     "Ser do mesmo naipe ajuda pouco sozinho: o naipe adiciona uns 2-3% de equity, não transforma a mão.",
    'lixo':             "Sem par, sem naipe e sem conexão, essa mão precisa acertar muito pra valer alguma coisa.",
    'desconhecida':     "",
}


def _rfi_principio(pos: str, stack: float) -> tuple[str, str]:
    """Abertura: o gatilho muda com a POSIÇÃO, e o SB é um caso à parte.
    Do SB só existe UM jogador atrás — dizer 'quantos podem te enfrentar' seria falso —
    mas você joga o resto da mão fora de posição e ainda pode completar."""
    if pos == 'SB':
        return (("Do SB só o BB está atrás, então você abre muito mais largo do que de outras "
                 "posições. O preço é jogar toda a mão fora de posição."),
                "SB: abra largo, mas lembre que você age primeiro em todas as ruas seguintes.")
    if pos == 'BTN':
        return (("No BTN quase ninguém está atrás e você joga o resto da mão em posição. "
                 "É a cadeira onde abrir barato mais lucra."),
                "BTN: o range de abertura é o mais largo da mesa. Não desperdice a posição.")
    return ((f"Abrindo de {pos}, ainda há vários jogadores atrás que podem pagar ou dar 3-bet. "
             f"Cada um deles é uma chance de você ficar numa mão difícil."),
            "Quanto mais gente atrás, mais apertado o range de abertura.")


def concept_for_spot(spot: dict, grade: dict | None = None) -> dict:
    """Camada 1 do feedback: uma linha sobre o GATILHO + a regra prática.

    Devolve {gatilho, principio, regra} — a UI mostra `principio` sempre (1 linha) e guarda o
    resto pro "entender melhor". Sem números: quantidade fica na camada 2.

    Ordem de prioridade = o que MAIS explica a resposta neste spot. Spot de contraste fala de
    profundidade (é pra isso que ele existe na sessão); stack curto fala de stack; mão de
    fronteira fala de mistura; o resto cai no gatilho do cenário.
    """
    scen   = (spot.get('scenario') or '').lower()
    pos    = (spot.get('position') or '').upper()
    vs     = (spot.get('vs_position') or '').upper()
    stack  = float(spot.get('stack_bb') or 0)
    hf     = (grade or {}).get('hand_freq') or {}
    mixed  = bool((grade or {}).get('mixed'))
    shove_dominante = float(hf.get('allin') or 0) >= 0.5
    is_contraste = spot.get('block_kind') == 'contrast'

    # (a) Spot de CONTRASTE: a lição é a profundidade, não a posição. Se aqui o texto falasse
    # de posição, o jogador não entenderia por que o spot mudou de stack no meio da sessão.
    if is_contraste:
        gatilho = 'stack'
        outro = spot.get('contrast_of')
        if shove_dominante:
            principio = (f"Mudou só a profundidade ({outro}bb → {stack:.0f}bb) e a resposta virou: "
                         f"aqui já não dá pra jogar pós-flop, a mão se resolve antes.")
        else:
            principio = (f"Mesmo spot, {stack:.0f}bb em vez de {outro}bb. Repare no que muda: "
                         f"com outra profundidade, a mesma mão pede outra linha.")
        regra = "O stack é gatilho antes da mão. Leia a profundidade primeiro."

    # (b) profundidade curta: é o gatilho mais forte e o mais ignorado
    elif stack <= _SHORT_BB:
        gatilho = 'stack'
        if shove_dominante:
            principio = (f"A {stack:.0f}bb não há pós-flop: a mão se decide agora. "
                         f"O shove ganha as blinds sem te dar chance de errar depois.")
            regra = "Stack curto: entre com força ou saia. Raise pequeno só cria decisão difícil."
        else:
            principio = (f"A {stack:.0f}bb cada ficha vale muito e você não tem espaço pra "
                         f"pagar agora e desistir depois.")
            regra = "Stack curto: prefira as linhas que terminam a mão."

    # (c) mão mista: o conceito é que NÃO existe resposta única
    elif mixed:
        gatilho = 'fronteira'
        principio = ("Esta mão está na fronteira do range: as duas linhas valem quase o mesmo. "
                     "O erro não é escolher uma, é escolher SEMPRE a mesma.")
        regra = "Em spot de fronteira, misture. Previsível é explorável."

    # (d) defesa de blind: preço e posição
    elif scen == 'vs_rfi' and pos in ('BB', 'SB'):
        gatilho = 'posição'
        if pos == 'BB':
            principio = ("Você já tem 1bb no pote e paga barato pra ver o flop, mas joga a mão "
                         "inteira fora de posição.")
            regra = "Defenda o BB largo em preço bom, e aperte quando for jogar sem posição."
        else:
            principio = ("Do SB você fica fora de posição o resto da mão e ainda tem o BB pra "
                         "agir atrás de você.")
            regra = "SB é a pior cadeira: defenda mais apertado do que o preço sugere."

    # (e) defesa em posição
    elif scen == 'vs_rfi':
        gatilho = 'posição'
        principio = (f"Contra a abertura de {vs or 'quem abriu'} você escolhe entre pagar e jogar "
                     f"o flop ou devolver a agressão agora.")
        regra = "Defenda mais quando estiver em posição; pagar fora de posição é o call mais caro."

    # (f) abertura: gatilho por posição (SB/BTN são casos próprios)
    elif scen == 'rfi':
        gatilho = 'posição'
        principio, regra = _rfi_principio(pos, stack)

    # (g) vs 3-bet
    elif scen == 'vs_3bet':
        gatilho = 'agressão'
        principio = ("Quem dá 3-bet mostra um range forte e polarizado. Aqui você não escolhe "
                     "entre mãos boas e ruins, e sim entre continuar ou devolver o pote.")
        regra = "Contra 3-bet, siga com o que joga bem contra range forte, não com o que parece bonito."

    else:
        gatilho = 'geral'
        principio = "A resposta muda com posição e profundidade, não só com as suas cartas."
        regra = "Leia o spot antes de olhar a mão."

    # Stack profundo muda a leitura de novo (não se aplica quando o gatilho JÁ é o stack)
    if stack >= _DEEP_BB and gatilho not in ('stack', 'fronteira'):
        principio += " Com stack profundo a mão vai longe: pesa mais como ela joga depois do flop."

    # Parte VARIÁVEL: por que ESTA família de mão se comporta assim. É o que impede a sessão
    # de repetir a mesma frase 10 vezes (fadiga) e o que o jogador leva pro jogo — ele não vai
    # reencontrar 94s, vai reencontrar "suited gapper fraco".
    classe = hand_class(spot.get('hand') or '')
    nota_mao = _HAND_NOTES.get(classe) or ''
    # conector suited em stack curto: o par implied-odds × profundidade é forte demais pra perder
    if classe == 'conector_suited' and stack <= _SHORT_BB:
        nota_mao = ("Conector suited vive de implied odds, e a {:.0f}bb não sobra stack pra pagar "
                    "quando ele acerta: aqui ele vale muito menos do que parece.").format(stack)

    return {
        'gatilho':   gatilho,
        'principio': principio,
        'regra':     regra,
        'classe':    classe,
        'nota_mao':  nota_mao,
    }


# ── 4. Estratos e o gate de "DOMINADO NO TREINO" ─────────────────────────────────────────────
# Os 3 estados do leak:
#   EM TREINO → (gate) → DOMINADO NO TREINO → (jogo real) → COMPROVADO NO JOGO
# O gate de PROGRESSÃO é o treino (rápido, amostra infinita); o SELO é o jogo real (lento).
# Nunca dizemos "corrigido" antes do jogo confirmar — é o que separa isto de um simulador.

MASTERY_WINDOW      = 30     # janela móvel de tentativas (o gate é por ACUMULADO, não por sessão:
                             # a duração da sessão é escolhida pelo jogador)
MASTERY_MIN_N       = 20     # volume mínimo na janela
MASTERY_MIN_ACC     = 0.85   # precisão geral
MASTERY_MIN_EDGE_N  = 3      # amostra mínima nos estratos que decidem (fronteira/contraste)
MASTERY_MIN_EDGE    = 0.70   # precisão exigida onde de fato se erra


def stratum_of(grade: dict | None) -> str:
    """Onde a mão cai na range: núcleo (resposta clara de continuar), lixo (fold claro) ou
    fronteira (o GTO mistura). É o estrato que diz se o jogador domina a range INTEIRA ou só a
    parte fácil — acertar 90% foldando lixo não é domínio."""
    hf = (grade or {}).get('hand_freq') or {}
    if not hf:
        return 'sem_dado'
    acao, freq = max(hf.items(), key=lambda x: x[1])
    if freq >= 0.85:
        return 'lixo' if acao == 'fold' else 'nucleo'
    return 'fronteira'


def mastery_status(attempts: list[dict]) -> dict:
    """Avalia o gate a partir das tentativas MAIS RECENTES da categoria (a lista já vem
    ordenada da mais nova pra mais velha pelo repositório).

    Devolve cada critério com progresso — o gate é TRANSPARENTE de propósito: o jogador tem que
    saber o que falta pra dominar, senão a barra vira mistério e ele desiste.

    Nota de projeto: NÃO exigimos cota igual por estrato. Medimos a distribuição real e ela é
    enviesada de formas opostas conforme a categoria (SB RFI 30bb dá 3% de lixo; BB vs SB 14bb
    dá 8% de fronteira) — exigir cota uniforme faria o domínio levar centenas de spots no
    estrato raro. Exigimos desempenho ONDE SE APRENDE: fronteira e contraste.
    """
    janela = attempts[:MASTERY_WINDOW]
    n = len(janela)
    acertos = sum(1 for a in janela if a.get('correct'))
    acc = (acertos / n) if n else 0.0

    def _slice(pred):
        s = [a for a in janela if pred(a)]
        ok = sum(1 for a in s if a.get('correct'))
        return len(s), (ok / len(s) if s else 0.0)

    n_front, acc_front = _slice(lambda a: a.get('stratum') == 'fronteira')
    n_contr, acc_contr = _slice(lambda a: a.get('block_kind') == 'contrast')
    estratos = {a.get('stratum') for a in janela if a.get('stratum') not in (None, 'sem_dado')}

    criterios = [
        {'key': 'volume',    'ok': n >= MASTERY_MIN_N,
         'atual': n, 'alvo': MASTERY_MIN_N,
         'label': 'Volume', 'desc': f'{MASTERY_MIN_N} spots recentes desta situação'},
        {'key': 'precisao',  'ok': n >= MASTERY_MIN_N and acc >= MASTERY_MIN_ACC,
         'atual': round(acc * 100), 'alvo': round(MASTERY_MIN_ACC * 100),
         'label': 'Precisão', 'desc': 'acerto geral na janela'},
        {'key': 'amplitude', 'ok': len(estratos) >= 2,
         'atual': len(estratos), 'alvo': 2,
         'label': 'Amplitude', 'desc': 'praticou mais de uma parte da range, não só a fácil'},
        {'key': 'fronteira', 'ok': n_front >= MASTERY_MIN_EDGE_N and acc_front >= MASTERY_MIN_EDGE,
         'atual': round(acc_front * 100) if n_front else 0, 'alvo': round(MASTERY_MIN_EDGE * 100),
         'amostra': n_front, 'amostra_min': MASTERY_MIN_EDGE_N,
         'label': 'Fronteira', 'desc': 'as mãos que o GTO mistura — é onde se erra de verdade'},
        {'key': 'transferencia', 'ok': n_contr >= MASTERY_MIN_EDGE_N and acc_contr >= MASTERY_MIN_EDGE,
         'atual': round(acc_contr * 100) if n_contr else 0, 'alvo': round(MASTERY_MIN_EDGE * 100),
         'amostra': n_contr, 'amostra_min': MASTERY_MIN_EDGE_N,
         'label': 'Transferência', 'desc': 'o mesmo spot noutra profundidade (prova que não decorou)'},
    ]
    faltando = [c for c in criterios if not c['ok']]
    return {
        'dominado':  not faltando,
        'criterios': criterios,
        'faltando':  [c['key'] for c in faltando],
        'janela':    {'n': n, 'acerto_pct': round(acc * 100, 1)},
    }


def state_for(mastery: dict, proof: dict | None = None) -> str:
    """Estado do leak. O selo 'comprovado' exige o JOGO REAL — o treino sozinho nunca o concede.

    `proof` vem do trilho lento (aderência antes×depois com amostra confiável). Enquanto a
    Fase 3 não substitui isso por taxa de erro com intervalo de confiança, exigimos que o
    trilho lento tenha marcado `confident` E melhora — assim 'comprovado' nunca sai de ruído.
    """
    if not mastery.get('dominado'):
        return 'em_treino'
    if proof and proof.get('confident') and float(proof.get('delta') or 0) > 0:
        return 'comprovado_no_jogo'
    return 'dominado_no_treino'


STATE_LABEL = {
    'em_treino':          'Em treino',
    'dominado_no_treino': 'Dominado no treino',
    'comprovado_no_jogo': 'Comprovado no jogo',
}


def sizing_note(spot: dict, raise_to_bb: float | None, recomendado: str | None = None) -> str | None:
    """ENSINA o tamanho do raise (o dado tem: o código 'R2.1' é raise para 2,1bb).

    Por que ensinar e não PERGUNTAR: medimos que **0% dos 1.036 nós do JSON têm mais de um
    tamanho de raise** — cada spot tem UM tamanho GTO. Transformar isso numa segunda pergunta
    de múltipla escolha viraria decoreba de tabela ("UTG 100bb abre 2,1"), dobraria os cliques
    da sessão e ensinaria o número em vez do conceito. O conceito — POR QUE este tamanho —
    é o que transfere pro jogo.
    """
    if not raise_to_bb:
        return None
    if recomendado and normalize_action(recomendado) not in ('raise',):
        return None
    scen = (spot.get('scenario') or '').lower()
    pos  = (spot.get('position') or '').upper()
    stack = float(spot.get('stack_bb') or 0)
    tam = f"{raise_to_bb:g}bb"

    if scen == 'rfi':
        if pos == 'SB':
            return (f"O open padrão daqui é {tam} — maior que das outras cadeiras, porque do SB "
                    f"você joga o resto da mão fora de posição e quer levar o pote agora.")
        if stack <= 20:
            return (f"O open padrão daqui é {tam}. Com stack curto o raise é menor: você já está "
                    f"comprometendo boa parte do stack, não precisa arriscar mais.")
        return (f"O open padrão daqui é {tam}. Pequeno resolve: rouba as blinds na maior parte "
                f"das vezes e mantém o pote controlado quando alguém paga.")
    if scen == 'vs_rfi':
        return (f"O 3-bet padrão aqui é {tam}. Fora de posição se 3-beta maior (você precisa "
                f"cobrar caro por jogar sem posição); em posição, menor já basta.")
    if scen == 'vs_3bet':
        return (f"O 4-bet padrão aqui é {tam} — pequeno em relação ao pote, porque você já tem "
                f"iniciativa e não precisa comprometer o stack pra negar a equity dele.")
    return f"O tamanho padrão neste spot é {tam}."


def contrast_note(spot: dict) -> str | None:
    """Texto da fatia de discriminação: explica por que aquele spot apareceu 'fora' da missão.
    Sem isso o jogador acha que o sistema se perdeu."""
    outro = spot.get('contrast_of')
    if not outro:
        return None
    return (f"Mesmo spot, profundidade diferente ({outro}bb → {spot.get('stack_bb')}bb). "
            f"É aqui que se aprende o gatilho: se a resposta mudou, o stack é que manda.")
