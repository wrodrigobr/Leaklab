"""
O worker da fila de mãos girando em falso — e a esteira de re-solve que isso criava.

O que aconteceu em produção no dia em que o worker finalmente passou a rodar lá (antes ele só
subia no `__main__`, então ninguém tinha visto): `req_id=8` reprocessado a cada 6 segundos, para
sempre.

A causa não é o worker, é uma incompatibilidade de CADÊNCIA. `get_pending_gto_hand_requests`
inclui 'solver_queued' de propósito, para que o pedido seja re-checado e vire 'done' depois que o
solver termina os spots. Isso foi desenhado para um cron de 5 minutos, onde é barato. Num loop
always-on que dorme 5 segundos, o pedido volta na lista a cada ciclo enquanto o solver não
termina.

E aí vem a parte cara: `enqueue_solver_spot` RESSUSCITA spot 'done'/'failed' de volta para
'pending'. Cada volta reenfileirava o mesmo spot. Um spot que o solver não consegue resolver
virava esteira de re-solve infinita, ocupando a máquina do solver com trabalho que nunca conclui.

Duas defesas, testadas aqui:
  1. o chamador escolhe a cadência (`include_queued`) — rápido para o que é novo, lento para o
     que já está com o solver;
  2. age-out: passado `_GTO_STALE_HOURS`, o pedido é encerrado. 'Sem cobertura' é um estado
     TERMINAL; 'em andamento' há três dias não é. Mesmo princípio que aposentou o `wizard_pending`.
"""
import sys, os, ast, traceback, tempfile, sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema
import database.repositories as repo

TEST_DB = tempfile.mktemp(suffix='_cadence.db')


def _conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


schema.get_conn = _conn
repo.get_conn = _conn
schema.init_db()


def _setup(linhas):
    """linhas = [(hand_id, status, idade_em_horas)]"""
    conn = _conn()
    conn.execute("DELETE FROM gto_hand_requests")
    conn.execute("DELETE FROM users WHERE id = 1")
    conn.execute("INSERT INTO users (id, username, email, password_hash) VALUES (1,'u','u@t.com','x')")
    for hid, status, idade in linhas:
        criado = (datetime.utcnow() - timedelta(hours=idade)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            "INSERT INTO gto_hand_requests (tournament_id, hand_id, requested_by, status, created_at) "
            "VALUES (?,?,?,?,?)", (1, hid, 1, status, criado))
    conn.commit()
    conn.close()


def _status():
    conn = _conn()
    try:
        return {r['hand_id']: r['status'] for r in
                conn.execute("SELECT hand_id, status FROM gto_hand_requests")}
    finally:
        conn.close()


# ── Cadência ──────────────────────────────────────────────────────────────────────────────────

def test_caminho_rapido_ignora_o_que_ja_esta_com_o_solver():
    """O ciclo curto só olha o que é NOVO. Era isto que faltava: incluir os queued a cada 5s é o
    que produzia o reprocessamento em loop."""
    _setup([('h_novo', 'pending', 0), ('h_queued', 'solver_queued', 0),
            ('h_proc', 'processing', 0)])
    ids = [r['hand_id'] for r in repo.get_pending_gto_hand_requests(limit=10, include_queued=False)]
    assert ids == ['h_novo'], ids
    print("OK  test_caminho_rapido_ignora_o_que_ja_esta_com_o_solver")


def test_rechecagem_traz_os_queued():
    """A re-checagem continua existindo — é ela que faz o pedido virar 'done'. Só não é a cada
    ciclo."""
    _setup([('h_novo', 'pending', 0), ('h_queued', 'solver_queued', 0)])
    ids = sorted(r['hand_id'] for r in
                 repo.get_pending_gto_hand_requests(limit=10, include_queued=True))
    assert ids == ['h_novo', 'h_queued'], ids
    print("OK  test_rechecagem_traz_os_queued")


