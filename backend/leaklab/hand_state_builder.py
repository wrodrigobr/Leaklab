from __future__ import annotations
import re
from typing import Optional, List
from .models import ParsedHand, HandState, ParsedAction

# ── Board por street ──────────────────────────────────────────────────────────
# PokerStars/GGPoker têm DOIS formatos de linha de board, ambos válidos:
#   combinado: *** RIVER *** [7s 6s 2c Jd] [Kh]          (cartas anteriores + nova)
#   separado:  *** RIVER *** [7s 6s 2c] [Jd] [Kh]        (um colchete por street)
# Por isso capturamos o RESTO da linha após o marcador e extraímos TODOS os
# colchetes (igual a parser._extract_board) — assumir só 2 grupos descartava a
# carta do river no formato separado.
_BOARD_STREET_RE = {
    'flop':  re.compile(r'\*\*\* FLOP \*\*\*([^\n]*)'),
    'turn':  re.compile(r'\*\*\* TURN \*\*\*([^\n]*)'),
    'river': re.compile(r'\*\*\* RIVER \*\*\*([^\n]*)'),
}
_BOARD_CARDS_RE = re.compile(r'\[([^\]]+)\]')

def _board_for_street(raw_text: str, street: str) -> list:
    """Retorna o board acumulado até aquela street (inclusivo)."""
    pattern = _BOARD_STREET_RE.get(street)
    if not pattern or not raw_text:
        return []
    m = pattern.search(raw_text)
    if not m:
        return []
    # Extrai TODOS os colchetes da linha da street (1 grupo no flop, 2+ no turn/river,
    # cobrindo o formato separado [flop] [turn] [river] e o combinado [flop+turn] [river]).
    cards = []
    for grp in _BOARD_CARDS_RE.findall(m.group(1)):
        cards.extend(grp.replace(',', ' ').split())
    return cards



# Ações que não representam decisão estratégica do hero
_NON_DECISIONS = {'shows', 'mucks', 'posts'}


def _normalize_action(action: Optional[str]) -> str:
    mapping = {
        None:     'fold',
        'folds':  'fold',
        'checks': 'check',
        'calls':  'call',
        'bets':   'bet',
        'raises': 'raise',
        'all-in': 'shove',
    }
    return mapping.get(action, action or 'fold')


def _position_names(n: int) -> dict:
    """Nomes de posição padrão para mesa de n jogadores.
    ordered[0]=SB, ordered[1]=BB, ..., ordered[n-1]=BTN.
    """
    names: dict = {0: 'SB', 1: 'BB'}
    if n == 2:
        return names
    names[n - 1] = 'BTN'
    if n >= 4:
        names[n - 2] = 'CO'
    if n >= 6:
        names[n - 3] = 'HJ'
    # Preenche do UTG para o centro
    utg_seq = ['UTG', 'UTG+1', 'UTG+2', 'MP1', 'MP2', 'MP3']
    utg_i = 0
    for i in range(2, n):
        if i not in names:
            names[i] = utg_seq[utg_i] if utg_i < len(utg_seq) else f'MP{utg_i + 1}'
            utg_i += 1
    return names


def _infer_position(hand: ParsedHand, hero: str) -> str:
    """Infere posição usando assento real + posição do botão."""
    if not hand.players or not hand.button_seat:
        idx = hand.players.index(hero) if hero in hand.players else 0
        n = len(hand.players)
        return _position_names(n).get(idx, f'P{idx}')

    # Extrair número de assento do hero
    hero_seat = None
    for line in hand.raw_text.splitlines():
        if f': {hero} (' in line and line.startswith('Seat '):
            try:
                hero_seat = int(line.split()[1].rstrip(':'))
            except (ValueError, IndexError):
                pass
            break

    if hero_seat is None:
        idx = hand.players.index(hero) if hero in hand.players else 0
        n = len(hand.players)
        return _position_names(n).get(idx, f'P{idx}')

    # Coletar assentos ativos em ordem
    active_seats = []
    for line in hand.raw_text.splitlines():
        if line.startswith('Seat ') and ': ' in line and '(' in line:
            try:
                seat_num = int(line.split()[1].rstrip(':'))
                active_seats.append(seat_num)
            except (ValueError, IndexError):
                pass

    if not active_seats:
        return 'unknown'

    active_seats = sorted(set(active_seats))
    n = len(active_seats)
    btn = hand.button_seat

    # Reordenar a partir do assento após o botão
    try:
        btn_idx = active_seats.index(btn)
    except ValueError:
        btn_idx = min(range(n), key=lambda i: (active_seats[i] - btn) % 100)

    ordered = active_seats[(btn_idx + 1):] + active_seats[:(btn_idx + 1)]
    # ordered[0]=SB, ordered[1]=BB, ..., ordered[n-1]=BTN

    try:
        hero_order_idx = ordered.index(hero_seat)
    except ValueError:
        return 'unknown'

    return _position_names(n).get(hero_order_idx, f'P{hero_order_idx}')


