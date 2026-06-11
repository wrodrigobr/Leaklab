"""
Testes da Fase 3 do plano do solver (specs/solver-improvement-plan.md):
visão POR MÃO da árvore solvada — iso_suit_map, gto_tree_strategies,
hand_view_for_spot e veredito hand-aware no engine (_enrich_gto).
"""
import sys, os, json, traceback, tempfile, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.gto_utils import (iso_suit_map, map_cards_suits, canonical_board_key,
                               compute_tree_hash, compute_spot_hash)


# ── iso_suit_map ───────────────────────────────────────────────────────────────

def test_iso_map_identity():
    m = iso_suit_map(['As', 'Kd', '2c'], ['As', 'Kd', '2c'])
    assert m is not None and map_cards_suits(['Ah', 'Qh'], m) == ['Ah', 'Qh']
    print("OK  test_iso_map_identity")


def test_iso_map_permuted():
    # spot Ad Kh 2s ↔ stored As Kd 2c: d→s, h→d, s→c
    m = iso_suit_map(['Ad', 'Kh', '2s'], ['As', 'Kd', '2c'])
    assert m is not None
    assert map_cards_suits(['Ad', 'Kh', '2s'], m) in (['As', 'Kd', '2c'],)
    print("OK  test_iso_map_permuted")


def test_iso_map_non_isomorphic():
    assert iso_suit_map(['As', 'Ks', '2s'], ['As', 'Kd', '2c']) is None  # monotone vs rainbow
    assert iso_suit_map(['As', 'Kd', '2c'], ['As', 'Kd', '3c']) is None  # ranks diferentes
    print("OK  test_iso_map_non_isomorphic")


def test_iso_map_roundtrip_property():
    import random
    from itertools import permutations
    random.seed(7)
    suits = 'cdhs'
    deck = [r + s for r in '23456789TJQKA' for s in suits]
    for _ in range(40):
        board = random.sample(deck, random.choice([3, 4, 5]))
        pm = dict(zip(suits, random.choice(list(permutations(suits)))))
        iso = [c[0] + pm[c[1]] for c in board]
        m = iso_suit_map(board, iso)
        assert m is not None, (board, iso)
        mapped = map_cards_suits(board, m)
        # flop como conjunto, turn/river posicionais
        assert sorted(mapped[:3]) == sorted(iso[:3]) and mapped[3:] == iso[3:], (board, iso, m)
    print("OK  test_iso_map_roundtrip_property")


# ── DB + hand_view_for_spot ────────────────────────────────────────────────────

def _setup_db():
    TEST_DB = tempfile.mktemp(suffix='.db')
    import database.schema as sch
    import database.repositories as repo
    def gc():
        conn = sqlite3.connect(TEST_DB)
        conn.row_factory = sqlite3.Row
        return conn
    sch.get_conn = gc
    repo.get_conn = gc
    sch.init_db()
    return repo


_STORED_BOARD = ['As', 'Kd', '2c']
_ACTIONS      = ['check', 'bet_50pct']
_HAND_TABLE   = [
    {'hand': 'AhQh', 'weight': 1.0, 'freqs': [0.10, 0.90], 'evs': [1.00, 1.50]},
    {'hand': 'QsJs', 'weight': 1.0, 'freqs': [0.95, 0.05], 'evs': [0.40, 0.10]},
]


def test_hand_view_same_board_and_iso():
    repo = _setup_db()
    assert repo.upsert_tree_strategy('th_test', _STORED_BOARD, _ACTIONS, _HAND_TABLE)
    from leaklab.gto_solver import hand_view_for_spot

    # mesmo board, ordem da mão invertida
    v = hand_view_for_spot('th_test', _STORED_BOARD, ['Qh', 'Ah'])
    assert v and v['best_action'] == 'bet_50pct'
    assert v['actions']['check']['ev_loss_bb'] == 0.5
    assert v['actions']['bet_50pct']['ev_loss_bb'] == 0.0

    # board ISOMORFO (d→s,h→d,s→c... spot Ad Kh 2s) — mão AcQc mapeia p/ AhQh
    v2 = hand_view_for_spot('th_test', ['Ad', 'Kh', '2s'], ['Ac', 'Qc'])
    assert v2 and v2['actions']['bet_50pct']['frequency'] == 0.90, v2

    # mão fora do range do solve → None
    assert hand_view_for_spot('th_test', _STORED_BOARD, ['7d', '2h']) is None
    # tree_hash inexistente → None
    assert hand_view_for_spot('th_nao_existe', _STORED_BOARD, ['Ah', 'Qh']) is None
    print("OK  test_hand_view_same_board_and_iso")


