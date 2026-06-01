"""
Corrige a classificação errada de spots PREFLOP em potes 3-bet/SQUEEZE.

Bug: quando o hero (cold caller / blind) enfrentava um squeeze (open + call + 3-bet),
o engine colapsava o spot em "vs_RFI" (defesa vs open simples), aplicava o range
larguíssimo de BB-vs-SB e recomendava, ex., CALL 45s vs squeeze — marcando um fold
correto como gto_critical. Raiz: faltava o sinal "nº de raises enfrentados".

Este script (idempotente):
  1. Re-parseia cada torneio (raw_text) e reconstrói os decision inputs via pipeline
     (que agora computa spot.preflopRaisesFaced / heroWasAggressor).
  2. BACKFILL: grava decisions.preflop_raises_faced em todas as decisões preflop.
  3. Para os spots "3-bet/squeeze enfrentado a frio" (>=2 raises, hero não-agressor):
     re-roda evaluate_decision e atualiza label/best_action (heurístico já corrigido)
     e LIMPA gto_label/gto_action -> NULL (sem cobertura honesta) onde estavam setados.

Uso:
    python scripts/fix_preflop_3bet_misclass.py            # dry-run (só reporta)
    python scripts/fix_preflop_3bet_misclass.py --apply    # aplica
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.schema import get_conn, init_db
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="aplica as mudanças (default: dry-run)")
    args = ap.parse_args()

    init_db()
    conn = get_conn()
    try:
        conn.execute("PRAGMA busy_timeout=8000")
    except Exception:
        pass

    tournaments = conn.execute(
        "SELECT id, tournament_id FROM tournaments WHERE raw_text IS NOT NULL ORDER BY id"
    ).fetchall()
    print(f"Torneios com raw_text: {len(tournaments)}")

    backfilled = 0
    fixed = 0
    seen = set()
    examples = []

    for trow in tournaments:
        tdb_id = trow["id"]
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id = ?", (tdb_id,)).fetchone()
        if not raw or not raw[0]:
            continue
        try:
            hands = parse_hand_history(raw[0])
        except Exception:
            continue

        for hand in hands:
            try:
                dis = build_decision_inputs_for_hand(hand)
            except Exception:
                continue
            for di in dis:
                if di.get("street") != "preflop":
                    continue
                hand_id = di.get("hand_id", "")
                spot = di.get("spot", {})
                act = (spot.get("actionTaken") or di.get("player_action", "")).lower()
                if not hand_id or not act:
                    continue
                key = (hand_id, "preflop", act)
                if key in seen:
                    continue
                seen.add(key)

                row = conn.execute(
                    "SELECT id, label, best_action, gto_label, gto_action FROM decisions "
                    "WHERE hand_id = ? AND street = 'preflop' AND action_taken = ? LIMIT 1",
                    (hand_id, act),
                ).fetchone()
                if not row:
                    continue

                prf = int(spot.get("preflopRaisesFaced") or 0)
                was_aggr = bool(spot.get("heroWasAggressor", False))

                # 1) BACKFILL da coluna (sempre)
                if args.apply:
                    conn.execute("UPDATE decisions SET preflop_raises_faced = ? WHERE id = ?",
                                 (prf, row["id"]))
                backfilled += 1

                # 2) Correção dos spots 3-bet/squeeze enfrentados a frio
                faces_3bet_cold = prf >= 2 and not was_aggr
                if not faces_3bet_cold:
                    continue

                try:
                    res = evaluate_decision(di)
                except Exception:
                    continue
                new_label = (res.get("evaluation") or {}).get("label") or row["label"]
                new_best = res.get("bestAction") or row["best_action"]
                # gto -> NULL (sem cobertura honesta nesses spots)
                changed = (new_label != row["label"] or new_best != row["best_action"]
                           or row["gto_label"] is not None or row["gto_action"] is not None)
                if changed:
                    fixed += 1
                    if len(examples) < 15:
                        examples.append(
                            f"  hand {hand_id} {di.get('position')} {spot.get('actionTaken')} "
                            f"| raises={prf} | gto {row['gto_label']}/{row['gto_action']} -> NULL "
                            f"| label {row['label']} -> {new_label} | best {row['best_action']} -> {new_best}")
                    if args.apply:
                        conn.execute(
                            "UPDATE decisions SET label = ?, best_action = ?, "
                            "gto_label = NULL, gto_action = NULL WHERE id = ?",
                            (new_label, new_best, row["id"]))

    if args.apply:
        conn.commit()
    conn.close()

    print(f"\nDecisões preflop com coluna backfillada: {backfilled}")
    print(f"Spots 3-bet/squeeze 'a frio' corrigidos (gto -> NULL): {fixed}")
    if examples:
        print("\nExemplos:")
        print("\n".join(examples))
    print(f"\n{'APLICADO' if args.apply else 'DRY-RUN (use --apply)'}")


if __name__ == "__main__":
    main()
