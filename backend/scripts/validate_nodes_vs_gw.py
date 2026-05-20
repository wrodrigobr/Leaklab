"""
validate_nodes_vs_gw.py — Valida/enriquece nós solver_cli e cobre novas decisões via GTO Wizard.

Modos:
  (padrão)          Valida nós solver_cli existentes contra GTO Wizard:
                      1. Nós com exploitability > 5%
                      2. Nós sem strategy_json (enriquecer)
                      3. Amostra ~10% dos demais

  --new-decisions   Cobre decisões postflop sem nenhum nó GTO:
                      query GW first, fallback para solver_cli queue
                    → Execute ANTES de run_gto_worker.py para priorizar GTO Wizard

Requer GW_ACCESS_TOKEN no ambiente:
    $env:GW_ACCESS_TOKEN = 'eyJ...'   (Bearer token do DevTools do browser)

Uso:
    python scripts/validate_nodes_vs_gw.py                          # dry-run (nós existentes)
    python scripts/validate_nodes_vs_gw.py --apply                  # aplica ao banco
    python scripts/validate_nodes_vs_gw.py --apply --limit 50       # max 50 chamadas
    python scripts/validate_nodes_vs_gw.py --apply --high-exploit-only
    python scripts/validate_nodes_vs_gw.py --apply --no-strategy-only
    python scripts/validate_nodes_vs_gw.py --apply --sample-pct 0.10
    python scripts/validate_nodes_vs_gw.py --street flop            # filtrar por street
    python scripts/validate_nodes_vs_gw.py --new-decisions --apply  # novas decisões via GW
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
HAR_DEFAULT = BACKEND_DIR / "docs" / "app.gtowizard.com.har"

sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from database.schema import get_conn

# ── Stack bucket → BB médio ────────────────────────────────────────────────────
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

GW_STACK_SNAPS = [10, 13, 15, 17, 20, 25, 30, 40, 50, 75, 100]

PREFLOP_BY_POS = {
    "UTG":   "R2.3-F-F-F-F-F-F-C",
    "UTG+1": "F-R2.3-F-F-F-F-F-C",
    "UTG+2": "F-F-R2.3-F-F-F-F-C",
    "LJ":    "F-F-R2.3-F-F-F-F-C",
    "HJ":    "F-F-F-R2.3-F-F-F-C",
    "CO":    "F-F-F-F-R2.3-F-F-C",
    "BTN":   "F-F-F-F-F-R2.3-F-C",
    "SB":    "F-F-F-F-F-F-R2.3-C",
    "BB":    "F-F-F-F-F-R2.3-F-C",
    "MP":    "F-F-R2.3-F-F-F-F-C",
    "EP":    "R2.3-F-F-F-F-F-F-C",
}

GW_GAMETYPE = "MTTGeneral"

RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"


def _c(text, code):
    return f"{code}{text}{RESET}" if sys.stdout.isatty() else str(text)


def _nearest_snap(stack_bb: float) -> float:
    return min(GW_STACK_SNAPS, key=lambda s: abs(s - stack_bb))


def _bucket_to_bb(bucket: str) -> float:
    return _BUCKET_MID.get(bucket, 30.0)


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


def _board_to_gw(cards: list[str]) -> str:
    """Converte lista de cartas para string GTO Wizard: 'Kc', 'Qh' → 'KcQh'."""
    result = []
    for c in cards:
        c = c.strip()
        if len(c) >= 2:
            result.append(c[0].upper() + c[1].lower())
    return "".join(result)


def build_gw_params(node: dict) -> Optional[dict]:
    """Converte um nó gto_nodes em parâmetros para a API GTO Wizard."""
    street   = (node.get("street") or "").lower()
    position = (node.get("position") or "BTN").upper()

    board_cards = _parse_board(node.get("board"))
    if not board_cards or len(board_cards) < 3:
        return None

    preflop_str = PREFLOP_BY_POS.get(position)
    if not preflop_str:
        return None

    stack_bb = _bucket_to_bb(node.get("stack_bucket") or "")
    snap     = _nearest_snap(stack_bb)
    depth    = snap + 0.125  # fracional = estado MTT com antes

    # Board: inclui todas as cartas do street atual
    _street_cards = {"flop": 3, "turn": 4, "river": 5}
    n_cards   = _street_cards.get(street, 3)
    board_str = _board_to_gw(board_cards[:n_cards])
    if not board_str or len(board_str) < 6:
        return None

    # Action sequences — assumimos check-check em todos os streets anteriores
    # (as nodes sem facing_bet são first-to-act)
    return {
        "gametype":        GW_GAMETYPE,
        "depth":           depth,
        "stacks":          "",
        "preflop_actions": preflop_str,
        "flop_actions":    "",
        "turn_actions":    "",
        "river_actions":   "",
        "board":           board_str,
        # campos privados para display
        "_street":    street,
        "_position":  position,
        "_snap_bb":   snap,
        "_board_str": board_str,
    }


def _gw_to_strategy_json(action_solutions: list) -> dict:
    """Converte action_solutions do GTO Wizard para o formato strategy_json do leaklab."""
    result = {}
    for sol in action_solutions:
        action_obj  = sol.get("action", {})
        action_type = (action_obj.get("type") or "").lower()
        betsize     = float(action_obj.get("betsize") or 0)
        allin       = bool(action_obj.get("allin", False))
        freq        = float(sol.get("total_frequency") or 0)

        if allin or action_type in ("all_in", "allin"):
            key = "jam"
        elif action_type in ("bet", "raise"):
            key = f"bet_{betsize:.0f}" if betsize > 0 else "bet"
        else:
            key = action_type

        if key in result:
            result[key]["frequency"] += freq
        else:
            result[key] = {"frequency": freq}

    return result


def _top_from_strategy(strategy: dict) -> tuple[str, float]:
    """Retorna (ação, frequência) da ação dominante."""
    if not strategy:
        return "", 0.0
    top = max(strategy, key=lambda k: strategy[k].get("frequency", 0))
    return top, strategy[top].get("frequency", 0)


def _norm_action(a: str) -> str:
    a = (a or "").lower().strip()
    if a in ("shove", "jam", "allin", "all-in", "all_in"):
        return "jam"
    if a.startswith("bet"):
        return "bet"
    if a.startswith("raise"):
        return "bet"
    return a


def fetch_nodes(conn, args) -> list[dict]:
    """Busca nós solver_cli do banco, priorizados conforme argumentos."""
    rows = conn.execute("""
        SELECT id, spot_hash, street, position, board, hero_hand,
               stack_bucket, gto_action, gto_freq, exploitability_pct,
               source, strategy_json
        FROM gto_nodes
        WHERE source = 'solver_cli'
        ORDER BY id
    """).fetchall()

    all_nodes = [dict(r) for r in rows]

    if args.street:
        all_nodes = [n for n in all_nodes if (n.get("street") or "").lower() == args.street.lower()]

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
        # Amostra aleatória dos restantes
        sample_n = max(1, int(len(rest) * args.sample_pct))
        random.seed(42)
        selected.extend(random.sample(rest, min(sample_n, len(rest))))

    if args.limit:
        selected = selected[:args.limit]

    return selected, len(high_exploit), len(no_strategy), len(rest)


def _build_client(dry_run: bool):
    """Inicializa GWClient ou retorna None se dry_run."""
    access = os.environ.get("GW_ACCESS_TOKEN", "").strip()
    if not access and not dry_run:
        print(
            "ERRO: GW_ACCESS_TOKEN não definido.\n"
            "Copie o Bearer token do DevTools:\n"
            "  DevTools → Network → qualquer request api.gtowizard.com → Headers → Authorization\n"
            "  $env:GW_ACCESS_TOKEN = 'eyJ...'"
        )
        sys.exit(1)

    if dry_run:
        return None

    from scripts.benchmark_gtowizard_live import GWAuth, GWClient
    auth = GWAuth.from_access_token(access)
    anal = GWAuth.anal_id_from_har(HAR_DEFAULT) if HAR_DEFAULT.is_file() else ""
    return GWClient(auth, anal)


def _query_gw(client, params: dict) -> Optional[dict]:
    """Chama GW com rate limit. Retorna strategy_json dict ou None."""
    time.sleep(0.8)
    gw_params = {k: v for k, v in params.items() if not k.startswith("_")}
    resp = client.spot_solution(gw_params)
    if not resp:
        return None
    solutions = resp.get("action_solutions", [])
    if not solutions:
        return None
    return _gw_to_strategy_json(solutions)


def _insert_gw_node(conn, spot_hash: str, street: str, position: str,
                    board_cards: list, stack_bb: float, facing_bb: float,
                    gw_strategy: dict) -> None:
    """Insere ou atualiza um nó GTO Wizard no banco."""
    gw_top, gw_top_freq = _top_from_strategy(gw_strategy)
    strategy_json_str   = json.dumps(gw_strategy)

    from leaklab.gto_utils import compute_spot_hash
    _street_cards  = {"flop": 3, "turn": 4, "river": 5}
    board_for_hash = board_cards[:_street_cards.get(street, len(board_cards))]

    # Deriva stack_bucket a partir do stack_bb
    if stack_bb >= 100:
        bucket = "100bb+"
    elif stack_bb >= 60:
        bucket = "60-100bb"
    elif stack_bb >= 35:
        bucket = "35-60bb"
    elif stack_bb >= 20:
        bucket = "20-35bb"
    elif stack_bb >= 10:
        bucket = "10-20bb"
    else:
        bucket = "0-10bb"

    try:
        conn.execute("""
            INSERT INTO gto_nodes
              (spot_hash, street, position, board, hero_hand, stack_bucket,
               gto_action, gto_freq, strategy_json, source)
            VALUES (?, ?, ?, ?, '[]', ?, ?, ?, ?, 'gto_wizard')
            ON CONFLICT(spot_hash) DO UPDATE SET
              gto_action    = excluded.gto_action,
              gto_freq      = excluded.gto_freq,
              strategy_json = excluded.strategy_json,
              source        = 'gto_wizard'
        """, (
            spot_hash, street, position,
            json.dumps(board_for_hash),
            bucket,
            gw_top, gw_top_freq,
            strategy_json_str,
        ))
    except Exception:
        # SQLite fallback: sem ON CONFLICT
        existing = conn.execute(
            "SELECT id FROM gto_nodes WHERE spot_hash = ?", (spot_hash,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE gto_nodes
                   SET gto_action=?, gto_freq=?, strategy_json=?, source='gto_wizard'
                   WHERE spot_hash=?""",
                (gw_top, gw_top_freq, strategy_json_str, spot_hash)
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
                    gw_top, gw_top_freq, strategy_json_str,
                )
            )


