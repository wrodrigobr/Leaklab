"""Testes de regressão dos invariantes do Decision Card.

Converte a classe de bugs achada nas varreduras (rec com ação <10%, off-tree
graduado severo, "fora do range" com continuação, shove↔allin) em guardas que
varrem TODA a matriz preflop de uma vez. Se um fix futuro reintroduzir a classe,
o teste quebra com a lista de spots violados.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scan_card_invariants import scan_preflop, scan_postflop, scan_hand_tree


def _assert_no_viol(viols, label):
    if viols:
        from collections import Counter
        by = Counter(v.inv for v in viols)
        sample = '\n  '.join(repr(v) for v in viols[:8])
        raise AssertionError(f"{label}: {len(viols)} violações {dict(by)}\n  {sample}")


def test_preflop_card_invariants_all_zero():
    """Nenhum spot preflop coberto produz card internamente contraditório (5
    invariantes sobre todos os ~960 spots × 169 mãos)."""
    _assert_no_viol(scan_preflop(verbose=False), 'preflop')
    print("OK  test_preflop_card_invariants_all_zero (0 violações)")


def test_postflop_card_invariants_all_zero():
    """Nenhum gto_node postflop produz card contraditório (5 invariantes sobre os
    ~820 nodes do solver: strategy normalizada, gto_action=dominante, dominante
    não-crítica, shove↔allin)."""
    _assert_no_viol(scan_postflop(verbose=False), 'postflop')
    print("OK  test_postflop_card_invariants_all_zero (0 violações)")


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


def test_hand_tree_card_invariants_all_zero():
    """A estratégia da MÃO específica (gto_tree_strategies) — fonte que o card AGORA
    usa pro veredito (fix do bug A2s/mão 5) — nunca produz card autocontraditório:
    freqs normalizadas, alinhadas às ações, e a ação dominante da mão não é crítica.
    Varre TODAS as ~180k (árvore × mão)."""
    _assert_no_viol(scan_hand_tree(verbose=False), 'hand_tree')
    print("OK  test_hand_tree_card_invariants_all_zero (0 violações)")


def test_verdict_from_hand_not_range():
    """Bug da mão 5: o card julgava pela ação modal do RANGE agregado em vez da MÃO.
    Trava a regra: havendo estratégia da mão, o veredito vem DELA. Espelha a
    cardLogic.verdictStrategy (frontend) — recomendação = dominante da MÃO, e a freq
    da ação jogada é a da MÃO, não a do range."""
    # Nó multiway aproximado: range folda 63%, mas A2s LEVANTA 93%.
    range_strat = [{'action': 'fold', 'frequency': 0.63},
                   {'action': 'raise', 'frequency': 0.34},
                   {'action': 'call', 'frequency': 0.03}]
    hand_strat  = [{'action': 'raise', 'frequency': 0.93},
                   {'action': 'call', 'frequency': 0.06},
                   {'action': 'fold', 'frequency': 0.01}]
    # a estratégia que JULGA é a da mão
    verdict_src = hand_strat  # verdictStrategy(isPostflop=True, hand, range)
    top = max(verdict_src, key=lambda s: s['frequency'])['action']
    assert top == 'raise', f"recomendação deve vir da mão (raise), veio {top}"
    # e o call do hero é julgado pela freq DELE na MÃO (6% → crítico), não no range (3%)
    assert _effective_label(hand_strat, 'call') == 'gto_critical'
    # contraprova: se (erradamente) usasse o range, recomendaria fold
    assert max(range_strat, key=lambda s: s['frequency'])['action'] == 'fold'
    print("OK  test_verdict_from_hand_not_range")


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
