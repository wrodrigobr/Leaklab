"""
smoke_test_known_good.py — Replica EXATAMENTE uma chamada que retornou 200
no HAR preflop_har.har, para isolar se o problema e auth ou gametype.

Spot conhecido (do HAR): Cash6mGeneral_6mNL25R25, custom_solution_id, F-R2-R5.
Tambem tenta variacoes para diagnosticar.
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
GW_APP    = "https://app.gtowizard.com"
GW_API    = "https://api.gtowizard.com"
GW_SPOT   = f"{GW_API}/v4/solutions/spot-solution/"
GW_CLIENT = "790ab864-ed0c-4545-9e5a-97efe89672cd"
CDP_PORT  = int(os.environ.get("CDP_PORT", "9222"))

# Custom solutions ids observados no HAR
KNOWN_CUSTOM_IDS = [
    "845064e1-c7e5-4d7a-99ff-b55ed87fbce7",
    "84b25a92-dac1-46a0-af71-7ab3be40c2a5",
]


def _grab_auth(page, timeout_s: int = 30) -> dict | None:
    captured: dict = {}
    last_seen: dict = {}

    def on_req(req):
        if "api.gtowizard.com" not in req.url:
            return
        h = dict(req.headers)
        # Acumula sempre — pega o header mais recente (pode ter google-anal-id em request tardia)
        if "authorization" in h:
            last_seen.update(h)
            if "google-anal-id" in h or not captured:
                captured.clear()
                captured.update(h)

    page.on("request", on_req)
    try:
        page.goto(f"{GW_APP}/solutions", timeout=20000, wait_until="domcontentloaded")
    except Exception:
        pass
    # Aguarda um pouco mais para capturar requests tardias (google-anal-id chega depois)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        page.wait_for_timeout(500)
        if captured and "google-anal-id" in captured:
            break
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.remove_listener("request", on_req)
    if last_seen and "google-anal-id" in last_seen and "google-anal-id" not in captured:
        captured.update(last_seen)
    return captured or None


def main() -> int:
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

        print("Capturando auth...")
        auth = _grab_auth(page, timeout_s=30)
        if not auth or "authorization" not in auth:
            print("ERRO: sem authorization")
            return 1
        print(f"  authorization: ...{auth['authorization'][-20:]}")
        print(f"  google-anal-id: {'PRESENTE' if 'google-anal-id' in auth else 'AUSENTE'}")
        print(f"  gwclientid: {auth.get('gwclientid', '(usando default)')}")

        session = _req.Session()
        session.headers.update({
            "authorization":  auth["authorization"],
            "accept":         "application/json, text/plain, */*",
            "origin":         GW_APP,
            "referer":        GW_APP + "/",
            "gwclientid":     auth.get("gwclientid", GW_CLIENT),
            "user-agent":     auth.get("user-agent", "Mozilla/5.0"),
        })
        if "google-anal-id" in auth:
            session.headers["google-anal-id"] = auth["google-anal-id"]

        # Lista de tentativas em ordem: do known-good ao mais ambicioso
        attempts = [
            ("KNOWN_GOOD: Cash6m custom_solution preflop F-R2-R5 (do HAR)", {
                "custom_solution_id": KNOWN_CUSTOM_IDS[0],
                "preflop_actions": "F-R2-R5",
                "flop_actions": "", "turn_actions": "", "river_actions": "", "board": "",
            }),
            ("MTT 8m generico, BTN RFI 100bb", {
                "gametype": "MTTGeneral_8m",
                "depth": 100, "stacks": "",
                "preflop_actions": "F-F-F-F-F",
                "flop_actions": "", "turn_actions": "", "river_actions": "", "board": "",
            }),
            ("MTT 9m generico, BTN RFI 100bb", {
                "gametype": "MTTGeneral_9m",
                "depth": 100, "stacks": "",
                "preflop_actions": "F-F-F-F-F-F",
                "flop_actions": "", "turn_actions": "", "river_actions": "", "board": "",
            }),
            ("MTTGeneral (generico antigo), BTN RFI", {
                "gametype": "MTTGeneral",
                "depth": 100.125, "stacks": "",
                "preflop_actions": "F-F-F-F-F-F",
                "flop_actions": "", "turn_actions": "", "river_actions": "", "board": "",
            }),
            ("MTT 9m, spot multiway alvo (4-way squeeze)", {
                "gametype": "MTTGeneral_9m",
                "depth": 62.125, "stacks": "",
                "preflop_actions": "F-F-R2.3-F-C-C",
                "flop_actions": "", "turn_actions": "", "river_actions": "", "board": "",
            }),
        ]

        results = []
        for desc, params in attempts:
            print(f"\n=== {desc} ===")
            print(f"  params: {json.dumps({k: v for k, v in params.items() if v}, indent=4)[:300]}")
            r = session.get(GW_SPOT, params=params, timeout=20)
            print(f"  Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                acts = data.get("action_solutions", [])
                if acts:
                    print(f"  action_solutions: {len(acts)}")
                    for a in acts[:5]:
                        t = a.get("action", {}).get("type", "?")
                        bz = a.get("action", {}).get("betsize", "")
                        f = float(a.get("total_frequency", 0))
                        print(f"    {t:<10} size={bz:<6} freq={f:.3f}")
                else:
                    print(f"  keys: {list(data.keys())[:8]}")
                results.append((desc, 200, "OK"))
            else:
                body = r.text[:200]
                print(f"  body: {body}")
                results.append((desc, r.status_code, body[:80]))
            time.sleep(0.8)

        print("\n=== RESUMO ===")
        for desc, code, msg in results:
            mark = "OK" if code == 200 else "FAIL"
            print(f"  [{mark}] {code}  {desc}")
            if code != 200:
                print(f"        -> {msg}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
