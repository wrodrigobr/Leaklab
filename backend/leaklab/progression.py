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
    missions = build_missions(user_id, days=days, top=3)
    if not missions:
        return {'size': size, 'total': 0, 'mission': None, 'blocks': [], 'reason': 'sem_leaks'}

    mission = missions[0]                       # UM leak ativo por vez (foco)
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


def contrast_note(spot: dict) -> str | None:
    """Texto da fatia de discriminação: explica por que aquele spot apareceu 'fora' da missão.
    Sem isso o jogador acha que o sistema se perdeu."""
    outro = spot.get('contrast_of')
    if not outro:
        return None
    return (f"Mesmo spot, profundidade diferente ({outro}bb → {spot.get('stack_bb')}bb). "
            f"É aqui que se aprende o gatilho: se a resposta mudou, o stack é que manda.")