def _is_in_position(position: str) -> bool:
    return position in {'BTN', 'CO', 'HJ'}


def _pot_up_to(actions: List[ParsedAction], stop_index: int) -> float:
    """Soma todas as apostas/calls/raises até (não incluindo) stop_index."""
    total = 0.0
    for a in actions[:stop_index]:
        if a.action in {'calls', 'bets', 'raises', 'all-in', 'posts'}:
            total += a.amount or 0.0
    return total


def _facing_size_at(actions: List[ParsedAction], hero_index: int,
                    street: str) -> float:
    """Última aposta/raise na street atual antes da ação do hero."""
    facing = 0.0
    for a in actions[:hero_index]:
        if a.street == street and a.action in {'bets', 'raises', 'all-in'}:
            facing = a.amount or 0.0
    return facing


_RAISE_TO_RE = re.compile(r"\bto\s+([\d.]+)", re.IGNORECASE)


def _facing_to_total_at(actions: List[ParsedAction], hero_index: int,
                        street: str) -> float:
    """Tamanho TOTAL ('raise to' X) da última aposta/raise antes do hero — não o
    incremento. PokerStars loga 'raises 546 to 626' e o parser captura 546 (o
    incremento); o GW/canônico raciocina sobre o 'to' total (626). Lê o 'to Y' do
    raw quando presente; senão usa a.amount (formato GG 'raises to Y' já é total)."""
    total = 0.0
    for a in actions[:hero_index]:
        if a.street == street and a.action in {'bets', 'raises', 'all-in'}:
            m = _RAISE_TO_RE.search(a.raw or '')
            total = float(m.group(1)) if m else (a.amount or 0.0)
    return total


def _effective_stack(hand: ParsedHand, hero: str,
                     actions_before: List[ParsedAction]) -> float:
    """Stack efetivo em BBs estimado subtraindo o que o hero já colocou."""
    bb = hand.bb or 1.0

    # Tentar extrair stack inicial do HH
    initial_stack = None
    for line in hand.raw_text.splitlines():
        if f': {hero} (' in line and line.startswith('Seat '):
            try:
                stack_str = line.split('(')[1].split()[0]
                initial_stack = float(stack_str)
            except (IndexError, ValueError):
                pass
            break

    if initial_stack is None:
        return 20.0  # fallback

    spent = sum(
        a.amount or 0.0
        for a in actions_before
        if a.player == hero and a.action in {'calls', 'bets', 'raises', 'all-in', 'posts'}
    )
    return max((initial_stack - spent) / bb, 0.0)


