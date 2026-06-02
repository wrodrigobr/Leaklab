"""
preflop_autocapture.py — Captura ON-DEMAND de spots preflop NULL via GTO Solver.

Quando um upload gera decisões preflop que o engine não consegue gradear (range
não coberta → `available=False`), este módulo busca o spot CANÔNICO no GTO Solver,
injeta no master de ranges (`leaklab_gto_ranges.json`) e re-grada as decisões
afetadas — fechando os NULLs organicamente conforme spots reais recorrem.

Reusa o que foi validado no backfill em massa:
  - pf CANÔNICO por posições (seat order 9-max), não o pf real da mão (que não casa
    na árvore do GW). Ver fetch_null_canonical.py.
  - fast-fail no-solution: `snap_raises=False` + `fetch_timeout=15` → no-solution
    falha em ~9-15s SEM travar as requisições seguintes.
  - classificação por hero_position REAL do GW + seat-tracking (mesma do conversor).

Tracking (`gto_preflop_capture`): grava o resultado por spot_key pra NÃO re-buscar
no-solution genuíno / impossível a cada upload (evita martelar o GW eternamente).

Amarrado ao fim do `/analyze` (app.py), em thread, escopo de 1 torneio.
"""
from __future__ import annotations
import json, os, tempfile, threading, logging
from collections import Counter

from database.schema import get_conn
from leaklab.parser import parse_hand_history
from leaklab.pipeline import build_decision_inputs_for_hand
from leaklab.decision_engine_v11 import evaluate_decision
from leaklab.preflop_gto_ranges import analyze_preflop, _stack_bucket, _norm_pos
from leaklab import preflop_gto_ranges as _pgr
from leaklab.gto_utils import hand_to_type
from leaklab import gto_wizard_client as gw

log = logging.getLogger(__name__)

_SEATS = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
_SEAT = {p: i for i, p in enumerate(_SEATS)}
_BUCKET_DEPTH = {"10bb": 10, "14bb": 14, "17bb": 17, "20bb": 20, "30bb": 30,
                 "40bb": 40, "50bb": 50, "75bb": 75, "100bb": 100}
_SECTION = {"vs_rfi": "vs_RFI", "vs_3bet": "vs_3bet",
            "squeeze": "squeeze", "faces_squeeze": "faces_squeeze"}
_OPEN, _THREEBET, _CALL, _FOLD = "R2", "R6", "C", "F"
_write_lock = threading.Lock()


# Em stacks RASOS o 3bet/squeeze é um SHOVE (RAI), não um raise R6 — o nó com R6
# não existe na árvore do GW (ex.: 10bb `R2-...-R6-F` = no-solution, mas
# `R2-...-RAI-F` resolve com 169 mãos). Ordem de tentativa do 3bet por bucket.
_3BET_ORDER = {
    "10bb": ["RAI", "R6"], "14bb": ["RAI", "R6"], "17bb": ["RAI", "R6"],
    "20bb": ["RAI", "R6"], "30bb": ["R6", "RAI"], "40bb": ["R6", "RAI"],
    "50bb": ["R6", "RAI"], "75bb": ["R6", "RAI"], "100bb": ["R6", "RAI"],
}


def build_canonical_pf(scenario: str, hero: str, vs: str, threebet: str = _THREEBET):
    """pf canônico por posições. `threebet` = token do 3bet/squeeze (R6 ou RAI),
    parametrizado pra cobrir o shove raso. vs_rfi não tem 3bet (ignora)."""
    if hero not in _SEAT or vs not in _SEAT:
        return None
    h, v = _SEAT[hero], _SEAT[vs]
    if h == v:
        return None
    if scenario == "vs_rfi":
        if v >= h:
            return None
        acts = [_FOLD] * 9
        acts[v] = _OPEN
        return "-".join(acts[:h])
    if scenario == "vs_3bet":
        if h >= v:
            return None
        acts = [_FOLD] * 9
        acts[h] = _OPEN
        acts[v] = threebet
        return "-".join(acts)
    if scenario == "faces_squeeze":
        cand = [s for s in range(v) if s != h]
        if not cand:
            return None
        acts = [_FOLD] * 9
        acts[cand[0]] = _OPEN
        acts[v] = threebet
        if h < v:
            acts[h] = _CALL
            # Hero deu cold-call ANTES do squeeze. No wrap, o OPENER responde primeiro
            # (não o hero); sem o fold do opener o GW devolve hero=opener e o spot é
            # keyado errado. Anexa o fold do opener → o cold-caller (hero) é o próximo.
            return "-".join(acts) + "-" + _FOLD
        return "-".join(acts[:h])
    return None


