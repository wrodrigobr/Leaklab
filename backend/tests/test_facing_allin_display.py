"""
Facing all-in: a linha agressiva do GTO (jam/raise) se executa CHAMANDO. O card mostrava
"GTO recomenda Call" ao lado de "Allin 99.9%" (o hand_freq cru) — parecia bug. Trava que
_normalize_facing_allin normaliza TAMBÉM as frequências exibidas (allin/raise dobram em call),
não só a recomendação. Regressão da mão 58 (99 na BTN foldou vs open-shove de 8.21bb).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from leaklab.preflop_gto_ranges import _normalize_facing_allin


def _base():
    # Simula a análise vs_rfi de 99 vs open-shove: GTO joga allin 99.9%.
    return {
        'available': True, 'scenario': 'vs_rfi', 'hand_type': '99',
        'recommended_actions': ['jam', 'call'],
        'hand_freq': {'call': 0.0012, 'raise': 0.0, 'allin': 0.9988, 'fold': 0.0},
        'call_pct': 0.0063, 'raise_pct': 0.0, 'allin_pct': 0.1425,
        'action_quality': 'unknown', 'in_range': False,
    }


def test_rec_becomes_call():
    b = _base()
    _normalize_facing_allin(b, 'fold')
    assert b['recommended_actions'] == ['call'], b['recommended_actions']
    print("OK  test_rec_becomes_call")


def test_hand_freq_folds_allin_into_call():
    """A freq exibida da mão não pode dizer 'allin' quando a recomendação virou 'call'."""
    b = _base()
    _normalize_facing_allin(b, 'fold')
    hf = b['hand_freq']
    assert hf['allin'] == 0.0 and hf['raise'] == 0.0, hf
    assert abs(hf['call'] - 1.0) < 1e-6, hf   # 0.0012 + 0.9988
    print("OK  test_hand_freq_folds_allin_into_call")


def test_aggregate_pcts_folded_into_call():
    b = _base()
    _normalize_facing_allin(b, 'fold')
    assert b['allin_pct'] == 0.0 and b['raise_pct'] == 0.0, b
    assert abs(b['call_pct'] - (0.0063 + 0.1425)) < 1e-6, b['call_pct']
    print("OK  test_aggregate_pcts_folded_into_call")


def test_call_of_the_shove_is_correct():
    """Pagar o all-in (ou shove redundante) com a mão no range agressivo = correto."""
    b = _base()
    _normalize_facing_allin(b, 'call')
    assert b['action_quality'] == 'correct' and b['in_range'] is True
    assert b['ev_loss_bb'] == 0.0
    print("OK  test_call_of_the_shove_is_correct")


def test_no_aggression_untouched():
    """GTO manda foldar → não há agressão a normalizar; frequências intactas."""
    b = {
        'available': True, 'recommended_actions': ['fold'],
        'hand_freq': {'call': 0.0, 'raise': 0.0, 'allin': 0.0, 'fold': 1.0},
        'call_pct': 0.0, 'allin_pct': 0.0, 'raise_pct': 0.0,
    }
    _normalize_facing_allin(b, 'fold')
    assert b['recommended_actions'] == ['fold']
    print("OK  test_no_aggression_untouched")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Total: {passed+failed} | Passed: {passed} | Failed: {failed}")
