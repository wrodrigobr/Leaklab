"""
test_gto_enrichment.py — Cobertura das funções de enrichment GTO do engine.

Cobre:
  - _validate_decision_input: warnings para stack/facing/board/position inválidos
  - _enrich_preflop_gto: KK correto, 72o fold, ausência de hero_hand/position
  - _enrich_gto: preflop rejeitado, hash lookup, nó sem strategy, strategy corrompida
  - _gto_classify_from_strategy: tiers (60%, 25-60%, 10-25%, <10%)
  - _preflop_gto_label_adjust: correct→standard, acceptable→cap marginal, leak→floor
  - score/label consistency em evaluate_decision()
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import (
    _validate_decision_input,
    _enrich_preflop_gto,
    _enrich_gto,
    _gto_classify_from_strategy,
    _preflop_gto_label_adjust,
)
from database.schema import get_conn

_PASSED = 0
_FAILED = 0


def _ok(name, cond, detail=''):
    global _PASSED, _FAILED
    if cond:
        _PASSED += 1
    else:
        _FAILED += 1
        print(f'  FAIL  {name}' + (f' — {detail}' if detail else ''))


# ── helpers ───────────────────────────────────────────────────────────────────

def _inp(street='flop', position='BTN', stack=30.0, facing=0.0, board=None,
         hero_cards=None, action='bet', is_3bet=False):
    """Monta input_data no formato do decision engine."""
    return {
        'street': street,
        'player_action': action,
        'hero_cards': hero_cards or [],
        'is_3bet': is_3bet,
        'spot': {
            'position': position,
            'effectiveStackBb': stack,
            'facingSize': facing,
            'board': board or ['Ks', 'Qd', '2c'],
        },
        'context': {},
        'math': {},
    }


def _insert_gto_node(conn, street, position, board_str, gto_action, gto_freq,
                     strategy_json=None, hero_hand=None, stack_bb=30.0, facing_bb=0.0):
    """Insere nó GTO sintético no banco em memória."""
    from leaklab.gto_utils import compute_spot_hash, stack_bucket
    board  = board_str.split() if isinstance(board_str, str) else board_str
    hand   = (hero_hand or '').split() if isinstance(hero_hand, str) else (hero_hand or [])
    h      = compute_spot_hash(street, position, board, hand, stack_bb, facing_bb)
    sj     = json.dumps(strategy_json) if isinstance(strategy_json, dict) else strategy_json
    sb     = stack_bucket(stack_bb)
    # Use exploitability_pct=5.0 so get_gto_node includes the node in results
    conn.execute(
        """INSERT OR IGNORE INTO gto_nodes
           (spot_hash, street, position, board, hero_hand, stack_bucket,
            gto_action, gto_freq, exploitability_pct, strategy_json, is_aggregate, source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (h, street, position, json.dumps(board), json.dumps(hand), sb,
         gto_action, gto_freq, 5.0, sj, 0, 'test')
    )
    conn.commit()
    return h


def _make_conn():
    """Cria banco SQLite em memória com schema completo."""
    from database.schema import _init_sqlite, _run_migrations
    import sqlite3
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    _init_sqlite(conn)
    _run_migrations(conn)
    return conn


# ── _validate_decision_input ──────────────────────────────────────────────────

def test_validate_valid_input():
    w = _validate_decision_input(_inp())
    _ok('validate_valid_no_warnings', w == [], f'{w}')


def test_validate_negative_stack():
    inp = _inp(stack=-5.0)
    w = _validate_decision_input(inp)
    _ok('validate_negative_stack', any('stack_bb' in s for s in w), f'{w}')


def test_validate_zero_stack():
    inp = _inp(stack=0.0)
    w = _validate_decision_input(inp)
    _ok('validate_zero_stack', any('stack_bb' in s for s in w), f'{w}')


def test_validate_nan_stack():
    import math
    inp = _inp(stack=math.nan)
    w = _validate_decision_input(inp)
    _ok('validate_nan_stack', any('stack_bb' in s for s in w), f'{w}')


def test_validate_negative_facing():
    inp = _inp(facing=-1.0)
    w = _validate_decision_input(inp)
    _ok('validate_negative_facing', any('facing_size' in s for s in w), f'{w}')


def test_validate_invalid_card_in_board():
    inp = _inp(board=['Ks', 'XX', '2c'])
    w = _validate_decision_input(inp)
    _ok('validate_invalid_card_board', any('card' in s for s in w), f'{w}')


def test_validate_short_card():
    inp = _inp(board=['K', 'Qd', '2c'])
    w = _validate_decision_input(inp)
    _ok('validate_short_card', any('card' in s for s in w), f'{w}')


