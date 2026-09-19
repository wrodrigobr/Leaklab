# -*- coding: utf-8 -*-
"""Harness de banco AGNOSTICO, num lugar so.

── Por que este arquivo existe (decisao do dono, 19/09) ─────────────────────────────────────

    "nao quero mais testar em sqlite, e sim no postgres local"

Existe Postgres 17 nativo na maquina do dev, e ele ja provou achar o que o SQLite esconde: um
defeito real de isolamento deu **20 de 20 no SQLite e 9 de 20 no Postgres** -- o mesmo 9/20 que o
host de producao devolveu.

O teste NAO impoe backend. Usa o Postgres quando `DATABASE_URL` esta no ambiente e um SQLite
descartavel quando nao. Assim o mesmo caso vale nos dois, que e o que a homologacao precisa.

── Duas pegadinhas que custaram rodada, e que este arquivo NAO consegue resolver sozinho ──────

1. **`USE_POSTGRES` e constante de modulo avaliada na IMPORTACAO.** A env precisa estar setada
   ANTES de o python subir, nunca no meio. Por isso quem escolhe o banco e a linha de comando, e
   nao o teste.
2. **`LEAKLAB_SECRET` vai junto.** `auth.py` trata a presenca de `DATABASE_URL` como producao e
   levanta `RuntimeError` sem um segredo de 32+ caracteres.

    DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/leaklab_suite" \\
    LEAKLAB_SECRET="dev_local_apenas_para_testes_0000000000000000" \\
      python tests/test_x.py

── Por que ele nao e uma copia do `banco_de_teste` que ja existe ─────────────────────────────

Aquele (em `test_arquivo_com_varios_torneios` e `test_historico_de_pratica`, COPIADO nos dois) e
acoplado ao caso de ponta a ponta daquele arquivo: UID fixo, tabelas especificas, token. Este e o
minimo que qualquer teste precisa -- escolher o banco, garantir o schema, e limpar o que sujou.
Unificar os dois e o passo 1 do AY-45.
"""
import contextlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def usa_postgres() -> bool:
    """O ambiente mandou Postgres? A pergunta e sobre a ENV, nao sobre o que ja foi importado."""
    return bool(os.environ.get('DATABASE_URL'))


def rotulo() -> str:
    return 'POSTGRES' if usa_postgres() else 'SQLite (sem DATABASE_URL)'


@contextlib.contextmanager
def banco_de_teste(limpar=(), user_id=None):
    """Prepara o banco do AMBIENTE e limpa o que o teste sujou.

    `limpar` = tabelas a esvaziar na saida (e na entrada, porque em Postgres o banco e o MESMO
    entre rodadas e o lixo da rodada anterior derruba a atual -- em SQLite cada teste ganha um
    arquivo novo e esse defeito fica invisivel).

    `user_id`, quando dado, restringe a limpeza a esse usuario: banco compartilhado nao pode ter
    teste apagando a linha de outro.
    """
    tmp = None
    anterior = os.environ.get('LEAKLAB_DB')
    if not usa_postgres():
        import importlib
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp.close()
        os.environ['LEAKLAB_DB'] = tmp.name
        from database import schema as _schema
        importlib.reload(_schema)
        _schema.init_db()
    else:
        from database import schema as _schema
        _schema.init_db()

    def limpa():
        if not limpar:
            return
        from database.schema import get_conn
        from database.repositories import _adapt
        for tab in limpar:
            # CONEXAO PROPRIA por tabela, e nao um try/except dentro de uma transacao unica: um
            # `rollback` no except desfaz a transacao INTEIRA e devolve o que as tabelas
            # anteriores ja tinham apagado. A casa tem a cicatriz.
            c = get_conn()
            try:
                if user_id is not None:
                    c.execute(_adapt("DELETE FROM %s WHERE user_id = ?" % tab), (user_id,))
                else:
                    c.execute(_adapt("DELETE FROM %s" % tab))
                c.commit()
            except Exception:
                pass                 # tabela ainda nao existe neste banco
            finally:
                c.close()

    limpa()
    try:
        yield
    finally:
        limpa()
        if tmp is not None:
            os.environ.pop('LEAKLAB_DB', None)
            if anterior is not None:
                os.environ['LEAKLAB_DB'] = anterior
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
