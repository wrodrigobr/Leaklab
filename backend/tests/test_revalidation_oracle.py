"""
Testa leaklab.revalidation.oracle.decide -- veredicto independente do engine.

Cobre as 5 fontes:
  rule_bb_free_check, preflop_ranges_static, postflop_strategy,
  postflop_top_action, heuristic_pushfold, heuristic_potodds, unavailable
"""
import sys, os, json, sqlite3, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Banco isolado em memória ANTES de importar repositories
os.environ['LEAKLAB_DB'] = ':memory:'

from leaklab.revalidation.oracle import decide, OracleDecision
from leaklab.gto_utils import compute_spot_hash


# -- Fábrica de decision_input ------------------------------------------------

def _di(street='preflop', position='BTN', action='raise', hero_cards=None,
        facing=0.0, stack_bb=50.0, board=None, equity=None, pot_odds=None,
        m_ratio=None, villain_position='', is_3bet=False, is_multiway=False):
    return {
        'hand_id': 'TEST_HAND',
        'street': street,
        'player_action': action,
        'hero_cards': hero_cards or [],
        'is_3bet': is_3bet,
        'spot': {
            'spotType': 'open',
            'position': position,
            'villainPosition': villain_position,
            'isInPosition': position in {'BTN', 'CO', 'HJ'},
            'isMultiway': is_multiway,
            'effectiveStackBb': stack_bb,
            'potSize': 1.5,
            'facingSize': facing,
            'raiseSizeBb': facing,
            'board': board or [],
        },
        'hand_profile': {},
        'math': {
            'potOddsEquity':       pot_odds,
            'estimatedHandEquity': equity,
            'rawEquity':           equity,
            'drawProfile':         'none',
            'equityAdjustment':    0.0,
            'impliedOddsFactor':   0.0,
            'reverseImpliedOddsFactor': 0.0,
            'pressureScore':       0.0,
        },
        'range_evaluation': {
            'recommendedPrimaryAction': 'fold',
            'alternativeActions': [],
            'rangeZone': 'unknown',
            'confidence': 'low',
            'mixWeight': 0.0,
        },
        'context': {
            'tournamentStage': 'mid',
            'icmPressure': 'low',
            'bountyDynamic': False,
            'readsAvailable': False,
            'mRatio': m_ratio,
            'heroStackBb': stack_bb,
        },
    }


# -- Stub do gto_node em memória -----------------------------------------------

class _FakeNodeStore:
    """Substitui get_gto_node por lookup em dict em memória."""

    def __init__(self):
        self._nodes: dict[str, dict] = {}
        self._installed = False
        self._saved = None

    def install(self):
        from database import repositories as repo
        if self._installed:
            return
        self._saved = repo.get_gto_node
        repo.get_gto_node = self._nodes.get
        self._installed = True

    def restore(self):
        if not self._installed:
            return
        from database import repositories as repo
        repo.get_gto_node = self._saved
        self._installed = False

    def add(self, *, street, position, board, hero_hand, stack_bb, facing,
            gto_action, gto_freq, strategy_json=None):
        h = compute_spot_hash(street, position, board, hero_hand, stack_bb, facing)
        self._nodes[h] = {
            'spot_hash': h, 'street': street, 'position': position.upper(),
            'board': json.dumps(board), 'hero_hand': json.dumps(hero_hand),
            'gto_action': gto_action, 'gto_freq': gto_freq,
            'strategy_json': strategy_json,
            'exploitability_pct': 2.5,
        }


# -- Testes --------------------------------------------------------------------

def test_bb_free_check_is_rule():
    d = decide(_di(street='preflop', position='BB', action='check', facing=0.0,
                   hero_cards=['7s', '4s']))
    assert d.action == 'check'
    assert d.source == 'rule_bb_free_check'
    assert d.confidence == 'high'
    print("OK  test_bb_free_check_is_rule")


def test_preflop_aa_utg_is_raise():
    d = decide(_di(street='preflop', position='UTG', action='raise', facing=0.0,
                   stack_bb=50.0, hero_cards=['Ah', 'Ad']))
    assert d.source == 'preflop_ranges_static', f"esperado preflop_ranges_static, recebi {d.source} / action={d.action}"
    assert d.action in {'raise', 'jam'}
    assert d.confidence == 'high'
    print(f"OK  test_preflop_aa_utg_is_raise (action={d.action})")


