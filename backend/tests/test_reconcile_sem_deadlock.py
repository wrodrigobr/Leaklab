# -*- coding: utf-8 -*-
"""O gancho nao pode ter duas passagens ao mesmo tempo, nem gravar fora de ordem (11/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Producao, horas depois do deploy que trocou o gancho de fill-only para `MODO_PRESERVA`:

    DeadlockDetected: Process 20393 waits for ShareLock on transaction 836930; blocked by 14055.
    Process 14055 waits for ShareLock on transaction 836929; blocked by 20393.
    while updating tuple (4382,24) in relation "decisions"
      api/app.py in _reconcile_drained_tournaments
      scripts/resync_postflop_gto.py in resync_tournament_postflop

Causa, achada no codigo: `_reconcile_drained_tournaments` tem DOIS chamadores em threads
diferentes do mesmo processo — `_reconcile_loop` (a cada 120s) e `_solver_queue_worker_loop`
quando a fila esvazia. As duas pegam a mesma lista de torneios drenados e escrevem as MESMAS
linhas de `decisions`, cada uma na sua transacao. O `MODO_PRESERVA` tornou isso provavel: onde o
fill-only escrevia quase nada, ele escreve centenas de linhas por torneio.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

Deadlock nao reaparece em teste por acaso, entao os guardas nao tentam reproduzi-lo: eles
ancoram nas duas CONDICOES que o tornam possivel.

1. **Uma passagem por vez.** Com uma passagem em curso, a segunda chamada desiste na hora, sem
   duplicar trabalho. Testado com o lock tomado de fora.
2. **Ordem deterministica de gravacao.** As linhas saem em ordem CRESCENTE de `decisions.id`,
   qualquer que seja a ordem das chaves `(hand_id, street, acao)` no dict. Dois escritores que
   travam na mesma ordem nao formam ciclo — e isto vale tambem entre PROCESSOS, onde nenhum lock
   de thread alcanca.

Quebrados de proposito: sem o lock, a segunda passagem entra; sem o `sort`, a ordem sai pela
chave e o teste acusa mostrando a sequencia.
"""
import io
import json
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
import scripts.resync_postflop_gto as rs                                       # noqa: E402

_DUMP = os.path.join(tempfile.gettempdir(), 'ordem_do_resync.jsonl')

#: A semente tem de produzir ordem de dict DIFERENTE da ordem de id, senao o guarda passa por
#: acaso — foi o que aconteceu na 1a versao deste arquivo, e a quebra de proposito pegou. O
#: `stored` e preenchido lendo `ORDER BY id`, entao com UMA linha por chave a ordem ja sai
#: crescente e o `sort` seria decorativo.
#:
#: A ordem so difere quando a MESMA chave tem duas linhas, que e o caso real do
#: `_pares_por_ordem`: o heroi age duas vezes na mesma street com a mesma acao (paga um open e
#: depois enfrenta um 3-bet). Aqui:
#:   ids 9301 e 9303 sao a chave (H1, turn, check); 9302 e (H2, flop, bet).
#:   O dict itera H1 primeiro (veio do 9301), entao sem `sort` a gravacao sai 9301, 9303, 9302.
_DIS = [
    {'hand_id': 'H1', 'street': 'turn', 'player_action': 'check'},
    {'hand_id': 'H2', 'street': 'flop', 'player_action': 'bet'},
    {'hand_id': 'H1', 'street': 'turn', 'player_action': 'check'},
]
#: (id, hand_id, street, acao) na ordem de gravacao no banco
_LINHAS = [(9301, 'H1', 'turn', 'check'), (9302, 'H2', 'flop', 'bet'),
           (9303, 'H1', 'turn', 'check')]


def _instala_duble():
    orig = (rs.parse_hand_history, rs.build_decision_inputs_for_hand, rs.evaluate_decision)
    # uma "mao" por di, na ORDEM cronologica que o pipeline devolveria
    rs.parse_hand_history = lambda _raw: list(_DIS)
    rs.build_decision_inputs_for_hand = lambda hand: [hand]

    def _resp(di):
        return {'evaluation': {'label': 'correct'}, 'bestAction': di['player_action'],
                'gto': {'gto_label': 'gto_correct', 'gto_action': di['player_action'],
                        'available': True, 'played_freq': 0.8, 'gto_freq': 0.8,
                        'ev_loss_bb': 0.0, 'ev_loss_source': 'solver_hand'}}
    rs.evaluate_decision = _resp

    def _restaura():
        rs.parse_hand_history, rs.build_decision_inputs_for_hand, rs.evaluate_decision = orig
    return _restaura