# ── classificação do resultado (espelha convert_seed_to_ranges.classify) ─────
def _is_raise(tok: str) -> bool:
    return bool(tok) and (tok == "RAI" or tok[0] in ("R", "B"))


def _classify(pf: str, hero: str) -> dict:
    parts = pf.split("-") if pf else []
    raises, calls = [], []
    for i, tok in enumerate(parts):
        if i >= len(_SEATS):
            break
        if tok == "F":
            continue
        if tok == "C":
            calls.append(_SEATS[i])
        elif _is_raise(tok):
            raises.append((_SEATS[i], i))
    nr = sum(1 for tok in parts if _is_raise(tok))
    if nr == 0:
        return {"scenario": "rfi", "k1": hero, "k2": None}
    opener = raises[0][0] if raises else None
    if nr == 1 and not calls:
        return {"scenario": "vs_rfi", "k1": opener, "k2": hero}
    if nr == 1 and calls:
        return {"scenario": "squeeze", "k1": hero, "k2": opener}
    if nr == 2:
        threbettor = raises[1][0] if len(raises) > 1 else None
        if hero == opener:
            return {"scenario": "vs_3bet", "k1": hero, "k2": threbettor}
        return {"scenario": "faces_squeeze", "k1": hero, "k2": threbettor}
    return {"scenario": "other", "k1": None, "k2": None}


# ── GW raw → spot_data (espelha convert_seed_to_ranges.build_spot) ───────────
def _classify_code(code):
    if not code:               return "OTHER"
    if code == "F":            return "FOLD"
    if code in ("C", "X"):     return "CALL"
    if code == "RAI":          return "ALLIN"
    if code[0] in ("R", "B"):  return "RAISE"
    return "OTHER"


def _spot_data(r: dict) -> dict:
    norm_hf = r.get("hand_freqs") or {}
    raw_hf = r.get("raw_hand_freqs") or {}
    raise_h, call_h, allin_h, fold_h = [], [], [], []
    for hand, acts in norm_hf.items():
        if (acts.get("raise") or 0) > 0: raise_h.append(hand)
        if (acts.get("call") or 0) > 0:  call_h.append(hand)
        if (acts.get("allin") or 0) > 0: allin_h.append(hand)
        if (acts.get("fold") or 0) > 0:  fold_h.append(hand)
    pct = {"fold": 0.0, "call": 0.0, "raise": 0.0, "allin": 0.0}
    for s in (r.get("strategy") or []):
        t = _classify_code(s.get("code")); f = float(s.get("frequency") or 0)
        if   t == "FOLD":  pct["fold"]  += f
        elif t == "CALL":  pct["call"]  += f
        elif t == "RAISE": pct["raise"] += f
        elif t == "ALLIN": pct["allin"] += f
    return {
        "fold_pct":  round(pct["fold"], 4),  "call_pct":  round(pct["call"], 4),
        "raise_pct": round(pct["raise"], 4), "allin_pct": round(pct["allin"], 4),
        "aggr_pct":  round(pct["call"] + pct["raise"] + pct["allin"], 4),
        "fold_hands":  ",".join(sorted(fold_h)),
        "call_hands":  ",".join(sorted(call_h)),
        "raise_hands": ",".join(sorted(raise_h)),
        "allin_hands": ",".join(sorted(allin_h)),
        "hand_freqs":  raw_hf,
        "source":      "gw_autocapture",
        "preflop_actions": (r.get("spot") or {}).get("preflop_actions"),
    }


def _persist_ranges(data: dict) -> None:
    """Escrita atômica do master JSON (temp + os.replace)."""
    path = _pgr._RANGES_FILE
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


