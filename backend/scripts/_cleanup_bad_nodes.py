"""
Limpa os nos com position=range_string ou stack_bucket='solver'.
1. Identifica as decisions que referenciam esses nos (via spot_hash)
2. Nullifica gto_label/gto_action dessas decisions
3. Deleta os nos ruins
4. Exibe resumo
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
from database.schema import get_conn
from leaklab.gto_utils import compute_spot_hash
from collections import Counter

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true', help='Executa as alteracoes (default: dry-run)')
args = parser.parse_args()

conn = get_conn()

bad_nodes = conn.execute("""
    SELECT id, spot_hash, street, position, board, stack_bucket, gto_action
    FROM gto_nodes
    WHERE source = 'solver_cli'
      AND (stack_bucket = 'solver' OR position LIKE '%+%' OR position LIKE '%,%')
""").fetchall()
bad_nodes = [dict(r) for r in bad_nodes]
bad_hashes = {n['spot_hash'] for n in bad_nodes}

print(f"Nos ruins encontrados: {len(bad_nodes)}")
print(f"  streets: {dict(Counter(n['street'] for n in bad_nodes))}")
print(f"  buckets: {dict(Counter(n['stack_bucket'] for n in bad_nodes))}")

# Encontra decisions afetadas
decisions = conn.execute("""
    SELECT d.id, d.street, d.position, d.board, d.hero_cards, d.stack_bb,
           d.facing_bet, d.gto_label, d.gto_action
    FROM decisions d
    WHERE d.street IN ('flop','turn','river')
      AND d.gto_label IS NOT NULL
""").fetchall()

affected_ids = []
_sc = {'flop': 3, 'turn': 4, 'river': 5}

for dec in decisions:
    r = dict(dec)
    board_raw = r.get('board') or '[]'
    board = json.loads(board_raw) if isinstance(board_raw, str) else board_raw
    street = r.get('street', '')
    bfh = board[:_sc.get(street, len(board))]
    stack = float(r.get('stack_bb') or 20)
    facing = float(r.get('facing_bet') or 0)
    hc = r.get('hero_cards') or ''
    hero_h = hc.split() if ' ' in hc else [hc[i:i+2] for i in range(0, len(hc), 2) if hc[i:i+2]] if hc else []

    hit = False
    for h_hand in ([hero_h, []] if hero_h else [[]]):
        for f_bet in ([facing, 0.0] if facing > 0 else [facing]):
            h = compute_spot_hash(street, r['position'], bfh, h_hand, stack, f_bet)
            if h in bad_hashes:
                hit = True
                break
        if hit:
            break
    if hit:
        affected_ids.append(r['id'])
        print(f"  Decision #{r['id']:4d}  {r['street']:5s}  pos={r['position']:6s}  gto_label={r['gto_label']}  gto_action={r['gto_action']}")

print(f"\nDecisions afetadas: {len(affected_ids)}")

if not args.apply:
    print("\n[DRY-RUN] Nenhuma alteracao feita. Use --apply para executar.")
    conn.close()
    sys.exit(0)

# Nullifica gto_label das decisions afetadas
if affected_ids:
    placeholders = ','.join('?' * len(affected_ids))
    conn.execute(
        f"UPDATE decisions SET gto_label = NULL, gto_action = NULL WHERE id IN ({placeholders})",
        affected_ids
    )
    print(f"Nullificadas {len(affected_ids)} decisions.")

# Deleta os nos ruins
bad_ids = [n['id'] for n in bad_nodes]
placeholders = ','.join('?' * len(bad_ids))
cur = conn.execute(f"DELETE FROM gto_nodes WHERE id IN ({placeholders})", bad_ids)
deleted = cur.rowcount
conn.commit()

print(f"Deletados {deleted} nos ruins.")
print("\nPROXIMOS PASSOS:")
print("  1. python scripts/validate_nodes_vs_gw.py --apply --new-decisions")
print("     (tenta cobrir as decisions nullificadas via GW)")
print("  2. python scripts/validate_nodes_vs_gw.py --apply --high-exploit-only")
print("  3. python scripts/resync_gto_actions.py --apply")

conn.close()
