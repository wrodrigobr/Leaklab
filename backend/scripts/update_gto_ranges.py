"""
update_gto_ranges.py — Atualiza leaklab_gto_ranges.json com dados extraídos do PDF RegLife.

Substitui as entradas RFI de cada stack bucket pelos ranges extraídos via pixel analysis.
Preserva: metadata, stack_buckets, vs_RFI, vs_3bet e dados do 10bb (push/fold).
Adiciona: num_players=8, source=reglife_pdf para os stacks cobertos.

Uso:
    cd backend
    python scripts/update_gto_ranges.py
    python scripts/update_gto_ranges.py --dry-run   # só exibe, não salva
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
EXISTING    = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"
REGLIFE     = BACKEND_DIR / "docs" / "leaklab_gto_ranges_reglife.json"
OUT         = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"

# Mapeamento: stack_bucket existente → chave RegLife mais próxima
# (usa dados RegLife onde disponível, interpolação nos outros)
BUCKET_TO_REGLIFE = {
    "10bb":  None,      # push/fold, manter existente
    "14bb":  "14bb",    # RegLife 14bb direto
    "20bb":  "20bb",    # RegLife 20bb (cobre 17-24bb)
    "30bb":  "30bb",    # RegLife 30bb direto
    "40bb":  None,      # interpolar 30bb e 50bb → manter existente
    "50bb":  "50bb",    # RegLife 50bb direto
    "75bb":  None,      # interpolar 50bb e 100bb → manter existente
    "100bb": "100bb",   # RegLife 100bb direto
}

POSITIONS = ['UTG', 'UTG1', 'LJ', 'HJ', 'CO', 'BTN', 'SB']

# RegLife usa 'MP' como 'UTG1' equivalente (segunda posição de abertura)
REGLIFE_POS_MAP = {
    'UTG':  'UTG',
    'UTG1': 'MP',   # UTG1/MP equivalente no RegLife
    'LJ':   'LJ',
    'HJ':   'HJ',
    'CO':   'CO',
    'BTN':  'BTN',
    'SB':   'SB',
}


def load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load(EXISTING)
    reglife  = load(REGLIFE)

    updated_buckets = []
    unchanged_buckets = []

    for bucket, rl_key in BUCKET_TO_REGLIFE.items():
        if bucket not in existing["ranges"]:
            continue

        if rl_key is None:
            unchanged_buckets.append(bucket)
            continue

        rl_data = reglife["ranges"].get(rl_key)
        if not rl_data:
            print(f"[WARN] RegLife nao tem dados para {rl_key}, mantendo {bucket}")
            unchanged_buckets.append(bucket)
            continue

        rfi_section = existing["ranges"][bucket].setdefault("RFI", {})

        for pos in POSITIONS:
            rl_pos = REGLIFE_POS_MAP.get(pos)
            if not rl_pos:
                continue

            rl_entry = rl_data.get("RFI", {}).get(rl_pos)
            if not rl_entry:
                continue

            # Constrói nova entrada com dados RegLife
            new_entry = {
                "pct":    rl_entry["pct"],
                "hands":  rl_entry["hands"],
                "acoes":  rl_entry["acoes"],
                "_fonte": f"reglife_pdf/{rl_key}",
            }

            # Propaga limp range para SB
            if pos == "SB" and rl_entry.get("limp_hands"):
                new_entry["limp_pct"]   = rl_entry["limp_pct"]
                new_entry["limp_hands"] = rl_entry["limp_hands"]
                new_entry["acoes_limp"] = ["CALL"]

            old_entry = rfi_section.get(pos, {})
            old_pct   = old_entry.get("pct", 0)
            rfi_section[pos] = new_entry

            print(f"  {bucket}/{pos}: pct {old_pct:.3f} -> {new_entry['pct']:.3f} | "
                  f"{new_entry['hands'][:50]}")

        # Garante que BB está definido
        rfi_section["BB"] = {
            "pct":    0.0,
            "hands":  "N/A - BB nao tem RFI",
            "acoes":  [],
            "_fonte": "n/a",
        }

        updated_buckets.append(bucket)

    # Atualiza metadata
    existing["_metadata"]["versao"]         = "2.0.0"
    existing["_metadata"]["num_players"]    = 8
    existing["_metadata"]["ultima_atualizacao"] = "2026-05-18"
    existing["_metadata"]["fontes"].append("RegLife PDF - Ranges RFI e vs RFI (pixel analysis)")
    existing["_metadata"]["descricao"] = (
        "Ranges GTO preflop para MTT 8-max com ante de 1bb. "
        "RFI atualizado com dados RegLife (solver-generated) via pixel analysis. "
        "vs_RFI preservado da versão anterior."
    )

    print(f"\nBuckets atualizados   : {updated_buckets}")
    print(f"Buckets preservados   : {unchanged_buckets}")

    if args.dry_run:
        print("\n[dry-run] Nao salvando.")
        return

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\nSalvo em: {OUT}")


if __name__ == "__main__":
    main()
