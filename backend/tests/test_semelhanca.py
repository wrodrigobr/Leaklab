# -*- coding: utf-8 -*-
"""Veredito por semelhanca (AY-28 passo 2, 08/09).

O que este arquivo defende, com dados forjados:
- a estrategia por relacao de uma arvore e a media PONDERADA pelo peso das maos com a mesma
  relacao com o board (trocar a relacao de uma mao muda o numero);
- a familia da acao ignora sizing (bet_75pct e bet; jam e allin);
- o veredito provisorio de um torneio novo vem SO de arvores vizinhas (mesma assinatura de
  board, acessadas pelas decisoes que ja tem no), e nao existe sem vizinho;
- `save_decisions` grava `spot_assinatura` (NULL no preflop);
- quando o exato chega, a comparacao grava acao/erro/rotulo igual e NAO reabre linha comparada;
- a curva do card do admin le a comparacao por semana e por rua, e a meta so fecha com duas
  semanas >= 85% no recorte de >= 3 vizinhos.
"""
import json
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
from database.repositories import _adapt                                           # noqa: E402
from leaklab import semelhanca as sm                                               # noqa: E402


# -- puro ---------------------------------------------------------------------------------

def _arvore():
    # board A72 2tone: AK = top pair; KQ de copas = flush draw sem par; 77 = set
    return {'board': ['Ah', '7h', '2c'], 'actions': ['check', 'bet_75pct'],
            'hand_table': [{'hand': 'AdKd', 'weight': 100, 'freqs': [0.2, 0.8], 'evs': [1, 2]},
                           {'hand': 'AsKs', 'weight': 300, 'freqs': [0.6, 0.4], 'evs': [1, 2]},
                           {'hand': 'KhQh', 'weight': 50, 'freqs': [0.0, 1.0], 'evs': [1, 2]},
                           {'hand': '7d7s', 'weight': 0, 'freqs': [1.0, 0.0], 'evs': [1, 2]}]}


def test_estrategia_por_relacao_e_media_ponderada_por_familia():
    e = sm.estrategia_por_relacao(_arvore())
    # top pair: (100*0.8 + 300*0.4) / 400 = 0.5 de bet; a familia e 'bet', nao 'bet_75pct'
    assert e['top_pair-sem_flush-sem_straight'] == {'check': 0.5, 'bet': 0.5}, e
    assert e['nada-flush_draw-sem_straight'] == {'check': 0.0, 'bet': 1.0}, e
    assert 'set-sem_flush-sem_straight' not in e, 'mao com peso 0 nao entra'
    # quebrado de proposito: sem ponderar, top pair daria 0.6 de bet
    assert e['top_pair-sem_flush-sem_straight']['bet'] != 0.6


def test_familia_ignora_sizing_e_unifica_allin():
    assert [sm.familia(a) for a in ('bet_75pct', 'raise_2.5bb', 'jam', 'shove', 'all-in', 'checks', 'folds')] == \
        ['bet', 'raise', 'allin', 'allin', 'allin', 'check', 'fold']


def test_combinar_e_veredito():
    est = sm.combinar([{'check': 0.5, 'bet': 0.5}, {'check': 0.0, 'bet': 1.0}])
    assert est == {'check': 0.25, 'bet': 0.75}
    assert sm.veredito(est, 'bet_50pct') == {'acao': 'bet', 'freq_jogada': 0.75, 'rotulo': 'gto_correct'}
    assert sm.veredito(est, 'check') == {'acao': 'bet', 'freq_jogada': 0.25, 'rotulo': 'gto_minor_deviation'}
    assert sm.veredito(None, 'bet') is None
    assert sm.assinatura_de_board('flop|CO|20-35bb|no_bet|3-A-seco-2tone-desconectado|top_pair-x-y') == 'flop|CO|20-35bb|no_bet|3-A-seco-2tone-desconectado'
    assert sm.relacao_da_assinatura('flop|CO|20-35bb|no_bet|3-A-seco-2tone-desconectado|top_pair-x-y') == 'top_pair-x-y'
    assert sm.assinatura_de_board(None) is None and sm.relacao_da_assinatura('a|b') is None


