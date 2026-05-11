"""
solver_api/server.py — HTTP wrapper do solver_cli para a VM de produção.

Recebe POST /solve com o spot JSON, chama o solver_cli Rust e retorna o resultado.
Autenticação via header x-api-key.

Uso:
  GTO_API_KEY=<chave> python server.py
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

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


def solve(spot: dict) -> dict:
    """Chama solver_cli com spot JSON e retorna resultado."""
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
        # normaliza campo exploitability
        if 'exploitability' in result and 'exploitability_pct' not in result:
            result['exploitability_pct'] = result['exploitability']
        return result
    finally:
        os.unlink(tmp)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silencia log padrão do http.server
        pass

    def _respond(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/health':
            self._respond(200, {'status': 'ok', 'solver': os.path.basename(SOLVER_BIN)})
        else:
            self._respond(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/solve':
            self._respond(404, {'error': 'not found'})
            return

        # auth
        if API_KEY and self.headers.get('x-api-key') != API_KEY:
            self._respond(401, {'error': 'unauthorized'})
            return

        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        try:
            spot = json.loads(body)
        except Exception:
            self._respond(400, {'error': 'invalid JSON'})
            return

        start = time.time()
        try:
            result  = solve(spot)
            elapsed = round(time.time() - start, 2)
            log.info('solved in %.1fs: %s %.0f%% exploit=%.2f%%',
                     elapsed, result.get('primary_action'), result.get('primary_freq', 0) * 100,
                     result.get('exploitability', 0))
            self._respond(200, result)
        except subprocess.TimeoutExpired:
            log.warning('timeout after %ds', TIMEOUT)
            self._respond(408, {'error': f'solver timeout after {TIMEOUT}s'})
        except Exception as e:
            log.error('solver error: %s', e)
            self._respond(500, {'error': str(e)})


if __name__ == '__main__':
    if not os.path.isfile(SOLVER_BIN):
        log.error('solver_cli nao encontrado em %s', SOLVER_BIN)
        log.error('Compile com: cd solver_cli && cargo build --release')
        sys.exit(1)

    if not API_KEY:
        log.warning('GTO_API_KEY nao definida — endpoint sem autenticacao!')

    log.info('Solver API iniciando na porta %d (solver=%s timeout=%ds)',
             PORT, SOLVER_BIN, TIMEOUT)
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    server.serve_forever()
