# -*- coding: utf-8 -*-
"""Seletor de tamanho de mesa na grade por assento, e o solver do CENARIO (08/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Report de um fundador: "o UTG esta abrindo mais maos do que o UTG+1, deveria ser o inverso; o
range tem que expandir quanto mais perto do button". Ele estava certo, e a causa nao era o
chart (que e monotonico em toda profundidade) nem a traducao de assento (que bate com o GTO
Wizard: mesa 8 a 40bb+ deu 17,1% no UTG contra 17,1% do GTOW).

A causa: a LINHA da grade e o rotulo da sala, e somar mesas de tamanhos diferentes junta
assentos estrategicamente diferentes — o UTG de 9-max tem 8 jogadores atras, o de 6-max tem 5.
Na conta dele, a linha "UTG" era 41% mesa 7, 31% mesa 8, 20% mesa 6.

E, na matriz, o resumo do solver era a media NAS MAOS QUE CAIRAM: com 10 oportunidades saiu
"solver abriria 7,2%" ao lado de uma grade desenhando o range inteiro (~20%). O cabecalho
contradizia a propria tela.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. o filtro de mesa muda o recorte, e dentro de UM tamanho a ordem do solver cresce em direcao
   ao botao (o que o fundador cobrou);
2. `solver_pct_todas` NAO depende de quais maos cairam: dois jogadores nos MESMOS contextos,
   com maos diferentes, tem o mesmo numero (e o `solver_pct` deles difere — e a prova de que o
   teste sabe distinguir os dois);
3. abaixo do piso de amostra, o numero do JOGADOR nao sai e o do solver sai;
4. o endpoint recusa tamanho desconhecido e, sem `?mesa=`, abre na mesa MAIS JOGADA.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from database.schema import get_conn, init_db                                      # noqa: E402
import database.repositories as repo                                              # noqa: E402
from database.repositories import (_adapt, get_position_open_matrix,               # noqa: E402
                                   get_player_stats_by_position, mesas_do_jogador,
                                   TAMANHOS_DE_MESA, MINIMO_MAOS_DO_RESUMO)

# maos "boas" e "ruins" o bastante para o chart separar: AA/KK sempre abrem, 72o/83o nunca
MAOS_FORTES = ['AsAd', 'KsKd', 'QsQd', 'AsKs']
MAOS_FRACAS = ['7s2d', '8s3d', '9s4d', 'Ts5d']


def _semeia(mesas_por_assento):
    """mesas_por_assento = [(num_players, position, n_maos, maos)] — uma decisao por mao."""
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash, plan) VALUES (1,'u','u@e.st','h','pro')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, hero, imported_at) "
                        "VALUES (1, 1, 'T1', 'Hero', datetime('now'))"))
    i = 0
    for mesa, pos, n, maos in mesas_por_assento:
        for k in range(n):
            i += 1
            conn.execute(_adapt("""INSERT INTO decisions
                (id, tournament_id, hand_id, street, position, action_taken, best_action, score, label,
                 hero_cards, board, stack_bb, effective_stack_bb, facing_bet, num_players, is_3bet)
                VALUES (?, 1, ?, 'preflop', ?, 'fold', 'fold', 0.1, 'standard', ?, '[]', 30, 30, 0, ?, ?)"""),
                (i, 'H%d' % i, pos, maos[k % len(maos)], mesa, False))
    conn.commit(); conn.close()


def test_o_filtro_de_mesa_muda_o_recorte_e_a_ordem_do_solver_cresce_ate_o_botao():
    # o MESMO rotulo "UTG" em duas mesas: em 9-max sao 8 atras (range apertado), em 6-max sao 5
    _semeia([(9, 'UTG', 40, MAOS_FRACAS), (6, 'UTG', 40, MAOS_FRACAS),
             (6, 'CO', 40, MAOS_FRACAS), (6, 'BTN', 40, MAOS_FRACAS)])
    todas = get_position_open_matrix(1, 'UTG', days=3650)
    so9   = get_position_open_matrix(1, 'UTG', days=3650, mesa='9max')
    so6   = get_position_open_matrix(1, 'UTG', days=3650, mesa='6max')
    assert (todas['n'], so9['n'], so6['n']) == (80, 40, 40), (todas['n'], so9['n'], so6['n'])
    # o UTG de 6-max e um assento MAIS LARGO que o de 9-max, e a mistura fica no meio
    assert so6['solver_pct_todas'] > so9['solver_pct_todas'], (so6['solver_pct_todas'], so9['solver_pct_todas'])
    assert so9['solver_pct_todas'] < todas['solver_pct_todas'] < so6['solver_pct_todas'], todas['solver_pct_todas']
    # e DENTRO de um tamanho de mesa a ordem cresce em direcao ao botao (o que o fundador cobrou)
    seq = [get_position_open_matrix(1, p, days=3650, mesa='6max')['solver_pct_todas'] for p in ('UTG', 'CO', 'BTN')]
    assert seq == sorted(seq) and seq[0] < seq[-1], seq
    # a composicao DECLARA a mistura quando o filtro esta desligado
    assert {c['mesa']: c['pct'] for c in todas['composicao']} == {9: 50, 6: 50}, todas['composicao']
    assert so6['composicao'] == [{'mesa': 6, 'n': 40, 'pct': 100}], so6['composicao']


def test_o_solver_do_cenario_nao_depende_das_maos_que_cairam():
    """O guarda do defeito original. Mesmo assento, mesma mesa, mesmo stack, MAOS diferentes:
    `solver_pct_todas` tem de ser IGUAL (e o range daquele cenario) e `solver_pct` DIFERENTE
    (e a media nas maos que cairam). Se alguem trocar um pelo outro no resumo, isto cai."""
    _semeia([(8, 'UTG', 40, MAOS_FORTES)])
    fortes = get_position_open_matrix(1, 'UTG', days=3650)
    _semeia([(8, 'UTG', 40, MAOS_FRACAS)])
    fracas = get_position_open_matrix(1, 'UTG', days=3650)
    assert fortes['solver_pct_todas'] == fracas['solver_pct_todas'], (fortes['solver_pct_todas'], fracas['solver_pct_todas'])
    assert fortes['solver_pct'] != fracas['solver_pct'], (fortes['solver_pct'], fracas['solver_pct'])
    # e o numero do cenario esta na faixa do chart do assento, nao no extremo das maos sorteadas
    assert 10 < fortes['solver_pct_todas'] < 30, fortes['solver_pct_todas']
    assert fortes['solver_pct'] > 90 and fracas['solver_pct'] < 10, (fortes['solver_pct'], fracas['solver_pct'])


def test_abaixo_do_piso_o_numero_do_jogador_nao_sai_mas_a_referencia_sai():
    _semeia([(8, 'UTG', MINIMO_MAOS_DO_RESUMO - 1, MAOS_FRACAS)])
    poucas = get_position_open_matrix(1, 'UTG', days=3650)
    assert poucas['n'] == MINIMO_MAOS_DO_RESUMO - 1
    assert poucas['voce_pct'] is None, poucas['voce_pct']
    assert poucas['solver_pct_todas'] is not None, 'a referencia nao depende do sorteio: ela sai'
    assert poucas['amostra_minima'] == MINIMO_MAOS_DO_RESUMO
    _semeia([(8, 'UTG', MINIMO_MAOS_DO_RESUMO, MAOS_FRACAS)])
    assert get_position_open_matrix(1, 'UTG', days=3650)['voce_pct'] == 0.0


def test_a_grade_respeita_o_filtro_e_a_distribuicao_sugere_a_mesa_mais_jogada():
    _semeia([(9, 'UTG', 10, MAOS_FRACAS), (8, 'UTG', 30, MAOS_FRACAS), (6, 'CO', 20, MAOS_FRACAS)])
    d = mesas_do_jogador(1, days=3650)
    assert d['sugerida'] == '8max', d
    assert {m['mesa']: m['n'] for m in d['mesas']} == {'9max': 10, '8max': 30, '6max': 20}, d
    grade_todas = get_player_stats_by_position(1, days=3650)
    grade_8 = get_player_stats_by_position(1, days=3650, mesa='8max')
    def maos(g, pos):
        return next((l['hands'] for l in g['positions'] if l['position'] == pos), 0)
    assert maos(grade_todas, 'UTG') == 40 and maos(grade_8, 'UTG') == 30, (maos(grade_todas, 'UTG'), maos(grade_8, 'UTG'))
    assert maos(grade_8, 'CO') == 0, 'mesa 6 fica de fora do recorte de 8-max'
    assert grade_8['mesa'] == '8max' and grade_todas['mesa'] is None
    assert grade_8['mesas'] == list(TAMANHOS_DE_MESA)


def test_o_endpoint_recusa_mesa_desconhecida_e_abre_na_mais_jogada():
    _semeia([(9, 'UTG', 10, MAOS_FRACAS), (8, 'UTG', 30, MAOS_FRACAS)])
    from api.app import app
    from database.auth import generate_token
    c = app.test_client()
    h = {'Authorization': 'Bearer %s' % generate_token(1, 'player')}
    r = c.get('/metrics/player-stats/by-position?days=3650', headers=h)
    d = r.get_json()
    assert r.status_code == 200 and d['mesa'] == '8max' and d['mesa_auto'] is True, (r.status_code, d.get('mesa'))
    assert d['distribuicao_de_mesas']['sugerida'] == '8max'
    # "todas" e escolha explicita: desliga o filtro e o payload DECLARA que nao ha mesa em vigor
    d2 = c.get('/metrics/player-stats/by-position?days=3650&mesa=todas', headers=h).get_json()
    assert d2['mesa'] is None and d2['mesa_auto'] is False
    assert next(l['hands'] for l in d2['positions'] if l['position'] == 'UTG') == 40
    # tamanho desconhecido e 400, nunca "todas" caladamente
    ruim = c.get('/metrics/player-stats/by-position?days=3650&mesa=10max', headers=h)
    assert ruim.status_code == 400 and 'mesas' in ruim.get_json(), ruim.get_data(as_text=True)[:200]
    assert c.get('/metrics/player-stats/by-position/hands?position=UTG&mesa=10max', headers=h).status_code == 400


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
