"""
benchmark_preflop_gw.py — Roda no servidor GCP. Para N spots preflop do banco:
  1. Reconstrói preflop_actions a partir do raw_text da hand
  2. Chama GTO Wizard via Chrome CDP (servidor GCP)
  3. Compara veredicto GW vs gto_label/gto_action armazenado
  4. Persiste resposta completa em gto_nodes (strategy_json) — cache para futuro

Configs do GW JÁ MAPEADAS — não alterar:
  - Gametype: MTTGeneral (V2 está bloqueado na conta atual)
  - Depths multiway preflop válidos: [40, 50, 60, 80, 100] (probe 2026-05-22)

Uso:
    python3 scripts/gto_validation/benchmark_preflop_gw.py --limit 100
    python3 scripts/gto_validation/benchmark_preflop_gw.py --limit 100 --dry-run
    python3 scripts/gto_validation/benchmark_preflop_gw.py --user-id 13 --limit 50

Saídas:
  - Imprime tabela com 5 colunas: spot, our_label, gw_top, agree?, status
  - Salva relatório em benchmark_preflop_report.json
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sqlite3, sys, time
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

GW_APP   = "https://app.gtowizard.com"
GW_SPOT  = "https://api.gtowizard.com/v4/solutions/spot-solution/"
GW_NEXT  = "https://api.gtowizard.com/v4/game-points/next-actions/"
CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))

GAMETYPE = "MTTGeneral"
# Depths validos descobertos para spots preflop diversos. Snap pro mais próximo.
VALID_DEPTHS = [10, 12, 14, 16, 18, 20, 25, 30, 40, 50, 60, 80, 100]

# Posicoes do PokerStars 9-max em ordem de acao preflop
POS_ORDER_9 = ["UTG", "UTG+1", "UTG+2", "MP", "MP1", "MP2", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
# Aliases — qualquer alias mapeia para o canonical (que respeita _POS_NORM do projeto)
POS_ALIAS = {"UTG+2": "UTG+2", "UTG+1": "UTG+1", "MP1": "MP", "MP2": "HJ", "EP": "UTG"}


def snap_depth(stack_bb: float) -> float:
    snap = min(VALID_DEPTHS, key=lambda d: abs(d - round(stack_bb)))
    return snap + 0.125


def normalize_pos(raw: str) -> str:
    raw = (raw or "").upper().strip()
    return POS_ALIAS.get(raw, raw)


# ── Encoder: hand history → preflop_actions GW ──────────────────────────────
def encode_preflop_actions(raw_text: str, hand_id: str, hero_name: str) -> tuple[str, int, str] | None:
    """
    Lê o raw_text do hand_id e retorna a sequência preflop_actions ATÉ a primeira
    ação do hero, no formato GW (F-R2.3-F-C-...).

    Args:
        raw_text: texto completo do torneio (concatena múltiplas hands)
        hand_id:  PokerStars hand id (ex: '258867027972')
        hero_name: nome do hero no PokerStars (ex: 'phpro')
    Returns:
        (preflop_actions, num_players, hero_position) ou None se falhar
    """
    # Localizar o bloco da hand
    idx = raw_text.find(hand_id)
    if idx < 0:
        return None
    end = raw_text.find("PokerStars Hand", idx + 50)
    if end < 0:
        end = idx + 5000
    block = raw_text[idx - 30:end]

    # Extrair seção entre HOLE CARDS e FLOP/SUMMARY
    s = block.find("*** HOLE CARDS ***")
    if s < 0:
        return None
    e_flop = block.find("*** FLOP ***", s)
    e_sum  = block.find("*** SUMMARY ***", s)
    e = e_flop if e_flop > 0 else e_sum
    if e < 0:
        return None
    preflop_section = block[s:e]

    # BB amount para normalizar tamanhos
    m_bb = re.search(r"posts big blind (\d+)", block)
    if not m_bb:
        return None
    bb = float(m_bb.group(1))

    # Listar acoes preflop até a primeira ação do hero
    actions = []
    hero_pos = None
    for line in preflop_section.splitlines():
        # Match: "Player: action [amount [to amount]]"
        m = re.match(r"^([^:\n]+?):\s+(folds|calls|raises|checks|bets)\s*(.*)$", line.strip())
        if not m:
            continue
        player = m.group(1).strip()
        act    = m.group(2)
        rest   = m.group(3)

        if player == hero_name:
            # Achamos a primeira ação do hero — parar
            return ("-".join(actions), len(actions) + 1, hero_pos or "?")

        if act == "folds":
            actions.append("F")
        elif act == "calls":
            actions.append("C")
        elif act == "raises":
            # "raises X to Y" -> Y / BB
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
    return ("-".join(actions), len(actions) + 1, hero_pos or "?")


def gw_label_from_freq(freq: float) -> str:
    """Aplica thresholds (mesmos do projeto)."""
    if freq >= 0.60: return "gto_correct"
    if freq >= 0.30: return "gto_mixed"
    if freq >= 0.10: return "gto_minor_deviation"
    return "gto_critical"


def norm_act(a: str) -> str:
    a = (a or "").lower().rstrip("s")
    return {"raise": "bet", "bet": "bet", "all_in": "allin", "allin": "allin",
            "jam": "allin", "fold": "fold", "call": "call", "check": "check"}.get(a, a)


def make_spot_hash(street: str, position: str, hero_hand: str,
                   stack_bucket: str, preflop_actions: str) -> str:
    raw = f"{street}|{position}|{hero_hand}|{stack_bucket}|{preflop_actions}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── DB sampling ─────────────────────────────────────────────────────────────
def sample_spots(conn, limit: int, user_id: int | None) -> list[dict]:
    where = "d.street='preflop' AND d.hero_cards IS NOT NULL AND d.hero_cards != ''"
    params: list = []
    if user_id is not None:
        where += " AND t.user_id = ?"
        params.append(user_id)

    rows = conn.execute(f"""
        SELECT d.id, d.hand_id, d.position, d.stack_bb, d.facing_bet, d.is_3bet,
               d.action_taken, d.best_action, d.label, d.gto_label, d.gto_action,
               d.hero_cards, t.id as tid, t.user_id, t.hero, t.raw_text
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE {where}
        ORDER BY RANDOM()
        LIMIT ?
    """, (*params, limit * 3)).fetchall()  # 3x oversample para descartar não-encodáveis

    seen_pos_stack = defaultdict(int)
    out = []
    for r in rows:
        if len(out) >= limit:
            break
        # Diversificar por (position, stack bucket coarse)
        stk = int(float(r["stack_bb"] or 20) / 10) * 10
        key = (r["position"], stk)
        if seen_pos_stack[key] >= max(2, limit // 30):
            continue
        seen_pos_stack[key] += 1
        out.append(dict(r))
    return out


# ── Persistir em gto_nodes ──────────────────────────────────────────────────
def upsert_gto_node(conn, spot_hash: str, street: str, position: str,
                    hero_hand: str, stack_bucket: str, gto_action: str,
                    gto_freq: float, strategy: dict, exploitability: float | None,
                    source: str = "gto_wizard") -> bool:
    """Insert ou update. Retorna True se foi insert (novo)."""
    existing = conn.execute(
        "SELECT id FROM gto_nodes WHERE spot_hash=?", (spot_hash,)
    ).fetchone()
    payload = (
        spot_hash, street, position, "[]", hero_hand, stack_bucket,
        gto_action, gto_freq, exploitability, source,
        json.dumps(strategy, ensure_ascii=False), 0,
    )
    if existing:
        conn.execute("""
            UPDATE gto_nodes SET gto_action=?, gto_freq=?, exploitability_pct=?,
                                 source=?, strategy_json=?, is_aggregate=?
            WHERE spot_hash=?
        """, payload[6:] + (spot_hash,))
        return False
    conn.execute("""
        INSERT INTO gto_nodes (spot_hash, street, position, board, hero_hand,
                                stack_bucket, gto_action, gto_freq,
                                exploitability_pct, source, strategy_json, is_aggregate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, payload)
    return True


