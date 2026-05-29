"""
Backfill de decisions.icm_tax_pct nos torneios já importados.

O `icm_tax_pct` (chip% − equity ICM%) é contexto a **nível de mão** — igual para
todas as decisões da mesma mão, pois `build_mtt_context` roda uma vez por mão. Este
script recomputa esse contexto a partir de `tournaments.raw_text` (mesmo caminho que
o /analyze persiste: `build_mtt_context` → `context_to_dict`) e atualiza todas as
decisões daquela mão. Só mãos de mesa final (2..9 jogadores) produzem valor; as
demais ficam NULL (e são ignoradas pelo detector de leak ICM).

Idempotente: só toca linhas com `icm_tax_pct IS NULL`.

Uso:
    cd backend
    python scripts/backfill_icm_tax.py [--dry-run] [--limit N]
"""
import sys
import argparse
sys.path.insert(0, ".")

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.mtt_context import build_mtt_context, context_to_dict


def backfill(dry_run: bool = False, limit: int = 0):
    conn = get_conn()
    try:
        # Garante a coluna (caso as migrations ainda não tenham rodado nesta conexão).
        try:
            conn.execute("ALTER TABLE decisions ADD COLUMN icm_tax_pct REAL")
            conn.commit()
        except Exception:
            pass

        q = """
            SELECT DISTINCT d.tournament_id AS tid, t.raw_text AS raw_text
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            WHERE d.icm_tax_pct IS NULL AND t.raw_text IS NOT NULL
        """
        if limit:
            q += f" LIMIT {int(limit)}"
        rows = conn.execute(q).fetchall()
        print(f"Torneios a processar: {len(rows)}")

        total_hands = ft_hands = updated_rows = failed = 0

        for row in rows:
            tid     = row["tid"]
            raw_txt = row["raw_text"]
            try:
                hands = parse_hand_history(raw_txt)
            except Exception as e:
                print(f"  [WARN] torneio {tid}: erro de parse — {e}")
                failed += 1
                continue

            for h in hands:
                total_hands += 1
                try:
                    ctx = context_to_dict(build_mtt_context(h))
                except Exception:
                    continue
                tax = ctx.get("icmTaxPct")
                if tax is None:
                    continue  # mão fora da mesa final → permanece NULL
                ft_hands += 1
                if not dry_run:
                    cur = conn.execute(
                        "UPDATE decisions SET icm_tax_pct = ? "
                        "WHERE tournament_id = ? AND hand_id = ? AND icm_tax_pct IS NULL",
                        (tax, tid, str(h.hand_id)),
                    )
                    rc = getattr(cur, "rowcount", 0) or 0
                    updated_rows += max(rc, 0)

        if not dry_run:
            conn.commit()

        # Total populado (verificação cross-backend, independente de rowcount).
        populated = conn.execute(
            "SELECT COUNT(*) AS n FROM decisions WHERE icm_tax_pct IS NOT NULL"
        ).fetchone()["n"]

        mode = "[DRY RUN] " if dry_run else ""
        print(
            f"\n{mode}Mãos: {total_hands} | mãos de mesa final c/ ICM: {ft_hands} | "
            f"linhas atualizadas: {updated_rows} | torneios c/ erro: {failed}"
        )
        print(f"Total de decisões com icm_tax_pct preenchido agora: {populated}")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    backfill(dry_run=args.dry_run, limit=args.limit)
