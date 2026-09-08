# -*- coding: utf-8 -*-
"""Assinatura de um spot pos-flop: o que o torna PARECIDO com outro, para o veredito por
semelhanca (08/09/2026, AY-28).

── Por que existe ─────────────────────────────────────────────────────────────────────────

O acervo de nos do solver e chaveado pelo board carta a carta; simulado em prod, o reuso por
torneio novo e 0% (24.805 spots distintos em 24.814 decisoes de um mes). A assinatura troca a
carta pela ESTRUTURA: a textura do board (carta alta, par, naipes, conexao) e a relacao da mao
do heroi com ele (top pair, overpair, flush draw...), mais rua, posicao, faixa de stack e de
aposta. Com ela, 28% das decisoes de um mes ja tinham vizinho resolvido, e a taxa cresce com o
acervo porque o espaco de assinaturas e finito.

── O que ela NAO e ────────────────────────────────────────────────────────────────────────

Nao substitui o nó exato: o solver continua resolvendo cada spot especifico. A assinatura
serve para achar, numa arvore ja resolvida de board parecido, a MAO que tem a mesma relacao
com aquele board, e ler a estrategia dela enquanto o exato nao chega. Veredito por semelhanca
e provisorio e nunca acusa com severidade; o exato substitui.
"""
from collections import Counter
from typing import Optional

from leaklab.gto_utils import stack_bucket, bet_bucket, normalize_position, board_for_street

RANKS = '23456789TJQKA'
_RV = {r: i for i, r in enumerate(RANKS)}


def _cartas(v) -> list:
    """Aceita lista ['Ah','7d'], string 'Ah7d' ou JSON; devolve cartas de 2 chars."""
    import json
    if not v:
        return []
    if isinstance(v, str):
        s = v.strip()
        if s.startswith('['):
            try:
                v = json.loads(s)
            except ValueError:
                return []
        else:
            v = [s[i:i + 2] for i in range(0, len(s), 2)]
    out = []
    for c in v:
        if isinstance(c, str) and len(c) == 2 and c[0].upper() in RANKS:
            out.append(c[0].upper() + c[1].lower())
    return out


def textura(board) -> Optional[str]:
    """Textura do board: n de cartas, carta alta, par/trinca, naipes, conexao.
    'A-seco-2tone-desconectado' e o que um coach chama de "board parecido"."""
    b = _cartas(board)
    if len(b) < 3:
        return None
    ranks = sorted((_RV[c[0]] for c in b), reverse=True)
    alta = ranks[0]
    alta_cls = 'A' if alta == 12 else 'K' if alta == 11 else 'QJ' if alta >= 9 else 'T9' if alta >= 7 else 'baixo'
    cnt = Counter(ranks)
    pares = 'trinca' if max(cnt.values()) >= 3 else ('par' if 2 in cnt.values() else 'seco')
    naipes = Counter(c[1] for c in b)
    m = max(naipes.values())
    naipe_cls = 'mono' if m >= 3 else ('2tone' if m == 2 else 'rainbow')
    uniq = sorted(set(ranks))
    gaps = [uniq[i + 1] - uniq[i] for i in range(len(uniq) - 1)]
    if gaps and min(gaps) == 1 and len(uniq) >= 3 and (uniq[-1] - uniq[0]) <= 4:
        conex = 'conectado'
    elif gaps and min(gaps) <= 2:
        conex = 'semi'
    else:
        conex = 'desconectado'
    return '%d-%s-%s-%s-%s' % (len(b), alta_cls, pares, naipe_cls, conex)


def relacao_da_mao(board, hand) -> Optional[str]:
    """Como a MAO se relaciona com o board: feita (set, dois pares, trinca, top pair, par medio,
    par baixo, overpair, underpair, par no meio, overcards, nada), flush (flush, flush draw,
    backdoor no flop, nenhum) e straight (straight, draw, nenhum). E o que decide a jogada,
    mais que a carta exata; e o que se compara entre boards parecidos."""
    b = _cartas(board); h = _cartas(hand)
    if len(h) != 2 or len(b) < 3:
        return None
    br = sorted((_RV[c[0]] for c in b), reverse=True)
    hr = sorted((_RV[c[0]] for c in h), reverse=True)
    cb = Counter(br)
    par_mao = hr[0] == hr[1]
    casadas = [r for r in hr if r in cb]
    if par_mao and hr[0] in cb:
        feita = 'set'
    elif len(set(casadas)) >= 2:
        feita = 'dois_pares'
    elif casadas:
        r = casadas[0]
        if cb[r] >= 2:
            feita = 'trinca'
        else:
            feita = 'top_pair' if r == br[0] else ('par_medio' if r > br[-1] else 'par_baixo')
    elif par_mao:
        feita = 'overpair' if hr[0] > br[0] else ('underpair' if hr[0] < br[-1] else 'par_no_meio')
    else:
        over = sum(1 for r in hr if r > br[0])
        feita = 'duas_overcards' if over == 2 else ('uma_overcard' if over == 1 else 'nada')
    naipes = Counter(c[1] for c in b + h)
    nh = {c[1] for c in h}
    if any(naipes[s] >= 5 for s in nh):
        fd = 'flush'
    elif len(b) < 5 and any(naipes[s] >= 4 for s in nh):
        fd = 'flush_draw'
    elif len(b) == 3 and any(naipes[s] == 3 for s in nh):
        fd = 'bd_flush'
    else:
        fd = 'sem_flush'
    ranks = set(br) | set(hr)
    if 12 in ranks:
        ranks = ranks | {-1}                      # o as tambem e o 1 (roda)
    janelas = [sum(1 for r in range(lo, lo + 5) if r in ranks) for lo in range(-1, 9)]
    if max(janelas) >= 5:
        sd = 'straight'
    elif len(b) < 5 and max(janelas) == 4:
        sd = 'straight_draw'
    else:
        sd = 'sem_straight'
    return '%s-%s-%s' % (feita, fd, sd)


def assinatura(street, position, stack_bb, facing_bet_bb, board, hand=None) -> Optional[str]:
    """A chave de semelhanca: 'flop|CO|20-35bb|no_bet|3-A-seco-2tone-desconectado|top_pair-flush_draw-sem_straight'.
    Sem a mao, e a assinatura do BOARD (para achar arvores vizinhas); com a mao, a do spot."""
    # O banco guarda o board COMPLETO da mao em TODA decisao: 59% das linhas de flop em dev
    # carregam 4 ou 5 cartas. Sem cortar, duas decisoes no MESMO flop teriam assinaturas
    # diferentes conforme a mao tenha ido longe ou nao, e a textura descreveria um board que o
    # heroi nao tinha visto. E exatamente o bug de 28/07 (ver gto_utils.board_for_street, que e
    # a fonte unica desta fatia e a mesma que alimenta o compute_spot_hash).
    board = board_for_street(_cartas(board), (street or '').lower())
    tx = textura(board)
    if not tx or not street or (street or '').lower() == 'preflop':
        return None
    partes = [(street or '').lower(), normalize_position(position or ''),
              stack_bucket(float(stack_bb or 0)), bet_bucket(float(facing_bet_bb or 0)), tx]
    if hand is not None:
        rel = relacao_da_mao(board, hand)
        if not rel:
            return None
        partes.append(rel)
    return '|'.join(partes)
