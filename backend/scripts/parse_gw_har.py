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
import re
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

# 8-max nativo (PKO do GW é 8-max): pula UTG+2. Confirmado no HAR real — ação
# pós-UTG+1 → next_position=LJ. Index = ordem do assento a partir de UTG.
EIGHTMAX_SEAT = {0: 'UTG', 1: 'UTG+1', 2: 'LJ', 3: 'HJ', 4: 'CO', 5: 'BTN', 6: 'SB', 7: 'BB'}


def seat_map(table_size: int) -> dict:
    """index do assento (a partir de UTG) → posição, por table size."""
    if table_size == 8:
        return EIGHTMAX_SEAT
    return NINEMAX_TO_8MAX  # 9-max (Classic) é o default


def humanize_stage(token: str) -> str:
    """Token de estágio PKO do gametype → rótulo legível. Tolerante a tokens novos.

    Confirmados nos HARs: START, PCT50, BUBBLEMID, FT. Os demais (PCT90/70/37(5)/25,
    Ntables) seguem a mesma gramática e são derivados por regex — sem hardcode frágil.
    """
    t = (token or '').upper()
    if t == 'START':
        return '100% left'
    if t == 'FT':
        return 'final table'
    if t in ('BUBBLEMID', 'BUBBLE', 'NEARBUBBLE', 'NEAR_BUBBLE'):
        return 'near bubble'
    m = re.match(r'PCT(\d+)$', t)
    if m:
        n = m.group(1)
        if n == '375':
            return '37.5% left'
        return f'{int(n)}% left'
    m = re.match(r'(\d+)TABLES?$', t)
    if m:
        return f'{m.group(1)} tables'
    return token  # desconhecido: preserva cru (nunca perde info)


def parse_gametype(gametype: str) -> dict:
    """`MTTGeneral_ICMPKO8m200PTSTART` → estrutura PKO. Classic → is_pko False.

    Gramática: MTTGeneral_ICMPKO{table}m{field}PT{STAGE}.
      table  = jogadores na mesa (8)
      field  = campo inicial do torneio (200 ou 1000)
      STAGE  = fase (START/PCT90/PCT70/PCT50/PCT375/PCT25/BUBBLEMID/2TABLES/3TABLES/FT)
    """
    m = re.search(r'ICMPKO(\d+)m(\d+)PT([A-Z0-9_]+)$', gametype or '')
    if not m:
        return {'is_pko': False, 'table_size': None, 'field_size': None,
                'stage_token': None, 'stage': None, 'gametype': gametype}
    return {
        'is_pko':      True,
        'table_size':  int(m.group(1)),
        'field_size':  int(m.group(2)),
        'stage_token': m.group(3),
        'stage':       humanize_stage(m.group(3)),
        'gametype':    gametype,
    }