def test_default_preservado_para_o_cron():
    """`scripts/drain_hand_requests.py` chama sem o parâmetro e PRECISA dos queued (roda em
    cadência de cron). Mudar o default quebraria o dreno manual em silêncio."""
    _setup([('h_queued', 'solver_queued', 0)])
    assert len(repo.get_pending_gto_hand_requests(limit=10)) == 1
    print("OK  test_default_preservado_para_o_cron")


# ── Age-out ───────────────────────────────────────────────────────────────────────────────────

def test_encerra_pedido_preso_ha_muito_tempo():
    _setup([('h_velho', 'solver_queued', repo._GTO_STALE_HOURS + 1)])
    assert repo.expire_stale_gto_hand_requests() == 1
    assert _status()['h_velho'] == 'done'
    print("OK  test_encerra_pedido_preso_ha_muito_tempo")


def test_nao_encerra_pedido_recente():
    """O solver leva minutos; encerrar cedo transformaria trabalho em andamento em desistência."""
    _setup([('h_novo', 'solver_queued', 1)])
    assert repo.expire_stale_gto_hand_requests() == 0
    assert _status()['h_novo'] == 'solver_queued'
    print("OK  test_nao_encerra_pedido_recente")


def test_age_out_nao_toca_em_pending():
    """'pending' velho é fila parada (worker caído), não spot sem cobertura — o dreno resolve.
    Encerrá-lo esconderia uma falha de operação em vez de mostrar."""
    _setup([('h_pending', 'pending', repo._GTO_STALE_HOURS + 5)])
    assert repo.expire_stale_gto_hand_requests() == 0
    assert _status()['h_pending'] == 'pending'
    print("OK  test_age_out_nao_toca_em_pending")


def test_pedido_encerrado_some_da_rechecagem():
    """O efeito que importa: encerrado não volta na lista, então para de reenfileirar o spot."""
    _setup([('h_velho', 'solver_queued', repo._GTO_STALE_HOURS + 1)])
    repo.expire_stale_gto_hand_requests()
    assert repo.get_pending_gto_hand_requests(limit=10, include_queued=True) == []
    print("OK  test_pedido_encerrado_some_da_rechecagem")


def test_dashboard_nao_conta_o_queued():
    """Reforço do invariante vizinho: o aviso do jogador conta só 'pending'. Um pedido esperando
    o solver não é 'spot sendo validado' na conta do banner."""
    _setup([('h_queued', 'solver_queued', 0)])
    assert repo.get_user_pending_gto_count(1) == 0
    _setup([('h_novo', 'pending', 0)])
    assert repo.get_user_pending_gto_count(1) == 1
    print("OK  test_dashboard_nao_conta_o_queued")


# ── O loop usa mesmo as duas cadências ────────────────────────────────────────────────────────

def test_worker_nao_pede_os_queued_a_cada_ciclo():
    """Trava por AST: se alguém voltar a chamar sem `include_queued`, o loop volta a girar a cada
    5 segundos — e isso não aparece em teste de unidade, só na conta do solver."""
    fonte = open(os.path.join(os.path.dirname(__file__), '..', 'api', 'app.py'),
                 encoding='utf-8').read()
    arvore = ast.parse(fonte)
    loop = next((n for n in ast.walk(arvore)
                 if isinstance(n, ast.FunctionDef) and n.name == '_gto_hand_worker_loop'), None)
    assert loop is not None, '_gto_hand_worker_loop sumiu'
    chamadas = [n for n in ast.walk(loop) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == 'get_pending_gto_hand_requests']
    assert chamadas, 'o loop não busca pedidos?'
    for c in chamadas:
        assert any(kw.arg == 'include_queued' for kw in c.keywords), (
            "o worker voltou a pedir TODOS os estados a cada ciclo — é o loop de 6s de volta")
    print("OK  test_worker_nao_pede_os_queued_a_cada_ciclo")


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
    raise SystemExit(1 if failed else 0)
