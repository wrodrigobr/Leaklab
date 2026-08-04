from __future__ import annotations
import re
from typing import Optional, List
from .models import ParsedHand, HandState, ParsedAction
from .parser import SEAT_OUT_OF_HAND_RE, raise_total_from_raw

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
    """Nomes de posicao para mesa de n jogadores. ordered[0]=SB, ordered[1]=BB, ordered[n-1]=BTN.

    Delega a `leaklab.posicoes` — a mesma regra vivia aqui e em `_build_replay_data`, e a copia
    de la nao tinha o caso de heads-up (o rotulo da big blind desaparecia). `miolo='MP1'` mantem
    o vocabulario historico deste caminho: o replay usa 'LJ' para casar com o Decision Card e o
    GTO Solver, e trocar o daqui mexeria em lookup de range.
    """
    from leaklab.posicoes import nomes_de_posicao
    return nomes_de_posicao(n, miolo='MP1')


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
            # Assento "out of hand" (movido de outra mesa) não entra na contagem:
            # incluí-lo aumentava o tamanho da mesa e deslocava as posições.
            if SEAT_OUT_OF_HAND_RE.search(line):
                continue
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


_RAISE_TO_RE = re.compile(r"\bto\s+([\d,.]+)", re.IGNORECASE)  # aceita separador de milhar do GG


def _facing_to_total_at(actions: List[ParsedAction], hero_index: int,
                        street: str, hand: 'ParsedHand | None' = None) -> float:
    """Tamanho TOTAL ('raise to' X) da última aposta/raise antes do hero — não o
    incremento. PokerStars loga 'raises 546 to 626' e o parser captura 546 (o
    incremento); o GW/canônico raciocina sobre o 'to' total (626). Lê o 'to Y' do
    raw quando presente.

    Sem 'to Y' o `amount` é o que aquele jogador pôs AGORA, e o total dele é o que ele
    já tinha na frente mais isso. O CoinPoker escreve `ALLIN 107,315.65` para quem já
    tinha 6.000 de SB: o total é 113.315,65, e tratar o número como total subestimava a
    aposta em um blind inteiro. `hand` é opcional só para não quebrar quem chama sem
    ela — sem `hand` os blinds não entram e o resultado degrada para o comportamento
    antigo."""
    total = 0.0
    for i, a in enumerate(actions[:hero_index]):
        if a.street != street or a.action not in {'bets', 'raises', 'all-in'}:
            continue
        m = _RAISE_TO_RE.search(a.raw or '')
        if m:
            total = float(m.group(1).replace(",", ""))
        elif hand is not None:
            total = _committed_on_street(hand, actions, i, street, a.player) + (a.amount or 0.0)
        else:
            total = (a.amount or 0.0)
    return total


def _blind_posted_by(hand: ParsedHand, player: str) -> float:
    """Blind que o jogador postou (SB ou BB), em fichas. Blinds NÃO chegam como ação do
    parser, então quem quiser saber o que já está na frente de alguém no preflop precisa
    reconstruí-los daqui — mesma regra de assentos do `build_table_state_at_decision`
    (em heads-up o botão É o SB, ver [[project_posicao_heads_up]])."""
    seats = sorted(int(s['seat']) for s in (hand.seats or []))
    if not seats or hand.button_seat is None:
        return 0.0
    seat = next((int(s['seat']) for s in (hand.seats or []) if s['name'] == player), None)
    if seat is None:
        return 0.0
    n = len(seats)
    try:
        bi = seats.index(hand.button_seat)
    except ValueError:
        # Botão MORTO: o assento do botão não tem linha 'Seat N:' (jogador saiu). O SB é o
        # primeiro assento vivo DEPOIS dele, então recuamos um para que seats[bi+1] caia
        # ali. Devolver 0 aqui zerava o blind em toda mão de botão morto — foi o que fez a
        # mão 2769806804 (888) contar 2.000 de investido onde havia 4.000.
        prox = min(range(n), key=lambda i: (seats[i] - hand.button_seat) % 100)
        bi = (prox - 1) % n
    if n == 2:
        sb_seat, bb_seat = seats[bi], seats[(bi + 1) % n]
    else:
        sb_seat, bb_seat = seats[(bi + 1) % n], seats[(bi + 2) % n]
    if seat == sb_seat:
        return float(hand.sb or 0)
    if seat == bb_seat:
        return float(hand.bb or 0)
    return 0.0


