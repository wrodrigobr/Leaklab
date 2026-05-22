"""
bench_step1_prepare.py — RODA LOCAL. Sample N spots preflop do banco,
reconstrói preflop_actions a partir do raw_text e gera benchmark_spots.json.

O JSON é então enviado ao servidor GCP via SCP. Lá o step2 chama o GW.

Uso:
    python scripts/gto_validation/bench_step1_prepare.py --limit 100
    python scripts/gto_validation/bench_step1_prepare.py --limit 50 --user-id 13
"""
from __future__ import annotations
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def encode_preflop_actions(raw_text: str, hand_id: str, hero_name: str):
    """Lê raw_text do hand_id, retorna (preflop_actions, num_acoes_antes_hero)."""
    idx = raw_text.find(hand_id)
    if idx < 0:
        return None
    end = raw_text.find("PokerStars Hand", idx + 50)
    if end < 0:
        end = idx + 5000
    block = raw_text[idx - 30:end]
    s = block.find("*** HOLE CARDS ***")
    if s < 0:
        return None
    e_flop = block.find("*** FLOP ***", s)
    e_sum  = block.find("*** SUMMARY ***", s)
    e = e_flop if e_flop > 0 else e_sum
    if e < 0:
        return None
    preflop_section = block[s:e]

    m_bb = re.search(r"posts big blind (\d+)", block)
    if not m_bb:
        return None
    bb = float(m_bb.group(1))

    actions: list[str] = []
    for line in preflop_section.splitlines():
        m = re.match(r"^([^:\n]+?):\s+(folds|calls|raises|checks|bets)\s*(.*)$", line.strip())
        if not m:
            continue
        player = m.group(1).strip()
        act    = m.group(2)
        rest   = m.group(3)
        if player == hero_name:
            return ("-".join(actions), len(actions))

        if act == "folds":
            actions.append("F")
        elif act == "calls":
            actions.append("C")
        elif act == "raises":
            m2 = re.search(r"to\s+(\d+)", rest)
            if m2:
                total = float(m2.group(1))
                size_bb = round(total / bb, 1)
                actions.append(f"R{size_bb}")
            else:
                actions.append("R")
        elif act == "checks":
            actions.append("X")
        elif act == "bets":
            m2 = re.search(r"(\d+)", rest)
            if m2:
                size_bb = round(float(m2.group(1)) / bb, 1)
                actions.append(f"B{size_bb}")
    return ("-".join(actions), len(actions))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--user-id", type=int, default=None)
    p.add_argument("--out", default=str(SCRIPT_DIR / "benchmark_spots.json"))
    args = p.parse_args()

    from database.schema import get_conn
    db = get_conn()

    where = "d.street='preflop' AND d.hero_cards IS NOT NULL AND d.hero_cards != ''"
    params: list = []
    if args.user_id is not None:
        where += " AND t.user_id = ?"
        params.append(args.user_id)

    rows = db.execute(f"""
        SELECT d.id, d.hand_id, d.position, d.stack_bb, d.facing_bet, d.is_3bet,
               d.action_taken, d.best_action, d.label, d.gto_label, d.gto_action,
               d.hero_cards, t.id as tid, t.user_id, t.hero, t.raw_text
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE {where}
        ORDER BY RANDOM()
        LIMIT ?
    """, (*params, args.limit * 4)).fetchall()
    db.close()

    seen = defaultdict(int)
    cap_per_bucket = max(3, args.limit // 25)  # diversifica
    out = []
    skipped_encode = 0

    for r in rows:
        if len(out) >= args.limit:
            break
        enc = encode_preflop_actions(r["raw_text"], r["hand_id"], r["hero"])
        if not enc:
            skipped_encode += 1
            continue
        prefl, n_before = enc
        stk_bucket = int(float(r["stack_bb"] or 20) / 10) * 10
        key = (r["position"], stk_bucket)
        if seen[key] >= cap_per_bucket:
            continue
        seen[key] += 1

        # Classificar tipo de spot
        n_raises = prefl.count("R")
        n_calls  = prefl.count("C")
        if n_raises == 0:
            spot_type = "rfi" if not r["is_3bet"] else "rfi_post_limp"
        elif n_raises == 1 and n_calls == 0:
            spot_type = "vs_rfi_hu"
        elif n_raises == 1 and n_calls >= 1:
            spot_type = "vs_rfi_multiway" if n_calls >= 1 else "vs_rfi_hu"
        elif n_raises >= 2:
            spot_type = "vs_3bet" if n_calls == 0 else "vs_squeeze_or_4bet"
        else:
            spot_type = "other"

        out.append({
            "id": r["id"], "hand_id": r["hand_id"],
            "position": r["position"], "stack_bb": float(r["stack_bb"] or 20),
            "facing_bet": float(r["facing_bet"] or 0),
            "is_3bet": bool(r["is_3bet"]),
            "hero_cards": r["hero_cards"], "user_id": r["user_id"],
            "tournament_db_id": r["tid"],
            "preflop_actions": prefl, "n_actions_before_hero": n_before,
            "spot_type": spot_type,
            "action_taken": r["action_taken"], "best_action": r["best_action"],
            "label": r["label"], "stored_gto_label": r["gto_label"],
            "stored_gto_action": r["gto_action"],
        })

    # Distribuição por tipo
    types = defaultdict(int)
    for o in out:
        types[o["spot_type"]] += 1

    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Sampled {len(out)} spots ({skipped_encode} skipped por encode falho)")
    print(f"Diversidade por tipo:")
    for t, n in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t:<25} {n}")
    print(f"\nEscrito: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
