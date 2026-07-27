"""
Auditoria da allowlist `_NO_ID_TABLES` — o gatilho que só dispara em produção.

O wrapper de conexão acrescenta ` RETURNING id` a todo INSERT quando o banco é Postgres (o
psycopg2 não popula `lastrowid`). Tabela de CHAVE NATURAL não tem coluna `id`, então precisa
estar na allowlist. Esquecer uma tabela ali quebra TODO INSERT nela — mas só em PG, com
`UndefinedColumn: column "id" does not exist`. Em SQLite passa liso.

Foi exatamente isso que manteve o painel de Uso do admin zerado desde sempre: `feature_usage`
ficou de fora, cada gravação falhava, e o `except: pass` do gravador engolia o erro. Ninguém
tinha como saber — nem log havia.

Este teste transforma "alguém precisa lembrar de atualizar a lista" em "o CI avisa".
"""
import sys, os, re, io, traceback, tempfile, sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema

TEST_DB = tempfile.mktemp(suffix='.db')


def _conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


schema.get_conn = _conn
schema.init_db()


def _allowlist() -> set:
    """Lê a allowlist do FONTE — ela é atributo de uma classe interna, sem import direto."""
    src = io.open(os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.py'),
                  encoding='utf-8').read()
    m = re.search(r'_NO_ID_TABLES = \{(.*?)\}', src, re.S)
    assert m, "_NO_ID_TABLES não encontrada em schema.py"
    return {x.strip().strip('\'"') for x in m.group(1).split(',') if x.strip()}


def _tabelas_sem_id() -> set:
    conn = _conn()
    try:
        tabs = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]
        return {t for t in tabs
                if 'id' not in {r[1] for r in conn.execute(f'PRAGMA table_info({t})').fetchall()}}
    finally:
        conn.close()


def test_toda_tabela_de_chave_natural_esta_na_allowlist():
    """A invariante. Se este teste cair, você criou uma tabela sem coluna `id` e o INSERT nela
    vai estourar em produção (e só lá)."""
    faltando = _tabelas_sem_id() - _allowlist()
    assert not faltando, (
        f"tabelas sem coluna `id` FORA de _NO_ID_TABLES: {sorted(faltando)}. "
        f"Todo INSERT nelas vai falhar em Postgres com 'column \"id\" does not exist'. "
        f"Acrescente-as à allowlist em database/schema.py.")
    print(f"OK  test_toda_tabela_de_chave_natural_esta_na_allowlist "
          f"({len(_tabelas_sem_id())} tabelas de chave natural)")


def test_feature_usage_na_allowlist():
    """Regressão nomeada: foi ela que zerou o painel de Uso do admin."""
    assert 'feature_usage' in _allowlist()
    print("OK  test_feature_usage_na_allowlist")


# Tabelas criadas SOB DEMANDA (CREATE TABLE IF NOT EXISTS no primeiro uso), não pelo init_db.
# Precisam continuar na allowlist — no dia em que forem criadas, o INSERT tem que funcionar.
_CRIADAS_SOB_DEMANDA = {
    'gto_preflop_capture',   # leaklab/preflop_autocapture.py, na primeira captura
}


def test_allowlist_nao_tem_tabela_inexistente():
    """Entrada morta na lista não quebra nada, mas indica tabela renomeada/removida — e a
    próxima pessoa vai confiar numa lista que descreve um schema que não existe mais.

    Exceção: tabelas criadas sob demanda não aparecem num schema recém-inicializado. Elas ficam
    listadas acima com o motivo, em vez de a asserção ser afrouxada em silêncio."""
    conn = _conn()
    try:
        existentes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()
    fantasmas = _allowlist() - existentes - _CRIADAS_SOB_DEMANDA
    assert not fantasmas, f"na allowlist mas sem tabela no schema: {sorted(fantasmas)}"
    print("OK  test_allowlist_nao_tem_tabela_inexistente")


def test_insert_em_tabela_de_chave_natural_funciona():
    """Prova funcional no dialeto que dá pra testar aqui. O caminho PG é coberto pela
    auditoria acima (não há Postgres no CI)."""
    conn = _conn()
    try:
        conn.execute("INSERT INTO feature_usage (day, feature_key, user_id, hits) "
                     "VALUES ('2026-01-01', 'x', 1, 1) "
                     "ON CONFLICT (day, feature_key, user_id) DO UPDATE SET hits = feature_usage.hits + 1")
        conn.execute("INSERT INTO feature_usage (day, feature_key, user_id, hits) "
                     "VALUES ('2026-01-01', 'x', 1, 1) "
                     "ON CONFLICT (day, feature_key, user_id) DO UPDATE SET hits = feature_usage.hits + 1")
        conn.commit()
        n = conn.execute("SELECT hits FROM feature_usage WHERE day='2026-01-01' AND feature_key='x'").fetchone()[0]
        assert n == 2, f"upsert não incrementou: hits={n}"
    finally:
        conn.close()
    print("OK  test_insert_em_tabela_de_chave_natural_funciona")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
