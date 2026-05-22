"""
smoke_test_multiway.py — Smoke test UNICA chamada a API do GTO Wizard
para o spot multiway capturado no banco do usuario.

Reutiliza a infra de auth do playwright_compare.py: conecta ao Chrome ja
rodando com --remote-debugging-port=9222 e captura os headers DPoP via
interceptacao de requests.

Spot alvo (hand 258867027972, decision id=26154):
  MTT 9-max, Level V (75/150 + ante 20)
  Hero: BTN, K9o, stack 62bb
  Sequencia preflop antes do hero:
    UTG fold, UTG+1 fold, MP raise to 2bb, LJ fold, HJ call, CO call
  Hero (BTN) decide squeeze/call/fold com K9o

Para rodar no servidor GCP (onde Chrome esta logado em GTO Wizard):
    cd backend
    python scripts/gto_validation/smoke_test_multiway.py
    python scripts/gto_validation/smoke_test_multiway.py --gametype MTTGeneral_9m
    python scripts/gto_validation/smoke_test_multiway.py --gametype MTTGeneral --depth 60

Saidas:
  - Imprime params usados, status HTTP, top action, frequencies, range hand-by-hand
  - Salva resposta completa em smoke_test_response.json
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
GW_APP    = "https://app.gtowizard.com"
GW_API    = "https://api.gtowizard.com"
GW_SPOT   = f"{GW_API}/v4/solutions/spot-solution/"
GW_NEXT   = f"{GW_API}/v4/game-points/next-actions/"
GW_CLIENT = "790ab864-ed0c-4545-9e5a-97efe89672cd"
CDP_PORT  = int(os.environ.get("CDP_PORT", "9222"))


def _grab_auth(page, timeout_s: int = 30) -> dict | None:
    """Captura headers de auth interceptando requests reais da SPA."""
    captured: dict = {}

    def on_req(req):
        if "api.gtowizard.com" not in req.url or captured:
            return
        h = dict(req.headers)
        if "authorization" in h:
            captured.update(h)

    page.on("request", on_req)
    try:
        page.goto(f"{GW_APP}/solutions", timeout=20000, wait_until="domcontentloaded")
    except Exception:
        pass
    deadline = time.time() + timeout_s
    while not captured and time.time() < deadline:
        page.wait_for_timeout(300)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.remove_listener("request", on_req)
    return captured or None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gametype", default="MTTGeneral",
                   help="Gametype GW (ex: MTTGeneral, MTTGeneral_9m, MTTGeneral_8m)")
    p.add_argument("--depth", type=float, default=62.125,
                   help="Stack effective bb (default 62.125, snap padrao GW)")
    p.add_argument("--preflop", default="F-F-R2.3-F-C-C",
                   help="Sequencia preflop antes do hero (default: squeeze spot 4-way)")
    args = p.parse_args()

    try:
        from playwright.sync_api import sync_playwright
        import requests as _req
    except ImportError:
        print("ERRO: pip install playwright requests && playwright install chromium")
        return 1

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        except Exception as e:
            print(f"ERRO conectando CDP localhost:{CDP_PORT}: {e}")
            print("Inicie o Chrome com: chromium --remote-debugging-port=9222 &")
            return 1

        ctx  = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print("Capturando headers via CDP...")
        auth = _grab_auth(page, timeout_s=30)
        if not auth or "authorization" not in auth:
            print("ERRO: nao foi possivel capturar Authorization do browser")
            print("Confirme que o GTO Wizard esta logado no Chrome com CDP")
            return 1
        print(f"[auth] Authorization: ...{auth['authorization'][-20:]}")
        print(f"[auth] google-anal-id: {'OK' if 'google-anal-id' in auth else 'AUSENTE'}")

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

        params = {
            "gametype":        args.gametype,
            "depth":           args.depth,
            "stacks":          "",
            "preflop_actions": args.preflop,
            "flop_actions":    "",
            "turn_actions":    "",
            "river_actions":   "",
            "board":           "",
        }
        print("\n=== Spot multiway: BTN K9o, 4-way pot (MP open + HJ call + CO call) ===")
        print(f"Params: {json.dumps(params, indent=2)}")

        print(f"\n[GET] {GW_SPOT}")
        r = session.get(GW_SPOT, params=params, timeout=30)
        print(f"Status: {r.status_code}")
        print(f"URL final: {r.url[:300]}")
        out_path = SCRIPTS_DIR / "smoke_test_response.json"

        if r.status_code != 200:
            print(f"\n[body] {r.text[:800]}")
            out_path.write_text(json.dumps({
                "status": r.status_code,
                "params": params,
                "body": r.text,
            }, indent=2), encoding="utf-8")
            print(f"\nResposta de erro salva em {out_path}")
            return 2

        data = r.json()
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nResposta completa salva em {out_path}")

        print("\n=== ACTION SOLUTIONS ===")
        actions = data.get("action_solutions", [])
        if not actions:
            print("Sem action_solutions na resposta — spot pode nao ter solucao nessa arvore.")
            print(f"Top-level keys: {list(data.keys())}")
            return 3

        for sol in actions:
            act = sol.get("action", {})
            atype = act.get("type", "?")
            betsize = act.get("betsize", "")
            freq = float(sol.get("total_frequency", 0))
            print(f"  {atype:<10} {('size=' + str(betsize)) if betsize else '':<12} freq={freq:.3f}")

        # Categorias de mao (range hand-by-hand)
        cats = data.get("hand_categories_range") or []
        if cats:
            print(f"\n[hand_categories_range] {len(cats)} entries")
            for c in cats[:5]:
                print(f"  {c.get('category', '?'):<20}: combos={c.get('combos', '?')}")

        return 0


if __name__ == "__main__":
    sys.exit(main())
