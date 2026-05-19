"""
interpolate_vsrfi.py — Preenche vs_RFI de 40bb e 75bb por interpolação 50/50.

40bb = média(30bb, 50bb)
75bb = média(50bb, 100bb)

Preserva todos os outros dados do bucket (RFI, vs_3bet, etc.).
Adiciona _source='interpolated_reglife' para identificar origem.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
JSON_PATH   = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"


def interp(a: float, b: float) -> float:
    return round((a + b) / 2, 4)


def interp_spot(slo: dict, shi: dict) -> dict:
    result = {
        "fold_pct":   interp(slo["fold_pct"],   shi["fold_pct"]),
        "call_pct":   interp(slo["call_pct"],   shi["call_pct"]),
        "raise_pct":  interp(slo["raise_pct"],  shi["raise_pct"]),
        "allin_pct":  interp(slo["allin_pct"],  shi["allin_pct"]),
        "aggr_pct":   interp(slo["aggr_pct"],   shi["aggr_pct"]),
        "_source":    "interpolated_reglife",
    }
    # Interpola handstrings apenas se ambos tiverem (evita mistura inconsistente)
    for key in ("fold_hands", "call_hands", "raise_hands", "allin_hands"):
        if key in slo and key in shi:
            # Não há interpolação de strings — omite para não confundir
            pass
    return result


def build_vsrfi(rlo: dict, rhi: dict) -> dict:
    result = {}
    for opener in set(rlo) | set(rhi):
        dlo = rlo.get(opener, {})
        dhi = rhi.get(opener, {})
        if not dlo or not dhi:
            continue
        result[opener] = {}
        for defender in set(dlo) | set(dhi):
            slo = dlo.get(defender)
            shi = dhi.get(defender)
            if not slo or not shi:
                continue
            if "fold_pct" not in slo or "fold_pct" not in shi:
                continue
            result[opener][defender] = interp_spot(slo, shi)
    return result


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    ranges = data["ranges"]
    updated = []

    for target, s_lo, s_hi in [("40bb", "30bb", "50bb"), ("75bb", "50bb", "100bb")]:
        rlo = ranges[s_lo]["vs_RFI"]
        rhi = ranges[s_hi]["vs_RFI"]
        new_vsrfi = build_vsrfi(rlo, rhi)

        n_spots = sum(len(v) for v in new_vsrfi.values())
        ranges[target]["vs_RFI"] = new_vsrfi
        updated.append((target, n_spots))
        print(f"  {target}: {n_spots} spots interpolados de {s_lo}+{s_hi}")

    data["_metadata"]["versao"] = "2.3.0"
    data["_metadata"]["ultima_atualizacao"] = "2026-05-19"
    data["_metadata"]["nota_vsrfi_interp"] = (
        "40bb e 75bb vs_RFI interpolados como media 50/50 dos stacks RegLife vizinhos. "
        "40bb=(30bb+50bb)/2, 75bb=(50bb+100bb)/2. "
        "Handstrings omitidas (sem interpolacao de texto). "
        "Spots marcados com _source='interpolated_reglife'."
    )

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nSalvo em {JSON_PATH.name} — versao 2.3.0")


if __name__ == "__main__":
    main()
