"""
fetch_null_canonical.py — Fetch CANÔNICO direcionado dos NULLs preflop cobríveis.

Diferença crucial vs `fetch_null_spots.py` (descartado): aquele codificava o
pf REAL da mão (sizings/sequência multiway específicos) que NÃO casa na árvore
canônica do GW → no-solution. Este constrói o pf CANÔNICO a partir das POSIÇÕES
(hero × 3bettor/opener) com códigos padrão do GW (R2 open / R6 3bet / C call),
em ordem de seat 9-max. Spots canônicos o GW resolve (~8s), e o engine indexa
faces_squeeze/vs_3bet/vs_rfi só por (hero, vs) — então um spot canônico por par
é consistente com o modelo do engine.

Regras de ordenação (seat order UTG..BB):
  vs_rfi:        vs ABRE, hero defende     → exige seat(vs)  < seat(hero)
  vs_3bet:       hero ABRE, vs 3beta       → exige seat(hero) < seat(vs)
  faces_squeeze: opener abre, vs 3beta/squeeze, hero (cold-caller ou blind) enfrenta
                 → exige um opener antes do vs; hero<vs → hero deu cold-call (C);
                   hero>vs → hero enfrenta o 3bet direto (trunca em hero).
Pares estruturalmente impossíveis (ex.: vs age depois do hero num RFI) → o
construtor devolve None ou o GW devolve not-found = NULL honesto.

Valida `hero_position` retornado == hero alvo antes de aceitar (guarda anti
construção errada). Grava nós no formato do seed em gw_preflop_seed/<bucket>.jsonl.

Uso: python scripts/fetch_null_canonical.py
"""
import sys, os, json, time
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
from leaklab.preflop_gto_ranges import analyze_preflop, _stack_bucket, _norm_pos  # noqa: E402
from leaklab.gto_utils import hand_to_type                            # noqa: E402
from leaklab import gto_wizard_client as gw                           # noqa: E402

SEED_DIR = BACKEND / "docs" / "gw_preflop_seed"
SEATS = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"]   # GW 9-max action order
SEAT = {p: i for i, p in enumerate(SEATS)}
BUCKET_DEPTH = {"10bb": 10, "14bb": 14, "17bb": 17, "20bb": 20, "30bb": 30,
                "40bb": 40, "50bb": 50, "75bb": 75, "100bb": 100}
OPEN, THREEBET, CALL, FOLD = "R2", "R6", "C", "F"


def build_pf(scen: str, hero: str, vs: str):
    """Constrói o preflop_actions canônico; None se estruturalmente impossível."""
    if hero not in SEAT or vs not in SEAT:
        return None
    h, v = SEAT[hero], SEAT[vs]
    if h == v:
        return None
    if scen == "vs_rfi":
        if v >= h:                       # opener tem de agir antes do defensor
            return None
        acts = [FOLD] * 9
        acts[v] = OPEN
        return "-".join(acts[:h])        # trunca: hero é o próximo a agir
    if scen == "vs_3bet":
        if h >= v:                       # hero abre antes do 3bettor
            return None
        acts = [FOLD] * 9
        acts[h] = OPEN
        acts[v] = THREEBET
        return "-".join(acts)            # orbita cheia; hero enfrenta no wrap
    if scen == "faces_squeeze":
        cand = [s for s in range(v) if s != h]   # opener antes do 3bettor, != hero
        if not cand:
            return None
        opener = cand[0]
        acts = [FOLD] * 9
        acts[opener] = OPEN
        acts[v] = THREEBET
        if h < v:                        # hero deu cold-call antes do squeeze → enfrenta no wrap
            acts[h] = CALL
            return "-".join(acts)
        return "-".join(acts[:h])        # hero depois do 3bettor → enfrenta direto (trunca)
    return None


def _node(r: dict) -> dict:
    spot = r.get("spot") or {}
    def _cls(code):
        if not code:                 return "OTHER"
        if code == "F":              return "FOLD"
        if code in ("C", "X"):       return "CALL"
        if code == "RAI":            return "ALLIN"
        if code[0] in ("R", "B"):    return "RAISE"
        return "OTHER"
    return {
        "pf":             spot.get("preflop_actions") or "",
        "depth_bb":       spot.get("depth_used"),
        "hero_position":  r.get("hero_position"),
        "spot":           spot,
        "hand_freqs":     r.get("hand_freqs") or {},
        "raw_hand_freqs": r.get("raw_hand_freqs") or {},
        "actions": [{"type": _cls(s.get("code")), "code": s.get("code"),
                     "freq": round(float(s.get("frequency") or 0), 4)}
                    for s in (r.get("strategy") or [])],
    }


