"""
Testa o ICM vendorizado do PokerKit (leaklab/icm.py) e sua integração no
mtt_context (equity ICM real na mesa final).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.icm import calculate_icm, hero_icm_equity, standard_payouts
from leaklab.parser import parse_hand_history
from leaklab.mtt_context import build_mtt_context, context_to_dict

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _approx(a, b, tol=0.01):
    return abs(a - b) <= tol


def test_calculate_icm_matches_pokerkit_doctests():
    """Valida que o trecho vendorizado bate com os valores do upstream (PokerKit)."""
    r = calculate_icm([70, 30], [50, 30, 20])
    assert _approx(r[0], 45.17, 0.01) and _approx(r[1], 32.25) and _approx(r[2], 22.57, 0.01)
    r = calculate_icm([50, 30, 20], [25, 87, 88])
    assert _approx(r[0], 25.69, 0.01) and _approx(r[1], 37.08, 0.01) and _approx(r[2], 37.21, 0.01)
    # soma das equities == soma dos payouts
    assert _approx(sum(calculate_icm([50, 30, 20], [10, 20, 30])), 100.0)
    print("OK  test_calculate_icm_matches_pokerkit_doctests")


def test_standard_payouts_normalized_and_capped():
    for n in (1, 2, 3, 6, 9):
        p = standard_payouts(n)
        assert _approx(sum(p), 1.0), f"payouts({n}) não soma 1.0"
        assert len(p) == min(n, 6), f"payouts({n}) deveria ter min(n,6) casas"
        # top-heavy: cada casa paga ≥ que a seguinte
        assert all(p[i] >= p[i + 1] for i in range(len(p) - 1))
    print("OK  test_standard_payouts_normalized_and_capped")


def test_hero_icm_equity_directions():
    # stacks iguais → equity == chip% → tax 0
    eq = hero_icm_equity([1000, 1000, 1000], hero_index=0)
    assert _approx(eq['tax_pct'], 0.0)
    # short stack → equity ICM ACIMA da fração de fichas (prêmio de sobrevivência) → tax < 0
    short = hero_icm_equity([1000, 1000, 200], hero_index=2)
    assert short['equity_pct'] > short['chip_pct']
    assert short['tax_pct'] < 0
    # chip leader → equity ICM ABAIXO da fração (retornos decrescentes) → tax > 0
    leader = hero_icm_equity([5000, 1000, 1000], hero_index=0)
    assert leader['equity_pct'] < leader['chip_pct']
    assert leader['tax_pct'] > 0
    print("OK  test_hero_icm_equity_directions")


def test_hero_icm_equity_guards():
    assert hero_icm_equity([], 0) is None
    assert hero_icm_equity([100, 200], 5) is None          # índice fora do range
    assert hero_icm_equity([0, 0, 0], 0) is None           # soma de fichas zero
    print("OK  test_hero_icm_equity_guards")


def test_mtt_context_icm_final_table():
    """Na mesa final (PartyPoker STT), o ICM é calculado e exposto no contexto."""
    raw = open(os.path.join(FIX, 'partypoker_tourney_stt.txt'), encoding='utf-8', errors='ignore').read()
    hands = parse_hand_history(raw)
    # 1ª mão: 4 jogadores com 500 cada → equity ≈ chip% ≈ 25%, tax ≈ 0
    c0 = build_mtt_context(hands[0])
    assert c0.active_players == 4
    assert c0.icm_equity_pct is not None
    assert _approx(c0.icm_chip_pct, 25.0, 0.5)
    assert _approx(c0.icm_tax_pct, 0.0, 0.5)
    # heads-up: hero chip leader → tax > 0 (paga o prêmio de risco)
    hu = next(h for h in hands if build_mtt_context(h).active_players == 2)
    chu = build_mtt_context(hu)
    assert chu.icm_equity_pct is not None and chu.icm_tax_pct > 0
    # exposto no dict + não quebrou icm_pressure heurístico
    d = context_to_dict(chu)
    assert d['icmEquityPct'] == chu.icm_equity_pct
    assert d['icmPressure'] in ('low', 'medium', 'high')
    print("OK  test_mtt_context_icm_final_table")


def test_mtt_context_no_icm_for_large_field():
    """Fora da mesa final (campo > 9 jogadores) o ICM não é calculado (None)."""
    seats = "\n".join(f"Seat {i}: P{i} (1500 in chips)" for i in range(1, 13))
    raw = (
        "PokerStars Hand #1: Tournament #999, Hold'em No Limit - Level I (10/20)"
        " - 2025/01/01 12:00:00 ET\nTable '999 1' 12-max Seat #1 is the button\n"
        + seats + "\nDealt to P1 [Ah Kh]\n"
    )
    h = parse_hand_history(raw)[0]
    c = build_mtt_context(h)
    assert c.active_players == 12
    assert c.icm_equity_pct is None and c.icm_tax_pct is None
    print("OK  test_mtt_context_no_icm_for_large_field")


def test_pressure_adjustment_uses_icm_tax_continuous():
    """Na mesa final usa o sinal contínuo (icm_tax); fora dela, o bucket heurístico."""
    from leaklab.decision_engine_v11 import calc_pressure_adjustment
    # contínuo: |tax| escala a equity requerida, capado em 0.02
    assert _approx(calc_pressure_adjustment('turn', None, False, 'high', icm_tax_pct=30.0), 0.018, 0.001)
    assert _approx(calc_pressure_adjustment('turn', None, False, 'low', icm_tax_pct=8.0), 0.0048, 0.001)
    assert calc_pressure_adjustment('turn', None, False, 'low', icm_tax_pct=100.0) <= 0.03  # clamp global
    # sem icm_tax → fallback heurístico idêntico ao comportamento anterior
    assert _approx(calc_pressure_adjustment('turn', None, False, 'high'), 0.01)
    assert _approx(calc_pressure_adjustment('turn', None, False, 'low'), 0.0)
    print("OK  test_pressure_adjustment_uses_icm_tax_continuous")


def _thin_call_input(icm_tax):
    ctx = {'tournamentStage': 'final_table', 'icmPressure': 'high', 'isPko': False}
    if icm_tax is not None:
        ctx['icmTaxPct'] = icm_tax
    return {
        'hand_id': 'h1', 'player_action': 'call', 'street': 'turn',
        'spot': {'position': 'BB', 'isInPosition': True, 'isMultiway': False,
                 'effectiveStackBb': 20, 'facingSize': 10, 'street': 'turn'},
        'hand_profile': {'handClass': 'marginal'},
        'math': {'potOddsEquity': 0.40, 'estimatedHandEquity': 0.41, 'pressureScore': 0.0,
                 'reverseImpliedOddsFactor': 0.0, 'impliedOddsFactor': 0.0},
        'range_evaluation': {'recommendedPrimaryAction': 'fold', 'alternativeActions': [],
                             'rangeZone': 'outside_range', 'confidence': 0.7},
        'context': ctx,
    }


def test_icm_tax_raises_required_equity_for_thin_call():
    """ICM tax alto eleva a equity requerida → call fino vira erro maior."""
    from leaklab.decision_engine_v11 import evaluate_decision
    base = evaluate_decision(_thin_call_input(None))
    iced = evaluate_decision(_thin_call_input(30.0))
    assert iced['thresholds']['adjustedRequiredEquity'] > base['thresholds']['adjustedRequiredEquity']
    assert iced['evaluation']['mistakeScore'] > base['evaluation']['mistakeScore']
    print("OK  test_icm_tax_raises_required_equity_for_thin_call")


def test_icm_interpretation_directional():
    """Na mesa final, o feedback da decisão (erro) traz a leitura direcional do ICM;
    fora dela, mantém o texto heurístico. Qualitativo — sem número 'duro'."""
    from leaklab.decision_engine_v11 import evaluate_decision

    def strat(tax):
        return evaluate_decision(_thin_call_input(tax))['interpretation']['strategicExplanation']

    big = strat(30.0)        # pilha grande (equity ICM < fichas)
    assert 'Mesa final' in big and 'maiores pilhas' in big

    short = strat(-30.0)     # pilha curta (prêmio de sobrevivência)
    assert 'Mesa final' in short and 'pilha curta' in short

    balanced = strat(1.0)    # stacks equilibrados
    assert 'Mesa final' in balanced and 'equilibrados' in balanced

    none = strat(None)       # fora da mesa final → fallback heurístico, sem "Mesa final"
    assert 'Mesa final' not in none and 'ICM elevado' in none
    print("OK  test_icm_interpretation_directional")


def test_cognitive_icm_blindness_detector():
    """O detector marca gambles finos de alto ICM na mesa final como padrão coachável."""
    from leaklab.cognitive_mapper import analyze_cognitive_failures

    def dec(i, action, label, tax):
        return {"tournament_id": 1, "id": i, "hand_id": f"h{i}", "street": "preflop",
                "action_taken": action, "best_action": "fold", "label": label,
                "score": 0.0, "position": "BB", "m_ratio": 8.0,
                "icm_pressure": "high", "icm_tax_pct": tax, "stack_bb": 15.0}

    decisions = []
    # 5 spots de alto ICM (tax 20) arriscando a pilha: 4 erros, 1 ok → leak claro
    decisions.append(dec(1, "call", "clear_mistake", 20.0))
    decisions.append(dec(2, "raise", "small_mistake", 20.0))
    decisions.append(dec(3, "all-in", "clear_mistake", -25.0))   # short stack, tax negativo
    decisions.append(dec(4, "call", "small_mistake", 18.0))
    decisions.append(dec(5, "call", "standard", 20.0))           # ok → opp mas não count
    # ruído: spots de baixo ICM (tax pequeno) e fora da mesa final (tax None) — ignorados
    for i in range(6, 36):
        decisions.append(dec(i, "fold", "standard", 1.0 if i % 2 else None))

    rep = analyze_cognitive_failures(decisions)
    icm = next((p for p in rep["patterns"] if p["type"] == "icm_blindness"), None)
    assert icm is not None, f"icm_blindness não detectado: {rep['patterns']}"
    # 5 opps (stack-risk em alto ICM), 4 erros → freq 0.8 → high
    assert icm["count"] == 4
    assert icm["severity"] == "high"

    # Sem spots de alto ICM → não dispara
    clean = [dec(i, "fold", "standard", None) for i in range(1, 36)]
    rep2 = analyze_cognitive_failures(clean)
    assert not any(p["type"] == "icm_blindness" for p in rep2["patterns"])
    print("OK  test_cognitive_icm_blindness_detector")


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
