"""Auditoria dirigida à divergência range×mão (campo natural do bug A2s/mão 5).

Prova, em DADO REAL (gto_tree_strategies), que a reconciliação do card segue a
estratégia da MÃO, não a ação modal do range — exatamente onde eles divergem (28,5%
das mãos solved). Reconstrói as estratégias reais de cada árvore e roda o
reconcile_verdict de produção sobre elas.
"""
import sys, os, json, traceback
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leaklab.card_verdict import reconcile_verdict
from scripts.audit_multiway_divergence import audit_divergence, _base


def _trees():
    from database.schema import get_conn
    c = get_conn()
    return [dict(r) for r in c.execute(
        "SELECT tree_hash, actions, hand_table FROM gto_tree_strategies").fetchall()]


def _reconstruct(row):
    """(range_strat, [(hand, hand_strat, hand_top, range_top)]) reais da árvore."""
    actions = json.loads(row['actions']); table = json.loads(row['hand_table'])
    bases = [_base(a) for a in actions]
    agg = Counter()
    for ent in table:
        w = float(ent.get('weight') or 0.0) or 1.0
        freqs = ent.get('freqs') or []
        if len(freqs) != len(bases):
            continue
        for b, f in zip(bases, freqs):
            agg[b] += w * float(f)
    tot = sum(agg.values()) or 1.0
    range_strat = [{'action': b, 'frequency': v / tot} for b, v in agg.items()]
    range_top = max(agg.items(), key=lambda kv: kv[1])[0] if agg else None
    hands = []
    for ent in table:
        freqs = ent.get('freqs') or []
        if len(freqs) != len(bases):
            continue
        hagg = Counter()
        for b, f in zip(bases, freqs):
            hagg[b] += float(f)
        if not hagg:
            continue
        hand_strat = [{'action': b, 'frequency': v} for b, v in hagg.items()]
        hand_top = max(hagg.items(), key=lambda kv: kv[1])[0]
        hands.append((ent.get('hand', ''), hand_strat, hand_top, range_top))
    return range_strat, hands


def test_audit_runs_and_divergence_is_real():
    """O audit roda sobre o DB real e encontra divergência substancial (a tabela
    tem dados e a classe do bug é massiva — valida que o fix importa)."""
    divs, st = audit_divergence()
    assert st['hands'] > 1000, st
    assert st['divergent_hands'] > 0, st
    print(f"OK  test_audit_runs_and_divergence_is_real "
          f"({st['divergent_hands']}/{st['hands']} = {st['pct_hands']:.1f}% divergentes)")


def test_reconcile_segue_a_mao_em_nos_divergentes_reais():
    """Para CADA (árvore × mão) onde a modal da mão ≠ modal do range, a reconciliação
    de produção recomenda a ação DA MÃO — nunca a do range. Amostra real, cap 500."""
    checked = divergent = 0
    cap = 500
    for row in _trees():
        try:
            range_strat, hands = _reconstruct(row)
        except Exception:
            continue
        for hand, hand_strat, hand_top, range_top in hands:
            if hand_top == range_top:
                continue
            divergent += 1
            # joga a ação que o RANGE manda — a antiga lógica recomendaria isso de volta;
            # a correta recomenda a ação da MÃO.
            v = reconcile_verdict(range_strat, hand_strat, range_top)
            assert v is not None and v['source'] == 'hand'
            assert _base(v['live_top_act']) == hand_top, (
                row['tree_hash'][:8], hand, f'recomendou {v["live_top_act"]} esperado {hand_top}')
            checked += 1
            if checked >= cap:
                break
        if checked >= cap:
            break
    assert checked > 0, 'nenhum nó divergente encontrado para validar'
    print(f"OK  test_reconcile_segue_a_mao_em_nos_divergentes_reais "
          f"({checked} nós divergentes reais, todos seguiram a mão)")


def test_reconcile_freq_da_mao_nao_do_range():
    """played_freq do veredito é a freq da ação NA MÃO, não no range — pega o sintoma
    exato do bug (label crítico calculado pela freq errada)."""
    checked = 0
    for row in _trees():
        try:
            range_strat, hands = _reconstruct(row)
        except Exception:
            continue
        rmap = {d['action']: d['frequency'] for d in range_strat}
        for hand, hand_strat, hand_top, range_top in hands:
            if hand_top == range_top:
                continue
            hmap = {d['action']: d['frequency'] for d in hand_strat}
            # escolhe uma ação cuja freq na mão difere da do range
            for act in hmap:
                if abs(hmap.get(act, 0) - rmap.get(act, 0)) > 0.2:
                    v = reconcile_verdict(range_strat, hand_strat, act)
                    assert abs(v['played_freq'] - hmap[act]) < 1e-9, (hand, act, v, hmap)
                    checked += 1
                    break
            if checked >= 300:
                break
        if checked >= 300:
            break
    assert checked > 0
    print(f"OK  test_reconcile_freq_da_mao_nao_do_range ({checked} casos)")


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
