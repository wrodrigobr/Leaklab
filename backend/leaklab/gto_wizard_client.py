"""
gto_wizard_client.py — GTO Wizard API client com auto-refresh de auth via CDP.

Mantém o google-anal-id e Bearer token frescos em background thread.
Envia email SMTP quando a autenticação cai (Chrome down, sessão expirada, etc.)
e outro email quando a autenticação é restaurada.

Variáveis de ambiente:
    GTO_WIZARD_ENABLED   "true" para habilitar (default: false)
    CDP_PORT             porta Chrome DevTools Protocol (default: 9222)
    GW_CLIENT_ID         client ID do app (fixo por conta)
    GTO_NOTIFY_EMAIL     email destino para alertas de auth
    SMTP_HOST            servidor SMTP (default: smtp.gmail.com)
    SMTP_PORT            porta SMTP (default: 587)
    SMTP_USER            usuário/remetente
    SMTP_PASS            senha ou app-password
    GTO_REFRESH_SEC      intervalo de refresh em segundos (default: 180)
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
import threading
import time
from email.mime.text import MIMEText
from typing import Optional

log = logging.getLogger(__name__)

# ── Configuração ───────────────────────────────────────────────────────────────

def _enabled() -> bool:
    return os.environ.get("GTO_WIZARD_ENABLED", "").lower() in ("true", "1", "yes")

def _cdp_port() -> int:
    return int(os.environ.get("CDP_PORT", "9222"))

GW_API_BASE   = "https://api.gtowizard.com"
GW_APP        = "https://app.gtowizard.com"
GW_SPOT_SOL   = f"{GW_API_BASE}/v4/solutions/spot-solution/"
GW_NEXT_ACTS  = f"{GW_API_BASE}/v4/game-points/next-actions/"
GW_CLIENT_ID  = os.environ.get("GW_CLIENT_ID", "790ab864-ed0c-4545-9e5a-97efe89672cd")

REFRESH_SEC   = int(os.environ.get("GTO_REFRESH_SEC", "180"))  # 3 minutos

GAMETYPE      = "MTTGeneral"
STACK_SNAPS   = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]

# Preflop sequences para MTTGeneral 9-max (8 ações)
# Confirmado via API: BTN = F-F-F-F-F-R2.3-F-C
PREFLOP_BY_POS: dict[str, str] = {
    "UTG":   "R2.3-F-F-F-F-F-F-C",
    "UTG+1": "F-R2.3-F-F-F-F-F-C",
    "UTG+2": "F-F-R2.3-F-F-F-F-C",
    "LJ":    "F-F-R2.3-F-F-F-F-C",
    "HJ":    "F-F-F-R2.3-F-F-F-C",
    "CO":    "F-F-F-F-R2.3-F-F-C",
    "BTN":   "F-F-F-F-F-R2.3-F-C",
    "SB":    "F-F-F-F-F-F-R2.3-C",
    "BB":    "F-F-F-F-F-R2.3-F-C",  # BTN abre, SB fold, BB call (OOP hero)
    "MP":    "F-F-R2.3-F-F-F-F-C",
    "EP":    "R2.3-F-F-F-F-F-F-C",
}
OOP_POSITIONS = {"BB", "SB"}


# ── Estado de autenticação (thread-safe) ───────────────────────────────────────

_auth_lock    = threading.Lock()
_auth_headers: dict = {}
_auth_ok      = False
_alert_sent   = False    # evita spam de emails no mesmo incidente
_last_refresh = 0.0
_stop_event   = threading.Event()
_thread: Optional[threading.Thread] = None


def _set_auth_ok(headers: dict) -> None:
    global _auth_headers, _auth_ok, _alert_sent, _last_refresh
    with _auth_lock:
        was_down    = not _auth_ok
        _auth_headers = dict(headers)
        _auth_ok      = True
        _last_refresh = time.time()
        if was_down and _alert_sent:
            _alert_sent = False
            threading.Thread(
                target=_send_email,
                args=("✅ GTO Wizard auth restaurada",
                      "A autenticação do GTO Wizard foi restaurada com sucesso.\n"
                      "O sistema voltou a usar o GTO Wizard como fonte primária."),
                daemon=True,
            ).start()
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
        threading.Thread(
            target=_send_email,
            args=("🔴 GTO Wizard auth caiu — ação necessária",
                  f"A autenticação do GTO Wizard falhou.\n\n"
                  f"Motivo: {reason}\n\n"
                  f"Para restaurar:\n"
                  f"  1. Conecte via VNC ao servidor\n"
                  f"  2. Verifique se o Chrome está rodando na porta {_cdp_port()}\n"
                  f"  3. Faça login no GTO Wizard se a sessão expirou\n"
                  f"  4. O sistema retomará automaticamente na próxima tentativa ({REFRESH_SEC}s)\n"),
            daemon=True,
        ).start()


def get_headers() -> Optional[dict]:
    with _auth_lock:
        if _auth_ok and _auth_headers:
            return dict(_auth_headers)
    return None


def get_status() -> dict:
    with _auth_lock:
        return {
            "enabled":      _enabled(),
            "auth_ok":      _auth_ok,
            "last_refresh": _last_refresh,
            "age_sec":      round(time.time() - _last_refresh, 1) if _last_refresh else None,
            "cdp_port":     _cdp_port(),
            "refresh_sec":  REFRESH_SEC,
        }


# ── Email SMTP ────────────────────────────────────────────────────────────────

def _send_email(subject: str, body: str) -> None:
    to_addr   = os.environ.get("GTO_NOTIFY_EMAIL", "").strip()
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASS", "").strip()

    if not all([to_addr, smtp_user, smtp_pass]):
        log.debug("gto_wizard: email não configurado (GTO_NOTIFY_EMAIL/SMTP_USER/SMTP_PASS ausentes)")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[LeakLab GTO] {subject}"
    msg["From"]    = smtp_user
    msg["To"]      = to_addr

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, [to_addr], msg.as_string())
        log.info("gto_wizard: email enviado para %s — %s", to_addr, subject)
    except Exception as e:
        log.warning("gto_wizard: falha ao enviar email — %s", e)


# ── Captura de headers via CDP ────────────────────────────────────────────────

def _capture_headers_via_cdp(timeout_s: int = 25) -> Optional[dict]:
    """
    Conecta ao Chrome via CDP, navega para /solutions para disparar
    um request autenticado, captura e retorna os headers.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("gto_wizard: playwright não instalado — instale com: pip install playwright")
        return None

    captured: dict = {}
    cdp_url = f"http://localhost:{_cdp_port()}"

    try:
        pw = sync_playwright().start()
    except Exception as e:
        log.debug("gto_wizard: playwright start failed — %s", e)
        return None

    try:
        try:
            browser = pw.chromium.connect_over_cdp(cdp_url)
        except Exception as e:
            log.debug("gto_wizard: CDP connect failed — %s", e)
            return None

        contexts = browser.contexts
        if not contexts:
            log.debug("gto_wizard: nenhum contexto no browser")
            return None

        ctx  = contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_req(req):
            if "api.gtowizard.com" not in req.url or captured:
                return
            h = dict(req.headers)
            if "authorization" in h:
                captured.update(h)

        page.on("request", on_req)

        # Navega para disparar requests autenticados
        # Usa Cash6max → MTTGeneral para evitar cache da SPA
        try:
            page.goto(f"{GW_APP}/solutions", timeout=15000, wait_until="domcontentloaded")
        except Exception:
            pass

        deadline = time.time() + timeout_s
        while not captured and time.time() < deadline:
            page.wait_for_timeout(400)

        page.remove_listener("request", on_req)

        # Não fecha o browser — é a sessão real do usuário
    finally:
        try:
            pw.stop()
        except Exception:
            pass

    return captured if captured and "authorization" in captured else None


