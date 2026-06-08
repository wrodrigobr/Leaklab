"""Re-enfileira spots POSTFLOP órfãos — jobs do solver marcados 'done' cujo nó GTO
foi apagado por uma purga anterior (purge_stale_texas_postflop SEM re-enqueue). Como o
worker só processa 'pending', esses spots ficaram com no-coverage permanente. Aqui
resetamos status 'done' → 'pending' SÓ para os órfãos postflop, pra o solver regenerar.

GARANTIAS (a mina de ouro preflop do GW é INTOCÁVEL):
  - Mexe SÓ em gto_solver_queue.status (jobs POSTFLOP). Nunca toca gto_nodes nem
    gto_preflop_ranges. Nunca reseta job preflop.
  - Órfão = job 'done' + street ∈ {flop,turn,river} + spot_hash AUSENTE de gto_nodes.

SOLVER NO GCP: o re-solve roda no servidor GCP (worker chama GTO_SOLVER_URL). Por isso
o --apply EXIGE GTO_SOLVER_URL setado — senão o worker LOCAL pegaria o binário local
(que não queremos). Use --allow-local só se souber o que está fazendo.

Uso:
    python -m scripts.requeue_orphaned_postflop              # dry-run (conta)
    python -m scripts.requeue_orphaned_postflop --apply      # exige GTO_SOLVER_URL
    python -m scripts.requeue_orphaned_postflop --apply --allow-local
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
from database.schema import get_conn

_POSTFLOP = {'flop', 'turn', 'river'}


def find_orphans(conn):
    node_hashes = {r['spot_hash'] for r in conn.execute('SELECT spot_hash FROM gto_nodes')}
    orphans = []
    for r in conn.execute("SELECT id, spot_hash, spot_json FROM gto_solver_queue WHERE status='done'"):
        try:
            street = (json.loads(r['spot_json']).get('street') or '').lower()
        except Exception:
            street = ''
        if street in _POSTFLOP and r['spot_hash'] not in node_hashes:
            orphans.append(r['id'])
    return orphans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--allow-local', action='store_true',
                    help='permite re-enqueue mesmo sem GTO_SOLVER_URL (solve local). NÃO recomendado.')
    args = ap.parse_args()

    conn = get_conn()
    orphans = find_orphans(conn)
    print(f"Spots POSTFLOP órfãos (job 'done' sem nó GTO): {len(orphans)}")

    if not args.apply:
        print("\nDRY-RUN — nada alterado. Use --apply para resetar → pending.")
        return

    if not os.environ.get('GTO_SOLVER_URL') and not args.allow_local:
        print("\n⛔ GTO_SOLVER_URL não setado. O solver deve rodar no GCP, não local.")
        print("  Configure GTO_SOLVER_URL apontando pro servidor GCP e rode de novo,")
        print("  ou use --allow-local se realmente quiser solve local (não recomendado).")
        return

    if not orphans:
        print("Nada a re-enfileirar.")
        return

    ph = ','.join('?' for _ in orphans)
    cur = conn.execute(
        f"UPDATE gto_solver_queue SET status='pending' WHERE id IN ({ph}) AND status='done'",
        orphans,
    )
    conn.commit()
    tgt = os.environ.get('GTO_SOLVER_URL', 'LOCAL (--allow-local)')
    print(f"\nAPLICADO: {cur.rowcount} jobs postflop re-enfileirados (→ pending). Solver: {tgt}")
    print("Preflop/GW intocados. O worker repovoa os nós ao processar a fila.")


if __name__ == '__main__':
    main()
