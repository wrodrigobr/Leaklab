"""
Testes da Fase 1 do plano do solver (specs/solver-improvement-plan.md):
tree_hash (identidade da árvore, sem hero_hand) + isomorfismo de naipes
(canonical_board_key) + dedup de solves no worker (cópia de nó existente).
"""
import sys, os, json, traceback, tempfile, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.gto_utils import canonical_board_key, compute_tree_hash


# ── canonical_board_key — isomorfismo ──────────────────────────────────────────

def test_iso_flop_suit_permutation():
    # As Kd 2c e Ah Kc 2d são o mesmo jogo (permutação de naipes)
    assert canonical_board_key(['As', 'Kd', '2c']) == canonical_board_key(['Ah', 'Kc', '2d'])
    print("OK  test_iso_flop_suit_permutation")


def test_iso_flop_is_set():
    # ordem das cartas do flop não importa
    assert canonical_board_key(['Kd', '2c', 'As']) == canonical_board_key(['As', 'Kd', '2c'])
    print("OK  test_iso_flop_is_set")


def test_iso_turn_position_matters():
    # Qh no turn != Qh no flop (streets distintas)
    assert canonical_board_key(['As', 'Kd', '2c', 'Qh']) != canonical_board_key(['As', 'Kd', 'Qh', '2c'])
    print("OK  test_iso_turn_position_matters")


def test_iso_distinct_boards_differ():
    assert canonical_board_key(['As', 'Kd', '2c']) != canonical_board_key(['As', 'Kd', '3c'])
    # monotone vs rainbow NÃO são isomorfos
    assert canonical_board_key(['As', 'Ks', '2s']) != canonical_board_key(['As', 'Kd', '2c'])
    print("OK  test_iso_distinct_boards_differ")


def test_iso_random_permutation_property():
    # property-based: para qualquer board, qualquer permutação de naipes → mesma chave
    import random
    from itertools import permutations
    random.seed(42)
    suits = 'cdhs'
    deck = [r + s for r in '23456789TJQKA' for s in suits]
    perms = list(permutations(suits))
    for _ in range(60):
        board = random.sample(deck, random.choice([3, 4, 5]))
        base = canonical_board_key(board)
        m = dict(zip(suits, random.choice(perms)))
        iso = [c[0] + m[c[1]] for c in board]
        assert canonical_board_key(iso) == base, (board, iso)
    print("OK  test_iso_random_permutation_property")


# ── compute_tree_hash ──────────────────────────────────────────────────────────

_BASE_PAYLOAD = {
    'street': 'flop', 'board': ['As', 'Kd', '2c'],
    'oop_range': 'AA,KK,QQ', 'ip_range': 'AKs,AQs,JJ+',
    'pot_bb': 10.0, 'effective_stack_bb': 40.0,
    'facing_size_bb': 0.0, 'hero_is_ip': False,
}


def test_tree_hash_iso_and_convergence_invariant():
    # board isomorfo + params de convergência diferentes → MESMO hash
    p2 = dict(_BASE_PAYLOAD, board=['Ah', 'Kc', '2d'],
              max_iterations=9999, target_exploitability_pct=0.1)
    assert compute_tree_hash(_BASE_PAYLOAD) == compute_tree_hash(p2)
    print("OK  test_tree_hash_iso_and_convergence_invariant")


def test_tree_hash_distinguishes_game_changers():
    h0 = compute_tree_hash(_BASE_PAYLOAD)
    assert compute_tree_hash(dict(_BASE_PAYLOAD, facing_size_bb=5.0)) != h0
    assert compute_tree_hash(dict(_BASE_PAYLOAD, hero_is_ip=True)) != h0
    assert compute_tree_hash(dict(_BASE_PAYLOAD, oop_range='22+')) != h0
    assert compute_tree_hash(dict(_BASE_PAYLOAD, pot_bb=20.0)) != h0
    assert compute_tree_hash(dict(_BASE_PAYLOAD, effective_stack_bb=60.0)) != h0
    print("OK  test_tree_hash_distinguishes_game_changers")


