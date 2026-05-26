"""
Fix stored decision labels where 'call outside vs_rfi range' was incorrectly
classified as 'marginal' (acceptable) instead of 'small_mistake' (leak).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type
from leaklab.decision_engine_v11 import _preflop_gto_label_adjust

conn = get_conn()

rows = conn.execute("""
    SELECT id, label, score, position, hero_cards, stack_bb, action_taken
    FROM decisions
    WHERE street = 'preflop'
      AND label IN ('marginal', 'standard')
      AND action_taken IS NOT NULL
""").fetchall()

print(f"Checking {len(rows)} preflop decisions...")
updated = 0

for did, label, score, pos, hero_cards, stack_bb, action_taken in rows:
    if not hero_cards or not pos:
        continue
    h_type = hand_to_type(hero_cards)
    if not h_type:
        continue
    gto = analyze_preflop(
        position=pos,
        hero_hand_type=h_type,
        stack_bb=float(stack_bb) if stack_bb else 30.0,
        action_taken=action_taken,
    )
    if not gto.get('available'):
        continue
    quality   = gto.get('action_quality', 'unknown')
    new_label = _preflop_gto_label_adjust(label, quality)
    if new_label != label:
        print(f"  id={did} hand={hero_hand} pos={pos} act={action_taken}: {label} -> {new_label} (quality={quality})")
        conn.execute("UPDATE decisions SET label = ? WHERE id = ?", (new_label, did))
        updated += 1

conn.commit()
conn.close()
print(f"\nDone. Updated {updated} decisions.")
