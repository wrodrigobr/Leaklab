# -*- coding: utf-8 -*-
"""Ritual da sessão: a promessa selada no check-in, o balanço honesto no debriefing.

── O que estes guardas fixam (30/08) ────────────────────────────────────────────────────────

1. A linha de base do foco é SELADA no check-in — o debriefing compara contra a régua do
   momento da promessa, não contra um histórico que se moveu (o princípio do gabarito vetado).
2. Sem amostra não há promessa: foco só com FOCO_MIN_AMOSTRA; sessão sem spot da família
   devolve taxa None, nunca 0% (que afirmaria promessa cumprida sem evidência).
3. Debriefing sem check-in ainda serve (mão gatilho + caras) — só a promessa fica de fora.
4. Fechar é ato explícito do jogador, nunca efeito de leitura.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('LEAKLAB_TESTING', '1')


def _banco():
    from database.schema import init_db
    init_db()


def _semeia(n_erros_flop_fold=6, n_ok=4):
    """Usuário com histórico: decisões flop/fold com erros — o leak que vira foco."""
    from database.repositories import create_user, _adapt
    from database.schema import get_conn
    m = uuid.uuid4().hex[:8]
    uid = create_user('rit_' + m, 'rit_%s@t.local' % m, 'x' * 12)
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, site, hero) VALUES (?,?,?,?)"),
            (uid, 'TH' + m, 'PokerStars', 'h'))
        tid_hist = dict(conn.execute(_adapt(
            'SELECT id FROM tournaments WHERE tournament_id = ?'), ('TH' + m,)).fetchone())['id']
        for i in range(n_erros_flop_fold):
            conn.execute(_adapt(
                "INSERT INTO decisions (tournament_id, hand_id, street, position, hero_cards, "
                "action_taken, best_action, label, score, ev_loss_bb) VALUES (?,?,?,?,?,?,?,?,?,?)"),
                (tid_hist, 'E%d' % i, 'flop', 'BB', 'AhKd', 'call', 'fold',
                 'clear_mistake', 0.8, 3.5))
        for i in range(n_ok):
            conn.execute(_adapt(
                "INSERT INTO decisions (tournament_id, hand_id, street, position, hero_cards, "
                "action_taken, best_action, label, score) VALUES (?,?,?,?,?,?,?,?,?)"),
                (tid_hist, 'O%d' % i, 'flop', 'BB', 'AhKd', 'fold', 'fold', 'correct', 0.0))
        conn.commit()
    finally:
        conn.close()
    return uid, tid_hist, m


def _torneio_novo(uid, m, decisoes):
    """decisoes: lista de (street, action, best, label, ev_loss)."""
    from database.repositories import _adapt
    from database.schema import get_conn
    conn = get_conn()
    try:
        conn.execute(_adapt(
            "INSERT INTO tournaments (user_id, tournament_id, site, hero) VALUES (?,?,?,?)"),
            (uid, 'TN' + m, 'PokerStars', 'h'))
        tid = dict(conn.execute(_adapt(
            'SELECT id FROM tournaments WHERE tournament_id = ?'), ('TN' + m,)).fetchone())['id']
        for i, (st, act, best, label, ev) in enumerate(decisoes):
            conn.execute(_adapt(
                "INSERT INTO decisions (tournament_id, hand_id, street, position, hero_cards, "
                "action_taken, best_action, label, score, ev_loss_bb) VALUES (?,?,?,?,?,?,?,?,?,?)"),
                (tid, 'N%d' % i, st, 'BB', 'QhQd', act, best, label,
                 0.5 if label != 'correct' else 0.0, ev))
        conn.commit()
    finally:
        conn.close()
    return tid


def test_foco_sugerido_sai_do_leak_mais_caro_COM_amostra():
    _banco()
    from leaklab.ritual_da_sessao import sugerir_foco
    uid, _tid, _m = _semeia(n_erros_flop_fold=6)
    foco = sugerir_foco(uid)
    assert foco and foco['spot'] == 'flop/fold', foco
    assert foco['n'] >= 5
    print('OK  test_foco_sugerido_sai_do_leak_mais_caro_COM_amostra')


def test_sem_amostra_NAO_ha_foco():
    """Jogador com 2 erros não recebe 'correção' — seria ruído vestido de diagnóstico."""
    _banco()
    from leaklab.ritual_da_sessao import sugerir_foco
    uid, _tid, _m = _semeia(n_erros_flop_fold=2, n_ok=0)
    assert sugerir_foco(uid) is None
    print('OK  test_sem_amostra_NAO_ha_foco')


def test_a_base_e_SELADA_no_checkin():
    """O princípio do gabarito vetado: jogar mais mãos DEPOIS do check-in não move a régua
    da promessa."""
    _banco()
    from leaklab.ritual_da_sessao import abrir_checkin, debrief
    uid, _tid, m = _semeia(n_erros_flop_fold=6, n_ok=4)     # base: 6 erros em 10
    ck = abrir_checkin(uid, bankroll_ok=True, foco_spot='flop/fold')
    assert ck['base_n'] == 10 and ck['base_erros'] == 6, ck
    # a sessão nova tem 1 erro em 4 spots do foco — e NÃO pode contaminar a base selada
    tid_novo = _torneio_novo(uid, m, [
        ('flop', 'fold', 'fold', 'correct', None),
        ('flop', 'fold', 'fold', 'correct', None),
        ('flop', 'fold', 'fold', 'correct', None),
        ('flop', 'call', 'fold', 'clear_mistake', 2.0),
        ('river', 'call', 'call', 'correct', None),
    ])
    d = debrief(uid, tid_novo)
    assert d['foco']['base'] == {'n': 10, 'erros': 6, 'taxa': 0.6}, (
        'a base moveu depois do check-in: %s' % d['foco']['base'])
    assert d['foco']['sessao'] == {'n': 4, 'erros': 1}
    assert d['foco']['taxa_sessao'] == 0.25
    print('OK  test_a_base_e_SELADA_no_checkin')


def test_sessao_sem_spot_do_foco_devolve_None_nao_zero():
    """0% afirmaria promessa cumprida sem evidência; None diz 'não apareceu spot do foco'."""
    _banco()
    from leaklab.ritual_da_sessao import abrir_checkin, debrief
    uid, _tid, m = _semeia()
    abrir_checkin(uid, bankroll_ok=None, foco_spot='flop/fold')
    tid_novo = _torneio_novo(uid, m, [('preflop', 'raise', 'raise', 'correct', None)])
    d = debrief(uid, tid_novo)
    assert d['foco']['taxa_sessao'] is None, d['foco']
    assert d['foco']['sessao']['n'] == 0
    print('OK  test_sessao_sem_spot_do_foco_devolve_None_nao_zero')


def test_debrief_sem_checkin_ainda_serve():
    """Mão gatilho e mãos caras não dependem de promessa."""
    _banco()
    from leaklab.ritual_da_sessao import debrief
    uid, _tid, m = _semeia()
    tid_novo = _torneio_novo(uid, m, [
        ('flop', 'call', 'fold', 'clear_mistake', 5.0),
        ('turn', 'call', 'fold', 'small_mistake', 1.2),
    ])
    d = debrief(uid, tid_novo)
    assert 'foco' not in d
    assert d['mao_gatilho']['ev_loss_bb'] == 5.0, 'a gatilho nao e a mais cara'
    assert len(d['maos_caras']) == 2
    print('OK  test_debrief_sem_checkin_ainda_serve')


def test_torneio_de_outro_devolve_None():
    _banco()
    from leaklab.ritual_da_sessao import debrief
    uid_a, tid_a, _m = _semeia()
    uid_b, _tid_b, _m2 = _semeia()
    assert debrief(uid_b, tid_a) is None, 'debriefing vazou torneio de outro usuario'
    print('OK  test_torneio_de_outro_devolve_None')


def test_fechar_e_ato_explicito_e_novo_checkin_substitui():
    _banco()
    from leaklab.ritual_da_sessao import (abrir_checkin, checkin_aberto, debrief,
                                          fechar_checkin)
    uid, _tid, m = _semeia()
    ck1 = abrir_checkin(uid, True, 'flop/fold')
    ck2 = abrir_checkin(uid, True, 'flop/fold')
    assert ck2['id'] != ck1['id'] and checkin_aberto(uid)['id'] == ck2['id'], (
        'novo check-in nao substituiu o anterior')
    tid_novo = _torneio_novo(uid, m, [('flop', 'call', 'fold', 'clear_mistake', 1.0)])
    debrief(uid, tid_novo)                       # LER não fecha
    assert checkin_aberto(uid) is not None, 'o debrief de leitura fechou o check-in sozinho'
    assert fechar_checkin(uid, ck2['id'], tid_novo) is True
    assert checkin_aberto(uid) is None
    assert fechar_checkin(uid, ck2['id'], tid_novo) is False, 'fechar duas vezes devolveu True'
    print('OK  test_fechar_e_ato_explicito_e_novo_checkin_substitui')


if __name__ == '__main__':
    falhas = 0
    testes = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for teste in testes:
        try:
            teste()
        except AssertionError as e:
            falhas += 1
            print('FALHOU  %s: %s' % (teste.__name__, e))
        except Exception as e:                              # noqa: BLE001
            falhas += 1
            print('ERRO    %s: %s: %s' % (teste.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
