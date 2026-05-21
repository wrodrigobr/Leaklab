"""
validate_nodes_vs_gw.py — Valida/enriquece nós e cobre decisões via servidor GTO Wizard (GCP).

Chama POST /gto-wizard no servidor GCP (gto_wizard_client.query_spot).
Não requer token de browser — o servidor já tem tudo.

Requer no .env (ou ambiente):
    GTO_SOLVER_URL      = http://34.70.251.42:8765
    GTO_SOLVER_API_KEY  = ...
    GTO_WIZARD_ENABLED  = true

Modos:
  (padrão)          Valida nós solver_cli existentes:
                      1. Exploit > 5%  →  2. Sem strategy_json  →  3. Amostra ~10%
  --new-decisions   Cobre decisões postflop sem nenhum nó GTO (GW first pipeline)

Uso:
    python scripts/validate_nodes_vs_gw.py --dry-run               # lista o que faria
    python scripts/validate_nodes_vs_gw.py --apply                 # valida nós existentes
    python scripts/validate_nodes_vs_gw.py --apply --limit 50
    python scripts/validate_nodes_vs_gw.py --apply --high-exploit-only
    python scripts/validate_nodes_vs_gw.py --apply --no-strategy-only
    python scripts/validate_nodes_vs_gw.py --apply --sample-pct 0.10
    python scripts/validate_nodes_vs_gw.py --street flop
    python scripts/validate_nodes_vs_gw.py --new-decisions --apply
    python scripts/validate_nodes_vs_gw.py --new-decisions --apply --limit 100
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# Força habilitação do cliente GW para este script
os.environ["GTO_WIZARD_ENABLED"] = "true"

from database.schema import get_conn
from leaklab.gto_wizard_client import query_spot as gw_query, get_status as gw_status

RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"


def _c(text, code):
    return f"{code}{text}{RESET}" if sys.stdout.isatty() else str(text)


# ── Helpers de dados ───────────────────────────────────────────────────────────

_BUCKET_MID = {
    "0-10bb":    8.0,
    "10-20bb":  15.0,
    "20-35bb":  27.0,
    "20-40bb":  30.0,
    "35-60bb":  47.0,
    "40bb+":    50.0,
    "60-100bb": 75.0,
    "100bb+":  100.0,
}


def _bucket_to_bb(bucket: str) -> float:
    return _BUCKET_MID.get(bucket or "", 30.0)


def _bb_to_bucket(stack_bb: float) -> str:
    if stack_bb >= 100: return "100bb+"
    if stack_bb >= 60:  return "60-100bb"
    if stack_bb >= 35:  return "35-60bb"
    if stack_bb >= 20:  return "20-35bb"
    if stack_bb >= 10:  return "10-20bb"
    return "0-10bb"


def _parse_board(board_raw) -> list[str]:
    if not board_raw:
        return []
    if isinstance(board_raw, str):
        try:
            parsed = json.loads(board_raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return board_raw.strip().split()
    return list(board_raw)


def _norm_action(a: str) -> str:
    a = (a or "").lower().strip()
    if a in ("shove", "jam", "allin", "all-in", "all_in", "all_in"):
        return "jam"
    if a.startswith("bet"):
        return "bet"
    if a.startswith("raise"):
        return "raise"
    return a


def _gw_to_strategy_json(strategy: list[dict]) -> dict:
    """Converte lista strategy do gw_query para formato strategy_json do banco."""
    result = {}
    for s in strategy:
        action   = (s.get("action") or "").lower().strip()
        freq     = float(s.get("frequency") or 0)
        betsize  = s.get("betsize_bb")

        if action in ("all_in", "allin", "shove", "jam"):
            key = "jam"
        elif action in ("bet", "raise") and betsize:
            key = f"bet_{int(betsize)}bb" if float(betsize) == int(float(betsize)) else f"bet_{betsize:.1f}bb"
        else:
            key = action

        if key in result:
            result[key]["frequency"] += freq
        else:
            result[key] = {"frequency": freq}
    return result


def _top_action(strategy_json: dict) -> tuple[str, float]:
    if not strategy_json:
        return "", 0.0
    top = max(strategy_json, key=lambda k: strategy_json[k].get("frequency", 0))
    return top, strategy_json[top].get("frequency", 0)


def _strat_str(strategy_json: dict) -> str:
    return " | ".join(
        f"{k} {v['frequency']*100:.0f}%"
        for k, v in sorted(strategy_json.items(), key=lambda x: -x[1]["frequency"])
    )


# ── Fetch nodes ────────────────────────────────────────────────────────────────

def fetch_nodes(conn, args) -> tuple[list[dict], int, int, int]:
    rows = conn.execute("""
        SELECT id, spot_hash, street, position, board, stack_bucket,
               gto_action, gto_freq, exploitability_pct, source, strategy_json
        FROM gto_nodes
        WHERE source = 'solver_cli'
    """ + (f" AND street = '{args.street}'" if args.street else "")).fetchall()

    all_nodes = [dict(r) for r in rows]

    high_exploit = [n for n in all_nodes
                    if n.get("exploitability_pct") is not None and n["exploitability_pct"] > 5.0]
    no_strategy  = [n for n in all_nodes
                    if not n.get("strategy_json") and n not in high_exploit]
    rest         = [n for n in all_nodes
                    if n not in high_exploit and n not in no_strategy]

    selected: list[dict] = []
    if args.high_exploit_only:
        selected = high_exploit
    elif args.no_strategy_only:
        selected = no_strategy
    else:
        selected.extend(high_exploit)
        selected.extend(no_strategy)
        sample_n = max(1, int(len(rest) * args.sample_pct))
        random.seed(42)
        selected.extend(random.sample(rest, min(sample_n, len(rest))))

    if args.limit:
        selected = selected[:args.limit]

    return selected, len(high_exploit), len(no_strategy), len(rest)


# ── Inserir nó GW ──────────────────────────────────────────────────────────────

def _insert_gw_node(conn, spot_hash: str, street: str, position: str,
                    board_cards: list, stack_bb: float,
                    strategy_json: dict) -> None:
    gw_top, gw_top_freq = _top_action(strategy_json)
    strat_str            = json.dumps(strategy_json)
    bucket               = _bb_to_bucket(stack_bb)
    _street_cards        = {"flop": 3, "turn": 4, "river": 5}
    board_for_hash       = board_cards[:_street_cards.get(street, len(board_cards))]

    existing = conn.execute(
        "SELECT id FROM gto_nodes WHERE spot_hash = ?", (spot_hash,)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE gto_nodes
               SET gto_action=?, gto_freq=?, strategy_json=?, source='gto_wizard'
               WHERE spot_hash=?""",
            (gw_top, gw_top_freq, strat_str, spot_hash)
        )
    else:
        conn.execute(
            """INSERT INTO gto_nodes
               (spot_hash, street, position, board, hero_hand, stack_bucket,
                gto_action, gto_freq, strategy_json, source)
               VALUES (?,?,?,?,?,?,?,?,?,'gto_wizard')""",
            (
                spot_hash, street, position,
                json.dumps(board_for_hash), "[]", bucket,
                gw_top, gw_top_freq, strat_str,
            )
        )


