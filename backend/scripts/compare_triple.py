"""
compare_triple.py — Comparacao tripla: Engine heuristico vs RegLife v2.0 vs GTO Wizard.

Para cada spot preflop RFI do banco, consulta as tres fontes e mostra:
  ENGINE  — best_action calculado pela heuristica do decision_engine
  RL      — recomendacao do leaklab_gto_ranges.json (RegLife v2.0)
  GW      — recomendacao do GTO Wizard via servidor 34.70.251.42:8765

Objetivo: validar se RegLife e GTO Wizard concordam, e onde o engine erra vs acerta.

Uso:
    cd backend
    python scripts/compare_triple.py
    python scripts/compare_triple.py --limit 50
    python scripts/compare_triple.py --pos BTN --limit 20
"""
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path
from collections import defaultdict

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import requests as _requests
from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type
from database.schema import get_conn

RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']

GW_URL = os.environ.get("GTO_SOLVER_URL", "http://34.70.251.42:8765")
GW_KEY = os.environ.get("GTO_SOLVER_API_KEY", "")


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
        i1 = RANKS.index(r1) if r1 in RANKS else 99
        i2 = RANKS.index(r2) if r2 in RANKS else 99
        if i1 > i2:
            r1, r2, s1, s2 = r2, r1, s2, s1
        if r1 == r2:
            return f"{r1}{r2}"
        return f"{r1}{r2}{'s' if s1==s2 else 'o'}"


def norm_action(a: str) -> str:
    a = (a or "").lower().strip()
    return {"jam":"allin","shove":"allin","all-in":"allin","all_in":"allin",
            "raise":"raise","3bet":"raise","open":"raise","rfi":"raise",
            "check":"fold","call":"call"}.get(a, a)


