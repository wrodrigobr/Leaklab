"""
validate_ranges_vs_solver.py — Valida leaklab_gto_ranges.json contra o solver remoto.

Para cada spot RFI do JSON, consulta o endpoint /gto-wizard do servidor remoto e
compara a frequência de raise (pct) do nosso JSON com a do GTO Wizard.

Critérios:
  agreement       : |nossa_pct - gw_raise_pct| <= 0.05
  close           : diferença entre 0.05 e 0.10
  divergence      : diferença > 0.10

Escopo:
  - Spots RFI (facing_size=0) para todas as posições × stack buckets
  - vs_RFI e push_fold retornam 204/403 do GW neste contexto (documentado)

Uso:
  cd backend
  python scripts/validate_ranges_vs_solver.py               # relatório
  python scripts/validate_ranges_vs_solver.py --save        # salva JSON
  python scripts/validate_ranges_vs_solver.py --pos BTN     # só uma posição
  python scripts/validate_ranges_vs_solver.py --stack 30bb  # só um bucket
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

RANGES_PATH = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"
OUTPUT_PATH = BACKEND_DIR / "scripts" / "gto_validation" / "comparison_preflop.json"

GTO_SOLVER_URL = os.environ.get("GTO_SOLVER_URL", "").rstrip("/")
GTO_SOLVER_KEY = os.environ.get("GTO_SOLVER_API_KEY", "")

# Positions supported by GTO Wizard via /gto-wizard endpoint
SUPPORTED_POSITIONS = {"UTG", "LJ", "HJ", "CO", "BTN", "SB"}

AGREEMENT_THRESHOLD = 0.05
CLOSE_THRESHOLD     = 0.10


def _query_gw(position: str, stack_bb: float, facing_size_bb: float = 0.0) -> dict:
    """Calls /gto-wizard on remote solver. Returns dict with found, strategy, error."""
    if not GTO_SOLVER_URL or not GTO_SOLVER_KEY:
        return {"found": False, "error": "solver_not_configured"}
    try:
        import requests
        r = requests.post(
            f"{GTO_SOLVER_URL}/gto-wizard",
            json={"street": "preflop", "position": position,
                  "hero_stack_bb": stack_bb, "facing_size_bb": facing_size_bb},
            headers={"x-api-key": GTO_SOLVER_KEY},
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
        return {"found": False, "error": f"http_{r.status_code}"}
    except Exception as e:
        return {"found": False, "error": str(e)[:80]}


def _stack_bb_from_key(key: str) -> float:
    return float(key.replace("bb", ""))


def _our_raise_pct(entry: dict) -> float | None:
    """Extract our raise/open frequency from a RFI entry."""
    pct = entry.get("pct") or entry.get("combo_pct") or entry.get("grid_pct")
    return float(pct) if pct is not None else None


def _gw_raise_pct(strategy: list[dict]) -> float:
    """Sum raise + allin frequencies from GTO Wizard strategy."""
    return sum(
        s["frequency"] for s in strategy
        if s.get("action") in ("raise", "allin")
    )


def _verdict(our: float, gw: float) -> str:
    diff = abs(our - gw)
    if diff <= AGREEMENT_THRESHOLD:
        return "agreement"
    if diff <= CLOSE_THRESHOLD:
        return "close"
    return "divergence"


def run_validation(
    filter_pos: str | None = None,
    filter_stack: str | None = None,
    verbose: bool = True,
) -> list[dict]:
    with open(RANGES_PATH) as f:
        data = json.load(f)
    ranges = data["ranges"]

    results: list[dict] = []
    skipped_403 = skipped_204 = skipped_no_data = 0

    for stack_key, bucket in ranges.items():
        if filter_stack and stack_key != filter_stack:
            continue
        if not isinstance(bucket, dict):
            continue
        rfi = bucket.get("RFI", {})
        if not isinstance(rfi, dict):
            continue
        stack_bb = _stack_bb_from_key(stack_key)

        for position, entry in rfi.items():
            if filter_pos and position.upper() != filter_pos.upper():
                continue
            if position not in SUPPORTED_POSITIONS:
                skipped_no_data += 1
                continue
            if not isinstance(entry, dict):
                skipped_no_data += 1
                continue

            our_pct = _our_raise_pct(entry)
            if our_pct is None:
                skipped_no_data += 1
                continue

            time.sleep(0.3)  # avoid hammering the server
            gw = _query_gw(position, stack_bb, facing_size_bb=0.0)

            result: dict = {
                "stack": stack_key,
                "position": position,
                "our_raise_pct": round(our_pct, 4),
                "gw_found": gw.get("found", False),
                "gw_raise_pct": None,
                "diff": None,
                "verdict": None,
                "error": gw.get("error"),
            }

            if gw.get("found") and gw.get("strategy"):
                gw_pct = _gw_raise_pct(gw["strategy"])
                diff = our_pct - gw_pct
                v = _verdict(our_pct, gw_pct)
                result.update({
                    "gw_raise_pct": round(gw_pct, 4),
                    "diff": round(diff, 4),
                    "verdict": v,
                    "error": None,
                })
                if verbose:
                    symbol = "OK" if v == "agreement" else ("~" if v == "close" else "DIVERGE")
                    print(f"  [{symbol}] {position:<4} {stack_key:<5} "
                          f"our={our_pct:.3f} gw={gw_pct:.3f} diff={diff:+.3f}")
            else:
                err = gw.get("error", "")
                if "403" in err:
                    skipped_403 += 1
                elif "204" in err:
                    skipped_204 += 1
                else:
                    skipped_no_data += 1
                if verbose:
                    print(f"  [SKIP] {position:<4} {stack_key:<5} — {err}")

            results.append(result)

    if verbose:
        compared = [r for r in results if r["verdict"]]
        agreement = sum(1 for r in compared if r["verdict"] == "agreement")
        close     = sum(1 for r in compared if r["verdict"] == "close")
        diverg    = sum(1 for r in compared if r["verdict"] == "divergence")
        print()
        print(f"Spots comparados : {len(compared)} / {len(results)}")
        print(f"  Agreement (<=5%): {agreement}")
        print(f"  Close (5-10%)   : {close}")
        print(f"  Divergence (>10%): {diverg}")
        if skipped_403:
            print(f"  Skipped 403 (plan limit): {skipped_403}")
        if skipped_204:
            print(f"  Skipped 204 (no GW node): {skipped_204}")
        if diverg:
            print()
            print("Divergencias:")
            for r in results:
                if r["verdict"] == "divergence":
                    print(f"  {r['position']:<4} {r['stack']:<5} "
                          f"our={r['our_raise_pct']:.3f} gw={r['gw_raise_pct']:.3f} "
                          f"diff={r['diff']:+.3f}")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save",  action="store_true", help="Salva resultados em JSON")
    parser.add_argument("--pos",   default=None, help="Filtrar por posicao (BTN, CO...)")
    parser.add_argument("--stack", default=None, help="Filtrar por stack (30bb, 50bb...)")
    args = parser.parse_args()

    if not GTO_SOLVER_URL:
        print("GTO_SOLVER_URL nao configurado. Defina no .env")
        sys.exit(1)

    print(f"Servidor: {GTO_SOLVER_URL}")
    print(f"Ranges  : {RANGES_PATH}")
    print()

    results = run_validation(
        filter_pos=args.pos,
        filter_stack=args.stack,
        verbose=True,
    )

    if args.save:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSalvo em {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
