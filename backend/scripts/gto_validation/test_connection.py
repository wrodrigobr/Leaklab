"""
Testa a conexão com o GTO Wizard usando o spot do HAR capturado.

Uso:
    export GTOWIZARD_REFRESH_TOKEN="eyJ..."
    python test_connection.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from scripts.gto_validation.gto_wizard_client import GtoWizardClient, GAMETYPE_MTT_8M

# Spot exato do app.gtowizard.com.har — referência conhecida com response 200
KNOWN_SPOT = {
    "gametype": GAMETYPE_MTT_8M,
    "depth": 20.125,
    "preflop_actions": "R2-F-C-F-F-F-F-R6.5-C-F",
    "board": "Ad6h5d",
    "flop_actions": "",
    "expected_check_freq": 0.461,  # total_frequency do CHECK na response do HAR
}


def main():
    token = os.environ.get("GTOWIZARD_REFRESH_TOKEN", "")
    if not token:
        print("ERROR: Set GTOWIZARD_REFRESH_TOKEN env var")
        print("  Example (PowerShell): $env:GTOWIZARD_REFRESH_TOKEN='eyJ...'")
        sys.exit(1)

    print("=== GTO Wizard Connection Test ===")
    print(f"Spot: {KNOWN_SPOT['preflop_actions']} | board={KNOWN_SPOT['board']} | depth={KNOWN_SPOT['depth']}bb")
    print()

    client = GtoWizardClient(refresh_token=token)

    print("Step 1: Token refresh... ", end="", flush=True)
    try:
        client._ensure_token()
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)

    print("Step 2: Spot solution... ", end="", flush=True)
    try:
        sol = client.get_spot_solution(
            depth=KNOWN_SPOT["depth"],
            preflop_actions=KNOWN_SPOT["preflop_actions"],
            board=KNOWN_SPOT["board"],
            flop_actions=KNOWN_SPOT["flop_actions"],
            gametype=KNOWN_SPOT["gametype"],
        )
        if not sol.found:
            print("NOT FOUND (404) — spot may not exist in your subscription plan")
            sys.exit(1)
        print(f"OK — {sol.summary()}")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)

    print()
    print("Strategy breakdown:")
    for action, freq in sorted(sol.actions.items(), key=lambda x: -x[1]):
        bar = "█" * int(freq * 40)
        print(f"  {action:<8} {freq*100:>5.1f}%  {bar}")

    expected = KNOWN_SPOT["expected_check_freq"]
    actual_check = sol.check
    delta = abs(actual_check - expected)
    print()
    if delta < 0.05:
        print(f"✓ Check frequency {actual_check:.3f} matches expected {expected:.3f} (delta={delta:.3f})")
        print("✓ Connection test PASSED")
    else:
        print(f"? Check frequency {actual_check:.3f} vs expected {expected:.3f} (delta={delta:.3f})")
        print("  Response differs from HAR reference — may be OK if spot was re-solved")

if __name__ == "__main__":
    main()
