"""
Testa o motor de ELO (leaklab/elo_engine.py) — sistema de rating dos jogadores.

Cobre: k_factor, expected_score, decision_score (sem fallback heurístico),
apply_decision (direção/magnitude), bandas (band_full/next_band_for),
compute_player_elo_from_decisions (agregado + por street + exclusão de spots
sem GTO + ordenação), compute_elo_curve (1 ponto por torneio) e snapshot_to_dict.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.elo_engine import (
    k_factor, expected_score, decision_score, apply_decision, apply_inactivity_decay,
    band_full, band_for, next_band_for,
    compute_player_elo_from_decisions, compute_elo_curve, snapshot_to_dict,
    SOLVER_ELO, INITIAL_ELO, BANDS, GTO_LABEL_SCORE, DECAY_MAX,
)


def _approx(a, b, tol=0.5):
    return abs(a - b) <= tol


def _dec(street, gto_label, i, tid=1, label="standard", created_at=None):
    return {
        "id": i,
        "tournament_id": tid,
        "street": street,
        "gto_label": gto_label,
        "label": label,
        "created_at": created_at if created_at is not None else f"2026-01-01 00:{i:02d}:00",
    }


# ── Primitivas ────────────────────────────────────────────────────────────────

def test_k_factor_thresholds():
    assert k_factor(0) == 32
    assert k_factor(99) == 32
    assert k_factor(100) == 16
    assert k_factor(999) == 16
    assert k_factor(1000) == 8
    assert k_factor(50000) == 8
    print("OK  test_k_factor_thresholds")


def test_expected_score():
    # ELO igual → 50%
    assert _approx(expected_score(1500, 1500), 0.5, 0.001)
    # +400 acima do oponente → ~10:1 (0.909)
    assert _approx(expected_score(1900, 1500), 0.909, 0.001)
    # −400 abaixo → ~0.091; simetria
    assert _approx(expected_score(1100, 1500), 0.091, 0.001)
    assert _approx(expected_score(1100, 1500) + expected_score(1900, 1500), 1.0, 0.001)
    # default usa SOLVER_ELO como oponente
    assert _approx(expected_score(SOLVER_ELO), 0.5, 0.001)
    print("OK  test_expected_score")


def test_decision_score_no_heuristic_fallback():
    assert decision_score("gto_correct") == 1.0
    assert decision_score("gto_mixed") == 0.7
    assert decision_score("gto_minor_deviation") == 0.4
    assert decision_score("gto_critical") == 0.0
    # Sem gto_label → None (excluído do rating), mesmo com engine_label presente
    assert decision_score(None) is None
    assert decision_score(None, "standard") is None
    assert decision_score("", "clear_mistake") is None
    assert decision_score("garbage_label") is None
    print("OK  test_decision_score_no_heuristic_fallback")


def test_apply_decision_direction_and_magnitude():
    # No par (1500), E=0.5 → acerto sobe +K*0.5, erro desce −K*0.5
    assert _approx(apply_decision(1500, 1.0, 0), 1516.0)   # K=32 → +16
    assert _approx(apply_decision(1500, 0.0, 0), 1484.0)   # K=32 → −16
    # gto_mixed (0.7) sobe menos que correct
    up_correct = apply_decision(1500, 1.0, 0) - 1500
    up_mixed   = apply_decision(1500, 0.7, 0) - 1500
    assert up_mixed < up_correct
    # K menor (mais decisões) → passo menor
    big_k = apply_decision(1500, 1.0, 0) - 1500     # K=32
    small_k = apply_decision(1500, 1.0, 1000) - 1500  # K=8
    assert small_k < big_k
    print("OK  test_apply_decision_direction_and_magnitude")


def test_inactivity_decay():
    # Dentro da carência (≤1 semana) → sem decay
    assert apply_inactivity_decay(1600, 0.5) == (1600.0, 0.0)
    assert apply_inactivity_decay(1600, 1.0) == (1600.0, 0.0)
    # Após carência: 3 semanas → 2 decaíveis × 2 = −4
    elo, dec = apply_inactivity_decay(1600, 3.0)
    assert dec == 4.0 and elo == 1596.0
    # Cap total em DECAY_MAX (−20), mesmo após muitas semanas
    elo, dec = apply_inactivity_decay(1600, 100.0)
    assert dec == DECAY_MAX and elo == 1600 - DECAY_MAX
    # Piso no INITIAL_ELO: rating logo acima do par não cai abaixo dele
    elo, dec = apply_inactivity_decay(1510, 100.0)
    assert elo == float(INITIAL_ELO) and dec == 10.0
    # No/abaixo do par → nunca decai (nem sobe)
    assert apply_inactivity_decay(1500, 100.0) == (1500.0, 0.0)
    assert apply_inactivity_decay(1400, 100.0) == (1400.0, 0.0)
    print("OK  test_inactivity_decay")


# ── Bandas ──────────────────────────────────────────────────────────────────

def test_bands_boundaries():
    # Abaixo da 1ª faixa → Iniciante
    assert band_full(1000)[1] == "Iniciante"
    assert band_full(1569)[1] == "Iniciante"
    # Limiares exatos sobem de faixa
    assert band_full(1570)[1] == "Estudante"
    assert band_full(1647)[1] == "Grinder"
    assert band_full(1710)[1] == "Regular"
    assert band_full(1816)[1] == "Sólido"
    assert band_full(1924)[1] == "Expert"
    assert band_full(2053)[1] == "Elite"
    assert band_full(3000)[1] == "Elite"
    # band_for é compat (label, color)
    assert band_for(2053)[0] == "Elite"
    print("OK  test_bands_boundaries")


def test_next_band():
    nb = next_band_for(1500)
    assert nb is not None and nb["label"] == "Estudante"
    assert nb["threshold"] == 1570
    assert _approx(nb["elo_to_go"], 70.0, 0.1)
    assert 0.0 <= nb["progress"] <= 1.0
    # No topo (Elite) → sem próxima banda
    assert next_band_for(2100) is None
    print("OK  test_next_band")


# ── Agregação por player ──────────────────────────────────────────────────────

def test_all_correct_rises_all_critical_falls():
    correct = [_dec("preflop", "gto_correct", i) for i in range(10)]
    s_up = compute_player_elo_from_decisions(1, correct)
    assert s_up.overall.elo > INITIAL_ELO
    assert s_up.total_decisions == 10

    critical = [_dec("preflop", "gto_critical", i) for i in range(10)]
    s_down = compute_player_elo_from_decisions(1, critical)
    assert s_down.overall.elo < INITIAL_ELO
    print("OK  test_all_correct_rises_all_critical_falls")


def test_spots_without_gto_label_excluded():
    # 5 sem gto_label + 0 com → ELO fica no inicial e total = 0
    decs = [_dec("preflop", None, i, label="clear_mistake") for i in range(5)]
    s = compute_player_elo_from_decisions(1, decs)
    assert s.total_decisions == 0
    assert _approx(s.overall.elo, INITIAL_ELO, 0.01)
    assert s.overall.band_label == "Iniciante"
    # mistura: 3 com gto_label contam, 2 sem não
    mixed = [_dec("preflop", "gto_correct", 0), _dec("preflop", None, 1),
             _dec("preflop", "gto_correct", 2), _dec("preflop", None, 3),
             _dec("preflop", "gto_correct", 4)]
    s2 = compute_player_elo_from_decisions(1, mixed)
    assert s2.total_decisions == 3
    print("OK  test_spots_without_gto_label_excluded")


def test_per_street_independence():
    decs = ([_dec("preflop", "gto_correct", i) for i in range(3)] +
            [_dec("flop", "gto_critical", 10 + i) for i in range(2)])
    s = compute_player_elo_from_decisions(1, decs)
    assert s.total_decisions == 5
    assert "preflop" in s.by_street and "flop" in s.by_street
    assert s.by_street["preflop"].elo > INITIAL_ELO   # só acertos
    assert s.by_street["flop"].elo < INITIAL_ELO       # só erros
    assert s.by_street["preflop"].n_decisions == 3
    assert s.by_street["flop"].n_decisions == 2
    # streets sem decisão não aparecem
    assert "turn" not in s.by_street and "river" not in s.by_street
    print("OK  test_per_street_independence")


def test_non_poker_streets_skipped():
    decs = [_dec("preflop", "gto_correct", 0),
            _dec("showdown", "gto_correct", 1),   # street inválida → ignorada
            _dec("", "gto_correct", 2)]
    s = compute_player_elo_from_decisions(1, decs)
    assert s.total_decisions == 1
    print("OK  test_non_poker_streets_skipped")


def test_ordering_by_created_at():
    # Mesma composição em ordens diferentes → mesmo ELO final (processa ordenado)
    a = [_dec("preflop", "gto_correct", 0, created_at="2026-01-01 00:00:00"),
         _dec("preflop", "gto_critical", 1, created_at="2026-01-01 00:01:00")]
    b = list(reversed(a))
    sa = compute_player_elo_from_decisions(1, a)
    sb = compute_player_elo_from_decisions(1, b)
    assert _approx(sa.overall.elo, sb.overall.elo, 0.01)
    print("OK  test_ordering_by_created_at")


# ── Curva ─────────────────────────────────────────────────────────────────────

def test_elo_curve_one_point_per_tournament():
    decs = ([_dec("preflop", "gto_correct", i, tid=1) for i in range(3)] +
            [_dec("preflop", "gto_correct", 10 + i, tid=2) for i in range(2)])
    curve = compute_elo_curve(decs)
    assert [p["tournament_id"] for p in curve] == [1, 2]
    assert curve[0]["n_decisions"] == 3
    assert curve[1]["n_decisions"] == 5   # acumulado ao longo dos torneios
    assert curve[1]["elo"] > curve[0]["elo"]  # mais acertos → sobe
    print("OK  test_elo_curve_one_point_per_tournament")


def test_elo_curve_skips_tournaments_without_gto():
    decs = ([_dec("preflop", "gto_correct", 0, tid=1)] +
            [_dec("preflop", None, 1, tid=2)] +          # torneio 2 sem cobertura GTO
            [_dec("preflop", "gto_correct", 2, tid=3)])
    curve = compute_elo_curve(decs)
    assert [p["tournament_id"] for p in curve] == [1, 3]  # torneio 2 omitido
    print("OK  test_elo_curve_skips_tournaments_without_gto")


# ── Serialização ──────────────────────────────────────────────────────────────

def test_snapshot_to_dict_shape():
    decs = [_dec("preflop", "gto_correct", i) for i in range(4)]
    d = snapshot_to_dict(compute_player_elo_from_decisions(7, decs))
    assert d["user_id"] == 7
    for k in ("elo", "n_decisions", "band_icon", "band_label", "band_color"):
        assert k in d["overall"]
    assert "next_band" in d
    assert "preflop" in d["by_street"]
    print("OK  test_snapshot_to_dict_shape")


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
