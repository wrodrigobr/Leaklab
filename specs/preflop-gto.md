# Preflop GTO — roteamento, reconciliação, cobertura

Como `analyze_preflop()` (em `leaklab/preflop_gto_ranges.py`) transforma um spot
num veredito. **Fonte de verdade do roteamento** — o display deve espelhar (INV-1).

## Cenários e roteamento (ordem importa)

Avaliados nesta ordem em `analyze_preflop` (primeiro que casa vence):

| Cenário | Condição | Range usada |
|---|---|---|
| `squeeze` | `is_3bet_pot AND vs_pos AND caller_pos` | `squeeze[hero][opener]` — hero squeeza sobre open+caller |
| `vs_3bet` | `hero_was_aggressor AND facing_size>0 AND vs_pos` | `vs_3bet[hero(opener)][3bettor]` — hero abriu, enfrenta 3bet |
| `faces_squeeze` | `facing_raises>=2 AND NOT hero_was_aggressor` | `faces_squeeze[hero][3bettor]` — hero cold/blind enfrenta open+3bet/squeeze |
| `vs_rfi` | `facing_size>0` (resto) | `vs_RFI[opener][hero]` — defesa vs open simples |
| `rfi` | nenhuma | `RFI[hero]` / push_fold (stacks rasos) |

**Crítico:** `faces_squeeze` só é alcançado com `facing_raises>=2`. Sem esse sinal,
o spot cai em `vs_rfi` (defesa larga) e sugere `call` indevido (o bug "call 54s vs
squeeze"). Por isso **todo caller de `analyze_preflop` deve passar `facing_raises`
e `hero_was_aggressor`** (INV-1).

`BB check` em pote não-contestado (`rfi` + pos BB + ação check) → `available=False`
(free play, não é decisão de range).

## Estrutura do master (`leaklab_gto_ranges.json`)

`ranges[bucket][secao][k1][k2] = spot_data`, onde:
- `RFI[hero]`, `vs_RFI[opener][hero]`, `vs_3bet[hero][3bettor]`,
  `squeeze[hero][opener]`, `faces_squeeze[hero][3bettor]`.
- `spot_data`: `*_pct`, `*_hands` (raise/call/allin/fold), `hand_freqs` (codes crus GW), `source`.

Buckets de stack (`_DEFAULT_BUCKETS`): 10/14/17/20/30/40/50/75/100bb (faixas em `preflop_gto_ranges.py`).

## Reconciliação (label ↔ gto_label) — INV-2

`_reconcile_label`: quando há `gto_label`, o `label` heurístico é derivado dele
(gto_correct/mixed → standard; gto_minor → marginal; gto_critical → small_mistake,
com exceções por severidade). Por isso `label` e `gto_label` concordam por design.

**Ao mudar a range** (nova captura / fix de roteamento), as decisões ARMAZENADAS
ficam stale. Reconciliar:
```
python scripts/resync_postflop_gto.py --street preflop --apply   # não-ambíguos
# + re-grade por ORDEM dentro da mão (preflop_autocapture._regrade_tournament) p/ ambíguos
```
Depois recalcular ELO (snapshot) e o leaderboard.

## Cobertura

`available=True` = spot tem range → recebe veredito. `available=False` = NULL honesto
(INV-3). Estado atual: ~95% das decisões preflop padrão cobertas. Os NULLs restantes
são pote limpado (fora do modelo raise-or-fold do GW), BB free-checks (não-decisão),
e linhas off-tree. Ver memória `project_preflop_coverage_ceiling`.

## Sizing depende da profundidade (INV-6 + INV-8)

- 3bet/squeeze: **RAI** (shove) em ≤20bb, **R6** em fundo. Open canônico: **R2** (2bb).
- **Limitação:** as ranges são para o sizing GTO. Open real off-tree (ex.: 3bb) não
  existe no GW → snapa pro canônico e a defesa fica larga demais. Não marcar crítico
  nesses casos (INV-8 / backlog #23).
