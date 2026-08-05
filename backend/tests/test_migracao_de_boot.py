# -*- coding: utf-8 -*-
"""
Tres `ALTER` mataram TODA a migracao de boot em producao, por meses.

── O defeito ──────────────────────────────────────────────────────────────────────────────────────

    try:
        conn.execute("ALTER TABLE drill_sessions ADD COLUMN next_drill_at TIMESTAMP")
    except Exception: pass

Sem `IF NOT EXISTS`, e com DDL cru dentro de `except: pass`. Na PRIMEIRA vez rodou e criou a
coluna. Da segunda em diante levanta `DuplicateColumn` — e no Postgres **um erro aborta a
transacao inteira**. O `except` engolia, e todo statement seguinte virava
`InFailedSqlTransaction` em silencio. Inclusive o `conn.commit()` do fim: os `ALTER` que ja
tinham dado certo iam junto no rollback.

Resultado: **nenhuma coluna nova aplicava em producao desde entao**, e o deploy parecia OK.

── Como foi encontrado ────────────────────────────────────────────────────────────────────────────

Instrumentando o boot em producao (2026-08-05). Nao saiu de leitura de codigo — duas hipoteses
minhas cairam antes (o cascade a partir do `_init_postgres`, e o `init_db` nao ser chamado sob
gunicorn; as duas foram REFUTADAS por teste). O log do boot instrumentado:

    [pid 8] OK    ALTER TABLE decisions ADD COLUMN IF NOT EXISTS facing_to_call_bb REAL
    [pid 8] BLOCO#13 -> DuplicateColumn: column "next_drill_at" ... already exists
    [pid 8] BLOCO#14+ -> InFailedSqlTransaction  (cascata ate o fim)

Repare que o ALTER de `decisions` **executa com sucesso** e mesmo assim nao sobrevive: o abort
vem depois, e o commit nao salva nada.

── O que estes testes travam ──────────────────────────────────────────────────────────────────────

`_pg_exec_isolated` existe exatamente para isolar cada DDL num SAVEPOINT. A regra e: no ramo
Postgres do `_run_migrations`, **nenhum `conn.execute` cru de DDL**, e todo `ADD COLUMN` com
`IF NOT EXISTS`.
"""
import os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

_CAMINHO = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.py')


def _ramo_postgres() -> str:
    """So o trecho PG do `_run_migrations` — o ramo SQLite tem outras regras (la um erro nao
    aborta a transacao, e o codigo checa `PRAGMA table_info` antes)."""
    s = open(_CAMINHO, encoding='utf-8').read()
    ini = s.index('def _run_migrations(conn):')
    fim = s.index('\n    else:', ini)
    return s[ini:fim]


def test_nenhum_ADD_COLUMN_sem_IF_NOT_EXISTS():
    """`DuplicateColumn` aborta a transacao no PG. Sem `IF NOT EXISTS`, a migracao se mata
    sozinha no SEGUNDO boot."""
    pg = _ramo_postgres()
    alters = re.findall(r'ALTER TABLE \w+ ADD COLUMN (?!IF NOT EXISTS)[^"\']+', pg)
    assert not alters, (
        "ADD COLUMN sem IF NOT EXISTS no ramo Postgres — mata a migracao no 2o boot:\n  "
        + "\n  ".join(a[:90] for a in alters))


def test_nenhum_DDL_cru_dentro_de_except_silencioso():
    """DDL cru em `try/except: pass` deixa a transacao ABORTADA com o erro escondido. Todo DDL
    do ramo PG tem que passar por `_pg_exec_isolated`, que isola em SAVEPOINT."""
    pg = _ramo_postgres()
    crus = re.findall(r'conn\.execute\(\s*["\'](ALTER TABLE [^"\']+)["\']', pg)
    assert not crus, (
        "DDL executado CRU no ramo Postgres (use _pg_exec_isolated):\n  "
        + "\n  ".join(c[:90] for c in crus))


def test_o_isolador_existe_e_usa_SAVEPOINT():
    """A rede de seguranca em si: sem SAVEPOINT, isolar nao isola."""
    s = open(_CAMINHO, encoding='utf-8').read()
    assert 'def _pg_exec_isolated' in s
    corpo = s[s.index('def _pg_exec_isolated'):]
    corpo = corpo[:corpo.index('\ndef ')]
    assert 'SAVEPOINT' in corpo and 'ROLLBACK TO SAVEPOINT' in corpo, corpo[:200]


def test_as_colunas_do_drill_sobreviveriam_a_um_segundo_boot():
    """Regressao do caso concreto: as tres colunas de `drill_sessions` que causaram tudo."""
    pg = _ramo_postgres()
    for col in ('next_drill_at', 'srs_interval_days', 'correct'):
        trechos = [l for l in pg.splitlines()
                   if f'drill_sessions ADD COLUMN' in l and col in l]
        assert trechos, f'a migracao de {col} sumiu do ramo PG'
        for t in trechos:
            assert 'IF NOT EXISTS' in t, f'{col} voltou a ser nao-idempotente: {t.strip()[:100]}'


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
        except AssertionError as e:
            falhas += 1
            print(f'FALHOU  {t.__name__}: {e}')
        except Exception as e:
            falhas += 1
            print(f'ERRO    {t.__name__}: {type(e).__name__}: {e}')
    print(f'\nTotal: {len(testes)} | Passed: {len(testes) - falhas} | Failed: {falhas}')
    sys.exit(1 if falhas else 0)
