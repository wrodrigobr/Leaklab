"""
Compara estratégias do nosso solver com o GTO Wizard.

Fluxo:
  1. Carrega unique_spots.jsonl
  2. Para cada spot, busca a estratégia no GTO Wizard
  3. Compara com o best_action/score do nosso DB
  4. Gera comparison_results.jsonl + resumo no terminal

Uso:
    export GTOWIZARD_REFRESH_TOKEN="eyJ..."
    python comparator.py [--spots unique_spots.jsonl] [--limit 20] [--output comparison_results.jsonl]
"""
from __future__ import annotations
import os, sys, json, time, argparse, logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.gto_validation.gto_wizard_client import GtoWizardClient, GAMETYPE_MTT_8M
from scripts.gto_validation.preflop_action_builder import get_scenario, COMMON_SCENARIOS

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

SCRIPTS_DIR = os.path.dirname(__file__)


def compare_action(our_action: str, gto_solution) -> dict:
    """
    Compara a ação recomendada pelo nosso sistema com a frequência GTO.
    Retorna verdict e frequência da nossa ação no GTO.
    """
    if not gto_solution.found:
        return {"verdict": "not_found", "our_action_freq": None, "gto_top_action": None}

    our_norm = our_action.lower().strip()
    # Map our action names to GTO Wizard aggregated names
    action_map = {
        "fold": "fold",
        "call": "call",
        "check": "check",
        "bet": "bet",
        "raise": "bet",   # GTO Wizard aggregates raise into bet for postflop
        "all-in": "allin",
        "jam": "allin",
    }
    gto_key = action_map.get(our_norm, our_norm)
    our_freq = gto_solution.actions.get(gto_key, 0.0)

    # Verdict based on GTO frequency of our recommended action
    if our_freq >= 0.40:
        verdict = "agreement"     # GTO agrees (40%+ frequency)
    elif our_freq >= 0.15:
        verdict = "mixed"         # GTO plays it sometimes (mixed strategy)
    else:
        verdict = "divergence"    # GTO rarely/never plays this action

    return {
        "verdict": verdict,
        "our_action_freq": round(our_freq, 4),
        "gto_top_action": gto_solution.top_action,
        "gto_strategy": {k: round(v, 4) for k, v in gto_solution.actions.items()},
    }


def process_spot(spot: dict, client: GtoWizardClient, delay: float = 0.5) -> dict:
    """Fetch GTO Wizard strategy for a spot and compare."""
    result = {
        "spot_id": spot["spot_id"],
        "street": spot["street"],
        "position": spot["position"],
        "villain_position": spot["villain_position"],
        "board": spot["board"],
        "stack_bucket": spot["stack_bucket"],
        "facing_bucket": spot["facing_bucket"],
        "occurrences": spot["occurrences"],
        "our_best_action": spot["example_best_action"],
        "our_label": spot["our_label"],
        "our_score": spot["our_score"],
        "gto_found": False,
        "verdict": "skipped",
        "error": None,
    }

    if spot["street"] != "flop":
        result["verdict"] = "skipped_not_flop"
        return result

    if not spot["board"]:
        result["verdict"] = "skipped_no_board"
        return result

    # Get preflop context from known scenarios
    scenario = get_scenario(
        spot["position"],
        str(spot["villain_position"]),
        spot["facing_bucket"],
    )
    if not scenario:
        result["verdict"] = "skipped_unknown_scenario"
        return result

    preflop_actions = scenario["preflop_actions"]

    # Build flop_actions: if there was a facing bet, add bet action
    if spot["facing_bucket"] > 0:
        # OOP checked, IP bet — simplify to "X-B{approx}"
        pot_frac = spot["facing_bucket"]
        bet_bb = round(spot["facing_bet"], 1) if spot["facing_bet"] else 0
        flop_actions = f"X-B{bet_bb}" if bet_bb > 0 else ""
    else:
        # No bet facing — either start of action or check-check
        flop_actions = ""

    try:
        time.sleep(delay)  # rate limiting — be respectful
        gto = client.get_spot_solution(
            depth=spot["stack_bucket"],
            preflop_actions=preflop_actions,
            board=spot["board"],
            flop_actions=flop_actions,
            gametype=scenario.get("gametype", GAMETYPE_MTT_8M),
        )
        comparison = compare_action(spot["example_best_action"] or "", gto)
        result.update({
            "gto_found": gto.found,
            "verdict": comparison["verdict"],
            "our_action_freq_in_gto": comparison["our_action_freq"],
            "gto_top_action": comparison["gto_top_action"],
            "gto_strategy": comparison.get("gto_strategy", {}),
            "preflop_actions_used": preflop_actions,
            "flop_actions_used": flop_actions,
        })
    except Exception as e:
        result["error"] = str(e)
        result["verdict"] = "error"
        log.error("Error fetching spot %s: %s", spot["spot_id"], e)

    return result


