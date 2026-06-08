"""Limpeza do bug de pot_bb (fichas→BB) nos nós postflop do Texas (solver_cli).

Os nós solver_cli postflop foram gerados com pot_bb em FICHAS → SPR colapsado → solver
degenerado (all-in forçado, exploitability 0.0% fake). Este script:
  1. PURGA todos os nós solver_cli postflop (degenerados).
  2. RE-ANALISA cada torneio do raw_text (parse → build_decision_inputs_for_hand) e,
     para cada spot postflop, monta o spot do solver com o pot CORRETO (usa spot['potBb']
     /['facingToBb'], já em BB), solve no GCP (_call_remote_solver) e insere o nó.

GARANTIAS: só toca gto_nodes solver_cli postflop. NUNCA toca preflop nem gto_wizard
(gto_preflop_ranges é tabela separada). Solve EXIGE GTO_SOLVER_URL (GCP).

Uso:
    python -m scripts.cleanup_postflop_pot_bug                       # dry-run
    python -m scripts.cleanup_postflop_pot_bug --apply --tournament 375
    python -m scripts.cleanup_postflop_pot_bug --apply               # todos
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except Exception:
    pass
from database.schema import get_conn

_POSTFLOP = ('flop', 'turn', 'river')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--tournament', type=int, default=0, help='só este tournament_id (0 = todos)')
    args = ap.parse_args()

    from leaklab.parser import parse_hand_history
    from leaklab.pipeline import build_decision_inputs_for_hand
    from leaklab.gto_solver import (_call_remote_solver, _remote_url, _remote_key,
                                    _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE, _solver_params_for_stack)
    from leaklab.gto_utils import compute_spot_hash
    from database.repositories import insert_gto_nodes, GTO_EXPLOITABILITY_THRESHOLD

    conn = get_conn()
    ph = ','.join('?' for _ in _POSTFLOP)
    n_deg = conn.execute(
        f"SELECT COUNT(*) c FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ({ph})",
        _POSTFLOP).fetchone()['c']
    print(f"Nós solver_cli postflop degenerados a purgar: {n_deg}")

    if not args.apply:
        print("DRY-RUN — nada apagado/solvado. Use --apply.")
        return
    if not (_remote_url() and _remote_key()):
        print("⛔ GTO_SOLVER_URL/API_KEY ausentes — solver é no GCP. Abortado.")
        return

    # 1) PURGA (só solver_cli postflop)
    conn.execute(f"DELETE FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ({ph})", _POSTFLOP)
    conn.commit()
    print(f"Purgados: {n_deg} nós.")

    # 2) RE-ANALISA + RE-SOLVA
    q = "SELECT id FROM tournaments WHERE raw_text IS NOT NULL"
    params = ()
    if args.tournament:
        q += " AND id=?"; params = (args.tournament,)
    tids = [r['id'] for r in conn.execute(q, params)]
    print(f"Torneios a re-analisar: {len(tids)}")

    solved = rejected = failed = seen = 0
    done_hashes = set()
    for tid in tids:
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()['raw_text']
        try:
            hands = parse_hand_history(raw)
        except Exception:
            continue
        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                st = (di.get('street') or '').lower()
                if st not in _POSTFLOP:
                    continue
                sp = di.get('spot', {})
                pos = (sp.get('position') or '').upper()
                vs_pos = (sp.get('villainPosition') or '').upper()
                board = sp.get('board', [])
                hero = di.get('hero_cards', [])
                stack = float(sp.get('effectiveStackBb') or 20.0)
                pot_bb = float(sp.get('potBb') or 0.0)         # JÁ em BB (fix)
                facing = float(sp.get('facingToBb') or 0.0)    # JÁ em BB (fix)
                if not pos or not board or not hero or stack <= 0:
                    continue
                shash = compute_spot_hash(st, pos, board, hero, stack, facing)
                if shash in done_hashes:
                    continue
                seen += 1
                _params = _solver_params_for_stack(stack)
                payload = {
                    'street': st, 'board': board, 'position': pos, 'hero_hand': hero,
                    'hero_stack_bb': stack, 'facing_size_bb': facing,
                    'oop_range': _DEFAULT_RANGES.get(vs_pos, _DEFAULT_RANGE_WIDE),
                    'ip_range': _DEFAULT_RANGES.get(pos, _DEFAULT_RANGE_WIDE),
                    'pot_bb': pot_bb,
                    'effective_stack_bb': _params['effective_stack_bb'],
                    'max_iterations': _params['max_iterations'],
                    'target_exploitability_pct': _params['target_exploitability_pct'],
                    '_meta': {'position': pos, 'vs_position': vs_pos, 'hero_hand': hero,
                              'hero_stack_bb': stack, 'facing_size_bb': facing,
                              'street': st, 'board': board},
                }
                try:
                    res = _call_remote_solver(payload, timeout=180)
                except Exception:
                    res = None
                if not res:
                    failed += 1; continue
                exploit = res.get('exploitability') or res.get('exploitability_pct')
                if exploit is None or float(exploit) > GTO_EXPLOITABILITY_THRESHOLD:
                    rejected += 1; continue
                node = {
                    'spot_hash': shash, 'street': st, 'position': pos, 'board': board,
                    'hero_hand': hero, 'hero_stack_bb': stack, 'facing_size_bb': facing,
                    'gto_action': res['primary_action'], 'gto_freq': res['primary_freq'],
                    'ev_diff': res.get('ev'), 'exploitability_pct': float(exploit),
                    'iterations': res.get('iterations'), 'strategy_detail': res.get('strategy_detail'),
                    'source': 'solver_cli',
                }
                if insert_gto_nodes([node]):
                    done_hashes.add(shash); solved += 1
                else:
                    rejected += 1
                if seen % 25 == 0:
                    print(f"  ... {seen} spots | {solved} solved, {rejected} rejected, {failed} failed")

    print(f"\nFIM: {seen} spots postflop | {solved} solved (+nó), {rejected} rejected, {failed} failed.")
    print("Preflop GW / gto_wizard intocados.")


if __name__ == '__main__':
    main()
