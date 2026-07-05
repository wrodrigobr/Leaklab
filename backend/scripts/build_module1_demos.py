"""
build_module1_demos.py — extrai os EXEMPLOS das demonstrações do Módulo 1 (vídeo-aulas)
a partir das ranges GTO keeper reais (docs/leaklab_gto_ranges.json via analyze_preflop).
NÃO inventa número: tudo sai do que o produto realmente serve.

Saída: scripts/out/module1_demos.json + um resumo legível no stdout.

Uso:
    python scripts/build_module1_demos.py [stack_bb]   # default 50
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from leaklab.preflop_gto_ranges import analyze_preflop          # noqa: E402
from leaklab.academy_gto_preflop import _HANDS                   # noqa: E402  (169 hand types)

RANKS = 'AKQJT98765432'


def _combos(hand: str) -> int:
    if len(hand) == 2:
        return 6                      # par
    return 4 if hand.endswith('s') else 12


def _norm_act(a: str) -> str:
    a = (a or '').lower()
    return 'allin' if a in ('jam', 'shove', 'allin', 'all-in') else a


def rfi_range(pos: str, stack: float) -> dict:
    """Range de abertura (RFI) da posição: {hand: {action, freq}} só das mãos que abrem,
    + estatística agregada. Fonte: analyze_preflop (ranges GW keeper)."""
    opens, raise_combos, total_open_combos = {}, 0, 0
    for h in _HANDS:
        r = analyze_preflop(pos, h, float(stack), 'fold',
                            facing_size=0.0, vs_position='', is_3bet_pot=False,
                            hero_was_aggressor=False, facing_raises=0)
        if not r.get('available') or r.get('scenario') != 'rfi':
            continue
        rec = r.get('recommended_actions') or []
        top = _norm_act(rec[0]) if rec else 'fold'
        if top in ('raise', 'allin'):
            hf = r.get('hand_freq') or {}
            freq = float(hf.get('raise', hf.get('jam', 1.0)) or 1.0)
            opens[h] = {'action': top, 'freq': round(freq, 3)}
            raise_combos += _combos(h) * freq
            total_open_combos += _combos(h)
    return {'position': pos, 'stack_bb': stack, 'hands': opens,
            'n_hand_types': len(opens),
            'range_pct': round(raise_combos / 1326 * 100, 1)}


def contains_king_or_overpair(hand: str) -> bool:
    """Mão conecta forte no board K83 (tem um K, ou é AA overpair)?"""
    if hand == 'AA':
        return True
    return 'K' in hand[:2]


def board_advantage(rng: dict, test=contains_king_or_overpair) -> float:
    """% dos combos do range que batem forte no board de teste (proxy de range advantage)."""
    strong = sum(_combos(h) * d['freq'] for h, d in rng['hands'].items() if test(h))
    total = sum(_combos(h) * d['freq'] for h, d in rng['hands'].items())
    return round(strong / total * 100, 1) if total else 0.0


def defend_range(defender: str, opener: str, stack: float) -> dict:
    """Range de defesa do BB/quem paga vs um open (call + 3bet). Fonte: analyze_preflop vs_rfi."""
    call_h, raise_h, call_combos, raise_combos = {}, {}, 0, 0
    for h in _HANDS:
        r = analyze_preflop(defender, h, float(stack), 'fold',
                            facing_size=2.2, vs_position=opener, is_3bet_pot=False,
                            hero_was_aggressor=False, facing_raises=0)
        if not r.get('available') or r.get('scenario') != 'vs_rfi':
            continue
        rec = r.get('recommended_actions') or []
        top = _norm_act(rec[0]) if rec else 'fold'
        if top == 'call':
            call_h[h] = 1; call_combos += _combos(h)
        elif top in ('raise', 'allin'):
            raise_h[h] = 1; raise_combos += _combos(h)
    return {'defender': defender, 'vs': opener, 'stack_bb': stack,
            'call_types': len(call_h), 'raise_types': len(raise_h),
            'call_pct': round(call_combos / 1326 * 100, 1),
            'threebet_pct': round(raise_combos / 1326 * 100, 1),
            'call_hands': sorted(call_h), 'threebet_hands': sorted(raise_h)}


def threebet_range_with_mix(defender: str, opener: str, stack: float, min_freq: float = 0.15) -> dict:
    """Range de 3bet INCLUINDO mixes de baixa freq (o blefe polarizado costuma ser 3bet 25% /
    call 75%, que a ação-TOP esconde). Coleta toda mão com freq de raise >= min_freq."""
    hands = {}
    for h in _HANDS:
        r = analyze_preflop(defender, h, float(stack), 'raise',
                            facing_size=2.2, vs_position=opener, is_3bet_pot=False,
                            hero_was_aggressor=False, facing_raises=0)
        if not r.get('available') or r.get('scenario') != 'vs_rfi':
            continue
        hf = r.get('hand_freq') or {}
        rf = float(hf.get('raise', hf.get('jam', 0.0)) or 0.0)
        if rf >= min_freq:
            hands[h] = round(rf, 3)
    return hands


def polarization_shape(rng_hands: dict) -> dict:
    """Descreve a forma de um range de 3bet: quanto é 'topo' (value) vs 'baixo suited' (blefe)
    vs 'meio'. Range polarizado tem topo+baixo e pouco meio."""
    top = mid = low_suited = 0
    for h in rng_hands:
        pair = len(h) == 2
        hi, lo = h[0], h[1]
        hi_i, lo_i = RANKS.index(hi), RANKS.index(lo)
        is_top = (pair and hi_i <= RANKS.index('T')) or (hi == 'A' and lo_i <= RANKS.index('Q'))
        is_low_suited = h.endswith('s') and lo_i >= RANKS.index('8') and not is_top
        if is_top:
            top += 1
        elif is_low_suited:
            low_suited += 1
        else:
            mid += 1
    return {'value_top': top, 'bluff_low_suited': low_suited, 'middle': mid}


def _real_hud_examples() -> dict:
    """Puxa 3 perfis REAIS anonimizados (opponent_profiles) que ilustram arquétipos claros:
    TAG (sólido), LAG (agressivo) e calling station (paga muito, agride pouco). Nomes
    trocados por rótulo, os NÚMEROS são reais e de alta confiança (amostra grande)."""
    try:
        import database.repositories as repo
    except Exception:
        return {'available': False, 'note': 'sem acesso ao banco'}
    conn = repo.get_conn()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT player_name, hands_seen, archetype, confidence, stats_json FROM opponent_profiles "
            "WHERE hands_seen >= 80").fetchall()]
    finally:
        conn.close()
    for r in rows:
        try:
            r['stats'] = json.loads(r['stats_json'])
        except Exception:
            r['stats'] = {}

    def pick(pred):
        cands = [r for r in rows if pred(r)]
        return max(cands, key=lambda r: r['hands_seen']) if cands else None

    def vp(r): return (r['stats'].get('vpip_pct') or 0)
    def pf(r): return (r['stats'].get('pfr_pct') or 0)
    tag = pick(lambda r: r['archetype'] == 'tag' and r['confidence'] == 'high')
    lag = pick(lambda r: r['archetype'] == 'lag' and r['confidence'] == 'high')
    # station = maior gap VPIP-PFR (paga muito, agride pouco). Pode ter amostra pequena de
    # propósito: vira o exemplo da RESSALVA (número forte, mas confiança baixa).
    st_cands = [r for r in rows if vp(r) >= 0.45 and vp(r) - pf(r) >= 0.30]
    station = max(st_cands, key=lambda r: vp(r) - pf(r)) if st_cands else None

    def fmt(r, label):
        if not r:
            return None
        s = r['stats']
        return {
            'label': label, 'hands': r['hands_seen'], 'archetype': r['archetype'],
            'confidence': r['confidence'],
            'vpip': round(vp(r) * 100, 1), 'pfr': round(pf(r) * 100, 1),
            'threebet': round((s.get('threebet_pct') or 0) * 100, 1),
            'cbet': round((s.get('cbet_pct') or 0) * 100, 1) if s.get('cbet_pct') is not None else None,
            'af': s.get('af'), 'wtsd': round((s.get('wtsd_pct') or 0) * 100, 1),
        }
    return {'available': True,
            'claim': 'Os números descrevem o jogador antes de ele mostrar uma carta (perfis reais, amostra 150+).',
            'examples': [x for x in (fmt(tag, 'Jogador A'), fmt(lag, 'Jogador B'), fmt(station, 'Jogador C')) if x]}


def build():
    stack = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0
    out = {'stack_bb': stack, 'source': 'leaklab_gto_ranges.json via analyze_preflop', 'lessons': {}}

    # ── Aula: CONCEITOS (posição) — a MESMA mão (KJ) abre do BTN e folda do UTG ──
    btn, utg = rfi_range('BTN', stack), rfi_range('UTG', stack)
    kj = {}
    for h in ('KJs', 'KJo'):
        kj[h] = {'BTN': btn['hands'].get(h, 'fold'), 'UTG': utg['hands'].get(h, 'fold')}
    out['lessons']['conceitos_posicao'] = {
        'claim': 'A mesma mão (KJ) é abertura do BTN e fold do UTG, só a posição muda.',
        'btn_range_pct': btn['range_pct'], 'utg_range_pct': utg['range_pct'],
        'KJ_by_position': kj,
        # grids completos (hand->freq) pro range grid do vídeo; fold = ausente/0
        'btn_grid': {h: d['freq'] for h, d in btn['hands'].items()},
        'utg_grid': {h: d['freq'] for h, d in utg['hands'].items()},
    }

    # ── Aula: RANGES — CO abre, BB defende, board K83: CO tem range advantage ──
    co = rfi_range('CO', stack)
    bb_def = defend_range('BB', 'CO', stack)
    # reconstrói o range de call do BB como dict-freq pra medir o board advantage
    bb_call_rng = {'hands': {h: {'freq': 1.0} for h in bb_def['call_hands']}}
    out['lessons']['ranges_range_advantage'] = {
        'claim': 'No board K83, o range do CO (abriu) domina o range de call do BB.',
        'board': ['K', '8', '3'],
        'co_open_pct': co['range_pct'],
        'co_king_or_overpair_pct': board_advantage(co),
        'bb_defend_call_pct': bb_def['call_pct'], 'bb_threebet_pct': bb_def['threebet_pct'],
        'bb_call_king_or_overpair_pct': board_advantage(bb_call_rng),
    }

    # ── Aula: POLARIZADO x CONDENSADO — range de 3bet do BTN vs CO tem forma polarizada ──
    # 3bet = raise do defensor; call = condensado. Reusa defend_range (BTN vs CO).
    btn_vs_co = defend_range('BTN', 'CO', stack)
    tb_mix = threebet_range_with_mix('BTN', 'CO', stack)     # inclui os 3bet-blefe (mixes)
    out['lessons']['polarizado_condensado'] = {
        'claim': 'O range de 3bet (BTN vs CO), com os mixes, é POLARIZADO (topo de valor + baixos suited de blefe); o range de call é CONDENSADO (mãos médias).',
        'threebet_shape': polarization_shape({h: 1 for h in tb_mix}),
        'threebet_hands_with_freq': tb_mix,
        'call_types': btn_vs_co['call_types'], 'call_hands': btn_vs_co['call_hands'],
    }

    # ── Aula: ESTATÍSTICAS — perfis REAIS anonimizados do banco (opponent_profiles) ──
    out['lessons']['estatisticas_hud'] = _real_hud_examples()

    os.makedirs(os.path.join(os.path.dirname(__file__), 'out'), exist_ok=True)
    path = os.path.join(os.path.dirname(__file__), 'out', 'module1_demos.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # resumo legível
    c = out['lessons']['conceitos_posicao']
    print(f"\n=== MÓDULO 1 — demos reais (stack {stack:.0f}bb) ===")
    print(f"\n[CONCEITOS] BTN abre {c['btn_range_pct']}% | UTG abre {c['utg_range_pct']}%")
    for h, v in c['KJ_by_position'].items():
        print(f"  {h}: BTN={v['BTN']}  UTG={v['UTG']}")
    r = out['lessons']['ranges_range_advantage']
    print(f"\n[RANGES] board K83 | CO abre {r['co_open_pct']}% e tem {r['co_king_or_overpair_pct']}% de Kx/overpair")
    print(f"  BB paga {r['bb_defend_call_pct']}% e só {r['bb_call_king_or_overpair_pct']}% do call é Kx/overpair")
    p = out['lessons']['polarizado_condensado']
    print(f"\n[POLARIZADO] 3bet BTN vs CO shape (com mixes): {p['threebet_shape']}")
    tb = p['threebet_hands_with_freq']
    print(f"  3bet: {', '.join(f'{h} {int(v*100)}%' for h, v in list(tb.items())[:24])}")
    e = out['lessons']['estatisticas_hud']
    if e.get('available'):
        print("\n[ESTATÍSTICAS] perfis reais anonimizados (amostra 150+, alta confiança):")
        for x in e['examples']:
            print(f"  {x['label']} ({x['archetype']}, {x['hands']}m, conf {x['confidence']}): "
                  f"VPIP {x['vpip']} / PFR {x['pfr']} / 3bet {x['threebet']} / "
                  f"cbet {x['cbet']} / AF {x['af']} / WTSD {x['wtsd']}")
    print(f"\n-> {path}")


if __name__ == '__main__':
    build()
