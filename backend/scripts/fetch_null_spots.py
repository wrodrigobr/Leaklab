"""
fetch_null_spots.py — Fetch DIRECIONADO dos spots dos NULLs preflop cobríveis.

Em vez de varrer a árvore inteira (que afunda em no-solution multiway/terminal),
busca SÓ os spots exatos que as decisões NULL cobríveis precisam (faces_squeeze /
vs_3bet / squeeze com vilão conhecido). Cada fetch é um spot de mão REAL (válido,
sem dead-end). Reusa `lookup_for_hand_decision` (encoder + snap + query_spot_raw).

Grava os nós no mesmo formato/bucket do seed (gw_preflop_seed/<bucket>.jsonl),
alinhado ao `_stack_bucket` que o analyze_preflop usa. Depois: convert + merge.

Uso:
    python scripts/fetch_null_spots.py
"""
import sys, os, json
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")
except Exception:
    pass
os.environ.setdefault("GTO_WIZARD_ENABLED", "true")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from database.schema import get_conn                                  # noqa: E402
from leaklab.parser import parse_hand_history                         # noqa: E402
from leaklab.pipeline import build_decision_inputs_for_hand           # noqa: E402
from leaklab.preflop_gto_ranges import analyze_preflop, _stack_bucket # noqa: E402
from leaklab.gto_utils import hand_to_type                            # noqa: E402
from leaklab import gto_wizard_client as gw                           # noqa: E402
from leaklab.gw_action_encoder import find_hero_preflop_decisions     # noqa: E402

SEED_DIR = BACKEND / "docs" / "gw_preflop_seed"


def _classify_code(code):
    if not code:
        return "OTHER"
    if code == "F":
        return "FOLD"
    if code in ("C", "X"):
        return "CALL"
    if code == "RAI":
        return "ALLIN"
    if code[0] in ("R", "B"):
        return "RAISE"
    return "OTHER"


def _node(r: dict) -> dict:
    spot = r.get("spot") or {}
    return {
        "pf":             spot.get("preflop_actions") or "",
        "hero_position":  r.get("hero_position"),
        "hand_freqs":     r.get("hand_freqs") or {},
        "raw_hand_freqs": r.get("raw_hand_freqs") or {},
        "actions": [{"type": _classify_code(s.get("code")), "code": s.get("code"),
                     "freq": round(float(s.get("frequency") or 0), 4)}
                    for s in (r.get("strategy") or [])],
    }


def _coverable(di: dict) -> bool:
    sp = di.get("spot", {})
    res = analyze_preflop(
        position=sp.get("position", ""), hero_hand_type=hand_to_type(di.get("hero_cards") or []),
        stack_bb=float(sp.get("effectiveStackBb") or 20), action_taken=(di.get("player_action") or "").lower(),
        facing_size=float(sp.get("facingSize") or 0), vs_position=sp.get("villainPosition", ""),
        is_3bet_pot=bool(di.get("is_3bet")), n_players=sp.get("nPlayers"),
        facing_raises=int(sp.get("preflopRaisesFaced") or 0), hero_was_aggressor=bool(sp.get("heroWasAggressor")))
    scen = res.get("scenario"); vs = sp.get("villainPosition")
    if scen == "faces_squeeze":
        return True
    return scen in ("vs_3bet", "vs_rfi", "squeeze") and bool(vs) and str(vs).lower() != "unknown"


def main():
    conn = get_conn()
    tids = [dict(x)["id"] for x in conn.execute(
        "SELECT id FROM tournaments WHERE raw_text IS NOT NULL "
        "AND tournament_id NOT LIKE 'FAKE-%' ORDER BY id").fetchall()]
    nullkeys = set()
    for row in conn.execute(
            "SELECT tournament_id,hand_id,action_taken FROM decisions "
            "WHERE lower(street)='preflop' AND (gto_label IS NULL OR gto_label='')").fetchall():
        d = dict(row); nullkeys.add((d["tournament_id"], d["hand_id"], (d["action_taken"] or "").lower()))

    out = {}; fetched = ok = 0; per_bk = {}; seen = set(); misaligned = 0
    for tid in tids:
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()[0]
        try:
            hands = parse_hand_history(raw)
        except Exception:
            continue
        for h in hands:
            try:
                dis = build_decision_inputs_for_hand(h)
                idxs = find_hero_preflop_decisions(h)
            except Exception:
                continue
            pre = [di for di in dis if (di.get("street") or "").lower() == "preflop"]
            if len(pre) != len(idxs):
                misaligned += 1
                continue   # alinhamento di↔índice incerto — pula (raro)
            for di, idx in zip(pre, idxs):
                act = (di.get("player_action") or "").lower()
                key = (tid, h.hand_id, act)
                if key not in nullkeys or key in seen:
                    continue
                if not _coverable(di):
                    continue
                seen.add(key)
                stack = float(di.get("spot", {}).get("effectiveStackBb") or 20)
                r = gw.lookup_for_hand_decision(h, idx, depth_bb=stack, use_cache=True, timeout=60)
                fetched += 1
                if not (r and r.get("found") and r.get("hand_freqs")):
                    print(f"  miss {h.hand_id} {act} stack={stack:.0f}bb -> "
                          f"{(r or {}).get('error') if r else 'None'}", flush=True)
                    continue
                bk = _stack_bucket(stack)
                node = _node(r)
                fp = SEED_DIR / f"{bk}.jsonl"
                if fp not in out:
                    out[fp] = open(fp, "a", encoding="utf-8")
                out[fp].write(json.dumps(node, ensure_ascii=False) + "\n"); out[fp].flush()
                ok += 1; per_bk[bk] = per_bk.get(bk, 0) + 1
                print(f"  ok {h.hand_id} {act} -> {bk} hero={node['hero_position']} "
                      f"scen={r.get('scenario')} pf={node['pf'][:28]}", flush=True)
    conn.close()
    for f in out.values():
        f.close()
    print(f"\nfetched={fetched} ok={ok} misaligned_hands={misaligned} por_bucket={per_bk}")
    print("Próximo: python scripts/convert_seed_to_ranges.py && python scripts/merge_seed_ranges.py "
          "&& python scripts/resync_postflop_gto.py --street preflop --apply")


if __name__ == "__main__":
    main()
