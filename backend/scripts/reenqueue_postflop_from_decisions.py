"""Re-enfileira spots POSTFLOP descobertos usando o MESMO hash que o lookup da decisão usa
(engine._postflop_gto_lookup / lookup_gto: facingToBb em BB, effectiveStackBb, pot_type efetivo),
em vez do hash do enqueue original (que usava facingSize/level_bb e por isso podia NÃO casar).
Assim o nó solvado cai sob o hash que a decisão procura, por construção.

Motivo: os órfãos MP1 re-chaveados só cobriram parte, porque o enqueue e o lookup calculavam o
'facing' de formas diferentes. Aqui a fonte é a DECISÃO (build_decision_inputs_for_hand), idêntica
ao lookup. Só POSTFLOP; nunca toca preflop/GW. Depois de rodar, drenar a fila e resync.

Uso:
    python -m scripts.reenqueue_postflop_from_decisions --tid 3910307458    # um torneio
    python -m scripts.reenqueue_postflop_from_decisions                     # dry-run, todos
    python -m scripts.reenqueue_postflop_from_decisions --apply             # aplica (enfileira)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.gto_utils import compute_spot_hash, normalize_position
from leaklab.gto_solver import (
    _effective_pot_type, _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE, _solver_params_for_stack,
)
from database.repositories import get_gto_node, enqueue_solver_spot

_POSTFLOP = ('flop', 'turn', 'river')
_APPLY = '--apply' in sys.argv


def _arg(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else None


def _covered(street, pos, board, hero_hand, stack_bb, facing_bb, eff_pot):
    """Mesmas variantes de hash que o lookup: exact → sem hand → sem facing."""
    variants = [
        compute_spot_hash(street, pos, board, hero_hand, stack_bb, facing_bb, eff_pot),
        compute_spot_hash(street, pos, board, [],        stack_bb, facing_bb, eff_pot),
    ]
    if facing_bb == 0.0:
        variants.append(compute_spot_hash(street, pos, board, [], stack_bb, 0.0, eff_pot))
    primary = variants[0]
    return primary, any(get_gto_node(h) for h in variants)


def main():
    tid_filter = _arg('--tid')
    conn = get_conn()
    q = "SELECT id, tournament_id, raw_text FROM tournaments WHERE raw_text IS NOT NULL"
    params = ()
    if tid_filter:
        q += " AND tournament_id = ?"
        params = (tid_filter,)
    rows = conn.execute(q, params).fetchall()

    enq = already = skipped = 0
    for tr in rows:
        t = dict(tr)
        try:
            hands = parse_hand_history(t['raw_text'])
        except Exception:
            continue
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for d in dis:
                street = d.get('street', '')
                if street not in _POSTFLOP:
                    continue
                spot = d.get('spot', {}) or {}
                board = spot.get('board', [])
                pos   = normalize_position(spot.get('position', ''))
                hero  = d.get('hero_cards', [])
                if not board or not pos:
                    continue
                stack_bb  = float(spot.get('effectiveStackBb') or 20.0)
                facing_bb = float(spot.get('facingToBb') or 0.0)          # BB — igual ao lookup
                eff_pot   = _effective_pot_type(spot.get('potType', ''), spot.get('preflopOpener', ''),
                                                spot.get('preflop3bettor', ''), stack_bb)
                primary, cov = _covered(street, pos, board, hero, stack_bb, facing_bb, eff_pot)
                if cov:
                    already += 1
                    continue
                # payload de solve (mesma forma do _enqueue_postflop_spots)
                vs_pos = normalize_position(spot.get('villainPosition', ''))
                level_bb = float(d.get('level_bb') or 1) or 1
                pot_chips = float(spot.get('potSize') or 0)
                pot_bb = round(pot_chips / level_bb, 2) if pot_chips > 0 else (facing_bb * 2 + 2 or 4.0)
                p = _solver_params_for_stack(stack_bb)
                payload = json.dumps({
                    'street': street, 'board': board, 'position': pos, 'hero_hand': hero,
                    'hero_stack_bb': stack_bb, 'facing_size_bb': facing_bb,
                    'oop_range': _DEFAULT_RANGES.get(vs_pos, _DEFAULT_RANGE_WIDE),
                    'ip_range':  _DEFAULT_RANGES.get(pos,    _DEFAULT_RANGE_WIDE),
                    'pot_bb': pot_bb,
                    'effective_stack_bb': p['effective_stack_bb'],
                    'max_iterations': p['max_iterations'],
                    'target_exploitability_pct': p['target_exploitability_pct'],
                })
                if _APPLY:
                    enqueue_solver_spot(primary, payload)
                enq += 1
                if enq <= 20:
                    print(f"  ENQ t{t['tournament_id']} {pos}/{street} facing={facing_bb} stack={stack_bb} -> {primary[:10]}")
    conn.close()
    print(f"\n{'APLICADO' if _APPLY else 'DRY-RUN (use --apply)'}: "
          f"enfileirados={enq}, já cobertos={already}")


if __name__ == '__main__':
    main()
