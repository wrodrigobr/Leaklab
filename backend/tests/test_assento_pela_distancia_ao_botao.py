# -*- coding: utf-8 -*-
"""O assento e nomeado pela DISTANCIA AO BOTAO, em qualquer tamanho de mesa (AY-20, 07/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

O Rullian, olhando a grade por posicao em prod: "tem bem pouca amostra pro Lojack; como ele
determina entre Lojack e UTG+2?". O parser nomeia contando a partir do UTG, entao "LJ" so
existe em mesa de 9 (ele jogou 107 maos em mesa de 9 e 20 mil em mesas de 7 e 8). Em mesa de
8, o que chamavamos de "UTG+2" tem HJ, CO e BTN atras: e o Lojack. A linha "UTG+2" da grade
misturava o UTG+2 de mesa 9 com o LJ de mesa 8, com a regua do chart errado. O motor de
veredito ja pareia por jogadores atras (`_mapa_da_mesa`); a grade e o HUD por assento e que
liam o rotulo cru.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. O CASE em SQL (`sql_assento`) e o MESMO mapa das ranges, para toda mesa de 2 a 9.
2. A grade, o HUD por assento, o detalhe "contra quem", o DNA e a matriz leem o assento
   relativo ao botao: em mesa de 8, "UTG+2" cai na linha LJ, "UTG" na linha UTG+1.
3. Mesa de 9, mesa sem `num_players` e os assentos que nao mudam de nome (BTN/CO/HJ/SB/BB)
   ficam como estao.
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
import database.repositories as repo                                           # noqa: E402
from database.repositories import (_adapt, get_gto_alignment_matrix,           # noqa: E402
                                   get_player_stats, get_player_stats_by_position,
                                   get_position_stat_detail, sql_assento)
from leaklab.preflop_gto_ranges import _mapa_da_mesa                           # noqa: E402


def _semeia(maos):
    """`maos`: dicts com position, num_players, action_taken e opcionais."""
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('botao', 'botao@t.local', 'senha12345', 'player')
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,played_at,imported_at) "
                        "VALUES (1,?,'T1','pokerstars','Hero','2026-09-01','2026-09-01')"), (uid,))
    for i, m in enumerate(maos):
        conn.execute(_adapt("INSERT INTO decisions (tournament_id,hand_id,street,position,num_players,action_taken,"
                            "best_action,score,label,facing_bet,facing_limp,effective_stack_bb,"
                            "preflop_raises_faced,hero_was_aggressor,vs_position,is_3bet,gto_label) "
                            "VALUES (1,?,?,?,?,?,'raise',0.1,'standard',?,?,?,?,?,?,?,?)"),
                     (m.get('hand_id', 'H%d' % i), m.get('street', 'preflop'), m['position'], m.get('num_players'),
                      m['action_taken'], m.get('facing_bet', 0), m.get('facing_limp', 0), m.get('effective_stack_bb', 30),
                      m.get('preflop_raises_faced', 0), m.get('hero_was_aggressor', 0), m.get('vs_position'),
                      m.get('is_3bet', 0), m.get('gto_label', 'gto_correct')))
    conn.commit(); conn.close()
    return uid


def _m(pos, n, acao, **kw):
    d = {'position': pos, 'num_players': n, 'action_taken': acao}
    d.update(kw)
    return d


def test_o_case_em_sql_e_o_mesmo_mapa_das_ranges_para_toda_mesa():
    """Para cada mesa de 2 a 9 e cada rotulo que o mapa renomeia, o SQL devolve o mesmo nome.
    Varredura N+1: uma mesa nova no mapa sem ramo no CASE acusa."""
    sql = sql_assento()
    for n in range(2, 10):
        for cru, nome in _mapa_da_mesa(n).items():
            if cru != nome:
                assert "d.num_players = %d AND d.position = '%s' THEN '%s'" % (n, cru, nome) in sql, (n, cru, nome)
    # mesa de 8: o 4o assento e o Lojack, o 1o e UTG+1
    assert "d.num_players = 8 AND d.position = 'UTG+2' THEN 'LJ'" in sql
    assert "d.num_players = 8 AND d.position = 'UTG' THEN 'UTG+1'" in sql


def test_na_mesa_de_8_o_UTG2_cai_na_linha_LJ_e_o_UTG_na_UTG1():
    uid = _semeia([_m('UTG+2', 8, 'raise' if i % 2 else 'fold') for i in range(120)]
                  + [_m('UTG', 8, 'raise') for _ in range(50)]
                  + [_m('UTG+2', 9, 'fold') for _ in range(30)]          # mesa de 9: continua UTG+2
                  + [_m('BTN', 8, 'raise') for _ in range(20)])          # BTN nao muda de nome
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    por = {l['position']: l['hands'] for l in grade['positions']}
    assert por == {'UTG+1': 50, 'UTG+2': 30, 'LJ': 120, 'BTN': 20}, por
    # e o HUD por assento le o mesmo conjunto (o teste de igualdade da grade depende disto)
    assert get_player_stats(uid, days=3650, last_n=0, position='LJ')['total_hands'] == 120
    assert get_player_stats(uid, days=3650, last_n=0, position='UTG+2')['total_hands'] == 30
    assert get_player_stats(uid, days=3650, last_n=0, position='UTG')['total_hands'] == 0


def test_sem_num_players_o_rotulo_cru_vale():
    uid = _semeia([_m('UTG+2', None, 'raise') for _ in range(10)] + [_m('MP1', None, 'raise') for _ in range(5)])
    por = {l['position']: l['hands'] for l in get_player_stats_by_position(uid, days=3650, last_n=0)['positions']}
    assert por == {'UTG+2': 10, 'LJ': 5}, por      # MP1 e LJ pelos aliases, como antes


def test_o_vilao_tambem_e_nomeado_pelo_botao_no_detalhe_e_na_referencia():
    """BB enfrentando open do "UTG+2" de mesa 8: no detalhe a linha e "LJ" e a referencia e a
    carta BB vs LJ, nao BB vs UTG+2."""
    uid = _semeia([_m('BB', 8, 'call', facing_bet=2.5, preflop_raises_faced=1, vs_position='UTG+2', effective_stack_bb=40) for _ in range(40)])
    d = get_position_stat_detail(uid, 'BB', 'three_bet', days=3650, last_n=0)
    assert [r['vs'] for r in d['rows']] == ['LJ'], d['rows']
    assert list(d['rows'][0]['ref']['pesos']).pop().endswith('vs LJ'), d['rows'][0]['ref']


def test_o_dna_e_a_matriz_leem_o_assento_pelo_botao():
    """Mesa de 8, "UTG+2" (= LJ) com 100% de raise e BTN passivo: o DNA tem de ver o LJ como
    assento CEDO (grupo MP), e a matriz de alinhamento tem de por as maos na linha MP."""
    uid = _semeia([_m('UTG+2', 8, 'raise', street='preflop') for _ in range(40)]
                  + [_m('BTN', 8, 'call', street='preflop') for _ in range(40)])
    m = get_gto_alignment_matrix(uid, since_days=3650, last_n=0)
    por = {}
    for c in m['cells']:
        por[c['position']] = por.get(c['position'], 0) + c['n']
    assert por.get('MP') == 40 and por.get('EP', 0) == 0, por


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
