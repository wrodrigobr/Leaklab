"""
Testes do Leak Trainer (motor) — geração de spot canônico, grading stateless e seleção adaptativa.
Funções puras (sem DB): a integração com get_leak_categories é coberta na suite database.
"""
import sys, os, random, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.leak_trainer import (
    _leak_scenario, _snap_stack, generate_canonical_spot, grade_canonical_spot,
    next_spot, _category_key, CORRECT_FREQ,
)


def test_scenario_mapping():
    assert _leak_scenario(0, 0) == 'rfi'
    assert _leak_scenario(0, 1) == 'vs_rfi'
    assert _leak_scenario(1, 0) == 'vs_3bet'
    assert _leak_scenario(0, 2) == 'vs_3bet'   # squeeze/2 raises = enfrenta 3-bet
    print("OK  test_scenario_mapping")


def test_snap_stack():
    assert _snap_stack(33) == 30
    assert _snap_stack(47) == 50
    assert _snap_stack(200) == 100   # cap no maior stack treinável
    print("OK  test_snap_stack")


def test_generate_canonical_spot_covered():
    """Garante cobertura: o spot gerado SEMPRE tem solução GTO (available) e o cenário bate.
    Nunca serve um spot que não consegue corrigir."""
    rng = random.Random(1)
    from leaklab.preflop_gto_ranges import analyze_preflop
    for pos in ['UTG', 'CO', 'BTN']:
        cat = {'scenario': 'rfi', 'position': pos, 'vs_position': '', 'stack_bb': 50,
               'weight': 1.0, 'key': f'rfi:{pos}::50'}
        ok = 0
        for _ in range(8):
            sp = generate_canonical_spot(cat, rng)
            assert sp is not None, f"sem spot coberto p/ {pos}"
            res = analyze_preflop(sp['position'], sp['hand'], float(sp['stack_bb']), 'fold',
                                  facing_size=sp['facing_size'], vs_position=sp['vs_position'],
                                  is_3bet_pot=sp['is_3bet_pot'])
            assert res.get('available'), "spot servido sem cobertura"
            assert res.get('scenario') == 'rfi'
            ok += 1
        assert ok == 8
    print("OK  test_generate_canonical_spot_covered")


def test_grade_fold_when_gto_folds():
    """O bug que motivou o redesign: foldar uma mão que o GTO folda 100% TEM que ser 'correto'."""
    g = grade_canonical_spot(
        {'position': 'UTG', 'hand': '72o', 'stack_bb': 50, 'facing_size': 0,
         'vs_position': '', 'is_3bet_pot': False}, 'fold')
    assert g['is_correct'] is True
    assert g['gto_tier'] == 'correct'
    assert g['gto_freq'] >= CORRECT_FREQ   # ~1.0 (GTO folda 72o UTG sempre)
    print(f"OK  test_grade_fold_when_gto_folds (freq={g['gto_freq']})")


def test_grade_raise_premium():
    g = grade_canonical_spot(
        {'position': 'UTG', 'hand': 'AA', 'stack_bb': 50, 'facing_size': 0,
         'vs_position': '', 'is_3bet_pot': False}, 'raise')
    assert g['is_correct'] is True
    assert g['gto_tier'] == 'correct'
    print("OK  test_grade_raise_premium")


def test_grade_dominated_action():
    """Abrir 72o de UTG é erro claro (GTO nunca abre)."""
    g = grade_canonical_spot(
        {'position': 'UTG', 'hand': '72o', 'stack_bb': 50, 'facing_size': 0,
         'vs_position': '', 'is_3bet_pot': False}, 'raise')
    assert g['is_correct'] is False
    assert g['gto_tier'] == 'error'
    print("OK  test_grade_dominated_action")


def test_grade_contract_keys():
    """O grade tem exatamente as chaves que o CoachCard lê (gto_strategy, gto_freq, gto_tier...)."""
    g = grade_canonical_spot(
        {'position': 'BTN', 'hand': 'A5s', 'stack_bb': 50, 'facing_size': 0,
         'vs_position': '', 'is_3bet_pot': False}, 'raise')
    for k in ('is_correct', 'gto_tier', 'gto_freq', 'gto_strategy', 'best_action', 'recommended'):
        assert k in g, f"falta chave {k}"
    assert isinstance(g['gto_strategy'], list)
    if g['gto_strategy']:
        assert set(g['gto_strategy'][0].keys()) == {'action', 'freq'}
    print("OK  test_grade_contract_keys")


def test_next_spot_adaptive():
    """Errar uma categoria aumenta o peso dela (super-representa o ponto fraco). RNG seedado."""
    curr = [
        {'scenario': 'rfi', 'position': 'UTG', 'vs_position': '', 'stack_bb': 50, 'weight': 1.0,
         'key': 'rfi:UTG::50'},
        {'scenario': 'rfi', 'position': 'BTN', 'vs_position': '', 'stack_bb': 50, 'weight': 1.0,
         'key': 'rfi:BTN::50'},
    ]
    # estado: errou UTG 3x → adapt UTG = 1 + 2*3 = 7; BTN = 1 → UTG ~7x mais provável
    state = {'rfi:UTG::50': {'hits': 0, 'misses': 3, 'seen': 3}}
    rng = random.Random(99)
    counts = {'rfi:UTG::50': 0, 'rfi:BTN::50': 0}
    for _ in range(60):
        sp = next_spot(curr, state, rng)
        assert sp is not None
        counts[sp['category']] += 1
    assert counts['rfi:UTG::50'] > counts['rfi:BTN::50'], counts
    print(f"OK  test_next_spot_adaptive ({counts})")


def test_next_spot_empty_curriculum():
    assert next_spot([], {}, random.Random(0)) is None
    print("OK  test_next_spot_empty_curriculum")


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
