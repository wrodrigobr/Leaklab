# -*- coding: utf-8 -*-
"""Multiway postflop fica FORA de tudo que soma, ranqueia e pontua, inclusive o ELO (15/09).

── O caso que originou ───────────────────────────────────────────────────────────────────────

O solver e heads-up. Uma decisao postflop com 2+ oponentes ativos e resolvida como se os outros
nao existissem (mao 262009780504: flop de CINCO, julgado como "HJ abre, BB paga"). O front ja
rebaixa essa decisao a "informativa" (`cardLogic.decisionSeverity`) e o /replay nao grada. Mas o
backend seguia contando: o auditor de vereditos (VER-4) forjou uma acusacao de 3bb numa decisao
multiway e mediu 23 rotas mudando -- ELO, plano de estudos, Leak Finder, ranking, nivel, a visao
do coach -- e ZERO excluindo.

Medido em producao, ELO com e sem multiway: user 58 1825,6 -> 1859,5 (+33,9); 40 +22,8;
3 +12,8; 65 +12,4; 62 -0,9. Multiway = 6 a 10 por cento das decisoes da janela.

── Semantica ─────────────────────────────────────────────────────────────────────────────────

Sai do DENOMINADOR: a decisao nao e medida. Nunca conta como acerto, porque contar como acerto
e a mesma mentira na direcao oposta ("celula sem dado nunca vira 0,0"). `n_active_opponents`
NULL e legado e conta como NAO multiway (convencao do drill e do card).

── O que este arquivo defende ────────────────────────────────────────────────────────────────

1. A fonte unica em Python (`card_verdict.multiway_sem_cobertura`) sobre uma tabela de casos.
2. Que o gemeo em SQL (`repositories._SQL_MULTIWAY_FORA`) concorda com o Python CASO A CASO
   (street preflop/flop/turn/NULL x n_ativos NULL/0/1/2/5). Sem isto sao duas regras que
   combinam de ser iguais.
3. Pela PORTA, rota a rota pelo test_client: a mesma forja de acusacao numa decisao multiway
   nao move NENHUM agregado (so as duas listas do torneio, que mostram a linha como
   informativa), e a mesma forja numa decisao heads-up move todos eles. O segundo lado e o
   controle: um filtro que excluisse tudo passaria no primeiro e mataria o produto.
4. Que o julgamento do COACH (override) numa mao multiway continua aparecendo para ele.
5. Que o torneio ja nasce com `*_pct` sem multiway (`build_session_metrics`), e nao so no resync.

Quebrado de proposito: `_SQL_MULTIWAY_FORA = "1=1"` faz o caso 2 e o 3 acusarem; a funcao
Python devolvendo False faz o 2 e o 5 acusarem.
"""
import logging
import os
import sys

logging.disable(logging.CRITICAL)      # o test_client loga cada GET; sao ~100 por caso
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from leaklab.card_verdict import multiway_sem_cobertura                      # noqa: E402
from test_arquivo_com_varios_torneios import UID, banco_de_teste              # noqa: E402

COACH = 9502
TID = 960001            # id ALTO: no Postgres o banco persiste entre rodadas e ids baixos colidem
EXT = 'T-MW-960001'

# (street, n_ativos) -> a regra. NULL conta como heads-up; street NULL nao e preflop.
CASOS = [
    ('preflop', None, False), ('preflop', 0, False), ('preflop', 1, False),
    ('preflop', 2, False), ('preflop', 5, False),
    ('flop', None, False), ('flop', 0, False), ('flop', 1, False),
    ('flop', 2, True), ('flop', 5, True),
    ('turn', None, False), ('turn', 1, False), ('turn', 2, True),
    ('river', 3, True),
    (None, None, False), (None, 1, False), (None, 2, True),
]


def _q(sql, params=()):
    from database.schema import get_conn
    from database.repositories import _adapt
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(_adapt(sql), params).fetchall()]
    finally:
        conn.close()


