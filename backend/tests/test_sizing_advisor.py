"""Testes do sizing_advisor — Fase 1 (open preflop) + Fase 2 (postflop vs nó GTO)."""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from leaklab.sizing_advisor import (analyze_open_sizing as A,
                                    gto_main_bet_size_pct as G,
                                    analyze_postflop_sizing as P,
                                    analyze_3bet_sizing as B,
                                    analyze_postflop_texture_sizing as TX,
                                    _board_texture as TEX,
                                    _size_label_to_pct as L)


def test_std_open_ok():
    r = A(to_bb=2.2, position='BTN')
    assert r['key'] == 'open_ok' and r['status'] == 'ok'
    print("OK  test_std_open_ok")


def test_std_open_too_big():
    r = A(to_bb=3.0, position='UTG')
    assert r['key'] == 'open_big' and r['status'] == 'warn'
    print("OK  test_std_open_too_big")


def test_std_open_min_is_ok():
    r = A(to_bb=2.0, position='CO')
    assert r['key'] == 'open_ok'
    print("OK  test_std_open_min_is_ok")


def test_sb_open_too_small():
    # SB abrindo min vs BB → suba (open_sb_small)
    r = A(to_bb=2.0, position='SB')
    assert r['key'] == 'open_sb_small' and r['status'] == 'warn'
    print("OK  test_sb_open_too_small")


def test_sb_open_sized_up_ok():
    r = A(to_bb=3.0, position='SB')
    assert r['key'] == 'open_ok'
    print("OK  test_sb_open_sized_up_ok")


def test_iso_over_limp_too_small():
    r = A(to_bb=2.5, position='CO', facing_limp=True)
    assert r['key'] == 'open_iso_small'
    print("OK  test_iso_over_limp_too_small")


def test_iso_over_limp_ok():
    r = A(to_bb=4.0, position='CO', facing_limp=True)
    assert r['key'] == 'open_ok'
    print("OK  test_iso_over_limp_ok")


def test_none_when_no_size():
    assert A(to_bb=None, position='BTN') is None
    assert A(to_bb=0, position='BTN') is None
    print("OK  test_none_when_no_size")


# ── Fase 2: postflop vs nó GTO ───────────────────────────────────────────────

def test_label_pct_parse():
    assert L('bet_50pct', None) == 50.0
    assert L('raise_119pct', None) == 119.0
    assert abs(L('bet_6.4bb', 8.0) - 80.0) < 1e-6   # 6.4/8 = 80% do pote
    assert L('bet_1.5x', None) == 150.0             # x = x vezes o pote
    assert L('check', None) is None and L('allin', None) is None
    print("OK  test_label_pct_parse")


def test_gto_main_picks_highest_freq_bet():
    strat = [{'action': 'check', 'frequency': 0.5},
             {'action': 'bet_33pct', 'frequency': 0.4},
             {'action': 'bet_75pct', 'frequency': 0.1}]
    assert G(strat) == 33                       # bet de maior freq, ignora o check
    print("OK  test_gto_main_picks_highest_freq_bet")


def test_gto_main_none_when_no_bet():
    assert G([{'action': 'check', 'frequency': 0.7}, {'action': 'call', 'frequency': 0.3}]) is None
    print("OK  test_gto_main_none_when_no_bet")


def test_postflop_ok():
    r = P(hero_pct=70, gto_pct=66)
    assert r['key'] == 'postflop_ok' and r['status'] == 'ok' and r['params']['gto'] == 66
    print("OK  test_postflop_ok")


def test_postflop_too_big():
    r = P(hero_pct=100, gto_pct=33)             # 3x o size do solver
    assert r['key'] == 'postflop_too_big' and r['status'] == 'warn'
    print("OK  test_postflop_too_big")


def test_postflop_too_small():
    r = P(hero_pct=20, gto_pct=66)              # ~0.3x
    assert r['key'] == 'postflop_too_small' and r['status'] == 'warn'
    print("OK  test_postflop_too_small")


def test_postflop_none_when_missing():
    assert P(hero_pct=None, gto_pct=50) is None
    assert P(hero_pct=50, gto_pct=None) is None
    assert P(hero_pct=50, gto_pct=0) is None
    print("OK  test_postflop_none_when_missing")


# ── #3: sizing do 3-bet (relativo ao open) ───────────────────────────────────

def test_3bet_ip_ok():
    # open 2,5bb, 3-bet IP pra 7,5bb = 3.0x → ok
    r = B(to_bb=7.5, open_to_bb=2.5, is_ip=True)
    assert r['key'] == '3bet_ok' and r['status'] == 'ok' and r['params']['pos'] == 'IP'
    print("OK  test_3bet_ip_ok")


