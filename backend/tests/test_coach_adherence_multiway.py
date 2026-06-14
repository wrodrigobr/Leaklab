"""Aderência coach × sistema MULTIWAY-aware (leaklab/coach_adherence).

Em pote 3-way+ o "erro do sistema" vem do multiway_advisor (mesma fonte do card),
mas SÓ quando o advisor tem alta confiança (is_clear) — decisões próximas deferem ao
label, sem over-flag. Trava o comportamento do badge = card.
"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.multiway_advisor import is_hero_leak
from leaklab.coach_adherence import _multiway_sys_mistake, classify


# ── is_hero_leak (puro, sem eval7) ────────────────────────────────────────────
def test_is_hero_leak_clear_cases():
    fold = {'is_clear': True, 'action': 'fold'}
    assert is_hero_leak(fold, 'call')  is True     # continuar quando é fold = leak
    assert is_hero_leak(fold, 'raise') is True
    assert is_hero_leak(fold, 'fold')  is False    # foldou = alinhado
    bet = {'is_clear': True, 'action': 'bet'}
    assert is_hero_leak(bet, 'check') is True       # não apostar valor = leak
    assert is_hero_leak(bet, 'bet')   is False
    assert is_hero_leak(bet, 'raise') is False      # apostar/levantar = ok
    raise_ = {'is_clear': True, 'action': 'raise'}
    assert is_hero_leak(raise_, 'fold') is True     # foldar mão forte = leak
    assert is_hero_leak(raise_, 'call') is False    # pagar mão forte = aceitável
    print("OK  test_is_hero_leak_clear_cases")


def test_is_hero_leak_defers_when_not_clear():
    """Sem alta confiança → None (defere ao engine/label, sem over-flag)."""
    assert is_hero_leak({'is_clear': False, 'action': 'check'}, 'bet') is None
    assert is_hero_leak({'is_clear': False, 'action': 'call'}, 'fold') is None
    assert is_hero_leak(None, 'bet') is None
    print("OK  test_is_hero_leak_defers_when_not_clear")


# ── _multiway_sys_mistake (gating) ────────────────────────────────────────────
def _dec(**kw):
    base = dict(street='flop', n_active_opponents=2, action_taken='call',
                board='["9c","4d","4h"]', hero_cards='Ac2c', pot_size=13.0,
                facing_bet=4.0, position='BB', label='standard')
    base.update(kw)
    return base


def test_não_aplica_fora_de_multiway():
    assert _multiway_sys_mistake(_dec(street='preflop')) is None
    assert _multiway_sys_mistake(_dec(n_active_opponents=1)) is None
    assert _multiway_sys_mistake(_dec(n_active_opponents=None)) is None
    assert _multiway_sys_mistake(_dec(board='[]')) is None
    assert _multiway_sys_mistake(_dec(hero_cards='')) is None
    print("OK  test_não_aplica_fora_de_multiway")


def test_board_truncado_pela_street():
    """Board final de 5 cartas no FLOP só enxerga as 3 do flop (senão A2c viraria dois
    pares com K/A futuros e o veredito mudaria de fold→raise)."""
    full = '["9c","4d","4h","Ks","Ah"]'
    leak_flop = _multiway_sys_mistake(_dec(board=full, street='flop'))  # A2c A-alto -> fold
    assert leak_flop is True, leak_flop   # hero deu call num fold claro = leak
    print("OK  test_board_truncado_pela_street")


def test_classify_multiway_leak_vira_match_erro():
    """Leak multiway claro (A2c paga no flop 944 onde é fold) + coach disse fold →
    match_erro (badge = card)."""
    dec = _dec()  # hero call
    ann = {'coach_action': 'fold', 'coach_override_label': None, 'comment': 'larga aqui'}
    kind, _ = classify(dec, ann)
    assert kind == 'match_erro', kind
    print("OK  test_classify_multiway_leak_vira_match_erro")


def test_classify_decisao_proxima_defere_ao_label():
    """Bet num flop multiway que o advisor acharia próximo → NÃO sobrepõe; usa o label.
    label=standard + coach aprova o bet → match_ok (sem over-flag)."""
    # board seco, hero bet com mão fraca-média: advisor não tem alta confiança de bet
    dec = _dec(action_taken='bet', facing_bet=0.0, pot_size=8.0,
               board='["5c","4d","Ad"]', hero_cards='7h6h', label='standard')
    ann = {'coach_action': 'bet', 'coach_override_label': None, 'comment': 'boa aposta'}
    kind, _ = classify(dec, ann)
    assert kind == 'match_ok', kind   # não vira diverge_rigido
    print("OK  test_classify_decisao_proxima_defere_ao_label")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
