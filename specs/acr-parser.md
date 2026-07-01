# Spec — Parser de Hand History do ACR Poker (Americas Cardroom / Winning Poker Network)

Status: **PARSER ENTREGUE 2026-07-01** (fases 1-4 + 6). Detecção/split/header/seats/antes/ações/board/showdown ACR no `leaklab/parser.py` (branch `site=='acr'`); validado nos 3 arquivos reais (86 mãos → 136 decisões com posição via pipeline). Teste `tests/test_acr_parser.py` (5, suite regression). **Fase 5 (financeiro via filename) PENDENTE** — o corpo da HH ACR é só em chips (sem $ de buy-in/prêmio); o buy-in vem do FILENAME (`TN-$0{FULLSTOP}50`), que o `/analyze` teria que receber e parsear. Sem isso, mãos/decisões/GTO funcionam, mas ROI/bankroll do torneio ficam zerados. Arquivos de amostra em `backend/HH20260630 SITGOID-G35409697T*.txt` (3 arquivos, MESMO torneio #35409697 — merge por hand_id já funciona no import).

## Objetivo
Adicionar o ACR como 3º site suportado (hoje: PokerStars, GGPoker) em `leaklab/parser.py`. ACR é dialeto **PokerStars-like na estrutura, mas com diferenças que quebram o parser atual** (sem dois-pontos nas ações, sem "in chips", valores com decimais).

## Diferenças vs PokerStars/GGPoker (o que precisa de código)

1. **Detecção de site:** header começa com `Game Hand #<id> - Tournament #<tid> - Holdem (No Limit) - Level N (sb/bb) - YYYY/MM/DD HH:MM:SS UTC`. Marcador único = `Game Hand #` + ` - Tournament #`. (`_detect_site` → 'acr'.)
2. **Split de mãos:** por `Game Hand #` (hoje split é por "PokerStars Hand #"/"Poker Hand #").
3. **Header/regex:** hand id `Game Hand #(\d+)`; torneio `Tournament #(\d+)`; blinds/level `Level (\d+) \(([\d.]+)/([\d.]+)\)` — **Level é número árabe** (não romano) e **blinds com decimais** (250.00/500.00). `SB_RE` já aceita decimais; o `BUTTON_RE`/`Table 'X' N-max Seat #K is the button` é igual ao PS (ok).
4. **Assentos:** `Seat N: nome (29150.00)` — **SEM "in chips"** e **stack com decimais**. O regex de seat atual exige "in chips" → não casa. Precisa de variante ACR.
5. **Ações SEM dois-pontos:** `Quenched raises 1150.00 to 1150.00`, `MusashiBR calls 250.00`, `ibslower checks`, `MusashiBR bets 675.00`, `AndreaBsAs folds`, `JAMESHARPER bets 26650.00 and is all-in`, `ibslower raises 7218.00 to 7218.00 and is all-in`. O `ACTION_LINE_RE` atual exige `nome: ação` → NÃO casa. Precisa de regex ACR: `^(?P<player>.+?) (?P<action>folds|checks|calls|bets|raises) ...` (nome non-greedy até o verbo) + tratar `and is all-in` → all-in. "raises X to Y" (X=incremento, Y=to-total; igual PS).
6. **Antes/blinds:** `nome posts ante 50.00` (sem "the"), `nome posts the small blind 250.00`, `posts the big blind 500.00`. O `ANTE_LINE_RE` (`posts (?:the )?ante`) já casa o ante; SB/BB vêm do header (não são ações).
7. **Valores com decimais e grandes** (chips: 250.00, 29150.00). Stripar/`float`; cuidado pra não confundir o "." com separador.
8. **Linhas extras `Main pot X.XX`** após `*** HOLE CARDS ***` e após cada street — ignorar (não é ação).
9. **Hole cards:** `Dealt to nome [Th 7c]` (igual PS — `HERO_DEALT_RE` casa).
10. **Board:** `*** FLOP *** [4s As Qc]`, `*** TURN *** [..] [x]`, `*** RIVER *** [..] [x]`, `*** SHOW DOWN ***` (com espaço). `_extract_board` casa.
11. **Showdown:** `nome shows [Js Ac] (a flush, ...)`, `nome collected 16686.00 from main pot`, `nome does not show`, `nome did not show and won 1600.00`.
12. **Summary:** `Seat N: nome (button) folded on the Pre-Flop` / `folded on the Flop` / `showed [..] and won X.XX with ...` / `did not show and won X.XX`. Wording diferente do PS ("folded before Flop") → o extrator de showdown/financeiro precisa do dialeto ACR.

## MESMO torneio em vários arquivos (importante — confirmado pelo dono)
Os 3 arquivos (filename `...T1/T4/T6`) são o **MESMO torneio**: todo header tem `Tournament #35409697` (os Ts são segmentos/níveis distintos do mesmo SNG on-demand: Level 1, 4, 11...). **Agrupar/mesclar por `Tournament #` do header** no import — NÃO criar 3 torneios separados. (Chave confiável = header, não o filename.)

## Filename (encoding ACR)
`HH20260630 SITGOID-G35409697T1 TN-$0{FULLSTOP}50 NLH Turbo - On Demand GAMETYPE-Hold'em LIMIT-no CUR-REAL OND-T BUYIN-0.txt`
- `{FULLSTOP}` = `.` literal (ACR escapa o ponto) → `$0.50` buy-in.
- `SITGOID-G<id>T<table>` = id do SNG + mesa/segmento.
- Buy-in vem do filename (`TN-$0{FULLSTOP}50` = $0.50); o corpo da HH é só em CHIPS (sem $ de buy-in/prêmio) → **extração financeira ACR depende do filename + payout por colocação** (gotcha: diferente de PS, que tem buy-in/prize no texto).

## Plano de implementação (fases)
1. **Detecção + split + header** (Game Hand/Tournament/Level decimais).
2. **Seats ACR** (sem "in chips", decimais) + **ações sem dois-pontos** (regex próprio + all-in) + ignorar `Main pot`.
3. **Showdown/summary ACR** (won/collected/does not show + wording de fold).
4. **Agrupamento por Tournament #** no import (mesma chave p/ os N arquivos).
5. **Financeiro** via filename ({FULLSTOP}→., buy-in) + payout.
6. **Testes de regressão** com os 3 arquivos reais (suite `regression`, padrão `test_tournament.py`): nº de mãos, hero, posições, ações, board — e que os 3 caem no MESMO tournament_id.

## Riscos/gotchas
- Nomes de jogador com espaço + ação sem dois-pontos (regex non-greedy até o verbo).
- Valores em chips com `.00` (float) — o pipeline normaliza pra BB via header (bb=500 → stacks ~58bb; ok).
- 888/PartyPoker tem flag `PARTYGAMING_ENABLED=False` (referência de como roteamos dialetos por site).
- Não quebrar PS/GG: o caminho ACR só dispara quando `_detect_site=='acr'`.