def _x(sql, params=()):
    from database.schema import get_conn
    from database.repositories import _adapt
    conn = get_conn()
    try:
        conn.execute(_adapt(sql), params)
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════════════════
# 1) A fonte unica
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_a_fonte_unica_sobre_a_tabela_de_casos():
    for street, n, esperado in CASOS:
        assert multiway_sem_cobertura(street, n) is esperado, (street, n, esperado)
    # lixo no campo nao vira multiway (o que nao se sabe nao acusa)
    assert multiway_sem_cobertura('flop', 'muitos') is False
    assert multiway_sem_cobertura('FLOP ', '2') is True         # normaliza street e aceita texto numerico
    assert multiway_sem_cobertura('Preflop', 4) is False


# ══════════════════════════════════════════════════════════════════════════════════════════
# 2) O gemeo em SQL concorda com o Python, caso a caso
# ══════════════════════════════════════════════════════════════════════════════════════════

def _semeia_torneio(played_at='2026-09-10 20:00:00'):
    _x("INSERT INTO tournaments (id, user_id, tournament_id, site, hero, played_at, imported_at, "
       "hands_count, decisions_count) VALUES (?,?,?,?,?,?,?,?,?)",
       (TID, UID, EXT, 'pokerstars', 'Hero', played_at, played_at, 10, 0))


def _apaga_torneio():
    for tab, col in (('coach_hand_annotations', 'student_id'),):
        try:
            _x("DELETE FROM %s WHERE %s=?" % (tab, col), (UID,))
        except Exception:
            pass
    _x("DELETE FROM decisions WHERE tournament_id=?", (TID,))
    _x("DELETE FROM tournaments WHERE id=?", (TID,))


def test_o_gemeo_sql_concorda_com_o_python_caso_a_caso():
    from database.repositories import _SQL_MULTIWAY_FORA
    with banco_de_teste():
        _semeia_torneio()
        try:
            esperado_fica = set()
            for i, (street, n, mw) in enumerate(CASOS):
                hid = 'EQ%02d' % i
                # street e NOT NULL na tabela: o caso NULL entra como string vazia, que para a
                # funcao Python e a mesma coisa ("nao e preflop").
                _x("INSERT INTO decisions (tournament_id, hand_id, street, action_taken, best_action, "
                   "label, score, n_active_opponents) VALUES (?,?,?,?,?,?,?,?)",
                   (TID, hid, street or '', 'bet', 'bet', 'standard', 0.1, n))
                if not multiway_sem_cobertura(street or '', n):
                    esperado_fica.add(hid)
            ficou = {r['hand_id'] for r in _q(
                "SELECT d.hand_id FROM decisions d WHERE d.tournament_id=? AND " + _SQL_MULTIWAY_FORA,
                (TID,))}
            assert ficou == esperado_fica, {'so_no_sql': ficou - esperado_fica,
                                            'so_no_python': esperado_fica - ficou}
            # o zero tranquilizador: a tabela precisa ter os dois lados, senao a igualdade acima
            # passaria com um filtro que deixa tudo (ou nada) passar
            assert 0 < len(ficou) < len(CASOS), (len(ficou), len(CASOS))
        finally:
            _apaga_torneio()


# ══════════════════════════════════════════════════════════════════════════════════════════
# 3) Pela PORTA: a forja multiway nao move agregado nenhum; a forja heads-up move todos
# ══════════════════════════════════════════════════════════════════════════════════════════

ROTAS = [
    '/history/breakdown', '/history/evolution', '/history/tournaments', '/metrics/leaderboard',
    '/metrics/level', '/player/dna', '/player/elo', '/player/elo-curve', '/player/ev-leaks',
    '/player/ev-summary?last_n=0', '/player/evolution', '/player/gto-alignment',
    '/player/gto-alignment-matrix', '/player/gto-position', '/player/gto-quality',
    '/player/leak-finder', '/player/leak-graph', '/player/leak-roi', '/player/pressure-profile',
    '/player/results-vs-gto', '/player/strategic-twin',
    '/history/tournament/%s' % EXT,
]
ROTAS_COACH = ['/coach/student/%d/worst-decisions?n=200' % UID,
               '/coach/student/%d/tournament/%s' % (UID, EXT)]
