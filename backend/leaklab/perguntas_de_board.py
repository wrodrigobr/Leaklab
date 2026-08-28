# -*- coding: utf-8 -*-
"""Leitura de range DEPOIS do flop: quanto da range dele sobrevive a este board?

── Por que existe (28/08) ──────────────────────────────────────────────────────────────────

O benchmark do concorrente tem um treino chamado "Leitura de Range — leia o vilão street a
street". Fui conferir o que nós tínhamos e a resposta me surpreendeu: **já temos leitura de
range, e mais rica que a deles** — `_sondagem_de_range` pergunta a largura do vilão antes de
mostrar as cartas do herói, e `perguntas_de_range` tem cinco formatos.

Mas todos são PRÉ-FLOP. Nenhum estreita a range conforme a mão avança, que é justamente a
habilidade pós-flop: o vilão abriu com 20% das mãos, veio um flop, e agora ele tem *o quê*?

O motor disso apareceu por acidente no dia anterior. `range_de_continuacao` nasceu para consertar
um defeito (em board pareado o filtro admitia 93% das mãos) e é, literalmente, "quem continua
neste board".

── A regra que mantém a pergunta honesta ───────────────────────────────────────────────────

Os distratores são frações **reais de outros boards**, nunca números inventados em volta da
resposta. É a mesma disciplina de `_sondagem_de_range`, cujos distratores são larguras reais de
outras posições. Alternativa inventada ensina a estimar de um jeito que o jogo não confirma.

E a contagem parte da range REAL de abertura daquela posição e profundidade, não de uma range
genérica: perguntar "quanto sobra da range dele" usando a range de outra pessoa seria uma resposta
certa para a pergunta errada.
"""
from __future__ import annotations

import random

# Boards escolhidos por CONTRASTE de textura, não por variedade estética: o que a pergunta ensina
# é que board seco corta mais que board conectado, e isso só aparece se as frações diferirem.
_BOARDS = [
    ('K72r',  ['Kd', '7c', '2h'], 'seco, carta alta'),
    ('A83r',  ['As', '8d', '3c'], 'seco, com ás'),
    ('QJTs',  ['Qh', 'Jh', 'Th'], 'conectado e do mesmo naipe'),
    ('9871',  ['9c', '8d', '7h'], 'conectado'),
    ('442r',  ['4s', '4d', '2c'], 'pareado baixo'),
    ('KK3r',  ['Ks', 'Kd', '3h'], 'pareado alto'),
    ('T64ss', ['Ts', '6s', '4d'], 'duas do mesmo naipe'),
    ('222r',  ['2s', '2d', '2h'], 'trinca no board'),
]

_MIN_DISTANCIA = 8.0     # pontos percentuais entre alternativas, para não colidirem no arredondamento


def _range_de_abertura(pos: str, stack: float) -> list:
    """As mãos que a posição abre de fato, na profundidade pedida. `[]` quando não há carta."""
    try:
        from leaklab.preflop_gto_ranges import (_load, balde_rfi_ou_none, _expand_range,
                                                _norm_pos)
    except Exception:                                          # noqa: BLE001
        return []
    # `balde_rfi_ou_none`, e NAO `balde_rfi`: o segundo SATURA. Pedir 999bb devolvia a carta de
    # 100bb e a pergunta afirmava uma fracao para uma profundidade que a carta nao cobre -- o
    # mesmo defeito que o endpoint /preflop-ranges levou ontem. O guarda pegou na 1a rodada.
    balde = balde_rfi_ou_none(float(stack))
    if not balde:
        return []
    bk = (_load().get('ranges') or {}).get(balde, {})
    spot = (bk.get('RFI') or {}).get(_norm_pos(pos)) or {}
    maos = set(_expand_range(spot.get('raise_hands', '')))
    maos |= set(_expand_range(spot.get('allin_hands', '')))
    return sorted(maos)


def _combos_de(mao: str) -> int:
    return 6 if len(mao) == 2 else (4 if mao.endswith('s') else 12)


def fracao_que_continua(pos: str, stack: float, board: list) -> float | None:
    """Que % dos COMBOS abertos por `pos` continua neste board. `None` sem carta ou sem eval7.

    Combos, não mãos: `AKo` são 12 combinações e `AKs` são 4, então contar mãos daria peso igual a
    coisas que não pesam igual — o mesmo erro que `rangeStats` cometia na grade.
    """
    maos = _range_de_abertura(pos, stack)
    if not maos:
        return None
    try:
        import eval7
        from leaklab.range_de_continuacao import categoria_do_board, continua
    except Exception:                                          # noqa: BLE001
        return None

    board_cards = [eval7.Card(c) for c in board]
    mortas = {str(c) for c in board_cards}
    cat = categoria_do_board(board_cards)

    total = segue = 0
    for hand, _peso in eval7.HandRange(','.join(maos)).hands:
        c1, c2 = hand
        if str(c1) in mortas or str(c2) in mortas:
            continue          # a carta está no board: essa combinação não existe neste spot
        total += 1
        if continua((c1, c2), board_cards, cat, com_draws=True):
            segue += 1
    return round(segue * 100.0 / total, 1) if total else None


