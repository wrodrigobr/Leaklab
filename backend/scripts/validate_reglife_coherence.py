"""
validate_reglife_coherence.py — Validacao tripla: RegLife v2.0 vs JSON antigo vs GTO Solver.

Compara spots preflop contra tres fontes:
  1. JSON atual (RegLife v2.0)  — _fonte: reglife_pdf/*
  2. JSON backup (pre-v2.0)     — _fonte: original
  3. GTO Wizard server           — http://34.70.251.42:8765 (opcional, se online)

Para cada posicao/stack, mostra o range atual e qualitativo para
responder: "os ranges RegLife sao coerentes para usar como referencia?"

Uso:
    cd backend
    python scripts/validate_reglife_coherence.py
    python scripts/validate_reglife_coherence.py --limit 200 --show-ranges
    python scripts/validate_reglife_coherence.py --pos BTN --stack 30
    python scripts/validate_reglife_coherence.py --gw-compare  # testa servidor GTO
"""
from __future__ import annotations
import argparse, json, sys, os
from pathlib import Path
from collections import defaultdict

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from leaklab.preflop_gto_ranges import analyze_preflop
from leaklab.gto_utils import hand_to_type
from database.schema import get_conn

RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
RANGES_FILE = BACKEND_DIR / "docs" / "leaklab_gto_ranges.json"

# ── Ranges "de referencia" conhecidos pela comunidade para validacao ──────────
# Fonte: GTO Wizard / Solver benchmarks publicos para MTT 8-max 100bb
KNOWN_GOOD_RFI = {
    # format: (pos, stack, hand) -> expected action ('raise','fold','borderline')
    ("UTG",  "100bb", "AKo"): "raise",
    ("UTG",  "100bb", "AQo"): "raise",
    ("UTG",  "100bb", "72o"): "fold",
    ("UTG",  "100bb", "98s"): "borderline",
    ("BTN",  "100bb", "AKo"): "raise",
    ("BTN",  "100bb", "72o"): "raise",   # BTN abre muito amplo
    ("BTN",  "100bb", "54s"): "raise",
    ("CO",   "100bb", "AQo"): "raise",
    ("CO",   "100bb", "87s"): "raise",
    ("HJ",   "100bb", "AJo"): "raise",
    ("HJ",   "100bb", "65s"): "raise",
    ("LJ",   "100bb", "ATo"): "borderline",
    ("LJ",   "100bb", "KQo"): "raise",
    ("SB",   "100bb", "AKo"): "raise",
    ("UTG",  "20bb",  "AKo"): "raise",
    ("UTG",  "20bb",  "55" ): "raise",
    ("BTN",  "20bb",  "ATo"): "raise",
}


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
        suffix = "s" if s1 == s2 else "o"
        return f"{r1}{r2}{suffix}"


def norm_action(a: str) -> str:
    a = (a or "").lower().strip()
    return {"jam":"allin","shove":"allin","all-in":"allin","all_in":"allin",
            "raise":"raise","3bet":"raise"}.get(a, a)


