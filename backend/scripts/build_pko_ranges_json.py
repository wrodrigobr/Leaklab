"""build_pko_ranges_json.py — converte a captura PKO (pko_ranges_pilot.json, local)
no arquivo de PRODUÇÃO docs/leaklab_pko_ranges.json (committável, sem segredo).

A captura live (`fetch_pko_rfi_layer`) guarda `hand_freqs` (action codes) + summary,
mas o `analyze_preflop` (RFI v3) também precisa das LISTAS raise_hands/allin_hands/
call_hands/fold_hands (membership via _in_range). Aqui derivamos essas listas do
hand_freqs — sem re-fetch — e gravamos o schema Classic-compatível.

Uso: python -m scripts.build_pko_ranges_json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SRC  = BACKEND_DIR / 'docs' / 'ranges_gto' / 'ko' / 'pko_ranges_pilot.json'   # local (gitignored)
DEST = BACKEND_DIR / 'docs' / 'leaklab_pko_ranges.json'                        # produção (commit)


def _derive_hands(hand_freqs: dict) -> dict:
    """hand_freqs {hand: {code: freq}} → listas raise/allin/call/fold (Classic v3)."""
    raise_h, allin_h, call_h, fold_h = [], [], [], []
    for hand, codes in (hand_freqs or {}).items():
        if not isinstance(codes, dict):
            continue
        rai = sum(f for c, f in codes.items() if c == 'RAI')
        rse = sum(f for c, f in codes.items() if c.startswith('R') and c != 'RAI')
        cal = sum(f for c, f in codes.items() if c == 'C')
        fld = sum(f for c, f in codes.items() if c == 'F')
        if rse > 0.001: raise_h.append(hand)
        if rai > 0.001: allin_h.append(hand)
        if cal > 0.001: call_h.append(hand)
        if fld > 0.001: fold_h.append(hand)
    return {
        'raise_hands': ','.join(sorted(raise_h)),
        'allin_hands': ','.join(sorted(allin_h)),
        'call_hands':  ','.join(sorted(call_h)),
        'fold_hands':  ','.join(sorted(fold_h)),
    }


def _enrich(spot: dict) -> dict:
    """Acrescenta as listas de hands ao spot_data capturado (mantém o resto)."""
    out = dict(spot)
    out.update(_derive_hands(spot.get('hand_freqs', {})))
    out['_source'] = 'pko_gto'
    return out


def _is_spot(o) -> bool:
    return isinstance(o, dict) and 'hand_freqs' in o and 'preflop_actions' in o


def _enrich_tree(obj):
    """Enriquece recursivamente: RFI = {hero: spot}; vs_RFI = {opener:{defender:spot}};
    squeeze = {hero:{opener:spot}}. Desce até achar o spot (hand_freqs+preflop_actions)."""
    if _is_spot(obj):
        return _enrich(obj)
    if isinstance(obj, dict):
        return {k: _enrich_tree(v) for k, v in obj.items()}
    return obj


def _count_spots(obj) -> int:
    if _is_spot(obj):
        return 1
    if isinstance(obj, dict):
        return sum(_count_spots(v) for v in obj.values())
    return 0


def main():
    if not SRC.exists():
        print(f"FONTE não encontrada: {SRC}\n(rode a captura primeiro: scripts/fetch_pko_rfi_layer.py)")
        sys.exit(1)
    src = json.loads(SRC.read_text(encoding='utf-8'))
    pko = src.get('pko_ranges', {})

    out = {'_metadata': {'source': 'pko_gto_via_proxy', 'schema': 'classic_v3_compatible'},
           'pko_ranges': {}}
    n_spots = 0
    for field, stages in pko.items():
        for stage, node in stages.items():
            dst_node = out['pko_ranges'].setdefault(field, {}).setdefault(
                stage, {'_stage': node.get('_stage', stage), 'ranges': {}})
            for bucket, scens in node.get('ranges', {}).items():
                for sc, subtree in scens.items():
                    dst_node['ranges'].setdefault(bucket, {})[sc] = _enrich_tree(subtree)
                    n_spots += _count_spots(subtree)

    out['_metadata']['total_spots'] = n_spots
    out['_metadata']['fields'] = sorted(out['pko_ranges'].keys())
    out['_metadata']['stages'] = sorted({s for f in out['pko_ranges'].values() for s in f})
    DEST.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"✓ {n_spots} spots → {DEST}")
    print(f"  fields: {out['_metadata']['fields']}")
    print(f"  stages: {out['_metadata']['stages']}")
    # amostra: UTG START raise_hands derivado
    try:
        utg = out['pko_ranges']['200p']['START']['ranges']['100bb']['RFI']['UTG']
        print(f"  sample UTG START raise_hands: {utg['raise_hands'][:60]}...")
    except Exception:
        pass


if __name__ == '__main__':
    main()
