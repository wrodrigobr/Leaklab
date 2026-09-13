# -*- coding: utf-8 -*-
"""O `/analyze` nao pode gastar o orcamento do worker em ida e volta ao banco (13/09).

── O caso, que chegou como erro de producao ───────────────────────────────────────────────

O dono mandou um `SystemExit: 1` do Sentry, com o traceback morrendo dentro de uma query de
contagem de erros por categoria. A query nao era a culpada: ela leva **0,07s** no pior caso do
acervo. `SystemExit` no meio de um `cur.execute` e a assinatura do **gunicorn matando o worker
no timeout de 120s** — o machado cai onde a fila estiver quando o tempo acaba.

Medido no maior torneio do acervo (id 262, 1.519 maos, 2.231 decisoes, 2,5 MB):

    parse               0,6s
    pipeline           27,6s
    motor             103,7s   <- 46,5 ms por decisao
    ────────────────────────
    so essas tres     131,9s   contra 120s de timeout

E o motor nao gastava isso em conta: **1,9 consultas a `gto_nodes` por decisao, 64% do tempo
dentro delas**, cada uma abrindo a propria conexao ao Neon, que fica em Frankfurt. Das 4.170
consultas do torneio, **59% repetiam um hash ja consultado no mesmo upload**.

O HUD somava mais: `upsert_opponent_profile` abria uma conexao POR JOGADOR, e os torneios do
acervo chegam a 349 oponentes (~18s so de handshake).

**Nao era regressao.** Nos 15 dias anteriores so 3 commits tocaram o motor, e nenhum mexeu em
consulta. O desenho sempre foi N+1; o que mudou foi o tamanho do arquivo que o jogador sobe.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. O cache de no e de ESCOPO, nunca global: fora do escopo cada chamada consulta, e dois escopos
   seguidos nao herdam um do outro. Isso importa porque o solver GRAVA nos, e um no recem-solvado
   invisivel por cache seria a pior troca possivel — o jogador perde um veredito que ja existe.
2. O escopo cobre a avaliacao no `/analyze`.
3. O HUD grava os perfis numa conexao so.

Ganho medido no mesmo torneio 262: **89,2s -> 39,0s** no motor (56% menos tempo, 57% menos
consultas), mais ~18s do HUD.
"""
import io
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db, _AdaptedConn                     # noqa: E402
from database.repositories import (_adapt, escopo_de_nos_gto, get_gto_node,     # noqa: E402
                                   upsert_opponent_profiles, get_opponent_profiles)

init_db()

_APP = os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py')


class _Contador:
    """Conta as consultas que batem num alvo, sem mexer no codigo medido."""

    def __init__(self, alvo):
        self.alvo, self.n = alvo, 0

    def __enter__(self):
        self._orig = _AdaptedConn.execute
        alvo, contador = self.alvo, self

        def espiao(zelf, sql, params=None):
            if alvo in (sql or ''):
                contador.n += 1
            return contador._orig(zelf, sql, params)
        _AdaptedConn.execute = espiao
        return self

    def __exit__(self, *a):
        _AdaptedConn.execute = self._orig


def test_dentro_do_escopo_o_mesmo_hash_consulta_UMA_vez():
    with _Contador('gto_nodes') as c:
        with escopo_de_nos_gto():
            for _ in range(6):
                get_gto_node('hash-repetido')
    assert c.n == 1, ('o cache de escopo nao cortou a repeticao: %d consultas' % c.n)


def test_FORA_do_escopo_nada_muda():
    """CONTROLE. Sem escopo o comportamento e o de sempre — o cache nao pode vazar para quem
    nao pediu, e o resync/replay dependem de ler o banco como ele esta."""
    with _Contador('gto_nodes') as c:
        for _ in range(6):
            get_gto_node('hash-repetido')
    assert c.n == 6, ('o cache vazou para fora do escopo: %d consultas em 6 chamadas' % c.n)


def test_dois_escopos_seguidos_NAO_herdam():
    """O que separa "cache de escopo" de "cache de processo". Se o segundo herdasse, um no
    solvado entre os dois uploads ficaria invisivel."""
    with _Contador('gto_nodes') as c:
        with escopo_de_nos_gto():
            get_gto_node('hash-a')
        with escopo_de_nos_gto():
            get_gto_node('hash-a')
    assert c.n == 2, ('o segundo escopo herdou o cache do primeiro: %d consultas' % c.n)


