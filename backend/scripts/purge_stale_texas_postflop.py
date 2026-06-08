"""Purga os nós POSTFLOP do solver Texas (source='solver_cli') resolvidos ANTES da
reativação com depth correto. Esses nós foram gerados quando o solve rodava capado a
stack curto (~20bb) e servido a spots de qualquer profundidade via o bucket de stack —
o depth de solve real é indistinguível do que está armazenado, então o seguro é apagar
e deixar repovoar no depth REAL (o lookup_gto reativado resolve ≤60bb com effective
stack correto). Nós preflop e GTO Wizard NÃO são tocados.

Uso:
    python -m scripts.purge_stale_texas_postflop            # dry-run (conta)
    python -m scripts.purge_stale_texas_postflop --apply    # apaga

OBS prod: rodar a mesma purga após o deploy da reativação (os nós antigos do banco de
produção também são do depth errado).
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
    ap.add_argument('--apply', action='store_true')
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
    print(f"Nós solver_cli postflop a purgar: {n}")
    for r in by_street:
        print(f"  {r['s']}: {r['c']}")

    if not args.apply:
        print("\nDRY-RUN — nada apagado. Use --apply para apagar.")
        return

    conn.execute(
        f"DELETE FROM gto_nodes WHERE source='solver_cli' AND lower(street) IN ({ph})",
        _POSTFLOP,
    )
    conn.commit()
    print(f"\nAPLICADO: {n} nós removidos. O Texas repovoa no depth real ao reanalisar/solve.")


if __name__ == '__main__':
    main()
