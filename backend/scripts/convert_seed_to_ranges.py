"""
convert_seed_to_ranges.py — Converte os checkpoints JSONL do seed_preflop_gw
(docs/gw_preflop_seed/*.jsonl) para a estrutura do master de ranges
(ranges[bucket][scenario][k1][k2] = spot_data), pronta pra merge.

Classificação CORRETA por seat-tracking + hero_position real do GW (não repete o
bug do classify_spot/parse_gw_har que assume hero=opener em 2 raises). Cenários:
  rfi            ranges[bk][RFI][hero]
  vs_rfi         ranges[bk][vs_RFI][opener][hero]          (defesa vs open)
  squeeze        ranges[bk][squeeze][hero][opener]         (hero pode dar squeeze)
  vs_3bet        ranges[bk][vs_3bet][hero][3bettor]        (hero=opener enfrenta 3bet)
  faces_squeeze  ranges[bk][faces_squeeze][hero][3bettor]  (hero cold/blind enfrenta 3bet/squeeze) — NOVO

spot_data: fold/call/raise/allin _pct + _hands + hand_freqs (codes crus do GW),
formato que o analyze_preflop já consome.

Uso:
    python scripts/convert_seed_to_ranges.py                  # todos os buckets
    python scripts/convert_seed_to_ranges.py --out docs/leaklab_gto_ranges_gw_seed.json
"""
from __future__ import annotations
import argparse, json, sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SEED_DIR = BACKEND / "docs" / "gw_preflop_seed"
SEATS = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"]


def _is_raise(tok: str) -> bool:
    return bool(tok) and (tok == "RAI" or tok[0] in ("R", "B"))


def classify(pf: str, hero: str) -> dict:
    """(scenario, k1, k2) pela sequência + hero real. k1/k2 = chaves no master."""
    parts = pf.split("-") if pf else []
    # ações de 1ª orbita por assento (cobre rfi/vs_rfi/squeeze/3bet/faces_squeeze)
    raises = []   # (seat, idx)
    calls  = []   # seat
    for i, tok in enumerate(parts):
        if i >= len(SEATS):
            break
        seat = SEATS[i]
        if tok == "F":
            continue
        if tok == "C":
            calls.append(seat)
        elif _is_raise(tok):
            raises.append((seat, i))
    nr = sum(1 for tok in parts if _is_raise(tok))

    if nr == 0:
        return {"scenario": "rfi", "k1": hero, "k2": None}

    opener = raises[0][0] if raises else None

    if nr == 1 and not calls:
        return {"scenario": "vs_rfi", "k1": opener, "k2": hero, "vs": opener}

    if nr == 1 and calls:
        return {"scenario": "squeeze", "k1": hero, "k2": opener,
                "vs": opener, "callers": calls}

    if nr == 2:
        threbettor = raises[1][0] if len(raises) > 1 else None
        if hero == opener:
            # opener voltou a agir enfrentando o 3bet
            return {"scenario": "vs_3bet", "k1": hero, "k2": threbettor, "vs": threbettor}
        # hero é cold/blind enfrentando open+3bet (ou squeeze) — sem ter aberto
        return {"scenario": "faces_squeeze", "k1": hero, "k2": threbettor,
                "vs": threbettor, "opener": opener, "callers": calls}

    # 4bet+ e multiway complexo: fora do escopo do seed por enquanto
    return {"scenario": "other", "k1": None, "k2": None}


def build_spot(node: dict) -> dict:
    norm_hf = node.get("hand_freqs") or {}        # {hand: {fold/call/raise/allin: freq}}
    raw_hf  = node.get("raw_hand_freqs") or {}    # {hand: {code: freq}} — formato do master
    raise_h, call_h, allin_h, fold_h = [], [], [], []
    for hand, acts in norm_hf.items():
        if (acts.get("raise") or 0) > 0:  raise_h.append(hand)
        if (acts.get("call") or 0) > 0:   call_h.append(hand)
        if (acts.get("allin") or 0) > 0:  allin_h.append(hand)
        if (acts.get("fold") or 0) > 0:   fold_h.append(hand)
    pct = {"fold": 0.0, "call": 0.0, "raise": 0.0, "allin": 0.0}
    for a in node.get("actions", []):
        t = a.get("type"); f = float(a.get("freq") or 0)
        if   t == "FOLD":  pct["fold"]  += f
        elif t == "CALL":  pct["call"]  += f
        elif t == "RAISE": pct["raise"] += f
        elif t == "ALLIN": pct["allin"] += f
    return {
        "fold_pct":  round(pct["fold"], 4),  "call_pct":  round(pct["call"], 4),
        "raise_pct": round(pct["raise"], 4), "allin_pct": round(pct["allin"], 4),
        "aggr_pct":  round(pct["call"] + pct["raise"] + pct["allin"], 4),
        "fold_hands":  ",".join(sorted(fold_h)),
        "call_hands":  ",".join(sorted(call_h)),
        "raise_hands": ",".join(sorted(raise_h)),
        "allin_hands": ",".join(sorted(allin_h)),
        "hand_freqs":  raw_hf,
        "source":      "gw_seed",
        "preflop_actions": node.get("pf"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BACKEND / "docs" / "leaklab_gto_ranges_gw_seed.json"))
    args = ap.parse_args()

    files = sorted(SEED_DIR.glob("*.jsonl"))
    if not files:
        print(f"Nenhum JSONL em {SEED_DIR}"); return

    ranges: dict = {}
    scen_count = Counter()
    skipped = Counter()
    total = 0
    for fp in files:
        bucket = fp.stem  # ex "20bb"
        with open(fp, encoding="utf-8") as f:
            for line in f:
                try:
                    node = json.loads(line)
                except Exception:
                    continue
                total += 1
                hero = node.get("hero_position")
                pf   = node.get("pf", "")
                if not hero:
                    skipped["no_hero"] += 1; continue
                cls = classify(pf, hero)
                scen = cls["scenario"]
                if scen == "other" or not cls.get("k1"):
                    skipped[scen] += 1; continue
                spot = build_spot(node)
                bk = ranges.setdefault(bucket, {})
                if scen == "rfi":
                    bk.setdefault("RFI", {})[cls["k1"]] = spot
                elif scen == "vs_rfi":
                    bk.setdefault("vs_RFI", {}).setdefault(cls["k1"], {})[cls["k2"]] = spot
                elif scen == "vs_3bet":
                    bk.setdefault("vs_3bet", {}).setdefault(cls["k1"], {})[cls["k2"]] = spot
                elif scen == "squeeze":
                    bk.setdefault("squeeze", {}).setdefault(cls["k1"], {})[cls["k2"]] = spot
                elif scen == "faces_squeeze":
                    bk.setdefault("faces_squeeze", {}).setdefault(cls["k1"], {})[cls["k2"]] = spot
                scen_count[scen] += 1

    out = {"ranges": ranges,
           "_metadata": {"source": "gw_seed", "total_nodes": total,
                         "scenarios": dict(scen_count), "skipped": dict(skipped)}}
    out_path = Path(args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Nós lidos: {total}")
    print("Por cenário:", dict(scen_count))
    print("Pulados:", dict(skipped))
    print("\nCobertura por bucket × cenário:")
    for bk in sorted(ranges, key=lambda x: int(x.replace("bb", ""))):
        per = {sc: (sum(len(v) for v in ranges[bk][sc].values()) if sc != "RFI" else len(ranges[bk][sc]))
               for sc in ranges[bk]}
        print(f"  {bk}: {per}")
    print(f"\n[OK] {out_path}")


if __name__ == "__main__":
    main()
