"""
bench_step2_call_gw.py — RODA NO SERVIDOR GCP. Lê benchmark_spots.json,
chama GTO Wizard para cada spot via Chrome CDP local, e escreve
benchmark_responses.json com a estratégia retornada.

Uso (no servidor):
    cd ~/leaklab/backend
    python3 scripts/gto_validation/bench_step2_call_gw.py
    python3 scripts/gto_validation/bench_step2_call_gw.py --sleep 0.4

NÃO altera nada no DB local — só faz GET requests para api.gtowizard.com.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

GW_APP   = "https://app.gtowizard.com"
GW_SPOT  = "https://api.gtowizard.com/v4/solutions/spot-solution/"
CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))

# Gametype validado em smoke test (MTTGeneralV2 retorna 403 na conta atual)
GAMETYPE = "MTTGeneral"
# Depths válidos confirmados via probe para spots preflop
VALID_DEPTHS = [10, 12, 14, 16, 18, 20, 25, 30, 40, 50, 60, 80, 100]


def snap_depth(stack_bb: float) -> float:
    snap = min(VALID_DEPTHS, key=lambda d: abs(d - round(stack_bb)))
    return snap + 0.125


def norm_act(a: str) -> str:
    a = (a or "").lower().rstrip("s")
    return {"raise": "bet", "bet": "bet", "all_in": "allin", "allin": "allin",
            "jam": "allin", "fold": "fold", "call": "call", "check": "check"}.get(a, a)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in",  dest="inp",  default=str(SCRIPT_DIR / "benchmark_spots.json"))
    p.add_argument("--out", dest="outp", default=str(SCRIPT_DIR / "benchmark_responses.json"))
    p.add_argument("--sleep", type=float, default=0.6)
    p.add_argument("--limit", type=int, default=0, help="limita N spots (0=todos)")
    args = p.parse_args()

    spots = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    if args.limit > 0:
        spots = spots[: args.limit]
    print(f"Lendo {len(spots)} spots de {args.inp}")

    try:
        from playwright.sync_api import sync_playwright
        import requests as _req
    except ImportError:
        print("ERRO: pip install playwright requests")
        return 1

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        except Exception as e:
            print(f"ERRO CDP: {e}")
            return 1
        ctx  = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        captured: dict = {}
        def on_req(req):
            if "api.gtowizard.com" in req.url and not captured:
                h = dict(req.headers)
                if "authorization" in h:
                    captured.update(h)
        page.on("request", on_req)
        try:
            page.goto(f"{GW_APP}/solutions", timeout=20000, wait_until="domcontentloaded")
        except Exception:
            pass
        deadline = time.time() + 30
        while not captured and time.time() < deadline:
            page.wait_for_timeout(300)
        page.remove_listener("request", on_req)
        if not captured.get("authorization"):
            print("ERRO: sem authorization capturado")
            return 1
        print(f"[auth] OK ...{captured['authorization'][-20:]}\n")

        session = _req.Session()
        session.headers.update({
            "authorization": captured["authorization"],
            "accept": "application/json, text/plain, */*",
            "origin": GW_APP, "referer": GW_APP + "/",
            "gwclientid": captured.get("gwclientid", ""),
            "user-agent": captured.get("user-agent", "Mozilla/5.0"),
        })

        results = []
        stats = {"200": 0, "204": 0, "403": 0, "404": 0, "other": 0, "exception": 0}
        last_refresh = time.time()
        for i, spot in enumerate(spots, 1):
            depth = snap_depth(spot["stack_bb"])
            params = {
                "gametype": GAMETYPE, "depth": depth, "stacks": "",
                "preflop_actions": spot["preflop_actions"],
                "flop_actions": "", "turn_actions": "", "river_actions": "", "board": "",
            }
            try:
                r = session.get(GW_SPOT, params=params, timeout=15)
            except Exception as e:
                stats["exception"] += 1
                results.append({"id": spot["id"], "status": -1, "error": str(e)[:120],
                                "depth": depth, "preflop_actions": spot["preflop_actions"]})
                print(f"[{i:>3}/{len(spots)}] id={spot['id']:>6} EXCEPTION {e}")
                continue

            entry = {
                "id": spot["id"], "status": r.status_code,
                "depth": depth, "preflop_actions": spot["preflop_actions"],
                "stack_bb": spot["stack_bb"], "position": spot["position"],
                "hero_cards": spot["hero_cards"], "spot_type": spot["spot_type"],
            }

            if r.status_code == 200:
                stats["200"] += 1
                data = r.json()
                # Reduzir o payload: só strategy agregada por familia
                strategy: dict[str, float] = {}
                for a in data.get("action_solutions", []):
                    t = norm_act(a.get("action", {}).get("type", ""))
                    f = float(a.get("total_frequency", 0))
                    strategy[t] = strategy.get(t, 0) + f
                # Manter raw action_solutions tambem (com bet sizes detalhados)
                entry["strategy_aggregated"] = strategy
                entry["action_solutions_raw"] = data.get("action_solutions", [])
                entry["pot"] = data.get("game", {}).get("pot")
                if strategy:
                    top = max(strategy, key=lambda k: strategy[k])
                    entry["gw_top"] = top
                    entry["gw_top_freq"] = strategy[top]
            elif r.status_code in (204, 403, 404):
                stats[str(r.status_code)] += 1
                entry["body"] = r.text[:200]
            else:
                stats["other"] += 1
                entry["body"] = r.text[:200]

            results.append(entry)
            mark = "OK" if r.status_code == 200 else r.status_code
            top_str = (f"top={entry.get('gw_top', '?')} freq={entry.get('gw_top_freq', 0):.2f}"
                       if r.status_code == 200 else "")
            print(f"[{i:>3}/{len(spots)}] id={spot['id']:>6} {spot['position']:<5} "
                  f"stk={spot['stack_bb']:>5.1f} d={depth:>6.3f} {spot['spot_type']:<22} "
                  f"-> {mark} {top_str}")

            time.sleep(args.sleep)

            # Refresh token a cada 5 min
            if time.time() - last_refresh > 300:
                last_refresh = time.time()
                captured.clear()
                page.on("request", on_req)
                try:
                    page.reload(timeout=15000, wait_until="domcontentloaded")
                except Exception:
                    pass
                dl = time.time() + 15
                while not captured and time.time() < dl:
                    page.wait_for_timeout(300)
                page.remove_listener("request", on_req)
                if captured.get("authorization"):
                    session.headers["authorization"] = captured["authorization"]
                    print(f"[auth-refresh] ...{captured['authorization'][-20:]}")

        Path(args.outp).write_text(json.dumps(results, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
        print(f"\nStats: {stats}")
        print(f"Resultados em {args.outp}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
