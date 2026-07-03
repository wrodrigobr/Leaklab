"""
test_gto_utils_comprehensive.py — Cobertura completa de leaklab/gto_utils.py

Cobre:
  - compute_spot_hash: determinismo, variação, normalização, BET_BUCKET, STACK_BUCKET
  - hand_to_type: todos os casos incluindo inválidos
  - expand_range_notation: pares, conectores, ranges
  - normalize_gto_action: normalização e canônico
  - stack_bucket / bet_bucket: boundaries
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.gto_utils import (
    compute_spot_hash,
    hand_to_type,
    expand_range_notation,
    normalize_gto_action,
    stack_bucket,
    bet_bucket,
    VALID_POSITIONS,
    VALID_GTO_ACTIONS,
)

_PASSED = 0
_FAILED = 0


def _ok(name, cond, detail=''):
    global _PASSED, _FAILED
    if cond:
        _PASSED += 1
    else:
        _FAILED += 1
        print(f'  FAIL  {name}' + (f' — {detail}' if detail else ''))


# ── compute_spot_hash ─────────────────────────────────────────────────────────

def test_hash_deterministic():
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], ['As', 'Kd'], 25.0, 5.0)
    h2 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], ['As', 'Kd'], 25.0, 5.0)
    _ok('hash_deterministic', h1 == h2, f'{h1} != {h2}')

def test_hash_varies_by_street():
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    h2 = compute_spot_hash('turn', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    _ok('hash_varies_street', h1 != h2)

def test_hash_pot_type_backward_compat():
    # Fase 2: pot_type ''/'srp' NÃO muda o hash (backward-compat); '3bet' muda (sem colisão).
    base = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], ['As', 'Kd'], 25.0, 5.0)
    same_empty = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], ['As', 'Kd'], 25.0, 5.0, '')
    same_srp   = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], ['As', 'Kd'], 25.0, 5.0, 'srp')
    diff_3bet  = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], ['As', 'Kd'], 25.0, 5.0, '3bet')
    _ok('hash_pot_type_backward_compat',
        base == same_empty and base == same_srp and base != diff_3bet,
        f'base={base} empty={same_empty} srp={same_srp} 3bet={diff_3bet}')

def test_hash_varies_by_position():
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    h2 = compute_spot_hash('flop', 'CO',  ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    _ok('hash_varies_position', h1 != h2)

def test_hash_varies_by_board():
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    h2 = compute_spot_hash('flop', 'BTN', ['As', 'Qd', '2c'], [], 25.0, 0.0)
    _ok('hash_varies_board', h1 != h2)

def test_hash_varies_by_facing_size():
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    h2 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 5.0)
    _ok('hash_varies_facing', h1 != h2)

def test_hash_hand_order_normalized():
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], ['As', 'Kd'], 25.0, 0.0)
    h2 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], ['Kd', 'As'], 25.0, 0.0)
    _ok('hash_hand_order_normalized', h1 == h2)

def test_hash_board_order_normalized():
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    h2 = compute_spot_hash('flop', 'BTN', ['2c', 'Ks', 'Qd'], [], 25.0, 0.0)
    _ok('hash_board_order_normalized', h1 == h2)

def test_hash_preflop_empty_board():
    h1 = compute_spot_hash('preflop', 'HJ', [], ['Kc', 'Kd'], 27.0, 0.0)
    h2 = compute_spot_hash('preflop', 'HJ', [], ['Kd', 'Kc'], 27.0, 0.0)
    _ok('hash_preflop_empty_board', h1 == h2)

def test_hash_street_case_insensitive():
    h1 = compute_spot_hash('Flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    h2 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    _ok('hash_street_lowercase', h1 == h2)

def test_hash_position_case_insensitive():
    h1 = compute_spot_hash('flop', 'btn', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    h2 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    _ok('hash_position_uppercase', h1 == h2)

def test_hash_facing_zero_vs_tiny():
    # 0.0 → 'no_bet', 0.001 → '0-3bb': different buckets → different hashes
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    h2 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.001)
    _ok('hash_facing_zero_vs_tiny_same_bucket', h1 != h2)

def test_hash_facing_bucket_boundary_3bb():
    # 3.0bb is 0-3bb, 3.01bb is 3-8bb
    h1 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 3.0)
    h2 = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 3.01)
    _ok('hash_facing_3bb_boundary', h1 != h2)

def test_hash_length_16():
    h = compute_spot_hash('flop', 'BTN', ['Ks', 'Qd', '2c'], [], 25.0, 0.0)
    _ok('hash_length_16', len(h) == 16, f'len={len(h)}')


# ── stack_bucket ──────────────────────────────────────────────────────────────

def test_stack_bucket_boundaries():
    cases = [
        (9.99,  '0-10bb'),
        (10.0,  '10-20bb'),
        (10.01, '10-20bb'),
        (19.99, '10-20bb'),
        (20.0,  '20-35bb'),
        (34.99, '20-35bb'),
        (35.0,  '35-60bb'),
        (59.99, '35-60bb'),
        (60.0,  '60-100bb'),
        (99.99, '60-100bb'),
        # Cap implícito 100bb desde 2026-05-26 — stacks >= 60bb usam mesmo bucket
        # pra evitar bucket '100bb+' isolado com poucos nós solver pre-computados.
        (100.0, '60-100bb'),
        (200.0, '60-100bb'),
    ]
    for bb, expected in cases:
        result = stack_bucket(bb)
        _ok(f'stack_bucket_{bb}bb', result == expected, f'{result!r} != {expected!r}')


# ── bet_bucket ────────────────────────────────────────────────────────────────

def test_bet_bucket_boundaries():
    cases = [
        (0.0,   'no_bet'),
        (0.001, '0-3bb'),
        (2.99,  '0-3bb'),
        (3.0,   '0-3bb'),
        (3.01,  '3-8bb'),
        (7.99,  '3-8bb'),
        (8.0,   '3-8bb'),
        (8.01,  '8-20bb'),
        (19.99, '8-20bb'),
        (20.0,  '8-20bb'),
        (20.01, '20-40bb'),
        (39.99, '20-40bb'),
        (40.0,  '20-40bb'),
        (40.01, '40bb+'),
        (100.0, '40bb+'),
    ]
    for bb, expected in cases:
        result = bet_bucket(bb)
        _ok(f'bet_bucket_{bb}bb', result == expected, f'{result!r} != {expected!r}')

def test_bet_bucket_negative():
    result = bet_bucket(-1.0)
    _ok('bet_bucket_negative', result == 'no_bet', f'{result!r}')


# ── hand_to_type ──────────────────────────────────────────────────────────────

def test_hand_to_type_pair():
    _ok('hand_pair_KcKd', hand_to_type(['Kc', 'Kd']) == 'KK')
    _ok('hand_pair_AcAd', hand_to_type(['Ac', 'Ad']) == 'AA')
    _ok('hand_pair_22',   hand_to_type(['2c', '2d']) == '22')

def test_hand_to_type_suited():
    _ok('hand_suited_AKs', hand_to_type(['Ac', 'Kc']) == 'AKs')
    _ok('hand_suited_T9s', hand_to_type(['Th', 'Jh']) == 'JTs')

def test_hand_to_type_offsuit():
    _ok('hand_offsuit_AKo', hand_to_type(['Ac', 'Kd']) == 'AKo')
    _ok('hand_offsuit_KAo', hand_to_type(['Kd', 'Ac']) == 'AKo')

def test_hand_to_type_high_rank_first():
    result = hand_to_type(['2c', 'As'])
    _ok('hand_high_rank_first', result == 'A2o', f'{result!r}')

def test_hand_to_type_reversed_order():
    h1 = hand_to_type(['As', 'Ks'])
    h2 = hand_to_type(['Ks', 'As'])
    _ok('hand_reversed_order', h1 == h2 == 'AKs')

def test_hand_to_type_invalid_empty():
    _ok('hand_empty_list',  hand_to_type([]) is None)
    _ok('hand_single_card', hand_to_type(['Ac']) is None)
    _ok('hand_none',        hand_to_type(None) is None)

def test_hand_to_type_invalid_card():
    _ok('hand_short_card', hand_to_type(['A', 'Kc']) is None)


# ── expand_range_notation ─────────────────────────────────────────────────────

def test_expand_single_pair():
    result = expand_range_notation('AA')
    _ok('expand_AA', result == ['AA'], f'{result}')

def test_expand_pair_plus():
    result = expand_range_notation('TT+')
    expected = ['TT', 'JJ', 'QQ', 'KK', 'AA']
    _ok('expand_TT+', sorted(result) == sorted(expected), f'{result}')

def test_expand_suited_plus():
    result = expand_range_notation('ATs+')
    expected = ['ATs', 'AJs', 'AQs', 'AKs']
    _ok('expand_ATs+', sorted(result) == sorted(expected), f'{result}')

def test_expand_offsuit_plus():
    result = expand_range_notation('ATo+')
    expected = ['ATo', 'AJo', 'AQo', 'AKo']
    _ok('expand_ATo+', sorted(result) == sorted(expected), f'{result}')

def test_expand_range_hyphen():
    result = expand_range_notation('ATs-AJs')
    _ok('expand_ATs-AJs', 'ATs' in result and 'AJs' in result, f'{result}')

def test_expand_empty_returns_empty():
    result = expand_range_notation('')
    _ok('expand_empty', result == [], f'{result}')

def test_expand_pair_aa_only():
    result = expand_range_notation('AA+')
    _ok('expand_AA+', result == ['AA'], f'{result}')


# ── normalize_gto_action ──────────────────────────────────────────────────────

def test_normalize_shove_to_jam():
    _ok('norm_shove',   normalize_gto_action('shove') == 'jam')
    _ok('norm_allin',   normalize_gto_action('allin') == 'jam')
    _ok('norm_all-in',  normalize_gto_action('all-in') == 'jam')
    _ok('norm_all_in',  normalize_gto_action('all_in') == 'jam')
    _ok('norm_all in',  normalize_gto_action('all in') == 'jam')

def test_normalize_valid_unchanged():
    for act in ('fold', 'check', 'call', 'bet', 'raise', 'jam'):
        _ok(f'norm_{act}_unchanged', normalize_gto_action(act) == act)

def test_normalize_case_insensitive():
    _ok('norm_FOLD', normalize_gto_action('FOLD') == 'fold')
    _ok('norm_Raise', normalize_gto_action('Raise') == 'raise')
    _ok('norm_SHOVE', normalize_gto_action('SHOVE') == 'jam')

def test_normalize_whitespace_stripped():
    _ok('norm_whitespace', normalize_gto_action(' raise ') == 'raise')
    _ok('norm_empty', normalize_gto_action('') == '')
    _ok('norm_none', normalize_gto_action(None) == '')


# ── VALID_POSITIONS / VALID_GTO_ACTIONS ──────────────────────────────────────

def test_valid_positions_set():
    for pos in ('UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB'):
        _ok(f'valid_pos_{pos}', pos in VALID_POSITIONS)
    _ok('invalid_pos_Button', 'Button' not in VALID_POSITIONS)
    _ok('invalid_pos_EP', 'EP' not in VALID_POSITIONS)

def test_valid_gto_actions_set():
    for act in ('fold', 'check', 'call', 'bet', 'raise', 'jam'):
        _ok(f'valid_action_{act}', act in VALID_GTO_ACTIONS)


def test_normalize_position_fullring():
    """MP1/MP2/MP → canônico (LJ/HJ/LJ) — spots que eram REJEITADOS no insert do nó."""
    from leaklab.gto_utils import normalize_position, compute_spot_hash
    _ok('mp1_to_lj', normalize_position('MP1') == 'LJ')
    _ok('mp2_to_hj', normalize_position('MP2') == 'HJ')
    _ok('mp_to_lj',  normalize_position('MP') == 'LJ')
    _ok('mp1_lower', normalize_position(' mp1 ') == 'LJ')       # case/trim
    _ok('co_unchanged', normalize_position('CO') == 'CO')       # canônico não muda
    _ok('lj_unchanged', normalize_position('LJ') == 'LJ')
    # invariante-chave: MP1 e LJ produzem o MESMO spot_hash (enqueue ↔ lookup da decisão)
    h_mp1 = compute_spot_hash('flop', 'MP1', ['9h', 'Ac', '5h'], ['Ah', 'Kd'], 20.0, 0.0)
    h_lj  = compute_spot_hash('flop', 'LJ',  ['9h', 'Ac', '5h'], ['Ah', 'Kd'], 20.0, 0.0)
    _ok('mp1_lj_same_hash', h_mp1 == h_lj)


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
