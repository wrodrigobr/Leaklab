"""Localiza a MÃO de um jogador pelas cartas do hero (e opcionalmente posição/stack) — read-only.

Serve pra achar o torneio/hand_id de um print de bug reportado pelo usuário.
Busca em DUAS camadas (a 2ª pega mãos que não viraram linha em `decisions`):
  1) tabela `decisions` (rápido) — traz posição, stack, ação e veredito
  2) varredura do `raw_text` do torneio (definitivo) — acha pelo "Dealt to <hero> [Jd 6d]"

Uso (dentro de backend/):
    python -m scripts.find_hand --user csm96 --cards J6 --suited
    python -m scripts.find_hand --user csm96 --cards Jd6d
    python -m scripts.find_hand --user csm96 --cards Jd6d --pos BB --stack 2.2
    python -m scripts.find_hand --cards Jd6d                     # todos os usuários

Saída: torneio (site + id), hand_id e a URL do replay (/replay/<tournament_db_id>/<hand_id>).
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history

RANKS = "23456789TJQKA"


def _arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _rows(conn, sql, params=()):
    # NÃO tentar reescrever placeholder aqui: o _AdaptedConn do schema.py já normaliza
    # '?' → '%s' conforme o backend. Um try/except em volta só mascarava o erro real
    # (ex.: "no such table" virava um confuso "near %: syntax error").
    return conn.execute(sql, params).fetchall()


def open_db(cmd_exemplo: str):
    """Abre a conexão dizendo em QUAL banco está falando e falhando CEDO com mensagem clara
    quando não há dado nenhum. Sem DATABASE_URL o schema.py cai no SQLite local — no host de
    produção isso é um arquivo vazio (o banco real é o Postgres, cuja env var vive DENTRO do
    container). Sem este guard, o sintoma era um traceback 'no such table: decisions'."""
    from database import schema as _sch
    pg = bool(getattr(_sch, 'USE_POSTGRES', False))
    print(f"banco: {'PostgreSQL (DATABASE_URL definido)' if pg else f'SQLite ({_sch.SQLITE_PATH})'}")
    conn = get_conn()
    try:
        conn.execute("SELECT 1 FROM tournaments LIMIT 1").fetchall()
    except Exception:
        print("\n  ✖ este banco não tem as tabelas da aplicação (está vazio).")
        if not pg:
            print("  DATABASE_URL não está definido — em produção o banco real é o PostgreSQL.")
            print("  Rode DENTRO do container, onde a env var existe:")
            print(f"      cd ~/app && docker compose exec web {cmd_exemplo}")
        sys.exit(1)
    print()
    return conn


def _v(row, key, idx):
    try:
        return row[key]
    except Exception:
        return row[idx]


def _cards_of(spec: str):
    """'Jd6d' → [('J','d'),('6','d')] · 'J6' → [('J',None),('6',None)]"""
    s = (spec or '').strip()
    out, i = [], 0
    while i < len(s):
        r = s[i].upper()
        if r not in RANKS:
            i += 1
            continue
        suit = None
        if i + 1 < len(s) and s[i + 1].lower() in 'cdhs':
            suit = s[i + 1].lower()
            i += 1
        out.append((r, suit))
        i += 1
    return out


def _hand_matches(hero_cards: str, want, suited_only: bool) -> bool:
    """hero_cards vem como 'Jd6d' (concatenado, ordem variável)."""
    if not hero_cards:
        return False
    got = _cards_of(hero_cards)
    if len(got) < 2 or len(want) < 2:
        return False
    if suited_only and got[0][1] and got[1][1] and got[0][1] != got[1][1]:
        return False
    pool = list(got)
    for wr, ws in want:
        hit = next((c for c in pool if c[0] == wr and (ws is None or c[1] == ws)), None)
        if not hit:
            return False
        pool.remove(hit)
    return True


def main():
    user   = _arg('--user')
    cards  = _arg('--cards')
    pos    = _arg('--pos')
    stack  = _arg('--stack')
    suited = '--suited' in sys.argv
    if not cards:
        print(__doc__)
        return

    want = _cards_of(cards)
    if len(want) < 2:
        print(f"cartas inválidas: {cards!r} (use ex.: Jd6d, J6, J6 --suited)")
        return
    stack_f = float(stack) if stack else None
    conn = open_db("python -m scripts.find_hand --user csm96 --cards Jd6d")

    # ── 1) tabela decisions ───────────────────────────────────────────────────
    sql = """SELECT t.id AS tdb, t.tournament_id, t.site, t.tournament_name, u.username,
                    d.hand_id, d.street, d.position, d.stack_bb, d.action_taken,
                    d.hero_cards, d.label, d.gto_label
               FROM decisions d
               JOIN tournaments t ON t.id = d.tournament_id
               JOIN users u       ON u.id = t.user_id
              WHERE d.hero_cards IS NOT NULL AND d.hero_cards <> ''"""
    params = []
    if user:
        sql += " AND (u.username = ? OR u.email = ?)"
        params += [user, user]
    if pos:
        sql += " AND d.position = ?"
        params.append(pos)
    sql += " ORDER BY t.imported_at DESC"

    achados = []
    for r in _rows(conn, sql, tuple(params)):
        if not _hand_matches(_v(r, 'hero_cards', 10), want, suited):
            continue
        sb = _v(r, 'stack_bb', 8)
        # stack_bb pode ser NULL — nesse caso NÃO exclui (senão o filtro esconde a mão procurada).
        if stack_f is not None and sb is not None and abs(float(sb) - stack_f) > 0.6:
            continue
        achados.append(r)

    print(f"== decisions: {len(achados)} ocorrência(s) ==")
    vistos = set()
    for r in achados:
        key = (_v(r, 'tdb', 0), _v(r, 'hand_id', 5))
        print(f"  {_v(r,'site',2):<11} torneio #{_v(r,'tournament_id',1):<13} "
              f"user={_v(r,'username',4):<10} mão={_v(r,'hand_id',5)}")
        print(f"     {_v(r,'street',6):<8} {str(_v(r,'position',7)):<4} "
              f"{_v(r,'hero_cards',10):<6} stack={_v(r,'stack_bb',8)}bb "
              f"ação={_v(r,'action_taken',9)} label={_v(r,'label',11)}/{_v(r,'gto_label',12)}")
        if key not in vistos:
            print(f"     → replay: /replay/{_v(r,'tdb',0)}/{_v(r,'hand_id',5)}")
            vistos.add(key)

    # ── 2) varredura do raw_text (pega o que não virou decisão) ───────────────
    tsql = """SELECT t.id, t.tournament_id, t.site, t.raw_text, u.username, t.hero
                FROM tournaments t JOIN users u ON u.id = t.user_id
               WHERE t.raw_text IS NOT NULL AND t.raw_text <> ''"""
    tparams = []
    if user:
        tsql += " AND (u.username = ? OR u.email = ?)"
        tparams += [user, user]

    print(f"\n== varredura do raw_text ==")
    total_raw = 0
    for t in _rows(conn, tsql, tuple(tparams)):
        raw = _v(t, 'raw_text', 3)
        try:
            hands = parse_hand_history(raw)
        except Exception as e:
            print(f"  ! torneio {_v(t,'tournament_id',1)}: falha ao parsear ({e})")
            continue
        for h in hands:
            hc = (h.hero_cards or '').replace(' ', '')
            if not _hand_matches(hc, want, suited):
                continue
            total_raw += 1
            already = (_v(t, 'id', 0), h.hand_id) in vistos
            print(f"  {_v(t,'site',2):<11} torneio #{_v(t,'tournament_id',1):<13} "
                  f"user={_v(t,'username',4):<10} mão={h.hand_id}  cartas={hc}"
                  f"{'   (já listada acima)' if already else ''}")
            print(f"     → replay: /replay/{_v(t,'id',0)}/{h.hand_id}   bb={h.bb}")
    if not total_raw:
        print("  nenhuma mão com essas cartas no raw_text")
        print("  (torneios importados antes do armazenamento do cru não têm raw_text)")


if __name__ == '__main__':
    main()
