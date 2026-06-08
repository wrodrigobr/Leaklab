"""Purga (LEGADO/DESATIVADO) os nós POSTFLOP do solver Texas (source='solver_cli').

CONTEXTO: este script foi uma migração ÚNICA — os nós antigos foram gerados quando o
solve rodava capado a stack curto (~20bb) e servido a qualquer profundidade via bucket
de stack, então o depth real era indistinguível e o seguro foi apagar e repovoar no
depth correto (lookup_gto reativado resolve ≤60bb com effective stack real).

POLÍTICA ATUAL (2026-06-08): a captura postflop do Texas no depth correto é PRESERVADA —
é um keeper, como a mina de ouro preflop do GTO Wizard. **Não deletamos mais resultados
postflop do Texas.** Por isso a deleção fica DESATIVADA por padrão; só roda com --force
(escotilha pra uma eventual nova migração de depth). Nós preflop e gto_wizard NUNCA são
tocados (filtro source='solver_cli' + street postflop).

Uso:
    python -m scripts.purge_stale_texas_postflop            # dry-run (conta)
    python -m scripts.purge_stale_texas_postflop --apply    # DESATIVADO (avisa e sai)
    python -m scripts.purge_stale_texas_postflop --force     # legado: apaga + re-enfileira
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
from database.schema import get_conn

_POSTFLOP = ('flop', 'turn', 'river')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='(desativado) ver --force')
    ap.add_argument('--force', action='store_true',
                    help='LEGADO: realmente apaga os nós postflop do Texas (+ re-enfileira). '
                         'Use só numa nova migração de depth — postflop Texas é keeper.')
    args = ap.parse_args()

    conn = get_conn()
    ph = ','.join('?' for _ in _POSTFLOP)
    n = conn.execute(
        f"SELECT COUNT(*) c FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ({ph})",
        _POSTFLOP,
    ).fetchone()['c']
    by_street = conn.execute(
        f"SELECT lower(street) s, COUNT(*) c FROM gto_nodes WHERE source='solver_cli' "
        f"AND lower(street) IN ({ph}) GROUP BY lower(street)",
        _POSTFLOP,
    ).fetchall()
    print(f"Nós solver_cli postflop existentes: {n}")
    for r in by_street:
        print(f"  {r['s']}: {r['c']}")

    # Deleção DESATIVADA por política: postflop Texas é keeper. Só com --force.
    if not args.force:
        if args.apply:
            print("\n⚠ DELEÇÃO DESATIVADA: a captura postflop do Texas é PRESERVADA "
                  "(keeper, como o preflop do GW). Não deletamos mais esses nós.")
            print("  Se REALMENTE precisar re-purgar (ex.: nova migração de depth), use --force.")
        else:
            print("\nDRY-RUN — nada apagado. (Deleção desativada por política; --force p/ legado.)")
        return

    # ── Caminho LEGADO (--force): apaga + RE-ENFILEIRA ───────────────────────────
    # spot_hashes dos nós a apagar — pra re-enfileirar o solve. SEM isso, o purge
    # deixa os jobs 'done' e o worker (só pega 'pending') NUNCA re-solva → órfãos.
    # NUNCA toca preflop nem gto_wizard (filtro source='solver_cli' + street postflop).
    hashes = [
        r['spot_hash'] for r in conn.execute(
            f"SELECT spot_hash FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ({ph})",
            _POSTFLOP,
        ).fetchall()
    ]
    conn.execute(
        f"DELETE FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ({ph})",
        _POSTFLOP,
    )
    requeued = 0
    if hashes:
        ph2 = ','.join('?' for _ in hashes)
        cur = conn.execute(
            f"UPDATE gto_solver_queue SET status='pending' "
            f"WHERE spot_hash IN ({ph2}) AND status IN ('done', 'rejected', 'failed')",
            hashes,
        )
        requeued = cur.rowcount
    conn.commit()
    print(f"\n[--force] APLICADO: {n} nós removidos, {requeued} jobs re-enfileirados (→ pending).")
    print("O solver (GCP, via GTO_SOLVER_URL) repovoa no depth real ao processar a fila.")


if __name__ == '__main__':
    main()
