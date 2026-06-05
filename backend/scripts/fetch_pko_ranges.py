"""fetch_pko_ranges.py — captura ranges PKO do GTO Solver (GW) via o proxy live.

Enumera spots (por enquanto RFI 8-max) para combinações field × stage × depth,
consulta `gto_wizard_client.query_spot_raw` com o gametype PKO
(`MTTGeneral_ICMPKO8m{field}PT{stage}`) e grava no namespace `pko_ranges` —
MESMA topologia do `parse_gw_har` (`pko_ranges[{field}p][stage]['ranges']
[bucket][scenario][hero]`), pro engine reusar o lookup Classic.

Pré-requisito: túnel SSH pro proxy aberto (`-L 8765:localhost:8765`) e Chrome
logado no GW no servidor (ver [[reference_vnc_gto_server]] / [[project_gw_preflop_fetch]]).

Uso (PILOTO):
  python -m scripts.fetch_pko_ranges --field 200 --stages START \
      --depths 100,50,30,20 --scenarios rfi
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
    load_dotenv(BACKEND_DIR / ".env")          # GTO_SOLVER_URL / _API_KEY / WIZARD_ENABLED
except Exception:
    pass

from scripts.parse_gw_har import depth_to_bucket, humanize_stage

# RFI 8-max: posição do hero → preflop_actions (folds antes dele). BB não dá RFI.
RFI_8MAX = [
    ('UTG',   ''),
    ('UTG+1', 'F'),
    ('LJ',    'F-F'),
    ('HJ',    'F-F-F'),
    ('CO',    'F-F-F-F'),
    ('BTN',   'F-F-F-F-F'),
    ('SB',    'F-F-F-F-F-F'),
]


def gametype_for(field: int, stage: str) -> str:
    return f"MTTGeneral_ICMPKO8m{field}PT{stage}"


def _summary_from_strategy(strategy: list) -> dict:
    """open/raise/allin/call/fold pct a partir do array `strategy` (freq por ação)."""
    out = {'raise_pct': 0.0, 'allin_pct': 0.0, 'call_pct': 0.0, 'fold_pct': 0.0}
    for a in strategy or []:
        code = (a.get('code') or '').upper()
        f = float(a.get('frequency') or 0)
        if code == 'F':
            out['fold_pct'] += f
        elif code == 'C':
            out['call_pct'] += f
        elif code == 'RAI':
            out['allin_pct'] += f
        elif code.startswith('R'):
            out['raise_pct'] += f
    out = {k: round(v, 4) for k, v in out.items()}
    out['open_pct'] = round(out['raise_pct'] + out['allin_pct'], 4)
    return out


def fetch_rfi(field: int, stages: list[str], depths: list[float],
              fetch_timeout: int, sleep_s: float) -> tuple[dict, list]:
    import leaklab.gto_wizard_client as gw
    pko: dict = {}
    grid: list = []   # (stage, depth, pos, ok, n_hands)
    fkey = f"{field}p"
    for stage in stages:
        gt = gametype_for(field, stage)
        for depth in depths:
            bucket = depth_to_bucket(depth)
            for pos, pa in RFI_8MAX:
                t0 = time.time()
                r = gw.query_spot_raw(
                    preflop_actions=pa, num_players=8, depth_bb=float(depth),
                    gametype=gt, include_strategy=True,
                    timeout=max(60, fetch_timeout + 20), fetch_timeout=fetch_timeout)
                dt = round(time.time() - t0, 1)
                if not r or not r.get('found'):
                    err = (r or {}).get('error', 'none')
                    grid.append((stage, depth, pos, False, 0))
                    print(f"  [--] {stage:9} {bucket:5} {pos:5} pa={pa:12} -> NO ({err}) {dt}s")
                    continue
                raw_hf = r.get('raw_hand_freqs') or r.get('hand_freqs') or {}
                summ = _summary_from_strategy(r.get('strategy'))
                spot_data = {
                    'hero':            r.get('hero_position') or pos,
                    'preflop_actions': pa,
                    'depth':           float(depth),
                    'gametype':        gt,
                    'stage':           humanize_stage(stage),
                    'actions': [
                        {'code': a.get('code'), 'frequency': round(float(a.get('frequency') or 0), 4),
                         'betsize_bb': a.get('betsize_bb')}
                        for a in (r.get('strategy') or [])
                    ],
                    'hand_freqs':      raw_hf,   # codes (compatível c/ JSON Classic)
                    **summ,
                }
                node = pko.setdefault(fkey, {}).setdefault(
                    stage, {'_stage': humanize_stage(stage), 'ranges': {}})
                node['ranges'].setdefault(bucket, {}).setdefault('RFI', {})[spot_data['hero']] = spot_data
                grid.append((stage, depth, pos, True, len(raw_hf)))
                print(f"  [OK] {stage:9} {bucket:5} {pos:5} pa={pa:12} -> open={summ['open_pct']:.2f} "
                      f"hands={len(raw_hf)} {dt}s")
                if sleep_s:
                    time.sleep(sleep_s)
    return pko, grid


def merge_into(out_path: Path, new_pko: dict) -> dict:
    base = {'_metadata': {'source': 'gtowizard_pko_via_proxy'}, 'pko_ranges': {}}
    if out_path.exists():
        try:
            base = json.loads(out_path.read_text(encoding='utf-8'))
            base.setdefault('pko_ranges', {})
        except Exception:
            pass
    pr = base['pko_ranges']
    for field, stages in new_pko.items():
        for stage, node in stages.items():
            dst = pr.setdefault(field, {}).setdefault(
                stage, {'_stage': node['_stage'], 'ranges': {}})
            for bucket, scens in node['ranges'].items():
                for sc, heroes in scens.items():
                    dst['ranges'].setdefault(bucket, {}).setdefault(sc, {}).update(heroes)
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--field', type=int, default=200)
    ap.add_argument('--stages', default='START')
    ap.add_argument('--depths', default='100,50,30,20')
    ap.add_argument('--scenarios', default='rfi')
    ap.add_argument('--fetch-timeout', type=int, default=20)
    ap.add_argument('--sleep', type=float, default=0.5)
    ap.add_argument('--solver-url', default='http://localhost:8765',
                    help='proxy via túnel SSH (sobrepõe GTO_SOLVER_URL do .env, que é o IP externo firewalled)')
    ap.add_argument('--output', default=str(BACKEND_DIR / 'docs' / 'ranges_gto' / 'ko' / 'pko_ranges_pilot.json'))
    args = ap.parse_args()

    if args.solver_url:
        os.environ['GTO_SOLVER_URL'] = args.solver_url
    os.environ.setdefault('GTO_WIZARD_ENABLED', 'true')

    stages = [s.strip() for s in args.stages.split(',') if s.strip()]
    depths = [float(d) for d in args.depths.split(',') if d.strip()]
    scenarios = [s.strip().lower() for s in args.scenarios.split(',') if s.strip()]

    import leaklab.gto_wizard_client as gw
    st = gw.get_status()
    print(f"proxy={os.environ['GTO_SOLVER_URL']} auth_ok={st.get('auth_ok')} "
          f"(nota: /gw-spot NÃO bloqueia em auth_ok)")
    print(f"field={args.field} stages={stages} depths={depths} scenarios={scenarios}")

    if scenarios != ['rfi']:
        print("AVISO: piloto só implementa 'rfi' por ora; ignorando o resto.")

    pko, grid = fetch_rfi(args.field, stages, depths, args.fetch_timeout, args.sleep)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged = merge_into(out_path, pko)
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')

    ok = sum(1 for *_, found, _ in grid if found)
    print(f"\n{'='*60}")
    print(f"PILOTO PKO — {ok}/{len(grid)} spots com solução")
    print(f"✓ gravado em {out_path}")
    # grade de cobertura por stage×depth
    print("\nCobertura (✓=solução, ·=no-solution):")
    by = {}
    for stage, depth, pos, found, n in grid:
        by.setdefault((stage, depth), []).append((pos, found))
    for (stage, depth), items in by.items():
        marks = ' '.join(f"{p}{'✓' if f else '·'}" for p, f in items)
        print(f"  {stage:9} {depth_to_bucket(depth):5}: {marks}")


if __name__ == '__main__':
    main()
