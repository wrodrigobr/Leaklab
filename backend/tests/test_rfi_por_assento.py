# -*- coding: utf-8 -*-
"""RFI por assento com referencia do CHART, e o filtro de stack do perfil por posicao (AY-15).

── O que originou (06/09) ─────────────────────────────────────────────────────────────────

O dono queria a regua de volta na grade por posicao e trouxe uma tabela de VPIP por assento.
Medida contra os nossos charts, a tabela era mais tight que o solver em todo assento (BTN
38-48 contra 51-55): folclore. A referencia que da para defender e o proprio chart de
abertura, e a metrica que o Rullian usa nos estudos e RFI, nao PFR (PFR inclui 3-bet).

── O que este arquivo defende ─────────────────────────────────────────────────────────────

1. RFI conta SO com o pote intacto: raise em cima de limp nao e RFI, enfrentar raise nao e
   oportunidade, e a BB nunca tem (se todos foldam, a mao acaba).
2. A faixa de stack recorta pela `effective_stack_bb` da decisao; NULL so entra em "todos".
3. A referencia vem do chart nas profundidades das MAOS do jogador, com folga declarada, e
   os baldes que pesam menos de 10% nao alargam a faixa.
4. A grade emite `ref` so no RFI (nao em VPIP/PFR: nao ha regua por assento defensavel), e o
   endpoint rejeita faixa desconhecida em vez de devolver "todos" sob o rotulo errado.
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
from database.repositories import (FAIXAS_DE_STACK, _adapt, get_player_stats,  # noqa: E402
                                   get_player_stats_by_position)
from leaklab.preflop_gto_ranges import (FOLGA_DA_REFERENCIA_PP, balde_rfi,     # noqa: E402
                                        referencia_rfi_por_assento, rfi_pct_do_chart)


def _semeia(maos):
    """`maos`: lista de (position, action_taken, facing_bet, facing_limp, effective_stack_bb)."""
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('rfi', 'rfi@t.local', 'senha12345', 'player')
    conn = get_conn()
    conn.execute(_adapt("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,played_at,imported_at) "
                        "VALUES (1,?,'T1','pokerstars','Hero','2026-09-01','2026-09-01')"), (uid,))
    for i, (pos, acao, fb, fl, stack) in enumerate(maos):
        conn.execute(_adapt("INSERT INTO decisions (tournament_id,hand_id,street,position,action_taken,"
                            "best_action,score,label,facing_bet,facing_limp,effective_stack_bb) "
                            "VALUES (1,?,'preflop',?,?,'raise',0.1,'standard',?,?,?)"),
                     ('H%d' % i, pos, acao, fb, fl, stack))
    conn.commit(); conn.close()
    return uid


def test_rfi_conta_so_com_o_pote_intacto():
    """4 oportunidades no BTN (2 raise, 1 fold, 1 call): RFI 50. O raise em cima de limp e o
    raise enfrentando open NAO entram nem no numerador nem no denominador."""
    uid = _semeia([
        ('BTN', 'raise', 0, 0, 30), ('BTN', 'raise', 0, 0, 30), ('BTN', 'fold', 0, 0, 30), ('BTN', 'call', 0, 0, 30),
        ('BTN', 'raise', 0, 1, 30),      # iso-raise em cima de limp: pote ja aberto
        ('BTN', 'raise', 2.5, 0, 30),    # 3-bet: enfrenta open
    ])
    s = get_player_stats(uid, days=3650, last_n=0, position='BTN')
    assert s['rfi'] == 50.0, s['rfi']
    # e o PFR, que e a conta antiga, ve 4 raises em 6 maos: por isso PFR nao serve
    assert s['pfr'] == round(4 / 6 * 100, 1), s['pfr']


def test_a_BB_nao_tem_RFI_e_o_SB_tem():
    uid = _semeia([('BB', 'raise', 0, 0, 30), ('BB', 'call', 0, 0, 30),
                   ('SB', 'raise', 0, 0, 30), ('SB', 'call', 0, 0, 30)])
    assert get_player_stats(uid, days=3650, last_n=0, position='BB')['rfi'] is None
    assert get_player_stats(uid, days=3650, last_n=0, position='SB')['rfi'] == 50.0
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    por = {l['position']: l['stats'] for l in grade['positions']}
    assert 'rfi' not in por['BB'], por['BB']


def test_a_faixa_de_stack_recorta_pela_effective_stack_bb():
    """60bb raise, 30bb fold, 12bb raise, NULL fold. Cada faixa ve so as suas; "todos" ve as 4."""
    uid = _semeia([('CO', 'raise', 0, 0, 60), ('CO', 'fold', 0, 0, 30),
                   ('CO', 'raise', 0, 0, 12), ('CO', 'fold', 0, 0, None)])
    todos = get_player_stats(uid, days=3650, last_n=0, position='CO')
    assert todos['total_hands'] == 4 and todos['rfi'] == 50.0, todos
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='40+')['rfi'] == 100.0
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='20-40')['rfi'] == 0.0
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='<20')['rfi'] == 100.0
    # a fronteira e [lo, hi): 40 cai em 40+, nao em 20-40
    uid = _semeia([('CO', 'raise', 0, 0, 40.0), ('CO', 'fold', 0, 0, 39.9)])
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='40+')['total_hands'] == 1
    assert get_player_stats(uid, days=3650, last_n=0, position='CO', stack_band='20-40')['total_hands'] == 1


def test_a_referencia_vem_do_chart_nas_profundidades_das_maos_com_folga():
    """BTN com stacks so de ~100bb: faixa = chart de 100bb +- folga. Mistura 100bb e 30bb:
    faixa do menor ao maior chart, com a folga. Balde com < 10% das maos nao alarga."""
    c100 = rfi_pct_do_chart('BTN', balde_rfi(100))
    c30 = rfi_pct_do_chart('BTN', balde_rfi(30))
    assert c100 and c30 and c100 != c30, (c100, c30)
    ref = referencia_rfi_por_assento('BTN', [100] * 10)
    assert (ref['lo'], ref['hi']) == (round(c100 - FOLGA_DA_REFERENCIA_PP, 1), round(c100 + FOLGA_DA_REFERENCIA_PP, 1)), ref
    ref = referencia_rfi_por_assento('BTN', [100] * 5 + [30] * 5)
    assert ref['lo'] == round(min(c100, c30) - FOLGA_DA_REFERENCIA_PP, 1), ref
    assert ref['hi'] == round(max(c100, c30) + FOLGA_DA_REFERENCIA_PP, 1), ref
    assert set(ref['pesos']) == {balde_rfi(100), balde_rfi(30)} and sum(ref['pesos'].values()) == 100, ref
    # 30bb com 5% das maos: nao alarga a faixa, mas aparece nos pesos
    ref = referencia_rfi_por_assento('BTN', [100] * 19 + [30])
    assert ref['lo'] == round(c100 - FOLGA_DA_REFERENCIA_PP, 1) and ref['hi'] == round(c100 + FOLGA_DA_REFERENCIA_PP, 1), ref
    assert balde_rfi(30) in ref['pesos']
    assert referencia_rfi_por_assento('BB', [30] * 10) is None       # a BB nao tem chart de abertura
    assert referencia_rfi_por_assento('BTN', []) is None


def test_a_grade_emite_ref_so_no_RFI_e_na_faixa_escolhida():
    uid = _semeia([('BTN', 'raise' if i % 2 else 'fold', 0, 0, 100 if i < 60 else 30) for i in range(120)])
    grade = get_player_stats_by_position(uid, days=3650, last_n=0)
    btn = next(l for l in grade['positions'] if l['position'] == 'BTN')['stats']
    assert 'ref' in btn['rfi'] and 'ref' not in btn['vpip'] and 'ref' not in btn['pfr'], btn
    assert set(btn['rfi']['ref']['pesos']) == {balde_rfi(100), balde_rfi(30)}
    assert grade['stack_band'] is None and grade['faixas'] == list(FAIXAS_DE_STACK)
    # na faixa 40+, so as maos de 100bb: a referencia estreita para o chart de 100bb
    grade = get_player_stats_by_position(uid, days=3650, last_n=0, stack_band='40+')
    btn = next(l for l in grade['positions'] if l['position'] == 'BTN')
    assert btn['hands'] == 60 and set(btn['stats']['rfi']['ref']['pesos']) == {balde_rfi(100)}, btn
    assert grade['stack_band'] == '40+'


def test_o_endpoint_aceita_faixa_conhecida_e_rejeita_desconhecida():
    uid = _semeia([('BTN', 'raise', 0, 0, 30)])
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
