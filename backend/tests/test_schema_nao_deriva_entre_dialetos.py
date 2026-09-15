# -*- coding: utf-8 -*-
"""O mesmo `init_db()` tem de produzir o mesmo SCHEMA nas duas gramaticas.

-- O defeito (auditoria DIA-8, 15/09) ------------------------------------------------------

Medido pelo `repro/DIA_8.py`: `tabelas com colunas divergentes=0; com FK divergente=4; com
UNIQUE divergente=1`. Quatro tabelas tinham `REFERENCES ... ON DELETE CASCADE` so no Postgres
(`evolution_reports`, `range_card_srs`, `tournament_finishes`, `engagement_emails`) e
`users.whatsapp_phone` era UNIQUE so la.

Efeito ja visto: `test_mesa_final` gravava colocacao para torneio inexistente, passava em SQLite
e caia no Postgres com `ForeignKeyViolation`. O resto e o risco de sempre desta classe: cascata
ao apagar usuario e colisao de telefone sao comportamentos que a suite nunca exercitava, porque
no dialeto dela eles nao existiam.

-- O que este arquivo defende --------------------------------------------------------------

1. A DDL do SQLite declara as quatro FKs com CASCADE e os dois indices unicos de `users`. Roda
   nas duas gramaticas, porque sobe um SQLite temporario num subprocesso.
2. O COMPORTAMENTO, no dialeto em que a suite estiver rodando: a FK recusa orfao, a cascata
   apaga junto, o handle colide sem olhar maiuscula e o telefone repetido e recusado.
3. Sob Postgres, a comparacao estrutural inteira (o `DIA_8.py` virado teste).

`leaderboard_handle` fica DECLARADO como equivalencia, e nao como igualdade de texto: a regra e
a mesma (unico, sem olhar maiuscula, so para quem definiu) e cada dialeto a escreve do seu jeito
(`COLLATE NOCASE` no SQLite, `LOWER(...)` no Postgres). Quem garante que sao a mesma coisa e o
teste de COMPORTAMENTO acima, nao a string.
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

RAIZ = os.path.join(os.path.dirname(__file__), '..')

#: As FKs que as duas gramaticas tem de declarar, com a MESMA regra de apagamento.
FKS_ESPERADAS = {
    'evolution_reports':   ('user_id', 'users', 'CASCADE'),
    'range_card_srs':      ('user_id', 'users', 'CASCADE'),
    'tournament_finishes': ('tournament_id', 'tournaments', 'CASCADE'),
    'engagement_emails':   ('user_id', 'users', 'CASCADE'),
}

#: UNIQUE cuja forma DIFERE de proposito entre os dialetos, porque cada um escreve a mesma regra
#: do seu jeito. O que prova a equivalencia e o teste de comportamento, nao esta lista.
EQUIVALENCIAS_DECLARADAS = {
    ('users', 'leaderboard_handle'):
        'unico sem olhar maiuscula e so para quem definiu: COLLATE NOCASE no SQLite, '
        'LOWER(...) parcial no Postgres',
}

_CODIGO_SQLITE = r'''
import json, os, sqlite3, sys
sys.path.insert(0, '.')
from database import schema
schema.init_db()
c = sqlite3.connect(os.environ['LEAKLAB_DB'])
out = {}
for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
    cols = {r[1] for r in c.execute('PRAGMA table_info(%s)' % t)}
    fks = {(r[3], r[2], (r[6] or '').upper()) for r in c.execute('PRAGMA foreign_key_list(%s)' % t)}
    uniq = set()
    for r in c.execute('PRAGMA index_list(%s)' % t):
        if r[2] and r[3] != 'pk':
            uniq.add(tuple(x[2] for x in c.execute('PRAGMA index_info(%s)' % r[1])))
    out[t] = {'cols': sorted(cols), 'fks': sorted(fks), 'uniq': sorted(uniq)}
print(json.dumps(out))
'''


def schema_do_sqlite():
    """O schema que `init_db()` cria num SQLite NOVO, num subprocesso sem `DATABASE_URL`.

    Subprocesso porque `USE_POSTGRES` e constante de modulo avaliada na importacao: dentro
    deste processo, sob `DATABASE_URL`, nao ha como pedir o outro dialeto."""
    tmp = tempfile.mktemp(suffix='.db')
    env = {k: v for k, v in os.environ.items() if k != 'DATABASE_URL'}
    env.update(LEAKLAB_DB=tmp, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run([sys.executable, '-c', _CODIGO_SQLITE], env=env, cwd=RAIZ,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    linhas = [l for l in r.stdout.splitlines() if l.startswith('{')]
    assert linhas, 'o subprocesso do SQLite nao respondeu: %s' % (r.stderr or r.stdout)[-400:]
    try:
        os.unlink(tmp)
    except OSError:
        pass
    return json.loads(linhas[-1])


def test_a_ddl_do_sqlite_declara_as_fks_com_cascade():
    lite = schema_do_sqlite()
    faltando = []
    for tabela, esperada in FKS_ESPERADAS.items():
        assert tabela in lite, 'tabela %s nao foi criada no SQLite' % tabela
        fks = {tuple(x) for x in lite[tabela]['fks']}
        if esperada not in fks:
            faltando.append((tabela, esperada, sorted(fks)))
    assert not faltando, 'FK que so existe no Postgres: %s' % faltando


def test_a_ddl_do_sqlite_declara_os_unicos_de_users():
    lite = schema_do_sqlite()
    uniq = {tuple(x) for x in lite['users']['uniq']}
    assert ('whatsapp_phone',) in uniq, 'whatsapp_phone sem UNIQUE no SQLite: %s' % sorted(uniq)
    assert ('leaderboard_handle',) in uniq, sorted(uniq)


# -- O COMPORTAMENTO, no dialeto em que esta suite estiver rodando ----------------------------

def _banco():
    """Conexao numa transacao aberta. Em SQLite, um arquivo NOVO: bancos de dev antigos foram
    criados antes destas FKs e nao as tem (SQLite nao aplica DDL nova a tabela existente)."""
    import database.schema as sch
    if not sch.USE_POSTGRES:
        sch.SQLITE_PATH = tempfile.mktemp(suffix='.db')
    sch.init_db()
    return sch.get_conn()


def _erro_de_banco():
    import database.schema as sch
    if sch.USE_POSTGRES:
        import psycopg2
        return psycopg2.Error
    import sqlite3
    return sqlite3.Error


UID, TID = 9805, 9805


def _esqueleto(c):
    from database.repositories import _adapt
    c.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (?,?,?,?)"),
              (UID, 'dia8', 'dia8@teste.local', 'x'))
    c.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, hero) "
                     "VALUES (?,?,?,?)"), (TID, UID, 'T-DIA8', 'Hero'))


def test_a_fk_recusa_colocacao_de_torneio_inexistente():
    from database.repositories import _adapt
    c = _banco()
    try:
        _esqueleto(c)
        try:
            c.execute(_adapt("INSERT INTO tournament_finishes (tournament_id, player, place) "
                             "VALUES (?,?,?)"), (987654321, 'ninguem', 1))
            recusou = False
        except _erro_de_banco():
            recusou = True
        assert recusou, 'o banco aceitou colocacao de torneio inexistente'
    finally:
        c.rollback()
        c.close()


def test_apagar_o_usuario_leva_junto_o_que_e_dele():
    from database.repositories import _adapt
    c = _banco()
    try:
        _esqueleto(c)
        c.execute(_adapt("INSERT INTO evolution_reports (user_id, motivo, snapshot) "
                         "VALUES (?,?,?)"), (UID, 'teste', '{}'))
        c.execute(_adapt("INSERT INTO engagement_emails (user_id, tipo) VALUES (?,?)"),
                  (UID, 'teste'))
        antes = dict(c.execute(_adapt(
            "SELECT count(*) AS n FROM evolution_reports WHERE user_id=?"), (UID,)).fetchone())
        assert antes['n'] == 1, antes                      # o teste mede algo
        c.execute(_adapt("DELETE FROM tournaments WHERE user_id=?"), (UID,))
        c.execute(_adapt("DELETE FROM users WHERE id=?"), (UID,))
        for tabela in ('evolution_reports', 'engagement_emails'):
            r = dict(c.execute(_adapt(
                "SELECT count(*) AS n FROM %s WHERE user_id=?" % tabela), (UID,)).fetchone())
            assert r['n'] == 0, '%s sobreviveu ao apagamento do usuario: %s' % (tabela, r)
    finally:
        c.rollback()
        c.close()


def test_o_handle_do_leaderboard_colide_sem_olhar_maiuscula():
    from database.repositories import _adapt
    c = _banco()
    try:
        _esqueleto(c)
        c.execute(_adapt("UPDATE users SET leaderboard_handle=? WHERE id=?"), ('Rullian', UID))
        c.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                         "VALUES (?,?,?,?)"), (UID + 1, 'dia8b', 'dia8b@teste.local', 'x'))
        try:
            c.execute(_adapt("UPDATE users SET leaderboard_handle=? WHERE id=?"),
                      ('rullian', UID + 1))
            recusou = False
        except _erro_de_banco():
            recusou = True
        assert recusou, 'dois handles iguais com maiuscula diferente convivem'
    finally:
        c.rollback()
        c.close()


def test_o_telefone_repetido_e_recusado_pelo_banco():
    from database.repositories import _adapt
    c = _banco()
    try:
        _esqueleto(c)
        c.execute(_adapt("UPDATE users SET whatsapp_phone=? WHERE id=?"), ('+5511999990000', UID))
        c.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                         "VALUES (?,?,?,?)"), (UID + 1, 'dia8c', 'dia8c@teste.local', 'x'))
        try:
            c.execute(_adapt("UPDATE users SET whatsapp_phone=? WHERE id=?"),
                      ('+5511999990000', UID + 1))
            recusou = False
        except _erro_de_banco():
            recusou = True
        assert recusou, 'o mesmo telefone em duas contas passou pelo banco'
    finally:
        c.rollback()
        c.close()


# -- A comparacao estrutural inteira (so faz sentido com os dois bancos na mao) ----------------

def _uniques_do_postgres(conn, tabela):
    uq = set()
    for r in conn.execute("""
            SELECT string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) AS cols
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
            WHERE tc.table_schema='public' AND tc.table_name=%s AND tc.constraint_type='UNIQUE'
            GROUP BY tc.constraint_name""", (tabela,)).fetchall():
        uq.add(tuple(dict(r)['cols'].split(',')))
    return uq


def test_as_fks_esperadas_existem_TAMBEM_no_postgres():
    """A deriva tem dois lados. Sob SQLite este caso diz o que faltou medir, e nao passa calado
    como se tivesse medido."""
    from database.schema import USE_POSTGRES, get_conn
    if not USE_POSTGRES:
        print('    (roda contra Postgres; em SQLite so a DDL acima e conferida)')
        return
    conn = get_conn()
    try:
        faltando = []
        for tabela, (coluna, ref, regra) in FKS_ESPERADAS.items():
            achadas = [dict(r) for r in conn.execute("""
                SELECT kcu.column_name AS col, ccu.table_name AS ref, rc.delete_rule AS regra
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                JOIN information_schema.referential_constraints rc
                  ON rc.constraint_name = tc.constraint_name
                WHERE tc.table_schema='public' AND tc.table_name=%s
                  AND tc.constraint_type='FOREIGN KEY'""", (tabela,)).fetchall()]
            if not any(a['col'] == coluna and a['ref'] == ref
                       and (a['regra'] or '').upper() == regra for a in achadas):
                faltando.append((tabela, coluna, ref, regra, achadas))
        assert not faltando, 'FK esperada ausente no Postgres: %s' % faltando
        assert ('whatsapp_phone',) in _uniques_do_postgres(conn, 'users')
    finally:
        conn.close()


def test_a_equivalencia_declarada_e_a_unica_diferenca_de_unique():
    """Toda diferenca de UNIQUE entre os dialetos precisa estar em EQUIVALENCIAS_DECLARADAS."""
    from database.schema import USE_POSTGRES, get_conn
    if not USE_POSTGRES:
        print('    (roda contra Postgres)')
        return
    lite = schema_do_sqlite()
    conn = get_conn()
    try:
        naodeclaradas = []
        for tabela, dados in lite.items():
            pg = _uniques_do_postgres(conn, tabela)
            so_lite = {u for u in {tuple(x) for x in dados['uniq']} if u not in pg}
            for u in so_lite:
                if (tabela, u[0] if len(u) == 1 else u) not in EQUIVALENCIAS_DECLARADAS:
                    naodeclaradas.append((tabela, u))
        assert not naodeclaradas, (
            'UNIQUE que existe so no SQLite e nao esta declarado como equivalencia: %s'
            % naodeclaradas)
    finally:
        conn.close()


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK      %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
