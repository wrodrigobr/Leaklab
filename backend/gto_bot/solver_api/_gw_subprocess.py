"""
_gw_subprocess.py — Fetch isolado do GTO Wizard num PROCESSO próprio.

Rodar o Playwright sync no processo do servidor (mesmo em thread dedicada)
acumula estado asyncio/greenlet e degrada após ~N chamadas ("Sync API inside
the asyncio loop"). Um subprocesso fresco por fetch elimina QUALQUER estado
compartilhado — start/connect/navigate/stop num interpretador limpo.

Invocado pelo server: `python _gw_subprocess.py '<json>'`
  json = {mode:"fetch"|"capture", cdp_port, gw_app, app_defaults?, api_path?,
          params?, timeout_s}
Imprime UMA linha JSON no stdout:
  fetch:   {ok, status?, json?, error?, via?}
  capture: {ok, headers?, error?}
"""
import json
import sys
import time
from urllib.parse import urlencode


def _do_fetch(browser, req: dict) -> dict:
    from playwright.sync_api import TimeoutError as PWTimeout
    api_path = req["api_path"]
    params = req.get("params") or {}
    app_defaults = req.get("app_defaults") or {}
    gw_app = req["gw_app"]
    timeout_s = int(req.get("timeout_s", 25))

    app_params = {**app_defaults, **params}
    app_url = f"{gw_app}/solutions?{urlencode(app_params)}"

    contexts = browser.contexts
    if not contexts:
        return {"ok": False, "error": "no_browser_context"}
    target_page = None
    for ctx in contexts:
        for p in ctx.pages:
            try:
                if "gtowizard.com" in (p.url or ""):
                    target_page = p
                    break
            except Exception:
                continue
        if target_page:
            break
    if target_page is None:
        try:
            target_page = contexts[0].new_page()
        except Exception as e:
            return {"ok": False, "error": f"new_page:{e}"}

    essential = ("gametype", "depth", "preflop_actions", "flop_actions",
                 "turn_actions", "river_actions", "board")
    expected = {k: str(params.get(k, "")) for k in essential}

    def is_target(resp):
        try:
            if api_path not in resp.url:
                return False
            if resp.request.method != "GET":
                return False
            for k, v in expected.items():
                if f"{k}={v}" not in resp.url and not (v == "" and f"{k}=&" in resp.url + "&"):
                    return False
            return True
        except Exception:
            return False

    try:
        with target_page.expect_response(is_target, timeout=timeout_s * 1000) as resp_info:
            target_page.goto(app_url, timeout=timeout_s * 1000, wait_until="commit")
        response = resp_info.value
    except PWTimeout:
        return {"ok": False, "error": "timeout_waiting_api_response"}
    except Exception as e:
        return {"ok": False, "error": f"navigate:{e}"}

    try:
        status = response.status
    except Exception:
        status = 0
    if status == 401:
        return {"ok": False, "status": 401, "error": "auth_expired"}
    if status == 204:
        return {"ok": False, "status": 204, "error": "no_solution_204"}
    if status < 200 or status >= 300:
        body_preview = None
        try:
            body_preview = response.text()[:300]
        except Exception:
            pass
        return {"ok": False, "status": status, "error": f"http_{status}", "body": body_preview}
    try:
        data = response.json()
    except Exception as e:
        return {"ok": False, "status": status, "error": f"json_parse:{e}"}
    return {"ok": True, "status": status, "json": data, "via": "navigate"}


def _do_capture(browser, req: dict) -> dict:
    gw_app = req["gw_app"]
    timeout_s = int(req.get("timeout_s", 25))
    captured: dict = {}
    contexts = browser.contexts
    if not contexts:
        return {"ok": False, "error": "no_browser_context"}
    page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()

    def on_req(rq):
        if "api.gtowizard.com" not in rq.url or captured:
            return
        h = dict(rq.headers)
        if "authorization" in h or "google-anal-id" in h:
            captured.update(h)

    page.on("request", on_req)
    try:
        page.goto(f"{gw_app}/solutions", timeout=15000, wait_until="domcontentloaded")
    except Exception:
        pass
    deadline = time.time() + timeout_s
    while not captured and time.time() < deadline:
        page.wait_for_timeout(400)
    try:
        page.remove_listener("request", on_req)
    except Exception:
        pass
    if captured and ("authorization" in captured or "google-anal-id" in captured):
        return {"ok": True, "headers": captured}
    return {"ok": False, "error": "no_auth_header"}


def main():
    try:
        req = json.loads(sys.argv[1])
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"bad_args:{e}"}))
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({"ok": False, "error": "playwright_not_installed"}))
        return
    cdp_port = req.get("cdp_port", 9222)
    try:
        pw = sync_playwright().start()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"playwright_start:{e}"}))
        return
    try:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"cdp_connect:{e}"}))
            return
        if req.get("mode") == "capture":
            result = _do_capture(browser, req)
        else:
            result = _do_fetch(browser, req)
    finally:
        try:
            pw.stop()
        except Exception:
            pass
    print(json.dumps(result))


if __name__ == "__main__":
    main()
