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
        self._autocommit = False

    # `autocommit` no psycopg2 não é um campo, é `set_session` — e ele LEVANTA dentro de uma
    # transação. O dublê aceitava a atribuição em silêncio, e por isso os testes ficaram verdes
    # enquanto produção subia em loop de restart com
    # `ProgrammingError: set_session cannot be used inside a transaction`.
    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, v):
        if self.em_transacao:
            raise Exception('set_session cannot be used inside a transaction')
        self._autocommit = v

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
    """Imita o ThreadedConnectionPool **incluindo as regras que mordem**.

    A primeira versão deste dublê guardava TODA conexão devolvida, e por isso os testes passaram
    sobre um modelo que não era o psycopg2. Duas regras reais estavam faltando, e as duas causaram
    defeito em produção:

    1. `_putconn` é `if len(self._pool) < self.minconn and not close:` — ele **retém até `minconn`
       e FECHA o resto**. Com `minconn=1` só uma conexão ficava quente e todo aninhamento pagava
       o handshake de novo.
    2. O construtor já cria `minconn` conexões, e essas nunca passaram pelo caminho de devolução
       — logo, o código não sabe a idade delas.
    """

    def __init__(self, minconn, maxconn):
        self.minconn = minconn
        self.maxconn = maxconn
        self.criadas = 0
        self.emprestadas = 0
        self.fechadas = 0
        self.pedidos = 0          # quantas vezes o pool foi CONSULTADO (não quantas criou)
        # o construtor do psycopg2 já abre minconn conexões
        self.livres = [self._nova() for _ in range(minconn)]

    def _nova(self):
        self.criadas += 1
        return _ConexaoFalsa(self.criadas)

    def getconn(self):
        self.pedidos += 1
        if self.livres:
            c = self.livres.pop()
        else:
            if self.emprestadas >= self.maxconn:
                raise Exception('connection pool exhausted')
            c = self._nova()
        self.emprestadas += 1
        return c

    def putconn(self, conn, close=False):
        self.emprestadas -= 1
        if close or conn.closed or len(self.livres) >= self.minconn:
            self.fechadas += 1
            conn.close()
            return
        if conn.em_transacao:          # a regra do psycopg2 de que o desenho depende
            conn.rollback()
        self.livres.append(conn)


class _Cenario:
    """Liga o caminho Postgres com os dublês e restaura tudo depois."""

    def __init__(self, maxconn=8, minconn=None, direto_falha=False):
        self._minconn = S._POOL_MIN if minconn is None else minconn
        self.pool = _PoolFalso(self._minconn, maxconn)
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
    novas = cen.pool.criadas - cen._minconn
    assert novas == 0, f'criou {novas} conexao(oes) NOVA(s) para 3 idas seguidas'
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
    novas = cen.pool.criadas - cen._minconn
    assert novas == 0, f'o aninhamento discou {novas} vez(es) a mais'
    print('OK  test_aninhamento_recebe_conexoes_DIFERENTES')


def test_liberacao_dupla_nao_devolve_duas_vezes():
    """`with get_conn() as c:` com um `c.close()` dentro dispara close E __exit__."""
    with _Cenario() as cen:
        with S.get_conn() as c:
            c.close()                      # o caminho que devolve duas vezes sem a trava
        n_livres = len(cen.pool.livres)
        assert n_livres <= cen._minconn, (
            f'a fila livre passou de {cen._minconn} para {n_livres}: a conexao voltou duas vezes')
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
            # DELTA, não total: o ping de vivacidade também dá rollback, então o número absoluto
            # mede quantas vezes a conexão foi conferida, não se a devolução limpou a transação.
            antes = c._conn.rollbacks
            suja = c._conn
        assert suja.rollbacks == antes + 1, 'a transação aberta voltou ao pool SEM rollback'
        assert not suja.em_transacao, 'o próximo dono herdaria a transação'
        assert suja in cen.pool.livres, 'a conexão suja nem voltou para o pool'
    print('OK  test_transacao_aberta_nao_vaza_para_o_proximo')


