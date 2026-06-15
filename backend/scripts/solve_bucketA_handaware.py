"""Solve hand-aware TARGETADO dos spots do bucket A (mapa postflop HU sem GTO).

Bucket A = nó agregado existe mas SEM tabela por-mão (gto_tree_strategies), então
`require_hand_aware` rejeita e a decisão fica sem gto_label. Aqui solvamos só esses
spots (com villain conhecido), gerando o tree hand-aware. Depois rode o resync
(scripts/resync_postflop_gto.py --apply) para anexar o gto_label às decisões.

Escopo deliberadamente restrito às decisões-alvo (não é a campanha geral). Spots com
villain 'unknown' NÃO são solváveis (sem range do oponente) e ficam de fora.

Uso:
    python scripts/solve_bucketA_handaware.py --dry-run
    python scripts/solve_bucketA_handaware.py            # solva
"""
import os, sys, argparse
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for line in Path(os.path.join(os.path.dirname(__file__), '..', '.env')).read_text().splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())
os.environ['TEXAS_HERO_IP'] = '1'
os.environ['TEXAS_HERO_IP_FACING'] = '1'

import sqlite3
from leaklab.parser import parse_pokerstars_file_from_text
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_solver import lookup_gto

# decisões-alvo do bucket A com villain conhecido (mapa postflop_hu_gto_gaps.md).
# `action` é OBRIGATÓRIO no match: uma street pode ter +1 decisão do hero (ex.: check
# first-in E shove vs-bet no mesmo turn) — sem isso casa o nó errado.
TARGETS = [
    {'decision_id': 33286, 'tid': 149, 'hand_id': '260605886991', 'street': 'river', 'pos': 'CO', 'vs': 'UTG', 'action': 'bet'},
    {'decision_id': 35868, 'tid': 388, 'hand_id': '100000022',    'street': 'turn',  'pos': 'BB', 'vs': 'HJ', 'action': 'shove'},
]

DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')
_STREET_N = {'flop': 3, 'turn': 4, 'river': 5}


def _norm_act(a):
    s = (a or '').lower().replace('-', '').replace('_', '').replace(' ', '')
    return 'allin' if s in ('shove', 'jam', 'allin') else s


def _find_spot(tid, hand_id, street, pos, vs, action):
    conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT raw_text FROM tournaments WHERE id=?', (tid,)).fetchone()
    conn.close()
    if not row or not row['raw_text']:
        return None
    for h in parse_pokerstars_file_from_text(row['raw_text']):
        if str(h.hand_id) != str(hand_id):
            continue
        for di in build_decision_inputs_for_hand(h):
            if di['street'] != street:
                continue
            sp = di['spot']
            if (sp.get('position') or '').upper() != pos.upper():
                continue
            if (sp.get('villainPosition') or '').upper() != vs.upper():
                continue
            if _norm_act(di.get('player_action')) != _norm_act(action):
                continue
            return di
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    for tgt in TARGETS:
        di = _find_spot(tgt['tid'], tgt['hand_id'], tgt['street'], tgt['pos'], tgt['vs'], tgt['action'])
        if not di:
            print(f"#{tgt['decision_id']}  NÃO ENCONTRADO no parse (hand {tgt['hand_id']})")
            continue
        sp = di['spot']
        board = sp.get('board') or []
        if len([c for c in board if c]) != _STREET_N.get(tgt['street'], -1):
            print(f"#{tgt['decision_id']}  board incompatível com street ({board})")
            continue
        common = dict(
            street=tgt['street'], position=sp.get('position', '').upper(), board=board,
            hero_hand=di.get('hero_cards') or [], hero_stack_bb=float(sp.get('effectiveStackBb') or 0),
            vs_position=sp.get('villainPosition', '').upper(), pot_bb=float(sp.get('potBb') or 0),
            pot_type=sp.get('potType', ''), opener=sp.get('preflopOpener', ''),
            threebettor=sp.get('preflop3bettor', ''))
        facing = float(sp.get('facingToBb') or 0)
        desc = (f"#{tgt['decision_id']} {tgt['street']} {common['position']}v{common['vs_position']} "
                f"stack={common['hero_stack_bb']:.0f}bb facing={facing:.1f} board={board}")
        if args.dry_run:
            print(f"[dry] solvaria  {desc}")
            continue
        try:
            r = lookup_gto(facing_size_bb=facing, bb_chips=1.0, allow_remote_solve=True,
                           block_remote=True, require_hand_aware=True, **common)
            src = r.get('source')
            if r.get('found') and r.get('strategy'):
                top = [(x['action'], round(x['frequency'], 2)) for x in r['strategy'][:3]]
                print(f"OK  SOLVE  {desc} -> {top}  (source={src})")
            else:
                print(f"SEM-COBERTURA  {desc}  (source={src})")
        except Exception as e:
            print(f"ERRO  {desc}  -> {e}")

    print("\nDepois: python scripts/resync_postflop_gto.py --apply  (anexa o gto_label)")


if __name__ == '__main__':
    main()
