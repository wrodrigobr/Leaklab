"""
merge_gaps.py — Mescla leaklab_gto_ranges_gaps.json no leaklab_gto_ranges.json.
NUNCA sobrescreve entries existentes — so adiciona as ausentes.

Backup automatico em leaklab_gto_ranges.backup.<timestamp>.json antes de escrever.

Uso:
    python scripts/merge_gaps.py             # dry-run (mostra o que seria adicionado)
    python scripts/merge_gaps.py --save      # persiste
"""
from __future__ import annotations
import argparse, json, shutil, sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR    = BACKEND_DIR / "docs"
RANGES      = DOCS_DIR / "leaklab_gto_ranges.json"
GAPS        = DOCS_DIR / "leaklab_gto_ranges_gaps.json"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--save", action="store_true")
    args = p.parse_args()

    if not GAPS.exists():
        print(f"ERRO: {GAPS} nao encontrado", file=sys.stderr)
        return 1

    existing = json.loads(RANGES.read_text(encoding="utf-8"))
    gaps     = json.loads(GAPS.read_text(encoding="utf-8"))

    added = {"vs_3bet": 0, "vs_4bet": 0}
    skipped = {"vs_3bet": 0, "vs_4bet": 0}
    details: list[str] = []

    for bucket, sections in gaps["ranges"].items():
        bk_data = existing["ranges"].setdefault(bucket, {})
        for scenario in ("vs_3bet", "vs_4bet"):
            new_entries = sections.get(scenario, {})
            if not new_entries:
                continue
            scenario_data = bk_data.setdefault(scenario, {})
            for key, entry in new_entries.items():
                if key in scenario_data:
                    skipped[scenario] += 1
                    details.append(f"  [skip] {bucket} {scenario}.{key} (ja existe)")
                else:
                    scenario_data[key] = entry
                    added[scenario] += 1
                    details.append(f"  [add]  {bucket} {scenario}.{key}")

    # Atualiza versao do metadata
    meta = existing.setdefault("_metadata", {})
    old_ver = meta.get("versao", "2.4.0")
    parts = old_ver.split(".")
    parts[-1] = str(int(parts[-1]) + 1) if parts[-1].isdigit() else "0"
    meta["versao"] = ".".join(parts)
    meta.setdefault("changelog", []).append({
        "versao": meta["versao"],
        "data": datetime.now().strftime("%Y-%m-%d"),
        "mudanca": f"Adicionadas {added['vs_3bet']} entries vs_3bet + {added['vs_4bet']} entries vs_4bet (Greenline+Pekarstas)",
    })

    for line in details:
        print(line)
    print()
    print(f"Total adicionadas: vs_3bet={added['vs_3bet']}, vs_4bet={added['vs_4bet']}")
    print(f"Total puladas (ja existiam): vs_3bet={skipped['vs_3bet']}, vs_4bet={skipped['vs_4bet']}")
    print(f"Nova versao: {meta['versao']}")

    if not args.save:
        print("\n[DRY RUN] Use --save para persistir.")
        return 0

    # Backup
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = RANGES.with_suffix(f".backup.{stamp}.json")
    shutil.copy2(RANGES, backup)
    print(f"\nBackup: {backup.name}")

    RANGES.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Escrito: {RANGES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