# ── Background refresh loop ───────────────────────────────────────────────────

def _refresh_once() -> bool:
    headers = _capture_headers_via_cdp()
    if headers:
        _set_auth_ok(headers)
        return True
    else:
        _set_auth_failed(
            f"Chrome não respondeu via CDP na porta {_cdp_port()} "
            f"ou GTO Wizard não está logado"
        )
        return False


def _refresh_loop() -> None:
    log.info("gto_wizard: background refresher iniciado (intervalo=%ds)", REFRESH_SEC)
    # Primeira tentativa imediata
    _refresh_once()
    while not _stop_event.wait(REFRESH_SEC):
        _refresh_once()
    log.info("gto_wizard: background refresher encerrado")


def start_background_refresher() -> None:
    """Inicia o thread de refresh. Chame uma vez no startup do app."""
    global _thread
    if not _enabled():
        log.info("gto_wizard: desabilitado (GTO_WIZARD_ENABLED != true)")
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_refresh_loop, name="gto-wizard-auth", daemon=True)
    _thread.start()


def stop_background_refresher() -> None:
    _stop_event.set()


# ── Auxiliares de params ──────────────────────────────────────────────────────

def _nearest_snap(stack_bb: float) -> int:
    return min(STACK_SNAPS, key=lambda s: abs(s - stack_bb))