def test_validate_unknown_position():
    inp = _inp(position='EP')
    w = _validate_decision_input(inp)
    _ok('validate_unknown_position', any('position' in s for s in w), f'{w}')


def test_validate_preflop_no_board_no_warning():
    inp = _inp(street='preflop', board=[])
    w = _validate_decision_input(inp)
    _ok('validate_preflop_no_board_ok', not any('card' in s for s in w), f'{w}')


def test_validate_none_stack_ignored():
    inp = _inp()
    inp['spot']['effectiveStackBb'] = None
    w = _validate_decision_input(inp)
    _ok('validate_none_stack_ignored', not any('stack_bb' in s for s in w), f'{w}')


# ── _enrich_preflop_gto ───────────────────────────────────────────────────────

def test_enrich_preflop_kk_hj_correct():
    """KK HJ ~27bb RFI deve retornar available=True, quality=correct."""
    inp = _inp(street='preflop', position='HJ', stack=27.0, facing=0.0,
               board=[], hero_cards=['Kc', 'Kd'], action='raise')
    result = _enrich_preflop_gto(inp)
    _ok('preflop_kk_hj_available',     result.get('available') is True, f'{result}')
    _ok('preflop_kk_hj_quality',       result.get('action_quality') in ('correct', 'acceptable'), f'{result}')
    _ok('preflop_kk_hj_rec_raise',     'raise' in (result.get('recommended_actions') or []), f'{result}')


def test_enrich_preflop_postflop_street_rejected():
    """Flop → _enrich_preflop_gto deve retornar available=False."""
    inp = _inp(street='flop')
    result = _enrich_preflop_gto(inp)
    _ok('preflop_flop_unavailable', result.get('available') is False, f'{result}')


def test_enrich_preflop_no_hero_cards():
    inp = _inp(street='preflop', board=[], hero_cards=[])
    result = _enrich_preflop_gto(inp)
    _ok('preflop_no_cards_unavailable', result.get('available') is False, f'{result}')


def test_enrich_preflop_invalid_position():
    """Posição inválida não deve levantar exceção — retorna available=False."""
    inp = _inp(street='preflop', position='INVALID', board=[], hero_cards=['Ac', 'Kd'], action='raise')
    result = _enrich_preflop_gto(inp)
    _ok('preflop_invalid_pos_unavailable', result.get('available') is False, f'{result}')


def test_enrich_preflop_returns_dict():
    inp = _inp(street='preflop', position='BTN', board=[], hero_cards=['Ac', 'Kd'], action='raise')
    result = _enrich_preflop_gto(inp)
    _ok('preflop_returns_dict', isinstance(result, dict), f'{type(result)}')


# ── _enrich_gto (postflop) ────────────────────────────────────────────────────

def test_enrich_gto_preflop_rejected():
    inp = _inp(street='preflop', board=[])
    result = _enrich_gto(inp)
    _ok('enrich_gto_preflop_unavailable', result.get('available') is False, f'{result}')


def test_enrich_gto_no_board():
    inp = _inp(board=[])
    result = _enrich_gto(inp)
    _ok('enrich_gto_no_board_unavailable', result.get('available') is False, f'{result}')


def test_enrich_gto_no_position():
    inp = _inp(position='')
    result = _enrich_gto(inp)
    _ok('enrich_gto_no_position_unavailable', result.get('available') is False, f'{result}')


def test_enrich_gto_node_not_in_db():
    """Sem nó no banco → available=False."""
    inp = _inp(position='CO', board=['2h', '3h', '4h'], stack=50.0)
    result = _enrich_gto(inp)
    _ok('enrich_gto_miss_unavailable', result.get('available') is False, f'{result}')


def test_enrich_gto_finds_node_by_hash():
    """Insere nó no banco e verifica que _enrich_gto o encontra pelo hash."""
    from leaklab.gto_utils import compute_spot_hash
    from database import repositories as repo

    # Substituir get_gto_node temporariamente usando banco em memória
    conn = _make_conn()
    board  = ['Ks', 'Qd', '2c']
    h      = _insert_gto_node(conn, 'flop', 'BTN', board, 'bet', 0.75, stack_bb=30.0)

    # Patch get_gto_node para usar nosso conn
    original = repo.get_gto_node
    def _patched(hash_val):
        row = conn.execute('SELECT * FROM gto_nodes WHERE spot_hash=?', (hash_val,)).fetchone()
        return dict(row) if row else None

    repo.get_gto_node = _patched
    try:
        inp = _inp(position='BTN', board=board, stack=30.0, action='bet')
        result = _enrich_gto(inp)
        _ok('enrich_gto_finds_node', result.get('available') is True, f'{result}')
        _ok('enrich_gto_top_action', result.get('gto_action') == 'bet', f'{result}')
    finally:
        repo.get_gto_node = original
        conn.close()


