"""
merge_squeeze_into_ranges.py — Mescla extracted_squeeze.json no
leaklab_gto_ranges.json com schema NOVO `vs_squeeze` (sem mexer em existentes).

Estrutura adicionada:
  ranges.<stack>bb.vs_squeeze.<hero>_squeeze_vs_<opener>_open_<caller>_call:
    pct_squeeze:  float (frequência total de raise/allin)
    pct_call:     float
    pct_fold:     float
    hands_4bet:   "AA,KK,..."
    hands_call:   "22,33,..."
    hands_fold:   "resto"
    hands_mixed:  hands com estratégia mista (opcional)
    _source:      "gto_wizard MTTGeneral 2026-05-22"
    _preflop_actions: "F-F-F-F-R2.3-C"

Uso:
    python scripts/gto_validation/merge_squeeze_into_ranges.py            # dry-run
    python scripts/gto_validation/merge_squeeze_into_ranges.py --save
"""
from __future__ import annotations
import argparse, json, shutil, sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
RANGES      = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"
EXTRACTED   = SCRIPT_DIR / "extracted_squeeze.json"

# Stack -> bucket usado no JSON (alinhado com chaves existentes)
DEPTH_TO_BUCKET = {
    30:  "30bb",
    40:  "40bb",
    50:  "50bb",
    60:  "50bb",   # 60 mais próximo de 50bb que de 75bb
    80:  "75bb",
    100: "100bb",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--save", action="store_true")
    args = p.parse_args()

    extracted = json.loads(EXTRACTED.read_text(encoding="utf-8"))
    existing  = json.loads(RANGES.read_text(encoding="utf-8"))

    ok_spots = [e for e in extracted if e.get("status") == 200]
    print(f"Spots extraídos com sucesso: {len(ok_spots)}")

    added: dict[str, int] = {}
    skipped_existing = 0

    for spot in ok_spots:
        depth = spot["depth"]
        bucket = DEPTH_TO_BUCKET.get(depth)
        if not bucket:
            continue

        ranges_node = existing["ranges"].setdefault(bucket, {})
        vs_sq = ranges_node.setdefault("vs_squeeze", {})

        # Key uniforme: hero é quem decide squeezar
        key = f"{spot['hero']}_squeeze_vs_{spot['opener']}_open_{spot['caller']}_call"

        if key in vs_sq:
            skipped_existing += 1
            continue

        agg = spot.get("aggregated", {})
        entry = {
            "pct_squeeze":      round(agg.get("raise", 0) + agg.get("allin", 0), 4),
            "pct_call":         round(agg.get("call", 0), 4),
            "pct_fold":         round(agg.get("fold", 0), 4),
            "hands_4bet":       spot.get("hands_4bet", ""),
            "hands_call":       spot.get("hands_call", ""),
            "hands_fold":       "resto",
        }
        if spot.get("hands_mixed"):
            entry["hands_mixed"] = spot["hands_mixed"]
        entry["_source"] = "gto_wizard MTTGeneral 2026-05-22"
        entry["_preflop_actions"] = spot["preflop_actions"]

        vs_sq[key] = entry
        added[bucket] = added.get(bucket, 0) + 1

    # Atualiza metadata
    meta = existing.setdefault("_metadata", {})
    old_ver = meta.get("versao", "2.4.1")
    parts = old_ver.split(".")
    parts[-1] = str(int(parts[-1]) + 1) if parts[-1].isdigit() else "0"
    meta["versao"] = ".".join(parts)
    meta.setdefault("changelog", []).append({
        "versao": meta["versao"],
        "data": datetime.now().strftime("%Y-%m-%d"),
        "mudanca": f"Adicionado schema vs_squeeze com {sum(added.values())} spots (GTO Wizard extraction)",
    })

    print(f"\nNovas entries por bucket:")
    for bucket, n in sorted(added.items()):
        print(f"  {bucket}: {n}")
    print(f"Total entries vs_squeeze adicionadas: {sum(added.values())}")
    print(f"Skipped (já existiam): {skipped_existing}")
    print(f"Versão nova: {meta['versao']}")

    if not args.save:
        print("\n[DRY-RUN] use --save para persistir")
        return 0

    # Backup
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = RANGES.with_suffix(f".backup.{stamp}.json")
    shutil.copy2(RANGES, backup)
    print(f"\nBackup: {backup.name}")

    RANGES.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Escrito: {RANGES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
