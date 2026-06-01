"""
test_recent_regressions.py — Regressões dos fixes da sessão 2026-05-25/26.

Cobre:
1. Tier 4 do _gto_classify_from_strategy (bet 7% → minor, não critical)
2. _gto_label_cap (minor_deviation cap clear→small; critical floor std→small)
3. Multiway equity adjustment (build_math_snapshot)
4. PKO ICM pressure atenuation (_detect_icm_pressure is_pko=True)
5. PKO required equity (calc_pressure_adjustment negativo)
6. Stack bucket cap >100bb (stack_bucket(150) == '60-100bb')
7. Guard facing all-in (best_action vira call/fold, não raise)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.decision_engine_v11 import (
    _gto_classify_from_strategy,
    _gto_label_cap,
    calc_pressure_adjustment,
    calc_adjusted_required_equity,
)
from leaklab.street_math_engine import build_math_snapshot
from leaklab.models import HandState
from leaklab.gto_utils import stack_bucket
from leaklab.mtt_context import _detect_icm_pressure
from leaklab.preflop_gto_ranges import analyze_preflop


# ── 1. Tier 4 do classifier — bet com freq baixa sem ev_diff ────────────────
def test_tier4_low_freq_no_ev_minor_deviation():
    """played_freq=7% sem ev_diff → minor_deviation (não critical).
    Caso real: solver Check 93% / Bet 7%. User bet matched freq da ação rara."""
    strat = [
        {'action': 'check', 'frequency': 0.93},
        {'action': 'bet 1.1', 'frequency': 0.07},
    ]
    label, freq = _gto_classify_from_strategy('bet', strat)
    assert label == 'gto_minor_deviation', f'expected minor_deviation, got {label}'
    assert abs(freq - 0.07) < 0.01
    print("OK  test_tier4_low_freq_no_ev_minor_deviation")

def test_tier4_very_low_freq_critical():
    """played_freq=1% (<3%) sem ev_diff → critical (ação fora do mix)."""
    strat = [
        {'action': 'check', 'frequency': 0.99},
        {'action': 'bet',   'frequency': 0.01},
    ]
    label, _ = _gto_classify_from_strategy('bet', strat)
    assert label == 'gto_critical', f'expected critical, got {label}'
    print("OK  test_tier4_very_low_freq_critical")

def test_tier4_dominant_action_correct():
    """played_freq=60%+ → correct (Tier 1)."""
    strat = [{'action': 'check', 'frequency': 0.70}, {'action': 'bet', 'frequency': 0.30}]
    label, _ = _gto_classify_from_strategy('check', strat)
    assert label == 'gto_correct'
    print("OK  test_tier4_dominant_action_correct")


# ── 2. _gto_label_cap — reconciliação bidirecional ──────────────────────────
def test_cap_gto_correct_clear_mistake_to_marginal():
    assert _gto_label_cap('clear_mistake', 'gto_correct') == 'marginal'
    assert _gto_label_cap('small_mistake', 'gto_mixed')   == 'marginal'
    print("OK  test_cap_gto_correct_clear_mistake_to_marginal")

def test_cap_minor_deviation_caps_clear_to_small():
    """Solver diz desvio leve — engine não pode dizer erro grave."""
    assert _gto_label_cap('clear_mistake', 'gto_minor_deviation') == 'small_mistake'
    assert _gto_label_cap('small_mistake', 'gto_minor_deviation') == 'small_mistake'
    print("OK  test_cap_minor_deviation_caps_clear_to_small")

def test_floor_gto_critical_promotes_standard():
    """Solver diz erro crítico — engine não pode dar pass como standard/marginal."""
    assert _gto_label_cap('standard', 'gto_critical') == 'small_mistake'
    assert _gto_label_cap('marginal', 'gto_critical') == 'small_mistake'
    # Já severo: mantém
    assert _gto_label_cap('clear_mistake', 'gto_critical') == 'clear_mistake'
    assert _gto_label_cap('small_mistake', 'gto_critical') == 'small_mistake'
    print("OK  test_floor_gto_critical_promotes_standard")


# ── 3. Multiway equity adjustment ───────────────────────────────────────────
def _state(n_opp: int, street='flop'):
    return HandState(
        hand_id='x', street=street, hero='h', hero_cards='AhAd',
        board=['7s', '2c', '9d'], player_action='check',
        pot_size=10, facing_size=0, effective_stack_bb=20,
        position='BTN', villain_position='SB', is_in_position=True,
        is_multiway=n_opp > 1, actions=[],
        metadata={'n_active_opponents': n_opp},
    )

def test_multiway_equity_hu_unchanged():
    """HU (1 opp) — equity heurística não é ajustada."""
    snap = build_math_snapshot(_state(1))
    assert snap.estimated_hand_equity == 0.58  # AA postflop heurística
    print("OK  test_multiway_equity_hu_unchanged")

def test_multiway_equity_3way_decay():
    """3-way (2 opps) → 77% do HU. AA 0.58 → ~0.45."""
    snap = build_math_snapshot(_state(2))
    expected = round(0.58 / (1.0 + 0.3 * 1), 4)
    assert abs(snap.estimated_hand_equity - expected) < 0.001, \
        f'expected {expected}, got {snap.estimated_hand_equity}'
    print("OK  test_multiway_equity_3way_decay")

def test_multiway_equity_5way_decay():
    """5-way (4 opps) → 53% do HU."""
    snap = build_math_snapshot(_state(4))
    expected = round(0.58 / (1.0 + 0.3 * 3), 4)
    assert abs(snap.estimated_hand_equity - expected) < 0.001
    print("OK  test_multiway_equity_5way_decay")

def test_multiway_preflop_not_adjusted():
    """Preflop preservado: ranges GTO já lidam com multiway."""
    snap = build_math_snapshot(_state(3, street='preflop'))
    assert snap.estimated_hand_equity == 0.64  # AA preflop heurística
    print("OK  test_multiway_preflop_not_adjusted")


# ── 4. PKO ICM pressure ─────────────────────────────────────────────────────
def test_pko_atenuates_pressure_pre_ft():
    """PKO atenua 1 nível pré-final-table: high→medium, medium→low."""
    # 9 active players, m=8 → classic medium → PKO low
    assert _detect_icm_pressure(8, 9, is_pko=False) == 'medium'
    assert _detect_icm_pressure(8, 9, is_pko=True)  == 'low'
    # m=5 → classic high → PKO medium (pré-FT)
    assert _detect_icm_pressure(5, 7, is_pko=False) == 'high'
    assert _detect_icm_pressure(5, 7, is_pko=True)  == 'medium'
    print("OK  test_pko_atenuates_pressure_pre_ft")

def test_pko_final_table_keeps_pressure():
    """Final table (≤3 players): PKO mantém high (bounty 'drowns' perto da bolha)."""
    assert _detect_icm_pressure(5, 3, is_pko=True)  == 'high'
    assert _detect_icm_pressure(5, 3, is_pko=False) == 'high'
    print("OK  test_pko_final_table_keeps_pressure")


# ── 5. PKO required equity ──────────────────────────────────────────────────
def test_pko_reduces_required_equity():
    """PKO subtrai 2pp da adjusted required equity pré-FT."""
    adj_classic = calc_pressure_adjustment('flop', 0.4, False, 'low', is_pko=False)
    adj_pko     = calc_pressure_adjustment('flop', 0.4, False, 'low', is_pko=True)
    assert adj_pko == round(adj_classic - 0.02, 4), \
        f'expected {adj_classic - 0.02}, got {adj_pko}'
    print("OK  test_pko_reduces_required_equity")

def test_pko_final_table_no_reduction():
    """Final table high ICM: PKO NÃO reduz (bounty effect drowns)."""
    adj = calc_pressure_adjustment('river', 0.7, False, 'high', is_pko=True)
    # Mesmo valor que classic high
    adj_classic = calc_pressure_adjustment('river', 0.7, False, 'high', is_pko=False)
    assert adj == adj_classic
    print("OK  test_pko_final_table_no_reduction")

def test_adjusted_required_equity_floor_5pct():
    """Piso de 5% pra evitar valores absurdos com PKO + pot odds muito baixos."""
    # pot_odds 5% + adj -3% = 2% → cap em 5%
    r = calc_adjusted_required_equity('flop', 0.05, 0.0, -0.03)
    assert r['adjustedRequiredEquity'] >= 0.05
    print("OK  test_adjusted_required_equity_floor_5pct")


# ── 6. Stack bucket cap 100bb+ ──────────────────────────────────────────────
def test_stack_bucket_cap_at_60_100():
    """Stacks >= 60bb usam bucket único '60-100bb' (cap implícito 100bb)."""
    assert stack_bucket(60)  == '60-100bb'
    assert stack_bucket(90)  == '60-100bb'
    assert stack_bucket(100) == '60-100bb'
    assert stack_bucket(150) == '60-100bb'
    assert stack_bucket(500) == '60-100bb'
    print("OK  test_stack_bucket_cap_at_60_100")

def test_stack_bucket_lower_brackets_intact():
    assert stack_bucket(0)  == '0-10bb'
    assert stack_bucket(9)  == '0-10bb'
    assert stack_bucket(10) == '10-20bb'
    assert stack_bucket(19) == '10-20bb'
    assert stack_bucket(20) == '20-35bb'
    assert stack_bucket(34) == '20-35bb'
    assert stack_bucket(35) == '35-60bb'
    assert stack_bucket(59) == '35-60bb'
    print("OK  test_stack_bucket_lower_brackets_intact")


# ── 7. Hero É o 3bettor (3beta um open) → vs_rfi, NÃO vs_3bet ─────────────────
def test_hero_as_3bettor_routes_to_vs_rfi():
    """is_3bet_pot=True com hero NÃO-agressor = hero é o 3bettor (3beta um open).
    É decisão de DEFESA vs open → vs_rfi (que tem a freq de 3bet do defensor),
    não vs_3bet (resposta do opener). SB 3betando o open do BTN é pareamento real."""
    r = analyze_preflop(
        position='SB', hero_hand_type='AKo', stack_bb=25,
        action_taken='raise', facing_size=5, vs_position='BTN',
        is_3bet_pot=True, n_players=9,
    )
    assert r.get('available') is True, 'hero-3bettor deve achar range vs_rfi'
    assert r.get('scenario') == 'vs_rfi', f"esperava vs_rfi, veio {r.get('scenario')}"
    print("OK  test_hero_as_3bettor_routes_to_vs_rfi")

def test_vs_3bet_hand_freq_fold_when_out_of_range():
    """Mão fora do range vs_3bet → hand_freq.fold=1.0 (inferido). Bucket A: hero
    abriu BTN e enfrenta 3bet da BB; 72o nunca continua vs 3-bet."""
    r = analyze_preflop(
        position='BTN', hero_hand_type='72o', stack_bb=25,
        action_taken='fold', facing_size=8, vs_position='BB',
        is_3bet_pot=False, hero_was_aggressor=True, facing_raises=1, n_players=9,
    )
    assert r.get('scenario') == 'vs_3bet'
    hf = r.get('hand_freq') or {}
    assert hf.get('fold', 0) >= 0.95, f'expected fold ~1.0, got {hf}'
    print("OK  test_vs_3bet_hand_freq_fold_when_out_of_range")


# ── 8. Squeeze/3-bet enfrentado a frio → faces_squeeze (NÃO vs_RFI; bug "call 45s vs squeeze") ──
def test_faces_squeeze_not_classified_as_vs_rfi():
    base = dict(position='BB', hero_hand_type='54s', stack_bb=29.7, action_taken='fold',
                facing_size=9.0, vs_position='SB', is_3bet_pot=False)
    # Sem o sinal (comportamento antigo): caía em vs_rfi (defesa larga vs open simples).
    bug = analyze_preflop(**base)
    assert bug['scenario'] not in ('faces_3bet_uncovered', 'faces_squeeze')
    # Com o sinal (2 raises, hero não agressor): roteia pra faces_squeeze. Sem range
    # coletado pra esse spot ainda → available=False (NULL honesto), jamais vs_rfi/call.
    fixed = analyze_preflop(**base, facing_raises=2, hero_was_aggressor=False)
    assert fixed['scenario'] == 'faces_squeeze'
    assert fixed['available'] is False  # sem cobertura no master de teste
    # Hero que FOI agressor (ex.: 3-bettor vs 4-bet) NÃO dispara o guard (pode ter cobertura).
    aggr = analyze_preflop(**base, facing_raises=2, hero_was_aggressor=True)
    assert aggr['scenario'] != 'faces_3bet_uncovered'
    print("OK  test_faces_squeeze_not_classified_as_vs_rfi")


def test_heuristic_borderline_folds_vs_cold_squeeze():
    from leaklab.preflop_range_evaluator import _recommended_action
    # 45s (borderline) facing 9bb: vs 3-bet HU → call (set-mine); squeeze a frio → fold.
    assert _recommended_action('4c5c', 'BB', facing_size=9.0, stack_bb=29.7, faces_3bet=False) == 'call'
    assert _recommended_action('4c5c', 'BB', facing_size=9.0, stack_bb=29.7, faces_3bet=True) == 'fold'
    print("OK  test_heuristic_borderline_folds_vs_cold_squeeze")


# ── 8b. Hero ABRIU e enfrenta 3bet → roteia pra vs_3bet (bucket A dos NULLs preflop) ──
def test_hero_opened_faces_3bet_routes_to_vs_3bet():
    # is_3bet_pot=False (hero NÃO 3betou — ele abriu), mas hero_was_aggressor=True e
    # enfrenta um re-raise. Antes caía em vs_rfi sem entrada → NULL falso. Agora vs_3bet.
    r = analyze_preflop(
        position='BTN', hero_hand_type='AJo', stack_bb=22, action_taken='call',
        facing_size=8.0, vs_position='BB', is_3bet_pot=False,
        hero_was_aggressor=True, facing_raises=1, n_players=9,
    )
    assert r.get('available') is True, 'hero-opened-faces-3bet deve achar range vs_3bet'
    assert r.get('scenario') == 'vs_3bet'
    print("OK  test_hero_opened_faces_3bet_routes_to_vs_3bet")


def test_vs_3bet_exact_pairing_only_no_random_fallback():
    # Bucket A com pareamento impossível: hero ABRIU no SB e "enfrenta 3bet" do UTG —
    # mas UTG age ANTES do SB, não pode 3betar um open do SB. vs_3bet[SB][UTG] não
    # existe. Sem o fallback "qualquer 3bettor", retorna sem cobertura (NULL honesto)
    # em vez de aplicar a range de um 3bettor aleatório (grade falso).
    r = analyze_preflop(
        position='SB', hero_hand_type='AKo', stack_bb=25, action_taken='call',
        facing_size=8.0, vs_position='UTG', is_3bet_pot=False,
        hero_was_aggressor=True, facing_raises=1, n_players=9,
    )
    assert r.get('scenario') == 'vs_3bet'
    assert r.get('available') is False, 'pareamento inexistente não deve grade via fallback'
    # Controle: pareamento bucket A válido (BTN abriu, BB 3bet) continua coberto.
    ok = analyze_preflop(
        position='BTN', hero_hand_type='AJo', stack_bb=22, action_taken='call',
        facing_size=8.0, vs_position='BB', is_3bet_pot=False,
        hero_was_aggressor=True, facing_raises=1, n_players=9,
    )
    assert ok.get('available') is True
    print("OK  test_vs_3bet_exact_pairing_only_no_random_fallback")


def test_hero_opened_faces_3bet_unknown_villain_no_false_grade():
    # 3bettor não detectado (vs_position='unknown'): o branch roteia pra vs_3bet mas o
    # lookup exato falha → sem grade falso (NULL honesto), pronto pra uploads reais.
    r = analyze_preflop(
        position='BTN', hero_hand_type='AJo', stack_bb=22, action_taken='call',
        facing_size=8.0, vs_position='unknown', is_3bet_pot=False,
        hero_was_aggressor=True, facing_raises=1, n_players=9,
    )
    assert r.get('available') is False, 'vilão desconhecido não pode produzir grade'
    print("OK  test_hero_opened_faces_3bet_unknown_villain_no_false_grade")


# ── 9. spot_hash robusto a hero_hand mal-formado (bug de ingestão solver_cli) ──
def test_spot_hash_normalizes_hero_hand():
    from leaklab.gto_utils import compute_spot_hash, normalize_cards
    # string '4dAd' e char-split ['4','A','d','d'] devem dar o MESMO hash da lista.
    base = ('flop', 'BTN', ['4c', '7c', 'Kh'])
    h_list = compute_spot_hash(*base, ['4d', 'Ad'], 80, 0.0)
    h_str  = compute_spot_hash(*base, 'Ad4d', 80, 0.0)
    h_bad  = compute_spot_hash(*base, ['4', 'A', 'd', 'd'], 80, 0.0)
    assert h_list == h_str == h_bad, (h_list, h_str, h_bad)
    assert normalize_cards('Ad4d') == ['Ad', '4d']
    assert normalize_cards(['4', 'A', 'd', 'd']) == ['4d', 'Ad']
    assert normalize_cards(['Ad', '4d']) == ['Ad', '4d']
    assert normalize_cards([]) == [] and normalize_cards(None) == []
    print("OK  test_spot_hash_normalizes_hero_hand")


# ── 10. guard de all-in usa facing em BB (facingSize está em fichas) ──────────
def test_allin_guard_converts_facing_chips_to_bb():
    from leaklab.decision_engine_v11 import evaluate_decision

    def _di(level_bb, facing_chips):
        return {
            # Hero abriu CO e enfrenta 3bet do BTN (bucket A, pareamento vs_3bet válido):
            # KK → jam. Pareamento real (não depende de fallback) p/ o teste do guard.
            'hand_id': 'T', 'street': 'preflop', 'player_action': 'call',
            'hero_cards': ['Kd', 'Kh'], 'is_3bet': False,
            'spot': {'spotType': 'preflop', 'position': 'CO', 'villainPosition': 'BTN',
                     'isInPosition': True, 'isMultiway': False, 'effectiveStackBb': 22.0,
                     'potSize': facing_chips, 'facingSize': facing_chips, 'raiseSizeBb': facing_chips,
                     'board': [], 'nPlayers': 9, 'nActiveOpponents': 1,
                     'preflopRaisesFaced': 1, 'heroWasAggressor': True},
            'hand_profile': {'handClass': 'premium', 'showdownValueTier': 'strong',
                             'drawTier': 'none', 'blockerProfile': [], 'rawEquityEstimate': 0.8,
                             'realizedEquityEstimate': 0.8},
            'math': {'potOddsEquity': 0.3, 'estimatedHandEquity': 0.8, 'rawEquity': 0.8,
                     'drawProfile': 'none', 'equityAdjustment': 0.0, 'impliedOddsFactor': 1.0,
                     'reverseImpliedOddsFactor': 1.0, 'pressureScore': 0.5},
            'range_evaluation': {'recommendedPrimaryAction': 'call',
                                 'alternativeActions': ['call', 'fold'], 'rangeZone': 'core_range',
                                 'confidence': 0.7, 'mixWeight': 0.05},
            'context': {'tournamentStage': 'early', 'icmPressure': 'medium', 'bountyDynamic': False,
                        'isPko': False, 'readsAvailable': False, 'heroStackBb': 22.0,
                        'levelBb': level_bb},
        }
    # facing 250 fichas com bb=250 = 1bb: o guard NÃO dispara → honra o jam do GTO.
    assert evaluate_decision(_di(250.0, 250.0)).get('bestAction') == 'jam'
    # facing 2300 fichas com bb=100 = 23bb >= stack 22bb: all-in genuíno → downgrade.
    res = evaluate_decision(_di(100.0, 2300.0))
    assert res.get('bestAction') != 'jam'
    # E o downgrade do GTO-commit (KK em range de jam) é para CALL, nunca fold:
    # preflop não computa equity-vs-range (eq=None); sem o branch GTO-aware o guard
    # caía no else → fold, rebaixando um call/commit trivial.
    assert res.get('bestAction') == 'call'
    print("OK  test_allin_guard_converts_facing_chips_to_bb")


# ── Runner ──────────────────────────────────────────────────────────────────
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
