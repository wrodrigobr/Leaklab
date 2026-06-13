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


# ── POSTFLOP: invariantes sobre os gto_nodes (strategy do solver) ─────────────
def _norm_pf(a: str) -> str:
    """Normaliza ação do solver: jam/shove/allin→allin; bet_Xbb→bet; raise_Xbb→raise."""
    s = (a or '').lower().replace('-', '').replace('_', '').replace(' ', '')
    if s in ('jam', 'shove', 'allin'):
        return 'allin'
    if s.startswith('bet'):
        return 'bet'
    if s.startswith('rai'):
        return 'raise'
    return s


def _effective_label_pf(strat_items, played):
    """Port do computeEffectiveGtoLabel (frontend) — unifica shove↔allin."""
    if not strat_items:
        return None
    pn = _norm_action_fe(played)
    freq = 0.0
    for act, f in strat_items:
        n = _norm_action_fe(act)
        if n == pn or pn.startswith(n) or n.startswith(pn):
            freq = float(f); break
    if freq >= 0.60: return 'gto_correct'
    if freq >= 0.30: return 'gto_mixed'
    if freq >= 0.10: return 'gto_minor_deviation'
    return 'gto_critical'


def _norm_action_fe(a: str) -> str:
    """Igual ao normAction do gtoUtils.ts (só unifica shove/jam/allin)."""
    s = (a or '').lower().replace('-', '').replace('_', '').replace(' ', '')
    if s in ('shove', 'jam', 'allin'):
        return 'allin'
    return s


def scan_postflop(verbose=False) -> list[Violation]:
    from database.schema import get_conn
    import json as _json
    c = get_conn()
    rows = c.execute("SELECT id, street, position, board, gto_action, strategy_json FROM gto_nodes").fetchall()
    viols = []
    for r in rows:
        d = dict(r)
        nid = d['id']; sj = d.get('strategy_json')
        def V(inv, detail):
            viols.append(Violation(inv, 'postflop', f'node#{nid}', '',
                                   d.get('street') or '', d.get('position') or '', detail))
        try:
            strat = _json.loads(sj) if sj else {}
        except Exception:
            V('pf_strategy_parse', f'strategy_json inválido'); continue
        # Dois formatos de strategy_json: flat {action:{frequency}} e aninhado
        # {strategy:{action:freq}, preflop_actions:...}. Usa o dict interno no aninhado.
        src = strat.get('strategy') if isinstance(strat, dict) and isinstance(strat.get('strategy'), dict) else strat
        items = []
        if isinstance(src, dict):
            for a, v in src.items():
                f = v.get('frequency', 0) if isinstance(v, dict) else v
                try:
                    items.append((a, float(f)))
                except (TypeError, ValueError):
                    continue
        if not items:
            continue
        tot = sum(f for _, f in items)
        # INV-P1 strategy normalizada (não all-zero / não duplo)
        if not (0.5 <= tot <= 1.5):
            V('pf_strategy_not_normalized', f'sum(freq)={tot:.3f} {strat}')
            continue
        # argmax (ação dominante)
        top_act, top_freq = max(items, key=lambda x: x[1])
        # INV-P2 gto_action armazenado == ação dominante da strategy (normalizado)
        ga = d.get('gto_action')
        if ga and _norm_pf(ga) != _norm_pf(top_act):
            V('pf_action_not_dominant', f'gto_action={ga} mas dominante={top_act}({top_freq:.2f})')
        # INV-P3 jogar a AÇÃO DOMINANTE não pode dar veredito crítico
        if _effective_label_pf(items, top_act) == 'gto_critical':
            V('pf_dominant_is_critical', f'dominante {top_act}({top_freq:.2f}) → gto_critical')
        # INV-P4 shove↔allin: se a dominante é allin, jogar SHOVE = correct (não crítico)
        if _norm_pf(top_act) == 'allin' and top_freq >= 0.60:
            lab = _effective_label_pf(items, 'shove')
            if lab != 'gto_correct':
                V('pf_shove_vs_allin', f'allin dominante {top_freq:.2f} mas shove→{lab} (esperado gto_correct)')
    if verbose:
        print(f'  postflop: {len(rows)} nodes varridos', file=sys.stderr)
    return viols


