"""
diag_solver_analyzing.py — por que um torneio aparece (ou não) com "Análise GTO em andamento".

Roda no HOST de prod (com DATABASE_URL → Neon):
    python scripts/diag_solver_analyzing.py rodrigo.phpro@gmail.com

── AS DUAS COLUNAS DE VEREDITO, E POR QUE SÃO DUAS ────────────────────────────────────────

Este script sempre teve uma conta PRÓPRIA, de propósito: lendo o estado cru, sem passar pela
lógica deployada, ele isola DADO de CÓDIGO. Isso continua valendo e é o valor dele.

O que quebrou foi outra coisa. Em 2026-07-07 a produção trocou o sinal de "fila GLOBAL ocupada"
para "spot DESTE torneio na fila" (`gto_tq_busy`), porque o proxy global acendia o torneio de um
usuário quando OUTRO subia mãos. A conta daqui ficou na versão antiga, **sem rótulo dizendo que
era uma segunda opinião** — então ela era lida como o veredito. Em 2026-07-28 isso imprimiu
`True` em 18 de 20 torneios, incluindo os de meses atrás, com `inflight=0` e `recent=0` em quase
todos, só porque a fila global tinha 15 pendentes. Diagnóstico que discorda da produção sem
avisar não é neutro: ele inventa um culpado, e quem lê acredita, porque é para isso que ele
existe.

Agora saem as duas, lado a lado:

  PROD   — vem de `get_tournaments`, a MESMA função que alimenta a tela. Se a regra mudar,
           esta coluna muda junto, sem ninguém precisar lembrar deste arquivo.
  CRU    — a leitura independente, a partir dos ingredientes.

Divergência entre elas não é bug do script: é EXATAMENTE o achado que se procura aqui (código
deployado velho, réplica de leitura em outro lugar, ou dado que a query da produção não enxerga).
Por isso as linhas discordantes saem marcadas com "!=".

── E O SELO TEM DUAS CAUSAS, NÃO UMA ───────────────────────────────────────────────────────

A tela acende com `avg_score != null AND (labels_reconciled_at IS NULL OR solver_analyzing)`.
A segunda causa não tem nada a ver com a fila: é a reconciliação de labels pendente. Investigar
só o `solver_analyzing` explica metade dos casos, e escolher a metade errada custa horas.
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

        # FILA GLOBAL — contexto, NÃO veredito. Fica visível justamente para dar para ver que ela
        # pode estar cheia sem que nenhum torneio deste usuário esteja esperando coisa alguma.
        q = _rows(conn, "SELECT status, COUNT(*) AS n FROM gto_solver_queue GROUP BY status")
        qmap = {r['status']: r['n'] for r in q}
        print(f"[gto_solver_queue GLOBAL] {qmap}")
        print(f"  ativos = {qmap.get('pending',0) + qmap.get('running',0)}"
              f"   (contexto: a fila global NÃO é mais o sinal, desde 2026-07-07)\n")

        from database.repositories import get_tournaments
        vivos = get_tournaments(uid, limit=20)

        print(f"{'tid':>6} {'hu_null':>7} {'tq_busy':>7} {'inflt':>5} {'reconc':>6} "
              f"{'PROD':>6} {'CRU':>6}  {'SELO':>4}")
        divergentes = []
        for t in vivos:
            tid = t['id']
            hu_null = _rows(conn,
                "SELECT SUM(CASE WHEN lower(street) IN ('flop','turn','river') "
                "  AND (n_active_opponents IS NULL OR n_active_opponents<2) "
                "  AND (gto_label IS NULL OR gto_label='') THEN 1 ELSE 0 END) AS n "
                "FROM decisions WHERE tournament_id = ?", (tid,))[0]['n'] or 0
            # Os DOIS ingredientes do sinal, cada um na sua coluna: sem isso o veredito é opaco e
            # não dá para saber se o torneio espera a fila ou um request próprio.
            tq = _rows(conn,
                "SELECT COUNT(*) AS n FROM gto_tournament_queue m "
                "JOIN gto_solver_queue q ON q.spot_hash = m.spot_hash "
                "WHERE m.tournament_id = ? AND q.status IN ('pending','running')", (tid,))[0]['n']
            inflt = _rows(conn,
                "SELECT COUNT(*) AS n FROM gto_hand_requests WHERE tournament_id = ? "
                "AND status IN ('pending','solver_queued','processing','queued','running') "
                "AND created_at > ?", (tid, cutoff))[0]['n']

            prod = bool(t.get('solver_analyzing'))
            cru = bool(hu_null > 0 and (tq > 0 or inflt > 0))
            reconc = 'NULL' if t.get('labels_reconciled_at') is None else 'ok'
            # A condição EXATA da tela, que é o que o usuário de fato vê.
            selo = bool(t.get('avg_score') is not None
                        and (t.get('labels_reconciled_at') is None or prod))
            marca = '' if prod == cru else '  != PROD e CRU discordam'
            if prod != cru:
                divergentes.append(tid)
            print(f"{tid:>6} {hu_null:>7} {tq:>7} {inflt:>5} {reconc:>6} "
                  f"{str(prod):>6} {str(cru):>6}  {'SIM' if selo else '-':>4}{marca}")

        print("\nPROD = get_tournaments (o que a tela usa) · CRU = leitura independente daqui.")
        print("SELO = avg_score E (reconc=NULL OU PROD). Note: reconc=NULL acende SOZINHO,")
        print("       sem envolver o solver — é a causa que mais se confunde com fila travada.")
        if divergentes:
            print(f"\n!! PROD e CRU discordam em {divergentes}: código deployado velho, ou a query")
            print("   da produção não enxerga um dado que existe. Investigue ANTES do resto.")

        # Se algo está aceso pela fila, mostrar QUAIS spots prendem. É a diferença entre "espere,
        # está solvando" e "está preso num spot que nunca vai fechar" — que já aconteceu aqui.
        presos = [t['id'] for t in vivos if t.get('solver_analyzing')]
        if presos:
            tid = presos[0]
            print(f"\n[spots que prendem o tid={tid}]")
            # `requested_at`, e não `created_at`: quem tem `created_at` é a gto_tournament_queue
            # (o vínculo), não a fila do solver. E a fila não guarda contador de tentativas.
            linhas = _rows(conn,
                "SELECT q.spot_hash AS h, q.status AS st, q.priority AS pri, "
                "       q.requested_at AS pedido, m.created_at AS vinculado "
                "FROM gto_tournament_queue m JOIN gto_solver_queue q ON q.spot_hash = m.spot_hash "
                "WHERE m.tournament_id = ? AND q.status IN ('pending','running') "
                "ORDER BY q.requested_at LIMIT 10", (tid,))
            if not linhas:
                print("  nenhum. Então este torneio está aceso por request próprio (inflt), "
                      "não pela fila.")
            for r in linhas:
                print(f"  {str(r['h'])[:16]}  {r['st']:<8} prio={r['pri']}  "
                      f"pedido {r['pedido']}  vinculado {r['vinculado']}")
            print("  (spot_hash é COMPARTILHADO entre torneios: um pedido de outro torneio, de "
                  "qualquer usuário,\n   acende este aqui se for o mesmo spot. É legítimo, a "
                  "cobertura dele vai mesmo melhorar.)")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
