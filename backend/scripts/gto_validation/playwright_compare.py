"""
playwright_compare.py — Compara spots do DB com GTO Wizard via browser automatizado.

O browser gerencia o DPoP/ECDSA automaticamente — sem precisar de token externo.

Instalacao:
    pip install playwright
    playwright install chromium

Uso:
    # Primeira execucao (login manual):
    python gto_validation/playwright_compare.py --login

    # Execucoes seguintes (cookies reutilizados):
    python gto_validation/playwright_compare.py --limit 30 --min-stack 20

    # So flop spots com erros:
    python gto_validation/playwright_compare.py --limit 20 --street flop --mistakes-only

Resultado salvo em comparison_results_raw.json
Proximo passo: python analyze_results.py --input comparison_results_raw.json
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent.parent
COOKIES_FILE = SCRIPTS_DIR / "gto_cookies.json"
GW_APP       = "https://app.gtowizard.com"
GW_API       = "https://api.gtowizard.com"
GAMETYPE      = "MTTGeneral"
NUM_PLAYERS   = 9
STACK_SNAPS   = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]
GW_CLIENT_ID  = "790ab864-ed0c-4545-9e5a-97efe89672cd"
GW_SPOT_SOL   = "https://api.gtowizard.com/v4/solutions/spot-solution/"
GW_NEXT_ACTS  = "https://api.gtowizard.com/v4/game-points/next-actions/"

# BB/SB act first post-flop (OOP); all other positions are IP post-flop
OOP_POSITIONS = {"BB", "SB"}

# Preflop sequences para MTTGeneral 9-max (8 acoes por mao)
# Raise size 2.3bb confirmado via API — BTN: F-F-F-F-F-R2.3-F-C ✓
PREFLOP_BY_POS = {
    "UTG":   "R2.3-F-F-F-F-F-F-C",
    "UTG+1": "F-R2.3-F-F-F-F-F-C",
    "UTG+2": "F-F-R2.3-F-F-F-F-C",  # alias LJ
    "LJ":    "F-F-R2.3-F-F-F-F-C",
    "HJ":    "F-F-F-R2.3-F-F-F-C",
    "CO":    "F-F-F-F-R2.3-F-F-C",
    "BTN":   "F-F-F-F-F-R2.3-F-C",  # confirmado via API
    "SB":    "F-F-F-F-F-F-R2.3-C",
    "BB":    "F-F-F-F-F-R2.3-F-C",  # BTN opens, SB fold, BB call (OOP hero)
    "MP":    "F-F-R2.3-F-F-F-F-C",  # alias LJ
    "EP":    "R2.3-F-F-F-F-F-F-C",  # alias UTG
}


def _nearest_snap(stack_bb: float) -> float:
    return min(STACK_SNAPS, key=lambda s: abs(s - stack_bb))


def _norm_board(board_raw: str) -> str:
    """'7s Ah 8h' -> 'Ah7s8h' (rank upper, suit lower, sem espaco, so 3 cartas)."""
    cards = board_raw.strip().split()[:3]
    result = []
    for c in cards:
        c = c.strip()
        if len(c) >= 2:
            result.append(c[0].upper() + c[1].lower())
    return "".join(result) if len(result) == 3 else ""


def build_params(spot: dict) -> dict | None:
    """Converte spot do DB em params para a URL do GTO Wizard."""
    position = str(spot.get("position", "")).upper().strip()
    preflop  = PREFLOP_BY_POS.get(position)
    if not preflop:
        return None

    board = _norm_board(spot.get("board", ""))
    if not board:
        return None

    snap       = _nearest_snap(float(spot.get("stack_bucket", 20)))
    stack_frac = snap + 0.125
    stacks_str = ""  # arvore MTTGeneral usa depth= como referencia

    facing_bb  = float(spot.get("facing_bet", 0) or 0)
    hero_is_oop = position in OOP_POSITIONS

    # flop_actions is a placeholder — valid bet size discovered via next-actions at runtime
    if facing_bb > 0:
        # OOP hero: checked then faced IP raise → "X-R{size}"
        # IP hero: faced OOP donk raise → "R{size}"
        # GTO Wizard usa R (raise) para bets, não B. RAI = all-in.
        raw_size = round(facing_bb, 1)
        flop_actions = f"X-R{raw_size}" if hero_is_oop else f"R{raw_size}"
    else:
        flop_actions = ""

    return {
        "gametype":        GAMETYPE,
        "depth":           stack_frac,
        "stacks":          stacks_str,
        "preflop_actions": preflop,
        "flop_actions":    flop_actions,
        "turn_actions":    "",
        "river_actions":   "",
        "board":           board,
        "_hero_is_oop":    hero_is_oop,
        "_facing_bb":      facing_bb,
    }


def build_app_url(params: dict) -> str:
    """Monta a URL do app GTO Wizard que vai acionar o spot-solution request."""
    from urllib.parse import urlencode
    return f"{GW_APP}/solutions?{urlencode(params)}"


def parse_strategy(data: dict) -> tuple[dict, str | None]:
    actions: dict[str, float] = {}
    top_action = None
    top_freq   = -1.0
    for item in data.get("action_solutions", []):
        atype = (item.get("action", {}).get("type") or "").lower()
        freq  = float(item.get("total_frequency") or 0)
        name  = {
            "check": "check", "call": "call", "fold": "fold",
            "bet": "bet", "raise": "bet", "all_in": "allin", "allin": "allin",
        }.get(atype, atype)
        actions[name] = actions.get(name, 0.0) + freq
        if freq > top_freq:
            top_freq   = freq
            top_action = name
    return actions, top_action


def load_cookies(ctx) -> bool:
    if COOKIES_FILE.exists():
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        ctx.add_cookies(cookies)
        return True
    return False


def save_cookies(ctx):
    COOKIES_FILE.write_text(
        json.dumps(ctx.cookies(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def do_login(page, ctx):
    """Abre o GTO Wizard e aguarda o usuario fazer login manualmente."""
    print("\n[login] Abrindo GTO Wizard...")
    page.goto(GW_APP, timeout=30000)
    print("[login] Faca login no browser. Quando estiver na pagina principal, pressione ENTER aqui.")
    input("  >> ENTER para continuar: ")
    save_cookies(ctx)
    print("[login] Cookies salvos.")


CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))


def _connect_cdp(pw):
    """
    Conecta ao Chrome/Edge JA RODANDO com --remote-debugging-port=9222.
    Isso usa a sessao real do usuario sem nenhuma deteccao de automacao.
    """
    import urllib.request as _ur
    cdp_url = f"http://localhost:{CDP_PORT}"
    try:
        _ur.urlopen(f"{cdp_url}/json/version", timeout=3)
    except Exception:
        return None

    try:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        print(f"[browser] Conectado ao browser via CDP (porta {CDP_PORT}).")
        return browser
    except Exception as e:
        print(f"[browser] Falha ao conectar via CDP: {e}")
        return None


def _query_next_actions(session, api_params: dict, flop_actions_so_far: str,
                        debug: bool = False) -> dict:
    """Chama game-points/next-actions para descobrir ações válidas no spot atual."""
    params = {k: v for k, v in api_params.items() if not k.startswith("_")}
    params["flop_actions"] = flop_actions_so_far
    try:
        r = session.get(GW_NEXT_ACTS, params=params, timeout=10)
        if debug:
            print(f"\n[next-actions] HTTP {r.status_code}  url={r.url[:120]}")
            if not r.ok:
                print(f"[next-actions] body={r.text[:300]}")
        if r.ok and r.content:
            return r.json()
    except Exception as e:
        if debug:
            print(f"[next-actions] exception: {e}")
    return {}


def _nearest_valid_bet(next_actions_resp: dict, target_bb: float,
                       debug: bool = False) -> float | None:
    """
    Extrai tamanhos de bet válidos da resposta de next-actions (formato real da API):
      {"next_actions": {"available_actions": [{"action": {"type": "BET", "betsize": "3.5"}}, ...]}}

    Retorna o tamanho mais próximo de target_bb, ou None se não houver bets.
    """
    if debug:
        print(f"\n[next-actions raw] {json.dumps(next_actions_resp)[:3000]}")

    sizes: list[float] = []

    # Caminho correto: next_actions_resp["next_actions"]["available_actions"]
    na       = next_actions_resp.get("next_actions") or {}
    pot_str  = na.get("game", {}).get("pot") or na.get("pot")
    available = na.get("available_actions") or []

    for item in available:
        action = item.get("action") or item
        atype  = str(action.get("type") or "").upper()
        if atype not in ("BET", "RAISE", "ALL_IN", "ALLIN"):
            continue
        betsize = action.get("betsize")
        if betsize is not None:
            try:
                sz = float(betsize)
                if sz > 0:
                    sizes.append(sz)
            except (ValueError, TypeError):
                pass

    if debug:
        pot_info = f"  pot={pot_str}bb" if pot_str else ""
        print(f"[next-actions] sizes válidos: {sizes}  target={target_bb}bb{pot_info}")

    if not sizes:
        return None
    return min(sizes, key=lambda s: abs(s - target_bb))


def _grab_auth_headers(page, timeout_s: int = 30) -> dict | None:
    """
    Captura headers de autenticação do GTO Wizard interceptando requests reais.

    Registra o interceptor ANTES de navegar para /solutions, deixando o reload
    acontecer naturalmente. As requests disparadas durante o carregamento da SPA
    contêm os headers DPoP corretos. Só retorna depois que a página estabiliza,
    garantindo que comparações não comecem com a página ainda carregando.
    """
    captured: dict = {}

    def on_req(req):
        if "api.gtowizard.com" not in req.url or captured:
            return
        h = dict(req.headers)
        if "authorization" in h:
            captured.update(h)
            print(f"\n[auth] Headers capturados de: {req.url[:80]}")

    page.on("request", on_req)

    # Navega para /solutions — dispara requests autenticadas durante o carregamento
    try:
        page.goto(f"{GW_APP}/solutions", timeout=20000, wait_until="domcontentloaded")
    except Exception:
        pass  # timeout ok — o que importa é capturar os headers

    # Espera pelos headers (disparados durante o carregamento da SPA)
    deadline = time.time() + timeout_s
    while not captured and time.time() < deadline:
        page.wait_for_timeout(300)

    # Aguarda a página estabilizar antes de iniciar as comparações
    if captured:
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

    page.remove_listener("request", on_req)
    return captured if captured else None


def run_comparison(spots: list[dict], headless: bool, timeout_ms: int, delay: float,
                   debug_next_actions: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
        import requests as _req
    except ImportError:
        print("ERRO: pip install playwright requests && playwright install chromium")
        sys.exit(1)

    results = []

    with sync_playwright() as pw:
        browser = _connect_cdp(pw)
        if browser is None:
            print(
                "\nERRO: Chrome nao esta rodando com CDP na porta 9222.\n"
                f'  python playwright_compare.py --start-browser\n'
            )
            sys.exit(1)

        ctx  = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        if "login" in page.url.lower() or "accounts.google" in page.url.lower():
            print("[auth] Faca login no GTO Wizard no browser e pressione ENTER aqui.")
            input("  >> ENTER: ")

        # Captura headers via CDP interceptando requests da SPA durante carregamento.
        # O _grab_auth_headers navega para /solutions, captura os headers e aguarda
        # networkidle — só retorna quando a página está pronta para uso.
        print("Capturando headers de autenticacao do browser via CDP...")
        auth = _grab_auth_headers(page, timeout_s=30)

        if not auth or "authorization" not in auth:
            print("ERRO: Nao foi possivel capturar Authorization do browser.")
            print("Certifique-se de estar logado no GTO Wizard e que o browser esta fazendo requests.")
            return []

        has_anal = "google-anal-id" in auth
        print(f"[auth] Authorization: ...{auth['authorization'][-20:]}")
        print(f"[auth] google-anal-id: {'capturado' if has_anal else 'AUSENTE — pode dar 403'}")

        session = _req.Session()
        session.headers.update({
            "authorization":  auth["authorization"],
            "accept":         "application/json, text/plain, */*",
            "origin":         GW_APP,
            "referer":        GW_APP + "/",
            "gwclientid":     auth.get("gwclientid", GW_CLIENT_ID),
            "user-agent":     auth.get("user-agent", "Mozilla/5.0"),
        })
        if has_anal:
            session.headers["google-anal-id"] = auth["google-anal-id"]

        def call_spot(api_params: dict, debug: bool = False) -> tuple[int, dict | None]:
            r = session.get(GW_SPOT_SOL, params=api_params, timeout=15)
            if debug and r.status_code != 200:
                print(f"\n[spot-solution] HTTP {r.status_code}  body={r.text[:400]}")
                print(f"[spot-solution] url={r.url[:200]}")
            if r.status_code == 200 and r.content:
                return 200, r.json()
            return r.status_code, None

        def refresh_auth():
            nonlocal auth
            print("\n[auth] Renovando headers...", end=" ", flush=True)
            new = _grab_auth_headers(page, timeout_s=20)
            if new and "authorization" in new:
                auth = new
                session.headers["authorization"] = auth["authorization"]
                if "google-anal-id" in auth:
                    session.headers["google-anal-id"] = auth["google-anal-id"]
                print("OK")
                return True
            print("FALHOU")
            return False

        print(f"\nIniciando comparacao de {len(spots)} spots...\n")

        for i, spot in enumerate(spots):
            params = build_params(spot)
            if not params:
                print(f"[{i+1}/{len(spots)}] SKIP (params invalidos)")
                continue

            api_params = {k: v for k, v in params.items() if not k.startswith("_")}
            position   = spot.get("position", "?")
            board      = params["board"]
            depth      = params["depth"]
            facing     = spot.get("facing_bet", 0)

            print(f"[{i+1}/{len(spots)}] {position} | {board} | {depth}bb"
                  + (f" | facing {facing:.1f}bb" if facing else ""), end="  ", flush=True)

            result: dict = {
                "spot_id":         spot.get("spot_id"),
                "position":        position,
                "board":           board,
                "stack":           depth,
                "facing_bet":      facing,
                "preflop_actions": params["preflop_actions"],
                "flop_actions":    params["flop_actions"],
                "our_best_action": spot.get("example_best_action"),
                "our_label":       spot.get("our_label"),
                "occurrences":     spot.get("occurrences", 1),
                "gto_found":       False,
                "gto_strategy":    {},
                "gto_top_action":  None,
                "verdict":         None,
                "error":           None,
            }

            try:
                # For facing-bet spots, discover the nearest valid GTO Wizard bet size
                # via game-points/next-actions before calling spot-solution
                facing_bb   = params.get("_facing_bb", 0.0)
                hero_is_oop = params.get("_hero_is_oop", True)
                if facing_bb > 0:
                    # next-actions at the point BEFORE the bet (IP's or OOP's decision)
                    flop_before_bet = "X" if hero_is_oop else ""
                    na_resp = _query_next_actions(session, api_params, flop_before_bet,
                                                  debug=debug_next_actions)
                    valid_size = _nearest_valid_bet(na_resp, facing_bb,
                                                    debug=debug_next_actions)
                    # GTO Wizard usa R (raise) para bets — "X-R{size}" ou "R{size}"
                    prefix = "X-R" if hero_is_oop else "R"
                    if valid_size is not None:
                        api_params["flop_actions"] = f"{prefix}{valid_size}"
                    else:
                        # Fallback: pot real da resposta next-actions (se disponível)
                        na_game = (na_resp.get("next_actions") or {}).get("game") or {}
                        pot_bb  = float(na_game.get("pot") or spot.get("pot_size") or 0)
                        if pot_bb <= 0:
                            pot_bb = facing_bb * 2
                        std_fracs = [0.25, 0.33, 0.50, 0.67, 0.75, 1.0, 1.25, 1.5, 2.0]
                        std_sizes = sorted(
                            {round(pot_bb * f, 1) for f in std_fracs},
                            key=lambda s: abs(s - facing_bb)
                        )
                        if std_sizes:
                            nearest_std = std_sizes[0]
                            api_params["flop_actions"] = f"{prefix}{nearest_std}"
                            if debug_next_actions:
                                print(f"[facing-fallback] usando {prefix}{nearest_std} "
                                      f"(target={facing_bb}bb, pot={pot_bb:.2f}bb)")

                status, data = call_spot(api_params, debug=debug_next_actions)

                if status == 401:
                    if refresh_auth():
                        status, data = call_spot(api_params, debug=debug_next_actions)

                if status == 200 and data:
                    strategy, top_action = parse_strategy(data)
                    result["gto_found"]      = True
                    result["gto_strategy"]   = strategy
                    result["gto_top_action"] = top_action

                    our_action = (spot.get("example_best_action") or "").lower()
                    gto_key    = {"raise": "bet", "all-in": "allin", "jam": "allin"}.get(our_action, our_action)
                    freq       = strategy.get(gto_key, 0.0)
                    result["our_action_gto_freq"] = freq
                    result["verdict"] = (
                        "agreement"  if freq >= 0.40 else
                        "mixed"      if freq >= 0.15 else
                        "divergence"
                    )
                    strat_str = " | ".join(
                        f"{k} {v*100:.0f}%"
                        for k, v in sorted(strategy.items(), key=lambda x: -x[1])[:3]
                    )
                    print(f"OK  {result['verdict'].upper():<12} our={our_action}({freq*100:.0f}%)  GTO: {strat_str}")

                elif status == 204:
                    print("204 no-content (sem solucao neste spot)")
                    result["error"] = "no_content_204"
                elif status == 403:
                    print("403 forbidden")
                    result["error"] = "forbidden_403"
                elif status == 404:
                    print("404 not found")
                    result["error"] = "not_found_404"
                else:
                    print(f"HTTP {status}")
                    result["error"] = f"http_{status}"

            except Exception as e:
                print(f"ERROR: {e}")
                result["error"] = str(e)

            results.append(result)
            time.sleep(delay)

        # Nao fechar — sessao real do usuario via CDP

    return results


def debug_capture(timeout_s: int = 30):
    """
    Modo debug: mostra todas as requests feitas pelo GTO Wizard.
    Navegue manualmente pelo GTO Wizard e veja quais URLs disparam spot-solution.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: pip install playwright"); sys.exit(1)

    print(f"[debug] Capturando requests por {timeout_s}s — navegue pelo GTO Wizard agora...")
    with sync_playwright() as pw:
        browser = _connect_cdp(pw)
        if not browser:
            print("ERRO: Chrome nao esta rodando com CDP. Execute --start-browser primeiro.")
            sys.exit(1)
        ctx  = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        seen: set = set()
        spot_count = [0]

        def on_req(req):
            url = req.url
            if "api.gtowizard" in url and url not in seen:
                seen.add(url)
                print(f"  REQ  {req.method}  {url[:130]}")

        def on_resp(resp):
            url = resp.url
            if "spot-solution" not in url:
                return
            spot_count[0] += 1
            print(f"\n{'='*70}")
            print(f"  *** SPOT-SOLUTION #{spot_count[0]} ***")
            print(f"  API URL : {url}")
            print(f"  Page URL: {page.url}")
            try:
                data = resp.json()
                n = len(data.get("action_solutions", []))
                print(f"  Status  : {resp.status}  |  action_solutions: {n}")
                if n:
                    for item in data["action_solutions"][:4]:
                        act = item.get("action", {})
                        print(f"    {act.get('type','?'):8}  freq={item.get('total_frequency',0):.2f}")
            except Exception:
                print(f"  Status  : {resp.status}  (nao-JSON)")
            print('='*70 + '\n')

        page.on("request",  on_req)
        page.on("response", on_resp)

        print(f"[debug] Monitorando por {timeout_s}s. Clique em spots no GTO Wizard...")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            page.wait_for_timeout(1000)
            remaining = int(deadline - time.time())
            print(f"  [{remaining}s restantes]", end="\r")

        print("\n[debug] Concluido.")
        # Nao fechar — e a sessao real do usuario via CDP


