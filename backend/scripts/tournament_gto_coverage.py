"""
tournament_gto_coverage.py — diagnóstico de cobertura GTO de UM torneio.

Mostra, por street, quantas decisões estão cobertas (gto) vs descobertas, o gto_label das
descobertas, e o estado GLOBAL da fila do solver (pending/done/failed/rejected/unsupported).
Responde "o que falta pra 100%": se a fila não tem pending mas o torneio segue descoberto, os
spots são TERMINAIS (rejected/failed/off-tree/multiway) — não vão cobrir só esperando.

Uso (no container): docker compose exec web python scripts/tournament_gto_coverage.py <tournament_id>
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from database.schema import get_conn          # noqa: E402
from database.repositories import _adapt       # noqa: E402

tid = sys.argv[1] if len(sys.argv) > 1 else None
if not tid:
    print("uso: tournament_gto_coverage.py <tournament_id>  (ex.: 292348828)")
    sys.exit(1)

conn = get_conn()
try:
    rows = list(conn.execute(_adapt(
        "SELECT d.street, d.position, d.facing_bet, d.gto_label, d.gto_action "
        "FROM decisions d JOIN tournaments t ON t.id = d.tournament_id "
        "WHERE t.tournament_id = ?"), (tid,)))
    rows = [dict(r) for r in rows]
    if not rows:
        print(f"torneio {tid} sem decisoes (ou nao encontrado)")
        sys.exit(0)

    def covered(d):
        return bool(d.get('gto_action'))

    print(f"== cobertura GTO do torneio {tid} ==")
    print(f"total decisoes: {len(rows)} | cobertas: {sum(1 for d in rows if covered(d))} "
          f"({100*sum(1 for d in rows if covered(d))//len(rows)}%)")
    print()
    print("por street (cobertas/total):")
    for st in ('preflop', 'flop', 'turn', 'river'):
        sub = [d for d in rows if (d.get('street') or '') == st]
        if sub:
            print(f"  {st:8} {sum(1 for d in sub if covered(d))}/{len(sub)}")
    print()
    print("descobertas (street | posicao | facing | gto_label):")
    for d in rows:
        if not covered(d):
            print(f"  {(d.get('street') or '?'):8} {(d.get('position') or '?'):4} "
                  f"facing={d.get('facing_bet')} label={d.get('gto_label')}")
    print()
    print("== estado GLOBAL da fila do solver (gto_solver_queue) ==")
    for r in conn.execute("SELECT status, COUNT(*) AS n FROM gto_solver_queue GROUP BY status"):
        d = dict(r)
        print(f"  {d['status']:12} {d['n']}")
    print()
    print("Leitura: se NAO ha 'pending'/'running' e o torneio segue descoberto, os spots restantes")
    print("sao TERMINAIS (rejected/failed/off-tree/multiway) — nao cobrem so esperando. Postflop")
    print("multiway e HU-only do solver; preflop descoberto = vs-limp/squeeze/non-standard sem range.")
finally:
    conn.close()
