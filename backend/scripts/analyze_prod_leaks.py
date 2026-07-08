"""
analyze_prod_leaks.py — Consolida os leaks de TODOS os torneios/jogadores e cruza
com o catalogo da Academia pra achar buracos de conteudo.

READ-ONLY (so SELECT). Rode no host onde o DATABASE_URL de prod esta setado:

    cd backend && python scripts/analyze_prod_leaks.py

Saida:
  1. Panorama (decisoes, jogadores, torneios, taxa de erro)
  2. Leaks por street x acao (onde o erro mora)
  3. Leaks por "lente conceitual" (3-bet, ICM, multiway, stack curto, etc.)
     cada um com o modulo da Academia correspondente e um alerta quando NAO ha aula.

As lentes conceituais se SOBREPOEM de proposito (um erro preflop 3-bet tambem conta
em "preflop"): sao recortes de diagnostico, nao uma particao.
"""
import sys, os
# bootstrap: acha o dir que contem 'database/' (roda por arquivo, via stdin ou no container)
_here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
for _cand in (os.path.join(_here, '..'), _here, os.getcwd(), '/app/backend', '/app'):
    if os.path.isdir(os.path.join(_cand, 'database')):
        sys.path.insert(0, _cand)
        break
from database.schema import get_conn

# label = pior erro; usamos small_mistake + clear_mistake como "leak".
MISTAKE = "label IN ('small_mistake','clear_mistake')"
# peso de severidade (mesma regua do leak_correlator)
SEV = "CASE WHEN label='clear_mistake' THEN 1.0 WHEN label='small_mistake' THEN 0.55 ELSE 0 END"


def truthy(col):
    """Booleano robusto entre Postgres (true/false) e SQLite (0/1)."""
    return f"CAST({col} AS TEXT) IN ('1','t','true','True','TRUE')"


def _vals(row):
    """Normaliza uma linha (dict no PG, Row/tuple no SQLite) numa lista posicional."""
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


def main():
    conn = get_conn()

    print("=" * 72)
    print("PANORAMA")
    print("=" * 72)
    total   = scalar(conn, "SELECT COUNT(*) FROM decisions")
    mist    = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {MISTAKE}")
    severe  = scalar(conn, "SELECT COUNT(*) FROM decisions WHERE label='clear_mistake'")
    players = scalar(conn, "SELECT COUNT(DISTINCT user_id) FROM tournaments "
                           "WHERE id IN (SELECT DISTINCT tournament_id FROM decisions)")
    tourns  = scalar(conn, "SELECT COUNT(DISTINCT tournament_id) FROM decisions")
    evloss  = scalar(conn, f"SELECT SUM(COALESCE(ev_loss_bb,0)) FROM decisions WHERE {MISTAKE}")
    rate = (mist / total * 100) if total else 0
    print(f"  decisoes analisadas : {total}")
    print(f"  jogadores           : {players}")
    print(f"  torneios            : {tourns}")
    print(f"  leaks (erros)       : {mist}  ({rate:.1f}% das decisoes)")
    print(f"  erros graves        : {severe}")
    print(f"  EV perdido (bb)     : {float(evloss or 0):.1f}")

    print()
    print("=" * 72)
    print("LEAKS POR STREET x ACAO (onde o erro mora)")
    print("=" * 72)
    print(f"  {'street':8s} {'acao':7s} {'erros':>7s} {'sev.med':>8s} {'EV bb':>9s}")
    for r in rows(conn, f"""
        SELECT COALESCE(street,'?') s, COALESCE(action_taken,'?') a, COUNT(*) n,
               AVG({SEV}) sev, SUM(COALESCE(ev_loss_bb,0)) ev
        FROM decisions WHERE {MISTAKE}
        GROUP BY street, action_taken ORDER BY COUNT(*) DESC LIMIT 15"""):
        s, a, n, sev, ev = r[0], r[1], r[2], r[3], r[4]
        print(f"  {str(s):8s} {str(a):7s} {int(n):7d} {float(sev or 0):8.3f} {float(ev or 0):9.1f}")

    print()
    print("=" * 72)
    print("LEAKS POR LENTE CONCEITUAL  ->  MODULO DA ACADEMIA")
    print("=" * 72)
    # (nome, WHERE do recorte, modulo academia, tem_aula?)
    lenses = [
        ("Preflop RFI (abertura)",
         "street='preflop' AND COALESCE(preflop_raises_faced,0)=0 AND COALESCE(stack_bb,100)>12",
         "ranges (/academy/gto-preflop)", True),
        ("Preflop defesa vs open",
         f"street='preflop' AND COALESCE(preflop_raises_faced,0)>=1 AND NOT {truthy('is_3bet')}",
         "ranges (vs_RFI)", True),
        ("Preflop pote 3-bet",
         f"street='preflop' AND {truthy('is_3bet')}",
         "ranges_advanced (vs_3bet)", True),
        ("Preflop STACK CURTO <=12bb (push/fold)",
         "street='preflop' AND COALESCE(stack_bb,100)<=12",
         "SEM AULA DEDICADA (tournament cobre so ICM)", False),
        ("Spots com ICM (medio/alto)",
         "icm_pressure IN ('high','medium')",
         "icm (/academy/icm)", True),
        ("Potes multiway (3+ no pote)",
         "COALESCE(n_active_opponents,1)>=2",
         "multiway (/academy/multiway)", True),
        ("Postflop FLOP",
         "street='flop'",
         "postflop / board_strength / bet_sizing", True),
        ("Postflop TURN",
         "street='turn'",
         "postflop / bet_sizing", True),
        ("Postflop RIVER",
         "street='river'",
         "postflop / math", True),
        ("River call (bluff-catch / pot odds)",
         "street='river' AND lower(action_taken)='call'",
         "math / showdown", True),
        ("Postflop com draw",
         "street IN ('flop','turn') AND draw_profile IS NOT NULL AND draw_profile <> ''",
         "math (equity/outs) / board_strength", True),
    ]
    results = []
    for name, where, module, has in lenses:
        n  = scalar(conn, f"SELECT COUNT(*) FROM decisions WHERE {MISTAKE} AND ({where})")
        ev = scalar(conn, f"SELECT SUM(COALESCE(ev_loss_bb,0)) FROM decisions WHERE {MISTAKE} AND ({where})")
        results.append((int(n or 0), float(ev or 0), name, module, has))
    results.sort(key=lambda x: -x[0])
    print(f"  {'erros':>7s} {'EV bb':>9s}  lente / modulo")
    for n, ev, name, module, has in results:
        flag = "" if has else "   <== BURACO DE CONTEUDO"
        print(f"  {n:7d} {ev:9.1f}  {name}")
        print(f"  {'':7s} {'':9s}    -> {module}{flag}")

    print()
    print("=" * 72)
    print("ALERTAS DE COBERTURA")
    print("=" * 72)
    gaps = [(n, name, module) for n, ev, name, module, has in results if not has and n > 0]
    if gaps:
        for n, name, module in sorted(gaps, key=lambda x: -x[0]):
            print(f"  {n} erros sem aula dedicada: {name}")
    else:
        print("  Nenhum recorte com volume relevante sem aula. Cobertura ok.")
    print()
    print("Obs.: as lentes se sobrepoem (recortes de diagnostico, nao particao).")
    conn.close()


if __name__ == "__main__":
    main()