def test_enrich_gto_strategy_json_used():
    """Nó com strategy_json completo → strategy não vazia no resultado."""
    from leaklab.gto_utils import compute_spot_hash
    from database import repositories as repo

    conn = _make_conn()
    board    = ['As', 'Td', '5c']
    strategy = {
        'bet':   {'frequency': 0.65, 'ev_bb': 4.2},
        'check': {'frequency': 0.35, 'ev_bb': 3.8},
    }
    _insert_gto_node(conn, 'flop', 'BTN', board, 'bet', 0.65, strategy_json=strategy, stack_bb=25.0)

    original = repo.get_gto_node
    def _patched(hash_val):
        row = conn.execute('SELECT * FROM gto_nodes WHERE spot_hash=?', (hash_val,)).fetchone()
        return dict(row) if row else None

    repo.get_gto_node = _patched
    try:
        inp = _inp(position='BTN', board=board, stack=25.0, action='bet')
        result = _enrich_gto(inp)
        _ok('enrich_gto_strategy_populated', len(result.get('strategy', [])) > 0, f'{result}')
        _ok('enrich_gto_strategy_sorted',
            result['strategy'][0]['frequency'] >= result['strategy'][-1]['frequency'],
            f'{result["strategy"]}')
    finally:
        repo.get_gto_node = original
        conn.close()


def test_enrich_gto_corrupted_strategy_rejected():
    """strategy_json com freq_sum < 0.10 deve ser descartado → available=False."""
    from database import repositories as repo

    conn = _make_conn()
    board    = ['7h', '8h', '9h']
    strategy = {
        'bet':   {'frequency': 0.01, 'ev_bb': 1.0},
        'check': {'frequency': 0.02, 'ev_bb': 0.9},
    }  # freq_sum = 0.03 < 0.10
    _insert_gto_node(conn, 'flop', 'CO', board, 'bet', 0.01, strategy_json=strategy, stack_bb=20.0)

    original = repo.get_gto_node
    def _patched(hash_val):
        row = conn.execute('SELECT * FROM gto_nodes WHERE spot_hash=?', (hash_val,)).fetchone()
        return dict(row) if row else None

    repo.get_gto_node = _patched
    try:
        inp = _inp(position='CO', board=board, stack=20.0, action='bet')
        result = _enrich_gto(inp)
        _ok('enrich_gto_corrupt_strategy_discarded',
            result.get('available') is False or result.get('strategy') == [],
            f'{result}')
    finally:
        repo.get_gto_node = original
        conn.close()


# ── _gto_classify_from_strategy ───────────────────────────────────────────────

def _strat(bet_freq, check_freq, bet_ev=None, check_ev=None):
    s = [
        {'action': 'bet',   'frequency': bet_freq,   'ev_bb': bet_ev},
        {'action': 'check', 'frequency': check_freq, 'ev_bb': check_ev},
    ]
    s.sort(key=lambda x: x['frequency'], reverse=True)
    return s


def test_classify_tier1_correct():
    """Frequência ≥ 0.60 → gto_correct."""
    label, freq = _gto_classify_from_strategy('bet', _strat(0.70, 0.30))
    _ok('classify_tier1_correct', label == 'gto_correct', f'{label}, freq={freq}')


def test_classify_tier2_mixed_high():
    """Frequência ≥ 0.25 e < 0.60 → gto_mixed."""
    label, freq = _gto_classify_from_strategy('bet', _strat(0.40, 0.60))
    _ok('classify_tier2_mixed', label == 'gto_mixed', f'{label}, freq={freq}')


def test_classify_tier3_low_freq_low_ev():
    """Frequência ≥ 0.10 e ev_diff < 0.15 → gto_mixed (ruído de misto)."""
    label, _ = _gto_classify_from_strategy(
        'bet', _strat(0.15, 0.85, bet_ev=3.90, check_ev=4.00)
    )  # ev_diff = 4.00 - 3.90 = 0.10 < 0.15
    _ok('classify_tier3_low_ev_mixed', label == 'gto_mixed', f'{label}')


def test_classify_tier3_low_freq_high_ev():
    """Frequência ≥ 0.10 e ev_diff ≥ 0.15 → gto_minor_deviation."""
    label, _ = _gto_classify_from_strategy(
        'bet', _strat(0.12, 0.88, bet_ev=3.70, check_ev=4.00)
    )  # ev_diff = 0.30 ≥ 0.15
    _ok('classify_tier3_high_ev_minor', label == 'gto_minor_deviation', f'{label}')


