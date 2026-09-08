# -*- coding: utf-8 -*-
"""Card do admin "Aproveitamento do solver" (AY-28, 08/09).

O que este arquivo defende, com dados forjados: reaproveitada = no criado ANTES do import;
resolvida depois = no criado depois; sem no = sem no; semana = a do import; enviados = linhas
de gto_tournament_queue do torneio; semelhanca = decisao sem no cuja assinatura de board tem
arvore resolvida; espera = solved_at - requested_at dos 'done'. E o endpoint exige admin.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
_TMPDB = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_TMPDB.close()
os.environ['LEAKLAB_DB'] = _TMPDB.name
os.environ.pop('DATABASE_URL', None)

from datetime import datetime, timedelta                                           # noqa: E402
from database.schema import get_conn, init_db                                      # noqa: E402
import database.repositories as repo                                               # noqa: E402
from database.repositories import _adapt, get_aproveitamento_do_solver             # noqa: E402


def _ts(dias_atras, hora='12:00:00'):
    return (datetime.utcnow() - timedelta(days=dias_atras)).strftime('%Y-%m-%d ') + hora


def _semeia():
    init_db()
    conn = get_conn()
    for t in ('decisions', 'tournaments', 'users', 'gto_nodes', 'gto_tree_strategies', 'gto_tournament_queue', 'gto_solver_queue'):
        conn.execute('DELETE FROM %s' % t)
    conn.commit(); conn.close()
    uid = repo.create_user('adm', 'adm@t.local', 'senha12345', 'admin')
    conn = get_conn()
    conn.execute(_adapt("UPDATE users SET role='admin' WHERE id=?"), (uid,))
    imp = _ts(3)
    conn.execute(_adapt("INSERT INTO tournaments (id,user_id,tournament_id,site,hero,played_at,imported_at) VALUES (1,?,'T1','pokerstars','Hero',?,?)"), (uid, imp, imp))
    def dec(i, spot, board, pos='CO', stack=30, facing=0):
        conn.execute(_adapt("INSERT INTO decisions (id,tournament_id,hand_id,street,position,action_taken,best_action,score,label,"
                            "spot_hash,board,hero_cards,stack_bb,facing_bet) VALUES (?,1,?,'flop',?,'bet','bet',0.1,'standard',?,?,'AhKh',?,?)"),
                     (i, 'H%d' % i, pos, spot, board, stack, facing))
    dec(1, 'antigo', '["Ah","7h","2c"]')            # no criado ANTES do import: reaproveitada
    dec(2, 'novo', '["Ks","8s","3d"]')              # no criado DEPOIS: resolvida depois
    dec(3, 'nada', '["Qs","9s","4d"]')              # sem no; mas ha arvore de board com a MESMA assinatura (spot 'antigo': A-seco-2tone? nao: Q alto)
    dec(4, 'nada2', '["Ad","8d","3c"]')             # sem no; assinatura igual a do 'antigo' (A-seco-2tone-desconectado, CO, 20-35bb, no_bet) -> vizinho
    conn.execute(_adapt("INSERT INTO gto_nodes (spot_hash,street,position,board,hero_hand,stack_bucket,gto_action,gto_freq,tree_hash,created_at) VALUES ('antigo','flop','CO','Ah7h2c','AhKh','20-35bb','bet',0.7,'arv1',?)"), (_ts(10),))
    conn.execute(_adapt("INSERT INTO gto_nodes (spot_hash,street,position,board,hero_hand,stack_bucket,gto_action,gto_freq,tree_hash,created_at) VALUES ('novo','flop','CO','Ks8s3d','AhKh','20-35bb','bet',0.7,'arv2',?)"), (_ts(1),))
    conn.execute(_adapt("INSERT INTO gto_tree_strategies (tree_hash,board,actions,hand_table) VALUES ('arv1','[\"Ah\",\"7h\",\"2c\"]','[\"check\",\"bet\"]','[]')"))
    conn.execute(_adapt("INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (1,'novo')"))
    conn.execute(_adapt("INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (1,'nada')"))
    conn.execute(_adapt("INSERT INTO gto_solver_queue (spot_hash,spot_json,status,priority,requested_at,solved_at) VALUES ('novo','{}','done',0,?,?)"), (_ts(2, '10:00:00'), _ts(2, '13:00:00')))
    conn.execute(_adapt("INSERT INTO gto_solver_queue (spot_hash,spot_json,status,priority,requested_at) VALUES ('nada','{}','pending',0,?)"), (_ts(2),))
    conn.commit(); conn.close()
    return uid


def test_semana_reaproveitada_resolvida_depois_sem_no_enviados_espera_e_semelhanca():
    _semeia()
    r = get_aproveitamento_do_solver(dias=56)
    assert r['acervo'] == {'nos': 2, 'arvores': 1}, r['acervo']
    assert r['fila'] == {'done': 1, 'pending': 1}, r['fila']
    assert r['espera'] == {'n': 1, 'media_h': 3.0, 'mediana_h': 3.0}, r['espera']
    assert len(r['semanas']) == 1, r['semanas']
    s = r['semanas'][0]
    assert (s['decisoes'], s['spots'], s['reaproveitadas'], s['resolvidas_depois'], s['sem_no'], s['enviados'], s['pct_reaproveitado']) == (4, 4, 1, 1, 2, 2, 25), s
    # semelhanca: das 2 sem no, a 'nada2' (A-seco-2tone, CO, 20-35bb, sem aposta) tem arvore de board igual (a do 'antigo'); a 'nada' (Q alto) nao
    assert r['semelhanca'] == {'sem_no': 2, 'com_vizinho': 1, 'pct': 50, 'assinaturas_conhecidas': 1}, r['semelhanca']


def test_o_endpoint_e_so_do_admin():
    uid = _semeia()
    from api.app import app
    from database.auth import generate_token
    c = app.test_client()
    r = c.get('/admin/solver/aproveitamento', headers={'Authorization': 'Bearer %s' % generate_token(uid, 'admin')})
    assert r.status_code == 200 and r.get_json()['semelhanca']['pct'] == 50, r.get_data(as_text=True)[:200]
    jogador = repo.create_user('jog', 'jog@t.local', 'senha12345', 'player')
    assert c.get('/admin/solver/aproveitamento', headers={'Authorization': 'Bearer %s' % generate_token(jogador, 'player')}).status_code in (401, 403)


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
