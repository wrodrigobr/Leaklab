"""test_pool_de_conexoes.py — o pool não pode inventar modo de falha que hoje não existe.

**Por que com driver FALSO:** o pool só roda em Postgres, e dev é SQLite. Um teste que exercitasse
só o caminho normal daria verde sobre código que ninguém executou — é literalmente a armadilha
"funciona no dev, não em prod" que este projeto já pagou várias vezes. O `_ConexaoFalsa` aqui imita
o contrato do psycopg2 que o pool usa (`closed`, `get_transaction_status`, `cursor`, `rollback`) e
o `_PoolFalso` imita as regras do `ThreadedConnectionPool` que o desenho depende — inclusive o
rollback no `putconn`, que é o item 2 do comentário no topo do `schema.py`.

O que aqui se trava:

1. **Reuso** — é o ponto inteiro. Duas idas seguidas ao banco discam UMA vez.
2. **Aninhamento** — medido em produção: `get_xp_status` segura uma conexão e chama
   `get_achievements`, que abre outra. As duas precisam ser conexões DIFERENTES.
3. **Liberação dupla** — `close()` e `__exit__` levam ao mesmo lugar. Voltar duas vezes para a
   fila livre entregaria a mesma conexão a dois donos: corrupção, e silenciosa.
4. **Transação suja não vaza** — `__exit__` fecha sem commitar; o próximo dono não pode herdar.
5. **Conexão morta e pool exausto** — degradam para o comportamento de hoje, nunca para erro.
6. **Fork** — pool herdado do pai é o mesmo socket em dois processos.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import database.schema as S


# ── dublês do driver ──────────────────────────────────────────────────────────

class _CursorFalso:
    def __init__(self, conexao):
        self._c = conexao

    def execute(self, sql, params=None):
        if self._c.morta:
            raise RuntimeError('server closed the connection unexpectedly')
        self._c.consultas.append(sql)
        self._c.em_transacao = True
        return self

    def fetchone(self):
        return {'?column?': 1}

    def fetchall(self):
        return []

    def close(self):
        pass


class _ConexaoFalsa:
    """`morta=True` imita o pior caso real: o servidor derrubou, mas o cliente não sabe —
    `closed` segue 0 e o status segue IDLE. Só a consulta revela."""

    def __init__(self, n):
        self.n = n
        self.closed = 0
        self.morta = False
        self.em_transacao = False
        self.rollbacks = 0
        self.consultas = []
        self.autocommit = False

    def cursor(self, *a, **kw):
        return _CursorFalso(self)

    def get_transaction_status(self):
        import psycopg2.extensions as _ext
        return (_ext.TRANSACTION_STATUS_INTRANS if self.em_transacao
                else _ext.TRANSACTION_STATUS_IDLE)

    def rollback(self):
        self.rollbacks += 1
        self.em_transacao = False

    def commit(self):
        self.em_transacao = False

    def close(self):
        self.closed = 1


class _PoolFalso:
    """Imita as regras do ThreadedConnectionPool que o desenho usa — inclusive o rollback no
    putconn de conexão com transação aberta."""

    def __init__(self, maxconn):
        self.maxconn = maxconn
        self.livres = []
        self.emprestadas = 0
        self.criadas = 0
        self.fechadas = 0

    def getconn(self):
        if self.livres:
            c = self.livres.pop()
        else:
            if self.emprestadas >= self.maxconn:
                raise Exception('connection pool exhausted')
            self.criadas += 1
            c = _ConexaoFalsa(self.criadas)
        self.emprestadas += 1
        return c

    def putconn(self, conn, close=False):
        self.emprestadas -= 1
        if close or conn.closed:
            self.fechadas += 1
            conn.close()
            return
        if conn.em_transacao:          # a regra do psycopg2 de que o desenho depende
            conn.rollback()
        self.livres.append(conn)


class _Cenario:
    """Liga o caminho Postgres com os dublês e restaura tudo depois."""

    def __init__(self, maxconn=8, direto_falha=False):
        self.pool = _PoolFalso(maxconn)
        self.diretas = 0
        self._maxconn = maxconn
        self._direto_falha = direto_falha

    def __enter__(self):
        self._orig = (S.USE_POSTGRES, S._pool_do_processo, S._conecta_pg,
                      S._POOL_LIGADO, S._POOL_MAX, S._pool, S._pool_pid)
        S.USE_POSTGRES = True
        S._POOL_LIGADO = True
        S._POOL_MAX = self._maxconn
        S._pool = None
        S._pool_pid = None
        S._pool_ocioso_desde.clear()
        S._pool_do_processo = lambda: self.pool

        def direto():
            if self._direto_falha:
                raise RuntimeError('sem banco')
            self.diretas += 1
            return _ConexaoFalsa(-1)

        S._conecta_pg = direto
        return self

    def __exit__(self, *a):
        (S.USE_POSTGRES, S._pool_do_processo, S._conecta_pg,
         S._POOL_LIGADO, S._POOL_MAX, S._pool, S._pool_pid) = self._orig
        S._pool_ocioso_desde.clear()
        return False


# ── testes ────────────────────────────────────────────────────────────────────

def test_reusa_a_mesma_conexao_em_idas_seguidas():
    """O ponto inteiro. Antes: cada ida discava de novo, ~72ms medidos em produção."""
    with _Cenario() as cen:
        c1 = S.get_conn(); n1 = c1._conn.n; c1.close()
        c2 = S.get_conn(); n2 = c2._conn.n; c2.close()
        c3 = S.get_conn(); n3 = c3._conn.n; c3.close()
    assert n1 == n2 == n3, f'discou de novo a cada ida: {n1}, {n2}, {n3}'
    assert cen.pool.criadas == 1, f'criou {cen.pool.criadas} conexoes para 3 idas seguidas'
    assert cen.diretas == 0, 'caiu no fallback sem motivo'
    print('OK  test_reusa_a_mesma_conexao_em_idas_seguidas')


def test_aninhamento_recebe_conexoes_DIFERENTES():
    """Medido em produção: `get_xp_status` segura uma e chama `get_achievements`, que abre outra.
    Entregar a mesma seria a de dentro liberando a conexão embaixo da de fora."""
    with _Cenario() as cen:
        fora = S.get_conn()
        dentro = S.get_conn()
        assert fora._conn is not dentro._conn, 'aninhamento recebeu a MESMA conexao'
        dentro.close()
        # a de fora continua viva e usável depois da de dentro voltar
        assert fora._conn.closed == 0, 'a de dentro fechou a conexao da de fora'
        fora.close()
    assert cen.pool.criadas == 2, cen.pool.criadas
    print('OK  test_aninhamento_recebe_conexoes_DIFERENTES')


def test_liberacao_dupla_nao_devolve_duas_vezes():
    """`with get_conn() as c:` com um `c.close()` dentro dispara close E __exit__."""
    with _Cenario() as cen:
        with S.get_conn() as c:
            c.close()                      # o caminho que devolve duas vezes sem a trava
        assert len(cen.pool.livres) == 1, f'a fila livre ficou com {len(cen.pool.livres)} entradas'
        # e a prova de que importa: dois donos não podem receber a mesma conexão
        a = S.get_conn(); b = S.get_conn()
        assert a._conn is not b._conn, 'dois donos receberam a MESMA conexao'
        a.close(); b.close()
    print('OK  test_liberacao_dupla_nao_devolve_duas_vezes')


def test_transacao_aberta_nao_vaza_para_o_proximo():
    """`__exit__` fecha SEM commitar. O próximo dono não pode herdar a transação suja."""
    with _Cenario() as cen:
        with S.get_conn() as c:
            c.execute('INSERT INTO users (username) VALUES (?)', ('x',))
            assert c._conn.em_transacao, 'o dublê não registrou a transação — o teste mede nada'
        suja = cen.pool.livres[-1]
        assert suja.rollbacks == 1, 'a transação aberta voltou ao pool SEM rollback'
        assert not suja.em_transacao, 'o próximo dono herdaria a transação'
    print('OK  test_transacao_aberta_nao_vaza_para_o_proximo')


def test_conexao_morta_e_descartada_e_o_chamador_recebe_uma_BOA():
    """O pior caso real: o servidor derrubou e o cliente não sabe. `closed` segue 0, o status
    segue IDLE, e só a consulta revela. Sem isto, o pool entregaria a conexão morta."""
    with _Cenario() as cen:
        c = S.get_conn(); primeira = c._conn; c.close()
        primeira.morta = True
        S._pool_ocioso_desde[primeira] = 0.0     # ociosa "há muito" → força o ping
        c2 = S.get_conn()
        assert c2._conn is not primeira, 'entregou a conexao MORTA'
        assert c2._conn.morta is False
        c2.close()
    assert cen.pool.fechadas >= 1, 'a conexao morta nao foi descartada'
    print('OK  test_conexao_morta_e_descartada_e_o_chamador_recebe_uma_BOA')


def test_ociosa_demais_e_descartada_sem_nem_perguntar():
    """Acima do teto de ociosidade nem vale o ping: descarta e disca. É o comportamento de HOJE,
    então o pior caso do pool é empatar com o que já existia."""
    with _Cenario() as cen:
        c = S.get_conn(); primeira = c._conn; c.close()
        S._pool_ocioso_desde[primeira] = -(S._POOL_DESCARTA_APOS_S + 1000)
        c2 = S.get_conn()
        assert c2._conn is not primeira, 'reusou conexao ociosa alem do teto'
        c2.close()
    assert cen.pool.fechadas >= 1
    print('OK  test_ociosa_demais_e_descartada_sem_nem_perguntar')


def test_conexao_fechada_no_putconn_nao_deixa_entrada_orfa():
    """O `putconn` fecha a conexão perdida em vez de devolvê-la, e sem levantar. A entrada de
    ociosidade dela precisa sair junto: uma órfã por conexão quebrada, num processo que vive dias,
    é vazamento lento — o tipo que ninguém liga a nada."""
    with _Cenario() as cen:
        c = S.get_conn()
        c._conn.closed = 1                      # imita o servidor derrubando durante o uso
        c.close()
        assert len(S._pool_ocioso_desde) == 0, \
            f'sobrou {len(S._pool_ocioso_desde)} entrada orfa no dicionario de ociosidade'
    print('OK  test_conexao_fechada_no_putconn_nao_deixa_entrada_orfa')


def test_pool_exausto_cai_no_fallback_e_NAO_levanta():
    """Aninhamento fundo ou concorrência não podem virar erro de requisição."""
    with _Cenario(maxconn=2) as cen:
        abertas = [S.get_conn(), S.get_conn()]     # esgota
        extra = S.get_conn()                       # tem que funcionar mesmo assim
        assert extra is not None
        assert cen.diretas == 1, f'nao caiu no fallback (diretas={cen.diretas})'
        assert extra._devolver is None, 'a conexao de fallback nao pode voltar para o pool'
        extra.close()
        assert extra._conn.closed == 1, 'a de fallback tem que FECHAR de verdade'
        for c in abertas:
            c.close()
    print('OK  test_pool_exausto_cai_no_fallback_e_NAO_levanta')


def test_pool_que_nem_sobe_cai_no_fallback():
    """Driver ausente, URL ruim, o que for: segue como sempre foi."""
    with _Cenario() as cen:
        def explode():
            raise RuntimeError('pool nao subiu')
        S._pool_do_processo = explode
        c = S.get_conn()
        assert c is not None and cen.diretas == 1
        c.close()
    print('OK  test_pool_que_nem_sobe_cai_no_fallback')


def test_fork_nao_herda_o_pool_do_pai():
    """Sockets do pai são os MESMOS descritores no filho. Dois processos escrevendo no mesmo
    socket é corrupção de protocolo, não lentidão."""
    orig = (S.USE_POSTGRES, S._pool, S._pool_pid, S._POOL_LIGADO)
    try:
        S.USE_POSTGRES = True
        S._POOL_LIGADO = True
        criados = []

        import psycopg2.pool as _pp
        orig_cls = _pp.ThreadedConnectionPool

        class _Espia(_PoolFalso):
            def __init__(self, minconn, maxconn, dsn, **kw):
                super().__init__(maxconn)
                criados.append(self)

        _pp.ThreadedConnectionPool = _Espia
        try:
            S._pool = None; S._pool_pid = None
            S._pool_do_processo()
            assert len(criados) == 1
            S._pool_do_processo()
            assert len(criados) == 1, 'recriou o pool sem trocar de processo'
            S._pool_pid = os.getpid() + 1          # finge ter nascido de um fork
            S._pool_do_processo()
            assert len(criados) == 2, 'o filho REUSOU o pool herdado do pai'
        finally:
            _pp.ThreadedConnectionPool = orig_cls
    finally:
        (S.USE_POSTGRES, S._pool, S._pool_pid, S._POOL_LIGADO) = orig
        S._pool_ocioso_desde.clear()
    print('OK  test_fork_nao_herda_o_pool_do_pai')


def test_desligar_por_env_volta_ao_comportamento_antigo():
    """A escotilha de emergência: `LEAKLAB_DB_POOL=0` e o app volta a discar sempre."""
    with _Cenario() as cen:
        S._POOL_LIGADO = False
        c1 = S.get_conn(); c1.close()
        c2 = S.get_conn(); c2.close()
        assert cen.diretas == 2, f'com o pool desligado deveria discar 2x, discou {cen.diretas}'
        assert cen.pool.criadas == 0, 'usou o pool mesmo desligado'
    print('OK  test_desligar_por_env_volta_ao_comportamento_antigo')


def test_sqlite_nao_passa_perto_do_pool():
    """O dev não pode mudar de comportamento: o pool é só do Postgres."""
    assert S.USE_POSTGRES is False, 'este teste roda no modo dev (SQLite)'
    c = S.get_conn()
    assert c._devolver is None, 'a conexao SQLite ganhou caminho de pool'
    c.close()
    print('OK  test_sqlite_nao_passa_perto_do_pool')


if __name__ == '__main__':
    testes = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    ok = fail = 0
    for nome, fn in testes:
        try:
            fn()
            ok += 1
        except Exception as e:
            print(f'FAIL {nome}: {e}')
            traceback.print_exc()
            fail += 1
    print(f"\n{'='*50}")
    print(f'Total: {ok+fail} | Passed: {ok} | Failed: {fail}')