# ── Modo padrão: validar nós solver_cli ───────────────────────────────────────

def run_validate_nodes(args, conn):
    nodes, n_exploit, n_no_strat, n_rest = fetch_nodes(conn, args)

    print(f"\n{'='*70}")
    print(f"Nós solver_cli: {n_exploit} exploit>5% | {n_no_strat} sem strategy | {n_rest} outros")
    print(f"Selecionados: {len(nodes)} nós")
    if args.dry_run:
        print("[DRY RUN]")
    print(f"{'='*70}\n")

    updated   = 0
    enriched  = 0
    divergent = 0
    agreed    = 0
    no_resp   = 0

    for i, node in enumerate(nodes, 1):
        street  = node.get("street", "?")
        pos     = node.get("position", "?")
        bucket  = node.get("stack_bucket", "?")
        exploit = node.get("exploitability_pct")
        stored  = _norm_action(node.get("gto_action") or "")
        stack_bb = _bucket_to_bb(bucket)

        board_cards = _parse_board(node.get("board"))
        _sc = {"flop": 3, "turn": 4, "river": 5}
        board = board_cards[:_sc.get(street, len(board_cards))]

        exp_str = f"{exploit:.1f}%" if exploit is not None else "n/a"
        print(f"[{i:3d}/{len(nodes)}] #{node['id']:5d} {street:5s} {pos:4s} {bucket:10s} "
              f"exploit={exp_str:6s}  stored={stored}", end="")

        if args.dry_run:
            print(f"  → stack={stack_bb:.0f}bb board={board} [dry-run]")
            continue

        time.sleep(0.5)
        resp = gw_query(street=street, position=pos, board=board,
                        hero_stack_bb=stack_bb, facing_size_bb=0.0)
        if not resp or not resp.get("found"):
            print(f"  {_c('SEM RESPOSTA', RED)}")
            no_resp += 1
            continue

        gw_strategy = _gw_to_strategy_json(resp["strategy"])
        if not gw_strategy:
            print(f"  {_c('STRATEGY VAZIO', RED)}")
            no_resp += 1
            continue

        gw_top, gw_freq = _top_action(gw_strategy)
        gw_action       = _norm_action(gw_top)

        match = (gw_action == stored or
                 {gw_action, stored} <= {"bet", "raise"})

        if match:
            agreed += 1
            verdict = _c("OK", GREEN)
        else:
            divergent += 1
            verdict = _c(f"DIVERG stored={stored} gw={gw_action}", RED)

        print(f"  {verdict}  [{_strat_str(gw_strategy)}]")

        if not args.apply:
            continue

        strat_str = json.dumps(gw_strategy)
        if not match:
            conn.execute(
                """UPDATE gto_nodes
                   SET gto_action=?, gto_freq=?, strategy_json=?, source='gto_wizard'
                   WHERE id=?""",
                (gw_top, gw_freq, strat_str, node["id"])
            )
            updated += 1
        else:
            conn.execute(
                "UPDATE gto_nodes SET strategy_json=?, source='gto_wizard' WHERE id=?",
                (strat_str, node["id"])
            )
            enriched += 1

    if args.apply:
        conn.commit()

    print(f"\n{'='*70}")
    print(f"Respondidos: {len(nodes) - no_resp} | Sem resp: {no_resp}")
    print(f"OK: {agreed} | Divergência: {divergent}")
    if args.apply:
        print(f"Atualizados (ação corrigida): {updated}")
        print(f"Enriquecidos (strategy_json): {enriched}")
    else:
        print("Use --apply para salvar.")
    print(f"{'='*70}")


