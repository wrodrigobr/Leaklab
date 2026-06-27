"""
Invariante do veredito: qualquer indício de erro de DIREÇÃO (GTO folda a mão mas hero agrediu)
⇒ a mão NUNCA pode ser 'standard'/'marginal' (não-erro). Cobre o sinal canônico
(is_verdict_error_signal) + a rede de segurança da reconciliação (_reconcile_label).
Regressão do caso KTo UTG (decisão 36471).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from database.repositories import is_verdict_error_signal, _reconcile_label


def test_signal_gto_fold_aggressive():
    assert is_verdict_error_signal('fold', 'raise') is True
    assert is_verdict_error_signal('fold', 'shove') is True
    assert is_verdict_error_signal('fold', 'bet') is True
    print("OK  test_signal_gto_fold_aggressive")


def test_signal_correct_actions_not_flagged():
    assert is_verdict_error_signal('fold', 'fold') is False     # foldar quando GTO folda = correto
    assert is_verdict_error_signal('raise', 'raise') is False   # agride quando GTO agride = correto
    assert is_verdict_error_signal('fold', 'call') is False     # call não-agressivo (depende do gto_label)
    print("OK  test_signal_correct_actions_not_flagged")


def test_signal_freq_zero_aggressive():
    assert is_verdict_error_signal('raise', 'bet', played_freq=0.0) is True   # bet com freq ~0
    assert is_verdict_error_signal('call', 'bet', played_freq=0.30) is False  # freq alta = ok
    print("OK  test_signal_freq_zero_aggressive")


def test_reconcile_floors_kto_case():
    # KTo UTG (36471): raise quando GTO folda, gto_label leniente → DEVE virar small_mistake.
    assert _reconcile_label('marginal', 'gto_minor_deviation', street='preflop',
                            action_taken='raise', gto_action='fold') == 'small_mistake'
    print("OK  test_reconcile_floors_kto_case")


def test_reconcile_floors_gto_critical():
    assert _reconcile_label('marginal', 'gto_critical', street='preflop',
                            action_taken='raise', gto_action='fold') == 'small_mistake'
    print("OK  test_reconcile_floors_gto_critical")


def test_reconcile_preserves_legit_mix():
    # gto_mixed: a agressão pode ser co-ótima → NÃO pune (não vira erro).
    assert _reconcile_label('standard', 'gto_mixed', street='preflop',
                            action_taken='raise', gto_action='fold') == 'standard'
    print("OK  test_reconcile_preserves_legit_mix")


def test_reconcile_keeps_existing_higher_severity():
    # Se já era clear_mistake, não rebaixa.
    assert _reconcile_label('clear_mistake', 'gto_minor_deviation', street='preflop',
                            action_taken='raise', gto_action='fold') == 'clear_mistake'
    print("OK  test_reconcile_keeps_existing_higher_severity")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = failed = 0
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            import traceback; traceback.print_exc(); failed += 1
    print(f"\n{'='*50}\nTotal: {passed+failed} | Passed: {passed} | Failed: {failed}")
    sys.exit(1 if failed else 0)
