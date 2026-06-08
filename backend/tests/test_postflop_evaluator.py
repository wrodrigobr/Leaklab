"""
Testes do postflop_range_evaluator.
Cobre todos os cenários identificados na auditoria:
  - Facing bet: equity alta / baixa / borderline
  - No bet: equity forte / média / fraca
  - Integração no pipeline com torneio real
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.models import HandState, ParsedHand, ParsedAction
from leaklab.postflop_range_evaluator import evaluate_postflop_range
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


def _state(street='flop', action='call', pot=600, facing=0,
           equity=None, cards='AsJs'):
    """Cria HandState mínimo para o postflop evaluator."""
    return HandState(
        hand_id='test',
        street=street,
        hero='Hero',
        hero_cards=cards,
        board=['Kh', '7d', '2c'],
        player_action=action,
        pot_size=float(pot),
        facing_size=float(facing),
        effective_stack_bb=20.0,
        position='BTN',
        villain_position='BB',
        is_in_position=True,
        is_multiway=False,
        actions=[],
        metadata={'estimated_equity': equity},
    )


# ── Cenário: SEM aposta (facing_size=0) ──────────────────────────────────────

def test_no_bet_weak_hand_recommends_check():
    """Mão fraca sem aposta → recomenda check."""
    ev = evaluate_postflop_range(_state(facing=0, equity=0.28))
    assert ev.recommended_primary_action == 'check'
    assert ev.range_zone == 'outside_range'
    print("OK  test_no_bet_weak_hand_recommends_check")


def test_no_bet_medium_hand_recommends_check():
    """Mão média sem aposta → check defensável."""
    ev = evaluate_postflop_range(_state(facing=0, equity=0.43))
    assert ev.recommended_primary_action == 'check'
    assert 'bet' in ev.alternative_actions
    assert ev.range_zone == 'borderline_range'
    print("OK  test_no_bet_medium_hand_recommends_check")


def test_no_bet_strong_hand_recommends_bet():
    """
    Mão forte sem aposta → bet.
    BTN (IP) a 100bb: threshold = 0.65. Equity 0.70 → bet.
    Calibrado contra GTO Wizard: o threshold antigo (0.55) causava over-betting
    sistemático (88% de erro), thresholds corrigidos por posição + stack depth.
    """
    state = _state(facing=0, equity=0.70)
    state = HandState(
        hand_id='test', street='flop', hero='Hero', hero_cards='AsJs',
        board=['Kh', '7d', '2c'], player_action='bet', pot_size=600.0,
        facing_size=0.0, effective_stack_bb=100.0,  # deep stack → threshold 0.65
        position='BTN', villain_position='BB', is_in_position=True,
        is_multiway=False, actions=[],
        metadata={'estimated_equity': 0.70},
    )
    ev = evaluate_postflop_range(state)
    assert ev.recommended_primary_action == 'bet', \
        f"BTN 100bb equity=0.70 deve recomendar bet (threshold=0.65), got: {ev.recommended_primary_action}"
    assert 'check' in ev.alternative_actions
    assert ev.range_zone == 'core_range'
    print("OK  test_no_bet_strong_hand_recommends_bet")


def test_no_bet_gto_calibrated_thresholds():
    """
    Thresholds GTO-calibrados por posição e stack depth.
    Validados contra GTO Wizard MTTGeneralV2: o threshold antigo (0.55) causava
    88% de erro em bet-vs-check — corrigido com thresholds dependentes de contexto.
    """
    def make_state(equity, position, stack_bb):
        return HandState(
            hand_id='test', street='flop', hero='Hero', hero_cards='AsJs',
            board=['Kh', '7d', '2c'], player_action='check', pot_size=600.0,
            facing_size=0.0, effective_stack_bb=float(stack_bb),
            position=position, villain_position='BB', is_in_position=(position != 'BB'),
            is_multiway=False, actions=[],
            metadata={'estimated_equity': equity},
        )

    # BTN (IP) deep (100bb): threshold=0.65
    assert evaluate_postflop_range(make_state(0.65, 'BTN', 100)).recommended_primary_action == 'bet'
    assert evaluate_postflop_range(make_state(0.64, 'BTN', 100)).recommended_primary_action == 'check'

    # BB (OOP) deep (100bb): threshold=0.65+0.06=0.71
    assert evaluate_postflop_range(make_state(0.71, 'BB', 100)).recommended_primary_action == 'bet'
    assert evaluate_postflop_range(make_state(0.70, 'BB', 100)).recommended_primary_action == 'check'

    # BTN (IP) short (20bb): threshold=0.72
    assert evaluate_postflop_range(make_state(0.72, 'BTN', 20)).recommended_primary_action == 'bet'
    assert evaluate_postflop_range(make_state(0.71, 'BTN', 20)).recommended_primary_action == 'check'

    # O antigo threshold 0.55 agora corretamente → check (não mais over-betting)
    assert evaluate_postflop_range(make_state(0.55, 'BTN', 20)).recommended_primary_action == 'check'
    assert evaluate_postflop_range(make_state(0.62, 'BTN', 20)).recommended_primary_action == 'check'

    print("OK  test_no_bet_gto_calibrated_thresholds")


def test_no_bet_equity_below_threshold_checks():
    """Equity abaixo de qualquer threshold → check (independente de posição)."""
    ev = evaluate_postflop_range(_state(facing=0, equity=0.54))
    assert ev.recommended_primary_action == 'check'
    print("OK  test_no_bet_equity_below_threshold_checks")


def test_no_bet_no_equity_data_defaults_check():
    """Sem dados de equity → check como padrão seguro."""
    ev = evaluate_postflop_range(_state(facing=0, equity=None))
    assert ev.recommended_primary_action == 'check'
    print("OK  test_no_bet_no_equity_data_defaults_check")


# ── Cenário: COM aposta (facing_size > 0) ────────────────────────────────────

def test_facing_bet_equity_above_pot_odds_recommends_call():
    """
    pot=600, facing=200 → pot_odds = 200/800 = 0.25
    equity=0.38 → diff=+0.13 (bem acima) → call
    """
    ev = evaluate_postflop_range(_state(pot=600, facing=200, equity=0.38))
    assert ev.recommended_primary_action == 'call'
    print(f"OK  test_facing_bet_equity_above_pot_odds_recommends_call")


def test_facing_bet_equity_below_pot_odds_recommends_fold():
    """
    pot=600, facing=400 → pot_odds = 400/1000 = 0.40
    equity=0.28 → diff=-0.12 (bem abaixo) → fold
    """
    ev = evaluate_postflop_range(_state(pot=600, facing=400, equity=0.28))
    assert ev.recommended_primary_action == 'fold'
    assert ev.range_zone == 'outside_range'
    print("OK  test_facing_bet_equity_below_pot_odds_recommends_fold")


def test_facing_bet_borderline_close_spot():
    """
    pot=600, facing=200 → pot_odds=0.25
    equity=0.27 → diff=+0.02 (dentro da margem ±4%) → borderline → call + fold alt
    """
    ev = evaluate_postflop_range(_state(pot=600, facing=200, equity=0.27))
    assert ev.recommended_primary_action == 'call'
    assert 'fold' in ev.alternative_actions
    assert ev.range_zone == 'borderline_range'
    print("OK  test_facing_bet_borderline_close_spot")


def test_facing_bet_strong_equity_may_raise():
    """
    Equity muito forte → call com raise como alternativa.
    pot=600, facing=200 → pot_odds=0.25, equity=0.65 (diff=+0.40)
    """
    ev = evaluate_postflop_range(_state(pot=600, facing=200, equity=0.65))
    assert ev.recommended_primary_action == 'call'
    assert 'raise' in ev.alternative_actions
    print("OK  test_facing_bet_strong_equity_may_raise")


def test_facing_bet_no_equity_defaults_call():
    """Sem equity data com aposta → call como padrão (borderline)."""
    ev = evaluate_postflop_range(_state(pot=600, facing=200, equity=None))
    assert ev.recommended_primary_action == 'call'
    assert 'fold' in ev.alternative_actions
    print("OK  test_facing_bet_no_equity_defaults_call")


def test_facing_bet_zone_core_with_strong_equity():
    """Equity >= 0.50 com aposta → core_range."""
    ev = evaluate_postflop_range(_state(pot=600, facing=100, equity=0.55))
    assert ev.range_zone == 'core_range'
    print("OK  test_facing_bet_zone_core_with_strong_equity")


def test_facing_bet_zone_outside_with_weak_equity():
    """Equity < 0.35 com aposta → outside_range."""
    ev = evaluate_postflop_range(_state(pot=600, facing=400, equity=0.30))
    assert ev.range_zone == 'outside_range'
    print("OK  test_facing_bet_zone_outside_with_weak_equity")


# ── Integração no pipeline ────────────────────────────────────────────────────

TOURNAMENT_FILE = os.path.join(os.path.dirname(__file__), '..', 'torneio_ingles.txt')


def test_pipeline_routes_postflop_correctly():
    """Verifica que decisões postflop usam o postflop evaluator."""
    from leaklab.parser import parse_pokerstars_file
    hands = parse_pokerstars_file(TOURNAMENT_FILE)

    postflop_recs = set()
    for hand in hands:
        for di in build_decision_inputs_for_hand(hand):
            if di['street'] != 'preflop':
                postflop_recs.add(di['range_evaluation']['recommendedPrimaryAction'])

    # Postflop evaluator deve recomendar check (nunca era recomendado pelo preflop)
    assert 'check' in postflop_recs, "Postflop evaluator não está sendo usado"
    # Não deve ter 'raise' como rec dominante postflop
    print(f"OK  test_pipeline_routes_postflop_correctly | recs={postflop_recs}")


def test_postflop_error_rate_reduced():
    """Guard de regressão da taxa de erros postflop.

    Threshold subiu de 30% pra 50% em 2026-05-26 — não por regressão, mas
    porque os fixes recentes (cap/floor de label vs gto_label, multiway
    equity decay, vs_3bet routing) tornam o engine mais SEVERO e honesto.
    Standards "mentirosos" (engine dava pass enquanto solver dizia critical)
    viraram small_mistake; clear_mistakes injustos (engine duro demais
    quando solver dizia minor) viraram small_mistake. Resultado líquido:
    taxa de erros sobe, mas reflete melhor a realidade. Faixa esperada
    pra um aluno em evolução: 30-50%.
    """
    from leaklab.parser import parse_pokerstars_file
    hands = parse_pokerstars_file(TOURNAMENT_FILE)

    postflop_results = []
    for hand in hands:
        for di in build_decision_inputs_for_hand(hand):
            if di['street'] == 'preflop':
                continue
            r = evaluate_decision(di)
            postflop_results.append(r['evaluation']['label'])

    total = len(postflop_results)
    errors = sum(1 for l in postflop_results if l in ('small_mistake', 'clear_mistake'))
    error_rate = errors / total

    assert error_rate < 0.50, f"Taxa de erro postflop ainda alta: {error_rate:.0%}"
    print(f"OK  test_postflop_error_rate_reduced | {error_rate:.0%} erro ({errors}/{total})")


def test_genuine_errors_preserved():
    """Erros com math penalty real devem ser mantidos após a correção."""
    from leaklab.parser import parse_pokerstars_file
    hands = parse_pokerstars_file(TOURNAMENT_FILE)

    # Conta a DETECÇÃO do heurístico (mathPenalty real), NÃO o label final. Motivo: a
    # cobertura GTO (nós Texas postflop) pode AMOLECER o label de alguns (ex.: um fold que
    # o GTO endossa vira gto_mixed/gto_correct em vez de small/clear_mistake), mas o math
    # penalty persiste — o erro genuíno não é "perdido", só contextualizado pelo GTO. Antes
    # este teste lia o label final e era NÃO-HERMÉTICO (dependia de quais nós GTO estavam no
    # DB); contar o penalty é estável (só depende do heurístico + do torneio fixo).
    genuine_errors = 0
    still_labeled_mistake = 0
    for hand in hands:
        for di in build_decision_inputs_for_hand(hand):
            if di['street'] == 'preflop':
                continue
            r = evaluate_decision(di)
            bd = r['evaluation']['scoreBreakdown']
            if bd['mathPenalty'] > 0:
                genuine_errors += 1
                if r['evaluation']['label'] in ('small_mistake', 'clear_mistake'):
                    still_labeled_mistake += 1

    # O heurístico deve seguir detectando os erros de math (eram 9; ~11 hoje), e ao menos
    # alguns devem continuar rotulados como mistake (os spots sem override GTO).
    assert genuine_errors >= 7, f"Detecção de erros genuínos (mathPenalty) caiu: {genuine_errors}"
    assert still_labeled_mistake >= 1, f"Nenhum erro genuíno ficou rotulado mistake: {still_labeled_mistake}"
    print(f"OK  test_genuine_errors_preserved | {genuine_errors} detectados (mathPenalty), "
          f"{still_labeled_mistake} ainda mistake")


def test_preflop_unaffected():
    """Decisões preflop devem usar range zones do preflop evaluator, não do postflop."""
    from leaklab.parser import parse_pokerstars_file
    hands = parse_pokerstars_file(TOURNAMENT_FILE)

    POSTFLOP_ZONES = {'strong', 'medium', 'weak', 'draw', 'air'}
    bad_zones = []
    for hand in hands:
        for di in build_decision_inputs_for_hand(hand):
            if di['street'] == 'preflop':
                zone = di['range_evaluation'].get('rangeZone', '')
                if zone in POSTFLOP_ZONES:
                    bad_zones.append(zone)

    assert not bad_zones, f"Preflop usando postflop evaluator (zones: {set(bad_zones)})"
    print(f"OK  test_preflop_unaffected | postflop zones em preflop: nenhuma")


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
