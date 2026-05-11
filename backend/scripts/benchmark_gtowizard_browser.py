"""
benchmark_gtowizard_browser.py — Benchmark LeakLab vs GTO Wizard via browser real.

Usa Playwright para abrir o Chrome com o perfil do usuario (ja logado no GTO Wizard)
e fazer as chamadas de API direto do contexto da pagina, onde o browser lida com toda
a autenticacao criptografica automaticamente.

Uso:
    python scripts/benchmark_gtowizard_browser.py [opcoes]

Opcoes:
    --user-id ID       Filtra por user_id (default: todos)
    --limit N          Max spots a testar (default: 10)
    --street flop      Filtra por street: flop, turn, river (default: flop)
    --mistakes-only    So testa decisoes com label != standard
    --db PATH          Caminho do banco SQLite
    --profile PATH     Caminho do perfil Chrome (default: detecta automaticamente)
    --headed           Mostra o browser (util para debug; default: headless)

Pre-requisito: Chrome instalado e usuario logado no GTO Wizard.
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, BrowserContext

# ── Caminhos ──────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_DEFAULT  = BACKEND_DIR / "data" / "leaklab.db"
GW_APP_URL  = "https://app.gtowizard.com"
GW_API_BASE = "https://api.gtowizard.com"

POSITIONS_8MAX = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
POS_IDX = {p: i for i, p in enumerate(POSITIONS_8MAX)}


# ── Perfil Chrome ─────────────────────────────────────────────────────────────

def find_chrome_profile() -> Optional[Path]:
    """Detecta o perfil Chrome padrao no Windows/Mac/Linux."""
    candidates = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(local) / "Google" / "Chrome" / "User Data",
            Path(local) / "Microsoft" / "Edge" / "User Data",
        ]
    elif sys.platform == "darwin":
        home = Path.home()
        candidates = [
            home / "Library" / "Application Support" / "Google" / "Chrome",
            home / "Library" / "Application Support" / "Microsoft Edge",
        ]
    else:
        home = Path.home()
        candidates = [
            home / ".config" / "google-chrome",
            home / ".config" / "microsoft-edge",
        ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ── Banco de dados ─────────────────────────────────────────────────────────────

def fetch_decisions(
    db_path: Path,
    user_id: Optional[int],
    street: str,
    mistakes_only: bool,
    limit: int,
) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    wheres = [
        "d.street = ?",
        "d.board IS NOT NULL AND d.board != ''",
        "d.stack_bb IS NOT NULL AND d.stack_bb > 3",
        "d.pot_size IS NOT NULL AND d.pot_size > 0.5",
        "d.position IS NOT NULL",
    ]
    args: list = [street]

    if user_id:
        wheres.append("t.user_id = ?")
        args.append(user_id)
    if mistakes_only:
        wheres.append("d.label IN ('clear_mistake','small_mistake','marginal')")

    args.append(limit)
    rows = conn.execute(f"""
        SELECT d.id, d.street, d.position, d.board,
               d.action_taken, d.best_action, d.label, d.score,
               d.stack_bb, d.pot_size, d.facing_bet, d.is_3bet,
               d.num_players, d.hand_id, t.user_id
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE {" AND ".join(wheres)}
        ORDER BY d.id DESC
        LIMIT ?
    """, args).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# ── Construcao de params GTO Wizard ───────────────────────────────────────────

def _round_half(x: float) -> float:
    return round(x * 2) / 2


def build_gw_params(dec: dict) -> Optional[dict]:
    try:
        board = json.loads(dec["board"]) if isinstance(dec["board"], str) else dec["board"]
    except Exception:
        return None
    if not board or len(board) < 3:
        return None

    position = (dec.get("position") or "BTN").upper()
    pot_bb   = float(dec["pot_size"])
    stack_bb = float(dec["stack_bb"])
    is_3bet  = bool(dec.get("is_3bet"))

    depth = round(stack_bb + pot_bb / 2, 3)

    if is_3bet:
        threebet_size = _round_half(max(6.0, pot_bb / 2))
        open_size     = _round_half(max(2.0, threebet_size / 3))
    else:
        open_size = _round_half(max(2.0, pot_bb / 2.2))

    pos_idx = POS_IDX.get(position, 5)

    actions: list[str] = []
    if is_3bet:
        if position == "BB":
            for i in range(8):
                if i < 5:    actions.append("F")
                elif i == 5: actions.append(f"R{open_size}")
                elif i == 6: actions.append("F")
                else:        actions.append(f"R{threebet_size}")
            actions.append("C")
        else:
            for i in range(8):
                if i < pos_idx:    actions.append("F")
                elif i == pos_idx: actions.append(f"R{open_size}")
                elif i < 7:        actions.append("F")
                else:              actions.append(f"R{threebet_size}")
            actions.append("C")
    else:
        if position in ("BB", "SB"):
            for i in range(8):
                if i < 5:    actions.append("F")
                elif i == 5: actions.append(f"R{open_size}")
                elif i == 6: actions.append("F")
                else:        actions.append("C")
        else:
            for i in range(8):
                if i < pos_idx:    actions.append("F")
                elif i == pos_idx: actions.append(f"R{open_size}")
                elif i < 7:        actions.append("F")
                else:              actions.append("C")

    flop_cards = board[:3]
    board_str  = "".join(flop_cards)
    stacks_str = "-".join([str(depth)] * 8)

    return {
        "gametype":        "MTTGeneral_8m",
        "depth":           depth,
        "stacks":          stacks_str,
        "preflop_actions": "-".join(actions),
        "flop_actions":    "",
        "turn_actions":    "",
        "river_actions":   "",
        "board":           board_str,
        "_board_list":     board,
        "_position":       position,
        "_is_3bet":        is_3bet,
        "_open_size":      open_size,
    }


# ── Chamada GTO Wizard via browser ────────────────────────────────────────────

def gw_fetch_spot(page: Page, params: dict) -> Optional[dict]:
    """
    Faz fetch do spot-solution direto do contexto do browser (GTO Wizard aberto).
    O browser usa automaticamente a autenticacao criptografica da sessao.
    """
    api_params = {k: v for k, v in params.items() if not k.startswith("_")}
    qs  = urllib.parse.urlencode(api_params)
    url = f"{GW_API_BASE}/v4/solutions/spot-solution/?{qs}"

    js = f"""
    async () => {{
        try {{
            const resp = await fetch({json.dumps(url)}, {{
                method: 'GET',
                credentials: 'include',
            }});
            const text = await resp.text();
            return {{ status: resp.status, body: text }};
        }} catch(e) {{
            return {{ status: 0, body: e.toString() }};
        }}
    }}
    """
    try:
        result = page.evaluate(js)
        if result["status"] == 200:
            return json.loads(result["body"])
        else:
            print(f"  [!] GW status {result['status']}: {result['body'][:150]}")
            return None
    except Exception as e:
        print(f"  [!] Playwright erro: {e}")
        return None


# ── Normalizacao ──────────────────────────────────────────────────────────────

def _norm(a: str) -> str:
    a = (a or "").lower().strip()
    if a in ("check", "x"):                      return "check"
    if a in ("fold", "f"):                        return "fold"
    if a in ("call", "c"):                        return "call"
    if a in ("bet", "raise", "jam", "allin",
             "all-in") or a.startswith("bet_") \
             or a.startswith("raise_"):           return "aggressive"
    return a


def gw_primary(action_solutions: list[dict]) -> tuple[str, float]:
    best = max(action_solutions, key=lambda x: x["total_frequency"])
    t = best["action"]["type"].lower()
    if t == "check":  return "check", best["total_frequency"]
    if t == "call":   return "call",  best["total_frequency"]
    if t == "fold":   return "fold",  best["total_frequency"]
    return "aggressive", best["total_frequency"]


# ── Exibicao ──────────────────────────────────────────────────────────────────

def _bar(freq: float, w: int = 18) -> str:
    f = round(freq * w)
    return "#" * f + "." * (w - f)


def print_spot(dec: dict, params: dict, gw_result: Optional[dict]) -> None:
    b_list = json.loads(dec["board"]) if isinstance(dec["board"], str) else dec["board"]
    b_str  = " ".join(b_list[:3])
    pos    = dec["position"]
    pot    = dec["pot_size"]
    stack  = dec["stack_bb"]
    acted  = dec["action_taken"]
    best   = dec["best_action"]
    label  = dec["label"]
    spr    = round(stack / pot, 2) if pot else 0
    pot_t  = "3BET" if dec.get("is_3bet") else "SRP"

    print()
    print("=" * 72)
    print(f"  {dec['street'].upper()}  Board: {b_str}  |  {pos} ({pot_t})  hand={dec.get('hand_id','?')}")
    print(f"  Pot: {pot:.1f} BB  Stack: {stack:.1f} BB  SPR: {spr}")
    print(f"  Preflop: {params['preflop_actions']}")
    print("-" * 72)
    print(f"  Jogado: {acted:<10}  Nossa recomendacao: {best:<10}  label: {label}")

    if gw_result is None:
        print("  [GTO Wizard: sem resposta]")
        print()
        return

    solutions = gw_result.get("action_solutions", [])
    if not solutions:
        print("  [GTO Wizard: resposta sem acoes]")
        print()
        return

    print()
    print(f"  {'Acao GW':<18} {'Freq':>7}   Barra")
    print("  " + "-" * 42)
    for sol in sorted(solutions, key=lambda x: -x["total_frequency"]):
        t    = sol["action"]["type"]
        bs   = sol["action"].get("betsize", 0)
        freq = sol["total_frequency"]
        lbl  = t + (f" {float(bs):.1f}BB" if bs and float(bs) > 0 else "")
        if sol["action"].get("allin"):
            lbl += " (AI)"
        print(f"  {lbl:<18} {freq*100:>6.1f}%   {_bar(freq)}")

    print()
    gw_p_type, gw_p_freq = gw_primary(solutions)
    match_best = _norm(best)  == gw_p_type
    match_play = _norm(acted) == gw_p_type

    v_best = "[MATCH]"   if match_best else "[DIVERGE]"
    v_play = "[GW OK]"   if match_play else "[GW ERRO]"

    print(f"  Nossa recomendacao: {best:<12} vs GW primary: {gw_p_type} ({gw_p_freq*100:.0f}%)  {v_best}")
    print(f"  Acao jogada:        {acted:<12} {v_play}")
    print()

    return match_best, match_play


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id",      type=int,  default=None)
    parser.add_argument("--limit",        type=int,  default=10)
    parser.add_argument("--street",       default="flop", choices=["flop","turn","river"])
    parser.add_argument("--mistakes-only",action="store_true")
    parser.add_argument("--db",           default=str(DB_DEFAULT))
    parser.add_argument("--profile",      default=None)
    parser.add_argument("--headed",       action="store_true")
    parser.add_argument("--cdp-port",     type=int, default=9222)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"DB nao encontrado: {db_path}")
        sys.exit(1)

    # Perfil Chrome
    profile_path = Path(args.profile) if args.profile else find_chrome_profile()
    if not profile_path:
        print("Perfil Chrome nao encontrado. Use --profile /caminho/perfil")
        sys.exit(1)
    print(f"[browser] Perfil: {profile_path}")

    # Busca decisoes
    decisions = fetch_decisions(db_path, args.user_id, args.street, args.mistakes_only, args.limit)
    print(f"[db] {len(decisions)} decisao(oes) encontrada(s).\n")

    total = matches = gw_ok = 0

    cdp_url = f"http://localhost:{args.cdp_port}"

    with sync_playwright() as pw:
        # Conecta ao Chrome ja aberto via CDP (nao precisa do perfil bloqueado)
        try:
            browser_ctx = pw.chromium.connect_over_cdp(cdp_url)
            print(f"[browser] Conectado ao Chrome via CDP ({cdp_url})")
        except Exception as e:
            print(f"\n[!] Nao conseguiu conectar ao Chrome na porta {args.cdp_port}.")
            print(f"    Erro: {e}")
            print(f"""
