# Mapa — spots POSTFLOP HU sem status GTO (autoritativo pelo engine)

Total: **18** decisões postflop heads-up sem `gto_label` (DB dev local). Cobertura HU postflop ≈ 94,6%.
Gerado por `scripts/map_postflop_hu_gto_gaps.py` — reconstrói o spot pelo parser ATUAL e pergunta ao `_enrich_gto` o motivo real. Read-only.

**Parser:** villain NÃO resolvido pelo parser atual em **0** dos 18 spots — ou seja, NÃO é problema de parser. Em **3** spots a coluna `vs_position` do banco está STALE (`unknown`) embora o parser resolva o villain (issue de dado, não de cobertura).

**Prioridade:** 7 acionáveis (jogou ≠ best); 11 são linhas default sem erro pendente.

## Resumo por causa-raiz (motivo do engine)

| Bucket | Qtde | Remediação |
|---|---|---|
| UNGRADEABLE — nó não oferece a ação do hero (bet/raise/shove) | 6 | Lado SOLVER: emitir nó com o ramo de bet/raise/sizing do hero. Re-solve sozinho NÃO fecha. |
| NO_NODE — sem nó usável (nunca solvado / solve falhou) | 12 | Enfileirar + solve (villain é conhecido pelo parser). Stacks >60bb estouram a RAM do solver → Opção B (≈ Aproximação). |

## Distribuições

- **Street/Facing:** flop/first-in=14, flop/vs-bet=2, river/first-in=1, turn/vs-bet=1
- **Profundidade:** 46-60bb=7, >60bb=6, 13-24bb=2, 36-45bb=2, 25-35bb=1
- **Posição (hero v villain LIVE):** SBvBB=6, BBvHJ=3, BTNvBB=2, BBvBTN=2, BBvSB=2, HJvBB=1, COvUTG=1, BBvCO=1

## UNGRADEABLE — nó não oferece a ação do hero (bet/raise/shove)  — 6 spot(s)  (6 acionável(is))

**Remediação:** Lado SOLVER: emitir nó com o ramo de bet/raise/sizing do hero. Re-solve sozinho NÃO fecha.

| id | torneio | mão | street | pos | villain (live) | vs_col(stale) | facing | depth | jogou | best | acionável |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 33087 | 147 | 258867150524 | flop | SB | BB | unknown | first-in | 25-35bb | bet | check | SIM |
| 33118 | 148 | 258867235685 | flop | BTN | BB | unknown | first-in | >60bb | bet | check | SIM |
| 33153 | 148 | 258867373219 | flop | HJ | BB | unknown | first-in | >60bb | bet | check | SIM |
| 33286 | 149 | 260605886991 | river | CO | UTG | UTG | first-in | 46-60bb | bet | check | SIM |
| 33960 | 196 | 260875800112 | flop | SB | BB | BB | vs-bet | 13-24bb | raise | fold | SIM |
| 35868 | 388 | 100000022 | turn | BB | HJ | HJ | vs-bet | 46-60bb | shove | call | SIM |

## NO_NODE — sem nó usável (nunca solvado / solve falhou)  — 12 spot(s)  (1 acionável(is))

**Remediação:** Enfileirar + solve (villain é conhecido pelo parser). Stacks >60bb estouram a RAM do solver → Opção B (≈ Aproximação).

| id | torneio | mão | street | pos | villain (live) | vs_col(stale) | facing | depth | jogou | best | acionável |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 35855 | 388 | 100000020 | flop | BB | BTN | BTN | first-in | 36-45bb | check | check | - |
| 35910 | 388 | 100000035 | flop | BB | HJ | HJ | vs-bet | 46-60bb | call | call | - |
| 35921 | 388 | 100000038 | flop | BB | HJ | HJ | first-in | >60bb | check | check | - |
| 36014 | 388 | 100000080 | flop | SB | BB | BB | first-in | 36-45bb | check | check | - |
| 36034 | 388 | 100000086 | flop | BB | SB | SB | first-in | 13-24bb | check | check | - |
| 36044 | 388 | 100000090 | flop | BB | CO | CO | first-in | 46-60bb | check | check | - |
| 36052 | 388 | 100000094 | flop | SB | BB | BB | first-in | 46-60bb | check | check | - |
| 36076 | 388 | 100000103 | flop | BTN | BB | BB | first-in | 46-60bb | check | check | - |
| 36083 | 388 | 100000105 | flop | SB | BB | BB | first-in | 46-60bb | check | check | - |
| 36092 | 388 | 100000110 | flop | BB | BTN | BTN | first-in | >60bb | check | check | - |
| 36130 | 388 | 100000121 | flop | SB | BB | BB | first-in | >60bb | check | check | - |
| 36138 | 388 | 100000123 | flop | BB | SB | SB | first-in | >60bb | bet | check | SIM |

