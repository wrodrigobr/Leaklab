"""
diag_solver_analyzing.py — imprime os números CRUS que decidem o "analisando" da lista de torneios,
pra achar por que um torneio aparece "Analisado" mesmo com spots pendentes no solver.

Roda no HOST de prod (com DATABASE_URL → Neon):
    python scripts/diag_solver_analyzing.py rodrigo.phpro@gmail.com

Mostra, por torneio do usuário:
  - post_total / post_null (gto_label NULL ou '') / post_hu_null (n_active<2 ou NULL, E gto_label NULL)
  - gto_inflight (request não-terminal < 24h) / gto_recent (request qualquer < 24h)
  - solver_analyzing = post_hu_null>0 AND (solver_busy OR inflight OR recent)
E global:
  - quebra de status da gto_solver_queue (existe 'pending'/'running'? = solver_busy)
  - amostra dos gto_label/n_active das decisões postflop descobertas (NULL vs heurístico)
Não depende da lógica deployada — lê o estado direto, pra isolar DADO vs CÓDIGO.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from database.schema import get_conn

STALE_H = 24


def _rows(conn, sql, params=()):
    try:
        from database.repositories import _fetchall, _adapt
        return [dict(r) for r in _fetchall(conn, _adapt(sql), params)]
    except Exception:
        return [dict(r) for r in conn.execute(sql.replace('%s', '?'), params).fetchall()]


def main():
    email = sys.argv[1] if len(sys.argv) > 1 else 'rodrigo.phpro@gmail.com'
    cutoff = (datetime.utcnow() - timedelta(hours=STALE_H)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    try:
        u = _rows(conn, "SELECT id FROM users WHERE email = ?", (email,))
        if not u:
            print(f"usuário {email} não encontrado"); return
        uid = u[0]['id']
        print(f"== usuário {email} (id={uid}) | cutoff {STALE_H}h = {cutoff} ==\n")

        # 1) FILA do solver — existe pending/running? (= solver_busy)
        q = _rows(conn, "SELECT status, COUNT(*) AS n FROM gto_solver_queue GROUP BY status")
        qmap = {r['status']: r['n'] for r in q}
        busy = (qmap.get('pending', 0) + qmap.get('running', 0)) > 0
        print(f"[gto_solver_queue] {qmap}")
        print(f"[solver_busy] pending+running = {qmap.get('pending',0)+qmap.get('running',0)}  -> busy={busy}\n")

        # 2) Por torneio do usuário
        ts = _rows(conn,
            "SELECT id, tournament_id, tournament_name FROM tournaments "
            "WHERE user_id = ? ORDER BY imported_at DESC LIMIT 20", (uid,))
        print(f"{'tid':>6} {'post_t':>6} {'p_null':>6} {'hu_null':>7} {'inflt':>5} {'recent':>6} {'ANALYZING':>9}")
        for t in ts:
            tid = t['id']
            agg = _rows(conn,
                "SELECT "
                " SUM(CASE WHEN lower(street) IN ('flop','turn','river') THEN 1 ELSE 0 END) AS post_t, "
                " SUM(CASE WHEN lower(street) IN ('flop','turn','river') AND (gto_label IS NULL OR gto_label='') THEN 1 ELSE 0 END) AS post_null, "
                " SUM(CASE WHEN lower(street) IN ('flop','turn','river') AND (n_active_opponents IS NULL OR n_active_opponents<2) AND (gto_label IS NULL OR gto_label='') THEN 1 ELSE 0 END) AS post_hu_null "
                "FROM decisions WHERE tournament_id = ?", (tid,))[0]
            inflt = _rows(conn,
                "SELECT COUNT(*) AS n FROM gto_hand_requests WHERE tournament_id = ? "
                "AND status IN ('pending','solver_queued','processing','queued','running') AND created_at > ?",
                (tid, cutoff))[0]['n']
            recent = _rows(conn,
                "SELECT COUNT(*) AS n FROM gto_hand_requests WHERE tournament_id = ? AND created_at > ?",
                (tid, cutoff))[0]['n']
            hu_null = agg['post_hu_null'] or 0
            analyzing = (hu_null > 0) and (busy or (inflt or 0) > 0 or (recent or 0) > 0)
            print(f"{tid:>6} {agg['post_t'] or 0:>6} {agg['post_null'] or 0:>6} {hu_null:>7} {inflt or 0:>5} {recent or 0:>6} {str(analyzing):>9}")

        # 3) Amostra: gto_label/n_active das postflop DESCOBERTAS (NULL) de 1 torneio recente
        if ts:
            tid = ts[0]['id']
            print(f"\n[amostra tid={tid}] gto_label das postflop (NULL = descoberto; valor = heurístico/coberto):")
            dist = _rows(conn,
                "SELECT COALESCE(gto_label,'(NULL)') AS lbl, COUNT(*) AS n FROM decisions "
                "WHERE tournament_id=? AND lower(street) IN ('flop','turn','river') GROUP BY gto_label", (tid,))
            print("  " + str({r['lbl']: r['n'] for r in dist}))
            nact = _rows(conn,
                "SELECT COALESCE(CAST(n_active_opponents AS TEXT),'(NULL)') AS na, COUNT(*) AS n FROM decisions "
                "WHERE tournament_id=? AND lower(street) IN ('flop','turn','river') GROUP BY n_active_opponents", (tid,))
            print("  n_active_opponents: " + str({r['na']: r['n'] for r in nact}))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
