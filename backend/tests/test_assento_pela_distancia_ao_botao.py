# -*- coding: utf-8 -*-
"""O ROTULO do assento segue a convencao dos jogadores; o CHART segue a distancia ao botao (AY-20, 07/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

O Rullian, olhando a grade por posicao em prod: "tem bem pouca amostra pro Lojack; como ele
determina entre Lojack e UTG+2?". O parser nomeia contando a partir do UTG, entao "LJ" so
existe em mesa de 9 (ele jogou 107 maos em mesa de 9 e 20 mil em mesas de 7 e 8). Em mesa de
8, o que chamavamos de "UTG+2" tem HJ, CO e BTN atras: e o Lojack. A linha "UTG+2" da grade
misturava o UTG+2 de mesa 9 com o LJ de mesa 8, com a regua do chart errado. O motor de
veredito ja pareia por jogadores atras (`_mapa_da_mesa`); a grade e o HUD por assento e que
liam o rotulo cru.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

O dono, depois da 1a versao: "UTG sempre tem na mesa; o que as vezes nao tem e o UTG+2". Dois
mapas, dois usos:
1. ROTULO (`sql_assento`): UTG e sempre o primeiro; LJ/HJ/CO/BTN contam do botao; quando a
   mesa encolhe some o meio. Mesa 8: UTG UTG+1 LJ HJ CO BTN. Mesa 7: UTG LJ HJ CO BTN.
2. CHART (`sql_assento_chart`): por jogadores atras, o MESMO mapa das ranges, para toda mesa
   de 2 a 9. O UTG de mesa 8 e comparado com a carta do UTG+1.
3. Mesa de 9, mesa sem `num_players` e BTN/CO/HJ/SB/BB ficam como estao.
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
from database.repositories import (ROTULO_POR_MESA, _adapt, get_gto_alignment_matrix,  # noqa: E402
                                   get_player_stats, get_player_stats_by_position,
                                   get_position_stat_detail, sql_assento, sql_assento_chart)
from leaklab.preflop_gto_ranges import _mapa_da_mesa, balde_rfi, rfi_pct_do_chart  # noqa: E402


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
                      bool(m.get('is_3bet', 0)), m.get('gto_label', 'gto_correct')))
    conn.commit(); conn.close()
    return uid


def _m(pos, n, acao, **kw):
    d = {'position': pos, 'num_players': n, 'action_taken': acao}
    d.update(kw)
    return d


def test_o_chart_e_o_mesmo_mapa_das_ranges_para_toda_mesa():
    """Para cada mesa de 2 a 9 e cada rotulo que o mapa renomeia, o SQL do CHART devolve o
    mesmo nome. Varredura N+1: uma mesa nova no mapa sem ramo no CASE acusa."""
    sql = sql_assento_chart()
    for n in range(2, 10):
        for cru, nome in _mapa_da_mesa(n).items():
            if cru != nome:
                assert "d.num_players = %d AND d.position = '%s' THEN '%s'" % (n, cru, nome) in sql, (n, cru, nome)
    assert "d.num_players = 8 AND d.position = 'UTG' THEN 'UTG+1'" in sql      # 5 atras


def test_o_rotulo_segue_a_convencao_UTG_sempre_e_some_o_meio():
    sql = sql_assento()
    assert "d.num_players = 8 AND d.position = 'UTG+2' THEN 'LJ'" in sql
    assert "d.num_players = 7 AND d.position = 'UTG+1' THEN 'LJ'" in sql
    assert "d.position = 'UTG' THEN" not in sql, 'UTG nunca muda de nome no rotulo'
    assert ROTULO_POR_MESA[(8, 'UTG+2')] == 'LJ' and ROTULO_POR_MESA[(7, 'UTG+1')] == 'LJ'


def test_na_mesa_de_8_o_UTG_fica_UTG_o_UTG2_vira_LJ_e_a_regua_usa_o_chart_do_UTG1():
    uid = _semeia([_m('UTG+2', 8, 'raise' if i % 2 else 'fold') for i in range(120)]
                  + [_m('UTG', 8, 'raise' if i % 2 else 'fold', effective_stack_bb=40) for i in range(120)]
                  + [_m('UTG+2', 9, 'fold') for _ in range(30)]          # mesa de 9: continua UTG+2
                  + [_m('BTN', 8, 'raise') for _ in range(20)])          # BTN nao muda de nome
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    por = {l['position']: l['hands'] for l in grade['positions']}
    assert por == {'UTG': 120, 'UTG+2': 30, 'LJ': 120, 'BTN': 20}, por
    # HUD por assento le o mesmo conjunto (o teste de igualdade da grade depende disto)
    assert get_player_stats(uid, days=3650, last_n=0, position='LJ')['total_hands'] == 120
    assert get_player_stats(uid, days=3650, last_n=0, position='UTG')['total_hands'] == 120
    # a regua do UTG de mesa 8 e a carta do UTG+1 (5 atras), nao a do UTG
    utg = next(l for l in grade['positions'] if l['position'] == 'UTG')['stats']['rfi']['ref']
    c_utg1 = rfi_pct_do_chart('UTG+1', balde_rfi(40)); c_utg = rfi_pct_do_chart('UTG', balde_rfi(40))
    assert c_utg1 != c_utg
    assert round((utg['lo'] + utg['hi']) / 2, 1) == c_utg1, (utg, c_utg1)


def test_sem_num_players_o_rotulo_cru_vale():
    uid = _semeia([_m('UTG+2', None, 'raise') for _ in range(10)] + [_m('MP1', None, 'raise') for _ in range(5)])
    por = {l['position']: l['hands'] for l in get_player_stats_by_position(uid, days=3650, last_n=0)['positions']}
    assert por == {'UTG+2': 10, 'LJ': 5}, por      # MP1 e LJ pelos aliases, como antes


def test_o_vilao_tem_rotulo_pela_convencao_e_chart_pela_distancia():
    """BB enfrentando opens de mesa 8: a linha do "UTG+2" e "LJ" (rotulo e chart coincidem); a
    linha do "UTG" continua "UTG" no rotulo, mas a referencia e a carta BB vs UTG+1 (chart)."""
    uid = _semeia([_m('BB', 8, 'call', facing_bet=2.5, preflop_raises_faced=1, vs_position='UTG+2', effective_stack_bb=40) for _ in range(40)]
                  + [_m('BB', 8, 'call', facing_bet=2.5, preflop_raises_faced=1, vs_position='UTG', effective_stack_bb=40) for _ in range(40)])
    d = get_position_stat_detail(uid, 'BB', 'three_bet', days=3650, last_n=0)
    assert [r['vs'] for r in d['rows']] == ['UTG', 'LJ'], d['rows']               # rotulo: UTG e LJ
    assert list(d['rows'][1]['ref']['pesos']).pop().endswith('vs LJ'), d['rows'][1]['ref']
    assert list(d['rows'][0]['ref']['pesos']).pop().endswith('vs UTG+1'), d['rows'][0]['ref']   # chart: o UTG de mesa 8 e o UTG+1


def test_o_dna_e_a_matriz_leem_o_rotulo():
    """Mesa de 8, "UTG+2" (= LJ) com 100% de raise e BTN passivo: o DNA tem de ver o LJ como
    assento CEDO (grupo MP), e a matriz de alinhamento tem de por as maos na linha MP."""
    uid = _semeia([_m('UTG+2', 8, 'raise', street='preflop') for _ in range(40)]
                  + [_m('BTN', 8, 'call', street='preflop') for _ in range(40)])
    m = get_gto_alignment_matrix(uid, since_days=3650, last_n=0)
    por = {}
    for c in m['cells']:
        por[c['position']] = por.get(c['position'], 0) + c['n']
    assert por.get('MP') == 40 and por.get('EP', 0) == 0, por



def test_no_detalhe_o_chart_do_HEROI_tambem_e_por_distancia():
    """Heroi "UTG" de mesa 8 (rotulo UTG, chart UTG+1) abriu e levou 3-bet do BTN: a referencia
    da linha e a carta UTG+1 vs BTN, nao UTG vs BTN. A BB nao serviria de heroi aqui: nao muda."""
    from leaklab.preflop_gto_ranges import _stack_bucket, fold3bet_pct_do_chart
    uid = _semeia([_m('UTG', 8, 'fold' if i % 2 else 'call', facing_bet=8, preflop_raises_faced=1, hero_was_aggressor=1,
                      vs_position='BTN', effective_stack_bb=30) for i in range(40)])     # 30bb: a carta existe nos dois
    d = get_position_stat_detail(uid, 'UTG', 'fold_to_3bet', days=3650, last_n=0)
    assert [r['vs'] for r in d['rows']] == ['BTN'], d['rows']
    ref = d['rows'][0]['ref']
    b = _stack_bucket(30)
    certo, errado = fold3bet_pct_do_chart('UTG+1', 'BTN', b), fold3bet_pct_do_chart('UTG', 'BTN', b)
    assert certo != errado, (certo, errado)
    assert round((ref['lo'] + ref['hi']) / 2, 1) == certo, (ref, certo, errado)

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
