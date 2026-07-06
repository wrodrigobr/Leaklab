"""
coach_replay.py — dados do Coach Replay INTERATIVO (reusa o Replayer real por mão).

Fonte da verdade: engines/decisions existentes. Zero invenção. Devolve os erros MAIS CAROS
do torneio (as mãos que valem a pena reassistir na mesa) + o que o herói fez × o GTO + o
plano de estudo. O front abre o replay real (get_replay) de cada hand_id e pausa na decisão.
"""
from __future__ import annotations

_STREET_PT = {'preflop': 'Pré-flop', 'flop': 'Flop', 'turn': 'Turn', 'river': 'River'}
_ACT_PAST = {'fold': 'deu fold', 'call': 'pagou', 'raise': 'deu raise', 'bet': 'apostou',
             'check': 'deu check', 'jam': 'deu shove', 'allin': 'deu shove'}
_ACT_PRES = {'fold': 'folda', 'call': 'paga', 'raise': 'aumenta', 'bet': 'aposta',
             'check': 'dá check', 'jam': 'dá shove', 'allin': 'dá shove'}


def _leak_title(spot: str) -> str:
    street, _, action = spot.partition('/')
    return f"{_STREET_PT.get(street, street)}: decisões de {action}"


def _coach_note(m: dict) -> str:
    taken = (m.get('action_taken') or '').lower()
    gto = (m.get('gto_action') or '').lower()
    ev = abs(float(m.get('ev_loss_bb') or 0))
    return (f"Você {_ACT_PAST.get(taken, taken)}, mas o GTO {_ACT_PRES.get(gto, gto)} aqui. "
            f"Essa decisão custou {round(ev, 1)} big blinds.")


def build_coach_replay(user_id: int, tournament_id: int, top_n: int = 3) -> dict | None:
    """Monta o Coach Replay do torneio (se for do usuário). None se não é dele ou sem dados."""
    import database.repositories as repo
    conn = repo.get_conn()
    try:
        trow = repo._fetchone(conn, repo._adapt(
            "SELECT id, tournament_name, buy_in, user_id FROM tournaments WHERE id = ?"), (tournament_id,))
        if not trow:
            return None
        t = dict(trow)
        if t['user_id'] != user_id:
            return None   # só o dono
        n_hands = dict(repo._fetchone(conn, repo._adapt(
            "SELECT COUNT(DISTINCT hand_id) AS n FROM decisions WHERE tournament_id = ?"), (tournament_id,)))['n']
        # os erros MAIS CAROS (o que vale reassistir), com o que o herói fez × GTO
        rows = conn.execute(repo._adapt(
            "SELECT hand_id, street, position, hero_cards, action_taken, "
            "COALESCE(gto_action, best_action) AS gto_action, ev_loss_bb "
            "FROM decisions WHERE tournament_id = ? AND gto_label = 'gto_critical' "
            "AND ev_loss_bb IS NOT NULL ORDER BY ev_loss_bb DESC LIMIT ?"), (tournament_id, top_n)).fetchall()
        mistakes = [dict(r) for r in rows]
    finally:
        conn.close()

    for m in mistakes:
        m['ev_loss_bb'] = round(float(m.get('ev_loss_bb') or 0), 1)
        m['street_pt'] = _STREET_PT.get(m.get('street'), m.get('street'))
        m['coach_note'] = _coach_note(m)

    # plano de estudo a partir dos leaks reais do jogador (mesma fonte do produto)
    lk = repo.get_leak_ranking_gto_first(user_id, days=3650, limit=3).get('leaks', [])
    plan = [{'week': i + 1, 'focus': _leak_title(l['spot'])} for i, l in enumerate(lk)]

    total_ev = round(sum(abs(m['ev_loss_bb']) for m in mistakes), 1)
    return {
        'tournament': {'id': t['id'], 'name': t.get('tournament_name') or f"Torneio #{t['id']}",
                       'buy_in': t.get('buy_in'), 'hands': n_hands},
        'intro': {'hands_analyzed': n_hands, 'mistakes_shown': len(mistakes), 'ev_lost_bb': total_ev},
        'mistakes': mistakes,
        'plan': plan,
    }