def test_conexao_de_idade_DESCONHECIDA_e_conferida_antes_de_entregar():
    """**Este é o teste do 503 em produção.**

    O pool abre `minconn` conexões no construtor. Elas nunca passaram pelo caminho de devolução,
    então não estão no dicionário de ociosidade — a idade delas é desconhecida. A primeira versão
    do código usava `pop(raw, time.monotonic())`, que faz o desconhecido ler como recém-criado: a
    conexão saía SEM ping, viva ou morta. O `/health` passou a responder `{"db": false}` e 503,
    cerca de uma em cinco, medido de fora.

    Idade desconhecida tem que pesar CONTRA reusar.
    """
    with _Cenario() as cen:
        assert cen.pool.livres, 'o dublê não abriu conexão no construtor — o teste mede nada'
        antiga = cen.pool.livres[-1]
        antiga.morta = True                       # nasceu no boot e morreu ociosa desde então
        assert antiga not in S._pool_ocioso_desde, 'a de construtor não pode estar registrada'
        c = S.get_conn()
        assert c._conn is not antiga, 'entregou a conexao de idade DESCONHECIDA sem conferir'
        c.execute('SELECT 1')                      # a prova final: ela funciona
        c.close()
    print('OK  test_conexao_de_idade_DESCONHECIDA_e_conferida_antes_de_entregar')


def test_minconn_mantem_conexoes_quentes_para_o_aninhamento():
    """`_putconn` do psycopg2 é `if len(self._pool) < self.minconn` — ele RETÉM até `minconn` e
    FECHA o resto. Com `minconn=1` a conexão de dentro do aninhamento era fechada a cada volta e
    o handshake voltava a ser pago (72ms medidos). O pool precisa reter mais de uma."""
    assert S._POOL_MIN >= 2, f'_POOL_MIN={S._POOL_MIN}: o aninhamento de profundidade 2 nao cabe'
    with _Cenario() as cen:
        fora, dentro = S.get_conn(), S.get_conn()
        n_fora, n_dentro = fora._conn.n, dentro._conn.n
        dentro.close(); fora.close()
        assert len(cen.pool.livres) >= 2, \
            f'so {len(cen.pool.livres)} conexao(oes) ficou quente: o aninhamento vai rediscar'
        # e a prova: repetir o aninhamento não cria conexão nova
        criadas_antes = cen.pool.criadas
        f2, d2 = S.get_conn(), S.get_conn()
        assert {f2._conn.n, d2._conn.n} == {n_fora, n_dentro}, 'o aninhamento nao reusou'
        d2.close(); f2.close()
        assert cen.pool.criadas == criadas_antes, 'discou de novo no aninhamento'
    print('OK  test_minconn_mantem_conexoes_quentes_para_o_aninhamento')


def test_o_ping_nao_pode_deixar_transacao_aberta():
    """**Este é o teste do loop de restart em produção.**

    O ping é um `SELECT 1`, e no psycopg2 isso ABRE uma transação. A conexão saía do pool dentro
    dela, e a linha seguinte (`raw.autocommit = False`) virava
    `ProgrammingError: set_session cannot be used inside a transaction`. O worker morria no boot,
    em `init_db()`, e o container entrou em loop de restart — 400 de 400 requisições em 502.

    Ironia registrada: antes do conserto anterior o ping quase nunca rodava, então este caminho
    não era exercitado. Consertar o ping o tornou o caminho NORMAL e o defeito latente virou
    parada total.
    """
    with _Cenario() as cen:
        antiga = cen.pool.livres[-1]              # a do construtor: idade desconhecida → força ping
        c = S.get_conn()                          # não pode levantar
        assert not c._conn.em_transacao, 'a conexao saiu do pool com transacao ABERTA'
        assert c._conn.consultas, 'o ping nem rodou — o teste nao mediu o caminho que quebrou'
        c.close()
    print('OK  test_o_ping_nao_pode_deixar_transacao_aberta')


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
    with _Cenario(maxconn=2, minconn=1) as cen:
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
                super().__init__(minconn, maxconn)
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
        assert cen.pool.pedidos == 0, 'consultou o pool mesmo desligado'
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
