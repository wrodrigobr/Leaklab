"""
fallback_gto_wizard.py — Fallback automático: spots sem GTO → GTO Wizard.

Fluxo:
  1. Busca decisões postflop com gto_label IS NULL (solver local não resolveu)
  2. Converte cada decisão num spot para o GTO Wizard
  3. Roda comparação via Playwright (Chrome CDP obrigatório)
  4. Salva estratégia em gto_nodes + atualiza gto_label/gto_action em decisions

Pré-requisito:
  Chrome rodando com CDP (python playwright_compare.py --start-browser)

Uso:
  cd backend
  python scripts/gto_validation/fallback_gto_wizard.py
  python scripts/gto_validation/fallback_gto_wizard.py --limit 20 --dry-run
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPTS_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

DB_PATH = BACKEND_DIR / "data" / "leaklab.db"

# Reutiliza constantes e funções do playwright_compare
from gto_validation.playwright_compare import (
    build_params, parse_strategy, run_comparison,
    _nearest_snap, _norm_board, GW_SPOT_SOL, GAMETYPE,
)


# ── Classificação gto_label (espelha _process_gto_hand_request em app.py) ──────

def _classify(action_taken: str, strategy: dict) -> tuple[str, str]:
    """Retorna (gto_label, gto_action) a partir da estratégia GTO."""
    if not strategy:
        return None, None

    top_action = max(strategy, key=lambda k: strategy[k])
    top_freq   = strategy[top_action]

    acted = (action_taken or '').lower().rstrip('s')
    # normalizar raise/allin
    acted = {'raise': 'bet', 'all-in': 'allin', 'jam': 'allin'}.get(acted, acted)

    freq = strategy.get(acted, 0.0)

    if freq >= 0.60:
        label = 'gto_correct'
    elif freq >= 0.30:
        label = 'gto_mixed'
    elif freq >= 0.10:
        label = 'gto_minor_deviation'
    else:
        label = 'gto_critical'

    return label, top_action


# ── Busca decisões sem GTO ─────────────────────────────────────────────────────

def _load_pending_decisions(limit: int = 0, street_filter: str = 'all') -> list[dict]:
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # NULL = nunca processado | wizard_pending = solver local falhou/não suportado
    where = ["d.street IN ('flop','turn','river')",
             "(d.gto_label IS NULL OR d.gto_label = 'wizard_pending')"]
    if street_filter != 'all':
        where.append(f"d.street = '{street_filter}'")

    q = f"""
        SELECT d.id, d.street, d.position, d.board, d.stack_bb,
               d.facing_bet, d.pot_size, d.action_taken, d.best_action,
               d.hero_cards, t.site
        FROM decisions d
        JOIN tournaments t ON t.id = d.tournament_id
        WHERE {' AND '.join(where)}
        ORDER BY d.id
    """
    if limit:
        q += f" LIMIT {limit}"

    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Converte decisão → spot para build_params ──────────────────────────────────

def _decision_to_spot(d: dict) -> dict | None:
    """Converte um dict de decision para o formato de spot do playwright_compare."""
    try:
        board_list = json.loads(d['board']) if isinstance(d['board'], str) else d['board']
    except Exception:
        return None

    if not board_list:
        return None

    board_str    = ' '.join(board_list)
    stack_bb     = float(d['stack_bb'] or 20)
    facing_bet   = float(d['facing_bet'] or 0)
    pot_size     = float(d['pot_size'] or 2)
    stack_bucket = _nearest_snap(stack_bb)

    return {
        'decision_id':        d['id'],
        'action_taken':       d['action_taken'],
        'best_action':        d['best_action'],
        'street':             d['street'],
        'position':           d['position'],
        'board':              board_str,
        'board_list':         board_list,
        'stack_bb':           stack_bb,
        'stack_bucket':       stack_bucket,
        'facing_bet':         facing_bet,
        'pot_size':           pot_size,
        # campos extras usados por build_params
        'spot_id':            f"dec_{d['id']}",
        'example_best_action': d['best_action'],
        'our_label':          None,
        'occurrences':        1,
    }


# ── Salva resultados no banco ──────────────────────────────────────────────────

def _save_result(result: dict, spot: dict) -> bool:
    """Insere em gto_nodes e atualiza decisions. Retorna True se salvo."""
    if not result.get('gto_found'):
        return False

    strategy  = result.get('gto_strategy') or {}
    if not strategy:
        return False

    from database.repositories import insert_gto_nodes, update_decision_gto
    from leaklab.gto_utils import compute_spot_hash

    board_list = spot['board_list']
    # board do flop/turn/river (só cartas relevantes para a street)
    n = {'flop': 3, 'turn': 4, 'river': 5}.get(spot['street'], 3)
    board_for_hash = board_list[:n]

    stack_bb  = spot['stack_bb']
    facing_bb = spot['facing_bet']
    position  = spot['position']
    street    = spot['street']

    top_action = result.get('gto_top_action') or max(strategy, key=lambda k: strategy[k])
    top_freq   = strategy.get(top_action, 0.0)

    # Inserir em gto_nodes
    node = {
        'street':            street,
        'position':          position,
        'board':             board_for_hash,
        'hero_hand':         [],
        'hero_stack_bb':     stack_bb,
        'facing_size_bb':    facing_bb,
        'gto_action':        top_action,
        'gto_freq':          top_freq,
        'ev_diff':           None,
        'exploitability_pct': 0.0,
        'iterations':        None,
        'source':            'gto_wizard',
        'strategy_detail':   strategy,
    }
    insert_gto_nodes([node])

    # Atualizar decisions
    gto_label, gto_action = _classify(spot['action_taken'], strategy)
    if gto_label:
        update_decision_gto(spot['decision_id'], gto_label, gto_action)

    return True


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit',   type=int, default=0,
                        help='Max decisoes a processar (0=todas)')
    parser.add_argument('--street',  default='all',
                        choices=['all', 'flop', 'turn', 'river'])
    parser.add_argument('--delay',   type=float, default=1.5)
    parser.add_argument('--timeout', type=int, default=12000)
    parser.add_argument('--dry-run', action='store_true',
                        help='Mostra spots sem chamar o GTO Wizard')
    parser.add_argument('--debug-next-actions', action='store_true')
    args = parser.parse_args()

    decisions = _load_pending_decisions(limit=args.limit, street_filter=args.street)
    print(f"\nDecisoes sem GTO encontradas: {len(decisions)}")

    spots: list[dict] = []
    skipped = 0
    for d in decisions:
        spot = _decision_to_spot(d)
        if spot and build_params(spot) is not None:
            spots.append(spot)
        else:
            skipped += 1

    print(f"Spots validos para GTO Wizard: {len(spots)}  |  Pulados (sem params): {skipped}")

    if not spots:
        print("Nada a processar.")
        return

    if args.dry_run:
        print("\n[DRY RUN] Spots que seriam enviados:")
        for s in spots:
            print(f"  dec_id={s['decision_id']}  {s['street']:<6} {s['position']:<6} "
                  f"{s['board']:<14} {s['stack_bb']:.1f}bb"
                  + (f"  facing={s['facing_bet']:.1f}bb" if s['facing_bet'] else ""))
        return

    print(f"\nIniciando fallback GTO Wizard para {len(spots)} spots...")
    results = run_comparison(
        spots,
        headless=False,
        timeout_ms=args.timeout,
        delay=args.delay,
        debug_next_actions=args.debug_next_actions,
    )

    # Salvar resultados
    saved   = 0
    not_found = 0
    for result, spot in zip(results, spots):
        if _save_result(result, spot):
            saved += 1
        else:
            not_found += 1

    print(f"\n{'='*50}")
    print(f"Salvos em gto_nodes + decisions: {saved}")
    print(f"Nao encontrados / erro:          {not_found}")

    # Status final
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    remaining = conn.execute("""
        SELECT COUNT(*) n FROM decisions
        WHERE street IN ('flop','turn','river') AND gto_label IS NULL
    """).fetchone()[0]
    conn.close()
    print(f"Decisoes ainda sem GTO:          {remaining}")


if __name__ == '__main__':
    main()
