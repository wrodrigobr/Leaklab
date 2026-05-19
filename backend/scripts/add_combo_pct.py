"""
add_combo_pct.py — Adiciona combo_pct a cada entrada RFI do leaklab_gto_ranges.json.

combo_pct = (pairs*6 + suited*4 + offsuit*12) / 1326
grid_pct  = total_cells / 169  (o que estava salvo como 'pct')

Renomeia 'pct' -> 'grid_pct' e adiciona 'combo_pct'.
Faz o mesmo para limp_pct -> limp_grid_pct + limp_combo_pct.

Uso:
    cd backend
    python scripts/add_combo_pct.py
    python scripts/add_combo_pct.py --dry-run
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

RANGES_FILE = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"

TOTAL_COMBOS = 1326
TOTAL_CELLS  = 169


def _expand_unique(hands_str: str) -> set[str]:
    """Expande notacao de range em conjunto deduplicated de hand_types."""
    if not hands_str or "N/A" in hands_str.upper():
        return set()
    from leaklab.gto_utils import expand_range_notation
    unique: set[str] = set()
    for part in hands_str.split(","):
        part = part.strip()
        if not part:
            continue
        for h in expand_range_notation(part):
            unique.add(h)
    return unique


def _combos(hands: set[str]) -> int:
    pairs   = sum(1 for h in hands if len(h) == 2)
    suited  = sum(1 for h in hands if h.endswith("s"))
    offsuit = sum(1 for h in hands if h.endswith("o"))
    return pairs * 6 + suited * 4 + offsuit * 12


def hands_to_combo_pct(hands_str: str, exclude_str: str = "") -> float:
    """Calcula combo% real de uma string de range.
    exclude_str: quando fornecido (ex: raise_hands para limp range),
    subtrai essas maos antes de contar — evita sobrecontagem por
    compressao de notacao (ex: '22+' incluindo pares do raise range).
    """
    if not hands_str or "N/A" in hands_str.upper():
        return 0.0
    try:
        unique = _expand_unique(hands_str)
        if exclude_str:
            unique -= _expand_unique(exclude_str)
        return round(_combos(unique) / TOTAL_COMBOS, 4)
    except Exception as e:
        print(f"  [WARN] Erro ao calcular combo_pct para '{hands_str[:40]}': {e}")
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(RANGES_FILE, encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    for bucket, bk_data in data.get("ranges", {}).items():
        rfi = bk_data.get("RFI", {})
        for pos, entry in rfi.items():
            if not isinstance(entry, dict):
                continue

            hands_str = entry.get("hands", "")
            grid_pct  = entry.get("pct", 0)

            combo_pct = hands_to_combo_pct(hands_str)

            # Renomeia pct -> grid_pct, adiciona combo_pct
            entry["grid_pct"]  = round(float(grid_pct), 4)
            entry["combo_pct"] = combo_pct
            # Mantém 'pct' como combo_pct para compatibilidade com código existente
            entry["pct"] = combo_pct

            # Limp range (SB) — exclui raise range para evitar sobrecontagem
            limp_str  = entry.get("limp_hands", "")
            limp_grid = entry.get("limp_grid_pct") or entry.get("limp_pct", 0)
            if limp_str:
                limp_combo = hands_to_combo_pct(limp_str, exclude_str=hands_str)
                entry["limp_grid_pct"]  = round(float(limp_grid), 4)
                entry["limp_combo_pct"] = limp_combo
                entry["limp_pct"]       = limp_combo  # compatibilidade

            print(f"  {bucket}/{pos}: grid={grid_pct:.1%} -> combo={combo_pct:.1%}"
                  + (f" | limp grid={limp_grid:.1%} -> combo={limp_combo:.1%}"
                     if limp_str else ""))
            updated += 1

    data["_metadata"]["versao"] = "2.1.0"
    data["_metadata"]["ultima_atualizacao"] = "2026-05-19"
    data["_metadata"]["nota_pct"] = (
        "pct = combo_pct (combos reais / 1326). "
        "grid_pct = celulas do grid 13x13 / 169 (sempre maior que combo_pct). "
        "Use pct/combo_pct para comparar com GTO Wizard e documentos externos."
    )

    print(f"\n{updated} entradas atualizadas. Versao -> 2.1.0")

    if args.dry_run:
        print("[dry-run] Nao salvando.")
        return

    with open(RANGES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Salvo em: {RANGES_FILE}")


if __name__ == "__main__":
    main()