def test_escopo_aninhado_nao_limpa_o_de_fora():
    with _Contador('gto_nodes') as c:
        with escopo_de_nos_gto():
            get_gto_node('hash-b')
            with escopo_de_nos_gto():
                get_gto_node('hash-b')
            get_gto_node('hash-b')
    assert c.n == 1, ('o escopo aninhado quebrou o cache do externo: %d consultas' % c.n)


def test_o_cache_e_POR_THREAD():
    """O `/analyze` dispara threads (autocapture, ELO). Cache compartilhado faria uma requisicao
    servir dado colhido por outra."""
    vistos = {}

    def outra():
        with _Contador('gto_nodes') as c2:
            get_gto_node('hash-c')          # fora de escopo nesta thread
            vistos['n'] = c2.n

    with escopo_de_nos_gto():
        get_gto_node('hash-c')
        t = threading.Thread(target=outra)
        t.start(); t.join()
    assert vistos.get('n') == 1, ('a thread vizinha herdou o cache: %s' % vistos)


def test_o_analyze_abre_o_escopo_na_avaliacao():
    """FIACAO: o cache so serve se alguem o usar, e o unico consumidor que importa e o upload."""
    src = io.open(_APP, encoding='utf-8').read()
    assert 'with escopo_de_nos_gto():' in src, 'o /analyze parou de abrir o escopo'
    i = src.index('with escopo_de_nos_gto():')
    trecho = src[i:i + 400]
    assert '_analyze_hands(' in trecho, (
        'o escopo existe mas nao cobre a avaliacao — e ali que estao 4.170 das consultas')


def test_o_HUD_grava_os_perfis_numa_conexao_so():
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                        "VALUES (7701,'u','u7701@e.st','h')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero, site, raw_text) VALUES (7701, 7701, 'T', 'T', 'Hero', 'pokerstars', 'x')"))
    conn.commit(); conn.close()

    perfis = {'Vilao%d' % i: {'hands': 100 + i, 'archetype': 'unknown'} for i in range(40)}
    n = upsert_opponent_profiles(7701, perfis)
    assert n == 40, n
    assert len(get_opponent_profiles(7701)) == 40, 'os perfis nao chegaram ao banco'
    # idempotente: a segunda passagem atualiza, nao duplica
    upsert_opponent_profiles(7701, perfis)
    assert len(get_opponent_profiles(7701)) == 40, 'o upsert em lote duplicou linha'


def test_o_analyze_NAO_grava_perfil_um_a_um():
    """CONDICAO, nao efeito: o laco `for` chamando a versao de um perfil so era o defeito —
    349 conexoes ao Neon num upload."""
    src = io.open(_APP, encoding='utf-8').read()
    linhas = [l.split('#', 1)[0] for l in src.splitlines()]
    codigo = '\n'.join(linhas)
    # A funcao de lote pode entrar por alias (`... as _upsert_lote`), entao o guarda olha o
    # IMPORT dela, e nao um nome de chamada que o proximo refactor renomeia.
    assert 'upsert_opponent_profiles' in codigo, (
        'o /analyze parou de importar a gravacao em lote dos perfis')
    assert 'upsert_opponent_profile as' not in codigo and '_upsert_prof(' not in codigo, (
        'voltou a gravar perfil um a um dentro de um laco: uma conexao por jogador')
    # E o LACO (statement) nao pode voltar. Ancorado em inicio de linha e nos dois-pontos: a
    # primeira versao deste assert usava o padrao solto e acusava a PROPRIA SOLUCAO, porque a
    # dict comprehension `{n: p for n, p in _profiles.items() ...}` casa igual. Guarda que
    # reprova o conserto e pior que guarda ausente.
    import re as _re
    assert not _re.search(r'^\s*for\s+\w+,\s*\w+\s+in\s+_profiles\.items\(\)\s*:',
                          codigo, _re.MULTILINE), (
        'voltou o laco por jogador sobre `_profiles`: uma conexao ao banco por oponente')


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
