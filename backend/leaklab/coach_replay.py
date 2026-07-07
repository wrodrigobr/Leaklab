"""
coach_replay.py — dados do Coach Replay: o WALKTHROUGH da sessão (reusa o Replayer real).

Fonte da verdade: engines/decisions existentes. Zero invenção. Devolve a PLAYLIST cronológica
das mãos que valem revisão (pula os folds pré-flop corretos e os spots triviais automáticos),
cada uma com o veredito, o custo de EV e uma narração, mais o plano de estudo. O front abre o
replay real (get_replay) de cada hand_id e navega mão a mão pela sessão.

Filtro (apertado, "só decisões reais"): mantém a mão se ela viu o flop (decisão postflop de
verdade), OU tem qualquer erro/desvio (severidade não-correta), OU foi um confronto all-in
pré-flop (shove ou showdown pré-flop). Cai fora: as mãos que só foldaram pré-flop no certo e os
opens triviais que levaram os blinds sem confronto.
"""
from __future__ import annotations

from leaklab.verdict import verdict3, CORRECT, ACCEPTABLE, ERROR

_STREET_PT = {'preflop': 'pré-flop', 'flop': 'flop', 'turn': 'turn', 'river': 'river'}
_STREET_RANK = {'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}
_ACT_PAST = {'fold': 'deu fold', 'call': 'pagou', 'raise': 'deu raise', 'bet': 'apostou',
             'check': 'deu check', 'shove': 'deu shove', 'jam': 'deu shove', 'allin': 'deu shove'}
_ACT_PRES = {'fold': 'folda', 'call': 'paga', 'raise': 'aumenta', 'bet': 'aposta',
             'check': 'dá check', 'shove': 'dá shove', 'jam': 'dá shove', 'allin': 'dá shove'}
_ACT_NOUN = {'fold': 'fold', 'call': 'call', 'raise': 'raise', 'bet': 'aposta',
             'check': 'check', 'shove': 'shove', 'jam': 'shove', 'allin': 'shove'}
_ACT_INF = {'fold': 'foldar', 'call': 'pagar', 'raise': 'aumentar', 'bet': 'apostar',
            'check': 'dar check', 'shove': 'dar shove', 'jam': 'dar shove', 'allin': 'dar shove'}


def _leak_title(spot: str) -> str:
    street, _, action = spot.partition('/')
    return f"{_STREET_PT.get(street, street).capitalize()}: decisões de {action}"


def _act_past(a: str) -> str:
    return _ACT_PAST.get((a or '').lower(), (a or '').lower())


def _act_pres(a: str) -> str:
    return _ACT_PRES.get((a or '').lower(), (a or '').lower())


def _narration(focus: dict, verdict: str, reached_street: str, is_allin: bool) -> str:
    """Frase pronta do coach pra mão, ancorada na decisão-foco. PT, sem travessão. O custo em
    bb NÃO entra no texto (o badge de EV do card já mostra, evita número divergente)."""
    st = _STREET_PT.get(focus.get('street'), focus.get('street'))
    act = (focus.get('action_taken') or '').lower()
    gto_act = (focus.get('gto_action') or focus.get('best_action') or '').lower()
    if verdict == ERROR:
        return f"No {st}, você {_act_past(act)}, mas o GTO {_act_pres(gto_act)} aqui."
    if verdict == ACCEPTABLE:
        noun = _ACT_NOUN.get(act, act)
        inf = _ACT_INF.get(gto_act, gto_act)
        return f"Seu {noun} no {st} é aceitável, mas o GTO tende a {inf}. A diferença é pequena."
    # correto (mão mantida por ter ido ao postflop ou por ser confronto all-in)
    if is_allin:
        return "All-in pré-flop. Decisão correta, sem vazamento."
    rp = _STREET_PT.get(reached_street, reached_street)
    return f"Você conduziu a mão até o {rp} e jogou alinhado ao GTO."


def _hand_verdict(decs: list[dict]) -> str:
    """Pior veredito da mão (erro > aceitável > correto). None de severidade conta como correto."""
    levels = {verdict3(d.get('label')) for d in decs}
    if ERROR in levels:
        return ERROR
    if ACCEPTABLE in levels:
        return ACCEPTABLE
    return CORRECT


def _pick_focus(decs: list[dict], hand_verdict: str) -> dict:
    """Decisão que ancora a narração: o pior erro (maior EV), senão o clímax (rua mais profunda)."""
    if hand_verdict == ERROR:
        cand = [d for d in decs if verdict3(d.get('label')) == ERROR]
    elif hand_verdict == ACCEPTABLE:
        cand = [d for d in decs if verdict3(d.get('label')) == ACCEPTABLE]
    else:
        cand = decs
    if hand_verdict in (ERROR, ACCEPTABLE):
        return max(cand, key=lambda d: abs(float(d.get('ev_loss_bb') or 0)))
    # correto: a decisão da rua mais profunda (o clímax da mão)
    return max(cand, key=lambda d: _STREET_RANK.get(d.get('street'), 0))


def build_coach_replay(user_id: int, tournament_id: int) -> dict | None:
    """Monta o walkthrough da sessão (se o torneio é do usuário). None se não é dele ou sem dados.

    `tournament_id` é o id INTERNO (o endpoint já resolveu o código → id)."""
    import database.repositories as repo
    conn = repo.get_conn()
    try:
        trow = repo._fetchone(conn, repo._adapt(
            "SELECT id, tournament_id, tournament_name, buy_in, user_id FROM tournaments WHERE id = ?"),
            (tournament_id,))
        if not trow:
            return None
        t = dict(trow)
        if t['user_id'] != user_id:
            return None   # só o dono
        rows = conn.execute(repo._adapt(
            "SELECT hand_id, street, position, hero_cards, action_taken, best_action, "
            "COALESCE(gto_action, best_action) AS gto_action, label, ev_loss_bb, showdown_result "
            "FROM decisions WHERE tournament_id = ? ORDER BY hand_id ASC, id ASC"),
            (tournament_id,)).fetchall()
        decisions = [dict(r) for r in rows]
    finally:
        conn.close()

    # agrupa por mão preservando a ordem cronológica (hand_id asc)
    by_hand: dict = {}
    for d in decisions:
        by_hand.setdefault(d['hand_id'], []).append(d)

    total_hands = len(by_hand)
    playlist: list[dict] = []
    for hand_id, decs in by_hand.items():
        reached_rank = max(_STREET_RANK.get(d.get('street'), 0) for d in decs)
        reached_street = next(s for s, r in _STREET_RANK.items() if r == reached_rank)
        saw_flop = reached_rank >= 1
        hverdict = _hand_verdict(decs)
        has_deviation = hverdict in (ERROR, ACCEPTABLE)
        preflop_allin = any(
            d.get('street') == 'preflop' and
            ((d.get('action_taken') or '').lower() in ('shove', 'jam', 'allin')
             or d.get('showdown_result') not in (None, ''))
            for d in decs)

        # filtro apertado: só entram as mãos com decisão real
        if not (saw_flop or has_deviation or preflop_allin):
            continue

        focus = _pick_focus(decs, hverdict)
        hero_cards = next((d.get('hero_cards') for d in decs if d.get('hero_cards')), '') or ''
        position = next((d.get('position') for d in decs if d.get('position')), '') or ''
        ev_cost = round(sum(abs(float(d.get('ev_loss_bb') or 0))
                            for d in decs if verdict3(d.get('label')) == ERROR), 1)
        playlist.append({
            'hand_id': str(hand_id),
            'position': position,
            'hero_cards': hero_cards,
            'street_reached': reached_street,
            'street_reached_pt': _STREET_PT.get(reached_street, reached_street).capitalize(),
            'verdict': hverdict,
            'ev_loss_bb': ev_cost,
            'narration': _narration(focus, hverdict, reached_street, preflop_allin),
        })

    for i, h in enumerate(playlist):
        h['seq'] = i + 1

    # plano de estudo a partir dos leaks reais do jogador (mesma fonte do produto)
    lk = repo.get_leak_ranking_gto_first(user_id, days=3650, limit=3).get('leaks', [])
    plan = [{'week': i + 1, 'focus': _leak_title(l['spot'])} for i, l in enumerate(lk)]

    mistakes_count = sum(1 for h in playlist if h['verdict'] == ERROR)
    total_ev = round(sum(h['ev_loss_bb'] for h in playlist), 1)
    return {
        'tournament': {'id': t['id'], 'code': t.get('tournament_id'),
                       'name': t.get('tournament_name') or f"Torneio #{t['id']}",
                       'buy_in': t.get('buy_in'), 'hands': total_hands},
        'intro': {
            'hands_total': total_hands,
            'hands_kept': len(playlist),
            'hands_skipped': total_hands - len(playlist),
            'mistakes_count': mistakes_count,
            'ev_lost_bb': total_ev,
        },
        'hands': playlist,
        'plan': plan,
    }