def p_quanto_sobra_no_flop(rng: random.Random, pos: str, stack: float):
    """Quanto da range de abertura dele continua neste flop.

    `None` quando não dá para montar alternativas suficientemente distantes: melhor não perguntar
    do que oferecer duas opções que arredondam para o mesmo número.
    """
    medidos = []
    for nome, cartas, textura in _BOARDS:
        f = fracao_que_continua(pos, stack, cartas)
        if f is not None:
            medidos.append((nome, cartas, textura, f))
    if len(medidos) < 4:
        return None

    nome, cartas, textura, certa = rng.choice(medidos)
    # Distratores REAIS: frações de OUTROS boards, afastadas o bastante para não colidirem.
    outros = sorted((m for m in medidos if m[0] != nome),
                    key=lambda m: -abs(m[3] - certa))
    escolhidos, usados = [], [certa]
    for _n, _c, _t, f in outros:
        if all(abs(f - u) >= _MIN_DISTANCIA for u in usados):
            escolhidos.append(f)
            usados.append(f)
        if len(escolhidos) == 2:
            break
    if len(escolhidos) < 2:
        return None

    from leaklab.perguntas_de_range import _embaralhar, _condicoes
    valores = [certa] + escolhidos
    opcoes, idx = _embaralhar(rng, ['%.0f%%' % v for v in valores], 0)
    return {
        'tipo': 'quanto_sobra_no_flop', 'dificuldade': 'intermediaria',
        **_condicoes(pos, stack),
        'board': cartas,
        'pergunta': ('%s abriu a %dbb e veio %s. Quanto da range dele continua neste board?'
                     % (pos, int(stack), ' '.join(cartas))),
        'opcoes': opcoes, 'correta': idx,
        'explicacao': (
            'Cerca de %.0f%% dos combos que %s abre a %dbb continuam num board %s. Continuar é '
            'ter par ou melhor usando as próprias cartas, ou um projeto de verdade. É esta conta '
            'que separa "ele abriu 20%% das mãos" de "ele tem alguma coisa AQUI" — e ela muda '
            'muito com a textura.'
            % (certa, pos, int(stack), textura)),
    }


def p_qual_board_ajuda_mais(rng: random.Random, pos: str, stack: float):
    """Entre dois flops, qual deixa mais da range dele de pé. Ensina textura por comparação."""
    medidos = []
    for nome, cartas, textura in _BOARDS:
        f = fracao_que_continua(pos, stack, cartas)
        if f is not None:
            medidos.append((nome, cartas, textura, f))
    if len(medidos) < 2:
        return None

    rng.shuffle(medidos)
    par = None
    for i in range(len(medidos)):
        for j in range(i + 1, len(medidos)):
            if abs(medidos[i][3] - medidos[j][3]) >= _MIN_DISTANCIA:
                par = (medidos[i], medidos[j])
                break
        if par:
            break
    if not par:
        return None

    a, b = par
    maior = a if a[3] > b[3] else b
    from leaklab.perguntas_de_range import _embaralhar, _condicoes
    opcoes, idx = _embaralhar(rng, [' '.join(a[1]), ' '.join(b[1])], 0 if maior is a else 1)
    return {
        'tipo': 'qual_board_ajuda_mais', 'dificuldade': 'avancada',
        **_condicoes(pos, stack),
        'pergunta': ('%s abriu a %dbb. Em qual destes flops sobra MAIS da range dele?'
                     % (pos, int(stack))),
        'opcoes': opcoes, 'correta': idx,
        'explicacao': (
            'Em %s continuam ~%.0f%% dos combos (%s); em %s, ~%.0f%% (%s). Board que conecta com '
            'muitas mãos deixa a range dele quase inteira de pé, e blefar contra isso é caro. '
            'Board seco corta, e é onde a aposta funciona.'
            % (' '.join(a[1]), a[3], a[2], ' '.join(b[1]), b[3], b[2])),
    }


_POSICOES_COM_CARTA = ('UTG', 'HJ', 'CO', 'BTN', 'SB')


def gerar(rng: random.Random | None = None, pos: str | None = None, stack: float = 30.0,
          dificuldade: str | None = None, tentativas: int = 4):
    """Uma pergunta de leitura de board. `None` quando não há cobertura — o chamador cai no
    exercício normal, em vez de mostrar pergunta inventada."""
    rng = rng or random
    candidatas = [
        ('intermediaria', p_quanto_sobra_no_flop),
        ('avancada',      p_qual_board_ajuda_mais),
    ]
    if dificuldade:
        candidatas = [c for c in candidatas if c[0] == dificuldade]
    if not candidatas:
        return None
    for _ in range(tentativas):
        _dif, fn = rng.choice(candidatas)
        try:
            q = fn(rng, pos or rng.choice(_POSICOES_COM_CARTA), float(stack))
        except Exception:                                      # noqa: BLE001
            q = None
        if q:
            return q
    return None


