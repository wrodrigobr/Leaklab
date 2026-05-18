"""
Ressincroniza decisions.gto_action e decisions.gto_label com os dados reais
armazenados em gto_nodes.strategy_json.

Causa raiz: o worker antigo gravava gto_action baseado em EV puro, sem considerar
a frequência da estratégia. Nodes com check=85% eram classificados como gto_action='allin'.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json as _json
from database.schema import get_conn
from leaklab.gto_utils import compute_spot_hash

GTO_LABELS = ('gto_correct', 'gto_mixed', 'gto_minor_deviation', 'gto_critical')

def _norm(a: str) -> str:
    a = (a or '').strip().lower()
    if a in ('shove', 'jam', 'allin', 'all-in', 'all_in'):
        return 'jam'
    if a.startswith('bet'):
        return 'bet'
    if a.startswith('raise'):
        return 'raise'
    return a

def _freq(data) -> float:
    """Extrai frequência de um item de strategy, suportando {frequency: f} ou float direto."""
    if isinstance(data, dict):
        return float(data.get('frequency', 0))
    return float(data)


def _classify(played: str, strategy: dict) -> tuple[str, str]:
    """Retorna (gto_action, gto_label) baseado na estratégia e ação jogada."""
    if not strategy:
        return played, 'gto_correct'

    # Ordena por frequência (desc)
    sorted_items = sorted(strategy.items(), key=lambda x: _freq(x[1]), reverse=True)
    top_action = sorted_items[0][0]

    # Frequência da ação jogada
    played_norm = _norm(played)
    played_freq = 0.0
    for action, data in strategy.items():
        if _norm(action) == played_norm:
            played_freq = _freq(data)
            break

    # Classificação
    if played_freq >= 0.60:
        gto_label = 'gto_correct'
    elif played_freq >= 0.25:
        gto_label = 'gto_mixed'
    elif played_freq >= 0.10:
        gto_label = 'gto_minor_deviation'
    else:
        gto_label = 'gto_critical'

    return top_action, gto_label


def resync():
    conn = get_conn()
    try:
        decisions = conn.execute("""
            SELECT d.id, d.action_taken, d.gto_action, d.gto_label,
                   d.street, d.position, d.stack_bb, d.facing_bet,
                   d.hero_cards, d.board
            FROM decisions d
            WHERE d.gto_label IN ('gto_correct','gto_mixed','gto_minor_deviation','gto_critical')
        """).fetchall()

        print(f"Decisões com gto_label a verificar: {len(decisions)}")
        updated = 0
        not_found = 0

        for row in decisions:
            r = dict(row)

            # Compute spot hash
            board_raw = r['board'] or '[]'
            try:
                board = _json.loads(board_raw) if isinstance(board_raw, str) else []
            except:
                board = []
            street_cards = {'flop': 3, 'turn': 4, 'river': 5}
            board = board[:street_cards.get(r['street'], len(board))]

            hero_raw = r['hero_cards'] or ''
            if ' ' in hero_raw.strip():
                hero_hand = hero_raw.strip().split()
            elif len(hero_raw) % 2 == 0 and hero_raw:
                hero_hand = [hero_raw[i:i+2] for i in range(0, len(hero_raw), 2)]
            else:
                hero_hand = []

            stack_bb = float(r['stack_bb'] or 30.0)
            facing_bb = float(r['facing_bet'] or 0.0)

            # Try hashes with and without hero hand
            node = None
            for hero in ([hero_hand, []] if hero_hand else [[]]):
                h = compute_spot_hash(r['street'], r['position'], board, hero, stack_bb, facing_bb)
                n = conn.execute(
                    "SELECT gto_action, gto_freq, strategy_json FROM gto_nodes WHERE spot_hash = ?", (h,)
                ).fetchone()
                if n:
                    node = dict(n)
                    break

            if not node:
                not_found += 1
                continue

            # Determine correct gto_action and gto_label from node
            strategy = {}
            if node.get('strategy_json'):
                try:
                    strategy = _json.loads(node['strategy_json'])
                except:
                    pass

            new_gto_action, new_gto_label = _classify(r['action_taken'], strategy)
            if not strategy and node.get('gto_action'):
                # No strategy_json: just use node.gto_action directly
                new_gto_action = node['gto_action']
                played_norm = _norm(r['action_taken'])
                top_norm = _norm(node['gto_action'])
                gf = float(node.get('gto_freq') or 0)
                if played_norm == top_norm or gf >= 0.60:
                    new_gto_label = 'gto_correct'
                elif gf >= 0.25:
                    new_gto_label = 'gto_mixed'
                else:
                    new_gto_label = 'gto_critical'

            old_action = r['gto_action']
            old_label  = r['gto_label']

            if new_gto_action != old_action or new_gto_label != old_label:
                conn.execute(
                    "UPDATE decisions SET gto_action=?, gto_label=? WHERE id=?",
                    (new_gto_action, new_gto_label, r['id'])
                )
                updated += 1
                print(f"  id={r['id']} street={r['street']} pos={r['position']} "
                      f"played={r['action_taken']}: "
                      f"{old_action}/{old_label} -> {new_gto_action}/{new_gto_label}")

        conn.commit()
        print(f"\nAtualizado: {updated} | Sem node: {not_found} | Total: {len(decisions)}")

    finally:
        conn.close()


if __name__ == '__main__':
    resync()
