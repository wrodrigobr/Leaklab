# -*- coding: utf-8 -*-
"""O gancho da fila drenada corrige rotulo velho, e nunca apaga veredito (10/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

A amostra do AY-29 mostrou o CONTROLE falhando em 21 de 50: decisoes marcadas `gto_critical`
com o proprio no gravado dizendo `gto_correct`. A varredura na base inteira mediu o tamanho:
1.179 decisoes pos-flop com `gto_label` diferente do que o no de hoje produz (14,3% das
comparaveis, com o controle da sonda em 97%), 166 delas ACUSANDO na tela sem o no sustentar,
92% com o no mais novo que a decisao.

A causa nao era o assento: era o gancho. `_reconcile_drained_tournaments` chamava
`resync_tournament_postflop`, que era FILL-ONLY por desenho — so rotulava quem estava sem
veredito e nunca tocava em quem ja tinha. O `label_drift` (no que JA existia e mudou de
resposta ao ser re-solvado) e exatamente o caso que o fill-only pula, e o gancho gravava
`labels_reconciled_at` em seguida, encerrando o assunto. Reparar as 1.179 a mao sem consertar o
gancho so adiaria: cada re-solve produz drift novo.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

A CONDICAO, nao o efeito: um torneio com as tres naturezas semeadas ao mesmo tempo.

  drift    — banco `gto_critical`, avaliacao fresca `gto_correct`  -> tem de virar `gto_correct`
  vanished — banco `gto_correct`, avaliacao fresca sem gto          -> tem de FICAR `gto_correct`
  appeared — banco sem gto, avaliacao fresca `gto_mixed`            -> tem de ser preenchido

A avaliacao fresca e injetada (parse/pipeline/engine dublados) porque o que esta sob teste e a
REGRA DE GRAVACAO, nao o motor: com o motor de verdade o teste dependeria de ter no de solver
para um board especifico, e passaria a medir outra coisa.

Quebrado de proposito (`grava_esta` devolvendo a regra fill-only), o teste acusa nos dois
caminhos — o resync direto e o gancho.
"""
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


#: (hand_id, street, acao) -> o que a avaliacao FRESCA diz. E o dublê do trio
#: parse -> pipeline -> engine; o formato e o que `_avaliacao_fresca` consome.
_FRESCO = {
    ('H1', 'turn', 'bet'):    {'label': 'correct',       'best': 'bet',
                               'gto_label': 'gto_correct', 'gto_action': 'bet',
                               'available': True, 'played': 0.71, 'top': 0.71, 'ev': 0.0},
    ('H2', 'flop', 'check'):  {'label': 'correct',       'best': 'check',
                               'gto_label': None,          'gto_action': None,
                               'available': False, 'played': None, 'top': None, 'ev': None},
    ('H3', 'river', 'call'):  {'label': 'small_mistake', 'best': 'fold',
                               'gto_label': 'gto_mixed',   'gto_action': 'fold',
                               'available': True, 'played': 0.31, 'top': 0.52, 'ev': 0.4},
}


def _instala_duble():
    """Substitui parse/pipeline/engine por fontes de `_FRESCO`. Devolve o restaurador."""
    orig = (rs.parse_hand_history, rs.build_decision_inputs_for_hand, rs.evaluate_decision)
    rs.parse_hand_history = lambda _raw: [
        {'hand_id': hid, 'street': st, 'player_action': act} for (hid, st, act) in _FRESCO]
    rs.build_decision_inputs_for_hand = lambda hand: [hand]
    rs.evaluate_decision = lambda di: _resposta(di)

    def _restaura():
        rs.parse_hand_history, rs.build_decision_inputs_for_hand, rs.evaluate_decision = orig
    return _restaura


def _resposta(di):
    v = _FRESCO[(di['hand_id'], di['street'], di['player_action'])]
    return {
        'evaluation': {'label': v['label']},
        'bestAction': v['best'],
        'gto': {'gto_label': v['gto_label'], 'gto_action': v['gto_action'],
                'available': v['available'], 'played_freq': v['played'],
                'gto_freq': v['top'], 'ev_loss_bb': v['ev'],
                'ev_loss_source': 'solver_hand' if v['available'] else None},
    }


def _semeia():
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users', 'gto_tournament_queue', 'gto_solver_queue'):
        conn.execute('DELETE FROM %s' % t)
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                        "VALUES (1,'u','u@e.st','h')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero, raw_text, labels_reconciled_at) "
                        "VALUES (1, 1, 'T1', 'Torneio 1', 'Hero', 'texto qualquer', "
                        "'2026-09-01 00:00:00')"))
    linhas = [
        # DRIFT: o no de hoje diz gto_correct, a tela ainda acusa gto_critical
        (1, 'H1', 'turn',  'bet',   'clear_mistake', 'check', 'gto_critical', 'check'),
        # VANISHED: a avaliacao fresca nao tem gto; o veredito NAO pode ser apagado pelo gancho
        (2, 'H2', 'flop',  'check', 'correct',       'check', 'gto_correct',  'check'),
        # APPEARED: sem veredito no banco (mas COM label do caminho sem gto, que e NOT NULL),
        # e com no agora
        (3, 'H3', 'river', 'call',  'correct',       'call',  None,           None),
    ]
    for did, hid, st, act, label, best, gl, ga in linhas:
        conn.execute(_adapt(
            "INSERT INTO decisions (id, tournament_id, hand_id, street, hero_cards, board, "
            "action_taken, best_action, gto_action, label, gto_label, score, position, "
            "vs_position, stack_bb, pot_size, facing_bet, estimated_equity, num_players, "
            "spot_hash) VALUES (?, 1, ?, ?, 'QsTs', '[\"3c\",\"Js\",\"Th\"]', ?, ?, ?, ?, ?, "
            "0.9, 'BB', 'BTN', 23.7, 5.4, 0.0, 0.5, 9, 'spot1')"),
            (did, hid, st, act, best, ga, label, gl))
    # a fila do torneio drenou DEPOIS da ultima reconciliacao (o gancho precisa disto para achar)
    conn.execute(_adapt("INSERT INTO gto_tournament_queue (tournament_id, spot_hash) "
                        "VALUES (1, 'spot1')"))
    conn.execute(_adapt("INSERT INTO gto_solver_queue (spot_hash, spot_json, status, priority, "
                        "requested_at, solved_at) VALUES ('spot1', '{}', 'done', 0, "
                        "'2026-09-02 00:00:00', '2026-09-03 00:00:00')"))
    conn.commit(); conn.close()


