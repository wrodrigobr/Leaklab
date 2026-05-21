"""Audita os nós com position=range e verifica se são encontráveis por alguma decision."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
from database.schema import get_conn
from leaklab.gto_utils import compute_spot_hash

conn = get_conn()

# 1. Nós com position inválida (range string ou stack_bucket='solver')
bad_nodes = conn.execute("""
    SELECT id, spot_hash, street, position, board, stack_bucket, gto_action, gto_freq
    FROM gto_nodes
    WHERE source = 'solver_cli'
      AND (stack_bucket = 'solver' OR position LIKE '%+%' OR position LIKE '%,%')
""").fetchall()
bad_nodes = [dict(r) for r in bad_nodes]

bad_hashes = {n['spot_hash'] for n in bad_nodes}
print(f"Nós com position/bucket inválidos: {len(bad_nodes)}")
print(f"  streets: {dict()}")
from collections import Counter
print(f"  streets: {dict(Counter(n['street'] for n in bad_nodes))}")
print(f"  buckets: {dict(Counter(n['stack_bucket'] for n in bad_nodes))}")

# 2. Conseguimos encontrar esses hashes partindo das decisions reais?
# (i.e., alguma decision usa exatamente esse hash?)
found_via_decision = 0
orphan_hashes = []

decisions = conn.execute("""
    SELECT d.id, d.street, d.position, d.board, d.hero_cards, d.stack_bb, d.facing_bet,
           d.gto_label, d.gto_action
    FROM decisions d
    WHERE d.street IN ('flop','turn','river')
      AND d.gto_label IS NOT NULL
""").fetchall()

for dec in decisions:
    r = dict(dec)
    board_raw = r.get('board') or '[]'
    board = json.loads(board_raw) if isinstance(board_raw, str) else board_raw
    _sc = {'flop':3,'turn':4,'river':5}
    street = r.get('street','')
    bfh = board[:_sc.get(street, len(board))]
    stack = float(r.get('stack_bb') or 20)
    facing = float(r.get('facing_bet') or 0)
    hc = r.get('hero_cards') or ''
    hero_h = hc.split() if ' ' in hc else [hc[i:i+2] for i in range(0, len(hc), 2) if hc[i:i+2]] if hc else []

    for h_hand in ([hero_h, []] if hero_h else [[]]):
        for f_bet in ([facing, 0.0] if facing > 0 else [facing]):
            h = compute_spot_hash(street, r['position'], bfh, h_hand, stack, f_bet)
            if h in bad_hashes:
                found_via_decision += 1
                break

print(f"\nDecisions que chegam a um no ruim via hash: {found_via_decision}")
print(f"\nConclusao: os {len(bad_nodes)} nos com position invalida")
if found_via_decision == 0:
    print(f"  -> NAO sao encontraveis por nenhuma decision real (hash foi gerado com position=range)")
    print(f"  -> Sao resquicios de runs antigos do solver")
    print(f"  -> Podem ser deletados com seguranca")
else:
    print(f"  -> ATENCAO: {found_via_decision} decisions chegam a um no ruim")
    print(f"  -> Essas decisions terao gto_label orfao apos delete")

conn.close()
