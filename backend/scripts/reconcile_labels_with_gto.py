"""
reconcile_labels_with_gto.py — Alinha `label` com `gto_label` para eliminar
desacordos entre o dashboard (label) e o Replayer (gto_label).

Regra:
  - gto_correct / gto_mixed     -> label = 'standard'   (GTO confirma: era erro do engine)
  - gto_minor_deviation         -> label >= 'marginal'  (mantém se engine já disse pior)
  - gto_critical                -> label >= 'small_mistake' (mantém se engine já disse pior)

Dry-run por padrão; use --save para persistir.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from database.schema import get_conn

SEVERITY = {'standard': 0, 'marginal': 1, 'small_mistake': 2, 'clear_mistake': 3}


def reconcile(label: str, gto_label: str) -> str:
    if gto_label in ('gto_correct', 'gto_mixed'):
        return 'standard'
    elif gto_label == 'gto_minor_deviation':
        return label if SEVERITY.get(label, 0) >= SEVERITY['marginal'] else 'marginal'
    elif gto_label == 'gto_critical':
        return label if SEVERITY.get(label, 0) >= SEVERITY['small_mistake'] else 'small_mistake'
    return label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    conn = get_conn()
    rows = conn.execute("""
        SELECT id, street, label, gto_label, tournament_id
        FROM decisions
        WHERE gto_label IS NOT NULL AND gto_label != ''
          AND label IS NOT NULL AND label != ''
    """).fetchall()
    rows = [dict(r) for r in rows]

    changes, affected_tids = [], set()
    for r in rows:
        new = reconcile(r['label'], r['gto_label'])
        if new != r['label']:
            changes.append((new, r['id']))
            affected_tids.add(r['tournament_id'])
            print(f"  id={r['id']:>7}  {r['street']:<8}  {r['label']:<15} -> {new:<15}  gto={r['gto_label']}")

    print(f"\nTotal: {len(changes)} decisoes | {len(affected_tids)} torneios afetados")

    if not changes:
        print("Nenhuma atualizacao necessaria.")
        conn.close()
        return

    if not args.save:
        print("\n[DRY RUN] Use --save para persistir.")
        conn.close()
        return

    for new_label, dec_id in changes:
        conn.execute("UPDATE decisions SET label=? WHERE id=?", (new_label, dec_id))

    # Recalculate standard_pct for affected tournaments
    for tid in affected_tids:
        row = conn.execute(
            "SELECT COUNT(CASE WHEN label='standard' THEN 1 END)*100.0/COUNT(*) AS s, "
            "AVG(score) AS a FROM decisions WHERE tournament_id=?", (tid,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE tournaments SET standard_pct=?, avg_score=? WHERE id=?",
                (round(row[0], 2), round(row[1] or 0, 4), tid)
            )

    conn.commit()
    conn.close()
    print(f"\n{len(changes)} decisoes atualizadas. standard_pct recalculado para {len(affected_tids)} torneios.")


if __name__ == "__main__":
    main()
