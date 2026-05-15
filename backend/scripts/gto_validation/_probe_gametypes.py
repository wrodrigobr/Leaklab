"""
_probe_gametypes.py — Testa chamadas diretas à API do GTO Wizard via CDP/headers capturados.

Uso no servidor Linux:
    python3 scripts/gto_validation/_probe_gametypes.py --port 9222

Requer Chrome rodando com --remote-debugging-port=9222 e usuário já logado no GTO Wizard.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import urllib.request

CDP_PORT = 9222

# Spot de teste: BTN open 2.3bb, BB call, flop Ah7s8h, stack 40bb
# Sequencia confirmada: F-F-F-F-F-R2.3-F-C (5 folds, BTN R2.3, SB fold, BB call)
TEST_PARAMS = {
    "gametype":        "MTTGeneral",
    "depth":           "40.125",
    "stacks":          "",
    "preflop_actions": "F-F-F-F-F-R2.3-F-C",
    "flop_actions":    "",
    "turn_actions":    "",
    "river_actions":   "",
    "board":           "Ah7s8h",
}

GW_SPOT_SOL  = "https://api.gtowizard.com/v4/solutions/spot-solution/"
GW_NEXT_ACTS = "https://api.gtowizard.com/v4/game-points/next-actions/"


def get_cdp_tabs(port: int) -> list[dict]:
    r = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=5)
    return json.loads(r.read())


def capture_auth_headers_via_cdp(port: int, timeout: int = 60) -> dict | None:
    """
    Conecta via CDP e captura headers de autenticação interceptando requests da página.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: playwright não instalado. Execute: pip3 install playwright")
        return None

    captured: dict = {}

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{port}")
        except Exception as e:
            print(f"ERRO CDP: {e}")
            return None

        contexts = browser.contexts
        if not contexts:
            print("ERRO: nenhum contexto no browser")
            return None

        page = contexts[0].pages[0] if contexts[0].pages else None
        if not page:
            print("ERRO: nenhuma aba aberta")
            return None

        print(f"[cdp] Conectado. Aba atual: {page.url[:80]}")

        def on_req(req):
            if "api.gtowizard.com" not in req.url or captured:
                return
            h = dict(req.headers)
            if "authorization" in h:
                captured.update(h)
                print(f"[auth] Capturado de: {req.url[:80]}")

        page.on("request", on_req)

        # Navega para /solutions para disparar requests autenticadas
        try:
            print("[cdp] Navegando para /solutions...")
            page.goto("https://app.gtowizard.com/solutions",
                      timeout=20000, wait_until="domcontentloaded")
        except Exception:
            pass

        deadline = time.time() + timeout
        while not captured and time.time() < deadline:
            time.sleep(0.5)

        browser.close()

    if not captured:
        print("ERRO: não foi possível capturar headers — verifique se está logado")
        return None

    print("[auth] Headers capturados com sucesso")
    return captured


def call_api(url: str, params: dict, headers: dict) -> tuple[int, dict | str]:
    from urllib.parse import urlencode
    full_url = f"{url}?{urlencode(params)}"
    req = urllib.request.Request(full_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read()
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, body.decode(errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return e.code, body
    except Exception as ex:
        return 0, str(ex)


def probe_spot(headers: dict, params: dict, debug: bool = False):
    # Filtra params internos
    p = {k: v for k, v in params.items() if not k.startswith("_")}
    auth_headers = {
        k: v for k, v in headers.items()
        if k.lower() in ("authorization", "dpop", "x-request-id", "content-type")
    }
    auth_headers.setdefault("content-type", "application/json")

    print(f"\n{'='*60}")
    print(f"Testando spot:")
    print(f"  gametype={p['gametype']}  depth={p['depth']}")
    print(f"  preflop={p['preflop_actions']}")
    print(f"  flop={p['flop_actions'] or '(checado)'}  board={p['board']}")

    # 1. next-actions
    print(f"\n--- next-actions ---")
    status, data = call_api(GW_NEXT_ACTS, p, auth_headers)
    print(f"Status: {status}")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2)[:2000])
    else:
        print(str(data)[:500])

    # 2. spot-solution
    print(f"\n--- spot-solution ---")
    status2, data2 = call_api(GW_SPOT_SOL, p, auth_headers)
    print(f"Status: {status2}")
    if isinstance(data2, dict):
        print(json.dumps(data2, indent=2)[:3000])
    else:
        print(str(data2)[:800])

    if debug and isinstance(data2, dict):
        print("\n[debug] full response keys:", list(data2.keys()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=CDP_PORT, help="CDP port")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--gametype", default="MTTGeneral")
    ap.add_argument("--depth", default="40.125")
    ap.add_argument("--preflop", default="F-F-F-F-F-F-R2-F-C", help="BTN open BB call")
    ap.add_argument("--board", default="Ah7s8h")
    ap.add_argument("--flop-actions", default="", dest="flop_actions")
    args = ap.parse_args()

    print(f"[probe] Capturando auth headers via CDP:{args.port}...")
    headers = capture_auth_headers_via_cdp(args.port)
    if not headers:
        sys.exit(1)

    params = dict(TEST_PARAMS)
    params["gametype"] = args.gametype
    params["depth"] = args.depth
    params["preflop_actions"] = args.preflop
    params["board"] = args.board
    params["flop_actions"] = args.flop_actions
    depth_float = float(args.depth)
    params["stacks"] = "-".join([str(depth_float)] * 9)

    probe_spot(headers, params, debug=args.debug)


if __name__ == "__main__":
    main()
