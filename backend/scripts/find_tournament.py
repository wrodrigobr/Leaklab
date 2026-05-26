import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database.schema import get_conn

conn = get_conn()
row = conn.execute(
    "SELECT d.tournament_id, t.filename FROM decisions d "
    "JOIN tournaments t ON t.id = d.tournament_id "
    "WHERE d.hand_id = '257045919085' LIMIT 1"
).fetchone()
if row:
    print('tournament_id:', row[0], 'file:', row[1])
else:
    print('not found')
conn.close()
