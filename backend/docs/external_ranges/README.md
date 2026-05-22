# External Ranges — Referência para cobertura vs_3bet/vs_4bet

Charts de poker de fontes externas baixados como **referência local** para popular
os ranges `vs_3bet` e `vs_4bet` no `leaklab_gto_ranges.json`.

## Fontes

### 1. Greenline (`greenline_ranges.ts`)
- **Origem:** `GreenCharts2024_01.pdf` (Greenline Poker)
- **Formato:** Cash 6-max, 100bb
- **Cobertura:**
  - RFI: UTG, MP, CO, SB, BTN
  - vs-open (defender → RFI): BB vs todas
  - **vs-3bet (opener → 3-bet):** UTG, MP, CO, BTN, SB — completo
  - **vs-4bet (3-bettor → 4-bet):** BB vs todas
  - ISO ranges
- **Granularidade:** estratégias mistas (ex: `['raise', 'fold']` = freq parcial)

### 2. Pekarstas (`pekarstas_ranges.ts`)
- **Origem:** GTO Preflop app (Peka Software AS, NO)
- **Formato:** Cash 6-max, 100bb
- **Cobertura:**
  - **vs-3bet (opener → 3-bet):** UTG, MP, CO, BTN, SB — completo
  - **vs-4bet (3-bettor → 4-bet):** BB, BTN, CO, MP, SB
  - vs-open: BB, BTN, SB
- **Granularidade:** ação única por mão (`raise`/`call`/`fold`/`allin`)

### 3. Index (`ranges_index.ts`)
Tipos e função de lookup do projeto upstream — útil pra entender o shape.

## Procedência

Repositório upstream: <https://github.com/AHTOOOXA/poker-charts> (commit main, snapshot baixado em 2026-05-22).
Licença: **MIT** — uso comercial, modificação e redistribuição permitidos com atribuição.

## Limitações para o nosso contexto

- **Formato 6-max cash, não 8-max MTT.** Mapeamento sugerido para nosso 8-max:
  | 6-max | 8-max equivalente | Observação |
  |---|---|---|
  | UTG | UTG | direto |
  | MP | HJ | tighter que HJ; usar como fallback |
  | — | LJ | sem equivalente direto; usar UTG ou MP como aproximação |
  | CO | CO | direto |
  | BTN | BTN | direto |
  | SB | SB | direto (note SB/BB dinâmica é similar) |
  | BB | BB | direto |
- **Apenas 100bb cash.** Para MTT precisamos adaptar via ICM/depth — ou completar com fontes adicionais para 30bb, 50bb.
- Ainda assim, é uma referência **muito superior** ao fallback atual (que usa UTG ou BTN para qualquer outra posição) — porque cobre HJ/MP, CO, SB com dados próprios.

## Próximo passo

Escrever `scripts/import_external_vs_3bet.py` que:
1. Lê os TS modules e converte para o shape `leaklab_gto_ranges.json` (chave `vs_3bet`)
2. Agrupa mãos por ação → `hands_4bet`, `hands_call`, `hands_fold`
3. Mescla com bucket `100bb` do JSON existente sem sobrescrever os ranges atuais (que já cobrem UTG/CO/BTN)
4. Adiciona LJ_RFI_vs_3bet, HJ_RFI_vs_3bet, MP_RFI_vs_3bet, SB_RFI_vs_3bet, BB_RFI_vs_3bet via mapeamento acima

Para outros stacks (30bb, 50bb): seguir o mesmo processo com fontes próprias quando localizadas.