def extract_decision_points(hand: ParsedHand) -> List[HandState]:
    """
    Retorna uma lista de HandState — um por cada decisão estratégica do hero.
    Exclui: posts de blind, shows, mucks.
    Inclui: fold, check, call, bet, raise, jam.
    """
    hero = hand.hero
    if not hero:
        return []

    decision_actions = {'folds', 'checks', 'calls', 'bets', 'raises', 'all-in'}
    states: List[HandState] = []

    for idx, action in enumerate(hand.actions):
        if action.player != hero:
            continue
        if action.action not in decision_actions:
            continue

        street = action.street
        actions_before = hand.actions[:idx]
        pot_size = _pot_up_to(hand.actions, idx)
        facing_size = _facing_size_at(hand.actions, idx, street)
        # Tamanho do open enfrentado em bb ('raise to' total / bb) — usado pra detectar
        # open off-tree (maior que o GTO) e não marcar fold de defesa como crítico (#23).
        _bb_amt = (hand.bb or 0) or 1.0
        facing_to_bb = round(_facing_to_total_at(hand.actions, idx, street) / _bb_amt, 2)
        position = _infer_position(hand, hero)
        eff_stack = _effective_stack(hand, hero, actions_before)

        # Determinar villain_position: quem fez a última aposta antes do hero
        villain_position = 'unknown'
        for a in reversed(actions_before):
            if a.player != hero and a.action in {'bets', 'raises', 'all-in'}:
                villain_position = _infer_position(hand, a.player)
                break

        # Contexto de multi-raise preflop (3-bet/squeeze): conta raises de villains ANTES do
        # hero e se o hero já foi agressor. >=2 raises sem o hero ter agredido = pote 3-bet/
        # squeeze enfrentado a frio — o engine NÃO deve tratar como vs_RFI (defesa vs open).
        preflop_raises_faced = 0
        hero_was_aggressor = False
        if street == 'preflop':
            for a in actions_before:
                if a.street != 'preflop' or a.action not in {'raises', 'all-in'}:
                    continue
                if a.player == hero:
                    hero_was_aggressor = True
                else:
                    preflop_raises_faced += 1

        # Pote LIMPADO (limp): villain deu open-limp/over-limp (calls >= ~1bb) e
        # NÃO houve raise. O hero (tipicamente BB) só completa/dá check de opção.
        # É uma árvore fora da cobertura GTO (capturamos só árvores raise-first) —
        # marca o spot p/ o display rotular "{pos} vs Limp" em vez de silêncio.
        facing_limp = False
        if street == 'preflop' and preflop_raises_faced == 0 and not hero_was_aggressor:
            bb_amt = (hand.bb or 0) or 1.0
            for a in actions_before:
                if (a.street == 'preflop' and a.player != hero
                        and a.action == 'calls' and (a.amount or 0) >= bb_amt * 0.9):
                    facing_limp = True
                    break

        # Cold caller (pra SQUEEZE): posição de quem PAGOU o open antes do hero agir,
        # quando houve open + call sem re-raise. O engine usa isso pra rotear um
        # hero-squeeze (raise sobre open + cold call) ao cenário 'squeeze' em vez de
        # vs_rfi (range errado). Só relevante quando o hero ainda não foi agressor.
        caller_position = ''
        if street == 'preflop' and not hero_was_aggressor:
            _seen_open = False
            for a in actions_before:
                if a.street != 'preflop' or a.player == hero:
                    continue
                if a.action in ('raises', 'all-in'):
                    _seen_open = True
                elif a.action == 'calls' and _seen_open:
                    caller_position = _infer_position(hand, a.player)
                    break

        # Multiway: mais de 2 jogadores ativos na street atual
        active_in_street = set(
            a.player for a in hand.actions
            if a.street == street and a.action not in {'shows', 'mucks'}
        )
        is_multiway = len(active_in_street) > 2
        # Numero exato de oponentes ainda vivos no pote no momento da decisao do hero.
        # Usado para ajustar equity heuristica vs HU em postflop multiway.
        n_active_opponents = max(0, len(active_in_street) - 1)  # exclui hero

        # Vilão em HU postflop quando ele deu CHECK (hero é o agressor): o loop acima só
        # captura quem APOSTOU antes do hero; com o vilão dando check, ficava 'unknown' →
        # o spot caía em "sem vilão" e PERDIA a cobertura GTO (ex.: c-bet HU num pote que
        # começou multiway e afunilou). Se há exatamente 1 oponente vivo na street, ele É
        # o vilão — resolve a posição pra alimentar a range adversária no solver.
        if villain_position == 'unknown' and n_active_opponents == 1 and street != 'preflop':
            _opp = next((p for p in active_in_street if p != hero), None)
            if _opp:
                villain_position = _infer_position(hand, _opp)

        # Board correto para a street atual
        board_at_street = _board_for_street(
            hand.raw_text if hasattr(hand, 'raw_text') else '',
            street
        ) or hand.board or []

        state = HandState(
            hand_id=hand.hand_id,
            street=street,
            hero=hero,
            hero_cards=hand.hero_cards,
            board=board_at_street,
            player_action=_normalize_action(action.action),
            pot_size=pot_size,
            facing_size=facing_size,
            effective_stack_bb=eff_stack,
            position=position,
            villain_position=villain_position,
            is_in_position=_is_in_position(position),
            is_multiway=is_multiway,
            actions=hand.actions,
            metadata={
                'bb': hand.bb or 1.0,
                'raw_hand': hand.raw_text,
                'decision_index': idx,
                'total_decisions': None,  # preenchido depois
                'n_players': len(hand.players) if hand.players else None,  # tamanho da mesa
                'n_active_opponents': n_active_opponents,
                'preflop_raises_faced': preflop_raises_faced,
                'hero_was_aggressor': hero_was_aggressor,
                'facing_limp': facing_limp,
                'caller_position': caller_position,
                'facing_to_bb': facing_to_bb,  # #23: tamanho do open enfrentado (bb)
            },
        )
        states.append(state)

    # Preencher total_decisions em cada state
    for s in states:
        s.metadata['total_decisions'] = len(states)

    return states


def build_hand_state(hand: ParsedHand) -> HandState:
    """
    Compatibilidade retroativa: retorna apenas o último ponto de decisão.
    Para análise completa, usar extract_decision_points().
    """
    points = extract_decision_points(hand)
    if points:
        return points[-1]

    # Fallback para mãos sem decisão do hero (ex: fold pré-flop antes de postar)
    hero = hand.hero or (hand.players[0] if hand.players else 'Hero')
    bb = hand.bb or 1.0
    return HandState(
        hand_id=hand.hand_id,
        street='preflop',
        hero=hero,
        hero_cards=hand.hero_cards,
        board=hand.board,
        player_action='fold',
        pot_size=0.0,
        facing_size=0.0,
        effective_stack_bb=20.0,
        position=_infer_position(hand, hero),
        villain_position='unknown',
        is_in_position=False,
        is_multiway=False,
        actions=hand.actions,
        metadata={'bb': bb, 'raw_hand': hand.raw_text,
                  'decision_index': 0, 'total_decisions': 0},
    )