def test_3bet_oop_ok():
    # open 2,5bb, 3-bet OOP pra 10bb = 4.0x → ok
    r = B(to_bb=10.0, open_to_bb=2.5, is_ip=False)
    assert r['key'] == '3bet_ok' and r['params']['pos'] == 'OOP'
    print("OK  test_3bet_oop_ok")


def test_3bet_ip_too_small():
    # IP a 2.4x (< 2.6) → pequeno
    r = B(to_bb=6.0, open_to_bb=2.5, is_ip=True)
    assert r['key'] == '3bet_small' and r['status'] == 'warn'
    print("OK  test_3bet_ip_too_small")


def test_3bet_oop_size_is_ip_too_big():
    # 3.0x serve IP, mas OOP (ideal 4x) 3.0x ainda é pequeno (< 3.4)
    r = B(to_bb=7.5, open_to_bb=2.5, is_ip=False)
    assert r['key'] == '3bet_small'
    print("OK  test_3bet_oop_size_is_ip_too_big")


def test_3bet_too_big():
    # IP a 5x → grande
    r = B(to_bb=12.5, open_to_bb=2.5, is_ip=True)
    assert r['key'] == '3bet_big'
    print("OK  test_3bet_too_big")


def test_3bet_squeeze_raises_band():
    # squeeze IP: banda sobe (~4x). 4.0x que seria 'big' sem squeeze vira 'ok'
    assert B(to_bb=10.0, open_to_bb=2.5, is_ip=True)['key'] == '3bet_big'
    r = B(to_bb=10.0, open_to_bb=2.5, is_ip=True, squeeze=True)
    assert r['key'] == '3bet_ok' and 'squeeze' in r['params']['ideal']
    print("OK  test_3bet_squeeze_raises_band")


def test_3bet_none_when_missing():
    assert B(to_bb=None, open_to_bb=2.5, is_ip=True) is None
    assert B(to_bb=7.5, open_to_bb=0, is_ip=True) is None
    assert B(to_bb=7.5, open_to_bb=None, is_ip=True) is None
    print("OK  test_3bet_none_when_missing")


# ── Fase 3: sizing postflop por textura (sem nó GTO) ─────────────────────────

def test_texture_dry_wet_verywet():
    assert TEX(['Kh', '7d', '2c']) == 'dry'           # rainbow desconexo
    assert TEX(['Kh', '8h', '3c']) == 'wet'           # 2-flush (h) desconexo
    assert TEX(['Jh', 'Th', '9h']) == 'very_wet'      # monotone
    assert TEX(['Qh', 'Jd', 'Tc']) == 'wet'           # conexão sem flush
    print("OK  test_texture_dry_wet_verywet")


def test_tex_dry_small_bet_ok():
    # board seco, c-bet 33% IP → ok
    r = TX(hero_pct=33, board=['Kh', '7d', '2c'], is_ip=True)
    assert r['key'] == 'tex_ok' and r['params']['tex'] == 'dry'
    print("OK  test_tex_dry_small_bet_ok")


def test_tex_dry_overbet_flagged():
    # board seco, apostou 90% → grande demais
    r = TX(hero_pct=90, board=['Kh', '7d', '2c'], is_ip=True)
    assert r['key'] == 'tex_big' and r['status'] == 'warn'
    print("OK  test_tex_dry_overbet_flagged")


def test_tex_wet_needs_bigger():
    # board muito molhado, apostou só 30% → pequena demais (não cobra os draws)
    r = TX(hero_pct=30, board=['Jh', 'Th', '9h'], is_ip=True)
    assert r['key'] == 'tex_small'
    print("OK  test_tex_wet_needs_bigger")


def test_tex_wet_big_bet_ok():
    r = TX(hero_pct=80, board=['Jh', 'Th', '9h'], is_ip=True)
    assert r['key'] == 'tex_ok' and r['params']['tex'] == 'very_wet'
    print("OK  test_tex_wet_big_bet_ok")


def test_tex_low_spr_tolerates_small():
    # board molhado: dinky (<28) flaga; com SPR baixo a banda abre e 24% passa (comprometido)
    assert TX(hero_pct=24, board=['Kh', '8h', '3c'], is_ip=True)['key'] == 'tex_small'
    assert TX(hero_pct=24, board=['Kh', '8h', '3c'], is_ip=True, spr=2.0)['key'] == 'tex_ok'
    print("OK  test_tex_low_spr_tolerates_small")


def test_tex_none_preflop_or_missing():
    assert TX(hero_pct=50, board=[], is_ip=True) is None
    assert TX(hero_pct=None, board=['Kh', '7d', '2c'], is_ip=True) is None
    print("OK  test_tex_none_preflop_or_missing")


if __name__ == '__main__':
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn(); passed += 1
        except Exception as e:
            print(f"FAIL {name}: {e}"); traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
