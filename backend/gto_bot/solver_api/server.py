"""
solver_api/server.py — HTTP wrapper do solver_cli + proxy GTO Wizard via CDP.

Endpoints:
  GET  /health        — status do solver e GTO Wizard auth
  POST /solve         — chama solver_cli Rust e retorna estratégia local
  POST /gto-wizard    — consulta GTO Wizard via CDP e retorna estratégia
  GET  /gw-status     — estado da autenticação GTO Wizard

Autenticação via header x-api-key.

Variáveis de ambiente:
  GTO_API_KEY       chave de autenticação (obrigatória em produção)
  GTO_PORT          porta HTTP (default: 8765)
  GTO_TIMEOUT       timeout do solver_cli em segundos (default: 300)
  CDP_PORT          porta Chrome DevTools (default: 9222)
  GTO_REFRESH_SEC   intervalo de refresh do token GTO Wizard (default: 180)
  GTO_NOTIFY_EMAIL  email destino para alertas de auth
  SMTP_HOST         servidor SMTP (default: smtp.gmail.com)
  SMTP_PORT         porta SMTP (default: 587)
  SMTP_USER         usuário remetente
  SMTP_PASS         senha / app-password
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from email.mime.text import MIMEText
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

API_KEY    = os.environ.get('GTO_API_KEY', '')
PORT       = int(os.environ.get('GTO_PORT', '8765'))
SOLVER_BIN = os.path.join(os.path.dirname(__file__), '..', 'solver_cli', 'target', 'release', 'solver_cli')
TIMEOUT    = int(os.environ.get('GTO_TIMEOUT', '300'))
CDP_PORT   = int(os.environ.get('CDP_PORT', '9222'))
REFRESH_SEC = int(os.environ.get('GTO_REFRESH_SEC', '180'))

GW_APP       = "https://app.gtowizard.com"
GW_API_BASE  = "https://api.gtowizard.com"
GW_SPOT_SOL  = f"{GW_API_BASE}/v4/solutions/spot-solution/"
GW_NEXT_ACTS = f"{GW_API_BASE}/v4/game-points/next-actions/"
GW_CLIENT_ID = os.environ.get('GW_CLIENT_ID', '790ab864-ed0c-4545-9e5a-97efe89672cd')

# Configuração por número de jogadores na mesa.
# Gametypes confirmados via HAR/browser: 9=MTTGeneralV2, 8=MTTGeneral_8m, 6=MTT6mSimple.
# Restantes inferidos pelo padrão de nomenclatura do GTO Wizard.
_TABLE_CONFIG: dict[int, dict] = {
    2: {"gametype": "MTTHUGeneral",   "positions": ["BTN","BB"],                                            "open": 2.0, "stacks": ""},
    3: {"gametype": "MTTGeneral_3m",  "positions": ["BTN","SB","BB"],                                      "open": 2.0},
    4: {"gametype": "MTTGeneral_4m",  "positions": ["CO","BTN","SB","BB"],                                  "open": 2.0},
    5: {"gametype": "MTTGeneral_5m",  "positions": ["HJ","CO","BTN","SB","BB"],                             "open": 2.0},
    6: {"gametype": "MTT6mSimple",    "positions": ["LJ","HJ","CO","BTN","SB","BB"],                        "open": 2.0},
    7: {"gametype": "MTTGeneral_7m",  "positions": ["UTG","LJ","HJ","CO","BTN","SB","BB"],                  "open": 2.0},
    8: {"gametype": "MTTGeneral_8m",  "positions": ["UTG","UTG+1","LJ","HJ","CO","BTN","SB","BB"],          "open": 2.0},
    9: {"gametype": "MTTGeneralV2",   "positions": ["UTG","UTG+1","UTG+2","LJ","HJ","CO","BTN","SB","BB"],  "open": 2.0},
}

OOP_POSITIONS = {"BB", "SB"}


# ── Estado de auth (thread-safe) ──────────────────────────────────────────────

_auth_lock    = threading.Lock()
_auth_headers: dict = {}
_auth_ok      = False
_alert_sent   = False
_last_refresh = 0.0


def _set_auth_ok(headers: dict) -> None:
    global _auth_headers, _auth_ok, _alert_sent, _last_refresh
    with _auth_lock:
        was_down      = not _auth_ok
        _auth_headers = dict(headers)
        _auth_ok      = True
        _last_refresh = time.time()
        if was_down and _alert_sent:
            _alert_sent = False
            threading.Thread(target=_send_email,
                             args=("✅ GTO Wizard auth restaurada",
                                   "A autenticação foi restaurada. Sistema voltou ao normal."),
                             daemon=True).start()
    log.info("gto_wizard: auth OK — headers atualizados")


def _set_auth_failed(reason: str) -> None:
    global _auth_ok, _alert_sent
    with _auth_lock:
        was_ok       = _auth_ok
        _auth_ok     = False
        should_alert = was_ok and not _alert_sent
        if not _auth_ok:
            _alert_sent = True
    log.warning("gto_wizard: auth FALHOU — %s", reason)
    if should_alert:
        threading.Thread(target=_send_email,
                         args=("🔴 GTO Wizard auth caiu — ação necessária",
                               f"A autenticação do GTO Wizard falhou.\n\n"
                               f"Motivo: {reason}\n\n"
                               f"Para restaurar:\n"
                               f"  1. Conecte via VNC ao servidor\n"
                               f"  2. Verifique se o Chrome está rodando na porta {CDP_PORT}\n"
                               f"  3. Faça login no GTO Wizard se necessário\n"
                               f"  4. O sistema retomará automaticamente em {REFRESH_SEC}s\n"),
                         daemon=True).start()


# ── Email SMTP ────────────────────────────────────────────────────────────────

def _send_email(subject: str, body: str) -> None:
    to_addr   = os.environ.get("GTO_NOTIFY_EMAIL", "").strip()
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASS", "").strip()
    if not all([to_addr, smtp_user, smtp_pass]):
        log.debug("email nao configurado — pulando notificacao")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[LeakLab GTO] {subject}"
    msg["From"]    = smtp_user
    msg["To"]      = to_addr
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.ehlo(); s.starttls(context=ctx); s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, [to_addr], msg.as_string())
        log.info("email enviado: %s", subject)
    except Exception as e:
        log.warning("falha ao enviar email: %s", e)


# ── CDP auth capture ──────────────────────────────────────────────────────────

def _capture_headers_via_cdp(timeout_s: int = 25) -> Optional[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("playwright nao instalado")
        return None

    captured: dict = {}
    try:
        pw = sync_playwright().start()
    except Exception as e:
        log.debug("playwright start: %s", e)
        return None

    try:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        except Exception as e:
            log.debug("CDP connect: %s", e)
            return None

        contexts = browser.contexts
        if not contexts:
            return None

        page = contexts[0].pages[0] if contexts[0].pages else contexts[0].new_page()

        def on_req(req):
            if "api.gtowizard.com" not in req.url or captured:
                return
            h = dict(req.headers)
            if "authorization" in h:
                captured.update(h)

        page.on("request", on_req)
        try:
            page.goto(f"{GW_APP}/solutions", timeout=15000, wait_until="domcontentloaded")
        except Exception:
            pass

        deadline = time.time() + timeout_s
        while not captured and time.time() < deadline:
            page.wait_for_timeout(400)

        page.remove_listener("request", on_req)
    finally:
        try:
            pw.stop()
        except Exception:
            pass

    return captured if captured and "authorization" in captured else None


def _refresh_once() -> bool:
    headers = _capture_headers_via_cdp()
    if headers:
        _set_auth_ok(headers)
        return True
    _set_auth_failed(
        f"Chrome nao respondeu via CDP na porta {CDP_PORT} "
        f"ou GTO Wizard nao esta logado"
    )
    return False


def _refresh_loop() -> None:
    log.info("gto_wizard: refresh loop iniciado (intervalo=%ds)", REFRESH_SEC)
    _refresh_once()
    while True:
        time.sleep(REFRESH_SEC)
        _refresh_once()


# ── GTO Wizard query ──────────────────────────────────────────────────────────

# Depths com solução confirmados empiricamente por gametype.
# MTTGeneralV2 (9p): 2026-05-20; MTTHUGeneral (2p): 2026-05-21.
_GW_VALID_DEPTHS: list[int] = sorted([
    7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24, 25,
    32, 34, 35, 36, 38, 40, 42, 44, 46, 48, 50,
    52, 54, 56, 58, 60,
    70, 80, 100, 130, 160, 200,
])

# HU tem depths completamente diferentes — soluções pré-computadas em subset menor.
_GW_HU_VALID_DEPTHS: list[int] = sorted([
    13, 14, 15, 16, 18, 20, 25, 26, 27, 28, 40, 41, 50, 51, 60, 61, 62, 63, 64, 65,
])

# Mapeamento gametype → lista de depths válidos (fallback: _GW_VALID_DEPTHS)
_GW_DEPTHS_BY_GAMETYPE: dict[str, list[int]] = {
    "MTTHUGeneral": _GW_HU_VALID_DEPTHS,
}


def _snap_to_valid_depth(stack_bb: float, gametype: str = "") -> int:
    """Retorna o depth válido do GTO Wizard mais próximo ao stack informado."""
    depths = _GW_DEPTHS_BY_GAMETYPE.get(gametype, _GW_VALID_DEPTHS)
    n = round(float(stack_bb))
    n = min(n, max(depths))
    return min(depths, key=lambda d: abs(d - n))


def _stack_frac(stack_bb: float, gametype: str = "") -> float:
    """Converte stack para formato V2: depth válido mais próximo + 0.125."""
    return round(float(_snap_to_valid_depth(stack_bb, gametype)) + 0.125, 3)


def _retry_depths(snapped: int, gametype: str = "", max_retries: int = 6) -> list[int]:
    """Retorna depths alternativos para retry quando 403 (válidos, em ordem de distância)."""
    depths = _GW_DEPTHS_BY_GAMETYPE.get(gametype, _GW_VALID_DEPTHS)
    idx = depths.index(snapped) if snapped in depths else -1
    candidates = []
    for offset in range(1, max_retries + 1):
        if idx + offset < len(depths):
            candidates.append(depths[idx + offset])
        if idx - offset >= 0:
            candidates.append(depths[idx - offset])
    return candidates


def _stacks_param(stack_bb: float, n_players: int) -> str:
    """Gera string de stacks: todos iguais ao hero (modelo simplificado), n_players entradas."""
    sf = _stack_frac(stack_bb)
    return "-".join([str(sf)] * n_players)


def _get_table_config(num_players: int) -> Optional[dict]:
    """Retorna config (gametype, positions, open) para o tamanho de mesa, ou None se não suportado."""
    if num_players in _TABLE_CONFIG:
        return _TABLE_CONFIG[num_players]
    return None


def _norm_board(board, max_cards: int = 3) -> str:
    """Normaliza board para string GW. max_cards: 3=flop, 4=turn, 5=river."""
    if isinstance(board, str):
        board = board.strip().split()
    result = []
    for c in list(board)[:max_cards]:
        c = str(c).strip()
        if len(c) >= 2:
            result.append(c[0].upper() + c[1].lower())
    # Exige exatamente max_cards cartas válidas para flop (3), aceita menos para turn/river
    if len(result) < 3:
        return ""
    return "".join(result)


def _make_session(headers: dict):
    import requests
    s = requests.Session()
    s.headers.update({
        "authorization":      headers.get("authorization", ""),
        "accept":             "application/json, text/plain, */*",
        "origin":             GW_APP,
        "referer":            GW_APP + "/",
        "gwclientid":         headers.get("gwclientid", GW_CLIENT_ID),
        "user-agent":         headers.get("user-agent", "Mozilla/5.0"),
        "sec-ch-ua":          headers.get("sec-ch-ua", '"Chromium";v="147", "Not/A)Brand";v="24"'),
        "sec-ch-ua-mobile":   headers.get("sec-ch-ua-mobile", "?0"),
        "sec-ch-ua-platform": headers.get("sec-ch-ua-platform", '"Linux"'),
    })
    if "google-anal-id" in headers:
        s.headers["google-anal-id"] = headers["google-anal-id"]
    return s


def _nearest_valid_bet(session, api_params: dict, street_before: str,
                       target_bb: float, street: str = "flop") -> Optional[float]:
    """Consulta GW para encontrar o tamanho de bet válido mais próximo de target_bb."""
    params = dict(api_params)
    key = f"{street}_actions"
    params[key] = street_before
    try:
        r = session.get(GW_NEXT_ACTS, params=params, timeout=10)
        if not r.ok or not r.content:
            return None
        na    = r.json().get("next_actions") or {}
        avail = na.get("available_actions") or []
        sizes = []
        for item in avail:
            act   = item.get("action") or item
            atype = str(act.get("type") or "").upper()
            if atype not in ("BET", "RAISE", "ALL_IN", "ALLIN"):
                continue
            bs = act.get("betsize")
            if bs is not None:
                try:
                    sz = float(bs)
                    if sz > 0:
                        sizes.append(sz)
                except (ValueError, TypeError):
                    pass
        return min(sizes, key=lambda s: abs(s - target_bb)) if sizes else None
    except Exception:
        return None


def _preflop_decision_point(position: str, facing_size_bb: float, positions: list[str], open_size: float) -> Optional[str]:
    """
    Constrói a string de ações preflop até (não incluindo) a ação do hero.
    Recebe a lista de posições do gametype correto para o tamanho da mesa.

    Retorna None para posição desconhecida, limp (0 < facing < 1.5bb) ou jam > 6bb.
    """
    if position not in positions:
        return None
    hero_idx = positions.index(position)
    open_s   = str(open_size) if open_size != int(open_size) else str(int(open_size))

    if facing_size_bb == 0 and position != "BB":
        return "-".join(["F"] * hero_idx) if hero_idx else ""

    if facing_size_bb == 0 and position == "BB":
        # BB free play: assume SB completou (limp)
        return "-".join(["F"] * (hero_idx - 1) + ["C"])

    if 0 < facing_size_bb < 1.5:
        return None  # limp — fora da árvore MTT

    if facing_size_bb > 6.0:
        return None  # jam preflop — não modelado

    # Facing raise padrão (1.5–6bb)
    if "BTN" in positions:
        btn_idx = positions.index("BTN")
    else:
        btn_idx = hero_idx - 2 if hero_idx >= 2 else 0

    sb_idx = positions.index("SB") if "SB" in positions else -1

    if position == "BB":
        actions = []
        for i in range(hero_idx):
            if i == btn_idx:
                actions.append(f"R{open_s}")
            elif i == sb_idx:
                actions.append("F")
            else:
                actions.append("F")
        return "-".join(actions)

    if position == "SB":
        actions = ["F" if i != btn_idx else f"R{open_s}" for i in range(hero_idx)]
        return "-".join(actions)

    # IP (CO/HJ/LJ etc.) vs raise: assume UTG (idx=0) abriu
    actions = [f"R{open_s}" if i == 0 else "F" for i in range(hero_idx)]
    return "-".join(actions)


def _postflop_preflop_seq(position: str, positions: list[str], open_size: float) -> Optional[str]:
    """
    Constrói a sequência preflop que leva a um pot HU no postflop (pot single-raised).

    Modela sempre: hero RFI (IP) ou hero é BB/SB chamando o open do BTN.
    Retorna None se posição não está na lista.
    """
    if position not in positions:
        return None
    hero_idx = positions.index(position)
    open_s   = str(open_size) if open_size != int(open_size) else str(int(open_size))
    n        = len(positions)
    btn_idx  = positions.index("BTN") if "BTN" in positions else n - 3
    sb_idx   = positions.index("SB")  if "SB"  in positions else n - 2
    bb_idx   = positions.index("BB")  if "BB"  in positions else n - 1

    if position == "BB":
        # BTN abriu, SB foldou, BB chamou
        actions = []
        for i in range(bb_idx):
            if i == btn_idx:
                actions.append(f"R{open_s}")
            elif i == sb_idx:
                actions.append("F")
            else:
                actions.append("F")
        actions.append("C")  # BB chama
        return "-".join(actions)

    if position == "SB":
        # BTN abriu, SB chamou HU (BB foldou)
        actions = ["F" if i != btn_idx else f"R{open_s}" for i in range(sb_idx)]
        actions.append("C")  # SB chama
        actions.append("F")  # BB folda (SB vs BTN é HU)
        return "-".join(actions)

    # IP (BTN, CO, HJ, LJ, UTG*): hero abriu, todos depois foldaram exceto BB que chamou
    actions = []
    for i in range(hero_idx):
        actions.append("F")
    actions.append(f"R{open_s}")   # hero abre
    for i in range(hero_idx + 1, n):
        p = positions[i]
        if p == "BB":
            actions.append("C")   # BB chama
        else:
            actions.append("F")   # todos os outros foldaram (BTN, SB, outros IP)
    return "-".join(actions)


def query_gto_wizard(spot: dict) -> dict:
    """
    Recebe parâmetros do spot e retorna estratégia do GTO Wizard.

    Parâmetros esperados:
      street, position, board (list ou string), hero_stack_bb,
      facing_size_bb (default 0), pot_bb (default 0), num_players (default 9)

    Retorna:
      {"found": true, "strategy": [{action, frequency, betsize_bb}]}
      {"found": false, "error": "..."}
    """
    with _auth_lock:
        if not _auth_ok or not _auth_headers:
            return {"found": False, "error": "auth_unavailable"}
        headers = dict(_auth_headers)

    street         = str(spot.get("street", "flop")).lower()
    position       = str(spot.get("position", "")).upper().strip()
    board          = spot.get("board", [])
    hero_stack_bb  = float(spot.get("hero_stack_bb", 20))
    facing_size_bb = float(spot.get("facing_size_bb", 0) or 0)
    num_players    = int(spot.get("num_players", 9) or 9)

    # Normaliza aliases de posição
    _pos_alias = {"MP1": "LJ", "MP2": "HJ", "MP": "LJ", "EP": "UTG"}
    position   = _pos_alias.get(position, position)
    if num_players == 2 and position == "SB":
        position = "BTN"  # HU: BTN posta o small blind

    # Resolve config de mesa — usa exato ou None (spot ignorado)
    tbl = _TABLE_CONFIG.get(num_players)
    if tbl is None:
        return {"found": False, "error": f"unsupported_num_players:{num_players}"}

    gametype   = tbl["gametype"]
    positions  = tbl["positions"]
    open_size  = tbl["open"]

    # Normaliza posição para as disponíveis neste gametype
    # Ex: UTG+2 em 8-max → LJ (mesma profundidade de ação); UTG+1 em 7-max → LJ
    if position not in positions:
        _pos_fallback: dict[str, list[str]] = {
            "UTG+2": ["LJ", "UTG+1", "UTG"],
            "UTG+1": ["LJ", "UTG"],
            "LJ":    ["UTG+1", "UTG"],
            "HJ":    ["CO", "LJ", "UTG+1", "UTG"],
        }
        for fb in _pos_fallback.get(position, []):
            if fb in positions:
                position = fb
                break
    stack_frac = _stack_frac(hero_stack_bb, gametype)
    # HU (MTTHUGeneral) usa stacks="" — confirmado via HAR. Outros gametypes usam stacks iguais.
    stacks_str = tbl.get("stacks", _stacks_param(hero_stack_bb, num_players))

    try:
        session = _make_session(headers)
    except ImportError:
        return {"found": False, "error": "requests_not_installed"}

    # ── Preflop ────────────────────────────────────────────────────────────────
    if street == "preflop":
        decision_point = _preflop_decision_point(position, facing_size_bb, positions, open_size)
        if decision_point is None:
            return {"found": False, "error": f"preflop_unknown_position:{position}"}

        api_params = {
            "gametype":        gametype,
            "depth":           stack_frac,
            "stacks":          stacks_str,
            "preflop_actions": decision_point,
            "flop_actions":    "",
            "turn_actions":    "",
            "river_actions":   "",
            "board":           "",
        }
        try:
            r = session.get(GW_SPOT_SOL, params=api_params, timeout=15)
        except Exception as e:
            return {"found": False, "error": str(e)}

        if r.status_code == 401:
            _set_auth_failed("Token expirado (HTTP 401)")
            return {"found": False, "error": "auth_expired"}
        if r.status_code in (204, 404) or not r.content:
            return {"found": False, "error": f"no_preflop_solution_{r.status_code}"}
        if not r.ok:
            log.warning("gto_wizard preflop: HTTP %d pos=%s stack=%.0f facing=%.1f — %s",
                        r.status_code, position, hero_stack_bb, facing_size_bb, r.text[:200])
            return {"found": False, "error": f"http_{r.status_code}"}

        try:
            data = r.json()
        except Exception:
            return {"found": False, "error": "invalid_json"}

        strategy = []
        for item in data.get("action_solutions", []):
            atype = (item.get("action", {}).get("type") or "").lower()
            freq  = float(item.get("total_frequency") or 0)
            name  = {"check": "check", "call": "call", "fold": "fold",
                     "bet": "raise", "raise": "raise",
                     "all_in": "allin", "allin": "allin"}.get(atype, atype)
            if item.get("action", {}).get("allin"):
                name = "allin"
            strategy.append({"action": name, "frequency": freq, "betsize_bb": None})

        if not strategy:
            return {"found": False, "error": "empty_preflop_strategy"}

        log.info("gto_wizard preflop: OK %s %d-max %.0fbb facing=%.1f dp=%s → %d acoes",
                 position, num_players, hero_stack_bb, facing_size_bb, decision_point, len(strategy))
        return {"found": True, "strategy": strategy, "source": "gtowizard_preflop"}

    # ── Postflop (flop/turn/river) ─────────────────────────────────────────────
    if street not in ("flop", "turn", "river"):
        return {"found": False, "error": f"unsupported_street:{street}"}

    preflop = _postflop_preflop_seq(position, positions, open_size)
    if not preflop:
        return {"found": False, "error": f"unknown_position:{position}"}

    # Send correct number of board cards: 3=flop, 4=turn, 5=river
    _street_cards = {"flop": 3, "turn": 4, "river": 5}
    board_str = _norm_board(board, max_cards=_street_cards.get(street, 3))
    if not board_str:
        return {"found": False, "error": "invalid_board"}

    hero_is_oop = position in OOP_POSITIONS

    api_params = {
        "gametype":        gametype,
        "depth":           stack_frac,
        "stacks":          stacks_str,
        "preflop_actions": preflop,
        "flop_actions":    "",
        "turn_actions":    "",
        "river_actions":   "",
        "board":           board_str,
    }

    # Build action context for the decision street.
    # Root of each street is modeled as X-X (both players checked previous streets).
    # If facing a bet, reconstruct the action sequence to that bet.
    if street == "flop":
        if facing_size_bb > 0:
            flop_before = "X" if hero_is_oop else ""
            prefix      = "X-R" if hero_is_oop else "R"
            valid_size  = _nearest_valid_bet(session, api_params, flop_before, facing_size_bb, street="flop")
            api_params["flop_actions"] = f"{prefix}{valid_size if valid_size else round(facing_size_bb, 1)}"
    elif street == "turn":
        api_params["flop_actions"] = "X-X"
        if facing_size_bb > 0:
            turn_before = "X" if hero_is_oop else ""
            prefix      = "X-R" if hero_is_oop else "R"
            valid_size  = _nearest_valid_bet(session, api_params, turn_before, facing_size_bb, street="turn")
            api_params["turn_actions"] = f"{prefix}{valid_size if valid_size else round(facing_size_bb, 1)}"
    elif street == "river":
        api_params["flop_actions"] = "X-X"
        api_params["turn_actions"] = "X-X"
        if facing_size_bb > 0:
            river_before = "X" if hero_is_oop else ""
            prefix       = "X-R" if hero_is_oop else "R"
            valid_size   = _nearest_valid_bet(session, api_params, river_before, facing_size_bb, street="river")
            api_params["river_actions"] = f"{prefix}{valid_size if valid_size else round(facing_size_bb, 1)}"

    try:
        r = session.get(GW_SPOT_SOL, params=api_params, timeout=15)
    except Exception as e:
        return {"found": False, "error": str(e)}

    if r.status_code == 401:
        _set_auth_failed("Token expirado (HTTP 401)")
        return {"found": False, "error": "auth_expired"}

    # 403 = depth não tem solução para esta posição/gametype — tentar depths alternativos
    if r.status_code == 403:
        snapped = _snap_to_valid_depth(hero_stack_bb)
        for alt_depth in _retry_depths(snapped, gametype):
            alt_frac   = round(alt_depth + 0.125, 3)
            alt_stacks = "-".join([str(alt_frac)] * num_players)
            alt_params = dict(api_params)
            alt_params["depth"]  = alt_frac
            alt_params["stacks"] = alt_stacks
            try:
                r2 = session.get(GW_SPOT_SOL, params=alt_params, timeout=15)
            except Exception:
                continue
            if r2.ok and r2.content:
                r          = r2
                stack_frac = alt_frac
                stacks_str = alt_stacks
                log.info("gto_wizard: retry depth %s→%s OK (%s %s %d-max)",
                         snapped, alt_depth, position, street, num_players)
                break
        else:
            # Último recurso: re-consulta com facing=0 (root do street) — mesma lógica que funciona
            if facing_size_bb > 0:
                log.info("gto_wizard: fallback root street — re-query facing=0 (%s %s %d-max)",
                         position, street, num_players)
                fallback = query_gto_wizard({**spot, "facing_size_bb": 0.0})
                if fallback.get("found"):
                    fallback["_fallback"] = "root_street"
                    return fallback
                return {"found": False, "error": "http_403_no_valid_depth"}
            else:
                return {"found": False, "error": "http_403_no_valid_depth"}

    if r.status_code == 204 or not r.content:
        return {"found": False, "error": "no_solution_204"}

    if not r.ok:
        return {"found": False, "error": f"http_{r.status_code}"}

    try:
        data = r.json()
    except Exception:
        return {"found": False, "error": "invalid_json"}

    strategy = []
    for item in data.get("action_solutions", []):
        atype = (item.get("action", {}).get("type") or "").lower()
        freq  = float(item.get("total_frequency") or 0)
        bs    = item.get("action", {}).get("betsize")
        allin = item.get("action", {}).get("allin", False)
        name  = {"check": "check", "call": "call", "fold": "fold",
                 "bet": "bet", "raise": "raise",
                 "all_in": "allin", "allin": "allin"}.get(atype, atype)
        if allin:
            name = "allin"
        strategy.append({
            "action":     name,
            "frequency":  freq,
            "betsize_bb": float(bs) if bs else None,
        })

    if not strategy:
        return {"found": False, "error": "empty_strategy"}

    log.info("gto_wizard: OK %s %s %d-max %.0fbb facing=%.1f → %d acoes",
             position, board_str, num_players, hero_stack_bb, facing_size_bb, len(strategy))
    return {"found": True, "strategy": strategy, "source": "gtowizard"}


# ── Solver local ──────────────────────────────────────────────────────────────

def solve(spot: dict) -> dict:
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
        json.dump(spot, f)
        tmp = f.name
    try:
        with open(tmp, 'r', encoding='utf-8') as stdin_f:
            proc = subprocess.run(
                [SOLVER_BIN],
                stdin=stdin_f,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=TIMEOUT,
            )
        if proc.returncode != 0:
            err = proc.stderr[:500] if proc.stderr else 'solver_cli error'
            raise RuntimeError(f'solver exit={proc.returncode}: {err}')
        result = json.loads(proc.stdout)
        if 'exploitability' in result and 'exploitability_pct' not in result:
            result['exploitability_pct'] = result['exploitability']
        return result
    finally:
        os.unlink(tmp)


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _respond(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _check_auth(self) -> bool:
        if API_KEY and self.headers.get('x-api-key') != API_KEY:
            self._respond(401, {'error': 'unauthorized'})
            return False
        return True

    def _read_body(self) -> Optional[dict]:
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        try:
            return json.loads(body)
        except Exception:
            self._respond(400, {'error': 'invalid JSON'})
            return None

    def do_GET(self):
        if self.path == '/health':
            with _auth_lock:
                gw_ok = _auth_ok
            self._respond(200, {
                'status':     'ok',
                'solver':     os.path.basename(SOLVER_BIN),
                'gto_wizard': 'ok' if gw_ok else 'degraded',
            })
        elif self.path == '/gw-status':
            with _auth_lock:
                age = round(time.time() - _last_refresh, 1) if _last_refresh else None
                self._respond(200 if _auth_ok else 503, {
                    'auth_ok':     _auth_ok,
                    'age_sec':     age,
                    'cdp_port':    CDP_PORT,
                    'refresh_sec': REFRESH_SEC,
                })
        else:
            self._respond(404, {'error': 'not found'})

    def do_POST(self):
        if not self._check_auth():
            return

        if self.path == '/solve':
            spot = self._read_body()
            if spot is None:
                return
            start = time.time()
            try:
                result  = solve(spot)
                elapsed = round(time.time() - start, 2)
                log.info('solved in %.1fs: %s %.0f%% exploit=%.2f%%',
                         elapsed, result.get('primary_action'),
                         result.get('primary_freq', 0) * 100,
                         result.get('exploitability', 0))
                self._respond(200, result)
            except subprocess.TimeoutExpired:
                log.warning('timeout after %ds', TIMEOUT)
                self._respond(408, {'error': f'solver timeout after {TIMEOUT}s'})
            except Exception as e:
                log.error('solver error: %s', e)
                self._respond(500, {'error': str(e)})

        elif self.path == '/gto-wizard':
            spot = self._read_body()
            if spot is None:
                return
            result = query_gto_wizard(spot)
            code   = 200 if result.get("found") else 503 if result.get("error") == "auth_unavailable" else 404
            self._respond(code, result)

        else:
            self._respond(404, {'error': 'not found'})


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not os.path.isfile(SOLVER_BIN):
        log.error('solver_cli nao encontrado em %s', SOLVER_BIN)
        sys.exit(1)

    if not API_KEY:
        log.warning('GTO_API_KEY nao definida — endpoint sem autenticacao!')

    # Inicia refresh loop do GTO Wizard em background
    threading.Thread(target=_refresh_loop, name='gw-auth-refresh', daemon=True).start()

    log.info('Solver API na porta %d (solver=%s timeout=%ds cdp=%d)',
             PORT, SOLVER_BIN, TIMEOUT, CDP_PORT)
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    server.serve_forever()
