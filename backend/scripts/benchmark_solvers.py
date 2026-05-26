"""
benchmark_solvers.py — Compara GTO Wizard vs Texas Postflop (solver remoto GCP).

Usa spots já armazenados no banco com source='gto_wizard' (strategy_json completo).
Para cada spot, consulta o solver remoto SEM salvar no banco.

Uso:
    python scripts/benchmark_solvers.py
    python scripts/benchmark_solvers.py --limit 20 --street flop
    python scripts/benchmark_solvers.py --output benchmark_results.json

Requisitos:
    - GTO_SOLVER_URL e GTO_SOLVER_API_KEY no .env ou ambiente
    - Pelo menos um spot com source='gto_wizard' no banco
"""
from __future__ import annotations
import json
import os
import sys
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from database.schema import get_conn
from leaklab.gto_solver import _call_remote_solver, _DEFAULT_RANGES, _DEFAULT_RANGE_WIDE


# Midpoint de cada bucket para reconstruir stack_bb ao chamar o solver
_BUCKET_MIDPOINTS = {
    "0-10bb":   8.0,
    "10-20bb":  15.0,
    "20-35bb":  27.0,
    "35-60bb":  47.0,
    "60-100bb": 80.0,
    "100bb+":   120.0,
}


def _load_gto_wizard_spots(street_filter: str | None, limit: int) -> list[dict]:
    conn = get_conn()
    try:
        q = """
            SELECT spot_hash, street, position, board, hero_hand,
                   stack_bucket, gto_action, gto_freq, strategy_json,
                   exploitability_pct
            FROM gto_nodes
            WHERE source = 'gto_wizard'
              AND strategy_json IS NOT NULL
        """
        params: list = []
        if street_filter:
            q += " AND street = ?"
            params.append(street_filter.lower())
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _parse_strategy(strategy_json: str) -> dict[str, float]:
    """Normaliza strategy_json para {action: frequency}."""
    raw = json.loads(strategy_json)
    result: dict[str, float] = {}
    for action, val in raw.items():
        if isinstance(val, dict):
            result[action] = float(val.get("frequency", 0.0))
        else:
            result[action] = float(val)
    return result


def _norm_action(a: str) -> str:
    """Normaliza variantes de ação para comparação."""
    return {"raise": "bet", "all-in": "allin", "jam": "allin", "all_in": "allin"}.get(
        a.lower().strip(), a.lower().strip()
    )


def _derive_label(strategy: dict[str, float], played_action: str) -> str:
    na = _norm_action(played_action)
    freq = strategy.get(na, 0.0)
    if freq >= 0.60:
        return "gto_correct"
    if freq >= 0.30:
        return "gto_mixed"
    if freq >= 0.10:
        return "gto_minor_deviation"
    return "gto_critical"


def _top_action(strategy: dict[str, float]) -> tuple[str, float]:
    if not strategy:
        return ("?", 0.0)
    top = max(strategy.items(), key=lambda x: x[1])
    return top


def _strategy_delta(s1: dict[str, float], s2: dict[str, float]) -> float:
    """Média das diferenças absolutas por ação (union de todas as ações)."""
    all_actions = set(s1) | set(s2)
    if not all_actions:
        return 0.0
    return sum(abs(s1.get(a, 0.0) - s2.get(a, 0.0)) for a in all_actions) / len(all_actions)


def _build_solver_payload(spot: dict) -> dict:
    board = json.loads(spot["board"]) if isinstance(spot["board"], str) else spot["board"]
    position = (spot["position"] or "BTN").upper()
    stack_bb = _BUCKET_MIDPOINTS.get(spot["stack_bucket"] or "", 30.0)
    street = spot["street"].lower()

    oop_range = _DEFAULT_RANGES.get(position, _DEFAULT_RANGE_WIDE)
    ip_range  = _DEFAULT_RANGE_WIDE
    pot_bb    = max(4.0, stack_bb * 0.1)

    return {
        "street":                    street,
        "board":                     board,
        "oop_range":                 oop_range,
        "ip_range":                  ip_range,
        "pot_bb":                    pot_bb,
        "effective_stack_bb":        min(stack_bb, 60.0),
        "max_iterations":            200,
        "target_exploitability_pct": 5.0,
        "facing_size_bb":            0.0,
    }