Para usar o benchmark, feche o Chrome e abra com debugging habilitado:

  Windows:
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port={args.cdp_port} --user-data-dir="{profile_path}"

  Ou pelo terminal PowerShell:
    Start-Process "chrome.exe" "--remote-debugging-port={args.cdp_port}"

Depois acesse https://app.gtowizard.com e rode este script novamente.
""")
            sys.exit(1)

        # Encontra ou abre uma pagina com o GTO Wizard
        page = None
        for ctx in browser_ctx.contexts:
            for pg in ctx.pages:
                if "gtowizard" in pg.url:
                    page = pg
                    print(f"[browser] Usando aba aberta: {pg.url[:60]}")
                    break
            if page:
                break

        if not page:
            # Abre nova aba com GTO Wizard
            ctx  = browser_ctx.contexts[0] if browser_ctx.contexts else browser_ctx.new_context()
            page = ctx.new_page()
            print("[browser] Abrindo GTO Wizard...")
            page.goto(GW_APP_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

        # Verifica login
        if "login" in page.url.lower() or "sign-in" in page.url.lower():
            print("[!] Nao logado. Faca login no GTO Wizard no browser e rode novamente.")
            browser_ctx.close()
            sys.exit(1)

        print(f"[browser] Sessao ativa em: {page.url[:60]}")
        print("[browser] Iniciando benchmark...\n")

        for dec in decisions:
            params = build_gw_params(dec)
            if not params:
                continue

            b_list = json.loads(dec["board"]) if isinstance(dec["board"], str) else dec["board"]
            print(f"Consultando: {' '.join(b_list[:3])} ({dec['position']})... ", end="", flush=True)

            gw_result = gw_fetch_spot(page, params)
            print("OK" if gw_result else "FALHOU")

            result = print_spot(dec, params, gw_result)
            if gw_result and gw_result.get("action_solutions") and result:
                mb, mp = result
                total  += 1
                if mb: matches += 1
                if mp: gw_ok  += 1

            time.sleep(0.5)

        browser_ctx.close()

    if total > 0:
        print("=" * 72)
        print(f"  RESUMO: {total} spots consultados com resposta do GTO Wizard")
        print(f"  Nossa recomendacao == GTO Wizard: {matches}/{total} ({matches/total*100:.0f}%)")
        print(f"  Acao jogada       == GTO Wizard: {gw_ok}/{total} ({gw_ok/total*100:.0f}%)")
        print()
    else:
        print("Nenhum spot retornou resultado do GTO Wizard.")


if __name__ == "__main__":
    main()