# ── tracking table ───────────────────────────────────────────────────────────
def _ensure_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gto_preflop_capture (
            spot_key   TEXT PRIMARY KEY,
            scenario   TEXT, hero TEXT, vs TEXT, bucket TEXT,
            status     TEXT,           -- captured / no_solution / impossible / failed
            attempts   INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        )""")


def _seen_status(conn, key: str):
    row = conn.execute("SELECT status, attempts FROM gto_preflop_capture WHERE spot_key=?",
                       (key,)).fetchone()
    return dict(row) if row else None


def _mark(conn, key, scen, hero, vs, bucket, status, attempts):
    conn.execute("""
        INSERT INTO gto_preflop_capture (spot_key,scenario,hero,vs,bucket,status,attempts,updated_at)
        VALUES (?,?,?,?,?,?,?,datetime('now'))
        ON CONFLICT(spot_key) DO UPDATE SET status=excluded.status,
            attempts=excluded.attempts, updated_at=datetime('now')""",
        (key, scen, hero, vs, bucket, status, attempts))


# ── captura de UM spot → injeta no master ────────────────────────────────────
def capture_one(scenario: str, hero: str, vs: str, bucket: str) -> str:
    """Retorna: captured / no_solution / impossible / error. Tenta os sizings de
    3bet na ordem do bucket (RAI raso / R6 fundo) com fallback pro outro."""
    depth = _BUCKET_DEPTH.get(bucket, 20)
    # vs_rfi não tem 3bet → 1 candidato; demais tentam RAI/R6 na ordem do bucket
    codes = [_THREEBET] if scenario == "vs_rfi" else _3BET_ORDER.get(bucket, ["R6", "RAI"])
    any_built = False
    last_err = False
    for code in codes:
        pf = build_canonical_pf(scenario, hero, vs, threebet=code)
        if pf is None:
            continue
        any_built = True
        try:
            r = gw.query_spot_raw(preflop_actions=pf, num_players=9, depth_bb=depth,
                                  include_strategy=True, timeout=30, use_cache=True,
                                  snap_raises=False, fetch_timeout=15)
        except Exception as e:
            log.info("autocapture: erro no fetch %s/%s vs %s @%s: %s", scenario, hero, vs, bucket, e)
            last_err = True
            continue
        if not (r and r.get("found") and r.get("hand_freqs")):
            continue
        got_hero = r.get("hero_position")
        rpf = (r.get("spot") or {}).get("preflop_actions") or pf
        cls = _classify(rpf, got_hero or hero)
        sec = _SECTION.get(cls["scenario"])
        if not sec or not cls.get("k1") or not cls.get("k2"):
            continue
        spot = _spot_data(r)
        with _write_lock:
            data = _pgr._load()
            node = data.setdefault("ranges", {}).setdefault(bucket, {}).setdefault(sec, {})
            node.setdefault(cls["k1"], {})[cls["k2"]] = spot
            _persist_ranges(data)
        log.info("autocapture: CAPTUROU %s[%s][%s]@%s (pf=%s)", sec, cls["k1"], cls["k2"], bucket, rpf)
        return "captured"
    if not any_built:
        return "impossible"
    return "error" if last_err else "no_solution"


# ── coleta dos pares NULL cobríveis de UM torneio ────────────────────────────
def _coverable_null_pairs(conn, tournament_db_id: int) -> set:
    row = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tournament_db_id,)).fetchone()
    if not row or not row[0]:
        return set()
    try:
        hands = parse_hand_history(row[0])
    except Exception:
        return set()
    # NULLs preflop atuais deste torneio (chave por hand_id+ação)
    nullkeys = set()
    for d in conn.execute(
            "SELECT hand_id, action_taken FROM decisions WHERE tournament_id=? "
            "AND lower(street)='preflop' AND (gto_label IS NULL OR gto_label='')",
            (tournament_db_id,)).fetchall():
        dd = dict(d)
        nullkeys.add((dd["hand_id"], (dd["action_taken"] or "").lower()))
    pairs = set()
    for h in hands:
        try:
            dis = build_decision_inputs_for_hand(h)
        except Exception:
            continue
        for di in dis:
            if (di.get("street") or "").lower() != "preflop":
                continue
            act = (di.get("player_action") or "").lower()
            if (h.hand_id, act) not in nullkeys:
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
            hero = res.get("position")
            vsn = _norm_pos(vs, np_) if vs else ""
            bk = _stack_bucket(float(sp.get("effectiveStackBb") or 20))
            if hero and vsn:
                pairs.add((bk, scen, hero, vsn))
    return pairs


def _regrade_tournament(conn, tournament_db_id: int) -> int:
    """Re-avalia as decisões preflop deste torneio e regrava os 4 campos quando
    mudam. Fecha os NULLs recém-cobertos. Match por ORDEM dentro da mão (não por
    (hand_id,action), que é ambíguo em mãos com 2+ decisões preflop da mesma ação —
    ex.: hero enfrenta CO e SB na mesma mão). Só casa quando a lista fresca e a
    armazenada têm o MESMO tamanho E as ações alinham posição-a-posição (segurança
    anti-escrita-errada); senão pula a mão inteira."""
    row = conn.execute("SELECT raw_text FROM tournaments WHERE id=?", (tournament_db_id,)).fetchone()
    if not row or not row[0]:
        return 0
    try:
        hands = parse_hand_history(row[0])
    except Exception:
        return 0
    # frescas por mão, EM ORDEM
    fresh_by_hand: dict = {}
    for h in hands:
        try:
            dis = build_decision_inputs_for_hand(h)
        except Exception:
            continue
        for di in dis:
            if (di.get("street") or "").lower() != "preflop":
                continue
            hid = di.get("hand_id", ""); act = (di.get("player_action") or "").lower()
            if not hid or not act:
                continue
            try:
                r = evaluate_decision(di)
            except Exception:
                continue
            g = r.get("gto") or {}
            fresh_by_hand.setdefault(hid, []).append({
                "act": act,
                "label": (r.get("evaluation") or {}).get("label") or None,
                "best": r.get("bestAction") or None,
                "gto_label": (g.get("gto_label") or None),
                "gto_action": (g.get("gto_action") or None)})
    # armazenadas por mão, EM ORDEM (por id = ordem de inserção ≈ ordem de ação)
    stored_by_hand: dict = {}
    for r in conn.execute(
            "SELECT id,hand_id,action_taken,label,best_action,gto_label,gto_action "
            "FROM decisions WHERE tournament_id=? AND lower(street)='preflop' ORDER BY id",
            (tournament_db_id,)).fetchall():
        d = dict(r)
        stored_by_hand.setdefault(d["hand_id"], []).append(d)
    updated = 0
    for hid, srows in stored_by_hand.items():
        frows = fresh_by_hand.get(hid, [])
        if len(frows) != len(srows):
            continue
        if any((s["action_taken"] or "").lower() != f["act"] for s, f in zip(srows, frows)):
            continue   # ações não alinham → não arrisca escrita errada
        for s, f in zip(srows, frows):
            if (f["label"] == s["label"] and f["best"] == s["best_action"]
                    and f["gto_label"] == (s["gto_label"] or None)
                    and f["gto_action"] == (s["gto_action"] or None)):
                continue
            conn.execute("UPDATE decisions SET label=?,best_action=?,gto_label=?,gto_action=? WHERE id=?",
                         (f["label"], f["best"], f["gto_label"], f["gto_action"], s["id"]))
            updated += 1
    return updated


# ── entrada principal (chamada após o upload, em thread) ─────────────────────
def run_autocapture(tournament_db_id: int, max_spots: int = 12,
                    max_retries: int = 2) -> dict:
    """Captura os spots NULL cobríveis deste torneio (até max_spots novos),
    persiste no master e re-grada. Pula spots já tentados (captured/no_solution/
    impossible) — só re-tenta 'failed' até max_retries. Retorna stats."""
    if not gw._enabled() or not gw._base_url():
        return {"skipped": "gw_disabled"}
    conn = get_conn()
    stats = Counter()
    captured_any = False
    try:
        _ensure_table(conn)
        pairs = _coverable_null_pairs(conn, tournament_db_id)
        stats["coverable"] = len(pairs)
        budget = max_spots
        for (bk, scen, hero, vs) in sorted(pairs):
            if budget <= 0:
                stats["deferred"] += 1
                continue
            key = f"{bk}|{scen}|{hero}|{vs}"
            seen = _seen_status(conn, key)
            if seen and seen["status"] in ("captured", "no_solution", "impossible"):
                stats[f"skip_{seen['status']}"] += 1
                continue
            if seen and seen["status"] == "failed" and (seen["attempts"] or 0) >= max_retries:
                stats["skip_failed_max"] += 1
                continue
            budget -= 1
            attempts = (seen["attempts"] if seen else 0) + 1
            res = capture_one(scen, hero, vs, bk)
            status = res if res in ("captured", "no_solution", "impossible") else "failed"
            _mark(conn, key, scen, hero, vs, bk, status, attempts)
            conn.commit()
            stats[res] += 1
            if res == "captured":
                captured_any = True
        if captured_any:
            stats["regraded"] = _regrade_tournament(conn, tournament_db_id)
            conn.commit()
    except Exception as e:
        log.warning("autocapture: falha geral t%s: %s", tournament_db_id, e)
        stats["error"] = 1
    finally:
        try:
            conn.close()
        except Exception:
            pass
    log.info("autocapture t%s: %s", tournament_db_id, dict(stats))
    return dict(stats)
