import sys; sys.path.insert(0, '.')
from database.schema import get_conn
conn = get_conn()
n = conn.execute("SELECT COUNT(*) FROM gto_nodes").fetchone()[0]
print("gto_nodes total:", n)
# list columns
cols = [c['name'] for c in conn.execute("PRAGMA table_info(gto_nodes)").fetchall()]
print("columns:", cols)
rows = conn.execute("SELECT * FROM gto_nodes WHERE street='preflop' LIMIT 5").fetchall()
for r in rows:
    d = dict(r)
    if 'strategy_json' in d and d['strategy_json']:
        d['strategy_json'] = d['strategy_json'][:120]
    print(d)
conn.close()
