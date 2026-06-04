"""Scanner de invariantes do Decision Card.

Em vez de varrer card a card visualmente, roda TODA a matriz preflop coberta
(cada section × hero × villain × bucket × 169 mãos) pelo `analyze_preflop` e
verifica invariantes de consistência interna do output que o card renderiza.
Cada invariante codifica uma classe de bug já encontrada nas varreduras, pra
virar lista finita de violações + teste de regressão.

Uso: python -m scripts.scan_card_invariants            (resumo)
     python -m scripts.scan_card_invariants --samples  (com exemplos)

Programático: from scripts.scan_card_invariants import scan_preflop -> list[Violation]
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, '.')
from collections import defaultdict
from leaklab.preflop_gto_ranges import analyze_preflop, _RANGES_FILE

# 169 mãos canônicas
_RANKS = 'AKQJT98765432'
def _all_hands():
    out = []
    for i, hi in enumerate(_RANKS):
        for j, lo in enumerate(_RANKS):
            if i == j:   out.append(hi + lo)            # par
            elif i < j:  out.append(hi + lo + 's')      # suited
            else:        out.append(lo + hi + 'o')      # offsuit
    return sorted(set(out))
ALL_HANDS = _all_hands()

# mapa ação(rec) -> chave em hand_freq
_ACT2HF = {'jam': 'allin', 'allin': 'allin', 'shove': 'allin',
           'call': 'call', 'raise': 'raise', 'fold': 'fold'}

# sections do JSON -> (scenario, nível de aninhamento [hero] ou [hero][villain])
_SECTIONS = {
    'RFI':            'rfi',
    'vs_RFI':         'vs_rfi',
    'vs_3bet':        'vs_3bet',
    'squeeze':        'squeeze',
    'faces_squeeze':  'faces_squeeze',
    'vs_4bet':        'vs_4bet',
}
_POS_ORDER = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def _bucket_stack(bucket: str) -> float:
    try:
        return float(bucket.replace('bb', ''))
    except Exception:
        return 20.0


def _build_kwargs(scenario, hero, villain, stack, hand):
    """Inputs que roteiam o analyze_preflop pro cenário+spot exato. action='fold'
    (a freq da mão é independente da ação; checamos a qualidade do fold também)."""
    base = dict(position=hero, hero_hand_type=hand, stack_bb=stack,
                action_taken='fold', n_players=9, facing_limp=False)
    if scenario == 'rfi':
        base.update(facing_size=0.0, vs_position='', is_3bet_pot=False,
                    facing_raises=0, hero_was_aggressor=False, caller_position='')
    elif scenario == 'vs_rfi':
        base.update(facing_size=2.2, vs_position=villain, is_3bet_pot=False,
                    facing_raises=1, hero_was_aggressor=False, caller_position='')
    elif scenario == 'vs_3bet':
        base.update(facing_size=6.0, vs_position=villain, is_3bet_pot=True,
                    facing_raises=1, hero_was_aggressor=True, caller_position='')
    elif scenario == 'faces_squeeze':
        base.update(facing_size=8.0, vs_position=villain, is_3bet_pot=False,
                    facing_raises=2, hero_was_aggressor=False, caller_position='')
    elif scenario == 'squeeze':
        caller = next((p for p in _POS_ORDER if p not in (hero, villain)), 'BB')
        base.update(facing_size=2.2, vs_position=villain, is_3bet_pot=True,
                    facing_raises=1, hero_was_aggressor=True, caller_position=caller)
    elif scenario == 'vs_4bet':
        base.update(facing_size=12.0, vs_position=villain, is_3bet_pot=False,
                    facing_raises=2, hero_was_aggressor=True, caller_position='')
    return base


_SEV = {'correct': 0, 'acceptable': 1, 'leak': 2, 'major_leak': 3, 'unknown': 0}


class Violation:
    __slots__ = ('inv', 'scenario', 'hero', 'villain', 'bucket', 'hand', 'detail')
    def __init__(self, inv, scenario, hero, villain, bucket, hand, detail):
        self.inv, self.scenario, self.hero, self.villain = inv, scenario, hero, villain
        self.bucket, self.hand, self.detail = bucket, hand, detail
    def __repr__(self):
        v = f'/{self.villain}' if self.villain else ''
        return f'{self.scenario} {self.hero}{v} @{self.bucket} {self.hand}: {self.detail}'


def _check(scenario, hero, villain, bucket, hand, res) -> list[Violation]:
    """As 5 invariantes do card sobre o output do analyze_preflop (action='fold')."""
    out = []
    def V(inv, detail): out.append(Violation(inv, scenario, hero, villain, bucket, hand, detail))
    if not res.get('available'):
        return out  # sem cobertura = card honesto "sem veredito", sem invariantes
    hf = res.get('hand_freq') or {}
    rec = res.get('recommended_actions') or []
    in_rng = bool(res.get('in_range'))
    quality = res.get('action_quality')

    tot = sum(float(v) for v in hf.values())
    # INV-1 hand_freq normalizado (não all-zero, não duplo) — raiz do off-tree
    if not (0.5 <= tot <= 1.5):
        V('hf_not_normalized', f'sum(hand_freq)={tot:.3f} hf={hf}')
        return out  # demais checks ficam sem sentido

    cont = sum(float(hf.get(a, 0)) for a in ('call', 'raise', 'allin'))
    # INV-2 só a DIREÇÃO do bug: continuação significativa (≥10%) mas marcado "fora do
    # range" (ex.: SB-complete Call 100% → in_range=False). Continuação ~0% com
    # in_range=True é inofensivo (mão de peso minúsculo no range, não é contradição).
    if cont >= 0.10 and not in_rng:
        V('in_range_mismatch', f'continuação={cont:.3f} mas in_range=False hf={hf}')

    # INV-3 toda ação recomendada tem freq >= 10% (exceto o fallback ['fold'])
    if rec and rec != ['fold']:
        for a in rec:
            f = float(hf.get(_ACT2HF.get(a, a), 0))
            if f < 0.10:
                V('rec_low_freq', f'rec={rec}: {a} freq={f:.3f} (<10%) hf={hf}')
                break

    # INV-4 ação recomendada dominante == ação de maior freq (idealAction certo)
    if rec and rec != ['fold']:
        top = _ACT2HF.get(rec[0], rec[0])
        argmax = max(('call', 'raise', 'allin', 'fold'), key=lambda k: float(hf.get(k, 0)))
        if float(hf.get(top, 0)) + 1e-9 < float(hf.get(argmax, 0)):
            V('rec_dominant_mismatch',
              f'rec[0]={rec[0]}(freq {hf.get(top,0):.3f}) < argmax={argmax}(freq {hf.get(argmax,0):.3f})')

    # INV-5 qualidade do FOLD não pode ser mais SEVERA que a freq de fold justifica
    # (pega off-tree: fold puro 100% graduado major_leak). Softening pode ser mais brando.
    ff = float(hf.get('fold', 0))
    exp = 'correct' if ff >= 0.30 else 'acceptable' if ff >= 0.10 else 'leak' if ff >= 0.03 else 'major_leak'
    if _SEV.get(quality, 0) > _SEV.get(exp, 0):
        V('fold_quality_too_harsh', f'fold_freq={ff:.3f} esperado≤{exp} mas veio {quality} hf={hf}')
    return out


def scan_preflop(verbose=False) -> list[Violation]:
    data = json.load(open(_RANGES_FILE, encoding='utf-8'))
    ranges = data.get('ranges', {})
    violations = []
    n_calls = 0
    for bucket, secs in ranges.items():
        if not isinstance(secs, dict):
            continue
        stack = _bucket_stack(bucket)
        for sec_name, scenario in _SECTIONS.items():
            sec = secs.get(sec_name)
            if not isinstance(sec, dict):
                continue
            for hero, lvl in sec.items():
                if not isinstance(lvl, dict):
                    continue
                # RFI = [hero]->spot; demais = [hero][villain]->spot
                spots = [('', lvl)] if 'hand_freqs' in lvl else list(lvl.items())
                for villain, spot in spots:
                    if not isinstance(spot, dict) or 'hand_freqs' not in spot:
                        continue
                    for hand in ALL_HANDS:
                        kw = _build_kwargs(scenario, hero, villain, stack, hand)
                        res = analyze_preflop(**kw)
                        n_calls += 1
                        # só checa quando o roteamento bateu no cenário esperado
                        if res.get('scenario') != scenario:
                            continue
                        violations.extend(_check(scenario, hero, villain, bucket, hand, res))
        if verbose:
            print(f'  ...{bucket} varrido', file=sys.stderr)
    if verbose:
        print(f'  total analyze_preflop: {n_calls}', file=sys.stderr)
    return violations


def main():
    show_samples = '--samples' in sys.argv
    viols = scan_preflop(verbose=True)
    by_inv = defaultdict(list)
    for v in viols:
        by_inv[v.inv].append(v)
    print('=' * 60)
    print(f'SCANNER DE INVARIANTES DO CARD — {len(viols)} violações')
    print('=' * 60)
    INV_DESC = {
        'hf_not_normalized':    'hand_freq all-zero / não normalizado (raiz off-tree)',
        'in_range_mismatch':    '"no range" vs continuação real (ex.: SB Call 100% «fora»)',
        'rec_low_freq':         'GTO recomenda ação de freq <10% (ex.: vs_rfi «Shove/Call»)',
        'rec_dominant_mismatch':'ação recomendada dominante ≠ maior freq (idealAction)',
        'fold_quality_too_harsh':'fold graduado mais severo que a freq justifica (off-tree)',
    }
    if not viols:
        print('OK 0 violações — todos os invariantes do card mantidos.')
    for inv in INV_DESC:
        lst = by_inv.get(inv, [])
        mark = 'OK' if not lst else 'XX'
        print(f'{mark} [{inv}] {INV_DESC[inv]}: {len(lst)}')
        if show_samples:
            for v in lst[:6]:
                print(f'      {v}')
    return len(viols)


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
