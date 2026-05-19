"""
compare_reglife_spots.py — Compara spots preflop (RFI + vs_RFI) contra ranges RegLife.

Para cada spot: mostra hero_cards, posição, stack, ação jogada, o que leaklab
diz (best_action) e o que os ranges RegLife dizem.

Uso:
    cd backend
    python scripts/compare_reglife_spots.py
    python scripts/compare_reglife_spots.py --limit 100 --save
    python scripts/compare_reglife_spots.py --type rfi
    python scripts/compare_reglife_spots.py --type vsrfi
    python scripts/compare_reglife_spots.py --all  # inclui standard + clear (todos, não só mistakes)
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type
from database.schema import get_conn

RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']


def parse_hero(raw: str) -> list[str]:
    raw = (raw or "").strip()
    if " " in raw:
        return raw.split()
    if len(raw) % 2 == 0:
        return [raw[i:i+2] for i in range(0, len(raw), 2)]
    return []


def hand_type(cards: list[str]) -> str:
    if len(cards) < 2:
        return ""
    try:
        return hand_to_type(cards[0], cards[1])
    except Exception:
        c1, c2 = cards[0], cards[1]
        r1, s1 = c1[0].upper(), c1[1].lower()
        r2, s2 = c2[0].upper(), c2[1].lower()
        i1, i2 = RANKS.index(r1) if r1 in RANKS else 99, RANKS.index(r2) if r2 in RANKS else 99
        if i1 > i2:
            r1, r2, s1, s2 = r2, r1, s2, s1
        if r1 == r2:
            return f"{r1}{r2}"
        suffix = "s" if s1 == s2 else "o"
        return f"{r1}{r2}{suffix}"


def norm_action(a: str) -> str:
    a = (a or "").lower().strip()
    return {"jam":"allin","shove":"allin","all-in":"allin","all_in":"allin",
            "raise":"raise","3bet":"raise"}.get(a, a)


def fetch_spots(limit: int, spot_type: str = 'both', all_labels: bool = False) -> list[dict]:
    conn = get_conn()

    label_filter = "" if all_labels else "AND d.label IN ('small_mistake','clear_mistake')"

    if spot_type == 'rfi':
        type_filter = "AND COALESCE(d.facing_bet, 0) = 0"
    elif spot_type == 'vsrfi':
        type_filter = "AND COALESCE(d.facing_bet, 0) > 0 AND COALESCE(d.is_3bet, 0) = 0"
    else:  # both
        type_filter = "AND (COALESCE(d.facing_bet, 0) = 0 OR (COALESCE(d.facing_bet, 0) > 0 AND COALESCE(d.is_3bet, 0) = 0))"

    rows = conn.execute(f"""
        SELECT d.id, d.position, d.stack_bb, d.facing_bet, d.is_3bet,
               d.action_taken, d.best_action, d.label, d.hero_cards,
               d.pot_size, d.level_bb, d.vs_position, t.tournament_id
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE d.street = 'preflop'
          {label_filter}
          AND d.position IS NOT NULL AND d.position != ''
          AND d.hero_cards IS NOT NULL AND d.hero_cards != ''
          {type_filter}
          AND (COALESCE(d.facing_bet, 0) = 0 OR d.facing_bet >= 2.0)
        ORDER BY d.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def print_section_header(title: str):
    print()
    print("=" * 110)
    print(f"  {title}")
    print("=" * 110)
    print(f"{'ID':>7}  {'POS':<6} {'VS':>5} {'STK':>5} {'FAC':>5} {'CARDS':<7} {'PLAYED':<7} "
          f"{'BEST_ACT':<8} {'RL_REC':<8} {'RL_QUAL':<16} {'MATCH'}")
    print("-" * 110)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--save",  action="store_true", help="Grava gto_label/gto_action no DB")
    parser.add_argument("--type",  choices=["rfi", "vsrfi", "both"], default="both")
    parser.add_argument("--all",   action="store_true", help="Inclui todos os labels, nao so mistakes")
    args = parser.parse_args()

    spots = fetch_spots(args.limit, args.type, args.all)
    print(f"Spots carregados: {len(spots)} (tipo={args.type}, all_labels={args.all})")

    updates: list[tuple] = []

    # Separate RFI from vs_RFI
    rfi_spots   = [d for d in spots if not d['facing_bet'] or float(d['facing_bet'] or 0) == 0]
    vsrfi_spots = [d for d in spots if d['facing_bet'] and float(d['facing_bet'] or 0) > 0]

    def process_section(section_spots: list[dict], title: str) -> dict:
        if not section_spots:
            return {}

        print_section_header(title)
        label_dist: dict[str, int] = {}
        fp_list: list[dict] = []
        total = 0
        avail_count = 0
        section_updates: list[tuple] = []

        for d in section_spots:
            pos    = (d["position"] or "").upper()
            vs_pos = (d.get("vs_position") or "").upper() or None
            stack  = float(d["stack_bb"] or 20)
            facing = float(d["facing_bet"] or 0)
            played = norm_action(d["action_taken"] or "")
            best   = norm_action(d["best_action"] or "")
            cards  = parse_hero(d["hero_cards"])
            ht     = hand_type(cards) if cards else "?"
            cards_str = "".join(cards[:2]) if cards else "?"

            total += 1

            analysis = analyze_preflop(
                position       = pos,
                hero_hand_type = ht,
                stack_bb       = stack,
                action_taken   = played,
                facing_size    = facing,
                vs_position    = vs_pos,
            )

            rl_qual  = analysis.get("action_quality", "unknown")
            rl_recs  = analysis.get("recommended_actions", [])
            rl_rec   = rl_recs[0] if rl_recs else "fold"
            avail    = analysis.get("available", False)

            if avail:
                avail_count += 1

            rl_correct = rl_qual in ("correct", "acceptable")

            if rl_correct and avail:
                fp_list.append({
                    "id": d["id"], "pos": pos, "vs_pos": vs_pos or "-",
                    "stack": stack, "facing": facing,
                    "cards": cards_str, "ht": ht, "played": played, "best": best,
                    "rl_rec": rl_rec, "rl_qual": rl_qual,
                })

            label_dist[rl_qual] = label_dist.get(rl_qual, 0) + 1

            if not avail:
                match_sym = "n/a"
            elif rl_correct:
                match_sym = "FP"
            else:
                match_sym = "OK"

            vs_str = vs_pos or "-"
            print(f"{d['id']:>7}  {pos:<6} {vs_str:>5} {stack:>5.1f} {facing:>5.1f} {cards_str:<7} {played:<7} "
                  f"{best:<8} {rl_rec:<8} {rl_qual:<16} {match_sym}")

            if args.save and avail:
                gto_lbl = "gto_correct" if rl_correct else "gto_critical"
                section_updates.append((gto_lbl, rl_rec, d["id"]))

        updates.extend(section_updates)

        # Section summary
        print()
        print(f"  Total: {total}  |  RegLife disponível: {avail_count}/{total}")
        print("  Distribuição qualidade:")
        for lbl, n in sorted(label_dist.items(), key=lambda x: -x[1]):
            bar = "#" * min(n, 40)
            print(f"    {lbl:<22} {n:>3}  {bar}")

        fp_n = len(fp_list)
        if total > 0:
            print(f"\n  Falsos positivos (engine errou, RL ok) : {fp_n}/{total} ({fp_n/total*100:.0f}%)")
        if fp_list:
            print(f"\n  Detalhes FP ({fp_n}):")
            print(f"    {'ID':>7}  {'POS':<5} {'VS':>5} {'STK':>5} {'FAC':>5} {'CARDS':<7} "
                  f"{'PLAYED':<7} {'BEST':<7} {'RL_REC':<7} {'RL_QUAL'}")
            print("    " + "-" * 80)
            for fp in fp_list:
                print(f"    {fp['id']:>7}  {fp['pos']:<5} {fp['vs_pos']:>5} {fp['stack']:>5.1f} {fp['facing']:>5.1f} "
                      f"{fp['cards']:<7} {fp['played']:<7} {fp['best']:<7} "
                      f"{fp['rl_rec']:<7} {fp['rl_qual']}")

        return {"total": total, "avail": avail_count, "fp": fp_n, "label_dist": label_dist}

    stats_rfi   = process_section(rfi_spots,   "RFI Spots (sem aposta enfrentada)")
    stats_vsrfi = process_section(vsrfi_spots, "vs_RFI Spots (enfrentando raise)")

    # Save to DB
    if updates:
        conn = get_conn()
        for lbl, rec, did in updates:
            conn.execute("UPDATE decisions SET gto_label=?, gto_action=? WHERE id=?",
                         (lbl, rec, did))
        conn.commit()
        conn.close()
        print(f"\n{len(updates)} decisoes atualizadas no DB.")

    # Grand summary
    print()
    print("=" * 110)
    print("RESUMO GERAL")
    print("=" * 110)
    total_rfi   = stats_rfi.get("total", 0)
    total_vsrfi = stats_vsrfi.get("total", 0)
    avail_rfi   = stats_rfi.get("avail", 0)
    avail_vsrfi = stats_vsrfi.get("avail", 0)

    print(f"  RFI    — total: {total_rfi:>4}  RegLife disponível: {avail_rfi:>4}  "
          f"cobertura: {avail_rfi/max(1,total_rfi)*100:.0f}%")
    print(f"  vs_RFI — total: {total_vsrfi:>4}  RegLife disponível: {avail_vsrfi:>4}  "
          f"cobertura: {avail_vsrfi/max(1,total_vsrfi)*100:.0f}%  "
          f"(spots sem vs_position serão n/a)")
    print()


if __name__ == "__main__":
    main()
