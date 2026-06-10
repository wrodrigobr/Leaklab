"""
opponent_stats.py — Fase 1 do HUD de comportamento de oponentes.

Varre as ações de TODOS os jogadores das mãos (não só do hero) e acumula
estatísticas de tendência por jogador, com NUMERADOR e DENOMINADOR (oportunidades)
por stat — pra poder gatear por amostra. Read-only: não toca o motor de decisão.

Princípio (igual ao resto da plataforma): nenhum read sem amostra suficiente.
Abaixo do gate, a taxa vem None (a UI mostra "amostra baixa", não um palpite).

Stats (definições padrão HM/PT3):
  VPIP, PFR, 3-bet, fold-to-3bet, c-bet, fold-to-c-bet, AF (agressão postflop), WTSD.

Limitações conhecidas (sinalizar ao usuário):
  - só funciona com nome estável (PokerStars / GG não-anônimo); GG anônimo → sem tracking;
  - só as mesas onde o hero sentou;
  - em MTT a amostra por vilão costuma ser pequena → a maioria dos reads só fica
    confiável em torneios longos / mesa final.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Optional

# ── Gates de amostra (denominador mínimo p/ a taxa ser exibível) ─────────────────
GATES = {
    'vpip': 15, 'pfr': 15, 'threebet': 12, 'fold3bet': 10,
    'cbet': 8, 'foldcbet': 8, 'af': 8, 'wtsd': 8,
}
MIN_HANDS_FOR_TYPE = 20          # mínimo de mãos vistas p/ arriscar um arquétipo

_VOLUNTARY = {'calls', 'raises', 'all-in'}
_AGGR = {'bets', 'raises', 'all-in'}
_POSTFLOP = ('flop', 'turn', 'river')


def _blank() -> dict:
    return defaultdict(int)


def _process_hand(hand) -> dict:
    """Contribuições de UMA mão por jogador (incrementos). Separar o per-hand do
    acúmulo global mantém a lógica 'uma vez por mão' (VPIP etc.) limpa."""
    out: dict = defaultdict(_blank)
    players = list(hand.players or [])
    for p in players:
        out[p]['hands'] = 1

    by_street: dict = {'preflop': [], 'flop': [], 'turn': [], 'river': []}
    for a in hand.actions:
        st = a.street
        if st in by_street and a.action not in ('shows', 'mucks'):
            by_street[st].append(a)

    folded_pre: set = set()       # foldou no preflop
    folded_post: set = set()      # foldou em flop/turn/river

    # ── PREFLOP: VPIP, PFR, 3-bet (+opp), fold-to-3bet (+opp) ────────────────────
    n_raises = 0
    first_raiser: Optional[str] = None
    acted: set = set()            # já tomou a 1ª decisão voluntária/fold
    threebet_seen = False         # houve um 3-bet (2º raise)
    awaiting_open_resp = False    # esperando a resposta do opener ao 3-bet

    for a in by_street['preflop']:
        p, act = a.player, a.action
        if act == 'posts':
            continue

        # Resposta do opener ao 3-bet (fold-to-3bet) — antes de processar como nova ação
        if awaiting_open_resp and p == first_raiser:
            out[p]['fold3bet_opp'] = 1
            if act == 'folds':
                out[p]['fold3bet'] = 1
            awaiting_open_resp = False

        first_action = p not in acted

        # 3-bet: oportunidade = 1ª ação do jogador enfrentando ≥1 raise (um open)
        if first_action and n_raises >= 1:
            out[p]['threebet_opp'] = 1
            if act in ('raises', 'all-in'):
                out[p]['threebet'] = 1

        if act in ('raises', 'all-in'):
            out[p]['vpip'] = 1
            out[p]['pfr'] = 1
            n_raises += 1
            if n_raises == 1:
                first_raiser = p
            elif n_raises == 2:
                threebet_seen = True
                awaiting_open_resp = True   # o opener ainda vai responder ao 3-bet
        elif act == 'calls':
            out[p]['vpip'] = 1
        elif act == 'folds':
            folded_pre.add(p)
        # checks: não é VPIP (BB de opção)
        acted.add(p)

    # ── POSTFLOP: c-bet (+opp), fold-to-cbet (+opp), AF, WTSD ────────────────────
    pfr_aggressor = first_raiser   # último/único raiser preflop = agressor (aprox: o opener)
    # (refina: o ÚLTIMO raiser preflop é o agressor que dá c-bet)
    for a in by_street['preflop']:
        if a.action in ('raises', 'all-in'):
            pfr_aggressor = a.player

    flop = by_street['flop']
    saw_flop = bool(flop)

    # quem viu o flop = estava na mão (não foldou preflop)
    live_at_flop = [p for p in players if p not in folded_pre] if saw_flop else []

    # c-bet: agressor preflop apostou primeiro no flop?
    cbet_player = None
    if saw_flop and pfr_aggressor and pfr_aggressor in live_at_flop:
        out[pfr_aggressor]['cbet_opp'] = 1
        # primeira aposta do flop pelo agressor
        for a in flop:
            if a.action == 'bets':
                if a.player == pfr_aggressor:
                    out[pfr_aggressor]['cbet'] = 1
                    cbet_player = pfr_aggressor
                break  # só a primeira aposta conta como "o c-bet"

    # fold-to-cbet: quem agiu DEPOIS do c-bet no flop
    if cbet_player:
        seen_cbet = False
        for a in flop:
            if not seen_cbet:
                if a.player == cbet_player and a.action == 'bets':
                    seen_cbet = True
                continue
            # ações após o c-bet
            if a.action in ('folds', 'calls', 'raises', 'all-in'):
                out[a.player]['foldcbet_opp'] = 1
                if a.action == 'folds':
                    out[a.player]['foldcbet'] = 1

    # AF + folds postflop + WTSD
    for st in _POSTFLOP:
        for a in by_street[st]:
            p, act = a.player, a.action
            if act in _AGGR:
                out[p]['pf_aggr'] += 1
            elif act == 'calls':
                out[p]['pf_calls'] += 1
            elif act == 'folds':
                folded_post.add(p)

    if saw_flop:
        for p in live_at_flop:
            out[p]['saw_flop'] = 1
            if p not in folded_post:
                out[p]['wtsd'] = 1

    return out


def accumulate(hands) -> dict:
    """Acumula as contribuições de várias mãos → dict[player -> counters]."""
    acc: dict = defaultdict(_blank)
    for hand in hands:
        try:
            per = _process_hand(hand)
        except Exception:
            continue
        for p, d in per.items():
            for k, v in d.items():
                acc[p][k] += v
    return acc


def _rate(num: int, den: int, gate: int) -> Optional[float]:
    """Taxa só quando o denominador passa o gate; senão None (amostra baixa)."""
    if den < gate or den <= 0:
        return None
    return round(num / den, 4)


def _classify(s: dict) -> str:
    """Arquétipo a partir das taxas gateadas. 'unknown' se amostra insuficiente."""
    if s['hands'] < MIN_HANDS_FOR_TYPE:
        return 'unknown'
    vpip, pfr, af = s['vpip_pct'], s['pfr_pct'], s['af']
    fcb, wtsd = s['foldcbet_pct'], s['wtsd_pct']
    if vpip is None or pfr is None:
        return 'unknown'
    # calling station: paga muito, agride pouco, vai a showdown
    if vpip >= 0.40 and (af is None or af < 1.5) and \
       ((fcb is not None and fcb < 0.40) or (wtsd is not None and wtsd > 0.32)):
        return 'calling_station'
    # nit: muito tight + foldão
    if vpip < 0.15 and pfr < 0.12 and (fcb is None or fcb > 0.55):
        return 'nit'
    # maniac: hiper agressivo
    if vpip >= 0.45 and pfr >= 0.35 and (af is not None and af >= 3.0):
        return 'maniac'
    # LAG: solto e agressivo
    if vpip >= 0.28 and pfr >= 0.20 and (af is None or af >= 1.8):
        return 'lag'
    # TAG: tight e agressivo (PFR colado no VPIP)
    if 0.15 <= vpip <= 0.27 and pfr >= vpip * 0.6:
        return 'tag'
    return 'unknown'


def finalize(acc: dict) -> dict:
    """Converte os counters em perfis: taxas (gateadas), AF, arquétipo, confiança."""
    profiles: dict = {}
    for p, c in acc.items():
        hands = c.get('hands', 0)
        af_den = c.get('pf_calls', 0)
        af = round(c.get('pf_aggr', 0) / af_den, 2) if af_den >= GATES['af'] else None
        s = {
            'hands': hands,
            'vpip_pct':     _rate(c.get('vpip', 0), hands, GATES['vpip']),
            'pfr_pct':      _rate(c.get('pfr', 0), hands, GATES['pfr']),
            'threebet_pct': _rate(c.get('threebet', 0), c.get('threebet_opp', 0), GATES['threebet']),
            'fold3bet_pct': _rate(c.get('fold3bet', 0), c.get('fold3bet_opp', 0), GATES['fold3bet']),
            'cbet_pct':     _rate(c.get('cbet', 0), c.get('cbet_opp', 0), GATES['cbet']),
            'foldcbet_pct': _rate(c.get('foldcbet', 0), c.get('foldcbet_opp', 0), GATES['foldcbet']),
            'af':           af,
            'wtsd_pct':     _rate(c.get('wtsd', 0), c.get('saw_flop', 0), GATES['wtsd']),
            # denominadores expostos (a UI mostra a amostra)
            'opps': {
                'hands': hands, 'threebet': c.get('threebet_opp', 0),
                'fold3bet': c.get('fold3bet_opp', 0), 'cbet': c.get('cbet_opp', 0),
                'foldcbet': c.get('foldcbet_opp', 0), 'af': af_den, 'wtsd': c.get('saw_flop', 0),
            },
        }
        s['archetype'] = _classify(s)
        s['confidence'] = 'high' if (hands >= MIN_HANDS_FOR_TYPE and s['archetype'] != 'unknown') \
            else ('low' if hands >= 8 else 'insufficient')
        profiles[p] = s
    return profiles


def build_profiles(hands) -> dict:
    """Pipeline completo: mãos → perfis por jogador."""
    return finalize(accumulate(hands))
