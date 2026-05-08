"""
parser.py — Converte respostas da API do GTO Wizard em GtoNode.

COMO CONFIGURAR:
1. Rode o bot em modo discovery:
       python -m gto_bot discover
2. Navegue pelo GTO Wizard normalmente por ~10 minutos
3. Abra discovery_log.jsonl e procure as chamadas que contêm frequências de ações
4. Preencha parse_response() abaixo com o formato real encontrado
5. Execute os testes: python -m gto_bot test-parser

Endpoints típicos de solvers GTO (guia de pesquisa):
  - Procure POSTs para /api/v*/solve, /api/v*/strategy, /api/v*/spot
  - Ou GETs para /solutions/* com parâmetros de board/position
  - O response deve conter algo como "fold_freq", "call_freq", "raise_freq"
    ou uma lista "actions": [{"name":"raise","frequency":0.67,"ev":1.2}]
"""
from __future__ import annotations
import json
import logging
from typing import Optional
from .models import GtoNode

log = logging.getLogger(__name__)

# ── URL filter: quais endpoints do GTO Wizard contêm soluções ────────────────
#
# PREENCHER após rodar o modo discovery e identificar o endpoint correto.
# Exemplos comuns (ajustar conforme o que você ver no discovery_log):
#
#   SOLUTION_URL_PATTERNS = ['/api/v1/strategy', '/api/spot', '/solutions']
#
SOLUTION_URL_PATTERNS: list[str] = [
    '/api/',          # placeholder amplo — substitua pelo endpoint real
]


def is_solution_url(url: str) -> bool:
    """Retorna True se a URL parece ser um endpoint de solução GTO."""
    return any(pat in url for pat in SOLUTION_URL_PATTERNS)


def parse_response(url: str, request_body: dict | None, response_body: dict) -> list[GtoNode]:
    """
    Converte um response da API do GTO Wizard em lista de GtoNode.

    ─────────────────────────────────────────────────────────────────
    TODO: PREENCHER APÓS IDENTIFICAR O FORMATO NO discovery_log.jsonl
    ─────────────────────────────────────────────────────────────────

    Exemplos de formatos que solvers costumam retornar:

    FORMATO A — lista de actions:
        {
          "street": "flop",
          "position": "BTN",
          "board": ["Ah","Kd","2c"],
          "hero_range": [{"hand":"AsKs", "actions":[{"name":"raise","freq":0.67,"ev":1.2},...]}]
        }

    FORMATO B — estratégia agregada por posição:
        {
          "spot": {"street":"flop","pos":"BTN","board":"AhKd2c","stack":25},
          "strategy": {"fold":0.1,"call":0.22,"raise":0.68},
          "ev": {"fold":0.0,"call":0.8,"raise":1.2}
        }

    FORMATO C — frequências por hand:
        {
          "hands": [
            {"hand":"AsKs","fold":0.0,"call":0.0,"raise":1.0,"ev_raise":1.8}
          ]
        }
    """

    # ── PLACEHOLDER — substitua esta seção ──────────────────────────────────
    # Quando você encontrar o formato real, remova este bloco e implemente.

    # Tentativa genérica para Formato B
    try:
        spot     = response_body.get('spot') or {}
        strategy = response_body.get('strategy') or {}
        ev_map   = response_body.get('ev') or {}

        if not strategy:
            return []

        street   = (spot.get('street') or response_body.get('street') or '').lower()
        position = (spot.get('pos') or spot.get('position') or response_body.get('position') or '').upper()
        board_raw = spot.get('board') or response_body.get('board') or []
        stack_bb  = float(spot.get('stack') or spot.get('hero_stack_bb') or response_body.get('stack_bb') or 30.0)

        if isinstance(board_raw, str):
            board = [board_raw[i:i+2] for i in range(0, len(board_raw), 2)]
        else:
            board = list(board_raw)

        hero_hand_raw = spot.get('hand') or response_body.get('hero_hand') or []
        if isinstance(hero_hand_raw, str):
            hero_hand = [hero_hand_raw[:2], hero_hand_raw[2:]] if len(hero_hand_raw) == 4 else [hero_hand_raw]
        else:
            hero_hand = list(hero_hand_raw)

        if not street or not position or not hero_hand:
            return []

        # Encontrar ação com maior frequência
        best_action = max(strategy.items(), key=lambda x: x[1])
        action_name = best_action[0].lower()
        action_freq = float(best_action[1])

        # EV diff (melhor - segundo melhor)
        ev_diff = None
        if ev_map and len(ev_map) >= 2:
            sorted_evs = sorted(ev_map.values(), reverse=True)
            if len(sorted_evs) >= 2:
                ev_diff = round(sorted_evs[0] - sorted_evs[1], 3)

        return [GtoNode(
            street=street, position=position, board=board,
            hero_hand=hero_hand, hero_stack_bb=stack_bb,
            gto_action=action_name, gto_freq=action_freq, ev_diff=ev_diff,
        )]

    except Exception as e:
        log.debug('parse_response fallback error: %s', e)
        return []

    # ── FIM DO PLACEHOLDER ───────────────────────────────────────────────────
