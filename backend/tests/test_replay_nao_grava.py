"""
`/replay` é somente-leitura — invariante travado.

Descoberto no Stage 3: o handler tinha DOIS blocos que diziam persistir o veredito reconciliado
(`update_decision_gto`), e nenhum dos dois jamais executou. Ambos referenciavam `_db_hand`, que é
local de `get_replay` e não existe dentro de `_build_replay_data`; o `except Exception: pass` ao
redor transformava o NameError em silêncio. Ninguém notou por meses porque a tela ficava certa —
quem estava errado era só o banco, e ninguém comparava os dois.

O que este teste protege:

  1. **O invariante que de fato vale hoje:** um GET não muda linha de `decisions`. Se alguém
     religar a persistência, este teste cai — e cair é o ponto. Ligar muda `gto_label`, que
     alimenta cobertura, scoring de leak e plano de estudo: é decisão de produto, e tem que
     passar por uma escolha explícita, não entrar de carona num refactor.

  2. **A divergência conhecida:** o card mostra o veredito reconciliado, o banco guarda o do
     import. Enquanto for assim, é melhor estar escrito e testado do que ser uma surpresa.
"""
import sys, os, tempfile, sqlite3, traceback, time

if os.environ.get('PYTHONHASHSEED') != '0':
    os.environ['PYTHONHASHSEED'] = '0'
    os.execv(sys.executable, [sys.executable] + sys.argv)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

try:
    import flask_cors  # noqa
except ImportError:
    import unittest.mock as mock
    sys.modules['flask_cors'] = mock.MagicMock()
    sys.modules['flask_cors'].CORS = lambda app, **kw: None

from database import schema, repositories

_N_HANDS = 12
# Colunas que o /replay teria motivo para querer gravar (é o veredito que ele recalcula).
_COLS = 'id, gto_label, gto_action, label, score'


def _setup():
    db = tempfile.mktemp(suffix='_readonly.db')

    def gc():
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    schema.get_conn = gc
    repositories.get_conn = gc
    import database.schema as sch
    sch.get_conn = gc
    schema.init_db()


def _snapshot(tid):
    conn = schema.get_conn()
    try:
        return {r['id']: tuple(r)[1:] for r in conn.execute(
            f"SELECT {_COLS} FROM decisions WHERE tournament_id=? ORDER BY id", (tid,))}
    finally:
        conn.close()


def _cenario(com_solver: bool):
    """Importa um torneio e devolve (client, headers, tid, hand_ids). Com solver sintético, a
    camada 2 roda de verdade — é justamente ela que dizia persistir."""
    _setup()
    import test_replay_reconciliation_golden as G
    solver = G._SyntheticSolver() if com_solver else None
    if solver:
        solver.install()
    from api.app import app
    import api.app as _am
    _am._REPLAY_CACHE.clear()          # senão a 2a execução recebe a resposta da 1a
    app.config['TESTING'] = True
    c = app.test_client()
    c.post('/auth/register', json={'username': 'ro', 'email': 'ro@t.com', 'password': 'pass1234'})
    tok = c.post('/auth/login', json={'email': 'ro@t.com', 'password': 'pass1234'}).get_json()['token']
    H = {'Authorization': f'Bearer {tok}'}
    content = open(os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt'),
                   encoding='utf-8').read()
    r = c.post('/analyze', json={'content': '\n\n\n'.join(content.split('\n\n\n')[:_N_HANDS])},
               headers=H)
    assert r.status_code == 200, r.status_code
    conn = schema.get_conn()
    tid = conn.execute("SELECT id FROM tournaments ORDER BY id DESC LIMIT 1").fetchone()['id']
    hand_ids = [row['hand_id'] for row in conn.execute(
        "SELECT DISTINCT hand_id FROM decisions WHERE tournament_id=? ORDER BY hand_id",
        (tid,)).fetchall()]
    conn.close()
    return c, H, tid, hand_ids, solver


def _estabilizar(tid, timeout=20.0):
    """Espera as threads de fundo do /analyze pararem de escrever.

    `/analyze` dispara `_preflop_sync_and_reconcile` numa thread, que ajusta `label`/`score` de
    algumas decisões depois da resposta. Sem esperar, essas escritas caem entre os dois
    snapshots e o teste acusa o /replay por algo que ele não fez — foi o que aconteceu na
    primeira versão. Quiesce: dois snapshots iguais em sequência."""
    fim = time.time() + timeout
    anterior = _snapshot(tid)
    while time.time() < fim:
        time.sleep(0.5)
        atual = _snapshot(tid)
        if atual == anterior:
            return atual
        anterior = atual
    raise AssertionError('as escritas de fundo do /analyze não estabilizaram a tempo')


def _roda(com_solver: bool, nome: str):
    c, H, tid, hand_ids, solver = _cenario(com_solver)
    try:
        antes = _estabilizar(tid)
        assert antes, 'nenhuma decisão importada'
        for hid in hand_ids:
            assert c.get(f'/replay/{tid}/{hid}', headers=H).status_code == 200
        depois = _snapshot(tid)
    finally:
        if solver:
            solver.uninstall()

    mudou = {k: (antes[k], depois[k]) for k in antes if antes.get(k) != depois.get(k)}
    assert not mudou, (
        f"/replay gravou em {len(mudou)} decisão(ões) — o GET deixou de ser somente-leitura.\n"
        f"Se foi INTENCIONAL, isso muda gto_label e portanto cobertura, scoring de leak e plano "
        f"de estudo: precisa de decisão explícita, não de um teste ajustado.\n"
        f"Exemplos: {list(mudou.items())[:3]}")
    assert set(antes) == set(depois), '/replay criou ou apagou decisões'
    print(f"OK  {nome} ({len(antes)} decisões intactas após {len(hand_ids)} GETs)")


def test_replay_nao_grava_sem_solver():
    _roda(False, 'test_replay_nao_grava_sem_solver')


def test_replay_nao_grava_com_solver():
    """O caso que importa: com nós presentes a camada 2 roda, e era ELA que dizia persistir."""
    _roda(True, 'test_replay_nao_grava_com_solver')


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