# -- banco --------------------------------------------------------------------------------

def _limpa():
    init_db()
    conn = get_conn()
    for t in ('vereditos_por_semelhanca', 'gto_tree_relacoes', 'decisions', 'tournaments', 'users',
              'gto_nodes', 'gto_tree_strategies', 'gto_tournament_queue', 'gto_solver_queue'):
        conn.execute('DELETE FROM %s' % t)
    conn.execute(_adapt("INSERT INTO users (id, username, email, password_hash) VALUES (1,'u','u@e.st','h')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, hero) VALUES (1, 1, 'T1', 'Hero')"))
    conn.execute(_adapt("INSERT INTO tournaments (id, user_id, tournament_id, hero) VALUES (2, 1, 'T2', 'Hero')"))
    conn.commit()
    return conn


def _dec(conn, i, tid, spot, board, hero, acao, ass, street='flop'):
    conn.execute(_adapt("INSERT INTO decisions (id,tournament_id,hand_id,street,position,action_taken,best_action,score,label,"
                        "spot_hash,board,hero_cards,stack_bb,facing_bet,spot_assinatura) VALUES (?,?,?,?,'CO',?,?,0.1,'standard',?,?,?,28,0,?)"),
                 (i, tid, 'H%d' % i, street, acao, acao, spot, board, hero, ass))


def _arvore_no_banco(conn, th, spot, board_json, hand_table):
    board = json.loads(board_json)
    conn.execute(_adapt("INSERT INTO gto_nodes (spot_hash,street,position,board,hero_hand,stack_bucket,gto_action,gto_freq,tree_hash) "
                        "VALUES (?,'flop','CO',?,'AhKh','20-35bb','bet',0.7,?)"), (spot, ''.join(board), th))
    conn.execute(_adapt("INSERT INTO gto_tree_strategies (tree_hash,board,actions,hand_table) VALUES (?,?,?,?)"),
                 (th, board_json, '["check","bet_75pct"]', json.dumps(hand_table)))


ASS_A = 'flop|CO|20-35bb|no_bet|3-A-seco-2tone-desconectado|top_pair-sem_flush-sem_straight'


def _semeia_vizinhos():
    """T1 tem duas decisoes COM no e arvore em boards A-seco-2tone (vizinhas); T2 tem uma decisao
    sem no na mesma assinatura (AK em A83 2tone, top pair) e uma preflop."""
    conn = _limpa()
    _dec(conn, 1, 1, 'spot_a', '["Ah","7h","2c"]', 'AdKd', 'bet', ASS_A)
    _dec(conn, 2, 1, 'spot_b', '["As","9s","4d"]', 'AhKh', 'check', ASS_A)
    _arvore_no_banco(conn, 'arv_a', 'spot_a', '["Ah","7h","2c"]',
                     [{'hand': 'AdKd', 'weight': 100, 'freqs': [0.2, 0.8], 'evs': [1, 2]}])
    _arvore_no_banco(conn, 'arv_b', 'spot_b', '["As","9s","4d"]',
                     [{'hand': 'AhKh', 'weight': 100, 'freqs': [0.6, 0.4], 'evs': [1, 2]}])
    # T2: top pair em A83 2tone, sem no; jogou check
    _dec(conn, 3, 2, 'spot_c', '["Ac","8c","3d"]', 'AsKh', 'check', ASS_A)
    _dec(conn, 4, 2, 'spot_pf', '[]', 'AsKh', 'raise', None, street='preflop')
    conn.commit(); conn.close()


