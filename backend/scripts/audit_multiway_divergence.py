"""Auditoria dirigida: divergência entre a ação modal do RANGE agregado e a da MÃO
específica, em cada árvore solved (gto_tree_strategies).

É a impressão digital do bug A2s/mão 5: onde a modal do range ≠ modal da mão, a lógica
ANTIGA do card recomendava a ação errada. Este audit mede a MAGNITUDE em dado real
(quantas (árvore × mão) eram mis-recomendadas) e lista os casos mais extremos — os nós
multiway aproximados são os campeões de divergência (solver é HU).

Uso:  python -m scripts.audit_multiway_divergence [--samples N]
Programático:  from scripts.audit_multiway_divergence import audit_divergence
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, '.')
from collections import Counter


def _base(a: str) -> str:
    """Ação-base: jam/shove/allin→allin; bet_*→bet; raise_*→raise; resto inalterado."""
    s = (a or '').lower().replace('-', '').replace('_', '').replace(' ', '')
    if s in ('jam', 'shove', 'allin'):
        return 'allin'
    if s.startswith('bet'):
        return 'bet'
    if s.startswith('rai'):
        return 'raise'
    return s


class Divergence:
    __slots__ = ('tree', 'hand', 'range_top', 'range_freq', 'hand_top', 'hand_freq', 'gap')
    def __init__(self, tree, hand, rt, rf, ht, hf):
        self.tree, self.hand = tree, hand
        self.range_top, self.range_freq = rt, rf
        self.hand_top, self.hand_freq = ht, hf
        self.gap = hf  # freq da ação que a mão realmente quer (peso do erro evitado)
    def __repr__(self):
        return (f'{self.tree[:8]} {self.hand}: range→{self.range_top}({self.range_freq:.0%}) '
                f'mão→{self.hand_top}({self.hand_freq:.0%})')


def audit_divergence():
    """Retorna (divs, stats). divs = list[Divergence] (mão_top ≠ range_top)."""
    from database.schema import get_conn
    c = get_conn()
    rows = c.execute(
        "SELECT tree_hash, actions, hand_table FROM gto_tree_strategies").fetchall()
    divs = []
    n_trees = n_hands = 0
    trees_with_div = 0
    for r in rows:
        d = dict(r)
        try:
            actions = json.loads(d['actions']) if d.get('actions') else []
            table   = json.loads(d['hand_table']) if d.get('hand_table') else []
        except Exception:
            continue
        if not actions or not table:
            continue
        n_trees += 1
        bases = [_base(a) for a in actions]

        # modal do RANGE agregado = soma ponderada por weight de (freq) por ação-base
        agg = Counter()
        for ent in table:
            w = float(ent.get('weight') or 0.0) or 1.0
            freqs = ent.get('freqs') or []
            if len(freqs) != len(bases):
                continue
            for b, f in zip(bases, freqs):
                agg[b] += w * float(f)
        if not agg:
            continue
        tot_w = sum(agg.values()) or 1.0
        range_top, range_w = max(agg.items(), key=lambda kv: kv[1])
        range_freq = range_w / tot_w

        # modal de cada MÃO
        tree_has_div = False
        for ent in table:
            freqs = ent.get('freqs') or []
            if len(freqs) != len(bases):
                continue
            hand = ent.get('hand', '')
            hagg = Counter()
            for b, f in zip(bases, freqs):
                hagg[b] += float(f)
            if not hagg:
                continue
            n_hands += 1
            hand_top, hand_f = max(hagg.items(), key=lambda kv: kv[1])
            if hand_top != range_top:
                divs.append(Divergence(d['tree_hash'], hand, range_top, range_freq, hand_top, hand_f))
                tree_has_div = True
        if tree_has_div:
            trees_with_div += 1

    stats = {
        'trees': n_trees, 'trees_with_divergence': trees_with_div,
        'hands': n_hands, 'divergent_hands': len(divs),
        'pct_hands': (100.0 * len(divs) / n_hands) if n_hands else 0.0,
    }
    return divs, stats


def main():
    n_samples = 20
    if '--samples' in sys.argv:
        try:
            n_samples = int(sys.argv[sys.argv.index('--samples') + 1])
        except Exception:
            pass
    divs, st = audit_divergence()
    print('=' * 64)
    print('AUDITORIA — divergência range×mão (impressão digital do bug A2s)')
    print('=' * 64)
    print(f"árvores solved:        {st['trees']}")
    print(f"árvores com divergência:{st['trees_with_divergence']}")
    print(f"mãos varridas:         {st['hands']}")
    print(f"mãos divergentes:      {st['divergent_hands']} ({st['pct_hands']:.1f}%)")
    print(f"  → sob a lógica ANTIGA, essas {st['divergent_hands']} mãos recebiam a")
    print(f"    recomendação do range em vez da própria mão. Hoje vêm da mão.")
    # divergências mais extremas: mão quer X com alta freq, range manda outra
    divs_sorted = sorted(divs, key=lambda x: x.hand_freq, reverse=True)
    by_pair = Counter((x.range_top, x.hand_top) for x in divs)
    print('\nTop pares range→mão:')
    for (rt, ht), n in by_pair.most_common(8):
        print(f'  range {rt:>6} → mão {ht:<6}: {n}')
    print(f'\n{n_samples} divergências mais extremas (mão muito decidida, range diverge):')
    for x in divs_sorted[:n_samples]:
        print(f'  {x}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
