"""
sync_gto_labels_from_ranges.py — Preenche gto_label/gto_action para decisões
preflop sem veredicto de solver, usando a análise de ranges estáticos.

O solver (gto_nodes) tem prioridade absoluta; este script só atualiza
decisões que ainda não têm gto_label, preenchendo o gap com o range estático.

Uso:
    cd backend
    python scripts/sync_gto_labels_from_ranges.py          # dry-run
    python scripts/sync_gto_labels_from_ranges.py --save   # persiste no banco
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from database.schema import get_conn
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type


def parse_cards(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if " " in raw:
        return raw.split()
    return [raw[i:i+2] for i in range(0, len(raw), 2)] if len(raw) % 2 == 0 else []


def quality_to_label(quality: str) -> str:
    if quality in ("correct",):
        return "gto_correct"
    if quality in ("acceptable",):
        return "gto_mixed"
    if quality in ("gto_minor_deviation", "minor_mistake"):
        return "gto_minor_deviation"
    return "gto_critical"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    conn = get_conn()

    rows = conn.execute("""
        SELECT id, street, position, stack_bb, facing_bet, is_3bet,
               action_taken, best_action, hero_cards, vs_position
        FROM decisions
        WHERE street = 'preflop'
          AND (gto_label IS NULL OR gto_label = '')
          AND hero_cards IS NOT NULL AND hero_cards != ''
    """).fetchall()
    rows = [dict(r) for r in rows]
    print(f"Preflop sem gto_label: {len(rows)}")

    updates: list[tuple] = []
    skipped = 0

    for r in rows:
        cards = parse_cards(r["hero_cards"])
        if len(cards) < 2:
            skipped += 1
            continue

        try:
            hand_type = hand_to_type(cards)
        except Exception:
            skipped += 1
            continue

        stack_bb   = float(r["stack_bb"] or 20)
        facing_bb  = float(r["facing_bet"] or 0)
        pos        = r["position"] or ""
        vs_pos     = r["vs_position"] or ""
        is_3bet    = bool(r["is_3bet"])
        action     = (r["action_taken"] or "").lower()

        try:
            result = analyze_preflop(
                position=pos,
                hero_hand_type=hand_type,
                stack_bb=stack_bb,
                action_taken=action,
                facing_size=facing_bb,
                vs_position=vs_pos,
                is_3bet_pot=is_3bet,
            )
        except Exception:
            skipped += 1
            continue

        if not result.get("available"):
            skipped += 1
            continue

        quality    = result.get("action_quality", "")
        rec_acts   = result.get("recommended_actions") or []
        new_label  = quality_to_label(quality)
        new_action = rec_acts[0] if rec_acts else (r["best_action"] or "")

        updates.append((new_label, new_action, r["id"]))
        if new_label != "gto_correct":
            print(f"  id={r['id']:>7}  {pos:<6} {stack_bb:>6.1f}bb  "
                  f"hand={hand_type:<4}  played={action:<6}  "
                  f"quality={quality:<24}  label={new_label}")

    print(f"\nCom range disponível: {len(updates)}")
    print(f"Sem range (skipped):  {skipped}")
    print(f"  gto_correct:         {sum(1 for l,_,_ in updates if l=='gto_correct')}")
    print(f"  gto_mixed:           {sum(1 for l,_,_ in updates if l=='gto_mixed')}")
    print(f"  gto_minor_deviation: {sum(1 for l,_,_ in updates if l=='gto_minor_deviation')}")
    print(f"  gto_critical:        {sum(1 for l,_,_ in updates if l=='gto_critical')}")

    if not updates:
        print("\nNenhuma atualização necessária.")
        conn.close()
        return

    if not args.save:
        print("\n[DRY RUN] Use --save para persistir.")
        conn.close()
        return

    for new_label, new_action, dec_id in updates:
        conn.execute(
            "UPDATE decisions SET gto_label=?, gto_action=? WHERE id=?",
            (new_label, new_action, dec_id)
        )
    conn.commit()
    conn.close()
    print(f"\n{len(updates)} decisões preflop atualizadas com veredicto de range estático.")


if __name__ == "__main__":
    main()