def _norm_board(board: list[str]) -> str:
    result = []
    for c in board[:3]:
        c = c.strip()
        if len(c) >= 2:
            result.append(c[0].upper() + c[1].lower())
    return "".join(result) if len(result) == 3 else ""


def _make_session(headers: dict):
    """Monta requests.Session com os headers capturados."""
    try:
        import requests
    except ImportError:
        return None

    s = requests.Session()
    s.headers.update({
        "authorization":      headers.get("authorization", ""),
        "accept":             "application/json, text/plain, */*",
        "origin":             GW_APP,
        "referer":            GW_APP + "/",
        "gwclientid":         headers.get("gwclientid", GW_CLIENT_ID),
        "user-agent":         headers.get("user-agent",
                                          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                                          "Chrome/147.0.0.0 Safari/537.36"),
        "sec-ch-ua":          headers.get("sec-ch-ua",
                                          '"Chromium";v="147", "Not/A)Brand";v="24"'),
        "sec-ch-ua-mobile":   headers.get("sec-ch-ua-mobile", "?0"),
        "sec-ch-ua-platform": headers.get("sec-ch-ua-platform", '"Linux"'),
    })
    if "google-anal-id" in headers:
        s.headers["google-anal-id"] = headers["google-anal-id"]
    return s


def _nearest_valid_bet(session, api_params: dict, flop_before: str,
                       target_bb: float) -> Optional[float]:
    """
    Chama game-points/next-actions para encontrar o bet size válido mais próximo
    de target_bb no tree do GTO Wizard.
    """
    params = dict(api_params)
    params["flop_actions"] = flop_before
    try:
        r = session.get(GW_NEXT_ACTS, params=params, timeout=10)
        if not r.ok or not r.content:
            return None
        data  = r.json()
        na    = data.get("next_actions") or {}
        avail = na.get("available_actions") or []
        sizes: list[float] = []
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


def _parse_strategy(data: dict) -> list[dict]:
    """Converte action_solutions do GTO Wizard para o formato interno do LeakLab."""
    result = []
    for item in data.get("action_solutions", []):
        atype = (item.get("action", {}).get("type") or "").lower()
        freq  = float(item.get("total_frequency") or 0)
        bs    = item.get("action", {}).get("betsize")
        allin = item.get("action", {}).get("allin", False)

        name_map = {
            "check": "check", "call": "call", "fold": "fold",
            "bet": "bet", "raise": "raise", "all_in": "allin", "allin": "allin",
        }
        action_name = name_map.get(atype, atype)
        if allin:
            action_name = "allin"

        result.append({
            "action":             action_name,
            "frequency":          freq,
            "combos":             None,
            "ev_bb":              None,
            "exploitability_pct": None,   # GTO Wizard não reporta exploitability
            "betsize_bb":         float(bs) if bs else None,
        })
    return result


