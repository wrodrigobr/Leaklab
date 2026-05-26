import sqlite3, os, json
db = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db'))

tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)

for t in tables:
    if any(x in t.lower() for x in ('queue', 'solver', 'job')):
        cols = [c[1] for c in db.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"\nQueue table: {t}, cols: {cols}")
        rows = db.execute(f"SELECT * FROM {t} ORDER BY id DESC LIMIT 10").fetchall()
        for r in rows:
            d = dict(zip(cols, r))
            if 'spot_json' in d:
                try:
                    spot = json.loads(d['spot_json'])
                    d['spot_json'] = f"street={spot.get('street')} facing={spot.get('facing_size_bb')} stack={spot.get('effective_stack_bb')}"
                except: pass
            print(' ', d)

db.close()
