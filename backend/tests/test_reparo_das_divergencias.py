# -*- coding: utf-8 -*-
"""O reparo por usuario: resync + reconcile + registro para desfazer, na ordem do gancho (10/09).

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. **O registro para desfazer e pre-requisito do `--apply`**, nao um extra. O reparo reescreve
   7 campos em milhares de decisoes de gente pagante; sem o antes gravado nao ha volta. Se o
   dump nao sai, o reparo nao acontece.
2. **O recorte e do usuario pedido**, e so dele. O reparo entra em etapas porque cinco pessoas
   concentram tudo e duas sao fundadores; vazar para o torneio de outro usuario quebraria a
   etapa em silencio.
3. **Torneio sem `raw_text` nem entra na lista** — o resync reparseia a mao, e sem o texto ele
   devolveria 0 sem dizer por que.
4. **O reconcile roda depois do resync**, na ordem do gancho. Sem ele, decisao acusada fica com
   `best_action` igual a jogada, o card dizendo "Erro" ao lado de "o ideal era exatamente isso"
   (AY-26, 62 casos em prod).

Quebrado de proposito: sem o dump o `--apply` grava (falha 1), com o recorte de outro usuario
(falha 2), e sem o reconcile o best_action fica desalinhado (falha 4).
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
import scripts.reparo_das_divergencias as rep                                  # noqa: E402

_DUMPDIR = os.path.join(tempfile.gettempdir(), 'rollback_de_teste')

#: (hand_id, street, acao) -> o que a avaliacao FRESCA diz. Dublê do trio parse/pipeline/engine:
#: o que esta sob teste e a orquestracao (recorte, ordem, registro), nao o motor.
_FRESCO = {
    ('H1', 'turn', 'bet'):   {'label': 'correct', 'best': 'bet', 'gto_label': 'gto_correct',
                              'gto_action': 'bet', 'available': True, 'played': 0.71,
                              'top': 0.71, 'ev': 0.0},
    ('H9', 'flop', 'check'): {'label': 'correct', 'best': 'check', 'gto_label': 'gto_correct',
                              'gto_action': 'check', 'available': True, 'played': 0.8,
                              'top': 0.8, 'ev': 0.0},
}


def _instala_duble():
    orig = (rs.parse_hand_history, rs.build_decision_inputs_for_hand, rs.evaluate_decision)
    rs.parse_hand_history = lambda _raw: [
        {'hand_id': h, 'street': s, 'player_action': a} for (h, s, a) in _FRESCO]
    rs.build_decision_inputs_for_hand = lambda hand: [hand]

    def _resp(di):
        v = _FRESCO[(di['hand_id'], di['street'], di['player_action'])]
        return {'evaluation': {'label': v['label']}, 'bestAction': v['best'],
                'gto': {'gto_label': v['gto_label'], 'gto_action': v['gto_action'],
                        'available': v['available'], 'played_freq': v['played'],
                        'gto_freq': v['top'], 'ev_loss_bb': v['ev'],
                        'ev_loss_source': 'solver_hand'}}
    rs.evaluate_decision = _resp

    def _restaura():
        rs.parse_hand_history, rs.build_decision_inputs_for_hand, rs.evaluate_decision = orig
    return _restaura


def _semeia():
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    for uid, nome in ((9001, 'alvo'), (9002, 'outro')):
        conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) "
                            "VALUES (?, ?, ?, 'h')"), (uid, nome, '%s@e.st' % nome))
    # torneio do ALVO (com raw_text), torneio do OUTRO usuario, e um SEM raw_text
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero, raw_text) VALUES (9101, 9001, 'T1', 'do alvo', 'Hero', 'texto')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero, raw_text) VALUES (9102, 9002, 'T2', 'do outro', 'Hero', 'texto')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero) VALUES (9103, 9001, 'T3', 'sem raw_text', 'Hero')"))
    linhas = [
        # do alvo: drift (o no de hoje diz correct, a tela acusa critical)
        (9201, 9101, 'H1', 'turn', 'bet', 'clear_mistake', 'check', 'gto_critical', 'check'),
        # do OUTRO usuario: a mesma divergencia, e nao pode ser tocada nesta etapa
        (9202, 9102, 'H1', 'turn', 'bet', 'clear_mistake', 'check', 'gto_critical', 'check'),
        # do alvo, no torneio SEM raw_text: fora do alcance do resync
        (9203, 9103, 'H1', 'turn', 'bet', 'clear_mistake', 'check', 'gto_critical', 'check'),
        # do alvo: a contradicao do AY-26 (best = jogada, gto diferente) — quem conserta e o
        # reconcile, nao o resync: a mao H9 nao esta no `_FRESCO` com esta acao
        (9204, 9101, 'H9', 'flop', 'bet', 'clear_mistake', 'bet', 'gto_critical', 'check'),
    ]
    for did, tid, hid, st, act, label, best, gl, ga in linhas:
        conn.execute(_adapt(
            "INSERT INTO decisions (id, tournament_id, hand_id, street, hero_cards, board, "
            "action_taken, best_action, gto_action, label, gto_label, score, position, "
            "vs_position, stack_bb, pot_size, facing_bet, estimated_equity, num_players, "
            "spot_hash) VALUES (?, ?, ?, ?, 'QsTs', '[\"3c\",\"Js\",\"Th\"]', ?, ?, ?, ?, ?, "
            "0.9, 'BB', 'BTN', 23.7, 5.4, 0.0, 0.5, 9, ?)"),
            (did, tid, hid, st, act, best, ga, label, gl, 'spot-%s' % did))
    conn.commit(); conn.close()


def _ler(did):
    conn = get_conn()
    r = dict(conn.execute(_adapt("SELECT label, best_action, gto_label, gto_action FROM decisions "
                                 "WHERE id=?"), (did,)).fetchone())
    conn.close()
    return r


def _roda(*extra):
    argv = sys.argv
    sys.argv = ['reparo_das_divergencias.py'] + list(extra)
    try:
        rep.main()
    finally:
        sys.argv = argv


def test_repara_so_o_usuario_pedido_e_grava_o_registro():
    _semeia()
    restaura = _instala_duble()
    try:
        _roda('--user', '9001', '--apply', '--dump-dir', _DUMPDIR)
    finally:
        restaura()
    assert _ler(9201)['gto_label'] == 'gto_correct', _ler(9201)          # o alvo foi reparado
    assert _ler(9202)['gto_label'] == 'gto_critical', (
        'a etapa vazou para o torneio de OUTRO usuario', _ler(9202))
    assert _ler(9203)['gto_label'] == 'gto_critical', (
        'torneio sem raw_text nao e alcancavel pelo resync', _ler(9203))
    caminho = os.path.join(_DUMPDIR, 'u9001_preserva.jsonl')
    assert os.path.exists(caminho), 'o registro para desfazer nao foi gravado'
    linhas = [json.loads(l) for l in io.open(caminho, encoding='utf-8') if l.strip()]
    assert linhas, 'registro vazio: nao ha como desfazer'
    d = [x for x in linhas if x['id'] == 9201]
    assert d and d[0]['de']['gto_label'] == 'gto_critical', d            # o ANTES esta la
    assert d[0]['para']['gto_label'] == 'gto_correct', d


def test_o_reconcile_roda_depois_do_resync():
    """AY-26: sem o reconcile, decisao acusada fica com `best_action` igual a jogada, e o card
    diz "Erro" ao lado de "o ideal era exatamente isso". A decisao 9204 esta nessa contradicao e
    o resync nao a alcanca (a mao/acao dela nao vem na avaliacao fresca)."""
    _semeia()
    antes = _ler(9204)
    assert antes['best_action'] == antes['action_taken'] if 'action_taken' in antes else True
    restaura = _instala_duble()
    try:
        _roda('--user', '9001', '--apply', '--dump-dir', _DUMPDIR)
    finally:
        restaura()
    d = _ler(9204)
    assert d['best_action'] == 'check', ('o reconcile tem de realinhar o best_action', d)


def test_o_registro_cobre_tambem_o_que_o_reconcile_mudou():
    """O furo achado em 10/09 aplicando na minha propria conta: o resync gravou 168 linhas e o
    `reconcile_tournament_labels` mexeu em ~180 OUTRAS, que o registro nao cobria. Registro que
    cobre metade da escrita nao e registro, e reverter deixaria o resto no meio do caminho.

    A decisao 9204 esta na contradicao do AY-26 e o resync NAO a alcanca (a mao/acao dela nao vem
    na avaliacao fresca): quem a conserta e o reconcile. Entao ela e a prova — tem de aparecer no
    arquivo com `natureza='reconcile'` e com o ANTES do lado certo.
    """
    _semeia()
    restaura = _instala_duble()
    try:
        _roda('--user', '9001', '--apply', '--dump-dir', _DUMPDIR)
    finally:
        restaura()
    caminho = os.path.join(_DUMPDIR, 'u9001_preserva.jsonl')
    linhas = [json.loads(l) for l in io.open(caminho, encoding='utf-8') if l.strip()]
    rec = [x for x in linhas if x['id'] == 9204]
    assert rec, ('a linha que SO o reconcile mexeu ficou fora do registro', [x['id'] for x in linhas])
    x = rec[0]
    assert x['natureza'] == 'reconcile', x
    assert x['de']['best'] == 'bet', ('o ANTES tem de ser o estado anterior ao reconcile', x)
    assert x['para']['best'] == 'check', x
    assert 'score' in x['de'] and 'score' in x['para'], (
        'o score viaja junto: o reconcile o re-deriva do label', x)


def test_dry_run_nao_escreve_e_nao_exige_registro():
    _semeia()
    restaura = _instala_duble()
    try:
        _roda('--user', '9001')
    finally:
        restaura()
    assert _ler(9201)['gto_label'] == 'gto_critical', 'dry-run gravou'


def test_o_recorte_ignora_torneio_sem_decisao_postflop():
    _semeia()
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, "
                        "hero, raw_text) VALUES (9104, 9001, 'T4', 'so preflop', 'Hero', 'x')"))
    conn.execute(_adapt(
        "INSERT INTO decisions (id, tournament_id, hand_id, street, hero_cards, board, "
        "action_taken, best_action, label, score, position, num_players, spot_hash) "
        "VALUES (9205, 9104, 'H5', 'preflop', 'QsTs', '[]', 'raise', 'raise', 'correct', "
        "0.9, 'BB', 9, 'spot-9205')"))
    conn.commit(); conn.close()
    assert 9104 not in rep.torneios_do_usuario(9001), 'torneio so-preflop nao deveria entrar'
    assert 9101 in rep.torneios_do_usuario(9001)
    assert 9102 not in rep.torneios_do_usuario(9001), 'torneio de outro usuario no recorte'


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
