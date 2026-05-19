"""
list_uncovered_vsrfi.py — Lista spots vs_RFI sem gto_label com motivo do miss.

Motivos possíveis:
  no_vs_position  — vs_position não foi extraído do hand text
  no_json_data    — combo (stack, opener, defender) ausente no JSON
  low_stack       — stack < 10bb (push/fold, fora do escopo RegLife)

Saída:
  --format table  — tabela legível (default)
  --format csv    — para importar em planilha / outra fonte
  --summary       — só agrupa por motivo e combo, sem linhas individuais
"""
from __future__ import annotations
import argparse, sys, csv
from pathlib import Path
from io import StringIO

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


def fetch_uncovered() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT d.id, d.position, d.vs_position, d.stack_bb, d.facing_bet,
               d.action_taken, d.best_action, d.label, d.hero_cards, d.level_bb
        FROM decisions d
        WHERE d.street = 'preflop'
          AND COALESCE(d.facing_bet, 0) > 1.0
          AND COALESCE(d.is_3bet, 0) = 0
          AND d.gto_label IS NULL
          AND d.position IS NOT NULL AND d.position != ''
        ORDER BY d.stack_bb, d.vs_position, d.position
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def classify_miss(d: dict) -> str:
    if not d.get("vs_position"):
        return "no_vs_position"
    stack = float(d.get("stack_bb") or 0)
    if stack < 10:
        return "low_stack"
    cards = parse_cards(d.get("hero_cards") or "")
    ht = hand_to_type(cards) if len(cards) >= 2 else "?"
    result = analyze_preflop(
        position=d["position"],
        hero_hand_type=ht,
        stack_bb=stack,
        action_taken=d.get("action_taken") or "fold",
        facing_size=float(d.get("facing_bet") or 0),
        vs_position=d["vs_position"],
    )
    if not result.get("available"):
        return "no_json_data"
    return "covered_now"   # já coberto (não deveria aparecer)


def stack_bucket(bb: float) -> str:
    if bb < 13:  return "10bb"
    if bb < 17:  return "14bb"
    if bb < 25:  return "20bb"
    if bb < 36:  return "30bb"
    if bb < 46:  return "40bb"
    if bb < 63:  return "50bb"
    if bb < 88:  return "75bb"
    return "100bb"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["table", "csv"], default="table")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    rows = fetch_uncovered()
    print(f"Total sem gto_label: {len(rows)}", file=sys.stderr)

    enriched = []
    for d in rows:
        miss = classify_miss(d)
        enriched.append({
            "id":           d["id"],
            "bucket":       stack_bucket(float(d.get("stack_bb") or 0)),
            "stack_bb":     round(float(d.get("stack_bb") or 0), 1),
            "position":     (d.get("position") or "").upper(),
            "vs_position":  (d.get("vs_position") or "").upper() or "?",
            "facing_bet":   round(float(d.get("facing_bet") or 0), 1),
            "hero_cards":   d.get("hero_cards") or "?",
            "action_taken": d.get("action_taken") or "?",
            "best_action":  d.get("best_action") or "?",
            "label":        d.get("label") or "?",
            "miss_reason":  miss,
        })

    if args.summary:
        from collections import Counter
        by_reason: dict[str, Counter] = {}
        for e in enriched:
            r = e["miss_reason"]
            key = f"{e['bucket']:>6}  {e['vs_position']:>8} -> {e['position']}"
            by_reason.setdefault(r, Counter())[key] += 1

        for reason, combos in sorted(by_reason.items()):
            print(f"\n{'='*60}")
            print(f"  Motivo: {reason}  ({sum(combos.values())} spots)")
            print(f"{'='*60}")
            for combo, n in sorted(combos.items(), key=lambda x: -x[1]):
                print(f"  {n:>4}x  {combo}")
        return

    if args.format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=list(enriched[0].keys()))
        writer.writeheader()
        writer.writerows(enriched)
        return

    # table
    print(f"\n{'ID':>7}  {'bucket':<7} {'stk':>5} {'pos':<6} {'vs':>8}  {'face':>5}  "
          f"{'cards':<7} {'played':<7} {'best':<7}  {'miss_reason'}")
    print("-" * 90)
    for e in enriched:
        print(f"{e['id']:>7}  {e['bucket']:<7} {e['stack_bb']:>5.1f} {e['position']:<6} "
              f"{e['vs_position']:>8}  {e['facing_bet']:>5.1f}  "
              f"{e['hero_cards']:<7} {e['action_taken']:<7} {e['best_action']:<7}  "
              f"{e['miss_reason']}")


if __name__ == "__main__":
    main()
