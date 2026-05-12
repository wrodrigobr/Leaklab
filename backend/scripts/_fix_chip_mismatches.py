"""
_fix_chip_mismatches.py — Limpa mismatches causados por facing_size em chips.

1. Zera gto_action/gto_label nas decisions com mismatch de contexto.
2. Remove entradas da gto_solver_queue com facing_size_bb > 500 (claramente em chips).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from database.repositories import get_conn

conn = get_conn()

# 1. Mismatch contextual (best_action vs gto_action incompatíveis)
mismatches = conn.execute("""
    SELECT id, best_action, gto_action
    FROM decisions
    WHERE gto_action IS NOT NULL
      AND ((best_action = 'call' AND gto_action IN ('check','bet'))
        OR (best_action != 'call' AND gto_action = 'call'))
""").fetchall()

print(f"Mismatches encontrados: {len(mismatches)}")
for row in mismatches:
    print(f"  dec={row[0]} best={row[1]} gto={row[2]}")

if mismatches:
    ids = [r[0] for r in mismatches]
    placeholders = ','.join('?' * len(ids))
    conn.execute(
        f"UPDATE decisions SET gto_label=NULL, gto_action=NULL WHERE id IN ({placeholders})",
        ids
    )
    print(f"-> {len(ids)} decisions resetadas")

# 2. Queue entries com facing_size_bb em chips (> 500bb — impossivel em BB)
bad_queue = conn.execute("""
    SELECT id, spot_json FROM gto_solver_queue
    WHERE status IN ('pending','failed')
""").fetchall()

chip_entries = []
for row in bad_queue:
    try:
        spot = json.loads(row[1])
        facing = float(spot.get('facing_size_bb', 0) or 0)
        if facing > 500:
            chip_entries.append(row[0])
            print(f"  queue id={row[0]} facing_size_bb={facing} (chips)")
    except Exception:
        pass

if chip_entries:
    placeholders = ','.join('?' * len(chip_entries))
    conn.execute(
        f"DELETE FROM gto_solver_queue WHERE id IN ({placeholders})",
        chip_entries
    )
    print(f"-> {len(chip_entries)} entradas de fila com chips removidas")
else:
    print("Nenhuma entrada de fila com chips encontrada")

conn.commit()
conn.close()
print("Concluido.")