def classify_spot(preflop_actions: str, table_size: int = 9) -> dict:
    """Categoriza um spot por padrão de preflop_actions.

    `table_size` escolhe o mapa de assentos (9-max Classic ou 8-max PKO).
    Retorna {'scenario': str, 'hero_pos': str|None, 'vs_pos': str|None, 'extra': dict}.
    Scenarios:
        rfi          — hero abre (só Fs antes)
        vs_rfi       — hero defende open (Fs + R2 + Fs, hero decide)
        threbet      — quem 3-beta? hero já fez raise no spot vs_rfi (acessível via mesmo response)
        vs_3bet      — hero abriu, foi 3-betado, decide (Fs + R2_hero + Fs + R3+_villain + Fs)
        squeeze      — open + call(s) + hero decide (Fs + R2 + C + opt_C + Fs)
        other        — tudo o mais (4-bet+, multiway complexo)
    """
    smap = seat_map(table_size)
    parts = preflop_actions.split('-') if preflop_actions else []

    # RFI: só Fs antes
    if all(p == 'F' for p in parts):
        n_folds = len(parts)
        hero_pos = smap.get(n_folds)
        return {'scenario': 'rfi', 'hero_pos': hero_pos, 'vs_pos': None, 'extra': {}}

    # Conta raises e calls
    raises = [(i, p) for i, p in enumerate(parts) if p.startswith('R')]
    calls  = [(i, p) for i, p in enumerate(parts) if p == 'C']
    folds  = [(i, p) for i, p in enumerate(parts) if p == 'F']

    if len(raises) == 1 and not calls:
        # vs_RFI: 1 raise (opener), hero decide depois
        opener_idx = raises[0][0]
        hero_idx   = len(parts)
        return {
            'scenario': 'vs_rfi',
            'hero_pos':  smap.get(hero_idx),
            'vs_pos':    smap.get(opener_idx),
            'extra': {}
        }

    if len(raises) == 2 and not calls:
        # vs_3bet: opener raise, villain 3-bet, hero (= opener) decide.
        # Após 3-bet, o next-to-act é sempre o opener original (que foi raised over).
        opener_idx = raises[0][0]
        threbettor_idx = raises[1][0]
        return {
            'scenario': 'vs_3bet',
            'hero_pos': smap.get(opener_idx),   # opener volta a decidir
            'vs_pos':   smap.get(threbettor_idx),
            'extra': {'opener': opener_idx, 'threbettor': threbettor_idx}
        }

    if len(raises) == 1 and len(calls) >= 1:
        # Squeeze: 1 open + 1+ calls + hero decide
        opener_idx = raises[0][0]
        caller_idxs = [c[0] for c in calls]
        hero_idx = len(parts)
        return {
            'scenario': 'squeeze',
            'hero_pos': smap.get(hero_idx),
            'vs_pos':   smap.get(opener_idx),
            'extra': {'caller_positions': [smap.get(i) for i in caller_idxs]}
        }

    if len(raises) == 3 and not calls:
        # vs_4bet: opener raise, 3-bettor raise, opener raise novamente (4-bet), 3-bettor decide
        opener_idx     = raises[0][0]
        threbettor_idx = raises[1][0]
        # O 3º raise está no idx N (next slot) — mas o ator real é o opener (volta a agir após 3-bet)
        # Logo o 4-better é SEMPRE o opener original
        return {
            'scenario': 'vs_4bet',
            'hero_pos': smap.get(threbettor_idx),  # 3-bettor decide vs 4-bet
            'vs_pos':   smap.get(opener_idx),       # 4-better = opener original
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


def extract_hand_freqs(counters: dict) -> dict:
    """Extrai mapa {hand_name: {action_code: freq}} preservando apenas mãos não-fold-puras.

    Usado pra renderização precisa por mão (em vez de % global do range).
    Skip mãos onde freq fold = 1.0 (não-jogadas) pra reduzir tamanho do JSON.
    """
    out = {}
    for hand, info in counters.items():
        freqs = info.get('actions_total_frequencies', {})
        if not freqs:
            continue
        # Skip mãos com fold = 1.0 (puramente foldadas) — não acrescentam info
        if freqs.get('F', 0) > 0.999:
            continue
        # Salva só ações com freq > 0 (compacta JSON)
        non_zero = {code: round(f, 4) for code, f in freqs.items() if f > 0.0001}
        if non_zero:
            out[hand] = non_zero
    return out


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
        'stacks':      params.get('stacks', [''])[0],
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
        # Freq exata por mão (estilo GTO Wizard): {hand: {action_code: freq}}
        # Permite renderização precisa por mão na barra stacked do Decision Card.
        'hand_freqs':  extract_hand_freqs(counters),
    }


def _count_spots(obj) -> int:
    """Conta folhas de spot (dicts com hand_freqs/preflop_actions) numa subárvore,
    independente da profundidade de aninhamento do scenario."""
    if isinstance(obj, dict):
        if 'preflop_actions' in obj and 'hand_freqs' in obj:
            return 1
        return sum(_count_spots(v) for v in obj.values())
    return 0


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


def _store_spot(ranges_root: dict, other_list: list, bucket: str, cls: dict, spot_data: dict) -> None:
    """Roteia um spot parseado para a árvore ranges[bucket][scenario]... ou _other.

    Compartilhado entre o caminho Classic (9-max) e o PKO (8-max) — mesma
    topologia de saída, só a raiz e o table_size mudam.
    """
    scenario = cls['scenario']
    hero_pos = cls['hero_pos']
    vs_pos   = cls['vs_pos']
    if scenario == 'rfi' and hero_pos:
        ranges_root.setdefault(bucket, {}).setdefault('RFI', {})[hero_pos] = spot_data
    elif scenario == 'vs_rfi' and hero_pos and vs_pos:
        # ranges[bucket][vs_RFI][opener][defender]
        ranges_root.setdefault(bucket, {}).setdefault('vs_RFI', {}).setdefault(vs_pos, {})[hero_pos] = spot_data
    elif scenario == 'vs_3bet' and hero_pos and vs_pos:
        # ranges[bucket][vs_3bet][opener_hero][3bettor_villain]
        ranges_root.setdefault(bucket, {}).setdefault('vs_3bet', {}).setdefault(hero_pos, {})[vs_pos] = spot_data
    elif scenario == 'vs_4bet' and hero_pos and vs_pos:
        # ranges[bucket][vs_4bet][3bettor_hero][4bettor_villain]
        ranges_root.setdefault(bucket, {}).setdefault('vs_4bet', {}).setdefault(hero_pos, {})[vs_pos] = spot_data
    elif scenario == 'squeeze' and hero_pos and vs_pos:
        # ranges[bucket][squeeze][hero][opener] — caller positions no extra
        spot_data['caller_positions'] = cls['extra'].get('caller_positions', [])
        ranges_root.setdefault(bucket, {}).setdefault('squeeze', {}).setdefault(hero_pos, {})[vs_pos] = spot_data
    else:
        spot_data = dict(spot_data)
        spot_data['scenario'] = scenario
        spot_data['extra'] = cls['extra']
        other_list.append(spot_data)