# As duas listas do torneio mostram a linha (o front a rebaixa a informativa): sao as UNICAS
# que podem mudar com a forja multiway.
LISTAS_DO_TORNEIO = {'/history/tournament/%s' % EXT, '/coach/student/%d/tournament/%s' % (UID, EXT)}
# O controle: com a forja heads-up, TODAS estas tem de mudar. Sao as portas que o VER-4 mediu.
OBRIGATORIAS_NO_HU = set(ROTAS) | set(ROTAS_COACH)

_VOLATEIS = {'calculated_at', 'created_at', 'imported_at', 'generated_at', 'updated_at', 'timestamp',
             'snapshot_at', 'weeks_inactive', 'decay_applied', 'delta_7d', 'ts', 'now', 'report_id',
             'next_drill_at', 'days_overdue', 'drilled_at', 'last_activity', 'server_time', 'cache_hit',
             'played_at', 'expires_at', 'labels_reconciled_at', 'trend', 'trend_n'}

_COLS_DA_FORJA = ('gto_label', 'gto_action', 'ev_loss_bb', 'ev_loss_source', 'label', 'score',
                  'verdict_source', 'verdict_has_cost')
FORJA = ("UPDATE decisions SET gto_label='gto_critical', gto_action='check', ev_loss_bb=3.0, "
         "ev_loss_source='solver_hand', label='clear_mistake', score=0.5, verdict_source='solver', "
         "verdict_has_cost=TRUE WHERE id=?")
DESFAZ = ("UPDATE decisions SET " + ', '.join('%s=?' % c for c in _COLS_DA_FORJA) + " WHERE id=?")


def _limpa_volateis(o):
    if isinstance(o, dict):
        return {k: _limpa_volateis(v) for k, v in o.items() if k not in _VOLATEIS}
    if isinstance(o, list):
        return [_limpa_volateis(v) for v in o]
    return o


def _snapshot(c, h, cc, ch):
    try:
        _x("DELETE FROM player_elo_history WHERE user_id=?", (UID,))   # /player/elo cacheia
    except Exception:
        pass
    out = {}
    for rota in ROTAS:
        r = c.get(rota + ('&' if '?' in rota else '?') + 'days=3650&period=3650&period_days=3650',
                  headers=h)
        assert r.status_code == 200, (rota, r.status_code, r.get_data(as_text=True)[:200])
        out[rota] = _limpa_volateis(r.get_json())
    for rota in ROTAS_COACH:
        r = cc.get(rota, headers=ch)
        assert r.status_code == 200, (rota, r.status_code, r.get_data(as_text=True)[:200])
        out[rota] = _limpa_volateis(r.get_json())
    return out


def _mudaram(a, b):
    return {rota for rota in a if a[rota] != b[rota]}


def _recalcula():
    from database.schema import get_conn
    from database.repositories import recalcula_agregados_do_torneio
    conn = get_conn()
    try:
        recalcula_agregados_do_torneio(conn, TID)
        conn.commit()
    finally:
        conn.close()