def test_engine_verdict_hand_aware():
    """AhQh aposta 90% (mão) num nó cuja RANGE checa 65% — o veredito do bet
    deve ser gto_correct (hand-aware), não gto_mixed (agregado)."""
    repo = _setup_db()
    stack, facing = 40.0, 0.0
    hero = ['Ah', 'Qh']
    sh = compute_spot_hash('flop', 'BB', _STORED_BOARD, hero, stack, facing)
    repo.insert_gto_nodes([{
        'spot_hash': sh, 'tree_hash': 'th_eng',
        'street': 'flop', 'position': 'BB', 'board': _STORED_BOARD,
        'hero_hand': hero, 'hero_stack_bb': stack, 'facing_size_bb': facing,
        'gto_action': 'check', 'gto_freq': 0.65, 'exploitability_pct': 0.5,
        'source': 'solver_cli',
        'strategy_detail': {'check': {'frequency': 0.65}, 'bet': {'frequency': 0.35}},
    }])
    repo.upsert_tree_strategy('th_eng', _STORED_BOARD, _ACTIONS, _HAND_TABLE)

    from leaklab.decision_engine_v11 import _enrich_gto
    inp = {
        'street': 'flop', 'player_action': 'bet',
        'hero_cards': hero, 'math': {},
        'spot': {'board': _STORED_BOARD, 'position': 'BB',
                 'effectiveStackBb': stack, 'facingToBb': facing},
    }
    os.environ['GTO_HAND_AWARE'] = '1'
    r = _enrich_gto(inp)
    assert r.get('available'), r
    assert r.get('hand_aware') is True, r
    assert r.get('gto_label') == 'gto_correct', r       # mão aposta 90%
    assert r.get('ev_loss_bb') == 0.0, r                # bet é a melhor ação da mão

    # check com a mesma mão: freq 10% e custo 0.5bb → desvio (não correto)
    r2 = _enrich_gto({**inp, 'player_action': 'check'})
    assert r2.get('hand_aware') is True
    assert r2.get('gto_label') in ('gto_minor_deviation', 'gto_critical'), r2
    assert r2.get('ev_loss_bb') == 0.5, r2

    # flag OFF → volta ao agregado (gto_mixed p/ bet 35%)
    os.environ['GTO_HAND_AWARE'] = '0'
    r3 = _enrich_gto(inp)
    assert r3.get('hand_aware') is False
    assert r3.get('gto_label') == 'gto_mixed', r3
    os.environ['GTO_HAND_AWARE'] = '1'
    print("OK  test_engine_verdict_hand_aware")


def test_postflop_ev_loss_persisted_to_decisions():
    """Fio completo do #24 postflop: _enrich_gto.ev_loss_bb → result['gto'] →
    save_decisions → coluna decisions.ev_loss_bb (+source 'solver_hand')."""
    repo = _setup_db()
    stack = 40.0
    hero = ['Ah', 'Qh']
    sh = compute_spot_hash('flop', 'BB', _STORED_BOARD, hero, stack, 0.0)
    repo.insert_gto_nodes([{
        'spot_hash': sh, 'tree_hash': 'th_e2e', 'street': 'flop', 'position': 'BB',
        'board': _STORED_BOARD, 'hero_hand': hero, 'hero_stack_bb': stack,
        'facing_size_bb': 0.0, 'gto_action': 'check', 'gto_freq': 0.65,
        'exploitability_pct': 0.5, 'source': 'solver_cli',
        'strategy_detail': {'check': {'frequency': 0.65}, 'bet': {'frequency': 0.35}},
    }])
    repo.upsert_tree_strategy('th_e2e', _STORED_BOARD, _ACTIONS, _HAND_TABLE)

    os.environ['GTO_HAND_AWARE'] = '1'
    from leaklab.decision_engine_v11 import _enrich_gto
    g = _enrich_gto({'street': 'flop', 'player_action': 'check', 'hero_cards': hero,
                     'math': {}, 'spot': {'board': _STORED_BOARD, 'position': 'BB',
                                          'effectiveStackBb': stack, 'facingToBb': 0.0}})
    assert g['ev_loss_bb'] == 0.5 and g['ev_loss_source'] == 'solver_hand', g

    import database.repositories as _repo
    conn = _repo.get_conn()
    conn.execute("INSERT INTO tournaments (user_id, tournament_id, site, tournament_name, hero) "
                 "VALUES (1,'t1','GG','t','hero')")
    conn.commit()
    tid = conn.execute("SELECT id FROM tournaments ORDER BY id DESC LIMIT 1").fetchone()[0]
    conn.close()
    repo.save_decisions(tid, [{
        'handId': 'h1', 'street': 'flop', 'hero_cards': 'Ah Qh', 'board': _STORED_BOARD,
        'actionTaken': 'check', 'bestAction': 'bet',
        'evaluation': {'label': 'marginal', 'mistakeScore': 0.2, 'scoreBreakdown': {}},
        'spot': {'board': _STORED_BOARD, 'position': 'BB', 'effectiveStackBb': stack},
        'math': {'estimatedHandEquity': 0.6}, 'context': {}, 'position': 'BB',
        'gto': g,
    }])
    conn = _repo.get_conn()
    row = conn.execute("SELECT ev_loss_bb, ev_loss_source FROM decisions "
                       "WHERE tournament_id=?", (tid,)).fetchone()
    conn.close()
    assert row and row['ev_loss_bb'] == 0.5 and row['ev_loss_source'] == 'solver_hand',         (dict(row) if row else None)
    print("OK  test_postflop_ev_loss_persisted_to_decisions")


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
