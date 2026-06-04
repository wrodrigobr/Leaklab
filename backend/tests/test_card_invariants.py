"""Testes de regressão dos invariantes do Decision Card.

Converte a classe de bugs achada nas varreduras (rec com ação <10%, off-tree
graduado severo, "fora do range" com continuação, shove↔allin) em guardas que
varrem TODA a matriz preflop de uma vez. Se um fix futuro reintroduzir a classe,
o teste quebra com a lista de spots violados.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scan_card_invariants import scan_preflop


def test_preflop_card_invariants_all_zero():
    """Nenhum spot coberto produz card internamente contraditório (5 invariantes
    sobre todos os ~960 spots × 169 mãos)."""
    viols = scan_preflop(verbose=False)
    if viols:
        from collections import Counter
        by = Counter(v.inv for v in viols)
        sample = '\n  '.join(repr(v) for v in viols[:8])
        raise AssertionError(
            f"{len(viols)} violações de invariante de card: {dict(by)}\n  {sample}")
    print(f"OK  test_preflop_card_invariants_all_zero ({0} violações)")


# ── shove↔allin (postflop): port da lógica do computeEffectiveGtoLabel ────────
def _norm_action(a: str) -> str:
    s = (a or '').lower().replace('-', '').replace('_', '').replace(' ', '')
    if s in ('shove', 'jam', 'allin'):
        return 'allin'
    return s


def _effective_label(strategy, played):
    if not strategy:
        return None
    pn = _norm_action(played)
    freq = 0.0
    for s in strategy:
        n = _norm_action(s.get('action'))
        if n == pn or pn.startswith(n) or n.startswith(pn):
            freq = float(s.get('frequency', 0)); break
    if freq >= 0.60: return 'gto_correct'
    if freq >= 0.30: return 'gto_mixed'
    if freq >= 0.10: return 'gto_minor_deviation'
    return 'gto_critical'


def test_shove_matches_allin_strategy_not_critical():
    """Um shove num nó cuja estratégia é Allin-dominante deve ser CORRETO, não
    falso 'DESVIO CRÍTICO' (o bug do shove↔allin não normalizado)."""
    strat = [{'action': 'allin', 'frequency': 0.96}, {'action': 'check', 'frequency': 0.04}]
    assert _effective_label(strat, 'shove') == 'gto_correct'
    assert _effective_label(strat, 'jam') == 'gto_correct'
    assert _effective_label(strat, 'allin') == 'gto_correct'
    # e o inverso: shove num nó que é check 100% segue crítico (correto)
    assert _effective_label([{'action': 'check', 'frequency': 1.0}], 'shove') == 'gto_critical'
    print("OK  test_shove_matches_allin_strategy_not_critical")


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
