"""
Backfill de `decisions.gto_played_freq` / `gto_top_freq` — a PUREZA da estratégia.

O que isso destrava: hoje `gto_label` só diz a faixa de frequência da ação JOGADA, então um fold
marcado `gto_correct` pode ser 100% (decisão automática, ninguém erra) ou 65% (decisão de verdade).
Sem separar, a taxa de erro de RFI dilui — cerca de 84% das decisões são folds óbvios, e um
"0% de erro" pode conviver com um limp de posição inicial que erra 3 de 3.

Com `gto_top_freq` gravado, dá para dizer o que hoje não dá: **"você acerta os spots puros e erra
os mistos"**, que é o diagnóstico mais fino que existe em preflop.

Como funciona: reprocessa `tournaments.raw_text` pelo MESMO caminho do /analyze
(`build_decision_inputs_for_hand` → `evaluate_decision` → `strategy_purity`) e atualiza as
decisões daquela mão. Não recalcula nada por conta própria — recalcular aqui criaria a segunda
definição de "frequência" que este projeto já pagou caro para não ter.

Idempotente: só toca linhas com `gto_top_freq IS NULL`.

Uso (dry-run por padrão):
    cd ~/app && docker compose exec web python -m scripts.backfill_strategy_purity
    cd ~/app && docker compose exec web python -m scripts.backfill_strategy_purity --apply
    cd ~/app && docker compose exec web python -m scripts.backfill_strategy_purity --apply --limit 5
"""
import sys, os, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.schema import get_conn
from database.repositories import _adapt, _fetchall, _fetchone
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision, strategy_purity


def _norm(a) -> str:
    a = (a or '').strip().lower()
    a = a[:-1] if a.endswith('s') else a
    return 'allin' if a in ('all-in', 'allin', 'jam', 'shove') else a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='executa (sem isto, só relata)')
    ap.add_argument('--limit', type=int, default=0, help='no máximo N torneios')
    args = ap.parse_args()

    conn = get_conn()
    try:
        pend = _fetchone(conn, _adapt(
            "SELECT COUNT(*) AS n FROM decisions WHERE gto_top_freq IS NULL"))
        total = _fetchone(conn, _adapt("SELECT COUNT(*) AS n FROM decisions"))
        print(f"decisões sem pureza gravada: {pend['n']} de {total['n']}")
        if not pend['n']:
            print("nada a fazer.")
            return

        q = ("SELECT DISTINCT t.id AS tid, t.tournament_id AS ext, t.raw_text AS raw "
             "FROM tournaments t JOIN decisions d ON d.tournament_id = t.id "
             "WHERE d.gto_top_freq IS NULL AND t.raw_text IS NOT NULL ORDER BY t.id")
        if args.limit:
            q += f" LIMIT {int(args.limit)}"
        torneios = _fetchall(conn, _adapt(q))
        print(f"torneios a reprocessar: {len(torneios)}\n")
    finally:
        conn.close()

    if not args.apply:
        print("(dry-run — nada foi alterado. Rode com --apply para executar.)")
        return

    maos = atualizadas = sem_cobertura = falhas = 0
    for t in torneios:
        try:
            hands = parse_hand_history(t['raw'])
        except Exception as e:
            print(f"  [WARN] torneio {t['ext']}: parse falhou — {e}")
            falhas += 1
            continue

        conn = get_conn()
        try:
            for h in hands:
                maos += 1
                try:
                    for di in build_decision_inputs_for_hand(h):
                        r = evaluate_decision(di)
                        played, top = strategy_purity(r)
                        if top is None:
                            sem_cobertura += 1
                            continue
                        cur = conn.execute(_adapt(
                            "UPDATE decisions SET gto_played_freq = ?, gto_top_freq = ? "
                            "WHERE tournament_id = ? AND hand_id = ? AND action_taken = ? "
                            "AND gto_top_freq IS NULL"),
                            (played, top, t['tid'], str(h.hand_id),
                             r.get('actionTaken') or r.get('action_taken') or ''))
                        atualizadas += (cur.rowcount or 0)
                except Exception:
                    falhas += 1
            conn.commit()
        finally:
            conn.close()
        print(f"  torneio {t['ext']}: acumulado {atualizadas} decisões")

    print(f"\n✔ mãos processadas: {maos} | decisões atualizadas: {atualizadas}")
    print(f"  sem cobertura GTO (ficam NULL, é honesto): {sem_cobertura} | falhas: {falhas}")


if __name__ == '__main__':
    main()
