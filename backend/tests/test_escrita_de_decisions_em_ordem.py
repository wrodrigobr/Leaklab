# -*- coding: utf-8 -*-
"""Todo escritor em massa de `decisions` grava em ordem crescente de id (11/09, 2a volta).

── O que originou ─────────────────────────────────────────────────────────────────────────

Producao deu `DeadlockDetected` em `decisions` DUAS vezes no mesmo dia. Na primeira eu tratei
UM escritor (`resync_tournament_postflop` ganhou `sort` por id) e pus um lock de thread no
gancho. Horas depois, no mesmo deploy:

    DeadlockDetected: deadlock detected
    while updating tuple (4958,33) in relation "decisions"
      database/repositories.py, line 13229, in reconcile_tournament_labels

O lock de thread nao alcanca o segundo processo (o solver-consumer e outro container), e a
ordem que eu arrumei era de UM escritor entre varios. **A minha propria docstring do guarda
anterior dizia que a ordem "vale tambem entre PROCESSOS" — e eu so a apliquei em um lugar.** E
a regra 5 do CLAUDE.md por extenso: regra aplicada em N lugares vira funcao, com teste que
varre os N+1.

── A raiz, achada no codigo ───────────────────────────────────────────────────────────────

`reconcile_tournament_labels` gravava em TRES ordens diferentes na MESMA transacao:

  1. os labels, por id;
  2. os `best_action`, por id (outro subconjunto);
  3. o score na banda, com **UPDATE EM MASSA** (`WHERE tournament_id=? AND label=?`), que trava
     as linhas na ordem que o plano do Postgres escolher, iterando os labels na ordem do dict.

Bastava outra transacao pegando as mesmas linhas por outro caminho. `resync_gto_labels_for_node`
(solver-consumer) era esse outro caminho: `SELECT ... WHERE street=? AND position=?` sem
`ORDER BY`, escrevendo linha a linha na ordem do plano, cruzando torneios.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

Deadlock nao se reproduz em teste por encomenda, entao os guardas ancoram nas CONDICOES, e
**observando o que sai** (nao relendo o fonte para reimplementar a regra):

1. **Nenhum UPDATE em massa.** Todo UPDATE em `decisions` traz `WHERE id=?`. Sem id nao ha
   ordem de trava conhecida, e nenhuma disciplina de ordenacao no resto do codigo salva.
2. **Ordem crescente.** A sequencia de ids que chega ao banco e estritamente crescente.
3. **A varredura dos N+1.** Os cinco escritores em massa que rodam junto em producao passam
   todos por `grava_decisions_em_ordem`.

Quebrados de proposito (11/09): sem o `sorted` em `grava_decisions_em_ordem`, o guarda 2 acusa
mostrando a sequencia; com o UPDATE em massa da banda de volta, o guarda 1 acusa nomeando o SQL.
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                                   # noqa: E402
import database.repositories as repo                                           # noqa: E402
from database.repositories import _adapt                                        # noqa: E402

_RAIZ = os.path.join(os.path.dirname(__file__), '..')

#: Os escritores em massa de `decisions` que podem estar rodando AO MESMO TEMPO em producao.
#: `api/app.py` e o web (gunicorn, varios workers), `repositories.py` e chamada pelos dois,
#: `preflop_autocapture` e `resync_postflop_gto` rodam no solver-consumer e no gancho. Os
#: scripts de backfill ficam fora de proposito: sao manuais, um por vez, e estao na mao de quem
#: os dispara.
_ESCRITORES = [
    'database/repositories.py',
    'api/app.py',
    'leaklab/preflop_autocapture.py',
    'scripts/resync_postflop_gto.py',
]


class _ConnEspiao:
    """Delega tudo ao conn real e anota os UPDATEs em `decisions`, na ordem em que sairam."""

    def __init__(self, real, registro):
        self._real = real
        self._registro = registro

    def execute(self, sql, params=None):
        if re.search(r'update\s+decisions', sql or '', re.IGNORECASE):
            self._registro.append((sql, params))
        return self._real.execute(sql, params)

    def __getattr__(self, nome):
        return getattr(self._real, nome)


def _espiona(registro):
    """Troca o `get_conn` de repositories pelo espiao. Devolve a funcao que restaura."""
    orig = repo.get_conn
    repo.get_conn = lambda *a, **k: _ConnEspiao(orig(*a, **k), registro)
    def _restaura():
        repo.get_conn = orig
    return _restaura


#: A semente precisa exercitar OS DOIS caminhos de gravacao, e com os ids do segundo ANTES dos
#: do primeiro — senao a ordem sai crescente por acaso e o guarda mede nada:
#:
#:   9401, 9402  label NULO e score fora da banda  -> so o alinhamento de banda (era o UPDATE
#:                                                    EM MASSA, o terceiro bloco)
#:   9405, 9406  label + gto_label divergentes     -> reconciliacao por id (o primeiro bloco)
#:
#: No codigo antigo o bloco 1 gravava 9405/9406 e SO DEPOIS vinha a massa, que nao traz id
#: nenhum. Com os ids baixos no bloco da banda, a ordem antiga sai 9405, 9406, <massa>.
_LINHAS = [
    # (id, label, gto_label, score)
    (9401, 'standard', None, 0.91),
    (9402, 'standard', None, 0.88),
    (9405, 'clear_mistake', 'gto_correct', 0.90),
    (9406, 'clear_mistake', 'gto_correct', 0.90),
]


def _semeia():
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                        "VALUES (9401,'u','u@e.st','h')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero, raw_text) VALUES (9401, 9401, 'T1', 'T', 'Hero', 'texto')"))
    for did, label, gto_label, score in _LINHAS:
        conn.execute(_adapt(
            "INSERT INTO decisions (id, tournament_id, hand_id, street, hero_cards, board, "
            "action_taken, best_action, gto_action, label, gto_label, score, position, "
            "num_players, stack_bb) VALUES (?, 9401, ?, 'flop', 'QsTs', "
            "'[\"3c\",\"Js\",\"Th\"]', 'bet', 'bet', 'bet', ?, ?, ?, 'BB', 9, 30)"),
            (did, 'H%d' % did, label, gto_label, score))
    conn.commit(); conn.close()


def _roda_reconcile():
    """Roda o reconcile com o espiao e devolve a lista de (sql, params) dos UPDATEs."""
    _semeia()
    registro = []
    restaura = _espiona(registro)
    try:
        repo.reconcile_tournament_labels(9401)
    finally:
        restaura()
    return registro


def test_nenhum_update_em_massa_em_decisions():
    """CONDICAO 1. `UPDATE decisions ... WHERE tournament_id=? AND label=?` trava as linhas na
    ordem do plano do Postgres. Nenhuma ordenacao no resto do codigo compensa isso."""
    registro = _roda_reconcile()
    assert registro, 'o reconcile nao gravou nada: a semente nao exercita o caminho de escrita'
    # OS DOIS placeholders. `_adapt` troca `?` por `%s` no Postgres, entao o SQL que chega ao
    # banco tem forma diferente em cada backend. A primeira versao olhava so `?`: passava em
    # SQLite e acusava FALSAMENTE na homologacao contra o Postgres, com o codigo correto. Guarda
    # que inspeciona SQL executado tem de conhecer os dois dialetos, ou ele mede o adapter.
    sem_id = [sql for sql, _ in registro
              if not re.search(r'where\s+id\s*=\s*(?:\?|%s)', sql, re.I)]
    assert not sem_id, ('UPDATE em massa em decisions (sem WHERE id): ordem de trava '
                        'imprevisivel', sem_id)


def test_os_ids_chegam_ao_banco_em_ordem_crescente():
    """CONDICAO 2. Dois escritores que travam na MESMA ordem nao formam ciclo. Esta e a unica
    defesa que funciona entre PROCESSOS, onde lock de thread nao alcanca.

    **Este guarda passou com o `sorted` removido** na quebra de proposito de 11/09, e por isso
    tem duas partes. A observacional sozinha ancora no EFEITO: a ordem de gravacao do reconcile
    sai crescente de qualquer jeito, porque o `por_id` e preenchido lendo as linhas em
    `ORDER BY id`. Quem realmente sustenta o efeito e a CONDICAO abaixo — o `ORDER BY` no SELECT
    — e e nela que o guarda tem de bater, senao ele protege o resultado sem proteger a causa."""
    registro = _roda_reconcile()
    ids = [p[-1] for _, p in registro if p]
    assert len(ids) >= 3, ('menos de 3 gravacoes observadas: o teste nao exercita a ordem', ids)
    assert ids == sorted(ids), ('os ids sairam fora de ordem', ids)
    # Controle: a semente tem de produzir gravacao NOS DOIS caminhos. Se so um rodasse, a ordem
    # sairia crescente de graca e o guarda passaria medindo metade.
    assert 9401 in ids and 9405 in ids, ('a semente nao exercitou os dois caminhos '
                                         '(banda de score e reconciliacao)', ids)

    # A CONDICAO: os dois SELECTs que alimentam gravacao em massa leem em ordem de id. Sem isto,
    # o SQLite do teste ainda devolveria ordenado (rowid) e o guarda acima passaria verde
    # enquanto o Postgres de producao entregaria a ordem do plano.
    src = open(os.path.join(_RAIZ, 'database/repositories.py'), encoding='utf-8').read()
    for fn in ('reconcile_tournament_labels', 'resync_gto_labels_for_node'):
        corpo = src.split('def %s(' % fn, 1)[1].split('\ndef ', 1)[0]
        sel = re.search(r'SELECT[^;]*?FROM decisions(.*?)"""', corpo, re.DOTALL)
        assert sel, ('nao achei o SELECT de decisions em %s' % fn)
        assert re.search(r'ORDER BY\s+id', sel.group(0), re.IGNORECASE), (
            '%s le decisions sem ORDER BY id: no Postgres a ordem e a do plano' % fn)


