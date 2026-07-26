"""Backfill de `decisions.stack_bb` a partir do hand history cru — Fase 0.2 do Protocolo.

Por que: `mtt_context` extraía o stack do hero com um regex que exigia "(N in chips)" sem
separador de milhar. ACR (sem "in chips") e CoinPoker/GG (milhar com vírgula) nunca casavam,
então `stack_bb` ficou NULO em boa parte do histórico — medido: ACR 100%, CoinPoker 98%,
GG 67%, PokerStars 4%. Sem profundidade, o leak não sabe em que stack aconteceu e o treino
serve o spot errado (era 43% do EV perdido sem stack).

O parser já lê o stack corretamente em todos os dialetos (hand.seats); este script reparseia
o `tournaments.raw_text` que já está no banco e preenche só as linhas NULAS.

Read-only por padrão. Só escreve com --apply.

Uso (dentro de backend/):
    python -m scripts.backfill_stack_bb                    # relatório (dry-run)
    python -m scripts.backfill_stack_bb --user CSM96
    python -m scripts.backfill_stack_bb --apply            # grava
    python -m scripts.backfill_stack_bb --apply --tid 72561
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.mtt_context import build_mtt_context


def _arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def open_db(cmd_exemplo: str):
    """Abre a conexão dizendo em QUAL banco está e falha cedo se estiver vazio."""
    from database import schema as _sch
    pg = bool(getattr(_sch, 'USE_POSTGRES', False))
    print(f"banco: {'PostgreSQL (DATABASE_URL definido)' if pg else f'SQLite ({_sch.SQLITE_PATH})'}")
    conn = get_conn()
    try:
        conn.execute("SELECT 1 FROM tournaments LIMIT 1").fetchall()
    except Exception:
        print("\n  ✖ este banco não tem as tabelas da aplicação (está vazio).")
        if not pg:
            print("  DATABASE_URL não definido — rode dentro do container:")
            print(f"      cd ~/app && docker compose exec web {cmd_exemplo}")
        sys.exit(1)
    print()
    return conn


def _v(row, key, idx):
    try:
        return row[key]
    except Exception:
        return row[idx]


def main():
    apply_ = '--apply' in sys.argv
    user   = _arg('--user')
    tid    = _arg('--tid')

    conn = open_db("python -m scripts.backfill_stack_bb --apply")

    sql = """SELECT t.id, t.tournament_id, t.site, t.raw_text, u.username
               FROM tournaments t JOIN users u ON u.id = t.user_id
              WHERE t.raw_text IS NOT NULL AND t.raw_text <> ''"""
    params = []
    if user:
        sql += " AND (LOWER(u.username) LIKE ? OR LOWER(COALESCE(u.email,'')) LIKE ?)"
        params += [f"%{user.lower().strip()}%"] * 2
    if tid:
        sql += " AND t.tournament_id = ?"
        params.append(tid)
    sql += " ORDER BY t.id"

    tours = conn.execute(sql, tuple(params)).fetchall()
    if not tours:
        print("nenhum torneio com raw_text encontrado")
        return

    print(f"{len(tours)} torneio(s) com hand history cru\n")
    print(f"{'torneio':<16} {'site':<11} {'nulos':>7} {'recuper.':>9} {'s/ mão':>7}")
    print("-" * 56)

    tot_null = tot_fix = tot_miss = 0
    for t in tours:
        t_pk = _v(t, 'id', 0)
        rows = conn.execute(
            "SELECT id, hand_id FROM decisions WHERE tournament_id = ? AND stack_bb IS NULL",
            (t_pk,)).fetchall()
        if not rows:
            continue
        try:
            hands = parse_hand_history(_v(t, 'raw_text', 3))
        except Exception as e:
            print(f"{str(_v(t,'tournament_id',1)):<16} {str(_v(t,'site',2)):<11} "
                  f"{len(rows):>7} {'ERRO':>9}  ({e})")
            continue
        # hand_id → stack_bb (uma vez por mão; várias decisões compartilham a mesma mão)
        stack_by_hand = {}
        for h in hands:
            try:
                sb = build_mtt_context(h).hero_stack_bb
            except Exception:
                sb = None
            if sb is not None:
                stack_by_hand[str(h.hand_id)] = float(sb)

        fix = miss = 0
        updates = []
        for r in rows:
            sb = stack_by_hand.get(str(_v(r, 'hand_id', 1)))
            if sb is None:
                miss += 1
            else:
                fix += 1
                updates.append((sb, _v(r, 'id', 0)))
        tot_null += len(rows); tot_fix += fix; tot_miss += miss
        print(f"{str(_v(t,'tournament_id',1)):<16} {str(_v(t,'site',2)):<11} "
              f"{len(rows):>7} {fix:>9} {miss:>7}")

        if apply_ and updates:
            for sb, did in updates:
                conn.execute("UPDATE decisions SET stack_bb = ? WHERE id = ?", (sb, did))
            conn.commit()

    print("-" * 56)
    pct = (100 * tot_fix / tot_null) if tot_null else 0
    print(f"{'TOTAL':<28} {tot_null:>7} {tot_fix:>9} {tot_miss:>7}   ({pct:.0f}% recuperável)")
    if apply_:
        print("\n✔ gravado (--apply).")
    else:
        print("\n(dry-run — nada gravado; use --apply para gravar)")
    conn.close()


if __name__ == '__main__':
    main()
