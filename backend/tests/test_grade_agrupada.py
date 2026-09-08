# -*- coding: utf-8 -*-
"""Grade por posicao AGRUPADA: EP / MP / CO / BTN / SB / BB (AY-21, 07/09).

O Rullian: o PokerTracker junta tudo antes do CO em EP e MP; "simplifica, mas fica ruim de
estudar". Entao a grade ganha a opcao, sem perder a detalhada.

O que este arquivo defende:
1. Um grupo e a UNIAO das linhas dos assentos: maos do EP = soma das maos de UTG, UTG+1 e
   UTG+2; o RFI do EP e o RFI sobre TODAS as oportunidades desses assentos (nao a media das
   tres medias); `members` diz quais assentos o jogador ocupou.
2. Os grupos derivam de `grupo_posicional`: um assento em dois grupos, ou fora de todos, acusa.
3. O modal "contra quem" do grupo le as mesmas maos: `rotulos_do_assento('EP')` e a uniao.
4. O endpoint aceita `?group=1` e o detalhe aceita `position=EP`.
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
import database.repositories as repo                                            # noqa: E402
from database.repositories import (GRUPOS_DA_GRADE, POSICOES_NA_ORDEM, _adapt,  # noqa: E402
                                   get_player_stats_by_position, get_position_stat_detail,
                                   grupo_posicional, rotulos_do_assento)


def _semeia(maos):
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('grupo', 'grupo@t.local', 'senha12345', 'player')
    conn = get_conn()
    conn.execute(_adapt("UPDATE users SET plan='pro' WHERE id=?"), (uid,))
    conn.execute(_adapt("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,played_at,imported_at) "
                        "VALUES (1,?,'T1','pokerstars','Hero','2026-09-01','2026-09-01')"), (uid,))
    for i, m in enumerate(maos):
        conn.execute(_adapt("INSERT INTO decisions (tournament_id,hand_id,street,position,num_players,action_taken,"
                            "best_action,score,label,facing_bet,facing_limp,effective_stack_bb,"
                            "preflop_raises_faced,hero_was_aggressor,vs_position,is_3bet,gto_label) "
                            "VALUES (1,?,'preflop',?,9,?,'raise',0.1,'standard',?,0,?,?,?,?,0,'gto_correct')"),
                     ('H%d' % i, m['position'], m['action_taken'], m.get('facing_bet', 0), m.get('effective_stack_bb', 30),
                      m.get('preflop_raises_faced', 0), m.get('hero_was_aggressor', 0), m.get('vs_position')))
    conn.commit(); conn.close()
    return uid


def _m(pos, acao, **kw):
    d = {'position': pos, 'action_taken': acao}; d.update(kw); return d


def test_os_grupos_derivam_de_grupo_posicional_e_cobrem_todos_os_assentos():
    vistos = [p for g in GRUPOS_DA_GRADE.values() for p in g]
    assert sorted(vistos) == sorted(POSICOES_NA_ORDEM) and len(vistos) == len(set(vistos)), vistos
    assert GRUPOS_DA_GRADE['EP'] == ('UTG', 'UTG+1', 'UTG+2') and GRUPOS_DA_GRADE['MP'] == ('LJ', 'HJ')
    for g, assentos in GRUPOS_DA_GRADE.items():
        assert all(grupo_posicional(p) == g for p in assentos), (g, assentos)
    assert list(GRUPOS_DA_GRADE) == ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB']


def test_o_grupo_e_a_uniao_das_linhas_nao_a_media_das_medias():
    """UTG: 100 maos, abre 10 (10%); UTG+2: 20 maos, abre 10 (50%). EP = 20 em 120 = 16,7%,
    nao (10+50)/2 = 30. LJ e HJ formam MP; CO sozinho; BB sem RFI."""
    maos = ([_m('UTG', 'raise' if i < 10 else 'fold', effective_stack_bb=40) for i in range(100)]
            + [_m('UTG+2', 'raise' if i < 10 else 'fold', effective_stack_bb=40) for i in range(20)]
            + [_m('LJ', 'raise', effective_stack_bb=40) for _ in range(30)]
            + [_m('HJ', 'fold', effective_stack_bb=40) for _ in range(30)]
            + [_m('CO', 'raise', effective_stack_bb=40) for _ in range(40)]
            + [_m('BB', 'call', facing_bet=2.5, preflop_raises_faced=1, vs_position='BTN', effective_stack_bb=40) for _ in range(40)])
    uid = _semeia(maos)
    g = get_player_stats_by_position(uid, days=3650, last_n=0, agrupado=True)
    assert g['agrupado'] is True and g['grupos']['EP'] == ['UTG', 'UTG+1', 'UTG+2']
    por = {l['position']: l for l in g['positions']}
    assert list(por) == ['EP', 'MP', 'CO', 'BB'], list(por)
    assert por['EP']['hands'] == 120 and por['EP']['members'] == ['UTG', 'UTG+2'], por['EP']
    assert por['EP']['stats']['rfi']['value'] == round(20 / 120 * 100, 1), por['EP']['stats']['rfi']
    assert por['EP']['stats']['rfi']['ref'] is not None
    assert por['MP']['hands'] == 60 and por['MP']['stats']['rfi']['value'] == 50.0
    assert por['CO']['members'] == ['CO']
    assert 'rfi' not in por['BB']['stats']
    # a detalhada continua igual, e o total nao muda com a visao
    d = get_player_stats_by_position(uid, days=3650, last_n=0)
    assert d['agrupado'] is False and [l['position'] for l in d['positions']] == ['UTG', 'UTG+2', 'LJ', 'HJ', 'CO', 'BB']
    assert d['total'] == g['total'] and d['total_hands'] == g['total_hands'] == 260


def test_o_detalhe_do_grupo_le_as_mesmas_maos():
    assert set(rotulos_do_assento('EP')) >= {'UTG', 'UTG+1', 'UTG+2'}
    assert set(rotulos_do_assento('MP')) >= {'LJ', 'HJ', 'MP1', 'MP2'}
    assert rotulos_do_assento('CO')[0] == 'CO'
    maos = ([_m('UTG', 'fold' if i < 6 else 'call', facing_bet=8, preflop_raises_faced=1, hero_was_aggressor=1, vs_position='BTN', effective_stack_bb=30) for i in range(10)]
            + [_m('UTG+1', 'fold' if i < 8 else 'call', facing_bet=8, preflop_raises_faced=1, hero_was_aggressor=1, vs_position='BTN', effective_stack_bb=30) for i in range(10)])
    uid = _semeia(maos)
    d = get_position_stat_detail(uid, 'EP', 'fold_to_3bet', days=3650, last_n=0)
    assert d['total']['n'] == 20 and d['total']['value'] == 70.0, d['total']
    assert [r['vs'] for r in d['rows']] == ['BTN'] and d['rows'][0]['n'] == 20
    g = get_player_stats_by_position(uid, days=3650, last_n=0, agrupado=True)
    ep = next(l for l in g['positions'] if l['position'] == 'EP')
    assert ep['stats']['fold_to_3bet']['value'] == d['total']['value']


def test_o_endpoint_aceita_group_e_o_detalhe_aceita_o_grupo():
    uid = _semeia([_m('UTG', 'raise', effective_stack_bb=40) for _ in range(20)] + [_m('HJ', 'raise', effective_stack_bb=40) for _ in range(20)])
    from api.app import app
    from database.auth import generate_token
    h = {'Authorization': 'Bearer %s' % generate_token(uid, 'player')}
    c = app.test_client()
    r = c.get('/metrics/player-stats/by-position?group=1', headers=h)
    assert r.status_code == 200 and [l['position'] for l in r.get_json()['positions']] == ['EP', 'MP'], r.get_data(as_text=True)[:200]
    r = c.get('/metrics/player-stats/by-position', headers=h)
    assert [l['position'] for l in r.get_json()['positions']] == ['UTG', 'HJ']
    assert c.get('/metrics/player-stats/by-position/detail?position=EP&stat=three_bet', headers=h).status_code == 200
    assert c.get('/metrics/player-stats/by-position/detail?position=OTHER&stat=three_bet', headers=h).status_code == 400


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