def test_provisorio_vem_so_das_arvores_vizinhas_e_nao_existe_sem_vizinho():
    _semeia_vizinhos()
    assert sm.gravar_provisorios(2) == 1
    conn = get_conn()
    v = dict(conn.execute("SELECT * FROM vereditos_por_semelhanca").fetchone())
    assert (v['decision_id'], v['tournament_id'], v['vizinhos']) == (3, 2, 2), v
    # media das duas arvores para top pair: bet (0.8+0.4)/2 = 0.6; jogou check -> 0.4 -> gto_mixed
    assert (v['acao'], v['freq_jogada'], v['rotulo']) == ('bet', 0.4, 'gto_mixed'), v
    assert v['comparado_em'] is None
    assert conn.execute("SELECT COUNT(*) AS n FROM gto_tree_relacoes").fetchone()['n'] == 2, 'cache por arvore'
    # idempotente: rodar de novo nao duplica
    conn.close()
    assert sm.gravar_provisorios(2) == 1
    conn = get_conn()
    assert conn.execute("SELECT COUNT(*) AS n FROM vereditos_por_semelhanca").fetchone()['n'] == 1
    # quebrado de proposito: sem vizinho (outra assinatura de board) nao ha veredito
    conn.execute("UPDATE decisions SET spot_assinatura='flop|CO|20-35bb|no_bet|3-K-par-rainbow-desconectado|top_pair-sem_flush-sem_straight' WHERE id=3")
    conn.execute("DELETE FROM vereditos_por_semelhanca"); conn.commit(); conn.close()
    assert sm.gravar_provisorios(2) == 0


def test_comparacao_com_o_exato_grava_os_tres_acordos_e_nao_reabre():
    _semeia_vizinhos()
    sm.gravar_provisorios(2)
    assert sm.comparar_com_exato(2) == 0, 'sem exato ainda, nada a comparar'
    conn = get_conn()
    # o exato chega: solver diz bet 0.9, jogou check (0.1) -> erro; acao igual; rotulo diferente (critical vs mixed)
    conn.execute("UPDATE decisions SET gto_action='bet_50pct', gto_played_freq=0.1, gto_top_freq=0.9, gto_label='gto_critical' WHERE id=3")
    conn.commit(); conn.close()
    assert sm.comparar_com_exato(2) == 1
    conn = get_conn()
    v = dict(conn.execute("SELECT * FROM vereditos_por_semelhanca").fetchone())
    assert (bool(v['acao_igual']), bool(v['erro_igual']), bool(v['rotulo_igual'])) == (True, False, False), v
    assert v['exato_acao'] == 'bet_50pct' and v['exato_rotulo'] == 'gto_critical' and v['comparado_em']
    # nao reabre: mudar o exato depois nao muda a comparacao, e gravar_provisorios nao apaga linha comparada
    conn.execute("UPDATE decisions SET gto_played_freq=0.5 WHERE id=3"); conn.commit(); conn.close()
    assert sm.comparar_com_exato(2) == 0
    assert sm.gravar_provisorios(2) == 1
    conn = get_conn()
    assert conn.execute("SELECT COUNT(*) AS n FROM vereditos_por_semelhanca").fetchone()['n'] == 2, 'a comparada fica; uma nova aberta nasce'
    conn.close()


def test_o_gancho_da_fila_drenada_compara_os_provisorios():
    _semeia_vizinhos()
    sm.gravar_provisorios(2)
    conn = get_conn()
    conn.execute("UPDATE decisions SET gto_action='bet', gto_played_freq=0.1, gto_top_freq=0.9, gto_label='gto_critical', label='clear_mistake', best_action='bet' WHERE id=3")
    conn.execute(_adapt("INSERT INTO gto_tournament_queue (tournament_id, spot_hash) VALUES (2, 'spot_c')"))
    conn.execute(_adapt("INSERT INTO gto_solver_queue (spot_hash, spot_json, status, priority, requested_at, solved_at) "
                        "VALUES ('spot_c', '{}', 'done', 0, '2026-09-02 00:00:00', '2026-09-03 00:00:00')"))
    conn.commit(); conn.close()
    from api.app import _reconcile_drained_tournaments
    _reconcile_drained_tournaments()
    conn = get_conn()
    v = dict(conn.execute("SELECT comparado_em, acao_igual FROM vereditos_por_semelhanca WHERE decision_id=3").fetchone())
    conn.close()
    assert v['comparado_em'] and bool(v['acao_igual']), v


