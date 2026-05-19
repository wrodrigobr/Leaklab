"""
compare_ranges_gw.py — Compara range% do RegLife v2.0 vs GTO Wizard por posicao/stack.

O GTO Wizard preflop retorna a estrategia AGREGADA da posicao (raise frequency = range%).
A comparacao correta e: RegLife range_pct vs GW raise_frequency por posicao/stack.

Uso:
    cd backend
    python scripts/compare_ranges_gw.py
    python scripts/compare_ranges_gw.py --stacks 20 30 50 100
"""
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import requests as _req

GW_URL = os.environ.get("GTO_SOLVER_URL", "http://34.70.251.42:8765")
GW_KEY = os.environ.get("GTO_SOLVER_API_KEY", "")

POSITIONS = ["UTG", "UTG1", "LJ", "HJ", "CO", "BTN", "SB"]
STACKS    = [14, 20, 30, 50, 100]

# Mapeamento posicao leaklab -> GTO Wizard
POS_TO_GW = {
    "UTG":  "UTG",
    "UTG1": "UTG1",  # pode ser MP no GW
    "LJ":   "LJ",
    "HJ":   "HJ",
    "CO":   "CO",
    "BTN":  "BTN",
    "SB":   "SB",
}


def get_rl_range_pct(pos: str, stack: float) -> float | None:
    """Retorna range% do RegLife para posicao/stack (raise range)."""
    import json
    ranges_file = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"
    with open(ranges_file, encoding="utf-8") as f:
        data = json.load(f)

    # Stack bucket
    bucket = None
    for label, bounds in data.get("stack_buckets", {}).items():
        if bounds["min"] <= stack <= bounds["max"]:
            bucket = label
            break
    if not bucket:
        return None

    pos_map = {"UTG+1": "UTG1", "UTG+2": "LJ", "MP": "LJ", "MP1": "LJ", "MP2": "HJ"}
    pos_key = pos_map.get(pos.upper(), pos.upper())

    entry = data.get("ranges", {}).get(bucket, {}).get("RFI", {}).get(pos_key)
    if not entry:
        return None
    return entry.get("pct", 0), entry.get("limp_pct", 0), entry.get("_fonte", "?"), bucket


