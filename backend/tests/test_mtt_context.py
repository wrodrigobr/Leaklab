"""
Testes do Sprint 2: contexto MTT real.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.models import ParsedHand, ParsedAction
from leaklab.mtt_context import build_mtt_context, context_to_dict, MTTContext
from leaklab.parser import parse_pokerstars_file
from leaklab.pipeline import build_decision_inputs_for_hand


# ── Helpers ───────────────────────────────────────────────────────────────────

def _raw(hero='phpro', sb=100, bb=200, ante=25, hero_stack=4000,
         players=8, level='X'):
    """Gera um raw_text mínimo de HH para testes."""
    seats = '\n'.join(
        f"Seat {i+1}: Player{i+1} (3000 in chips)" for i in range(players - 1)
    )
    seats += f"\nSeat {players}: {hero} ({hero_stack} in chips)"
    antes = '\n'.join(
        f"Player{i+1}: posts the ante {ante}" for i in range(players - 1)
    )
    antes += f"\n{hero}: posts the ante {ante}"
    return (
        f"PokerStars Hand #999: Tournament #123, $1+$0.10 Hold'em No Limit "
        f"- Level {level} ({sb}/{bb}) - 2025/01/01\n"
        f"Table '123 1' 9-max Seat #1 is the button\n"
        f"{seats}\n"
        f"{antes}\n"
        f"*** HOLE CARDS ***\n"
    )


def _make_hand(raw, hero='phpro'):
    return ParsedHand(
        hand_id='999', hero=hero, bb=200,
        hero_cards='AsJs', players=[hero],
        raw_text=raw, actions=[],
    )


# ── M Ratio ───────────────────────────────────────────────────────────────────

def test_m_ratio_calculation():
    # stack=4000, orbit = sb(100) + bb(200) + ante(25)*8 = 500
    raw = _raw(hero_stack=4000, sb=100, bb=200, ante=25, players=8)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.orbit_cost == 500.0
    assert ctx.m_ratio == 8.0
    print(f"OK  test_m_ratio_calculation (M={ctx.m_ratio})")


def test_m_ratio_no_ante():
    # orbit = sb(50) + bb(100) + 0 = 150
    raw = _raw(hero_stack=3000, sb=50, bb=100, ante=0, players=6)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.orbit_cost == 150.0
    assert ctx.m_ratio == 20.0
    print(f"OK  test_m_ratio_no_ante (M={ctx.m_ratio})")


def test_m_ratio_large_stack():
    raw = _raw(hero_stack=100000, sb=400, bb=800, ante=100, players=5)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.m_ratio is not None
    assert ctx.m_ratio > 20
    print(f"OK  test_m_ratio_large_stack (M={ctx.m_ratio})")


def test_hero_stack_in_bbs():
    raw = _raw(hero_stack=4000, sb=100, bb=200, ante=0, players=6)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.hero_stack_bb == 20.0
    print(f"OK  test_hero_stack_in_bbs ({ctx.hero_stack_bb} BBs)")


# ── Tournament stage ──────────────────────────────────────────────────────────

def test_stage_early():
    raw = _raw(players=9)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.tournament_stage == 'early'
    print(f"OK  test_stage_early ({ctx.active_players} players)")


def test_stage_middle():
    raw = _raw(players=6)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.tournament_stage == 'middle'
    print(f"OK  test_stage_middle ({ctx.active_players} players)")


def test_stage_late():
    raw = _raw(players=4)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.tournament_stage == 'late'
    print(f"OK  test_stage_late ({ctx.active_players} players)")


def test_stage_final_table():
    raw = _raw(players=3)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.tournament_stage == 'final_table'
    print(f"OK  test_stage_final_table ({ctx.active_players} players)")


def test_stage_heads_up():
    raw = _raw(players=2)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.tournament_stage == 'heads_up'
    print(f"OK  test_stage_heads_up ({ctx.active_players} players)")


# ── ICM pressure ──────────────────────────────────────────────────────────────

def test_icm_low_comfortable():
    # M=20, 9 players → low
    raw = _raw(hero_stack=10000, sb=100, bb=200, ante=25, players=9)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.icm_pressure == 'low', f"Expected low, got {ctx.icm_pressure} (M={ctx.m_ratio})"
    print(f"OK  test_icm_low_comfortable (M={ctx.m_ratio})")


def test_icm_medium_short():
    # orbit = 100+200+25*7=475, stack=3800 → M≈8 (entre 6 e 10) → medium
    raw = _raw(hero_stack=3800, sb=100, bb=200, ante=25, players=7)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.icm_pressure == 'medium', f"Expected medium, got {ctx.icm_pressure} (M={ctx.m_ratio})"
    print(f"OK  test_icm_medium_short (M={ctx.m_ratio})")


def test_icm_high_critical():
    # M ≤ 6 → high
    raw = _raw(hero_stack=800, sb=100, bb=200, ante=25, players=8)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.icm_pressure == 'high', f"Expected high, got {ctx.icm_pressure} (M={ctx.m_ratio})"
    print(f"OK  test_icm_high_critical (M={ctx.m_ratio})")


def test_icm_high_final_table():
    # Final table sempre high independente do M
    raw = _raw(hero_stack=50000, sb=100, bb=200, ante=25, players=3)
    ctx = build_mtt_context(_make_hand(raw))
    assert ctx.icm_pressure == 'high'
    print(f"OK  test_icm_high_final_table (M={ctx.m_ratio}, players=3)")


# ── context_to_dict ───────────────────────────────────────────────────────────

def test_context_to_dict_shape():
    raw = _raw(hero_stack=4000, sb=100, bb=200, ante=25, players=8)
    ctx = build_mtt_context(_make_hand(raw))
    d = context_to_dict(ctx)
    assert 'tournamentStage' in d
    assert 'icmPressure' in d
    assert 'mRatio' in d
    assert 'heroStackBb' in d
    assert 'activePlayers' in d
    assert d['icmPressure'] in {'low', 'medium', 'high'}
    print(f"OK  test_context_to_dict_shape | {d}")


# ── Integração com torneio real ───────────────────────────────────────────────

TOURNAMENT_FILE = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')


def test_mtt_context_on_real_tournament():
    from leaklab.parser import parse_pokerstars_file
    hands = parse_pokerstars_file(TOURNAMENT_FILE)
    errors = []
    contexts = []
    for hand in hands:
        try:
            ctx = build_mtt_context(hand)
            contexts.append(ctx)
        except Exception as e:
            errors.append((hand.hand_id, str(e)))

    assert len(errors) == 0, f"{len(errors)} erros: {errors[:3]}"
    assert len(contexts) == len(hands)

    # Verificar que M ratio foi calculado em todas as mãos
    with_m = [c for c in contexts if c.m_ratio is not None]
    assert len(with_m) > len(hands) * 0.9, "M ratio ausente em muitas mãos"

    # Verificar que ICM pressure variou (não está tudo 'low')
    pressures = set(c.icm_pressure for c in contexts)
    assert len(pressures) >= 2, f"ICM pressure não variou: {pressures}"

    print(f"OK  test_mtt_context_on_real_tournament")
    print(f"    M ratio: min={min(c.m_ratio for c in with_m):.1f} "
          f"max={max(c.m_ratio for c in with_m):.1f} "
          f"avg={sum(c.m_ratio for c in with_m)/len(with_m):.1f}")
    print(f"    ICM pressure dist: { {p: sum(1 for c in contexts if c.icm_pressure==p) for p in pressures} }")
    print(f"    Stages: { {s: sum(1 for c in contexts if c.tournament_stage==s) for s in set(c.tournament_stage for c in contexts)} }")


def test_pipeline_uses_mtt_context():
    """Verifica que o pipeline injeta ICM pressure real nos decision inputs."""
    from leaklab.parser import parse_pokerstars_file
    hands = parse_pokerstars_file(TOURNAMENT_FILE)

    # Pegar uma mão com stack curto (late game)
    all_inputs = []
    for hand in hands:
        inputs = build_decision_inputs_for_hand(hand)
        all_inputs.extend(inputs)

    # Verificar que icmPressure não é sempre 'low'
    pressures = set(i['context']['icmPressure'] for i in all_inputs)
    assert 'medium' in pressures or 'high' in pressures, \
        f"Pipeline não está usando MTT context real: {pressures}"
    print(f"OK  test_pipeline_uses_mtt_context | pressures encontradas: {pressures}")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
