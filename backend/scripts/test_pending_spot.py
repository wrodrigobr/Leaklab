"""Run solver directly on a pending spot to see the error."""
import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.schema import init_db, get_conn

init_db()
conn = get_conn()
row = conn.execute(
    "SELECT spot_hash, spot_json FROM gto_solver_queue WHERE status='pending' LIMIT 1"
).fetchone()
conn.close()

if not row:
    print('Nenhum spot pendente')
    sys.exit(0)

spot_hash = row[0]
spot = json.loads(row[1])
print('Hash: ' + spot_hash)
print('Spot: ' + json.dumps(spot, indent=2)[:600])

bin_path = os.path.join(os.path.dirname(__file__), '..', 'gto_bot', 'solver_cli', 'target', 'release', 'solver_cli.exe')
print('\nRodando solver...')

with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.json', delete=False) as f:
    f.write(json.dumps(spot))
    tmp = f.name

try:
    with open(tmp, 'r', encoding='utf-8') as stdin_f:
        proc = subprocess.run(
            [bin_path], stdin=stdin_f, capture_output=True, text=True,
            encoding='utf-8', timeout=30, creationflags=0x01000000
        )
    print('exit=' + str(proc.returncode))
    print('stdout: ' + proc.stdout[:300])
    print('stderr: ' + proc.stderr[:300])
finally:
    os.unlink(tmp)