def collect_pairs():
    """Extrai os pares (bucket, scen, hero, vs) dos NULLs preflop cobríveis."""
    conn = get_conn()
    tids = [dict(x)["id"] for x in conn.execute(
        "SELECT id FROM tournaments WHERE raw_text IS NOT NULL AND tournament_id NOT LIKE 'FAKE-%'").fetchall()]
    nullkeys = set()
    for row in conn.execute(
            "SELECT tournament_id,hand_id,action_taken FROM decisions "
            "WHERE lower(street)='preflop' AND (gto_label IS NULL OR gto_label='')").fetchall():
        d = dict(row); nullkeys.add((d["tournament_id"], d["hand_id"], (d["action_taken"] or "").lower()))
    pairs = {}; seen = set()
    for tid in tids:
        raw = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tid,)).fetchone()[0]
        try:
            hands = parse_hand_history(raw)
        except Exception:
            continue
        for h in hands:
            try:
                dis = build_decision_inputs_for_hand(h)
            except Exception:
                continue
            for di in dis:
                if (di.get("street") or "").lower() != "preflop":
                    continue
                act = (di.get("player_action") or "").lower()
                key = (tid, h.hand_id, act)
                if key not in nullkeys or key in seen:
                    continue
                sp = di.get("spot", {})
                np_ = sp.get("nPlayers")
                res = analyze_preflop(
                    position=sp.get("position", ""), hero_hand_type=hand_to_type(di.get("hero_cards") or []),
                    stack_bb=float(sp.get("effectiveStackBb") or 20), action_taken=act,
                    facing_size=float(sp.get("facingSize") or 0), vs_position=sp.get("villainPosition", ""),
                    is_3bet_pot=bool(di.get("is_3bet")), n_players=np_,
                    facing_raises=int(sp.get("preflopRaisesFaced") or 0),
                    hero_was_aggressor=bool(sp.get("heroWasAggressor")))
                scen = res.get("scenario"); vs = sp.get("villainPosition")
                cov = scen == "faces_squeeze" or (scen in ("vs_3bet", "vs_rfi") and vs and str(vs).lower() != "unknown")
                if not cov:
                    continue
                seen.add(key)
                hero = res.get("position")
                vsn = _norm_pos(vs, np_) if vs else ""
                bk = _stack_bucket(float(sp.get("effectiveStackBb") or 20))
                pairs[(bk, scen, hero, vsn)] = pairs.get((bk, scen, hero, vsn), 0) + 1
    conn.close()
    return pairs


def main():
    pairs = collect_pairs()
    print(f"Pares cobríveis: {len(pairs)} (cobrindo {sum(pairs.values())} decisões NULL)\n")
    out = {}; ok = miss = skip = badhero = 0
    for (bk, scen, hero, vs), cnt in sorted(pairs.items()):
        pf = build_pf(scen, hero, vs)
        if pf is None:
            print(f"  SKIP   {bk:>5} {scen:<13} {hero:>5} vs {vs:<5} (estruturalmente impossível) x{cnt}")
            skip += 1
            continue
        depth = BUCKET_DEPTH.get(bk, 20)
        r = gw.query_spot_raw(preflop_actions=pf, num_players=9, depth_bb=depth,
                              include_strategy=True, timeout=30, use_cache=False)
        time.sleep(0.2)
        if not (r and r.get("found") and r.get("hand_freqs")):
            print(f"  MISS   {bk:>5} {scen:<13} {hero:>5} vs {vs:<5} pf={pf:<30} (GW sem solução) x{cnt}")
            miss += 1
            continue
        got_hero = r.get("hero_position")
        if got_hero != hero:
            print(f"  BADHERO{bk:>5} {scen:<13} esperava {hero}, GW deu {got_hero} pf={pf}")
            badhero += 1
            continue
        node = _node(r)
        fp = SEED_DIR / f"{bk}.jsonl"
        if fp not in out:
            out[fp] = open(fp, "a", encoding="utf-8")
        out[fp].write(json.dumps(node, ensure_ascii=False) + "\n"); out[fp].flush()
        ok += 1
        print(f"  OK     {bk:>5} {scen:<13} {hero:>5} vs {vs:<5} pf={pf:<30} x{cnt}")
    for f in out.values():
        f.close()
    print(f"\nOK={ok} MISS={miss} SKIP={skip} BADHERO={badhero}")
    print("Próximo: convert_seed_to_ranges.py -> merge_seed_ranges.py -> resync_postflop_gto.py --street preflop --apply")


if __name__ == "__main__":
    main()
