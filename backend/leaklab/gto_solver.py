"""
gto_solver.py — Orquestrador GTO: lookup → cache hit ou enfileirar solver.

Fluxo:
  1. Preflop → consulta gto_preflop_ranges por hand_type + posição (cobertura ~90%)
  2. Postflop → consulta gto_nodes por spot_hash (cobertura cresce com uso)
  3. Miss → enfileira spot na gto_solver_queue e retorna status 'queued'
  4. Worker (run_solver_worker) consome a fila, chama solver_cli (Rust) e
     armazena resultado em gto_nodes para futuros lookups

O solver_cli é um binário Rust separado (backend/gto_bot/solver_cli/).
Se o binário não estiver disponível, o worker retorna status 'unavailable'.
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
from typing import Optional

log = logging.getLogger(__name__)

# Caminho para o binário Rust compilado
_SOLVER_BIN = os.path.join(
    os.path.dirname(__file__), '..', 'gto_bot', 'solver_cli', 'target', 'release', 'solver_cli'
)
_SOLVER_AVAILABLE: Optional[bool] = None  # cache da verificação do binário


def _solver_binary() -> Optional[str]:
    """Retorna caminho do binário se existir, None caso contrário."""
    global _SOLVER_AVAILABLE
    if _SOLVER_AVAILABLE is None:
        _SOLVER_AVAILABLE = os.path.isfile(_SOLVER_BIN)
        if not _SOLVER_AVAILABLE:
            log.warning("solver_cli não encontrado em %s — on-demand solve desativado", _SOLVER_BIN)
    return _SOLVER_BIN if _SOLVER_AVAILABLE else None


# ── Lookup principal ───────────────────────────────────────────────────────────

def lookup_gto(
    street: str,
    position: str,
    board: list[str],
    hero_hand: list[str],
    hero_stack_bb: float,
    action_seq: str = 'rfi',
    vs_position: str = '',
) -> dict:
    """
    Ponto de entrada único para consultas GTO.

    Retorna:
    {
      "found":      bool,
      "source":     "preflop_db" | "postflop_db" | "queued" | "unavailable",
      "strategy":   [ {action, frequency, ev_bb}, ... ],   # se found=True
      "spot_hash":  str,
      "queued":     bool,   # True se foi enfileirado para solve
    }
    """
    from leaklab.gto_utils import compute_spot_hash, hand_to_type, stack_bucket
    from database.repositories import (
        get_preflop_gto, get_gto_node, enqueue_solver_spot,
    )

    street_l    = street.lower()
    position_u  = position.upper()
    sb          = stack_bucket(hero_stack_bb)
    hand_type   = hand_to_type(hero_hand)
    spot_hash   = compute_spot_hash(street_l, position_u, board, hero_hand, hero_stack_bb)

    # 1. Preflop → range database
    if street_l == 'preflop' and hand_type:
        rows = get_preflop_gto(
            position=position_u,
            hand_type=hand_type,
            action_seq=action_seq,
            vs_position=vs_position.upper(),
            stack_bucket=sb,
        )
        if rows:
            return {
                'found':     True,
                'source':    'preflop_db',
                'hand_type': hand_type,
                'strategy':  rows,
                'spot_hash': spot_hash,
                'queued':    False,
            }

    # 2. Postflop → gto_nodes (spots já solvidos)
    node = get_gto_node(spot_hash)
    if node:
        return {
            'found':    True,
            'source':   'postflop_db',
            'strategy': [{
                'action':    node['gto_action'],
                'frequency': node['gto_freq'],
                'ev_bb':     node.get('ev_diff'),
            }],
            'spot_hash': spot_hash,
            'queued':    False,
        }

    # 3. Miss — enfileira para solve on-demand
    spot_payload = json.dumps({
        'street':        street_l,
        'position':      position_u,
        'board':         board,
        'hero_hand':     hero_hand,
        'hero_stack_bb': hero_stack_bb,
        'vs_position':   vs_position,
        'action_seq':    action_seq,
    }, sort_keys=True)

    enqueued = enqueue_solver_spot(spot_hash, spot_payload, priority=_priority(street_l))

    return {
        'found':     False,
        'source':    'queued' if enqueued else 'already_queued',
        'strategy':  [],
        'spot_hash': spot_hash,
        'queued':    True,
    }


def _priority(street: str) -> int:
    return {'preflop': 8, 'flop': 6, 'turn': 5, 'river': 4}.get(street, 5)


# ── Worker — consume fila e chama solver Rust ─────────────────────────────────

def run_solver_worker(max_jobs: int = 10) -> int:
    """
    Processa até max_jobs spots da fila. Deve ser chamado por um cron ou endpoint admin.
    Retorna o número de spots solvidos com sucesso.
    """
    from database.repositories import get_next_solver_job, mark_solver_job_done, insert_gto_nodes

    bin_path = _solver_binary()
    if not bin_path:
        log.warning("Solver binário indisponível — worker abortado")
        return 0

    solved = 0
    for _ in range(max_jobs):
        job = get_next_solver_job()
        if not job:
            break

        spot_hash = job['spot_hash']
        spot      = json.loads(job['spot_json'])

        try:
            result = _call_solver(bin_path, spot)
            if result:
                insert_gto_nodes([{
                    'street':        spot['street'],
                    'position':      spot['position'],
                    'board':         spot.get('board', []),
                    'hero_hand':     spot.get('hero_hand', []),
                    'hero_stack_bb': spot.get('hero_stack_bb', 30.0),
                    'gto_action':    result['primary_action'],
                    'gto_freq':      result['primary_freq'],
                    'ev_diff':       result.get('ev'),
                    'source':        'solver_cli',
                }])
                mark_solver_job_done(spot_hash, 'done')
                solved += 1
                log.info("Solved %s → %s %.0f%%", spot_hash, result['primary_action'], result['primary_freq'] * 100)
            else:
                mark_solver_job_done(spot_hash, 'failed')
        except Exception as e:
            log.exception("Solver error for %s: %s", spot_hash, e)
            mark_solver_job_done(spot_hash, 'failed')

    return solved


def _call_solver(bin_path: str, spot: dict, timeout: int = 120) -> Optional[dict]:
    """
    Chama o binário solver_cli com o spot em JSON via stdin.
    Espera JSON de resposta em stdout.

    Formato de saída esperado do solver_cli:
    {
      "primary_action": "bet",
      "primary_freq":   0.72,
      "ev":             1.43,
      "strategy": {
        "bet_75":  0.72,
        "check":   0.18,
        "bet_125": 0.10
      },
      "exploitability": 0.8
    }
    """
    try:
        proc = subprocess.run(
            [bin_path],
            input=json.dumps(spot),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            log.error("solver_cli stderr: %s", proc.stderr[:500])
            return None
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        log.error("solver_cli timeout após %ds para spot %s", timeout, spot.get('street'))
        return None
    except json.JSONDecodeError as e:
        log.error("solver_cli output inválido: %s", e)
        return None
