import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from database.repositories import get_conn
from leaklab.gto_solver import _call_remote_solver
import json

print('GTO_SOLVER_URL:', os.environ.get('GTO_SOLVER_URL', 'NAO DEFINIDO'))
print('GTO_SOLVER_API_KEY:', 'OK' if os.environ.get('GTO_SOLVER_API_KEY') else 'NAO DEFINIDO')

conn = get_conn()
# pega um spot pendente (antes eram falhos, agora resetados)
row = conn.execute(
    "SELECT spot_json FROM gto_solver_queue WHERE status='pending' LIMIT 1"
).fetchone()
conn.close()

if not row:
    print('Nenhum spot pendente')
    sys.exit()

spot = json.loads(row[0])
print()
print('board:', spot.get('board'), '| eff_stack:', spot.get('effective_stack_bb'))
print('max_iterations:', spot.get('max_iterations'))
print('Chamando solver remoto (timeout=60s)...')
result = _call_remote_solver(spot, timeout=60)
if result:
    expl = result.get('exploitability') or result.get('exploitability_pct')
    print('OK — exploitability:', expl)
    print('primary_action:', result.get('primary_action'))
else:
    print('FALHOU — resultado None (timeout, HTTP error, ou URL/KEY errado)')
