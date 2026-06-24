"""
enqueue_deep_approx.py — MVP: enfileira variantes APROXIMADAS (stack capado a 30bb) dos spots
postflop FUNDOS (stack > 35bb) que o solver não cobriu no stack real.

Deep OOP de alta SPR é a cobertura mais rala (árvore grande → solver rejeita/não fecha). Em HU,
o solve a ~30bb é tratável e a AÇÃO transfere bem (sizing/comprometimento podem diferir). O nó
capado é keyed pelo hash a 30bb → o lookup do replay (get_decision_gto, fallback 'e') o acha e
marca "≈ Aproximação (solver a 30bb)". O cron resolve offline.

DRY-RUN por padrão. --apply pra enfileirar.
Uso (no container): docker compose exec -T web python scripts/enqueue_deep_approx.py <tournament_id> [--apply]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn                                          # noqa: E402
from database.repositories import _adapt, get_gto_node, enqueue_solver_spot    # noqa: E402
from leaklab.gto_utils import compute_spot_hash                                # noqa: E402
from leaklab.gto_solver import (_DEFAULT_RANGES, _DEFAULT_RANGE_WIDE,          # noqa: E402
                                _solver_params_for_stack, _priority)

APPROX_STACK = 30.0
MIN_BB = 35.0
SC = {'flop': 3, 'turn': 4, 'river': 5}

tid = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else None
apply = '--apply' in sys.argv
check = '--check' in sys.argv   # diagnóstico: o nó a 30bb existe? qual a ação top? (guard de jam?)
hand = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--hand=')), None)  # filtra 1 mão
if not tid:
    print("uso: enqueue_deep_approx.py <tournament_id> [--apply | --check] [--hand=<hand_id>]")
    sys.exit(1)

conn = get_conn()
try:
    _sql = ("SELECT d.street, d.position, d.vs_position, d.board, d.hero_cards, d.stack_bb, "
            "       d.facing_bet, d.pot_size, d.gto_label "
            "FROM decisions d JOIN tournaments t ON t.id = d.tournament_id "
            "WHERE t.tournament_id = ? AND d.street IN ('flop','turn','river')")
    _params = [tid]
    if hand:
        _sql += " AND d.hand_id = ?"
        _params.append(hand)
    rows = [dict(r) for r in conn.execute(_adapt(_sql), tuple(_params))]

    deep_uncovered = enqueued = already = skipped = 0
    for r in rows:
        if r.get('gto_label'):           # já coberto no stack real
            continue
        stack = float(r.get('stack_bb') or 0)
        if stack <= MIN_BB:              # não é deep → o solve real já cobre essa profundidade
            skipped += 1
            continue
        deep_uncovered += 1
        street = r['street']
        try:
            board = json.loads(r['board']) if isinstance(r['board'], str) else (r['board'] or [])
        except Exception:
            board = []
        board = board[:SC.get(street, len(board))]
        hr = (r.get('hero_cards') or '').strip()
        hero = hr.split() if ' ' in hr else ([hr[i:i + 2] for i in range(0, len(hr), 2)] if hr else [])
        pos = (r.get('position') or '').upper()
        vs_pos = (r.get('vs_position') or '').upper()
        facing = round(float(r.get('facing_bet') or 0), 2)
        pot_bb = round(float(r.get('pot_size') or 0), 2) or (facing * 2 + 2 or 4.0)

        # hash a 30bb (= o que o fallback do lookup procura); facing/pot mantidos → SPR cai (tratável)
        h = compute_spot_hash(street, pos, board, hero, APPROX_STACK, facing)
        existing = get_gto_node(h)
        if check:
            # diagnóstico: o nó a 30bb existe? qual a ação top? (se 'shove'/'jam', o guard de SPR
            # descarta no lookup → não vira aproximação; bet/check/fold transfere)
            if existing:
                ta = existing.get('gto_action')
                try:
                    sj = existing.get('strategy_json')
                    if sj:
                        sd = json.loads(sj) if isinstance(sj, str) else sj
                        if sd:
                            ta = max(sd, key=lambda k: float((sd[k] or {}).get('frequency', 0)))
                except Exception:
                    pass
                print(f"  OK no30bb  {street:5} {pos:4} facing={facing:<5} top={ta}  hash={h[:12]}")
                already += 1
            else:
                print(f"  FALTA     {street:5} {pos:4} facing={facing:<5} (nao resolvido a 30bb)  hash={h[:12]}")
                enqueued += 1
            continue
        if existing:
            already += 1
            continue
        params = _solver_params_for_stack(APPROX_STACK)
        payload = json.dumps({
            'street': street, 'board': board, 'position': pos, 'hero_hand': hero,
            'hero_stack_bb': APPROX_STACK, 'facing_size_bb': facing,
            'oop_range': _DEFAULT_RANGES.get(vs_pos, _DEFAULT_RANGE_WIDE),
            'ip_range':  _DEFAULT_RANGES.get(pos,    _DEFAULT_RANGE_WIDE),
            'pot_bb': pot_bb,
            'effective_stack_bb':        params['effective_stack_bb'],
            'max_iterations':            params['max_iterations'],
            'target_exploitability_pct': params['target_exploitability_pct'],
            '_meta': {'position': pos, 'vs_position': vs_pos, 'hero_hand': hero,
                      'approx_of_stack': stack, 'deep_approx': True},
        })
        if apply:
            enqueue_solver_spot(h, payload, priority=_priority(street))
        enqueued += 1

    mode = 'ENFILEIRADOS' if apply else 'SERIAM enfileirados (dry-run)'
    print(f"torneio {tid}: deep-uncovered={deep_uncovered} | {mode}={enqueued} | "
          f"ja no solver={already} | nao-deep pulados={skipped}")
    if not apply and enqueued:
        print("Rode com --apply pra enfileirar. Depois o cron resolve e o replay mostra")
        print("'≈ Aproximacao (solver a 30bb)' nesses spots deep.")
finally:
    conn.close()
