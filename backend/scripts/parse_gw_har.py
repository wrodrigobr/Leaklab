"""
parse_gw_har.py — Extrai ranges GTO de um HAR exportado do GTO Wizard.

Lê HAR (DevTools → Network → Export HAR), filtra requests `/spot-solution/`,
parseia frequências por ação e gera JSON estruturado pronto pro engine.

Uso:
    python scripts/parse_gw_har.py <arquivo.har>
    python scripts/parse_gw_har.py docs/ranges_har.har --output docs/gw_v3.json

Suporta múltiplos HARs (concatena dedup por URL):
    python scripts/parse_gw_har.py har1.har har2.har har3.har
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BACKEND_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR    = BACKEND_DIR / "docs"

# Ordem canônica das 169 mãos no array `strategy` do GW.
# Linha = card1, Coluna = card2. Diagonal=pares, acima=suited, abaixo=offsuit.
RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

POSITIONS_9MAX = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
# Aliases nossos (engine usa MP1/MP2 ou MP genérico em 8-max)
POSITIONS_OUT  = ['UTG', 'MP', 'LJ', 'HJ', 'CO', 'BTN', 'SB']  # BB não tem RFI


def hand_name(row: int, col: int) -> str:
    if row == col:
        return f"{RANKS[row]}{RANKS[row]}"
    elif row < col:
        return f"{RANKS[row]}{RANKS[col]}s"
    else:
        return f"{RANKS[col]}{RANKS[row]}o"


def strategy_to_hands(strategy: list) -> list[str]:
    """DEPRECATED — ordem do array `strategy` no GW não é trivial.
    Use simple_hand_counters do response em vez disso (parse_spot_v2)."""
    return []


def hands_from_counters(counters: dict, action_code: str) -> tuple[list[str], float]:
    """Extrai mãos com freq > 0 pra uma action_code específica do simple_hand_counters.

    Retorna (lista_de_mãos, frequência_média_ponderada).
    """
    if not counters:
        return [], 0.0
    hands_in = []
    total_combos = 0.0
    action_combos = 0.0
    for hand_name_str, h in counters.items():
        freqs = h.get('actions_total_frequencies', {})
        combos = h.get('total_combos', 0)
        total_combos += combos
        f = freqs.get(action_code, 0)
        if f > 0.001:
            hands_in.append(hand_name_str)
            action_combos += combos * f
    avg_freq = action_combos / total_combos if total_combos > 0 else 0
    return hands_in, round(avg_freq, 4)


# 9-max nativo (mantém todas posições — engine pode mapear 9→8 na leitura se necessário)
NINEMAX_TO_8MAX = {0: 'UTG', 1: 'UTG+1', 2: 'UTG+2', 3: 'LJ', 4: 'HJ', 5: 'CO', 6: 'BTN', 7: 'SB', 8: 'BB'}
EIGHTMAX_TO_9MAX = {'UTG': 0, 'UTG+1': 1, 'UTG+2': 2, 'LJ': 3, 'HJ': 4, 'CO': 5, 'BTN': 6, 'SB': 7, 'BB': 8}
POSITIONS_9MAX_LIST = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def classify_spot(preflop_actions: str) -> dict:
    """Categoriza um spot por padrão de preflop_actions.

    Retorna {'scenario': str, 'hero_pos': str|None, 'vs_pos': str|None, 'extra': dict}.
    Scenarios:
        rfi          — hero abre (só Fs antes)
        vs_rfi       — hero defende open (Fs + R2 + Fs, hero decide)
        threbet      — quem 3-beta? hero já fez raise no spot vs_rfi (acessível via mesmo response)
        vs_3bet      — hero abriu, foi 3-betado, decide (Fs + R2_hero + Fs + R3+_villain + Fs)
        squeeze      — open + call(s) + hero decide (Fs + R2 + C + opt_C + Fs)
        other        — tudo o mais (4-bet+, multiway complexo)
    """
    parts = preflop_actions.split('-') if preflop_actions else []

    # RFI: só Fs antes
    if all(p == 'F' for p in parts):
        n_folds = len(parts)
        hero_pos = NINEMAX_TO_8MAX.get(n_folds)
        return {'scenario': 'rfi', 'hero_pos': hero_pos, 'vs_pos': None, 'extra': {}}

    # Conta raises e calls
    raises = [(i, p) for i, p in enumerate(parts) if p.startswith('R')]
    calls  = [(i, p) for i, p in enumerate(parts) if p == 'C']
    folds  = [(i, p) for i, p in enumerate(parts) if p == 'F']

    if len(raises) == 1 and not calls:
        # vs_RFI: 1 raise (opener), hero decide depois
        opener_idx_9max = raises[0][0]
        hero_idx_9max   = len(parts)
        return {
            'scenario': 'vs_rfi',
            'hero_pos':  NINEMAX_TO_8MAX.get(hero_idx_9max),
            'vs_pos':    NINEMAX_TO_8MAX.get(opener_idx_9max),
            'extra': {}
        }

    if len(raises) == 2 and not calls:
        # vs_3bet: opener raise, villain 3-bet, hero (= opener) decide.
        # Após 3-bet, o next-to-act é sempre o opener original (que foi raised over).
        opener_idx = raises[0][0]
        threbettor_idx = raises[1][0]
        return {
            'scenario': 'vs_3bet',
            'hero_pos': NINEMAX_TO_8MAX.get(opener_idx),   # opener volta a decidir
            'vs_pos':   NINEMAX_TO_8MAX.get(threbettor_idx),
            'extra': {'opener': opener_idx, 'threbettor': threbettor_idx}
        }

    if len(raises) == 1 and len(calls) >= 1:
        # Squeeze: 1 open + 1+ calls + hero decide
        opener_idx = raises[0][0]
        caller_idxs = [c[0] for c in calls]
        hero_idx = len(parts)
        return {
            'scenario': 'squeeze',
            'hero_pos': NINEMAX_TO_8MAX.get(hero_idx),
            'vs_pos':   NINEMAX_TO_8MAX.get(opener_idx),
            'extra': {'caller_positions': [NINEMAX_TO_8MAX.get(i) for i in caller_idxs]}
        }

    if len(raises) == 3 and not calls:
        # vs_4bet: opener raise, 3-bettor raise, opener raise novamente (4-bet), 3-bettor decide
        opener_idx     = raises[0][0]
        threbettor_idx = raises[1][0]
        # O 3º raise está no idx N (next slot) — mas o ator real é o opener (volta a agir após 3-bet)
        # Logo o 4-better é SEMPRE o opener original
        return {
            'scenario': 'vs_4bet',
            'hero_pos': NINEMAX_TO_8MAX.get(threbettor_idx),  # 3-bettor decide vs 4-bet
            'vs_pos':   NINEMAX_TO_8MAX.get(opener_idx),       # 4-better = opener original
            'extra': {'opener': opener_idx, '3bettor': threbettor_idx,
                      '4bettor_action_idx': raises[2][0]}
        }

    if len(raises) >= 4:
        return {'scenario': '5bet_or_higher', 'hero_pos': None, 'vs_pos': None,
                'extra': {'raises': len(raises), 'preflop_actions': preflop_actions}}

    return {'scenario': 'other', 'hero_pos': None, 'vs_pos': None,
            'extra': {'preflop_actions': preflop_actions}}


def position_from_preflop_actions(preflop_actions: str) -> str | None:
    """
    preflop_actions vazio → UTG decidir
    "F" → UTG+1 (= MP no nosso esquema 8-max)
    "F-F" → UTG+2 (= LJ se 9-max contém UTG+2; mapeamos pra LJ no 8-max)
    ...

    Em 9-max do GW: UTG (0 folds), UTG+1 (1 fold), UTG+2 (2 folds), LJ, HJ, CO, BTN, SB.
    Mapeamento nosso (8-max): UTG, MP, LJ, HJ, CO, BTN, SB.
    """
    if not preflop_actions:
        # UTG é quem decide (sem ações antes)
        return 'UTG'
    # Conta quantos F consecutivos no início
    parts = preflop_actions.split('-')
    if not all(p == 'F' for p in parts):
        # Tem RAISE ou CALL no meio — não é RFI puro, é vs_RFI/3bet/etc
        return None
    n_folds = len(parts)
    # 9-max GW: UTG=0F, UTG+1=1F, UTG+2=2F, LJ=3F, HJ=4F, CO=5F, BTN=6F, SB=7F
    # Mapeamento determinístico 9-max → 8-max:
    #   0F  → UTG (UTG real)
    #   1F  → MP (UTG+1 do 9-max é nosso "MP" único)
    #   2F  → None (UTG+2 não existe em 8-max — descarta pra não sobrescrever LJ)
    #   3F  → LJ (LJ real do 9-max)
    #   4F  → HJ
    #   5F  → CO
    #   6F  → BTN
    #   7F  → SB
    return {0: 'UTG', 1: 'MP', 3: 'LJ', 4: 'HJ', 5: 'CO', 6: 'BTN', 7: 'SB'}.get(n_folds)


def parse_spot(raw: dict, params: dict) -> dict:
    """Extrai summary de uma response /spot-solution/.

    Usa simple_hand_counters do hero (mapeamento por nome da mão, confiável).
    """
    # Encontra hero — quem decide
    counters = {}
    for p in raw.get('players_info', []):
        if p.get('player', {}).get('is_hero'):
            counters = p.get('simple_hand_counters', {}) or {}
            break

    actions = []
    raise_set: set = set()
    allin_set: set = set()
    call_set:  set = set()
    fold_set:  set = set()
    check_set: set = set()
    raise_pct = 0.0
    allin_pct = 0.0
    call_pct  = 0.0
    fold_pct  = 0.0
    check_pct = 0.0

    for sol in raw.get('action_solutions', []):
        act = sol.get('action', {})
        atype = act.get('type', '')
        allin = act.get('allin', False)
        code  = act.get('code', '')
        freq  = sol.get('total_frequency', 0)

        hands_list, _ = hands_from_counters(counters, code)

        actions.append({
            'type':     atype,
            'code':     code,
            'betsize':  act.get('betsize'),
            'allin':    allin,
            'frequency': round(freq, 4),
            'hand_count': len(hands_list),
            'hands':    ','.join(sorted(hands_list)) if hands_list else '',
        })

        if atype == 'FOLD':
            fold_set = set(hands_list)
            fold_pct = round(freq, 4)
        elif atype == 'CALL':
            call_set |= set(hands_list)
            call_pct = round(call_pct + freq, 4)
        elif atype == 'CHECK':
            check_set |= set(hands_list)
            check_pct = round(check_pct + freq, 4)
        elif atype == 'RAISE':
            if allin:
                allin_set |= set(hands_list)
                allin_pct = round(allin_pct + freq, 4)
            else:
                raise_set |= set(hands_list)
                raise_pct = round(raise_pct + freq, 4)

    open_pct = round(raise_pct + allin_pct, 4)

    return {
        'gametype':    params.get('gametype', [''])[0],
        'depth':       float(params.get('depth', ['0'])[0]),
        'preflop_actions': params.get('preflop_actions', [''])[0],
        'actions_summary': actions,
        'raise_pct':   raise_pct,
        'allin_pct':   allin_pct,
        'call_pct':    call_pct,
        'check_pct':   check_pct,
        'open_pct':    open_pct,
        'fold_pct':    fold_pct,
        'raise_hands': ','.join(sorted(raise_set)) if raise_set else '',
        'allin_hands': ','.join(sorted(allin_set)) if allin_set else '',
        'call_hands':  ','.join(sorted(call_set)) if call_set else '',
        'check_hands': ','.join(sorted(check_set)) if check_set else '',
        'fold_hands':  ','.join(sorted(fold_set)) if fold_set else '',
    }


def depth_to_bucket(depth: float) -> str:
    """20.125 → '20bb' (bucket compatível com nosso JSON)."""
    BUCKETS = [10, 14, 17, 20, 30, 40, 50, 75, 100]
    # Snap pro bucket mais próximo
    best = min(BUCKETS, key=lambda b: abs(b - depth))
    return f"{best}bb"


def process_har(har_path: Path) -> list[dict]:
    """Retorna lista de spots parseados de um HAR. Tolera HARs truncados."""
    try:
        with open(har_path, encoding='utf-8') as f:
            har = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  [SKIP] {har_path.name}: JSON inválido/truncado ({e})")
        return []
    except Exception as e:
        print(f"  [SKIP] {har_path.name}: erro de leitura ({e})")
        return []
    spots = []
    seen_urls = set()
    for entry in har.get('log', {}).get('entries', []):
        req = entry.get('request', {})
        if req.get('method') != 'GET':
            continue
        url = req.get('url', '')
        if '/v4/solutions/spot-solution/' not in url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        body = entry.get('response', {}).get('content', {}).get('text', '')
        if not body:
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        params = parse_qs(urlparse(url).query)
        spots.append({'url': url, 'params': params, 'data': data})
    return spots


def build_ranges_json(all_spots: list[dict]) -> dict:
    """Agrupa spots por stack/cenário e gera JSON pronto pro engine."""
    out = {
        '_metadata': {
            'source': 'gtowizard_api_v4_via_har',
            'gametype': 'MTTGeneralV2',
            'parsed_at': datetime.now().isoformat(),
            'total_spots': 0,
            'spots_rfi': 0,
            'spots_other': 0,
        },
        'ranges': {},
        '_other_spots': [],  # vs_RFI, 3bet, etc — bucketed mas não promovidos pra RFI
    }

    # Contadores por categoria
    counters = {'rfi': 0, 'vs_rfi': 0, 'vs_3bet': 0, 'squeeze': 0, '4bet_or_higher': 0, 'other': 0, 'vs_3bet_other': 0}

    for s in all_spots:
        parsed = parse_spot(s['data'], s['params'])
        bucket = depth_to_bucket(parsed['depth'])
        cls = classify_spot(parsed['preflop_actions'])
        scenario = cls['scenario']
        hero_pos = cls['hero_pos']
        vs_pos = cls['vs_pos']

        counters[scenario] = counters.get(scenario, 0) + 1

        # Estrutura comum dos dados
        spot_data = {
            'open_pct':    parsed['open_pct'],
            'raise_pct':   parsed['raise_pct'],
            'allin_pct':   parsed['allin_pct'],
            'call_pct':    parsed['call_pct'],
            'check_pct':   parsed['check_pct'],
            'fold_pct':    parsed['fold_pct'],
            'raise_hands': parsed['raise_hands'],
            'allin_hands': parsed['allin_hands'],
            'call_hands':  parsed['call_hands'],
            'check_hands': parsed['check_hands'],
            'fold_hands':  parsed['fold_hands'],
            'actions':     parsed['actions_summary'],
            'preflop_actions': parsed['preflop_actions'],
        }

        if scenario == 'rfi' and hero_pos:
            out['ranges'].setdefault(bucket, {}).setdefault('RFI', {})[hero_pos] = spot_data
        elif scenario == 'vs_rfi' and hero_pos and vs_pos:
            # Estrutura: ranges[bucket][vs_RFI][opener][defender]
            out['ranges'].setdefault(bucket, {}).setdefault('vs_RFI', {}).setdefault(vs_pos, {})[hero_pos] = spot_data
        elif scenario == 'vs_3bet' and hero_pos and vs_pos:
            # ranges[bucket][vs_3bet][opener_hero][3bettor_villain]
            out['ranges'].setdefault(bucket, {}).setdefault('vs_3bet', {}).setdefault(hero_pos, {})[vs_pos] = spot_data
        elif scenario == 'vs_4bet' and hero_pos and vs_pos:
            # ranges[bucket][vs_4bet][3bettor_hero][4bettor_villain]
            out['ranges'].setdefault(bucket, {}).setdefault('vs_4bet', {}).setdefault(hero_pos, {})[vs_pos] = spot_data
        elif scenario == 'squeeze' and hero_pos and vs_pos:
            # ranges[bucket][squeeze][hero][opener] — caller positions estão no extra
            spot_data['caller_positions'] = cls['extra'].get('caller_positions', [])
            out['ranges'].setdefault(bucket, {}).setdefault('squeeze', {}).setdefault(hero_pos, {})[vs_pos] = spot_data
        else:
            spot_data['scenario'] = scenario
            spot_data['extra'] = cls['extra']
            out['_other_spots'].append(spot_data)

    out['_metadata']['scenarios'] = counters
    out['_metadata']['spots_rfi'] = counters['rfi']
    out['_metadata']['spots_other'] = sum(v for k, v in counters.items() if k != 'rfi')
    out['_metadata']['total_spots'] = sum(counters.values())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('hars', nargs='+', help='Arquivos HAR para processar')
    ap.add_argument('--output', default=str(DOCS_DIR / 'leaklab_gto_ranges_gw_v3.json'))
    args = ap.parse_args()

    all_spots = []
    for har_path_str in args.hars:
        har_path = Path(har_path_str)
        if not har_path.exists():
            print(f"AVISO: {har_path} não encontrado")
            continue
        spots = process_har(har_path)
        print(f"  {har_path.name}: {len(spots)} spots /spot-solution/")
        all_spots.extend(spots)

    print(f"\nTotal spots brutos: {len(all_spots)}")
    if not all_spots:
        print("Nada pra processar.")
        return

    result = build_ranges_json(all_spots)
    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    meta = result['_metadata']
    print(f"\n✓ Salvo em {output_path}")
    print(f"\nSpots por cenário:")
    for sc, n in meta.get('scenarios', {}).items():
        if n > 0:
            print(f"  {sc:20s} {n}")
    print(f"\nCoverage RFI:")
    for bucket in sorted(result['ranges'].keys(), key=lambda x: int(x.replace('bb', ''))):
        positions = list(result['ranges'][bucket].get('RFI', {}).keys())
        print(f"  {bucket}: {len(positions)}/7 ({','.join(positions)})")

    # Coverage vs_RFI (9-max: 36 pairs por stack)
    print(f"\nCoverage vs_RFI (defender × opener, 9-max = 36 pairs/stack):")
    for bucket in sorted(result['ranges'].keys(), key=lambda x: int(x.replace('bb', ''))):
        vs_rfi = result['ranges'][bucket].get('vs_RFI', {})
        if not vs_rfi:
            continue
        n_pairs = sum(len(defs) for defs in vs_rfi.values())
        opener_list = list(vs_rfi.keys())
        print(f"  {bucket}: {n_pairs}/36 pairs (openers: {','.join(opener_list)})")


if __name__ == '__main__':
    main()
