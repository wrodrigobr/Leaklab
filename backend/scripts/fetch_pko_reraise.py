"""fetch_pko_reraise.py — captura vs_3bet / vs_4bet / faces_squeeze PKO (8-max).

Cenários de re-raise: cada nível de raise tem um sizing que importa, extraído das
capturas anteriores:
  open  ← RFI[opener]
  3bet  ← vs_RFI[opener][3bettor]   (ação de raise do defensor)
  4bet  ← vs_3bet[opener][3bettor]  (ação de raise do opener; precisa vs_3bet ANTES)
  squeeze ← squeeze[squeezer][opener]

Linhas (validadas live):
  vs_3bet [opener][3bettor]:  open + 3bet + folds-back        hero=opener
  vs_4bet [3bettor][opener]:  open + 3bet + folds + 4bet      hero=3bettor
  faces_squeeze [caller][sqz]: open + call + squeeze + opener-fold  hero=caller
                              (opener fixo = UTG, representativo)

Uso: python -m scripts.fetch_pko_reraise --scenario vs_3bet   # depois vs_4bet / faces_squeeze
Pré-req: túnel -L 8765 + Chrome logado. Checkpoint por estágio.
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

from scripts.parse_gw_har import depth_to_bucket, humanize_stage
from scripts.fetch_pko_ranges import gametype_for, _summary_from_strategy, merge_into

OUT = BACKEND_DIR / 'docs' / 'ranges_gto' / 'ko' / 'pko_ranges_pilot.json'
SEATS = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def _rc(sd):
    """Código de raise dominante (não-RAI) de um spot_data, ou None."""
    rs = [a['code'] for a in sd.get('actions', [])
          if a.get('code') and a['code'].startswith('R') and a['code'] != 'RAI']
    return rs[0] if rs else None


def load_meta(field=200):
    """Por estágio: depth, bucket e códigos de sizing (open/3bet/4bet/squeeze)."""
    pr = json.loads(OUT.read_text(encoding='utf-8'))['pko_ranges'][f'{field}p']
    meta = {}
    for stage, node in pr.items():
        depth = None
        rng = node['ranges']
        bucket = next(iter(rng))
        scens = rng[bucket]
        opens, tbet, fbet, sqz = {}, {}, {}, {}
        for hero, sd in scens.get('RFI', {}).items():
            opens[hero] = _rc(sd); depth = sd.get('depth')
        for op, defs in scens.get('vs_RFI', {}).items():
            for de, sd in defs.items():
                tbet[(op, de)] = _rc(sd)
        for op, defs in scens.get('vs_3bet', {}).items():
            for tb, sd in defs.items():
                fbet[(op, tb)] = _rc(sd)
        for sq, ops in scens.get('squeeze', {}).items():
            for op, sd in ops.items():
                sqz[(sq, op)] = _rc(sd)
        meta[stage] = {'depth': depth, 'bucket': bucket,
                       'open': opens, '3bet': tbet, '4bet': fbet, 'squeeze': sqz}
    return meta


def _spot_data(r, pa, depth, gt, stage, extra=None):
    raw_hf = r.get('raw_hand_freqs') or r.get('hand_freqs') or {}
    sd = {
        'hero': r.get('hero_position'), 'preflop_actions': pa, 'depth': float(depth),
        'gametype': gt, 'stage': humanize_stage(stage),
        'actions': [{'code': a.get('code'), 'frequency': round(float(a.get('frequency') or 0), 4),
                     'betsize_bb': a.get('betsize_bb')} for a in (r.get('strategy') or [])],
        'hand_freqs': raw_hf, **_summary_from_strategy(r.get('strategy')),
    }
    if extra:
        sd.update(extra)
    return sd


def vs3bet_lines(m):
    for oi in range(7):
        op = SEATS[oi]; oc = m['open'].get(op)
        if not oc:
            continue
        for ti in range(oi + 1, 8):
            tb = SEATS[ti]; tc = m['3bet'].get((op, tb))
            if not tc:
                continue
            pa = '-'.join(['F'] * oi + [oc] + ['F'] * (ti - oi - 1) + [tc] + ['F'] * (7 - ti))
            yield {'opener': op, 'threeb': tb, 'pa': pa, 'key': ('vs_3bet', op, tb)}


def vs4bet_lines(m):
    for oi in range(7):
        op = SEATS[oi]; oc = m['open'].get(op)
        if not oc:
            continue
        for ti in range(oi + 1, 8):
            tb = SEATS[ti]; tc = m['3bet'].get((op, tb)); fc = m['4bet'].get((op, tb))
            if not (tc and fc):
                continue
            pa = '-'.join(['F'] * oi + [oc] + ['F'] * (ti - oi - 1) + [tc] + ['F'] * (7 - ti) + [fc])
            yield {'opener': op, 'threeb': tb, 'pa': pa, 'key': ('vs_4bet', tb, op)}


def facessqueeze_lines(m):
    oi = 0  # opener fixo = UTG (representativo; faces_squeeze keyed por [caller][squeezer])
    op = SEATS[oi]; oc = m['open'].get(op)
    if not oc:
        return
    for ci in range(oi + 1, 7):
        caller = SEATS[ci]
        for si in range(ci + 1, 8):
            sqz = SEATS[si]; sc = m['squeeze'].get((sqz, op))
            if not sc:
                continue
            pa = '-'.join(['F'] * oi + [oc] + ['F'] * (ci - oi - 1) + ['C']
                          + ['F'] * (si - ci - 1) + [sc] + ['F'] * (7 - si) + ['F'])
            yield {'opener': op, 'caller': caller, 'sqz': sqz, 'pa': pa,
                   'key': ('faces_squeeze', caller, sqz), 'extra': {'caller_positions': [caller]}}


LINES = {'vs_3bet': vs3bet_lines, 'vs_4bet': vs4bet_lines, 'faces_squeeze': facessqueeze_lines}


def run(scenario, fetch_timeout, sleep_s, only, field=200):
    import leaklab.gto_wizard_client as gw
    meta = load_meta(field)
    stages = [s for s in meta if not only or s in only]
    grid = {}
    for stage in stages:
        m = meta[stage]
        depth, bucket = m['depth'], m['bucket']
        gt = gametype_for(field, stage)
        pko = {}
        node = pko.setdefault(f'{field}p', {}).setdefault(
            stage, {'_stage': humanize_stage(stage), 'ranges': {}})
        ok = tot = 0
        print(f"=== {stage} ({humanize_stage(stage)}) @ {depth:.0f}bb ===")
        for spec in LINES[scenario](m):
            tot += 1
            r = gw.query_spot_raw(preflop_actions=spec['pa'], num_players=8, depth_bb=float(depth),
                                  gametype=gt, include_strategy=True,
                                  timeout=max(60, fetch_timeout + 30), fetch_timeout=fetch_timeout)
            if r and r.get('found'):
                ok += 1
                sd = _spot_data(r, spec['pa'], depth, gt, stage, spec.get('extra'))
                _, k1, k2 = spec['key']
                section = spec['key'][0]
                node['ranges'].setdefault(bucket, {}).setdefault(section, {}).setdefault(k1, {})[k2] = sd
            else:
                print(f"  [--] {spec['key']} pa={spec['pa']}")
            if sleep_s:
                time.sleep(sleep_s)
        merged = merge_into(OUT, pko)
        OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
        grid[stage] = (ok, tot)
        print(f"  -> {ok}/{tot} ok (checkpoint salvo)")
    print(f"\n{'='*60}")
    for stage, (ok, tot) in grid.items():
        print(f"  {stage:9}: {ok}/{tot}")
    print(f"✓ {OUT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenario', required=True, choices=['vs_3bet', 'vs_4bet', 'faces_squeeze'])
    ap.add_argument('--field', type=int, default=200)
    ap.add_argument('--fetch-timeout', type=int, default=20)
    ap.add_argument('--sleep', type=float, default=0.3)
    ap.add_argument('--only', default='')
    ap.add_argument('--solver-url', default='http://localhost:8765')
    args = ap.parse_args()
    if args.solver_url:
        os.environ['GTO_SOLVER_URL'] = args.solver_url
    os.environ.setdefault('GTO_WIZARD_ENABLED', 'true')
    only = [s.strip() for s in args.only.split(',') if s.strip()]
    run(args.scenario, args.fetch_timeout, args.sleep, only or None, args.field)


if __name__ == '__main__':
    main()