def fetch_spots(limit: int, pos_filter: str = "") -> list[dict]:
    conn = get_conn()
    params: list = []
    extra = ""
    if pos_filter:
        extra = " AND UPPER(d.position) = ?"
        params.append(pos_filter.upper())
    params.append(limit)
    rows = conn.execute(f"""
        SELECT d.id, d.position, d.stack_bb, d.facing_bet,
               d.action_taken, d.best_action, d.label, d.hero_cards, d.level_bb
        FROM decisions d
        WHERE d.street = 'preflop'
          AND d.label IN ('small_mistake','clear_mistake')
          AND d.position IS NOT NULL AND d.position != ''
          AND d.hero_cards IS NOT NULL AND d.hero_cards != ''
          AND d.is_3bet = 0
          AND COALESCE(d.facing_bet, 0) = 0
          {extra}
        ORDER BY d.id DESC
        LIMIT ?
    """, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_gw(position: str, stack_bb: float, facing_size_bb: float = 0.0) -> dict:
    """Consulta GTO Wizard via servidor. Retorna dict com found, rec, strategy."""
    try:
        r = _requests.post(
            f"{GW_URL}/gto-wizard",
            json={
                "street":         "preflop",
                "position":       position,
                "board":          [],
                "hero_stack_bb":  stack_bb,
                "facing_size_bb": facing_size_bb,
                "pot_bb":         0.0,
            },
            headers={"x-api-key": GW_KEY},
            timeout=15,
        )
        if r.status_code == 503:
            return {"found": False, "error": "auth_expired"}
        if not r.ok:
            return {"found": False, "error": f"http_{r.status_code}"}
        data = r.json()
        if not data.get("found"):
            return {"found": False, "error": data.get("error", "not_found")}

        # Pega a acao com maior frequencia
        strategy = data.get("strategy", [])
        if not strategy:
            return {"found": False, "error": "empty_strategy"}

        best = max(strategy, key=lambda x: x.get("frequency", 0))
        rec  = norm_action(best.get("action", ""))
        freq = best.get("frequency", 0)

        # Frequencias por acao
        freqs = {}
        for s in strategy:
            act = norm_action(s.get("action", ""))
            freqs[act] = freqs.get(act, 0) + s.get("frequency", 0)

        return {
            "found":    True,
            "rec":      rec,
            "freq":     freq,
            "freqs":    freqs,
            "strategy": strategy,
        }
    except Exception as e:
        return {"found": False, "error": str(e)[:40]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--pos",   type=str, default="")
    parser.add_argument("--delay", type=float, default=0.5, help="delay entre requests GW (s)")
    args = parser.parse_args()

    # Verifica auth GW
    try:
        st = _requests.get(f"{GW_URL}/gw-status",
                           headers={"x-api-key": GW_KEY}, timeout=5).json()
        if not st.get("auth_ok"):
            print(f"[AVISO] GTO Wizard auth_ok=False (age={st.get('age_sec',0):.0f}s)")
            print("Continuando mesmo assim — resultados GW podem estar vazios.\n")
        else:
            print(f"GTO Wizard OK (age={st.get('age_sec',0):.0f}s)\n")
    except Exception as e:
        print(f"[AVISO] Nao conseguiu conectar ao servidor GW: {e}\n")

    spots = fetch_spots(args.limit, args.pos)
    print(f"{len(spots)} spots carregados.\n")

    # Cabecalho
    print(f"{'ID':>7}  {'POS':<6} {'STK':>4} {'HAND':<5} {'PLAYED':<7} "
          f"{'ENGINE':<8} {'RL_REC':<8} {'GW_REC':<8} {'RL=GW':<6} {'ENG=RL':<7} {'ENG=GW'}")
    print("-" * 95)

    stats = defaultdict(int)
    gw_errors: dict[str, int] = {}

    for d in spots:
        pos    = (d["position"] or "").upper()
        stack  = float(d["stack_bb"] or 20)
        played = norm_action(d["action_taken"] or "")
        engine = norm_action(d["best_action"] or "")
        cards  = parse_hero(d["hero_cards"])
        ht     = hand_type(cards) if cards else "?"

        # RegLife
        rl = analyze_preflop(
            position=pos, hero_hand_type=ht,
            stack_bb=stack, action_taken=played, facing_size=0.0,
        )
        rl_rec  = (rl.get("recommended_actions") or ["?"])[0] if rl.get("available") else "n/a"
        rl_qual = rl.get("action_quality", "?")

        # GTO Wizard
        gw = query_gw(pos, stack, 0.0)
        if gw["found"]:
            gw_rec  = gw["rec"]
            gw_freq = gw.get("freq", 0)
            gw_str  = f"{gw_rec}({gw_freq:.0%})"
        else:
            gw_rec  = "n/a"
            gw_str  = f"n/a[{gw.get('error','?')[:12]}]"
            err_key = gw.get("error", "?")[:20]
            gw_errors[err_key] = gw_errors.get(err_key, 0) + 1

        # Concordancias
        rl_gw  = "OK" if rl_rec  != "n/a" and gw_rec != "n/a" and rl_rec == gw_rec  else ("n/a" if "n/a" in (rl_rec, gw_rec) else "DIFF")
        eng_rl = "OK" if engine != "n/a" and rl_rec != "n/a" and engine == rl_rec else ("n/a" if rl_rec == "n/a" else "DIFF")
        eng_gw = "OK" if engine != "n/a" and gw_rec != "n/a" and engine == gw_rec else ("n/a" if gw_rec == "n/a" else "DIFF")

        stats["total"] += 1
        if rl_rec != "n/a" and gw_rec != "n/a":
            stats["both_available"] += 1
            if rl_rec == gw_rec:
                stats["rl_gw_agree"] += 1
        if engine != "n/a" and rl_rec != "n/a" and engine == rl_rec:
            stats["eng_rl_agree"] += 1
        if engine != "n/a" and gw_rec != "n/a" and engine == gw_rec:
            stats["eng_gw_agree"] += 1

        print(f"{d['id']:>7}  {pos:<6} {stack:>4.0f} {ht:<5} {played:<7} "
              f"{engine:<8} {rl_rec:<8} {gw_str:<20} {rl_gw:<6} {eng_rl:<7} {eng_gw}")

        if args.delay > 0:
            time.sleep(args.delay)

    # Sumario
    print("\n" + "="*80)
    print("SUMARIO")
    print("="*80)
    total = stats["total"]
    avail = stats["both_available"]
    print(f"Spots analisados              : {total}")
    print(f"GW disponivel                 : {avail}/{total} ({avail/total*100:.0f}%)")
    if avail > 0:
        agree = stats['rl_gw_agree']
        print(f"RegLife == GTO Wizard         : {agree}/{avail} ({agree/avail*100:.0f}%)")
    if stats["total"] > 0:
        n = stats["eng_rl_agree"]
        print(f"Engine == RegLife             : {n}/{total} ({n/total*100:.0f}%)")
        n = stats["eng_gw_agree"]
        print(f"Engine == GTO Wizard          : {n}/{total} ({n/total*100:.0f}%)")

    if gw_errors:
        print(f"\nErros GTO Wizard:")
        for err, cnt in sorted(gw_errors.items(), key=lambda x: -x[1]):
            print(f"  {err:<30} {cnt}x")

    # Conclusao
    if avail > 0:
        agree_pct = stats['rl_gw_agree'] / avail
        print(f"\nConclusao: RegLife e GTO Wizard concordam em {agree_pct:.0%} dos spots.")
        if agree_pct >= 0.80:
            print("=> RegLife esta ALINHADO com GTO Wizard. Pode ser usado como referencia primaria.")
        elif agree_pct >= 0.60:
            print("=> RegLife tem ALINHAMENTO PARCIAL. Verificar spots divergentes.")
        else:
            print("=> RegLife tem BAIXO ALINHAMENTO com GTO Wizard. Revisar extracao.")


if __name__ == "__main__":
    main()
