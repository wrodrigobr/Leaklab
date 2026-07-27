"""Diagnóstico: por que o dashboard diz "N spots sendo validados" e o admin mostra 0?

São DUAS filas diferentes, e é fácil confundir:
  · `gto_solver_queue`   — jobs do solver postflop. É o que o painel do admin conta em "Pendentes".
  · `gto_hand_requests`  — pedidos por MÃO (o "resolver esta mão" do replay). É o que o
                           dashboard do jogador conta.

Zero numa não implica zero na outra. Este script mostra as duas lado a lado e, principalmente,
a IDADE de cada pedido pendente: pedido parado há dias não está "em andamento", está preso —
ou o worker não está rodando, ou ele falha e volta pra fila.

Uso (dentro de backend/):
    python -m scripts.diag_pending_gto
    cd ~/app && docker compose exec web python -m scripts.diag_pending_gto
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn


def _v(row, key, idx):
    """Nome primeiro, posição como fallback: em PG a linha é dict (`row[0]` → KeyError: 0)."""
    try:
        return row[key]
    except Exception:
        return row[idx]


def _counts(conn, tabela):
    try:
        rows = conn.execute(
            f"SELECT status AS status, COUNT(*) AS n FROM {tabela} GROUP BY status").fetchall()
        return {str(_v(r, 'status', 0)): int(_v(r, 'n', 1)) for r in rows}
    except Exception as e:
        return {'(erro)': str(e)[:60]}


def main():
    conn = get_conn()
    try:
        from database import schema as _sch
        print(f"banco: {'PostgreSQL' if getattr(_sch, 'USE_POSTGRES', False) else _sch.SQLITE_PATH}\n")

        hr = _counts(conn, 'gto_hand_requests')
        sq = _counts(conn, 'gto_solver_queue')
        print(f"gto_hand_requests  (dashboard do jogador): {hr}")
        print(f"gto_solver_queue   (painel do admin)     : {sq}\n")

        rows = conn.execute("""
            SELECT r.id AS id, r.hand_id AS hand_id, r.requested_by AS uid,
                   r.created_at AS created_at, r.decisions_found AS found,
                   r.decisions_done AS done, r.error_msg AS err,
                   t.tournament_id AS tcode
            FROM gto_hand_requests r
            LEFT JOIN tournaments t ON t.id = r.tournament_id
            WHERE r.status = 'pending'
            ORDER BY r.id
        """).fetchall()

        if not rows:
            print("Nenhum pedido pendente em gto_hand_requests.")
            print("Se o dashboard ainda mostra o aviso, o backend está com código antigo "
                  "(o deploy não subiu) ou o navegador está com a resposta em cache.")
            return

        print(f"{len(rows)} pedido(s) PENDENTE(S) — é o número que o dashboard exibe:\n")
        for r in rows:
            print(f"  id={_v(r,'id',0)} user={_v(r,'uid',2)} torneio={_v(r,'tcode',7)} "
                  f"mão={_v(r,'hand_id',1)}")
            print(f"     criado em : {_v(r,'created_at',3)}")
            print(f"     progresso : {_v(r,'done',5)}/{_v(r,'found',4)} decisões")
            if _v(r, 'err', 6):
                print(f"     erro      : {str(_v(r,'err',6))[:120]}")
        print("\nComo ler: se `criado em` for de horas/dias atrás, o worker não está drenando a "
              "fila (ou falha e devolve o pedido). Pedido parado não é 'em andamento'.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
