"""Diagnóstico dos processos de fundo — o que está VIVO em produção.

Motivo: três bugs numa noite tiveram a mesma raiz. Worker declarado dentro de
`if __name__ == '__main__'` NÃO roda sob gunicorn, então em produção ele precisa de um par
(cron ou serviço dedicado). Quando o par não existe, a fila entope em silêncio e a UI mente:
"3 spots sendo validados", "Análise GTO em andamento", indicadores zerados.

Ler o código diz se o par EXISTE. Este script diz se ele está RODANDO — olhando o rastro que
cada processo deixa no banco (último item processado, idade do pendente mais velho). Não precisa
de acesso a systemd nem ao crontab.

Uso:
    python -m scripts.diag_workers
    cd ~/app && docker compose exec web python -m scripts.diag_workers
"""
import sys, os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn


def _v(row, key, idx):
    """Nome primeiro, posição como fallback: em PG a linha é dict (`row[0]` → KeyError: 0)."""
    try:
        return row[key]
    except Exception:
        return row[idx]


def _one(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchone()
    except Exception as e:
        print(f"      (query falhou: {type(e).__name__}: {str(e)[:80]})")
        return None


def _idade(ts) -> str:
    """Idade legível de um timestamp do banco. Formato varia (SQLite texto × PG datetime)."""
    if not ts:
        return "nunca"
    s = str(ts)[:19].replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            d = datetime.strptime(s, fmt)
            delta = datetime.now(timezone.utc).replace(tzinfo=None) - d
            h = delta.total_seconds() / 3600
            if h < 1:
                return f"há {int(delta.total_seconds()/60)} min"
            if h < 48:
                return f"há {h:.1f} h"
            return f"há {int(h/24)} dias"
        except ValueError:
            continue
    return str(ts)


def _bloco(nome, par_em_prod, pendentes, mais_velho, ultimo_ok):
    """Imprime o veredito de um processo. O critério é simples e honesto: há pendente VELHO?"""
    print(f"\n── {nome}")
    print(f"   par em prod : {par_em_prod}")
    print(f"   pendentes   : {pendentes}")
    print(f"   mais velho  : {_idade(mais_velho)}")
    print(f"   último OK   : {_idade(ultimo_ok)}")
    if pendentes and mais_velho:
        s = str(mais_velho)[:19].replace('T', ' ')
        try:
            d = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
            if datetime.now(timezone.utc).replace(tzinfo=None) - d > timedelta(hours=1):
                print("   ⚠ PARADO: há pendente com mais de 1h. O par não está rodando.")
                return
        except ValueError:
            pass
        print("   ok: há fila, mas recente — provavelmente em processamento.")
    elif pendentes:
        print("   ok: há fila (sem data pra avaliar).")
    else:
        print("   ok: fila vazia.")


def main():
    from database import schema as _sch
    print(f"banco: {'PostgreSQL' if getattr(_sch, 'USE_POSTGRES', False) else _sch.SQLITE_PATH}")
    conn = get_conn()
    try:
        # 1. Pedidos por MÃO (o "resolver esta mão" do replay)
        r = _one(conn, "SELECT COUNT(*) AS n, MIN(created_at) AS velho "
                       "FROM gto_hand_requests WHERE status = 'pending'")
        u = _one(conn, "SELECT MAX(processed_at) AS ts FROM gto_hand_requests")
        _bloco("gto_hand_requests  (_gto_hand_worker_loop, só no __main__)",
               "cron: drain_hand_requests / drain_solver_queue._finalize_hand_requests",
               int(_v(r, 'n', 0) or 0) if r else 0,
               _v(r, 'velho', 1) if r else None,
               _v(u, 'ts', 0) if u else None)

        # 2. Fila do SOLVER
        r = _one(conn, "SELECT COUNT(*) AS n, MIN(requested_at) AS velho "
                       "FROM gto_solver_queue WHERE status IN ('pending','running')")
        u = _one(conn, "SELECT MAX(solved_at) AS ts FROM gto_solver_queue")
        _bloco("gto_solver_queue   (_solver_queue_worker_loop, só no __main__)",
               "serviço run_solver_consumer.py OU cron: drain_solver_queue",
               int(_v(r, 'n', 0) or 0) if r else 0,
               _v(r, 'velho', 1) if r else None,
               _v(u, 'ts', 0) if u else None)

        # 3. Carimbo de reconciliação (o selo "Análise GTO em andamento")
        r = _one(conn, "SELECT COUNT(*) AS n FROM tournaments WHERE labels_reconciled_at IS NULL")
        u = _one(conn, "SELECT MAX(labels_reconciled_at) AS ts FROM tournaments")
        sem = int(_v(r, 'n', 0) or 0) if r else 0
        print(f"\n── labels_reconciled_at  (_reconcile_drained_tournaments, só no __main__)")
        print(f"   par em prod : serviço run_solver_consumer.py OU cron: drain_solver_queue")
        print(f"   sem carimbo : {sem} torneio(s)  ← cada um mostra 'Análise GTO em andamento'")
        print(f"   último OK   : {_idade(_v(u, 'ts', 0) if u else None)}")
        if sem:
            print("   ⚠ Rode: docker compose exec web python -m scripts.drain_solver_queue")

        # 4. Analytics de uso
        r = _one(conn, "SELECT MAX(day) AS ts, COUNT(*) AS n FROM feature_usage")
        print(f"\n── feature_usage    (hook after_request, roda em prod normalmente)")
        print(f"   linhas      : {int(_v(r,'n',1) or 0) if r else 0}")
        print(f"   último dia  : {_v(r, 'ts', 0) if r else '(vazio)'}")
        print("   (se vazio APÓS tráfego autenticado: scripts/diag_feature_usage.py)")

        print("\n" + "=" * 70)
        print("Como ler: 'par em prod' é o que substitui o worker que só existe no __main__.")
        print("Se um bloco acusa PARADO, o par não está configurado ou parou de rodar.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
