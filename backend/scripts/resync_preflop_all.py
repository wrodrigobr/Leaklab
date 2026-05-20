"""
resync_preflop_all.py — Revalida TODAS as decisions preflop contra os ranges JSON.

Diferente de sync_gto_labels_from_ranges.py (que só preenche NULL), este script
compara o gto_label ATUAL de CADA decisão preflop com o que o range JSON retorna
hoje, e atualiza o que divergir.

Source of truth preflop = leaklab_gto_ranges.json (via analyze_preflop).

Uso:
    python scripts/resync_preflop_all.py                     # dry-run
    python scripts/resync_preflop_all.py --apply             # aplica ao banco
    python scripts/resync_preflop_all.py --apply --user-id 5
    python scripts/resync_preflop_all.py --apply --tid 42
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from database.schema import get_conn
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type


def _parse_cards(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if " " in raw:
        return raw.split()
    return [raw[i:i+2] for i in range(0, len(raw), 2)] if len(raw) % 2 == 0 else []


def _quality_to_label(quality: str) -> str:
    if quality == "correct":
        return "gto_correct"
    if quality == "acceptable":
        return "gto_mixed"
    if quality in ("minor_mistake", "gto_minor_deviation"):
        return "gto_minor_deviation"
    return "gto_critical"


def resync(args) -> None:
    conn = get_conn()
    try:
        where = "WHERE d.street = 'preflop' AND d.hero_cards IS NOT NULL AND d.hero_cards != ''"
        params: list = []

        if args.user_id:
            where += " AND t.user_id = ?"
            params.append(args.user_id)
        if args.tid:
            where += " AND d.tournament_id = ?"
            params.append(args.tid)

        rows = conn.execute(f"""
            SELECT d.id, d.position, d.stack_bb, d.facing_bet, d.is_3bet,
                   d.action_taken, d.best_action, d.hero_cards, d.vs_position,
                   d.gto_label, d.gto_action
            FROM decisions d
            JOIN tournaments t ON t.id = d.tournament_id
            {where}
        """, params).fetchall()

        total     = len(rows)
        changed   = []
        unchanged = 0
        no_range  = 0

        print(f"\nRevalidando {total} decisions preflop contra ranges JSON...\n")

        for row in rows:
            r = dict(row)
            cards = _parse_cards(r["hero_cards"])
            if len(cards) < 2:
                no_range += 1
                continue

            try:
                hand_type = hand_to_type(cards)
            except Exception:
                no_range += 1
                continue

            stack_bb  = float(r["stack_bb"] or 20)
            facing_bb = float(r["facing_bet"] or 0)
            pos       = r["position"] or ""
            vs_pos    = r["vs_position"] or ""
            is_3bet   = bool(r["is_3bet"])
            action    = (r["action_taken"] or "").lower()

            # BB check grátis sempre correto
            if pos.upper() == "BB" and facing_bb == 0 and action == "check":
                new_label  = "gto_correct"
                new_action = "check"
            else:
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
                    no_range += 1
                    continue

                if not result.get("available"):
                    no_range += 1
                    continue

                quality    = result.get("action_quality", "")
                rec_acts   = result.get("recommended_actions") or []
                new_label  = _quality_to_label(quality)
                new_action = rec_acts[0] if rec_acts else (r["best_action"] or action)

            old_label  = r.get("gto_label") or ""
            old_action = r.get("gto_action") or ""

            if new_label != old_label or new_action != old_action:
                changed.append({
                    "id":         r["id"],
                    "pos":        pos,
                    "hand":       hand_type,
                    "stack":      stack_bb,
                    "played":     action,
                    "old_label":  old_label,
                    "new_label":  new_label,
                    "old_action": old_action,
                    "new_action": new_action,
                })
            else:
                unchanged += 1

        print(f"{'='*70}")
        print(f"Total: {total} | Sem range: {no_range} | Sem mudança: {unchanged} | Mudanças: {len(changed)}")
        print(f"{'='*70}")

        if changed:
            print(f"\nMudanças {'(serão aplicadas)' if args.apply else '(dry-run — use --apply)'}:")
            for c in changed:
                flag = "🏷 " if c["old_label"] != c["new_label"] else "   "
                print(f"  {flag}#{c['id']:6d}  {c['pos']:<4} {c['hand']:<4} {c['stack']:>5.0f}bb "
                      f"played={c['played']:<6} "
                      f"label: {c['old_label'] or 'NULL':28s}→ {c['new_label']:<28s} "
                      f"action: {c['old_action'] or 'NULL':8s}→ {c['new_action']}")

        if args.apply and changed:
            for c in changed:
                conn.execute(
                    "UPDATE decisions SET gto_label=?, gto_action=? WHERE id=?",
                    (c["new_label"], c["new_action"], c["id"])
                )
            conn.commit()
            print(f"\n✅ {len(changed)} decisions preflop atualizadas.")
        elif not args.apply and changed:
            print(f"\nUse --apply para salvar as {len(changed)} mudanças.")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Revalida TODAS as decisions preflop contra ranges JSON")
    parser.add_argument("--apply",   action="store_true", help="Aplica mudanças no banco")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--tid",     type=int, default=None, help="Filtrar por tournament_id interno")
    args = parser.parse_args()
    resync(args)


if __name__ == "__main__":
    main()
