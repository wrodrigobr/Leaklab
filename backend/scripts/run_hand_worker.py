"""Manually run _process_gto_hand_request for a specific hand request."""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

import os
print("GTO_SOLVER_URL:", os.environ.get('GTO_SOLVER_URL', 'NOT SET'))

from database.repositories import get_conn, _fetchone, _adapt

HAND_ID = sys.argv[1] if len(sys.argv) > 1 else '257045919085'

conn = get_conn()
req = _fetchone(conn, _adapt(
    "SELECT * FROM gto_hand_requests WHERE hand_id = ? ORDER BY id DESC LIMIT 1"
), (HAND_ID,))
conn.close()

if not req:
    print("No request found for hand", HAND_ID)
    sys.exit(1)

print(f"Request: id={req['id']} status={req['status']}")

# Force to pending for test
from database.repositories import update_gto_hand_request
update_gto_hand_request(req['id'], 'pending')

# Run the actual worker function
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'api'))
from app import _process_gto_hand_request

status, err, done, queued = _process_gto_hand_request(dict(req))
print(f"Result: status={status} err={err} done={done} queued={queued}")
