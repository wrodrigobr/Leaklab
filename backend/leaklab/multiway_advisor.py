"""
Conselheiro MULTIWAY postflop — recomendação independente do solver HU.

Nosso solver (e Pio) só resolve heads-up. Em pote 3-way+ ele projeta a lógica HU e
recomenda agressão que multiway costuma ser erro (ex.: mão 5 — A2c levanta 93% HU, mas
3-way o certo é fold). Este módulo NÃO usa o solver: estima a equity da mão do hero
contra a(s) range(s) de CONTINUAÇÃO via Monte Carlo (eval7), aplica pot odds e uma
penalidade de REALIZAÇÃO multiway, e devolve a ação correta (fold/call/raise/check/bet)
com os números pra transparência. É uma ESTIMATIVA honesta — rotulada como tal —, não GTO.

Princípios multiway (Galfond): aperta; não blefa-raise contra vários; ás-alto/mãos
marginais raramente apostam ou pagam; só os pedaços fortes do range agridem.
"""
from __future__ import annotations
import random
from functools import lru_cache

try:
    import eval7
    _HAS_EVAL7 = True
except Exception:  # pragma: no cover
    _HAS_EVAL7 = False

from leaklab.draw_detector import detect_draws

# Base de mãos que um vilão poderia ter num pote multiway (sem lixo puro). O FILTRO de
# interação com o board faz o aperto real ("continua com par+ ou draw"). Mantém ampla
# pra não subestimar a força do vilão de forma enviesada.
_BASE_RANGE = (
    "22+,A2s+,K2s+,Q4s+,J6s+,T6s+,96s+,85s+,74s+,64s+,53s+,43s,"
    "A2o+,K8o+,Q9o+,J9o+,T8o+,98o,87o,76o,65o,54o"
)


def norm_action(a) -> str:
    """rstrip 's' + unifica all-in/allin/jam/shove → 'allin'."""
    a = (a or '').strip().lower()
    if not a:
        return ''
    a = a[:-1] if a.endswith('s') else a
    return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a


def _card_str(c) -> str:
    return str(c)


@lru_cache(maxsize=512)
def _continue_combos(board_key: str):
    """Combos da base que INTERAGEM com o board (par+ ou draw) — a range de
    continuação. Cacheado por board. Retorna lista de tuplas (Card, Card)."""
    if not _HAS_EVAL7:
        return []
    board = board_key.split(',') if board_key else []
    board_cards = [eval7.Card(c) for c in board]
    board_set = set(board)
    out = []
    for hand, _w in eval7.HandRange(_BASE_RANGE).hands:
        c1, c2 = hand
        s1, s2 = _card_str(c1), _card_str(c2)
        if s1 in board_set or s2 in board_set:
            continue
        # made hand? (par ou melhor usando as 2 + board)
        score = eval7.evaluate([c1, c2] + board_cards)
        made = eval7.handtype(score) != 'High Card'
        if not made:
            # draw? (flush / oesd / gutshot — descarta backdoors p/ a range de continuação)
            dp = detect_draws(s1 + s2, board)
            if not (dp.flush_draw or dp.oesd or dp.gutshot):
                continue
        out.append((c1, c2))
    return out


def _equity_vs_field(hero_str: str, board: list, n_opp: int, n_sims: int, seed: int):
    """Equity Monte Carlo do hero vs n_opp vilões amostrados da range de continuação,
    completando o board até o river. Determinístico por (hero, board, seed)."""
    rng = random.Random(seed)
    hero = [eval7.Card(hero_str[0:2]), eval7.Card(hero_str[2:4])]
    board_cards = [eval7.Card(c) for c in board]
    dead = set(_card_str(c) for c in hero + board_cards)
    combos = [hc for hc in _continue_combos(','.join(board))
              if _card_str(hc[0]) not in dead and _card_str(hc[1]) not in dead]
    if not combos or n_opp < 1:
        return None
    full = eval7.Deck().cards
    need_board = 5 - len(board_cards)
    win = tie = 0.0
    trials = 0
    for _ in range(n_sims):
        used = set(dead)
        opps = []
        ok = True
        for _i in range(n_opp):
            pick = None
            for _try in range(40):
                cand = combos[rng.randrange(len(combos))]
                a, b = _card_str(cand[0]), _card_str(cand[1])
                if a not in used and b not in used:
                    pick = cand; used.add(a); used.add(b); break
            if pick is None:
                ok = False; break
            opps.append(pick)
        if not ok:
            continue
        avail = [c for c in full if _card_str(c) not in used]
        run = rng.sample(avail, need_board) if need_board > 0 else []
        full_board = board_cards + run
        hs = eval7.evaluate(hero + full_board)
        scores = [eval7.evaluate(list(o) + full_board) for o in opps]
        best = max([hs] + scores)
        if hs == best:
            k = 1 + sum(1 for s in scores if s == best)
            if k == 1:
                win += 1
            else:
                tie += 1.0 / k
        trials += 1
    if trials == 0:
        return None
    return (win + tie) / trials


def _realization_tax(raw_eq: float, is_in_position, n_opp: int,
                     hero_str: str, board: list) -> float:
    """Penalidade de REALIZAÇÃO multiway (quanto da equity crua NÃO se realiza).
    Maior OOP, com mais vilões, e com mão sem showdown forte (ás-alto/draw nu)."""
    tax = 0.02 * max(0, n_opp - 1)            # cada vilão extra dificulta realizar
    if is_in_position is False:
        tax += 0.04
    # mão feita forte realiza bem; ás-alto / draw nu realiza mal
    made_strong = False
    if _HAS_EVAL7 and len(board) >= 3:
        score = eval7.evaluate([eval7.Card(hero_str[0:2]), eval7.Card(hero_str[2:4])]
                               + [eval7.Card(c) for c in board])
        ht = eval7.handtype(score)
        made_strong = ht not in ('High Card', 'Pair')   # 2 pares+ realiza
        if ht == 'High Card':
            tax += 0.05
    if not made_strong:
        tax += 0.02
    return min(tax, 0.15)


