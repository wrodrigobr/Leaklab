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
            + [_m('UTG', 'Ts9s', 'raise' if i < 3 else 'fold') for i in range(10)]
            + [_m('UTG', '??', 'fold') for _ in range(4)])
    uid = _semeia(maos)
    m = get_position_open_matrix(uid, 'UTG', days=3650, last_n=0)
    # as 4 maos ilegiveis entram no total (e o denominador do RFI da grade), nao nas celulas
    assert m['n'] == 34 and m['cobertura'] == round(30 * 100 / 34), (m['n'], m['cobertura'])
    assert m['cells']['AKs'] == {'n': 10, 'voce': 1.0, 'solver': round(float(villain_open_range('UTG', 40).get('AKs', 0.0)), 3)}
    assert m['cells']['72o']['voce'] == 0.0 and m['cells']['72o']['solver'] == 0.0
    assert m['cells']['T9s']['voce'] == 0.3
    # as 169 maos existem; as nunca recebidas vem com n=0, sem `voce`, e com a carta do solver
    assert len(m['cells']) == 169 and {h for h, c in m['cells'].items() if c['n'] > 0} == {'AKs', '72o', 'T9s'}
    assert m['cells']['AQs'] == {'n': 0, 'voce': None, 'solver': round(float(villain_open_range('UTG', 40).get('AQs', 0.0)), 3)}
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
