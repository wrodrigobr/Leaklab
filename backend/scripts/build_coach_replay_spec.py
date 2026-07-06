"""
build_coach_replay_spec.py — PROVA do Coach Replay: monta o ReplaySpec de um torneio REAL,
100% ancorado nos engines/dados existentes (leaks reais + mãos-exemplo reais + EV real).
NÃO renderiza vídeo e NÃO inventa nada. É a fonte única que alimentaria o Video Composer.

Uso: python scripts/build_coach_replay_spec.py [tournament_id]
Saída: ../video/src/data/coach_replay_spec.json
"""
import os, sys, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import database.repositories as repo   # noqa: E402

_STREET_PT = {'preflop': 'Pré-flop', 'flop': 'Flop', 'turn': 'Turn', 'river': 'River'}
_ACT_PT = {'fold': 'fold', 'call': 'call', 'raise': 'raise', 'check': 'check', 'bet': 'aposta',
           'jam': 'shove', 'allin': 'shove'}


def _leak_title(spot: str) -> str:
    street, _, action = spot.partition('/')
    return f"{_STREET_PT.get(street, street)}: decisões de {_ACT_PT.get(action, action)}"


def _recommendation(spot: str) -> str:
    street, _, action = spot.partition('/')
    if street == 'preflop':
        return "Revisar os ranges por posição e stack: onde o GTO define fold, call, raise ou shove."
    return "Revisar a linha por textura de board e vantagem de range antes de agir."


def build(tid: int):
    conn = repo.get_conn()
    trow = repo._fetchone(conn, "SELECT id, tournament_name, buy_in FROM tournaments WHERE id = ?", (tid,))
    if not trow:
        print(f"torneio {tid} não encontrado"); return
    t = dict(trow)
    user_id = dict(repo._fetchone(conn, "SELECT user_id FROM tournaments WHERE id = ?", (tid,)))['user_id']
    n_hands = dict(repo._fetchone(conn, "SELECT COUNT(DISTINCT hand_id) AS n FROM decisions WHERE tournament_id = ?", (tid,)))['n']

    # leaks REAIS (ranking unificado GTO-first), top 3
    lk = repo.get_leak_ranking_gto_first(user_id, days=3650, limit=10)
    leaks_src = lk['leaks'][:3]

    leaks = []
    for l in leaks_src:
        spot = l['spot']
        street, _, action = spot.partition('/')
        # mãos-exemplo REAIS deste torneio na família do leak (desvio crítico do GTO)
        rows = conn.execute(repo._adapt(
            "SELECT hand_id, position, hero_cards, best_action, ev_loss_bb, gto_label "
            "FROM decisions WHERE tournament_id = ? AND street = ? AND best_action = ? "
            "AND gto_label IN ('gto_critical','gto_minor_deviation') "
            "ORDER BY COALESCE(ev_loss_bb, 0) DESC LIMIT 3"), (tid, street, action)).fetchall()
        examples = [dict(r) for r in rows]
        ev_bb = conn.execute(repo._adapt(
            "SELECT COALESCE(SUM(ev_loss_bb), 0) AS ev FROM decisions WHERE tournament_id = ? "
            "AND street = ? AND best_action = ? AND gto_label = 'gto_critical'"), (tid, street, action)).fetchone()
        leaks.append({
            'rank': l.get('priority_rank'),
            'spot': spot,
            'title': _leak_title(spot),
            'occurrences': l.get('n'),
            'severity': round(float(l.get('avg_score') or 0), 3),
            'trend': l.get('trend'),
            'ev_lost_bb': round(float(dict(ev_bb)['ev'] or 0), 1),
            'recommendation': _recommendation(spot),
            'examples': [{
                'hand_id': e['hand_id'], 'position': e.get('position'),
                'hero_cards': e.get('hero_cards'), 'gto_action': e.get('best_action'),
                'ev_loss_bb': round(float(e.get('ev_loss_bb') or 0), 2), 'gto_label': e.get('gto_label'),
            } for e in examples],
        })
    conn.close()

    spec = {
        'source': 'engines reais (get_leak_ranking_gto_first + decisions), sem invenção',
        'tournament': {'id': t['id'], 'name': t.get('tournament_name') or f"Torneio #{t['id']}",
                       'buy_in': t.get('buy_in'), 'hands': n_hands},
        'intro': {'hands_analyzed': n_hands, 'leaks_found': len(leaks)},
        'leaks': leaks,
        'plan': [{'week': i + 1, 'focus': lk['title']} for i, lk in enumerate(leaks)],
    }
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'video', 'src', 'data', 'coach_replay_spec.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

    print(f"=== Coach Replay spec — {spec['tournament']['name']} ({n_hands} mãos) ===")
    for l in leaks:
        print(f"\n#{l['rank']} {l['title']} — {l['occurrences']} spots, severidade {l['severity']}, "
              f"tendência {l['trend']}, EV perdido {l['ev_lost_bb']}bb")
        for e in l['examples']:
            print(f"    mão {e['hand_id']} · {e['position']} · {e['hero_cards']} · GTO {e['gto_action']} · {e['ev_loss_bb']}bb")
    print(f"\nPlano: " + " → ".join(f"S{p['week']}: {p['focus']}" for p in spec['plan']))
    print('->', os.path.normpath(path))


if __name__ == '__main__':
    build(int(sys.argv[1]) if len(sys.argv) > 1 else 151)
