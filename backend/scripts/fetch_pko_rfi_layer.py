"""fetch_pko_rfi_layer.py — captura a camada RFI PKO inteira (todos os estágios).

Para cada estágio, faz um PROBE UTG com "primeiro depth que resolve vence"
(o GW só resolve cada estágio no stack característico dele — depth é acoplado ao
estágio). Ao achar o depth canônico, captura as 7 posições RFI 8-max e grava no
namespace `pko_ranges` (reusa os helpers do fetch_pko_ranges / parse_gw_har).

Tokens CONFIRMADOS nos HARs reais: START, BUBBLEMID, PCT50, FT.
Tokens PALPITE (pela lista do usuário): PCT90/70/375/25, 2TABLES, 3TABLES — se
não resolverem em nenhum depth candidato, marca MISS (token/depth a confirmar).

Uso: python -m scripts.fetch_pko_rfi_layer --field 200
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except Exception:
    pass

from scripts.parse_gw_har import depth_to_bucket, humanize_stage
from scripts.fetch_pko_ranges import (
    RFI_8MAX, gametype_for, _summary_from_strategy, merge_into,
)

# Estágio → depths candidatos (ordem = probabilidade). Anchors dos HARs primeiro.
STAGE_CANDIDATES = {
    'START':     [100],
    'PCT90':     [90, 100],
    'PCT70':     [80, 70],
    'PCT50':     [72, 50],
    'PCT375':    [60, 50],
    'PCT25':     [50, 40],
    'BUBBLEMID': [50, 40],
    '3TABLES':   [40, 30],
    '2TABLES':   [30, 25],
    'FT':        [100, 50, 30],
}


def _spot_data(r: dict, pa: str, depth: float, gt: str, stage: str) -> dict:
    raw_hf = r.get('raw_hand_freqs') or r.get('hand_freqs') or {}
    summ = _summary_from_strategy(r.get('strategy'))
    return {
        'hero':            r.get('hero_position'),
        'preflop_actions': pa,
        'depth':           float(depth),
        'gametype':        gt,
        'stage':           humanize_stage(stage),
        'actions': [
            {'code': a.get('code'), 'frequency': round(float(a.get('frequency') or 0), 4),
             'betsize_bb': a.get('betsize_bb')}
            for a in (r.get('strategy') or [])
        ],
        'hand_freqs':      raw_hf,
        **summ,
    }


def _store(pko: dict, field: int, stage: str, depth: float, sd: dict) -> None:
    node = pko.setdefault(f"{field}p", {}).setdefault(
        stage, {'_stage': humanize_stage(stage), 'ranges': {}})
    node['ranges'].setdefault(depth_to_bucket(depth), {}).setdefault(
        'RFI', {})[sd['hero']] = sd


def run(field: int, fetch_timeout: int, sleep_s: float):
    import leaklab.gto_wizard_client as gw
    pko: dict = {}
    stage_depth: dict = {}
    grid: list = []
    for stage, depths in STAGE_CANDIDATES.items():
        gt = gametype_for(field, stage)
        hit = None
        for depth in depths:
            t0 = time.time()
            r = gw.query_spot_raw(preflop_actions='', num_players=8, depth_bb=float(depth),
                                  gametype=gt, include_strategy=True,
                                  timeout=max(60, fetch_timeout + 30), fetch_timeout=fetch_timeout)
            dt = round(time.time() - t0, 1)
            if r and r.get('found'):
                hit = (depth, r)
                print(f"[HIT ] {stage:9} @ {depth:.0f}bb (UTG {dt}s)")
                break
            print(f"  probe {stage:9} @ {depth:.0f}bb -> no ({dt}s)")
        if not hit:
            stage_depth[stage] = None
            grid.append((stage, None, 0))
            print(f"[MISS] {stage:9}: nenhum depth resolveu {depths} (token/depth a confirmar)")
            continue
        depth, r_utg = hit
        stage_depth[stage] = depth
        _store(pko, field, stage, depth, _spot_data(r_utg, '', depth, gt, stage))
        n_ok = 1
        for pos, pa in RFI_8MAX[1:]:        # UTG já capturado no probe
            if sleep_s:
                time.sleep(sleep_s)
            r = gw.query_spot_raw(preflop_actions=pa, num_players=8, depth_bb=float(depth),
                                  gametype=gt, include_strategy=True,
                                  timeout=max(60, fetch_timeout + 30), fetch_timeout=fetch_timeout)
            if r and r.get('found'):
                _store(pko, field, stage, depth, _spot_data(r, pa, depth, gt, stage))
                n_ok += 1
                print(f"    [OK] {pos:5} open={_summary_from_strategy(r.get('strategy'))['open_pct']:.2f}")
            else:
                print(f"    [--] {pos:5} no-solution")
        grid.append((stage, depth, n_ok))
    return pko, stage_depth, grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--field', type=int, default=200)
    ap.add_argument('--fetch-timeout', type=int, default=18)
    ap.add_argument('--sleep', type=float, default=0.4)
    ap.add_argument('--solver-url', default='http://localhost:8765')
    ap.add_argument('--output', default=str(BACKEND_DIR / 'docs' / 'ranges_gto' / 'ko' / 'pko_ranges_pilot.json'))
    args = ap.parse_args()

    if args.solver_url:
        os.environ['GTO_SOLVER_URL'] = args.solver_url
    os.environ.setdefault('GTO_WIZARD_ENABLED', 'true')

    import leaklab.gto_wizard_client as gw
    st = gw.get_status()
    print(f"proxy={os.environ['GTO_SOLVER_URL']} auth_ok={st.get('auth_ok')} field={args.field}")

    pko, stage_depth, grid = run(args.field, args.fetch_timeout, args.sleep)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged = merge_into(out_path, pko)
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n{'='*64}")
    print("MAPA stage->depth (RFI 200p):")
    for stage, depth in stage_depth.items():
        d = f"{depth:.0f}bb" if depth else "MISS (confirmar token/depth no GW)"
        n = next((n for s, dp, n in grid if s == stage), 0)
        print(f"  {stage:9} -> {d:38} RFI {n}/7")
    print(f"\n✓ gravado em {out_path}")


if __name__ == '__main__':
    main()
