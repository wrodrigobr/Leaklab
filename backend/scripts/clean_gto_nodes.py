"""
clean_gto_nodes.py — Audita e remove nós GTO incorretos.

Detecta entradas com dados implausíveis:
  1. Board no nó != board de qualquer decisão com aquele spot_hash
  2. strategy_json recomenda jam >80% em street postflop com stack_bucket >=20-40bb
     (overbet de >8x o pote como ação dominante não existe no GTO)

Uso:
    python scripts/clean_gto_nodes.py          # modo auditoria (apenas lista)
    python scripts/clean_gto_nodes.py --delete # apaga os nós suspeitos
    python scripts/clean_gto_nodes.py --delete --yes  # sem confirmação
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from database.schema import get_conn

POSTFLOP_STREETS = {'flop', 'turn', 'river'}
# Stack buckets onde jam como first-aggressor é implausível no postflop
DEEP_BUCKETS = {'20-35bb', '20-40bb', '35-60bb', '40bb+', '60-100bb', '100bb+'}

_JAM_KEYS = {'shove', 'jam', 'allin', 'all-in', 'all_in'}


def _top_action(strategy_json_str):
    """Retorna (ação, frequência) da ação mais frequente no strategy_json."""
    if not strategy_json_str:
        return None, 0.0
    try:
        strat = json.loads(strategy_json_str)
        top_key = max(strat, key=lambda k: float(strat[k].get('frequency', 0)))
        return top_key.lower(), float(strat[top_key].get('frequency', 0))
    except Exception:
        return None, 0.0


def audit(conn, verbose=True):
    """Retorna lista de (node_id, spot_hash, motivo) de nós suspeitos."""
    suspicious = []

    nodes = conn.execute("""
        SELECT id, spot_hash, street, position, board, hero_hand,
               stack_bucket, gto_action, strategy_json, source
        FROM gto_nodes
    """).fetchall()

    # Índice de boards por spot_hash da tabela decisions (ground truth)
    decision_boards = {}
    for row in conn.execute("""
        SELECT d.id, d.street, d.position, d.board, d.stack_bb, d.facing_bet,
               d.hero_cards
        FROM decisions d
        WHERE d.gto_label IN ('gto_minor_deviation', 'gto_critical')
    """).fetchall():
        r = dict(row)
        # Reconstruir o spot_hash como o worker fez
        try:
            from leaklab.gto_utils import compute_spot_hash
            board_raw = r.get('board') or '[]'
            board = json.loads(board_raw) if isinstance(board_raw, str) else (board_raw or [])
            _street_cards = {'flop': 3, 'turn': 4, 'river': 5}
            board_for_hash = board[:_street_cards.get(r['street'], len(board))]
            stack_bb  = float(r.get('stack_bb') or 30)
            facing_bb = float(r.get('facing_bet') or 0)
            hand_raw  = r.get('hero_cards') or ''
            if isinstance(hand_raw, str) and hand_raw.strip():
                _raw = hand_raw.strip()
                hero_hand = _raw.split() if ' ' in _raw else [_raw[i:i+2] for i in range(0, len(_raw), 2)]
            else:
                hero_hand = []

            for h in ([hero_hand, []] if hero_hand else [[]]):
                for f in ([facing_bb, 0.0] if facing_bb > 0 else [0.0]):
                    h_key = compute_spot_hash(r['street'], r['position'], board_for_hash, h, stack_bb, f)
                    if h_key not in decision_boards:
                        decision_boards[h_key] = []
                    decision_boards[h_key].append(sorted(board_for_hash))
        except Exception:
            pass

    for node in nodes:
        n = dict(node)
        node_id   = n['id']
        spot_hash = n['spot_hash']
        street    = (n.get('street') or '').lower()
        reasons   = []

        # ── Check 1: board mismatch vs decisions ────────────────────────────
        if spot_hash in decision_boards:
            try:
                node_board = sorted(json.loads(n.get('board') or '[]'))
                dec_boards = decision_boards[spot_hash]
                if dec_boards and node_board and node_board not in dec_boards:
                    reasons.append(
                        f"board mismatch: node={node_board} vs decisions={dec_boards[0]}"
                    )
            except Exception:
                pass

        # ── Check 2: jam dominante em postflop com stack alto ────────────────
        if street in POSTFLOP_STREETS:
            top_act, top_freq = _top_action(n.get('strategy_json'))
            if top_act in _JAM_KEYS and top_freq > 0.80:
                bucket = n.get('stack_bucket') or ''
                if bucket in DEEP_BUCKETS:
                    reasons.append(
                        f"jam {top_freq:.0%} dominante em {street} com stack_bucket={bucket} "
                        f"(overbet implausível como ação principal)"
                    )

        if reasons:
            suspicious.append({
                'id':        node_id,
                'spot_hash': spot_hash,
                'street':    street,
                'position':  n.get('position'),
                'board':     n.get('board'),
                'stack_bucket': n.get('stack_bucket'),
                'gto_action': n.get('gto_action'),
                'source':    n.get('source'),
                'reasons':   reasons,
            })

    if verbose:
        print(f"\n{'='*60}")
        print(f"TOTAL de nós no gto_nodes: {len(nodes)}")
        print(f"Nós suspeitos encontrados: {len(suspicious)}")
        print(f"{'='*60}")
        for s in suspicious:
            print(f"\n  [#{s['id']}] {s['spot_hash']}")
            print(f"  Street: {s['street']} | Position: {s['position']} | Board: {s['board']}")
            print(f"  Stack bucket: {s['stack_bucket']} | GTO action: {s['gto_action']} | Source: {s['source']}")
            for r in s['reasons']:
                print(f"  ⚠  {r}")

    return suspicious


def delete_suspicious(conn, suspicious, dry_run=False):
    ids = [s['id'] for s in suspicious]
    if not ids:
        print("Nenhum nó suspeito para remover.")
        return 0
    if dry_run:
        print(f"\n[DRY RUN] Removeria {len(ids)} nós: {ids}")
        return 0
    conn.executemany("DELETE FROM gto_nodes WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    print(f"\n✅ {len(ids)} nós removidos do gto_nodes.")
    return len(ids)


def main():
    parser = argparse.ArgumentParser(description="Auditoria de gto_nodes")
    parser.add_argument('--delete', action='store_true', help='Remove nós suspeitos')
    parser.add_argument('--yes',    action='store_true', help='Sem confirmação interativa')
    args = parser.parse_args()

    conn = get_conn()
    try:
        suspicious = audit(conn, verbose=True)

        if not args.delete:
            print("\nUse --delete para remover os nós suspeitos.")
            return

        if not suspicious:
            print("\nNenhum nó suspeito. Banco limpo.")
            return

        if not args.yes:
            resp = input(f"\nRemover {len(suspicious)} nós? [s/N] ").strip().lower()
            if resp not in ('s', 'sim', 'y', 'yes'):
                print("Cancelado.")
                return

        delete_suspicious(conn, suspicious, dry_run=False)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
