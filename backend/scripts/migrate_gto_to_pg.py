"""
Migra os dados GTO do SQLite local → Postgres (Neon).

Copia SÓ o ativo de GTO que é caro de recriar:
  - gto_nodes          (nós postflop solvados / capturados do GW)
  - gto_tree_strategies (estratégias hand-aware, ligadas por tree_hash)
  - gto_preflop_ranges  (se houver linhas)

NÃO migra: users/tournaments/decisions (produção começa limpa), nem as filas
(gto_solver_queue / gto_hand_requests, que são trabalho transitório).

Idempotente: usa ON CONFLICT DO NOTHING, então rodar 2× não duplica.

PRÉ-REQUISITO: psycopg2 instalado e a connection string do Neon em DATABASE_URL.
    pip install psycopg2-binary   # se não tiver

Uso (no PC que tem o SQLite local):
    cd backend
    # Windows PowerShell:
    $env:DATABASE_URL="postgresql://...eu-central-1...neon.tech/grindlab?sslmode=require"
    python scripts/migrate_gto_to_pg.py --dry-run
    python scripts/migrate_gto_to_pg.py            # aplica
"""
import os
import sys
import argparse
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (tabela, coluna_de_conflito, colunas_a_ignorar_na_origem)
TABLES = [
    ("gto_nodes",           "spot_hash", {"id"}),
    ("gto_tree_strategies", "tree_hash", set()),
    ("gto_preflop_ranges",  None,        {"id"}),
]


def _default_sqlite():
    import database.schema as sch
    return getattr(sch, "SQLITE_PATH", os.path.join("data", "leaklab.db"))


def main():
    ap = argparse.ArgumentParser(description="Migra dados GTO do SQLite → Postgres (Neon).")
    ap.add_argument("--sqlite", default=None, help="caminho do leaklab.db (default: o do projeto)")
    ap.add_argument("--dry-run", action="store_true", help="só conta, não escreve")
    args = ap.parse_args()

    src_path = args.sqlite or _default_sqlite()
    if not os.path.exists(src_path):
        print(f"ERRO: SQLite não encontrado em {src_path}"); sys.exit(1)
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("ERRO: defina DATABASE_URL com a string do Neon (Postgres)."); sys.exit(1)

    import psycopg2
    from psycopg2.extras import execute_values

    sq = sqlite3.connect(src_path); sq.row_factory = sqlite3.Row
    pg = psycopg2.connect(dsn)
    print(f"Origem (SQLite): {src_path}")
    print(f"Destino (Postgres): {dsn.split('@')[-1].split('?')[0]}")
    print("-" * 60)

    total = 0
    for table, conflict, skip in TABLES:
        try:
            cols = [r[1] for r in sq.execute(f"PRAGMA table_info({table})")]
        except sqlite3.OperationalError:
            print(f"{table:24s} origem não tem a tabela — pulando"); continue
        if not cols:
            print(f"{table:24s} sem colunas — pulando"); continue
        use = [c for c in cols if c not in skip]
        rows = sq.execute(f"SELECT {','.join(use)} FROM {table}").fetchall()
        rows = [tuple(r) for r in rows]
        # contagem atual no destino
        cur = pg.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        before = cur.fetchone()[0]
        if not rows:
            print(f"{table:24s} origem vazia ({before} no destino) — nada a fazer"); continue
        if args.dry_run:
            print(f"{table:24s} {len(rows):>6} linhas na origem · {before} no destino → migraria")
            continue
        collist = ",".join(use)
        conflict_sql = f"ON CONFLICT ({conflict}) DO NOTHING" if conflict else "ON CONFLICT DO NOTHING"
        execute_values(cur, f"INSERT INTO {table} ({collist}) VALUES %s {conflict_sql}", rows, page_size=500)
        pg.commit()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        after = cur.fetchone()[0]
        inserted = after - before
        total += inserted
        print(f"{table:24s} {len(rows):>6} na origem · +{inserted} inseridas (destino: {before}→{after})")

    sq.close(); pg.close()
    print("-" * 60)
    print(f"{'DRY-RUN — nada escrito' if args.dry_run else f'OK — {total} linhas inseridas no Neon'}")


if __name__ == "__main__":
    main()