# ── Main ────────────────────────────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--user-id", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sleep", type=float, default=0.6)
    args = p.parse_args()

    # Conectar ao Chrome via CDP
    try:
        from playwright.sync_api import sync_playwright
        import requests as _req
    except ImportError:
        print("ERRO: pip install playwright requests")
        return 1

    from database.schema import get_conn
    db = get_conn()

    spots = sample_spots(db, args.limit, args.user_id)
    print(f"Samplados {len(spots)} spots preflop\n")
    if not spots:
        return 0

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        except Exception as e:
            print(f"ERRO CDP: {e}")
            return 1
        ctx  = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Captura auth headers
        captured = {}
        def on_req(req):
            if "api.gtowizard.com" in req.url and not captured:
                h = dict(req.headers)
                if "authorization" in h:
                    captured.update(h)
        page.on("request", on_req)
        try:
            page.goto(f"{GW_APP}/solutions", timeout=20000, wait_until="domcontentloaded")
        except Exception:
            pass
        deadline = time.time() + 30
        while not captured and time.time() < deadline:
            page.wait_for_timeout(300)
        page.remove_listener("request", on_req)
        if not captured.get("authorization"):
            print("ERRO: sem authorization capturado")
            return 1
        print(f"[auth] OK ...{captured['authorization'][-20:]}\n")

        session = _req.Session()
        session.headers.update({
            "authorization": captured["authorization"],
            "accept": "application/json, text/plain, */*",
            "origin": GW_APP, "referer": GW_APP + "/",
            "gwclientid": captured.get("gwclientid", ""),
            "user-agent": captured.get("user-agent", "Mozilla/5.0"),
        })

        stats = {
            "total": 0, "encoded": 0, "gw_200": 0, "gw_204": 0, "gw_403": 0, "gw_404": 0,
            "agree": 0, "disagree": 0, "no_stored": 0, "inserted": 0, "updated": 0,
        }
        details = []

        print(f"{'ID':>6} {'POS':<5} {'STK':>5} {'HAND':<5} {'STORED':<22} {'GW_TOP':<8} {'GW_FREQ':>7} {'STATUS'}")
        print("-" * 90)
        for spot in spots:
            stats["total"] += 1
            enc = encode_preflop_actions(spot["raw_text"], spot["hand_id"], spot["hero"])
            if not enc:
                details.append({**{k: spot[k] for k in ["id", "position"]}, "status": "encode_fail"})
                continue
            prefl, num_players, _ = enc
            stats["encoded"] += 1

            stack = float(spot["stack_bb"] or 20)
            depth = snap_depth(stack)
            hand_short = spot["hero_cards"].replace(" ", "")[:5]
            pos = normalize_pos(spot["position"])

            params = {
                "gametype": GAMETYPE, "depth": depth, "stacks": "",
                "preflop_actions": prefl, "flop_actions": "", "turn_actions": "",
                "river_actions": "", "board": "",
            }
            r = session.get(GW_SPOT, params=params, timeout=20)
            time.sleep(args.sleep)
            if r.status_code == 200:
                stats["gw_200"] += 1
                data = r.json()
            elif r.status_code == 204:
                stats["gw_204"] += 1; data = None
            elif r.status_code == 403:
                stats["gw_403"] += 1; data = None
            elif r.status_code == 404:
                stats["gw_404"] += 1; data = None
            else:
                data = None

            if not data:
                print(f"{spot['id']:>6} {pos:<5} {stack:>5.1f} {hand_short:<5} "
                      f"{(spot['gto_label'] or '-'):<22} {'-':<8} {'-':>7} "
                      f"http={r.status_code} prefl={prefl[:25]}")
                details.append({"id": spot["id"], "pos": pos, "status": f"gw_{r.status_code}",
                                "preflop_actions": prefl})
                continue

            # Parse estrategia agregada por familia
            strategy: dict[str, float] = {}
            for a in data.get("action_solutions", []):
                t = norm_act(a.get("action", {}).get("type", ""))
                f = float(a.get("total_frequency", 0))
                strategy[t] = strategy.get(t, 0) + f
            if not strategy:
                continue
            gw_top = max(strategy, key=lambda k: strategy[k])
            gw_top_freq = strategy[gw_top]

            # Comparar com stored
            stored_action = (spot["gto_action"] or "").lower()
            stored_label  = spot["gto_label"]
            if not stored_label:
                stats["no_stored"] += 1
                agree_mark = "no_stored"
            else:
                # Acordo se top_action bate (com tolerância para bet=raise)
                stored_norm = norm_act(stored_action)
                if stored_norm == gw_top:
                    stats["agree"] += 1; agree_mark = "AGREE"
                else:
                    stats["disagree"] += 1; agree_mark = "DIFF"

            # Persist em gto_nodes
            if not args.dry_run:
                stack_bucket = f"{int(snap_depth(stack) - 0.125)}bb"
                spot_hash = make_spot_hash("preflop", pos, hand_short, stack_bucket, prefl)
                inserted = upsert_gto_node(
                    db, spot_hash, "preflop", pos, hand_short, stack_bucket,
                    gw_top, gw_top_freq, strategy,
                    exploitability=data.get("exploitability"),
                )
                if inserted:
                    stats["inserted"] += 1
                else:
                    stats["updated"] += 1

            print(f"{spot['id']:>6} {pos:<5} {stack:>5.1f} {hand_short:<5} "
                  f"{(stored_label or '-'):<22} {gw_top:<8} {gw_top_freq:>7.3f} "
                  f"[{agree_mark}] prefl={prefl[:20]}")
            details.append({
                "id": spot["id"], "pos": pos, "stack": stack, "hand": hand_short,
                "preflop_actions": prefl, "stored_label": stored_label,
                "stored_action": stored_action, "gw_strategy": strategy,
                "gw_top": gw_top, "gw_top_freq": gw_top_freq, "agree": agree_mark,
            })

        if not args.dry_run:
            db.commit()
        db.close()

        # Relatorio
        report = {"stats": stats, "details": details, "params": {
            "gametype": GAMETYPE, "valid_depths": VALID_DEPTHS, "limit": args.limit,
        }}
        report_path = SCRIPT_DIR / "benchmark_preflop_report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        print(f"\n{'=' * 60}")
        print("STATS:", json.dumps(stats, indent=2))
        print(f"Relatorio: {report_path}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