def test_os_cinco_escritores_passam_pela_funcao_unica():
    """A VARREDURA DOS N+1 (regra 5). Na primeira volta eu consertei um escritor e declarei o
    deadlock resolvido; o de baixo quebrou producao no mesmo dia. Este guarda cobra todos.

    Ancora na CONDICAO, nao no texto: cada arquivo que roda concorrente em producao ou nao
    escreve `decisions` em massa, ou chama `grava_decisions_em_ordem`."""
    faltando = []
    for rel in _ESCRITORES:
        src = open(os.path.join(_RAIZ, rel), encoding='utf-8').read()
        # A CHAMADA, nao a mencao: todos estes arquivos citam a funcao em comentario explicando
        # a ordem, e comentario nao e evidencia (regra 8). A primeira versao deste guarda
        # procurava o nome solto e passava verde com a chamada apagada e o comentario de pe.
        linhas = [l.split('#', 1)[0] for l in src.splitlines()]
        if not re.search(r'grava_decisions_em_ordem\s*\(', '\n'.join(linhas)):
            faltando.append(rel)
    assert not faltando, ('escritor em massa de decisions sem a funcao de ordem', faltando)


def test_nenhum_update_em_massa_no_FONTE_dos_escritores():
    """O guarda observacional acima so ve o caminho que a semente exercita. Este varre o fonte
    dos quatro arquivos e acusa `UPDATE decisions` cujo WHERE nao e por id — que foi exatamente
    a forma do bug (o alinhamento de banda por label)."""
    achados = []
    for rel in _ESCRITORES:
        src = open(os.path.join(_RAIZ, rel), encoding='utf-8').read()
        # Junta o SQL quebrado em varias strings adjacentes antes de olhar o WHERE.
        for m in re.finditer(r'UPDATE\s+decisions\s+SET(.{0,400}?)(?:"\s*\)|\'\s*\))',
                             src, re.IGNORECASE | re.DOTALL):
            trecho = re.sub(r'["\']\s*\n\s*["\']', ' ', m.group(0))
            if not re.search(r'WHERE\s+id\s*=\s*\?', trecho, re.IGNORECASE):
                achados.append((rel, ' '.join(trecho.split())[:120]))
    assert not achados, ('UPDATE em massa em decisions no fonte de um escritor concorrente',
                         achados)


