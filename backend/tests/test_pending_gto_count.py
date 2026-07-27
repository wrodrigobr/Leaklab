"""
Regressão: o dashboard anunciava spots "sendo validados" que ninguém ia validar.

Relatado: admin mostrando 0 pendentes na fila do solver e, ao mesmo tempo, o dashboard do
jogador dizendo "3 spots ainda sendo validados pelo solver. Suas estatísticas serão recomputadas
automaticamente conforme concluem."

`get_user_pending_gto_count` somava DUAS fontes: a fila real (`gto_hand_requests`) e as decisões
com `gto_label='wizard_pending'`. Essa segunda marcava spots para o fallback do GTO Wizard, que
foi descontinuado — a função que as criava já está aposentada, mas as linhas antigas seguiam no
banco e contando. O aviso prometia uma conclusão que nunca chega.

A invariante: "em andamento" é só o que está MESMO na fila.
"""
import sys, os, traceback, tempfile, sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import database.schema as schema
import database.repositories as repo

# Banco temporário próprio (mesmo padrão de test_database): `:memory:` não serve porque cada
# get_conn() abriria um banco NOVO e vazio.
TEST_DB = tempfile.mktemp(suffix='.db')


def _conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    return c


schema.get_conn = _conn
repo.get_conn = _conn
schema.init_db()
get_user_pending_gto_count = repo.get_user_pending_gto_count


def _setup():
    """1 usuário, 1 torneio, 3 decisões wizard_pending e a fila do solver VAZIA.

    Sem `except: pass` no meio: se uma limpeza falhar eu QUERO ver o erro — foi engolindo
    exceção assim que este projeto perdeu horas atrás de "a tabela não existe".
    """
    conn = _conn()
    try:
        conn.execute('DELETE FROM gto_hand_requests')
        conn.execute('DELETE FROM decisions')
        conn.execute('DELETE FROM tournaments')
        conn.execute('DELETE FROM users')
        conn.execute("INSERT INTO users (id, username, email, password_hash, role) "
                     "VALUES (901, 'pend', 'p@x.com', 'x', 'player')")
        conn.execute("INSERT INTO tournaments (id, user_id, tournament_id, hero, site) "
                     "VALUES (9010, 901, 'T-PEND', 'pend', 'PokerStars')")
        for i in range(3):
            conn.execute(
                "INSERT INTO decisions (tournament_id, hand_id, street, position, action_taken, "
                "best_action, label, score, gto_label) "
                "VALUES (9010, ?, 'preflop', 'BTN', 'call', 'call', 'standard', 0.0, "
                "'wizard_pending')", (f'H{i}',))
        conn.commit()
    finally:
        conn.close()      # fechar SEMPRE: conexão pendurada trava o arquivo pro próximo teste


def _fila(user_id: int, status: str, hand: str):
    """Insere um pedido na fila REAL do solver (a mesma que o painel do admin lê)."""
    c = _conn()
    try:
        c.execute("INSERT INTO gto_hand_requests (tournament_id, hand_id, requested_by, status) "
                  "VALUES (9010, ?, ?, ?)", (hand, user_id, status))
        c.commit()
    finally:
        c.close()


def test_wizard_pending_nao_conta_como_em_andamento():
    """O caso exato do relato: 3 decisões marcadas, fila do solver vazia → contador ZERO."""
    _setup()
    c = _conn()
    marcadas = c.execute("SELECT COUNT(*) FROM decisions WHERE gto_label='wizard_pending'").fetchone()[0]
    c.close()
    assert marcadas == 3, marcadas
    assert get_user_pending_gto_count(901) == 0, "wizard_pending voltou a contar"
    print("OK  test_wizard_pending_nao_conta_como_em_andamento")


def test_fila_real_continua_contando():
    """A correção não pode zerar o indicador legítimo: pedido de fato na fila conta."""
    _setup()
    _fila(901, 'pending', 'H-FILA')
    assert get_user_pending_gto_count(901) == 1
    print("OK  test_fila_real_continua_contando")


def test_pedido_concluido_nao_conta():
    _setup()
    _fila(901, 'done', 'H-OK')
    _fila(901, 'error', 'H-ERR')
    assert get_user_pending_gto_count(901) == 0
    print("OK  test_pedido_concluido_nao_conta")


def test_fila_de_outro_usuario_nao_vaza():
    _setup()
    _fila(902, 'pending', 'H-OUTRO')
    assert get_user_pending_gto_count(901) == 0
    print("OK  test_fila_de_outro_usuario_nao_vaza")


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
