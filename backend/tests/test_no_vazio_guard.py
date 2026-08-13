# -*- coding: utf-8 -*-
"""O guarda do solve vazio: insert_gto_nodes REJEITA solver_cli sem estratégia.

Achado no ataque aos 7 vanished (12/08): 45 nós em produção com strategy_json NULL e a fila
dizendo `done`. O solve falhou (o solver devolveu sem `strategy_detail`), o escritor gravou
assim mesmo — e o nó vazio OCUPA o hash: o reenqueue passa a dizer "coberto" e o spot fica
heurístico para sempre. Pior: no caso t23 o lookup caiu num nó vizinho de check para um spot
com facing de 8,68bb.

A regra é a 6 do CLAUDE.md: operação que pode falhar em silêncio precisa de conferência
explícita. O guarda mora no PONTO ÚNICO (insert_gto_nodes), então cobre todos os escritores —
pool local, worker remoto, scripts — sem edição por chamador: `inserted=0` já faz cada um
marcar o job como rejected em vez de done.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
sch.SQLITE_PATH = os.environ['LEAKLAB_DB']
sch.init_db()
from database.repositories import insert_gto_nodes, get_gto_node


def _no(**extra):
    base = {
        'spot_hash': extra.pop('spot_hash', 'teste-no-vazio'),
        'street': 'flop', 'position': 'BTN', 'board': ['2h', '7c', '9d'],
        'hero_hand': [], 'hero_stack_bb': 25.0, 'facing_size_bb': 0.0,
        'gto_action': 'check', 'gto_freq': 0.8, 'exploitability_pct': 1.0,
    }
    base.update(extra)
    return base


def test_solver_cli_sem_estrategia_e_rejeitado():
    n = _no(spot_hash='vazio-1')  # source default: solver_cli; sem strategy_detail
    assert insert_gto_nodes([n]) == 0, 'solve vazio foi gravado — a falha silenciosa voltou'
    assert get_gto_node('vazio-1') is None, 'o nó vazio ocupou o hash mesmo rejeitado'
    print('OK  test_solver_cli_sem_estrategia_e_rejeitado')


def test_solver_cli_COM_estrategia_segue_entrando():
    """A âncora: sem ela, "rejeitar tudo" passaria no teste de cima."""
    n = _no(spot_hash='cheio-1',
            strategy_detail={'check': {'frequency': 0.8}, 'bet': {'frequency': 0.2}})
    assert insert_gto_nodes([n]) == 1, 'o guarda ficou largo — nó são foi rejeitado'
    assert get_gto_node('cheio-1') is not None
    print('OK  test_solver_cli_COM_estrategia_segue_entrando')


def test_gto_wizard_preflop_sem_estrategia_nao_e_alvo():
    """O guarda mira o solve (solver_cli). Fonte gto_wizard com exploitability declarada
    mantém o comportamento anterior — mudar isso seria conserto causando dano que o bug
    não causava (importadores de captura não passam por solve)."""
    n = _no(spot_hash='gw-1', source='gto_wizard', street='preflop', board=[],
            exploitability_pct=0.0)
    assert insert_gto_nodes([n]) == 1, 'o guarda vazou para fora do solver_cli'
    print('OK  test_gto_wizard_preflop_sem_estrategia_nao_e_alvo')


def test_rejected_com_payload_IGUAL_nao_reenfileira_e_com_payload_novo_sim():
    """O par do reset de `rejected`: payload novo merece solve novo, payload IGUAL produz o
    mesmo resultado — re-enfileirá-lo é pagar o solve para re-rejeitar em loop (o spot t23
    de nó inalcançado voltaria à fila a cada rodada do reenqueue)."""
    from database.repositories import enqueue_solver_spot
    from database.schema import get_conn
    payload = '{"street": "flop", "board": ["2h", "7c", "9d"], "pot_bb": 5.0}'
    assert enqueue_solver_spot('rejeitado-1', payload) is True
    conn = get_conn()
    conn.execute("UPDATE gto_solver_queue SET status='rejected' WHERE spot_hash='rejeitado-1'")
    conn.commit(); conn.close()
    assert enqueue_solver_spot('rejeitado-1', payload) is False, (
        'payload IGUAL re-enfileirou um rejected — o loop de re-pagar o solve voltou')
    payload2 = '{"street": "flop", "board": ["2h", "7c", "9d"], "pot_bb": 6.0}'
    assert enqueue_solver_spot('rejeitado-1', payload2) is True, (
        'payload NOVO não resetou o rejected — spots presos no payload que os condenou')
    print('OK  test_rejected_com_payload_IGUAL_nao_reenfileira_e_com_payload_novo_sim')


if __name__ == '__main__':
    import sys as _s
    _testes = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    _falhas = 0
    for _t in _testes:
        try:
            _t()
        except Exception as _e:
            _falhas += 1
            print('FALHOU  %s: %s: %s' % (_t.__name__, type(_e).__name__, _e))
    print()
    print('Total: %d | Passed: %d | Failed: %d' % (len(_testes), len(_testes) - _falhas, _falhas))
    _s.exit(1 if _falhas else 0)
