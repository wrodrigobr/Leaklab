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
    num_players: int = 9,
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
                "num_players":     num_players,
            },
            headers={"x-api-key": _api_key()},
            timeout=20,
        )
    except Exception as e:
        log.debug("gto_wizard: request falhou — %s", e)
        return None

    if r.status_code == 503:
        log.info("gto_wizard: auth indisponível no servidor (503)")
        return None

    if not r.ok:
        log.info("gto_wizard: HTTP %d — %s", r.status_code, r.text[:200])
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


# ── Raw passthrough (multiway / squeeze / cold-callers) ───────────────────────

def _normalize_gw_action(code: str, action_type: str = "") -> tuple[str, float | None]:
    """
    Normaliza action code do GW pro vocabulário do engine.

    Retorna (action_name, betsize_bb).
    Tipo de ação tem precedência sobre prefixo do code quando disponível.
    """
    code = (code or "").strip()
    t = (action_type or "").upper()
    if t in ("FOLD",):
        return "fold", None
    if t in ("CHECK",):
        return "check", None
    if t in ("CALL",):
        return "call", None
    if t in ("ALLIN", "ALL_IN") or code.upper() == "RAI":
        return "allin", None
    if t in ("RAISE", "BET"):
        try:
            sz = float(code.lstrip("Rr").lstrip("Bb")) if code else None
        except (ValueError, TypeError):
            sz = None
        return ("raise" if t == "RAISE" else "bet"), sz
    # Sem tipo conhecido: fallback pelo prefixo
    if code == "F":  return "fold",  None
    if code == "C":  return "call",  None
    if code == "X":  return "check", None
    if code.upper() == "RAI": return "allin", None
    if code.startswith("R"):
        try: return "raise", float(code[1:])
        except ValueError: return "raise", None
    if code.startswith("B"):
        try: return "bet", float(code[1:])
        except ValueError: return "bet", None
    return code.lower(), None