def main():
    parser = argparse.ArgumentParser(description="Compara spots com GTO Wizard via Playwright")
    parser.add_argument("--start-browser", action="store_true",
                        help="Inicia Chrome com CDP e abre GTO Wizard (feche o Chrome antes)")
    parser.add_argument("--debug",     action="store_true",
                        help="Modo debug: monitora requests enquanto voce navega manualmente")
    parser.add_argument("--debug-time", type=int, default=60,
                        help="Segundos para monitorar no modo --debug (default 60)")
    parser.add_argument("--login",    action="store_true", help="(legado) Forca re-login")
    parser.add_argument("--spots",    default=str(SCRIPTS_DIR / "unique_spots.jsonl"))
    parser.add_argument("--limit",    type=int, default=30)
    parser.add_argument("--street",   default="flop", choices=["flop","turn","river","preflop","all"])
    parser.add_argument("--min-stack",type=float, default=20.0)
    parser.add_argument("--mistakes-only", action="store_true")
    parser.add_argument("--headless", action="store_true", help="Roda sem janela (nao funciona para login)")
    parser.add_argument("--delay",    type=float, default=1.5, help="Delay entre spots em segundos")
    parser.add_argument("--timeout",  type=int, default=12000, help="Timeout por spot em ms")
    parser.add_argument("--output",   default=str(SCRIPTS_DIR / "comparison_results_raw.json"))
    parser.add_argument("--debug-next-actions", action="store_true",
                        help="Mostra resposta raw do next-actions para debug de 422")
    args = parser.parse_args()

    if args.start_browser:
        import subprocess, shutil, tempfile
        chrome = shutil.which("chrome") or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        tmp_dir = tempfile.mkdtemp(prefix="gw_chrome_")
        subprocess.Popen([chrome, f"--remote-debugging-port={CDP_PORT}",
                          f"--user-data-dir={tmp_dir}", GW_APP])
        print(f"Chrome iniciado na porta {CDP_PORT} (perfil temporario: {tmp_dir}).")
        print("Faca login se necessario e rode o script novamente.")
        sys.exit(0)

    if args.debug:
        debug_capture(timeout_s=args.debug_time)
        sys.exit(0)

    if args.login and COOKIES_FILE.exists():
        COOKIES_FILE.unlink()
        print("[login] Cookies removidos.")

    if not Path(args.spots).exists():
        print(f"ERRO: {args.spots} nao encontrado. Execute spot_extractor.py primeiro.")
        sys.exit(1)

    spots: list[dict] = []
    with open(args.spots, encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            if args.street != "all" and s.get("street") != args.street:
                continue
            if float(s.get("stack_bucket", 0)) < args.min_stack:
                continue
            if args.mistakes_only and s.get("our_label") not in ("clear_mistake", "small_mistake", "marginal"):
                continue
            if build_params(s) is None:
                continue
            spots.append(s)
            if args.limit and len(spots) >= args.limit:
                break

    print(f"Spots carregados: {len(spots)}  |  tempo estimado: ~{len(spots) * (args.delay + args.timeout/1000):.0f}s")

    results = run_comparison(spots, headless=args.headless, timeout_ms=args.timeout,
                             delay=args.delay,
                             debug_next_actions=getattr(args, "debug_next_actions", False))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    found    = [r for r in results if r.get("gto_found")]
    verdicts: dict[str, int] = {}
    for r in results:
        k = r.get("verdict") or r.get("error") or "skip"
        verdicts[k] = verdicts.get(k, 0) + 1

    print(f"\n{'='*60}")
    print(f"RESULTADO: {len(found)}/{len(results)} spots encontrados")
    for v, n in sorted(verdicts.items(), key=lambda x: -x[1]):
        pct = n / max(len(results), 1) * 100
        print(f"  {v:<20} {n:>3}  ({pct:.0f}%)")
    print(f"{'='*60}")
    print(f"Salvo em: {args.output}")
    if found:
        print(f"Proximo passo: python analyze_results.py --input {args.output}")


if __name__ == "__main__":
    main()
