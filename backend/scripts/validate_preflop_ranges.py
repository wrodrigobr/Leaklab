"""
validate_preflop_ranges.py — Valida e classifica spots preflop com GTO label.

Duas funções:
  1. Preenche gto_label/gto_action nas decisões preflop que ainda não têm
     (usando nossa tabela leaklab_gto_ranges.json como referência GTO).
  2. Tenta comparar com GTO Wizard ao vivo (requer GW_ACCESS_TOKEN no ambiente)
     para validar se nossas tabelas de ranges estão corretas.

Uso:
  cd backend
  python scripts/validate_preflop_ranges.py                  # preenche DB + relatório
  python scripts/validate_preflop_ranges.py --dry-run        # só exibe, não grava
  python scripts/validate_preflop_ranges.py --gw-compare     # tenta comparação GW ao vivo
  python scripts/validate_preflop_ranges.py --limit 20       # limita decisões
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
from collections import Counter

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

DB_PATH      = BACKEND_DIR / "data" / "leaklab.db"
RANGES_PATH  = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"
GW_API_BASE  = "https://api.gtowizard.com"
GW_CLIENT_ID = "790ab864-ed0c-4545-9e5a-97efe89672cd"
GW_GAMETYPE  = "MTTGeneral"

# ── GTO Wizard preflop action sequences ───────────────────────────────────────
# 8-max positions in order: UTG(0) LJ(1) HJ(2) CO(3) BTN(4) SB(5) BB(6)
POSITIONS = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
POS_IDX   = {p: i for i, p in enumerate(POSITIONS)}
# Also map aliases
POS_IDX.update({"UTG+1": 1, "UTG1": 1, "MP": 1, "EP": 0})

GW_STACK_SNAPS = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]


def _nearest_snap(stack: float) -> float:
    return min(GW_STACK_SNAPS, key=lambda s: abs(s - stack))


def _norm_action(a: str) -> str:
    a = (a or "").strip().lower()
    if a in ("jam", "allin", "all-in", "shove"):
        return "allin"
    if a in ("raise", "3bet"):
        return "raise"
    return a


# ── Range table helpers ───────────────────────────────────────────────────────

def load_ranges() -> dict:
    with open(RANGES_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_stack_bucket(stack_bb: float, ranges: dict) -> str:
    buckets = ranges["stack_buckets"]
    for bk, bounds in buckets.items():
        if bounds["min"] <= stack_bb <= bounds["max"]:
            return bk
    return "100bb"  # fallback


def range_recommendation(
    position: str,
    stack_bb: float,
    facing_bet: float,
    is_3bet: bool,
    ranges: dict,
) -> tuple[str | None, str | None]:
    """
    Returns (gto_action, scenario_key) from leaklab_gto_ranges.json.
    gto_action: 'raise'|'fold'|'call'|'allin'|None
    """
    pos = position.upper()
    bk  = get_stack_bucket(stack_bb, ranges)
    r   = ranges["ranges"].get(bk, {})

    if facing_bet == 0 and pos != "BB":
        # RFI scenario
        rfi = r.get("RFI", {}).get(pos, {})
        acoes = rfi.get("acoes", [])
        if "ALLIN" in acoes:
            return "allin", f"RFI/{bk}/{pos}"
        if "RFI" in acoes:
            return "raise", f"RFI/{bk}/{pos}"
        return "fold", f"RFI/{bk}/{pos}"

    if facing_bet > 0 and not is_3bet:
        # vs RFI — look for our position under some opener key
        vs_rfi = r.get("vs_RFI", {})
        # Try each opener key
        for opener_key, hero_map in vs_rfi.items():
            if not isinstance(hero_map, dict):
                continue
            if pos in hero_map:
                entry = hero_map[pos]
                acoes = entry.get("acoes", [])
                if "ALLIN" in acoes:
                    return "allin", f"vsRFI/{bk}/{opener_key}/{pos}"
                if "CALL" in acoes:
                    return "call", f"vsRFI/{bk}/{opener_key}/{pos}"
                if "THREBET" in acoes or "3BET" in acoes:
                    return "raise", f"vsRFI/{bk}/{opener_key}/{pos}"
                return "fold", f"vsRFI/{bk}/{opener_key}/{pos}"

    if is_3bet:
        vs_3bet = r.get("vs_3bet", {})
        if pos in vs_3bet:
            entry = vs_3bet[pos]
            acoes = entry.get("acoes", [])
            if "ALLIN" in acoes:
                return "allin", f"vs3bet/{bk}/{pos}"
            if "CALL" in acoes:
                return "call", f"vs3bet/{bk}/{pos}"
            return "fold", f"vs3bet/{bk}/{pos}"

    # BB free play / limped pot
    if pos == "BB" and facing_bet == 0:
        return "check", f"BBfree/{bk}"

    return None, None


# ── GTO label classification ──────────────────────────────────────────────────

def classify_preflop(label: str) -> str:
    """Map our heuristic label to a gto_label."""
    return {
        "small_mistake":  "gto_minor_deviation",
        "clear_mistake":  "gto_critical",
        "marginal":       "gto_mixed",
        "standard":       "gto_correct",
    }.get(label, "gto_mixed")


# ── GTO Wizard API (optional) ─────────────────────────────────────────────────

def _build_preflop_actions_up_to_hero(
    position: str, facing_bet: float, is_3bet: bool, stack_bb: float
) -> str | None:
    """
    Build GTO Wizard preflop action string up to (but not including) hero's action.
    This queries the decision node where hero must act.
    """
    pos      = position.upper()
    hero_idx = POS_IDX.get(pos, -1)
    if hero_idx == -1:
        return None

    n = len(POSITIONS)  # 7

    if facing_bet == 0 and pos != "BB":
        # RFI: everyone before folded
        actions = ["F"] * hero_idx
        return "-".join(actions) if actions else ""

    if facing_bet == 0 and pos == "BB":
        # BB free play: assume SB completed
        actions = ["F"] * (n - 2) + ["C"]  # SB completes
        return "-".join(actions)

    if facing_bet > 0 and not is_3bet:
        # Facing a single raise — determine likely raiser position
        snap = _nearest_snap(float(stack_bb))
        raise_size = round(snap * 0.092, 1)  # ~2.3bb typical
        if pos == "BB":
            # Assume BTN raised, SB folded
            btn_idx = POS_IDX["BTN"]
            sb_idx  = POS_IDX["SB"]
            actions = []
            for i in range(n - 1):  # up to but not including BB
                if i < btn_idx:
                    actions.append("F")
                elif i == btn_idx:
                    actions.append(f"R{raise_size}")
                elif i == sb_idx:
                    actions.append("F")
            return "-".join(actions)

        if pos == "SB":
            # Assume BTN raised
            btn_idx = POS_IDX["BTN"]
            actions = []
            for i in range(n - 1):  # up to SB
                if i < btn_idx:
                    actions.append("F")
                elif i == btn_idx:
                    actions.append(f"R{raise_size}")
            return "-".join(actions)

        # HJ/CO/BTN facing raise from earlier position — assume UTG raised
        actions = []
        for i in range(hero_idx):
            actions.append("F" if i != 0 else f"R{raise_size}")
        return "-".join(actions)

    if is_3bet:
        # 3-bet pot: opener + re-raise already happened
        # Too complex to reconstruct without more data; skip GW call
        return None

    return None


def try_gw_preflop(
    position: str, facing_bet: float, is_3bet: bool, stack_bb: float,
    access_token: str, anal_id: str = "",
) -> dict | None:
    """
    Attempt GTO Wizard API query for a preflop spot.
    Returns parsed action strategy dict or None on failure.
    """
    try:
        import requests
    except ImportError:
        return None

    preflop_actions = _build_preflop_actions_up_to_hero(
        position, facing_bet, is_3bet, stack_bb
    )
    if preflop_actions is None:
        return None

    snap = _nearest_snap(float(stack_bb)) + 0.125

    params = {
        "gametype":        GW_GAMETYPE,
        "depth":           snap,
        "stacks":          "",
        "preflop_actions": preflop_actions,
        "flop_actions":    "",
        "turn_actions":    "",
        "river_actions":   "",
        "board":           "",  # preflop = no board
    }
    hdrs = {
        "Authorization":      f"Bearer {access_token}",
        "Accept":             "application/json, text/plain, */*",
        "Origin":             "https://app.gtowizard.com",
        "Referer":            "https://app.gtowizard.com/",
        "gwclientid":         GW_CLIENT_ID,
    }
    if anal_id:
        hdrs["google-anal-id"] = anal_id

    try:
        r = requests.get(
            f"{GW_API_BASE}/v4/solutions/spot-solution/",
            params=params, headers=hdrs, timeout=15,
        )
        if r.status_code in (404, 204):
            return None
        if not r.ok:
            return None
        data = r.json()
    except Exception:
        return None

    # Parse action_solutions
    strategy: dict[str, float] = {}
    for item in data.get("action_solutions", []):
        raw_type = (item.get("action", {}).get("type") or "").lower()
        freq     = float(item.get("total_frequency", 0))
        name = {
            "check": "check", "call": "call", "fold": "fold",
            "bet": "raise", "raise": "raise", "all_in": "allin",
        }.get(raw_type, raw_type)
        strategy[name] = strategy.get(name, 0.0) + freq

    return strategy if strategy else None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",    action="store_true", help="Nao grava no DB")
    parser.add_argument("--gw-compare", action="store_true", help="Tenta comparacao GW ao vivo")
    parser.add_argument("--limit",      type=int, default=0)
    parser.add_argument("--user-id",    type=int, default=None)
    parser.add_argument("--db",         default=str(DB_PATH))
    args = parser.parse_args()

    import sqlite3
    db = sqlite3.connect(str(args.db))
    db.row_factory = sqlite3.Row

    ranges = load_ranges()

    where = [
        "d.street = 'preflop'",
        "d.label IN ('small_mistake','clear_mistake')",
        "d.gto_label IS NULL",
        "d.position IS NOT NULL AND d.position != ''",
        "d.hero_cards IS NOT NULL AND d.hero_cards != ''",
    ]
    if args.user_id:
        where.append(f"t.user_id = {args.user_id}")
    if args.limit:
        limit_clause = f"LIMIT {args.limit}"
    else:
        limit_clause = ""

    rows = db.execute(f"""
        SELECT d.id, d.position, d.stack_bb, d.facing_bet, d.is_3bet,
               d.action_taken, d.best_action, d.label, d.hero_cards,
               d.pot_size, d.level_bb, t.user_id
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE {" AND ".join(where)}
        ORDER BY d.id DESC
        {limit_clause}
    """).fetchall()

    print(f"Spots preflop a classificar: {len(rows)}")

    # Optional GW auth
    gw_token = os.environ.get("GW_ACCESS_TOKEN", "").strip() if args.gw_compare else ""
    gw_anal  = os.environ.get("GW_ANAL_ID", "").strip()
    if args.gw_compare and not gw_token:
        print("AVISO: GW_ACCESS_TOKEN nao definido — comparacao GW desabilitada")
        print("  $env:GW_ACCESS_TOKEN = 'eyJ...'")

    results = []
    updated = 0
    gw_calls = 0
    gw_matches = 0
    label_counter: Counter = Counter()
    match_counter: Counter = Counter()

    # Header
    print()
    print(f"{'ID':>7}  {'POS':<6} {'STK':>6} {'FACED':>6} {'PLAYED':<8} "
          f"{'BEST':8} {'GTO_ACT':<8} {'GTO_LBL':<22} {'GW':>6}")
    print("-" * 90)

    for r in rows:
        d = dict(r)
        pos       = (d["position"] or "").upper()
        stack     = float(d["stack_bb"] or 20)
        facing    = float(d["facing_bet"] or 0)
        is_3bet   = bool(d["is_3bet"])
        played    = _norm_action(d["action_taken"] or "")
        best      = _norm_action(d["best_action"] or "")
        label     = d["label"] or ""

        # gto_action for preflop = best_action (derived from our range table)
        # The range_recommendation() lookup is used only for cross-validation
        gto_action = best  # best_action IS the GTO recommendation for preflop
        gto_label  = classify_preflop(label)

        # Cross-validate: does range_recommendation() agree with best_action?
        range_action, scenario = range_recommendation(pos, stack, facing, is_3bet, ranges)
        range_match = range_action == best if range_action else None

        # Optional GW comparison
        gw_strategy = None
        gw_top      = None
        if gw_token:
            gw_strategy = try_gw_preflop(pos, facing, is_3bet, stack, gw_token, gw_anal)
            if gw_strategy:
                gw_calls += 1
                gw_top = max(gw_strategy, key=lambda k: gw_strategy[k])
                if _norm_action(gw_top) == _norm_action(gto_action):
                    gw_matches += 1
            time.sleep(0.5)

        label_counter[gto_label] += 1
        match_status = "ok" if range_match else ("mismatch" if range_match is False else "no_range")
        match_counter[match_status] += 1

        gw_col = f"{gw_top:<6}" if gw_top else "  n/a"
        mismatch_flag = " !" if range_match is False else ""
        print(f"{d['id']:>7}  {pos:<6} {stack:>6.1f} {facing:>6.1f} {played:<8} "
              f"{best:<8} {gto_action:<8} {gto_label:<22} {gw_col}{mismatch_flag}")

        results.append({
            "id":          d["id"],
            "gto_action":  gto_action,
            "gto_label":   gto_label,
            "range_match": range_match,
            "gw_top":      gw_top,
        })

        if not args.dry_run:
            db.execute(
                "UPDATE decisions SET gto_action=?, gto_label=? WHERE id=?",
                (gto_action, gto_label, d["id"]),
            )
            updated += 1

    if not args.dry_run:
        db.commit()
    db.close()

    # Summary
    print()
    print("=" * 70)
    print(f"Decisoes processadas : {len(results)}")
    print(f"Gravadas no DB       : {updated}  (dry_run={args.dry_run})")
    print()
    print("Distribuição gto_label:")
    for lbl, n in sorted(label_counter.items(), key=lambda x: -x[1]):
        print(f"  {lbl:<28} {n}")
    print()
    print("Consistência range table vs best_action:")
    for st, n in sorted(match_counter.items(), key=lambda x: -x[1]):
        print(f"  {st:<28} {n}")

    mismatches = [r for r in results if r["range_match"] is False]
    if mismatches:
        print()
        print(f"ATENCAO: {len(mismatches)} decisoes com best_action != range_table:")
        for m in mismatches[:20]:
            print(f"  id={m['id']}  gto_action={m['gto_action']}  best_action diverge")

    if gw_calls:
        print()
        print(f"GTO Wizard comparado : {gw_calls} spots")
        pct = gw_matches / gw_calls * 100
        print(f"Match GW vs leaklab  : {gw_matches}/{gw_calls} ({pct:.0f}%)")
        gw_diverge = [r for r in results if r["gw_top"] and
                      _norm_action(r["gw_top"]) != _norm_action(r["gto_action"])]
        if gw_diverge:
            print(f"Divergencias GW      : {len(gw_diverge)} — revisar leaklab_gto_ranges.json")
            for d in gw_diverge[:10]:
                print(f"  id={d['id']}  leaklab={d['gto_action']}  gw={d['gw_top']}")

    print()


if __name__ == "__main__":
    main()