def _gto():
    conn = get_conn()
    rows = {dict(r)['id']: dict(r) for r in conn.execute(
        "SELECT id, gto_label, gto_action, label, best_action, gto_played_freq, ev_loss_bb "
        "FROM decisions ORDER BY id").fetchall()}
    conn.close()
    return rows


def test_o_resync_corrige_o_rotulo_que_o_no_nao_sustenta_mais():
    _semeia()
    restaura = _instala_duble()
    try:
        n = rs.resync_tournament_postflop(1, apply=True)
    finally:
        restaura()
    d = _gto()
    assert d[1]['gto_label'] == 'gto_correct', d[1]     # drift corrigido: a acusacao SAI da tela
    assert d[1]['gto_action'] == 'bet', d[1]            # os campos viajam juntos
    assert d[1]['label'] == 'correct', d[1]
    assert round(float(d[1]['gto_played_freq']), 2) == 0.71, d[1]
    assert d[3]['gto_label'] == 'gto_mixed', d[3]       # appeared continua sendo preenchido
    assert n == 2, ('drift + appeared, e nada mais', n)


def test_o_resync_nunca_apaga_veredito_existente():
    """Regra 7: o conserto nao pode causar dano que o bug nao causava. O bug deixava rotulo
    velho na tela; tirar o veredito de quem tem um e outra decisao (as 727 `vanished` medidas em
    10/09), e nao cabe a um gancho automatico tomar."""
    _semeia()
    restaura = _instala_duble()
    try:
        rs.resync_tournament_postflop(1, apply=True)
    finally:
        restaura()
    d = _gto()
    assert d[2]['gto_label'] == 'gto_correct', ('vanished: o veredito tem de ficar', d[2])
    assert d[2]['gto_action'] == 'check', d[2]


def test_o_modo_fill_continua_existindo_e_pula_o_drift():
    """Os tres modos tem de ser DISTINGUIVEIS: se `MODO_FILL` tambem corrigisse o drift, o teste
    de cima passaria com a regra colada em qualquer modo e nao provaria nada."""
    _semeia()
    restaura = _instala_duble()
    try:
        n = rs.resync_tournament_postflop(1, apply=True, modo=rs.MODO_FILL)
    finally:
        restaura()
    d = _gto()
    assert d[1]['gto_label'] == 'gto_critical', ('fill-only nao mexe em quem tem veredito', d[1])
    assert d[3]['gto_label'] == 'gto_mixed', d[3]
    assert n == 1, ('so o appeared', n)


def test_a_natureza_e_a_regra_de_gravacao_sao_uma_funcao_so():
    """A regra vivia em dois lugares (flag do CLI e `if` cravado no resync por torneio), e foi a
    divergencia entre eles que deixou o gancho no modo mais conservador sem ninguem escolher."""
    banco = {'gto_label': 'gto_critical', 'gto_action': 'check'}
    fresco = {'gto_label': 'gto_correct', 'gto_action': 'bet'}
    assert rs.natureza_da_mudanca(banco, fresco) == 'label_drift'
    assert rs.natureza_da_mudanca(banco, {'gto_label': None, 'gto_action': None}) == 'vanished'
    assert rs.natureza_da_mudanca({'gto_label': None, 'gto_action': None}, fresco) == 'appeared'
    assert rs.natureza_da_mudanca(banco, dict(banco, gto_action='bet')) == 'action_only'
    assert rs.natureza_da_mudanca(banco, dict(banco)) is None
    assert rs.grava_esta('label_drift', rs.MODO_PRESERVA) is True
    assert rs.grava_esta('vanished', rs.MODO_PRESERVA) is False
    assert rs.grava_esta('vanished', rs.MODO_TOTAL) is True
    assert rs.grava_esta('label_drift', rs.MODO_FILL) is False
    try:
        rs.grava_esta('label_drift', 'modo_que_nao_existe')
    except ValueError:
        pass
    else:
        raise AssertionError('modo desconhecido tem de estourar, nao virar default silencioso')


def test_o_gancho_da_fila_drenada_usa_o_modo_que_corrige_o_drift():
    """O caminho de producao inteiro: o gancho acha o torneio drenado e o rotulo velho sai."""
    _semeia()
    restaura = _instala_duble()
    try:
        from api.app import _reconcile_drained_tournaments
        _reconcile_drained_tournaments()
    finally:
        restaura()
    d = _gto()
    assert d[1]['gto_label'] == 'gto_correct', ('o gancho tem de corrigir o drift', d[1])
    assert d[2]['gto_label'] == 'gto_correct', ('e nao pode apagar veredito', d[2])
    assert d[3]['gto_label'] == 'gto_mixed', d[3]
    conn = get_conn()
    t = dict(conn.execute("SELECT labels_reconciled_at FROM tournaments WHERE id=1").fetchone())
    conn.close()
    assert t['labels_reconciled_at'] and str(t['labels_reconciled_at']) > '2026-09-03', t


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
