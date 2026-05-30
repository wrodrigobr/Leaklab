"""
Testa o motor de ranking de alunos (leaklab/leaderboard.py) — item #15, fundação.
Funções puras: normalização, guarda de elegibilidade, pontuação por dimensão
(40/30/20/10) e ranqueamento determinístico.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.leaderboard import (
    _norm, eligibility, score_player, rank_leaderboard,
    W_GTO, W_EVO, W_ENG, W_VOL,
    MIN_HANDS, MIN_TOURNAMENTS, MIN_GTO_DECISIONS,
    TARGET_HANDS,
)
from leaklab.elo_engine import expected_score, INITIAL_ELO


def _approx(a, b, tol=0.1):
    return abs(a - b) <= tol


def _player(uid, **kw):
    base = dict(user_id=uid, display_name=f"u{uid}",
                player_elo=1700,  # dimensão A vem do ELO (expected_score)
                aligned_pct=0.8, aligned_early=0.8, aligned_recent=0.8,
                drills=20, tournaments=20, hands=2000, gto_decisions=500)
    base.update(kw)
    return base


def test_norm_clamps():
    assert _norm(0, 100) == 0.0
    assert _norm(50, 100) == 0.5
    assert _norm(200, 100) == 1.0     # satura em 1
    assert _norm(5, 0) == 0.0          # alvo 0 → 0 (sem divisão por zero)
    print("OK  test_norm_clamps")


def test_eligibility_gates():
    assert eligibility(_player(1)) == (True, None)
    assert eligibility(_player(1, hands=MIN_HANDS - 1))[1] == "insufficient_hands"
    assert eligibility(_player(1, tournaments=MIN_TOURNAMENTS - 1))[1] == "insufficient_tournaments"
    assert eligibility(_player(1, gto_decisions=MIN_GTO_DECISIONS - 1))[1] == "insufficient_gto_coverage"
    print("OK  test_eligibility_gates")


def test_dimension_weights():
    # A (aderência GTO) = expected_score(ELO); evo=0.5 (delta 0), eng/vol no piso.
    a_hi = expected_score(1900)  # ~0.909
    only_gto = score_player(_player(1, player_elo=1900, drills=0, tournaments=0, hands=0,
                                    gto_decisions=MIN_GTO_DECISIONS))
    assert _approx(only_gto["score"], 100 * (W_GTO * a_hi + W_EVO * 0.5))
    # Volume cheio + ELO no par (A=0.5): 100*(0.5*0.5 + 0.25*0.5 + 0.1*1)
    only_vol = score_player(_player(1, player_elo=INITIAL_ELO, drills=0, tournaments=0,
                                    hands=TARGET_HANDS, gto_decisions=MIN_GTO_DECISIONS))
    assert _approx(only_vol["score"], 100 * (W_GTO * 0.5 + W_EVO * 0.5 + W_VOL * 1))
    print("OK  test_dimension_weights")


def test_gto_dimension_from_elo():
    # Dimensão GTO sobe com o ELO; no par (1500) = 50 (expected_score 0.5).
    lo = score_player(_player(1, player_elo=INITIAL_ELO))
    hi = score_player(_player(1, player_elo=2000))
    assert _approx(lo["dimensions"]["gto"], 50.0)
    assert hi["dimensions"]["gto"] > lo["dimensions"]["gto"]
    print("OK  test_gto_dimension_from_elo")


def test_evolution_direction():
    improving = score_player(_player(1, aligned_early=0.6, aligned_recent=0.9))
    flat      = score_player(_player(1, aligned_early=0.8, aligned_recent=0.8))
    declining = score_player(_player(1, aligned_early=0.9, aligned_recent=0.6))
    assert improving["dimensions"]["evolution"] > flat["dimensions"]["evolution"]
    assert flat["dimensions"]["evolution"] > declining["dimensions"]["evolution"]
    assert _approx(flat["dimensions"]["evolution"], 50.0)   # delta 0 → meio da banda
    print("OK  test_evolution_direction")


def test_rank_orders_and_excludes_ineligible():
    players = [
        _player(1, player_elo=2000, aligned_pct=0.95, aligned_early=0.7, aligned_recent=0.95),  # forte
        _player(2, player_elo=1600, aligned_pct=0.70, aligned_early=0.70, aligned_recent=0.70), # médio
        _player(3, hands=100),   # inelegível (poucas mãos)
    ]
    res = rank_leaderboard(players)
    ranked_ids = [p["user_id"] for p in res["ranked"]]
    assert ranked_ids == [1, 2]                         # ordenado por score desc
    assert res["ranked"][0]["rank"] == 1 and res["ranked"][1]["rank"] == 2
    assert [p["user_id"] for p in res["ineligible"]] == [3]
    assert res["ineligible"][0]["reason"] == "insufficient_hands"
    assert res["ranked"][0]["score"] > res["ranked"][1]["score"]
    print("OK  test_rank_orders_and_excludes_ineligible")


def test_rank_tiebreak_deterministic():
    # Dois jogadores idênticos exceto user_id → desempate estável por user_id asc
    a = _player(7); b = _player(3)
    res = rank_leaderboard([a, b])
    assert [p["user_id"] for p in res["ranked"]] == [3, 7]
    print("OK  test_rank_tiebreak_deterministic")


def test_score_bounds():
    best  = score_player(_player(1, player_elo=2400, aligned_early=0.0, aligned_recent=1.0,
                                 drills=999, tournaments=999, hands=999999))
    worst = score_player(_player(1, player_elo=1200, aligned_early=1.0, aligned_recent=0.0,
                                 drills=0, tournaments=0, hands=0, gto_decisions=MIN_GTO_DECISIONS))
    assert 0.0 <= worst["score"] <= best["score"] <= 100.0
    print("OK  test_score_bounds")


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
