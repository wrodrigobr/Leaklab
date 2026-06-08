"""Resolve DIRETO os spots postflop órfãos (job 'done'/'rejected' sem nó GTO) — solve no
GCP + insert_gto_nodes, num processo FRESCO (código atual). Repovoa a cobertura postflop
sem depender do worker vivo (que pode rodar código antigo) e SEM tocar a fila 'pending'
(então não corre risco de o worker vivo pegar/rejeitar os mesmos spots em paralelo).

Resolve a causa raiz dos ~89% de jobs 'done' sem nó: o solver devolve labels de size
(raise_119pct, bet_50pct) no strategy_json; com o fix de normalize_gto_action eles
colapsam pro canônico e o insert passa.

GARANTIAS: só mexe em gto_nodes/gto_solver_queue de spots POSTFLOP solver_cli. NUNCA
toca preflop nem gto_wizard. Solve EXIGE GTO_SOLVER_URL (GCP).

Uso:
    python -m scripts.resolve_postflop_orphans                # dry-run (conta)
    python -m scripts.resolve_postflop_orphans --apply --limit 20
    python -m scripts.resolve_postflop_orphans --apply        # todos
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

_POSTFLOP = {'flop', 'turn', 'river'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    from leaklab.gto_solver import _call_remote_solver, _remote_url, _remote_key
    from database.repositories import insert_gto_nodes, mark_solver_job_done, GTO_EXPLOITABILITY_THRESHOLD

    conn = get_conn()
    node_hashes = {r['spot_hash'] for r in conn.execute('SELECT spot_hash FROM gto_nodes')}
    orphans = []
    for r in conn.execute("SELECT spot_hash, spot_json FROM gto_solver_queue "
                          "WHERE status IN ('done','rejected')"):
        try:
            sj = json.loads(r['spot_json'])
        except Exception:
            continue
        if (sj.get('street', '').lower() in _POSTFLOP) and r['spot_hash'] not in node_hashes:
            orphans.append((r['spot_hash'], sj))

    print(f"Órfãos postflop (sem nó): {len(orphans)}")
    if not args.apply:
        print("DRY-RUN — nada solvado. Use --apply.")
        return
    if not (_remote_url() and _remote_key()):
        print("⛔ GTO_SOLVER_URL/API_KEY ausentes — solver é no GCP. Abortado.")
        return

    todo = orphans[:args.limit] if args.limit else orphans
    solved = rejected = failed = 0
    for spot_hash, spot in todo:
        meta = spot.get('_meta', {})
        try:
            res = _call_remote_solver(spot, timeout=180)
        except Exception:
            res = None
        if not res:
            failed += 1
            continue
        exploit = res.get('exploitability') or res.get('exploitability_pct')
        if exploit is None or float(exploit) > GTO_EXPLOITABILITY_THRESHOLD:
            rejected += 1
            continue
        node = {
            'spot_hash': spot_hash, 'street': spot['street'],
            'position': spot.get('position') or meta.get('position', ''),
            'board': spot.get('board', []),
            'hero_hand': spot.get('hero_hand') or meta.get('hero_hand', []),
            'hero_stack_bb': spot.get('hero_stack_bb') or meta.get('hero_stack_bb', 30.0),
            'facing_size_bb': spot.get('facing_size_bb') or meta.get('facing_size_bb', 0.0),
            'gto_action': res['primary_action'], 'gto_freq': res['primary_freq'],
            'ev_diff': res.get('ev'), 'exploitability_pct': float(exploit),
            'iterations': res.get('iterations'), 'strategy_detail': res.get('strategy_detail'),
            'source': 'solver_cli',
        }
        if insert_gto_nodes([node]):
            mark_solver_job_done(spot_hash, 'done')
            solved += 1
        else:
            rejected += 1
        if (solved + rejected + failed) % 20 == 0:
            print(f"  ... {solved} solved, {rejected} rejected, {failed} failed")

    print(f"\nFIM: {solved} solved (+nó), {rejected} rejected, {failed} failed. "
          f"Preflop/GW intocados.")


if __name__ == '__main__':
    main()