def test_a_funcao_de_ordem_ordena_mesmo():
    """A funcao e a fonte unica: se ela parar de ordenar, todos os quatro escritores perdem a
    garantia de uma vez. Chamada com os ids ao contrario, ela grava do menor para o maior."""
    registro = []
    conn = _ConnEspiao(type('_Falso', (), {'execute': lambda self, s, p=None: None})(), registro)
    # `label` sempre acompanhado de `score` — a porta recusa o contrario, e e de proposito
    # (ver `test_a_porta_generica_RECUSA_gravar_label_sem_score`).
    repo.grava_decisions_em_ordem(conn, {9406: {'score': 0.1}, 9401: {'score': 0.2},
                                         9405: {'label': 'standard', 'score': 0.0}})
    ids = [p[-1] for _, p in registro]
    assert ids == [9401, 9405, 9406], ids
    # Uma linha, um UPDATE, com todas as colunas dela juntas (nao um UPDATE por coluna).
    repo.grava_decisions_em_ordem(conn, {}) is None


def test_a_porta_generica_RECUSA_gravar_label_sem_score():
    """A invariante de v0.168 ("quem muda o veredito carrega o score junto") era defendida por
    uma varredura TEXTUAL que procura `label` e `score` na mesma sentenca de UPDATE. Esta porta
    monta o SET a partir de um dict: as colunas sao DADOS, e nenhuma varredura textual alcanca.

    Em vez de abrir excecao no guarda, a porta recusa a gravacao. Vale para todo chamador,
    inclusive o proximo, e nao depende de ninguem lembrar da regra."""
    registro = []
    conn = _ConnEspiao(type('_Falso', (), {'execute': lambda self, s, p=None: None})(), registro)
    try:
        repo.grava_decisions_em_ordem(conn, {5: {'label': 'clear_mistake'}})
        assert False, 'gravou `label` sem `score`: a invariante de v0.168 caiu'
    except ValueError as e:
        assert 'score' in str(e), e
    assert not registro, ('recusou mas gravou alguma coisa', registro)
    # Os dois juntos passam, e o score sozinho tambem (ele nao muda veredito).
    repo.grava_decisions_em_ordem(conn, {5: {'label': 'standard', 'score': 0.0}})
    repo.grava_decisions_em_ordem(conn, {6: {'score': 0.2}})
    assert len(registro) == 2, registro


def test_uma_linha_recebe_um_unico_update_com_todas_as_colunas():
    """Label, score e best_action da MESMA linha saiam num UPDATE so. Dois UPDATEs na mesma
    linha nao criam ciclo, mas dobram a ida ao banco no caminho mais quente do reconcile."""
    registro = []
    conn = _ConnEspiao(type('_Falso', (), {'execute': lambda self, s, p=None: None})(), registro)
    repo.grava_decisions_em_ordem(conn, {77: {'label': 'standard', 'score': 0.0,
                                              'best_action': 'fold'}})
    assert len(registro) == 1, ('a linha recebeu %d UPDATEs' % len(registro), registro)
    sql, params = registro[0]
    for col in ('label', 'score', 'best_action'):
        assert col in sql, (col, sql)
    assert params[-1] == 77, params


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
