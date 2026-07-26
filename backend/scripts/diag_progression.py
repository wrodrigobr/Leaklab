"""Diagnóstico do Protocolo: por que os indicadores do gate não sobem? — read-only.

Responde, na ordem, as causas possíveis de "treinei mas o painel segue zerado":
  1. a tabela `progression_attempts` existe? (migração rodou no banco DESTE ambiente?)
  2. há tentativas gravadas? de que categorias?
  3. as categorias gravadas BATEM com as missões que o painel mostra?
     (é a causa mais traiçoeira: você treinou o leak A, mas o painel exibe o leak B)
  4. o backend está com o código do protocolo? (deploy do backend NÃO é automático — o
     frontend do Cloudflare sobe sozinho a cada push, o backend não)

Uso (dentro de backend/):
    python -m scripts.diag_progression --user CSM96
    cd ~/app && docker compose exec web python -m scripts.diag_progression --user CSM96
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn


def _arg(flag, default=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _v(row, key, idx):
    try:
        return row[key]
    except Exception:
        return row[idx]


def main():
    user = _arg('--user')
    if not user:
        print(__doc__)
        return

    from database import schema as _sch
    pg = bool(getattr(_sch, 'USE_POSTGRES', False))
    print(f"banco: {'PostgreSQL' if pg else f'SQLite ({_sch.SQLITE_PATH})'}\n")
    conn = get_conn()

    # 4. o código do protocolo está presente?
    try:
        from leaklab.progression import build_missions, mastery_status  # noqa
        print("[código] módulo progression: OK")
    except Exception as e:
        print(f"[código] ✖ progression AUSENTE ({e})")
        print("         → o backend deste ambiente está DESATUALIZADO.")
        print("         → cd ~/app && git pull && docker compose up -d --build web")
        return

    # 1. a tabela existe?
    try:
        conn.execute("SELECT 1 FROM progression_attempts LIMIT 1").fetchall()
        print("[tabela] progression_attempts: OK")
    except Exception:
        print("[tabela] ✖ progression_attempts NÃO EXISTE neste banco.")
        print("         → a migração roda no startup; reinicie o backend depois do git pull:")
        print("         → cd ~/app && docker compose up -d --build web")
        return

    # usuário
    term = f"%{user.lower().strip()}%"
    try:
        urow = conn.execute(
            "SELECT id, username FROM users WHERE LOWER(username) LIKE ? "
            "OR LOWER(COALESCE(email,'')) LIKE ?", (term, term)).fetchall()
    except Exception as e:
        print(f"✖ falha ao buscar usuário: {e}")
        return
    if not urow:
        print(f"✖ nenhum usuário casa com {user!r}")
        return
    uid, uname = _v(urow[0], 'id', 0), _v(urow[0], 'username', 1)
    print(f"[usuário] {uname} (id={uid})\n")

    # 2. tentativas gravadas
    rows = conn.execute(
        "SELECT category_key, COUNT(*) AS n, SUM(correct) AS ok FROM progression_attempts "
        "WHERE user_id = ? GROUP BY category_key ORDER BY n DESC", (uid,)).fetchall()
    total = sum(int(_v(r, 'n', 1)) for r in rows)
    print(f"[tentativas] {total} gravadas em {len(rows)} categoria(s)")
    for r in rows:
        print(f"   {str(_v(r,'category_key',0)):26} n={_v(r,'n',1)} acertos={_v(r,'ok',2)}")
    if not total:
        print("   ✖ NENHUMA tentativa gravada.")
        print("     Causas: (a) você treinou ANTES deste backend subir; (b) o grade está")
        print("     falhando (procure 'record_progression_attempt falhou' no log do container).")

    # 3. batem com as missões exibidas?
    print()
    try:
        missions = build_missions(uid, days=365)
    except Exception as e:
        print(f"✖ build_missions falhou: {e}")
        return
    gravadas = {str(_v(r, 'category_key', 0)) for r in rows}
    print("[missões exibidas no painel] — a janela do gate lê por ESTA chave:")
    for i, m in enumerate(missions, 1):
        marca = "✔ tem tentativas" if m['key'] in gravadas else "— sem tentativas"
        print(f"   {i}. {m['key']:26} {marca}   ({m['titulo']})")
    orfas = gravadas - {m['key'] for m in missions}
    if orfas:
        print("\n   ⚠ tentativas em categorias que NÃO são missão atual:")
        for o in sorted(orfas):
            print(f"       {o}")
        print("     → você treinou essas, mas o painel mostra outras. É o caso mais comum:")
        print("       treino via 'Treinar outra coisa' (adaptativo/fundamentos) grava na")
        print("       categoria treinada, não na missão em exibição.")
    conn.close()


if __name__ == '__main__':
    main()
