"""
sync_gto_labels_from_solver.py — Atualiza gto_label/gto_action no banco a partir do solver.

Para cada decisão preflop com hero_cards, computa o spot_hash e consulta gto_nodes.
Se encontrar strategy_json, recalcula gto_label com base na frequência da ação jogada
(mesmos thresholds do effectiveGtoLabel no frontend).

O solver tem prioridade absoluta sobre RegLife.

Uso:
    cd backend
    python scripts/sync_gto_labels_from_solver.py          # dry-run
    python scripts/sync_gto_labels_from_solver.py --save   # persiste no banco
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from database.schema import get_conn
from leaklab.gto_utils import compute_spot_hash


def parse_cards(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if " " in raw:
        return raw.split()
    return [raw[i:i+2] for i in range(0, len(raw), 2)] if len(raw) % 2 == 0 else []


def freq_to_label(played_freq: float) -> str:
    """Mesmos thresholds do effectiveGtoLabel no frontend (Replayer.tsx)."""
    if played_freq >= 0.60:  return "gto_correct"
    if played_freq >= 0.30:  return "gto_mixed"
    if played_freq >= 0.10:  return "gto_minor_deviation"
    return "gto_critical"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true", help="Persiste no banco (default: dry-run)")
    args = parser.parse_args()

    conn = get_conn()

    rows = conn.execute("""
        SELECT id, street, position, stack_bb, facing_bet,
               action_taken, gto_label, gto_action, hero_cards
        FROM decisions
        WHERE hero_cards IS NOT NULL AND hero_cards != ''
    """).fetchall()
    rows = [dict(r) for r in rows]
    print(f"Decisoes com hero_cards: {len(rows)}")

    updates: list[tuple] = []
    skipped_no_node = 0
    skipped_no_strategy = 0

    for r in rows:
        cards = parse_cards(r["hero_cards"])
        if len(cards) < 2:
            continue

        stack_bb    = float(r["stack_bb"] or 20)
        facing_bb   = float(r["facing_bet"] or 0)
        street      = (r["street"] or "preflop").lower()
        pos         = (r["position"] or "").upper()
        board: list = []   # preflop: sem board

        # Calcula hashes possíveis (com hero_hand e genérico)
        hash_exact   = compute_spot_hash(street, pos, board, cards,  stack_bb, facing_bb)
        hash_generic = compute_spot_hash(street, pos, board, [],     stack_bb, facing_bb)
        hash_nf      = compute_spot_hash(street, pos, board, [],     stack_bb, 0.0)

        node = None
        for h in [hash_exact, hash_generic] + ([hash_nf] if facing_bb == 0 else []):
            candidate = conn.execute(
                "SELECT * FROM gto_nodes WHERE spot_hash=?", (h,)
            ).fetchone()
            if candidate and candidate["strategy_json"]:
                node = dict(candidate)
                break

        if not node:
            skipped_no_node += 1
            continue

        try:
            strat: dict = json.loads(node["strategy_json"])
        except Exception:
            skipped_no_strategy += 1
            continue

        if not strat:
            skipped_no_strategy += 1
            continue

        # Frequência da ação jogada
        played       = (r["action_taken"] or "").lower().strip()
        played_freq  = 0.0
        for act_key, act_val in strat.items():
            freq = act_val["frequency"] if isinstance(act_val, dict) else float(act_val)
            if act_key.lower() == played or (played in ("jam", "shove", "allin") and act_key.lower() in ("allin", "jam", "shove")):
                played_freq = freq
                break

        top_action = max(strat, key=lambda k: strat[k]["frequency"] if isinstance(strat[k], dict) else float(strat[k]))
        new_label  = freq_to_label(played_freq)
        new_action = top_action

        old_label  = r["gto_label"]
        old_action = r["gto_action"]

        if new_label != old_label or new_action != old_action:
            updates.append((new_label, new_action, r["id"]))
            print(f"  id={r['id']:>7}  {street:<8} {pos:<6} {stack_bb:>6.1f}bb  "
                  f"played={played:<6} freq={played_freq:.2f}  "
                  f"label: {(old_label or 'NULL'):<24} → {new_label:<24}  "
                  f"action: {(old_action or 'NULL')} → {new_action}")

    print(f"\nCom nó no solver:   {len(rows) - skipped_no_node}")
    print(f"Sem nó no solver:   {skipped_no_node}")
    print(f"Sem strategy_json:  {skipped_no_strategy}")
    print(f"Com divergência:    {len(updates)}")

    if not updates:
        print("\nNenhuma alteração necessária.")
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
    print(f"\n{len(updates)} decisoes atualizadas com veredicto do solver.")


if __name__ == "__main__":
    main()
