"""
diag_tournament_coverage.py — Por que um torneio ficou com cobertura GTO baixa?

Quebra as decisoes de UM torneio em coberta vs nao-coberta e, entre as nao-cobertas,
mostra o motivo provavel: fila ainda pendente (transitorio), multiway, stack fundo,
preflop sem cobertura, ou bb nao extraido (nos degenerados).

READ-ONLY. Rode no host com o DATABASE_URL de prod:
    docker compose exec -T web python - < scripts/diag_tournament_coverage.py            # torneio mais recente
    docker compose exec -T web python - < scripts/diag_tournament_coverage.py 3910307458  # por tournament_id externo
    docker compose exec -T web python - < scripts/diag_tournament_coverage.py --id 151     # por id interno

Coberta = gto_label IS NOT NULL (mesma regua do painel).
"""
import sys, os
_here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
for _cand in (os.path.join(_here, '..'), _here, os.getcwd(), '/app/backend', '/app'):
    if os.path.isdir(os.path.join(_cand, 'database')):
        sys.path.insert(0, _cand)
        break
from database.schema import get_conn


def _vals(row):
    if row is None:
        return []
    if isinstance(row, dict):
        return list(row.values())
    return list(row)


def scalar(conn, sql, default=0):
    v = _vals(conn.execute(sql).fetchone())
    return v[0] if v and v[0] is not None else default


def rows(conn, sql):
    return [_vals(r) for r in conn.execute(sql).fetchall()]


def _resolve_tid(conn, argv):
    """Resolve o id INTERNO do torneio a partir do argv (id interno, tournament_id externo,
    ou o mais recente por imported_at)."""
    # flags
    if '--id' in argv:
        return int(argv[argv.index('--id') + 1])
    pos = [a for a in argv[1:] if not a.startswith('--')]
    if pos:
        ext = pos[0]
        # tenta como tournament_id externo
        r = _vals(conn.execute(
            f"SELECT id FROM tournaments WHERE CAST(tournament_id AS TEXT) = '{ext}' ORDER BY id DESC LIMIT 1").fetchone())
        if r:
            return int(r[0])
        # senao trata como id interno
        return int(ext)
    # mais recente
    r = _vals(conn.execute(
        "SELECT id FROM tournaments ORDER BY COALESCE(imported_at, played_at) DESC, id DESC LIMIT 1").fetchone())
    return int(r[0]) if r else None