def print_summary(results: list[dict]):
    total = len(results)
    found = [r for r in results if r.get("gto_found")]
    verdicts = {}
    for r in results:
        v = r.get("verdict", "unknown")
        verdicts[v] = verdicts.get(v, 0) + 1

    print(f"\n{'='*65}")
    print(f"GTO WIZARD COMPARISON SUMMARY")
    print(f"{'='*65}")
    print(f"Total spots processed: {total}")
    print(f"GTO Wizard found:      {len(found)}")
    print(f"\nVerdicts:")
    for v, count in sorted(verdicts.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total else 0
        bar = "█" * int(pct / 4)
        print(f"  {v:<25} {count:>4} ({pct:5.1f}%) {bar}")

    if found:
        agreements = [r for r in found if r.get("verdict") == "agreement"]
        mixed = [r for r in found if r.get("verdict") == "mixed"]
        divergences = [r for r in found if r.get("verdict") == "divergence"]
        print(f"\nOf {len(found)} spots found:")
        print(f"  Agreement  (GTO freq >= 40%): {len(agreements):>3} ({len(agreements)/len(found)*100:.0f}%)")
        print(f"  Mixed      (GTO freq 15-40%): {len(mixed):>3} ({len(mixed)/len(found)*100:.0f}%)")
        print(f"  Divergence (GTO freq < 15%):  {len(divergences):>3} ({len(divergences)/len(found)*100:.0f}%)")

        if divergences:
            print(f"\nTop divergences (our action vs GTO):")
            for r in sorted(divergences, key=lambda x: x.get("our_score", 0))[:10]:
                our = r.get("our_best_action", "?")
                gto_top = r.get("gto_top_action", "?")
                freq = r.get("our_action_freq_in_gto", 0)
                board = r.get("board", "")[:10]
                print(f"  {r['position']:<4} vs {str(r['villain_position']):<4} "
                      f"{board:<12} stack={r['stack_bucket']:>4.0f}bb "
                      f"our={our:<6} gto={gto_top:<6} our_freq={freq*100:.0f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spots", default=os.path.join(SCRIPTS_DIR, "unique_spots.jsonl"))
    parser.add_argument("--limit", type=int, default=50, help="Max spots to process")
    parser.add_argument("--delay", type=float, default=0.8, help="Delay between API calls (seconds)")
    parser.add_argument("--output", default=os.path.join(SCRIPTS_DIR, "comparison_results.jsonl"))
    parser.add_argument("--street", default="flop", help="Filter by street (default: flop)")
    args = parser.parse_args()

    if not os.path.exists(args.spots):
        print(f"ERROR: {args.spots} not found. Run spot_extractor.py first.")
        sys.exit(1)

    spots = []
    with open(args.spots, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            if args.street and s.get("street") != args.street:
                continue
            spots.append(s)
            if args.limit and len(spots) >= args.limit:
                break

    print(f"Processing {len(spots)} spots (street={args.street}, limit={args.limit})")
    print(f"Delay between calls: {args.delay}s")
    print()

    client = GtoWizardClient()

    results = []
    for i, spot in enumerate(spots):
        pos = spot.get("position", "?")
        board = spot.get("board", "")[:10]
        stack = spot.get("stack_bucket", 0)
        print(f"[{i+1:>3}/{len(spots)}] {pos:<4} {board:<12} {stack:>4.0f}bb ", end="", flush=True)
        r = process_spot(spot, client, delay=args.delay)
        results.append(r)
        verdict = r.get("verdict", "?")
        freq = r.get("our_action_freq_in_gto")
        freq_str = f"{freq*100:.0f}%" if freq is not None else "  -"
        print(f"→ {verdict:<25} our_freq={freq_str}")

    with open(args.output, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"\nResults written to {args.output}")
    print_summary(results)


if __name__ == "__main__":
    main()
