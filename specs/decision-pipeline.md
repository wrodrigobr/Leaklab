# Pipeline de decisão — do texto ao veredito armazenado

## Fluxo

1. **`parser.py`** → `ParsedHand` (hero, ações, board, `raw_text`).
2. **`pipeline.build_decision_inputs_for_hand(hand)`** → lista de `di` (1 por decisão do hero).
   Cada `di['spot']` tem os sinais de roteamento: `position`, `villainPosition`,
   `effectiveStackBb`, `facingSize`, **`preflopRaisesFaced`**, **`heroWasAggressor`**,
   `nPlayers`, `is3betPot`.
3. **`decision_engine_v11.evaluate_decision(di)`** → veredito (label, bestAction, gto).
   Preflop: chama `analyze_preflop` com TODOS os sinais. **É a referência** (INV-1).
4. **`repositories.save_decisions(...)`** → tabela `decisions`.

## Colunas-chave de `decisions`

| Coluna | Significado |
|---|---|
| `label` | qualidade heurística: standard / marginal / small_mistake / clear_mistake |
| `best_action` | ação recomendada (heurística, reconciliada com gto) |
| `gto_label` | aderência GTO: gto_correct / gto_mixed / gto_minor_deviation / gto_critical / **NULL** (sem cobertura) |
| `gto_action` | ação GTO recomendada (NULL se sem cobertura) |
| `preflop_raises_faced` | nº de raises enfrentados (open=1, 3bet/squeeze=2) — **sinal durável do roteamento** |
| `vs_position` | posição do vilão de referência |
| `hero_won_hand` | 1/0/NULL — hero coletou o pote (INV-9) |
| `showdown_result` | won/lost/NULL — só showdown (diferente de hero_won_hand) |

## Os paths que recomputam o veredito (devem concordar — INV-1)

O produto serve o veredito ARMAZENADO. Mas alguns paths **recomputam** preflop para
display e DEVEM passar os mesmos sinais (`facing_raises`, `hero_was_aggressor`, `n_players`):

| Path (`app.py`) | Uso |
|---|---|
| `_analyze_hands` → `enriched['preflop_gto']` | resposta do `/analyze` |
| `/replay/<t>/<h>` (build_replay_data) | Replayer |
| coach replay | replay do aluno pro coach |
| GTO live override (preflop) | recomendação on-the-fly |

**Bug histórico:** 3 destes (e o /replay) omitiam `facing_raises`/`hero_was_aggressor`
→ `faces_squeeze` virava `vs_rfi` → "call 54s vs squeeze". 14 spots afetados em 5
torneios. **Ideal:** consolidar num helper único.

## Reconciliar após mudar a range

Decisões armazenadas ficam stale quando a range muda → rodar `resync_postflop_gto.py
--street preflop --apply` + re-grade por ordem, depois recalcular ELO. Ver [`preflop-gto.md`](preflop-gto.md).