def _semeia():
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                        "VALUES (9301,'u','u@e.st','h')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero, raw_text) VALUES (9301, 9301, 'T1', 'T', 'Hero', 'texto')"))
    for did, hid, st, act in _LINHAS:
        conn.execute(_adapt(
            "INSERT INTO decisions (id, tournament_id, hand_id, street, hero_cards, board, "
            "action_taken, best_action, gto_action, label, gto_label, score, position, "
            "num_players, spot_hash) VALUES (?, 9301, ?, ?, 'QsTs', '[\"3c\",\"Js\",\"Th\"]', "
            "?, 'x', 'x', 'clear_mistake', 'gto_critical', 0.9, 'BB', 9, ?)"),
            (did, hid, st, act, 'spot-%s' % did))
    conn.commit(); conn.close()


def test_as_linhas_sao_gravadas_em_ordem_CRESCENTE_de_id():
    """A ordem de lock e o que impede o ciclo entre dois escritores — inclusive entre PROCESSOS,
    onde lock de thread nao alcanca. O dump registra uma linha por gravacao, na ordem em que
    aconteceram, entao ele e a prova."""
    _semeia()
    restaura = _instala_duble()
    try:
        with io.open(_DUMP, 'w', encoding='utf-8', newline='\n') as fh:
            n = rs.resync_tournament_postflop(9301, apply=True, modo=rs.MODO_PRESERVA, dump=fh)
    finally:
        restaura()
    assert n == 3, n
    ids = [json.loads(l)['id'] for l in io.open(_DUMP, encoding='utf-8') if l.strip()]
    assert ids == sorted(ids), ('as linhas sairam fora de ordem de id', ids)
    assert ids == [9301, 9302, 9303], ids


def test_uma_passagem_por_vez_e_a_segunda_DESISTE():
    """Com uma passagem em curso, a segunda chamada volta na hora. Ela nao perde trabalho: a
    lista de candidatos e guardada por `labels_reconciled_at` e o que sobrar entra na proxima."""
    _semeia()
    import api.app as app
    assert hasattr(app, '_RECONCILE_EM_CURSO'), 'o lock da passagem desapareceu'
    assert hasattr(app, '_reconcile_drained_impl'), 'o corpo separado desapareceu'

    chamou = []
    orig = app._reconcile_drained_impl
    app._reconcile_drained_impl = lambda limite_s=None: chamou.append(1)
    try:
        # sem ninguem segurando, a passagem roda
        app._reconcile_drained_tournaments()
        assert chamou == [1], chamou
        # com o lock tomado (a outra thread), a chamada desiste sem executar o corpo
        assert app._RECONCILE_EM_CURSO.acquire(blocking=False)
        try:
            app._reconcile_drained_tournaments()
        finally:
            app._RECONCILE_EM_CURSO.release()
        assert chamou == [1], ('a segunda passagem NAO deveria ter rodado', chamou)
        # e depois de liberar, volta a rodar
        app._reconcile_drained_tournaments()
        assert chamou == [1, 1], chamou
    finally:
        app._reconcile_drained_impl = orig


def test_o_lock_e_liberado_mesmo_quando_a_passagem_ESTOURA():
    """Guarda que se desarma sozinha (licao propria): se o corpo levanta e o lock nao volta, a
    reconciliacao morre para sempre no processo, em silencio — pior que o deadlock."""
    _semeia()
    import api.app as app
    orig = app._reconcile_drained_impl

    def _estoura(limite_s=None):
        raise RuntimeError('falha de proposito')
    app._reconcile_drained_impl = _estoura
    try:
        try:
            app._reconcile_drained_tournaments()
        except RuntimeError:
            pass
        assert app._RECONCILE_EM_CURSO.acquire(blocking=False), (
            'o lock ficou preso depois de uma falha: a reconciliacao nunca mais roda')
        app._RECONCILE_EM_CURSO.release()
    finally:
        app._reconcile_drained_impl = orig


def test_os_DOIS_chamadores_continuam_existindo():
    """O conserto nao pode ter sido "tirar um dos chamadores": os dois existem por razoes
    diferentes. O laco proprio garante cadencia mesmo com o solver ocupado (achado de 09/09, 25
    min sem reconciliar); a chamada do laco do solver fecha o que sobrou quando a fila esvazia.
    O que estava errado era eles se atropelarem, nao existirem."""
    import inspect
    import api.app as app
    assert 'reconcile' in inspect.getsource(app._reconcile_loop)
    fonte = inspect.getsource(app._solver_queue_worker_loop)
    assert '_reconcile_drained_tournaments' in fonte, (
        'a chamada do laco do solver desapareceu: o conserto era a exclusao mutua, nao remover')


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