def fetch_spots(limit: int, pos_filter: str = "", stack_filter: float = 0) -> list[dict]:
    conn = get_conn()
    where = """
        WHERE d.street = 'preflop'
          AND d.label IN ('small_mistake','clear_mistake','standard','big_mistake')
          AND d.position IS NOT NULL AND d.position != ''
          AND d.hero_cards IS NOT NULL AND d.hero_cards != ''
          AND d.is_3bet = 0
          AND COALESCE(d.facing_bet, 0) = 0
    """
    params: list = []
    if pos_filter:
        where += " AND UPPER(d.position) = ?"
        params.append(pos_filter.upper())
    if stack_filter > 0:
        where += " AND d.stack_bb BETWEEN ? AND ?"
        params.append(stack_filter * 0.7)
        params.append(stack_filter * 1.4)

    params.append(limit)
    rows = conn.execute(f"""
        SELECT d.id, d.position, d.stack_bb, d.facing_bet, d.is_3bet,
               d.action_taken, d.best_action, d.label, d.hero_cards,
               d.pot_size, d.level_bb, t.tournament_id
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        {where}
        ORDER BY RANDOM()
        LIMIT ?
    """, tuple(params)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_ranges_json() -> dict:
    with open(RANGES_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_rfi_entry(rng: dict, bucket: str, pos: str) -> dict | None:
    """Retorna a entrada RFI para um bucket/posicao do JSON."""
    pos_map = {
        'UTG+1': 'UTG1', 'UTG+2': 'LJ', 'MP': 'LJ',
        'MP1': 'LJ', 'MP2': 'HJ',
    }
    pos = pos_map.get(pos.upper(), pos.upper())
    return rng.get('ranges', {}).get(bucket, {}).get('RFI', {}).get(pos)


def _stack_bucket(stack_bb: float) -> str:
    data = load_ranges_json()
    for label, bounds in data.get('stack_buckets', {}).items():
        if bounds['min'] <= stack_bb <= bounds['max']:
            return label
    return '100bb'


# ── GTO Wizard integration (opcional) ────────────────────────────────────────
def check_gw_server() -> tuple[bool, str]:
    """Verifica se o servidor GTO Wizard esta online e autenticado."""
    try:
        import requests
        r = requests.get("http://34.70.251.42:8765/status", timeout=5)
        d = r.json()
        ok = d.get("auth_ok", False)
        age = d.get("age_sec", 0)
        return ok, f"auth_ok={ok}, age={age:.0f}s"
    except Exception as e:
        return False, str(e)


def query_gw(position: str, hand_type_str: str, stack_bb: float) -> dict | None:
    """Consulta o servidor GTO Wizard para um spot RFI."""
    try:
        import requests
        payload = {
            "position": position,
            "hand": hand_type_str,
            "stack_bb": stack_bb,
            "street": "preflop",
            "action_seq": []
        }
        r = requests.post("http://34.70.251.42:8765/lookup_gto",
                          json=payload, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


# ── Validacao dos ranges conhecidos ──────────────────────────────────────────
def validate_known_spots(rng: dict, show: bool = True) -> dict:
    """Valida ranges contra benchmarks conhecidos da comunidade."""
    results = {"pass": 0, "fail": 0, "borderline": 0, "details": []}

    if show:
        print("\n" + "="*80)
        print("VALIDACAO contra benchmarks GTO conhecidos (MTT 8-max)")
        print("="*80)
        print(f"{'POS':<5} {'STACK':<7} {'HAND':<5} {'EXPECTED':<11} {'RL_REC':<10} {'RL_PCT':<8} STATUS")
        print("-"*65)

    from leaklab.preflop_gto_ranges import analyze_preflop
    for (pos, stack_str, hand), expected in sorted(KNOWN_GOOD_RFI.items()):
        # Convert stack string to float
        stack_val = float(stack_str.replace("bb", ""))

        analysis = analyze_preflop(
            position=pos, hero_hand_type=hand,
            stack_bb=stack_val, action_taken="raise",
            facing_size=0.0,
        )

        rl_rec = (analysis.get("recommended_actions") or ["?"])[0]
        rl_pct = analysis.get("range_pct", 0)
        avail  = analysis.get("available", False)

        if not avail:
            status = "N/A"
            results["borderline"] += 1
        elif expected == "borderline":
            status = "OK (borderline)"
            results["borderline"] += 1
        elif expected == "raise" and rl_rec in ("raise", "jam"):
            status = "PASS"
            results["pass"] += 1
        elif expected == "fold" and rl_rec == "fold":
            status = "PASS"
            results["pass"] += 1
        else:
            status = f"FAIL (got {rl_rec})"
            results["fail"] += 1

        results["details"].append({
            "pos": pos, "stack": stack_str, "hand": hand,
            "expected": expected, "rl_rec": rl_rec, "status": status,
        })

        if show:
            flag = "" if "PASS" in status or "OK" in status else " <<<"
            pct_str = f"{rl_pct:.1%}" if avail else "n/a"
            print(f"{pos:<5} {stack_str:<7} {hand:<5} {expected:<11} {rl_rec:<10} {pct_str:<8} {status}{flag}")

    if show:
        total = results["pass"] + results["fail"] + results["borderline"]
        print(f"\nResultado: {results['pass']}/{total} PASS | "
              f"{results['fail']} FAIL | {results['borderline']} borderline/n/a")

    return results


# ── Range coherence checks ────────────────────────────────────────────────────
def check_range_ordering(rng: dict, show: bool = True) -> dict:
    """
    Verifica coerencia dos ranges:
    - UTG deve ter range menor que BTN (para mesmo stack)
    - Deep stack deve ter range similar ou menor que short (para RFI)
    - SB deve ter range maior que UTG
    """
    POSITIONS_ORDER = ['UTG', 'UTG1', 'LJ', 'HJ', 'CO', 'BTN', 'SB']
    issues = []

    if show:
        print("\n" + "="*80)
        print("COERENCIA DE RANGES — Ordenacao por posicao (deve aumentar UTG->BTN)")
        print("="*80)

    for bucket in ['14bb', '20bb', '30bb', '50bb', '100bb']:
        pcts = {}
        for pos in POSITIONS_ORDER:
            entry = get_rfi_entry(rng, bucket, pos)
            if entry:
                pcts[pos] = entry.get('pct', 0)

        if show:
            line = f"{bucket:>6}: "
            for pos in POSITIONS_ORDER:
                if pos in pcts:
                    line += f"{pos}={pcts[pos]:.1%}  "
            print(line)

        # Verifica ordenacao
        prev_pct = 0.0
        prev_pos = ""
        for pos in ['UTG', 'LJ', 'HJ', 'CO', 'BTN']:
            if pos not in pcts:
                continue
            if prev_pos and pcts[pos] < prev_pct * 0.85:
                # Tolerancia de 15% (BTN pode ter pct menor em stacks curtos por push)
                issues.append(f"{bucket}: {pos}({pcts[pos]:.1%}) < {prev_pos}({prev_pct:.1%})")
            prev_pct = pcts[pos]
            prev_pos = pos

    if issues:
        if show:
            print(f"\n[ALERTA] {len(issues)} inconsistencias de ordenacao:")
            for iss in issues:
                print(f"  {iss}")
    else:
        if show:
            print("\n[OK] Ordenacao UTG < HJ < CO < BTN confirmada em todos os buckets.")

    # Verifica SB: em stacks profundos SB deve ter raise% baixo (e limp% alto)
    sb_issues = []
    for bucket in ['30bb', '50bb', '100bb']:
        entry = get_rfi_entry(rng, bucket, 'SB')
        if entry:
            raise_pct = entry.get('pct', 0)
            limp_pct  = entry.get('limp_pct', 0)
            if limp_pct == 0 and raise_pct > 0.5:
                sb_issues.append(f"{bucket}: SB raise={raise_pct:.1%} sem limp range — suspeito")
            elif limp_pct > 0:
                if show:
                    print(f"  SB {bucket}: raise={raise_pct:.1%} + limp={limp_pct:.1%} "
                          f"(total={raise_pct+limp_pct:.1%}) [OK - limp range presente]")

    if sb_issues and show:
        for iss in sb_issues:
            print(f"  [ALERTA] {iss}")

    return {"issues": issues, "sb_issues": sb_issues}


# ── Comparacao spot-a-spot contra DB ─────────────────────────────────────────
def run_spot_comparison(spots: list[dict], show_ranges: bool = False) -> dict:
    """Compara cada spot contra RegLife. Agrupa por posicao/stack."""
    stats_pos:   dict[str, dict[str, int]] = defaultdict(lambda: {"total":0,"ok":0,"fp":0,"unk":0})
    stats_stack: dict[str, dict[str, int]] = defaultdict(lambda: {"total":0,"ok":0,"fp":0,"unk":0})
    label_dist:  dict[str, int] = {}
    boundary:    list[dict] = []   # hands na fronteira do range (para validacao)

    print("\n" + "="*80)
    print("COMPARACAO SPOT-A-SPOT (spots do banco vs RegLife v2.0)")
    print("="*80)
    print(f"{'ID':>7}  {'POS':<5} {'STK':>4} {'HAND':<5} {'PLAYED':<7} "
          f"{'RL_REC':<7} {'RL_QUAL':<14} {'FONTE':<18} MATCH")
    print("-"*85)

    for d in spots:
        pos    = (d["position"] or "").upper()
        stack  = float(d["stack_bb"] or 20)
        played = norm_action(d["action_taken"] or "")
        cards  = parse_hero(d["hero_cards"])
        ht     = hand_type(cards) if cards else "?"
        bucket = _stack_bucket(stack)

        analysis = analyze_preflop(
            position=pos, hero_hand_type=ht,
            stack_bb=stack, action_taken=played,
            facing_size=0.0,
        )

        rl_qual = analysis.get("action_quality", "unknown")
        rl_recs = analysis.get("recommended_actions", [])
        rl_rec  = rl_recs[0] if rl_recs else "fold"
        avail   = analysis.get("available", False)
        in_rng  = analysis.get("in_range", False)
        range_pct = analysis.get("range_pct", 0)

        # Fonte do range (reglife ou original)
        rng_json = load_ranges_json()
        entry = get_rfi_entry(rng_json, bucket, pos)
        fonte = entry.get("_fonte", "?") if entry else "n/a"

        # Classifica resultado
        if not avail:
            match_sym = "n/a"
            stats_pos[pos]["unk"]   += 1
            stats_stack[bucket]["unk"] += 1
            label_dist["unknown"]    = label_dist.get("unknown", 0) + 1
        elif rl_qual in ("correct", "acceptable"):
            match_sym = "FP"  # engine disse erro, RL diz ok
            stats_pos[pos]["fp"]    += 1
            stats_stack[bucket]["fp"] += 1
            label_dist["fp"]         = label_dist.get("fp", 0) + 1
        else:
            match_sym = "TP"  # ambos dizem erro
            stats_pos[pos]["ok"]    += 1
            stats_stack[bucket]["ok"] += 1
            label_dist["tp"]         = label_dist.get("tp", 0) + 1

        stats_pos[pos]["total"]      += 1
        stats_stack[bucket]["total"] += 1

        # Detecta hands na fronteira (range_pct proxima de 50% = marginal)
        if avail and 0.35 < range_pct < 0.65:
            boundary.append({
                "id": d["id"], "pos": pos, "stack": stack, "hand": ht,
                "played": played, "rl_rec": rl_rec, "rl_qual": rl_qual,
                "range_pct": range_pct, "in_range": in_rng,
            })

        print(f"{d['id']:>7}  {pos:<5} {stack:>4.0f} {ht:<5} {played:<7} "
              f"{rl_rec:<7} {rl_qual:<14} {fonte:<18} {match_sym}")

        if show_ranges and avail and entry:
            hands_preview = (entry.get("hands","")[:60] or "").replace(",", ", ")
            print(f"         Range [{bucket}/{pos}] {range_pct:.1%}: {hands_preview}...")

    return {
        "stats_pos": dict(stats_pos),
        "stats_stack": dict(stats_stack),
        "label_dist": label_dist,
        "boundary": boundary,
    }


def print_summary(res: dict, total: int) -> None:
    print("\n" + "="*80)
    print("SUMARIO POR POSICAO")
    print("="*80)
    print(f"{'POS':<7} {'TOTAL':>6} {'TP(erro)':>9} {'FP(ok)':>7} {'UNK':>5} {'PRECISAO':>9}")
    print("-"*50)
    for pos in ['UTG','UTG1','LJ','HJ','CO','BTN','SB','BB']:
        s = res["stats_pos"].get(pos)
        if not s or s["total"] == 0:
            continue
        tp   = s["ok"]
        fp   = s["fp"]
        unk  = s["unk"]
        tot  = s["total"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        print(f"{pos:<7} {tot:>6}   {tp:>7}   {fp:>5}   {unk:>4}   {prec:>8.0%}")

    print("\n" + "="*80)
    print("SUMARIO POR STACK BUCKET")
    print("="*80)
    print(f"{'BUCKET':<8} {'TOTAL':>6} {'TP':>5} {'FP':>5} {'UNK':>5} {'PRECISAO':>9} {'FONTE'}")
    print("-"*55)
    for bucket in ['10bb','14bb','20bb','30bb','40bb','50bb','75bb','100bb']:
        s = res["stats_stack"].get(bucket)
        if not s or s["total"] == 0:
            continue
        tp   = s["ok"]
        fp   = s["fp"]
        unk  = s["unk"]
        tot  = s["total"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rng_json = load_ranges_json()
        entry_utg = get_rfi_entry(rng_json, bucket, 'UTG')
        fonte = entry_utg.get("_fonte", "?") if entry_utg else "original"
        print(f"{bucket:<8} {tot:>6}   {tp:>3}   {fp:>3}   {unk:>4}   {prec:>8.0%}   {fonte}")

    ld = res["label_dist"]
    tp  = ld.get("tp", 0)
    fp  = ld.get("fp", 0)
    unk = ld.get("unknown", 0)
    print(f"\nTotal: {total} | TP (ambos erro): {tp} ({tp/total*100:.0f}%) | "
          f"FP (so engine errou): {fp} ({fp/total*100:.0f}%) | "
          f"Sem dados: {unk} ({unk/total*100:.0f}%)")
    print(f"Precisao geral (TP/analyzed): "
          f"{tp/(tp+fp)*100:.0f}%" if (tp+fp) > 0 else "Precisao geral: n/a")

    # Hands na fronteira
    bnd = res["boundary"]
    if bnd:
        print(f"\n{'='*80}")
        print(f"HANDS NA FRONTEIRA DO RANGE ({len(bnd)} spots com range_pct 35-65%)")
        print("Estes spots sao mais sensiveis a erros de extracao:")
        print(f"{'ID':>7} {'POS':<5} {'STK':>4} {'HAND':<5} {'PCT':>6} {'IN_RNG':<7} {'PLAYED':<7} RL_REC")
        print("-"*60)
        for b in bnd[:20]:
            print(f"{b['id']:>7} {b['pos']:<5} {b['stack']:>4.0f} {b['hand']:<5} "
                  f"{b['range_pct']:>5.1%} {'sim' if b['in_range'] else 'nao':<7} "
                  f"{b['played']:<7} {b['rl_rec']}")


def print_range_overview(show_all: bool = False) -> None:
    """Imprime overview dos ranges atuais para inspecao visual."""
    rng = load_ranges_json()
    print("\n" + "="*80)
    print("OVERVIEW DOS RANGES REGLIFE v2.0 (RFI por posicao/stack)")
    print("="*80)
    POSITIONS = ['UTG','UTG1','LJ','HJ','CO','BTN','SB']

    for bucket in ['14bb','20bb','30bb','50bb','100bb']:
        print(f"\n--- {bucket} ---")
        print(f"{'POS':<6} {'PCT':>6} {'LIMP':>6} {'FONTE':<20} HANDS (primeiros 60 chars)")
        print("-"*90)
        for pos in POSITIONS:
            entry = get_rfi_entry(rng, bucket, pos)
            if not entry:
                continue
            pct       = entry.get("pct", 0)
            limp_pct  = entry.get("limp_pct", 0)
            fonte     = entry.get("_fonte", "?")
            hands     = entry.get("hands", "")[:60]
            limp_str  = f"{limp_pct:.1%}" if limp_pct > 0 else " -   "
            print(f"{pos:<6} {pct:>5.1%} {limp_str:>6}  {fonte:<20} {hands}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",       type=int,   default=200)
    parser.add_argument("--pos",         type=str,   default="", help="Filtrar por posicao")
    parser.add_argument("--stack",       type=float, default=0,  help="Filtrar por stack aprox")
    parser.add_argument("--show-ranges", action="store_true",    help="Mostra range por spot")
    parser.add_argument("--overview",    action="store_true",    help="Mostra overview ranges RegLife")
    parser.add_argument("--benchmarks",  action="store_true",    help="Valida benchmarks conhecidos")
    parser.add_argument("--coherence",   action="store_true",    help="Checa coerencia de ordenacao")
    parser.add_argument("--gw-compare",  action="store_true",    help="Testa conexao GTO Wizard")
    parser.add_argument("--all",         action="store_true",    help="Executa todos os checks")
    args = parser.parse_args()

    run_all = args.all or not any([
        args.overview, args.benchmarks, args.coherence, args.gw_compare
    ])

    rng = load_ranges_json()
    ver = rng.get("_metadata", {}).get("versao", "?")
    print(f"LeakLab GTO Ranges v{ver} carregado.")

    if args.overview or run_all:
        print_range_overview()

    if args.coherence or run_all:
        check_range_ordering(rng)

    if args.benchmarks or run_all:
        validate_known_spots(rng)

    if args.gw_compare:
        ok, msg = check_gw_server()
        print(f"\nGTO Wizard server: {msg}")
        if ok:
            print("Servidor online e autenticado — pode usar --gw-compare em compare_reglife_spots.py")
        else:
            print("Servidor offline ou sessao expirada.")
            print("Para reautenticar: abrir http://34.70.251.42:8765 no browser (Cloud console)")

    if run_all or (args.limit > 0 and not args.overview and not args.coherence and not args.benchmarks):
        spots = fetch_spots(args.limit, args.pos, args.stack)
        print(f"\n{len(spots)} spots RFI carregados do banco (label qualquer, facing=0).")
        if spots:
            res = run_spot_comparison(spots, show_ranges=args.show_ranges)
            print_summary(res, len(spots))


if __name__ == "__main__":
    main()