# ── Modo --new-decisions: cobrir decisões sem nó ──────────────────────────────

def run_new_decisions(args, conn):
    from leaklab.gto_utils import compute_spot_hash
    from database.repositories import get_gto_node

    street_filter = f" AND d.street = '{args.street}'" if args.street else ""
    rows = conn.execute(f"""
        SELECT d.id, d.street, d.position, d.board, d.hero_cards,
               d.stack_bb, d.facing_bet, d.pot_size
        FROM decisions d
        WHERE d.street IN ('flop','turn','river')
          AND d.board IS NOT NULL AND d.stack_bb IS NOT NULL
          {street_filter}
        ORDER BY d.id DESC
    """).fetchall()

    # Filtrar só as sem nó GTO
    uncovered = []
    seen = set()
    for row in rows:
        r = dict(row)
        board = _parse_board(r.get("board"))
        if not board or len(board) < 3:
            continue
        street  = r.get("street", "")
        pos     = (r.get("position") or "BTN").upper()
        stack   = float(r.get("stack_bb") or 20.0)
        facing  = float(r.get("facing_bet") or 0.0)
        hc      = r.get("hero_cards") or ""
        hero_h  = hc.split() if " " in hc else [hc[i:i+2] for i in range(0, len(hc), 2) if hc[i:i+2]] if hc else []

        _sc = {"flop": 3, "turn": 4, "river": 5}
        bfh = board[:_sc.get(street, len(board))]

        h1 = compute_spot_hash(street, pos, bfh, hero_h, stack, facing)
        h2 = compute_spot_hash(street, pos, bfh, [],     stack, facing)

        if h2 in seen:
            continue
        if get_gto_node(h1) or get_gto_node(h2):
            seen.add(h2)
            continue

        seen.add(h2)
        uncovered.append({
            "decision_id": r["id"],
            "street":      street,
            "position":    pos,
            "board":       board,
            "board_hash":  bfh,
            "stack_bb":    stack,
            "facing_bb":   facing,
            "pot_bb":      float(r.get("pot_size") or 0),
            "spot_hash":   h2,
            "num_players": int(r.get("num_players") or 9),
        })

    if args.limit:
        uncovered = uncovered[:args.limit]

    print(f"\n{'='*70}")
    print(f"Decisões postflop sem nó GTO: {len(uncovered)}")
    if args.dry_run:
        print("[DRY RUN]")
    print(f"{'='*70}\n")

    inserted  = 0
    no_resp   = 0

    for i, dec in enumerate(uncovered, 1):
        street      = dec["street"]
        pos         = dec["position"]
        board       = dec["board_hash"]
        stack_bb    = dec["stack_bb"]
        facing      = dec["facing_bb"]
        pot_bb      = dec["pot_bb"]
        num_players = dec.get("num_players", 9)

        board_str = " ".join(board)
        print(f"[{i:3d}/{len(uncovered)}] #{dec['decision_id']:6d} {street:5s} {pos:4s} "
              f"{stack_bb:.0f}bb {num_players}p [{board_str}]", end="")

        if args.dry_run:
            print("  [dry-run]")
            continue

        time.sleep(0.5)
        resp = gw_query(street=street, position=pos, board=board,
                        hero_stack_bb=stack_bb, facing_size_bb=facing, pot_bb=pot_bb,
                        num_players=num_players)
        if not resp or not resp.get("found"):
            print(f"  {_c('SEM RESPOSTA', RED)}")
            no_resp += 1
            continue

        gw_strategy = _gw_to_strategy_json(resp["strategy"])
        if not gw_strategy:
            print(f"  {_c('STRATEGY VAZIO', RED)}")
            no_resp += 1
            continue

        gw_top, gw_freq = _top_action(gw_strategy)
        print(f"  {_c(gw_top, GREEN)} {gw_freq*100:.0f}%  [{_strat_str(gw_strategy)}]")

        if args.apply:
            _insert_gw_node(conn, dec["spot_hash"], street, pos,
                            board, stack_bb, gw_strategy)
            inserted += 1

    if args.apply:
        conn.commit()

    print(f"\n{'='*70}")
    print(f"Processadas: {len(uncovered) - no_resp} | Sem resposta: {no_resp}")
    if args.apply:
        print(f"Nós GTO Wizard inseridos/atualizados: {inserted}")
        print("Execute resync_gto_actions.py --apply para propagar labels às decisions.")
    else:
        print("Use --apply para salvar no banco.")
    print(f"{'='*70}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Valida nós e decisões via GTO Wizard (servidor GCP)")
    parser.add_argument("--apply",             action="store_true")
    parser.add_argument("--limit",             type=int,   default=None)
    parser.add_argument("--street",            default=None, help="flop | turn | river")
    parser.add_argument("--sample-pct",        type=float, default=0.10)
    parser.add_argument("--high-exploit-only", action="store_true")
    parser.add_argument("--no-strategy-only",  action="store_true")
    parser.add_argument("--new-decisions",     action="store_true",
                        help="Cobre decisões sem nó GTO (GW first pipeline)")
    parser.add_argument("--dry-run",           action="store_true")
    args = parser.parse_args()
    args.dry_run = args.dry_run or not args.apply

    # Verificar servidor
    if not args.dry_run:
        status = gw_status()
        if not status.get("auth_ok"):
            print(f"ERRO: servidor GTO Wizard indisponível ou sem auth.")
            print(f"  Status: {status}")
            print(f"  Verifique GTO_SOLVER_URL, GTO_SOLVER_API_KEY e GTO_WIZARD_ENABLED no .env")
            sys.exit(1)
        print(f"[GW] Servidor OK — {status.get('model','?')} | auth={status.get('auth_ok')}")

    conn = get_conn()
    try:
        if args.new_decisions:
            run_new_decisions(args, conn)
        else:
            run_validate_nodes(args, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