def _semeia_decisoes():
    """42 decisoes 'standard' de um torneio: 30 preflop, 6 flop heads-up, 6 flop multiway.
    30+ porque o Strategic Twin exige 30; 2 por spot porque os rankings exigem HAVING >= 2."""
    _semeia_torneio()
    cols = ("tournament_id, hand_id, street, position, action_taken, best_action, label, score, "
            "gto_label, ev_loss_bb, ev_loss_source, stack_bb, n_active_opponents, icm_pressure, "
            "estimated_equity, pot_size, facing_bet, hero_cards, board")
    ph = ','.join('?' * 19)
    pos = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']
    linhas = []
    for i in range(30):
        linhas.append((TID, 'P%02d' % i, 'preflop', pos[i % 6], 'raise', 'raise', 'standard', 0.05,
                       'gto_correct', 0.0, 'gw_har', 30.0, 1, 'none', 0.55, 1.5, 0.0, 'AhKd', ''))
    for i in range(6):
        linhas.append((TID, 'H%02d' % i, 'flop', 'CO', 'bet', 'bet', 'standard', 0.05,
                       'gto_correct', 0.0, 'solver_hand', 30.0, 1, 'none', 0.60, 6.0, 0.0, 'AhKd', '2c7d9s'))
    for i in range(6):
        linhas.append((TID, 'M%02d' % i, 'flop', 'CO', 'bet', 'bet', 'standard', 0.05,
                       None, None, None, 30.0, 3, 'none', 0.60, 12.0, 0.0, 'AhKd', '2c7d9s'))
    for l in linhas:
        _x("INSERT INTO decisions (%s) VALUES (%s)" % (cols, ph), l)
    _x("UPDATE tournaments SET decisions_count=? WHERE id=?", (len(linhas), TID))
    _recalcula()
    ids = {r['hand_id']: r['id'] for r in _q("SELECT id, hand_id FROM decisions WHERE tournament_id=?", (TID,))}
    return [ids['M00'], ids['M01']], [ids['H00'], ids['H01']]


def _cria_coach(c_fn):
    _x("UPDATE users SET coach_id=NULL WHERE coach_id=?", (COACH,))
    _x("DELETE FROM users WHERE id=?", (COACH,))
    _x("INSERT INTO users (id, username, email, password_hash, plan, role) VALUES (?,?,?,?,?,?)",
       (COACH, 'coach%d' % COACH, 'coach%d@t.local' % COACH, 'h', 'pro', 'coach'))
    _x("UPDATE users SET coach_id=? WHERE id=?", (COACH, UID))
    return c_fn(COACH, 'coach')


def _apaga_coach():
    _x("UPDATE users SET coach_id=NULL WHERE coach_id=?", (COACH,))
    _x("DELETE FROM users WHERE id=?", (COACH,))


def _forja(ids):
    """Forja o veredito de solver e devolve as linhas ORIGINAIS, para o desfazer ser exato."""
    ph = ','.join('?' * len(ids))
    antes = _q("SELECT id, %s FROM decisions WHERE id IN (%s)" % (', '.join(_COLS_DA_FORJA), ph),
               tuple(ids))
    for i in ids:
        _x(FORJA, (i,))
    _recalcula()
    return antes


def _desfaz(antes):
    for r in antes:
        _x(DESFAZ, tuple(r[c] for c in _COLS_DA_FORJA) + (r['id'],))
    _recalcula()


def test_pela_porta_a_forja_multiway_nao_move_agregado_e_a_heads_up_move_todos():
    from database.auth import generate_token
    with banco_de_teste() as (c, h):
        import api.app as _app

        def cliente(uid, role):
            return _app.app.test_client(), {'Authorization': 'Bearer ' + generate_token(uid, role)}
        cc, ch = _cria_coach(cliente)
        try:
            mw, hu = _semeia_decisoes()
            base = _snapshot(c, h, cc, ch)

            originais = _forja(mw)
            com_mw = _snapshot(c, h, cc, ch)
            _desfaz(originais)
            mudou_mw = _mudaram(base, com_mw)
            # a forja precisa ser VISIVEL em algum lugar, senao "nada mudou" nao prova nada
            assert LISTAS_DO_TORNEIO <= mudou_mw, ('a forja multiway nao chegou nem na lista', mudou_mw)
            vazou = mudou_mw - LISTAS_DO_TORNEIO
            assert not vazou, 'agregados que CONTARAM a decisao multiway: %s' % sorted(vazou)

            volta = _snapshot(c, h, cc, ch)
            assert _mudaram(base, volta) == set(), ('o desfazer nao restaurou', _mudaram(base, volta))

            originais = _forja(hu)
            com_hu = _snapshot(c, h, cc, ch)
            _desfaz(originais)
            mudou_hu = _mudaram(base, com_hu)
            faltou = OBRIGATORIAS_NO_HU - mudou_hu
            assert not faltou, 'o controle quebrou: a forja heads-up NAO moveu %s' % sorted(faltou)
        finally:
            _apaga_torneio()
            _apaga_coach()


