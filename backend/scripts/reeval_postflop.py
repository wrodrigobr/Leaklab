"""
Reavalia decisões postflop no banco com o evaluator atual.

A equity estimada não é armazenada em decisions — o evaluator a calcula
em runtime. Por isso, este script usa uma abordagem conservadora:

1. Draws fracos (BDFD/BDSD) que foram recomendados como 'bet' sem aposta:
   -> Muda para 'check' (novo evaluator exige equity_adj >= 0.10 para semi-bluff)

2. Spots de aposta pura (sem draw, facing_bet=0) que foram 'bet':
   -> Para re-avaliar corretamente, seria necessário equity (não armazenada).
   -> Este script NÃO toca esses casos. Para o fix completo, re-upload as mãos.

Uso:
    cd backend
    python scripts/reeval_postflop.py [--dry-run]
"""
from __future__ import annotations
import argparse, sqlite3, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'leaklab.db')

# Mapeamento de draw → equity_adj (baseado em draw_detector.py)
_DRAW_ADJ: dict[str, float] = {
    "FD": 0.15, "FLUSH_DRAW": 0.15,
    "OESD": 0.17, "OPEN_ENDED": 0.17,
    "GUT": 0.08, "GUTSHOT": 0.08,
    "BDFD": 0.06, "BACKDOOR_FLUSH": 0.06,
    "BDSD": 0.04, "BACKDOOR_STRAIGHT": 0.04,
    "COMBO_DRAW": 0.25, "FD+OESD": 0.25,
}


def _equity_adj_from_profile(draw_profile: str) -> float:
    """Soma equity_adj de todos os draws no profile (ex: 'GUT+BDFD' → 0.08+0.06=0.14)."""
    if not draw_profile or draw_profile.upper() in ("NONE", ""):
        return 0.0
    total = 0.0
    for part in draw_profile.upper().replace("+", " ").replace(",", " ").split():
        total += _DRAW_ADJ.get(part, 0.0)
    return total


def reeval(dry_run: bool = False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT id, street, position, stack_bb, facing_bet,
               best_action, draw_profile, range_penalty, score,
               estimated_equity
        FROM decisions
        WHERE street IN ('flop', 'turn', 'river')
          AND best_action = 'bet'
          AND (facing_bet IS NULL OR facing_bet = 0)
    """).fetchall()

    total_bet_nofacing = len(rows)
    weak_draw_fixes: list[int] = []
    equity_fixes:    list[int] = []   # draw forte mas equity insuficiente → check
    still_needs:     list[dict] = []  # draw forte sem equity armazenada

    for r in rows:
        dp       = (r["draw_profile"] or "none").strip()
        adj      = _equity_adj_from_profile(dp)
        equity   = r["estimated_equity"]

        is_weak = adj < 0.15

        if is_weak:
            weak_draw_fixes.append(r["id"])
            continue

        # Draw forte (FD/OESD+) — usa equity armazenada se disponível
        if equity is not None:
            stack_bb  = float(r["stack_bb"] or 100)
            position  = (r["position"] or "").upper()
            is_oop    = position in ("BB", "SB")
            if stack_bb <= 35:
                draw_threshold = 0.52 if is_oop else 0.48
            elif stack_bb <= 60:
                draw_threshold = 0.48 if is_oop else 0.44
            else:
                draw_threshold = 0.46 if is_oop else 0.42
            if equity < draw_threshold:
                equity_fixes.append(r["id"])
        else:
            still_needs.append({
                "id": r["id"],
                "position": r["position"],
                "stack_bb": r["stack_bb"],
                "draw_profile": dp,
                "range_penalty": r["range_penalty"],
            })

    print(f"\nReavaliação postflop — bet sem aposta adversária")
    print(f"  Total 'bet' no-facing:                  {total_bet_nofacing}")
    print(f"  Draws fracos (adj<0.15) -> check:       {len(weak_draw_fixes)}")
    print(f"  Draws fortes c/ equity baixa -> check:  {len(equity_fixes)}")
    print(f"  Sem equity armazenada (re-upload):      {len(still_needs)}")

    if still_needs:
        print(f"\n  [!] {len(still_needs)} decisoes sem equity — re-uploade as maos pelo /analyze.")
        for r in still_needs[:5]:
            print(f"        {r['position'] or '?':<8} {r['stack_bb'] or 0:>6.1f}bb  "
                  f"draw={r['draw_profile'] or 'none':<15}")

    total_fixes = len(weak_draw_fixes) + len(equity_fixes)

    if dry_run:
        print(f"\n[DRY RUN] {total_fixes} decisões seriam corrigidas. Nenhuma alteração salva.")
        return

    if not total_fixes:
        print("\nNada a atualizar.")
        return

    confirm = input(f"\nAtualizar {total_fixes} decisões (bet->check)? [s/N] ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    for decision_id in weak_draw_fixes + equity_fixes:
        conn.execute("UPDATE decisions SET best_action = 'check' WHERE id = ?",
                     (decision_id,))
    conn.commit()
    conn.close()
    print(f"\nAtualizado: {total_fixes} decisoes -> check "
          f"({len(weak_draw_fixes)} draw fraco, {len(equity_fixes)} equity insuficiente)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    reeval(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
