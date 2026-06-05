"""build_gto_evs.py — gera o overlay de EV por mão (#24 ev_loss).

Re-parseia os HARs do GTO Solver (que carregam `evs` por ação/mão) e grava
`docs/leaklab_gto_evs.json` com a MESMA topologia de chave do
`leaklab_gto_ranges.json` ([bucket][cenário][hero][villain] → {hand:{code:ev}}).
Mantido SEPARADO das ranges (não infla/arrisca o JSON de freqs); o engine carrega
os dois e computa `ev_loss_bb = max_ação(ev) − ev(ação do hero)`.

Cobertura = spots presentes nos HARs do repo (preflop Classic). EV em bb. PKO fica
num overlay próprio (build_pko_evs futuro) — aqui só o Classic.

Uso: python -m scripts.build_gto_evs
"""
from __future__ import annotations
import glob
import json
import os
from pathlib import Path

from scripts.parse_gw_har import (
    process_har, parse_spot, classify_spot, depth_to_bucket,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEST = BACKEND_DIR / 'docs' / 'leaklab_gto_evs.json'


def _store(root: dict, bucket: str, cls: dict, hand_evs: dict) -> bool:
    """Injeta hand_evs na mesma chave que build_ranges_json usa. True se gravou."""
    sc = cls['scenario']; hero = cls['hero_pos']; vs = cls['vs_pos']
    if sc == 'rfi' and hero:
        root.setdefault(bucket, {}).setdefault('RFI', {})[hero] = hand_evs
    elif sc == 'vs_rfi' and hero and vs:
        root.setdefault(bucket, {}).setdefault('vs_RFI', {}).setdefault(vs, {})[hero] = hand_evs
    elif sc == 'vs_3bet' and hero and vs:
        root.setdefault(bucket, {}).setdefault('vs_3bet', {}).setdefault(hero, {})[vs] = hand_evs
    elif sc == 'vs_4bet' and hero and vs:
        root.setdefault(bucket, {}).setdefault('vs_4bet', {}).setdefault(hero, {})[vs] = hand_evs
    elif sc == 'squeeze' and hero and vs:
        root.setdefault(bucket, {}).setdefault('squeeze', {}).setdefault(hero, {})[vs] = hand_evs
    else:
        return False
    return True


def main():
    files = sorted(set(glob.glob(str(BACKEND_DIR / 'docs' / 'ranges_gto' / '**' / '*.har'), recursive=True)
                       + glob.glob(str(BACKEND_DIR / 'docs' / '*.har'))))
    ranges: dict = {}
    n_spots = n_stored = 0
    by_scen: dict = {}
    for fn in files:
        norm = fn.replace(os.sep, '/')
        if '/ko/' in norm or 'login' in norm:   # PKO em overlay próprio; pula login
            continue
        try:
            spots = process_har(Path(fn))
        except Exception:
            continue
        for s in spots:
            try:
                p = parse_spot(s['data'], s['params'])
            except Exception:
                continue
            n_spots += 1
            hand_evs = p.get('hand_evs')
            if not hand_evs:
                continue
            cls = classify_spot(p['preflop_actions'])
            bucket = depth_to_bucket(p['depth'])
            if _store(ranges, bucket, cls, hand_evs):
                n_stored += 1
                by_scen[cls['scenario']] = by_scen.get(cls['scenario'], 0) + 1

    out = {
        '_metadata': {'source': 'gtowizard_har_evs', 'unit': 'bb',
                      'spots_parsed': n_spots, 'spots_stored': n_stored,
                      'by_scenario': by_scen},
        'ranges': ranges,
    }
    DEST.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    sz = DEST.stat().st_size / 1024
    print(f"✓ {n_stored} spots com EV → {DEST} ({sz:.0f} KB)")
    print(f"  por cenário: {by_scen}")
    # cobertura por bucket
    print(f"  buckets: {sorted(ranges.keys(), key=lambda b: int(b.replace('bb','')))}")


if __name__ == '__main__':
    main()
