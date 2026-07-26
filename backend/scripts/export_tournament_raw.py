"""Exporta o hand history CRU (raw_text) de torneios para .txt — read-only.

Serve pra reproduzir um bug de outro usuário na sua própria conta: exporta o arquivo e
reimporta pelo fluxo normal. Funciona em SQLite (dev) e PostgreSQL (prod), via a camada do app.

Uso (dentro de backend/):
    python -m scripts.export_tournament_raw --user csm96                 # lista os torneios
    python -m scripts.export_tournament_raw --user csm96 --site coinpoker
    python -m scripts.export_tournament_raw --id 42 --out ./exports      # exporta 1 (id do banco)
    python -m scripts.export_tournament_raw --user csm96 --all --out ./exports

Nome do arquivo (mesmo padrão do endpoint admin):
    {site}_{tournament_id}_{tournament_name}.txt   (name sanitizado; omitido se vazio)
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn


def _arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _rows(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        return conn.execute(sql.replace('?', '%s'), params).fetchall()


def _v(row, key, idx):
    try:
        return row[key]
    except Exception:
        return row[idx]


def safe_filename(site: str, tournament_id: str, name: str | None) -> str:
    """Padrão único de nome (espelhado no endpoint admin de download)."""
    parts = [str(site or 'site'), str(tournament_id or 'sem-id')]
    if name:
        slug = re.sub(r'[^\w\-]+', '-', str(name), flags=re.UNICODE).strip('-')[:60]
        if slug:
            parts.append(slug)
    return '_'.join(parts) + '.txt'


def main():
    user = _arg('--user')
    site = _arg('--site')
    tid  = _arg('--id')
    out  = _arg('--out', '.')
    do_all = '--all' in sys.argv

    if not (user or tid):
        print(__doc__)
        return

    conn = get_conn()
    if tid:
        rows = _rows(conn, """SELECT t.id, t.tournament_id, t.site, t.tournament_name, t.hero,
                                     t.imported_at, t.hands_count, t.raw_text, u.username
                                FROM tournaments t JOIN users u ON u.id = t.user_id
                               WHERE t.id = ?""", (tid,))
    else:
        sql = """SELECT t.id, t.tournament_id, t.site, t.tournament_name, t.hero,
                        t.imported_at, t.hands_count, t.raw_text, u.username
                   FROM tournaments t JOIN users u ON u.id = t.user_id
                  WHERE (u.username = ? OR u.email = ?)"""
        params = [user, user]
        if site:
            sql += " AND t.site = ?"
            params.append(site)
        sql += " ORDER BY t.imported_at DESC"
        rows = _rows(conn, sql, tuple(params))

    if not rows:
        print("nenhum torneio encontrado")
        return

    print(f"{len(rows)} torneio(s):\n")
    for r in rows:
        raw = _v(r, 'raw_text', 7)
        print(f"  id={_v(r,'id',0):<6} {str(_v(r,'site',2)):<11} {str(_v(r,'tournament_id',1)):<14} "
              f"hero={str(_v(r,'hero',4)):<12} mãos={_v(r,'hands_count',6)} "
              f"raw={len(raw or '')} bytes  user={_v(r,'username',8)}")

    if not (tid or do_all):
        print("\n(use --id <id> ou --all pra exportar)")
        return

    os.makedirs(out, exist_ok=True)
    for r in rows:
        raw = _v(r, 'raw_text', 7)
        if not raw:
            print(f"  ! id={_v(r,'id',0)} sem raw_text (import antigo) — pulado")
            continue
        fname = safe_filename(_v(r, 'site', 2), _v(r, 'tournament_id', 1), _v(r, 'tournament_name', 3))
        path = os.path.join(out, fname)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(raw)
        print(f"  ✔ {path}  ({len(raw)} bytes)")


if __name__ == '__main__':
    main()
