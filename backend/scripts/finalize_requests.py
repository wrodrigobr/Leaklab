"""Mark processed hand requests as done and process remaining pending ones."""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

import sqlite3
db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'leaklab.db')
conn = sqlite3.connect(db)
c = conn.cursor()

# Mark request 14 as done (already processed by run_hand_worker.py)
c.execute("UPDATE gto_hand_requests SET status='done', decisions_done=2 WHERE id=14 AND status='processing'")
print(f'Marked id=14 as done: {c.rowcount} rows')
conn.commit()

# Reset request 13 to pending for processing
c.execute("UPDATE gto_hand_requests SET status='pending', decisions_done=0 WHERE id=13")
print(f'Reset id=13 to pending: {c.rowcount} rows')
conn.commit()
conn.close()

# Process request 13
from database.repositories import _fetchone, _adapt, get_conn, update_gto_hand_request

rconn = get_conn()
req13 = _fetchone(rconn, _adapt(
    "SELECT * FROM gto_hand_requests WHERE id=13"
), ())
rconn.close()

if req13:
    print(f"\nProcessing request 13: hand={req13['hand_id']}")
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'api'))
    from app import _process_gto_hand_request
    status, err, done, queued = _process_gto_hand_request(dict(req13))
    print(f"Result: status={status} err={err} done={done} queued={queued}")
    if status == 'done':
        update_gto_hand_request(13, 'done', decisions_done=done)
    elif status == 'solver_queued':
        update_gto_hand_request(13, 'solver_queued', decisions_done=done)