def run_benchmark(spots: list[dict], delay: float) -> list[dict]:
    results = []
    url = os.environ.get("GTO_SOLVER_URL", "")
    if not url:
        print("ERROR: GTO_SOLVER_URL não está definido. Configure no .env ou ambiente.")
        sys.exit(1)

    print(f"\nBenchmark: {len(spots)} spots GTO Wizard vs Texas Postflop ({url})")
    print(f"{'─' * 70}")
    print(f"{'#':<4} {'Street':<8} {'Pos':<5} {'Board':<18} {'GW Top':<12} {'TX Top':<12} {'Δavg':>6} {'Match':>6}")
    print(f"{'─' * 70}")

    for i, spot in enumerate(spots):
        gw_strategy = _parse_strategy(spot["strategy_json"])
        gw_top_action, gw_top_freq = _top_action(gw_strategy)

        board_raw = json.loads(spot["board"]) if isinstance(spot["board"], str) else spot["board"]
        board_str = " ".join(board_raw[:5]) if board_raw else "?"
        street = spot["street"]
        position = spot["position"]

        payload = _build_solver_payload(spot)
        t0 = time.time()
        remote = _call_remote_solver(payload, timeout=120)
        elapsed = time.time() - t0

        result: dict = {
            "spot_hash":      spot["spot_hash"],
            "street":         street,
            "position":       position,
            "board":          board_str,
            "stack_bucket":   spot["stack_bucket"],
            "gw_strategy":    gw_strategy,
            "gw_top_action":  gw_top_action,
            "gw_top_freq":    gw_top_freq,
            "gw_gto_action":  spot["gto_action"],
            "tx_strategy":    None,
            "tx_top_action":  None,
            "tx_top_freq":    None,
            "tx_exploitability_pct": None,
            "tx_elapsed_s":   round(elapsed, 1),
            "strategy_delta": None,
            "top_action_match": None,
            "label_delta":    None,
            "error":          None,
        }

        if remote is None:
            result["error"] = "solver_unavailable"
            print(f"{i+1:<4} {street:<8} {position:<5} {board_str:<18} "
                  f"{gw_top_action:<12} {'TIMEOUT':<12} {'—':>6} {'—':>6}")
        else:
            strategy_detail = remote.get("strategy_detail") or remote.get("strategy", {})
            if isinstance(strategy_detail, dict):
                tx_strategy = {k: float(v["frequency"] if isinstance(v, dict) else v)
                               for k, v in strategy_detail.items()}
            elif isinstance(strategy_detail, list):
                tx_strategy = {s["action"]: float(s["frequency"]) for s in strategy_detail}
            else:
                tx_strategy = {}

            tx_top_action, tx_top_freq = _top_action(tx_strategy)
            exploit = remote.get("exploitability_pct")
            delta = _strategy_delta(gw_strategy, tx_strategy)
            match = _norm_action(gw_top_action) == _norm_action(tx_top_action) if tx_top_action != "?" else None

            # Label agreement: does both agree on what the top action label would be?
            gw_label = _derive_label(gw_strategy, gw_top_action)
            tx_label = _derive_label(tx_strategy, gw_top_action) if tx_strategy else None
            label_match = gw_label == tx_label if tx_label else None

            result.update({
                "tx_strategy":            tx_strategy,
                "tx_top_action":          tx_top_action,
                "tx_top_freq":            tx_top_freq,
                "tx_exploitability_pct":  float(exploit) if exploit else None,
                "strategy_delta":         round(delta, 4),
                "top_action_match":       match,
                "label_delta":            label_match,
            })

            match_str = "✓" if match else "✗"
            expl_str  = f"{exploit:.1f}%" if exploit else "?"
            print(f"{i+1:<4} {street:<8} {position:<5} {board_str:<18} "
                  f"{gw_top_action}({gw_top_freq:.0%})".ljust(12) + " " +
                  f"{tx_top_action}({tx_top_freq:.0%})".ljust(12) + " " +
                  f"{delta*100:.1f}pp".rjust(6) + " " +
                  f"{match_str} exploit={expl_str}")

        results.append(result)
        if i < len(spots) - 1 and delay > 0:
            time.sleep(delay)

    return results


