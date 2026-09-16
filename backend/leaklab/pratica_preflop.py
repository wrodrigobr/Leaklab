# -*- coding: utf-8 -*-
"""Modo Pratica: de 1 a 4 mesas preflop ao mesmo tempo.

── O pedido (16/09) ──────────────────────────────────────────────────────────────────────────

Um fundador mostrou o Practice do GTO Wizard e pediu algo parecido: abrir varias mesas e validar
spots em paralelo, como no grind de verdade. O dono decidiu comecar SO com preflop, e ir abrindo
outros modos conforme o acervo cresce.

Preflop nao e limitacao aqui. Medido no acervo: **820 spots com a grade inteira declarada** (169
classes, fold explicito em `fold_hands`, nao ausencia muda) em 14 baldes de 3 a 100bb, mais 257
nos condicionados. Quatro mesas nao chegam perto de esgotar isso.

── Por que este modulo NAO sorteia nada ──────────────────────────────────────────────────────

O sorteio mora em `academy_gto_preflop.generate_gto_preflop_question`, que ja carrega duas regras
que doem se forem copiadas: o **gate de premissa** do vs_3bet (a mao precisa estar no range de
abertura, senao o treino pergunta "UTG abriu 84o e levou 3-bet") e o **menu de acoes vindo do
StrategyProvider**, que e fonte unica. Aqui so entra o que e novo: montar a MESA do spot e servir
N mesas distintas.

── O que a mesa modela, e o que ela nao modela ───────────────────────────────────────────────

Modela: os 9 assentos, o botao, os blinds postados, quem foldou antes, a aposta de quem abriu (ou
3-betou), e a aposta do proprio heroi quando ele ja agiu (vs_3bet).

**Nao modela ante**, e isso e deliberado: nem o `_metadata` do acervo nem o no declaram ante, e a
casa ja tem a cicatriz de supor o contrario (a calibracao com o Pluribus mostrou 92% das nossas
acusacoes na mesma direcao justamente porque *a carta ignora o ante*). Inventar 1bb de ante aqui
mudaria o pote que o jogador le para decidir, com base em palpite sobre a solucao de origem.
Quando isso for confirmado na fonte, entra em UM lugar: `_pote_e_apostas`.
"""
from __future__ import annotations

import random

from leaklab.academy_gto_preflop import (_ACTION_ORDER, _hand_to_cards,
                                         generate_gto_preflop_question,
                                         grade_gto_preflop_answer)

#: O acervo tem carta de 3 a 100bb. O Pratica abre as faixas curtas, que e onde vive o MTT, e
#: onde a Academia nao entra de proposito (ela quer fold/call/raise limpos).
STACKS_PRATICA = [10, 14, 17, 20, 30, 40, 50, 75, 100]

#: Teto de mesas. Quatro e o do GTO Wizard, e tambem o que caber em 2x2 sem a mesa virar selo.
MAX_MESAS = 4

#: Quanto vale um BB em fichas na mesa sintetica. O front normaliza para BB via `bb_chips`, então
#: o valor e so escala de exibicao: 100 deixa o 0,5 do SB inteiro.
BB_EM_FICHAS = 100


def _assento(pos: str) -> int:
    """Assento 1..9 na ORDEM DE ACAO (UTG=1 ... BB=9).

    Nao e capricho: o front desenha pelo assento, e a ordem de acao e a unica que faz o vizinho
    da esquerda na tela ser quem fala depois. Tabela de posicao para assento inventada aqui seria
    o terceiro vocabulario de assento do projeto, e os dois que existem ja custaram uma auditoria.
    """
    return _ACTION_ORDER.index(pos) + 1


def _pote_e_apostas(spot: dict, bb_chips: int) -> tuple[dict, float]:
    """`({assento: aposta_em_fichas}, pote_em_fichas)` no momento da decisao do heroi.

    O pote e a SOMA das apostas na mesa, porque preflop nao ha street anterior. Sem ante, pelo
    motivo declarado no cabecalho do modulo.
    """
    apostas: dict[str, float] = {}
    apostas[str(_assento('SB'))] = bb_chips * 0.5
    apostas[str(_assento('BB'))] = bb_chips * 1.0

    heroi = spot.get('position') or ''
    vilao = spot.get('vs_position') or ''
    facing = float(spot.get('facing_size') or 0)
    cenario = spot.get('scenario') or 'rfi'

    if cenario == 'vs_rfi' and vilao:
        # O vilao ABRIU; o heroi ainda nao agiu.
        apostas[str(_assento(vilao))] = bb_chips * facing
    elif cenario == 'vs_3bet' and vilao:
        # O heroi abriu e levou 3-bet. As DUAS apostas ficam na mesa, senao o pote que o jogador
        # le para decidir se pagar cabe fica menor do que e.
        abertura = float(spot.get('open_size') or 2.2)
        apostas[str(_assento(heroi))] = bb_chips * abertura
        apostas[str(_assento(vilao))] = bb_chips * facing

    return {k: round(v, 1) for k, v in apostas.items()}, round(sum(apostas.values()), 1)


def _foldaram(spot: dict) -> list[str]:
    """Quem ja jogou fora, pela ordem de acao. Todo mundo que fala antes e nao e o vilao.

    No RFI a historia e "foldaram ate voce", entao todos os anteriores ao heroi sairam. No vs_RFI
    o vilao abriu, e quem esta entre ele e o heroi foldou. No vs_3bet o heroi abriu de uma posicao
    anterior, entao quem sai e quem fala entre os dois, fora o vilao que 3-betou.
    """
    heroi = spot.get('position') or ''
    vilao = spot.get('vs_position') or ''
    cenario = spot.get('scenario') or 'rfi'
    i_heroi = _ACTION_ORDER.index(heroi) if heroi in _ACTION_ORDER else 0

    if cenario == 'vs_3bet':
        # o heroi e o mais antigo dos dois; folda quem esta entre ele e o vilao
        i_vilao = _ACTION_ORDER.index(vilao) if vilao in _ACTION_ORDER else len(_ACTION_ORDER) - 1
        return [p for i, p in enumerate(_ACTION_ORDER) if i_heroi < i < i_vilao]

    fora = [p for i, p in enumerate(_ACTION_ORDER) if i < i_heroi]
    return [p for p in fora if p != vilao]