# ── HAND-TREE: invariantes sobre a estratégia da MÃO específica ───────────────
# O bug da mão 5 (A2s): o card julgava pela ação modal do RANGE agregado em vez da
# estratégia da MÃO. scan_postflop valida o nó agregado; este valida a tabela por mão
# (gto_tree_strategies) — a fonte que o card AGORA usa pro veredito. Garante que cada
# (árvore × mão) produz um card coerente: freqs normalizadas, dimensão certa, e jogar
# a própria ação dominante da mão nunca daria "DESVIO CRÍTICO".
def scan_hand_tree(verbose=False) -> list[Violation]:
    from database.schema import get_conn
    import json as _json
    c = get_conn()
    rows = c.execute(
        "SELECT tree_hash, board, actions, hand_table FROM gto_tree_strategies").fetchall()
    viols = []
    n_hands = 0
    for r in rows:
        d = dict(r)
        th = d['tree_hash']
        try:
            actions = _json.loads(d['actions']) if d.get('actions') else []
            table   = _json.loads(d['hand_table']) if d.get('hand_table') else []
        except Exception:
            viols.append(Violation('ht_parse', 'hand_tree', f'tree#{th}', '', '', '', 'json inválido'))
            continue
        if not actions or not table:
            continue
        bases = [_norm_pf(a) for a in actions]
        for ent in table:
            hand  = ent.get('hand', '')
            freqs = ent.get('freqs') or []
            def V(inv, detail, _h=hand):
                viols.append(Violation(inv, 'hand_tree', f'tree#{th}', '', '', _h, detail))
            # INV-H1 freqs alinhadas às ações da árvore
            if len(freqs) != len(actions):
                V('ht_len_mismatch', f'len(freqs)={len(freqs)} ≠ len(actions)={len(actions)}')
                continue
            tot = sum(float(f) for f in freqs)
            # INV-H2 estratégia da mão normalizada (não all-zero / não duplo)
            if not (0.5 <= tot <= 1.5):
                V('ht_not_normalized', f'sum(freqs)={tot:.3f} actions={actions}')
                continue
            # agrega por ação-base (igual ao handAgg do widget: bet_75pct+bet_1.1bb→bet)
            agg = {}
            for b, f in zip(bases, freqs):
                agg[b] = agg.get(b, 0.0) + float(f)
            n_hands += 1
            top_base = max(agg, key=lambda k: agg[k])
            top_freq = agg[top_base]
            # INV-H3 jogar a AÇÃO DOMINANTE da própria mão não pode dar veredito crítico.
            # (é a recomendação que o card mostra — se ela mesma cair em <10%, o card se
            #  autocontradiz: "GTO recomenda X" com X marcado DESVIO CRÍTICO.)
            if top_freq < 0.10:
                V('ht_dominant_critical',
                  f'dominante {top_base} freq={top_freq:.3f} (<10%) → card recomendaria ação crítica')
    if verbose:
        print(f'  hand_tree: {len(rows)} árvores, {n_hands} mãos varridas', file=sys.stderr)
    return viols


def main():
    show_samples = '--samples' in sys.argv
    viols = scan_preflop(verbose=True)
    viols += scan_postflop(verbose=True)
    viols += scan_hand_tree(verbose=True)
    by_inv = defaultdict(list)
    for v in viols:
        by_inv[v.inv].append(v)
    print('=' * 60)
    print(f'SCANNER DE INVARIANTES DO CARD — {len(viols)} violações')
    print('=' * 60)
    INV_DESC = {
        # preflop
        'hf_not_normalized':    'hand_freq all-zero / não normalizado (raiz off-tree)',
        'in_range_mismatch':    '"no range" vs continuação real (ex.: SB Call 100% «fora»)',
        'rec_low_freq':         'GTO recomenda ação de freq <10% (ex.: vs_rfi «Shove/Call»)',
        'rec_dominant_mismatch':'ação recomendada dominante ≠ maior freq (idealAction)',
        'fold_quality_too_harsh':'fold graduado mais severo que a freq justifica (off-tree)',
        # postflop (gto_nodes)
        'pf_strategy_parse':        'postflop: strategy_json inválido',
        'pf_strategy_not_normalized':'postflop: strategy do solver all-zero / não normalizada',
        'pf_action_not_dominant':   'postflop: gto_action armazenado ≠ ação dominante da strategy',
        'pf_dominant_is_critical':  'postflop: jogar a ação dominante daria DESVIO CRÍTICO',
        'pf_shove_vs_allin':        'postflop: shove num nó allin-dominante não é correct (shove↔allin)',
        # hand-tree (gto_tree_strategies) — fonte do veredito por mão
        'ht_parse':             'hand-tree: actions/hand_table json inválido',
        'ht_len_mismatch':      'hand-tree: freqs da mão desalinhadas das ações da árvore',
        'ht_not_normalized':    'hand-tree: estratégia da mão all-zero / não normalizada',
        'ht_dominant_critical': 'hand-tree: ação dominante da mão tem freq <10% (card recomendaria ação crítica)',
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
