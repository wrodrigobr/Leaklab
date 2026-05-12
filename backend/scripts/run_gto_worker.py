"""
run_gto_worker.py — Worker contínuo: drena gto_solver_queue usando o solver remoto (Google Cloud).

Uso:
    python scripts/run_gto_worker.py [--poll 30] [--timeout 300] [--enqueue] [--limit 0]

Flags:
    --poll N      Intervalo entre polls quando a fila está vazia (segundos). Padrão: 30
    --timeout N   Timeout por chamada ao solver remoto (segundos). Padrão: 300
    --enqueue     Antes de iniciar, enfileira spots postflop sem solução do banco local
    --limit N     Para após N spots resolvidos. 0 = rodar para sempre. Padrão: 0

Variáveis de ambiente necessárias (.env ou ambiente):
    GTO_SOLVER_URL      URL base do solver remoto (ex: http://34.x.x.x:8080)
    GTO_SOLVER_API_KEY  Chave x-api-key para o solver remoto
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

# ── Setup de paths ─────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gto-worker")

# ── Importações do projeto ─────────────────────────────────────────────────────
from database.repositories import (
    get_next_solver_job,
    mark_solver_job_done,
    insert_gto_nodes,
    enqueue_solver_spot,
    get_conn,
    _fetchall,
    _adapt,
)
from leaklab.gto_solver import _call_remote_solver

# ── Globals ────────────────────────────────────────────────────────────────────
_running = True


def _handle_sigint(sig, frame):
    global _running
    log.info("Interrompido — aguardando job atual terminar...")
    _running = False


signal.signal(signal.SIGINT, _handle_sigint)
signal.signal(signal.SIGTERM, _handle_sigint)


# ── Auto-enqueue a partir do banco local ───────────────────────────────────────

_DEFAULT_RANGES = {
    "BTN": "22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,54s,A2o+,K8o+,Q9o+,J9o+,T9o",
    "CO":  "22+,A2s+,K6s+,Q8s+,J8s+,T8s+,98s,87s,76s,A4o+,K9o+,Q9o+,J9o+",
    "HJ":  "44+,A2s+,K9s+,Q9s+,J9s+,T9s,A9o+,KTo+,QTo+,JTo",
    "UTG": "55+,A9s+,KTs+,QTs+,JTs,AJo+,KQo",
    "SB":  "22+,A2s+,K2s+,Q4s+,J6s+,T7s+,97s+,87s,76s,65s,A2o+,K7o+,Q9o+",
    "BB":  "22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K4o+,Q7o+,J8o+,T8o+",
}
_RANGE_WIDE = "22+,A2s+,K2s+,Q2s+,J4s+,T6s+,96s+,86s+,75s+,65s,54s,A2o+,K8o+,Q9o+,J9o+"

_PRIORITY = {"flop": 6, "turn": 5, "river": 4}
_STACK_PARAMS = [
    (15, {"effective_stack_bb": 12, "max_iterations": 100, "target_exploitability_pct": 5.0}),
    (25, {"effective_stack_bb": 20, "max_iterations": 200, "target_exploitability_pct": 3.0}),
    (50, {"effective_stack_bb": 40, "max_iterations": 400, "target_exploitability_pct": 2.5}),
    (9999, {"effective_stack_bb": 75, "max_iterations": 600, "target_exploitability_pct": 2.0}),
]


def _solver_params(stack: float) -> dict:
    for cap, p in _STACK_PARAMS:
        if stack <= cap:
            return p
    return _STACK_PARAMS[-1][1]


def enqueue_from_db(max_spots: int = 5000) -> int:
    """
    Varre decisions no banco local e enfileira spots postflop que ainda não
    têm solução em gto_nodes nem estão na fila.
    Retorna o número de spots enfileirados.
    """
    from leaklab.gto_utils import compute_spot_hash
    from database.repositories import get_gto_node

    conn = get_conn()
    try:
        rows = _fetchall(conn, _adapt("""
            SELECT d.id, d.street, d.board, d.hero_cards, d.position,
                   d.stack_bb, d.facing_bet, d.pot_size, d.is_3bet
            FROM decisions d
            WHERE d.street IN ('flop','turn','river')
            ORDER BY d.id DESC
            LIMIT ?
        """), (max_spots,))
    finally:
        conn.close()

    enqueued = already = skipped = 0
    for row in rows:
        try:
            street = row['street']
            board_raw = row['board'] or '[]'
            board = json.loads(board_raw) if board_raw.startswith('[') else [board_raw[i:i+2] for i in range(0, len(board_raw), 2)]
            hc_raw = row['hero_cards'] or ''
            hero_h = json.loads(hc_raw) if hc_raw.startswith('[') else [hc_raw[i:i+2] for i in range(0, len(hc_raw), 2) if hc_raw[i:i+2]]
            pos    = (row['position'] or 'BTN').upper()
            stack  = float(row['stack_bb'] or 20)
            facing = float(row['facing_bet'] or 0)
            pot_bb = float(row['pot_size'] or max(facing * 2 + 2, 2.0))

            # Deduz posição do villão: is_3bet=True → provavelmente BTN vs BB, senão BB
            vs_pos = 'BTN' if row['is_3bet'] else 'BB'

            spot_hash = compute_spot_hash(street, pos, board, hero_h, stack, facing)
            if get_gto_node(spot_hash):
                already += 1
                continue

            params  = _solver_params(stack)
            payload = json.dumps({
                'street':                    street,
                'board':                     board,
                'position':                  pos,
                'hero_hand':                 hero_h,
                'hero_stack_bb':             stack,
                'facing_size_bb':            facing,
                'oop_range':                 _DEFAULT_RANGES.get(vs_pos, _RANGE_WIDE),
                'ip_range':                  _DEFAULT_RANGES.get(pos, _RANGE_WIDE),
                'pot_bb':                    pot_bb,
                'effective_stack_bb':        params['effective_stack_bb'],
                'max_iterations':            params['max_iterations'],
                'target_exploitability_pct': params['target_exploitability_pct'],
                '_meta': {
                    'position': pos, 'vs_position': vs_pos,
                    'hero_hand': hero_h, 'hero_stack_bb': stack,
                    'facing_size_bb': facing, 'street': street, 'board': board,
                },
            }, sort_keys=True)

            if enqueue_solver_spot(spot_hash, payload, priority=_PRIORITY.get(street, 5)):
                enqueued += 1
        except Exception as e:
            log.debug("enqueue_from_db skip row %s: %s", row.get('id'), e)
            skipped += 1

    log.info("Auto-enqueue: %d enfileirados, %d ja resolvidos, %d ignorados", enqueued, already, skipped)
    return enqueued


# ── Reset de stale jobs ────────────────────────────────────────────────────────

def reset_stale_jobs() -> None:
    """Reseta jobs em 'running' há mais de 10 minutos (crash/restart)."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE gto_solver_queue SET status='pending' "
            "WHERE status='running' AND requested_at < datetime('now', '-10 minutes')"
        )
        if cur.rowcount:
            log.info("Resetados %d jobs stale", cur.rowcount)
        conn.commit()
    finally:
        conn.close()


