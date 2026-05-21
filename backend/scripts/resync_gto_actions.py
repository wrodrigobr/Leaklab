"""
resync_gto_actions.py — Ressincroniza decisions.gto_action e gto_label.

Para cada decisão com gto_label (minor_deviation/critical/mixed/correct):
  1. Busca nó via compute_spot_hash com fallbacks a/b
  2. Valida que o board do nó bate com o board da decisão
  3. Aplica guard SPR: jam dominante com SPR > 8 e facing=0 → rejeita nó
  4. Recalcula gto_action e gto_label a partir da estratégia do nó
  5. Atualiza se diferente

Uso:
    python scripts/resync_gto_actions.py          # dry-run — apenas mostra mudanças
    python scripts/resync_gto_actions.py --apply  # aplica mudanças
    python scripts/resync_gto_actions.py --apply --user-id 5
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from database.schema import get_conn
from database.repositories import get_gto_node
from leaklab.gto_utils import compute_spot_hash

_JAM_KEYS = {'shove', 'jam', 'allin', 'all-in', 'all_in'}


def _norm(a: str, facing_bb: float = 0.0) -> str:
    a = (a or '').strip().lower()
    if a in _JAM_KEYS:
        return 'jam'
    if a.startswith('bet'):
        return 'bet'
    if a.startswith('raise'):
        return 'bet' if facing_bb == 0 else 'raise'
    return a


def _freq(data) -> float:
    if isinstance(data, dict):
        return float(data.get('frequency', 0))
    return float(data)


def _classify(played: str, strategy: dict, facing_bb: float) -> tuple:
    """Retorna (gto_action, gto_label) baseado na estratégia e ação jogada."""
    if not strategy:
        return played, 'gto_correct'

    sorted_items = sorted(strategy.items(), key=lambda x: _freq(x[1]), reverse=True)
    top_action   = _norm(sorted_items[0][0], facing_bb)

    played_norm  = _norm(played, facing_bb)
    played_freq  = 0.0
    for action, data in strategy.items():
        if _norm(action, facing_bb) == played_norm:
            played_freq = _freq(data)
            break

    if played_freq >= 0.60:
        gto_label = 'gto_correct'
    elif played_freq >= 0.25:
        gto_label = 'gto_mixed'
    elif played_freq >= 0.10:
        gto_label = 'gto_minor_deviation'
    else:
        gto_label = 'gto_critical'

    return top_action, gto_label


def _valid_node(n, street, board_for_hash):
    """Rejeita nó com street ou board incorretos (colisão de hash SHA256[:16])."""
    if not n:
        return None
    if n.get('street', '').lower() != street.lower():
        return None
    try:
        node_board = sorted(json.loads(n.get('board') or '[]') if isinstance(n.get('board'), str) else (n.get('board') or []))
        if board_for_hash and node_board and node_board != sorted(board_for_hash):
            return None
    except Exception:
        pass
    return n


def resolve(r: dict):
    """Retorna (gto_action, gto_label, node_found) para uma decisão."""
    street    = r.get('street', '')
    position  = r.get('position', '')
    facing_bb = float(r.get('facing_bet') or 0.0)
    stack_bb  = float(r.get('stack_bb') or 30.0)
    pot_bb    = float(r.get('pot_size') or 0.0)

    try:
        board_raw = r.get('board') or '[]'
        board = json.loads(board_raw) if isinstance(board_raw, str) else (board_raw or [])
    except Exception:
        board = []

    _street_cards = {'flop': 3, 'turn': 4, 'river': 5}
    board_for_hash = board[:_street_cards.get(street, len(board))]

    hand_raw = r.get('hero_cards') or ''
    if isinstance(hand_raw, str) and hand_raw.strip():
        _raw = hand_raw.strip()
        hero_hand = _raw.split() if ' ' in _raw else [_raw[i:i+2] for i in range(0, len(_raw), 2)]
    else:
        hero_hand = []

    node = None
    if hero_hand:
        node = _valid_node(
            get_gto_node(compute_spot_hash(street, position, board_for_hash, hero_hand, stack_bb, facing_bb)),
            street, board_for_hash
        )
    if not node:
        node = _valid_node(
            get_gto_node(compute_spot_hash(street, position, board_for_hash, [], stack_bb, facing_bb)),
            street, board_for_hash
        )
    if not node and facing_bb == 0:
        node = _valid_node(
            get_gto_node(compute_spot_hash(street, position, board_for_hash, [], stack_bb, 0.0)),
            street, board_for_hash
        )

    if not node:
        return r.get('gto_action'), r.get('gto_label'), False

    strategy = {}
    if node.get('strategy_json'):
        try:
            strategy = json.loads(node['strategy_json'])
        except Exception:
            pass

    if strategy:
        new_action, new_label = _classify(r.get('action_taken', ''), strategy, facing_bb)

        # Guard SPR: jam dominante com SPR > 8 e sem aposta = nó suspeito, descartar
        if new_action == 'jam' and facing_bb == 0 and pot_bb > 0 and stack_bb / pot_bb > 8:
            return r.get('gto_action'), r.get('gto_label'), False
    else:
        # Sem strategy_json: usar gto_action do nó diretamente
        node_action  = _norm(node.get('gto_action') or '', facing_bb)
        played_norm  = _norm(r.get('action_taken', ''), facing_bb)
        gf = float(node.get('gto_freq') or 0)
        if played_norm == node_action or gf >= 0.60:
            new_label = 'gto_correct'
        elif gf >= 0.25:
            new_label = 'gto_mixed'
        else:
            new_label = 'gto_critical'
        new_action = node_action

        if new_action == 'jam' and facing_bb == 0 and pot_bb > 0 and stack_bb / pot_bb > 8:
            return r.get('gto_action'), r.get('gto_label'), False

    return new_action, new_label, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply',   action='store_true', help='Aplica mudanças no banco')
    parser.add_argument('--user-id', type=int, default=None)
    args = parser.parse_args()

    conn = get_conn()
    try:
        user_filter = "AND t.user_id = ?" if args.user_id else ""
        params = [args.user_id] if args.user_id else []

        rows = conn.execute(f"""
            SELECT d.id, d.action_taken, d.gto_action, d.gto_label,
                   d.street, d.position, d.stack_bb, d.facing_bet,
                   d.pot_size, d.hero_cards, d.board, d.best_action
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.street IN ('flop','turn','river')
              {user_filter}
        """, params).fetchall()

        total     = len(rows)
        changed   = []
        unchanged = 0
        no_node   = 0

        print(f"\nAnalisando {total} decisões postflop (com e sem label)...")

        for row in rows:
            r = dict(row)
            new_action, new_label, found = resolve(r)

            if not found:
                no_node += 1
                continue

            old_action = (r.get('gto_action') or '').lower()
            old_label  = r.get('gto_label') or ''

            if new_action != old_action or new_label != old_label:
                changed.append({
                    'id':         r['id'],
                    'street':     r.get('street', ''),
                    'pos':        r.get('position', ''),
                    'played':     r.get('action_taken', ''),
                    'old_action': old_action,
                    'new_action': new_action,
                    'old_label':  old_label,
                    'new_label':  new_label,
                })
            else:
                unchanged += 1

        print(f"\n{'='*70}")
        print(f"Total: {total} | Com nó: {total - no_node} | Sem nó: {no_node}")
        print(f"Mudanças: {len(changed)} | Sem mudança: {unchanged}")
        print(f"{'='*70}")

        if changed:
            print(f"\nMudanças {'(serão aplicadas)' if args.apply else '(dry-run — use --apply)'}:")
            for c in changed:
                flag = '🏷 ' if c['old_label'] != c['new_label'] else '   '
                print(f"  {flag}#{c['id']:6d} {c['street']:6s} {c['pos']:4s} "
                      f"played={c['played']:6s}  "
                      f"action: {c['old_action']:6s}→{c['new_action']:6s}  "
                      f"label: {c['old_label']}→{c['new_label']}")

        if args.apply and changed:
            for c in changed:
                conn.execute(
                    "UPDATE decisions SET gto_action=?, gto_label=? WHERE id=?",
                    (c['new_action'], c['new_label'], c['id'])
                )
            conn.commit()
            print(f"\n✅ {len(changed)} decisões atualizadas no banco.")
        elif not args.apply and changed:
            print(f"\nUse --apply para salvar as {len(changed)} mudanças.")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
