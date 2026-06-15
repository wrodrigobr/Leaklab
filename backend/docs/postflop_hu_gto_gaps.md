# Mapa — spots POSTFLOP HU sem status GTO

Total: **18** decisões postflop heads-up sem `gto_label` (DB dev local).
Gerado por `scripts/map_postflop_hu_gto_gaps.py` (read-only).

**Prioridade:** 7 são "acionáveis" (jogou ≠ best — o engine já sinaliza um possível erro que falta o GTO confirmar); os outros 11 são linhas default (check/check etc.) sem erro pendente — cobertura por completude, baixa prioridade.

## Resumo por causa-raiz

| Bucket | Qtde | Remediação |
|---|---|---|
| A) Nó agregado SEM tabela hand-aware (require_hand_aware rejeita) | 4 | Re-solve hand-aware (gerar gto_tree_strategies) — mesma campanha de 2026-06-12. |
| B) Solver FALHOU (no-solution genuíno ou erro) | 2 | Investigar log do solver: confirmar no-solution do GW vs erro de servidor. |
| C) NUNCA enfileirado (órfão — sem nó, fora da fila) | 12 | Enfileirar (requeue_orphaned_postflop --apply) + solve hand-aware; >60bb usa Opção B (≈ Aproximação). |

## Distribuições (todos os spots)

- **Street/Facing:** flop/first-in=14, flop/vs-bet=2, river/first-in=1, turn/vs-bet=1
- **Profundidade:** 46-60bb=7, >60bb=6, 13-24bb=2, 36-45bb=2, 25-35bb=1
- **Posição:** BB=8, SB=6, BTN=2, HJ=1, CO=1
- **Tipo de pote:** SRP=18

## A) Nó agregado SEM tabela hand-aware (require_hand_aware rejeita)  — 4 spot(s)

**Remediação:** Re-solve hand-aware (gerar gto_tree_strategies) — mesma campanha de 2026-06-12.

_4 acionável(is) (jogou ≠ best) de 4._

| id | torneio | mão | street | pos | vs | facing | depth | jogou | best | acionável | fonte_nó | fila |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 33153 | 148 | 258867373219 | flop | HJ | unknown | first-in | >60bb | bet | check | SIM | gto_wizard | - |
| 33118 | 148 | 258867235685 | flop | BTN | unknown | first-in | >60bb | bet | check | SIM | gto_wizard | - |
| 33286 | 149 | 260605886991 | river | CO | UTG | first-in | 46-60bb | bet | check | SIM | gto_wizard | done |
| 35868 | 388 | 100000022 | turn | BB | HJ | vs-bet | 46-60bb | shove | call | SIM | solver_cli | done |

## B) Solver FALHOU (no-solution genuíno ou erro)  — 2 spot(s)

**Remediação:** Investigar log do solver: confirmar no-solution do GW vs erro de servidor.

_1 acionável(is) (jogou ≠ best) de 2._

| id | torneio | mão | street | pos | vs | facing | depth | jogou | best | acionável | fonte_nó | fila |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 33087 | 147 | 258867150524 | flop | SB | unknown | first-in | 25-35bb | bet | check | SIM | - | failed |
| 36044 | 388 | 100000090 | flop | BB | CO | first-in | 46-60bb | check | check | - | - | failed |

## C) NUNCA enfileirado (órfão — sem nó, fora da fila)  — 12 spot(s)

**Remediação:** Enfileirar (requeue_orphaned_postflop --apply) + solve hand-aware; >60bb usa Opção B (≈ Aproximação).

_2 acionável(is) (jogou ≠ best) de 12._

| id | torneio | mão | street | pos | vs | facing | depth | jogou | best | acionável | fonte_nó | fila |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 36034 | 388 | 100000086 | flop | BB | SB | first-in | 13-24bb | check | check | - | - | - |
| 33960 | 196 | 260875800112 | flop | SB | BB | vs-bet | 13-24bb | raise | fold | SIM | - | - |
| 35855 | 388 | 100000020 | flop | BB | BTN | first-in | 36-45bb | check | check | - | - | - |
| 36014 | 388 | 100000080 | flop | SB | BB | first-in | 36-45bb | check | check | - | - | - |
| 35910 | 388 | 100000035 | flop | BB | HJ | vs-bet | 46-60bb | call | call | - | - | - |
| 36052 | 388 | 100000094 | flop | SB | BB | first-in | 46-60bb | check | check | - | - | - |
| 36076 | 388 | 100000103 | flop | BTN | BB | first-in | 46-60bb | check | check | - | - | - |
| 36083 | 388 | 100000105 | flop | SB | BB | first-in | 46-60bb | check | check | - | - | - |
| 35921 | 388 | 100000038 | flop | BB | HJ | first-in | >60bb | check | check | - | - | - |
| 36130 | 388 | 100000121 | flop | SB | BB | first-in | >60bb | check | check | - | - | - |
| 36092 | 388 | 100000110 | flop | BB | BTN | first-in | >60bb | check | check | - | - | - |
| 36138 | 388 | 100000123 | flop | BB | SB | first-in | >60bb | bet | check | SIM | - | - |

