"""fetch_pko_depth_slice.py — captura fatias (estágio, depth) EXPLÍCITAS do PKO,
cobrindo os 6 cenários numa única passada (multi-depth).

Para cada alvo (stage, depth) roda o pipeline na ordem de dependência, extraindo
os sizings em tempo real:
  RFI → open_codes
  vs_RFI → 3bet_codes ; squeeze → squeeze_codes
  vs_3bet → 4bet_codes
  vs_4bet (usa 4bet) ; faces_squeeze (usa squeeze)
Grava em pko_ranges[{field}p][stage]['ranges'][{round(depth)}bb][scenario] — bucket
de depth EXATO (evita colisão entre depths que cairiam no mesmo bucket coarse).

Reusa a geração de linha de fetch_pko_vsrfi_squeeze / fetch_pko_reraise.
Pré-req: túnel -L 8765 + Chrome logado (NÃO navegar durante a captura). Checkpoint
por fatia.

Uso: python -m scripts.fetch_pko_depth_slice --field 200 \
        --targets PCT50:60,PCT50:40,T3:35,T3:30,T3:25,T3:20
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except Exception:
    pass

from scripts.parse_gw_har import humanize_stage
from scripts.fetch_pko_ranges import gametype_for, _summary_from_strategy, merge_into, RFI_8MAX
from scripts.fetch_pko_vsrfi_squeeze import SEATS, vsrfi_lines, squeeze_lines
from scripts.fetch_pko_reraise import vs3bet_lines, vs4bet_lines, facessqueeze_lines, _spot_data, _rc

OUT = BACKEND_DIR / 'docs' / 'ranges_gto' / 'ko' / 'pko_ranges_pilot.json'


def _q(gw, gt, depth, pa, ftimeout):
    return gw.query_spot_raw(preflop_actions=pa, num_players=8, depth_bb=float(depth),
                             gametype=gt, include_strategy=True,
                             timeout=max(60, ftimeout + 30), fetch_timeout=ftimeout)


def capture_slice(gw, field, stage, depth, ftimeout, sleep_s):
    gt = gametype_for(field, stage)
    bucket = f"{round(depth)}bb"
    scens: dict = {}            # scenario -> nested dict
    counts: dict = {}
    m = {'open': {}, '3bet': {}, '4bet': {}, 'squeeze': {}}

    def put(section, k1, k2, sd):
        scens.setdefault(section, {}).setdefault(k1, {})[k2] = sd if k2 else None

    def fetch(pa, store_fn, code_into=None, code_key=None):
        r = _q(gw, gt, depth, pa, ftimeout)
        ok = bool(r and r.get('found'))
        if ok:
            store_fn(r)
            if code_into is not None:
                code_into[code_key] = _rc({'actions': [
                    {'code': a.get('code'), 'frequency': a.get('frequency')} for a in (r.get('strategy') or [])]})
        if sleep_s:
            time.sleep(sleep_s)
        return ok

    def sd_of(r, pa, extra=None):
        return _spot_data(r, pa, depth, gt, stage, extra)

    # 1) RFI
    n = tot = 0
    for pos, pa in RFI_8MAX:
        tot += 1
        r = _q(gw, gt, depth, pa, ftimeout)
        if r and r.get('found'):
            n += 1
            sd = sd_of(r, pa)
            scens.setdefault('RFI', {})[sd['hero']] = sd
            m['open'][sd['hero']] = _rc({'actions': sd['actions']})
        if sleep_s: time.sleep(sleep_s)
    counts['RFI'] = (n, tot)

    # 2) vs_RFI
    n = tot = 0
    for opener, defender, pa in vsrfi_lines(m['open']):
        tot += 1
        r = _q(gw, gt, depth, pa, ftimeout)
        if r and r.get('found'):
            n += 1; sd = sd_of(r, pa)
            scens.setdefault('vs_RFI', {}).setdefault(opener, {})[defender] = sd
            m['3bet'][(opener, defender)] = _rc({'actions': sd['actions']})
        if sleep_s: time.sleep(sleep_s)
    counts['vs_RFI'] = (n, tot)

    # 3) squeeze
    n = tot = 0
    for opener, caller, hero, pa in squeeze_lines(m['open']):
        tot += 1
        r = _q(gw, gt, depth, pa, ftimeout)
        if r and r.get('found'):
            n += 1; sd = sd_of(r, pa, {'caller_positions': [caller]})
            scens.setdefault('squeeze', {}).setdefault(hero, {})[opener] = sd
            m['squeeze'][(hero, opener)] = _rc({'actions': sd['actions']})
        if sleep_s: time.sleep(sleep_s)
    counts['squeeze'] = (n, tot)

    # 4) vs_3bet (precisa de open+3bet)
    n = tot = 0
    for spec in vs3bet_lines(m):
        tot += 1
        r = _q(gw, gt, depth, spec['pa'], ftimeout)
        if r and r.get('found'):
            n += 1; sd = sd_of(r, spec['pa'])
            _, k1, k2 = spec['key']
            scens.setdefault('vs_3bet', {}).setdefault(k1, {})[k2] = sd
            m['4bet'][(spec['opener'], spec['threeb'])] = _rc({'actions': sd['actions']})
        if sleep_s: time.sleep(sleep_s)
    counts['vs_3bet'] = (n, tot)

    # 5) vs_4bet (precisa de 4bet)
    n = tot = 0
    for spec in vs4bet_lines(m):
        tot += 1
        r = _q(gw, gt, depth, spec['pa'], ftimeout)
        if r and r.get('found'):
            n += 1; sd = sd_of(r, spec['pa'])
            _, k1, k2 = spec['key']
            scens.setdefault('vs_4bet', {}).setdefault(k1, {})[k2] = sd
        if sleep_s: time.sleep(sleep_s)
    counts['vs_4bet'] = (n, tot)

    # 6) faces_squeeze (precisa de squeeze)
    n = tot = 0
    for spec in facessqueeze_lines(m):
        tot += 1
        r = _q(gw, gt, depth, spec['pa'], ftimeout)
        if r and r.get('found'):
            n += 1; sd = sd_of(r, spec['pa'], spec.get('extra'))
            _, k1, k2 = spec['key']
            scens.setdefault('faces_squeeze', {}).setdefault(k1, {})[k2] = sd
        if sleep_s: time.sleep(sleep_s)
    counts['faces_squeeze'] = (n, tot)

    pko = {f'{field}p': {stage: {'_stage': humanize_stage(stage), 'ranges': {bucket: scens}}}}
    return pko, bucket, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--field', type=int, default=200)
    ap.add_argument('--targets', required=True, help='ex: PCT50:60,PCT50:40,T3:35,T3:30,T3:25,T3:20')
    ap.add_argument('--fetch-timeout', type=int, default=18)
    ap.add_argument('--sleep', type=float, default=0.3)
    ap.add_argument('--solver-url', default='http://localhost:8765')
    args = ap.parse_args()
    if args.solver_url:
        os.environ['GTO_SOLVER_URL'] = args.solver_url
    os.environ.setdefault('GTO_WIZARD_ENABLED', 'true')

    targets = []
    for t in args.targets.split(','):
        t = t.strip()
        if not t:
            continue
        st, d = t.split(':')
        targets.append((st.strip(), float(d)))

    import leaklab.gto_wizard_client as gw
    print(f"alvos: {targets}")
    for stage, depth in targets:
        t0_label = f"{stage}@{depth:.0f}bb"
        print(f"=== {t0_label} ===")
        pko, bucket, counts = capture_slice(gw, args.field, stage, depth, args.fetch_timeout, args.sleep)
        merged = merge_into(OUT, pko)
        OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
        line = ' '.join(f"{k}={v[0]}/{v[1]}" for k, v in counts.items())
        print(f"  {line}  (checkpoint {bucket})")
    print(f"\n✓ {OUT}")


if __name__ == '__main__':
    main()