def print_summary(results: list[dict]):
    valid = [r for r in results if r.get("tx_strategy")]
    errors = [r for r in results if r.get("error")]

    print(f"\n{'=' * 70}")
    print(f"RESUMO  ({len(valid)}/{len(results)} spots com resposta do solver)")
    print(f"{'=' * 70}")

    if not valid:
        print("Nenhum spot retornou resultado do solver. Verifique GTO_SOLVER_URL/KEY.")
        return

    deltas = [r["strategy_delta"] for r in valid if r["strategy_delta"] is not None]
    matches = [r for r in valid if r["top_action_match"] is True]
    mismatches = [r for r in valid if r["top_action_match"] is False]
    label_matches = [r for r in valid if r.get("label_delta") is True]

    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    max_delta = max(deltas) if deltas else 0

    print(f"Concordância de ação principal:   {len(matches)}/{len(valid)}  ({len(matches)/len(valid)*100:.0f}%)")
    print(f"Concordância de gto_label:        {len(label_matches)}/{len(valid)}  ({len(label_matches)/len(valid)*100:.0f}%)")
    print(f"Delta médio de estratégia:        {avg_delta*100:.1f} pp  (max {max_delta*100:.1f} pp)")
    if errors:
        print(f"Erros / timeouts:                 {len(errors)}")

    # Por street
    streets: dict[str, list] = {}
    for r in valid:
        s = r["street"]
        streets.setdefault(s, []).append(r)

    if len(streets) > 1:
        print(f"\nPor street:")
        for st, rs in sorted(streets.items()):
            d = [r["strategy_delta"] for r in rs if r["strategy_delta"] is not None]
            m = sum(1 for r in rs if r["top_action_match"] is True)
            print(f"  {st:<8} {len(rs):>3} spots  match={m}/{len(rs)}  Δavg={sum(d)/len(d)*100:.1f}pp")

    if mismatches:
        print(f"\nTop divergências (ação diferente):")
        top5 = sorted(mismatches, key=lambda r: r["strategy_delta"] or 0, reverse=True)[:5]
        for r in top5:
            print(f"  {r['street']:<8} {r['position']:<5} {r['board']:<18} "
                  f"GW={r['gw_top_action']} TX={r['tx_top_action']}  Δ={r['strategy_delta']*100:.1f}pp")


def main():
    parser = argparse.ArgumentParser(description="Benchmark GTO Wizard vs Texas Postflop")
    parser.add_argument("--limit",   type=int, default=30, help="Máx de spots a comparar (default 30)")
    parser.add_argument("--street",  default=None,         help="Filtrar por street: flop, turn, river")
    parser.add_argument("--delay",   type=float, default=1.0, help="Delay entre solves em segundos (default 1.0)")
    parser.add_argument("--output",  default=None,         help="Salvar resultados em JSON (opcional)")
    args = parser.parse_args()

    spots = _load_gto_wizard_spots(args.street, args.limit)
    if not spots:
        print("Nenhum spot gto_wizard encontrado no banco.")
        print("Rode alguns torneios com o solver GTO Wizard primeiro.")
        sys.exit(0)

    print(f"Encontrados {len(spots)} spots com source='gto_wizard' no banco.")

    results = run_benchmark(spots, args.delay)
    print_summary(results)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResultados salvos em: {args.output}")


if __name__ == "__main__":
    main()