# ── Stats da fila ──────────────────────────────────────────────────────────────

def queue_stats() -> dict:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM gto_solver_queue GROUP BY status"
        ).fetchall()
        return {r[0]: r[1] for r in rows}
    finally:
        conn.close()


# ── Processar um job ───────────────────────────────────────────────────────────

def process_job(job: dict, timeout: int) -> str:
    """
    Chama o solver remoto para um job.
    Retorna: 'solved' | 'rejected' | 'failed'
    """
    spot_hash = job['spot_hash']
    spot      = json.loads(job['spot_json'])

    result = _call_remote_solver(spot, timeout=timeout)
    if not result:
        mark_solver_job_done(spot_hash, 'failed')
        return 'failed'

    exploit = result.get('exploitability') or result.get('exploitability_pct')
    if exploit is None:
        log.warning("Spot %s sem exploitability — descartando", spot_hash)
        mark_solver_job_done(spot_hash, 'failed')
        return 'failed'

    exploit = float(exploit)
    # Threshold mais permissivo para o solver remoto (que é mais preciso)
    if exploit > 15.0:
        log.warning("Spot %s exploitability=%.2f%% > 15%% — descartando", spot_hash, exploit)
        mark_solver_job_done(spot_hash, 'failed')
        return 'failed'

    meta     = spot.get('_meta', {})
    position = spot.get('position') or meta.get('position', '')
    facing   = spot.get('facing_size_bb') or meta.get('facing_size_bb', 0.0)
    hero_h   = spot.get('hero_hand') or meta.get('hero_hand', [])
    hero_stk = spot.get('hero_stack_bb') or meta.get('hero_stack_bb', 30.0)

    inserted = insert_gto_nodes([{
        'spot_hash':          spot_hash,
        'street':             spot['street'],
        'position':           position,
        'board':              spot.get('board', []),
        'hero_hand':          hero_h,
        'hero_stack_bb':      hero_stk,
        'facing_size_bb':     facing,
        'gto_action':         result['primary_action'],
        'gto_freq':           result['primary_freq'],
        'ev_diff':            result.get('ev'),
        'exploitability_pct': exploit,
        'iterations':         result.get('iterations'),
        'strategy_detail':    result.get('strategy_detail'),
    }])

    if inserted:
        mark_solver_job_done(spot_hash, 'done')
        log.info(
            "Solved %s -> %s %.0f%% (exploit=%.2f%%)",
            spot_hash, result['primary_action'], result['primary_freq'] * 100, exploit,
        )
        return 'solved'
    else:
        mark_solver_job_done(spot_hash, 'rejected')
        log.info("Rejected %s (exploit=%.2f%% > threshold)", spot_hash, exploit)
        return 'rejected'


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="GTO remote solver worker")
    parser.add_argument("--poll",    type=int, default=30,  help="Segundos entre polls quando fila vazia")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout por job (segundos)")
    parser.add_argument("--enqueue", action="store_true",   help="Auto-enfileirar decisions existentes antes de iniciar")
    parser.add_argument("--limit",   type=int, default=0,   help="Parar apos N spots resolvidos (0 = infinito)")
    args = parser.parse_args()

    solver_url = os.environ.get("GTO_SOLVER_URL", "")
    if not solver_url:
        log.error("GTO_SOLVER_URL nao definido. Configure no .env ou ambiente.")
        sys.exit(1)
    log.info("Solver remoto: %s", solver_url)

    if args.enqueue:
        log.info("Auto-enfileirando spots do banco local...")
        n = enqueue_from_db()
        log.info("%d spots novos na fila", n)

    reset_stale_jobs()
    stats = queue_stats()
    log.info("Fila inicial: %s", stats)

    solved = rejected = failed = total_polls = 0
    last_stats_log = time.time()

    log.info("Worker iniciado. Ctrl+C para parar.")

    while _running:
        if args.limit > 0 and solved >= args.limit:
            log.info("Limite de %d spots resolvidos atingido.", args.limit)
            break

        reset_stale_jobs()

        job = get_next_solver_job()
        if not job:
            total_polls += 1
            if total_polls % 10 == 1:
                stats = queue_stats()
                log.info("Fila vazia. Stats: %s | Aguardando %ds...", stats, args.poll)
            time.sleep(args.poll)
            continue

        total_polls = 0
        result_label = process_job(job, args.timeout)
        if result_label == 'solved':
            solved += 1
        elif result_label == 'rejected':
            rejected += 1
        else:
            failed += 1

        # Log de progresso a cada 60s
        if time.time() - last_stats_log >= 60:
            stats = queue_stats()
            log.info(
                "Progresso: solved=%d rejected=%d failed=%d | Fila: %s",
                solved, rejected, failed, stats,
            )
            last_stats_log = time.time()

    log.info("Worker encerrado. Total: solved=%d rejected=%d failed=%d", solved, rejected, failed)


if __name__ == "__main__":
    main()
