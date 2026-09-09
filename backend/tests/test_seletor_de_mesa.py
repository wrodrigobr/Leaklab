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
4. o endpoint recusa tamanho desconhecido e, sem `?mesa=`, abre na mesa MAIS JOGADA;
5. a matriz DECLARA de qual carta veio o numero do solver, em jogadores atras (AY-34).

── O que o item 5 conserta (09/09) ────────────────────────────────────────────────────────

Duvida do mesmo fundador: "em relacao ao UTG, to achando essa porcentagem que o solver abriria
um tanto quanto alta, de onde vem esse valor?". Vinha da carta CERTA: o UTG dele era de mesa 7,
que tem 6 jogadores atras, e a carta de 6 atras abre 20,0% contra 15,8% da de 8 atras. A conta
estava certa e a tela nao dizia qual carta era. Dizer o nome do assento no vocabulario 9-max
("UTG+2") troca uma duvida por outra, porque a tela chama esse mesmo assento de UTG; o unico
numero que fecha a pergunta e QUANTOS AGEM DEPOIS.
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


def test_com_um_numero_de_jogadores_a_grade_nao_inventa_assento_que_nao_existe():
    """Dono, 08/09: "em 7 jogadores nao era nem pra exibir o utg+2 mesmo". O UTG e sempre o
    primeiro a agir; o que some quando a mesa esvazia e o UTG+2 e depois o UTG+1. Medido no
    acervo: 14 decisoes carregam assento impossivel nos tamanhos que o filtro isola (dado de
    borda do parser). Elas NAO somem caladas: continuam no total, e o rodape as declara."""
    _semeia([(7, 'UTG', 40, MAOS_FRACAS), (7, 'LJ', 40, MAOS_FRACAS), (7, 'BTN', 40, MAOS_FRACAS),
             (7, 'UTG+2', 3, MAOS_FRACAS),          # impossivel em mesa de 7: o parser errou
             (9, 'UTG+2', 40, MAOS_FRACAS)])        # em mesa de 9 o UTG+2 existe
    g7 = get_player_stats_by_position(1, days=3650, mesa='7max')
    assert [l['position'] for l in g7['positions']] == ['UTG', 'LJ', 'BTN'], [l['position'] for l in g7['positions']]
    # as 3 maos impossiveis seguem no TOTAL do recorte: a diferenca e o que o rodape declara
    assert g7['total']['total_hands'] == 123, g7['total']['total_hands']
    assert sum(l['hands'] for l in g7['positions']) == 120
    # com 9 jogadores o UTG+2 e assento de verdade e aparece
    g9 = get_player_stats_by_position(1, days=3650, mesa='9max')
    assert [l['position'] for l in g9['positions']] == ['UTG+2'], [l['position'] for l in g9['positions']]
    # sem filtro, nada e escondido (o balde "todas" nao tem um tamanho so para validar)
    todas = get_player_stats_by_position(1, days=3650, mesa=None)
    assert 'UTG+2' in [l['position'] for l in todas['positions']]


def test_a_matriz_declara_de_qual_carta_veio_o_numero_do_solver():
    """`assento_da_carta` + `jogadores_atras`: sem isso o jogador nao tem como saber que o
    "UTG" da tela e comparado com a carta de OUTRO assento, e conclui que o solver abre alto.

    A segunda metade e o que impede a promessa falsa: num recorte que MISTURA cartas (sem
    filtro de mesa, conta com mais de um tamanho) nao existe referencia unica, e a tela tem de
    dizer isso em vez de escolher uma das cartas e apresenta-la como se fosse a do numero."""
    _semeia([(7, 'UTG', 40, MAOS_FRACAS), (9, 'UTG', 40, MAOS_FRACAS)])

    m7 = get_position_open_matrix(1, 'UTG', days=3650, mesa='7max')
    # o primeiro a agir em mesa de 7 tem 6 atras -> no vocabulario 9-max isso e o UTG+2
    assert m7['assento_da_carta'] == 'UTG+2', m7['assento_da_carta']
    assert m7['jogadores_atras'] == 6, m7['jogadores_atras']

    m9 = get_position_open_matrix(1, 'UTG', days=3650, mesa='9max')
    assert m9['assento_da_carta'] == 'UTG' and m9['jogadores_atras'] == 8, (m9['assento_da_carta'], m9['jogadores_atras'])

    # o MESMO rotulo de tela, duas cartas diferentes: e a prova de que o numero muda de origem
    assert m7['solver_pct_todas'] > m9['solver_pct_todas'], (m7['solver_pct_todas'], m9['solver_pct_todas'])

    # recorte que junta os dois tamanhos: nao ha carta unica, entao a tela nao promete uma
    misto = get_position_open_matrix(1, 'UTG', days=3650, mesa=None)
    assert misto['assento_da_carta'] is None and misto['jogadores_atras'] is None, misto['assento_da_carta']
    assert misto['n'] == 80, misto['n']


