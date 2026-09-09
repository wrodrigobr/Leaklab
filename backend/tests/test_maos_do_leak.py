# -*- coding: utf-8 -*-
"""As maos de um leak reconciliam com a linha do card (AY-32, 09/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Um fundador, olhando o card "Leaks por custo": *"e possivel cada uma dessas linhas ser
clicavel, e mostrar a lista de maos em que esta situacao ocorreu? e nesta lista conseguirmos
abrir o replayer pra ver o que fizemos, e os vereditos do solver?"*.

Parecia so ligar `get_decisions_for_spot`, que ja existe e alimenta o plano de estudos. Nao
serve, por tres motivos: ela filtra por (street, ASSENTO) e nao pelo par de acoes; aceita mao
por `gto_label` mesmo sem custo em bb; e nao passa pela regua `ev_loss_trustworthy`. Ligada na
tela, traria maos de outros pares de acao e a lista nao fecharia com o `count` da linha.

"Lista e card com duas politicas para a mesma pergunta" e defeito que este projeto ja pagou
caro: sem a regua, este MESMO card publicou 7.669 bb/100 onde o numero honesto era 9,8.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

A RECONCILIACAO, que e a unica coisa que impede a tela de mentir: para toda linha do card, a
lista tem o mesmo numero de maos e a mesma soma de bb. Mais: a lista nao mistura par de acao,
respeita o mesmo recorte de torneios, e a paginacao nao muda o total.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                                   # noqa: E402
from database.repositories import (_adapt, get_ev_summary, get_maos_do_leak)    # noqa: E402


def _semeia(decisoes):
    """decisoes = [(street, action_taken, best_action, ev_loss_bb, stack_bb)]"""
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (1,'u','u@e.st','h')"))
    for tid in (1, 2):
        conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, tournament_name, hero, played_at, imported_at) "
                            "VALUES (?, 1, ?, ?, 'Hero', datetime('now'), datetime('now'))"),
                     (tid, 'T%d' % tid, 'Torneio %d' % tid))
    for i, (street, jogada, ideal, ev, stack) in enumerate(decisoes, start=1):
        conn.execute(_adapt("""INSERT INTO decisions
            (id, tournament_id, hand_id, street, position, hero_cards, board, action_taken, best_action,
             score, label, ev_loss_bb, ev_loss_source, stack_bb, num_players)
            VALUES (?, ?, ?, ?, 'BTN', 'AhKh', '[]', ?, ?, 0.4, 'small_mistake', ?, 'solver_hand', ?, 9)"""),
            (i, 1 if i % 2 else 2, 'H%d' % i, street, jogada, ideal, ev, stack))
    conn.commit(); conn.close()


#: um leak gordo, um magro, e um par de acoes DIFERENTE na mesma street (a armadilha)
SEED = ([('flop', 'fold', 'call', 2.0, 40.0)] * 6
        + [('flop', 'fold', 'shove', 5.0, 40.0)] * 2
        + [('turn', 'fold', 'call', 1.0, 40.0)] * 3
        + [('flop', 'fold', 'call', 0.01, 40.0)] * 4)      # abaixo do corte de 0,05bb


def test_a_lista_reconcilia_com_TODA_linha_do_card():
    """O guarda central: para cada linha, mesmo numero de maos e mesma soma de bb."""
    _semeia(SEED)
    s = get_ev_summary(1, last_n=50)
    linhas = s.get('top_leaks') or []
    assert linhas, 'o seed tem de produzir linhas no card'
    for l in linhas:
        d = get_maos_do_leak(1, l['street'], l['action_taken'], l['best_action'], last_n=50)
        assert d['total'] == l['count'], (l, d['total'])
        assert abs(d['loss_bb'] - l['loss_bb']) < 0.15, (l, d['loss_bb'])
        assert len(d['hands']) == d['total'], 'sem paginacao, a lista vem inteira'


def test_a_lista_nao_mistura_par_de_acao_na_mesma_street():
    """A armadilha que a consulta do plano de estudos cairia: ela filtra so (street, assento)."""
    _semeia(SEED)
    call = get_maos_do_leak(1, 'flop', 'fold', 'call', last_n=50)
    shove = get_maos_do_leak(1, 'flop', 'fold', 'shove', last_n=50)
    assert call['total'] == 6 and shove['total'] == 2, (call['total'], shove['total'])
    assert all(m['ev_loss_bb'] == 2.0 for m in call['hands']), call['hands']
    assert all(m['ev_loss_bb'] == 5.0 for m in shove['hands']), shove['hands']
    # e as 4 decisoes de 0,01bb ficam de fora, como no card
    assert 0.01 not in [m['ev_loss_bb'] for m in call['hands']]


def test_a_paginacao_nao_muda_o_total_nem_repete_mao():
    _semeia(SEED)
    p1 = get_maos_do_leak(1, 'flop', 'fold', 'call', last_n=50, limit=4, offset=0)
    p2 = get_maos_do_leak(1, 'flop', 'fold', 'call', last_n=50, limit=4, offset=4)
    assert p1['total'] == p2['total'] == 6, (p1['total'], p2['total'])
    assert len(p1['hands']) == 4 and len(p2['hands']) == 2
    ids = [m['decision_id'] for m in p1['hands']] + [m['decision_id'] for m in p2['hands']]
    assert len(set(ids)) == 6, 'a pagina 2 nao pode repetir mao da pagina 1'


def test_cada_mao_carrega_o_que_o_replayer_precisa():
    _semeia(SEED)
    m = get_maos_do_leak(1, 'flop', 'fold', 'call', last_n=50)['hands'][0]
    for campo in ('tournament_id', 'hand_id', 'decision_id', 'position', 'hero_cards', 'ev_loss_bb'):
        assert m.get(campo) is not None, (campo, m)


def test_o_endpoint_exige_a_linha_inteira_e_pagina():
    _semeia(SEED)
    from api.app import app
    from database.auth import generate_token
    c = app.test_client()
    h = {'Authorization': 'Bearer %s' % generate_token(1, 'player')}
    ok = c.get('/player/ev-leaks/hands?street=flop&action_taken=fold&best_action=call&limit=2', headers=h)
    assert ok.status_code == 200 and ok.get_json()['total'] == 6 and len(ok.get_json()['hands']) == 2
    # sem a chave inteira nao da para responder: 400, nunca uma lista de outro spot
    faltando = c.get('/player/ev-leaks/hands?street=flop&action_taken=fold', headers=h)
    assert faltando.status_code == 400, faltando.status_code


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