def build_ranges_json(all_spots: list[dict]) -> dict:
    """Agrupa spots por stack/cenário e gera JSON pronto pro engine.

    Classic (9-max) → `ranges[bucket][scenario]...` (intacto).
    PKO    (8-max)  → `pko_ranges[{field}p][stage]['ranges'][bucket][scenario]...`,
                      mesma topologia interna — o engine reaproveita o lookup Classic.
    """
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
        'pko_ranges': {},    # [field][stage] -> {_stage, _other, ranges{bucket{scenario}}}
    }

    # Contadores por categoria
    counters = {'rfi': 0, 'vs_rfi': 0, 'vs_3bet': 0, 'squeeze': 0, '4bet_or_higher': 0, 'other': 0, 'vs_3bet_other': 0}
    pko_spots = 0

    for s in all_spots:
        parsed = parse_spot(s['data'], s['params'])
        gt = parse_gametype(parsed['gametype'])
        bucket = depth_to_bucket(parsed['depth'])

        # PKO é 8-max; Classic 9-max. table_size vem do gametype, fallback p/ n_stacks.
        if gt['is_pko']:
            table_size = gt['table_size'] or len([x for x in parsed['stacks'].split('-') if x])
        else:
            table_size = 9
        cls = classify_spot(parsed['preflop_actions'], table_size=table_size)
        scenario = cls['scenario']
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
            'hand_freqs':  parsed['hand_freqs'],
        }

        if gt['is_pko']:
            # PKO: bounty embutido na estratégia pelo solver; guardamos stacks/stage
            # pra estágios de stack heterogêneo (PCT50/FT = aproximação ICM).
            spot_data['stage']    = gt['stage']
            spot_data['gametype'] = parsed['gametype']
            spot_data['stacks']   = parsed['stacks']
            node = out['pko_ranges'].setdefault(f"{gt['field_size']}p", {}).setdefault(
                gt['stage_token'], {'_stage': gt['stage'], '_other': [], 'ranges': {}})
            _store_spot(node['ranges'], node['_other'], bucket, cls, spot_data)
            pko_spots += 1
        else:
            _store_spot(out['ranges'], out['_other_spots'], bucket, cls, spot_data)

    out['_metadata']['scenarios'] = counters
    out['_metadata']['spots_rfi'] = counters['rfi']
    out['_metadata']['spots_other'] = sum(v for k, v in counters.items() if k != 'rfi')
    out['_metadata']['total_spots'] = sum(counters.values())
    out['_metadata']['pko_spots'] = pko_spots
    if not out['pko_ranges']:
        out.pop('pko_ranges')
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
    if result.get('ranges'):
        print(f"\nCoverage vs_RFI (defender × opener, 9-max = 36 pairs/stack):")
        for bucket in sorted(result['ranges'].keys(), key=lambda x: int(x.replace('bb', ''))):
            vs_rfi = result['ranges'][bucket].get('vs_RFI', {})
            if not vs_rfi:
                continue
            n_pairs = sum(len(defs) for defs in vs_rfi.values())
            opener_list = list(vs_rfi.keys())
            print(f"  {bucket}: {n_pairs}/36 pairs (openers: {','.join(opener_list)})")

    # Coverage PKO (8-max) — field → stage → bucket → scenarios
    pko = result.get('pko_ranges') or {}
    if pko:
        print(f"\nPKO ranges (8-max) — {meta.get('pko_spots', 0)} spots:")
        for field in sorted(pko.keys()):
            print(f"  campo {field}:")
            for stage_tok, node in pko[field].items():
                rng = node['ranges']
                scen_counts: dict = {}
                for b, scens in rng.items():
                    for sc, subtree in scens.items():
                        scen_counts[sc] = scen_counts.get(sc, 0) + _count_spots(subtree)
                buckets = ','.join(sorted(rng.keys(), key=lambda x: int(x.replace('bb', ''))))
                scen_str = ', '.join(f"{k}={v}" for k, v in scen_counts.items()) or '—'
                other_n = len(node.get('_other', []))
                print(f"    {stage_tok:11} ({node['_stage']:12}) buckets=[{buckets}] | {scen_str} | other={other_n}")


if __name__ == '__main__':
    main()
