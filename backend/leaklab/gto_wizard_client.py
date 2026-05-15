"""
gto_wizard_client.py — Cliente HTTP para o endpoint /gto-wizard do servidor GTO.

O CDP, Chrome e a lógica de auth ficam no servidor (gto_bot/solver_api/server.py).
Este módulo apenas encaminha requisições para lá, exatamente como o solver local.

Variáveis de ambiente:
    GTO_SOLVER_URL      URL base do servidor (ex: http://34.70.251.42:8765)
    GTO_SOLVER_API_KEY  chave de autenticação
    GTO_WIZARD_ENABLED  "true" para habilitar (default: false)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.environ.get("GTO_WIZARD_ENABLED", "").lower() in ("true", "1", "yes")


def _base_url() -> str:
    return os.environ.get("GTO_SOLVER_URL", "").rstrip("/")


def _api_key() -> str:
    return os.environ.get("GTO_SOLVER_API_KEY", "")


def get_status() -> dict:
    """Consulta /gw-status no servidor e retorna o estado da auth."""
    base = _base_url()
    if not base:
        return {"enabled": False, "error": "GTO_SOLVER_URL não configurada"}
    try:
        import requests
        r = requests.get(f"{base}/gw-status",
                         headers={"x-api-key": _api_key()},
                         timeout=5)
        data = r.json()
        data["enabled"] = _enabled()
        return data
    except Exception as e:
        return {"enabled": _enabled(), "auth_ok": False, "error": str(e)}


def start_background_refresher() -> None:
    """No-op — o refresh roda no servidor, não no backend."""
    if _enabled():
        log.info("gto_wizard: cliente HTTP ativo → servidor %s", _base_url())


def query_spot(
    street: str,
    position: str,
    board: list[str],
    hero_stack_bb: float,
    facing_size_bb: float = 0.0,
    pot_bb: float = 0.0,
) -> Optional[dict]:
    """
    Consulta o GTO Wizard via servidor remoto (POST /gto-wizard).

    Retorna None se desabilitado, servidor indisponível ou sem solução.
    Retorna dict no formato de lookup_gto quando encontrado:
    {
        "found": True, "source": "gtowizard",
        "strategy": [{action, frequency, betsize_bb}],
        "exploitability_pct": None,
    }
    """
    if not _enabled():
        return None

    base = _base_url()
    if not base:
        return None

    # Por ora apenas flop
    if street.lower() != "flop":
        return None

    try:
        import requests
        r = requests.post(
            f"{base}/gto-wizard",
            json={
                "street":          street,
                "position":        position,
                "board":           board,
                "hero_stack_bb":   hero_stack_bb,
                "facing_size_bb":  facing_size_bb,
                "pot_bb":          pot_bb,
            },
            headers={"x-api-key": _api_key()},
            timeout=20,
        )
    except Exception as e:
        log.debug("gto_wizard: request falhou — %s", e)
        return None

    if r.status_code == 503:
        log.debug("gto_wizard: auth indisponível no servidor")
        return None

    if not r.ok:
        log.debug("gto_wizard: HTTP %d", r.status_code)
        return None

    try:
        data = r.json()
    except Exception:
        return None

    if not data.get("found"):
        log.debug("gto_wizard: sem solução — %s", data.get("error"))
        return None

    strategy = [
        {
            "action":             s["action"],
            "frequency":          s["frequency"],
            "combos":             None,
            "ev_bb":              None,
            "exploitability_pct": None,
            "betsize_bb":         s.get("betsize_bb"),
        }
        for s in data.get("strategy", [])
    ]

    if not strategy:
        return None

    log.info("gto_wizard: OK %s %.0fbb facing=%.1f → %d ações",
             position, hero_stack_bb, facing_size_bb, len(strategy))
    return {
        "found":               True,
        "source":              "gtowizard",
        "strategy":            strategy,
        "exploitability_pct":  None,
        "spot_hash":           None,
        "queued":              False,
    }
