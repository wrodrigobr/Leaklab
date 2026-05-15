"""
import_gto_results.py — Importa resultados do GTO Wizard para gto_nodes.

Lê comparison_results_raw.json (produzido por playwright_compare.py) e insere
cada spot encontrado (gto_found=True) na tabela gto_nodes do banco local.

Exploitability: GTO Wizard usa árvores pré-resolvidas em equilíbrio de Nash,
portanto exploitability_pct = 0.0 é o valor correto.

Uso:
    cd backend
    python scripts/gto_validation/import_gto_results.py
    python scripts/gto_validation/import_gto_results.py --input scripts/gto_validation/comparison_deep.json
    python scripts/gto_validation/import_gto_results.py --dry-run
"""
from __future__ import annotations
import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

DEFAULT_INPUT = os.path.join(
    os.path.dirname(__file__), 'comparison_results_raw.json'
)


def _parse_board(board_str: str) -> list[str]:
    """'Ah7s8h' → ['Ah', '7s', '8h'] (formato compacto do playwright_compare)."""
    board_str = board_str.strip()
    # Se já vier com espaços ou separado
    if ' ' in board_str:
        return board_str.split()
    # Formato compacto: 2 chars por carta
    cards = []
    i = 0
    while i + 1 < len(board_str):
        cards.append(board_str[i:i+2])
        i += 2
    return cards


def import_results(input_path: str, dry_run: bool = False) -> None:
    with open(input_path, encoding='utf-8') as f:
        results: list[dict] = json.load(f)

    found = [r for r in results if r.get('gto_found')]
    print(f"\nTotal de resultados:   {len(results)}")
    print(f"gto_found=True:        {len(found)}")
    print(f"gto_found=False/erro:  {len(results) - len(found)}")

    if not found:
        print("\nNenhum resultado para importar.")
        return

    nodes: list[dict] = []
    skipped: list[str] = []

    for r in found:
        strategy: dict = r.get('gto_strategy') or {}
        if not strategy:
            skipped.append(f"{r.get('position')} {r.get('board')} — sem estratégia")
            continue

        top_action = r.get('gto_top_action') or max(strategy, key=lambda k: strategy[k])
        top_freq   = strategy.get(top_action, 0.0)

        board_str  = r.get('board', '')
        board_list = _parse_board(board_str)
        if len(board_list) < 3:
            skipped.append(f"{r.get('position')} {board_str} — board inválido")
            continue

        # stack: playwright salva como depth = snap + 0.125 → reverter para BB
        stack_depth = float(r.get('stack', 30.125))
        stack_bb    = round(stack_depth - 0.125, 3)

        facing_bb   = float(r.get('facing_bet') or 0)
        position    = (r.get('position') or '').upper()
        street      = r.get('street', 'flop')

        node = {
            'street':          street,
            'position':        position,
            'board':           board_list,
            'hero_hand':       [],
            'hero_stack_bb':   stack_bb,
            'facing_size_bb':  facing_bb,
            'gto_action':      top_action,
            'gto_freq':        top_freq,
            'ev_diff':         None,
            'exploitability_pct': 0.0,   # GTO Wizard = equilíbrio de Nash
            'iterations':      None,
            'source':          'gto_wizard',
            'strategy_detail': strategy,
        }
        nodes.append(node)

        strat_str = ' | '.join(
            f"{k} {int(v*100)}%"
            for k, v in sorted(strategy.items(), key=lambda x: -x[1])
        )
        print(f"  {street:<6} {position:<6} {board_str:<12} {stack_bb:>6.1f}bb"
              + (f"  facing={facing_bb:.1f}bb" if facing_bb else "           ")
              + f"  → {top_action} ({int(top_freq*100)}%)  [{strat_str}]")

    if skipped:
        print(f"\n  Pulados ({len(skipped)}):")
        for s in skipped:
            print(f"    - {s}")

    if dry_run:
        print(f"\n[DRY RUN] {len(nodes)} nós seriam importados. Nenhuma alteração salva.")
        return

    if not nodes:
        print("\nNada a importar.")
        return

    confirm = input(f"\nImportar {len(nodes)} nós para gto_nodes? [s/N] ").strip().lower()
    if confirm != 's':
        print("Cancelado.")
        return

    from database.repositories import insert_gto_nodes
    imported = insert_gto_nodes(nodes)
    print(f"\nImportado: {imported}/{len(nodes)} nós → gto_nodes (source=gto_wizard)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',   default=DEFAULT_INPUT)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"ERRO: {args.input} não encontrado.")
        print("Execute playwright_compare.py primeiro.")
        sys.exit(1)

    import_results(args.input, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