def main():
    conn = get_conn()
    tid = _resolve_tid(conn, sys.argv)
    if tid is None:
        print("Nenhum torneio encontrado."); return

    meta = _vals(conn.execute(
        f"SELECT tournament_id, site, hero, tournament_name, imported_at FROM tournaments WHERE id = {tid}").fetchone())
    print("=" * 72)
    print(f"TORNEIO id={tid}  externo={meta[0] if meta else '?'}  site={meta[1] if meta else '?'}")
    print(f"  hero={meta[2] if meta else '?'}  nome={meta[3] if meta else '?'}  importado={meta[4] if meta else '?'}")
    print("=" * 72)

    W = f"tournament_id = {tid}"
    total   = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {W}")
    if not total:
        print("Sem decisoes para este torneio."); conn.close(); return
    covered = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {W} AND gto_label IS NOT NULL AND gto_label <> ''")
    pct = covered / total * 100
    print(f"  decisoes        : {total}")
    print(f"  cobertas (GTO)  : {covered}  ({pct:.1f}%)")
    print(f"  NAO cobertas    : {total - covered}  ({100 - pct:.1f}%)")

    print()
    print("NAO-COBERTAS por street:")
    for r in rows(conn, f"""
        SELECT COALESCE(street,'?') s, COUNT(*) n FROM decisions
        WHERE {W} AND (gto_label IS NULL OR gto_label = '')
        GROUP BY street ORDER BY COUNT(*) DESC"""):
        print(f"  {str(r[0]):8s} {int(r[1]):5d}")

    print()
    print("MOTIVO das nao-cobertas (buckets MUTUAMENTE EXCLUSIVOS, em ordem de prioridade):")
    unc = f"{W} AND (gto_label IS NULL OR gto_label = '')"
    _MW   = "COALESCE(n_active_opponents,1) >= 2"
    _DEEP = "COALESCE(stack_bb,0) > 60"
    pf   = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {unc} AND street='preflop'")
    mw   = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {unc} AND street<>'preflop' AND {_MW}")
    deep = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {unc} AND street<>'preflop' AND NOT ({_MW}) AND {_DEEP}")
    hu   = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {unc} AND street<>'preflop' AND NOT ({_MW}) AND NOT ({_DEEP})")
    print(f"  preflop sem cobertura            : {pf}    (limped pot / cenario nao coberto)")
    print(f"  postflop MULTIWAY (3+)           : {mw}    ESTRUTURAL: solver e HU-only")
    print(f"  postflop HU fundo (>60bb)        : {deep}    ESTRUTURAL: solver capa ~60bb (ha aprox opcao B)")
    print(f"  postflop HU raso (<=60bb)        : {hu}    <== ACIONAVEL: deveria ser coberto, investigar")

    print()
    print("FILA DO SOLVER para os spots DESTE torneio (gto_tournament_queue -> gto_solver_queue):")
    qrows = rows(conn, f"""
        SELECT COALESCE(sq.status,'(sem linha na fila)') st, COUNT(*) n
        FROM gto_tournament_queue gtq
        LEFT JOIN gto_solver_queue sq ON sq.spot_hash = gtq.spot_hash
        WHERE gtq.tournament_id = {tid}
        GROUP BY sq.status ORDER BY COUNT(*) DESC""")
    if qrows:
        for r in qrows:
            print(f"  {str(r[0]):22s} {int(r[1]):5d}")
        pend = scalar(conn, f"""
            SELECT COUNT(*) FROM gto_tournament_queue gtq
            LEFT JOIN gto_solver_queue sq ON sq.spot_hash = gtq.spot_hash
            WHERE gtq.tournament_id = {tid} AND sq.status IN ('pending','running')""")
        if pend:
            print(f"  >> {pend} spots deste torneio AINDA na fila (pending/running): cobertura sobe quando drenar.")
    else:
        print("  (nenhum spot deste torneio na gto_tournament_queue)")

    print()
    print("SANIDADE DE BB (nos degenerados / bb nao extraido):")
    mn = scalar(conn, f"SELECT MIN(stack_bb) FROM decisions WHERE {W}")
    mx = scalar(conn, f"SELECT MAX(stack_bb) FROM decisions WHERE {W}")
    huge = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {W} AND COALESCE(stack_bb,0) > 500")
    tiny = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {W} AND stack_bb IS NOT NULL AND stack_bb > 0 AND stack_bb < 2")
    nullbb = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {W} AND stack_bb IS NULL")
    null_pct = nullbb / total * 100
    print(f"  stack_bb min/max : {mn} / {mx}")
    print(f"  stack_bb > 500bb : {huge}   (>0 = bb NAO extraido -> pote/stack em FICHAS)")
    print(f"  stack_bb 0<x<2bb : {tiny}   (muitos = normalizacao de bb errada, stack irreal)")
    print(f"  stack_bb NULL    : {nullbb}  ({null_pct:.0f}%)")
    # As tres assinaturas de bb quebrado: chips-as-bb (>500), stack minusculo (<2), ou NULL em massa.
    if huge or tiny > total * 0.2 or null_pct >= 50:
        print("  >> SUSPEITA FORTE: parser nao extraiu o big blind deste formato/site.")
        print("     Rode: python -m scripts.diag_missing_bb  (revela o header que o SB_RE nao casa)")

    print()
    print("Coberta = gto_label preenchido. Se 'postflop sem cobertura' ~ 'pending' na fila,")
    print("e' transitorio (solver drenando). Se e' multiway/deep/bb, e' estrutural.")
    conn.close()


if __name__ == "__main__":
    main()
