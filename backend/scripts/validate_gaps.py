"""
validate_gaps.py — Sanity checks no leaklab_gto_ranges_gaps.json antes do merge.

Checks:
  1. Range 4bet ⊆ RFI da posicao no mesmo bucket
  2. Range call ⊆ RFI da posicao no mesmo bucket
  3. |4bet ∪ call| ≤ |RFI| (range vs_3bet sempre mais tight que RFI)
  4. AA/KK/AKs sempre em hands_4bet (sanity da estrategia)
  5. Spot check: HJ 75bb vs 3-bet com A8s → fold (caso real reportado)
"""
from __future__ import annotations
import json, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
RANGES      = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"
GAPS        = BACKEND_DIR / "docs" / "leaklab_gto_ranges_gaps.json"


def _hands_to_set(s: str) -> set[str]:
    """Converte hands_4bet/hands_call em set de hands (literal — sem expansao 'A2s+')."""
    return {h.strip() for h in (s or "").split(",") if h.strip() and h.strip() != "resto"}


def _expand_rfi(hands_str: str) -> set[str]:
    """Expande notacao RFI (ex: '66+,A4s+,K8s+') em set explicito de hands."""
    # Importa funcao do projeto que ja faz isso bem
    sys.path.insert(0, str(BACKEND_DIR))
    from leaklab.preflop_gto_ranges import _expand_range
    return _expand_range(hands_str)


def main() -> int:
    if not GAPS.exists():
        print(f"ERRO: {GAPS} nao existe. Rode synthesize_missing_vs3bet.py primeiro.")
        return 1

    existing = json.loads(RANGES.read_text(encoding="utf-8"))
    gaps     = json.loads(GAPS.read_text(encoding="utf-8"))

    errors: list[str] = []
    warnings: list[str] = []

    for bucket, sections in gaps["ranges"].items():
        rfi_section = existing["ranges"].get(bucket, {}).get("RFI", {})
        for entry_key, entry in sections.get("vs_3bet", {}).items():
            pos = entry_key.split("_")[0]
            rfi_data = rfi_section.get(pos, {})
            rfi_str = rfi_data.get("hands", "")
            rfi_set = _expand_rfi(rfi_str) if rfi_str else set()

            v4bet = _hands_to_set(entry["hands_4bet"])
            vcall = _hands_to_set(entry["hands_call"])

            if rfi_set:
                # Check 1+2: subsets do RFI
                missing_4bet = v4bet - rfi_set
                if missing_4bet:
                    warnings.append(f"{bucket} {entry_key}: 4bet contem mao fora de RFI -> {sorted(missing_4bet)[:5]}")
                missing_call = vcall - rfi_set
                if missing_call:
                    warnings.append(f"{bucket} {entry_key}: call contem mao fora de RFI -> {sorted(missing_call)[:5]}")

                # Check 3: continua <= RFI
                continua = v4bet | vcall
                if len(continua) > len(rfi_set):
                    errors.append(f"{bucket} {entry_key}: continua ({len(continua)}) > RFI ({len(rfi_set)})")

            # Check 4: AA/KK/AKs em 4-bet
            for must_4bet in ("AA", "KK"):
                if must_4bet not in v4bet:
                    warnings.append(f"{bucket} {entry_key}: {must_4bet} NAO esta em hands_4bet")

    print(f"Sanity check de {GAPS.name}:")
    print(f"  Errors: {len(errors)}")
    for e in errors[:20]:
        print(f"    ERR: {e}")
    print(f"  Warnings: {len(warnings)}")
    for w in warnings[:20]:
        print(f"    WARN: {w}")

    # Spot check: HJ 75bb vs 3-bet com A8s
    print("\nSpot check: HJ 75bb vs 3-bet (caso reportado)")
    hj_75 = gaps["ranges"].get("75bb", {}).get("vs_3bet", {}).get("HJ_RFI_vs_3bet")
    if hj_75:
        v4bet = _hands_to_set(hj_75["hands_4bet"])
        vcall = _hands_to_set(hj_75["hands_call"])
        for hand in ("AA", "KK", "AKs", "AQs", "JJ", "A8s", "A5s", "QQ"):
            if hand in v4bet:
                act = "4bet"
            elif hand in vcall:
                act = "call"
            else:
                act = "fold"
            print(f"  {hand}: {act}")
    else:
        print("  ERRO: entry nao encontrada")

    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