def test_o_upload_grava_a_assinatura_e_o_gancho_grava_o_provisorio():
    _semeia_vizinhos()
    results = [
        {'handId': 'H9', 'street': 'flop', 'hero_cards': 'AsKh', 'board': ['Ac', '8c', '3d'], 'actionTaken': 'check',
         'bestAction': 'bet', 'evaluation': {'label': 'standard', 'mistakeScore': 0.1}, 'context': {'heroStackBb': 27.5},
         'position': 'CO', 'spot': {'facingToBb': 0.0}},
        {'handId': 'H9', 'street': 'preflop', 'hero_cards': 'AsKh', 'board': [], 'actionTaken': 'raise',
         'bestAction': 'raise', 'evaluation': {'label': 'standard', 'mistakeScore': 0.0}, 'context': {'heroStackBb': 27.5},
         'position': 'CO', 'spot': {}},
    ]
    repo.save_decisions(2, results)
    conn = get_conn()
    rows = {r['street']: r['spot_assinatura'] for r in conn.execute("SELECT street, spot_assinatura FROM decisions WHERE tournament_id=2").fetchall()}
    conn.close()
    assert rows == {'flop': ASS_A, 'preflop': None}, rows
    assert sm.gravar_provisorios(2) == 1


def test_a_curva_do_admin_le_a_comparacao_e_a_meta_exige_duas_semanas():
    _semeia_vizinhos()
    conn = get_conn()
    conn.execute("DELETE FROM decisions WHERE id=4")
    agora = datetime.utcnow()
    def v(i, dec, viz, acao, erro, rot, dias):
        conn.execute(_adapt("INSERT INTO vereditos_por_semelhanca (id,decision_id,tournament_id,assinatura,vizinhos,acao,freq_jogada,rotulo,"
                            "acao_igual,erro_igual,rotulo_igual,comparado_em) VALUES (?,?,?,?,?,'bet',0.5,'gto_mixed',?,?,?,?)"),
                     (i, dec, 1, ASS_A, viz, acao, erro, rot, (agora - timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')))
    v(1, 1, 3, True, True, True, 1)
    v(2, 2, 3, False, True, False, 1)
    v(3, 3, 1, False, False, False, 1)      # 1 vizinho: fora do recorte da meta
    v(4, 1, 3, True, True, True, 8)         # semana anterior
    conn.execute(_adapt("INSERT INTO vereditos_por_semelhanca (id,decision_id,tournament_id,assinatura,vizinhos,acao,freq_jogada,rotulo) "
                        "VALUES (5,2,1,?,2,'bet',0.5,'gto_mixed')"), (ASS_A,))   # aberto
    conn.execute("UPDATE decisions SET street='turn' WHERE id=3")
    conn.commit(); conn.close()
    c = repo.get_aproveitamento_do_solver(dias=56)['semelhanca']['curva']
    assert c['total'] == {'comparadas': 4, 'acao_pct': 50, 'erro_pct': 75, 'rotulo_pct': 50}, c['total']
    assert c['com_3_vizinhos'] == {'comparadas': 3, 'acao_pct': 67, 'erro_pct': 100, 'rotulo_pct': 67}, c['com_3_vizinhos']
    assert c['abertos'] == 1
    assert c['ruas']['turn'] == {'comparadas': 1, 'acao_pct': 0, 'erro_pct': 0, 'rotulo_pct': 0}, c['ruas']
    assert len(c['semanas']) == 2 and c['semanas'][-1]['comparadas'] == 3 and c['semanas'][-1]['com_3_vizinhos']['erro_pct'] == 100, c['semanas']
    assert c['meta'] == {'pct': 85, 'min_vizinhos': 3, 'atingida': True}, c['meta']
    # quebrado de proposito: a semana anterior cai abaixo de 85% -> meta nao atingida
    conn = get_conn(); conn.execute("UPDATE vereditos_por_semelhanca SET erro_igual=FALSE WHERE id=4"); conn.commit(); conn.close()
    assert repo.get_aproveitamento_do_solver(dias=56)['semelhanca']['curva']['meta']['atingida'] is False
    # e sem nenhuma comparacao a curva nao inventa zero
    conn = get_conn(); conn.execute("DELETE FROM vereditos_por_semelhanca"); conn.commit(); conn.close()
    c = repo.get_aproveitamento_do_solver(dias=56)['semelhanca']['curva']
    assert c['semanas'] == [] and c['total']['erro_pct'] is None and c['meta']['atingida'] is False


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
