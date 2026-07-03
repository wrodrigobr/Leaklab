"""
Blindagem do insert_gto_nodes: um re-solve NUNCA rebaixa um nó bom.
Regressão do incidente do --force (re-solve em massa sobrescreveu nós compartilhados).
DB SQLite temporário isolado.
"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['LEAKLAB_DB'] = tempfile.mktemp(suffix='.db')

import database.schema as sch
import database.repositories as repo
sch.init_db()
from leaklab.gto_utils import compute_spot_hash

_SH = compute_spot_hash('flop', 'CO', ['9h', 'Ac', '5h'], ['Ah', 'Kd'], 20.0, 0.0)


def _node(exploit, strat, action='check', source='solver_cli'):
    return {'spot_hash': _SH, 'street': 'flop', 'position': 'CO', 'board': ['9h', 'Ac', '5h'],
            'hero_hand': ['Ah', 'Kd'], 'hero_stack_bb': 20.0, 'gto_action': action, 'gto_freq': 0.6,
            'exploitability_pct': exploit, 'strategy_json': strat, 'source': source, 'iterations': 100}


def _cur():
    return dict(repo.get_gto_node(_SH))


def test_insert_guard_keeps_better_node():
    # 1) nó bom
    repo.insert_gto_nodes([_node(3.0, '{"check":0.6,"bet":0.4}')])
    assert _cur()['exploitability_pct'] == 3.0

    # 2) re-solve PIOR (exploitability maior) não sobrescreve
    repo.insert_gto_nodes([_node(20.0, '{"check":0.9,"bet":0.1}', action='bet')])
    n = _cur()
    assert n['exploitability_pct'] == 3.0 and n['gto_action'] == 'check', ('rebaixou!', n)

    # 3) nó SEM estratégia (re-solve rejeitado/parcial) não sobrescreve o bom
    repo.insert_gto_nodes([_node(1.0, None, action='fold', source='gto_wizard')])
    assert _cur()['gto_action'] == 'check', 'aceitou nó sem estratégia'

    # 4) re-solve MELHOR (exploitability menor) substitui
    repo.insert_gto_nodes([_node(2.0, '{"bet":1.0}', action='bet')])
    n = _cur()
    assert n['exploitability_pct'] == 2.0 and n['gto_action'] == 'bet', ('não aceitou o melhor', n)
    print("OK  test_insert_guard_keeps_better_node")


def test_insert_guard_never_downgrades_gw():
    sh2 = compute_spot_hash('turn', 'BTN', ['9h', 'Ac', '5h', '2d'], ['Ah', 'Kd'], 30.0, 0.0)
    def gw(action):
        return {'spot_hash': sh2, 'street': 'turn', 'position': 'BTN',
                'board': ['9h', 'Ac', '5h', '2d'], 'hero_hand': ['Ah', 'Kd'], 'hero_stack_bb': 30.0,
                'gto_action': action, 'gto_freq': 0.7, 'exploitability_pct': None,
                'strategy_json': '{"check":0.7,"bet":0.3}', 'source': 'gto_wizard', 'iterations': None}
    repo.insert_gto_nodes([gw('check')])
    assert _cur() is None or dict(repo.get_gto_node(sh2))['source'] == 'gto_wizard'
    # solver tenta sobrescrever o GW → NÃO pode (GW é preferido/Nash)
    solver = {**gw('bet'), 'source': 'solver_cli', 'exploitability_pct': 1.0}
    repo.insert_gto_nodes([solver])
    n = dict(repo.get_gto_node(sh2))
    assert n['source'] == 'gto_wizard' and n['gto_action'] == 'check', ('rebaixou GW!', n)
    print("OK  test_insert_guard_never_downgrades_gw")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    try: os.unlink(os.environ['LEAKLAB_DB'])
    except Exception: pass
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