def _committed_on_street(hand: ParsedHand, actions: List[ParsedAction], upto_index: int,
                         street: str, player: str) -> float:
    """Fichas que `player` tem na frente NESTA street, olhando as ações até `upto_index`.

    Convenção idêntica à do `build_table_state_at_decision`: raise/all-in gravam o
    TO-TOTAL ('raises 1200 to 1600' → 1600), bets/calls somam. No preflop o blind entra
    mesmo sem ser ação do parser.

    Somar `amount` cru NÃO serve: o parser guarda o INCREMENTO do raise, que é medido
    contra a aposta anterior da MESA e não contra o que o próprio jogador já pôs. Um
    'raises 120 to 240' de quem ainda não tinha nada vale 240, não 120."""
    bet = _blind_posted_by(hand, player) if street == 'preflop' else 0.0
    for a in actions[:upto_index]:
        if a.street != street or a.player != player:
            continue
        act = (a.action or '').lower()
        amt = float(a.amount or 0)
        if act in ('raises', 'all-in'):
            m = _RAISE_TO_RE.search(a.raw or '')
            bet = float(m.group(1).replace(",", "")) if m else bet + amt
        elif amt > 0 and act in ('bets', 'calls'):
            bet += amt
    return bet


def _hero_committed_at(hand: ParsedHand, actions: List[ParsedAction], hero_index: int,
                       street: str, hero: str) -> float:
    """Fichas que o hero já tem na frente nesta street, no momento da decisão."""
    return _committed_on_street(hand, actions, hero_index, street, hero)


def _facing_to_call_at(hand: ParsedHand, actions: List[ParsedAction], hero_index: int,
                       street: str, hero: str) -> float:
    """Quanto o hero AINDA PRECISA PAGAR, em fichas — não o tamanho da aposta do vilão.

    `_facing_to_total_at` devolve o TO-TOTAL do vilão, e é ele que identifica o nó
    (uma aposta "to 12bb" é o mesmo nó independente de quem já pôs quanto). Mas o CUSTO
    de pagar é `to_total - o que o hero já tem na frente`, e é esse que manda nas pot
    odds. Confundir os dois cobrava do jogador uma aposta inteira quando ele só devia a
    diferença: mão 93440400037, all-in total de 1.677 sobre o raise de 1.600 do hero —
    o histórico diz `Hero: calls 277.41`, e as pot odds exigiam equity de 27% para uma
    decisão que custava 5%."""
    to_total = _facing_to_total_at(actions, hero_index, street, hand)
    if to_total <= 0:
        return 0.0
    to_call = max(0.0, to_total - _hero_committed_at(hand, actions, hero_index, street, hero))
    # Ninguém paga mais do que tem. Com o hero coberto, o que ele arrisca é o stack, e é
    # esse o número que manda nas pot odds — 12 dos 168 calls conferidos são `and is
    # all-in`, em que o histórico mostra o hero pagando menos que a aposta cheia.
    resto = _hero_remaining_chips(hand, hero, actions[:hero_index])
    if resto is not None:
        to_call = min(to_call, resto)
    return to_call


def _stack_inicial_de(hand: ParsedHand, jogador: str) -> float | None:
    """Stack inicial do jogador, lido da linha 'Seat N: nome (X in chips)'. Regex tolerante:
    casa PS/GG '(21,280 in chips)' e ACR '(30200.00)'."""
    for line in (hand.raw_text or '').splitlines():
        if f': {jogador} (' in line and line.startswith('Seat '):
            m = re.search(r'\(\s*([\d.,]+)', line)
            if m:
                try:
                    return float(m.group(1).replace(',', ''))
                except ValueError:
                    return None
            return None
    return None


