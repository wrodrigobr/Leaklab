# -*- coding: utf-8 -*-
"""Quando a fila do solver drena, o gancho RECONCILIA label, score e best_action (AY-26, 08/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

A varredura de invariantes acusou 62 decisoes em prod (AUTO): label de erro com `best_action`
igual a jogada e `gto_action` diferente. O realinhamento existia desde 03/09 dentro de
`reconcile_tournament_labels`, mas o gancho que roda quando a fila drena
(`_reconcile_drained_tournaments`) so chamava `resync_tournament_postflop`, que e FILL-ONLY:
preenche gto em quem nao tinha e nao toca em quem ja tinha. Ninguem chamava o reconcile
depois do solve, e o gancho ainda gravava `labels_reconciled_at`, encerrando o assunto.
Reparado em prod com o proprio reconcile (413 decisoes em 46 torneios; AUTO 62 -> 0).

── O que este arquivo defende ─────────────────────────────────────────────────────────────

Um torneio com a fila drenada (spot 'done' mais novo que a ultima reconciliacao) e uma decisao
na contradicao exata: depois do gancho, `best_action` = `gto_action`, e `labels_reconciled_at`
gravado. Sem raw_text de proposito: o resync devolve 0 e o que conserta e o reconcile.
Quebrado de proposito (gancho sem o reconcile), o teste acusa.
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                                  # noqa: E402
from database.repositories import _adapt                                       # noqa: E402


def _semeia():
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users', 'gto_tournament_queue', 'gto_solver_queue'):
        conn.execute('DELETE FROM %s' % t)
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (1,'u','u@e.st','h')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, hero, labels_reconciled_at) "
                        "VALUES (1, 1, 'T1', 'Torneio 1', 'Hero', '2026-09-01 00:00:00')"))
    # a contradicao exata (o padrao dos 62): erro acusado, best = jogada, gto diferente
    conn.execute(_adapt("""INSERT INTO decisions (id, tournament_id, hand_id, street, hero_cards, board, action_taken,
        best_action, gto_action, label, gto_label, score, position, vs_position, stack_bb, pot_size, facing_bet,
        estimated_equity, ev_loss_source, num_players, spot_hash)
        VALUES (1, 1, 'H1', 'turn', 'QsTs', '["3c","Js","Th","Tc"]', 'bet', 'bet', 'check', 'clear_mistake',
        'gto_critical', 0.9, 'BB', 'BTN', 23.7, 5.4, 0.0, 0.5, 'solver_hand', 9, 'spot1')"""))
    # a fila do torneio drenou DEPOIS da ultima reconciliacao
    conn.execute(_adapt("INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (1, 'spot1')"))
    conn.execute(_adapt("INSERT INTO gto_solver_queue (spot_hash, spot_json, status, priority, requested_at, solved_at) "
                        "VALUES ('spot1', '{}', 'done', 0, '2026-09-02 00:00:00', '2026-09-03 00:00:00')"))
    conn.commit(); conn.close()


def test_o_gancho_da_fila_drenada_reconcilia_o_best_action():
    _semeia()
    from api.app import _reconcile_drained_tournaments
    _reconcile_drained_tournaments()
    conn = get_conn()
    d = dict(conn.execute("SELECT best_action, label, gto_action FROM decisions WHERE id=1").fetchone())
    t = dict(conn.execute("SELECT labels_reconciled_at FROM tournaments WHERE id=1").fetchone())
    conn.close()
    assert d['best_action'] == 'check', d          # realinhado ao gto_action: o card para de se contradizer
    assert t['labels_reconciled_at'] and str(t['labels_reconciled_at']) > '2026-09-03', t
    # e o gancho nao roda de novo sem solve novo (nada mais novo que a reconciliacao)
    conn = get_conn(); conn.execute("UPDATE decisions SET best_action='bet' WHERE id=1"); conn.commit(); conn.close()
    _reconcile_drained_tournaments()
    conn = get_conn(); d2 = dict(conn.execute("SELECT best_action FROM decisions WHERE id=1").fetchone()); conn.close()
    assert d2['best_action'] == 'bet', 'sem solve novo o gancho nao deve reprocessar'


def test_o_torneio_drenado_e_reconciliado_mesmo_com_a_fila_global_cheia():
    """Achado em prod (08/09): o gancho so era ALCANCADO quando a fila global zerava, porque com
    `pending > 0` o laco do consumidor fazia `continue` antes dele. Com upload entrando, a fila
    quase nunca zera: 150 torneios drenados esperavam 11h na mediana (21h no pior), com 5.614
    decisoes pos-flop sem veredito. O torneio drena ANTES da fila, e e por torneio que a
    reconciliacao tem de decidir."""
    _semeia()
    conn = get_conn()
    # OUTRO torneio, com spot ainda pendente: a fila GLOBAL nao esta vazia
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, hero) "
                        "VALUES (2, 1, 'T2', 'Torneio 2', 'Hero')"))
    conn.execute(_adapt("INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (2, 'spot2')"))
    conn.execute(_adapt("INSERT INTO gto_solver_queue (spot_hash, spot_json, status, priority, requested_at) "
                        "VALUES ('spot2', '{}', 'pending', 0, '2026-09-02 00:00:00')"))
    conn.commit(); conn.close()
    from api.app import _reconcile_drained_tournaments
    _reconcile_drained_tournaments(limite_s=30)
    conn = get_conn()
    d = dict(conn.execute("SELECT best_action FROM decisions WHERE id=1").fetchone())
    pend = conn.execute("SELECT COUNT(*) AS n FROM gto_solver_queue WHERE status='pending'").fetchone()
    conn.close()
    assert dict(pend)['n'] == 1, 'a fila global tem de continuar com pendencia neste teste'
    assert d['best_action'] == 'check', 'o torneio 1 drenou e tem de ser reconciliado mesmo assim'


def test_o_teto_de_tempo_nao_derruba_a_reconciliacao():
    """O teto existe para nao roubar o consumidor; com teto generoso o comportamento e o mesmo."""
    _semeia()
    from api.app import _reconcile_drained_tournaments
    _reconcile_drained_tournaments(limite_s=0.0)     # teto zerado: nao processa nenhum
    conn = get_conn(); d = dict(conn.execute("SELECT best_action FROM decisions WHERE id=1").fetchone()); conn.close()
    assert d['best_action'] == 'bet', 'com teto 0 o gancho nao deve ter reconciliado nada'
    _reconcile_drained_tournaments(limite_s=60)
    conn = get_conn(); d = dict(conn.execute("SELECT best_action FROM decisions WHERE id=1").fetchone()); conn.close()
    assert d['best_action'] == 'check'


def test_a_reconciliacao_tem_thread_propria_e_nao_depende_do_lote_do_solver():
    """Achado no LOG de producao (09/09), depois de a 1a versao do conserto nao funcionar: com o
    gancho dentro do laco do consumidor, a passagem entrou as 01:20 com 740 pendentes e seguia
    dentro de `run_solver_worker_pool` 25 min depois (50 jobs, concorrencia 2, ~50s por solve).
    Amarrada ali, a reconciliacao rodava no maximo uma vez por lote — e nas 25 min medidas nao
    rodou nenhuma. Reconciliar nao faz parte de solvar; aqui isso vira estrutura, nao comentario."""
    import inspect
    import api.app as app
    assert hasattr(app, '_reconcile_loop'), 'a reconciliacao precisa de laco proprio'
    fonte_loop = inspect.getsource(app._solver_queue_worker_loop)
    antes_do_continue = fonte_loop.split('continue   # re-checa')[0]
    assert '_reconcile_drained_tournaments' not in antes_do_continue,         'a reconciliacao NAO pode voltar para dentro do laco do solver: la ela fica refem do lote'
    # e o consumidor de producao sobe a thread
    raiz = os.path.join(os.path.dirname(__file__), '..')
    consumidor = io.open(os.path.join(raiz, 'run_solver_consumer.py'), encoding='utf-8').read()
    assert '_reconcile_loop' in consumidor and 'Thread(target=_reconcile_loop' in consumidor,         'o consumidor de producao tem de iniciar a thread de reconciliacao'


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for t in testes:
        try:
            t()
            print('OK  %s' % t.__name__)
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (t.__name__, e))
        except Exception as e:                                  # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