def mesa_do_spot(spot: dict, hero_cards=None, bb_chips: int = BB_EM_FICHAS) -> dict:
    """O estado da mesa no MESMO formato de `/player/spots/drill/<id>/table`.

    Falar o formato que o front ja consome e o que deixa o Pratica reusar `PokerTableV3` e o
    `buildDrillStep` sem um segundo caminho de montagem no cliente.
    """
    stack_bb = float(spot.get('stack_bb') or 20)
    stack_fichas = round(stack_bb * bb_chips)
    heroi = spot.get('position') or 'BTN'
    apostas, pote = _pote_e_apostas(spot, bb_chips)
    fora = set(_foldaram(spot))

    seats = []
    for pos in _ACTION_ORDER:
        n = _assento(pos)
        aposta = float(apostas.get(str(n), 0.0))
        seats.append({
            'seat': n,
            'name': 'Hero' if pos == heroi else pos,
            # o stack MOSTRADO e o que sobrou depois do que ele ja pos na mesa, como na sala
            'stack': round(stack_fichas - aposta),
            'bet': aposta,
            'folded': pos in fora,
            'active': pos not in fora,
            'hero': pos == heroi,
            'pos': pos,
        })

    return {
        'seats': seats,
        'button': _assento('BTN'),
        'pot': pote,
        'bb_chips': bb_chips,
        'street': 'preflop',
        'board': [],
        'hero_cards': hero_cards,
    }


def cartas_da_mao(hand: str) -> str:
    """`'K7s'` -> `'Ks7h'`: a CLASSE da mao vira duas cartas concretas, com naipe.

    Existe porque a mesa manda as cartas do heroi como STRING, e o front as le com uma regex de
    `rank + naipe` (`parseCards`). Passar a classe crua fazia `'K7s'` casar so o `'7s'`: uma carta
    em vez de duas, e no desenho da mesa a mao do heroi simplesmente nao aparecia.

    Os naipes sao os de exibicao que a Academia ja usa (`_hand_to_cards`), e nao sorteados: o que
    importa no preflop e a classe, e naipe aleatorio faria a MESMA mao aparecer diferente entre a
    lista e a mesa.
    """
    return ''.join('%s%s' % (c['rank'], c['suit']) for c in _hand_to_cards(hand or ''))


def chave_do_spot(spot: dict) -> str:
    """Identidade do spot para nao repetir entre as mesas ABERTAS.

    A mao entra na chave: o mesmo no com outra mao e outro exercicio, e o acervo tem 169 delas
    por no. Sem a mao, quatro mesas esgotariam os nos de um filtro estreito em poucas rodadas.
    """
    return '%s|%s|%s|%s|%s' % (spot.get('scenario'), spot.get('position'),
                               spot.get('vs_position') or '-', spot.get('stack_bb'),
                               spot.get('hand'))


def mesas(n: int = 1, cenario: str = 'mixed', stacks=None, posicoes=None, evitar=()) -> list[dict]:
    """De 1 a `MAX_MESAS` mesas preflop, todas com spot DIFERENTE entre si.

    `evitar` sao chaves que o cliente ja viu nesta sessao. Elas nao bloqueiam a resposta: com
    filtro estreito o pool fica pequeno, e devolver menos mesas do que o jogador pediu seria pior
    do que repetir uma mao vista ha 50 rodadas. Por isso a tentativa de evitar tem teto, e o que
    NUNCA repete e o spot entre as mesas abertas AGORA, que e o que se ve lado a lado.
    """
    quantas = max(1, min(int(n or 1), MAX_MESAS))
    vistas = set(evitar or ())
    abertas: set[str] = set()
    saida: list[dict] = []

    for _ in range(quantas):
        escolhido = None
        for tentativa in range(40):
            q = generate_gto_preflop_question(cenario, stacks=stacks or STACKS_PRATICA,
                                              permitir_allin=True, posicoes=posicoes)
            ch = chave_do_spot(q['spot'])
            if ch in abertas:
                continue                      # nunca duas mesas iguais na tela
            # as 20 primeiras tentativas tambem fogem do que ele ja viu; depois disso repetir
            # uma antiga e melhor do que entregar menos mesas
            if ch in vistas and tentativa < 20:
                continue
            escolhido = (ch, q)
            break
        if escolhido is None:
            break
        ch, q = escolhido
        abertas.add(ch)
        saida.append({
            'id': ch,
            'spot': q['spot'],
            'scenario': q['scenario'],
            'context': q['context'],
            'hand': q['hand'],
            'hero_cards': q['hero_cards'],
            'options': q['options'],
            'xp_value': q['xp_value'],
            'table': mesa_do_spot(q['spot'], hero_cards=cartas_da_mao(q['hand'])),
        })
    return saida


def corrigir(spot: dict, acao: str) -> dict:
    """Corrige UMA mesa. Delega inteiro para a Academia: o veredito tem de ser o mesmo texto e a
    mesma regua que o jogador ve no exercicio avulso, senao temos duas verdades para o mesmo spot.
    """
    return grade_gto_preflop_answer(spot or {}, acao or '')