def test_preflop_72o_utg_is_fold():
    d = decide(_di(street='preflop', position='UTG', action='fold', facing=0.0,
                   stack_bb=50.0, hero_cards=['7c', '2d']))
    assert d.source in {'preflop_ranges_static', 'heuristic_potodds'}
    assert d.action == 'fold'
    print(f"OK  test_preflop_72o_utg_is_fold (source={d.source})")


def test_preflop_vs_rfi_kqs_bb_responds():
    d = decide(_di(street='preflop', position='BB', action='call', facing=2.5,
                   villain_position='BTN', stack_bb=50.0,
                   hero_cards=['Kh', 'Qh']))
    assert d.source == 'preflop_ranges_static'
    # GTO sugere call ou 3bet -- qualquer dos dois é aceitável
    assert d.action in {'call', 'raise', 'jam'}
    print(f"OK  test_preflop_vs_rfi_kqs_bb_responds (action={d.action})")


def test_pushfold_high_equity_jam():
    d = decide(_di(street='preflop', position='BTN', action='jam', facing=0.0,
                   stack_bb=8.0, m_ratio=4.5, hero_cards=['Ad', '5d'],
                   equity=0.55))
    # M=4.5 < 6 force push/fold heuristic when preflop ranges não tem cobertura -- mas
    # com BTN @ 8bb existe range. Aceita qualquer fonte que escolha jam.
    assert d.action in {'jam', 'raise'}, f"esperado jam, recebi {d.action} / source={d.source}"
    print(f"OK  test_pushfold_high_equity_jam (source={d.source}, action={d.action})")


def test_pushfold_low_equity_fold():
    # M < 6 + position que NÃO tem cobertura preflop = força heuristic_pushfold
    d = decide(_di(street='preflop', position='UTG', action='fold', facing=2.0,
                   stack_bb=4.0, m_ratio=3.0, hero_cards=['8c', '3d'],
                   equity=0.20, pot_odds=0.30, is_3bet=True, villain_position='CO'))
    assert d.action == 'fold'
    print(f"OK  test_pushfold_low_equity_fold (source={d.source})")


def test_postflop_strategy_top_action_bet():
    store = _FakeNodeStore()
    store.install()
    try:
        board = ['Ah', 'Kd', '3c']
        store.add(
            street='flop', position='BTN', board=board, hero_hand=[],
            stack_bb=50.0, facing=0.0,
            gto_action='bet', gto_freq=0.75,
            strategy_json=json.dumps({
                'bet':   {'frequency': 0.75, 'ev_bb': 1.20},
                'check': {'frequency': 0.25, 'ev_bb': 0.80},
            }),
        )
        d = decide(_di(street='flop', position='BTN', action='check', facing=0.0,
                       stack_bb=50.0, board=board, hero_cards=['Qs', 'Qd'],
                       equity=0.65))
        assert d.source == 'postflop_strategy'
        assert d.action == 'bet'
        assert d.opp_cost_bb is not None
        assert abs(d.opp_cost_bb - 0.40) < 1e-6
        print(f"OK  test_postflop_strategy_top_action_bet (opp_cost={d.opp_cost_bb})")
    finally:
        store.restore()


def test_postflop_strategy_mixed_includes_alts():
    store = _FakeNodeStore()
    store.install()
    try:
        board = ['9h', '7d', '6c']
        store.add(
            street='flop', position='BB', board=board, hero_hand=[],
            stack_bb=40.0, facing=2.0,
            gto_action='call', gto_freq=0.55,
            strategy_json=json.dumps({
                'call':  {'frequency': 0.55},
                'raise': {'frequency': 0.30},
                'fold':  {'frequency': 0.15},
            }),
        )
        d = decide(_di(street='flop', position='BB', action='raise', facing=2.0,
                       stack_bb=40.0, board=board, hero_cards=['8s', '8d']))
        assert d.source == 'postflop_strategy'
        assert d.action == 'call'
        assert 'raise' in d.alternatives  # >= 20% freq -> entra como alt
        print(f"OK  test_postflop_strategy_mixed_includes_alts (alts={d.alternatives})")
    finally:
        store.restore()


def test_postflop_top_action_only_fallback():
    store = _FakeNodeStore()
    store.install()
    try:
        board = ['Ts', '5d', '2c']
        store.add(
            street='flop', position='CO', board=board, hero_hand=[],
            stack_bb=30.0, facing=0.0,
            gto_action='bet', gto_freq=0.80,
            strategy_json=None,  # nó parcial -- só top action
        )
        d = decide(_di(street='flop', position='CO', action='check', facing=0.0,
                       stack_bb=30.0, board=board, hero_cards=['Jh', 'Tc']))
        assert d.source == 'postflop_top_action'
        assert d.action == 'bet'
        assert d.confidence == 'medium'
        print(f"OK  test_postflop_top_action_only_fallback (action={d.action})")
    finally:
        store.restore()