# ══════════════════════════════════════════════════════════════════════════════════════════
# 4) O julgamento do coach numa mao multiway continua valendo para ele
# ══════════════════════════════════════════════════════════════════════════════════════════

def test_o_override_do_coach_numa_mao_multiway_continua_na_lista_dele():
    from database.auth import generate_token
    with banco_de_teste():
        import api.app as _app

        def cliente(uid, role):
            return _app.app.test_client(), {'Authorization': 'Bearer ' + generate_token(uid, role)}
        cc, ch = _cria_coach(cliente)
        try:
            mw, hu = _semeia_decisoes()
            rota = '/coach/student/%d/worst-decisions?n=200' % UID
            antes = {d['id'] for d in cc.get(rota, headers=ch).get_json()['decisions']}
            assert mw[0] not in antes
            _x("INSERT INTO coach_hand_annotations (coach_id, student_id, decision_id, comment, "
               "coach_override_label) VALUES (?,?,?,?,?)",
               (COACH, UID, mw[0], 'multiway, mas foi erro mesmo', 'clear_mistake'))
            depois = {d['id'] for d in cc.get(rota, headers=ch).get_json()['decisions']}
            assert mw[0] in depois, 'o override do coach numa mao multiway sumiu da lista dele'
            assert mw[1] not in depois, 'a multiway SEM override entrou'
        finally:
            _apaga_torneio()
            _apaga_coach()


# ══════════════════════════════════════════════════════════════════════════════════════════
# 5) O torneio nasce sem multiway no denominador (o mesmo criterio do resync)
# ══════════════════════════════════════════════════════════════════════════════════════════

def _saida(street, n_ativos, label, score):
    return {'handId': 'X%s%s%s' % (street, n_ativos, label), 'street': street,
            'spot': {'nActiveOpponents': n_ativos},
            'evaluation': {'label': label, 'mistakeScore': score}}


def test_as_metricas_da_sessao_nao_medem_multiway_mas_contam_a_decisao():
    from leaklab.session_metrics import build_session_metrics
    m = build_session_metrics([
        _saida('preflop', 1, 'standard', 0.0),
        _saida('flop', 1, 'clear_mistake', 0.8),
        _saida('flop', 3, 'clear_mistake', 0.8),     # multiway: existe, nao tem nota
    ])
    assert m['total_decisions'] == 3, m
    assert m['label_pct'] == {'standard': 50.0, 'clear_mistake': 50.0}, m['label_pct']
    assert m['avg_mistake_score'] == 0.4, m['avg_mistake_score']
    assert m['by_street'] == {'preflop': {'standard': 1}, 'flop': {'clear_mistake': 1}}, m['by_street']
    # o controle: a mesma linha heads-up conta
    m2 = build_session_metrics([_saida('flop', 1, 'clear_mistake', 0.8), _saida('flop', 1, 'clear_mistake', 0.8)])
    assert m2['label_pct'] == {'clear_mistake': 100.0}, m2['label_pct']
    # so multiway: nada medido, nada de nota, sem divisao por zero
    m3 = build_session_metrics([_saida('turn', 2, 'clear_mistake', 0.8)])
    assert m3['total_decisions'] == 1 and m3['label_pct'] == {} and m3['avg_mistake_score'] == 0.0, m3


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
            import traceback
            traceback.print_exc()
            print('ERRO    %s: %s: %s' % (t.__name__, type(e).__name__, e))
    print('\nTotal: %d | Passed: %d | Failed: %d' % (len(testes), len(testes) - falhas, falhas))
    sys.exit(1 if falhas else 0)
