"""
merge_seed_ranges.py — Mescla o JSON do seed (leaklab_gto_ranges_gw_seed.json)
no master (leaklab_gto_ranges.json).

Padrão ADD-ONLY: só adiciona spots/seções que NÃO existem no master (preenche
lacunas — faces_squeeze inteiro, squeeze/vs_3bet faltantes). NÃO sobrescreve dados
do master já validados (HAR/RegLife). `--overwrite` prefere o seed onde houver
conflito. Faz backup do master antes de gravar. `--dry-run` só relata.

Uso:
    python scripts/merge_seed_ranges.py --dry-run
    python scripts/merge_seed_ranges.py
    python scripts/merge_seed_ranges.py --overwrite
"""
from __future__ import annotations
import argparse, json, shutil
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
MASTER = BACKEND / "docs" / "leaklab_gto_ranges.json"
SEED   = BACKEND / "docs" / "leaklab_gto_ranges_gw_seed.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite", action="store_true", help="prefere o seed em conflito")
    ap.add_argument("--master", default=str(MASTER))
    ap.add_argument("--seed", default=str(SEED))
    args = ap.parse_args()

    master = json.load(open(args.master, encoding="utf-8"))
    seed   = json.load(open(args.seed, encoding="utf-8"))
    m_ranges = master.setdefault("ranges", {})
    s_ranges = seed.get("ranges", {})

    added = Counter()       # (scenario) -> n adicionados
    overwritten = Counter()
    skipped = Counter()     # já existia e sem --overwrite

    for bucket, scen_map in s_ranges.items():
        m_bk = m_ranges.setdefault(bucket, {})
        for scen, payload in scen_map.items():
            m_scen = m_bk.setdefault(scen, {})
            if scen == "RFI":
                # RFI: {hero_pos -> spot}
                for hero, spot in payload.items():
                    if hero in m_scen and not args.overwrite:
                        skipped[scen] += 1; continue
                    if hero in m_scen:
                        overwritten[scen] += 1
                    else:
                        added[scen] += 1
                    m_scen[hero] = spot
            else:
                # 2 níveis: {k1 -> {k2 -> spot}}
                for k1, k2map in payload.items():
                    m_k1 = m_scen.setdefault(k1, {})
                    for k2, spot in k2map.items():
                        if k2 in m_k1 and not args.overwrite:
                            skipped[scen] += 1; continue
                        if k2 in m_k1:
                            overwritten[scen] += 1
                        else:
                            added[scen] += 1
                        m_k1[k2] = spot

    print("Adicionados:", dict(added))
    print("Sobrescritos:", dict(overwritten))
    print("Pulados (já existiam, sem --overwrite):", dict(skipped))

    if args.dry_run:
        print("\nDRY-RUN — nada gravado.")
        return

    # backup + write
    bk = Path(args.master).with_suffix(".bak.pre_seed_merge.json")
    shutil.copy2(args.master, bk)
    with open(args.master, "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] master atualizado. Backup: {bk.name}")
    print("Próximo: sync_gto_labels_from_ranges --force --save -> resync_postflop_gto -> auditoria.")


if __name__ == "__main__":
    main()
