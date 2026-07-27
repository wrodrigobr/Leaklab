"""Diagnóstico do painel de Uso do admin (DAU/WAU/MAU zerados).

O caminho tem 4 elos, e o código de produção engole exceção em dois deles — por isso o painel
pode ficar zerado sem nenhum sinal no log. Este script percorre os 4 SEM engolir nada:

  1. a tabela `feature_usage` existe neste banco?
  2. o INSERT ... ON CONFLICT funciona neste dialeto? (o upsert é a parte que mais varia
     entre SQLite e Postgres)
  3. há linhas gravadas? de quando?
  4. o relatório que o admin lê devolve o quê?

Uso (dentro de backend/):
    python -m scripts.diag_feature_usage
    cd ~/app && docker compose exec web python -m scripts.diag_feature_usage
"""
import sys, os, traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn


def _v(row, key, idx):
    """Nome primeiro, posição como fallback: em PG a linha é dict (`row[0]` → KeyError: 0)."""
    try:
        return row[key]
    except Exception:
        return row[idx]


def main():
    from database import schema as _sch
    pg = bool(getattr(_sch, 'USE_POSTGRES', False))
    print(f"banco: {'PostgreSQL' if pg else _sch.SQLITE_PATH}\n")
    conn = get_conn()
    try:
        # 1. tabela
        try:
            conn.execute("SELECT 1 FROM feature_usage LIMIT 1").fetchall()
            print("[1/4] tabela feature_usage: OK")
        except Exception as e:
            print(f"[1/4] ✖ tabela feature_usage NÃO EXISTE: {type(e).__name__}: {e}")
            print("      → a migração não rodou neste banco. Reinicie o backend após o deploy.")
            return

        # 2. o upsert (a parte que varia de dialeto) — sem try/except escondendo
        hoje = datetime.utcnow().strftime('%Y-%m-%d')
        print("[2/4] testando o upsert com uma chave de diagnóstico...")
        try:
            conn.execute(
                "INSERT INTO feature_usage (day, feature_key, user_id, hits) VALUES (?, ?, ?, 1) "
                "ON CONFLICT (day, feature_key, user_id) DO UPDATE SET hits = feature_usage.hits + 1",
                (hoje, '__diag__', 0))
            conn.commit()
            print("      OK: o INSERT ... ON CONFLICT funciona neste dialeto.")
            conn.execute("DELETE FROM feature_usage WHERE feature_key = '__diag__'")
            conn.commit()
        except Exception as e:
            try: conn.rollback()
            except Exception: pass
            print(f"      ✖ FALHOU: {type(e).__name__}: {e}")
            print("      → É ESTA a causa do painel zerado: record_feature_usage engole este erro.")
            traceback.print_exc()
            return

        # 3. dados
        row = conn.execute("SELECT COUNT(*) AS n FROM feature_usage").fetchone()
        total = int(_v(row, 'n', 0)) if row else 0
        print(f"[3/4] linhas gravadas: {total}")
        if total:
            dias = conn.execute(
                "SELECT day AS day, COUNT(*) AS n, SUM(hits) AS hits FROM feature_usage "
                "GROUP BY day ORDER BY day DESC LIMIT 7").fetchall()
            for r in dias:
                print(f"      {_v(r,'day',0)}: {_v(r,'n',1)} pares (feature,user) · {_v(r,'hits',2)} acessos")
        else:
            print("      → tabela vazia. Se JÁ houve tráfego autenticado depois do deploy, o")
            print("        gravador está falhando calado; procure 'record_feature_usage falhou'")
            print("        no log do container (agora ele loga uma vez por processo).")

        # 4. o que o admin lê
        from database.repositories import get_feature_usage_report
        rep = get_feature_usage_report(30)
        print(f"\n[4/4] relatório do admin (30d): dau={rep.get('dau')} wau={rep.get('wau')} "
              f"mau={rep.get('mau')} ativos_janela={rep.get('active_window')}")
        for f in (rep.get('features') or [])[:8]:
            print(f"      {f.get('feature_key'):24} usuários={f.get('users')} acessos={f.get('hits')}")
        if total and not rep.get('mau'):
            print("      ⚠ há linhas no banco mas o relatório devolve zero — o problema é a")
            print("        LEITURA (janela de dias / formato de `day`), não a gravação.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
