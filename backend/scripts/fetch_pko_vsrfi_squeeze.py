"""fetch_pko_vsrfi_squeeze.py — captura vs_RFI e squeeze PKO (8-max) nos estágios
já mapeados, usando o open-size correto por (estágio, posição) extraído da camada
RFI capturada. Linhas com raise SÃO capturáveis pelo proxy (a falha anterior era
cascata de página presa, resolvida com sessão fresca).

vs_RFI:  ranges[bucket]['vs_RFI'][opener][defender]
squeeze: ranges[bucket]['squeeze'][hero][opener]  (1 caller representativo = seat antes do hero)

Pré-req: túnel -L 8765 + Chrome logado. Checkpoint por estágio (grava incremental).

Uso: python -m scripts.fetch_pko_vsrfi_squeeze --scenario vs_rfi   # ou squeeze / both
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
SEATS = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']  # ordem de assento 8-max


def load_meta(field=200):
    """Do RFI capturado: stage→depth e open-code por (stage, posição)."""
    pr = json.loads(OUT.read_text(encoding='utf-8'))['pko_ranges'][f'{field}p']
    stage_depth, open_codes = {}, {}
    for stage, node in pr.items():
        oc, depth = {}, None
        for bucket, scens in node['ranges'].items():
            for hero, sd in scens.get('RFI', {}).items():
                rs = [a['code'] for a in sd.get('actions', [])
                      if a.get('code') and a['code'].startswith('R') and a['code'] != 'RAI']
                if rs:
                    oc[hero] = rs[0]
                depth = sd.get('depth')
        stage_depth[stage] = depth
        open_codes[stage] = oc
    return stage_depth, open_codes


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


def vsrfi_lines(oc):
    for oi in range(7):
        opener = SEATS[oi]
        code = oc.get(opener)
        if not code:
            continue
        for di in range(oi + 1, 8):
            pa = '-'.join(['F'] * oi + [code] + ['F'] * (di - oi - 1))
            yield opener, SEATS[di], pa


def squeeze_lines(oc):
    # 1 caller representativo = seat imediatamente antes do hero (cold-call tardio)
    for oi in range(6):
        opener = SEATS[oi]
        code = oc.get(opener)
        if not code:
            continue
        for hi in range(oi + 2, 8):       # precisa de espaço p/ 1 caller
            ci = hi - 1                    # caller logo antes do hero
            caller = SEATS[ci]
            pa = '-'.join(['F'] * oi + [code] + ['F'] * (ci - oi - 1) + ['C'] + ['F'] * (hi - ci - 1))
            yield opener, caller, SEATS[hi], pa


def run(scenario, fetch_timeout, sleep_s, only, field=200):
    import leaklab.gto_wizard_client as gw
    stage_depth, open_codes = load_meta(field)
    stages = [s for s in stage_depth if not only or s in only]
    grid = {}
    for stage in stages:
        depth = stage_depth[stage]
        gt = gametype_for(field, stage)
        bucket = depth_to_bucket(depth)
        oc = open_codes[stage]
        pko = {}                          # acumula só este estágio (checkpoint)
        node = pko.setdefault(f'{field}p', {}).setdefault(
            stage, {'_stage': humanize_stage(stage), 'ranges': {}})
        ok = tot = 0
        print(f"=== {stage} ({humanize_stage(stage)}) @ {depth:.0f}bb ===")
        if scenario in ('vs_rfi', 'both'):
            for opener, defender, pa in vsrfi_lines(oc):
                tot += 1
                r = gw.query_spot_raw(preflop_actions=pa, num_players=8, depth_bb=float(depth),
                                      gametype=gt, include_strategy=True,
                                      timeout=max(60, fetch_timeout + 30), fetch_timeout=fetch_timeout)
                if r and r.get('found'):
                    ok += 1
                    sd = _spot_data(r, pa, depth, gt, stage)
                    node['ranges'].setdefault(bucket, {}).setdefault('vs_RFI', {}).setdefault(opener, {})[defender] = sd
                else:
                    print(f"  [--] vs_RFI {opener}->{defender} pa={pa}")
                if sleep_s:
                    time.sleep(sleep_s)
        if scenario in ('squeeze', 'both'):
            for opener, caller, hero, pa in squeeze_lines(oc):
                tot += 1
                r = gw.query_spot_raw(preflop_actions=pa, num_players=8, depth_bb=float(depth),
                                      gametype=gt, include_strategy=True,
                                      timeout=max(60, fetch_timeout + 30), fetch_timeout=fetch_timeout)
                if r and r.get('found'):
                    ok += 1
                    sd = _spot_data(r, pa, depth, gt, stage, {'caller_positions': [caller]})
                    node['ranges'].setdefault(bucket, {}).setdefault('squeeze', {}).setdefault(hero, {})[opener] = sd
                else:
                    print(f"  [--] squeeze {opener}/{caller}->{hero} pa={pa}")
                if sleep_s:
                    time.sleep(sleep_s)
        # CHECKPOINT: grava incremental após cada estágio
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
    ap.add_argument('--scenario', default='vs_rfi', choices=['vs_rfi', 'squeeze', 'both'])
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