def test_classify_tier4_critical():
    """Frequência < 0.10 e ev_diff ≥ 0.30 → gto_critical."""
    label, _ = _gto_classify_from_strategy(
        'bet', _strat(0.05, 0.95, bet_ev=3.50, check_ev=4.00)
    )  # ev_diff = 0.50 ≥ 0.30
    _ok('classify_tier4_critical', label == 'gto_critical', f'{label}')


def test_classify_tier4_minor_low_ev():
    """Frequência < 0.10 e ev_diff < 0.30 → gto_minor_deviation."""
    label, _ = _gto_classify_from_strategy(
        'bet', _strat(0.05, 0.95, bet_ev=3.80, check_ev=4.00)
    )  # ev_diff = 0.20 < 0.30
    _ok('classify_tier4_minor_low_ev', label == 'gto_minor_deviation', f'{label}')


def test_classify_empty_strategy():
    """Strategy vazia → gto_critical (sem informação disponível)."""
    label, freq = _gto_classify_from_strategy('bet', [])
    _ok('classify_empty_strategy_critical', label == 'gto_critical', f'{label}')
    _ok('classify_empty_strategy_freq_zero', freq == 0.0, f'{freq}')


def test_classify_action_norm_jam_shove():
    """Alias shove deve ser reconhecido como jam."""
    s = [
        {'action': 'jam',   'frequency': 0.80, 'ev_bb': 5.0},
        {'action': 'fold',  'frequency': 0.20, 'ev_bb': 0.0},
    ]
    label, freq = _gto_classify_from_strategy('shove', s)
    _ok('classify_shove_matches_jam', label == 'gto_correct', f'{label}, freq={freq}')


def test_classify_played_freq_returned():
    """Retorna frequência correta da ação jogada."""
    s = _strat(0.65, 0.35)
    _, freq = _gto_classify_from_strategy('bet', s)
    _ok('classify_played_freq_value', abs(freq - 0.65) < 0.01, f'{freq}')


# ── _preflop_gto_label_adjust ─────────────────────────────────────────────────

def test_label_adjust_correct_always_standard():
    for label in ('standard', 'marginal', 'small_mistake', 'clear_mistake'):
        result = _preflop_gto_label_adjust(label, 'correct')
        _ok(f'adjust_correct_{label}→standard', result == 'standard', f'{result}')


def test_label_adjust_acceptable_caps_at_marginal():
    _ok('adjust_acceptable_standard',     _preflop_gto_label_adjust('standard',      'acceptable') == 'standard')
    _ok('adjust_acceptable_marginal',     _preflop_gto_label_adjust('marginal',       'acceptable') == 'marginal')
    _ok('adjust_acceptable_small_mistake',_preflop_gto_label_adjust('small_mistake', 'acceptable') == 'marginal')
    _ok('adjust_acceptable_clear_mistake',_preflop_gto_label_adjust('clear_mistake', 'acceptable') == 'marginal')


def test_label_adjust_leak_floors_at_small_mistake():
    _ok('adjust_leak_standard_floor', _preflop_gto_label_adjust('standard', 'leak') == 'small_mistake')
    _ok('adjust_leak_marginal_floor', _preflop_gto_label_adjust('marginal',  'leak') == 'small_mistake')
    _ok('adjust_leak_small_keeps',    _preflop_gto_label_adjust('small_mistake', 'leak') == 'small_mistake')
    _ok('adjust_leak_clear_keeps',    _preflop_gto_label_adjust('clear_mistake', 'leak') == 'clear_mistake')


def test_label_adjust_unknown_quality_passthrough():
    result = _preflop_gto_label_adjust('marginal', 'unknown_quality')
    _ok('adjust_unknown_passthrough', result == 'marginal', f'{result}')


# ── Score/label consistency ───────────────────────────────────────────────────

def test_score_label_thresholds():
    """Verifica que as constantes do engine batem com os thresholds esperados."""
    from leaklab.decision_engine_v11 import decision_engine_config
    cfg = decision_engine_config.get('labels', {})
    _ok('standard_max_008',  abs(cfg.get('standardMax', 0) - 0.08) < 0.001,
        f'standardMax={cfg.get("standardMax")}')
    _ok('marginal_max_018',  abs(cfg.get('marginalMax', 0) - 0.18) < 0.001,
        f'marginalMax={cfg.get("marginalMax")}')


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        fn()
    print(f'\nTotal: {_PASSED + _FAILED} | Passed: {_PASSED} | Failed: {_FAILED}')
    return _FAILED


if __name__ == '__main__':
    failed = run_all()
    sys.exit(1 if failed else 0)
