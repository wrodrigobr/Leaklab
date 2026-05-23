#!/usr/bin/env python3
"""
revalidate.py -- CLI para a varredura de revalidação engine vs oracle.

Uso:
    python -m scripts.revalidate                              # todos os torneios
    python -m scripts.revalidate --user-id 1                  # só um usuário
    python -m scripts.revalidate --tournament-id 42           # um torneio
    python -m scripts.revalidate --with-llm-judge             # ativa LLM juiz (top-50)
    python -m scripts.revalidate --llm-budget 100             # cap de chamadas LLM
    python -m scripts.revalidate --output reports/revalidation # diretório de saída

Saída:
    stdout: resumo executivo (counts por categoria, top torneios)
    arquivos: <output>/revalidation_run_<id>.{md,json}
"""
from __future__ import annotations

import argparse
import os
import sys

# Garante backend/ no sys.path
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='Revalida recomendações engine vs oracle independente.'
    )
    p.add_argument('--user-id', type=int, default=None,
                   help='Filtrar por usuário')
    p.add_argument('--tournament-id', type=int, default=None,
                   help='Filtrar por tournament_db_id')
    p.add_argument('--with-llm-judge', action='store_true',
                   help='Ativa Claude Haiku como tiebreaker nos top findings')
    p.add_argument('--llm-budget', type=int, default=50,
                   help='Máximo de chamadas LLM por run (default 50)')
    p.add_argument('--output', type=str,
                   default=os.path.join('reports', 'revalidation'),
                   help='Diretório de saída para markdown + json')
    p.add_argument('--no-persist', action='store_true',
                   help='Não grava em revalidation_runs/findings (dry-run)')
    p.add_argument('--notes', type=str, default=None,
                   help='Texto livre para anotar no run (ex: "pós-fix #123")')
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    from leaklab.revalidation.orchestrator import revalidate, Scope

    if args.tournament_id is not None:
        scope = Scope.for_tournament(args.tournament_id)
    elif args.user_id is not None:
        scope = Scope.for_user(args.user_id)
    else:
        scope = Scope.all()

    print(f'== Revalidação ({scope.label()}) ==')
    print('  iniciando varredura -- pode demorar conforme o volume...')
    result = revalidate(
        scope=scope,
        with_llm_judge=args.with_llm_judge,
        llm_budget=args.llm_budget,
        persist=not args.no_persist,
        output_dir=args.output,
        notes=args.notes,
    )
    _print_summary(result)
    if not args.no_persist:
        print(f'\nRun salvo: id={result.run_id}')
    print(f'Relatório: {os.path.abspath(args.output)}/revalidation_run_{result.run_id}.md')
    return 0


def _print_summary(result) -> None:
    print()
    print(f'  Torneios:  {result.total_tournaments}')
    print(f'  Mãos:      {result.total_hands}')
    print(f'  Decisões:  {result.total_decisions}')
    print(f'  Tempo:     {result.elapsed_sec:.1f}s')
    if result.errors:
        print(f'  ! Erros:   {len(result.errors)} (ver JSON)')
    print()
    print('  Distribuição por categoria:')
    total = result.total_decisions or 1
    for cat in ['major_mismatch', 'minor_mismatch', 'no_oracle_data',
                'engine_no_data', 'acceptable_alt', 'aligned']:
        n = result.category_counts.get(cat, 0)
        pct = n * 100.0 / total
        bar = '#' * int(pct // 2) if pct > 0 else ''
        print(f'    {cat:<18}  {n:>6}  ({pct:5.1f}%)  {bar}')


if __name__ == '__main__':
    raise SystemExit(main())
