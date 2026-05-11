"""
gto_solver.py — Orquestrador GTO: lookup → solver verificado → cache.

Garantia de qualidade:
  - Nenhum dado entra no banco sem exploitability_pct medida pelo solver
  - Threshold: exploitability_pct <= 1.0% do pot (configurável em repositories.py)
  - Solves que não convergem são descartados e recolocados na fila com mais iterações

Fluxo:
  1. Preflop → gto_preflop_ranges (só rows com exploitability confirmada)
  2. Postflop → gto_nodes (só rows com exploitability confirmada)
  3. Miss → tenta solver remoto (Oracle Cloud) → fallback local → enfileira
  4. Worker chama solver_cli (Rust CFR) → armazena com exploitability real
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
from typing import Optional

# ── Solver remoto (Oracle Cloud) ──────────────────────────────────────────────
# Lidas em runtime (não no import) para garantir que o .env já foi carregado
def _remote_url() -> str:
    return os.environ.get('GTO_SOLVER_URL', '').rstrip('/')

def _remote_key() -> str:
    return os.environ.get('GTO_SOLVER_API_KEY', '')

# Ranges padrão por posição (6-max, 100bb, RFI / call). Simplificadas para convergência rápida.
_DEFAULT_RANGES: dict[str, str] = {
    'BTN': '22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,54s,A2o+,K8o+,Q9o+,J9o+,T9o',
    'CO':  '22+,A2s+,K6s+,Q8s+,J8s+,T8s+,98s,87s,76s,A4o+,K9o+,Q9o+,J9o+',
    'HJ':  '44+,A2s+,K9s+,Q9s+,J9s+,T9s,A9o+,KTo+,QTo+,JTo',
    'UTG': '55+,A9s+,KTs+,QTs+,JTs,AJo+,KQo',
    'SB':  '22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,A2o+,K7o+,Q9o+',
    'BB':  '22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K4o+,Q7o+,J8o+,T8o+',
}
_DEFAULT_RANGE_WIDE = '22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K8o+,Q9o+,J9o+'

log = logging.getLogger(__name__)

_SOLVER_BIN = os.environ.get(
    'GTO_SOLVER_BIN',
    os.path.join(
        os.path.dirname(__file__), '..', 'gto_bot', 'solver_cli', 'target', 'release',
        'solver_cli.exe' if os.name == 'nt' else 'solver_cli',
    )
)
_SOLVER_AVAILABLE: Optional[bool] = None

# Threshold: exploitability acima deste valor → solve rejeitado e recolocado na fila
MAX_EXPLOITABILITY_PCT = 1.0
# Se o solve não convergiu, rodar com este fator de iterações a mais
RETRY_ITERATION_FACTOR = 3


def _solver_binary() -> Optional[str]:
    global _SOLVER_AVAILABLE
    if _SOLVER_AVAILABLE is None:
        _SOLVER_AVAILABLE = os.path.isfile(_SOLVER_BIN)
        if not _SOLVER_AVAILABLE:
            log.warning("solver_cli não encontrado em %s — on-demand solve indisponível", _SOLVER_BIN)
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
    facing_size_bb: float = 0.0,
    pot_bb: float = 0.0,
) -> dict:
    """
    Ponto de entrada único para consultas GTO.

    Retorna apenas dados com exploitability_pct garantida pelo solver.

    {
      "found":               bool,
      "source":              "postflop_db" | "queued" | "solver_unavailable",
      "strategy":            [{action, frequency, ev_bb, exploitability_pct}],
      "exploitability_pct":  float | None,
      "spot_hash":           str,
      "queued":              bool,
    }
    """
    from leaklab.gto_utils import compute_spot_hash, hand_to_type, stack_bucket
    from database.repositories import (
        get_preflop_gto, get_gto_node, enqueue_solver_spot, insert_gto_nodes,
    )

    street_l   = street.lower()
    position_u = position.upper()
    sb         = stack_bucket(hero_stack_bb)
    hand_type  = hand_to_type(hero_hand)
    spot_hash  = compute_spot_hash(street_l, position_u, board, hero_hand, hero_stack_bb, facing_size_bb)

    # 1. Preflop — só retorna se houver dados verificados
    if street_l == 'preflop' and hand_type:
        rows = get_preflop_gto(
            position=position_u,
            hand_type=hand_type,
            action_seq=action_seq,
            vs_position=vs_position.upper(),
            stack_bucket=sb,
        )
        if rows:
            top_exploit = min(r.get('exploitability_pct') or 99 for r in rows)
            return {
                'found':              True,
                'source':             'preflop_db',
                'hand_type':          hand_type,
                'strategy':           rows,
                'exploitability_pct': top_exploit,
                'spot_hash':          spot_hash,
                'queued':             False,
            }

    # 2. Postflop — gto_nodes verificados
    node = get_gto_node(spot_hash)
    if node:
        return {
            'found':    True,
            'source':   'postflop_db',
            'strategy': [{
                'action':              node['gto_action'],
                'frequency':           node['gto_freq'],
                'ev_bb':               node.get('ev_diff'),
                'exploitability_pct':  node.get('exploitability_pct'),
            }],
            'exploitability_pct': node.get('exploitability_pct'),
            'spot_hash':          spot_hash,
            'queued':             False,
        }

    # 3. Miss — tenta solver remoto primeiro
    # Monta payload no formato que o solver_cli Rust espera
    oop_range = _DEFAULT_RANGES.get(vs_position.upper(), _DEFAULT_RANGE_WIDE)
    ip_range  = _DEFAULT_RANGES.get(position_u, _DEFAULT_RANGE_WIDE)
    effective_pot = pot_bb if pot_bb > 0 else max(facing_size_bb * 2 + 2, 4.0)

    solver_payload = {
        'street':                    street_l,
        'board':                     board,
        'oop_range':                 oop_range,
        'ip_range':                  ip_range,
        'pot_bb':                    effective_pot,
        'effective_stack_bb':        hero_stack_bb,
        'target_exploitability_pct': MAX_EXPLOITABILITY_PCT,
    }

    # Metadados extras para armazenar no DB após o solve
    spot_dict = {
        **solver_payload,
        'position':       position_u,
        'hero_hand':      hero_hand,
        'vs_position':    vs_position,
        'action_seq':     action_seq,
        'facing_size_bb': facing_size_bb,
    }
    spot_payload = json.dumps(spot_dict, sort_keys=True)

    remote = _call_remote_solver(solver_payload)
    if remote:
        exploit = remote.get('exploitability_pct')
        # Normalize strategy: Oracle returns dict {action: freq}, worker expects list of dicts
        strategy_raw = remote.get('strategy')
        if isinstance(strategy_raw, dict):
            strategy_list = [
                {'action': k, 'frequency': v, 'ev_bb': None, 'exploitability_pct': exploit}
                for k, v in strategy_raw.items()
            ]
        elif isinstance(strategy_raw, list):
            strategy_list = strategy_raw
        else:
            strategy_list = [{
                'action':             remote['primary_action'],
                'frequency':          remote['primary_freq'],
                'ev_bb':              remote.get('ev'),
                'exploitability_pct': exploit,
            }]
        insert_gto_nodes([{
            'street':             street_l,
            'position':           position_u,
            'board':              board,
            'hero_hand':          hero_hand,
            'hero_stack_bb':      hero_stack_bb,
            'gto_action':         remote['primary_action'],
            'gto_freq':           remote['primary_freq'],
            'ev_diff':            remote.get('ev'),
            'exploitability_pct': float(exploit) if exploit else None,
            'iterations':         remote.get('iterations'),
        }])
        log.info("GTO remote solve: %s → %s %.0f%% (exploit=%.2f%%)",
                 spot_hash, remote['primary_action'],
                 remote['primary_freq'] * 100, exploit or 0)
        return {
            'found':              True,
            'source':             'remote_solver',
            'strategy':           strategy_list,
            'exploitability_pct': float(exploit) if exploit else None,
            'spot_hash':          spot_hash,
            'queued':             False,
        }

    # 4. Fallback — enfileira para solve local
    bin_path = _solver_binary()
    enqueued = enqueue_solver_spot(spot_hash, spot_payload, priority=_priority(street_l))

    return {
        'found':              False,
        'source':             'queued' if bin_path else 'solver_unavailable',
        'strategy':           [],
        'exploitability_pct': None,
        'spot_hash':          spot_hash,
        'queued':             enqueued or True,
    }


def _priority(street: str) -> int:
    return {'preflop': 8, 'flop': 6, 'turn': 5, 'river': 4}.get(street, 5)


def _call_remote_solver(spot: dict, timeout: int = 300) -> Optional[dict]:
    """Chama o solver remoto (Oracle Cloud). Retorna resultado ou None em caso de falha."""
    url = _remote_url()
    key = _remote_key()
    if not url or not key:
        return None
    try:
        import requests
        resp = requests.post(
            f"{url}/solve",
            json=spot,
            headers={"x-api-key": key},
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json()
        log.warning("Remote solver HTTP %d: %s", resp.status_code, resp.text[:200])
        return None
    except Exception as e:
        log.warning("Remote solver indisponível: %s", e)
        return None


# ── Worker — consume fila, valida exploitability ──────────────────────────────

def run_solver_worker(max_jobs: int = 10) -> dict:
    """
    Processa até max_jobs spots da fila.
    Só armazena solves com exploitability <= MAX_EXPLOITABILITY_PCT.

    Retorna {solved, rejected, failed}
    """
    from database.repositories import get_next_solver_job, mark_solver_job_done, insert_gto_nodes

    bin_path = _solver_binary()
    if not bin_path:
        return {'solved': 0, 'rejected': 0, 'failed': 0, 'error': 'solver_unavailable'}

    solved = rejected = failed = 0

    for _ in range(max_jobs):
        job = get_next_solver_job()
        if not job:
            break

        spot_hash = job['spot_hash']
        spot      = json.loads(job['spot_json'])

        try:
            result = _call_solver(bin_path, spot)

            if not result:
                mark_solver_job_done(spot_hash, 'failed')
                failed += 1
                continue

            exploit = result.get('exploitability')
            if exploit is None or float(exploit) > MAX_EXPLOITABILITY_PCT:
                # Solve não convergiu — aumenta iterações e recoloca na fila
                log.warning(
                    "Spot %s exploitability=%.2f%% > threshold %.1f%% — recolocando na fila",
                    spot_hash, exploit or 999, MAX_EXPLOITABILITY_PCT
                )
                _requeue_with_more_iterations(spot_hash, spot)
                mark_solver_job_done(spot_hash, 'requeued')
                rejected += 1
                continue

            inserted = insert_gto_nodes([{
                'street':            spot['street'],
                'position':          spot['position'],
                'board':             spot.get('board', []),
                'hero_hand':         spot.get('hero_hand', []),
                'hero_stack_bb':     spot.get('hero_stack_bb', 30.0),
                'gto_action':        result['primary_action'],
                'gto_freq':          result['primary_freq'],
                'ev_diff':           result.get('ev'),
                'exploitability_pct': float(exploit),
                'iterations':        result.get('iterations'),
            }])

            if inserted:
                mark_solver_job_done(spot_hash, 'done')
                solved += 1
                log.info(
                    "GTO verified: %s → %s %.0f%% (exploit=%.2f%%)",
                    spot_hash, result['primary_action'],
                    result['primary_freq'] * 100, exploit
                )
            else:
                # insert_gto_nodes retornou 0 — exploitability rejeitada internamente
                mark_solver_job_done(spot_hash, 'rejected')
                rejected += 1

        except Exception as e:
            log.exception("Solver error for %s: %s", spot_hash, e)
            mark_solver_job_done(spot_hash, 'failed')
            failed += 1

    return {'solved': solved, 'rejected': rejected, 'failed': failed}


def _requeue_with_more_iterations(spot_hash: str, spot: dict) -> None:
    """Recoloca spot na fila com mais iterações para forçar convergência."""
    from database.repositories import enqueue_solver_spot
    current = spot.get('max_iterations', 1000)
    spot_augmented = {**spot, 'max_iterations': current * RETRY_ITERATION_FACTOR}
    enqueue_solver_spot(
        spot_hash + '_retry',
        json.dumps(spot_augmented, sort_keys=True),
        priority=_priority(spot.get('street', 'flop')) + 1,
    )


def _call_solver(bin_path: str, spot: dict, timeout: int = 300) -> Optional[dict]:
    """
    Chama solver_cli com spot JSON via stdin. Retorna dict com resultado ou None.
    """
    # CREATE_BREAKAWAY_FROM_JOB: libera o processo do Job Object do Python no Windows,
    # permitindo que Rayon crie threads sem restrições (sem isso: ~10x mais lento).
    _BREAKAWAY = 0x01000000 if os.name == 'nt' else 0
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', suffix='.json', delete=False
        ) as f:
            f.write(json.dumps(spot))
            tmp_path = f.name
        try:
            with open(tmp_path, 'r', encoding='utf-8') as stdin_f:
                proc = subprocess.run(
                    [bin_path],
                    stdin=stdin_f,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=timeout,
                    creationflags=_BREAKAWAY,
                )
        finally:
            os.unlink(tmp_path)
        if proc.returncode != 0:
            log.error("solver_cli exit=%d stderr: %s", proc.returncode, proc.stderr[:500])
            return None
        result = json.loads(proc.stdout)
        # Normaliza nome do campo exploitability (solver retorna 'exploitability')
        if 'exploitability' not in result and 'exploitability_pct' in result:
            result['exploitability'] = result['exploitability_pct']
        return result
    except subprocess.TimeoutExpired:
        log.error("solver_cli timeout após %ds", timeout)
        return None
    except json.JSONDecodeError as e:
        log.error("solver_cli output inválido: %s", e)
        return None