def _fichas_restantes_de(hand: ParsedHand, jogador: str,
                         actions_before: List[ParsedAction]) -> float | None:
    """Fichas que sobram ao jogador no ponto da decisão. None quando o stack inicial não foi
    lido (aí quem chama não deve chutar — palpite é pior que a ausência)."""
    inicial = _stack_inicial_de(hand, jogador)
    if inicial is None:
        return None
    n = len(actions_before)
    gasto = sum(_committed_on_street(hand, actions_before, n, st, jogador)
                for st in {a.street for a in actions_before} | {'preflop'})
    return max(0.0, inicial - gasto - float((hand.antes or {}).get(jogador, 0) or 0))


# Nomes antigos, mantidos porque `_facing_to_call_at` e os testes já os usam.
_hero_initial_stack   = _stack_inicial_de
_hero_remaining_chips = _fichas_restantes_de


def _effective_stack(hand: ParsedHand, hero: str,
                     actions_before: List[ParsedAction],
                     street: str = '', oponentes_vivos: set | None = None) -> tuple:
    """Stack EFETIVO em bb: o máximo que ainda pode mudar de mãos. Devolve `(bb, fonte)`.

    Efetivo é `min(eu, ele)` — quem tem 88bb contra um vilão de 14bb está jogando um spot de
    14bb, e a mão se decide ali. Este cálculo NUNCA olhava o oponente: usava só o stack do
    hero, e o número ia para o bucket da range preflop **e** para a profundidade da árvore do
    CFR. Medido: o valor muda em 96,4% das decisões heads-up e o bucket em 49% delas.

    Do lado do hero, o que ainda pode entrar é:

        min(resto_do_hero,  (aposta_dele_na_street - minha_aposta_na_street) + resto_dele)

    O segundo termo é o que ele ainda pode cobrar: o que falta pagar agora mais o que sobra
    atrás dele. Com o vilão já all-in, `resto_dele` é 0 e o efetivo vira exatamente o que dá
    para pagar — que é o certo.

    **Só vale em heads-up.** Em pote multiway com um curto e um profundo NÃO EXISTE um stack
    efetivo; forçar um número trocaria um erro por outro. Fora do heads-up devolve o stack do
    próprio hero, como sempre foi, e diz isso em `fonte`:

        'heads_up'  — min(eu, ele), inequívoco
        'hero_only' — multiway, ou ninguém agiu ainda (RFI: qualquer um atrás pode pagar,
                      e o oponente relevante ainda não existe)
        'fallback'  — nem o stack inicial deu para ler; 20bb, como antes
    """
    bb = hand.bb or 1.0
    meu = _fichas_restantes_de(hand, hero, actions_before)
    if meu is None:
        return 20.0, 'fallback'          # mesmo fallback de sempre

    if not oponentes_vivos or len(oponentes_vivos) != 1:
        return max(meu / bb, 0.0), 'hero_only'

    oponente = next(iter(oponentes_vivos))
    dele = _fichas_restantes_de(hand, oponente, actions_before)
    if dele is None:
        return max(meu / bb, 0.0), 'hero_only'

    n = len(actions_before)
    minha_aposta = _committed_on_street(hand, actions_before, n, street, hero)
    aposta_dele  = _committed_on_street(hand, actions_before, n, street, oponente)
    pendente     = max(0.0, aposta_dele - minha_aposta)
    return max(min(meu, pendente + dele) / bb, 0.0), 'heads_up'


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
        facing_to_bb = round(_facing_to_total_at(hand.actions, idx, street, hand) / _bb_amt, 2)
        # Quanto FALTA PAGAR — não o tamanho da aposta do vilão. Os dois divergem sempre
        # que o hero já tem fichas na street (blind, open que levou 3-bet), e é este que
        # manda no CUSTO da decisão. Ver `_facing_to_call_at`.
        facing_to_call    = _facing_to_call_at(hand, hand.actions, idx, street, hero)
        facing_to_call_bb = round(facing_to_call / _bb_amt, 2)
        position = _infer_position(hand, hero)
        # `eff_stack` é calculado MAIS ABAIXO, depois de `still_in_now` — o efetivo depende de
        # quem ainda está no pote, e isso só se sabe ali.

        # Determinar villain_position: quem fez a última aposta antes do hero.
        # facing_allin = a aposta/raise que o hero enfrenta É um all-in (não dá pra aumentar
        # um all-in → call = a jogada agressiva máxima; usado p/ não flagar call vs shove).
        villain_position = 'unknown'
        villain_name = None
        facing_allin = False
        for a in reversed(actions_before):
            if a.player != hero and a.action in {'bets', 'raises', 'all-in'}:
                villain_name = a.player
                villain_position = _infer_position(hand, a.player)
                facing_allin = (a.action == 'all-in')
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
                # Num pote SEM raise, qualquer 'calls' de villain é limp/complete: open-limp
                # (~1bb) OU complete do SB (~0,5bb). O threshold 0,4bb pega os dois (antes 0,9bb
                # perdia o complete do SB → BB iso sobre SB-limp caía na banda de OPEN, flagrando
                # 3bb como "grande demais").
                if (a.street == 'preflop' and a.player != hero
                        and a.action == 'calls' and (a.amount or 0) >= bb_amt * 0.4):
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

        # Oponentes ainda no pote NO MOMENTO da decisão do hero — não no início da street.
        # O que importa é quando a ação CHEGA no hero: um vilão que foldou ANTES do hero
        # agir (ex.: agressor c-beta, CO folda, hero raise) NÃO conta. Sem isto o spot
        # virava falso multiway (ex.: mão 11: HU no raise, mas contava 2 oponentes).
        #
        # REGRA: só conta como oponente vivo quem JÁ CONTINUOU VOLUNTARIAMENTE (check/call/
        # bet/raise/all-in) e não foldou. Um jogador que ainda NÃO agiu (sentado atrás do
        # hero num open RFI, ou que só postou blind) NÃO conta — ele ainda pode foldar.
        # Sem isto, TODO open/fold preflop virava "multiway" porque os jogadores por agir
        # eram contados como no pote (bug: jogador "na mão" mesmo tendo foldado em seguida).
        # Callers/checkers de streets anteriores seguem contando (a ação está em actions_before),
        # então um pote multiway de verdade que afunila postflop continua correto.
        _VOLUNTARY = {'checks', 'calls', 'bets', 'raises', 'all-in'}
        folded_so_far = set(a.player for a in actions_before if a.action == 'folds')
        committed = set(a.player for a in actions_before if a.action in _VOLUNTARY)
        still_in_now = (committed - folded_so_far) | {hero}  # hero está vivo (decide agora)
        n_active_opponents = max(0, len(still_in_now) - 1)  # exclui hero (ainda no pote)
        is_multiway = n_active_opponents >= 2

        # Stack EFETIVO — precisa saber quem está vivo, por isso vem só agora. Em heads-up é
        # `min(eu, ele)`; fora dele continua sendo o stack do hero, e `fonte` diz qual dos dois
        # foi usado (o consumidor não deve ter que adivinhar). Ver `_effective_stack`.
        #
        # O conjunto NÃO é o `still_in_now`: aquele conta só quem já agiu VOLUNTARIAMENTE, e
        # preflop isso mente. Na mão 100000008, UTG+2 vai all-in com 1,25bb e o hero sobe com
        # 31bb; `still_in_now` via um heads-up de 1,25bb, mas CO/BTN/SB/BB ainda não tinham
        # agido e podiam pagar — o pote podia virar 31bb. Aqui vale "sentou e não foldou":
        # quem ainda tem cartas conta, tendo agido ou não. Postflop os dois conjuntos
        # coincidem, então nada muda lá.
        _sentados = {s['name'] for s in (hand.seats or [])} or set(hand.players or [])
        _vivos_na_mao = (_sentados - folded_so_far) | {hero}
        eff_stack, eff_stack_fonte = _effective_stack(
            hand, hero, actions_before, street, _vivos_na_mao - {hero})

        # Vilão em HU postflop quando ele deu CHECK (hero é o agressor): o loop acima só
        # captura quem APOSTOU antes do hero; com o vilão dando check, ficava 'unknown' →
        # o spot caía em "sem vilão" e PERDIA a cobertura GTO (ex.: c-bet HU num pote que
        # começou multiway e afunilou). Se há exatamente 1 oponente vivo, ele É o vilão —
        # resolve a posição pra alimentar a range adversária no solver.
        if villain_position == 'unknown' and n_active_opponents == 1 and street != 'preflop':
            _opp = next((p for p in still_in_now if p != hero), None)
            if _opp:
                villain_name = _opp
                villain_position = _infer_position(hand, _opp)

        # Estrutura do pote PREFLOP (pra ranges 3-bet no solver postflop): posição do 1º
        # raiser (opener) e do 2º raiser DISTINTO (3-bettor), + pot_type pelo nº de raises.
        # 'srp' (1 raise) é o legado; '3bet' (2) usa ranges vs_RFI.raise / vs_3bet.call.
        _pf_raisers = []
        for a in hand.actions:
            if a.street == 'preflop' and a.action in ('raises', 'all-in') and a.player not in _pf_raisers:
                _pf_raisers.append(a.player)
        _n_pf_raises = sum(1 for a in hand.actions
                           if a.street == 'preflop' and a.action in ('raises', 'all-in'))
        preflop_opener   = _infer_position(hand, _pf_raisers[0]) if len(_pf_raisers) >= 1 else ''
        preflop_3bettor  = _infer_position(hand, _pf_raisers[1]) if len(_pf_raisers) >= 2 else ''
        pot_type = ('limped' if _n_pf_raises == 0 else 'srp' if _n_pf_raises == 1
                    else '3bet' if _n_pf_raises == 2 else '4bet')

        # Tamanho do próprio raise do hero (raise-to em bb) — leitura pelo PARSER, que é a
        # fonte única de "como ler uma linha de hand history" (tolera separador de milhar).
        hero_raise_to_bb = None
        if action.action in ('raises', 'all-in'):
            _hr_total = raise_total_from_raw(action.raw)
            if _hr_total and _bb_amt:
                hero_raise_to_bb = round(_hr_total / _bb_amt, 2)

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
                'villain_name': villain_name,   # HUD: nome do vilão do spot (lookup do perfil)
                'facing_allin': facing_allin,   # hero enfrenta um all-in (call = a agressão)
                'facing_to_bb': facing_to_bb,  # #23: tamanho do open enfrentado (bb)
                # Os dois números abaixo respondem "quanto CUSTA pagar", enquanto o
                # facing_to_bb acima responde "de que tamanho é a aposta". Só coincidem
                # quando o hero não tem nada na frente.
                'facing_to_call':    facing_to_call,
                'facing_to_call_bb': facing_to_call_bb,
                # De onde saiu o `effective_stack_bb`: 'heads_up' (min entre os dois, que é o
                # efetivo de verdade), 'hero_only' (multiway ou RFI — não existe UM efetivo
                # ali) ou 'fallback'. Quem confia no número precisa poder saber disso.
                'effective_stack_source': eff_stack_fonte,
                # Tamanho do PRÓPRIO raise do hero (raise-to em bb). O facing_to_bb acima é o do
                # VILÃO; sem este, o sizing do hero não podia ser agregado ao longo do tempo (era
                # recalculado ao vivo no /replay) e por isso não virava leak nem missão.
                'hero_raise_to_bb': hero_raise_to_bb,
                'pot_type': pot_type,           # Fase 2: srp|3bet|4bet|limped (ranges do solver)
                'preflop_opener': preflop_opener,     # posição do 1º raiser
                'preflop_3bettor': preflop_3bettor,   # posição do 2º raiser (3-bettor)
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