def _cache_key_for_spot(
    gametype: str,
    depth_bb: float,
    preflop_actions: str,
    flop_actions: str = "",
    turn_actions: str = "",
    river_actions: str = "",
    board: str = "",
) -> str:
    """Chave deterministica para cache de /gw-spot — independe do hero_hand
    (response cobre todos os 169 hand_types via hero_hand_freqs)."""
    import hashlib
    raw = "|".join([
        gametype or "",
        f"{float(depth_bb):.3f}",
        preflop_actions or "",
        flop_actions or "",
        turn_actions or "",
        river_actions or "",
        (board or "").replace(" ", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def query_spot_raw(
    preflop_actions: str,
    num_players: int,
    depth_bb: float,
    *,
    flop_actions: str = "",
    turn_actions: str = "",
    river_actions: str = "",
    board: str | list[str] = "",
    stacks_bb: list[float] | None = None,
    gametype: str | None = None,
    include_strategy: bool = False,
    timeout: int = 45,
    use_cache: bool = True,
    cache_only: bool = False,
) -> Optional[dict]:
    """
    Consulta GW via servidor remoto `POST /gw-spot` — suporta qualquer cenário
    (multiway, squeeze, cold-callers) desde que `preflop_actions` esteja
    encoded no formato GW (ex: "R2.1-F-F-C-F-C-R11.55").

    Retorna None se desabilitado, servidor indisponível ou sem solução.

    Em sucesso, retorna dict:
    {
      "found":            True,
      "source":           "gtowizard_raw",
      "hero_position":    str | None,
      "strategy":         [{action, frequency, betsize_bb, code, total_combos}],
      "hand_freqs":       { hand_type: {action: frequency, ...} },  # action normalizado
      "raw_hand_freqs":   { hand_type: {code: frequency, ...} },    # codes brutos do GW
      "spot":             { gametype, depth_used, stacks, preflop_actions },
    }
    """
    if not _enabled():
        return None
    base = _base_url()
    if not base:
        return None

    # Cache lookup (transparente). Chave baseada em gametype/depth/actions/board —
    # NAO inclui hero_hand pois response cobre todos os 169 hand_types.
    effective_gametype = gametype
    if not effective_gametype:
        # Reproduz mapping do server (_TABLE_CONFIG) — fallback se omitido.
        _gt_map = {2:"MTTHUGeneral",3:"MTTGeneral_3m",4:"MTTGeneral_4m",
                   5:"MTTGeneral_5m",6:"MTT6mSimple",7:"MTTGeneral_7m",
                   8:"MTTGeneral_8m",9:"MTTGeneralV2"}
        effective_gametype = _gt_map.get(int(num_players), "")

    # Board string normalizada pra chave de cache
    board_str = board if isinstance(board, str) else ("".join(board) if board else "")

    cache_key = _cache_key_for_spot(
        gametype=effective_gametype,
        depth_bb=depth_bb,
        preflop_actions=preflop_actions or "",
        flop_actions=flop_actions or "",
        turn_actions=turn_actions or "",
        river_actions=river_actions or "",
        board=board_str,
    )

    if use_cache:
        try:
            from database.repositories import get_gw_raw_cache
            cached = get_gw_raw_cache(cache_key)
            if cached:
                log.info("gw-spot: cache HIT key=%s gametype=%s", cache_key, effective_gametype)
                return cached["payload"]
        except Exception as e:
            log.debug("gw-spot: cache lookup falhou — %s", e)

    # cache_only: no cache miss, retorna None imediatamente (sem chamar server).
    # Util pra hot paths como /replay onde nao podemos bloquear 30s no GW.
    if cache_only:
        return None

    payload = {
        "num_players":     int(num_players),
        "depth_bb":        float(depth_bb),
        "preflop_actions": preflop_actions or "",
        "flop_actions":    flop_actions or "",
        "turn_actions":    turn_actions or "",
        "river_actions":   river_actions or "",
        "board":           board or "",
        "include_strategy":   bool(include_strategy),
        "include_hand_freqs": True,
    }
    if stacks_bb is not None:
        payload["stacks_bb"] = list(stacks_bb)
    if gametype:
        payload["gametype"] = gametype

    try:
        import requests
        r = requests.post(
            f"{base}/gw-spot",
            json=payload,
            headers={"x-api-key": _api_key()},
            timeout=timeout,
        )
    except Exception as e:
        log.debug("gw-spot: request falhou — %s", e)
        return None

    if r.status_code == 503:
        log.info("gw-spot: auth indisponível no servidor (503)")
        return None
    if r.status_code == 401:
        log.info("gw-spot: token GW expirado (401)")
        return None
    if not r.ok:
        log.info("gw-spot: HTTP %d — %s", r.status_code, r.text[:200])
        return None

    try:
        data = r.json()
    except Exception:
        return None
    if not data.get("found"):
        log.debug("gw-spot: sem solução — %s", data.get("error"))
        return None

    # Normaliza strategy do action_solutions
    strategy_out = []
    for entry in data.get("action_solutions") or []:
        act    = entry.get("action") or {}
        code   = act.get("code") or ""
        atype  = act.get("type") or ""
        name, betsize = _normalize_gw_action(code, atype)
        strategy_out.append({
            "action":             name,
            "code":               code,
            "frequency":          round(float(entry.get("total_frequency") or 0), 4),
            "betsize_bb":         betsize,
            "total_combos":       entry.get("total_combos"),
        })

    # Normaliza hand_freqs: codes crus → ações normalizadas
    raw_hf = data.get("hero_hand_freqs") or {}
    hand_freqs: dict[str, dict[str, float]] = {}
    for hand_name, freqs in raw_hf.items():
        norm: dict[str, float] = {}
        for code, freq in freqs.items():
            name, _ = _normalize_gw_action(code)
            norm[name] = round(norm.get(name, 0.0) + float(freq), 4)
        hand_freqs[hand_name] = norm

    spot_info = {
        "gametype":        data.get("gametype"),
        "depth_used":      data.get("depth_used"),
        "stacks":          data.get("stacks"),
        "preflop_actions": (data.get("params") or {}).get("preflop_actions"),
    }
    log.info("gw-spot: OK hero=%s %d acoes hands=%d gametype=%s",
             data.get("hero_position"), len(strategy_out),
             len(hand_freqs), data.get("gametype"))

    result = {
        "found":          True,
        "source":         "gtowizard_raw",
        "hero_position":  data.get("hero_position"),
        "strategy":       strategy_out,
        "hand_freqs":     hand_freqs,
        "raw_hand_freqs": raw_hf,
        "spot":           spot_info,
    }

    # Cache write (best-effort). Usa preflop_actions FINAL (pos-snap se houver).
    if use_cache:
        try:
            from database.repositories import upsert_gw_raw_cache
            final_pf = (spot_info or {}).get("preflop_actions") or preflop_actions or ""
            final_gametype = (spot_info or {}).get("gametype") or effective_gametype
            final_depth    = (spot_info or {}).get("depth_used") or float(depth_bb)
            final_key = _cache_key_for_spot(
                gametype=final_gametype, depth_bb=final_depth,
                preflop_actions=final_pf,
                flop_actions=flop_actions or "", turn_actions=turn_actions or "",
                river_actions=river_actions or "", board=board_str,
            )
            upsert_gw_raw_cache(
                cache_key=final_key,
                gametype=final_gametype,
                depth_used=final_depth,
                preflop_actions=final_pf,
                hero_position=result.get("hero_position"),
                payload=result,
            )
            # Tambem cacheia sob a chave ORIGINAL (preflop_actions pre-snap)
            # — proximas chamadas com mesmos sizings imperfeitos batem cache direto.
            if final_key != cache_key:
                upsert_gw_raw_cache(
                    cache_key=cache_key,
                    gametype=final_gametype,
                    depth_used=final_depth,
                    preflop_actions=preflop_actions or "",
                    hero_position=result.get("hero_position"),
                    payload=result,
                )
        except Exception as e:
            log.debug("gw-spot: cache write falhou — %s", e)

    return result


# ── Convenience: lookup direto a partir de ParsedHand + decision index ────────

def lookup_for_hand_decision(
    hand,                # ParsedHand
    decision_index: int, # index em hand.actions onde o hero decide
    *,
    depth_bb: float | None = None,
    timeout: int = 60,
    use_cache: bool = True,
    cache_only: bool = False,
) -> Optional[dict]:
    """
    Wrapper: encoder + classifier + query_spot_raw (com cache).

    Retorna o mesmo dict de query_spot_raw, OU None se:
      - GTO Wizard desabilitado
      - encoder nao consegue gerar preflop_actions (decisao nao preflop)
      - num_players nao suportado pelo GW
      - chamada GW falhou

    Adiciona `scenario` ao dict (do classify_multiway).
    """
    if not _enabled():
        return None
    try:
        from leaklab.gw_action_encoder import (
            encode_preflop_actions, num_seated_players, gw_gametype_for,
            classify_multiway,
        )
    except Exception:
        return None

    n_players = num_seated_players(hand)
    gametype  = gw_gametype_for(n_players)
    if not gametype:
        return None

    try:
        pf = encode_preflop_actions(hand, decision_index)
    except Exception:
        return None

    # Depth: tenta stack inicial do hero (em bb); fallback 100bb
    if depth_bb is None:
        try:
            from leaklab.hand_state_builder import _effective_stack as _es
            depth_bb = _es(hand, hand.hero, [a for a in hand.actions[:decision_index]])
        except Exception:
            depth_bb = 100.0
    if depth_bb is None or depth_bb <= 0:
        depth_bb = 100.0

    classify = classify_multiway(pf)
    result = query_spot_raw(
        preflop_actions=pf, num_players=n_players, depth_bb=float(depth_bb),
        gametype=gametype, timeout=timeout, use_cache=use_cache,
        cache_only=cache_only,
    )
    if result:
        result["scenario"] = classify.get("scenario")
    return result