def test_a_grade_declara_os_assentos_que_nao_existem_na_mesa():
    """Dono, 09/09, na grade de 7 do Rullian: "ta faltando o UTG+1". Nao faltava: com 7 na mao
    o segundo a agir e o LJ. Mas sumir em silencio parece esquecimento — a grade DECLARA os
    ausentes e o front os mostra desligados com o motivo. Vazio na grade agrupada."""
    _semeia([(7, 'UTG', 40, MAOS_FRACAS), (7, 'UTG+1', 40, MAOS_FRACAS)])   # o UTG+1 cru de mesa 7 E o LJ
    g = get_player_stats_by_position(1, days=3650, mesa='7max')
    assert g['assentos_ausentes'] == ['UTG+1', 'UTG+2'], g['assentos_ausentes']
    assert [l['position'] for l in g['positions'] if l['hands']] == ['UTG', 'LJ'], [l['position'] for l in g['positions'] if l['hands']]
    g9 = get_player_stats_by_position(1, days=3650, mesa='9max')
    assert g9['assentos_ausentes'] == [], g9['assentos_ausentes']
    ga = get_player_stats_by_position(1, days=3650, mesa='7max', agrupado=True)
    assert ga['assentos_ausentes'] == [], ga['assentos_ausentes']


def test_com_a_lista_de_validacao_so_quem_esta_nela_ve_o_perfil_por_posicao():
    """Dono, 09/09: "apenas o rullian visualizar este bloco ate que ele seja completamente
    validado". `STATS_BY_POSITION_USERS` setada: quem nao esta nela recebe 403 `em_validacao`
    (o front some com o bloco); quem esta segue a regra normal. Ausente: so a regra do plano.

    O 403 e distinto do 402 do plano DE PROPOSITO: 402 vira cadeado "exclusivo do Pro", e um
    Pro fora da lista lendo isso seria a tela mentindo."""
    import os
    _semeia([(8, 'UTG', 30, MAOS_FRACAS)])
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash, plan) VALUES (2,'v','v@e.st','h','pro')"))
    conn.commit(); conn.close()
    from api.app import app
    from database.auth import generate_token
    c = app.test_client()
    h1 = {'Authorization': 'Bearer %s' % generate_token(1, 'player')}
    h2 = {'Authorization': 'Bearer %s' % generate_token(2, 'player')}
    antes = os.environ.pop('STATS_BY_POSITION_USERS', None)
    try:
        os.environ['STATS_BY_POSITION_USERS'] = ' 1 , 999 '        # espacos e id inexistente nao atrapalham
        for url in ('/metrics/player-stats/by-position?days=3650',
                    '/metrics/player-stats/by-position/hands?position=UTG&days=3650',
                    '/metrics/player-stats/by-position/detail?position=UTG&stat=three_bet&days=3650'):
            assert c.get(url, headers=h1).status_code == 200, url
            r2 = c.get(url, headers=h2)
            assert r2.status_code == 403 and r2.get_json()['code'] == 'em_validacao', (url, r2.status_code)
            assert 'upgrade_required' not in r2.get_json()                # nao e cadeado de plano
        os.environ['STATS_BY_POSITION_USERS'] = ''                       # vazia = ninguem barrado
        assert c.get('/metrics/player-stats/by-position?days=3650', headers=h2).status_code == 200
    finally:
        if antes is None:
            os.environ.pop('STATS_BY_POSITION_USERS', None)
        else:
            os.environ['STATS_BY_POSITION_USERS'] = antes


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
    # "todas" DEIXOU de existir (dono, 09/09). Ele foi aceito ate aqui e desligava o filtro; a
    # medicao que o matou: a linha "UTG" do acervo do Rullian somava CINCO assentos, comparados
    # com cartas que abrem de 15,8% a 28,0%, e o cabecalho virava uma media que nao descreve
    # situacao nenhuma. Agora ele e um tamanho invalido como qualquer outro, e o 400 tem de
    # ACUSAR: aceitar de volta em silencio devolveria a media sem ninguem notar.
    recusa = c.get('/metrics/player-stats/by-position?days=3650&mesa=todas', headers=h)
    assert recusa.status_code == 400, (recusa.status_code, recusa.get_data(as_text=True)[:200])
    assert 'todas' not in recusa.get_json()['mesas'], recusa.get_json()
    # tamanho desconhecido e 400 tambem, nunca "a mais jogada" caladamente sob o rotulo errado
    ruim = c.get('/metrics/player-stats/by-position?days=3650&mesa=10max', headers=h)
    assert ruim.status_code == 400 and 'mesas' in ruim.get_json(), ruim.get_data(as_text=True)[:200]
    assert c.get('/metrics/player-stats/by-position/hands?position=UTG&mesa=10max', headers=h).status_code == 400
    assert c.get('/metrics/player-stats/by-position/hands?position=UTG&mesa=todas', headers=h).status_code == 400
    # A MATRIZ segue a MESMA politica da grade: sem `?mesa=`, abre na mesa mais jogada. Ate
    # 09/09 so a grade fazia isso e a matriz caia no recorte misturado — duas politicas para a
    # mesma pergunta. Nao aparecia na tela (o front repassa a mesa que a grade declarou), e era
    # por isso que valia consertar: quem chamasse o endpoint direto recebia um numero que
    # mistura assentos, sem nada no payload dizendo isso.
    mat = c.get('/metrics/player-stats/by-position/hands?position=UTG&days=3650', headers=h).get_json()
    assert mat['mesa'] == '8max', mat['mesa']                      # a mais jogada, como a grade
    assert mat['assento_da_carta'] is not None, mat                # recorte unico => tem referencia
    assert mat['n'] == 30, mat['n']                                # so as maos de mesa 8, nao as 40


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