def test_postflop_no_node_falls_to_heuristic():
    # store vazio -> cai pra heurística potodds
    store = _FakeNodeStore()
    store.install()
    try:
        d = decide(_di(street='turn', position='CO', action='call', facing=4.0,
                       stack_bb=25.0, board=['As', 'Kd', '3c', '7h'],
                       hero_cards=['Ah', 'Tc'], equity=0.55, pot_odds=0.30))
        assert d.source == 'heuristic_potodds'
        assert d.action == 'call'
        print(f"OK  test_postflop_no_node_falls_to_heuristic (action={d.action})")
    finally:
        store.restore()


def test_postflop_heuristic_fold_when_no_equity_edge():
    store = _FakeNodeStore()
    store.install()
    try:
        d = decide(_di(street='river', position='UTG', action='call', facing=10.0,
                       stack_bb=20.0, board=['As', 'Kd', '3c', '7h', '9d'],
                       hero_cards=['7c', '4d'], equity=0.10, pot_odds=0.30))
        assert d.action == 'fold'
        assert d.source == 'heuristic_potodds'
        print("OK  test_postflop_heuristic_fold_when_no_equity_edge")
    finally:
        store.restore()


def test_unavailable_when_no_data():
    # Sem cartas, sem equity, sem pot odds, sem M-Ratio -> unavailable
    store = _FakeNodeStore()
    store.install()
    try:
        d = decide(_di(street='turn', position='UTG', action='fold', facing=3.0,
                       stack_bb=20.0, board=['As', 'Kd', '3c', '7h']))
        assert d.confidence == 'unavailable'
        assert d.source == 'unavailable'
        assert d.action is None
        print("OK  test_unavailable_when_no_data")
    finally:
        store.restore()


def test_strategy_corrupt_freq_sum_zero():
    store = _FakeNodeStore()
    store.install()
    try:
        board = ['2s', '3d', '4c']
        store.add(
            street='flop', position='BTN', board=board, hero_hand=[],
            stack_bb=40.0, facing=0.0,
            gto_action='bet', gto_freq=0.0,
            strategy_json=json.dumps({'bet': {'frequency': 0.001}}),  # soma < 0.10 -> corrupto
        )
        d = decide(_di(street='flop', position='BTN', action='check', facing=0.0,
                       stack_bb=40.0, board=board, hero_cards=['7c', '6c'],
                       equity=0.45))
        # Cai para postflop_top_action (gto_action='bet' freq=0) ou heurística -- não deve crashar
        assert d.action is not None or d.source == 'unavailable'
        print(f"OK  test_strategy_corrupt_freq_sum_zero (source={d.source})")
    finally:
        store.restore()


def test_opp_cost_none_when_played_action_outside_range():
    store = _FakeNodeStore()
    store.install()
    try:
        board = ['Qs', 'Js', '9d']
        store.add(
            street='flop', position='BTN', board=board, hero_hand=[],
            stack_bb=30.0, facing=0.0,
            gto_action='bet', gto_freq=1.0,
            strategy_json=json.dumps({'bet': {'frequency': 1.0, 'ev_bb': 2.0}}),
        )
        d = decide(_di(street='flop', position='BTN', action='check', facing=0.0,
                       stack_bb=30.0, board=board, hero_cards=['Ks', 'Kd'],
                       equity=0.80))
        assert d.action == 'bet'
        # 'check' not in strategy -> opp_cost_bb fica None (não inventamos)
        assert d.opp_cost_bb is None
        print("OK  test_opp_cost_none_when_played_action_outside_range")
    finally:
        store.restore()


def test_to_dict_shape():
    d = decide(_di(street='preflop', position='BB', action='check', facing=0.0,
                   hero_cards=['7s', '4s']))
    out = d.to_dict()
    for k in ('action', 'alternatives', 'confidence', 'source', 'justification',
              'opp_cost_bb', 'strategy_freqs'):
        assert k in out, f"chave {k} faltando em to_dict()"
    print("OK  test_to_dict_shape")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\nTotal: {passed + failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(0 if failed == 0 else 1)
