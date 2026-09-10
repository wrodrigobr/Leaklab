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
2. O resumo (`voce_pct`) e igual ao RFI da grade no mesmo recorte; `cobertura` e a fracao com
   carta; sem stack nao ha carta (entra em `n`, nao na cobertura).
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


def test_o_stack_e_filtro_obrigatorio_e_abre_na_faixa_com_mais_maos():
    """Dono, 09/09: "no GTO Wizard somos obrigados a definir o stack, entao nao faz sentido o
    todos". A carta de abertura e funcao de assento, jogadores atras E profundidade; sem a
    profundidade fixa o numero do solver e uma media entre cartas.

    Tres coisas defendidas aqui: (1) `faixas_do_jogador` conta a faixa da MAO pela primeira
    decisao preflop e sugere a de mais maos, DENTRO da mesa em vigor; (2) sem `?stack=` os
    tres endpoints da grade abrem nessa faixa e DECLARAM (`stack_auto`); (3) `stack=todos` e
    400 como qualquer faixa desconhecida — aceitar de volta em silencio devolveria a media."""
    from database.repositories import faixas_do_jogador
    # mesa 8: 6 maos a 45bb (40+) e 3 a 25bb (20-40); mesa 6: 10 maos a 12bb (<20).
    # (10 e nao 9: empate de mesas desempata pela ordem 9,8,7,6 e o teste ficaria ambiguo)
    uid = _semeia([_m('CO', 'AsKs', 'raise', stack=45, num_players=8) for _ in range(6)]
                  + [_m('CO', 'AsKs', 'raise', stack=25, num_players=8) for _ in range(3)]
                  + [_m('CO', 'AsKs', 'raise', stack=12, num_players=6) for _ in range(10)])
    todas = faixas_do_jogador(uid, days=3650, last_n=0)
    assert todas['sugerida'] == '<20' and todas['n'] == 19, todas      # no total, a mesa 6 pesa mais
    mesa8 = faixas_do_jogador(uid, days=3650, last_n=0, mesa='8max')
    assert mesa8['sugerida'] == '40+' and mesa8['n'] == 9, mesa8       # DENTRO da mesa 8, e 40+
    assert [f['faixa'] for f in mesa8['faixas']] == ['40+', '20-40'], mesa8['faixas']

    from api.app import app
    from database.auth import generate_token
    h = {'Authorization': 'Bearer %s' % generate_token(uid, 'player')}
    c = app.test_client()
    # sem filtros: mesa mais jogada (6) e, dentro dela, a faixa com mais maos (<20)
    m = c.get('/metrics/player-stats/by-position/hands?position=CO&days=3650', headers=h).get_json()
    assert m['mesa'] == '6max' and m['stack_band'] == '<20' and m['stack_auto'] is True, (m['mesa'], m['stack_band'])
    assert m['n'] == 10, m['n']
    assert [f['faixa'] for f in m['distribuicao_de_stacks']['faixas']] == ['<20']
    # mesa fixada em 8: a faixa sugerida muda junto, porque e calculada dentro da mesa
    m8 = c.get('/metrics/player-stats/by-position/hands?position=CO&days=3650&mesa=8max', headers=h).get_json()
    assert m8['stack_band'] == '40+' and m8['stack_auto'] is True and m8['n'] == 6, (m8['stack_band'], m8['n'])
    # stack explicito vence e o payload diz que nao foi automatico
    m8b = c.get('/metrics/player-stats/by-position/hands?position=CO&days=3650&mesa=8max&stack=20-40', headers=h).get_json()
    assert m8b['stack_band'] == '20-40' and m8b['stack_auto'] is False and m8b['n'] == 3
    # A GRADE nao segue esta politica: ela SOMA TUDO (09/09 noite). Exigir os dois filtros la
    # esvaziou a grade do dono: piso de 100 maos por assento contra 36 no recorte.
    g = c.get('/metrics/player-stats/by-position?days=3650', headers=h).get_json()
    assert g['mesa'] is None and g['stack_band'] is None, (g['mesa'], g['stack_band'])
    assert g['stack_auto'] is False and g['mesa_auto'] is False
    assert g['total_hands'] == 19, g['total_hands']            # as 19 maos, nao as 10 da mesa 6
    # "todos" existe na grade e no painel dela, e NAO existe na matriz
    for url in ('/metrics/player-stats/by-position?days=3650&stack=todos',
                '/metrics/player-stats/by-position/detail?position=CO&stat=three_bet&stack=todos'):
        assert c.get(url, headers=h).status_code == 200, url
    assert c.get('/metrics/player-stats/by-position/hands?position=CO&stack=todos', headers=h).status_code == 400


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

    u = c.get('/metrics/player-stats/by-position/hands?position=UTG&days=3650', headers=h).get_json()
    assert u['mesa'] == '9max' and u['stack_band'] == '40+' and u['n'] == 7, (u['mesa'], u['stack_band'], u['n'])
    assert [(x['mesa'], x['n']) for x in u['distribuicao_de_mesas']['mesas']] == [('9max', 7)], u['distribuicao_de_mesas']
    assert [(x['faixa'], x['n']) for x in u['distribuicao_de_stacks']['faixas']] == [('40+', 7)], u['distribuicao_de_stacks']

    b = c.get('/metrics/player-stats/by-position/hands?position=BTN&days=3650', headers=h).get_json()
    # o modal do BTN abre no recorte DELE, nao no do UTG (que tem mais volume no total)
    assert b['mesa'] == '6max' and b['stack_band'] == '<20' and b['n'] == 4, (b['mesa'], b['stack_band'], b['n'])
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
