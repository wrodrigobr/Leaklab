"""
Testes do draw_detector — Sprint 3 do Ciclo 2.
"""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gaphunter.draw_detector import detect_draws, adjust_equity_for_draws, DrawProfile


# ── Flush draws ───────────────────────────────────────────────────────────────

def test_flush_draw_4_suited():
    p = detect_draws('AsKs', ['2s', '7h', 'Ts'])  # As,Ks,2s,Ts = 4 spades → FD
    assert p.flush_draw
    assert not p.backdoor_flush_draw
    print("OK  test_flush_draw_4_suited")


def test_backdoor_flush_draw_3_suited():
    p = detect_draws('AsKs', ['2s', '7h', 'Td'])
    # As + Ks + 2s = 3 spades com board 1 spade → 4 total = FD
    # Recriar com apenas 3
    p2 = detect_draws('AsKs', ['7h', 'Td'])  # 2 board cards → 2+2=4... depende
    # As9s com board Ac Jc → 3 clubs total → BDFD
    p3 = detect_draws('8cAc', ['Td'])  # 2 clubs hero, 0 clubs board → BDFD? não
    # 8cAc + Td: suits = c,c,d → max=2 → nem BDFD
    p4 = detect_draws('8cAc', ['Tc', '2h'])  # 3 clubs → BDFD
    assert p4.backdoor_flush_draw
    assert not p4.flush_draw
    print("OK  test_backdoor_flush_draw_3_suited")


def test_no_flush_draw():
    p = detect_draws('AsKh', ['2c', '7d', 'Td'])
    assert not p.flush_draw
    assert not p.backdoor_flush_draw
    print("OK  test_no_flush_draw")


def test_made_flush_not_draw():
    # 5+ suited = flush feito, não draw
    p = detect_draws('AsKs', ['2s', '7s', 'Ts'])
    assert not p.flush_draw  # já fez flush
    print("OK  test_made_flush_not_draw")


# ── Straight draws ────────────────────────────────────────────────────────────

def test_oesd():
    # 5678 → OESD (precisa de 4 ou 9)
    p = detect_draws('5d6h', ['7s', '8c', 'Ah'])
    assert p.oesd
    print("OK  test_oesd")


def test_gutshot():
    # 5679 → gutshot (precisa de 8)
    p = detect_draws('5d6h', ['7s', '9c', 'Ah'])
    assert p.gutshot
    assert not p.oesd
    print("OK  test_gutshot")


def test_no_straight_draw():
    p = detect_draws('AsKh', ['2c', '7d', 'Td'])
    assert not p.oesd
    assert not p.gutshot
    print("OK  test_no_straight_draw")


def test_ace_low_straight_draw():
    # A234 → OESD para wheel (precisa de 5)
    p = detect_draws('Ah2d', ['3s', '4c', 'Kh'])
    assert p.oesd or p.gutshot  # deve detectar draw para A-2-3-4-5
    print("OK  test_ace_low_straight_draw")


# ── DrawProfile ───────────────────────────────────────────────────────────────

def test_equity_adjustment_flush_draw():
    p = detect_draws('AsKs', ['2s', '7h', 'Ts'])  # As,Ks,2s,Ts = 4 spades = FD
    assert p.flush_draw
    # FD(0.15) pode combinar com BDSD(0.04) → 0.19 (mas cap 0.25 não ativa)
    assert p.equity_adjustment >= 0.15
    print(f"OK  test_equity_adjustment_flush_draw | adj={p.equity_adjustment}")


def test_equity_adjustment_oesd():
    p = detect_draws('5d6h', ['7s', '8c', 'Ah'])
    assert p.oesd
    assert abs(p.equity_adjustment - 0.17) < 0.01
    print(f"OK  test_equity_adjustment_oesd | adj={p.equity_adjustment}")


def test_equity_adjustment_capped():
    # FD + OESD = 0.15 + 0.17 = 0.32 > cap 0.25
    p = detect_draws('5s6s', ['7s', '8s', 'Ah'])  # FD + OESD
    assert p.equity_adjustment <= 0.25
    print(f"OK  test_equity_adjustment_capped | adj={p.equity_adjustment} (cap=0.25)")


def test_has_any_draw():
    p1 = detect_draws('AsKs', ['2s', '7h', 'Ts'])  # FD
    p2 = detect_draws('2h3d', ['7c', '8h', 'Kd'])  # sem draw
    assert p1.has_any_draw
    assert not p2.has_any_draw
    print("OK  test_has_any_draw")


def test_draw_profile_str():
    p = detect_draws('AsKs', ['2s', '7h', 'Ts'])
    s = str(p)
    assert 'FD' in s
    print(f"OK  test_draw_profile_str | '{s}'")


# ── adjust_equity_for_draws ───────────────────────────────────────────────────

def test_adjust_equity_flop_with_fd():
    eq, p = adjust_equity_for_draws(0.29, 'AsKs', ['2s', '7h', 'Ts'], 'flop')
    assert eq > 0.29
    assert p.flush_draw
    print(f"OK  test_adjust_equity_flop_with_fd | {0.29} → {eq}")


def test_adjust_equity_river_no_change():
    # No river não há draws — equity não muda
    eq, p = adjust_equity_for_draws(0.29, 'AsKs', ['2s', '7h', 'Ts', 'Kh', '3d'], 'river')
    assert eq == 0.29
    assert not p.has_any_draw
    print("OK  test_adjust_equity_river_no_change")


def test_adjust_equity_no_draw_no_change():
    # Mão sem draw: offsuit rainbow com nenhum draw
    eq, p = adjust_equity_for_draws(0.45, '2h3d', ['7c', '8s', 'Kd'], 'flop')
    assert eq == 0.45
    assert not p.has_any_draw
    print("OK  test_adjust_equity_no_draw_no_change")


def test_adjust_equity_capped_at_095():
    eq, p = adjust_equity_for_draws(0.80, 'AsKs', ['2s', '7h', 'Ts'], 'flop')
    assert eq <= 0.95
    print(f"OK  test_adjust_equity_capped_at_095 | {eq}")


# ── Bug fix: board por street ─────────────────────────────────────────────────

def test_real_case_as9s_flop():
    """As9s com board Ac Jc 5c → BDFD (3 clubs)."""
    p = detect_draws('As9s', ['Ac', 'Jc', '5c'])
    # As + 9s: suits s,s. Board: c,c,c → clubs=3 → BDFD
    assert p.backdoor_flush_draw
    eq, _ = adjust_equity_for_draws(0.29, 'As9s', ['Ac', 'Jc', '5c'], 'flop')
    assert eq > 0.29
    print(f"OK  test_real_case_as9s_flop | draw={p} eq={eq}")


def test_real_case_as3s_flop():
    """As3s com board Qs 8s 9s: 5 spades total = flush já feito, não draw.
    Com board Ad: As,3s,Ad = 2s+1d → BDSD pela sequência."""
    p = detect_draws('As3s', ['Qs', '8s', '9s'])
    # 5 spades = flush feito → flush_draw=False
    assert not p.flush_draw
    # Caso real do torneio: board Ad no turn
    p2 = detect_draws('As3s', ['Ad'])
    # A,3 com board A: BDSD possível (A-2-3-4 sequence)
    eq, _ = adjust_equity_for_draws(0.29, 'As3s', ['Qs', '8s', '9s'], 'flop')
    print(f"OK  test_real_case_as3s_flop | draw={p} eq={eq}")


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
