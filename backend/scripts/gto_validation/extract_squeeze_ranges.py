"""
extract_squeeze_ranges.py — RODA NO SERVIDOR GCP. Extrai ranges de squeeze
e cold 4-bet do GTO Wizard, com decodificação hand-by-hand do array strategy[169].

Mapping descoberto empiricamente:
  ranks = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']  # low to high
  index = row*13 + col
  - row == col: pair (e.g., AA at 168)
  - row > col: suited (higher card first, e.g., AKs at 167)
  - row < col: offsuit (higher card first, e.g., AKo at 155)

GW gametype: MTTGeneral (8-max). Posições: UTG, UTG+1, LJ, HJ, CO, BTN, SB, BB.
Fold count na sequência define a posição do hero (0=UTG, ..., 5=BTN, 6=SB, 7=BB).

Uso (no servidor):
    cd ~/leaklab/backend
    python3 scripts/gto_validation/extract_squeeze_ranges.py
    python3 scripts/gto_validation/extract_squeeze_ranges.py --sleep 0.5
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GW_APP     = "https://app.gtowizard.com"
GW_SPOT    = "https://api.gtowizard.com/v4/solutions/spot-solution/"
CDP_PORT   = int(os.environ.get("CDP_PORT", "9222"))
GAMETYPE   = "MTTGeneral"

# Depths válidos descobertos para multiway (probes anteriores)
VALID_DEPTHS = [30, 40, 50, 60, 80, 100]


# ── Mapping 169 → hand notation ─────────────────────────────────────────────
RANKS_LOW_HIGH = ['2','3','4','5','6','7','8','9','T','J','Q','K','A']

def index_to_hand(i: int) -> str:
    row, col = divmod(i, 13)
    if row == col:
        return RANKS_LOW_HIGH[row] * 2  # par
    if row > col:
        return RANKS_LOW_HIGH[row] + RANKS_LOW_HIGH[col] + 's'  # suited
    return RANKS_LOW_HIGH[col] + RANKS_LOW_HIGH[row] + 'o'  # offsuit


HAND_BY_INDEX = [index_to_hand(i) for i in range(169)]


def categorize_hands(action_solutions: list) -> dict:
    """Para cada hand do grid 13x13, determina a categoria dominante.
    Retorna dict com:
      hands_4bet: hands com frequência total de RAISE >= 50% (raise pequeno + all-in)
      hands_call: hands com CALL >= 50%
      hands_fold: hands com FOLD >= 50%
      hands_mixed: hands sem categoria dominante (>= 50%)
    """
    # Agregar por hand_index
    n_actions = len(action_solutions)
    if not action_solutions or not action_solutions[0].get("strategy"):
        return {"hands_4bet": "", "hands_call": "", "hands_fold": "",
                "hands_mixed": "", "aggregated": {}}

    # Agregação por familia de ação (fold/call/raise/allin)
    per_hand: list[dict[str, float]] = [{} for _ in range(169)]
    for sol in action_solutions:
        atype = sol["action"]["type"].lower()
        family = "allin" if atype in ("all_in", "allin") else (
                 "raise" if atype == "raise" else atype)
        strat = sol.get("strategy") or []
        for i, freq in enumerate(strat[:169]):
            per_hand[i][family] = per_hand[i].get(family, 0.0) + float(freq)

    h_4bet, h_call, h_fold, h_mixed = [], [], [], []
    for i in range(169):
        ph = per_hand[i]
        # Total raise (incluindo allin) é "agressivo"
        agg_raise = ph.get("raise", 0.0) + ph.get("allin", 0.0)
        fold_f    = ph.get("fold", 0.0)
        call_f    = ph.get("call", 0.0)
        # Skip hands que tem total 0 (não estão no range)
        if agg_raise + fold_f + call_f < 0.01:
            continue
        hand = HAND_BY_INDEX[i]
        if agg_raise >= 0.5:
            h_4bet.append(hand)
        elif call_f >= 0.5:
            h_call.append(hand)
        elif fold_f >= 0.5:
            h_fold.append(hand)
        else:
            h_mixed.append(hand)

    aggregated = {"raise": 0.0, "call": 0.0, "fold": 0.0, "allin": 0.0}
    for sol in action_solutions:
        atype = sol["action"]["type"].lower()
        family = "allin" if atype in ("all_in", "allin") else (
                 "raise" if atype == "raise" else atype)
        aggregated[family] = aggregated.get(family, 0.0) + float(sol.get("total_frequency", 0))

    return {
        "hands_4bet": ",".join(sorted(h_4bet)),
        "hands_call": ",".join(sorted(h_call)),
        "hands_fold": ",".join(sorted(h_fold)),
        "hands_mixed": ",".join(sorted(h_mixed)),
        "aggregated": {k: round(v, 4) for k, v in aggregated.items()},
    }


# ── Matriz de spots squeeze ────────────────────────────────────────────────
def build_squeeze_spots() -> list[dict]:
    """Define spots de squeeze para cada (opener, cold_caller, hero_squeezer, depth).

    Estrutura preflop_actions GW (8-max): F-...-R2.3-...-C-...
    - Antes do opener: folds das posições anteriores
    - Opener: R2.3 (raise 2.3bb padrão MTT)
    - Entre opener e cold_caller: folds
    - Cold caller: C
    - Entre cold_caller e hero: folds
    - Hero: agora decide (squeeze) — não está na string
    """
    # Posições por índice 8-max
    POS_IDX = {"UTG": 0, "UTG+1": 1, "LJ": 2, "HJ": 3, "CO": 4, "BTN": 5, "SB": 6, "BB": 7}

    def make_seq(opener: str, caller: str, hero: str) -> str | None:
        opener_idx = POS_IDX[opener]
        caller_idx = POS_IDX[caller]
        hero_idx   = POS_IDX[hero]
        if not (opener_idx < caller_idx < hero_idx):
            return None
        parts = []
        for i in range(hero_idx):
            if i < opener_idx:
                parts.append("F")
            elif i == opener_idx:
                parts.append("R2.3")
            elif i == caller_idx:
                parts.append("C")
            else:
                parts.append("F")
        return "-".join(parts)

    spots = []
    # Combinações tradicionais de squeeze (open + 1 cold call + hero squeeze)
    combos = [
        ("UTG", "UTG+1", "HJ"),
        ("UTG", "UTG+1", "CO"),
        ("UTG", "UTG+1", "BTN"),
        ("UTG", "UTG+1", "SB"),
        ("UTG", "UTG+1", "BB"),
        ("UTG", "LJ",    "CO"),
        ("UTG", "LJ",    "BTN"),
        ("UTG", "LJ",    "BB"),
        ("LJ",  "HJ",    "CO"),
        ("LJ",  "HJ",    "BTN"),
        ("LJ",  "HJ",    "BB"),
        ("HJ",  "CO",    "BTN"),
        ("HJ",  "CO",    "SB"),
        ("HJ",  "CO",    "BB"),
        ("CO",  "BTN",   "SB"),
        ("CO",  "BTN",   "BB"),   # spot squeeze mais comum em MTT
    ]
    for opener, caller, hero in combos:
        seq = make_seq(opener, caller, hero)
        if not seq:
            continue
        for depth in VALID_DEPTHS:
            spots.append({
                "scenario": "vs_squeeze_opportunity",
                "opener": opener, "caller": caller, "hero": hero,
                "depth": depth, "preflop_actions": seq,
                "key": f"{hero}_squeeze_vs_{opener}_open_{caller}_call_{depth}bb",
            })
    return spots


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(SCRIPT_DIR / "extracted_squeeze.json"))
    p.add_argument("--sleep", type=float, default=0.5)
    p.add_argument("--depths", default="", help="lista de depths separados por vírgula (ex: 50,100)")
    args = p.parse_args()

    if args.depths:
        global VALID_DEPTHS
        VALID_DEPTHS = [int(x) for x in args.depths.split(",")]

    spots = build_squeeze_spots()
    print(f"Total spots a testar: {len(spots)}")

    try:
        from playwright.sync_api import sync_playwright
        import requests as _req
    except ImportError:
        print("ERRO: pip install playwright requests"); return 1

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        except Exception as e:
            print(f"ERRO CDP: {e}"); return 1
        ctx  = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        cap = {}
        def on_req(req):
            if "api.gtowizard.com" in req.url and not cap:
                h = dict(req.headers)
                if "authorization" in h: cap.update(h)
        page.on("request", on_req)
        try:
            page.goto(f"{GW_APP}/solutions", timeout=20000, wait_until="domcontentloaded")
        except Exception: pass
        deadline = time.time() + 30
        while not cap and time.time() < deadline: page.wait_for_timeout(300)
        page.remove_listener("request", on_req)
        if not cap.get("authorization"):
            print("ERRO: sem authorization"); return 1
        print(f"[auth] OK ...{cap['authorization'][-20:]}\n")

        session = _req.Session()
        session.headers.update({
            "authorization": cap["authorization"],
            "accept": "application/json, text/plain, */*",
            "origin": GW_APP, "referer": GW_APP + "/",
            "gwclientid": cap.get("gwclientid", ""),
            "user-agent": cap.get("user-agent", "Mozilla/5.0"),
        })

        results = []
        last_refresh = time.time()
        for i, spot in enumerate(spots, 1):
            params = {
                "gametype": GAMETYPE, "depth": spot["depth"] + 0.125, "stacks": "",
                "preflop_actions": spot["preflop_actions"],
                "flop_actions": "", "turn_actions": "", "river_actions": "", "board": "",
            }
            r = session.get(GW_SPOT, params=params, timeout=15)
            time.sleep(args.sleep)

            entry = {**spot, "status": r.status_code}
            if r.status_code == 200:
                data = r.json()
                categorized = categorize_hands(data.get("action_solutions", []))
                entry.update(categorized)
                entry["pot"] = data.get("game", {}).get("pot")

            print(f"[{i:>3}/{len(spots)}] {spot['hero']:<5} squeeze vs {spot['opener']:<5}+{spot['caller']:<5} "
                  f"d={spot['depth']:>3}bb prefl={spot['preflop_actions']:<25} -> {r.status_code}"
                  + (f"  4bet={len(entry.get('hands_4bet','').split(',')) if entry.get('hands_4bet') else 0} "
                     f"call={len(entry.get('hands_call','').split(',')) if entry.get('hands_call') else 0}"
                     if r.status_code == 200 else ""))
            results.append(entry)

            # Refresh auth a cada 5min
            if time.time() - last_refresh > 300:
                last_refresh = time.time()
                cap.clear()
                page.on("request", on_req)
                try: page.reload(timeout=15000, wait_until="domcontentloaded")
                except Exception: pass
                dl = time.time() + 15
                while not cap and time.time() < dl: page.wait_for_timeout(300)
                page.remove_listener("request", on_req)
                if cap.get("authorization"):
                    session.headers["authorization"] = cap["authorization"]
                    print(f"[auth-refresh] ...{cap['authorization'][-20:]}")

        Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

        # Stats
        ok = sum(1 for r in results if r["status"] == 200)
        no_sol = sum(1 for r in results if r["status"] == 204)
        denied = sum(1 for r in results if r["status"] == 403)
        print(f"\nStats: 200={ok}  204={no_sol}  403={denied}  total={len(results)}")
        print(f"Output: {args.out}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