# ── A sondagem sobre o board DO SPOT ────────────────────────────────────────────────────────
#
# As perguntas acima usam boards de catálogo e ensinam textura no abstrato. Esta é a irmã
# pós-flop de `_sondagem_de_range`: fala do board que o jogador tem na frente AGORA, antes de ele
# ver as próprias cartas. É a mesma inversão de ordem — ler o vilão antes de olhar a própria mão.
#
# ── Quando ela se cala, e por quê ───────────────────────────────────────────────────────────
#
# Só existe quando a range do vilão naquele nó É a range de abertura dele. Em pote 3-bet o BB
# 3-betou e o BTN pagou: a range do BTN ali é "paga um 3-bet", que é outra coisa e muito mais
# estreita. Contar a RFI e chamar de "a range dele" seria a resposta certa para a pergunta errada
# — o defeito que o docblock deste arquivo diz evitar, cometido duas telas adiante.
#
# Por isso a elegibilidade é declarada, não inferida: pote de um aumento só, e o herói é quem
# defende. Fora disso, `None`, e a tela mostra o exercício normal.

_POTE_DE_UM_AUMENTO = ('', 'srp', 'single_raised')
_BLINDS = ('BB', 'SB')


def spot_e_elegivel(spot: dict) -> bool:
    """O vilão deste spot chega com a range de ABERTURA dele? Só aí a conta responde a pergunta."""
    if not spot or spot.get('kind') != 'postflop':
        return False
    if str(spot.get('pot_type') or '').lower() not in _POTE_DE_UM_AUMENTO:
        return False                                    # pote 3-bet: a range dele não é a RFI
    if spot.get('position') not in _BLINDS:
        return False                                    # herói não é quem defende: quem abriu foi ele
    vil = spot.get('vs_position')
    if not vil:
        return False                                    # sem vilão nomeado
    if vil == 'BB':
        return False        # ESTRUTURAL: o BB é o último a agir pré-flop e nunca "abre". A range
                            # dele ali é de DEFESA, e contar a RFI seria a mesma troca de pergunta
                            # do pote 3-bet.
    if vil == 'SB':
        return False        # DECLARADA, não estrutural: o SB abre de verdade, e herói BB vs SB
                            # seria legítimo. Fica de fora porque é a linha onde mora o limp — e
                            # é justamente a linha em que `rangeStats` divergia (9 de 112 spots de
                            # RFI, todos SB). Enquanto o limp não entra na conta de continuação, a
                            # fração do SB não é afirmável. Exceção declarada, não esquecimento.
    board = spot.get('board') or []
    return len(board) >= 3


def sondagem_do_board(spot: dict, rng: random.Random):
    """"Quanto da range dele sobrevive a ESTE board?", sobre o board do próprio spot.

    Distratores continuam sendo frações reais — as dos boards de catálogo, para a mesma posição e
    profundidade. `None` sempre que não der para afirmar o número.
    """
    if not spot_e_elegivel(spot):
        return None
    vil = spot['vs_position']
    stack = float(spot.get('stack_bb') or 0)
    board = list(spot['board'])[:3]          # a range estreitou no FLOP; turn/river é outra conta
    certa = fracao_que_continua(vil, stack, board)
    if certa is None:
        return None

    outros = []
    for _n, cartas, _t in _BOARDS:
        f = fracao_que_continua(vil, stack, cartas)
        if f is not None and abs(f - certa) >= _MIN_DISTANCIA:
            outros.append(f)
    escolhidos, usados = [], [certa]
    for f in sorted(outros, key=lambda v: -abs(v - certa)):
        if all(abs(f - u) >= _MIN_DISTANCIA for u in usados):
            escolhidos.append(f)
            usados.append(f)
        if len(escolhidos) == 2:
            break
    if len(escolhidos) < 2:
        return None

    from leaklab.perguntas_de_range import _embaralhar
    opcoes, idx = _embaralhar(rng, ['%.0f%%' % v for v in [certa] + escolhidos], 0)
    return {
        'tipo': 'sobra_da_range_no_board', 'dificuldade': 'intermediaria',
        'posicao': vil, 'stack': stack, 'board': board,
        'pergunta': ('Antes de ver suas cartas: %s abriu e veio %s. Quanto da range dele continua?'
                     % (vil, ' '.join(board))),
        'opcoes': opcoes, 'correta': idx,
        'explicacao': (
            'Cerca de %.0f%% dos combos que %s abre a %dbb continuam neste flop — par ou melhor '
            'com as próprias cartas, ou projeto de verdade. Estimar isso ANTES de olhar a sua mão '
            'é o que separa "ele abriu larga" de "ele tem alguma coisa AQUI".'
            % (certa, vil, int(stack))),
    }