_ADVISE_CACHE = {}


def advise_multiway(hero_cards, board, pot_bb, to_call_bb, n_opponents,
                    is_in_position=None, street='flop', eff_stack_bb=None,
                    n_sims=12000):
    """Wrapper cacheado (determinístico por entrada) — evita re-rodar o Monte Carlo
    quando o mesmo spot é avaliado em várias superfícies (card + aderência)."""
    _key = (str(hero_cards), tuple(board or []), round(float(pot_bb or 0), 2),
            round(float(to_call_bb or 0), 2), int(n_opponents or 0), is_in_position,
            street, n_sims)
    if _key not in _ADVISE_CACHE:
        _ADVISE_CACHE[_key] = _advise_impl(hero_cards, board, pot_bb, to_call_bb,
                                           n_opponents, is_in_position, street,
                                           eff_stack_bb, n_sims)
    return _ADVISE_CACHE[_key]


def _advise_impl(hero_cards, board, pot_bb, to_call_bb, n_opponents,
                 is_in_position=None, street='flop', eff_stack_bb=None,
                 n_sims=12000):
    """
    Recomendação multiway independente do solver HU. Retorna dict ou None
    (quando indisponível: sem eval7, sem board, n_opp<2, hero_cards inválidas).

      action        : 'fold'|'call'|'raise'|'check'|'bet'
      equity        : equity crua vs range de continuação (0..1)
      realized_eq   : equity após penalidade de realização multiway
      required_eq   : pot odds necessárias (só quando enfrenta aposta)
      n_opponents   : vilões considerados
      rationale     : texto curto
      confidence    : 'estimate' (sempre — é heurística, não GTO)
    """
    if not _HAS_EVAL7:
        return None
    hs = (hero_cards or '').replace(' ', '')
    if len(hs) != 4 or not board or len(board) < 3:
        return None
    n_opp = int(n_opponents or 0)
    if n_opp < 2:
        return None  # 2+ vilões = genuinamente multiway; HU tem o solver

    seed = (hash((hs, tuple(board), n_opp)) & 0x7FFFFFFF)
    raw = _equity_vs_field(hs, list(board), n_opp, n_sims, seed)
    if raw is None:
        return None
    tax = _realization_tax(raw, is_in_position, n_opp, hs, list(board))
    realized = max(0.0, raw - tax)

    facing = float(to_call_bb or 0) > 0.0
    pot = float(pot_bb or 0)
    call = float(to_call_bb or 0)
    required = (call / (pot + call)) if (facing and (pot + call) > 0) else None

    # Limiares: agredir multiway exige mão FORTE (só valor/proteção). Marginal paga ou passa.
    STRONG = 0.62      # equity crua vs range de continuação que justifica value bet/raise
    FOLD_MARGIN = 0.03 # folga abaixo das pot odds p/ chamar o fold de CLARO
    # is_clear = veredito de ALTA confiança que VALE sobrepor o solver HU. Decisões próximas
    # (bet vs check marginal, fold no limite) NÃO sobrepõem — caem no engine, sem over-flag.
    if facing:
        req = required or 0
        if realized < req - FOLD_MARGIN:
            action, is_clear = 'fold', True
            why = f'realiza {realized*100:.0f}% < {req*100:.0f}% necessário ({n_opp} vilões)'
        elif raw >= STRONG and realized > req:
            action, is_clear = 'raise', True
            why = f'{raw*100:.0f}% vs range de continuação → valor/proteção'
        elif realized >= req:
            action, is_clear = 'call', False
            why = f'realiza {realized*100:.0f}% ≥ {req*100:.0f}%, decisão próxima'
        else:
            action, is_clear = 'fold', False
            why = f'realiza {realized*100:.0f}% ~ {req*100:.0f}% necessário, fold marginal'
    else:
        if raw >= STRONG:
            action, is_clear = 'bet', True
            why = f'{raw*100:.0f}% vs range de continuação → aposta por valor'
        else:
            action, is_clear = 'check', False
            why = f'{raw*100:.0f}% vs {n_opp} vilões — bet vs check é próximo multiway'

    return {
        'action': action,
        'is_clear': is_clear,
        'equity': round(raw, 4),
        'realized_eq': round(realized, 4),
        'required_eq': round(required, 4) if required is not None else None,
        'n_opponents': n_opp,
        'rationale': why,
        'confidence': 'estimate',
    }


def is_hero_leak(adv, hero_action):
    """Dado o veredito multiway e a ação do hero, a jogada é um LEAK claro? Só quando
    adv['is_clear'] (alta confiança); senão None → defere ao engine/label (sem over-flag).
      fold recomendado  → continuar (call/raise/bet) é leak
      bet  recomendado  → não apostar valor (check/fold) é leak
      raise recomendado → foldar mão forte é leak (pagar é aceitável)"""
    if not adv or not adv.get('is_clear'):
        return None
    h = norm_action(hero_action)
    a = norm_action(adv.get('action'))
    if a == 'fold':
        return h in ('call', 'raise', 'bet', 'allin')
    if a == 'bet':
        return h in ('check', 'fold')
    if a == 'raise':
        return h == 'fold'
    return h != a
