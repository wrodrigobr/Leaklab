"""Diagnóstico do bug "RAISE de 0bb" no Replayer.

Sintoma: o assento mostra a ação (ex.: RAISE) mas as fichas na frente aparecem como 0 BB e o
pote não recebe o valor. Read-only — não altera nada.

Três causas possíveis produzem o MESMO sintoma; este script desempata mostrando o texto CRU
da linha de ação e o que cada camada extrai dela:

  (A) amount None/0 no parser  → app.py pula o bloco inteiro (`and amt`) → fichas 0 E pote intacto
  (B) amount truncado (separador de MILHAR com ESPAÇO, ex.: "raises 1 500 to 3 000" → 1)
                               → fichas ~0,01 BB (arredonda p/ "0 BB") E pote quase intacto
  (C) pseat=None (nome da ação não casa com nenhum assento)
                               → fichas 0 MAS o pote AUMENTA (assinatura distinta de (A)/(B))

Uso (no host de produção, dentro de backend/):
    python -m scripts.diag_zero_bet --user csm96                 # varre os torneios do usuário
    python -m scripts.diag_zero_bet --user csm96 --hero-cards Jd6d
    python -m scripts.diag_zero_bet --tid <tournament_id>        # um torneio específico
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.parser import parse_hand_history, ACTION_LINE_RE, ACR_ACTION_RE, PG_ACTION_RE

# O mesmo regex que o /replay usa pra achar o total do "raises X to Y" (app.py).
REPLAY_TO_RE = re.compile(r'raises \d+ to (\d+)')


def _arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _rows(conn, sql, params=()):
    # O _AdaptedConn do schema.py já normaliza '?' → '%s' conforme o backend; um try/except
    # aqui só mascarava o erro real (ex.: "no such table" virava "near %: syntax error").
    return conn.execute(sql, params).fetchall()


def open_db(cmd_exemplo: str):
    """Abre a conexão dizendo em QUAL banco está falando e falha CEDO com mensagem clara quando
    o banco está vazio. Sem DATABASE_URL o schema.py cai no SQLite local — em produção o banco
    real é o PostgreSQL, cuja env var vive DENTRO do container."""
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


def _fetch_tournaments(conn, user, tid):
    if tid:
        return _rows(conn, "SELECT id, tournament_id, site, raw_text FROM tournaments "
                           "WHERE tournament_id = ?", (tid,))
    return _rows(conn, """
        SELECT t.id, t.tournament_id, t.site, t.raw_text
          FROM tournaments t JOIN users u ON u.id = t.user_id
         WHERE u.username = ? OR u.email = ?
         ORDER BY t.id DESC
    """, (user, user))


def _val(row, key, idx):
    try:
        return row[key]
    except Exception:
        return row[idx]


def main():
    user  = _arg('--user')
    tid   = _arg('--tid')
    cards = (_arg('--hero-cards') or '').lower()
    if not (user or tid):
        print(__doc__)
        return

    conn = open_db("python -m scripts.diag_zero_bet --user csm96")
    tours = _fetch_tournaments(conn, user, tid)
    if not tours:
        print(f"nenhum torneio encontrado (user={user} tid={tid})")
        return
    print(f"torneios encontrados: {len(tours)}\n")

    total_susp = 0
    for t in tours:
        t_pk   = _val(t, 'id', 0)
        t_id   = _val(t, 'tournament_id', 1)
        site   = _val(t, 'site', 2)
        raw    = _val(t, 'raw_text', 3)
        if not raw:
            print(f"[{t_id}] site={site} — SEM raw_text (import antigo), pulando")
            continue

        hands = parse_hand_history(raw)
        print(f"[{t_id}] site={site} · {len(hands)} mãos · bb da 1ª mão={getattr(hands[0], 'bb', None) if hands else '?'}")

        for h in hands:
            if cards and cards not in (h.hero_cards or '').lower().replace(' ', ''):
                continue
            seat_players = set(h.players or [])
            for a in (h.actions or []):
                if a.action not in ('raises', 'bets', 'calls', 'all-in'):
                    continue
                amt = a.amount
                raw_line = (a.raw or '').strip()
                # Reproduz o que o /replay faria
                m_to = REPLAY_TO_RE.search(raw_line)
                replay_total = int(m_to.group(1)) if m_to else (amt or 0)
                bb = h.bb or 0
                in_bb = (replay_total / bb) if bb else None

                suspeito = (
                    not amt                                        # (A)
                    or (bb and (replay_total / bb) < 0.05)         # (B) fichas somem no display
                    or (a.player not in seat_players)              # (C)
                )
                if not suspeito:
                    continue
                total_susp += 1
                causa = ('(A) amount vazio' if not amt else
                         '(C) player fora dos assentos' if a.player not in seat_players else
                         '(B) amount truncado/minúsculo')
                print(f"\n  ⚠ mão {h.hand_id} · {a.street} · {a.player} · {a.action}  → {causa}")
                print(f"    raw   : {raw_line!r}")
                print(f"    parser: amount={amt!r}   (ACTION_LINE_RE)")
                print(f"    replay: total_placed={replay_total}  bb={bb}  →  {in_bb if in_bb is None else round(in_bb,3)} BB"
                      f"{'   ← exibe 0 BB' if in_bb is not None and round(in_bb,1) == 0 else ''}")
                print(f"    m_to  : {'casou' if m_to else 'NÃO casou (regex raises \\d+ to \\d+)'}")
                # o que cada dialeto extrairia desta linha (mostra o formato do número)
                for nome, rx in (('PS/GG/Coin', ACTION_LINE_RE), ('ACR', ACR_ACTION_RE), ('PG', PG_ACTION_RE)):
                    m = rx.match(raw_line)
                    if m:
                        g = m.groupdict()
                        print(f"      {nome:11}: amount={g.get('amount')!r} toamt={g.get('toamt')!r}")

    print(f"\n{'='*60}\nlinhas suspeitas: {total_susp}")
    if not total_susp:
        print("nenhuma anomalia — o bug pode estar em outra mão/torneio (tente sem --hero-cards)")


if __name__ == '__main__':
    main()