# ── API pública: query_spot ───────────────────────────────────────────────────

def query_spot(
    street: str,
    position: str,
    board: list[str],
    hero_stack_bb: float,
    facing_size_bb: float = 0.0,
    pot_bb: float = 0.0,
) -> Optional[dict]:
    """
    Consulta o GTO Wizard para um spot postflop.

    Retorna None se:
      - GTO_WIZARD_ENABLED não está ativo
      - Auth não disponível (Chrome down, sessão expirada)
      - API retornou erro ou sem solução
      - Street não é flop (turn/river: futuro)

    Retorna dict no formato de lookup_gto:
    {
        "found":               True,
        "source":              "gtowizard",
        "strategy":            [{action, frequency, ev_bb, exploitability_pct, betsize_bb}],
        "exploitability_pct":  None,
        "spot_hash":           None,  # preenchido pelo caller
        "queued":              False,
    }
    """
    if not _enabled():
        return None

    # Por ora apenas flop; turn/river ficam para o solver local
    if street.lower() != "flop":
        return None

    headers = get_headers()
    if not headers:
        return None

    preflop = PREFLOP_BY_POS.get(position.upper())
    if not preflop:
        return None

    board_str = _norm_board(board)
    if not board_str:
        return None

    snap       = _nearest_snap(hero_stack_bb)
    stack_frac = snap + 0.125

    api_params = {
        "gametype":        GAMETYPE,
        "depth":           stack_frac,
        "stacks":          "",
        "preflop_actions": preflop,
        "flop_actions":    "",
        "turn_actions":    "",
        "river_actions":   "",
        "board":           board_str,
    }

    session = _make_session(headers)
    if session is None:
        log.warning("gto_wizard: requests não instalado")
        return None

    # Resolve flop_actions quando hero enfrenta aposta
    if facing_size_bb > 0:
        hero_is_oop  = position.upper() in OOP_POSITIONS
        flop_before  = "X" if hero_is_oop else ""
        prefix       = "X-R" if hero_is_oop else "R"
        valid_size   = _nearest_valid_bet(session, api_params, flop_before, facing_size_bb)
        if valid_size is not None:
            api_params["flop_actions"] = f"{prefix}{valid_size}"
        else:
            # Fallback: arredonda para 1 casa e tenta direto
            api_params["flop_actions"] = f"{prefix}{round(facing_size_bb, 1)}"

    try:
        r = session.get(GW_SPOT_SOL, params=api_params, timeout=15)
    except Exception as e:
        log.debug("gto_wizard: request exception — %s", e)
        return None

    if r.status_code == 401:
        # Token expirado — marca para re-auth no próximo ciclo
        _set_auth_failed("Token expirado (HTTP 401) — aguardando próximo refresh")
        return None

    if r.status_code == 204 or not r.content:
        log.debug("gto_wizard: 204 no-content — spot não existe no tree (%s %s facing=%.1f)",
                  position, board_str, facing_size_bb)
        return None

    if not r.ok:
        log.debug("gto_wizard: HTTP %d — %s", r.status_code, r.text[:200])
        return None

    try:
        data = r.json()
    except Exception:
        return None

    strategy = _parse_strategy(data)
    if not strategy:
        return None

    log.info("gto_wizard: OK %s %s %.0fbb facing=%.1f → %d ações",
             position, board_str, hero_stack_bb, facing_size_bb, len(strategy))
    return {
        "found":               True,
        "source":              "gtowizard",
        "strategy":            strategy,
        "exploitability_pct":  None,
        "spot_hash":           None,
        "queued":              False,
    }
