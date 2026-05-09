"""
gto_preflop_seeder.py — DESATIVADO.

Este módulo existia para popular gto_preflop_ranges com ranges estimadas.
Foi desativado porque estimativas não são GTO garantido.

A tabela gto_preflop_ranges só deve ser populada com saídas reais de solver
com exploitability_pct medida e documentada.

Como popular corretamente:
  1. Compile o solver Rust: cd backend/gto_bot/solver_cli && cargo build --release
  2. O worker em gto_solver.py (run_solver_worker) popula gto_nodes automaticamente
     após cada solve, com exploitability_pct garantida.
  3. Para preflop especificamente, use POST /admin/gto/import-verified
     fornecendo um arquivo JSON de ranges com exploitability de solver externo
     verificado (ex: exportação do PioSOLVER ou GTO Wizard).

Formato esperado para importação verificada:
{
  "solver": "piosolver_3.0",
  "game_tree": "6max_100bb_2.5x_ante",
  "exploitability_pct": 0.3,
  "ranges": [
    {
      "position": "BTN",
      "vs_position": "",
      "action_seq": "rfi",
      "hand_type": "AKs",
      "action": "raise",
      "frequency": 1.0,
      "ev_bb": 1.63
    },
    ...
  ]
}
"""

raise RuntimeError(
    "gto_preflop_seeder está desativado. "
    "Use apenas dados de solver verificado via POST /admin/gto/import-verified. "
    "Veja a documentação no topo deste arquivo."
)