def run_new_decisions(args):
    """Modo --new-decisions: cobre decisões postflop sem nenhum nó GTO via GW primeiro."""
    client = _build_client(args.dry_run)

    from leaklab.gto_utils import compute_spot_hash
    from database.repositories import get_gto_node

    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT d.id, d.street, d.position, d.board, d.hero_cards,
                   d.stack_bb, d.facing_bet, d.pot_size
            FROM decisions d
            WHERE d.street IN ('flop','turn','river')
              AND d.board IS NOT NULL
              AND d.stack_bb IS NOT NULL
        """ + (" AND d.street = '" + args.street + "'" if args.street else "") + """
            ORDER BY d.id DESC
        """).fetchall()

        # Filtrar apenas decisões sem nó GTO
        uncovered = []
        seen_hashes = set()
        for row in rows:
            r = dict(row)
            board   = _parse_board(r.get("board"))
            if not board or len(board) < 3:
                continue
            street  = r.get("street", "")
            pos     = (r.get("position") or "BTN").upper()
            stack   = float(r.get("stack_bb") or 20.0)
            facing  = float(r.get("facing_bet") or 0.0)
            hand_raw = r.get("hero_cards") or ""
            if isinstance(hand_raw, str) and hand_raw.strip():
                _raw = hand_raw.strip()
                hero_h = _raw.split() if " " in _raw else [_raw[i:i+2] for i in range(0, len(_raw), 2)]
            else:
                hero_h = []

            _street_cards = {"flop": 3, "turn": 4, "river": 5}
            board_hash = board[:_street_cards.get(street, len(board))]

            h = compute_spot_hash(street, pos, board_hash, hero_h, stack, facing)
            h2 = compute_spot_hash(street, pos, board_hash, [], stack, facing)

            # Pular se já tem nó
            if h in seen_hashes or h2 in seen_hashes:
                continue
            if get_gto_node(h) or get_gto_node(h2):
                seen_hashes.add(h)
                seen_hashes.add(h2)
                continue

            seen_hashes.add(h)
            seen_hashes.add(h2)
            uncovered.append({
                "decision_id": r["id"],
                "street":      street,
                "position":    pos,
                "board":       board,
                "stack_bb":    stack,
                "facing_bet":  facing,
                "spot_hash":   h2,  # usar hash sem hero_hand para o nó (mais reutilizável)
            })

        if args.limit:
            uncovered = uncovered[:args.limit]

        print(f"\n{'='*70}")
        print(f"Decisões postflop sem nó GTO: {len(uncovered)}")
        if args.dry_run:
            print("[DRY RUN — sem chamadas ao GTO Wizard]")
        print(f"{'='*70}\n")

        inserted = 0
        skipped  = 0
        gw_errors = 0
        no_params = 0

        for i, dec in enumerate(uncovered, 1):
            street   = dec["street"]
            pos      = dec["position"]
            board    = dec["board"]
            stack_bb = dec["stack_bb"]
            snap_bb  = _nearest_snap(stack_bb)

            # Build node dict para reutilizar build_gw_params
            node_like = {
                "street":       street,
                "position":     pos,
                "board":        json.dumps(board),
                "stack_bucket": f"{snap_bb}bb",
            }
            params = build_gw_params(node_like)
            if not params:
                print(f"[{i:3d}/{len(uncovered)}] #{dec['decision_id']:6d} {street:5s} {pos:4s} "
                      f"{_c('SKIP: sem params', YELLOW)}")
                no_params += 1
                continue

            print(f"[{i:3d}/{len(uncovered)}] #{dec['decision_id']:6d} {street:5s} {pos:4s} "
                  f"board={params['_board_str']} snap={snap_bb}bb", end="")

            if args.dry_run:
                print("  [dry-run]")
                continue

            gw_strategy = _query_gw(client, params)
            if not gw_strategy:
                print(f"  {_c('ERR: GW sem resposta', RED)}")
                gw_errors += 1
                continue

            gw_top, gw_top_freq = _top_from_strategy(gw_strategy)
            strat_str = " | ".join(
                f"{k} {v['frequency']*100:.0f}%"
                for k, v in sorted(gw_strategy.items(), key=lambda x: -x[1]["frequency"])
            )
            print(f"  → {_c(gw_top, GREEN)} {gw_top_freq*100:.0f}%  [{strat_str}]")

            if args.apply:
                _insert_gw_node(
                    conn, dec["spot_hash"], street, pos,
                    board, stack_bb, dec["facing_bet"], gw_strategy
                )
                inserted += 1

        if args.apply:
            conn.commit()

        print(f"\n{'='*70}")
        print(f"Processadas: {len(uncovered) - no_params - gw_errors} | Erros GW: {gw_errors} | Sem params: {no_params}")
        if args.apply:
            print(f"Nós GTO Wizard inseridos: {inserted}")
            print("Execute run_gto_worker.py --enqueue para filas restantes (fallback solver_cli).")
        else:
            print("Use --apply para salvar no banco.")
        print(f"{'='*70}")

    finally:
        conn.close()


def run(args):
    if args.new_decisions:
        run_new_decisions(args)
        return

    client = _build_client(args.dry_run)

    conn = get_conn()
    try:
        nodes, n_exploit, n_no_strat, n_rest = fetch_nodes(conn, args)

        print(f"\n{'='*70}")
        print(f"Nós solver_cli: {n_exploit} exploit>5% | {n_no_strat} sem strategy | {n_rest} outros")
        print(f"Selecionados para validação: {len(nodes)} nós")
        if args.dry_run:
            print("[DRY RUN — sem chamadas ao GTO Wizard e sem escrita no banco]")
        print(f"{'='*70}\n")

        updated    = 0
        enriched   = 0
        divergent  = 0
        agreed     = 0
        no_params  = 0
        gw_errors  = 0

        for i, node in enumerate(nodes, 1):
            node_id = node["id"]
            street  = node.get("street", "?")
            pos     = node.get("position", "?")
            bucket  = node.get("stack_bucket", "?")
            exploit = node.get("exploitability_pct")
            stored_action = _norm_action(node.get("gto_action") or "")

            exploit_str = f"{exploit:.1f}%" if exploit is not None else "n/a"
            print(f"[{i:3d}/{len(nodes)}] #{node_id:5d} {street:5s} {pos:4s} {bucket:10s} "
                  f"exploit={exploit_str:6s}  stored={stored_action}", end="")

            params = build_gw_params(node)
            if not params:
                print(f"  {_c('SKIP: sem params válidos', YELLOW)}")
                no_params += 1
                continue

            if args.dry_run:
                print(f"  → board={params['_board_str']} snap={params['_snap_bb']}bb [dry-run]")
                continue

            gw_strategy = _query_gw(client, params)
            if not gw_strategy:
                print(f"  {_c('ERR: GW sem resposta', RED)}")
                gw_errors += 1
                continue

            gw_top, gw_top_freq = _top_from_strategy(gw_strategy)
            gw_action = _norm_action(gw_top)

            strat_str = " | ".join(
                f"{k} {v['frequency']*100:.0f}%"
                for k, v in sorted(gw_strategy.items(), key=lambda x: -x[1]["frequency"])
            )

            action_match = (gw_action == stored_action or
                            (stored_action == "bet" and gw_action in ("bet", "raise")) or
                            (gw_action == "bet" and stored_action in ("bet", "raise")))

            if action_match:
                agreed += 1
                verdict = _c("OK", GREEN)
            else:
                divergent += 1
                verdict = _c(f"DIVERG: gw={gw_action} stored={stored_action}", RED)

            print(f"  {verdict}  [{strat_str}]")

            if not args.apply:
                continue

            strategy_json_str = json.dumps(gw_strategy)

            # Atualiza nó: strategy_json sempre (enriquecimento)
            # gto_action e gto_freq: só se divergente (GW é mais confiável)
            if not action_match:
                conn.execute(
                    """UPDATE gto_nodes
                       SET gto_action = ?, gto_freq = ?, strategy_json = ?, source = 'gto_wizard'
                       WHERE id = ?""",
                    (gw_top, gw_top_freq, strategy_json_str, node_id)
                )
                updated += 1
            elif not node.get("strategy_json"):
                conn.execute(
                    "UPDATE gto_nodes SET strategy_json = ? WHERE id = ?",
                    (strategy_json_str, node_id)
                )
                enriched += 1
            else:
                # Já tem strategy_json e ação bate — apenas atualiza strategy com dados GW
                conn.execute(
                    "UPDATE gto_nodes SET strategy_json = ? WHERE id = ?",
                    (strategy_json_str, node_id)
                )
                enriched += 1

        if args.apply:
            conn.commit()

        print(f"\n{'='*70}")
        print(f"Validados: {len(nodes) - no_params - gw_errors} | Erros GW: {gw_errors} | Sem params: {no_params}")
        print(f"Concordância: {agreed} | Divergência: {divergent}")
        if args.apply:
            print(f"Atualizados (ação divergente → GW): {updated}")
            print(f"Enriquecidos (strategy_json adicionado): {enriched}")
        else:
            print("Use --apply para salvar mudanças no banco.")
        print(f"{'='*70}")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Valida nós solver_cli contra GTO Wizard")
    parser.add_argument("--apply",             action="store_true",
                        help="Aplica mudanças no banco (sem: dry-run)")
    parser.add_argument("--limit",             type=int, default=None,
                        help="Limita o total de nós a processar")
    parser.add_argument("--street",            default=None,
                        help="Filtra por street: flop, turn, river")
    parser.add_argument("--sample-pct",        type=float, default=0.10,
                        help="Fração dos nós 'outros' a amostrar (default 0.10 = 10%%)")
    parser.add_argument("--high-exploit-only", action="store_true",
                        help="Processa apenas nós com exploitability > 5%%")
    parser.add_argument("--no-strategy-only",  action="store_true",
                        help="Processa apenas nós sem strategy_json")
    parser.add_argument("--dry-run",           action="store_true",
                        help="Não chama GTO Wizard, apenas lista nós selecionados")
    parser.add_argument("--new-decisions",     action="store_true",
                        help="Modo GTO-first: cobre decisões sem nó GTO via GW antes do solver_cli")
    args = parser.parse_args()
    args.dry_run = args.dry_run or not args.apply

    run(args)


if __name__ == "__main__":
    main()