# ── Integração: dedup no banco + worker ────────────────────────────────────────

def _setup_db():
    TEST_DB = tempfile.mktemp(suffix='.db')
    import database.schema as sch
    import database.repositories as repo
    def get_conn_test():
        conn = sqlite3.connect(TEST_DB)
        conn.row_factory = sqlite3.Row
        return conn
    sch.get_conn  = get_conn_test
    repo.get_conn = get_conn_test
    sch.init_db()
    return repo


def test_node_lookup_by_tree_hash():
    repo = _setup_db()
    th = compute_tree_hash(_BASE_PAYLOAD)
    n = repo.insert_gto_nodes([{
        'spot_hash': 'spot_a', 'tree_hash': th,
        'street': 'flop', 'position': 'BB', 'board': ['As', 'Kd', '2c'],
        'hero_hand': ['Ah', 'Qh'], 'hero_stack_bb': 40.0, 'facing_size_bb': 0.0,
        'gto_action': 'check', 'gto_freq': 0.7, 'exploitability_pct': 0.5,
        'source': 'solver_cli',
        'strategy_detail': {'check': {'frequency': 0.7}, 'bet': {'frequency': 0.3}},
    }])
    assert n == 1
    found = repo.get_gto_node_by_tree_hash(th)
    assert found and found['spot_hash'] == 'spot_a' and found['strategy_json']
    assert repo.get_gto_node_by_tree_hash('inexistente') is None
    print("OK  test_node_lookup_by_tree_hash")


def test_enqueue_stores_tree_hash():
    repo = _setup_db()
    spot = dict(_BASE_PAYLOAD)
    assert repo.enqueue_solver_spot('spot_q1', json.dumps(spot), 5)
    job = repo.get_next_solver_job()
    assert job and job['spot_hash'] == 'spot_q1'
    assert job['tree_hash'] == compute_tree_hash(spot)
    print("OK  test_enqueue_stores_tree_hash")


def test_worker_copies_instead_of_solving():
    repo = _setup_db()
    # nó existente: árvore solvada com a mão X num board
    th = compute_tree_hash(_BASE_PAYLOAD)
    repo.insert_gto_nodes([{
        'spot_hash': 'spot_orig', 'tree_hash': th,
        'street': 'flop', 'position': 'BB', 'board': ['As', 'Kd', '2c'],
        'hero_hand': ['Ah', 'Qh'], 'hero_stack_bb': 40.0, 'facing_size_bb': 0.0,
        'gto_action': 'check', 'gto_freq': 0.7, 'exploitability_pct': 0.5,
        'source': 'solver_cli',
        'strategy_detail': {'check': {'frequency': 0.7}, 'bet': {'frequency': 0.3}},
    }])
    # fila: MESMA árvore, board isomorfo + outra mão do hero → deve COPIAR, não solvar
    spot_iso = dict(_BASE_PAYLOAD, board=['Ah', 'Kc', '2d'])
    spot_iso['_meta'] = {'position': 'BB', 'hero_hand': ['Th', 'Td'], 'hero_stack_bb': 40.0}
    assert repo.enqueue_solver_spot('spot_novo', json.dumps(spot_iso), 5)

    import leaklab.gto_solver as gs
    old_env = os.environ.pop('GTO_SOLVER_URL', None)
    old_bin = gs._solver_binary
    gs._solver_binary = lambda: '/bin/true'  # nunca chamado: a cópia vem antes do solve
    try:
        result = gs.run_solver_worker(max_jobs=3)
    finally:
        gs._solver_binary = old_bin
        if old_env is not None:
            os.environ['GTO_SOLVER_URL'] = old_env
    assert result.get('copied') == 1, result
    assert result.get('solved') == 0 and result.get('failed') == 0, result
    node = repo.get_gto_node('spot_novo')
    assert node and node['gto_action'] == 'check' and node['strategy_json']
    print("OK  test_worker_copies_instead_of_solving")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
