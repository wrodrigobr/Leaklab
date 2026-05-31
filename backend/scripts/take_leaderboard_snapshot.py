"""
Grava um snapshot do leaderboard (#15) — uma "fotografia" do ranking no momento,
uma linha por jogador elegível (rank, score, dimensões). Constrói a série
temporal que alimenta o histórico de posição e o delta ("subiu X posições").

Pensado para rodar como CRON DIÁRIO. Enquanto não há scheduler/hosting, o
endpoint `/metrics/leaderboard` também grava sob demanda (~1/dia). Este script é
o ponto de entrada para um cron real (Render cron, Windows Task Scheduler, etc.).

Uso:
    cd backend
    python scripts/take_leaderboard_snapshot.py            # período padrão (90 dias)
    python scripts/take_leaderboard_snapshot.py --period 30
    python scripts/take_leaderboard_snapshot.py --force    # ignora o guard de ~1/dia

Agendamento (exemplos):
    # Windows Task Scheduler (diário): aponte para este script com o python do projeto.
    # cron (Linux):  0 3 * * *  cd /app/backend && python scripts/take_leaderboard_snapshot.py
"""
import sys
import argparse

sys.path.insert(0, ".")

from database.schema import init_db
from database.repositories import (
    take_leaderboard_snapshot, maybe_take_daily_snapshot, get_last_snapshot_at,
)


def main():
    ap = argparse.ArgumentParser(description="Grava um snapshot do leaderboard (#15).")
    ap.add_argument("--period", type=int, default=90, help="janela do ranking em dias (default 90)")
    ap.add_argument("--force", action="store_true", help="grava mesmo se já houve snapshot hoje")
    args = ap.parse_args()

    init_db()  # garante schema/migrations (idempotente)

    if args.force:
        n = take_leaderboard_snapshot(args.period)
        print(f"[snapshot] gravado (forçado): {n} linhas | período {args.period}d")
    else:
        took = maybe_take_daily_snapshot(args.period)
        if took:
            print(f"[snapshot] gravado | período {args.period}d")
        else:
            print(f"[snapshot] pulado — já houve snapshot recente (último: {get_last_snapshot_at(args.period)})")


if __name__ == "__main__":
    main()
