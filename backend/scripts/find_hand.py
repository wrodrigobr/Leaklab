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
        # Casa SEM depender de maiúscula/exatidão: 'CSM96', 'csm96 ' ou parte do email acham.
        # (a versão anterior usava '=' e devolvia vazio em silêncio quando o login diferia)
        sql += " AND (LOWER(u.username) LIKE ? OR LOWER(COALESCE(u.email,'')) LIKE ?)"
        term = f"%{user.lower().strip()}%"
        params += [term, term]
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
        tsql += " AND (LOWER(u.username) LIKE ? OR LOWER(COALESCE(u.email,'')) LIKE ?)"
        _term = f"%{user.lower().strip()}%"
        tparams += [_term, _term]

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

    # ── 3) nada encontrado: mostra O QUE EXISTE (senão o usuário fica no escuro) ──
    if not achados and not total_raw:
        print(f"\n{'='*62}\nNADA ENCONTRADO — inventário do que existe para orientar a busca:")

        if user:
            us = _rows(conn, """SELECT u.id, u.username, u.email,
                                       (SELECT COUNT(*) FROM tournaments t WHERE t.user_id = u.id) AS n
                                  FROM users u
                                 WHERE LOWER(u.username) LIKE ? OR LOWER(COALESCE(u.email,'')) LIKE ?
                              """, (f"%{user.lower().strip()}%", f"%{user.lower().strip()}%"))
            if not us:
                print(f"\n  ✖ NENHUM usuário casa com {user!r}. Usuários com mais torneios:")
                for r in _rows(conn, """SELECT u.username, u.email, COUNT(t.id) AS n
                                          FROM users u JOIN tournaments t ON t.user_id = u.id
                                      GROUP BY u.id, u.username, u.email
                                      ORDER BY n DESC LIMIT 10"""):
                    print(f"      {str(_v(r,'username',0)):<18} {str(_v(r,'email',1)):<28} {_v(r,'n',2)} torneios")
                print("\n  → repita com o login/e-mail correto (a busca aceita parte do nome).")
                return
            for r in us:
                print(f"\n  usuário: {_v(r,'username',1)} ({_v(r,'email',2)}) — {_v(r,'n',3)} torneio(s)")

        # torneios do usuário + se dá pra buscar neles
        tsql2 = """SELECT t.id, t.tournament_id, t.site, t.hands_count, u.username,
                          CASE WHEN t.raw_text IS NULL OR t.raw_text='' THEN 0 ELSE 1 END AS has_raw,
                          (SELECT COUNT(*) FROM decisions d
                            WHERE d.tournament_id = t.id AND d.hero_cards IS NOT NULL AND d.hero_cards <> '') AS n_cards
                     FROM tournaments t JOIN users u ON u.id = t.user_id"""
        p2 = []
        if user:
            tsql2 += " WHERE (LOWER(u.username) LIKE ? OR LOWER(COALESCE(u.email,'')) LIKE ?)"
            p2 = [f"%{user.lower().strip()}%"] * 2
        tsql2 += " ORDER BY t.imported_at DESC LIMIT 30"
        ts = _rows(conn, tsql2, tuple(p2))
        if not ts:
            print("  ✖ este usuário não tem nenhum torneio importado.")
            return
        print(f"\n  torneios ({len(ts)} mais recentes) — 'raw' e 'cartas' dizem se dá pra achar a mão:")
        for r in ts:
            has_raw = _v(r, 'has_raw', 5)
            n_cards = _v(r, 'n_cards', 6)
            flag = "" if (has_raw or n_cards) else "   ← invisível à busca (sem raw e sem cartas)"
            print(f"      #{str(_v(r,'tournament_id',1)):<14} {str(_v(r,'site',2)):<11} "
                  f"mãos={str(_v(r,'hands_count',3)):<5} raw={'sim' if has_raw else 'NÃO':<3} "
                  f"decisões-com-cartas={n_cards}{flag}")

        # que cartas ESTE usuário realmente tem (confere se o par procurado existe)
        csql = """SELECT d.hero_cards, COUNT(*) AS n FROM decisions d
                    JOIN tournaments t ON t.id = d.tournament_id
                    JOIN users u ON u.id = t.user_id
                   WHERE d.hero_cards IS NOT NULL AND d.hero_cards <> ''"""
        p3 = []
        if user:
            csql += " AND (LOWER(u.username) LIKE ? OR LOWER(COALESCE(u.email,'')) LIKE ?)"
            p3 = [f"%{user.lower().strip()}%"] * 2
        csql += " GROUP BY d.hero_cards ORDER BY n DESC LIMIT 12"
        cs = _rows(conn, csql, tuple(p3))
        if cs:
            print("\n  amostra de cartas gravadas (formato esperado 'Jd6d'):")
            print("      " + ", ".join(f"{_v(r,'hero_cards',0)}" for r in cs))
        else:
            print("\n  ⚠ NENHUMA decisão deste usuário tem hero_cards preenchido —")
            print("    a busca pela camada 1 é impossível; só o raw_text acha (veja a coluna 'raw').")


if __name__ == '__main__':
    main()