def build_table_state_at_decision(hand, target_street: str, hero_name=None,
                                  target_facing=None) -> dict:
    """Reconstrói o estado por assento ANTES da ação do hero em `target_street`
    (Ghost Table visual — mesa fiel). Caminha hand.actions acumulando por assento:
    folded, stack atual e bet em frente na street. **Folds e botão são fiéis**;
    bets/stacks em potes multi-raise são best-effort (o parser dá o incremento do
    raise, não o to-total). Devolve {seats:[...], button, sb, bb}.

    `target_facing` (BB): quando o hero age 2+x na street (ex.: aposta, leva raise,
    folda), para na ação cujo facing-to-call bate o da decisão — senão a mesa mostraria
    o momento errado (antes do raise do vilão). None = para na 1ª ação do hero.

    BUG B fix: para raises o `bet` por assento passa a ser o TO-TOTAL da street ('raises
    48 to 88' => bet=88), não o incremento acumulado. O parser guarda só o incremento
    (48) em amount, mas o raw tem 'to 88'; lemos o to-total igual a _facing_to_total_at.
    Assim o facing_bb do matcher bate o target_facing do DB e o loop para no ponto certo.

    BUG A fix: devolve `pot` = fichas dos streets ANTERIORES (carried_pot) + bets da street
    atual. Sem isso, postflop first-to-act (facing==0) renderizava pote 0."""
    hero_name = hero_name or hand.hero
    by_name: dict = {}
    for s in (hand.seats or []):
        by_name[s['name']] = {
            'seat': int(s['seat']), 'name': s['name'], 'stack': float(s['stack']),
            'bet': 0.0, 'folded': False, 'hero': s['name'] == hero_name,
        }
    btn = hand.button_seat
    sb_amt, bb_amt = float(hand.sb or 0), float(hand.bb or 0)
    if not by_name:
        return {'seats': [], 'button': btn, 'sb': sb_amt, 'bb': bb_amt, 'pot': 0.0}

    seat_nums = sorted(st['seat'] for st in by_name.values())
    n = len(seat_nums)

    # Postar blinds preflop (não vêm como ações no parser). SB/BB = assentos após o botão.
    if btn in seat_nums and (sb_amt or bb_amt):
        bi = seat_nums.index(btn)
        if n == 2:   # heads-up: o botão é o SB
            sb_seat, bb_seat = seat_nums[bi], seat_nums[(bi + 1) % n]
        else:
            sb_seat, bb_seat = seat_nums[(bi + 1) % n], seat_nums[(bi + 2) % n]
        for st in by_name.values():
            if st['seat'] == sb_seat:
                st['bet'] = sb_amt
                st['stack'] = max(0.0, st['stack'] - sb_amt)
            elif st['seat'] == bb_seat:
                st['bet'] = bb_amt
                st['stack'] = max(0.0, st['stack'] - bb_amt)

    cur_street = 'preflop'
    carried_pot = 0.0   # BUG A: fichas comprometidas nos streets ANTERIORES ao alvo
    # BUG ANTES: antes não vêm como ações; são dead money (vão direto pro pote, NÃO como bet
    # vivo) e reduzem o stack de cada assento que postou. Sem isso o pote ficava ~1bb menor e
    # os stacks ~1 ante maiores em todo spot de nível com ante (maioria das mãos de MTT).
    _antes = getattr(hand, 'antes', None) or {}
    if _antes:
        for st in by_name.values():
            _a = float(_antes.get(st['name'], 0) or 0)
            if _a > 0:
                # all-in pelo ante: posta no máximo o stack disponível (não superestima o pote).
                _paid = min(_a, st['stack'])
                st['stack'] = max(0.0, st['stack'] - _paid)
                carried_pot += _paid
    last_opp_inc = 0.0  # incremento ('raises 200 to 400' => 200) do último agressor ≠ hero na street
    for act in (hand.actions or []):
        if act.street != cur_street:
            cur_street = act.street
            # Antes de zerar, recolhe os bets da street que terminou para o pote.
            carried_pot += sum(st['bet'] for st in by_name.values())
            for st in by_name.values():
                st['bet'] = 0.0   # nova street: zera os bets em frente
            last_opp_inc = 0.0
        # para ANTES da ação do hero na street alvo (o ponto da decisão do drill).
        # Com 2+ ações do hero na street, para na que bate o facing-to-call da decisão.
        if act.player == hero_name and act.street == target_street:
            if target_facing is None:
                break
            opp_max  = max((st0['bet'] for st0 in by_name.values()
                            if not st0['hero'] and not st0['folded']), default=0.0)
            # CONVENÇÃO DO DB: facing_bet (facingToBb) é o TO-TOTAL do vilão em bb
            # (_facing_to_total_at/bb), SEM subtrair o que o hero já pôs na street. Logo
            # o matcher compara opp_max/bb (to-total), não o to-call (opp_max-hero_bet).
            # Subtrair o hero_bet quebrava spots onde o hero já tinha fichas na street
            # (blind, ou open antes de levar 3-bet): seen=to_call ≠ db=to_total → overrun.
            facing_bb = (opp_max / bb_amt) if bb_amt else 0.0
            # Linhas antigas (pré-facingToBb) guardaram o INCREMENTO/bb (facingSize/bb).
            # Casa contra QUALQUER das duas representações — sem isso o matcher overruns
            # nessas linhas legadas e o hero aparece já tendo agido/foldado.
            inc_bb = (last_opp_inc / bb_amt) if bb_amt else 0.0
            tgt = float(target_facing)
            if abs(facing_bb - tgt) <= 0.6 or abs(inc_bb - tgt) <= 0.6:  # tolerância resíduo/rounding
                break
            # senão é uma ação ANTERIOR do hero nesta street → processa e segue
        st = by_name.get(act.player)
        if not st:
            continue
        a = (act.action or '').lower()
        amt = float(act.amount or 0)
        if act.player != hero_name and a in ('bets', 'raises', 'all-in'):
            last_opp_inc = amt   # incremento cru do parser (pra casar target_facing legado)
        if 'fold' in a or 'muck' in a:
            st['folded'] = True
        elif a in ('raises', 'all-in'):
            # BUG B: raise/all-in => o `bet` da street é o TO-TOTAL ('raises 48 to 88' => 88),
            # não a soma dos incrementos. O parser dá só o incremento em amount; o to-total
            # vem do 'to Y' do raw (igual a _facing_to_total_at). Sem 'to Y' (formato GG
            # 'raises to Y' já total, ou all-in [X]) usa amount como incremento.
            m = _RAISE_TO_RE.search(act.raw or '')
            if m:
                to_total = float(m.group(1).replace(",",""))
                inc = max(0.0, to_total - st['bet'])
                st['bet']   = to_total
                st['stack'] = max(0.0, st['stack'] - inc)
            elif amt > 0:
                st['bet']   += amt
                st['stack']  = max(0.0, st['stack'] - amt)
        elif amt > 0 and a in ('bets', 'calls'):
            st['bet']   += amt
            st['stack']  = max(0.0, st['stack'] - amt)

    pot = round(carried_pot + sum(st['bet'] for st in by_name.values()), 1)
    pos_by_seat = _seat_positions(seat_nums, btn)
    return {
        'seats': [
            {'seat':   st['seat'],
             'name':   'Hero' if st['hero'] else st['name'],
             'stack':  round(st['stack'], 1),
             'bet':    round(st['bet'], 1),
             'folded': st['folded'],
             'active': not st['folded'],
             'hero':   st['hero'],
             'pos':    pos_by_seat.get(st['seat'], '')}
            for st in sorted(by_name.values(), key=lambda x: x['seat'])
        ],
        'button': btn,
        'sb':     sb_amt,
        'bb':     bb_amt,
        'pot':    pot,   # BUG A: carried (streets anteriores) + bets da street atual
    }


def _seat_positions(seat_nums, button) -> dict:
    """Posição por assento (BTN/SB/BB/UTG…CO), clockwise a partir do botão. Assim a
    mesa fiel mostra os badges de posição (sem isto, vinham vazios → 'blinds somem')."""
    if not seat_nums or button not in seat_nums:
        return {}
    n = len(seat_nums)
    bi = seat_nums.index(button)
    order = [seat_nums[(bi + k) % n] for k in range(n)]   # botão primeiro, clockwise
    if n == 2:
        names = ['BTN', 'BB']            # heads-up: botão = SB, mas rotula BTN
    else:
        names = ['BTN', 'SB', 'BB']
        rest = n - 3                     # posições não-blind/não-botão: UTG…CO
        for k in range(rest):
            if k == rest - 1:
                names.append('CO')
            elif k == rest - 2 and rest >= 3:
                names.append('HJ')
            elif k == 0:
                names.append('UTG')
            else:
                names.append(f'UTG+{k}')
    return {order[i]: names[i] for i in range(n)}
