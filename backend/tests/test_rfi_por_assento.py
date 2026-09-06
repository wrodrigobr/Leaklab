# -*- coding: utf-8 -*-
"""A grade "voce contra o solver, por assento": RFI, 3-Bet e Fold 3-Bet do open, cada um com
a referencia do CHART, e o filtro de stack (AY-15, fases 1 e 2, 06/09).

── O que originou ─────────────────────────────────────────────────────────────────────────

O dono queria a regua de volta na grade por posicao e trouxe uma tabela de VPIP por assento.
Medida contra os nossos charts, a tabela era mais tight que o solver em todo assento (BTN
38-48 contra 51-55): folclore. A referencia que da para defender e o proprio chart, e a
metrica que o Rullian usa nos estudos e RFI, nao PFR (PFR inclui 3-bet). Depois de ver 12
colunas com uma regua so, o dono perguntou se nao ficava mais limpo mostrar so o que tem
chart. Fica: coluna entra quando existe carta para ela.

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. RFI conta SO com o pote intacto: raise em cima de limp nao e RFI, enfrentar raise nao e
   oportunidade, e a BB nunca tem (se todos foldam, a mao acaba).
2. A faixa de stack recorta pela `effective_stack_bb` da decisao; NULL so entra em "todos".
3. A referencia vem do chart nas profundidades (e, no 3-bet e no fold, contra QUEM) das maos
   do jogador, como percentil P20-P80 com folga declarada; a cauda nao alarga a faixa.
4. Fold 3-Bet da grade e o do OPEN (`fold_to_3bet_open`): so o abridor tem carta. O
   `fold_to_3bet` do PT4 (que conta 3-bet a frio) fica no HUD.
5. A grade so tem colunas com `ref`, e o endpoint rejeita faixa desconhecida em vez de
   devolver "todos" sob o rotulo errado.
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
from database.repositories import (FAIXAS_DE_STACK, MINIMO_DO_DETALHE,         # noqa: E402
                                   _GRADE_COM_VOLUME, _GRADE_SEMPRE, _adapt, get_player_stats,
                                   get_player_stats_by_position, get_position_stat_detail)
from leaklab.preflop_gto_ranges import (COBERTURA_MINIMA_VPIP_PFR, FOLGA_DA_REFERENCIA_PP,  # noqa: E402
                                        FOLGA_MINIMA_PP, _stack_bucket, balde_rfi,
                                        fold3bet_pct_do_chart, referencia_3bet_por_assento,
                                        referencia_fold3bet_por_assento,
                                        referencia_rfi_por_assento, referencia_vpip_pfr_por_assento,
                                        rfi_pct_do_chart, solver_na_primeira_decisao,
                                        tresbet_pct_do_chart)


def _semeia(maos):
    """`maos`: lista de dicts com position, action_taken e, opcionais, facing_bet, facing_limp,
    effective_stack_bb, preflop_raises_faced, hero_was_aggressor, vs_position."""
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('rfi', 'rfi@t.local', 'senha12345', 'player')
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,played_at,imported_at) "
                        "VALUES (1,?,'T1','pokerstars','Hero','2026-09-01','2026-09-01')"), (uid,))
    for i, m in enumerate(maos):
        conn.execute(_adapt("INSERT INTO decisions (tournament_id,hand_id,street,position,action_taken,"
                            "best_action,score,label,facing_bet,facing_limp,effective_stack_bb,"
                            "preflop_raises_faced,hero_was_aggressor,vs_position,is_3bet) "
                            "VALUES (1,?,'preflop',?,?,'raise',0.1,'standard',?,?,?,?,?,?,?)"),
                     (m.get('hand_id', 'H%d' % i), m['position'], m['action_taken'], m.get('facing_bet', 0), m.get('facing_limp', 0),
                      m.get('effective_stack_bb', 30), m.get('preflop_raises_faced', 0),
                      m.get('hero_was_aggressor', 0), m.get('vs_position'), m.get('is_3bet', 0)))
    conn.commit(); conn.close()
    return uid


def _m(pos, acao, **kw):
    d = {'position': pos, 'action_taken': acao}
    d.update(kw)
    return d


def test_rfi_conta_so_com_o_pote_intacto():
    """4 oportunidades no BTN (2 raise, 1 fold, 1 call): RFI 50. O raise em cima de limp e o
    raise enfrentando open NAO entram nem no numerador nem no denominador."""
    uid = _semeia([
        _m('BTN', 'raise'), _m('BTN', 'raise'), _m('BTN', 'fold'), _m('BTN', 'call'),
        _m('BTN', 'raise', facing_limp=1),                          # iso-raise: pote ja aberto
        _m('BTN', 'raise', facing_bet=2.5, preflop_raises_faced=1),  # 3-bet: enfrenta open
    ])
    s = get_player_stats(uid, days=3650, last_n=0, position='BTN')
    assert s['rfi'] == 50.0, s['rfi']
    assert s['pfr'] == round(4 / 6 * 100, 1), s['pfr']   # a conta antiga ve 4 em 6: PFR nao serve


def test_a_BB_nao_tem_RFI_e_o_SB_tem():
    uid = _semeia([_m('BB', 'raise'), _m('BB', 'call'), _m('SB', 'raise'), _m('SB', 'call')])
    assert get_player_stats(uid, days=3650, last_n=0, position='BB')['rfi'] is None
    assert get_player_stats(uid, days=3650, last_n=0, position='SB')['rfi'] == 50.0
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    por = {l['position']: l['stats'] for l in grade['positions']}
    assert 'rfi' not in por['BB'], por['BB']


def test_fold_3bet_do_open_e_so_quando_o_heroi_abriu():
    """Hero abre do CO e leva 3-bet do BTN 2x (folda 1): 50%. A BB enfrentando open + 3-bet a
    frio entra no fold_to_3bet do PT4 (HUD), mas NAO no da grade: so o abridor tem carta."""
    uid = _semeia([
        _m('CO', 'fold', facing_bet=7, preflop_raises_faced=1, hero_was_aggressor=1, vs_position='BTN'),
        _m('CO', 'call', facing_bet=7, preflop_raises_faced=1, hero_was_aggressor=1, vs_position='BTN'),
        _m('BB', 'fold', facing_bet=7, preflop_raises_faced=2, hero_was_aggressor=0, vs_position='BTN'),  # a frio
    ])
    hud = get_player_stats(uid, days=3650, last_n=0)
    assert hud['fold_to_3bet_open'] == 50.0, hud['fold_to_3bet_open']
    assert hud['fold_to_3bet'] == round(2 / 3 * 100, 1), hud['fold_to_3bet']     # PT4: 3 oportunidades
    assert get_player_stats(uid, days=3650, last_n=0, position='BB')['fold_to_3bet_open'] is None


def test_a_faixa_de_stack_recorta_pela_effective_stack_bb():
    uid = _semeia([_m('CO', 'raise', effective_stack_bb=60), _m('CO', 'fold', effective_stack_bb=30),
                   _m('CO', 'raise', effective_stack_bb=12), _m('CO', 'fold', effective_stack_bb=None)])
    todos = get_player_stats(uid, days=3650, last_n=0, position='CO')
    assert todos['total_hands'] == 4 and todos['rfi'] == 50.0, todos
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='40+')['rfi'] == 100.0
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='20-40')['rfi'] == 0.0
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='<20')['rfi'] == 100.0
    uid = _semeia([_m('CO', 'raise', effective_stack_bb=40.0), _m('CO', 'fold', effective_stack_bb=39.9)])
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='40+')['total_hands'] == 1
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='20-40')['total_hands'] == 1


def test_a_referencia_de_RFI_e_o_percentil_dos_charts_das_suas_maos_com_folga():
    """So 100bb: faixa = chart de 100bb +- folga. Metade 100bb e metade 30bb: P20 cai no menor
    chart e P80 no maior. Uma mao de 30bb em vinte: a cauda NAO alarga a faixa."""
    c100 = rfi_pct_do_chart('BTN', balde_rfi(100))
    c30 = rfi_pct_do_chart('BTN', balde_rfi(30))
    assert c100 and c30 and c100 != c30, (c100, c30)
    f = FOLGA_DA_REFERENCIA_PP
    ref = referencia_rfi_por_assento('BTN', [100] * 10)
    assert (ref['lo'], ref['hi']) == (round(c100 - f, 1), round(c100 + f, 1)), ref
    assert ref['cobertura'] == 100 and ref['pesos'] == {balde_rfi(100): 100}
    ref = referencia_rfi_por_assento('BTN', [100] * 5 + [30] * 5)
    assert ref['lo'] == round(min(c100, c30) - f, 1) and ref['hi'] == round(max(c100, c30) + f, 1), ref
    ref = referencia_rfi_por_assento('BTN', [100] * 19 + [30])
    assert (ref['lo'], ref['hi']) == (round(c100 - f, 1), round(c100 + f, 1)), ref
    assert balde_rfi(30) in ref['pesos']                     # mas aparece nos pesos
    assert referencia_rfi_por_assento('BB', [30] * 10) is None
    assert referencia_rfi_por_assento('BTN', []) is None


def test_a_referencia_de_3bet_pondera_por_QUEM_abriu():
    """BB contra UTG e BB contra BTN a 40bb sao cartas diferentes; a faixa segue a mistura."""
    b = _stack_bucket(40)
    vs_utg = tresbet_pct_do_chart('BB', 'UTG', b)
    vs_btn = tresbet_pct_do_chart('BB', 'BTN', b)
    assert vs_utg and vs_btn and vs_utg != vs_btn, (vs_utg, vs_btn)
    f = FOLGA_DA_REFERENCIA_PP
    ref = referencia_3bet_por_assento('BB', [('UTG', 40)] * 10)
    assert (ref['lo'], ref['hi']) == (round(vs_utg - f, 1), round(vs_utg + f, 1)), ref
    ref = referencia_3bet_por_assento('BB', [('UTG', 40)] * 5 + [('BTN', 40)] * 5)
    assert ref['lo'] == round(min(vs_utg, vs_btn) - f, 1) and ref['hi'] == round(max(vs_utg, vs_btn) + f, 1), ref
    assert set(ref['pesos']) == {'%s vs UTG' % b, '%s vs BTN' % b}
    # abridor sem carta para este par nao conta, e a cobertura diz isso
    ref = referencia_3bet_por_assento('UTG+1', [('UTG', 40)] * 8 + [('BTN', 40)] * 2)   # BTN nunca abre antes do UTG+1
    assert ref['cobertura'] == 80, ref


def test_a_referencia_de_fold_3bet_e_a_carta_do_ABRIDOR_contra_quem_deu_3bet():
    b = _stack_bucket(40)
    v = fold3bet_pct_do_chart('CO', 'BTN', b)
    assert v is not None
    ref = referencia_fold3bet_por_assento('CO', [('BTN', 40)] * 6)
    assert (ref['lo'], ref['hi']) == (round(v - FOLGA_DA_REFERENCIA_PP, 1), round(min(100.0, v + FOLGA_DA_REFERENCIA_PP), 1)), ref
    assert referencia_fold3bet_por_assento('BB', [('SB', 40)] * 3) is None     # BB nao abre: sem carta


def test_a_grade_tem_as_3_colunas_com_ref_e_VPIP_PFR_como_contexto():
    """As 3 colunas com chart trazem `ref`; VPIP e PFR entram como contexto, sem `ref`."""
    maos = []
    for i in range(120):
        maos.append(_m('BTN', 'raise' if i % 2 else 'fold', effective_stack_bb=100 if i < 60 else 30))
    for i in range(800):   # 3-bet e fold 3-bet pedem 750 maos no assento
        maos.append(_m('BTN', 'raise' if i % 7 == 0 else 'fold', facing_bet=2.5, preflop_raises_faced=1,
                       vs_position='UTG' if i % 2 else 'CO', is_3bet=1 if i % 7 == 0 else 0))
        maos.append(_m('BTN', 'fold' if i % 2 else 'call', facing_bet=8, preflop_raises_faced=1,
                       hero_was_aggressor=1, vs_position='SB'))
    uid = _semeia(maos)
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    assert grade['sempre'] + grade['com_volume'] == ['vpip', 'pfr', 'rfi', 'three_bet', 'fold_to_3bet_open'], grade['sempre']
    btn = next(l for l in grade['positions'] if l['position'] == 'BTN')['stats']
    for k in ('rfi', 'three_bet', 'fold_to_3bet_open'):
        assert k in btn and btn[k]['band'] == 'ok' and 'ref' in btn[k], (k, btn.get(k))
    for k in ('vpip', 'pfr'):          # contexto: numero sem regua
        assert k in btn and 'ref' not in btn[k], (k, btn.get(k))
    assert set(btn['rfi']['ref']['pesos']) == {balde_rfi(100), balde_rfi(30)}
    assert grade['stack_band'] is None and grade['faixas'] == list(FAIXAS_DE_STACK)
    # na faixa 40+, so as maos de 100bb do RFI: a referencia estreita para o chart de 100bb
    grade = get_player_stats_by_position(uid, days=3650, last_n=0, stack_band='40+')
    btn = next(l for l in grade['positions'] if l['position'] == 'BTN')
    assert set(btn['stats']['rfi']['ref']['pesos']) == {balde_rfi(100)}, btn['stats']['rfi']
    assert grade['stack_band'] == '40+'


def test_o_endpoint_aceita_faixa_conhecida_e_rejeita_desconhecida():
    uid = _semeia([_m('BTN', 'raise', effective_stack_bb=30)])
    from api.app import app
    from database.auth import generate_token
    h = {'Authorization': 'Bearer %s' % generate_token(uid, 'player')}
    c = app.test_client()
    r = c.get('/metrics/player-stats?stack=20-40', headers=h)
    assert r.status_code == 200 and r.get_json()['rfi'] == 100.0, r.get_data(as_text=True)[:200]
    r = c.get('/metrics/player-stats?stack=30-50', headers=h)
    assert r.status_code == 400, r.status_code
    r = c.get('/metrics/player-stats?stack=<20', headers=h)
    assert r.status_code == 200 and r.get_json()['rfi'] is None



# ── Fase 3: VPIP e PFR = a media do solver nas maos do jogador ─────────────────────────

def test_o_solver_na_primeira_decisao_le_a_carta_certa_ou_se_cala():
    """Pote intacto -> chart de abertura (no SB o limp conta como VPIP); enfrentando um open
    -> vs_RFI do abridor; limp na frente, 3-bet a frio e BB com pote intacto -> None."""
    intacto = {'facing_bet': 0, 'facing_limp': 0, 'preflop_raises_faced': 0, 'hero_was_aggressor': 0, 'effective_stack_bb': 40}
    r = solver_na_primeira_decisao('BTN', intacto)
    assert r and r['chave'] == balde_rfi(40) and abs(r['p_pfr'] * 100 - rfi_pct_do_chart('BTN', balde_rfi(40))) < 0.11, r
    assert r['p_vpip'] >= r['p_pfr']
    sb = solver_na_primeira_decisao('SB', intacto)
    assert sb and sb['p_vpip'] > sb['p_pfr'] + 0.2, sb          # o limp do SB e VPIP, nao PFR
    assert solver_na_primeira_decisao('BB', intacto) is None      # a BB nao tem pote intacto
    vs_open = {'facing_bet': 2.5, 'facing_limp': 0, 'preflop_raises_faced': 1, 'hero_was_aggressor': 0, 'vs_position': 'UTG', 'effective_stack_bb': 40}
    r = solver_na_primeira_decisao('BB', vs_open)
    assert r and r['chave'] == '%s vs UTG' % _stack_bucket(40) and abs(r['p_pfr'] * 100 - tresbet_pct_do_chart('BB', 'UTG', _stack_bucket(40))) < 0.11, r
    vs_btn = solver_na_primeira_decisao('BB', dict(vs_open, vs_position='BTN'))
    assert vs_btn['chave'].endswith('vs BTN') and vs_btn['p_vpip'] != r['p_vpip'], (vs_btn, r)   # quem abriu importa
    assert solver_na_primeira_decisao('BTN', dict(intacto, facing_limp=1)) is None           # limp na frente
    assert solver_na_primeira_decisao('BB', dict(vs_open, preflop_raises_faced=2)) is None    # 3-bet a frio
    assert solver_na_primeira_decisao('BTN', dict(intacto, effective_stack_bb=None)) is None


def test_a_referencia_de_vpip_pfr_e_a_media_com_folga_estatistica_e_cala_sem_cobertura():
    intacto = {'facing_bet': 0, 'facing_limp': 0, 'preflop_raises_faced': 0, 'hero_was_aggressor': 0, 'effective_stack_bb': 100}
    p = solver_na_primeira_decisao('BTN', intacto)
    import math
    ref = referencia_vpip_pfr_por_assento('BTN', [(intacto, i % 2 == 0, i % 4 == 0) for i in range(400)])
    folga = max(FOLGA_MINIMA_PP, 2 * math.sqrt(p['p_pfr'] * (1 - p['p_pfr']) / 400) * 100)
    assert ref['cobertura'] == 100 and ref['pfr']['tipo'] == 'media'
    assert abs(ref['pfr']['lo'] - (p['p_pfr'] * 100 - folga)) < 0.11 and abs(ref['pfr']['hi'] - (p['p_pfr'] * 100 + folga)) < 0.11, ref['pfr']
    assert ref['pfr']['valor_coberto'] == 25.0 and ref['vpip']['valor_coberto'] == 50.0
    ref40 = referencia_vpip_pfr_por_assento('BTN', [(intacto, True, True)] * 40)
    assert ref40['pfr']['folga'] > ref['pfr']['folga']                # amostra menor, folga maior
    limp = dict(intacto, facing_limp=1)
    ref = referencia_vpip_pfr_por_assento('BTN', [(intacto, True, True)] * 60 + [(limp, True, False)] * 40)
    assert ref['vpip'] is None and ref['pfr'] is None and ref['cobertura'] == 60, ref
    ref = referencia_vpip_pfr_por_assento('BTN', [(intacto, True, True)] * 75 + [(limp, True, False)] * 25)
    assert ref['vpip'] and ref['cobertura'] == 75


def test_a_grade_emite_ref_de_vpip_e_pfr_so_com_cobertura():
    uid = _semeia([_m('BTN', 'raise' if i % 2 else 'fold', effective_stack_bb=50) for i in range(120)])
    btn = next(l for l in get_player_stats_by_position(uid, days=3650, last_n=0)['positions'] if l['position'] == 'BTN')['stats']
    assert btn['vpip'].get('ref', {}).get('tipo') == 'media' and btn['pfr'].get('ref', {}).get('tipo') == 'media', btn
    assert btn['vpip']['ref']['cobertura'] == 100
    uid = _semeia([_m('BTN', 'raise' if i % 2 else 'fold', effective_stack_bb=50, facing_limp=1 if i % 5 < 2 else 0) for i in range(120)])
    btn = next(l for l in get_player_stats_by_position(uid, days=3650, last_n=0)['positions'] if l['position'] == 'BTN')['stats']
    assert 'ref' not in btn['vpip'] and 'ref' not in btn['pfr'], btn
    assert COBERTURA_MINIMA_VPIP_PFR == 0.70


def test_so_a_primeira_decisao_da_mao_alimenta_a_referencia():
    """120 maos no BTN: em 60 o heroi abre e leva 3-bet (2a decisao: fold, enfrentando 2
    raises, SEM carta). Se a 2a decisao entrasse, a cobertura cairia para 67% e a referencia
    se calaria; contando so a primeira, cobertura 100% e `n` = 120 maos."""
    maos = []
    for i in range(120):
        maos.append(_m('BTN', 'raise' if i % 2 else 'fold', effective_stack_bb=50, hand_id='H%d' % i))
        if i % 2:
            maos.append(_m('BTN', 'fold', effective_stack_bb=50, hand_id='H%d' % i, facing_bet=8,
                           preflop_raises_faced=1, hero_was_aggressor=1, vs_position='BB'))
    uid = _semeia(maos)
    btn = next(l for l in get_player_stats_by_position(uid, days=3650, last_n=0)['positions'] if l['position'] == 'BTN')['stats']
    assert btn['vpip'].get('ref', {}).get('cobertura') == 100, btn['vpip']
    assert btn['vpip']['ref']['valor_coberto'] == 50.0, btn['vpip']['ref']


def test_a_faixa_de_stack_e_da_MAO_pela_primeira_decisao():
    """Mao aberta a 41bb que leva 3-bet e e decidida a 39bb (outro vilao): e UMA mao, na
    faixa 40+. Filtrar por decisao punha a mesma mao em duas faixas (84 de 6.029 em dev) e as
    faixas somavam mais que "todos"."""
    uid = _semeia([
        _m('CO', 'raise', effective_stack_bb=41, hand_id='H1'),
        _m('CO', 'fold', effective_stack_bb=39, hand_id='H1', facing_bet=8, preflop_raises_faced=1, hero_was_aggressor=1, vs_position='BTN'),
        _m('CO', 'fold', effective_stack_bb=30, hand_id='H2'),
    ])
    todos = get_player_stats(uid, days=3650, last_n=0, position='CO')['total_hands']
    por_faixa = {b: get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band=b)['total_hands'] for b in FAIXAS_DE_STACK}
    assert todos == 2 and por_faixa == {'40+': 1, '20-40': 1, '<20': 0}, (todos, por_faixa)
    # e o fold ao 3-bet da mao H1 fica na faixa da MAO (40+), nao na da decisao (20-40)
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='40+')['fold_to_3bet_open'] == 100.0
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='20-40')['fold_to_3bet_open'] is None


def test_os_pesos_do_tooltip_somam_100():
    from leaklab.preflop_gto_ranges import _pesos_que_somam_100
    p = _pesos_que_somam_100({'a': 1, 'b': 1, 'c': 1, 'd': 1, 'e': 1, 'f': 1, 'g': 1})
    assert sum(p.values()) == 100 and len(p) == 7, p
    p = _pesos_que_somam_100({'a': 997, 'b': 1, 'c': 1, 'd': 1})
    assert sum(p.values()) == 100 and p['a'] >= 97, p


# ── Item 1: "contra quem" ───────────────────────────────────────────────────────────────

def test_o_detalhe_abre_o_3bet_por_quem_abriu_com_a_mesma_definicao_do_stat():
    """BB enfrenta 40 opens de UTG (da 3-bet em 4) e 40 de BTN (em 12): 10% e 30%, na ordem
    da mesa, cada um com a propria faixa do chart. Um open de MP1 e o mesmo assento que LJ."""
    maos = []
    for i in range(40):
        maos.append(_m('BB', 'raise' if i < 4 else 'call', facing_bet=2.5, preflop_raises_faced=1, vs_position='UTG', is_3bet=1 if i < 4 else 0, effective_stack_bb=40))
        maos.append(_m('BB', 'raise' if i < 12 else 'call', facing_bet=2.5, preflop_raises_faced=1, vs_position='BTN', is_3bet=1 if i < 12 else 0, effective_stack_bb=40))
    maos.append(_m('BB', 'call', facing_bet=2.5, preflop_raises_faced=1, vs_position='MP1', effective_stack_bb=40))
    maos.append(_m('BB', 'fold', facing_bet=7, preflop_raises_faced=2, vs_position='BTN', effective_stack_bb=40))   # 3-bet a frio: nao e oportunidade
    uid = _semeia(maos)
    d = get_position_stat_detail(uid, 'BB', 'three_bet', days=3650, last_n=0)
    assert [r['vs'] for r in d['rows']] == ['UTG', 'LJ', 'BTN'], d['rows']
    utg, lj, btn = d['rows']
    assert (utg['n'], utg['value'], utg['band']) == (40, 10.0, 'ok'), utg
    assert (btn['n'], btn['value']) == (40, 30.0) and lj['band'] == 'low_sample', (btn, lj)
    assert utg['ref'] and btn['ref'] and utg['ref']['hi'] < btn['ref']['lo'], (utg['ref'], btn['ref'])   # o solver 3-beta mais contra BTN
    assert d['minimo'] == MINIMO_DO_DETALHE == 30
    # o total do detalhe fecha com o stat do assento (mesma definicao de oportunidade)
    hud = get_player_stats(uid, days=3650, last_n=0, position='BB')
    assert round(sum(r['n'] * r['value'] for r in d['rows']) / sum(r['n'] for r in d['rows']), 1) == hud['three_bet'] or hud['three_bet'] is None


def test_o_detalhe_do_fold_3bet_e_por_quem_deu_o_3bet_e_respeita_a_faixa_de_stack():
    maos = []
    for i in range(30):
        maos.append(_m('CO', 'fold' if i < 20 else 'call', facing_bet=8, preflop_raises_faced=1, hero_was_aggressor=1, vs_position='BTN', effective_stack_bb=60, hand_id='A%d' % i))
        maos.append(_m('CO', 'fold' if i < 10 else 'call', facing_bet=8, preflop_raises_faced=1, hero_was_aggressor=1, vs_position='BB', effective_stack_bb=25, hand_id='B%d' % i))
    uid = _semeia(maos)
    d = get_position_stat_detail(uid, 'CO', 'fold_to_3bet_open', days=3650, last_n=0)
    assert {r['vs']: r['value'] for r in d['rows']} == {'BTN': round(20 / 30 * 100, 1), 'BB': round(10 / 30 * 100, 1)}, d['rows']
    d = get_position_stat_detail(uid, 'CO', 'fold_to_3bet_open', days=3650, last_n=0, stack_band='40+')
    assert [r['vs'] for r in d['rows']] == ['BTN'] and d['stack_band'] == '40+', d


def test_o_endpoint_do_detalhe_valida_assento_e_stat():
    uid = _semeia([_m('BB', 'call', facing_bet=2.5, preflop_raises_faced=1, vs_position='UTG', effective_stack_bb=40)])
    conn = get_conn(); conn.execute(_adapt("UPDATE users SET plan='pro' WHERE id=?"), (uid,)); conn.commit(); conn.close()   # mesmo gate da grade
    from api.app import app
    from database.auth import generate_token
    h = {'Authorization': 'Bearer %s' % generate_token(uid, 'player')}
    c = app.test_client()
    r = c.get('/metrics/player-stats/by-position/detail?position=BB&stat=three_bet', headers=h)
    assert r.status_code == 200 and r.get_json()['rows'][0]['vs'] == 'UTG', r.get_data(as_text=True)[:200]
    assert c.get('/metrics/player-stats/by-position/detail?position=BB&stat=vpip', headers=h).status_code == 400
    assert c.get('/metrics/player-stats/by-position/detail?position=XX&stat=three_bet', headers=h).status_code == 400

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