def query_gw_position(pos: str, stack: float) -> dict:
    """Consulta GTO Wizard e retorna raise_frequency da posicao."""
    gw_pos = POS_TO_GW.get(pos, pos)
    try:
        r = _req.post(
            f"{GW_URL}/gto-wizard",
            json={
                "street":         "preflop",
                "position":       gw_pos,
                "board":          [],
                "hero_stack_bb":  float(stack),
                "facing_size_bb": 0.0,
                "pot_bb":         0.0,
            },
            headers={"x-api-key": GW_KEY},
            timeout=15,
        )
        if not r.ok:
            return {"found": False, "error": f"http_{r.status_code}"}
        data = r.json()
        if not data.get("found"):
            return {"found": False, "error": data.get("error", "not_found")}

        strategy = data.get("strategy", [])
        freqs = {}
        for s in strategy:
            act = s.get("action", "").lower()
            freqs[act] = freqs.get(act, 0) + s.get("frequency", 0)

        raise_freq = freqs.get("raise", 0) + freqs.get("allin", 0)
        fold_freq  = freqs.get("fold", 0)
        call_freq  = freqs.get("call", 0)

        return {
            "found":       True,
            "raise_freq":  raise_freq,
            "fold_freq":   fold_freq,
            "call_freq":   call_freq,
            "freqs":       freqs,
        }
    except Exception as e:
        return {"found": False, "error": str(e)[:40]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stacks", type=int, nargs="+", default=STACKS)
    parser.add_argument("--delay",  type=float, default=0.3)
    args = parser.parse_args()

    # Verifica auth
    try:
        st = _req.get(f"{GW_URL}/gw-status", headers={"x-api-key": GW_KEY}, timeout=5).json()
        print(f"GTO Wizard: auth_ok={st.get('auth_ok')} age={st.get('age_sec',0):.0f}s\n")
        if not st.get("auth_ok"):
            print("[AVISO] GW auth expirada — resultados podem ser incorretos.\n")
    except Exception as e:
        print(f"[ERRO] Servidor GW inacessivel: {e}\n")
        return

    print("Comparando range% do RegLife v2.0 vs GTO Wizard por posicao/stack")
    print("(GW raise_frequency = % de maos que abrem nessa posicao = range%)")
    print()

    total_comparisons = 0
    aligned = 0
    divergent_spots: list[dict] = []

    for stack in args.stacks:
        print(f"\n{'='*80}")
        print(f"Stack: {stack}bb")
        print(f"{'='*80}")
        print(f"{'POS':<6} {'RL_PCT':>7} {'RL_LIMP':>8} {'GW_RAISE':>9} {'GW_CALL':>8} {'DIFF':>7} {'DELTA':>7} {'STATUS'}")
        print("-"*70)

        for pos in POSITIONS:
            rl_result = get_rl_range_pct(pos, float(stack))
            if rl_result is None:
                print(f"{pos:<6} {'n/a':>7}")
                continue

            rl_pct, rl_limp, fonte, bucket = rl_result
            gw = query_gw_position(pos, float(stack))

            if not gw["found"]:
                err = gw.get("error", "?")
                print(f"{pos:<6} {rl_pct:>6.1%}          {'n/a':>9}          [{err}]")
                continue

            gw_raise = gw["raise_freq"]
            gw_call  = gw["call_freq"]
            delta    = rl_pct - gw_raise
            abs_delta = abs(delta)

            # Status
            if abs_delta <= 0.05:
                status = "OK (<5%)"
                aligned += 1
            elif abs_delta <= 0.10:
                status = "~OK (<10%)"
                aligned += 1
            elif abs_delta <= 0.15:
                status = "ATENCAO (15%)"
            else:
                status = f"DIVERGE ({abs_delta:.0%})"
                divergent_spots.append({
                    "pos": pos, "stack": stack, "bucket": bucket,
                    "rl_pct": rl_pct, "gw_raise": gw_raise, "delta": delta,
                    "fonte": fonte,
                })

            total_comparisons += 1

            limp_str = f"{rl_limp:.1%}" if rl_limp > 0 else "   -  "
            delta_str = f"{delta:+.1%}"
            print(f"{pos:<6} {rl_pct:>6.1%} {limp_str:>8} {gw_raise:>8.1%} {gw_call:>8.1%} {delta_str:>7} {'':<4} {status}")

            if args.delay:
                time.sleep(args.delay)

    # Sumario
    print(f"\n{'='*80}")
    print("SUMARIO FINAL")
    print(f"{'='*80}")
    print(f"Comparacoes realizadas : {total_comparisons}")
    if total_comparisons > 0:
        pct_aligned = aligned / total_comparisons
        print(f"Alinhados (<10% delta) : {aligned}/{total_comparisons} ({pct_aligned:.0%})")
        print(f"Divergentes            : {len(divergent_spots)}/{total_comparisons}")

    if divergent_spots:
        print(f"\nSpots com maior divergencia (>15%):")
        print(f"{'POS':<6} {'STACK':>6} {'BUCKET':<8} {'RL_PCT':>7} {'GW_RAISE':>9} {'DELTA':>7} FONTE")
        print("-"*60)
        for s in sorted(divergent_spots, key=lambda x: -abs(x["delta"])):
            print(f"{s['pos']:<6} {s['stack']:>6}bb {s['bucket']:<8} {s['rl_pct']:>6.1%} "
                  f"{s['gw_raise']:>8.1%} {s['delta']:>+7.1%}  {s['fonte']}")

    if total_comparisons > 0:
        pct = aligned / total_comparisons
        print(f"\nConclusao: RegLife alinhado com GTO Wizard em {pct:.0%} das posicoes.")
        if pct >= 0.75:
            print("=> RegLife APROVADO como referencia primaria preflop.")
        elif pct >= 0.55:
            print("=> RegLife PARCIALMENTE alinhado. Verificar posicoes divergentes.")
        else:
            print("=> RegLife com BAIXO alinhamento. Necessita revisao de extracao.")


if __name__ == "__main__":
    main()
