"""
GTO Worker — Oracle Cloud / Linux

Roda em Linux ARM64 (Oracle Always Free Ampere A1).
Sem restrições de Job Object: Rayon usa todos os vCPUs nativamente.

Uso:
    DATABASE_URL=sqlite:////caminho/leaklab.db python3 worker.py
    DATABASE_URL=postgresql://user:pass@host/db python3 worker.py

Variáveis de ambiente:
    DATABASE_URL   — sqlite:// ou postgresql:// (obrigatório)
    SOLVER_BIN     — caminho do solver_cli compilado (padrão: ./solver_cli)
    MAX_EXPLOIT    — threshold de exploitability % (padrão: 1.0)
    SOLVER_TIMEOUT — timeout por spot em segundos (padrão: 120)
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DATABASE_URL    = os.environ.get('DATABASE_URL', '')
SOLVER_BIN      = os.environ.get('SOLVER_BIN', str(Path(__file__).parent / 'solver_cli'))
MAX_EXPLOIT     = float(os.environ.get('MAX_EXPLOIT', '1.0'))
SOLVER_TIMEOUT  = int(os.environ.get('SOLVER_TIMEOUT', '120'))

if not DATABASE_URL:
    sys.exit('ERROR: DATABASE_URL não definida.\n'
             'Exemplo: export DATABASE_URL=sqlite:////home/ubuntu/leaklab.db')

if not Path(SOLVER_BIN).is_file():
    sys.exit(f'ERROR: solver_cli não encontrado em {SOLVER_BIN}\n'
             f'Compile com: cargo build --release  (na pasta solver_cli/)')

# ── Database ──────────────────────────────────────────────────────────────────

def _get_conn():
    if DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://'):
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn, '%s'
    else:
        import sqlite3
        path = DATABASE_URL.replace('sqlite:///', '').replace('sqlite://', '')
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn, '?'


def _fetchone(conn, ph, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql.replace('?', ph), params)
    row = cur.fetchone()
    if row is None:
        return None
    if hasattr(row, 'keys'):
        return dict(row)
    desc = [d[0] for d in cur.description]
    return dict(zip(desc, row))


def _execute(conn, ph, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql.replace('?', ph), params)


def _fetchscalar(conn, ph, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql.replace('?', ph), params)
    row = cur.fetchone()
    return row[0] if row else None


# ── Solver ────────────────────────────────────────────────────────────────────

def call_solver(spot: dict, timeout: int = SOLVER_TIMEOUT) -> dict | None:
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', suffix='.json', delete=False
    ) as f:
        f.write(json.dumps(spot))
        tmp = f.name
    try:
        with open(tmp, 'r', encoding='utf-8') as stdin_f:
            proc = subprocess.run(
                [SOLVER_BIN],
                stdin=stdin_f,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=timeout,
            )
        if proc.returncode != 0:
            print(f'  solver stderr: {proc.stderr[:300]}', flush=True)
            return None
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        print(f'  timeout após {timeout}s', flush=True)
        return None
    except (json.JSONDecodeError, Exception) as e:
        print(f'  solver error: {e}', flush=True)
        return None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ── Worker loop ───────────────────────────────────────────────────────────────

def main() -> None:
    conn, ph = _get_conn()

    # Reset failed/rejected → pending para re-tentar
    _execute(conn, ph,
             "UPDATE gto_solver_queue SET status='pending', solved_at=NULL "
             "WHERE status IN ('failed','rejected')")
    conn.commit()

    total  = _fetchscalar(conn, ph,
                          "SELECT COUNT(*) FROM gto_solver_queue WHERE status='pending'")
    solved = rejected = failed = 0
    t_start = time.time()

    print(f'START total={total} spots  solver={SOLVER_BIN}  max_exploit={MAX_EXPLOIT}%',
          flush=True)

    while True:
        row = _fetchone(conn, ph,
                        "SELECT spot_hash, spot_json FROM gto_solver_queue "
                        "WHERE status='pending' ORDER BY priority DESC, id ASC LIMIT 1")
        if not row:
            break

        sh   = row['spot_hash']
        spot = json.loads(row['spot_json'])

        # Marca como running para evitar double-processing (multi-worker)
        _execute(conn, ph,
                 "UPDATE gto_solver_queue SET status='running' WHERE spot_hash=? AND status='pending'",
                 (sh,))
        conn.commit()

        t0     = time.time()
        result = call_solver(spot)
        elapsed = time.time() - t0

        if result is None:
            _execute(conn, ph,
                     "UPDATE gto_solver_queue SET status='failed', solved_at=datetime('now') "
                     "WHERE spot_hash=?", (sh,))
            conn.commit()
            failed += 1
            print(f'FAIL {sh} ({elapsed:.0f}s)', flush=True)
            continue

        exploit = result.get('exploitability')

        if exploit is None or float(exploit) > MAX_EXPLOIT:
            _execute(conn, ph,
                     "UPDATE gto_solver_queue SET status='rejected', solved_at=datetime('now') "
                     "WHERE spot_hash=?", (sh,))
            conn.commit()
            rejected += 1
            print(f'REJ  {sh} exploit={exploit} ({elapsed:.0f}s)', flush=True)
            continue

        # Armazena resultado verificado
        try:
            _execute(conn, ph, """
                INSERT OR REPLACE INTO gto_nodes
                (spot_hash, street, position, board, hero_hand, stack_bucket,
                 gto_action, gto_freq, ev_diff, source, exploitability_pct, iterations, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            """, (
                sh,
                spot.get('street', ''),
                spot.get('oop_range', '')[:30],
                json.dumps(spot.get('board', [])),
                '',
                'solver',
                result['primary_action'],
                result['primary_freq'],
                result.get('ev'),
                'solver_cli',
                float(exploit),
                result.get('iterations'),
            ))
            _execute(conn, ph,
                     "UPDATE gto_solver_queue SET status='done', solved_at=datetime('now') "
                     "WHERE spot_hash=?", (sh,))
            conn.commit()
            solved += 1
            done = solved + rejected + failed
            print(
                f"OK   {sh} {result['primary_action']} exploit={exploit:.2f}% "
                f"({elapsed:.0f}s) [{done}/{total}]",
                flush=True
            )
        except Exception as e:
            conn.rollback()
            _execute(conn, ph,
                     "UPDATE gto_solver_queue SET status='failed' WHERE spot_hash=?", (sh,))
            conn.commit()
            failed += 1
            print(f'FAIL {sh} db_error={e} ({elapsed:.0f}s)', flush=True)

    elapsed_total = time.time() - t_start
    print(
        f'\nDONE solved={solved} rejected={rejected} failed={failed} '
        f'time={elapsed_total / 60:.1f}min',
        flush=True
    )
    conn.close()


if __name__ == '__main__':
    main()
