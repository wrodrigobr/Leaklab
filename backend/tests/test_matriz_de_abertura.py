# -*- coding: utf-8 -*-
"""Matriz 13x13 das maos abertas por assento, voce x solver (AY-15 c, 07/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

Sugestao do Rullian: "o conjunto de maos que voce abriu de cada posicao". O rascunho com o
acervo real mostrou por que importa: no UTG o total batia com o solver (17,2 contra 18,5) e a
composicao nao (T9s aberto 44% onde o solver abre 100%). A celula esconde, a matriz mostra.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. Uma linha por oportunidade de RFI do assento (a MESMA definicao do HUD e da grade); a mao
   canonica ('AsKd' -> 'AKo'); `voce` = fracao em que abriu; `solver` = frequencia da carta
   do assento do CHART na profundidade da vez (a mesma range do motor), media nas ocorrencias.
2. O resumo (`voce_pct`) e igual ao RFI da grade no mesmo recorte, e desde 11/09 a matriz ABRE
   nesse recorte (todas as faixas de stack), porque abrir numa faixa fazia a tela seguinte
   contradizer a porta de entrada (Rullian: 17,2% na grade, 19,8% na matriz). `cobertura` e a
   fracao com carta; sem stack nao ha carta (entra em `n`, nao na cobertura).
3. `divergencias`: so maos com >= 8 ocorrencias e distancia >= 0,30, da maior para a menor.
4. Grupo (EP) e faixa de stack funcionam; o endpoint recusa BB e assento desconhecido.
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
import database.repositories as repo                                               # noqa: E402
from database.repositories import (_adapt, get_player_stats_by_position,           # noqa: E402
                                   get_position_open_matrix, MINIMO_MAOS_DIVERGENCIA, DIVERGENCIA_MINIMA)
from leaklab.preflop_gto_ranges import villain_open_range                          # noqa: E402


def _semeia(maos):
    """`maos`: dicts com position, hero_cards, action_taken e opcionais (stack, num_players)."""
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('matriz', 'matriz@t.local', 'senha12345', 'player')
    conn = get_conn()
    conn.execute(_adapt("UPDATE users SET plan='pro' WHERE id=?"), (uid,))
    conn.execute(_adapt("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,played_at,imported_at) "
                        "VALUES (1,?,'T1','pokerstars','Hero','2026-09-01','2026-09-01')"), (uid,))
    for i, m in enumerate(maos):
        conn.execute(_adapt("INSERT INTO decisions (tournament_id,hand_id,street,position,num_players,action_taken,hero_cards,"
                            "best_action,score,label,facing_bet,facing_limp,effective_stack_bb,preflop_raises_faced,"
                            "hero_was_aggressor,is_3bet,gto_label) "
                            "VALUES (1,?,'preflop',?,?,?,?,'raise',0.1,'standard',0,0,?,0,0,?,'gto_correct')"),
                     ('H%d' % i, m['position'], m.get('num_players', 9), m['action_taken'], m['hero_cards'],
                      m.get('stack', 40), False))
    conn.commit(); conn.close()
    return uid


def _m(pos, cartas, acao, **kw):
    d = {'position': pos, 'hero_cards': cartas, 'action_taken': acao}; d.update(kw); return d


def test_celulas_voce_e_solver_e_o_resumo_bate_com_a_grade():
    """UTG a 40bb: AKs recebida 10x, aberta 10x (100%); 72o 10x, nunca (0%); T9s 10x, aberta
    3x (30%); e 4 folds com cartas malformadas ('??') que nao viram celula."""
    maos = ([_m('UTG', 'AsKs', 'raise') for _ in range(10)]
            + [_m('UTG', '7h2d', 'fold') for _ in range(10)]
            + [_m('UTG', 'Ts9s', 'raise' if i < 3 else ('call' if i < 5 else 'fold')) for i in range(10)]   # 3 raises, 2 limps, 5 folds
            + [_m('UTG', '??', 'fold') for _ in range(4)])
    uid = _semeia(maos)
    m = get_position_open_matrix(uid, 'UTG', days=3650, last_n=0)
    # as 4 maos ilegiveis entram no total (e o denominador do RFI da grade), nao nas celulas
    assert m['n'] == 34 and m['cobertura'] == round(30 * 100 / 34), (m['n'], m['cobertura'])
    assert m['cells']['AKs'] == {'n': 10, 'voce': 1.0, 'limp': 0.0, 'solver': round(float(villain_open_range('UTG', 40).get('AKs', 0.0)), 3)}
    assert m['cells']['T9s']['limp'] == 0.2, 'limp nao e fold: 2 dos 10 T9s foram limp'
    assert m['cells']['72o']['voce'] == 0.0 and m['cells']['72o']['solver'] == 0.0
    assert m['cells']['T9s']['voce'] == 0.3
    # as 169 maos existem; as nunca recebidas vem com n=0, sem `voce`, e com a carta do solver
    assert len(m['cells']) == 169 and {h for h, c in m['cells'].items() if c['n'] > 0} == {'AKs', '72o', 'T9s'}
    assert m['cells']['AQs'] == {'n': 0, 'voce': None, 'limp': None, 'solver': round(float(villain_open_range('UTG', 40).get('AQs', 0.0)), 3)}
    assert m['cells']['AQs']['solver'] > 0.9, 'AQs nunca recebida continua sendo abertura do solver'
    assert m['voce_pct'] == round(13 / 34 * 100, 1)
    # o resumo e o RFI da grade no mesmo recorte (mesma oportunidade, mesma definicao)
    g = get_player_stats_by_position(uid, days=3650, last_n=0)
    utg = next(l for l in g['positions'] if l['position'] == 'UTG')
    assert utg['stats']['rfi']['value'] == m['voce_pct']
    # o solver "abriria" = media das frequencias da carta nas 30 maos
    esperado = (10 * m['cells']['AKs']['solver'] + 10 * 0.0 + 10 * m['cells']['T9s']['solver']) / 30 * 100   # so as 30 com carta
    assert abs(m['solver_pct'] - esperado) < 0.11, (m['solver_pct'], esperado)


def test_divergencias_so_com_amostra_e_distancia_e_da_maior_para_a_menor():
    """T9s: 10x, aberta 0 onde a carta abre ~1.0 (distancia ~1); AKs: 10x aberta 10x, carta 1.0
    (0); 72o: 10x, 0 (0); J9s: 7x aberta 0 (amostra < 8, fora da lista)."""
    maos = ([_m('UTG', 'Ts9s', 'fold') for _ in range(10)] + [_m('UTG', 'AsKs', 'raise') for _ in range(10)]
            + [_m('UTG', '7h2d', 'fold') for _ in range(10)] + [_m('UTG', 'Js9s', 'fold') for _ in range(7)])
    uid = _semeia(maos)
    m = get_position_open_matrix(uid, 'UTG', days=3650, last_n=0)
    assert MINIMO_MAOS_DIVERGENCIA == 8 and DIVERGENCIA_MINIMA == 0.3
    carta_t9s = float(villain_open_range('UTG', 40).get('T9s', 0.0))
    assert carta_t9s >= 0.3, 'o teste precisa de uma mao que a carta do UTG a 40bb abra: T9s = %s' % carta_t9s
    assert [d['hand'] for d in m['divergencias']] == ['T9s'], m['divergencias']
    d = m['divergencias'][0]
    assert d['n'] == 10 and d['voce'] == 0.0 and d['solver'] == round(carta_t9s, 3) and d['delta'] == round(-carta_t9s, 3)
    # mao nunca recebida NAO entra nas divergencias (n=0), mesmo com a carta abrindo sempre
    assert m['cells']['AKo']['n'] == 0 and 'AKo' not in [x['hand'] for x in m['divergencias']]


def test_grupo_faixa_de_stack_e_sem_stack():
    """EP = UTG + UTG+1 (mesa de 9). A faixa <20 separa; sem stack a mao entra em n mas nao na
    cobertura, e a carta e a do assento do CHART: o UTG de mesa 8 e comparado com UTG+1."""
    maos = ([_m('UTG', 'AsKs', 'raise', stack=40) for _ in range(5)]
            + [_m('UTG+1', 'AsKs', 'raise', stack=40) for _ in range(5)]
            + [_m('UTG', 'AsKs', 'fold', stack=12) for _ in range(5)]
            + [_m('UTG', 'AsKs', 'fold', stack=None) for _ in range(2)])
    uid = _semeia(maos)
    ep = get_position_open_matrix(uid, 'EP', days=3650, last_n=0)
    assert ep['n'] == 17 and ep['cells']['AKs']['n'] == 17 and ep['cobertura'] == round(15 * 100 / 17)
    from leaklab.preflop_gto_ranges import balde_rfi
    esperado = (5 * float(villain_open_range('UTG', 40).get('T9s', 0)) + 5 * float(villain_open_range('UTG+1', 40).get('T9s', 0))
                + 5 * float(villain_open_range('UTG', 12).get('T9s', 0))) / 15
    assert abs(ep['cells']['T9s']['solver'] - esperado) < 0.002 and ep['cells']['T9s']['n'] == 0, (ep['cells']['T9s'], esperado)
    curto = get_position_open_matrix(uid, 'UTG', days=3650, last_n=0, stack_band='<20')
    assert curto['n'] == 5 and curto['cells']['AKs']['voce'] == 0.0 and curto['stack_band'] == '<20'
    # mesa de 8: o "UTG" e comparado com a carta do UTG+1 (chart pela distancia ao botao)
    uid = _semeia([_m('UTG', 'Ts9s', 'raise', stack=40, num_players=8) for _ in range(10)])
    m = get_position_open_matrix(uid, 'UTG', days=3650, last_n=0)
    assert m['cells']['T9s']['solver'] == round(float(villain_open_range('UTG+1', 40).get('T9s', 0.0)), 3)


def test_a_matriz_abre_com_TODAS_as_faixas_e_o_numero_BATE_com_a_grade():
    """O achado do Rullian (11/09): "em perfil por posicao ta mostrando um valor pra RFI na tela
    inicial, mas quando clico na posicao pra ver o spot detalhado o valor e diferente. RFI de
    17.2% pro UTG, clicando no spot o RFI esta 19.8%".

    Reproduzido exato no acervo dele: 17,2% em 3.690 oportunidades na GRADE (soma as
    profundidades) contra 19,8% em 1.557 na MATRIZ (so 40bb+, que era a faixa sugerida como
    padrao). Nao era erro de conta — com o mesmo recorte as duas batem na casa decimal.

    Este guarda inverte a politica de 09/09 (stack obrigatorio) e ancora na CONDICAO que
    importa: **ao abrir sem filtro, o numero da matriz e o mesmo da grade.** Dois numeros para a
    mesma coisa, um na porta de entrada e outro na tela seguinte, custa mais confianca do que
    uma media entre cartas custa em precisao — desde que a tela DECLARE a mistura, o que a
    ultima assercao exige.

    Quebrado de proposito (voltando a sugerir a faixa por padrao), o `voce_pct` deixa de bater
    com o `rfi` da grade e o teste acusa com os dois numeros no erro."""
    from database.repositories import faixas_do_jogador
    # mesa 8: 6 maos a 45bb (40+) e 3 a 25bb (20-40); mesa 6: 10 maos a 12bb (<20).
    # As 19 maos sao do CO, e 13 delas abrem: o numero da grade nao pode depender da faixa.
    # Acima do piso de 100 maos do resumo: com amostra menor o `voce_pct` volta None de
    # proposito (a matriz nao afirma um numero que a amostra nao sustenta) e a comparacao com a
    # grade ficaria vazia. 60 a 45bb (40+), 30 a 25bb (20-40) e 30 a 12bb (<20) = 120.
    uid = _semeia([_m('CO', 'AsKs', 'raise', stack=45, num_players=8) for _ in range(60)]
                  + [_m('CO', 'AsKs', 'fold', stack=25, num_players=8) for _ in range(30)]
                  + [_m('CO', 'AsKs', 'raise', stack=12, num_players=6) for _ in range(20)]
                  + [_m('CO', 'AsKs', 'fold', stack=12, num_players=6) for _ in range(10)])
    # A sugestao continua existindo: os chips precisam dizer onde ha mao. O que mudou e que ela
    # NAO e aplicada sozinha.
    todas = faixas_do_jogador(uid, days=3650, last_n=0)
    assert todas['sugerida'] == '40+' and todas['n'] == 120, todas
    mesa8 = faixas_do_jogador(uid, days=3650, last_n=0, mesa='8max')
    assert mesa8['sugerida'] == '40+' and mesa8['n'] == 90, mesa8

    from api.app import app
    from database.auth import generate_token
    h = {'Authorization': 'Bearer %s' % generate_token(uid, 'player')}
    c = app.test_client()

    g = c.get('/metrics/player-stats/by-position?days=3650', headers=h).get_json()
    linha = next(p for p in g['positions'] if p['position'] == 'CO')
    rfi_da_grade = linha['stats']['rfi']['value']

    m = c.get('/metrics/player-stats/by-position/hands?position=CO&days=3650', headers=h).get_json()
    assert m['stack_band'] is None and m['stack_auto'] is False, (m['stack_band'], m['stack_auto'])
    assert m['n'] == 120, m['n']                      # TODAS as maos, nao so as da faixa sugerida
    assert m['voce_pct'] == rfi_da_grade, (
        'a matriz aberta sem filtro tem de mostrar o MESMO numero da grade',
        m['voce_pct'], rfi_da_grade)

    # `stack=todos` explicito e a mesma coisa, e nao mais um 400
    mt = c.get('/metrics/player-stats/by-position/hands?position=CO&days=3650&stack=todos',
               headers=h)
    assert mt.status_code == 200, mt.status_code
    assert mt.get_json()['voce_pct'] == rfi_da_grade, mt.get_json()['voce_pct']

    # e estreitar por profundidade continua sendo escolha do jogador, com o numero mudando
    m40 = c.get('/metrics/player-stats/by-position/hands?position=CO&days=3650&stack=40%2B',
                headers=h).get_json()
    assert m40['stack_band'] == '40+' and m40['n'] == 60, (m40['stack_band'], m40['n'])
    assert m40['voce_pct'] == 100.0, m40['voce_pct']   # as 60 de 45bb abriram todas
    assert m40['voce_pct'] != rfi_da_grade             # e por isso o padrao nao podia ser este

    # A MISTURA tem de ser declarada: com todas as faixas a referencia do solver e media entre
    # cartas de profundidades diferentes, e a legenda precisa poder dizer isso. Ausencia calada
    # aqui seria o mesmo defeito do filtro obrigatorio, so que silencioso.
    profs = m.get('profundidades_da_carta') or []
    assert len(profs) >= 2, ('a composicao tem de declarar as profundidades misturadas', profs)
    assert sum(p['n'] for p in profs) <= m['n'], profs
    assert all(p.get('profundidade') for p in profs), profs
    # e a composicao por assento continua respondendo pela outra dimensao
    assert m.get('composicao_da_carta'), m.get('composicao_da_carta')
    print('OK  test_a_matriz_abre_com_TODAS_as_faixas_e_o_numero_BATE_com_a_grade (grade %s%%)'
          % rfi_da_grade)


def test_a_matriz_soma_os_tamanhos_de_mesa_e_DECLARA_a_faixa_de_jogadores_por_agir():
    """Rullian, 10/09: "essa parte de selecionar numero de jogadores e estranha... considerando o
    PokerTracker, nao existe essa separacao por numero de jogadores".

    Medido no acervo dele ANTES de tirar (21 linhas, do UTG ao SB, 3 faixas de stack): somar os
    tamanhos custa mediana 0,6 pp no numero do solver (max 3,9) e MULTIPLICA a amostra por 2,3.
    O custo esta concentrado no UTG, o unico assento que existe em TODA mesa: 5 cartas possiveis,
    de 16,4% a 29,5%. Do LJ para o botao a carta e UMA so (o assento conta do botao), e o UTG+1
    so existe em mesa 8 e 9, com duas cartas vizinhas.

    Entao a tela declara a faixa NO UTG em vez de pedir um filtro em toda parte. O `stack`
    tambem deixou de ser obrigatorio em 11/09 (ver
    `test_a_matriz_abre_com_TODAS_as_faixas_e_o_numero_BATE_com_a_grade`): a matriz abre no
    recorte da grade e a profundidade vira escolha, com a mistura DECLARADA em
    `profundidades_da_carta`."""
    from api.app import app
    from database.auth import generate_token
    # o mesmo UTG em mesa 9 (8 por agir) e em mesa 6 (5 por agir), e um BTN de controle
    uid = _semeia([_m('UTG', 'AsKs', 'raise', stack=45, num_players=9) for _ in range(6)]
                  + [_m('UTG', 'AsKs', 'raise', stack=45, num_players=6) for _ in range(4)]
                  + [_m('BTN', 'AsKs', 'raise', stack=45, num_players=6) for _ in range(5)])
    c = app.test_client()
    h = {'Authorization': 'Bearer %s' % generate_token(uid, 'player')}

    u = c.get('/metrics/player-stats/by-position/hands?position=UTG&days=3650', headers=h).get_json()
    assert u['mesa'] is None, u['mesa']                       # nao fixa mais o tamanho
    assert u['n'] == 10, u['n']                               # soma as duas mesas
    assert u['assento_da_carta'] is None                      # mais de uma carta: nao promete uma
    comp = {x['assento']: x for x in u['composicao_da_carta']}
    assert set(comp) == {'UTG', 'LJ'}, comp                   # mesa 9 -> UTG; mesa 6 -> LJ
    assert comp['UTG']['atras'] == 8 and comp['LJ']['atras'] == 5, comp
    assert comp['UTG']['n'] == 6 and comp['LJ']['n'] == 4, comp

    # o BTN nao mistura: o assento conta do botao e a carta e uma so
    b = c.get('/metrics/player-stats/by-position/hands?position=BTN&days=3650', headers=h).get_json()
    assert b['assento_da_carta'] == 'BTN' and b['jogadores_atras'] == 2, (b['assento_da_carta'], b['jogadores_atras'])
    assert len(b['composicao_da_carta']) == 1, b['composicao_da_carta']

    # `stack=todos` e 200 desde 11/09 (e o padrao), e `?mesa=` continua aceito para quem
    # quiser o recorte
    assert c.get('/metrics/player-stats/by-position/hands?position=UTG&stack=todos', headers=h).status_code == 200
    fix = c.get('/metrics/player-stats/by-position/hands?position=UTG&days=3650&mesa=9max', headers=h).get_json()
    assert fix['n'] == 6 and fix['assento_da_carta'] == 'UTG', (fix['n'], fix['assento_da_carta'])


def test_os_chips_do_modal_contam_O_ASSENTO_e_nao_a_mesa_toda():
    """Dono, 09/09, no modal em BTN / 9 jogadores / 40bb+: "eu geralmente jogo sit and go de
    9max, imagino que eu deveria ter algumas maos aqui na abertura com 9 jogadores... pq nao
    aparecem?". O chip de stack dizia 114 e o recorte entregou 1: os 114 eram de TODOS os
    assentos com 9 jogadores. No botao, abrir com o pote intacto exige seis folds antes.

    Contador que promete volume que o recorte nao tem manda o jogador clicar no vazio. Agora as
    duas distribuicoes filtram pelo assento, e o recorte automatico e o melhor DAQUELE assento."""
    from api.app import app
    from database.auth import generate_token
    # UTG so em mesa de 9 a 45bb; BTN so em mesa de 6 a 12bb. Nenhum dos dois tem mao no
    # recorte do outro, e e isso que os chips tem de mostrar.
    uid = _semeia([_m('UTG', 'AsKs', 'raise', stack=45, num_players=9) for _ in range(7)]
                  + [_m('BTN', 'AsKs', 'raise', stack=12, num_players=6) for _ in range(4)])
    c = app.test_client()
    h = {'Authorization': 'Bearer %s' % generate_token(uid, 'player')}

    # O stack vai EXPLICITO porque o padrao deixou de ser automatico em 11/09 (a matriz abre
    # em todas as faixas, para bater com a grade). O que este teste defende segue igual: os
    # chips contam o ASSENTO, nao a mesa toda.
    u = c.get('/metrics/player-stats/by-position/hands?position=UTG&days=3650&stack=40%2B',
              headers=h).get_json()
    assert u['mesa'] is None and u['stack_band'] == '40+' and u['n'] == 7, (u['mesa'], u['stack_band'], u['n'])
    assert [(x['mesa'], x['n']) for x in u['distribuicao_de_mesas']['mesas']] == [('9max', 7)], u['distribuicao_de_mesas']
    assert [(x['faixa'], x['n']) for x in u['distribuicao_de_stacks']['faixas']] == [('40+', 7)], u['distribuicao_de_stacks']

    b = c.get('/metrics/player-stats/by-position/hands?position=BTN&days=3650&stack=%3C20',
              headers=h).get_json()
    # os chips do BTN falam do BTN: a faixa <20 tem as 4 maos dele, e a mesa 9 (onde ele nao tem
    # mao nenhuma) nao aparece nem como opcao
    assert b['mesa'] is None and b['stack_band'] == '<20' and b['n'] == 4, (b['mesa'], b['stack_band'], b['n'])
    assert [(x['mesa'], x['n']) for x in b['distribuicao_de_mesas']['mesas']] == [('6max', 4)], b['distribuicao_de_mesas']
    # e o chip NAO oferece a mesa de 9, onde o BTN nao tem mao nenhuma
    assert '9max' not in [x['mesa'] for x in b['distribuicao_de_mesas']['mesas']]


def test_acima_do_teto_a_carta_de_100bb_fala_e_abaixo_do_piso_continua_muda():
    """AY-36 (dono, 09/09): "podemos usar a carta de 100bb nessa condicao de stack > 100bb?".
    Sim, e so nessa ponta. As duas pontas eram simetricas e a simetria custava: KQs a 262bb saia
    "sem carta" e a grade a desenhava como fold; 341 oportunidades de RFI do acervo (2,2%)
    ficavam sem range de vilao. A ponta RASA continua recusando: a 0,2bb a carta de 10bb e outro
    regime e ja produziu acusacao falsa medida.

    O guarda olha as DUAS pontas de proposito: saturar a rasa junto seria o conserto que causa
    dano que o defeito nao causava (regra 7)."""
    from leaklab.preflop_gto_ranges import balde_rfi_ou_none, _balde_da_carta, _stack_bucket
    fundo = _stack_bucket(10_000.0)
    for s in (133, 163, 262, 304, 1_000):
        assert balde_rfi_ou_none(s) == fundo, (s, balde_rfi_ou_none(s))     # acima do teto: a mais funda
    assert balde_rfi_ou_none(100) == fundo and balde_rfi_ou_none(120) == fundo
    for s in (0.2, 1.0, 2.0):
        assert _balde_da_carta(s) is None, (s, _balde_da_carta(s))          # abaixo do piso: muda
    # e a matriz deixa de ter "sem carta" por profundidade funda: KQs a 262bb ganha a carta de
    # 100bb DELA, nao a do recorte, e entra na cobertura
    uid = _semeia([_m('UTG', 'AsKs', 'raise', stack=40) for _ in range(9)]
                  + [_m('UTG', 'KhQh', 'raise', stack=262)])
    m = get_position_open_matrix(uid, 'UTG', days=3650, last_n=0)
    assert m['cobertura'] == 100, m['cobertura']
    assert m['cells']['KQs']['solver'] == round(float(villain_open_range('UTG', 262).get('KQs', 0.0)), 3)


def test_mao_recebida_sem_carta_mostra_a_carta_do_recorte_e_nao_um_fold():
    """Dono, 09/09, no UTG de mesa 8 a 40bb+: "me parece bem estranho o solver nao abrir KQs e
    A6s". O solver abre as duas 100%. KQs tinha caido UMA vez, a 262bb, acima do teto da carta:
    a celula saia `solver=None` e a grade pinta None igual a 0% — "sem carta" virava "o solver
    folda". Agora a mao recebida sem carta mostra a carta do RECORTE, como a mao nunca
    recebida; a cobertura segue contando-a como sem carta (ela nao entra no `solver_pct`)."""
    from leaklab.preflop_gto_ranges import balde_rfi_ou_none
    # 09/09, mais tarde no mesmo dia: 262bb PASSOU a ter carta (AY-36). A mao sem carta agora e a
    # de stack abaixo do piso, que continua recusada de proposito.
    assert balde_rfi_ou_none(1.0) is None, 'o teste precisa de uma profundidade SEM carta'
    uid = _semeia([_m('UTG', 'AsKs', 'raise', stack=40) for _ in range(9)]
                  + [_m('UTG', 'KhQh', 'raise', stack=1.0)])          # a unica KQs, sem carta
    m = get_position_open_matrix(uid, 'UTG', days=3650, last_n=0)
    kqs = m['cells']['KQs']
    esperado = round(float(villain_open_range('UTG', 40).get('KQs', 0.0)), 3)
    assert esperado > 0, 'o teste precisa de uma mao que a carta do UTG a 40bb abra'
    assert kqs['n'] == 1 and kqs['voce'] == 1.0, kqs
    assert kqs['solver'] == esperado, (kqs['solver'], esperado)            # a carta do recorte, nao None
    assert m['cobertura'] == 90, m['cobertura']                             # 9 de 10 com carta: honesto
    assert all(c['solver'] is not None for c in m['cells'].values())


def test_o_endpoint_aceita_assento_e_grupo_e_recusa_a_BB():
    uid = _semeia([_m('CO', 'AsKs', 'raise') for _ in range(3)])
    from api.app import app
    from database.auth import generate_token
    h = {'Authorization': 'Bearer %s' % generate_token(uid, 'player')}
    c = app.test_client()
    r = c.get('/metrics/player-stats/by-position/hands?position=CO', headers=h)
    assert r.status_code == 200 and r.get_json()['cells']['AKs']['n'] == 3 and r.get_json()['minimo_maos'] == 8, r.get_data(as_text=True)[:200]
    assert c.get('/metrics/player-stats/by-position/hands?position=EP&stack=40%2B', headers=h).status_code == 200
    assert c.get('/metrics/player-stats/by-position/hands?position=BB', headers=h).status_code == 400
    assert c.get('/metrics/player-stats/by-position/hands?position=XX', headers=h).status_code == 400
    assert c.get('/metrics/player-stats/by-position/hands?position=CO&stack=99', headers=h).status_code == 400


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
