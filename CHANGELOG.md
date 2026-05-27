# Changelog

Todas as mudanÃ§as notÃ¡veis neste projeto serÃ£o documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Unreleased]

### fix(gto-bot): captura aceita token `google-anal-id` (GW novo)
- `backend/gto_bot/solver_api/server.py`: `_capture_headers_via_cdp` agora aceita header `google-anal-id` como evidência de auth válida, não só `authorization`. GW migrou de Bearer JWT pra token ECDSA assinado client-side; antes, refresh sempre falhava com "Chrome não respondeu" mesmo com Chrome logado.

### feat(gto): endpoint `/gw-spot` para spots multiway (passthrough cru pro GW)
- `backend/gto_bot/solver_api/server.py`: nova função `query_gto_wizard_raw()` + rota `POST /gw-spot`. Cliente envia `preflop_actions` já encoded (formato GW: `R2.1-F-F-C-F-C-R11.55`) e servidor proxia com headers de auth capturados via CDP. Suporta multiway, squeeze e cold-callers — qualquer cenário que GW resolva.
- Response inclui `action_solutions[].strategy[169]` cru (frequência por hand_type 13×13) — permite extrair `hand_freqs` por mão específica no cliente.
- Validação via HAR de mão real (UTG+1 open + HJ call + BTN call + SB squeeze, BB to act): GW retorna FOLD 96.7% / RAISE 2.6% / ALLIN 0.8%.

### fix(replayer): rota `/replay/<t>/<h>` não bloqueia mais em I/O remoto GTO offline
- `backend/leaklab/gto_solver.py`: novo parâmetro `block_remote=True` em `lookup_gto`. Quando `False`, pula GTO Wizard e solver remoto, retornando apenas dados do DB local.
- `backend/api/app.py`: chamada inline em `/replay/<t>/<h>` passa `block_remote=False` — frontend responde em <1s mesmo com servidor GTO offline (antes ficava 2min em "Carregando mão..." aguardando timeout).

### fix(frontend): silencia Vercel Analytics em dev
- `frontend/src/main.tsx`: `<Analytics />` só renderiza em produção (`import.meta.env.PROD`). Elimina 404s espúrios em `/_vercel/insights/view` durante `npm run dev`.

---

## [v0.163.0] — 2026-05-25 — feat(preflop): integração GTO Wizard v3 (900 spots 9-max nativo)

### Why
JSON RegLife v2.3.0 tinha bug sistemático de extração de pixels (cor azul-petróleo classificada como fold). Pares premium QQ-77 frequentemente apareciam em `fold_hands` em spots vs_RFI, gerando feedback errado para alunos. Substituído por JSON master coletado direto da API GTO Wizard via HARs navegando o tree do app — 900 spots GTO-quality em 9-max nativo cobrindo RFI + vs_RFI + vs_3bet + vs_4bet em 9 stacks (10-100bb).

### Coleta
- **RFI**: 72/72 (9 buckets × 8 posições openers)
- **vs_RFI**: 324/324 (9 buckets × 36 pairs opener/defender)
- **vs_3bet**: 324/324 (9 buckets × 36 pairs opener/3-bettor)
- **vs_4bet**: 180/180 (5 buckets 30-100bb × 36 pairs; ≤20bb não tem 4-bet sized)
- **Total: 900 spots GTO-Wizard puros**

### Mudanças no engine
- `preflop_gto_ranges.py:_POS_NORM`: agora 9-max nativo (UTG, UTG+1, UTG+2, LJ, HJ, CO, BTN, SB, BB). Mapeia 8-max → 9-max (MP → UTG+1; MP2 → UTG+2). Legacy UTG1 → UTG+1.
- `preflop_gto_ranges.py:analyze_preflop()` RFI: adapter detecta formato v3 (campo `open_pct` presente) vs v2 (`pct`). v3 usa `raise_hands`+`allin_hands` separados; recomendação derivada via `in_raise`/`in_allin`. Compat v2 preservada como fallback.
- `preflop_gto_ranges.py` vs_RFI: aliases simplificados — `UTG+1` agora é nativo (não precisa mais converter pra MP).
- **Workaround Backlog #17 removido** — pares premium QQ-77 vinham bugados no RegLife; JSON v3 tem dados corretos.

### Arquivos novos
- `backend/scripts/parse_gw_har.py` — parser HARs do GW (9-max nativo, categorização rfi/vs_rfi/vs_3bet/vs_4bet)
- `backend/scripts/fetch_gw_passive.py` — captura passiva via CDP (fallback)
- `backend/scripts/fetch_gw_rfi.py` — coleta RFI via Playwright (deprecated em favor de HAR manual)
- `backend/docs/ranges_gto/master_gw_ranges.json` — JSON master 9-max (fonte da verdade)
- `backend/docs/ranges_gto/{vs_rfi,vs_3bet,4bet}/*.har` — HARs fonte (200+ arquivos, organizados por opener)
- `backend/docs/leaklab_gto_ranges.bak.pre_gw_v3.json` — backup do JSON RegLife v2.3.0

### Reprocessamento
- 1118 decisions verificadas, **208 atualizadas** com novo JSON v3
- 208 mudanças adicionais via reconcile_label

### Testes
- Suite engine: 194/196 OK
  - `vs_rfi_88_call_in_range`: fixture esperava False, v3 mostra True (correto — RegLife antigo tinha bug)
  - `test_postflop_error_rate_reduced`: pré-existente (não relacionado)
- `test_engine_internal_consistency`: **91 violations residuais** (era 24 com v2). Causa: v3 tem ranges mais accurate, expondo decisions antes mascaradas pelo RegLife bugado. Follow-up: revisar `_reconcile_label` para promover label quando best_action diverge significativamente.

### Próximas categorias (não cobertas ainda)
- **Squeeze** (multiway 3-way) — ~450 spots
- **vs Squeeze** — ~450 spots
- 5-bet+ — ~50 spots

### Files
- **Changed**: `backend/leaklab/preflop_gto_ranges.py` (POS_NORM, RFI adapter, vs_RFI aliases, workaround removido)
- **Changed**: `backend/docs/leaklab_gto_ranges.json` (← `master_gw_ranges.json`)
- **New**: `backend/scripts/parse_gw_har.py`, `backend/scripts/fetch_gw_passive.py`, `backend/scripts/fetch_gw_rfi.py`
- **New**: `backend/docs/ranges_gto/` (master + HARs fonte)
- **New**: `backend/docs/leaklab_gto_ranges.bak.pre_gw_v3.json` (backup)

---

## [v0.162.0] — 2026-05-23 — fix(preflop): workaround para pares premium QQ-77 em vs_RFI

### Why
Descoberto que JSON `leaklab_gto_ranges.json` v2.3.0 tem bug sistemático de extração: cor azul-petróleo RGB(59,128,155) do PDF RegLife — que representa **call** — foi classificada erroneamente como **fold** pelo `extract_vsrfi_ranges.py`. Resultado: pares premium (QQ, JJ, TT, 99, 88, 77) e mãos como QJo apareciam em `fold_hands` em vários spots vs_RFI. Aluno com QQ defendendo open recebia "leak" se desse call — feedback completamente errado em centenas de mãos do banco.

### Fix temporário (Backlog #17 mantém solução definitiva)
- `backend/leaklab/preflop_gto_ranges.py:269-276`: guard em `analyze_preflop` para cenário `vs_rfi`. Quando hero tem QQ-77 e o lookup do JSON retorna `in_range=False`, força `in_range=True` com recomendação `jam` (stack ≤20bb) ou `call` (>20bb). Não aplica em PF zone (≤12bb usa lógica push/fold separada).
- Não corrige o JSON nem o Range Panel do frontend (esse continua mostrando QQ azul = fold no grid)
- Resolve impacto direto no Decision Card (verdict + recomendação)

### Validação
- Reprocessamento: 1118 decisions, **80 atualizadas** + 80 reconcile
- Test consistency: 24 → 25 violações (categorias residuais não cobertas pelo workaround)
- Suite engine: 33/33 OK

### Tentativa anterior (rejeitada)
Tentei re-extrair via pixel (opção C do plano). Descobri 2 bugs aninhados:
1. Cor azul-petróleo classificada como fold (corrigi)
2. `_detect_y_bounds` captura área errada em PNGs 100bb (apenas 1.7% pixels brancos vs 45-55% nos 17-20bb) — layout do PDF varia por stack

Re-extração pixel exigiria 1-2 dias de calibração. JSON e script restaurados via backup `leaklab_gto_ranges.bak.v2.3.0.json`. Solução definitiva (D) — validação programática contra GTO Wizard — documentada em Backlog #17.

### Files
- **Changed**: `backend/leaklab/preflop_gto_ranges.py` (+11 linhas guard)
- **New**: `backend/docs/leaklab_gto_ranges.bak.v2.3.0.json` (backup pré-tentativa)

---

## [v0.161.0] — 2026-05-23 — feat(replayer): DecisionCard template único + coerência verdict×math

### Why
Replayer mostrava 6+ variações de card (preflop, postflop math, push/fold banner, sem-GTO banner, spot-incompatível banner, conflito footnote) com layouts diferentes. Pior: inconsistências semânticas exibidas (verdict "Correto" + frase "Call lucrativo" + math card "Fold −EV") porque math card usava `pot_odds_equity` bruto enquanto engine classifica com `adjusted_required_equity` (pot_odds + realization_adj + pressure_adj).

### Fix 1 — DecisionCard template único (5 slots fixos)
Novo `frontend/src/components/replayer/DecisionCard.tsx`: template aplicado a TODOS os spots.
- **Slot 1** Verdict bar: icon + label + source badge + toggle 👁
- **Slot 2** Action comparison: Você jogou (+ Recomendado quando diverge)
- **Slot 3** Evidence: 1 widget primário (range bar | math card | solver bars | equity bar)
- **Slot 4** Indicators: chips/rows secundários (audit, SPR, Sizing) — sempre visíveis
- **Slot 5** Context footer: Stack · M · ICM

Toggle 👁: revela frase Why + pro_notes. Profissional vê só dados; iniciante ativa explicação.

Source badges com cor distinta: `Solver` (roxo), `Preflop` (foreground), `Engine` (muted), `Heurística` (cinza), `Push/Fold` (amber), `Spot N/A` (orange).

### Fix 2 — Banners separados eliminados (–193 linhas líquidas)
- Push/Fold Zone → source badge amber + frase no Why
- Sem cobertura GTO → source badge cinza + frase no Why
- Spot incompatível → source badge orange + frase no Why
- Conflito Engine vs GTO footnote → frase no Why quando diverge

### Fix 3 — Duplicação visual removida
- `✓` extra na coluna "Você jogou" (já existe `✓ Correto` no banner)
- "Fold 85% · Raise 15%" abaixo das barras do GtoStrategyPanel
- Audit trail movido para toggle (era sempre visível, redundante)

### Fix 4 — Tipografia consolidada (5 tamanhos → 3 níveis 10/11/13)
Opacidades agressivas (`/30`, `/40`, `/45`) substituídas por `text-muted-foreground`. Resolve violação WCAG SC 1.4.4 (texto em `[8px] opacity-40`).

### Fix 5 — Frase Why descreve a ação tomada, não a alternativa
Antes: `"Call lucrativo — equity 37% supera pot odds 33%"` aparecia mesmo quando hero foldou. Agora: para fold mostra `"Fold correto"`, `"Fold defensável (break-even)"` ou `"Fold deixou EV na mesa"` conforme margem.

### Fix 6 — adjusted_required_equity exposto ao frontend (coerência verdict × math)
- `backend/api/app.py`: endpoint do Replayer agora retorna `thresholds` do engine e popula `tech.adjusted_required_equity` no step
- `frontend/src/lib/api.ts`: novo campo `adjusted_required_equity?: number`
- `frontend/src/pages/Replayer.tsx`: `req = step.adjusted_required_equity ?? poRaw` — math card e frase Why usam o mesmo critério que o engine usa para classificar
- Math card label vira `"Equity Necessária"` (tooltip com pot odds bruto) quando há ajuste relevante
- Caso resolvido: fold com SPR 0.6, pot_odds=33%, eq=37%, adjusted=37% → verdict `Correto`, badge `Fold +EV`, frase `"Fold defensável — break-even"` — tudo coerente

### Fix 7 — Backend guard: fold com equity ≥ pot_odds + 3pp promove para small_mistake
`decision_engine_v11.py:apply_anti_rules`: nova regra postflop. Fold com `equity − pot_odds ≥ 3pp` + `label='standard'` é promovido para `small_mistake` + `best_action='call'`. Test unit `test_anti_fold_plus_ev_promotes_standard` cobre 4 casos. Reprocessamento aplicou em **89 decisions** + 76 mudanças via reconcile.

### Fix 8 — Test consistency interna
Novo `tests/test_engine_internal_consistency.py`: invariantes label/best_action/gto_label. Sessão: **85 → 24 violações (−72%)**. Resíduo é preflop sem pot_odds (backlog).

### Files
- **New**: `frontend/src/components/replayer/DecisionCard.tsx`, `backend/scripts/reanalyze_all_labels.py`, `backend/tests/test_engine_internal_consistency.py`
- **Changed**: `frontend/src/pages/Replayer.tsx` (–193 linhas líquidas), `frontend/src/components/replayer/GtoStrategyPanel.tsx`, `frontend/src/lib/api.ts`, `backend/api/app.py`, `backend/leaklab/decision_engine_v11.py`, `backend/tests/test_decision_engine.py`

---

## [v0.160.0] — 2026-05-23 — fix(engine): revalidação reduz majors 32 → 2 (-94%)

### Why
Relatório `revalidation_run_1` detectou 32 majors (2.9% das 1122 decisões). Em 4 padrões:
- 19 casos `engine='bet'` vs `oracle='raise'` em preflop (60%)
- 5 casos postflop jam não enumerado (16%)
- 5 casos multiway iso engine recomendava raise quando oracle diz call
- 3 casos SB push/fold engine sugeria call

### Fix 1 — bet↔raise preflop normalize (cobre 19/32)
- `decision_engine_v11.py`: guard `raise → bet` quando `facingSize=0` só dispara em **postflop**. Preflop RFI continua sendo `raise` (existe BB facing implícito)
- `revalidation/differ.py`: nova `_norm_for_compare(action, street)` trata `bet ↔ raise` como equivalentes em preflop. Postflop mantém distinção
- `revalidation/orchestrator.py` passa `street` ao differ

### Fix 2 — Push/Fold zone no engine (cobre 3/32 + extras)
- `preflop_range_evaluator.py`: `_recommended_action` ganha parâmetro `stack_bb`. Quando `stack_bb ≤ 14bb` (PF zone), retorna apenas `jam` ou `fold` — nunca `call`/`raise`/`limp`
  - core_range → jam (todas posições)
  - borderline → jam (BTN/SB/CO/HJ/LJ/MP), fold (UTG/UTG+1)
  - outside → fold
- `evaluate_preflop_range` extrai stack do state e passa adiante

### Fix 3 — postflop jam awareness (cobre 5/32)
- `decision_engine_v11.py`: quando GTO postflop sem strategy_json mas com `gto_label=gto_critical`, override `bestAction = gto.gto_action`. Antes só capeava o label, agora também corrige a recomendação (call → allin quando solver diz jam)

### Fix 4 — heurístico facing ≥ 2bb (cobre 5/32)
- `preflop_range_evaluator.py`: threshold de facing para tighter logic baixou de 3bb → **2bb**. Cobre iso-over-limp típicos (2-2.5x) que antes não disparavam set-mine/call para borderline

### Tweak adicional — oracle alts agressivas
- `revalidation/oracle.py:_heuristic_potodds`: quando `equity ≥ 0.55`, adiciona `raise` como alternative. Permite que engine.raise vs oracle.call vire `acceptable_alt` em vez de `major` quando hero tem equity confortável

### Resultados (1122 decisões)
| Métrica | Run #1 (baseline) | Run #4 (pós-fix) | Δ |
|---|---:|---:|---|
| Aligned | 89.5% | **98.3%** | +8.8pp |
| Major mismatch | 32 (2.9%) | **2 (0.2%)** | **-94%** |
| Acceptable alt | 79 (7.0%) | 15 (1.3%) | -64 (viraram aligned) |

### Majors residuais (2 — aceitos)
- **AQs UTG+2 30bb equity=0.49 facing iso**: spot mixed (4-bet ou call ambos GTO); equity abaixo do threshold 0.55 do oracle alt
- **K7s BTN 12bb vs all-in massivo**: PF zone heurístico recomendou jam, spot real é vs-shove com equity ruim — distinção que requer detecção de "facing all-in" no heurístico (TODO futuro)

### Validated
- Suites engine 194/195 (1 falha pré-existente postflop, sem relação), database 36/36, audit 8/8, reconcile 5/5
- Reprocess completo (1122 decisions) + sync + reconcile aplicados

### Próximo passo natural
- Refinar oracle/engine para spots vs-all-in (PF zone com facing >> stack)
- Considerar `revalidation_run_5` após mais torneios serem importados

---

## [v0.159.0] — 2026-05-22 — feat(push-fold): banner explícito + reconcile não mascara leak

### Added
- **Banner Push/Fold Zone no Replayer**: quando hero está em preflop com `stack_bb ≤ 12`, exibe banner âmbar explicando que apenas JAM ou FOLD são GTO em short stack. Esclarece dúvida do aluno sobre "por que call é leak"

### Fixed
- **`_reconcile_label` não mais mascara limp/call em push/fold zone**: antes, `gto_mixed → label='standard'` sempre. Agora: em PF zone (stack≤12bb preflop), se hero não-jam/fold com `gto_mixed`, demota para `small_mistake`. Não é "standard" limpar QTs UTG 10bb mesmo se GTO tiver 35% limp na strategy
- Assinatura de `_reconcile_label` ganha parâmetros opcionais `stack_bb`, `street`, `action_taken` para contexto. Callers em `update_decision_gto`, `resync_gto_labels_for_node`, `reconcile_tournament_labels` passam os campos do DB
- Função auxiliar `_is_pf_zone(stack_bb, street)` encapsula a heurística (≤12bb + preflop)

### Why
- **Reportado pelo usuário**: hand 260605903016 (QTs UTG 10.2bb, limp em zona push/fold) — engine via que era PF (best_action='jam') e GTO retornou gto_mixed → reconcile fazia `label='standard'`. Aluno via "decisão standard" mascarando o leak real
- Após fix: `label='small_mistake'`, gto_label permanece gto_mixed, mas aluno vê leak corretamente no dashboard

### Reprocess feito (decisão do user)
- Re-rodada do engine em todos os 10 torneios (1122 decisions) para aplicar fixes acumulados v0.151-v0.158 (is_3bet contextual, _POS_NORM corrigido, heurístico facing 3-bet+)
- Backup automático em `data/leaklab.backup.20260522_*.db`
- Cobertura GTO: 89.8% (postflop solver nodes reconectados via lookup natural)
- 4 labels reconciliados pelo demote PF

### Validated
- QTs UTG 10.2bb limp (id=28797): `label standard → small_mistake` ✓
- TypeScript verde, suite database 36/36, reconcile phase2 5/5

### Não fiz (deliberadamente)
- **A) Override de label em PF zone sem GTO** (escopo original): pulado pois B+C resolvem o caso do usuário. Pode ser adicionado se aparecerem outros casos sem gto_label em PF zone

---

## [v0.158.0] — 2026-05-22 — fix(heuristic): facing 3-bet+ vira set-mine/call para borderline + banner "Sem cobertura GTO"

### Fixed
- `_recommended_action` em `preflop_range_evaluator.py`: quando `facing_size >= 3bb` (hero enfrenta 3-bet ou squeeze), borderline hands (small pairs 44-77, suited connectors, broadway weak como K9s) → recomenda **call** (set-mine / implied odds) em vez de raise. Premium core hands (88+, broadway suited) em IP ainda podem 4-bet, OOP preferem call
- **Reportado pelo usuário**: hand 260886194685 (K9s UTG 44.9bb facing 4bb 3-bet + cold caller) — engine recomendava raise quando GTO correto é call/fold. Após fix: recomenda **call**

### Added
- Banner "Sem cobertura GTO" no Replayer: quando uma decisão do hero não tem `gto_label` (spot multiway sem solução pré-computada), exibe nota explícita explicando que a recomendação vem do engine heurístico, com confiança moderada, e que detalhes profissionais não estão disponíveis para esse tipo de spot

### Why
- Antes: usuário via "Recomendado: raise" em spot multiway sem entender que não havia dados de solver e a recomendação era heurística genérica que ignorava o facing_size grande
- Agora: heurístico sabe que facing 3-bet+ ≠ facing RFI; UI deixa transparente quando a fonte é heurística vs GTO

### Limitação
- Opener facing squeeze (open + 3bet + cold caller, hero=opener) continua sem cobertura GTO na conta atual do GW (`MTTGeneral` antigo retorna 204 para esses spots). Cobertura completa exigiria upgrade do plano GW para `MTTGeneralV2`

### Validated
- K9s UTG facing 4bb → recomenda `call` (era `raise`)
- 4c4s LJ facing 4bb → recomenda `call` (set-mine)
- AA UTG facing 4bb → recomenda `call` (OOP prefer manter range)
- AA BTN facing 4bb → recomenda `raise` (IP 4-bet)
- Sem facing (RFI): comportamento inalterado
- TypeScript verde, suite database 36/36 verde, engine 194/195 (1 falha pré-existente em test_postflop_error_rate_reduced, sem relação)

---

## [v0.157.0] — 2026-05-22 — fix(preflop): mapping 9-max → 8-max corrigido (MP1→HJ, MP2→CO)

### Fixed
- **Bug estrutural no `_POS_NORM`** (introduzido no commit 30fb9e7 em 10/maio): `MP1` colapsava para `LJ` e `MP2` para `HJ`, causando colisão geométrica quando o opener era `UTG+2` (também `LJ`)
- Quando hero=MP1 e opener=UTG+2, lookup virava `vs_RFI[LJ][LJ]` (não existe) → `available=False` → engine caía no heurístico genérico que recomendava raise mesmo com small pairs (set-mining seria correto)
- **Reportado pelo usuário**: hand 260886154914 (MP1 com 44 vs UTG+2 raise + UTG+1 limp, 70bb) — engine recomendava raise quando GTO correto é fold/call (set-mine)

### Changed
- `_POS_NORM` em `preflop_gto_ranges.py`: MP1 agora → HJ; MP2 → CO (mapping geométrico por índice de ação 9-max → 8-max)
- Mesma correção aplicada em `gto_bot/solver_api/server.py`, `scripts/enqueue_preflop_gw.py`, `scripts/compare_ranges_gw.py`, `scripts/validate_reglife_coherence.py` para consistência

### Validation feita antes do fix
- **V1 git blame**: confirmado commit de origem (30fb9e7), intenção era resolver `available=False` mas mapping foi geometricamente errado
- **V2 escopo real**: apenas 26 decisions afetadas (2.4% do banco) — 16 com position=MP1 + 10 com vs_position=MP1; zero MP2
- **V3 convenção**: 9-max PokerStars → 8-max RegLife: UTG+2 é 3ª (LJ), MP1 é 4ª (HJ), MP2 é 5ª (CO)
- **V5 tests**: nenhum test pinning este mapping; safe para mexer

### Validated post-fix
- Hand reportada (id=27337, 44 MP1): antes `gto_label=None` → agora `gto_correct, gto_action=fold` ✓
- 23 decisions re-syncadas com sucesso
- Cobertura GTO: 98.0% → 98.2%
- Suites database (36) verde. Falha em test_postflop_error_rate_reduced é pré-existente (não relacionada com preflop)

### Limitação documentada
- `_POS_NORM` continua collapsing 9-max → 8-max (lossy por design — não temos ranges 9-max no RegLife). Para conta com `MTTGeneralV2` no GW (9-max nativo), seria possível usar mapping 1:1 — fica como melhoria futura

---

## [v0.156.0] — 2026-05-22 — feat(study-plan): item #9 do backlog — plano de estudos GTO-first

### Added — Helper unificado em repositories.py
- `get_leak_ranking_gto_first(user_id, days, last_n, limit)` — retorna `{source, leaks}`:
  - Tenta `get_gto_leak_ranking` (GTO) primeiro
  - Fallback para `get_leak_roi_impact` (heurístico) quando GTO está vazio
  - Retorna `source='empty'` se ambos vazios
- Reutilizado por todos os endpoints que consomem leak ranking para recomendações

### Endpoints refatorados (GTO-first com fallback transparente)
- `/coach/student/<id>/study-plan` (coach gerando plano para aluno)
- `/study/plan` (aluno gerando próprio plano)
- `/coach/chat` (AI Coach conversacional)
- `/coach/context` (contexto greeting do AI Coach)
- `/history/evolution` (dashboard de evolução)
- `/coach/student/<id>/history` (dashboard do coach com leaks do aluno)
- `recommend_coaches_for_leaks` em repositories.py (recomendação de coaches)

### LLM Coach narrative atualizado
- `generate_study_plan()` ganha parâmetro `leak_source: str` e:
  - Inclui nota de fonte no prompt do Claude (alta confiança GTO vs moderada heurística)
  - Retorna `source` no payload final para frontend
- `coach_chat_reply()` ganha parâmetro `leak_source` que contextualiza a confiança da fonte ao Claude

### Frontend
- `StudyPlanResponse`, `EvolutionResponse`, `CoachContext` types ampliados com `source`/`leak_source`
- `StudyPlan.tsx`: badge "GTO" (verde) ou "Heurístico" (cinza) no header do plano de estudos, com tooltip explicando precisão
- i18n nas 3 locales: chaves novas `source.gto`, `source.heuristic` + tooltips

### Why
- Antes: plano de estudos, AI Coach e recomendações usavam `get_leak_summary` (heurístico) como fonte primária — gerava recomendações inconsistentes com o que o aluno via no Replayer
- Agora: tudo passa por `get_leak_ranking_gto_first` — recomendações refletem análise GTO real quando disponível, com fallback transparente quando não há cobertura
- Alinhado com Ghost Table/Sparring GTO-only (v0.146.x) e Fase 3 do item #2 (v0.151.0)

### Validated
- Smoke test: `get_leak_ranking_gto_first(13, 90)` retorna `source='gto'`, 10 leaks (banco real do user)
- Suites database (36) + api (64) — todas verdes, zero regressão
- TypeScript verde

### Próximo
- Item 3 (multiway equity HU) ou Item 10 (cap 100bb) ou Item 12 (Range Grid postflop)

---

## [v0.155.0] — 2026-05-22 — feat(gto): engine consome vs_squeeze (squeeze multiway com cobertura GTO)

### Added — `analyze_preflop` agora reconhece scenario `squeeze`
- `analyze_preflop()` ganha parâmetro `caller_position` (str): quando preenchido junto com `vs_position` em pote 3-bet, scenario passa a ser `'squeeze'` em vez de `'vs_3bet'`
- Lookup acontece em `bk_data['vs_squeeze'][<pos>_squeeze_vs_<opener>_open_<caller>_call]`
- Fallback de bucket: stack 28-29bb (bucket 30bb) cai para 40bb quando vs_squeeze não tem 30bb
- Mantém compatibilidade: sem `caller_position`, comportamento de vs_3bet inalterado

### Detector de squeeze no sync
- `_detect_squeeze_context()` em `sync_gto_labels_from_ranges.py`: parsea `raw_text` do hand history para identificar opener e cold caller. Retorna `(opener_pos, caller_pos)` quando padrão `raise + call + hero_raise` é detectado
- Mapeamento de seats → posições 8-max canonical (UTG, UTG+1, LJ, HJ, CO, BTN, SB, BB)
- Skip casos não-tradicionais (cold 4bet, limp+iso+squeeze, etc.)
- `_process_rows()` agora carrega `raw_text` por torneio (cache) e usa detector para spots `is_3bet=True`

### Bugs corrigidos durante implementação
- Regex de seats no detector: restringido ao header (antes de `*** HOLE CARDS ***`) para evitar match duplicado no SUMMARY com sufixos como "showed [...]"

### Validated
- Spot real do banco do user: decision id=26443 (CO AQs 28.5bb squeeze vs UTG+LJ) — antes sem `gto_label`, agora classificada como `gto_critical` (squeeze de AQs nesse spot deveria foldar)
- 1/2 squeeze spots reais do banco ganharam cobertura. O outro (26367, BTN KJs vs limp+iso+squeeze) é cenário não-tradicional não coberto pelo schema vs_squeeze (limper + raise ≠ raise + caller).
- Suites database (36) + audit phase 1 (8) + reconcile phase 2 (5) — todas verdes, zero regressão

### Cobertura efetiva no banco
- 2 squeezes reais identificados; 1 classificado pelo novo schema (50%)
- Pipeline pronto para qualquer torneio futuro com squeezes tradicionais

---

## [v0.154.0] — 2026-05-22 — feat(gto): ranges vs_squeeze extraídos do GTO Wizard (64 spots novos)

### Added — leaklab_gto_ranges.json v2.4.2
**+64 entries no schema novo `vs_squeeze`** (não conflita com vs_3bet/vs_4bet existentes):

Cobertura por bucket:
- **40bb**: 16 entries
- **50bb**: 16 entries (mapeia também 60bb)
- **75bb**: 16 entries (mapeia também 80bb)
- **100bb**: 16 entries

Combinações cobertas (16 únicas):
- `BTN_squeeze_vs_HJ_open_CO_call`, `BB_squeeze_vs_CO_open_BTN_call` (clássicos)
- `CO_squeeze_vs_UTG_open_UTGplus1_call`, `BB_squeeze_vs_UTG_open_UTGplus1_call`
- Outros squeezes UTG/MP/LJ/HJ/CO opener + caller intermediário

### Pipeline reprodutivel
- `extract_squeeze_ranges.py` (servidor GCP): 96 queries ao GW via Chrome CDP, decoding hand-by-hand do array `strategy[169]`. 80/96 sucesso (16 spots 30bb fora da árvore)
- **Mapping `index → hand` descoberto via probe empírico:** ranks low→high (`'2','3','4','5','6','7','8','9','T','J','Q','K','A'`), index = row*13+col, com convenção:
  - row==col → par
  - row>col → suited (rank maior primeiro)
  - row<col → offsuit (rank maior primeiro)
  - Validado com: AA=168, 23o=1, 32s=13, AKs=167
- `merge_squeeze_into_ranges.py`: merge controlado com backup automático

### Schema novo (não invasivo)
```json
"50bb": {
  "vs_squeeze": {
    "BB_squeeze_vs_CO_open_BTN_call": {
      "pct_squeeze": 0.1264, "pct_call": 0.5161, "pct_fold": 0.3575,
      "hands_4bet": "AA,KK,AKs,JJ,KTs,...",
      "hands_call": "22-77,A9s,JTs,...",
      "hands_fold": "resto",
      "hands_mixed": "...",
      "_source": "gto_wizard MTTGeneral 2026-05-22",
      "_preflop_actions": "F-F-F-F-R2.3-C-F"
    }
  }
}
```

### Validated
- Sample BTN squeeze vs HJ+CO 100bb: 10.7% squeeze (composição polarizada: AA/JJ/AKs + bluffs blocker)
- Sample BB squeeze vs CO+BTN 50bb: 12.6% squeeze + 51.6% call (BB defende wide)
- 0 erros 403 — todos os spots squeeze cobertos pela árvore atual
- Backup automático em `leaklab_gto_ranges.backup.20260522_171941.json`

### Não foi mexido
- Gametype mapping (`MTTGeneralV2` para HU, `MTTGeneral` antigo aceito) — mantido como estava
- gto_nodes cache — não tocado (reverti rollback dos inserts experimentais)
- Engine `analyze_preflop`, `compute_spot_hash` — não modificados
- Lookup atual continua funcionando para os cenários cobertos hoje

### Próximo passo natural
- Engine ainda não consome `vs_squeeze` (estrutura nova). Quando consumir: detectar spot multiway com cold caller em `pipeline.py` e chamar lookup no novo schema. Fica como sprint separada.

---

## [v0.153.0] — 2026-05-22 — feat(gto): benchmark + cache populado via GTO Wizard (100 spots preflop)

### Added
- Pipeline benchmark em 3 passos (separação local ↔ servidor GCP):
  - `bench_step1_prepare.py` (local): sample 100 spots preflop diversos do DB, parsea raw_text do hand history, reconstrói `preflop_actions` no formato GW
  - `bench_step2_call_gw.py` (servidor GCP): chama API GW via Chrome CDP (porta 9222), salva responses brutos
  - `bench_step3_persist.py` (local): persiste em `gto_nodes` usando `stack_bucket` canônico do projeto
- Confirmado empiricamente: gametype `MTTGeneral` é **8-max** (não 9-max). Mapping fold-count → posição: 0=UTG, 1=UTG+1, 2=LJ, 3=HJ, 4=CO, 5=BTN, 6=SB

### Cache populado
- **gto_nodes preflop: 46 → 97** (+51 novos)
- Distribuição: 0-10bb (15), 10-20bb (19), 20-35bb (38), 35-60bb (16), 60-100bb (5), 100bb+ (4)
- Cada node tem `strategy_json` rico (frequências por família de ação)

### Stats benchmark (100 spots preflop)
| HTTP status | Count | Significa |
|---|---|---|
| 200 OK | 51 | Estratégia retornada |
| 204 No Content | 39 | Spot existe na árvore mas sem solução na conta |
| 403 Forbidden | 10 | Sem permissão (vs_3bet/multiway na maioria) |

### Limitações descobertas e documentadas
- A conta atual NÃO tem acesso a `MTTGeneralV2` (V2 retorna 403 para tudo). Mantido `MTTGeneral` (antigo)
- Comparação "agree/disagree" inicial estava comparando NÍVEIS DIFERENTES (ação dominante do range completo vs ação tomada com mão específica) — **inválida**. Benchmark hand-by-hand requer descobrir ordem do array `strategy[169]` retornado por action_solution (TODO próximo passo)
- Multiway (squeeze, cold 4-bet) e vs_3bet pré-resolvidos na árvore atual: maioria retorna 204 — cobertura limitada para estes cenários

### Recovery do erro de bucket
- Primeira leva de 51 inserts usou stack_bucket no formato `Xbb` puro (`50bb`, `60bb`) inconsistente com o resto do projeto (`X-Ybb` range). Foram revertidos e re-inseridos usando `leaklab.gto_utils.stack_bucket()` canônico
- Backup automático criado antes da operação

### Próximo passo (pendente decisão)
- Para benchmark hand-by-hand real: descobrir mapeamento do array `strategy[169]` em cada `action_solution` (ordem das 169 hands em row-major do grid 13×13). Via probe direcionado, ~15min de trabalho.

---

## [v0.152.0] — 2026-05-22 — feat(gto): cobertura vs_3bet/vs_4bet completa (item #13 backlog)

### Added — leaklab_gto_ranges.json v2.4.1
**+19 entries vs_3bet** preenchendo gaps (NÃO sobrescreve entries existentes):
- 100bb: MP, LJ, HJ, SB
- 75bb: MP, LJ, HJ, CO, SB
- 50bb: MP, LJ, HJ, CO, SB
- 30bb: MP, LJ, HJ, CO, SB

**+18 entries vs_4bet** (cenário 3-bettor enfrentando 4-bet):
- 100bb / 75bb / 50bb: MP, HJ, CO, BTN, SB, BB
- Convenção: `<POS>_3bet_vs_4bet`. Engine ainda não consome (requer fix posterior em `analyze_preflop` se quiser usar)

### Pipeline
- `backend/docs/external_ranges/`: charts MIT do AHTOOOXA/poker-charts (Greenline + Pekarstas, 100bb 6-max cash) como fonte
- `backend/scripts/parse_external_ranges.py`: TS → JSON normalizado
- `backend/scripts/synthesize_missing_vs3bet.py`: agrega greenline+pekarstas por voto majoritário, mapeia 6-max → 8-max, aplica stack compression para 30/50bb
- `backend/scripts/validate_gaps.py`: sanity checks (4bet ⊆ RFI, AA/KK em 4-bet, spot check da hand reportada)
- `backend/scripts/merge_gaps.py`: merge controlado com backup automático

### Mapeamento 6-max → 8-max
- UTG → UTG; MP_6max → LJ_8max (via `_POS_NORM` existente); HJ → HJ (mapeia também MP2); CO/BTN/SB/BB → identidade
- LJ usa range de UTG_6max (mais tight); HJ usa MP_6max

### Stack compression
- 100bb / 75bb: identity
- 50bb: remove hands marginais do call range (A2s-A8s, T9s, 76s, etc.)
- 30bb: compression mais agressiva (remove broadway suited marginais, pares médios)

### Validated
- Sanity check passou (2 errors em SB são consequência do SB RFI estar anomalamente tight no JSON original, não dos novos ranges)
- Spot check: HJ 75bb vs CO 3-bet com A8s → fold ✓ (mão reportada pelo usuário)
- Cobertura GTO atual: 98.0% (já estava no mesmo nível desde fix de detecção de is_3bet — os novos ranges agora servem como base estrutural para análises futuras com cenários HJ/CO/SB vs 3-bet)
- Backup do JSON original em `backend/docs/leaklab_gto_ranges.backup.20260522_121305.json`

### Limitações
- Fontes Greenline + Pekarstas são 6-max 100bb cash; adaptação para 8-max MTT é aproximada (~5% diferença no range real esperado)
- Stack compression para 30/50bb é heurística baseada em conceitos GTO, não solver-exato
- vs_4bet não consumido pelo engine ainda (requer fix em `analyze_preflop` se desejar uso ativo)
- Multiway spots (squeeze, cold 4-bet, limpers) continuam sem cobertura — próximo natural é GTO Wizard

---

## [v0.151.2] — 2026-05-22 — fix(gto): cobertura vs_3bet — detecta is_3bet_pot por contexto

### Fixed
- **Bug crítico de cobertura vs_3bet**: `pipeline.py` marcava `is_3bet=True` somente quando o hero **dava** um 3-bet (action='raise' + facing_size>0). Quando o hero **foldava ou callava** ao 3-bet do villain, a flag ficava False — o engine acabava tentando lookup vs_RFI e retornando `available=False`, deixando `gto_label=None`
- Fix em `scripts/sync_gto_labels_from_ranges.py`: nova função `_build_vs3bet_context()` faz lookup intra-hand — se hero já deu raise antes nessa mesma hand preflop, a decisão seguinte com `facing_bet > 0` é semanticamente vs_3bet, independente da ação tomada
- Adicionado `hand_id` aos SELECTs do sync (preflop)

### Why
- Reportado pelo usuário: torneio 4002336128, hand 260886143567, decision id=27336 (fold A8s do HJ vs CO 3-bet) estava com `gto_label=None`. Após o fix, classificada como `gto_correct` — fold A8s vs 3-bet está fora do range de continuação (22%)
- Ranges vs_3bet **já estão** integrados no `analyze_preflop` (`preflop_gto_ranges.py:303-324`) e no JSON `leaklab_gto_ranges.json` para 30bb/50bb/100bb com fallback para outras posições/stacks. O bug era só na detecção do cenário

### Validated
- Cobertura GTO global: 96.9% → **98.0%** após sync global
- 13 decisions ganharam cobertura (4 no torneio 199 + 9 nos demais)
- Suites: database 36/36, audit phase 1 8/8, reconcile phase 2 5/5

### Backlog
- Item #13 (Ranges vs_3bet por posição) parcialmente atendido: a infra existe e funciona; falta completar tabela vs_3bet para 10/14/17/20/40/75bb e para posições HJ/CO/LJ/MP/SB nos stacks que já têm dados. Fica como continuidade do item #13

---

## [v0.151.0] — 2026-05-22 — feat(dashboard): Fase 3 do backlog #2 — transparência GTO no dashboard

### Backend
- `get_tournaments` (`repositories.py`): retorna `labels_reconciled_at` e `gto_coverage_pct` por torneio (calculado on-demand a partir de decisions.gto_label)
- `get_breakdown` (`repositories.py`): retorna `gto_coverage_pct`, `total_decisions` e `with_gto` no payload
- `/player/leak-roi` (`app.py`): retorna `{source: 'gto' | 'heuristic', leaks: [...]}` em vez de só a lista — frontend agora sabe a fonte explícita

### Frontend
- `Tournament` type (`api.ts`): novos campos opcionais `labels_reconciled_at` e `gto_coverage_pct`
- `metrics.leakRoi`: response type ampliado para incluir `source`
- `RecentTournamentsTable`: badge "Análise GTO em andamento" (loader animado) quando `labels_reconciled_at == null` — substitui o badge "Analisado". Quando reconcile concluído, badge "Analisado" passa a exibir `· X% GTO` ao lado (cobertura)
- `LeaksPanel`: badge "GTO" (verde) ou "Heurístico" (cinza) no header, sinalizando a fonte do ranking. Tooltips explicam a diferença
- i18n nas 3 locales (pt-BR, en, es): chaves novas em `table.gtoPending`, `table.gtoCoverage`, `leaks.sourceGto`, `leaks.sourceHeuristic` e tooltips

### Decisão
- `DecisionQualityCard.tsx` é órfão no projeto (não é importado em nenhum lugar) — task de aplicar badge nele foi descartada por irrelevância. Foco ficou nos cards efetivamente usados (`GtoQualityCard` já mostra coverage no header; agora `RecentTournamentsTable` e `LeaksPanel` também)

### Validated
- TypeScript compila sem erros (`npx tsc --noEmit`)
- Smoke test backend: endpoint `/player/leak-roi` registrado; `get_tournaments` retorna os novos campos no banco real
- Suites: database 36/36, fase 1 audit 8/8, fase 2 reconcile 5/5, api 64/64

### Next
- Fase 4: leak ranking com `source` propagado para o LLM Coach e plano de estudos (alinhado com item #9 do backlog)

---

## [v0.150.0] — 2026-05-22 — feat(reconcile): Fase 2 do backlog #2 — reconciliação observável e backfill

### Added
- Coluna `tournaments.labels_reconciled_at` (TIMESTAMP, SQLite + PostgreSQL) — marca quando o reconcile rodou pela última vez. Frontend pode usar para mostrar "análise GTO em andamento" quando NULL
- `POST /admin/reconcile-tournament/<tournament_db_id>` (require_admin) — força sync preflop + reconcile manual; retorna `{tournament_id, preflop_synced, reconciled, labels_reconciled_at}`
- `backend/scripts/backfill_label_reconciliation.py` — itera torneios e reconcilia tudo. Modos: `--dry-run`, `--user-id`, `--since`, `--no-sync`. Reporta pending antes e reconciliations realizadas
- `backend/tests/test_label_reconcile_phase2.py`: 5 testes cobrindo migration, reconcile com/sem mudanças, backfill dry-run e execução normal

### Changed
- `reconcile_tournament_labels` agora seta `labels_reconciled_at = CURRENT_TIMESTAMP` ao final, mesmo quando 0 mudanças — assim o dashboard sabe que a análise GTO foi aplicada

### Validated
- Backfill rodado no banco local: 105/105 decisions reconciliadas em 9 torneios
- Auditoria pós-backfill: 0 pending (era 105 = 9.66%)
- Suites database (36) + api (64) + audit phase 1 (8) + phase 2 (5) verdes

### Note
- Fase 2 originalmente previa fallback de hash matching em `resync_gto_labels_for_node` (Furo C), mas a auditoria reportou 0 divergências live vs stored no banco atual. Sem evidência do problema, o fallback foi adiado — o audit C continua sendo a detecção contínua. Será revisitado se aparecerem casos

### Next
- Fase 3: transparência no dashboard (badges de cobertura GTO, "análise em andamento" enquanto `labels_reconciled_at IS NULL`)
- Fase 4: leak ranking unificado com `source` explícito

---

## [v0.149.0] — 2026-05-22 — feat(audit): Fase 1 do backlog #2 — diagnóstico de coerência label vs gto_label

### Added
- `backend/scripts/audit_label_coherence.py`: script de auditoria read-only com 4 categorias:
  - **A) Reconciliação pendente** — decisions onde `_reconcile_label(label, gto_label) != label`, agrupadas por transição
  - **B) Cobertura GTO** — % de decisions com gto_label populado, por street e por posição
  - **C) Live vs stored** — decisions cujo gto_label recalculado pela strategy_json do nó atual diverge do gto_label armazenado (resync pendente)
  - **D) Confiança dos KPIs de torneio** — tournaments cujo `standard_pct` deriva de baixa cobertura GTO
  - CLI: `--user-id`, `--samples`, `--json`, `--scan-limit`
  - Função `run_audit(user_id, scan_limit)` reutilizada pelo endpoint
- `GET /admin/label-coherence` (protegido `@require_admin`): expõe o relatório em JSON, com filtros `user_id` e `scan_limit`
- `backend/tests/test_label_coherence_audit.py`: 8 testes de integração cobrindo as 4 categorias e o filtro por usuário

### Fixed
- `reconcile_tournament_labels` (`repositories.py`) substituía `except: return 0` silencioso por log estruturado (`log.exception`); agora falhas são visíveis em produção
- `_preflop_sync_and_reconcile` (`app.py`): cada etapa (sync preflop + reconcile) tem try/except próprio com logging; antes uma falha no sync abortava silenciosamente o reconcile

### Why
- Item #2 do backlog (CRÍTICO): dashboard exibia `label` heurístico enquanto Replayer mostrava `gto_label` GTO, levando o aluno a ver "Standard" no dashboard e descobrir erro crítico no Replayer
- Esta fase é diagnóstica: mede a extensão do problema antes de remediar. No banco local atual: 105 decisions (9.66%) em 9 torneios pendentes de reconciliação, dominadas por transições `standard → small_mistake (gto_critical)` (43 casos) e `clear_mistake → standard (gto_correct/mixed)` (37 casos)

### Next
- Fase 2: tornar reconcile observável (`tournaments.labels_reconciled_at`), endpoint admin para forçar reconciliação, comando de backfill
- Fase 3: transparência no dashboard (badges de cobertura GTO nos cards)
- Fase 4: leak ranking unificado com `source` explícito

---

## [v0.148.0] — 2026-05-22 — fix(replayer): call vs shove com mao premium classifica como Correto

### Fixed
- `_build_replay_data` (app.py): `_facing` era 0.0 para decisões sem `gto_label` no banco (live_decisions não carregava `facing_bet` de `gto_data` quando gto_label=None). Com facing=0.0, `analyze_preflop` entendia como spot RFI e retornava `quality='acceptable'` para KK call vs shove → exibia "Misto" sem contexto
- Correção: `_facing` agora também tenta `spot.facingSize / level_bb` quando `decision.facing_bet` não está disponível (conversão chips→BB)
- Adicionado fallback "call vs shove": quando `analyze_preflop` retorna `available=False` para um CALL com `facing >= 40% do stack`, o sistema verifica o range de abertura da mão. Se premium (RFI quality='correct') → `quality='correct'`; se borderline → `quality='acceptable'`; se fora do range → `leak`. Evita análise incorreta de spots sem dados específicos de vs_3bet
- Mesmo fallback aplicado no enriquecimento de `preflop_gto` em `all_decisions` (linha 3139)
- Campo `reasoning` adicionado ao resultado do fallback: "Mão premium em range de abertura — call de shove correto."
- Novo label de cenário no frontend: `vs_shove_fallback` → "Call vs Shove" em `RangePanel.tsx`
- `reasoning` exibido no banner de contexto GTO do RangePanel quando presente
- KK HJ 27.4bb call vs shove 17.7bb: agora classificado como "✓ Correto (GTO)" com nota de raciocínio

### Technical
- `api.ts`: tipo de `scenario` ampliado para incluir `vs_shove_fallback`; campo `reasoning?: string` adicionado ao tipo `preflop_gto`

---

## [v0.147.0] — 2026-05-22 — fix(replayer): bloqueia escrita de dados preflop agregados no banco

### Fixed
- `_build_replay_data` (app.py): terceiro vetor do bug KK — o bloco "live strategy" chamava `_upd_gto` para **todas** as streets incluindo preflop. Para KK com nó agregado (fold=72%), isso gravava `gto_action='fold'` e `gto_label='gto_minor_deviation'` no banco, corrompendo futuras consultas ao endpoint `get_decision_gto`
- Solução: o `_upd_gto` do bloco live-strategy agora é protegido por `if action.street != 'preflop'` — nós agregados nunca mais poluem o DB
- O bloco `preflop_override_action` agora também persiste os valores corretos (`gto_label`, `preflop_override_action`) no banco via `update_decision_gto`, sobrescrevendo qualquer dado incorreto que já exista
- Todos os 194 testes da suite GTO passam sem regressão

---

## [v0.146.0] — 2026-05-22 — fix(replayer): corrige bug KK na timeline de replay (_build_replay_data)

### Fixed
- `_build_replay_data` (app.py): segundo vetor do bug KK descoberto e corrigido. O bloco de "live strategy" usava `lookup_gto` para buscar a estratégia do nó — que retornava o nó **agregado** preflop (fold=72%, raise=28%). Para KK (raise no range com 28%), `live_freq=0.28 < 0.30` definia `is_error=True` mesmo quando o DB tinha `gto_label='gto_correct'`
- Adicionado bloco `preflop_override_action` na timeline: após o live-strategy block, chama `analyze_preflop` com a mão específica do herói. Se `quality in ('correct','acceptable')`: `is_error=False`, `reconciled_best=action`, `gto_label='gto_correct'`. Tem prioridade máxima sobre `live_top_act` e `gto_action` armazenado
- Novo campo na timeline: `gto_action: preflop_override_action or live_top_act or gto_action`
- 6 novos testes em `test_gto_enrichment.py` cobrindo o fluxo de override e o comportamento correto para mãos fora do range (72o UTG)

---

## [v0.145.0] — 2026-05-22 — feat(gto): blindagem total do pipeline GTO — 6 camadas de proteção

### Added
- `backend/leaklab/gto_utils.py`: `normalize_gto_action()` — canonicaliza shove/allin/all-in → jam; constantes `VALID_POSITIONS`, `VALID_GTO_ACTIONS`
- `backend/database/schema.py`: migration `is_aggregate BOOLEAN DEFAULT FALSE` na tabela `gto_nodes`
- `backend/database/repositories.py` — `insert_gto_nodes()` reescrito com sanity checks completos:
  - Rejeita nós com street/position/gto_action inválidos
  - Rejeita nós com `gto_freq` fora de `[0,1]`
  - Rejeita `strategy_json` com `freq_sum < 0.10` (dados corrompidos)
  - Marca nós preflop sem `hero_hand` como `is_aggregate=True` automaticamente
  - Normaliza `gto_action` via `normalize_gto_action()` antes de inserir
- `backend/leaklab/decision_engine_v11.py`:
  - `_validate_decision_input()` — valida stack_bb, facing_size, board cards, position antes do lookup GTO
  - `_log_gto_miss()` — logging estruturado de todos os fallbacks GTO silenciosos
  - Guard em `_enrich_gto`: strategy com `freq_sum < 0.10` descartada
  - Consistência score/label: quality=correct → `final_score = min(score, 0.08)`; acceptable → `min(score, 0.18)`
- `backend/api/app.py` — `get_decision_gto()`: campo `is_aggregate` e `gto_note` na resposta JSON
- `backend/scripts/audit_gto_nodes.py` — script de auditoria com 9 checks (C1–C9):
  - C9 detecta o padrão "KK bug" (preflop fold-dominant aggregate nodes)
  - `--fix` aplica correções seguras: normaliza ações, marca is_aggregate, limpa strategy corrompida
- `backend/tests/test_gto_utils_comprehensive.py` — 92 testes de `gto_utils.py`
- `backend/tests/test_gto_enrichment.py` — 51 testes de enrichment functions do engine
- `backend/tests/test_api_gto_endpoints.py` — 38 testes de endpoints GTO incl. regressão KK
- `backend/tests/run_all_tests.py` — suite `gto` registrada com 4 arquivos (188 testes)
- `.github/workflows/ci-cd.yml` — step dedicado `Suite GTO` (zero falhas permitidas) antes do deploy

### Fixed
- Regressão KK: nós preflop agregados não contaminam mais análise hand-specific via `is_aggregate` flag e override em `get_decision_gto()`

---

## [v0.144.0] — 2026-05-21 — fix(replayer): GTO preflop usa análise hand-specific, não estratégia agregada do range

### Fixed
- `get_decision_gto` (replayer): para streets preflop, o nó GTO da DB contém estratégia **agregada** do range (ex: "HJ abre 28% → fold 72% de todas as mãos"). O sistema usava erroneamente esse fold 72% como recomendação para KK, marcando KK open como "Desvio Leve" com "Solver → Fold"
- Adicionado bloco preflop override: após encontrar o nó, chama `analyze_preflop` com a mão específica do herói; se retornar `available=True`, sobrescreve `top_action` com a recomendação hand-specific (ex: KK → raise)
- O strategy display (fold 72% · raise 28%) é mantido como contexto do range — apenas o `gto_action` (recomendação) é corrigido

---

## [v0.143.0] — 2026-05-21 — fix(ui): corrige labels do Top Leaks e remove referência IA_CORE

### Fixed
- `LeaksPanel.tsx`: removido badge "IA_CORE v2.1" — apenas "DEMO" exibido em modo fallback
- `leaks.doing` i18n em PT-BR/EN/ES: semântica corrigida — `best_action` é a ação **recomendada** pelo GTO, não a ação errada do jogador. Labels anteriores diziam "dando X quando não devia" (invertido); agora: "deveria dar X"
- `aicoach.json` (3 locales): campo `model` corrigido de "Modelo tático v2.1" / "Tactical model v2.1" para "Claude Haiku" (modelo real em uso)

---

## [v0.142.0] — 2026-05-21 — fix(replayer): v4 dimensões e cor da borda fieis ao PS

### Fixed
- Borda refeita com dimensões medidas pixel-a-pixel na referência PS (`mesa ps.png`, 1441×767px)
  - Cor: `#242424` charcoal escuro (era mahogany quente — totalmente errado)
  - Espessura: +42px sobre o feltro (54px na imagem PS × escala 1120/1441)
  - Apenas 4 camadas de profundidade 3D (era 9), offsets sutis
  - Nenhum destaque quente — apenas linha especular `rgba(255,255,255,0.11)` na borda externa
- Feltro: `rx=435, ry=128` → ratio 3.40:1 (matches apparent oval do PS)
- CSS `rotateX` removido — perspectiva embutida diretamente no canvas (oval desenhado flat)
- Fundo: quase preto puro `#050606` com glow verde mínimo (PS-accurate)
- `CY=310, RY_SEAT=178` alinhados ao novo centro da mesa

## [v0.141.0] — 2026-05-21 — feat(replayer): v4 Canvas API — mesa ultra-realista

### Changed
- **`leaklab-replayer-v4.html`**: background da mesa migrado de SVG para Canvas 2D API
  - Maior controle de gradientes e texturas — qualidade visivelmente superior ao SVG
  - Mesa oval `rx=482, ry=172` (ratio 2.80:1 → aparente ~3.5:1 após CSS perspective)
  - Borda mahogany com 9 camadas de profundidade 3D (offset maior = face frontal mais visível)
  - Gradiente rim top-lit warm: `#8a6e54 → #6a4e38 → #422f20 → #0e0b08`
  - Catchlight externo `rgba(255,225,155,0.32)` + groove sombra 10px → separação clara feltro/borda
  - Textura de feltro: crosshatch diagonal (warp+weft, canvas clip)
  - Perspectiva reforçada: `rotateX(24deg)`, `perspective: 620px`
  - Slots de cartas comunitárias redesenhados: inset escuro com borda visível + inner glow

## [v0.140.0] — 2026-05-21 — feat(replayer): leaklab-replayer-v4 — mesa PS-quality

### Added
- **`leaklab-replayer-v4.html`**: redesign visual completo do replayer com qualidade PokerStars
  - Mesa oval ratio ~2.4:1 (era 1.9:1), igual ao PS
  - Borda 3D com 4 camadas de profundidade (bottom-face, side-face × 2, top-face) visíveis na perspectiva
  - CSS `rotateX(19deg)` com `perspective: 700px` para tilt dramático tipo casino
  - Felt verde rico com destaque central e vinheta escura nas bordas
  - Ambiente escuro com glow verde emanando da mesa (efeito luz de mesa)
  - Player pods PS-style: avatar circular (r=21) com silhueta, nameplate horizontal dark
  - Cartas sempre posicionadas ACIMA dos player spots
  - Face-down card back com padrão de diamantes e escudo LeakLab
  - Chip stacks mais altos (CH=5) com drop shadow

### Fixed
- Ghost Table: `originalMistake` removido das fases active e result (evita ancoragem)
- Ghost Table: label "Heads-up" agora só exibe quando `num_players <= 2`
- Ghost Table: painel duplicado "Você escolheu / Ação correta" removido do resultado
- Ghost Table: modal IA agora renderiza no branch full-screen correto (estava no HudLayout que não era montado)

---

## [v0.139.0] — 2026-05-21 — chore: plano Ghost Table confirmado completo

### Confirmed
- **FIX 1** (`raise→bet` guard): presente em `app.py:1057` e `decision_engine_v11.py:548` — sem aposta anterior, `raise` é normalizado para `bet`
- **FIX 2** (live GTO lookup no drill submit): `_resolve_best_action_from_node()` em `app.py:931` — mesma lógica do Replayer, com 3 fallbacks de hash e guard SPR
- **FIX 3** (`num_players` no GhostTable): `GhostTable.tsx:156` usa `Math.min(9, spot.num_players ?? 6)` — sem hardcode HU para postflop
- **FIX 4** (reset SRS): endpoint `DELETE /player/drill-sessions/reset` + botão "Reiniciar histórico de treino" na intro do Ghost Table + `drill.resetSessions()` no API client

Todos os 4 fixes do plano `fuzzy-percolating-parnas.md` confirmados implementados. Plano fechado.

---

## [v0.138.0] — 2026-05-21 — feat(gto): force-refresh todos os nós + invalidação de cache LLM

### Changed
- **`validate_nodes_vs_gw.py --force-refresh`**: re-consulta GTO Wizard para todos os 199 spots únicos das decisions postflop, substituindo nós antigos (criados com `stack_bucket` ou `solver_cli`) por estratégias com stack exato, facing_bet e num_players corretos. 235 decisions agora têm dados precisos
- **LLM cache invalidado**: 27 entradas removidas do banco (explicações geradas com gto_label antigo). Dashboard, planos de estudo e análises serão regenerados com dados corretos na próxima consulta
- **`/admin/llm-cache/clear`**: novo endpoint admin para invalidar LLM cache (banco + in-memory) sem precisar acessar banco diretamente

### Impact
- gto_critical flop: 78→80 | gto_correct flop: 40→42 | turn: distribuição rebalanceada com dados precisos de stack/facing/num_players
- Próximas explicações LLM gerarão contexto correto ("você tinha 42bb e foldou contra um c-bet de 1.6bb" vs "você tinha 50bb e...")

---

## [v0.137.0] — 2026-05-21 — fix(gto): cobertura postflop 100% — fallback root street via re-query

### Fixed
- **Fallback root street**: quando todos os retries de depth falham (facing_bet fracionário sem árvore no GW), re-consulta `query_gto_wizard` com `facing_size_bb=0`. Usa exatamente o mesmo code path que funciona, evitando interferência de sessão HTTP dos requests anteriores
- **BTN 13bb 4p facing=1.6bb**: último spot sem cobertura — agora retorna estratégia do root do flop (check 100%) via fallback

### Impact
- Cobertura postflop: **1 → 0 sem resposta** (100% de cobertura, 212/235 decisions com nó GTO)
- 1 decisão (#26960) atualizada: action=check, label=gto_critical

---

## [v0.136.0] — 2026-05-21 — fix(gto): cobertura postflop 98% — depths HU + MTTHUGeneral stacks vazio

### Fixed
- **MTTHUGeneral `stacks=""`**: HAR heads-up confirmou que o gametype HU não envia o parâmetro `stacks` (todos os outros gametypes enviam `stacks=X.125-X.125-...`). Adicionado `"stacks": ""` no `_TABLE_CONFIG[2]`
- **`_GW_HU_VALID_DEPTHS`**: depths válidos para HU completamente diferentes do 9p — `[13,14,15,16,18,20,25,26,27,28,40,41,50,51,60,61,62,63,64,65]` mapeados empiricamente. Depths 7–12 e 66+ sem solução em HU
- **`_GW_DEPTHS_BY_GAMETYPE`**: mapa gametype → lista de depths, permitindo snap e retry corretos por gametype
- **`_snap_to_valid_depth` / `_retry_depths`**: recebem `gametype` como parâmetro e usam a lista correta

### Impact
- Cobertura postflop: **4 → 1 sem resposta** (98% de cobertura, 211/235 decisions com nó GTO)
- 1 spot restante sem cobertura: BTN 13bb 4p com facing_bet=1.6 (reconstrução de action sequence para bet fracionário falha)
- 6 decisões HU propagadas com gto_label via resync

---

## [v0.135.0] — 2026-05-21 — fix(gto-server): cobertura postflop 93% — depths válidos, retry, multi-gametype

### Fixed
- **`_GW_VALID_DEPTHS`**: lista completa de 41 depths com solução no GTO Wizard MTT (mapeados empiricamente 7–200bb). GW não tem solução em todo inteiro — padrão: 7–25 contínuo, 26–60 pares+extras, depois saltos 70/80/100/130/160/200
- **`_snap_to_valid_depth`**: snap para o depth válido mais próximo (antes: inteiro mais próximo → gerava 403 em ~60% dos casos)
- **`_retry_depths` + retry on 403**: quando depth não tem solução para a posição/gametype, tenta até 4 depths alternativos em ordem de distância. Resolve CO 34bb→35bb, LJ 24bb→25bb, SB 37bb→38bb, BB 34bb 7p→35bb
- **Fallback de posição**: UTG+2 em 8-max → LJ; UTG+1 em 7-max → LJ (posição equivalente no gametype menor)
- **SB→BTN em 2p**: em mesas HU não existe posição SB — mapeado para BTN
- **Multi-gametype**: suporte a MTTHUGeneral (2p), MTTGeneral_3m/4m/5m/7m/8m e MTTGeneralV2 (9p)
- **`_postflop_preflop_seq`**: sequência preflop correta para todos os gametypes (folds para todos entre hero e BB, BB calls)

### Impact
- Cobertura postflop: **37 → 4 sem resposta** (93% de cobertura, 205/235 decisions)
- 81 decisions atualizadas com gto_action e gto_label via resync
- 4 spots sem cobertura restantes: 3 HU (MTTHUGeneral — requer HAR específico) + 1 BTN 13bb 4p

### Added
- `scripts/probe_gw_depths.py`: mapeia depths válidos por gametype empiricamente

---

## [v0.134.0] — 2026-05-20 — fix(parser): prêmio do vencedor PokerStars ("wins the tournament")

### Fixed
- **`_extract_financials`**: regex não capturava o vencedor — formato "hero wins the tournament and receives $X" usa verbos no presente ("wins"/"receives"), enquanto o código só cobria "finished...received" (lugar 2+). Fallback somava chips coletados em potes → valores absurdos (ex: +$41.106)
- Agora: vencedor capturado com `place=1` e `prize` correto

---

## [v0.133.0] — 2026-05-20 — fix(gto-server): snap de stack para depth válido no GTO Wizard

### Fixed
- **`_stack_frac`**: stacks fracionários (ex: 22.3bb → 22.425) retornavam 403 no GTO Wizard, pois GW só tem soluções em profundidades inteiras. Agora snapa para `round(stack_bb)` antes de adicionar 0.125

---

## [v0.132.0] — 2026-05-20 — fix(gto-server): MTTGeneralV2 9-max com stacks param, preflop correto, multi-gametype

### Fixed
- **`MTTGeneralV2`** (9-max): adicionado parâmetro `stacks=` com 9 valores iguais (era string vazia → 0 respostas)
- **`_TABLE_CONFIG`**: mapeamento completo num_players 2–9 → gametype/positions/open_size
- **`_postflop_preflop_seq`**: gerava sequências com contagem errada de ações (ex: UTG gerava 3 em vez de 9)
- **`positions`** MTTGeneralV2: incluído UTG+2 (era 8 posições → sem match para CO e abaixo)
- **`validate_nodes_vs_gw.py`**: SELECT agora inclui `d.num_players` — antes todas decisions defaultavam para 9p

---

## [v0.131.0] — 2026-05-20 — fix(gto-server): reverter MTTGeneralV2, manter fix de board por street

### Fixed
- **`GAMETYPE`**: revertido para `"MTTGeneral"` — `MTTGeneralV2` exige parâmetro `stacks` completo com todos os jogadores que nossa implementação não envia, causando 0 respostas
- **`query_gto_wizard` — turn/river**: simplificado para enviar `flop_actions=""` / `turn_actions=""` (root do street) com o board correto (4/5 cartas). Não usa `X-X` — notação de check-check não confirmada no HAR do GW
- O ganho real desta versão: turn queries agora enviam 4 cartas e river enviam 5, fazendo o GW consultar o tree correto em vez do flop tree

---

## [v0.130.0] — 2026-05-20 — fix(gto-server): turn/river enviavam apenas 3 cartas ao GW (tratados como flop)

### Fixed
- **`gto_bot/solver_api/server.py` — `_norm_board`**: recebia `max_cards` fixo em 3, enviando apenas o flop para GW em todos os streets. Turn e river agora enviam 4/5 cartas respectivamente, consultando o tree correto
- **`query_gto_wizard` — action sequences**: turn agora usa `flop_actions="X-X"` (check-check no flop para chegar ao turn root); river usa `flop_actions="X-X" + turn_actions="X-X"`. Quando `facing_size_bb > 0`, modela a aposta no street correto
- **`_nearest_valid_bet`**: generalizado para aceitar `street` e definir `{street}_actions` corretamente (antes sempre definia `flop_actions`)
- **`resync_gto_actions.py`**: expandido para processar TODAS as decisions postflop (com e sem gto_label), não apenas as que já tinham label — permite propagar labels de nós recém-inseridos pelo GW

### Impact
- Turn e river de spots cobertas pelo GW agora retornam SEM RESPOSTA pela razão correta (board sem solução) vs. antes onde eram silenciados pela truncagem do board
- Requer restart do servidor GCP (`gto_bot/solver_api/server.py`) para o fix entrar em vigor

---

## [v0.129.0] — 2026-05-20 — fix(admin): cobertura GTO inclui preflop_ranges como terceiro source

### Fixed
- **`GET /admin/dashboard`**: `coverage` agora inclui `preflop_ranges` (decisions preflop com gto_label validado via arquivo JSON de ranges) além de `solver_cli` e `gto_wizard`. `total` inclui os três. Antes, as ~696 decisions preflop cobertas não apareciam no painel
- **Admin UI — Cobertura por Fonte**: cada fonte tem cor distinta (emerald=preflop_ranges, blue=gto_wizard, amber=solver_cli) e subtitle explicativo. KPI tile renomeado para "Decisions Cobertas" com breakdown `nodes: X · preflop: Y`

---

## [v0.128.0] — 2026-05-20 — fix(data): limpeza de nós ruins + propagação de labels GTO

### Fixed
- **176 nós ruins deletados**: nós `solver_cli` com `position=range_string` (ex: `JJ+,AKs,...`) e `stack_bucket='solver'` criados por runs antigos do solver foram identificados e removidos. Hashes desses nós eram inacessíveis via `compute_spot_hash()` com position real, tornando-os dead code no banco
- **11 decisions nullificadas**: decisions que referenciavam os nós ruins (todas UTG+1/UTG+2 — posições não suportadas pelo GW) tiveram `gto_label/gto_action` nulificados para evitar classificações baseadas em dados corrompidos
- **82 nós solver_cli enriquecidos com strategy_json**: run `--no-strategy-only` enriqueceu 82 nós válidos com `strategy_json` detalhado via GW (84 respondidos de 511 processados; os demais são UTG+2/0-10bb/boards não cobertos pelo GW)
- **2 ações de nós corrigidas** onde GW divergia da ação armazenada pelo solver local
- **11 labels de decisions propagados**: `resync_gto_actions.py --apply` atualizou 11 decisions cujos nós GTO foram enriquecidos/corrigidos

### Added
- **`scripts/_cleanup_bad_nodes.py`**: identifica nós com position=range_string ou stack_bucket='solver', encontra decisions afetadas, nullifica labels e deleta os nós. Dry-run por padrão, `--apply` para executar

### Estado do banco após esta versão
- `gto_nodes`: 449 solver_cli (159 com strategy_json) + 167 gto_wizard (todos com strategy_json)
- Preflop: 696/704 decisions com label (99%) — 8 sem cobertura (UTG+1, UTG+2 não suportados)
- Flop: 32/94 com label (34%) | Turn: 18/50 (36%) | River: 6/19 (32%)
- Distribuição de labels: gto_correct=526, gto_critical=168, gto_mixed=47, gto_minor_deviation=11

---

## [v0.127.0] — 2026-05-20 — refactor(gto): validate_nodes_vs_gw usa servidor GCP em vez de token de browser

### Changed
- **`scripts/validate_nodes_vs_gw.py`** reescrito para usar `gto_wizard_client.query_spot()` (POST /gto-wizard no servidor GCP). Não requer mais `GW_ACCESS_TOKEN` de browser. Requer `GTO_SOLVER_URL`, `GTO_SOLVER_API_KEY` e `GTO_WIZARD_ENABLED=true` no `.env`. Verifica status do servidor antes de iniciar (`/gw-status`)
- Removida dependência de `GWAuth`/`GWClient`/`build_gw_params()` do benchmark script
- Formato de resposta adaptado para `gw_query()` → `strategy_json` correto no banco

---

## [v0.126.0] — 2026-05-20 — fix(data): revalidação completa preflop + limpeza de orphans postflop

### Fixed
- **Preflop — 84 decisions corrigidas**: `resync_preflop_all.py` revalidou TODAS as 708 decisions preflop contra os ranges JSON (não apenas as NULL). Principal padrão corrigido: shoves de short stack (5-15bb) classificados como `gto_correct` que deveriam ser `gto_mixed` (ação de frequência mista no push/fold correto). Também capturou inversões em spots vs_RFI e is_3bet
- **Postflop orphans — 34 decisions limpas**: decisions postflop com `gto_label` setado mas cujo nó GTO foi deletado na limpeza anterior (93 nodes corrompidos removidos em v0.123.0) foram identificadas e tiveram `gto_label/gto_action` nulificados. Agora são candidatas a cobertura via `validate_nodes_vs_gw.py --new-decisions`

### Added
- **`scripts/resync_preflop_all.py`**: revalida TODAS as decisions preflop contra ranges JSON (diferente de `sync_gto_labels_from_ranges.py` que só preenche NULL). Dry-run por padrão, `--apply` para salvar. Suporta `--user-id` e `--tid`

### Estado do banco após esta versão
- Preflop: 708 decisions, todas validadas contra ranges JSON (source of truth)
- Postflop com cobertura GTO: ~47 decisions com nó GTO válido encontrável
- Postflop sem cobertura: ~96 decisions (34 orphans + 62 nunca cobertas) — aguardando `validate_nodes_vs_gw.py --new-decisions`

---

## [v0.125.0] — 2026-05-20 — feat(gto): script de validação e enriquecimento de nós via GTO Wizard

### Added
- **`scripts/validate_nodes_vs_gw.py`**: script para validar e enriquecer nós `solver_cli` contra GTO Wizard.
  - Modo padrão: prioriza (1) nós com exploitability > 5%, (2) 515 nós sem `strategy_json`, (3) amostra aleatória ~10% dos demais
  - Modo `--new-decisions`: cobre decisões postflop sem nenhum nó GTO — consulta GW primeiro (GTO Wizard first pipeline), fallback para `run_gto_worker.py` (solver_cli)
  - Flags: `--apply`, `--limit N`, `--street`, `--high-exploit-only`, `--no-strategy-only`, `--sample-pct`, `--dry-run`, `--new-decisions`
  - Quando ação GW diverge da stored, atualiza `gto_action + gto_freq + source='gto_wizard'`
  - Sempre enriquece `strategy_json` com frequências completas do GW (melhora painel Estratégia GTO no Ghost Table)

---

## [v0.124.0] — 2026-05-20 — feat(ghost-table): exibe torneio e hand ID no contexto do spot

### Added
- **Ghost Table — `sitStrip`**: linha de referência discreta abaixo do contexto do spot mostrando nome do torneio, `#hand_id` e data. Permite identificar a mão original para busca manual quando necessário. Visível tanto no mobile quanto no desktop durante toda a sessão (fase active e result)

---

## [v0.123.0] — 2026-05-20 — fix(data): limpeza e ressincronização de gto_nodes e decisions.gto_action

### Fixed
- **`gto_nodes` (93 entradas removidas)**: deletados todos os nós `source=solver_cli` com `strategy_json` recomendando jam ≥ 80% em flop/turn/river com stack_bucket ≥ 20-35bb. Eram resultado de runs incorretos do solver onde `allin` dominava spots que deveriam ter check/bet. Muitos tinham boards com número errado de cartas para o street indicado (ex: flop com 4-5 cartas)
- **`decisions.gto_action` + `gto_label` (26 decisões corrigidas)**: ressincronizado contra `gto_nodes` limpos com board validation e guard SPR. Principais correções: normalização `allin → jam` e 2 mudanças de ação genuínas (ex: `allin → check` com reclassificação `gto_critical → gto_minor_deviation`)
- **`_resolve_best_action_from_node()` + `_valid_node()`**: adicionada validação de board após lookup — rejeita nós onde `board` do nó ≠ board da decisão, capturando colisões de hash SHA256[:16]
- **`get_decision_gto()` (Replayer)**: mesmo guard de board aplicado

### Added
- **`scripts/clean_gto_nodes.py`**: script de auditoria — lista nós suspeitos (board mismatch + jam implausível). `--delete --yes` para remover. Reutilizável em produção
- **`scripts/resync_gto_actions.py`** (reescrito): ressincroniza `decisions.gto_action` + `gto_label` usando lookup ao vivo com board validation e SPR guard. Dry-run por padrão, `--apply` para salvar

### Metrics
- Taxa de erro postflop: 51% → 38% (melhoria imediata após limpeza dos nós corrompidos)
- `gto_nodes`: 874 → 781 entradas válidas

---

## [v0.122.0] — 2026-05-20 — fix(ghost-table): guard SPR para nós GTO incorretos (jam implausível)

### Fixed
- **`_resolve_best_action_from_node()` (drill submit)**: se o nó retornar `jam` como ação dominante, `facing_bet = 0` e SPR (stack/pot) > 8, o nó é descartado como incorreto e o sistema usa `decisions.gto_action` como fallback. SPR > 8 sem aposta anterior torna jam como overbet de >8× o pote — GTO nunca recomenda jam como ação dominante nesse cenário
- **`get_decision_gto()` (Replayer `/replay/<id>/gto`)**: mesmo guard SPR aplicado ao painel Estratégia GTO — evita que a UI mostre "Shove 96%" para um spot onde o GTO correto é check/bet

### Root Cause
Nós do GTO Wizard em `gto_nodes` estavam sendo associados a spots diferentes via hash match com dados inválidos (ex: `strategy_json` com shove 96% para turn de Q4o com 28bb/pot 1.5bb = SPR 18.7). O guard de SPR detecta esses matches impossíveis sem precisar auditar o banco.

---

## [v0.121.0] — 2026-05-20 — fix(ghost-table): corrige lookup GTO Wizard no drill e replayer

### Fixed
- **`repositories.get_gto_node()`**: query ampliada para incluir nós do GTO Wizard (`source='gto_wizard'`) que possuem `strategy_json` mas `exploitability_pct = NULL` — antes eram sempre ignorados, causando fallback para `decisions.gto_action` (potencialmente desatualizado)
- **`_resolve_best_action_from_node()`** (drill submit): removido fallback d (`get_gto_node_by_spot`) que usava algoritmo de hash incompatível com `compute_spot_hash` e podia retornar nós aleatórios via colisão; adicionada validação pós-lookup (`node.street == street`)
- **`get_decision_gto()`** (endpoint Replayer `/replay/<id>/gto`): mesmas correções — removido fallback d, adicionada validação de street

### Why
Ghost Table mostrava recomendações erradas (ex: "shove" em flop 4-9-7 com A7o 33.7bb onde GTO é check, "shove" em KQK com Q8s 73.7bb). A cadeia de lookup chamava `get_gto_node()` que filtrava `exploitability_pct IS NOT NULL` — excluindo todos os nós GTO Wizard (armazenados com exploitability=NULL). Sem nó, o sistema usava `decisions.gto_action` que foi salvo por um worker via hash match que pode ter sido incorreto.

---

## [v0.120.0] — 2026-05-19 — feat(dashboard): GtoAlignmentCard — breakdown GTO por street (item 5)

### Added
- **`GET /player/gto-alignment`**: novo endpoint que retorna breakdown de alinhamento GTO por preflop/flop/turn/river — total, cobertura%, aligned%, correct/mixed/minor/critical por street
- **`repositories.get_gto_alignment_by_street()`**: query GROUP BY street com todas as métricas; janela de 90 dias
- **`frontend/src/components/hud/GtoAlignmentCard.tsx`**: card no dashboard com overall aligned%, mini stacked bar por street e cobertura
- **`frontend/src/lib/api.ts`**: interfaces `GtoAlignmentData` + `GtoAlignmentStreet`; função `metrics.gtoAlignment()`
- **i18n** (`pt-BR`, `en`, `es`): chave `gtoAlignment.*` em `dashboard.json`

### Backlog
- Item 5a (heatmap posição × street) adicionado ao backlog futuro — requer volume suficiente por (street × posição) para ser útil

---

## [v0.119.0] — 2026-05-19 — fix(preflop): SB complete aceitável em stacks sem limp_hands (Opção 2)

### Fixed
- **`preflop_gto_ranges.py` — `_rfi_quality`**: para SB com `is_sb=True`, quando a mão não está no raise range e o jogador completa (call/limp), retorna `acceptable` em vez de `leak`. Nos 6/9 stack buckets que já têm `limp_hands` preenchido, o comportamento existente é preservado. O fix afeta apenas os 3 buckets sem limp range (10bb, 40bb, 75bb)
- **`docs/leaklab_gto_ranges.json`**: reescrito em UTF-8 puro (encoding fix) — o metadata da validação introduziu um em-dash `\x97` que causava `UnicodeDecodeError` ao abrir no Linux/produção

### Why
GTO Wizard modela SB com fold/complete/raise. Nosso modelo tem apenas fold/raise. Para os stacks sem dados de complete zone, completar com uma mão fora do raise range não é um erro detectável — marcar como `leak` era um falso positivo.

---

## [v0.118.0] — 2026-05-19 — feat(validation): validação preflop ranges vs solver remoto (item 4)

### Added
- **`scripts/validate_ranges_vs_solver.py`** (novo): valida `leaklab_gto_ranges.json` contra o endpoint `/gto-wizard` do servidor remoto (GTO Wizard via CDP). Compara frequência de raise por posição × stack bucket
- **`scripts/gto_validation/comparison_preflop.json`**: resultado da validação — 42 spots comparados

### Fixed
- **SB 40bb RFI**: entrada com `fonte=None` e pct=70.7% (range quase full, interpolação incorreta). Corrigido para pct=43.1% usando SB 30bb como base (GW confirma freq similar nos dois stacks)
- **SB 75bb RFI**: entrada com `fonte=None` e pct=84.6% (full range). Corrigido para pct=12.8% via interpolação entre SB 50bb e SB 100bb RegLife

### Result
- 42/54 spots RFI comparados (12 skipped: 14bb e 75bb sem cobertura no plano GW)
- **Agreement (≤5%)**: 33 spots (79%)
- **Close (5–10%)**: 7 spots (17%)
- **Divergência (>10%)**: 2 spots — ambos SB, explicados por limitação de modelo (sem limp option vs GW que tem fold/complete/raise)
- Item 4 do backlog fechado: ranges validados e precisos para UTG/LJ/HJ/CO/BTN em todos os stacks

---

## [v0.117.0] — 2026-05-19 — feat(pipeline): deep dive 3-source GTO pipeline — FIX 1-5

### Fixed
- **FIX 1 — `decision_engine_v11.py`**: `gto_label`/`gto_action` preflop agora é persistido no DB no momento do upload. `analyze_preflop` retorna `available=True` → `result['gto']` preenchido → `save_decisions` armazena no DB. Antes, o campo ficava NULL até rodar o batch script manualmente
- **FIX 2 — `decision_engine_v11.py`**: `_enrich_preflop_gto()` agora passa `is_3bet_pot=bool(input_data.get('is_3bet', False))` para `analyze_preflop`. Spots de 3-bet são roteados para `scenario='vs_3bet'` em vez de `vs_rfi`
- **FIX 3 — `frontend/src/lib/gtoUtils.ts`** (novo arquivo): `computeEffectiveGtoLabel()` extraída para utilidade compartilhada. `Replayer.tsx` e `RangePanel.tsx` importam desta fonte única — elimina duplicação e risco de divergência futura
- **FIX 4 — `RangePanel.tsx`**: quando `solverOverridesRegLife=true`, o grid de ranges estático fica com `opacity-40 pointer-events-none` para indicar que é contexto, não o veredicto ativo. Elimina dois sinais contraditórios simultâneos
- **FIX 5 — `sync_gto_labels_from_ranges.py`**: refatorado para expor `sync_tournament(tournament_id)` como API pública. `api/app.py` chama `sync_tournament` + `reconcile_tournament_labels` no background thread `label-reconcile` após cada upload

### Result
- Pipeline 3 fontes coerente do upload ao Replayer: ranges estáticos → gto_nodes → heurístico, com fonte única exibida por vez
- `gto_label` preflop populado no momento do upload (antes: NULL até batch manual)
- Spots 3-bet avaliados no cenário correto via `is_3bet_pot`

---

## [v0.116.0] — 2026-05-19 — feat(pipeline): reconciliação label/gto_label automática

### Added
- **`database/repositories.py`**: `_reconcile_label(label, gto_label)` — helper de reconciliação; `reconcile_tournament_labels(tournament_id)` — reconcilia + recalcula `standard_pct` para um torneio
- **`api/app.py`**: background thread `label-reconcile` disparado após cada upload, aplica reconciliação automática para o novo torneio
- **`update_decision_gto`**: quando chamado sem `label` explícito (ex: Replayer salva veredicto ao vivo), agora reconcilia o label existente com o novo `gto_label`
- **`resync_gto_labels_for_node`**: quando solver atualiza `gto_label` via hash-match, agora também atualiza `label` via reconciliação
- **`sync_gto_labels_from_ranges.py`**: ao final do `--save`, chama `reconcile_tournament_labels` para os torneios afetados

### Result
- Qualquer novo upload, atualização do solver ou sync de ranges mantém `label` e `gto_label` automaticamente consistentes — sem mais intervenção manual

---

## [v0.115.0] — 2026-05-19 — fix(data): reconciliar label vs gto_label — zero conflitos

### Fixed
- **Desacordo `label`/`gto_label`**: dashboard dizia "Standard" enquanto Replayer mostrava erro GTO crítico. 173 decisões em 6 torneios reconciliadas usando regra de prioridade: GTO é autoritativo para direção (correto vs erro); quando ambos apontam erro, mantém o mais severo
- **98 `standard → small_mistake`**: engine disse ok, GTO disse crítico
- **61 upgrades** (43 `marginal→standard` + 18 `small_mistake→standard`): engine disse erro, GTO confirmou play correto
- **3 `marginal → small_mistake`** + **11 `clear_mistake → standard`**: ajustes de severidade
- `standard_pct` recalculado para todos os 6 torneios afetados
- `scripts/reconcile_labels_with_gto.py` adicionado para re-execução futura após novos uploads

### Result
- Zero conflitos `label`/`gto_label` na base — o que o dashboard mostra é o que o Replayer confirma

---

## [v0.114.0] — 2026-05-19 — feat(data-quality): cobertura preflop 98% — LJ push/fold + BB free-play

### Added
- **`leaklab_gto_ranges.json`**: posição `LJ` adicionada ao `push_fold` nos buckets `10bb`, `14bb` e `20bb` (baseada em UTG1 — posição adjacente em 6-max). Cobre casos `UTG+2` vs `UTG+1` que falhavam por alias
- **`sync_gto_labels_from_ranges.py`**: caso especial para BB free-play — quando BB checa sem facing bet, classifica automaticamente como `gto_correct` (ação trivialmente correta)

### Result
- Cobertura preflop: **696/704 (98%)** — antes ~79%, agora 8 restantes genuinamente irredutíveis
- Distribuição final: 527 `gto_correct` · 138 `gto_critical` · 22 `gto_minor_deviation` · 9 `gto_mixed`
- 8 casos irredutíveis documentados: 3x 3-bet sem `vs_position` (pipeline gap), 2x >100bb (sem dados), 1x BTN vs SB (ausente do RegLife), 2x outros

---

## [v0.113.0] — 2026-05-19 — fix(ranges): remover bluff-shoves trash offsuit de vs_RFI

### Fixed
- **`docs/leaklab_gto_ranges.json`**: removidos `32o, 42o+, 52o+, 62o+` das `raise_hands` de vs_RFI em todos os buckets e spots (116 entradas). Esses trash offsuits eram artefatos de solver de cash game que não se aplicam a MTT — causavam classificação incorreta de folds corretos como `gto_critical`
- Identificado via consulta manual no solver: SB 43o 28bb vs MP1 fold = correto; sistema marcava como erro
- 18 decisões revertidas para NULL e reprocessadas → 11 passaram para `gto_correct`

### Result
- `analyze_preflop` agora classifica folds de trash offsuit em spots vs_RFI como `correct` em vez de `gto_critical`

---

## [v0.112.0] — 2026-05-19 — feat(backend): sync_gto_labels_from_ranges

### Added
- **`backend/scripts/sync_gto_labels_from_ranges.py`**: preenche `gto_label`/`gto_action` para decisões preflop sem veredicto de solver, usando `analyze_preflop` com o range estático. Solver (gto_nodes) tem prioridade absoluta; este script só atua onde não há nó de solver
- Resultado: 146 de 201 decisões preflop sem gto_label classificadas — 101 `gto_correct`, 3 `gto_mixed`, 42 `gto_critical`

### Changed
- Quando range estático preflop confirma a ação do jogador, o badge "GTO ✓" passa a aparecer na lista de mãos em vez de nenhum indicador

---

## [v0.111.0] — 2026-05-19 — refactor(ui): simplificar indicadores de veredicto

### Changed
- **`TournamentDetail.tsx`**: removida linha lateral colorida (stripe esquerdo) e borda codificada por severidade — card tem borda neutra única. Eliminado visual duplicado de 3 indicadores para o mesmo veredicto
- **`TournamentDetail.tsx`**: badge engine (`Linha sólida`, `Atenção`, etc.) suprimido quando `category === "ok"` sem gtoLabel — ausência de badge comunica correção
- **`TournamentDetail.tsx`**: `leakTag` (texto `▸ small mistake`) suprimido sempre que `gtoLabel` existe — GTO já fala tudo
- **`Replayer.tsx`**: removido `GtoMixedBadge` do banner do solution card — label colorido já comunica o veredicto sem duplicar

### Principle
Uma fonte, um indicador: quando GTO existe → só o badge GTO fala; quando não existe → engine fala; badge ausente = jogada ok

---

## [v0.110.0] — 2026-05-19 — feat(replayer): badge GTO Misto com tooltip

### Added
- **`frontend/src/components/replayer/GtoMixedBadge.tsx`**: componente reutilizável com Radix Tooltip para três variantes:
  - `gto_mixed` → `◎ GTO Misto` (sky-400): ação do jogador tem 30–60% de frequência no equilíbrio
  - `gto_minor_deviation` → `◎ Defensável` (amber-400): ação com 10–30% de frequência, incomum mas defensável
  - `spot_mixed` → `◎ Spot Misto` (sky-400 suave): o spot em si tem ≥2 ações com ≥10% de frequência
- **`GtoStrategyPanel.tsx`**: badge `◎ Spot Misto` substitui parágrafo de texto pouco visível quando solver usa estratégia mista — tooltip explica o conceito ao hover

---

## [v0.109.0] — 2026-05-19 — fix(replayer): solver priority + UI cleanup

### Fixed
- **`Replayer.tsx`**: `gto_minor_deviation` reclassificado como não-erro — `isActionOk` e supressores de chips/notas agora incluem esta categoria
- **`Replayer.tsx`**: "⏳ Calculando…" substituído por mensagem honesta quando não há frequências de solver disponíveis
- **`Replayer.tsx`**: chip `Qualidade` e `pro_notes` suprimidos quando solver contradiz análise de range estático
- **`Replayer.tsx`**: `vs_position === 'UNKNOWN'` não exibe mais o chip de range
- **`RangePanel.tsx`**: banner neutralizado e conteúdo suprimido quando solver override ativo; texto "Veredicto do solver substitui análise de range estática"
- **`GtoStrategyPanel.tsx`**: nota de estratégia mista quando ≥2 ações têm ≥10% de frequência
- **`app.py`**: solver sempre persiste `gto_label`/`gto_action` no banco ao consultar — garante prioridade absoluta do solver sobre range estático
- **`sync_gto_labels_from_solver.py`**: batch sync que re-calcula gto_label a partir de gto_nodes via spot_hash

### Changed
- Thresholds `effectiveGtoLabel` alinhados entre frontend e backend: ≥60% → correct, ≥30% → mixed, ≥10% → minor_deviation, <10% → critical
- Nomes de marcas externas removidos de todo texto visível ao usuário: "RegLife" → "análise estática", "GTO Wizard" → "Solver GTO" / "solver"

---

## [v0.108.0] — 2026-05-19 — feat(gto): ranges push/fold para stacks curtos (10/14/20bb)

### Added
- **`backend/scripts/add_pushfold_ranges.py`**: script que integra ranges GTO push/fold (sem ICM, MTT full ring) ao JSON para stacks 10bb, 12bb, 15bb, 20bb; estrutura `push_fold[pos][stack] = {shove_hands, shove_pct, _source}`
- **`leaklab/preflop_gto_ranges.py`**: fallback push/fold em `analyze_preflop` para cenários RFI e vs_RFI quando não há dados RegLife (buckets 10bb/14bb); constante `_PUSHFOLD_BUCKET_STACK` mapeia bucket → stack keys; novas funções `_pushfold_quality` e `_pushfold_notes`
- **`docs/leaklab_gto_ranges.json` v2.4.0**: 20 entradas push/fold adicionadas — UTG/UTG1/CO/BTN/SB para stacks 10bb, 12bb, 15bb, 20bb_pf nos buckets correspondentes

### Changed
- `analyze_preflop`: ao não encontrar dados RegLife em RFI, consulta `push_fold[pos]` do bucket; em vs_RFI short-stack sem dados, usa shove range como reshove heurística

### Result
- Stacks curtos (10–15bb): análise disponível para todas as posições via push/fold GTO
- Spots classificados como leak/major_leak quando ação diverge do shove/fold GTO

---

## [v0.107.0] — 2026-05-19 — fix(gto): alias UTG1→MP no lookup vs_RFI + filtro facing_bet

### Fixed
- **`preflop_gto_ranges.py`**: opener `UTG+1` normalizava para `UTG1` mas JSON vs_RFI usa `MP` — adicionado alias `_VSRFI_OPENER_ALIAS = {'UTG1': 'MP'}` no lookup
- **`compare_reglife_spots.py`**: filtro `facing_bet >= 2.0` excluía opens curtos (<2bb em stacks rasos) — relaxado para `> 1.0` (exclui apenas limps puros de 1bb)

### Result
- vs_RFI cobertura: 29% → **43%** (RFI mantém 98%)
- Cobertura por stack: 40bb 90%, 50bb 74%, 30bb 55%, 100bb 55%, 14bb 41%
- Teto atual determinado pelos combos ausentes no RegLife PDF (10bb legacy: apenas 2 openers)

---

## [v0.106.0] — 2026-05-19 — chore(gto): recalcula gto_label com JSON v2.3.0 completo

### Changed
- Rodou `compare_reglife_spots.py --all --save` para RFI e vs_RFI com o JSON atualizado:
  - **RFI**: 340/347 decisões com gto_label (cobertura 98%)
  - **vs_RFI**: 64/115 decisões com gto_label (cobertura 56% — limitado pelos combos ausentes no RegLife PDF)
  - 40bb e 75bb agora cobertos via interpolação → 21 spots adicionais classificados

---

## [v0.105.0] — 2026-05-19 — feat(ranges): interpola vs_RFI 40bb e 75bb a partir de dados RegLife

### Added
- **`backend/scripts/interpolate_vsrfi.py`** — preenche vs_RFI de 40bb e 75bb por interpolação 50/50:
  - 40bb = média(30bb, 50bb): 28 spots com fold/call/raise/allin/aggr_pct
  - 75bb = média(50bb, 100bb): 27 spots com mesma estrutura
  - Spots marcados com `_source: "interpolated_reglife"` para distinguir de dados extraídos direto do PDF

### Changed
- **`backend/docs/leaklab_gto_ranges.json`** — versão 2.3.0:
  - 40bb e 75bb vs_RFI agora cobertos (antes: 6 e 12 spots em formato antigo)
  - Todos os 9 stacks têm cobertura vs_RFI com 7 openers cada
  - Cobertura total: 8 stacks com dados RegLife/interpolados + 10bb (push/fold legado)

---

## [v0.104.0] — 2026-05-19 — feat(gto): vs_position em decisions + comparação RFI+vs_RFI com RegLife

### Added
- **`decisions.vs_position`** — nova coluna para armazenar a posição do opener em spots vs_RFI:
  - Migração automática em `schema.py` (PostgreSQL + SQLite)
  - `save_decisions` em `repositories.py` salva `spot.villainPosition` neste campo para novos uploads
- **`backend/scripts/populate_vs_position.py`** — script retroativo que popula `vs_position` para as 346 decisões vs_RFI existentes re-parseando `tournaments.raw_text`:
  - Agrupa por torneio para evitar re-parse desnecessário
  - Usa `_infer_position` do `hand_state_builder` para mapear nome → posição
  - Resultado: 346 decisions atualizadas (UTG: 84, UTG+1: 57, HJ: 48, CO: 48, etc.)

### Changed
- **`backend/scripts/compare_reglife_spots.py`** — reescrito para comparar RFI + vs_RFI:
  - Passa `vs_position` para `analyze_preflop` em spots vs_RFI (facing_bet > 0, is_3bet=0)
  - Exibe coluna `VS` na tabela (posição do opener)
  - Seções separadas: "RFI Spots" e "vs_RFI Spots"
  - Suporta `--type rfi/vsrfi/both` e `--all` (todos os labels, não só mistakes)
  - Resumo geral com cobertura RegLife por tipo
  - Resultado: 100% cobertura RFI, 53% cobertura vs_RFI (restante = combos ausentes no RegLife)

---

## [v0.103.0] — 2026-05-19 — feat(ranges): extrai vs_RFI do PDF RegLife e adiciona lookup completo

### Added
- **`backend/scripts/render_reglife_pages.py`** (reescrito) — renderiza todas as 205 tabelas do PDF RegLife como PNG:
  - Detecta múltiplos títulos por página (1, 2 ou 3 tabelas) via posição Y, sem limite de half-page
  - Threshold de fonte baixado para 12pt (captura tabelas com título menor como `vsrfi_50bb_MP_vs_UTG`)
  - Override de página específica para corrigir typo no PDF (p071: "50 bbs" → 30bb)
  - Clip dinâmico por intervalo entre títulos consecutivos
- **`backend/scripts/extract_vsrfi_ranges.py`** — extrai ranges vs_RFI (3bet/call/fold) de 163 imagens:
  - Reutiliza classificador de pixels da RFI com 4 ações: fold (azul), call (verde), raise/3bet-size (vermelho claro), allin/3bet-push (vermelho escuro)
  - Estrutura: `ranges.[stack].vs_RFI.[opener].[defender]`
  - Campos: `fold_pct`, `call_pct`, `raise_pct`, `allin_pct`, `aggr_pct` (todos combo_pct / 1326)
  - Handstrings por ação: `fold_hands`, `call_hands`, `raise_hands`, `allin_hands`
- **`backend/scripts/add_combo_pct.py`** — adiciona `combo_pct` e `grid_pct` ao leaklab_gto_ranges.json

### Changed
- **`backend/docs/leaklab_gto_ranges.json`** — versão 2.2.0:
  - Adicionado bucket `17bb` com dados RegLife RFI + vs_RFI
  - 163 spots vs_RFI em 6 stacks (14bb, 17bb, 20bb, 30bb, 50bb, 100bb)
  - `pct` = `combo_pct` (combos reais / 1326); `grid_pct` preservado como backup
- **`backend/leaklab/preflop_gto_ranges.py`** — lookup vs_RFI atualizado para novo formato RegLife:
  - Suporte ao novo formato (chave direta de posição) e fallback ao formato antigo
  - `_vs_rfi_quality_new()` e `_vs_rfi_notes_new()` com base em fold/call/raise/allin por mão
  - Retorna `fold_pct`, `call_pct`, `raise_pct`, `allin_pct`, `fold_hands`, etc.
- **`backend/tests/test_preflop_gto_quality.py`** — teste `vs_rfi_AKo_fold_quality` atualizado para novo dado RegLife (CO AKo vs UTG 30bb é call, fold=leak)
- **`backend/docs/range_pages/`** — 205 imagens PNG (42 RFI + 163 vs_RFI) extraídas do PDF

---

## [v0.102.0] — 2026-05-18 — feat(ranges): atualiza leaklab_gto_ranges.json com dados RegLife via pixel analysis

### Added
- **`backend/scripts/extract_reglife_ranges.py`** — extrai ranges RFI dos 42 PNGs do PDF RegLife via análise de pixels:
  - Detecta bounds da grade 13×13 automaticamente por imagem (top vs bottom half pages)
  - Classifica cada célula por cor: raise (vermelho), fold (azul), limp/call (verde), shove (vermelho escuro)
  - Amostragem 5×5 por célula com filtro de pixels de texto/borda
  - Captura range de limp separado para SB em todos os stacks
  - Compressão de hands para notação poker padrão (ex: `44+,A4s+,K9s+`)
- **`backend/scripts/update_gto_ranges.py`** — atualiza `leaklab_gto_ranges.json` com dados RegLife preservando estrutura existente
- **`backend/scripts/probe_grid.py`** — utilitário de calibração para debug de imagens

### Changed
- **`backend/docs/leaklab_gto_ranges.json`** — versão 2.0.0 com dados RegLife solver-generated:
  - RFI ranges atualizados para 5 stacks: 14bb, 20bb, 30bb, 50bb, 100bb (todos os 7 posições)
  - 10bb, 40bb, 75bb preservados (push/fold e interpolações)
  - SB agora tem `limp_hands` e `limp_pct` separados (ex: SB 100bb: raise 3.6%, limp 88.2%)
  - Fonte marcada por entrada: `_fonte: "reglife_pdf/Xbb"` vs `"original"`
- **`backend/leaklab/preflop_gto_ranges.py`** — suporte ao limp range da SB:
  - `analyze_preflop`: lê `limp_hands`/`limp_pct` da SB e inclui `in_limp_range` na resposta
  - `_rfi_quality`: novos casos para limp correto, raise aceitável, fold leak da SB
  - `_rfi_notes`: mensagens contextualizadas para limp SB (range de limp, fold leak, raise aceitável)

---

## [v0.101.9] — 2026-05-17 — feat(gto): classificação inteligente + GTO Alignment Card no dashboard

### Changed
- **`backend/leaklab/decision_engine_v11.py`** — `_gto_classify_from_strategy` reescrita com lógica inteligente:
  - Extrai `ev_bb` de cada ação do `strategy_json` durante desserialização
  - Calcula `ev_diff` (custo real em BBs vs top action GTO)
  - Novos tiers: `≥60%` → correct; `≥25%` → mixed; `10-25%` → mixed se ev_diff < 0.15bb, senão minor_deviation; `<10%` → minor_deviation se ev_diff < 0.30bb, senão critical
  - Evita punir estratégias mistas legítimas (ex: call 15% com ev_diff 0.02bb deixa de ser `gto_critical`)

### Added
- **`GET /player/gto-quality`**: endpoint que retorna distribuição de `gto_label` nos últimos 90 dias (`gto_correct_pct`, `gto_mixed_pct`, `gto_minor_pct`, `gto_critical_pct`, `aligned_pct`, `coverage_pct`, `total_with_gto`)
- **`database/repositories.py`** — `get_gto_quality_breakdown(user_id, since_days=90)`
- **`frontend/src/components/hud/GtoQualityCard.tsx`** — card "Alinhamento GTO" no dashboard:
  - Barra empilhada com 4 segmentos coloridos (verde/azul/âmbar/vermelho)
  - Big number: % alinhado ao GTO (correct + mixed) com cor por desempenho
  - Legenda com percentuais por categoria
  - Oculto quando `total_with_gto < 10`
- **i18n** — chaves `gtoQuality.*` adicionadas em PT-BR, EN e ES

---

## [v0.101.8] — 2026-05-17 — feat(admin): painel de re-análise de labels preflop

### Added
- **`POST /admin/reanalyze-preflop-labels`**: endpoint admin que roda o pipeline completo server-side — re-parseia raw_text de todos os torneios, reconstrói decision inputs (com `facingSize`, `villainPosition`, `is_3bet`), re-executa `evaluate_decision` e corrige `decisions.label` onde difere. Recalcula `tournaments.standard_pct` nos torneios afetados. Idempotente.
- **AdminDashboard aba "GTO Worker"**: painel "Re-análise de Labels Preflop" com botão Executar, 3 KPIs (decisões verificadas / atualizadas / torneios afetados) e tabela de changes (hand_id · ação · label antes → depois)

---

## [v0.101.7] — 2026-05-17 — fix(gto): correção contradições GTO + re-análise labels preflop

### Fixed
- **`backend/leaklab/preflop_gto_ranges.py`** — todos os 5 bugs de contradição já corrigidos em versões anteriores:
  - BUG 1 (`_rfi_quality`): limp/call fora do range agora retorna `leak` em vez de `acceptable`
  - BUG 2 (`_vs_rfi_quality`): desvio de ação dentro do range agora retorna `leak` em vez de `acceptable`
  - BUG 3 (`_find_opener_key`): fallback silencioso para BTN_open removido — retorna `None` se sem match exato
  - BUG 4 (`analyze_preflop`): `facing_size > 0` → `vs_rfi` independente de `vs_position`
  - BUG 5 (`app.py`): `is_3bet_pot` passado corretamente para `analyze_preflop` em ambas as chamadas
- **`backend/scripts/reanalyze_preflop_labels.py`** — reescrito com pipeline completo:
  - Deduplicação por `(hand_id, position, action)` — evita double-update de DIs duplicados do pipeline
  - Recalcula `tournaments.standard_pct` nos torneios afetados (KPIs e RecentForm também atualizam)
  - Resultado: 700 decisões verificadas, 3 labels corrigidas em 3 torneios

---

## [v0.101.6] — 2026-05-17 — feat(study-plan): roteiro tático enriquecido com HUD stats

### Changed
- **`backend/leaklab/llm_explainer.py`**: `generate_study_plan` recebe agora `player_stats: dict` com todos os 12 HUD stats comportamentais
- **`_format_hud_stats_for_prompt()`**: nova função auxiliar que formata os stats com interpretação automática (`✓ dentro do range` / `⚠ acima/abaixo do ideal`) — o LLM recebe o contexto em linguagem de coach, não só números
- **Instrução de coaching**: novo parágrafo guia o LLM a cruzar VPIP/AF/BB Defense/Open Limp com os leaks para gerar módulos específicos de comportamento (ex: "VPIP alto + PFR baixo → loose-passive; AF abaixo de 2x → postflop passivo")
- Cache key atualizado para `v3` — invalida planos gerados sem HUD stats automaticamente na próxima chamada
- Ambos os endpoints `/study/plan` e `/coach/student/{id}/study-plan` passam os HUD stats

### Analysis
- Antes: LLM só recebia "frequência de erros por spot" — módulos eram genéricos
- Depois: LLM recebe perfil comportamental completo (12 stats + interpretação) — pode gerar módulos como "Você open limpa 8% das vezes (ideal 0-5%) — este módulo foca em eliminar limps e converter em opens ou folds"

---

## [v0.101.5] — 2026-05-17 — fix(i18n): textos hardcoded no dashboard

### Fixed
- **`CareerGraphCard.tsx`**: `"torneos"` hardcoded (espanhol) substituído por `t("career.analyzedCount")` — seguia o idioma errado independente da locale do usuário
- **`PlayerStatsCard.tsx`**: `"Ref MTT"` hardcoded substituído por `t("playerStats.refMtt")` — agora respeita o idioma
- Chaves adicionadas nas 3 locales (pt-BR, en, es)

---

## [v0.101.4] — 2026-05-17 — feat(hud): Pending GTO Notice + Open Limp% + fix StrategicTwin

### Added
- **`GET /player/pending-gto-count`**: endpoint que conta spots `wizard_pending` + `gto_hand_requests` pendentes para o usuário
- **Dashboard**: linha informativa com spinner `⏳ N spots GTO em análise no solver` entre os KPIs e PlayerStatsCard — visível apenas quando > 0; polling automático a cada 30s enquanto houver spots pendentes. Mensagem contextualmente correta: os HUD stats comportamentais (VPIP, PFR, etc.) NÃO são afetados pelo solver — só os indicadores do Replayer atualizam.
- **Open Limp%**: 4° stat da Row 3 do Player HUD Stats — % de limps preflop de posições non-BB sem aposta em frente (ref MTT ideal: 0–5%; acima de 8% = leak sério de fold equity). Row 3 agora 4 colunas simétricas com as demais rows.
- **`StrategicTwinCard`**: adicionado `"allin"` como alias de `"jam"` → "Shove" nas 3 locales; fallback gracioso para ações não mapeadas (exibe valor raw sem mostrar chave i18n)

---

## [v0.101.2] — 2026-05-17 — feat(dashboard): Confidence Drift Alert no topo + dismiss persistente

### Changed
- **`frontend/src/pages/Index.tsx`**: Confidence Drift Alert movido para o **topo absoluto** do dashboard (antes dos KPIs e do DailyFocusCard) — primeira informação visível quando há drift detectado
- **Dismiss persistente via `localStorage`**: ao fechar o alerta, ele não reaparece mesmo após recarregar a página; chave baseada em `userId + affected_sessions` — reseta automaticamente quando novos torneios são importados e o alerta muda de baseline
- **`GhostDrillCard` removido do dashboard**: drill_row agora exibe apenas `PressureProfileCard + IcmBreakdown` (grid-cols-2); o Ghost Table continua acessível via `/training`

---

## [v0.101.1] — 2026-05-17 — feat(hud): Fold to Flop Bet + BB Defense + Steal% no Player HUD Stats

### Added
- **`backend/database/repositories.py`** (`get_player_stats`): 3 novos stats calculados a partir do banco:
  - `fold_to_flop_bet`: % de folds no flop quando enfrenta aposta — proxy para **Fold to C-Bet** (o stat mais solicitado por coaches; ref MTT: 40–55%)
  - `bb_defense`: % de defesas da BB (call + 3-bet) ao enfrentar abertura pré-flop (ref MTT: 35–55%)
  - `steal_pct`: % de raises/shoves do BTN/CO/SB quando não há aposta anterior (ref MTT: 25–45%)
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: Row 3 com os 3 novos indicadores, cada um com barra de referência colorida (verde/amarelo/vermelho) e tooltip explicativo
- **`frontend/src/lib/api.ts`** (`PlayerStatsResponse`): 3 novos campos adicionados à interface

### Analysis
- Auditoria completa do HUD revelou: C-Bet% já existia (hero como aggressor); o que faltava era **Fold to C-Bet** (hero como caller/defender) — statísticas distintas e igualmente críticas. BB Defense e Steal% completam o perfil de jogo posicional.
- Stats não implementáveis com schema atual: Double Barrel (requer tracking cross-street), Check-Raise% (requer sequência intra-street), AF por street (sample muito pequeno no dataset atual)

---

## [v0.101.0] — 2026-05-17 — feat(docs): transparência GTO para coaches + audit trail no replayer

### Added
- **`frontend/src/pages/Docs.tsx`** + **`i18n/locales/*/docs.json`**: nova seção **"Metodologia de Classificação GTO"** (PT/EN/ES) explicando: os 3 cenários pré-flop (RFI, vs Open, vs 3-Bet), o pipeline de 4 etapas, a tabela de `action_quality` → impacto no label, os 8 buckets de stack (10bb–100bb com ranges exatos), quando `available=false` e a garantia de ausência de contradições — informação necessária para que coaches e professores entendam e recomendem o sistema com segurança
- **`frontend/src/pages/Replayer.tsx`**: **"Raciocínio do sistema"** — audit trail colapsável na Decision Card (botão 👁) mostrando o caminho de 4 etapas que gerou a classificação: Cenário → Range consultada (ex. UTG · 30bb) → Mão in/out (88 ✗) → Qualidade da ação (leak/correct/etc.). Disponível em todas as decisões pré-flop com `available=true`
- **`frontend/src/components/replayer/RangePanel.tsx`**: rodapé de metadados exibindo a fonte do range (`Nash MTT (local)` ou `tabelas estáticas`) e indicador quando análise GTO está indisponível — dá aos coaches clareza sobre qual dataset está sendo usado

---

## [v0.100.1] — 2026-05-17 — fix(gto): corrigir contradições no sistema de classificação preflop + testes de regressão

### Fixed
- **`backend/leaklab/preflop_gto_ranges.py`** — `_rfi_quality`: limp/call com mão **fora do range de abertura** classificava como `acceptable` em vez de `leak` — corrigido
- **`backend/leaklab/preflop_gto_ranges.py`** — `_vs_rfi_quality`: mão **in-range mas com ação diferente da recomendada** (ex: range recomenda call, hero 3-beta) classificava como `acceptable` em vez de `leak` — corrigido
- **`backend/leaklab/preflop_gto_ranges.py`** — `_find_opener_key`: fallback silencioso para `BTN_open` quando opener não encontrado causava análise com dados do **opener errado** (`available=True` falso); agora retorna `None` se não há correspondência exata — corrigido
- **`backend/leaklab/preflop_gto_ranges.py`** — `analyze_preflop`: `facing_size > 0` sem `vs_position` definia `scenario='rfi'` (abertura) em vez de `vs_rfi` (defesa), gerando recomendações invertidas — corrigido
- **`backend/api/app.py`** — linhas ~1508 e ~2927: `is_3bet_pot` nunca era passado para `analyze_preflop`; spots de 4-bet eram analisados como `vs_rfi` em vez de `vs_3bet` — corrigido
- **`frontend/vite.config.ts`** + **`frontend/src/components/replayer/RangePanel.tsx`**: `/preflop-ranges` não estava no proxy Vite, causando erro CORS silencioso; `apiData` ficava `null` e o componente exibia o range estático genérico (`CALL_IP`, 264 combos) em vez dos dados reais da API — corrigido

### Added
- **`backend/tests/test_preflop_gto_quality.py`** (novo): 76 testes de regressão cobrindo todos os classificadores de qualidade GTO (`_rfi_quality`, `_vs_rfi_quality`, `_vs_3bet_quality`), o lookup de opener (`_find_opener_key`), o ajuste de labels (`_preflop_gto_label_adjust`) e integração com dados reais via `analyze_preflop`

### Migration
- **`backend/scripts/reanalyze_preflop_labels.py`** (reescrito): re-analisa decisões preflop de todos os torneios importados usando o pipeline completo (`parse_hand_history` → `build_decision_inputs_for_hand` → `evaluate_decision`) — 40 decisions corrigidas no banco

---

## [v0.99.9] — 2026-05-16 — feat(replayer): odds ao vivo, GTO strategy panel, bounty badges, Ghost Table melhorias

### Added
- **`frontend/src/components/replayer/GtoStrategyPanel.tsx`** (novo): componente compartilhado que exibe a estratégia do solver com barras de frequência por ação, EV em BB, marcador da ação jogada e custo de oportunidade no rodapé. Reutilizado no Replayer e no Ghost Table (compact mode).
- **`frontend/src/pages/Replayer.tsx`** — Call Math Card: bloco compacto em steps de decisão postflop do hero exibindo pot odds vs equity com veredito +EV/-EV e EV estimado em BB.
- **`frontend/src/pages/Replayer.tsx`** — Bounty no showdown: badge `💀 $X` por seat no painel de resultados mostrando o bounty na cabeça do jogador e o ganho de KO quando aplicável.
- **`frontend/src/pages/GhostTable.tsx`** — indicador de pot odds na fase active (desktop sidebar + mobile), visível apenas quando há `facing_bet`.
- **`frontend/src/pages/GhostTable.tsx`** — GtoStrategyPanel compact no painel de resultado: após submit de um spot postflop, busca estratégia via `/replay/{id}/gto` e exibe frequências GTO da decisão.

### Changed
- **`frontend/src/components/hud/PokerTableV3.tsx`**: badge de bounty no SVG alterado de 🏆 verde para 💀 âmbar — mais coerente com a notação padrão de bounty.
- **`frontend/src/pages/Replayer.tsx`**: seção "Estratégia do Solver" agora usa `GtoStrategyPanel` em vez do rendering inline anterior.
- **`frontend/src/lib/api.ts`**: `GtoStrategyAction` recebe `ev_bb` e `exploitability_pct`; `ReplayStep` recebe `gto_strategy`; `ReplaySeat` recebe `bounty`.

---

## [v0.99.7] — 2026-05-16 — fix(replayer): LJ no RangePanel + jam→shove + GTO no prompt LLM

### Fixed
- **`frontend/src/data/ranges.ts`**: `LJ` adicionado ao `Position` type, `POSITIONS` e `normalizePosition` — antes retornava `null`, causando fallback para BTN e exibindo ranges errados
- **`frontend/src/data/ranges.ts`**: `PUSH_FOLD` agora tem entrada `LJ` em `≤15bb` (~33%) e `≤20bb` (~26%) com ranges Nash MTT interpoladas entre HJ e CO — inclui A8o em ambos os buckets
- **`frontend/src/components/replayer/RangePanel.tsx`**: `showGtoCtx` não depende mais de `pos === detectedPos`; banner GTO aparece sempre que `gto.available`, evitando inconsistência entre texto do engine e grid visual
- **`backend/leaklab/llm_explainer.py`**: `gto_solver_block` agora usa o campo `gto{}` completo do engine (strategy, frequências, exploitability) com fallback para campos raiz do banco — IA recebe dados objetivos do solver para análise postflop

### Changed
- **`frontend/src/lib/utils.ts`**, **`llm_explainer.py`**, **`i18n/locales/*/docs.json`**: "jam" substituído por "shove" em todo texto visível ao usuário (labels, prompts LLM, documentação, templates)

---

## [v0.99.5] — 2026-05-16 — feat(admin): GTO Worker dashboard

### Added
- **`backend/api/app.py`** (`GET /admin/gto/worker-status`): novo endpoint admin que retorna saúde do worker, contadores de fila (`gto_hand_requests` + `gto_solver_queue`), throughput por hora (últimas 24h), cobertura de `gto_nodes` por fonte e lista dos últimos 10 erros
- **`frontend/src/lib/api.ts`** (`GtoWorkerStatus`, `adminDashboard.gtoWorkerStatus()`): interface TypeScript e função de chamada para o novo endpoint
- **`frontend/src/pages/admin/AdminDashboard.tsx`** (`GtoWorkerTab`): nova tab "GTO Worker" no painel admin com indicador de saúde (ativo/ocioso), KPIs de fila, gráfico de throughput (Recharts BarChart), barra de cobertura por fonte e painel de erros recentes

---

## [v0.99.4] — 2026-05-15 — feat(GTO-011): análise GTO proativa e automática no import

### Added
- **`api/app.py`** (`_auto_queue_gto_for_tournament`): nova função que enfileira automaticamente `gto_hand_requests` para todas as mãos postflop após o import de um torneio — sem necessidade de intervenção do usuário
- **`api/app.py`** (`_analyze_impl`): dispara `_auto_queue_gto_for_tournament` em thread daemon imediatamente após `save_decisions()`
- **`database/repositories.py`** (`bulk_request_gto_for_hands`): INSERT OR IGNORE em lote na `gto_hand_requests` — idempotente, safe para reimports
- **`backend/scripts/migrate_gto_requests.py`**: script one-shot para enfileirar análise de torneios já importados

### Changed
- **`api/app.py`** (`_gto_hand_worker_loop`): batch aumentado de 3 → 10 requests por ciclo; intervalo adaptativo 5s (fila ocupada) / 30s (fila vazia)
- **`frontend/src/pages/Replayer.tsx`**: botão "Solicitar Análise GTO" removido — spots sem GTO exibem indicador automático "Analisando este spot automaticamente"
- **`leaklab/gto_solver.py`**: nós parciais (sem `strategy_json`) não retornam mais como definitivos — caem por para GTO Wizard; strategy retornada do DB ordenada por frequency desc
- **`leaklab/gto_solver.py`**: `gto_action` agora reflete a ação de maior frequência no strategy_json (antes usava campo direto podendo divergir)
- **`database/repositories.py`** (`insert_gto_nodes`): aceita nós do GTO Wizard sem `exploitability_pct`; aceita chave `strategy_json` diretamente além de `strategy_detail`

### Fixed
- **`api/app.py`** (`_process_gto_hand_request`): early returns corrigidos para retornar 4 valores (evitava `ValueError: not enough values to unpack`)
- **`api/app.py`** (`_build_replay_data`): `live_top_act` propagado corretamente ao campo `gto_action` — antes, strategy DB com `check 97%` sobrepunha GTO Wizard `allin 96%`; DB atualizado automaticamente quando `live_top_act` difere do `gto_action` armazenado

---

## [v0.99.3] â€” 2026-05-15 â€” feat(GTO-005/006): estimated_equity no banco + validaÃ§Ã£o GTO 98-100% + threshold draw fix

### Added
- **`database/schema.py`**: coluna `estimated_equity REAL` adicionada Ã  tabela `decisions` â€” migrations automÃ¡ticas para SQLite e PostgreSQL
- **`database/repositories.py`**: `estimated_equity` incluÃ­do no INSERT de decisÃµes (via `math.estimatedHandEquity` do pipeline)
- **`scripts/reeval_postflop.py`**: novo script de re-avaliaÃ§Ã£o postflop â€” detecta draws fracos (equity_adj < 0.15) e draws fortes com equity insuficiente dado posiÃ§Ã£o/stack, converte `best_action='bet'â†’'check'` em lote com `--dry-run` para preview

### Fixed
- **`postflop_range_evaluator.py`**: semi-bluff threshold `equity_adj >= 0.10` â†’ `>= 0.15`. GUT+BDFD (0.14) e BDFD+BDSD (0.10) nÃ£o justificam bet â€” confirmado por validaÃ§Ã£o GTO Wizard (98% flop, 100% turn/river)
- **`scripts/gto_validation/playwright_compare.py`**: interceptor de headers registrado ANTES de `page.goto` â€” evitava race condition onde a pÃ¡gina recarregava antes de capturar DPoP token; action format `B{size}` â†’ `R{size}` (API GTO Wizard aceita apenas R, nÃ£o B); parser `next-actions` corrigido para path real `next_actions.available_actions[].action.betsize`
- **`scripts/gto_validation/analyze_results.py`**: output reformatado para mostrar distribuiÃ§Ã£o completa GTO (`check^82%  bet 18%<nÃ³s` em vez de `our=bet(18%)`); adicionado breakdown de erros por tipo; encoding UTF-8 no Windows

### Tests
- **`tests/test_postflop_evaluator.py`**: testes atualizados para threshold 0.15 â€” GUT+BDFD agora espera `check`, FD e OESD ainda esperam `bet`

---

## [v0.99.2] â€” 2026-05-13 â€” fix(AUD-001): guard foldâ†’check restrito a BB â€” corrige regressÃ£o em 577 spots

### Fixed
- **`preflop_range_evaluator.py`**: `_recommended_action` retorna `'check'` apenas quando `position == 'BB'` e `facing_size == 0`. Demais posiÃ§Ãµes (UTG/HJ/CO/BTN/SB) retornam `'fold'` para mÃ£os fracas sem aposta â€” comportamento correto (escolha de nÃ£o abrir)
- **`preflop_range_evaluator.py`**: filtro de `alternatives` tambÃ©m restrito a `BB` â€” outros posiÃ§Ãµes podem ter `'fold'` como alternativa em borderline spots sem aposta
- **`decision_engine_v11.py`**: guard final `facingSize=0 â†’ check` adicionado `and spot.get('position') == 'BB'`. Antes afetava 577 decisÃµes de non-BB incorretamente
- **`api/app.py`** (`player_drill_submit`): guard serve-time restrito a `position == 'BB'`
- **`database/repositories.py`** (`get_sparring_hand`): guard serve-time restrito a `position == 'BB'`

### Data Migration
- **Phase 2 DB fix**: 20 decisÃµes `BB + facing_bet IS NULL + best_action='fold'` atualizadas: `best_action â†’ 'check'`. 13 dessas (action_taken='check') tambÃ©m tiveram `score â†’ 0.02, label â†’ 'standard'` (eram small_mistake/marginal por engano)

### Tests
- **`test_evaluators.py`**: 27 testes reescritos para comportamento correto por posiÃ§Ã£o â€” BB check, non-BB fold para mÃ£os fracas sem aposta
- **`test_postflop_evaluator.py`**: `test_preflop_unaffected` agora verifica range zones do postflop evaluator (nÃ£o presenÃ§a de 'check'), jÃ¡ que BB legÃ­timamente retorna 'check' preflop

---

## [v0.99.1] â€” 2026-05-13 â€” fix(GTO-004): unidades facing_size_bb e threshold is_simple_spot

### Fixed
- **`api/app.py`**: revert `facing_size_bb` para `decision.get("facing_bet")` (BBs do DB). Estava usando `_spot.get("facingSize")` que retorna chips â€” `bet_bucket(6400)="40bb+"` em vez do correto `bet_bucket(1.0)="0-3bb"`, causando hash de lookup completamente errado
- **`gto_solver.py`**: `is_simple_spot` threshold `stack_bb <= 20` â†’ `<= 25` para cobrir stacks de ~20bb, comuns em MTT. Stack de 20.1bb antes causava resoluÃ§Ã£o assÃ­ncrona que nunca retornava ao frontend
- **`Replayer.tsx`**: indicador "â³ Calculandoâ€¦" exibido quando `gto_label` existe mas `stratSorted` ainda estÃ¡ vazio (solver ainda processando) â€” evita silÃªncio confuso para o usuÃ¡rio

---

## [v0.99.0] â€” 2026-05-13 â€” feat(GTO-009): solver_cli facing_size_bb + deploy VM â€” estratÃ©gia completa por nÃ³ de decisÃ£o

### Added
- **`solver_cli` (`main.rs`)**: novo campo opcional `facing_size_bb` (padrÃ£o 0.0). Quando > 0, apÃ³s resolver o game tree completo, navega internamente para o nÃ³ onde OOP enfrenta a aposta do IP (`OOP check â†’ IP bet closest_to(facing_size_bb) â†’ OOP to act`) e retorna a estratÃ©gia de resposta (fold/call/raise/allin com frequÃªncias). Campo `facing_node: bool` na saÃ­da indica se a navegaÃ§Ã£o foi bem-sucedida
- **`gto_solver.py`**: `solver_payload` agora inclui `facing_size_bb` â†’ worker da fila e chamadas sÃ­ncronas passam o campo automaticamente ao binary
- **NÃ³s turn/river populados** para mÃ£o t=3910307458 h=257048692293 com estratÃ©gia completa: turn fold 55% / call 30% / raise 15%; river fold 56% / call 33% / raise 8% / allin 2%
- **Frontend** (`Replayer.tsx`): barras de frequÃªncia agora aparecem com qualquer nÃºmero de aÃ§Ãµes (`>= 1` em vez de `>= 2`); `topFreqPct` inline removido da coluna "GTO recomenda" (frequÃªncia jÃ¡ visÃ­vel nas barras)

### Technical
- NavegaÃ§Ã£o no game tree: `navigate_to_facing_bet()` busca `Action::Check` no root (OOP) e depois o `Action::Bet/Raise/AllIn` mais prÃ³ximo de `facing_chips` no nÃ³ IP; `game.back_to_root()` se o nÃ³ nÃ£o existir
- Pot de referÃªncia para labels de resposta: `pot_chips + facing_chips` (mais preciso para raise percentages)
- Flop ainda sem multi-action strategy no servidor de teste (1 core/1GB): Ã¡rvore de 3 streets excede 120s; produÃ§Ã£o (4 vCPU) suporta

---

## [v0.98.7] â€” 2026-05-12 â€” fix(UX-021): engine nÃ£o penaliza BB check em pot nÃ£o contestado

### Fixed
- **`decision_engine_v11.py`**: BB + preflop + check + facingSize=0 retorna imediatamente `label="standard"`, `bestAction="check"` sem calcular penalidades. Resultado no frontend: `is_error=false`, card mostra `âœ“ Correto` (ou nÃ£o aparece se nÃ£o hÃ¡ dados adicionais) em vez de `âœ— Erro / Ideal: Fold`
- O fix de `preflop_gto_ranges.py` (v0.98.6) sÃ³ eliminava o range analysis; a engine ainda calculava um erro independente baseado no `range_evaluation.recommendedPrimaryAction="fold"`

---

## [v0.98.6] â€” 2026-05-12 â€” fix(UX-020): BB free play nÃ£o gera anÃ¡lise de range preflop

### Fixed
- **BB check em pot nÃ£o contestado**: `analyze_preflop` retornava `available=True` com `action_quality="acceptable"` e nota "Fold correto" quando o BB simplesmente checkava seu free play. Corrigido: BB + scenario `rfi` + `action_taken="check"` retorna `available=False` imediatamente â€” painel de anÃ¡lise nÃ£o aparece
- **`_rfi_notes` default incorreto**: o else que gerava "Fold correto" disparava para qualquer aÃ§Ã£o nÃ£o-raise/jam fora do range (incluindo check/call). Corrigido para verificar explicitamente `act == 'fold'` antes de emitir essa nota

---

## [v0.98.5] â€” 2026-05-12 â€” feat(UX-019): DecisionCard unificado no /replayer React

### Changed
- **Painel lateral do Replayer React**: trÃªs seÃ§Ãµes separadas (AnÃ¡lise tÃ©cnica, Preflop Range GTO, GTO Analysis) substituÃ­das por um Ãºnico `DecisionCard` por aÃ§Ã£o do hero
- **Hierarquia de veredito**: GTO Solver > Range preflop > Engine â€” `[GTO Solver]` / `[Range]` / `[AnÃ¡lise]` exibidos como tag discreta no banner, resolvendo ambiguidade de qual fonte priorizar
- **Banner unificado**: colorido por severidade (emerald/sky/amber/red), Ã­cone + label em portuguÃªs sem jargÃ£o tÃ©cnico ("Desvio CrÃ­tico" em vez de "gto_critical", "Leak Grave" em vez de "major_leak")
- **ComparaÃ§Ã£o de aÃ§Ãµes**: "VocÃª jogou / GTO recomenda" em 1 ou 2 colunas conforme discrepÃ¢ncia; frequÃªncia top inline quando `gto_strategy` disponÃ­vel
- **Barras de frequÃªncia do solver**: integradas no mesmo card, aÃ§Ã£o do jogador marcada com `â†` em Ã¢mbar; EV diff `âˆ’0.18 BB vs Ã³timo` exibido quando `ev_bb` disponÃ­vel
- **RodapÃ© contextual compacto**: M-ratio + ICM como grid 2 colunas, visÃ­vel sÃ³ quando campos presentes
- **Conflito engine vs GTO**: substituiu caixa Ã¢mbar separada por 1 linha footnote discreta (`Engine â†’ FOLD / Solver â†’ CHECK â€” priorizando GTO`)
- **Removido**: score breakdown (`math_penalty`, `range_penalty`, `context_penalty`) â€” debug output, nÃ£o coaching; `error_score` com 3 casas decimais; palavra "HeurÃ­stica" completamente eliminada da UI

---

## [v0.98.4] â€” 2026-05-12 â€” feat(UX-018): novo design de painÃ©is no /replayer React

### Changed
- **Preflop Range GTO panel**: header banner colorido (ok/leak/grave) + badges em linha (in_range, hand_type, stack+bucket) + barra de range% com progress bar; remove layout de 2 colunas com Ã­cone solto
- **GTO Analysis panel**: substitui grid de cards por barras horizontais de frequÃªncia â€” sorted desc, player action marcada com `â†` em Ã¢mbar; verdict banner no topo (ok/mixed/bad) com background colorido por label; fallback para `gto_action` sem strategy preservado
- `isPlayedAction`: lÃ³gica de match flexÃ­vel (prefixo bidirecional) para `bet_50pct`, `allin`, etc.

---

## [v0.98.3] â€” 2026-05-12 â€” feat(GTO-008): Replayer standalone com dados reais da API

### Added
- **Carregamento real de dados**: replayer lÃª `?t=<tournament_id>&h=<hand_id>` da URL, busca `ll_token` do `sessionStorage`, e chama `/replay/<t>/<h>` (ou `/coach/student/<student>/replay/<t>/<h>` com `?student=`)
- **Loading overlay**: spinner enquanto busca a API; sem travar a UI
- **Error overlay**: exibe mensagem de erro + botÃ£o "Carregar demo" como fallback
- **Fallback demo**: sem params â†’ DEMO data (comportamento anterior preservado)
- **Vite multi-page build**: `leaklab-replayer-v3.html` adicionado como entry point do rollup â†’ copiado para `dist/` no build de produÃ§Ã£o
- **Vercel**: rewrite explÃ­cito para `/leaklab-replayer-v3.html` antes do catch-all â†’ servido como arquivo estÃ¡tico em produÃ§Ã£o

---

## [v0.98.2] â€” 2026-05-12 â€” feat(GTO-007): painel lateral no Replayer â€” heurÃ­stica + GTO

### Added
- **Painel lateral direito** no Replayer standalone (`leaklab-replayer-v3.html`): aparece em toda aÃ§Ã£o do herÃ³i, desliza com `transition: width .25s ease`
- **Heuristic Card**: prÃ©-flop mostra scenario/in-range/quality badges + range% + aÃ§Ãµes recomendadas; pÃ³s-flop mostra equity bar, pot odds, draw profile badge, M-ratio e ICM pressure
- **GTO Card**: verdict banner colorido (ok/mixed/bad), GTO rec vs aÃ§Ã£o do jogador, EV diff, barras de frequÃªncia de estratÃ©gia com marcaÃ§Ã£o `â†` na aÃ§Ã£o do jogador
- FunÃ§Ãµes JS: `gtoActionLabel`, `gtoVerdictClass`, `gtoVerdictText`, `isPlayerAct`, `stratFillClass`, `stratLblClass`, `rpRenderGtoCard`, `rpRenderHeuristicCard`, `rpRenderSidePanel`
- Demo data atualizado para exibir os dois cards sem API real

---

## [v0.98.1] â€” 2026-05-12 â€” fix(GTO-006): endpoint /decisions/<id>/gto â€” board truncation + hash fallbacks

### Fixed
- **Board truncation**: decisions table stores full board (4+ cards); endpoint now slices to street-appropriate length before hashing (flopâ†’3, turnâ†’4, riverâ†’5)
- **`hero_hand` guard removed**: endpoint previously returned 404 when hero_cards was empty (most decisions); now hero_hand is optional
- **`facing_bb` missing from hash**: `compute_spot_hash` call was missing the `facing_size_bb` arg â€” now passed correctly
- **Multi-step hash fallback**: endpoint tries 4 strategies in order â€” exact (hero_hand+facing), generic (no hand+facing), generic_nf (no facing), `get_gto_node_by_spot` (old hash scheme for legacy nodes)
- **Stored gto_action fallback**: if no node found at all but decision has `gto_label`/`gto_action` stored by worker, returns a synthetic single-action strategy so GTO panel always shows something
- **`get_decision_spot`**: added `gto_action` and `gto_label` to SELECT query
- **Hero card parsing**: handles both space-separated ("Jc Th") and concatenated ("JcTh") formats
- Result: 11/11 labeled decisions now return `found=True` with strategy (was 0/11)

---

## [v0.98.0] â€” 2026-05-12 â€” feat(GTO-004/005): GTO panel redesign + fixes chipsâ†’BB + solver stuck

### Added
- **GTO Panel redesign** (3 layers): Verdict banner (green/amber/red por `player_action_freq`), Full Strategy bars com barra da aÃ§Ã£o do jogador marcada (`â†`), Context collapsÃ­vel (position, street, stack, facing, exploitability)
- **`GtoStrategyAction` interface** em `api.ts`; `GtoDecisionResult` expandido com `strategy[]`, `player_action_freq`, `player_action_label`, `gto_action_label`, `ev_diff`, `exploitability_pct`
- **i18n**: novas chaves `gto.verdict.*`, `gto.ctx.*`, `gto.youPlayedLabel`, `gto.evDiffLabel`, `gto.exploitability`, `gto.strategyLabel`, `gto.contextLabel` nos 3 locales (PT/EN/ES)

### Fixed
- **GTO-004 chipsâ†’BB**: `facing_size_bb` em 3 locais do `app.py` usava `spot.get('facingSize')` (chips raw) em vez de `db_dec.get('facing_bet')` (BB normalizado da tabela `decisions`) â€” hashes errados corrigidos
- **GTO-005 solver stuck**: `hash_no_facing` fallback retornava nÃ³s sem aposta quando hero enfrentava bet â†’ removido; nÃ³s corrompidos (`gto_action=NULL`) voltavam `found=True` com `strategy=[]` â†’ fallback para enqueue corrigido
- **Endpoint `/player/decisions/<id>/gto`** reescrito: retorna `strategy` completa do nÃ³, `player_action_freq` (fuzzy match), `ev_diff`, `exploitability_pct`, labels human-readable
- **`get_decision_spot`** em `repositories.py`: adicionado `facing_bet` ao SELECT

---

## [v0.97.0] â€” 2026-05-11 â€” feat(UX-020): stacks BB com precisÃ£o decimal + C-bet real no HUD

### Changed
- **Stacks sem arredondamento** (`PokerTableV3`): `fmtAmt` agora exibe 1 decimal quando necessÃ¡rio (`1.8 BB`), inteiros sem decimal (`4 BB`), espaÃ§o antes de "BB"
- **C-Bet substituiu Flop Bet** no HUD principal e em `StudentDetail`: indicador passa a medir apenas bets no flop como agressor prÃ©-flop (denominator = oportunidades de c-bet, nÃ£o total de decisÃµes no flop)

### Fixed
- Backend `get_player_stats`: nova query SQL calcula `cbet_pct` via subquery que filtra hands onde hero raised/jammed preflop e viu o flop; campo `flop_bet_pct` removido
- Interface `PlayerStatsResponse` e `PlayerStats` atualizadas para `cbet_pct`

---

## [v0.96.0] â€” 2026-05-10 â€” feat(range-panel): contexto GTO integrado no painel de ranges

### Added
- **Banner de contexto GTO** no RangePanel: quando a mÃ£o Ã© do hero, exibe:
  - CenÃ¡rio detectado (RFI / vs Open / vs 3-Bet)
  - Badge in-range/fora do range com Ã­cone e cor (verde/Ã¢mbar)
  - Quality badge: Correto / AceitÃ¡vel / Leak / Leak grave
  - AÃ§Ã£o recomendada pelo GTO e % do range
- **SeÃ§Ã£o "AnÃ¡lise GTO"** abaixo do grid: exibe as `pro_notes` da engine como bullet points explicativos
- **Auto-seleÃ§Ã£o de tab**: o tab correto (Open / Call / 3-Bet) Ã© selecionado automaticamente com base no `scenario` da decisÃ£o (`rfi`â†’Open, `vs_rfi`â†’Call, `vs_3bet`â†’3-Bet)
- **vs_RFI usa opener correto**: quando disponÃ­vel, usa `vs_position` do preflop_gto para selecionar o opener certo no JSON

---

## [v0.95.0] â€” 2026-05-10 â€” feat(range-panel): ranges dinÃ¢micos do JSON por posiÃ§Ã£o e stack depth

### Added
- **`GET /preflop-ranges`** â€” novo endpoint que serve ranges GTO preflop do `leaklab_gto_ranges.json` por posiÃ§Ã£o e stack depth:
  - ParÃ¢metros: `position` (ex: BTN) e `stack_bb` (float)
  - Retorna: `rfi` (mÃ£os expandidas + %), `vs_rfi` (por opener), `vs_3bet` (4bet/call separados)
  - Stack bucket resolvido automaticamente pelo `_stack_bucket()` existente
  - PosiÃ§Ãµes normalizadas via `_norm_pos()` (suporta UTG+1, MP1, etc.)

### Changed
- **`frontend/src/components/replayer/RangePanel.tsx`** â€” painel de ranges agora consome o endpoint `/preflop-ranges` em vez dos dados estÃ¡ticos de `ranges.ts`:
  - Usa `step.hero_stack_bb` como stack depth da mÃ£o atual (coerente com a anÃ¡lise)
  - Mostra indicador de loading (`Loader2`) enquanto aguarda a API
  - Exibe `stack_bucket` no header para confirmaÃ§Ã£o visual (ex: `50bb`)
  - Fallback automÃ¡tico para dados estÃ¡ticos de `ranges.ts` se a API falhar
  - Label e description dinÃ¢micos com % do range por stack depth
  - vs_RFI usa primeiro opener disponÃ­vel no JSON para a posiÃ§Ã£o selecionada

---

## [v0.94.0] â€” 2026-05-10 â€” feat(engine): preflop GTO range integrado no decision_engine

### Changed
- **`backend/leaklab/decision_engine_v11.py`** â€” `evaluate_decision()` agora aplica range GTO preflop apÃ³s scoring de equity:
  - `_enrich_preflop_gto()`: chama `analyze_preflop()` para cada decisÃ£o preflop com posiÃ§Ã£o, stack e cenÃ¡rio (RFI/vs RFI/vs 3bet)
  - `_preflop_gto_label_adjust()`: matriz completa de ajuste de label por `action_quality`:
    - `correct` â†’ sempre `standard` (GTO confirma a aÃ§Ã£o do jogador)
    - `acceptable` â†’ cap em `marginal` (subÃ³timo mas defensÃ¡vel)
    - `leak` / `major_leak` â†’ floor em `small_mistake` (nÃ£o capeia `clear_mistake` para baixo)
  - `_best_action` sobrescrito com `recommended_actions[0]` do range quando GTO disponÃ­vel
  - `preflop_gto` adicionado ao dict de retorno de `evaluate_decision()`

### Fixed
- DecisÃµes preflop historicamente avaliadas sÃ³ por equity threshold agora recebem classificaÃ§Ã£o baseada em ranges GTO por posiÃ§Ã£o e stack depth
- `bestAction` para preflop agora reflete a aÃ§Ã£o GTO recomendada, nÃ£o apenas a heurÃ­stica de equity

### Tests
- 32 testes existentes do engine: todos passando (sem regressÃ£o)
- 8 novos cenÃ¡rios preflop validados: `correct`, `acceptable`, `leak`, `major_leak` Ã— RFI e vs_rfi

---

## [v0.93.0] â€” 2026-05-10 â€” feat(LLM-002): prompt de anÃ¡lise v2 â€” ICM como multiplicador, reverse implied odds e sÃ­ntese de padrÃµes

### Changed
- **`backend/leaklab/llm_explainer.py`** â€” `_build_payload()` e `system_prompt` completamente reescritos:
  - **ICM como multiplicador matemÃ¡tico**: equity mÃ­nima = pot odds Ã— fator (Ã—1.00 low / Ã—1.15 medium / Ã—1.30 high / Ã—1.50 bubble) â€” calculado em Python antes de enviar ao LLM, nÃ£o estimado pelo modelo
  - **Reverse implied odds**: tier low/medium/high â†’ subtrai 0/3/6pp da equity estimada; dÃ©ficit final = equity mÃ­nima ICM âˆ’ equity real ajustada
  - **Filtro M-Ratio obrigatÃ³rio**: M<6 = push/fold puro (aÃ§Ãµes invÃ¡lidas sinalizadas), M 6-12 = zona de pressÃ£o, M>12 = jogo normal; lÃ³gica integrada na construÃ§Ã£o do input
  - **Rastreamento de padrÃµes recorrentes**: `error_pattern_tracker` conta ocorrÃªncias por tipo de erro na sessÃ£o; nota automÃ¡tica quando mesmo leak aparece N vezes
  - **BLOCO 4 â€” SÃ­ntese Final obrigatÃ³ria**: RelatÃ³rio de PadrÃµes ao final de cada anÃ¡lise (leak dominante, stack depth crÃ­tico, padrÃ£o posicional, ICM sensibilidade, top 3 prioridades, EV recuperÃ¡vel)
  - **pfgto_block push/fold**: branch separado para M<6 com range de jam em vez de range de abertura padrÃ£o
  - **`max_tokens`** aumentado: `max(1200 Ã— N, 3000)` para acomodar sÃ­ntese final

### Added
- Constantes e helpers de mÃ³dulo: `_ICM_MULTIPLIER`, `_REV_IMPL_ADJ_PP`, `_rev_impl_tier()`, `_m_zone()`, `_action_warning()`

---

## [v0.92.0] â€” 2026-05-10 â€” feat(GTO-004): preflop range GTO â€” anÃ¡lise completa por posiÃ§Ã£o e stack depth

### Added
- **`backend/leaklab/preflop_gto_ranges.py`** (novo mÃ³dulo): lÃª `leaklab_gto_ranges.json` e analisa decisÃµes preflop cobrindo trÃªs cenÃ¡rios â€” RFI, vs RFI e vs 3bet â€” com classificador de qualidade (`correct/acceptable/leak/major_leak`) e notas profissionais por posiÃ§Ã£o e stack depth
- **`backend/docs/leaklab_gto_ranges.json`**: ranges MTT 8-max validados (RFI por posiÃ§Ã£o, vs RFI por abridor+defensor, vs 3bet) para buckets de stack 10bbâ€“100bb
- **Frontend â€” painel Range GTO preflop** (`Replayer.tsx`): exibido para hero actions preflop com badge de qualidade, cenÃ¡rio (RFI/vs RFI/vs 3bet), indicador in-range (âœ“/âœ—), aÃ§Ã£o jogada vs recomendada, range %, stack depth e notas profissionais

### Changed
- **`backend/api/app.py`**: `_build_replay_data()` injeta `preflop_gto` em cada hero action preflop via `analyze_preflop()`
- **`backend/leaklab/llm_explainer.py`**: prompt do LLM inclui bloco `ðŸ“Š Range GTO` para decisÃµes preflop, com cenÃ¡rio, in-range, aÃ§Ã£o recomendada e notas profissionais
- **`frontend/src/lib/api.ts`**: `ReplayStep.preflop_gto` adicionado com interface tipada completa
- Painel GTO solver (Oracle) ocultado para hero actions preflop â€” preflop usa range tables; solver apenas para postflop

---

## [v0.91.0] â€” 2026-05-08 â€” feat(UX-012): Replayer â€” cartas inseridas no pod + inlay branco maior

### Changed
- **`leaklab-replayer-v3.html`**: refinamentos visuais nas cartas e fichas
  - **Cartas 30% atrÃ¡s do pod**: cartas sÃ£o renderizadas antes do pod (z-order atrÃ¡s) e posicionadas para 70% visÃ­vel / 30% tucked atrÃ¡s do bloco do jogador; direction-aware (top seats: cartas abaixo do pod, bottom seats: acima)
  - **Inlay branco maior**: elipse central das fichas aumentada de `RX*0.42` para `RX*0.58` â€” dÃ¡ espaÃ§o confortÃ¡vel para "100" (3 dÃ­gitos) sem truncamento

---

## [v0.90.0] â€” 2026-05-08 â€” feat(UX-011): Replayer â€” fichas casino com inlay branco + botÃ£o dealer redesenhado

### Changed
- **`leaklab-replayer-v3.html`**: refinamentos visuais premium nas fichas e botÃ£o dealer
  - **Inlay branco nas fichas**: elipse central agora branca (`rgba(255,255,255,0.92)`) em todas as denominaÃ§Ãµes, com texto de valor sempre em preto `#111` â€” fidelidade a fichas de casino reais
  - **BotÃ£o dealer maior**: dimensÃµes aumentadas de 13Ã—7 para 16Ã—9 (mesmo tamanho das fichas regulares); lado agora com 12 notches alinhados (tÃ©cnica coseno, igual Ã s demais fichas)
  - **SÃ­mbolo â˜… no botÃ£o dealer**: substituiÃ§Ã£o da letra "D" por estrela de 5 pontas desenhada em SVG path (`M0,-5 L1.18,-1.62 ...`), posicionada sobre inlay branco
  - **Fichas amarelas (denom 1)**: denominaÃ§Ã£o 1 permanece amarela (`#f0d020`) â€” branca reservada exclusivamente para o chip dealer

---

## [v0.89.0] â€” 2026-05-08 â€” feat(UX-010): Replayer â€” fichas por denominaÃ§Ã£o real + cards com naipe central vÃ­vido

### Changed
- **`leaklab-replayer-v3.html`**: fichas e cartas redesenhadas com fidelidade PokerStars
  - **Fichas por denominaÃ§Ã£o real**: sistema `breakChips(amount)` decompÃµe o valor em denominaÃ§Ãµes (1000=ouro, 500=roxo, 100=preto, 25=verde, 5=vermelho, 1=branco); badge no topo mostra o valor da denominaÃ§Ã£o da ficha mais alta (e.g. 25 para verde)
  - **RemoÃ§Ã£o de `potToChips`/`betToChips`**: call sites agora passam o valor real direto para `chipStackSVG`
  - **Cartas com naipe central vÃ­vido**: sÃ­mbolo de naipe Ãºnico e dominante no centro do card (opacidade plena); fonte escalada por largura do card (`fCenter = w*0.78`); rank em negrito com sÃ­mbolo menor no canto topo-esquerdo; cores mais vÃ­vidas (#e50a0a para copas/ouros, #111 para espadas/paus)
  - **Verso das cartas**: padrÃ£o azul marinho limpo (remoÃ§Ã£o dos efeitos de diamante anteriores)
  - **Ficha Dealer premium**: botÃ£o D dourado/marfim posicionado geometricamente entre o pod e o centro da mesa (via atan2); badges de posiÃ§Ã£o (BTN/BB/SB) removidos dos pods
  - **Perspectiva isolada**: apenas o SVG de background inclina (`rotateX(9deg)`); pods, fichas e cartas permanecem flat (dois SVGs em camadas separadas)

---

## [v0.88.0] â€” 2026-05-08 â€” feat(UX-009): Replayer v3 â€” fidelidade visual PokerStars

### Changed
- **`leaklab-replayer-v3.html`**: rewrite completo com qualidade PokerStars
  - **Perspectiva 3D real**: CSS `perspective:1100px` + `rotateX(9deg)` no container SVG â€” mesa inclina visualmente como nos softwares comerciais
  - **Mesa**: feltro verde vibrante (`#40b558â†’#1d6430`) + rail grafite escuro (`#252525â†’#0e0e0e`) substituindo o rail marrom anterior
  - **Seat pods**: pill-shaped (borda arredondada `rx=26`), 128Ã—52px, posicionados no perÃ­metro do rail (fora do feltro) â€” idÃªntico ao PokerStars
  - **Hero ring**: oval branca (`rgba(255,255,255,0.88)` stroke-width=3.5) ao redor do pod do hero
  - **Fichas 3D** (`chipStackSVG`): discos empilhados com 8 cores distintas, sombra, borda interna e highlight de luz â€” aplicado no pot e nas apostas individuais
  - **Cartas maiores**: board cards 50Ã—68px com rank+suit topo-esquerdo e baixo-direito, suit central translÃºcido
  - **Dealer button**: cÃ­rculo vermelho com "D" branco no canto do pod
  - **Badge de posiÃ§Ã£o**: pill colorida (BTN=dourado, BB=vermelho, SB=laranja) sobreposta ao pod
  - **Fonte**: migraÃ§Ã£o de Rajdhani â†’ Inter para leitura mais nÃ­tida dos nomes e stacks
  - **Controles**: barra preta flat, abas de street sem bordas internas, botÃµes circulares, aba ativa vermelha

---

## [v0.87.0] â€” 2026-05-08 â€” feat(UX): Replayer premium â€” redesign visual PokerStars-quality

### Changed
- **`leaklab-replayer-v3.html`**: redesign completo
  - Mesa SVG com feltro verde (`#2e7d46 â†’ #1a5230`) e rail marrom/madeira via radial gradient
  - Hero sempre posicionado na parte inferior da mesa (rotOffset formula)
  - Nomes reais de todos os jogadores (removida anonimizaÃ§Ã£o "Villain")
  - Card backs com padrÃ£o X (linhas diagonais + losango), substituindo "?"
  - Hero ring: borda branca semitransparente ao redor do seat box do hero
  - Abas de street (`Pre-flop | Flop | Turn | River | Showdown`) substituindo dots de timeline
  - Slider de velocidade (`0.5Ã— â†’ 3Ã—`) substituindo dropdown
  - BotÃ£o BB/chips para alternar unidade de exibiÃ§Ã£o
  - Cartas posicionadas entre o seat e o centro da mesa (nÃ£o mais flutuando para fora)
- **`frontend/src/components/hud/PokerTable.tsx`**: alinhado com novo estilo
  - Feltro: radial gradient verde (`#2e7d46 â†’ #1a5230`) em vez do teal anterior
  - Rail: fundo marrom escuro (`#1a0a04`) com overlay radial (`#5a2510 â†’ #2d1005`)
  - Feltro oval com `inset-[10%]` e `rounded-[50%]` para melhor proporÃ§Ã£o
  - Hero nameplate: `ring-2 ring-white/40 shadow-[0_0_12px_rgba(255,255,255,0.18)]` (hero ring branca)

---

## [v0.86.0] â€” 2026-05-08 â€” fix(UX): dashboard sem flash ao navegar de volta â€” cache de mÃ³dulo

### Fixed
- **`Index.tsx`**: variÃ¡vel `_cachedTourns` no escopo de mÃ³dulo (fora do componente) persiste o resultado de `tournaments.list()` entre navegaÃ§Ãµes â€” na remontagem, `tourns` e `tournsLoaded` sÃ£o inicializados a partir do cache, eliminando o flash de KPI cards com dashes antes do EmptyDashboard
- **`Index.tsx`**: condiÃ§Ã£o para EmptyDashboard simplificada para `tournsLoaded && !hasData` (sem `!loading`) â€” o cache garante estado correto desde o primeiro render apÃ³s navegaÃ§Ã£o

---

## [v0.85.9] â€” 2026-05-08 â€” fix(UX): dashboard nÃ£o pisca EmptyDashboard ao navegar de volta

### Fixed
- **`Index.tsx`**: adicionado flag `tournsLoaded` (boolean) que sÃ³ vira `true` quando `tournaments.list()` retorna com sucesso â€” EmptyDashboard sÃ³ aparece quando `!loading && tournsLoaded && !hasData`, evitando que uma falha silenciosa da API (catch â†’ null) cause EmptyDashboard mesmo que o usuÃ¡rio tenha dados

---

## [v0.85.8] â€” 2026-05-08 â€” fix(UX): dashboard vazio exibe EmptyDashboard em vez dos KPI cards

### Changed
- **`Index.tsx`**: KPI cards e drift alert movidos para dentro do branch `hasData` â€” sem torneios importados, o dashboard exibe diretamente o `EmptyDashboard` com a Ã¡rea de upload, sem mostrar os cards com "â€”" e "Sem dados"
- **`Index.tsx`**: hints dos KPI cards simplificados (removidos fallbacks `t("kpis.noData")` e `t("kpis.eventsHintEmpty")` agora desnecessÃ¡rios)

---

## [v0.85.7] â€” 2026-05-08 â€” fix(UX): CareerGraphCard â€” contexto da janela de cÃ¡lculo no nÃ­vel atual

### Changed
- **`CareerGraphCard.tsx`**: adicionado rÃ³tulo "Ãºltimos 5 torneios" abaixo do percentual do nÃ­vel atual para deixar claro que o valor Ã© a mÃ©dia dos 5 torneios mais recentes (nÃ£o o histÃ³rico completo)
- **i18n** (PT-BR/EN/ES `dashboard.json`): nova chave `career.currentWindow`

---

## [v0.85.6] â€” 2026-05-06 â€” fix(UX): LeakCausalMap â€” texto legÃ­vel + tooltip no hover

### Changed
- **`LeakCausalMap.tsx`**: texto dentro dos cÃ­rculos substituÃ­do por abreviaÃ§Ã£o de 3-4 letras maiÃºsculas (`abbrev()`) com `fontSize=11` em vez do label completo ilegÃ­vel em `fontSize=9`
- **`LeakCausalMap.tsx`**: raio mÃ­nimo dos cÃ­rculos aumentado de 16 para 18px para acomodar melhor o texto
- **`LeakCausalMap.tsx`**: tooltip de hover adicionado â€” exibe label completo, contagem (nÃ—), avg_score e severity badge; posicionamento inteligente (acima/abaixo) baseado na posiÃ§Ã£o vertical do nÃ³
- **`LeakCausalMap.tsx`**: hit area invisÃ­vel (`r+6`) adicionado para facilitar o hover em cÃ­rculos menores
- **`LeakCausalMap.tsx`**: painel de detalhe ao clicar agora exibe `node.label` completo em vez de `node.id`

---

## [v0.85.5] â€” 2026-05-06 â€” feat: Replayer redesign â€” full-screen, sem scroll, Range flutuante

### Changed
- **`Replayer.tsx`**: layout migrado de `HudLayout` para layout customizado `h-dvh overflow-hidden flex-col` â€” sem barra de rolagem, mesa ocupa todo o espaÃ§o disponÃ­vel entre header e controles
- **`Replayer.tsx`**: `PokerTable` agora Ã© constrangida pela altura (`max-h-[calc(100dvh-20rem)]`) em vez da largura â€” aspect-ratio calculado automaticamente sem overflow
- **`Replayer.tsx`**: `Action Log` removido â€” painÃ©is contextuais (EV feedback, anotaÃ§Ã£o coach, showdown) movidos para faixa horizontal compacta abaixo dos controles
- **`Replayer.tsx`**: botÃ£o **Range** movido para a barra de controles (ao lado de Speed/BB); sempre visÃ­vel, desabilitado fora do preflop
- **`RangePanel.tsx`**: painel Range vira floating draggable no desktop (`fixed z-50`, arrastÃ¡vel pelo header via `onHeaderMouseDown`) e bottom sheet no mobile (backdrop + `max-h-72vh`)
- **`Replayer.tsx`**: identificaÃ§Ã£o da mÃ£o (`MÃƒO 4/68` + progress bar) centralizada na mesma linha do botÃ£o Voltar via `grid grid-cols-3`
- **`Replayer.tsx`**: default de apostas alterado para `BB` em vez de chips
- **`Replayer.tsx`**: `pb-16 md:pb-2` no container mobile para nÃ£o sobrepor a nav bar fixa
- **i18n** (`common.json` PT-BR/ES): `nav.study` encurtado para `"Estudos"` / `"Estudios"` (EN jÃ¡ era `"Study"`)
- **i18n** (`replayer.json` PT-BR/EN/ES): novas chaves `navigation.handLabel`, `navigation.prev`, `navigation.next`

---

## [v0.85.4] â€” 2026-05-06 â€” feat: campo Instagram no perfil pÃºblico do coach

### Added
- **`coach_profiles`**: nova coluna `social_instagram TEXT` â€” schema criado com a coluna e migration (`ALTER TABLE ... ADD COLUMN`) adicionada para Postgres e SQLite
- **`upsert_coach_profile`** (repositories.py): parÃ¢metro `social_instagram` adicionado ao INSERT/ON CONFLICT UPDATE
- **`/coach/profile` POST** (app.py): passa `social_instagram` do payload para o repositÃ³rio
- **`CoachProfile` interface** (api.ts): campo `social_instagram: string | null`
- **`CoachProfile.tsx`** (editor do coach): campo "Instagram" com Ã­cone `<Instagram />` apÃ³s o campo Twitter/X â€” exibiÃ§Ã£o e ediÃ§Ã£o
- **`PublicCoachProfile.tsx`** (perfil pÃºblico): Ã­cone `<Instagram />` clicÃ¡vel na seÃ§Ã£o de redes sociais, ao lado de YouTube/Twitch/Twitter

---

## [v0.85.3] â€” 2026-05-06 â€” fix: admin Users tab nÃ£o mostrava display_name dos coaches

### Fixed
- **`get_all_users` (repositories.py)**: adicionado `LEFT JOIN coach_profiles` para incluir `display_name` do perfil pÃºblico do coach na listagem de usuÃ¡rios do admin
- **`get_all_users_count`**: mesma correÃ§Ã£o para manter contagem paginada consistente com a query principal; filtros de `plan` e `role` agora usam alias `u.` para evitar ambiguidade
- **Busca por display_name**: admin pode agora buscar coaches pelo nome pÃºblico (ex: "Daniel Negreanu") no campo de busca da aba Users â€” antes sÃ³ buscava por `username` e `email`
- **`AdminDashboard.tsx` UsersTab**: coaches com `display_name` sÃ£o exibidos com o mesmo padrÃ£o da aba Finance: nome pÃºblico em destaque + `@username` abaixo â€” elimina a confusÃ£o de um coach aparecer como "coach" na aba Users e "Daniel Negreanu" na aba Finance
- **`AdminUser` interface (api.ts)**: adicionado campo `display_name: string | null`

---

## [v0.85.2] â€” 2026-05-06 â€” fix: coach inbox mostrava sÃ³ 1 conversa (filtro errado)

### Fixed
- **`CoachDashboard.tsx` `MensagensTab`**: o filtro `.filter((t) => t.last_sender_role === "student")` escondia todas as conversas onde o coach jÃ¡ havia respondido, deixando o inbox aparentemente vazio ou com 1 Ãºnica thread. Removido o filtro â€” o inbox agora mostra **todas** as conversas
- **Badge do tab "Mensagens"**: trocado `filter(last_sender_role === "student").length` por `reduce(unread_count)` para contar mensagens nÃ£o lidas reais, nÃ£o apenas threads sem resposta
- **UX**: username em negrito e preview colorido para conversas com mensagens nÃ£o lidas; prefixo `â†©` para indicar threads que aguardam resposta do coach (aluno enviou Ãºltimo); empty state atualizado para "Nenhuma conversa ainda"

---

## [v0.85.1] â€” 2026-05-06 â€” feat: UX-009 â€” exemplos visuais interativos na /docs

### Added
- **Exemplos visuais** adicionados a 9 seÃ§Ãµes da documentaÃ§Ã£o: Scoring, Top Leaks, Forma Recente, Qualidade das DecisÃµes, Performance por Street, Performance por PosiÃ§Ã£o, Colapso sob PressÃ£o, PressÃ£o ICM e Meu NÃ­vel
- **Componentes `ExampleBox`, `MiniBar`, `MiniScoreLine`, `MiniSessionBars`** em `Docs.tsx` para renderizar mini-rÃ©plicas dos indicadores reais com cores e proporÃ§Ãµes fiÃ©is
- **Chaves de exemplo i18n** em PT, EN e ES para todas as 9 seÃ§Ãµes (`exampleLabel`, `example`, `example_*` por seÃ§Ã£o)

### Fixed
- `t("leaks.critical")` e `t("form.*")` no `Docs.tsx` agora usam `td` (namespace `dashboard`) em vez do namespace `docs` â€” evita fallback silencioso para chave literal

---

## [v0.85.0] â€” 2026-05-05 â€” feat: UX-008 â€” tooltips, renome Strategic Twin e docs expandida

### Added
- **HudTooltip** adicionado a 8 cards que estavam sem: `BankrollChart`, `CareerGraphCard`, `CognitiveFailureCard`, `GhostDrillCard`, `LeakCausalMap`, `LeaksPanel`, `LevelCard`, `StrategicTwinCard`
- **11 novas seÃ§Ãµes** em `/docs` cobrindo todos os cards do dashboard: Top Leaks, Mapa Causal, Forma Recente, Qualidade das DecisÃµes, Performance por Street, Performance por PosiÃ§Ã£o, Colapso sob PressÃ£o, PressÃ£o ICM, EvoluÃ§Ã£o do Bankroll, Meu NÃ­vel â€” cada um com explicaÃ§Ã£o de objetivo, conexÃ£o com leaks e orientaÃ§Ã£o para iniciantes. DisponÃ­vel em PT, EN e ES.
- **8 chaves de tooltip** novas no `dashboard.json` (3 locales) para os cards acima

### Changed
- **`StrategicTwinCard`** renomeado de "Perfil EstratÃ©gico" para "TendÃªncias EstratÃ©gicas" (PT) / "Strategic Patterns" (EN) / "Tendencias EstratÃ©gicas" (ES) â€” elimina conflito de nome com `PlayerDnaCard` (Decision DNA)
- **`Docs.tsx`**: `SECTION_IDS` expandido de 12 para 23 seÃ§Ãµes com nav lateral totalmente funcional
- **`docs.json`** (3 locales): nav atualizado, seÃ§Ã£o `twin.title` atualizado com novo nome

---

## [v0.84.8] â€” 2026-05-05 â€” Fix: replay 404 no Sparring Mode

### Fixed
- **`backend/api/app.py`**: endpoint `/replay/<tournament_id>/<hand_id>` usava `get_tournament()` (busca por PokerStars tournament_id string), mas o Sparring envia o `id` inteiro do banco. Agora tenta `get_tournament_by_db_id` primeiro quando o parÃ¢metro Ã© numÃ©rico, com fallback para a busca por string â€” compatÃ­vel com ambos os callers.

---

## [v0.84.7] â€” 2026-05-05 â€” Fix: Sparring 500 no PostgreSQL (HAVING alias)

### Fixed
- **`backend/database/repositories.py`**: `get_sparring_hand` usava `HAVING mistakes > 0` com alias de SELECT â€” PostgreSQL nÃ£o permite aliases no HAVING (sÃ³ SQLite). SubstituÃ­do pela expressÃ£o completa `HAVING SUM(CASE WHEN ... THEN 1 ELSE 0 END) > 0` nas duas variantes da query (com e sem exclusÃ£o de mÃ£os jÃ¡ vistas).

---

## [v0.84.6] â€” 2026-05-05 â€” Fix: Ghost Table 500 no PostgreSQL

### Fixed
- **`backend/database/repositories.py`**: `get_drill_stats` usava `datetime('now', ? || ' days')` â€” concatenaÃ§Ã£o dinÃ¢mica de parÃ¢metro nÃ£o Ã© convertida pelo regex do `_adapt()`, entÃ£o `datetime()` chegava ao PostgreSQL que nÃ£o conhece essa funÃ§Ã£o. SubstituÃ­do por cutoff prÃ©-computado em Python (mesmo padrÃ£o de todas as outras funÃ§Ãµes do arquivo).

---

## [v0.84.5] â€” 2026-05-05 â€” UX: tabs na pÃ¡gina Plano de Estudos

### Changed
- **`frontend/src/pages/StudyPlan.tsx`**: conteÃºdo reorganizado em 3 tabs â€” DiagnÃ³stico, Roteiro, ExercÃ­cios â€” eliminando o scroll longo em coluna Ãºnica. KPIs ficam sempre visÃ­veis acima das tabs. Tab DiagnÃ³stico mantÃ©m o layout 8/4 col no desktop.
- **`frontend/src/i18n/locales/*/study.json`**: adicionada chave `tabs.{diagnosis,schedule,exercises}` nas 3 locales (PT-BR / EN / ES).
- Aproveitado para substituir hardcoded `"Dia {n}"` pelo i18n `t("day.label", { n })` no roteiro semanal.

---

## [v0.84.4] â€” 2026-05-05 â€” Fix /coaches 500 + remoÃ§Ã£o do card WhatsApp

### Fixed
- **`backend/database/repositories.py`**: `ROUND(AVG(CAST(rating AS REAL)), 1)` â†’ `NUMERIC` em 3 queries â€” PostgreSQL nÃ£o aceita `ROUND(double precision, integer)`, somente `ROUND(numeric, integer)`. Causava 500 em `/coaches` e no endpoint de perfil do coach.

### Removed
- **`frontend/src/pages/StudyPlan.tsx`**: card "Treinar no WhatsApp" removido junto com variÃ¡vel `waNumber` e import `MessageCircle` (ambos inutilizados apÃ³s remoÃ§Ã£o).

---

## [v0.84.3] â€” 2026-05-05 â€” Fix: 500/CORS em /study/plan apÃ³s deploy de observabilidade

### Fixed
- **`backend/api/app.py`**: `_log_request` after_request handler agora envolto em `try/except` â€” uma falha no logging nÃ£o mais substitui a resposta do endpoint por uma nova 500 sem CORS headers.
- **`backend/api/app.py`**: `sentry_sdk.init()` movido para APÃ“S `logging.basicConfig(force=True)` â€” impede que `force=True` remova o `LoggingIntegration` handler do Sentry ao inicializar depois.
- **`backend/api/app.py`**: imports do `sentry_sdk` agora dentro de `try/except ImportError` â€” app sobe normalmente em ambientes sem o SDK instalado (dev sem `pip install`).

---

## [v0.84.2] â€” 2026-05-05 â€” Auditoria de seguranÃ§a + CLAUDE.md atualizado

### Security
- **`backend/api/app.py`**: CORS configurÃ¡vel via variÃ¡vel de ambiente `ALLOWED_ORIGINS` (padrÃ£o `*` em dev; em prod, restrito aos domÃ­nios explicitamente listados). Header `Vary: Origin` adicionado quando origin-specific.
- **`backend/api/app.py`**: `/health` nÃ£o expÃµe mais tipo de banco nem `db_url_set` â€” retorna apenas `{status, version}`.
- **`backend/api/app.py`**: `/analyze/guest` recebe `@limiter.limit("10 per hour")` â€” endpoint pÃºblico agora tem rate limiting.
- **`render.yaml`**: variÃ¡vel `ALLOWED_ORIGINS` adicionada com valor padrÃ£o `https://leaklab.vercel.app` (ajustar para domÃ­nio real antes de deploy).

### Docs
- **`CLAUDE.md`**: reescrito â€” arquitetura atualizada com todas as tabelas (18), endpoints principais, pÃ¡ginas frontend, mÃ³dulos de features, variÃ¡veis de ambiente e notas de seguranÃ§a/CORS. Era crÃ­tico: estava desatualizado desde v0.45.0.

### Not changed (false positives / low risk)
- `.env` com secrets: `backend/.env` estÃ¡ corretamente no `.gitignore`; `frontend/.env` contÃ©m apenas `pk_test_*` (Stripe publishable key â€” pÃºblico por design).
- JWT secret: `auth.py` jÃ¡ levanta `RuntimeError` em produÃ§Ã£o se `LEAKLAB_SECRET` nÃ£o estiver setado.
- `dangerouslySetInnerHTML` em `Docs.tsx`: strings vÃªm de JSON bundlado no build, sem input de usuÃ¡rio.

---

## [v0.84.1] â€” 2026-05-04 â€” Suporte: badge no header + fix estado reply no admin

### Fixed
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: `TicketRow.handleReply` chama `setOpen(false)` antes de invalidar queries â€” textarea some imediatamente ao confirmar envio, exibindo o card de "Resposta enviada".

### Changed
- **`frontend/src/components/hud/HudHeader.tsx`**: botÃ£o `LifeBuoy` adicionado no header (visÃ­vel a todos os usuÃ¡rios nÃ£o-admin). Badge vermelho aparece quando hÃ¡ tickets com resposta do admin. Clicar abre `SupportModal` diretamente na aba "Minhas mensagens" quando hÃ¡ respostas pendentes. `SupportModal` renderizado inline no header (igual ao drawer do coach).
- **`frontend/src/pages/Index.tsx`**: badge de suporte do footer removido para nÃ£o-admin (movido para o header). Footer mantÃ©m apenas o badge de tickets abertos para admin.

---

## [v0.84.0] â€” 2026-05-04 â€” Suporte bidirecional: aluno visualiza resposta do admin

### Added
- **`backend/api/app.py`**: `GET /support/my-tickets` â€” retorna todos os tickets do usuÃ¡rio logado (com admin_reply e replied_at). `GET /support/my-tickets/unread` â€” contagem de tickets com resposta do admin.
- **`frontend/src/components/hud/SupportModal.tsx`**: reescrito com duas abas â€” "Nova mensagem" (formulÃ¡rio) e "Minhas mensagens" (histÃ³rico de tickets + respostas do admin). Badge na aba Minhas mensagens quando hÃ¡ respostas. Abre direto na aba inbox quando `initialTab="inbox"`.
- **`frontend/src/pages/Index.tsx`**: badge no botÃ£o Suporte do footer para alunos nÃ£o-admin quando hÃ¡ tickets respondidos. Modal abre na aba inbox automaticamente nesse caso. `useQuery` para `myUnreadCount` com polling de 2min.
- **`frontend/src/lib/api.ts`**: interface `MyTicket` + mÃ©todos `support.myTickets()` e `support.myUnreadCount()`.

---

## [v0.83.9] â€” 2026-05-04 â€” Admin: exclusÃ£o permanente de usuÃ¡rios com confirmaÃ§Ã£o

### Added
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: botÃ£o de lixeira por linha na aba UsuÃ¡rios. Abre `DeleteUserModal` com nome/email do alvo, campo de senha administrativa e aviso de irreversibilidade. Senha Ã© verificada no backend antes de qualquer exclusÃ£o.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: `DeleteUserModal` â€” modal com Ã­cone de alerta, input de senha com `autoFocus`, feedback de erro inline, botÃ£o "Excluir definitivamente" desabilitado atÃ© senha digitada.
- **`backend/api/app.py`**: `DELETE /admin/users/<uid>` â€” exige `admin_password` no body, verifica credenciais do admin via `verify_password`, bloqueia auto-exclusÃ£o, deleta todos os dados do usuÃ¡rio em cascata.
- **`backend/database/repositories.py`**: `delete_user_admin(user_id)` â€” remove decisÃµes, torneios, cache LLM, tickets de suporte e o registro `users` em cascata, dentro de uma Ãºnica transaÃ§Ã£o.
- **`frontend/src/lib/api.ts`**: `adminDashboard.deleteUser(id, adminPassword)` mÃ©todo adicionado.

---

## [v0.83.8] â€” 2026-05-04 â€” Badge de tickets abertos + sistema de resposta no admin

### Added
- **`frontend/src/pages/Index.tsx`**: badge vermelho no botÃ£o "Suporte" do footer mostrando contagem de tickets abertos (admin only). Polling a cada 2 minutos via `useQuery`.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: aba "Suporte" agora exibe lista completa de tickets com sistema de resposta inline â€” textarea de reply, botÃ£o de envio, toggle "editar resposta", badges de status (open=vermelho, replied=azul). Consulta e invalida `admin-support-count` apÃ³s resposta.
- **`backend/api/app.py`**: `POST /admin/support-tickets/<id>/reply` â€” atualiza `admin_reply`, `status='replied'` e `replied_at` (require_admin). `GET /admin/support-tickets/count` â€” retorna `{ open: N }` (require_admin).
- **`backend/database/schema.py`**: colunas `admin_reply TEXT` e `replied_at` adicionadas Ã  tabela `support_tickets` em SQLite e PostgreSQL.
- **`frontend/src/lib/api.ts`**: mÃ©todos `support.unreadCount()` e `support.replyTicket(id, reply)` adicionados ao namespace `support`.

---

## [v0.83.6] â€” 2026-05-04 â€” Footer: remoÃ§Ã£o do status bar + modal de suporte

### Changed
- **`frontend/src/pages/Index.tsx`**: footer simplificado â€” removido "ENC: AES-256 â€¢ LATENCY: 14ms â€¢ SESSION_LOCKED" e link "Status". Mantidos apenas "Docs" e "Suporte". Suporte agora abre um modal em vez de ser um link morto.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: removidas chaves `sessionLocked` e `status_page`; adicionadas chaves `supportModal.*` com tÃ­tulo, campos, categorias e mensagens de feedback nas 3 locales.

### Added
- **`frontend/src/components/hud/SupportModal.tsx`**: modal de contato com seletor de categoria (bug, dÃºvida, sugestÃ£o, cobranÃ§a, outro), campo de assunto e mensagem (2000 chars), prÃ©-preenchimento de usuÃ¡rio/email, feedback de sucesso e erro. i18n nas 3 locales.
- **`backend/database/schema.py`**: tabela `support_tickets` (id, user_id, category, subject, message, status, created_at) criada em SQLite e PostgreSQL.
- **`backend/api/app.py`**: `POST /support/contact` â€” salva ticket no banco, exige mensagem nÃ£o-vazia, requer autenticaÃ§Ã£o.

---

## [v0.83.5] â€” 2026-05-04 â€” Bugfix: narrativas IA nÃ£o atualizam ao trocar idioma

### Fixed
- **`frontend/src/pages/Index.tsx`**: adicionado `useEffect` separado com dependÃªncia `[i18n.language]` que re-busca apenas os 4 endpoints de narrativa sensÃ­veis ao idioma (`leakGraph`, `career`, `cognitiveFailures`, `strategicTwin`) quando o locale muda. Guard `langMounted` evita double-fetch no mount inicial. Os demais dados (evolution, breakdown, tournaments, etc.) nÃ£o sÃ£o re-buscados desnecessariamente.

---

## [v0.83.4] â€” 2026-05-04 â€” Bugfix: termos de poker em inglÃªs nos prompts LLM

### Fixed
- **`backend/leaklab/llm_explainer.py`**: adicionada constante `_POKER_TERMS_EN` com lista canÃ´nica de termos tÃ©cnicos (fold, call, raise, bet, check, jam, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position, IP, OOP, shove, reshove, open, limp, squeeze). InstruÃ§Ã£o injetada em todos os system prompts: decisÃ£o, resumo de torneio, comparaÃ§Ã£o, sessÃ£o review, coach chat e sparring. Elimina traduÃ§Ãµes indevidas como "ruas" (â†’ turn/river), "mÃ£o" (â†’ hand), "tabuleiro" (â†’ board) no texto gerado pela IA.
- **`backend/leaklab/llm_explainer.py`**: `_LANG_INSTRUCTIONS` atualizado para incluir a clÃ¡usula de poker terms nas 3 locales (PT-BR e ES).

---

## [v0.83.3] â€” 2026-05-04 â€” Bugfix: terminologia tÃ©cnica e truncamento na AnÃ¡lise Comparativa

### Fixed
- **`backend/leaklab/llm_explainer.py`**: `max_tokens` da narrativa comparativa aumentado de 100 â†’ 350 (texto era cortado no meio da segunda frase).
- **`backend/leaklab/llm_explainer.py`**: prompts de comparaÃ§Ã£o, sessÃ£o e coach chat substituem `standard_pct`/`avg_score`/`clear_pct` por `Standard%`/`Score mÃ©dio`/`Erros claros` â€” o LLM nÃ£o mais repete nomes de variÃ¡veis no texto gerado.
- **`backend/leaklab/llm_explainer.py`**: corrigida interpolaÃ§Ã£o dupla-chave `{{avg_score:.4f}}` â†’ `{avg_score:.4f}` no prompt do plano de estudos â€” mÃ©tricas reais agora chegam ao LLM em vez de placeholders literais.
- **`backend/leaklab/llm_explainer.py`**: template fallback `_template_comparison` e string de carreira usam `Standard%` em vez de `standard_pct`.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seÃ§Ã£o TrajetÃ³ria de Carreira substituiu todos os `standard_pct` por `Standard%` (em negrito) nos valores de parÃ¡grafo e tabela.

---

## [v0.83.2] â€” 2026-05-04 â€” Bugfix: import mÃºltiplo de torneios no EmptyDashboard

### Fixed
- **`frontend/src/components/hud/EmptyDashboard.tsx`**: refatorado para usar `useUploadQueue` (mesmo hook do HudHeader) em vez de `processFile` prÃ³prio. Agora aceita mÃºltiplos arquivos via drag-and-drop e via seletor (`multiple`). O painel de fila com status por arquivo Ã© exibido durante o processamento. Reset `e.target.value = ""` no `onChange` para permitir re-seleÃ§Ã£o do mesmo arquivo.

---

## [v0.83.1] â€” 2026-05-04 â€” Sprint AY: Mobile audit + responsividade

### Fixed
- **`frontend/src/components/hud/DraggableCard.tsx`**: drag handle sempre visÃ­vel em mobile (`opacity-100 md:opacity-0 md:group-hover:opacity-100`); tamanho aumentado (`px-3 py-1 / size-4`) para alvo de toque adequado; `touch-none` para impedir scroll acidental durante drag.
- **`frontend/src/pages/GhostTable.tsx`**: botÃµes de aÃ§Ã£o com `min-h-[44px]` â€” atende ao mÃ­nimo de toque iOS/Android HIG (era ~42px).
- **`frontend/src/pages/Sparring.tsx`**: mesmo fix de `min-h-[44px]` nos botÃµes de aÃ§Ã£o contextuais.
- **`frontend/src/components/hud/HudHeader.tsx`**: `LanguageSwitcher` removido do `hidden sm:` â€” seletor de idioma agora acessÃ­vel em mobile (era invisÃ­vel em telas < 640px).
- **`frontend/src/pages/StudentProfile.tsx`**: grids de 2 colunas nos formulÃ¡rios de dados do jogador alterados para `grid-cols-1 sm:grid-cols-2` â€” campos nÃ£o colapsam em telas < 400px.

---

## [v0.83.0] â€” 2026-05-04 â€” Sprint AX: Onboarding para novos usuÃ¡rios

### Added
- **`backend/database/schema.py`**: coluna `onboarding_completed` (BOOLEAN, default FALSE) adicionada Ã  tabela `users` via migraÃ§Ã£o em Postgres e SQLite.
- **`backend/database/repositories.py`**: `set_onboarding_completed(user_id)` â€” marca o onboarding como concluÃ­do no banco.
- **`backend/api/app.py`**: `POST /player/onboarding/complete` â€” endpoint para registrar conclusÃ£o ou skip do onboarding. Campo `onboarding_completed` incluÃ­do no payload de `GET /auth/me`.
- **`frontend/src/lib/api.ts`**: campo `onboarding_completed?: boolean` adicionado Ã  interface `UserProfile`; `auth.completeOnboarding()` chama `POST /player/onboarding/complete`.
- **`frontend/src/components/hud/OnboardingModal.tsx`**: modal multi-step (4 passos) com stepper visual, Ã­cones Lucide por etapa, botÃµes Pular/Voltar/PrÃ³ximo, CTA final navega para `/analyze`. Ao fechar (skip ou finish) chama `completeOnboarding()` e `refreshUser()` para nÃ£o exibir novamente.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/onboarding.json`**: namespace `onboarding` completo nas 3 locales â€” passos welcome, upload, train, ready.
- **`frontend/src/i18n/index.ts`**: namespace `onboarding` registrado nas 3 locales.

### Changed
- **`frontend/src/pages/Index.tsx`**: estado `showOnboarding` inicializado com `!user?.onboarding_completed`; `<OnboardingModal>` renderizado condicionalmente ao lado do `<AcceptCoachModal>`.

---

## [v0.82.3] â€” 2026-05-04 â€” Docs: Pressure Mode + Sparring rotation + BACKLOG atualizado

### Changed
- **`frontend/src/pages/Docs.tsx`**: seÃ§Ã£o Ghost Table agora renderiza `ghost.p5` â€” descriÃ§Ã£o do Pressure Mode (cronÃ´metro 30s, anel SVG, fold automÃ¡tico, badge ðŸ”¥ de streak).
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: adicionada chave `ghost.p5` nas 3 locales descrevendo o Pressure Mode. Chave `sparring.p2` atualizada para mencionar o mecanismo de rotaÃ§Ã£o de mÃ£os por sessÃ£o (exclusÃ£o de mÃ£os jÃ¡ jogadas, ciclo de 90 dias).
- **`BACKLOG.md`**: Sprints AQâ€“AW e bugfixes v0.81.1â€“v0.82.2 movidos para tabela de concluÃ­dos. SeÃ§Ã£o "Em Aberto" atualizada: FEAT-14/15/16 (entregues) removidos; FEAT-17 (Onboarding) e FEAT-18 (Mobile audit) adicionados como prÃ³ximas sprints AX e AY.

---

## [v0.82.2] â€” 2026-05-04 â€” Fix: perfil i18n completo + telefone no perfil + remoÃ§Ã£o WhatsApp Coaching

### Changed
- **`frontend/src/pages/StudentProfile.tsx`**: seÃ§Ã£o WhatsApp Coaching removida (integraÃ§Ã£o Meta adiada). Campo "Telefone / WhatsApp" movido para dentro de "Dados do Jogador" â€” salvo em conjunto com os demais dados no mesmo botÃ£o; saves chamadom `profileApi.update()` + `authApi.updatePhone()`.
- **`frontend/src/pages/StudentProfile.tsx`**: i18n completo â€” todos os textos hardcoded da pÃ¡gina substituÃ­dos por `t()`. Sub-componentes `CoachReviewWidget`, `CoachDiscoveryCard` e `NoCoachDiscovery` agora usam `useTranslation("profile")` e nÃ£o tÃªm nenhum string hardcoded em PT-BR.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/profile.json`**: adicionados grupos `email.*`, `password.*` (labels, placeholders, botÃµes, toasts) e `coach.*` (review, discovery, unlink) â€” cobertura total da pÃ¡gina em PT/EN/ES. Chaves `whatsapp.*` e `sections.whatsapp` removidas.

---

## [v0.82.1] â€” 2026-05-04 â€” Fix: perfil demogrÃ¡fico visÃ­vel e editÃ¡vel na pÃ¡gina de Perfil

### Added
- **`frontend/src/pages/StudentProfile.tsx`**: nova seÃ§Ã£o "Dados do Jogador" no topo da pÃ¡gina de perfil â€” exibe e permite editar todos os 7 campos demogrÃ¡ficos (ano de nascimento, paÃ­s, estado, cidade, anos de experiÃªncia, modalidade, faixa de buy-in) mesmo quando ainda nÃ£o preenchidos. Barra de progresso mostra quantos dos 5 campos essenciais estÃ£o completos; fica verde ao completar todos.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/profile.json`**: namespace `demo.*` adicionado nas 3 locales com todas as labels, opÃ§Ãµes de select e mensagens de status.

### Fixed
- **Dados do jogador preenchidos mas invisÃ­veis**: os campos demogrÃ¡ficos sÃ³ existiam no `ProfileCompletionCard` do dashboard (descartÃ¡vel e que some apÃ³s o preenchimento). Agora ficam sempre acessÃ­veis via `/profile`, com valores carregados do backend e salvos via `PATCH /player/profile`.

---

## [v0.82.0] â€” 2026-05-04 â€” Sprint AW: Ghost Table Pressure Mode + Sparring hand rotation

### Added
- **`frontend/src/pages/GhostTable.tsx`**: **Pressure Mode** â€” toggle na intro desbloqueia modo cronometrado: 30 s por decisÃ£o, timeout dispara fold automÃ¡tico via `submitRef.current` (sem stale closure), streak de acertos exibido com badge ðŸ”¥ durante a sessÃ£o e tile dedicado na tela de conclusÃ£o.
- **`frontend/src/pages/GhostTable.tsx`**: `TimerRing` â€” anel SVG circular de contagem regressiva com transiÃ§Ã£o CSS suave; vermelho quando â‰¤ 10 s. BotÃµes de aÃ§Ã£o bloqueados apÃ³s timeout atÃ© o prÃ³ximo spot.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/ghost.json`**: chaves `pressure.toggle`, `pressure.desc`, `pressure.timedOut`, `pressure.streakLabel` adicionadas nas 3 locales.
- **`backend/database/repositories.py`**: parÃ¢metro `exclude_hand_ids: list` em `get_sparring_hand` â€” filtra mÃ£os jÃ¡ vistas na sessÃ£o; se todas as mÃ£os foram excluÃ­das, retorna o ciclo desde o inÃ­cio.
- **`backend/api/app.py`**: endpoint `GET /player/sparring/hand` passa `exclude_hand_ids` (comma-separated) para o repositÃ³rio.
- **`frontend/src/lib/api.ts`**: `sparring.hand()` aceita `exclude_hand_ids?: string[]` e os envia como query param.
- **`frontend/src/pages/Sparring.tsx`**: `seenHandIds` ref â€” rastreia IDs de mÃ£os jÃ¡ jogadas na sessÃ£o; `loadHand()` passa a lista para excluir ao buscar a prÃ³xima mÃ£o, garantindo rotaÃ§Ã£o mesmo com mÃºltiplas chamadas de "New Hand".

### Fixed
- **Sparring sempre exibia a mesma mÃ£o**: `get_sparring_hand` nÃ£o tinha mecanismo de exclusÃ£o â€” `New Hand` sempre retornava a mÃ£o com o pior erro. Agora cada mÃ£o jogada Ã© adicionada Ã  lista de exclusÃ£o e a prÃ³xima chamada traz uma mÃ£o diferente.

---

## [v0.81.1] â€” 2026-05-04 â€” Bugfix: i18n sparring + test suite verde

### Fixed
- **`frontend/src/i18n/locales/{pt-BR,en,es}/sparring.json`**: chaves `arenaLabel` e `arenaDesc` adicionadas nas 3 locales â€” eram usadas pelo card de intro da fase idle do Sparring mas estavam ausentes nos arquivos de traduÃ§Ã£o (as chaves retornavam o prÃ³prio nome da chave em vez do texto traduzido).
- **`backend/tests/run_all_tests.py`**: substituÃ­do `python3` por `sys.executable` + adicionado `encoding='utf-8'` â€” `python3` no Windows apontava para Python 3.10 (sem suporte a backslash em f-strings), causando falsos negativos em 25 testes da suite de subscription.
- **`backend/tests/test_api_endpoints.py`**: 3 testes de coach registration atualizados para o novo fluxo `/auth/coach-apply` (coaches nÃ£o se registram mais diretamente via `/auth/register`; login retorna 403 `coach_pending` atÃ© aprovaÃ§Ã£o admin).
- **`backend/tests/test_subscription.py`**: 2 testes de webhook atualizados â€” `test_webhook_no_secret_allowed` e `test_webhook_subscription_deleted_downgrades` agora patcham `api.app.STRIPE_WEBHOOK_SECRET` para `""` evitando interferÃªncia do `.env` local; comportamento esperado corrigido para refletir a implementaÃ§Ã£o atual do endpoint.

---

## [v0.81.0] â€” 2026-05-04 â€” Sprint AV: PÃ¡gina Treinos + BotÃµes contextuais

### Added
- **`frontend/src/pages/Training.tsx`**: nova pÃ¡gina `/training` â€” landing de treino com dois cards (Ghost Table e Sparring Mode), esquema visual primÃ¡rio vs amber, lista de features, CTAs diretos.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/training.json`**: namespace `training` com todas as strings da pÃ¡gina nas 3 locales.
- **`frontend/src/i18n/index.ts`**: namespace `training` registrado nas 3 locales.
- **`frontend/src/App.tsx`**: rota `/training` adicionada (ProtectedRoute).

### Changed
- **`frontend/src/components/hud/HudHeader.tsx`**: `TrainingDropdown` removido â€” substituÃ­do por `NavLink` simples `/training` com `activePaths: ["/training", "/ghost", "/sparring"]`; cÃ³digo simplificado (sem `TrainingDropdown`, sem `ChevronDown`, sem `isDropdown`).
- **`frontend/src/pages/Sparring.tsx`**: botÃµes de aÃ§Ã£o contextuais â€” `facing_bet > 0` exibe `[fold, call, raise, jam]`; `facing_bet == 0` exibe `[fold, check, bet, jam]`; `facing_bet == null` exibe todos os 6 (fallback). Grid adapta de 4 para 6 colunas conforme o conjunto.

---

## [v0.80.0] â€” 2026-05-04 â€” Sprint AU: PokerTable visual no Sparring

### Changed
- **`frontend/src/pages/Sparring.tsx`**: substituiÃ§Ã£o da exibiÃ§Ã£o plana de cartas pelo componente `PokerTable` completo â€” herÃ³i posicionado na parte inferior da mesa, vilÃµes ao redor (N baseado em `num_players`), board real, pot real, stacks em BB. Exibido tanto na fase *playing* quanto na fase *feedback* (mesa congelada como contexto). Remove import direto de `PlayingCard` (agora encapsulado no `PokerTable`).

### Added
- **`frontend/src/pages/Sparring.tsx`**: helper `buildSparringSeats(step, heroCards)` â€” constrÃ³i o array `Seat[]` com herÃ³i (cartas reais + stack real) e vilÃµes (cartas viradas + 100 BB estimado).

---

## [v0.79.0] â€” 2026-05-04 â€” Sprint AT: Menu "Treinos" + Sparring Visual

### Added
- **`frontend/src/components/hud/HudHeader.tsx`**: componente `TrainingDropdown` â€” agrupamento de Ghost Table e Sparring sob um menu "Treinos/Training/Entrenamiento" com dropdown no desktop; mobile mantÃ©m item Ãºnico "Treinos" â†’ `/ghost` com estado ativo cobrindo ambas as rotas (`/ghost`, `/sparring`).
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: chave `nav.training` adicionada ("Treinos" / "Training" / "Entrenamiento").

### Changed
- **`frontend/src/pages/Sparring.tsx`**: redesign visual completo para diferenciar do Ghost Table â€” esquema de cores amber/laranja, componente `StreetTimeline` (cadeia horizontal de pontos com Ã­cones Flame/CheckCircle2/XCircle), componente `HandRecap` (histÃ³rico compacto de decisÃµes anteriores), arena intro card com gradiente e Ã­cone `Swords`.

---

## [v0.78.0] â€” 2026-05-04 â€” Sprint AS: AI Sparring Mode

### Added
- **`backend/database/repositories.py`**: `get_sparring_hand(user_id, hand_id, tournament_id)` â€” auto-seleciona a mÃ£o com pior erro nos Ãºltimos 90 dias (priorizando mÃ£os com mÃºltiplas decisÃµes), retorna todas as decisÃµes em ordem cronolÃ³gica com contexto completo.
- **`backend/api/app.py`**: `GET /player/sparring/hand?hand_id=&tournament_id=` â€” serve mÃ£o para o modo Sparring.
- **`frontend/src/lib/api.ts`**: interfaces `SparringStep` e `SparringHand`; `sparring.hand(hand_id?, tournament_id?)`.
- **`frontend/src/pages/Sparring.tsx`**: nova pÃ¡gina `/sparring` com 4 fases â€” playing (cartas + botÃµes de aÃ§Ã£o), feedback (correto/errado, best action, delta, SRS, anÃ¡lise engine), summary (precisÃ£o geral, linha por decisÃ£o), idle. Reutiliza `PlayingCard`, `drill.submit`, `drill.analysis` e SRS do Ghost Table.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/sparring.json`**: namespace `sparring` com todas as strings da pÃ¡gina (PT/EN/ES).
- **`frontend/src/i18n/index.ts`**: namespace `sparring` registrado nas 3 locales.
- **`frontend/src/pages/Docs.tsx`**: seÃ§Ã£o `sparring` com tabela de fases.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seÃ§Ã£o `sparring` na docs e chave `nav.sparring`.

### Changed
- **`frontend/src/App.tsx`**: rota `/sparring` adicionada (ProtectedRoute).
- **`frontend/src/components/hud/HudHeader.tsx`**: item "Sparring" adicionado ao nav de players.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: chave `nav.sparring` adicionada.

---

## [v0.77.0] â€” 2026-05-04 â€” Sprint AR: Personal Strategic Twin

### Added
- **`backend/database/repositories.py`**: `get_strategic_twin_profile(user_id, days=180)` â€” agrega spots por `(street, best_action, icm_pressure)`, calcula taxa de erro por spot, retorna taxa mÃ©dia do jogador, top 5 spots por volume e top 5 spots mais custosos (error_rate > avg + 10%, mÃ­n. 5 decisÃµes).
- **`backend/leaklab/llm_explainer.py`**: `generate_twin_narrative(profile, lang)`, `_call_twin_narrative`, `_template_twin` â€” narrativa em 1Âª pessoa preditiva (2-3 frases) com o spot mais custoso, tendÃªncia revelada e ajuste concreto; suporte PT/EN/ES; fallback determinÃ­stico.
- **`backend/api/app.py`**: `GET /player/strategic-twin?lang=&days=` â€” retorna perfil + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `TwinSpot` e `StrategicTwinProfile`; `metrics.strategicTwin(lang, days)`.
- **`frontend/src/components/hud/StrategicTwinCard.tsx`**: card lateral com taxa mÃ©dia de erro, lista dos 3 spots mais custosos (barra de erro vs linha de mÃ©dia do jogador, delta colorido, volume de decisÃµes) e narrativa LLM. Totalmente i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seÃ§Ã£o `strategicTwin` com aÃ§Ãµes, streets, nÃ­veis de ICM e labels de UI.

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: `"twin"` adicionado ao tipo `SidebarSection`; incluÃ­do no `DEFAULT_LAYOUT.sidebar` ao final da lista â€” merge automÃ¡tico garante apariÃ§Ã£o para usuÃ¡rios existentes.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.strategicTwin(i18n.language)` no carregamento; renderiza `StrategicTwinCard` como card draggable no sidebar.

---

## [v0.76.0] â€” 2026-05-04 â€” Sprint AQ+: Dashboard UX Redesign

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: tipos `MainSection` e `SidebarSection` reescritos para novo modelo de layout. `MainSection` agora Ã© `"quality_row" | "bankroll_row" | "street_row" | "dna_row" | "drill_row" | "insight_row"` (BankrollChart e PlayerDnaCard viram rows sortÃ¡veis). `SidebarSection` reduzido a `"leaks" | "causal_map" | "level"` (3 cards essenciais). `DEFAULT_LAYOUT` atualizado; merge automÃ¡tico migra layouts salvos de usuÃ¡rios existentes.
- **`frontend/src/pages/Index.tsx`**: funÃ§Ã£o `renderMainRow(id)` unifica renderizaÃ§Ã£o das 6 rows do main column, incluindo `insight_row` que exibe `CareerGraphCard` e `CognitiveFailureCard` lado a lado em grid 2-col. `renderSidebarCard(id)` reduzido a 3 cards. `BankrollChart` e `PlayerDnaCard` agora sÃ£o rows sortÃ¡veis (`bankroll_row`, `dna_row`) em vez de injetados entre rows via Ã­ndice. Card `ai_confidence` removido. Import `HudTooltip` removido (era unused apÃ³s remoÃ§Ã£o do card).

### Removed
- Card `ai_confidence` removido do layout â€” nÃ£o havia dados suficientes para preencher de forma significativa.
- `career` e `cognitive_failures` removidos do sidebar â€” movidos para `insight_row` no main column onde ficam lado a lado com espaÃ§o adequado (~700px cada).

---

## [v0.75.0] â€” 2026-05-04 â€” Sprint AQ: Cognitive Failure Mapper

### Added
- **`backend/leaklab/cognitive_mapper.py`**: detector de 5 padrÃµes cognitivo-emocionais sobre sequÃªncias de decisÃµes â€” `revenge_aggression` (agressividade apÃ³s folds corretos), `fear_folding` (folds incorretos apÃ³s blowups), `sunk_cost` (calls ruins em mÃºltiplas streets), `entitlement_tilt` (erros apÃ³s boa sequÃªncia) e `compensation_call` (calls ruins apÃ³s fold correto). Usa janelas deslizantes de 5â€“10 decisÃµes por torneio; retorna padrÃµes ordenados por frequÃªncia com severity (high/medium/low).
- **`backend/database/repositories.py`**: `get_cognitive_failure_report(user_id, days=90)` â€” consulta decisÃµes dos Ãºltimos N dias ordenadas por torneio + id, e chama `analyze_cognitive_failures`.
- **`backend/leaklab/llm_explainer.py`**: `generate_cognitive_narrative(patterns, lang)`, `_call_cognitive_narrative`, `_template_cognitive` â€” narrativa de 2-3 frases com o padrÃ£o dominante, custo em EV e um hÃ¡bito corretivo; suporte multilÃ­ngue (PT/EN/ES); fallback determinÃ­stico.
- **`backend/api/app.py`**: `GET /player/cognitive-failures?lang=&days=` â€” retorna relatÃ³rio + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `CognitivePattern` e `CognitiveFailureData`; `metrics.cognitiveFailures(lang, days)`.
- **`frontend/src/components/hud/CognitiveFailureCard.tsx`**: card com lista de padrÃµes detectados (nome traduzido, severity badge colorido, barra de frequÃªncia, descriÃ§Ã£o), narrativa LLM e estados de loading/empty. Totalmente i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seÃ§Ã£o `cognitiveFailure` com 5 nomes de padrÃ£o, 5 descriÃ§Ãµes, 3 nÃ­veis de severity.

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: adicionado `"cognitive_failures"` ao tipo `SidebarSection`; incluÃ­do no `DEFAULT_LAYOUT` entre `"career"` e `"ai_confidence"`.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.cognitiveFailures(i18n.language)` no carregamento; renderiza `CognitiveFailureCard` como card draggable no sidebar.

---

## [v0.74.0] â€” 2026-05-04 â€” Sprint AP: Strategic Career Graph

### Added
- **`backend/database/repositories.py`**: `get_career_projection(user_id)` â€” regressÃ£o linear pura (sem numpy) sobre histÃ³rico completo de `standard_pct`; calcula slope, projeÃ§Ã£o por torneio, datas estimadas para cada um dos 7 nÃ­veis, leaks bloqueadores (top 3, Ãºltimos 90d), e sÃ©ries de sparkline (histÃ³rico + projeÃ§Ã£o curta).
- **`backend/leaklab/llm_explainer.py`**: `generate_career_narrative(projection, lang)` â€” narrativa de 2-3 frases sobre tendÃªncia, tempo para prÃ³ximo nÃ­vel e leak prioritÃ¡rio; template fallback se LLM indisponÃ­vel; suporte multilÃ­ngue (PT/EN/ES).
- **`backend/api/app.py`**: `GET /player/career?lang=` â€” retorna projeÃ§Ã£o + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `CareerProjection` e `CareerMilestone`; `metrics.career(lang)`.
- **`frontend/src/components/hud/CareerGraphCard.tsx`**: card com sparkline SVG (linha histÃ³rica sÃ³lida + projeÃ§Ã£o tracejada), nÃ­vel atual vs. prÃ³ximo, milestones projetados, leaks bloqueadores e narrativa LLM. Totalmente i18n (PT/EN/ES).
- **`frontend/src/hooks/useDashboardLayout.ts`**: adicionado `"career"` como `SidebarSection`; incluÃ­do no `DEFAULT_LAYOUT` entre `"level"` e `"ai_confidence"`.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.career(i18n.language)` no carregamento; renderiza `CareerGraphCard` como card draggable no sidebar.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seÃ§Ã£o `career` com 15 chaves de traduÃ§Ã£o.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seÃ§Ã£o `career` + chave `nav.career` adicionadas.
- **`frontend/src/pages/Docs.tsx`**: nova seÃ§Ã£o `/docs#career` com tabela de termos e descriÃ§Ã£o da metodologia de projeÃ§Ã£o.

---

## [v0.73.0] â€” 2026-05-04 â€” Bugfix: i18n level names, LeakCausalMap narrative, drag handle

### Fixed
- **`frontend/src/components/hud/LevelCard.tsx`**: nomes de nÃ­vel agora sÃ£o traduzidos (PT/EN/ES) via chaves `level.names.*` no namespace `dashboard`; mapeamento `LEVEL_SLUG` converte strings PT do backend em slugs canÃ´nicos para cores, Ã­cones e i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: adicionada seÃ§Ã£o `level.names` com os 7 nomes de nÃ­vel em cada idioma.
- **`backend/leaklab/llm_explainer.py`**: `explain_leak_causality` e `_call_llm_causality` aceitam `lang` param â€” o prompt agora instrui o LLM a responder no idioma correto (PT/EN/ES); `max_tokens` aumentado de 150 para 280 para evitar truncamento da narrativa.
- **`backend/database/repositories.py`**: `get_leak_graph_data` aceita `lang` param e o passa para o LLM.
- **`backend/api/app.py`**: endpoint `GET /player/leak-graph` agora lÃª `?lang=` da query string.
- **`frontend/src/lib/api.ts`**: `metrics.leakGraph(days, lang)` passa idioma para o endpoint.
- **`frontend/src/pages/Index.tsx`**: `leakGraph` carregado com `i18n.language` para narrativa no idioma correto.
- **`frontend/src/components/hud/DraggableCard.tsx`**: grip handle movido para `left-3` (era `right-3`) â€” evita sobreposiÃ§Ã£o com conteÃºdo como "90d" no canto direito do header.

---

## [v0.72.0] â€” 2026-05-04 â€” Sprint i18n: cobertura completa de novos componentes

### Changed
- **`frontend/src/pages/Docs.tsx`**: substituÃ­dos todos os placeholders por chaves i18n corretas â€” linhas da Ghost Table usam `t("ghost.result_hit/miss/mastery")`, termo de coaching usa `t("coaching.term_override")`, nomes de nÃ­vel usam `t("gamification.level_*")`; removida importaÃ§Ã£o `tc` desnecessÃ¡ria.
- **`frontend/src/components/hud/LeakCausalMap.tsx`**: adicionado `useTranslation("dashboard")`; substituÃ­dos todos os 5 textos hardcoded por chaves `t("leakCausalMap.*")` â€” tÃ­tulo, aria-label, "Co-ocorre com", "limpar seleÃ§Ã£o", labels de severidade, "espessura = correlaÃ§Ã£o".
- **`frontend/src/components/hud/HudHeader.tsx`**: tÃ­tulo do drawer de chat do coach agora usa `t("coachMessages")` (fallback quando `coach_username` nÃ£o estÃ¡ disponÃ­vel); `title` do botÃ£o badge tambÃ©m i18n.
- **`frontend/src/components/hud/DraggableCard.tsx`**: tooltip "Arrastar para reordenar" agora usa `tc("actions.dragToReorder")`.
- **`frontend/src/pages/Index.tsx`**: botÃ£o "Restaurar padrÃ£o" agora usa `tc("actions.resetLayout")`.

---

## [v0.71.0] â€” 2026-05-04 â€” Sprint AG: FEAT-12 PÃ¡gina de DocumentaÃ§Ã£o

### Added
- **`frontend/src/pages/Docs.tsx`**: pÃ¡gina `/docs` estilo wiki com 8 seÃ§Ãµes â€” Sistema de Scoring, Indicadores, Fases de M-Ratio, Decision DNA, Ghost Table/Drills, Comparativo de Torneios, Coaching, GamificaÃ§Ã£o. Sidebar fixa com navegaÃ§Ã£o Ã¢ncora e active highlight por IntersectionObserver. Tabelas com valores precisos extraÃ­dos do cÃ³digo (thresholds reais do engine, XP amounts, nÃ­veis, conquistas).
- **`frontend/src/App.tsx`**: rota `/docs` pÃºblica (AuthRoute).
- **`frontend/src/pages/Index.tsx`**: link "Docs" no footer agora aponta para `/docs`.

---

## [v0.70.0] â€” 2026-05-04 â€” Sprint AL: UX-017 Dashboard PersonalizÃ¡vel

### Added
- **`backend/database/schema.py`**: coluna `dashboard_layout TEXT` na tabela `users` (SQLite + PostgreSQL).
- **`backend/database/repositories.py`**: `get_user_preferences(user_id)` e `save_user_preferences(user_id, layout)`.
- **`backend/api/app.py`**: `GET /player/preferences` e `PATCH /player/preferences`.
- **`frontend/package.json`**: dependÃªncias `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`.
- **`frontend/src/hooks/useDashboardLayout.ts`**: hook que carrega layout do servidor, persiste com debounce de 800ms e expÃµe `updateMain`, `updateSidebar`, `reset`.
- **`frontend/src/components/hud/DraggableCard.tsx`**: wrapper sortable com drag handle (â ¿) visÃ­vel ao hover no canto superior direito.
- **`frontend/src/lib/api.ts`**: interface `DashboardLayoutData`; objeto `preferences` com `get()` e `save()`.

### Changed
- **`frontend/src/pages/Index.tsx`**: coluna principal (3 linhas: quality_row, street_row, drill_row) e sidebar (leaks, causal_map, level, ai_confidence) agora sÃ£o sortÃ¡veis via `@dnd-kit`. BankrollChart e PlayerDnaCard permanecem fixos. BotÃ£o "Restaurar padrÃ£o" no header do dashboard. Layout sincronizado entre devices via backend.

---

## [v0.69.0] â€” 2026-05-04 â€” Sprint AN: UX-019 Coach Chat Drawer

### Changed
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: adicionado prop `drawer` â€” quando `true`, renderiza como painel full-height (sem header colapsÃ¡vel, `flex-1 min-h-0`) para uso dentro do drawer flutuante.
- **`frontend/src/components/hud/HudHeader.tsx`**: Ã­cone de mensagens no header agora Ã© um botÃ£o que abre/fecha o drawer de chat em vez de navegar para `/coach`. Badge vermelho exibido somente quando hÃ¡ mensagens nÃ£o lidas (badge oculto quando zero). Drawer renderizado como `fixed inset-y-0 right-0 w-full sm:w-96` com overlay semi-transparente; fecha com clique no overlay ou tecla Escape.
- **`frontend/src/pages/AICoach.tsx`**: `CoachMessagesPanel` removido da sidebar â€” chat agora estÃ¡ exclusivamente no drawer global do header.

---

## [v0.68.0] â€” 2026-05-03 â€” Sprint AM: UX-018 Tabela de Alunos com Busca e Filtros

### Changed
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: `AlunosTab` reescrita como tabela responsiva com busca por nome, filtro de status (Todos/Ativos/Inativos), ordenaÃ§Ã£o por coluna (Aluno, Torneios, Ãšltimo Import, TendÃªncia) e paginaÃ§Ã£o client-side (25 por pÃ¡gina). Colunas responsivas: Torneios oculto em mobile, Ãšltimo Import oculto abaixo de md, TendÃªncia oculta abaixo de lg. Ãcone de tendÃªncia colorido (verdeâ†‘/vermelhoâ†“/cinzaâ†’). Badge Ativo/Inativo baseado em import nos Ãºltimos 30 dias. Contador "Xâ€“Y de Z" e botÃµes Anterior/PrÃ³ximo.

---

## [v0.67.0] â€” 2026-05-04 â€” Sprint AJ+AK: UX-015 Coach Inbox + UX-016 Student Badge

### Added
- **`backend/database/repositories.py`**: `get_coach_inbox(coach_id)` â€” agrega conversas por aluno com `last_message_body`, `last_message_at` e `unread_count`.
- **`backend/api/app.py`**: `GET /coach/messages/inbox` â€” retorna threads ordenadas por `last_message_at DESC`.
- **`frontend/src/lib/api.ts`**: interface `InboxThread`; `coachDashboard.inbox()`.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: aba "Mensagens" com inbox â€” avatar inicial, nome do aluno, prÃ©via da Ãºltima mensagem, timestamp relativo e badge vermelho de nÃ£o lidas. Badge de nÃ£o lidas total no botÃ£o da aba (polling 60s).

### Changed
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: mensagens nÃ£o lidas do coach recebem highlight (`border-primary/30 bg-primary/5`). Badge no header da aba desaparece imediatamente ao abrir o painel via `invalidateQueries`.

### Backlog
- **Sprint AM (UX-018)** adicionado: listagem de alunos com tabela, busca, filtros e paginaÃ§Ã£o.

---

## [v0.66.0] â€” 2026-05-03 â€” Sprint AI: BACK-019 Perfil DemogrÃ¡fico do UsuÃ¡rio

### Added
- **`backend/database/schema.py`**: 8 novas colunas em `users` â€” `birth_year`, `country`, `state_province`, `city`, `poker_experience_years`, `main_game_type`, `usual_buyin_range`, `profile_completed_at` (migraÃ§Ãµes Postgres e SQLite).
- **`backend/database/repositories.py`**: `get_user_demographics`, `update_user_demographics` (marca `profile_completed_at` quando campos core preenchidos), `get_demographics_aggregate` (dados anonimizados para o admin).
- **`backend/api/app.py`**: `GET /player/profile`, `PATCH /player/profile`, `GET /admin/demographics`; campo `profile_completed_at` adicionado Ã  resposta do `/auth/me`.
- **`frontend/src/lib/api.ts`**: interface `DemographicProfile`; objeto `profile` com `get()` e `update()`; `adminDashboard.demographics()`.
- **`frontend/src/components/hud/ProfileCompletionCard.tsx`**: card colapsÃ¡vel no dashboard â€” exibido quando perfil nÃ£o estÃ¡ completo; formulÃ¡rio com todos os campos demogrÃ¡ficos; barra de progresso; nota LGPD; botÃ£o "NÃ£o mostrar mais" persiste em localStorage.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: painel "Perfis DemogrÃ¡ficos" na aba VisÃ£o Geral â€” taxa de completion, top paÃ­ses, distribuiÃ§Ã£o por tipo de jogo e faixa de buy-in.

### Changed
- **`frontend/src/pages/Index.tsx`**: `ProfileCompletionCard` inserido entre `DailyFocusCard` e `SessionGoalPanel`.
- **`backend/api/app.py`**: `/auth/me` passa a retornar `profile_completed_at`.

---

## [v0.65.0] â€” 2026-05-03 â€” Sprint AH: BACK-018 Coach Application Flow

### Added
- **`backend/database/schema.py`**: tabela `coach_applications` (user_id, instagram_handle, bio, specialties, experience_years, biggest_results, status pending/approved/rejected, admin_note, reviewed_at).
- **`backend/database/repositories.py`**: `create_coach_application`, `get_coach_applications`, `approve_coach_application`, `reject_coach_application`, helper `_now()`.
- **`backend/leaklab/email_digest.py`**: helper `send_transactional_email(to_email, subject, html_body)` reutilizando a infra SMTP do digest.
- **`backend/api/app.py`**: `POST /auth/coach-apply` (pÃºblico, rate-limited 5/min) â€” cria usuÃ¡rio com role `coach_pending` + registro de candidatura. `GET /admin/coach-applications` + `POST /admin/coach-applications/<id>/approve` + `POST /admin/coach-applications/<id>/reject` â€” gestÃ£o pelo admin com envio de e-mail automÃ¡tico.
- **`frontend/src/pages/CoachApply.tsx`**: formulÃ¡rio pÃºblico de candidatura (username, @instagram, email, senha, bio â‰¥30 chars, especialidades, anos de experiÃªncia, maiores resultados) com estado de confirmaÃ§Ã£o.
- **`frontend/src/lib/api.ts`**: interface `CoachApplication`, mÃ©todos `adminDashboard.coachApplications`, `approveApplication`, `rejectApplication`; `coachApplyApi.apply`.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: aba "Candidaturas" com filtro por status, linhas expansÃ­veis (bio/especialidades/resultados), botÃµes aprovar/rejeitar com nota opcional.
- **`frontend/src/App.tsx`**: rota pÃºblica `/coach-apply`.

### Changed
- **`backend/api/app.py`**: `POST /auth/register` com `role: coach` retorna 400 â€” coaches devem usar `/auth/coach-apply`.
- **`backend/api/app.py`**: `POST /auth/login` com role `coach_pending` retorna 403 com `code: 'coach_pending'`.
- **`frontend/src/pages/Login.tsx`**: botÃ£o "Coach" na aba de registro redireciona para `/coach-apply`; mensagem de erro `coach_pending` tratada com texto especÃ­fico.

### Fixed
- **`frontend/src/pages/coach/StudentDetail.tsx`**: Feed de Atividade exibia `standard_pct` multiplicado por 100 (ex.: 83% aparecia como 8300%). Removida duplicaÃ§Ã£o de `* 100`.

---

## [v0.64.0] â€” 2026-05-03 â€” Sprint AF: UX-014 StudentDetail + CoachDashboard wide layout

### Changed
- **`frontend/src/pages/coach/StudentDetail.tsx`**: container `max-w-5xl` â†’ `max-w-[1440px] px-4 md:px-8` (consistente com o dashboard principal). `OverviewTab` reestruturado para grid `lg:grid-cols-12` â€” coluna principal (8-col) com LevelCard + HUD stats + evolution chart + comparativo; aside (4-col) com Principais Leaks + Performance por Street + Performance por PosiÃ§Ã£o. Evolution chart aumentado de 200px para 220px de altura.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: mesma atualizaÃ§Ã£o de container `max-w-5xl` â†’ `max-w-[1440px] px-4 md:px-8`.

---

## [v0.63.0] â€” 2026-05-03 â€” Sprint AF-fix: Dashboard layout holes

### Fixed
- **`frontend/src/pages/Index.tsx`**: GhostDrillCard, PressureProfileCard e IcmBreakdown movidos para dentro da coluna principal (8-col) como subgrid `md:grid-cols-3` abaixo do PlayerDnaCard â€” elimina o "buraco" visual causado pela quebra de ritmo entre o grid 8+4 e o antigo row 4-col. AI Confidence card retorna para o aside, mantendo o painel lateral com conteÃºdo atÃ© o final.

---

## [v0.62.0] â€” 2026-05-03 â€” Sprint AF: Dashboard card reposition

### Changed
- **`frontend/src/pages/Index.tsx`**: GhostDrillCard, PressureProfileCard, IcmBreakdown e AI Confidence movidos da aside (4 col) para uma nova row full-width abaixo do grid principal, em `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`. Aside agora contÃ©m apenas LeaksPanel, LeakCausalMap e LevelCard â€” os cards analÃ­ticos mais crÃ­ticos.

---

## [v0.61.0] â€” 2026-05-03 â€” Sprint AE: UX-013 "JAM" â†’ "All In" na camada de display

### Added
- **`frontend/src/lib/utils.ts`**: funÃ§Ã£o `formatAction(a: string)` â€” mapeia `"jam"` â†’ `"All In"`, capitaliza demais aÃ§Ãµes. Identificadores internos do backend permanecem inalterados.

### Changed
- **`frontend/src/pages/GhostTable.tsx`**: `.toUpperCase()` direto nos valores de aÃ§Ã£o substituÃ­do por `formatAction(...).toUpperCase()` em 4 locais (originalMistake, bestAction subtitle, yourAction card, bestAction card).
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: `{d.action_taken}` e `{d.best_action}` na tabela de decisÃµes encapsulados com `formatAction()`.
- **`frontend/src/pages/coach/StudentDetail.tsx`**: mesma correÃ§Ã£o nas duas tabelas de decisÃµes e no card de detalhe (6 ocorrÃªncias).
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: tooltip de Flop Bet atualizado de "bet/raise/jam" para "bet/raise/all-in".

---

## [v0.60.0] â€” 2026-05-03 â€” Sprint AD: UX-012 Remove recent tournaments from dashboard

### Removed
- **`frontend/src/pages/Index.tsx`**: `RecentTournamentsTable` removido do dashboard â€” o menu /tournaments jÃ¡ serve essa funÃ§Ã£o. O estado `tourns` e o fetch de `tournaments.list()` permanecem para os cÃ¡lculos de KPI (ROI, ITM, Total Eventos, Total MÃ£os).

---

## [v0.59.0] â€” 2026-05-03 â€” Sprint AC: UX-011 Dashboard title/subtitle

### Changed
- **`frontend/src/i18n/locales/pt-BR|en|es/dashboard.json`**: `title` e `titleDefault` passam de "{{name}} â€” Centro de Comando / Command Center / Centro de Mando" para simplesmente `"Dashboard"` nos trÃªs idiomas. Subtitle encurtado para caber em uma linha sem quebra em viewports comuns.
- **`frontend/src/pages/Index.tsx`**: `<h1>` simplificado â€” removida interpolaÃ§Ã£o `{name}` e o fallback `titleDefault`; ambas as keys agora retornam `"Dashboard"`.

---

## [v0.58.0] â€” 2026-05-03 â€” Sprint AB: UX-010 Bankroll period filters

### Fixed
- **`frontend/src/components/hud/BankrollChart.tsx`**: filtros de perÃ­odo (1M/3M/1Y/Tudo) agora funcionam â€” componente passou a ser self-contained, gerencia seu prÃ³prio estado de perÃ­odo e busca os dados via `useQuery` com o nÃºmero correto de dias (30/90/365/3650). BotÃ£o ativo destacado corretamente. Spinner overlay durante refetch. Prop `evolution` removida (o componente nÃ£o depende mais do parent para dados).
- **`frontend/src/pages/Index.tsx`**: `<BankrollChart>` sem prop â€” componente busca seus prÃ³prios dados.
- **`backend/requirements.txt`**: `python-dotenv==1.0.1` adicionado â€” estava faltando, causando `ModuleNotFoundError: No module named 'dotenv'` no boot do Gunicorn no Render.

---

## [v0.57.0] â€” 2026-05-03 â€” Sprint AA: INFRA-001 Build + display bugs

### Fixed
- **`vercel.json`**: substituÃ­do config quebrado `@vercel/static-build` com rotas `"/frontend/$1"` pelo formato moderno â€” `buildCommand` + `outputDirectory` + `rewrites` apontando tudo para `/index.html`; corrige roteamento do React Router em produÃ§Ã£o.
- **`backend/leaklab/email_digest.py`**: variÃ¡vel de ambiente do token de unsubscribe corrigida de `JWT_SECRET_KEY` para `LEAKLAB_SECRET` (alinhado com `database/auth.py` e `render.yaml`).
- **`frontend/src/pages/AICoach.tsx`**: `standard_pct` no painel de contexto exibia valor multiplicado por 100 duas vezes (ex: 85.18 â†’ 8518%). O endpoint retorna jÃ¡ em % â€” removida a multiplicaÃ§Ã£o `* 100` incorreta.

---

## [v0.56.0] â€” 2026-05-03 â€” Sprint Z: UX-009 Tournament date display

### Changed
- **`frontend/src/pages/Tournaments.tsx`**: `formatDate` agora exibe ano de 2 dÃ­gitos (`DD/MM/YY`) quando o torneio Ã© de ano anterior ao atual â€” torneios do ano corrente continuam como `DD/MM`. Novo componente `TournamentDate` distingue visualmente `played_at` (data real do torneio) de `imported_at` (data de importaÃ§Ã£o): quando `played_at` nÃ£o estÃ¡ disponÃ­vel, exibe a data de importaÃ§Ã£o com label "importado" em tom reduzido. Aplicado na tabela desktop e nos cards mobile.

---

## [v0.55.0] â€” 2026-05-03 â€” Sprint Y: UX-008 Coaches Directory mobile + terminologia

### Changed
- **`frontend/src/pages/CoachesDirectory.tsx`**: layout mobile corrigido â€” filtros movidos para painel colapsÃ¡vel com toggle (botÃ£o mostra contagem de filtros ativos); sidebar visÃ­vel apenas em `lg+`; grid muda de `md:grid-cols-2` para `sm:grid-cols-2` para usar melhor o espaÃ§o; `min-w-0` na coluna do grid evita overflow.
- **`frontend/src/pages/Login.tsx`**: seletor de role na tela de registro: "Professor" â†’ "Coach".
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: tÃ­tulo "Dashboard do Professor" â†’ "Dashboard do Coach".
- **`frontend/src/i18n/locales/pt-BR/dashboard.json`**: banner de vÃ­nculo: "Tem um professor?" â†’ "Tem um coach?".
- **`frontend/src/components/hud/AcceptCoachModal.tsx`**: 3 ocorrÃªncias de "professor" substituÃ­das por "coach" (tÃ­tulo do modal, mensagem de instruÃ§Ã£o, confirmaÃ§Ã£o de sucesso).

---

## [v0.54.0] â€” 2026-05-03 â€” Sprint W: FEAT-11 Weekly Digest Email

### Added
- **`backend/leaklab/email_digest.py`**: mÃ³dulo de digest semanal â€” `build_digest_data` (coleta mÃ©tricas dos Ãºltimos 7 dias: standard%, EV loss, drill atrasado, precisÃ£o), `build_digest_html` (template dark responsivo com EV bar visual), `send_digest_email` (SMTP via smtplib nativo com STARTTLS), `run_weekly_digest` (itera inscritos e envia). Sem dependÃªncias extras alÃ©m da stdlib.
- **`backend/database/schema.py`**: coluna `digest_subscribed INTEGER NOT NULL DEFAULT 0` na tabela `users` (SQLite + Postgres migration).
- **`backend/database/repositories.py`**: `get_digest_subscribers` (usuÃ¡rios com `digest_subscribed=1` e `last_login` nos Ãºltimos 30 dias), `update_digest_subscription`.
- **`backend/api/app.py`**: `POST /player/digest/subscribe`, `POST /player/digest/unsubscribe` (autenticado), `GET /player/digest/unsubscribe` (link do email com token HMAC), `POST /admin/send-digest`; campo `digest_subscribed` incluÃ­do na resposta de `/auth/me`.
- **`frontend/src/lib/api.ts`**: campo `digest_subscribed` em `UserProfile`; mÃ³dulo `digest` com `subscribe()` e `unsubscribe()`.
- **`frontend/src/pages/Index.tsx`**: banner de opt-in contextual â€” visÃ­vel para players com dados que ainda nÃ£o ativaram o digest; dispensÃ¡vel pelo X; botÃ£o "Ativar" chama `digest.subscribe()` e atualiza o perfil via `refreshUser()`.

---

## [v0.53.0] â€” 2026-05-03 â€” Sprint V: FEAT-09 Coach Templates + FEAT-10 Coach Messaging

### Added
- **`backend/database/schema.py`**: tabela `coach_plan_templates` (id, coach_id, name, target_archetype, cards_json) e `coach_messages` (id, coach_id, student_id, body, sender_role, decision_id, read_at) â€” SQLite + Postgres.
- **`backend/database/repositories.py`**: `get_coach_templates`, `create_coach_template`, `delete_coach_template`; `send_coach_message`, `get_coach_messages`, `mark_messages_read`, `get_unread_message_count`.
- **`backend/api/app.py`**: endpoints `GET/POST /coach/templates`, `DELETE /coach/templates/<id>`; `GET/POST /coach/student/<id>/messages`; `GET/POST /player/coach/messages`, `GET /player/messages/unread`.
- **`frontend/src/lib/api.ts`**: interfaces `CoachTemplate`, `CoachMessage`; mÃ©todos em `coachDashboard` (getTemplates, createTemplate, deleteTemplate, getMessages, sendMessage); mÃ³dulo `playerMessages` (list, send, unreadCount).
- **`frontend/src/pages/coach/StudentDetail.tsx`**: aba "Mensagens" com chat bidirecional em tempo real (polling 15s), badge de nÃ£o lidas na aba, botÃ£o "Salvar como template" nos cards substituÃ­dos do plano de estudos.
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: painel colapsÃ¡vel de chat para o player na pÃ¡gina do AI Coach â€” mostra conversa com coach humano vinculado, badge de nÃ£o lidas, envio via Enter.
- **`frontend/src/pages/AICoach.tsx`**: `CoachMessagesPanel` integrado na sidebar, visÃ­vel apenas quando `user.coach_id` estÃ¡ presente.
- **`frontend/src/components/hud/HudHeader.tsx`**: badge de nÃ£o lidas no header (Ã­cone `MessageSquare` com contador) para players com coach vinculado â€” polling 60s, link para `/coach`.

---

## [v0.52.0] â€” 2026-05-03 â€” Sprint U: FEAT-08 Session Goals + AI Review

### Added
- **`backend/database/schema.py`**: tabela `session_goals` (SQLite + Postgres) â€” `id`, `user_id`, `goal_leak_spot`, `target_standard_pct`, `notes`, `tournament_id` (nullable), `llm_review`, `created_at`, `linked_at`.
- **`backend/database/repositories.py`**: `create_session_goal`, `link_session_goal`, `get_pending_session_goal`, `get_session_goal_by_tournament`, `save_session_review`.
- **`backend/leaklab/llm_explainer.py`**: `generate_session_review(goal, tournament)` â€” Claude Haiku (~300 tokens) compara meta prÃ©-sessÃ£o com resultado real; 3 frases: atingiu/nÃ£o atingiu meta, ponto tÃ©cnico relevante, recomendaÃ§Ã£o para prÃ³xima sessÃ£o. Fallback `_template_session_review` determinÃ­stico.
- **`backend/api/app.py`**: endpoints `POST /player/session-goals`, `GET /player/session-goals/pending`, `POST /player/session-goals/<id>/link`, `GET /player/session-review/<tournament_id>` (gera e persiste review on-demand).
- **`frontend/src/lib/api.ts`**: interfaces `SessionGoal`, `SessionReviewResponse`; mÃ©todos `metrics.createSessionGoal`, `metrics.pendingSessionGoal`, `metrics.linkSessionGoal`, `metrics.sessionReview`.
- **`frontend/src/components/hud/UploadQueue.tsx`**: `SessionGoalPanel` exportado â€” painel colapsÃ¡vel com campos spot de foco, meta de standard% e anotaÃ§Ã£o livre; persiste goal ID em `sessionStorage`; hook `useUploadQueue` lÃª `ll_pending_goal` do `sessionStorage` apÃ³s upload e chama `metrics.linkSessionGoal` automaticamente.
- **`frontend/src/pages/Index.tsx`**: `SessionGoalPanel` integrado ao dashboard (visÃ­vel apenas para players).
- **`frontend/src/pages/TournamentDetail.tsx`**: card "Review da SessÃ£o" exibido apÃ³s narrativa quando hÃ¡ meta vinculada â€” mostra spot de foco, meta vs resultado real com indicador âœ“/âœ—, review gerado por IA e anotaÃ§Ã£o livre do jogador.

---

## [v0.51.0] â€” 2026-05-03 â€” Sprint T: FEAT-07 Coach Effectiveness Metrics

### Added
- **`backend/database/repositories.py`**: `get_coach_effectiveness_report(coach_id)` â€” itera todos os alunos com baseline, chama `get_baseline_comparison` por aluno, calcula delta de `standard_pct`, melhora mediana, % com melhora positiva e badge pÃºblico (visÃ­vel com â‰¥3 alunos e mediana positiva).
- **`backend/api/app.py`**: endpoint `GET /coach/effectiveness` (autenticado como coach). Perfil pÃºblico `GET /coaches/<id>` passa a incluir `effectiveness_badge` e `effectiveness_median_delta`.
- **`frontend/src/lib/api.ts`**: interfaces `EffectivenessStudent`, `EffectivenessSummary`, `CoachEffectivenessReport`; mÃ³dulo `coachEffectiveness` com mÃ©todo `report()`.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: aba "Efetividade" com 3 KPI cards (alunos analisados, melhora mediana, % com melhora), preview do badge pÃºblico com indicaÃ§Ã£o "visÃ­vel no perfil pÃºblico", tabela por aluno com before/after `standard_pct`, delta colorido e leaks corrigidos.
- **`frontend/src/pages/PublicCoachProfile.tsx`**: badge "Alunos melhoram +Xpp em standard_pct" exibido na seÃ§Ã£o de badges do perfil pÃºblico quando disponÃ­vel.

---

## [v0.50.0] â€” 2026-05-03 â€” Sprint S: FEAT-06 Leak Causal Map

### Added
- **`backend/leaklab/leak_causal_graph.py`**: `build_leak_graph(rows)` â€” analisa co-ocorrÃªncia de leaks entre torneios, calcula correlaÃ§Ã£o de Jaccard por par (threshold 35%), retorna nÃ³s com `severity` (critical/moderate/minor por avg_score) e arestas ordenadas por correlaÃ§Ã£o; label compacto (`PF Fold`, `FL Bet`, etc.); nÃ³s incluem `degree` (nÃºmero de conexÃµes).
- **`backend/leaklab/llm_explainer.py`**: `explain_leak_causality(edges, hero)` â€” 1 chamada Claude Haiku (~150 tokens) gerando 2-3 frases de diagnÃ³stico causal para os 3 pares mais correlacionados; cache em memÃ³ria por combinaÃ§Ã£o de pares; fallback `_template_causality()` determinÃ­stico.
- **`backend/database/repositories.py`**: `get_leak_graph_data(user_id, days)` â€” busca todas as decisÃµes com mistake do usuÃ¡rio no perÃ­odo, chama `build_leak_graph` e `explain_leak_causality`, retorna `{nodes, edges, narrative}`.
- **`backend/api/app.py`**: endpoint `GET /player/leak-graph?days=90`.
- **`frontend/src/lib/api.ts`**: interfaces `LeakGraphNode`, `LeakGraphEdge`, `LeakGraphResponse`; mÃ©todo `metrics.leakGraph(days)`.
- **`frontend/src/components/hud/LeakCausalMap.tsx`**: card com grafo SVG circular â€” nÃ³s coloridos por severidade (vermelho/Ã¢mbar/verde), arestas com espessura e opacidade proporcionais Ã  correlaÃ§Ã£o; interaÃ§Ã£o: clique no nÃ³ destaca suas conexÃµes e exibe detalhe com lista de co-ocorrÃªncias; narrativa LLM abaixo do grafo; legenda de cores.
- **`frontend/src/pages/Index.tsx`**: `LeakCausalMap` inserido apÃ³s `LeaksPanel` quando hÃ¡ â‰¥ 3 nÃ³s; `metrics.leakGraph(90)` carregado no mount.

---

## [v0.49.0] â€” 2026-05-03 â€” Sprint R: FEAT-05 SRS Adaptativo nos Drills

### Added
- **`backend/database/schema.py`**: colunas `next_drill_at TEXT` e `srs_interval_days INTEGER DEFAULT 3` em `drill_sessions` (Postgres + SQLite migrations).
- **`backend/database/repositories.py`**: `save_drill_session` reescrito com lÃ³gica SRS â€” acerto dobra o intervalo (`3d â†’ 7d â†’ 14d â†’ 28d â†’ 60d`, cap em 60), erro reseta para 3 dias; calcula `next_drill_at = now + interval` e persiste ambos os campos. `get_drill_spots` reescrito â€” substitui filtro de `drilled_at >= 7 days` por LEFT JOIN na sessÃ£o mais recente por decisÃ£o, filtra por `next_drill_at IS NULL OR next_drill_at <= now`, ordena por mais atrasado primeiro; calcula `days_overdue` em Python (compatÃ­vel SQLite + Postgres).
- **`backend/api/app.py`**: endpoint `POST /player/spots/drill/submit` passa a retornar `next_drill_at` e `srs_interval_days`.
- **`frontend/src/lib/api.ts`**: `DrillSpot` com campos `next_drill_at`, `srs_interval_days`, `days_overdue`; `DrillSubmitResult` com `next_drill_at` e `srs_interval_days`.
- **`frontend/src/pages/GhostTable.tsx`**: badge "prÃ³xima revisÃ£o em X dias" (verde=acerto, amarelo=reset) no card de resultado apÃ³s cada drill; badge de dias de atraso discreto (vermelho/amarelo) na barra de progresso do spot ativo.
- **`frontend/src/components/hud/GhostDrillCard.tsx`**: prop `pendingSpots` opcional â€” exibe contador "N atrasados" com Ã­cone Clock no header do card quando hÃ¡ spots vencidos.
- **`frontend/src/pages/Index.tsx`**: carrega `drill.spots({ limit: 20 })` no mount e passa `pendingSpots` para `GhostDrillCard`.

---

## [v0.48.0] â€” 2026-05-03 â€” Sprint Q: FEAT-02 Daily Focus + FEAT-03 XP Server-Side

### Added
- **`backend/database/schema.py`**: migraÃ§Ãµes para `xp_total INT DEFAULT 0`, `xp_streak INT DEFAULT 0`, `xp_last_activity DATE`, `daily_focus_done_at DATE` na tabela `users`; nova tabela `achievements` (`user_id`, `achievement_id`, `unlocked_at`).
- **`backend/database/repositories.py`**: `get_daily_focus(user_id)` â€” lÃ³gica determinÃ­stica (zero LLM) que combina top EV-loss leak, drill com cooldown expirado e torneio nÃ£o revisado; retorna `{primary, secondary[], valid_until, completed, streak}`. `mark_daily_focus_done(user_id)` â€” persiste data de conclusÃ£o. `add_xp(user_id, event_type, amount?)` â€” streak server-side: +1 se Ãºltimo XP foi ontem, reset se mais antigo; checa conquistas automaticamente via `_check_and_grant_achievements()`. `get_xp_status(user_id)`, `get_achievements(user_id)`. `_XP_AMOUNTS` (`tournament_imported=50`, `exercise_correct=10`, `drill_completed=25`, `drill_mastered=100`). 5 conquistas: `first_tournament`, `decisions_100`, `first_drill`, `streak_7`, `tournaments_10`.
- **`backend/api/app.py`**: 5 novos endpoints â€” `GET /player/daily-focus`, `POST /player/daily-focus/complete`, `GET /player/xp`, `POST /player/xp`, `GET /player/achievements`.
- **`frontend/src/components/hud/DailyFocusCard.tsx`**: card de foco diÃ¡rio â€” exibe aÃ§Ã£o primÃ¡ria e 2 secundÃ¡rias com link direto; timer countdown atÃ© meia-noite; estado "concluÃ­do" com streak de dias; usa `useQuery` + `useMutation` via React Query.
- **`frontend/src/lib/api.ts`**: interfaces `DailyFocusData`, `DailyFocusAction`, `XpStatus`, `Achievement`; mÃ©todos `metrics.dailyFocus()`, `metrics.completeDailyFocus()`, `metrics.xpStatus()`, `metrics.addXp(event_type)`, `metrics.achievements()`.
- **`frontend/src/pages/Index.tsx`**: `DailyFocusCard` inserido acima da seÃ§Ã£o de KPIs (visÃ­vel apenas quando hÃ¡ torneios importados).
- **`frontend/src/pages/StudyPlan.tsx`**: `metrics.addXp("exercise_correct")` disparado a cada resposta correta em exercÃ­cio (fire-and-forget).
- **`frontend/src/components/hud/UploadQueue.tsx`**: `metrics.addXp("tournament_imported")` disparado apÃ³s upload bem-sucedido de torneio.

---

## [v0.47.0] â€” 2026-05-03 â€” Sprint P: FEAT-04 RelatÃ³rio PDF Premium

### Added
- **`backend/leaklab/report_generator.py`**: redesign completo â€” `build_html_report(t, decisions, phases, hero)` gera template HTML premium com Inter/JetBrains Mono (Google Fonts), paleta dark profissional, grÃ¡ficos CSS puros (barras, indicadores de score coloridos por threshold). SeÃ§Ãµes: capa com hero + torneio + meta pills, KPI row (Standard%, Avg Score, Clear Mistakes%, DecisÃµes), Quality Distribution com barras + referÃªncia MTT saudÃ¡vel, Phase Breakdown (Deep/Mid/Short Stack/Push/Fold), Top 5 Leaks com barra proporcional e score colorido, Performance por ICM Pressure, Top 10 DecisÃµes CrÃ­ticas com label badges.
- **`generate_pdf_bytes(html)`**: converte HTML para PDF via WeasyPrint; levanta `ImportError` se a lib nÃ£o estiver disponÃ­vel â€” o endpoint faz fallback automÃ¡tico para download HTML.
- **`backend/Dockerfile`**: adicionadas dependÃªncias de sistema para WeasyPrint â€” `libpango`, `libcairo2`, `libgdk-pixbuf2.0-0`, `libpangocairo`, `libffi-dev`, `fonts-liberation`.
- **`render.yaml`**: migrado de `runtime: python` para `runtime: docker` (necessÃ¡rio para instalar as dependÃªncias de sistema do WeasyPrint no Render).
- **`backend/requirements.txt`**: `weasyprint==62.3`.
- **`backend/api/app.py`**: endpoint `GET /history/tournament/<id>/report.pdf` â€” retorna PDF (`application/pdf`) ou HTML como fallback se WeasyPrint nÃ£o disponÃ­vel; `Content-Disposition: attachment`.
- **`frontend/src/lib/api.ts`**: `tournaments.downloadReport(tournamentId)` â€” fetch binÃ¡rio com auth header, cria blob URL e dispara download automaticamente.
- **`frontend/src/pages/TournamentDetail.tsx`**: botÃ£o "PDF" (Ã­cone `FileDown`) ao lado do botÃ£o Replay; estado `pdfDownloading` com spinner enquanto gera.

### Changed
- **`backend/leaklab/report_generator.py`**: `generate_report()` (legacy) mantida e intacta para compatibilidade com callers existentes.

---

## [v0.46.0] â€” 2026-05-03 â€” Sprint O: FEAT-01 Comparativo de Torneios

### Added
- **`backend/database/repositories.py`**: `get_tournaments_comparison(user_id, ids)` â€” agrega por torneio: `standard_pct`, `avg_score`, `clear_pct`, hands/decisions count, profit, buy_in, place, phase breakdown e top 5 leaks; `_compute_comparison_leaks(decisions)` â€” calcula mÃ©dia de score por spot para o ranking de leaks.
- **`backend/leaklab/llm_explainer.py`**: `generate_comparison_narrative(items)` â€” narrativa comparativa de 2 frases via Claude Haiku (max 100 tokens); cache por `cmp_{id1}_{id2}...`; fallback `_template_comparison()` calcula delta de `standard_pct` entre primeiro e Ãºltimo torneio.
- **`backend/api/app.py`**: endpoint `GET /history/tournaments/compare?ids=A,B,C` â€” valida 2â€“4 IDs, retorna `{items: TournamentComparison[], narrative}`.
- **`frontend/src/lib/api.ts`**: interface `TournamentComparison` e mÃ©todo `tournaments.compare(ids)`.
- **`frontend/src/pages/TournamentCompare.tsx`**: pÃ¡gina de comparativo lado a lado â€” componentes `Delta` (trend Â±) e `QualityBar` (barra colorida por threshold); seÃ§Ãµes: narrativa LLM, cards de cabeÃ§alho por torneio, tabela de qualidade (Standard%/Avg Score/Clear Mistakes%), phase breakdown (Deep/Mid/Short Stack/Push-Fold), top leaks com destaque amarelo para leaks compartilhados entre torneios; badge "â–² melhor" no melhor valor de cada mÃ©trica.
- **`frontend/src/pages/Tournaments.tsx`**: multi-seleÃ§Ã£o de 2â€“4 torneios via checkboxes (desktop e mobile); CTA "Comparar N torneios" com Ã­cone aparece ao selecionar â‰¥ 2 itens; navega para `/tournaments/compare?ids=...`.
- **`frontend/src/App.tsx`**: rota `/tournaments/compare` adicionada antes de `/tournaments/:id`.
- **`backend/database/repositories.py`**: labels de fase de M-ratio padronizadas para inglÃªs â€” `Deep Stack`, `Mid Stack`, `Short Stack`, `Push/Fold` (era PT-BR).

### Changed
- **`frontend/src/pages/TournamentDetail.tsx`**: tooltips das fases atualizados para inglÃªs (Deep Stack / Mid Stack / Short Stack / Push/Fold).

---

## [v0.45.0] â€” 2026-05-03 â€” Sprint M: PERF-008 Tournament Narrative Engine

### Added
- **`backend/leaklab/llm_explainer.py`**: `generate_tournament_narrative(tournament_id, ctx)` â€” gera 2-3 frases descrevendo o arco de qualidade da sessÃ£o via Claude Haiku (max 130 tokens); cache em memÃ³ria por `tournament_id`; fallback determinÃ­stico `_template_narrative()` se LLM indisponÃ­vel.
- **`backend/api/app.py`**: endpoint `GET /history/tournament/<id>/narrative` â€” retorna `{narrative, quality_level}` (solid/regular/poor derivado de `standard_pct`); helper `_build_narrative_context()` agrega label counts, top leaks, ICM breakdown e pior fase do torneio.
- **`frontend/src/lib/api.ts`**: `tournaments.narrative(id)` â†’ `{narrative, quality_level}`.
- **`frontend/src/pages/TournamentDetail.tsx`**: seÃ§Ã£o "Narrativa da SessÃ£o" inline (entre stats grid e phase analysis) â€” badge de qualidade colorido + texto narrativo gerado pelo LLM, carregado automaticamente ao abrir o torneio.
- **`frontend/src/i18n/locales/*/tournaments.json`**: chaves `detail.narrative.*` em PT-BR, EN e ES.

---

## [v0.44.0] â€” 2026-05-03 â€” UX: LeaksPanel layout + PlayerDnaCard radar fix

### Changed
- **`LeaksPanel.tsx`**: redesign do layout de cada item â€” nome do leak em linha prÃ³pria (sem truncate), badges reorganizadas com `justify-between` â€” nÃ— badge e EV loss Ã  esquerda como grupo, botÃ£o **Estudar** sempre ancorado Ã  direita; elimina hack de `flex-1` spacer e overflow em cards com muitos badges simultÃ¢neos.
- **`PlayerDnaCard.tsx`**: corrige label "Disciplina" cortada no grÃ¡fico radar â€” `outerRadius="65%"` + margens aumentadas (`top:15 right:35 bottom:20 left:35`); remove `truncate` desnecessÃ¡rio nas labels do grid de stats.

---

## [v0.43.0] â€” 2026-05-03 â€” Sprint L: PERF-007 Decision DNA

### Backend â€” PERF-007

- **`repositories.py`** â€” `get_player_dna(user_id, days)`: agrega `decisions` em 5 mÃ©tricas normalizadas (0-100):
  - `aggression_index` â€” % de aÃ§Ãµes que sÃ£o raise/bet/jam (excluindo folds)
  - `fold_frequency` â€” % global de folds
  - `three_bet_pct` â€” % de preflop decisions com `is_3bet = True`
  - `positional_awareness` â€” diferencial de agressividade BTN/CO vs UTG/EP (escala 0-100, 50 = neutro)
  - `discipline` â€” standard% geral
  - `icm_awareness` (opcional) â€” ratio de standard% sob alta pressÃ£o ICM vs sem pressÃ£o ICM
  - `_classify_archetype()`: classifica em TAG / LAG / Nit / Calling Station / Balanced a partir das mÃ©tricas
- **`app.py`** â€” `GET /player/dna?days=N`: retorna `{dna, sample_size}`; requer auth

### Frontend â€” PERF-007

- **`PlayerDnaCard.tsx`** (novo) â€” card com radar chart pentagon (Recharts RadarChart), badge de arquÃ©tipo colorido por tipo, grid de 6 mÃ©tricas, descriÃ§Ã£o contextual do arquÃ©tipo; estado vazio com mensagem quando sample_size < 10
- **`pages/Index.tsx`** â€” fetch paralelo de `metrics.dna(90)`; `<PlayerDnaCard>` inserido entre o grid `RecentForm+DecisionQuality` e `BankrollChart`
- **`lib/api.ts`** â€” interfaces `PlayerDna`, `PlayerDnaResponse`; `metrics.dna(days)`

### i18n â€” 3 locales (pt-BR / en / es)

- `dashboard.json` â€” seÃ§Ã£o `dna.*`: title, tooltip, archetype label, sampleSize, noData, 6 axis labels, 5 archetype names + descriptions

### BACKLOG

- Sprint L (PERF-007) concluÃ­da; Sprint M (PERF-008 Tournament Narrative) e Sprint N (PERF-009 GGPoker Parser) aguardam priorizaÃ§Ã£o

---

## [v0.42.0] â€” 2026-05-03 â€” Sprint K pt.2: Ghost Table UX + Engine Notes + Drill-Dashboard Loop

### Backend â€” Ghost Table enhancements

- **`schema.py`** â€” colunas `pot_size REAL` e `facing_bet REAL` adicionadas Ã  tabela `decisions` (SQLite + PostgreSQL, com migration automÃ¡tica)
- **`repositories.py`** â€” `save_decisions()`: extrai `potSize`/`facingSize` do `spot` e armazena em BB dividindo por `level_bb`; `get_drill_spots()`: inclui `pot_size` e `facing_bet` no SELECT; `get_decision_for_drill()`: expandido para retornar todos os campos necessÃ¡rios pelo `analyze_single_decision()`; `get_leak_roi_impact()`: JOIN com `drill_sessions` â€” adiciona `drill_count` e `drill_accuracy` por spot
- **`app.py`** â€” Bug fix crÃ­tico em `_analyze_hands()`: `enriched` dict agora inclui `'spot': di['spot']` (sem isso `pot_size`/`facing_bet` eram sempre `None`); `_GENERIC_NOTES` + `_enrich_note(row)`: detecta 3 strings genÃ©ricas legadas e as substitui por notas especÃ­ficas geradas dos campos do banco (street, position, stack_bb, facing_bet, pot_size, m_ratio, ICM, label, score, action gap); aplicado em `history_tournament` e `coach_student_tournament`; novo endpoint `GET /player/drill-stats` (resumo leve sem carregar spots); novo endpoint `GET /player/spots/drill/<id>/analysis` com cache na tabela `llm_cache` (chave `drill_analysis:{decision_id}`) â€” chama Claude Haiku apenas na primeira vez
- **`decision_engine_v11.py`** â€” `build_interpretation()` reescrito: notas vazias para `standard`/`marginal`; para `small_mistake`/`clear_mistake` gera nota especÃ­fica usando equity diff, draw context, M-Ratio zone, ICM pressure, range zone + position, facing bet context; sempre termina com "AÃ§Ã£o esperada: X."

### Frontend â€” Ghost Table UX

- **`GhostTable.tsx`** â€” board cards limitados por street (preflop = 0, flop = 3, turn = 4, river = 5) para nÃ£o revelar cartas futuras; `pot_size` e `facing_bet` em BB adicionados ao SituationBox; nota do motor movida da fase `active` para a fase `result` (nÃ£o influencia decisÃ£o); renomeado "AnÃ¡lise da IA" â†’ "AnÃ¡lise do Motor"; botÃ£o "Ver anÃ¡lise desta mÃ£o" (BookOpen) na fase result com `requestAnalysis()` â†’ `drill.analysis(id)`; estado `analysis` e `analysisLoading` gerenciados; aÃ§Ãµes "JAM" renomeadas para "All-In" nas 3 locales
- **`GhostDrillCard.tsx`** (novo) â€” card sidebar no dashboard: mostra total de spots treinados, acerto %, avg delta dos Ãºltimos 30 dias; estado vazio com CTA "Iniciar drill" para `/ghost`
- **`LeaksPanel.tsx`** â€” badge "Treinando" (cinza) ou "Dominando" (primÃ¡ria) quando `drill_count > 0`; badge "CrÃ­tico" ocultado quando spot em treino; tooltip mostra `Ghost Table: Nx treinado (X% acerto)`
- **`pages/Index.tsx`** â€” fetch paralelo de `metrics.drillStats(30)`; `<GhostDrillCard stats={drillStats} />` inserido entre LevelCard e LeaksPanel

### i18n â€” 3 locales (pt-BR / en / es)

- **`ghost.json`** â€” chaves: `context.pot`, `context.facing`, `result.engineNote`, `result.requestAnalysis`, `result.analysisLoading`, `result.analysisError`, `situation.*`; `actions.jam` â†’ "All-In"
- **`dashboard.json`** â€” chaves: `leaks.drillPracticing`, `leaks.drillMastering`, `ghost.title`, `ghost.spots`, `ghost.accuracy`, `ghost.continueStudy`, `ghost.noActivity`, `ghost.startNow`

### Removido

- **`backend/leaklab/mercadopago_gateway.py`** â€” arquivo legado do gateway Mercado Pago (migrado para Stripe em v0.29.0); removido para limpar o repositÃ³rio

---

## [v0.41.0] â€” 2026-05-03 â€” Sprint K: PERF-006 Ghost Table Simulator MVP

### Backend â€” PERF-006
- `schema.py` â€” `drill_sessions` table (id, user_id, decision_id, new_action, new_score, original_score, delta, drilled_at) â€” SQLite + PostgreSQL
- `repositories.py` â€” `get_drill_spots()`: fetches undrilled mistake decisions (7-day cooldown); `save_drill_session()`: persists re-decision with score delta; `get_drill_stats()`: 30-day accuracy/total/avg_delta; `get_decision_for_drill()`: ownership-verified decision fetch
- `app.py` â€” `GET /player/spots/drill`: returns spots + stats; `POST /player/spots/drill/submit`: evaluates new_action vs best_action, scores 0.02 if correct else original_score

### Frontend â€” PERF-006
- `GhostTable.tsx` â€” full drill page with state machine (intro â†’ loading â†’ active â†’ result â†’ done): spot context card (street/ICM/position/stack/M-ratio/cards/board), 6 action buttons, result reveal, session accuracy, done screen
- `App.tsx` â€” `/ghost` route with `ProtectedRoute`
- `HudHeader.tsx` â€” "Ghost Table" nav item (Swords icon) for playerNavItems
- `i18n/locales/[pt-BR|en|es]/ghost.json` â€” new namespace (63 keys: drill UI, actions, result messages, stats)
- `i18n/locales/[pt-BR|en|es]/common.json` â€” `nav.ghost` key added
- `api.ts` â€” `DrillSpot`, `DrillStats`, `DrillSubmitResult` interfaces + `drill.spots()` + `drill.submit()`

---

## [v0.40.0] â€” 2026-05-03 â€” Sprint J: PERF-003+004+005 Leak Progression + Pressure Collapse + Drift

### Backend â€” PERF-003: Leak Progression (trend)

- **`repositories.py`** â€” `get_leak_roi_impact()` estendido: compara avg_score dos Ãºltimos 30 dias vs. 30-60 dias anteriores por spot; retorna `trend`: `improving` / `stagnant` / `regressing` / `new`

### Backend â€” PERF-004: Pressure Collapse Detection

- **`repositories.py`** â€” `get_pressure_profile(user_id, days)`: baseline score geral + avg_score por `icm_pressure`; calcula `collapse_delta = score_high - score_none`; flag `has_collapse` se delta > 0.08
- **`app.py`** â€” `GET /player/pressure-profile`

### Backend â€” PERF-005: Confidence Drift Monitor

- **`repositories.py`** â€” `get_confidence_drift(user_id, days=30)`: detecta torneios com avg_score > baseline Ã— 1.30; retorna `drift_detected`, `severity` (mild/moderate/severe), lista de sessÃµes afetadas
- **`app.py`** â€” `GET /player/confidence-drift`

### Frontend â€” Sprint J completo

- **`lib/api.ts`** â€” interfaces `PressureProfile`, `ConfidenceDrift`; `metrics.pressureProfile()`, `metrics.confidenceDrift()`; `LeakRoiData` expandido com campo `trend`
- **`components/hud/PressureProfileCard.tsx`** â€” novo card: barras de mistake_score por pressÃ£o ICM, badge "Colapso" / "SÃ³lido", delta summary
- **`components/hud/LeaksPanel.tsx`** â€” Ã­cones de tendÃªncia (â†“ melhorando / â†’ estagnado / â†‘ regredindo) por leak
- **`pages/Index.tsx`** â€” fetch paralelo de `pressureProfile` + `confidenceDrift`; banner de alerta dismissÃ­vel quando drift detectado; `PressureProfileCard` no sidebar
- **Locales** â€” chaves `pressure.*`, `drift.*` e `leaks.trend*` adicionadas a `dashboard.json` (PT-BR + EN + ES)

## [v0.39.0] â€” 2026-05-03 â€” Sprint I: PERF-001 + PERF-002 ROI Attribution + Leak Priority

### Backend â€” PERF-001: ROI Attribution Engine

- **`repositories.py`** â€” `get_leak_roi_impact(user_id, days)`: query enriquecida com `AVG(t.buy_in)`, `priority_score = n Ã— avg_score`, `ev_loss_monthly = (nÃ—30/days) Ã— avg_score Ã— avg_buy_in Ã— 0.10`; ordenada por `priority_score DESC`
- **`app.py`** â€” `GET /player/leak-roi`: endpoint protegido por `@require_auth`; importa `get_leak_roi_impact`

### Frontend â€” PERF-001 + PERF-002

- **`lib/api.ts`** â€” interface `LeakRoiData` com campos `ev_loss_monthly`, `priority_score`, `priority_rank`; `metrics.leakRoi(days)`
- **`pages/Index.tsx`** â€” fetch paralelo de `leakRoi`; passa ao `LeaksPanel` quando disponÃ­vel
- **`components/hud/LeaksPanel.tsx`** â€” custo mensal estimado por leak (`~$X/mÃªs`); badge `CRÃTICO` com Ã­cone chama para `priority_rank â‰¤ 3`
- **Locales** â€” chaves `leaks.critical` e `leaks.evLoss` adicionadas a `dashboard.json` (PT-BR + EN + ES)

### Backlog

- **`BACKLOG.md`** â€” roadmap atualizado com Sprint I (ðŸ”„), J, K (ðŸ“‹); specs completos de PERF-001 a PERF-006

## [v0.38.0] â€” 2026-05-03 â€” Sprint H: UX-007 Dashboard i18n â€” cards traduzidos

### Frontend â€” Dashboard cards i18n (bug fix)

- **`LeaksPanel.tsx`** â€” `spotLabel()` movido para dentro do componente; `t("leaks.*")` para tÃ­tulo, botÃ£o estudar e descriÃ§Ã£o de leak
- **`BankrollChart.tsx`** â€” botÃµes de perÃ­odo, tÃ­tulo e estado vazio via `t("bankroll.*")`
- **`RecentTournamentsTable.tsx`** â€” cabeÃ§alhos, status (Analisado/Em fila) e `formatDate` com `i18n.language` dinÃ¢mico
- **`DecisionQualityCard.tsx`** â€” array `LABELS` movido para dentro do componente; todos os rÃ³tulos via `t("decisions.*")`
- **`StreetBreakdown.tsx`** â€” tÃ­tulo, tooltip e estado vazio via `t("streets.*")`
- **`PositionChart.tsx`** â€” tÃ­tulo, tooltip e estado vazio via `t("positions.*")`
- **`RecentForm.tsx`** â€” `scoreDot()` movido para dentro do componente; legenda e tÃ­tulo via `t("form.*")`
- **`IcmBreakdown.tsx`** â€” `ICM_LABEL` movido para dentro do componente; rÃ³tulos de pressÃ£o ICM e tÃ­tulo via `t("icm.*")`
- **`LevelCard.tsx`** â€” nÃ­vel, progresso, leaks bloqueadores e link de estudo via `t("level.*")`; pluralizaÃ§Ã£o i18next (`tournament_one`/`tournament_other`)
- **`EmptyDashboard.tsx`** â€” array `MODULES` movido para dentro do componente; upload section e mÃ³dulos via `t("empty.*")`
- **`PlayerStatsCard.tsx`** â€” "em breve", "sem dados", "mÃ£os" e mensagem vazia via `t("playerStats.*")`
- **Locales** â€” ~80 novas chaves adicionadas a `dashboard.json` (PT-BR + EN + ES)

## [v0.37.0] â€” 2026-05-02 â€” Sprint G: UX-006 Header Cleanup + i18n Full Coverage

### Frontend â€” Header simplification

- **`HudHeader.tsx`** â€” removidos badges (NEW/ALPHA) dos itens de nav, pill "Engine Active" e pill com nome do coach
- **`Index.tsx`** â€” coach badge movido para a seÃ§Ã£o hero do dashboard (abaixo do subtÃ­tulo), com Ã­cone `GraduationCap` e ring sutil

### Frontend â€” i18n cobertura completa (5 novos namespaces, 3 idiomas)

- **Novos namespaces** â€” `aicoach`, `coaches`, `profile`, `replayer`, `landing` (PT-BR + EN + ES)
- **`NotFound.tsx`** â€” traduzido via `common.notFound.*`
- **`AICoach.tsx`** â€” traduzido via namespace `aicoach`; sugestÃµes, saudaÃ§Ã£o, painel de contexto e sessÃ£o
- **`Tournaments.tsx`** â€” traduzido; badges de formato, stats, cabeÃ§alhos de tabela, estados vazios
- **`TournamentDetail.tsx`** â€” traduzido; `SEVERITY_META` e `FILTERS` movidos para dentro do componente; `ScoreLabel` inline
- **`StudyPlan.tsx`** â€” traduzido; toolbar, KPIs, diagnÃ³stico, roadmap semanal, recursos, botÃµes de dia
- **`CoachesDirectory.tsx`** â€” traduzido; `SORT_OPTIONS` movido para dentro de `FilterPanel`
- **`PublicCoachProfile.tsx`** â€” traduzido; loading, nÃ£o encontrado, botÃ£o voltar, contadores
- **`StudentProfile.tsx`** â€” traduzido; tÃ­tulos de seÃ§Ã£o, coach linkado, botÃµes de unlink
- **`Replayer.tsx`** â€” traduzido; navegaÃ§Ã£o de mÃ£os, controles, action log, painel EV, formulÃ¡rio de anotaÃ§Ã£o de coach, resultado do showdown
- **`Landing.tsx`** â€” traduzido completamente; arrays `PLANS`, `HOW_IT_WORKS`, `FEATURES` movidos para dentro dos sub-componentes; cada seÃ§Ã£o usa `useTranslation("landing")`
- **Locales atualizados** â€” `tournaments.json` + `common.json` + `study.json` com novas chaves; `landing.json` reescrito com estrutura completa (planos, CTA, footer)

---

## [v0.36.0] â€” 2026-05-02 â€” Sprint D: BACK-016 WhatsApp Coaching Drills

### Backend

- **`leaklab/whatsapp_bot.py`** â€” mÃ³dulo do bot: `send_text()` (Cloud API v19), `handle_incoming()` (dispatcher), `_handle_answer()` (correÃ§Ã£o MCQ), `_send_question()` (busca top leak e gera exercÃ­cio), `_generate_exercise()` (Claude Haiku â†’ JSON com question/answer/explanation), `_fallback_exercise()` (template local sem LLM); estado de questÃµes pendentes em dict in-memory por nÃºmero
- **`api/app.py`** â€” 3 novas rotas:
  - `GET /whatsapp/webhook` â€” verificaÃ§Ã£o de webhook pelo Meta (hub.challenge)
  - `POST /whatsapp/webhook` â€” recebe eventos Meta, despacha para `handle_incoming()`; sempre retorna 200 imediato
  - `PATCH /profile/phone` â€” vincula/desvincula nÃºmero de WhatsApp ao usuÃ¡rio logado (validaÃ§Ã£o E.164, unicidade)
  - `GET /auth/me` â€” agora retorna `whatsapp_phone`
- **`database/schema.py`** â€” migration `ALTER TABLE users ADD COLUMN whatsapp_phone TEXT UNIQUE` (Postgres + SQLite)
- **`database/repositories.py`** â€” `get_user_by_phone(phone)` + `update_user_phone(user_id, phone)`
- **`.env`** â€” adicionado `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`, `WHATSAPP_VERIFY_TOKEN`

### Frontend

- **`lib/api.ts`** â€” `auth.updatePhone(phone)` â†’ `PATCH /profile/phone`; `UserProfile.whatsapp_phone` adicionado ao tipo
- **`pages/StudentProfile.tsx`** â€” nova seÃ§Ã£o "WhatsApp â€” Coaching Drills": campo para inserir nÃºmero (formato DDI+DDD), botÃ£o Salvar e botÃ£o Desvincular; mostra nÃºmero atual vinculado
- **`frontend/.env`** â€” `VITE_WHATSAPP_NUMBER=15556305701` (nÃºmero sandbox Meta; substituir pelo nÃºmero real em produÃ§Ã£o)

### Fluxo
1. UsuÃ¡rio vincula nÃºmero em Perfil â†’ WhatsApp
2. Clica "Iniciar no WhatsApp" no StudyPlan â†’ abre conversa com o bot
3. Qualquer mensagem â†’ bot busca top leak, gera MCQ via Claude Haiku, envia a questÃ£o
4. UsuÃ¡rio responde A/B/C/D â†’ bot corrige e explica
5. PrÃ³xima mensagem â†’ novo exercÃ­cio

---

## [v0.35.0] â€” 2026-05-02 â€” Sprint F: UX-005 InternacionalizaÃ§Ã£o (i18n) PT/EN/ES

### Frontend

- **`i18n/index.ts`** â€” setup `i18next` + `i18next-browser-languagedetector`; auto-detecta via `localStorage` â†’ `navigator.language`; fallback `pt-BR`; namespaces: `common`, `dashboard`, `tournaments`, `study`, `auth`
- **`main.tsx`** â€” importa `./i18n` para inicializar antes do React
- **Locales PT-BR** â€” `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **Locales EN** â€” `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **Locales ES** â€” `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **`HudHeader.tsx`** â€” `LanguageSwitcher` dropdown (ðŸ‡§ðŸ‡· PT Â· ðŸ‡ºðŸ‡¸ EN Â· ðŸ‡ªðŸ‡¸ ES) no canto direito; nav labels e botÃ£o Import traduzidos via `t()`; preferÃªncia salva em `localStorage` (`leaklab_lang`)
- **`Login.tsx`** â€” labels, placeholders e estados de loading traduzidos via namespace `auth`
- **`Index.tsx`** â€” eyebrow, tÃ­tulo, subtÃ­tulo, KPIs, AI Confidence e footer traduzidos via namespaces `dashboard` + `common`

---

## [v0.34.0] â€” 2026-05-02 â€” Sprint C+E: BACK-014 + BACK-017 Revenue Share + Admin Panel

### Backend

- **`schema.py`** â€” novo campo `users.referral_coach_id` + `users.suspended`; nova tabela `coach_payments` (coach_id, period YYYY-MM, active_students, amount_cents, status, paid_at) em SQLite e PostgreSQL via `_run_migrations`
- **`auth.py`** â€” novo decorator `require_admin()` que valida `role == 'admin'` no banco
- **`repositories.py`** â€” novas funÃ§Ãµes: `calculate_coach_payout()` (lÃ³gica de revenue share), `get_admin_dashboard_stats()`, `get_all_users()`, `get_all_users_count()`, `update_user_admin()`, `get_coaches_with_payout_status()`, `upsert_coach_payment()`, `mark_coach_payment_paid()`, `get_coach_finance_summary()`, `get_coach_finance_students()`, `get_coach_finance_history()`, `get_admin_activity_logs()`
- **`app.py`** â€” 10 novos endpoints:
  - `GET /admin/dashboard` â€” MRR estimado, usuÃ¡rios ativos, distribuiÃ§Ã£o de planos, repasses pendentes
  - `GET /admin/users` â€” lista paginada com filtros (plan, role, search)
  - `PATCH /admin/users/<id>` â€” suspender/alterar plano
  - `GET /admin/finance/coaches` â€” repasses do ciclo com auto-upsert
  - `PATCH /admin/finance/coaches/<id>/pay` â€” marcar como pago
  - `GET /admin/finance/export.csv` â€” exportaÃ§Ã£o CSV para processamento bancÃ¡rio
  - `GET /admin/logs` â€” Ãºltimas importaÃ§Ãµes de torneios
  - `GET /coach/finance/summary` â€” ciclo atual do coach
  - `GET /coach/finance/students` â€” alunos com status de atividade
  - `GET /coach/finance/history` â€” histÃ³rico de repasses recebidos

### Frontend

- **`api.ts`** â€” tipos `AdminStats`, `AdminUser`, `CoachPayout`, `CoachFinanceSummary`, `CoachFinanceStudent`, `CoachPaymentRecord`; objetos `adminDashboard` e `coachFinance` com todas as chamadas
- **`pages/admin/AdminDashboard.tsx`** â€” painel admin com 4 abas: VisÃ£o Geral (KPIs + distribuiÃ§Ã£o de planos), UsuÃ¡rios (tabela paginada com filtros, alterar plano inline, suspender/reativar), Financeiro (tabela de repasses por perÃ­odo, "Marcar pago", exportar CSV), Logs (Ãºltimas importaÃ§Ãµes)
- **`CoachDashboard.tsx`** â€” nova aba "Financeiro": resumo do ciclo atual (alunos totais/ativos, receita estimada, mensalidade zerada), lista de alunos com badge Ativo/Inativo, histÃ³rico de repasses
- **`App.tsx`** â€” `AdminRoute` guard + rota `/admin`; `PublicRoute` redireciona admin para `/admin`
- **`HudHeader.tsx`** â€” nav item "Admin" com Ã­cone Shield para role admin

### Regras de negÃ³cio implementadas
- 1â€“3 alunos ativos: mensalidade do coach zerada, R$0 de repasse
- 4â€“9 alunos ativos: mensalidade zerada + R$15/aluno/mÃªs
- 10+ alunos ativos: mensalidade zerada + R$20/aluno/mÃªs
- Aluno ativo = importou â‰¥1 torneio nos Ãºltimos 30 dias + plano PRO

---

## [v0.33.0] â€” 2026-05-02 â€” Sprint B: UX-002 Responsividade Mobile/Tablet

### Frontend

- **`HudHeader.tsx`** â€” bottom navigation bar fixa em mobile (`fixed bottom-0 z-50 md:hidden`) com Ã­cone + label curto por rota; FAB de import (`fixed bottom-[72px] right-4 size-12`) substitui o botÃ£o de import do header em mobile; padding do header ajustado para `px-4 md:px-8`
- **`HudLayout.tsx`** â€” padding inferior `pb-28 md:pb-8` para deixar clearance acima do bottom nav fixo
- **`Index.tsx`** â€” grid de KPIs vai de 1-col para `grid-cols-2 lg:grid-cols-4` (2 colunas em mobile); sidebar com LevelCard/LeaksPanel usa `order-first lg:order-none` â€” aparece antes dos grÃ¡ficos em mobile
- **`RecentTournamentsTable.tsx`** â€” modo duplo: lista de cards clicÃ¡veis `md:hidden` + tabela `hidden md:block overflow-x-auto`; `formatDateShort()` para data compacta nos cards mobile
- **`Tournaments.tsx`** â€” modo duplo: lista de cards mobile com profit, badge, delete + tabela desktop; empty state diferente por viewport
- **`Replayer.tsx`** â€” barra de controles vira sticky bottom em mobile (`sticky bottom-14 z-30 border-t bg-background/95 backdrop-blur-md`) e volta ao painel normal em desktop (`md:static md:border md:rounded-xl md:bg-hud-surface`)
- **`TournamentDetail.tsx`** â€” tabelas de fase (M-Ratio) e textura de board recebem `overflow-x-auto` para scroll horizontal em mobile
- **`StudentDetail.tsx`** â€” tabs do detalhe do aluno (coach view) recebem `overflow-x-auto` + `shrink-0` nos botÃµes para scroll horizontal em telas pequenas

---

## [v0.32.0] â€” 2026-05-02 â€” Sprint 4: BACK-001 + BACK-005 (confirmados + gap fechado)

### Backend
- **`api/app.py` â†’ `history_tournament`** â€” enriquece cada decisÃ£o com `has_annotation: bool` usando `get_annotations_for_decisions`; aluno agora sabe quais mÃ£os tÃªm anotaÃ§Ã£o do coach sem fazer request extra

### Frontend
- **`api.ts`** â€” `TournamentDecision` ganha campo opcional `has_annotation?: boolean`
- **`TournamentDetail.tsx`** â€” `Hand.hasAnnotation` propagado via `groupByHand` (true se qualquer decisÃ£o do grupo tem anotaÃ§Ã£o); badge "Coach" com Ã­cone GraduationCap aparece ao lado do severity badge em mÃ£os anotadas pelo coach

### Confirmado jÃ¡ implementado (BACK-001 e BACK-005 core)
- Tabela `coach_hand_annotations` + endpoints GET/POST/DELETE `/coach/student/:id/hand-annotations`
- `AnnotationForm` no `WorstTab` do `StudentDetail.tsx` (visÃ£o coach)
- Replayer: painel de anotaÃ§Ã£o para coach (form com modo/aÃ§Ã£o/veredito) e balÃ£o read-only para aluno
- Ambos os endpoints de replay (`/replay/:t/:h` e `/coach/student/:id/replay/:t/:h`) incluem `coach_annotations`
- Badge "âœ“ Coach" na listagem de torneios do aluno (`Tournaments.tsx`) via `get_reviewed_tournament_ids()`

---

## [v0.31.0] â€” 2026-05-02 â€” Sprint A: UX-001 + UX-003 + LLM template upgrade

### Frontend â€” UX-001: Lista de torneios melhorada
- **`RecentTournamentsTable.tsx`** â€” fallback de nome agora usa `#tournament_id` (era `site`); badge detection estendida: +SAT (satellite), +KO (knockout/bounty/PKO), +SNG (sit & go variants); subtitle mostra `{hands_count} mÃ£os` abaixo do ID
- **`Tournaments.tsx`** â€” coluna "ID" renomeada para "Torneio"; mesmas melhorias de badge e fallback; `{hands_count} mÃ£os` no subtitle

### Frontend â€” UX-003: Tooltips e score auto-explicativo
- **`TournamentDetail.tsx`** â€” componente `InfoTooltip` (HelpCircle + Radix Tooltip) adicionado a cabeÃ§alhos das seÃ§Ãµes fase/textura e Ã s colunas "Erros %" e "Score MÃ©dio"; tooltips explicam os thresholds (M-Ratio, texturas de board com exemplos de cartas, % de erro, faixas do score)
- **`TournamentDetail.tsx`** â€” componente `ScoreLabel` exibe rÃ³tulo colorido (Ã“timo / Bom / Moderado / Alto) inline ao score para leitura imediata sem referÃªncia externa

### Backend / IA â€” LLM template upgrade
- **`llm_explainer.py`** â€” `analyze_single_decision` migrada de 3 parÃ¡grafos genÃ©ricos para template estruturado em 5 seÃ§Ãµes: âŒ O Erro / ðŸ“ A MatemÃ¡tica / ðŸ§­ O Contexto / âœ… A AÃ§Ã£o Correta / ðŸ’¡ A LiÃ§Ã£o; `max_tokens` 500 â†’ 900

### Infra â€” BACK-007 (confirmado como jÃ¡ implementado)
- `UploadQueue.tsx` + `HudHeader.tsx` jÃ¡ implementavam upload mÃºltiplo com fila sequencial â€” confirmado durante Sprint A; nenhuma mudanÃ§a necessÃ¡ria

---

## [v0.30.0] â€” 2026-05-02 â€” AnÃ¡lise por Fase e Textura de Board

### Backend
- **`leaklab/board_texture.py`** â€” novo mÃ³dulo: `classify_board_texture(board_json)` classifica boards pÃ³s-flop em `dry | coordinated | wet | monotone | paired` usando span de ranks e contagem de naipes
- **`repositories.py`** â€” `get_phase_analysis(tournament_db_id)`: agrupa decisÃµes por fase (Folgado Mâ‰¥20 / MÃ©dio M10-20 / PressÃ£o M6-10 / CrÃ­tico M<6) derivando fase do `m_ratio`; `get_texture_analysis(tournament_db_id)`: classifica boards pÃ³s-flop e retorna stats por textura
- **`GET /history/tournament/<id>/phase_analysis`** â€” novo endpoint: retorna distribuiÃ§Ã£o de erros e score mÃ©dio por fase de torneio
- **`GET /history/tournament/<id>/texture_analysis`** â€” novo endpoint: retorna distribuiÃ§Ã£o de erros pÃ³s-flop por textura de board

### Frontend
- **`TournamentDetail.tsx`** â€” duas novas seÃ§Ãµes entre o grid de stats e os filtros: tabela de AnÃ¡lise por Fase e tabela de PÃ³s-Flop por Textura de Board; cÃ³digo de cores: verde (<25% erros), amarelo (25-40%), vermelho (>40%)
- **`api.ts`** â€” `tournaments.phaseAnalysis()` e `tournaments.textureAnalysis()`; novas interfaces `PhaseData` e `TextureData`

---

## [v0.29.0] â€” 2026-05-02 â€” BACK-015: MigraÃ§Ã£o Mercado Pago â†’ Stripe

### Pagamentos
- **`stripe_gateway.py`** â€” novo gateway: `create_subscription`, `cancel_subscription`, `get_subscription`, `get_payment`, `validate_webhook`; usa Stripe Subscriptions API com `payment_behavior=default_incomplete`
- **`POST /subscription/checkout`** â€” simplificado: recebe sÃ³ `plan`, cria Stripe Customer + Subscription, retorna `{ client_secret, subscription_id }` para confirmaÃ§Ã£o no frontend
- **`POST /subscription/activate`** â€” novo: verifica `PaymentIntent.status` e ativa o plano no banco (chamado pelo frontend apÃ³s `stripe.confirmPayment`)
- **`POST /subscription/webhook`** â€” reescrito para eventos Stripe: `invoice.payment_succeeded` â†’ ativa plano; `customer.subscription.deleted` â†’ reverte para free; sem secret configurado aceita sem validaÃ§Ã£o (dev mode)
- **`POST /subscription/cancel`** â€” usa `stripe.Subscription.cancel()` via gateway
- Removido `mercadopago_gateway.py` (todas as rotas MP descontinuadas)

### Frontend
- **`CheckoutModal.tsx`** â€” reescrito com `@stripe/stripe-js`; `loadStripe` + `PaymentElement` substitui 8 campos manuais do MP; `Promise.all` carrega SDK e intent em paralelo; confirmaÃ§Ã£o via `stripe.confirmPayment({ redirect: 'if_required' })` + `/subscription/activate`
- **`api.ts`** â€” `checkout()` simplificado (sÃ³ `plan`); novo `activate(plan, payment_intent_id, subscription_id)`

### DependÃªncias
- `requirements.txt`: + `stripe==12.0.0`; removido `requests` (nÃ£o mais usado pelo gateway)
- `package.json`: + `@stripe/stripe-js`

### Env vars necessÃ¡rias
| VariÃ¡vel | DescriÃ§Ã£o |
|---|---|
| `STRIPE_SECRET_KEY` | Chave secreta Stripe (`sk_test_...` / `sk_live_...`) |
| `STRIPE_PUBLISHABLE_KEY` | NÃ£o usada no backend |
| `STRIPE_WEBHOOK_SECRET` | Secret do webhook Stripe (`whsec_...`) |
| `STRIPE_PRICE_STARTER` | Price ID do plano Starter (`price_...`) |
| `STRIPE_PRICE_PRO` | Price ID do plano Pro (`price_...`) |
| `VITE_STRIPE_PUBLISHABLE_KEY` | Chave pÃºblica Stripe para o frontend |

### Testes
- `test_subscription.py` reescrito: 25 testes cobrindo checkout, activate, invoices, cancel, webhook â€” 0 regressÃµes

---

## [v0.28.1] â€” 2026-05-01 â€” BACK-015 fix: payer.identification + debugging

### Pagamentos
- **`mercadopago_gateway.py`** â€” `create_subscription` aceita `identification_type`/`identification_number`; inclui `payer.identification` no body do `/v1/payments` (obrigatÃ³rio no Brasil); log completo do response de erro
- **`POST /subscription/checkout`** â€” extrai `identification_type`, `identification_number` e `payer_email` do body; `payer_email` do form substitui email do usuÃ¡rio quando fornecido (permite usar email de conta teste MP)
- **`CheckoutModal.tsx`** â€” extrai `identificationType`, `identificationNumber`, `cardholderEmail` de `getCardFormData()` e envia ao backend
- **`api.ts`** â€” `subscription.checkout()` aceita os novos campos

### Testes
- 2 novos testes: `test_checkout_forwards_identification`, `test_checkout_payer_email_override`
- 23 testes de subscription â€” 0 regressÃµes

---

## [v0.28.0] â€” 2026-04-27 â€” BACK-015: Mercado Pago Transparent Checkout

### Pagamentos
- **`mercadopago_gateway.py`** â€” novo mÃ³dulo: `get_or_create_plan`, `create_subscription`, `cancel_subscription`, `get_subscription`, `get_payment`, `validate_webhook_signature` (HMAC-SHA256)
- **`POST /subscription/checkout`** â€” cria assinatura recorrente MP via card token; rate limit 5/h; atualiza `plan` e `mp_subscription_id` do usuÃ¡rio no banco
- **`POST /subscription/webhook`** â€” recebe eventos MP (`subscription_preapproval`, `payment`); valida assinatura HMAC-SHA256; atualiza plano e salva pagamentos
- **`GET /subscription/invoices`** â€” retorna histÃ³rico de pagamentos do usuÃ¡rio (limit 20)
- **`POST /subscription/cancel`** â€” cancela assinatura MP ativa e reverte plano para `free`

### Schema
- Tabela `payments` (id, user_id, plan, amount_cents, currency, status, gateway, gateway_id, gateway_sub_id, period_start, period_end, created_at)
- Coluna `mp_subscription_id` adicionada a `users`

### Frontend
- **`CheckoutModal.tsx`** â€” modal de checkout transparente: carrega MP JS SDK v2 dinamicamente, inicializa `mp.cardForm()` com iframes seguros para dados do cartÃ£o, submete token ao backend, exibe sucesso/erro e chama `refreshUser()`
- **`AccountMenu.tsx`** â€” botÃµes "Starter R$19" e "Pro R$39" abrem `CheckoutModal` (substituindo links `mailto:`)
- **`QuotaBanner.tsx`** â€” idem: botÃµes de upgrade abrem `CheckoutModal`
- **`api.ts`** â€” `subscription.checkout()`, `subscription.invoices()`, `subscription.cancel()`

### Testes
- 227 testes â€” 0 regressÃµes

---

## [v0.27.0] â€” 2026-04-27 â€” BACK-011 pt.2: Anti-Prompt Injection + ModeraÃ§Ã£o de ConteÃºdo

### SeguranÃ§a â€” Camada 1: Anti-Prompt Injection
- **`content_moderation.py`** â€” novo mÃ³dulo com `sanitize_llm_input(text, max_len)`: remove 14 padrÃµes de injection (EN + PT-BR) via regex antes de qualquer chamada ao LLM; tenta de role spoofing (`system:`, `assistant:`), token markers (`<|...|>`, `[INST]`), comandos de esquecimento e personas alternativas
- **`coach_chat_reply`** â€” mensagem do usuÃ¡rio sanitizada antes de entrar no payload do Claude
- **`analyze_single_decision`** â€” campo `note` (texto livre do hand history) sanitizado antes de ir ao LLM
- **`/coach/chat`** â€” sanitizaÃ§Ã£o no endpoint antes de repassar ao `coach_chat_reply`; erro interno nÃ£o mais exposto na resposta
- **AnotaÃ§Ãµes de coach** â€” `comment` sanitizado via `sanitize_llm_input` antes de salvar no banco
- Todas as tentativas detectadas sÃ£o logadas com `log.warning` para anÃ¡lise posterior

### SeguranÃ§a â€” Camada 2: ModeraÃ§Ã£o de ConteÃºdo (blocklist local v1)
- **`moderate_text(text)`** â€” verifica texto livre contra blocklist PT-BR + EN cobrindo: discurso de Ã³dio, ataques, spam/scam, links de redes sociais suspeitos, conteÃºdo adulto explÃ­cito; retorna `(is_clean, reason)` e loga flags
- **`/coach-profile` (POST)** â€” campo `bio` verificado antes de salvar; retorna 422 se flaggeado
- **`/coach/review` (POST)** â€” `review_text` verificado antes de salvar; retorna 422 se flaggeado
- **`/coach/student/:id/hand-annotations` (POST)** â€” `comment` verificado + sanitizado antes de salvar

### Schema
- Coluna `moderation_status TEXT DEFAULT 'approved'` adicionada a `coach_profiles`, `coach_reviews`, `coach_hand_annotations` (PostgreSQL: `ALTER TABLE IF NOT EXISTS`; SQLite: migration lazy)

### Testes
- 227 testes â€” 0 regressÃµes

---

## [v0.26.0] â€” 2026-04-27 â€” BACK-011: Hardening de seguranÃ§a

### SeguranÃ§a â€” CrÃ­tico
- **bcrypt** â€” senhas agora armazenadas com bcrypt + salt aleatÃ³rio; migraÃ§Ã£o transparente: hashes SHA-256 legados sÃ£o re-hasheados no prÃ³ximo login com sucesso
- **SECRET_KEY forÃ§ado** â€” inicializaÃ§Ã£o levanta `RuntimeError` em produÃ§Ã£o se `LEAKLAB_SECRET` nÃ£o estiver definido ou tiver menos de 32 caracteres; aviso no terminal em desenvolvimento

### SeguranÃ§a â€” Alta
- **`require_coach` usa role do banco** â€” antes validava o campo `role` do JWT (forjÃ¡vel); agora consulta o banco em cada requisiÃ§Ã£o protegida
- **Token nÃ£o aceito via URL** â€” `_extract_token()` removia fallback `?token=` que expunha tokens nos logs de servidor; aceita apenas `Authorization: Bearer` e cookie
- **IDOR em anotaÃ§Ãµes de coach corrigido** â€” endpoint `POST /coach/student/:id/hand-annotations` agora valida que `decision_id` pertence ao aluno antes de salvar
- **Headers de seguranÃ§a HTTP** â€” `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy` adicionados a toda resposta; `Strict-Transport-Security` ativado em produÃ§Ã£o (`RENDER=true`)

### SeguranÃ§a â€” MÃ©dia
- **Rate limiting** â€” Flask-Limiter instalado; limites por IP: `/auth/register` 10/min, `/auth/login` 15/min, `/analyze` 30/h, `/analyze/decision` e `/analyze/hand-coach` 30/h, `/analyze/tournament-summary` 20/h; desativado automaticamente em testes (`app.testing`)
- **ValidaÃ§Ã£o de extensÃ£o de arquivo** â€” upload em `/analyze` rejeita arquivos que nÃ£o terminem em `.txt`
- **Mensagens de erro sanitizadas** â€” exceÃ§Ãµes internas logadas com `log.exception()` em vez de expostas no corpo da resposta
- **Senha mÃ­nima 8 caracteres** â€” aumentado de 6 para 8 em `/auth/register`
- **Role restrito no cadastro** â€” valores fora de `player/coach` sÃ£o coercidos para `player` silenciosamente

### Infraestrutura
- `bcrypt==4.2.1` e `Flask-Limiter==3.8.0` adicionados ao `requirements.txt`
- `repositories.py`: funÃ§Ãµes `_hash_password`, `_check_password`, `decision_belongs_to_student` extraÃ­das; `update_user_email`, `change_user_password`, `check_password` migradas para usar bcrypt

### Testes
- 227 testes â€” 0 regressÃµes

---

## [v0.25.0] â€” 2026-04-27 â€” UX-004: Menu de conta com plano e uso

### Adicionado
- **`AccountMenu`** â€” dropdown acessÃ­vel ao clicar no nome/plano no header; exibe username, badge de plano colorido por tier (Free/Starter/Pro/Coach), barras de uso mensal (torneios + anÃ¡lises LeakLabs), CTAs de upgrade contextuais e links para Perfil e Sair
- **`/auth/me` inclui quota** â€” resposta agora inclui `plan`, `tournaments_used`, `ai_calls_used`, `plan_limits`; elimina segundo request separado ao `/subscription/status`

### Alterado
- **`HudHeader`** â€” item "Perfil" removido do menu de navegaÃ§Ã£o do jogador; bloco username+logout substituÃ­do por `AccountMenu`; Dashboard corrigido para `/dashboard`
- **`UserProfile`** â€” interface TypeScript estendida com campos de quota
- **Dashboard (`Index.tsx`)** â€” `QuotaBanner` removido da sidebar (redundante com `AccountMenu`)

---

## [v0.24.0] â€” 2026-04-27 â€” Proposta B: 3 planos (Free / Starter / Pro)

### Adicionado
- **Plano Starter R$19/mÃªs** â€” 20 torneios + 40 anÃ¡lises/mÃªs; pÃºblico alvo: jogador casual que ultrapassou o Free mas nÃ£o precisa de volume de grinder
- **3 planos no `/subscription/plans`** â€” Free, Starter (R$19), Pro (R$39)

### Alterado
- **Plano Pro**: R$15 â†’ **R$39/mÃªs** â€” torneios ilimitados + 150 anÃ¡lises LeakLabs/mÃªs
- **PLAN_LIMITS** â€” `starter: {tournaments: 20, ai_calls: 40}` Â· `pro: {tournaments: None, ai_calls: 150}`
- **Landing page** â€” seÃ§Ã£o Planos migrada para grid de 3 colunas; badge "Mais popular" no Starter, badge "Grinder" + destaque primÃ¡rio no Pro
- **QuotaBanner** â€” botÃµes Starter R$19 + Pro R$39 lado a lado no banner de limite atingido

---

## [v0.23.0] â€” 2026-04-27 â€” UX-003: Landing page pÃºblica

### Adicionado
- **Landing page pÃºblica em `/`** â€” apresentaÃ§Ã£o do produto para visitantes nÃ£o autenticados; seÃ§Ãµes: Hero com nÃ­veis preview, EstatÃ­sticas, Como Funciona (3 passos), Funcionalidades (6 cards), Planos (Free vs Pro), CTA final e Footer
- **Rota `/dashboard`** â€” dashboard do jogador movido de `/` para `/dashboard`; usuÃ¡rios autenticados sÃ£o redirecionados automaticamente para o destino correto ao acessar `/` ou `/login`
- **`PublicRoute`** â€” guarda de rota pÃºblico: redireciona usuÃ¡rio jÃ¡ logado para `/dashboard` (jogador) ou `/coach-dashboard` (coach), evitando que veja a landing ou tela de login desnecessariamente

### Alterado
- `App.tsx` â€” `/` agora renderiza `Landing` (via `PublicRoute`); `/login` tambÃ©m usa `PublicRoute`; `/dashboard` Ã© a nova rota protegida do jogador; `CoachRoute` redireciona nÃ£o-coaches para `/dashboard`
- `Login.tsx` â€” pÃ³s-login redireciona jogador para `/dashboard` em vez de `/`
- `HudHeader.tsx` â€” logo aponta para `/dashboard` em vez de `/` (usuÃ¡rio autenticado)

---

## [v0.22.0] â€” 2026-04-27 â€” BACK-010: Freemium + quota + backlog expandido

### Adicionado
- **Planos freemium e controle de quota** â€” plano Free: 3 torneios/mÃªs + 10 anÃ¡lises IA/mÃªs; plano Pro: ilimitado; quota resetada automaticamente no inÃ­cio de cada mÃªs (lazy reset por usuÃ¡rio)
- **Endpoints de subscription** â€” `GET /subscription/plans`, `GET /subscription/status`, `POST /subscription/upgrade`; upgrade manual em v1 (sem gateway de pagamento)
- **Middleware de quota no backend** â€” `_check_upload_quota()` antes do `/analyze`; `_check_ai_quota()` antes de `/analyze/decision`, `/analyze/hand-coach` e `/analyze/tournament-summary`; retorna HTTP 402 com `quota_exceeded: true` quando limite atingido
- **Cache de tournament summary** â€” `/analyze/tournament-summary` agora retorna o summary jÃ¡ salvo no banco quando disponÃ­vel, sem chamar o LLM novamente; economiza quota e reduz latÃªncia
- **QuotaBanner no dashboard** â€” barra de uso de torneios e anÃ¡lises IA exibida na sidebar do dashboard; aparece somente para plano Free e apenas quando â‰¥ 80% do limite foi atingido; botÃ£o de upgrade via email em v1
- **Busca corrigida em /tournaments** â€” placeholder atualizado de "herÃ³i" para "nome, tipo (MTT/SNG) ou ID"
- **Backlog expandido** â€” UX-002 (responsividade mobile/tablet, ~15h) e BACK-014 (revenue share para coaches, ~20h) documentados com escopo, modelo de dados e esforÃ§o estimado

### Backend
- `backend/database/schema.py` â€” colunas `tournaments_this_month`, `ai_calls_this_month`, `quota_reset_at` na tabela `users`; migrations para SQLite e Postgres
- `backend/database/repositories.py` â€” `PLAN_LIMITS`, `get_quota_status()`, `increment_tournament_count()`, `increment_ai_calls()`, `_maybe_reset_quota()` (lazy reset mensal)
- `backend/api/app.py` â€” `_check_upload_quota()`, `_check_ai_quota()`; subscription endpoints; quota wiring em analyze + LLM endpoints

### Frontend
- `frontend/src/lib/api.ts` â€” interface `QuotaStatus`; namespace `subscription` com `status()`, `plans()`, `upgrade()`
- `frontend/src/components/hud/QuotaBanner.tsx` â€” componente novo com barras de progresso e CTA de upgrade
- `frontend/src/pages/Index.tsx` â€” `QuotaBanner` inserido no topo da sidebar
- `frontend/src/pages/Tournaments.tsx` â€” placeholder da busca corrigido

---

## [v0.21.0] â€” 2026-04-26 â€” UX: Logos de sites, auto-reload pÃ³s-import, nÃ­veis rebalanceados

### Adicionado
- **Logo dos sites na lista de torneios** â€” componente `SiteLogo` exibe favicon do site (PokerStars, GGPoker, 888Poker, Winamax, ACR) em container 24Ã—24 com tooltip do nome completo; fallback para sigla em texto se a imagem falhar; visÃ­vel na `RecentTournamentsTable` (dashboard) e na lista completa `/tournaments`

### Corrigido
- **Auto-reload pÃ³s-importaÃ§Ã£o em qualquer tela** â€” `UploadQueue` agora dispara evento global `leaklab:tournament-imported` a cada arquivo processado; `Tournaments.tsx` escuta o evento e chama `reload()` automaticamente; antes, importar pelo botÃ£o do header na tela `/tournaments` nÃ£o atualizava a lista
- **Badge SNG/MTT incorreto** â€” `_extract_tournament_name()` agora conta jogadores Ãºnicos no arquivo HH: â‰¤ 9 = SNG (sem reposiÃ§Ã£o de mesa), > 9 = MTT (jogadores vindos de mesas quebradas); resolve badge "MTT" incorreto em Sit & Go PokerStars
- **Thresholds de nÃ­vel rebalanceados** â€” escala anterior era leniente demais (SÃ³lido comeÃ§ava em 75%); nova escala: Iniciante < 60%, Estudante 60â€“69%, Grinder 70â€“76%, Regular 77â€“85%, SÃ³lido 86â€“91%, Expert 92â€“95%, Elite 96%+; calibrada para que 83â€“85% std_pct = Regular

### Frontend
- `frontend/src/components/hud/SiteLogo.tsx` â€” componente novo com mapa de favicons e fallback de sigla
- `frontend/src/components/hud/RecentTournamentsTable.tsx` â€” logo inline, badge corrigido
- `frontend/src/pages/Tournaments.tsx` â€” coluna Rede vira logo; listener de reload pÃ³s-import
- `frontend/src/components/hud/UploadQueue.tsx` â€” dispara `CustomEvent('leaklab:tournament-imported')` apÃ³s cada upload concluÃ­do

### Backend
- `backend/database/repositories.py` â€” thresholds de `get_player_level()` atualizados
- `backend/api/app.py` â€” `_extract_tournament_name()` usa contagem de jogadores Ãºnicos para distinguir SNG de MTT

---

## [v0.20.0] â€” 2026-04-26 â€” UX-001: Nome e Tipo do Torneio na Lista

### Adicionado
- **Nome do torneio na lista de torneios** (UX-001) â€” substituÃ­do o par "site â€¢ nome do hero" pelo nome descritivo do torneio (ex: "Spin&Gold #14", "NLH $2.20"); badge "MTT" / "Spin&Go" ao lado do nome; subtext exibe site + ID interno para rastreabilidade
- Coluna `tournament_name TEXT` adicionada Ã  tabela `tournaments` (SQLite + PostgreSQL); migration automÃ¡tica via `_run_migrations`

### Backend
- `backend/api/app.py` â€” novo helper `_extract_tournament_name()`: GGPoker extrai nome do header (`Tournament #N, Spin&Gold #14 Hold'em`); PokerStars constrÃ³i label do buy-in (`NLH $2.20`); chamado no `/analyze` e persistido com o torneio
- `backend/database/repositories.py` â€” `save_tournament()` aceita `tournament_name`; `get_tournaments()` inclui o campo no SELECT
- `backend/database/schema.py` â€” coluna `tournament_name TEXT` nas definiÃ§Ãµes CREATE TABLE e nas migrations SQLite/Postgres

### Frontend
- `frontend/src/lib/api.ts` â€” `Tournament.tournament_name?: string | null` adicionado Ã  interface
- `frontend/src/components/hud/RecentTournamentsTable.tsx` â€” helper `formatTournamentLabel()` e `formatBadge()`; cÃ©lula "Torneio" exibe nome + badge de formato + subtext com site e ID
- `frontend/src/pages/coach/StudentDetail.tsx` â€” `TournamentsTab` usa `tournament_name ?? site` como label principal; subtext inclui site + ID

---

## [v0.19.0] â€” 2026-04-26 â€” BACK-008: Visualizador de Ranges + BUG-001: PrÃªmio de Torneio

### Adicionado
- **Visualizador de Ranges no Replayer** (BACK-008) â€” botÃ£o "Range" aparece durante o preflop; painel lateral 13Ã—13 com ranges GTO-aproximadas para 6 posiÃ§Ãµes (UTG, MP, HJ, CO, BTN, SB, BB); auto-detecta posiÃ§Ã£o do herÃ³i e contexto (open vs facing raise); seletor manual de posiÃ§Ã£o e tipo (Open Â· Call Â· 3-Bet); mÃ£o do herÃ³i destacada em amarelo; legenda com % de mÃ£os e contagem de combos

### Corrigido
- **BUG-001 â€” PrÃªmio incorreto em torneios PokerStars** â€” quando eliminado sem ITM, o arquivo PokerStars contÃ©m apenas "hero finished the tournament" sem prÃªmio; o cÃ³digo caÃ­a no fallback GGPoker que somava todos os chips coletados em potes normais do jogo como prÃªmio; fix: detecta "finished the tournament" antes do fallback e define `prize = 0.0`; torneios afetados devem ser reimportados

### Frontend
- `frontend/src/data/ranges.ts` â€” ranges GTO-aproximadas para Open/Call/3-Bet por posiÃ§Ã£o; expansor de notaÃ§Ã£o de range ("AA-77", "AKs-A2s"); utils `cellHand`, `cellLabel`, `heroHand`, `getCellAction`, `rangeStats`
- `frontend/src/components/replayer/RangeGrid.tsx` â€” grid 13Ã—13 com aspect-square, cores por aÃ§Ã£o (verde=raise, azul=call), destaque da mÃ£o do herÃ³i
- `frontend/src/components/replayer/RangePanel.tsx` â€” painel com auto-detecÃ§Ã£o de posiÃ§Ã£o/contexto, seletores de posiÃ§Ã£o e tipo, rodapÃ© com posiÃ§Ã£o detectada
- `frontend/src/pages/Replayer.tsx` â€” botÃ£o "Range" no header do Action Log (visÃ­vel apenas no preflop); importa `RangePanel` e `LayoutGrid`

### Backend
- `backend/api/app.py` â€” fix em `_extract_financials()`: PokerStars bust-out sem prÃªmio define `prize = 0.0` ao invÃ©s de somar chips coletados em potes

---

## [v0.18.0] â€” 2026-04-26 â€” Sprint 10: Sistema de NÃ­vel do Jogador / GamificaÃ§Ã£o (BACK-009)

### Adicionado
- **Sistema de nÃ­vel do jogador** â€” 7 nÃ­veis baseados no `standard_pct` mÃ©dio dos Ãºltimos 20 torneios (ou 30 dias): Iniciante, Estudante, Grinder, Regular, SÃ³lido, Expert, Elite; sem rÃ³tulos ofensivos; thresholds rebalanceados em v0.21.0
- **LevelCard** â€” componente visual com badge de nÃ­vel (Ã­cone + nome + cor por nÃ­vel), barra de progresso para o prÃ³ximo nÃ­vel, threshold do prÃ³ximo nÃ­vel, leaks que bloqueiam avanÃ§o; modo `compact` para uso no dashboard do coach; link para o plano de estudos (opcional)
- **Dashboard do jogador** â€” `LevelCard` exibido na sidebar do Index.tsx ao lado dos leaks e ICM
- **Dashboard do coach** â€” `LevelCard` em modo compacto na aba "VisÃ£o Geral" de cada aluno; query `coach-student-level`

### Backend
- `get_player_level(user_id, min_tournaments=5, days=30)` â€” calcula nÃ­vel, progresso (0-1), prÃ³ximo nÃ­vel, leaks bloqueadores, contagem de torneios usados
- `GET /metrics/level` â€” retorna nÃ­vel do prÃ³prio jogador
- `GET /coach/student/:id/level` â€” retorna nÃ­vel de um aluno (requer `@require_coach`)

### Frontend
- `LevelCard.tsx` â€” criado com cores por nÃ­vel, barra de progresso, leaks bloqueadores, CTA de plano de estudos
- `api.ts` â€” interface `PlayerLevel`; `metrics.level()`; `coachDashboard.studentLevel(studentId)`
- `Index.tsx` â€” query `player-level` com React Query; `LevelCard` na sidebar
- `StudentDetail.tsx` â€” query `coach-student-level`; `LevelCard` compacto no topo da `OverviewTab`

---

## [v0.17.0] â€” 2026-04-26 â€” Sprint 9: Upload MÃºltiplo com Fila + Perfil do Coach Unificado (BACK-007 + BACK-012)

### Adicionado
- **Upload mÃºltiplo de torneios** (BACK-007) â€” botÃ£o "Import" aceita mÃºltiplos arquivos `.txt` de uma vez; fila processa sequencialmente com badge de status por arquivo (`Em fila`, `Processandoâ€¦`, `Analisado âœ“`, `Erro`); painel flutuante no canto inferior direito com botÃ£o "Fechar" apÃ³s conclusÃ£o
- **Perfil do coach unificado** (BACK-012) â€” pÃ¡gina `/coach-dashboard/profile` reescrita com todos os campos estendidos do Sprint 7 (foto, experiÃªncia, stakes, mÃ©todo, idiomas, maiores resultados, preÃ§os, trial, redes sociais) + aba "AvaliaÃ§Ãµes" com distribuiÃ§Ã£o de ratings; abas "Perfil PÃºblico" e "AvaliaÃ§Ãµes" removidas do CoachDashboard

### Frontend
- `UploadQueue.tsx` â€” hook `useUploadQueue` + `QueuePanel` com `useReducer`; `fileMap` ref para mapear IDs aos `File` objetos sem poluir o estado
- `HudHeader.tsx` â€” input de upload agora com `multiple`; usa `useUploadQueue` ao invÃ©s de upload manual unitÃ¡rio; retorna `<>header + panel</>` via Fragment
- `CoachProfile.tsx` â€” reescrito completamente com `ProfileSection` + `AvaliacoesSection` internos; suprime a versÃ£o anterior com campos bÃ¡sicos apenas
- `CoachDashboard.tsx` â€” tabs "Perfil PÃºblico" e "AvaliaÃ§Ãµes" removidos; imports de lucide e tipos relacionados limpos

---

## [v0.16.0] â€” 2026-04-26 â€” Sprint 8: DiretÃ³rio PÃºblico de Coaches + IntegraÃ§Ã£o Contextual (BACK-006 pt.2 + BACK-013)

### Adicionado
- **DiretÃ³rio pÃºblico de coaches** (`/coaches`) â€” lista com filtros de especialidade, idioma, preÃ§o mÃ¡ximo, trial e ordenaÃ§Ã£o; barra de busca por nome; sidebar colapsÃ¡vel; grid responsivo
- **Perfil pÃºblico do coach** (`/coaches/:id`) â€” avatar, bio, especialidades, maiores resultados, distribuiÃ§Ã£o de avaliaÃ§Ãµes, reviews pÃºblicos, contato e links sociais; CTA contextual para vincular coach via chave de convite
- **Coaches no menu principal** â€” entrada "Coaches" adicionada ao `HudHeader` para jogadores
- **BACK-013 â€” Coaches contextuais no Plano de Estudos** â€” strip de coaches especializados no leak ativo, exibida somente para alunos sem coach; clique direciona ao perfil do coach
- **BACK-013 â€” Coaches no Perfil do aluno** â€” quando sem coach: lista top-3 coaches por rating + formulÃ¡rio de link por chave de convite; substitui botÃ£o antigo sem destino Ãºtil

### Backend
- `GET /coaches` aceita `specialty`, `language`, `trial`, `max_price`, `q`, `sort`, `limit` como filtros
- `GET /coaches/:id` retorna perfil completo + reviews pÃºblicos recentes
- `GET /coaches/:id/reviews` retorna reviews pÃºblicos paginados
- `GET /student/recommended-coaches` â€” endpoint para recomendaÃ§Ã£o futura (stub)

### Frontend
- `CoachesDirectory.tsx` â€” nova pÃ¡gina com `StarRow`, `CoachCard`, `FilterPanel`
- `PublicCoachProfile.tsx` â€” nova pÃ¡gina com distribuiÃ§Ã£o de rating, reviews, formulÃ¡rio de avaliaÃ§Ã£o (alunos vinculados) e CTA de contrataÃ§Ã£o
- `StudyPlan.tsx` â€” `CoachRecommendationStrip` + `CoachMiniCard` injetados no card de diagnÃ³stico de leaks
- `StudentProfile.tsx` â€” `NoCoachDiscovery` com `CoachDiscoveryCard` e formulÃ¡rio de invite key
- `HudHeader.tsx` â€” "Coaches" adicionado ao nav de jogadores

---

## [v0.15.0] â€” 2026-04-26 â€” Sprint 7: Perfil Estendido do Coach + Sistema de AvaliaÃ§Ãµes (BACK-006 pt.1)

### Adicionado
- **Aba "Perfil PÃºblico"** no CoachDashboard â€” formulÃ¡rio completo com foto, experiÃªncia, stakes, mÃ©todo de coaching, idiomas, maiores resultados, preÃ§os, disponibilidade e redes sociais; modo visualizaÃ§Ã£o / ediÃ§Ã£o inline
- **Aba "AvaliaÃ§Ãµes"** no CoachDashboard â€” aggregate de rating com barra de distribuiÃ§Ã£o por estrela + lista de reviews recebidas
- **AvaliaÃ§Ã£o de coach pelo aluno** â€” widget na pÃ¡gina de perfil do aluno (`StudentProfile`) com StarPicker, comentÃ¡rio opcional, ediÃ§Ã£o e exclusÃ£o; aparece somente quando hÃ¡ coach vinculado
- Tabela `coach_reviews` com constraint `UNIQUE(coach_id, student_id)` â€” 1 review por par aluno-coach

### Backend
- `coach_profiles`: 13 novos campos adicionados (`photo_url`, `experience_years`, `stakes`, `coaching_style`, `languages`, `biggest_results`, `price_per_session`, `price_monthly`, `trial_available`, `availability`, `social_youtube`, `social_twitch`, `social_twitter`)
- `GET /coach/profile` agora retorna `avg_rating` e `review_count` calculados em tempo real
- `POST /coach/review` â€” aluno envia/atualiza avaliaÃ§Ã£o (upsert por par coach-aluno)
- `DELETE /coach/review` â€” aluno remove sua avaliaÃ§Ã£o
- `GET /coach/my-review` â€” aluno consulta sua prÃ³pria avaliaÃ§Ã£o
- `GET /coach/reviews` â€” coach vÃª todas as avaliaÃ§Ãµes recebidas com stats detalhados
- Migrations automÃ¡ticas para SQLite e Postgres

---

## [v0.14.0] â€” 2026-04-26 â€” Sprint 6: Feed de Atividade + Baseline de Coaching (BACK-002)

### Adicionado
- **Aba "Progresso"** no perfil do aluno (coach) â€” baseline de coaching com comparaÃ§Ã£o antes/depois + feed de atividade em timeline
- **Baseline de coaching** â€” coach define data de inÃ­cio do acompanhamento; armazenado por par `(coach_id, student_id)` com nota opcional; editÃ¡vel/removÃ­vel
- **ComparaÃ§Ã£o antes/depois** â€” mÃ©tricas de score mÃ©dio, % decisÃµes standard e nÂ° de torneios separadas pela data baseline; leaks top-5 em cada perÃ­odo; lista de leaks resolvidos
- **Feed de atividade** â€” timeline de torneios do aluno com marcos automÃ¡ticos: "Melhora" (â†“5pts score), "RegressÃ£o" (â†‘5pts score), "Alta Qualidade" (â‰¥80% standard)
- Tabela `coach_baselines` no banco (SQLite e Postgres) com constraint `UNIQUE(coach_id, student_id)`

### Backend
- `GET/POST/DELETE /coach/student/:id/baseline` â€” gerenciar baseline de coaching
- `GET /coach/student/:id/activity-feed` â€” feed de torneios + marcos de performance (param `limit`)
- `GET /coach/student/:id/progress-report` â€” relatÃ³rio comparativo antes/depois da baseline
- Novos repositÃ³rios: `get_coach_baseline`, `set_coach_baseline`, `delete_coach_baseline`, `get_student_activity_feed`, `get_baseline_comparison`

### Frontend
- Ãcones `Activity, Flag, Star, BarChart2` adicionados
- Tipos `CoachBaseline, ActivityEvent, LeakSpot, PeriodMetrics, ProgressReport` em `api.ts`
- API functions `getBaseline`, `setBaseline`, `deleteBaseline`, `activityFeed`, `progressReport` em `coachDashboard`
- Componentes `ActivityTimeline`, `MetricsCompare`, `ProgressTab` em `StudentDetail.tsx`

---

## [v0.13.1] â€” 2026-04-26 â€” Combos de aÃ§Ã£o + classificaÃ§Ã£o coach + OpÃ§Ã£o C de reclassificaÃ§Ã£o

### Adicionado
- **Combo "AÃ§Ã£o Correta"** nas anotaÃ§Ãµes do coach â€” substituiu o campo livre por select com opÃ§Ãµes padrÃ£o do poker (fold, check, call, bet, raise, re-raise, all-in)
- **Combo "ClassificaÃ§Ã£o"** nas anotaÃ§Ãµes â€” coach pode atribuir o veredito da decisÃ£o: Jogada Correta / Marginal / Erro Pequeno / Erro Claro; campo `coach_override_label` armazenado no banco
- Badge visual do veredito exibido no balloon de anotaÃ§Ã£o (aluno e coach) e na listagem de "MÃ£os CrÃ­ticas"
- **OpÃ§Ã£o C implementada** â€” `coach_override_label` Ã© respeitado nas queries de `worst-decisions` do aluno: decisÃµes marcadas como "Jogada Correta" ou "Marginal" pelo coach saem da lista de mÃ£os crÃ­ticas; avg_score do torneio **nÃ£o** Ã© alterado (mÃ©tricas de performance permanecem do engine)

### Backend
- `coach_hand_annotations`: nova coluna `coach_override_label TEXT` â€” migrations automÃ¡ticas SQLite + Postgres
- `upsert_annotation` aceita e persiste `coach_override_label`
- `POST /coach/student/:id/hand-annotations` aceita e valida `coach_override_label`
- `GET /coach/student/:id/worst-decisions` usa `COALESCE(coach_override_label, label)` para filtrar â€” decisÃµes requalificadas pelo coach como corretas nÃ£o aparecem mais na lista de erros

---

## [v0.13.0] â€” 2026-04-26 â€” Sprint 5: AtenÃ§Ã£o Urgente + Leaks SistÃªmicos (BACK-003 + BACK-004)

### Adicionado
- **Aba "AtenÃ§Ã£o Urgente"** no Dashboard do Coach â€” tabela com as piores decisÃµes de **todos os alunos** ao mesmo tempo, com filtros por aluno, street e label (erro claro / erro pequeno); botÃ£o "Replay" abre diretamente o replay do aluno na mÃ£o errada
- **Aba "Leaks SistÃªmicos"** no Dashboard do Coach â€” lista de spots de erro agrupados por ocorrÃªncia, com destaque nos que afetam mÃºltiplos alunos ("Leaks sistÃªmicos") vs. individuais; cada spot Ã© expandÃ­vel para ver quais alunos sÃ£o afetados e quantas vezes
- **Filtro de perÃ­odo** (30/60/90 dias) na aba de Leaks SistÃªmicos
- Dashboard do Coach reorganizado em **3 abas**: Alunos (existente) Â· AtenÃ§Ã£o Urgente Â· Leaks SistÃªmicos

### Backend
- `repositories.py`: `get_all_students_worst_decisions(coach_id, n, student_id_filter, street_filter, label_filter)` â€” query cross-student com filtros dinÃ¢micos
- `repositories.py`: `get_common_leaks(coach_id, days)` â€” agrupa erros por spot e retorna lista de alunos afetados por spot
- `GET /coach/all-worst-decisions` â€” piores decisÃµes multi-aluno com filtros via query string
- `GET /coach/common-leaks` â€” leaks com breakdown por aluno

### Fix
- **AnotaÃ§Ãµes do coach nÃ£o apareciam no replay do aluno** â€” endpoint `GET /replay/<tournament_id>/<hand_id>` nÃ£o incluÃ­a `coach_annotations`; agora busca e injeta as anotaÃ§Ãµes do coach igual ao endpoint do coach student replay

---

## [v0.12.1] â€” 2026-04-26 â€” Fix: Replay para coaches + AnotaÃ§Ã£o direto no Replayer (BACK-001 complemento)

### Corrigido
- **Replay inacessÃ­vel para coaches** â€” rota `/replayer` estava envolvida em `ProtectedRoute` que redirecionava coaches para `/coach-dashboard`; criada `AuthRoute` que permite qualquer usuÃ¡rio autenticado acessar o replayer
- **ParÃ¢metro `student` perdido na navegaÃ§Ã£o de mÃ£os** â€” botÃµes "MÃ£o anterior" / "PrÃ³xima mÃ£o" no Replayer nÃ£o preservavam `?student=N` na URL; coach perdia o contexto e o replay passava a buscar dados do prÃ³prio jogador em vez do aluno

### Adicionado
- **Painel de anotaÃ§Ã£o do coach no Replayer** â€” quando o coach acessa o replay de um aluno e a etapa atual Ã© um erro do herÃ³i, o painel lateral exibe:
  - BotÃ£o "Anotar" (se sem anotaÃ§Ã£o) ou anotaÃ§Ã£o existente com botÃµes "Editar" / "Remover"
  - FormulÃ¡rio inline com seletor de modo (Complementar / Substituir IA), textarea de comentÃ¡rio e campo de jogada correta
  - Salvar atualiza o estado local imediatamente sem re-fetch da mÃ£o inteira
- **`decisions` em estado no Replayer** â€” decisÃµes do torneio sÃ£o mantidas em memÃ³ria para resolver `decision_id` de novos spots sem annotation existente (match por `hand_id + street + action_taken`)
- **BACK-007 adicionado ao backlog** â€” importaÃ§Ã£o mÃºltipla de torneios com fila + badge de progresso por arquivo

---

## [v0.12.0] â€” 2026-04-26 â€” Sprint 4: AnotaÃ§Ãµes de MÃ£os + Selo Coach (BACK-001 + BACK-005)

### Adicionado
- **AnotaÃ§Ãµes de mÃ£os pelo coach** â€” na aba "MÃ£os CrÃ­ticas" do perfil do aluno, o coach pode anotar qualquer decisÃ£o com dois modos:
  - **Complementar** â€” exibe a anÃ¡lise da IA + nota do coach empilhadas
  - **Substituir IA** â€” oculta a anÃ¡lise da IA, exibe apenas a nota do coach
- **Campo "Jogada correta"** â€” coach pode indicar a aÃ§Ã£o que considera correta para o spot anotado
- **Badge "Anotado"** â€” decisÃµes com anotaÃ§Ã£o exibem indicador visual na listagem
- **BalÃ£o do coach no Replayer** â€” ao chegar na aÃ§Ã£o anotada, o painel lateral exibe a nota do coach com destaque visual diferenciado do painel da IA
- **Selo "âœ“ Coach"** (BACK-005) â€” torneios revisados (com ao menos uma anotaÃ§Ã£o) ganham badge roxo "Coach" na lista de torneios do aluno

### Backend
- Tabela `coach_hand_annotations` (SQLite + PostgreSQL) com migration automÃ¡tica
- `repositories.py`: `get_annotations`, `get_annotations_for_decisions`, `upsert_annotation`, `delete_annotation`, `get_reviewed_tournament_ids`
- `GET /coach/student/:id/hand-annotations` â€” lista anotaÃ§Ãµes do coach para o aluno
- `POST /coach/student/:id/hand-annotations` â€” cria ou atualiza anotaÃ§Ã£o por decision_id
- `DELETE /coach/student/:id/hand-annotations/:decision_id` â€” remove anotaÃ§Ã£o
- Replay do coach (`/coach/student/:id/replay/...`) agora inclui `coach_annotations` na resposta
- `GET /history/tournaments` agora inclui `coach_reviewed: bool` por torneio

---

## [v0.11.1] â€” 2026-04-26 â€” CorreÃ§Ãµes de ambiente local + seguranÃ§a

### Corrigido
- **CORS local resolvido via Vite proxy** â€” todos os prefixos de API (`/auth`, `/history`, `/analyze`, `/study`, `/coach`, `/student`, `/tournaments`, `/replay`, `/metrics`, `/admin`, `/health`) sÃ£o roteados pelo proxy do Vite, eliminando erros de CORS no desenvolvimento
- **`get_user_by_id` nÃ£o importado** em `app.py` causava 500 em `/auth/me` â€” adicionado ao import
- **Coach redirecionado para `/coach-dashboard`** ao logar â€” `ProtectedRoute` agora redireciona coaches que tentam acessar rotas de aluno
- **Menu "Dashboard" do coach ficava ativo em `/coach-dashboard/profile`** â€” adicionado `end={true}` ao NavLink do dashboard do coach
- **Banner de vÃ­nculo nÃ£o sumia apÃ³s vincular coach** â€” `AcceptCoachModal` agora chama `refreshUser()` apÃ³s sucesso, atualizando `user.coach_id` imediatamente
- **`GET /coach/profile` retornava 404** quando perfil nÃ£o existia, causando loop de retentativas no `useQuery` â€” endpoint agora retorna `{}` (200)
- **Mensagens de erro no Login** â€” `TypeError` (ex: "Failed to fetch") exibe "NÃ£o foi possÃ­vel conectar ao servidor" em vez da mensagem tÃ©cnica bruta

### SeguranÃ§a
- **RemoÃ§Ã£o de vÃ­nculo com coach exige senha atual** â€” `DELETE /student/coach` agora requer `password` no body; backend verifica hash antes de desvincular
- `repositories.py`: nova funÃ§Ã£o `check_password(user_id, password)` reutilizÃ¡vel

---

## [v0.11.0] â€” 2026-04-26 â€” Perfil do aluno + seguranÃ§a de conta

### Adicionado
- **PÃ¡gina `/profile`** para alunos: alterar e-mail (com confirmaÃ§Ã£o de senha), trocar senha (verifica atual, mÃ­n. 8 chars), gerenciar vÃ­nculo de coach (remover com confirmaÃ§Ã£o dupla)
- **Header**: badge do coach vinculado visÃ­vel no topo quando aluno tem coach; link "Perfil" no nav do player
- **Plano de Estudos**: lock exibido sempre que o aluno tem coach vinculado (nÃ£o sÃ³ quando hÃ¡ overrides), mostrando o nome do coach
- **Banner de vÃ­nculo** no Dashboard: oculto quando aluno jÃ¡ tem coach vinculado

### Corrigido
- `/auth/me` agora retorna `coach_id` e `coach_username` â€” frontend usa para controle de acesso sem chamadas extras

### Backend
- `POST /auth/update-email` â€” atualiza e-mail apÃ³s verificar senha atual
- `POST /auth/change-password` â€” verifica senha atual antes de atualizar
- `DELETE /student/coach` â€” remove vÃ­nculo com coach
- `repositories.py`: `update_user_email`, `change_user_password`, `unlink_student_coach`

---

## [v0.10.2] â€” 2026-04-25 â€” Plano de estudos com fonte Ãºnica (canonical plan)

### Corrigido
- **Importar torneio nunca apaga o plano** â€” o plano de estudos sÃ³ Ã© substituÃ­do por aÃ§Ã£o explÃ­cita ("Gerar com IA" pelo aluno ou "Gerar novo plano" pelo coach)
- **Aluno com coach nÃ£o pode regerar** â€” backend bloqueia `?new=1` se o aluno tiver coach vinculado
- **Overrides do coach aplicados no plano do aluno** â€” cards substituÃ­dos/comentados pelo coach jÃ¡ chegam modificados para o aluno via `/study/plan`, alinhando o conteÃºdo visto por ambos
- **Coach â€” StudyCardItem exibe recursos completos** (livros, vÃ­deos, curso) para equiparar ao nÃ­vel de detalhe do plano do aluno
- **Coach â€” "Substituir" gerencia recursos**: formulÃ¡rio de substituiÃ§Ã£o inclui campos para livros (um por linha), vÃ­deos (um por linha) e curso â€” coach pode indicar material prÃ³prio
- Recursos substituÃ­dos pelo coach sÃ£o aplicados no plano do aluno via backend
- **Plano de estudos inconsistente entre aluno e coach**: aluno e coach agora compartilham o mesmo plano armazenado por chave estÃ¡vel `study_plan_current` no banco â€” nÃ£o mais por hash dos dados, que podia divergir quando os dados mudavam entre as geraÃ§Ãµes
- **BotÃ£o "Gerar com IA"** agora forÃ§a de fato uma nova geraÃ§Ã£o (`?new=1`), sobrescrevendo o plano anterior no banco â€” antes apenas re-buscava o cache sem regenerar

### Adicionado
- **Coach â€” botÃ£o "Gerar novo plano"** na aba Plano de Estudos: gera um plano novo via IA para o aluno e o torna o plano canÃ´nico â€” o aluno passa a ver exatamente este plano
- ParÃ¢metro `force_new` em `generate_study_plan()` e nos dois endpoints (`/study/plan?new=1`, `/coach/student/:id/study-plan?new=1`)

---

## [v0.10.1] â€” 2026-04-25 â€” MÃ£os CrÃ­ticas com cartas + lock coach_managed

### Adicionado
- **WorstTab (MÃ£os CrÃ­ticas)**: cada decisÃ£o agora exibe:
  - ID da mÃ£o (`hand_id`)
  - Cartas do herÃ³i como `PlayingCard` (tamanho sm)
  - Board cards (quando disponÃ­veis)
- **Lock "Gerar com IA"** na tela do aluno: quando o coach tem overrides no plano, o botÃ£o Ã© substituÃ­do por "Gerenciado pelo Coach" com Ã­cone de cadeado
- **Backend `/study/plan`**: responde `coach_managed: true` quando existem overrides do coach para o aluno

---

## [v0.10.0] â€” 2026-04-25 â€” Sprint 3: Coach Study Plan + Comparativo HistÃ³rico

### Adicionado
- **Coach Study Plan interativo**: cada card do plano IA tem 3 aÃ§Ãµes do coach:
  - **Validar** (âœ“) â€” marca o card como aprovado (badge verde)
  - **Comentar** (ðŸ’¬) â€” abre textarea inline para nota visÃ­vel ao aluno (badge Ã¢mbar)
  - **Substituir** (âœï¸) â€” formulÃ¡rio inline para reescrever tÃ­tulo, diagnÃ³stico e exercÃ­cio (badge roxo)
  - BotÃ£o de remover anotaÃ§Ã£o (Ã­cone lixeira)
  - Resumo de status no topo: "X validados Â· Y comentados Â· Z substituÃ­dos"
- **Comparativo histÃ³rico** no OverviewTab:
  - Score mÃ©dio e Standard% â€” primeiros 3 vs Ãºltimos 3 torneios
  - Delta com indicador visual: melhorou / piorou / estÃ¡vel
  - Total de torneios no perÃ­odo
- **Backend**: tabela `coach_study_overrides` (SQLite + PostgreSQL) com UNIQUE(coach_id, student_id, card_spot)
- **3 endpoints**: `GET/POST /coach/student/:id/study-overrides`, `DELETE /coach/student/:id/study-overrides/:spot`
- **Fixes**: replay link no WorstTab (`?tid=` â†’ `?t=`), nome do aluno no header (era "Aluno #N")

---

## [v0.9.0] â€” 2026-04-25 â€” Sprint 2: Coach Full Student View

### Adicionado
- **6 novos endpoints backend** para o coach acessar dados completos do aluno:
  - `GET /coach/student/:id/stats` â€” HUD stats (VPIP, PFR, AF, 3BET%, W$SDâ€¦)
  - `GET /coach/student/:id/breakdown` â€” performance por street e posiÃ§Ã£o
  - `GET /coach/student/:id/tournament/:tid` â€” detalhe de torneio + decisÃµes
  - `GET /coach/student/:id/worst-decisions` â€” piores N decisÃµes do aluno
  - `GET /coach/student/:id/study-plan` â€” plano de estudos IA do aluno
  - `GET /coach/student/:id/replay/:tid/:hid` â€” replay de mÃ£o do aluno
- **StudentDetail.tsx** totalmente reescrito com 4 abas:
  - **VisÃ£o Geral**: HUD Stats (8 indicadores), grÃ¡fico de evoluÃ§Ã£o, leaks, performance por street (bar chart) e por posiÃ§Ã£o
  - **Torneios**: lista completa clicÃ¡vel â†’ detalhe com tabela de decisÃµes + botÃ£o "Ver Replay"
  - **MÃ£os CrÃ­ticas**: fila das 30 piores decisÃµes (score, street, posiÃ§Ã£o, ICM, M-ratio, aÃ§Ã£o vs. correto) com link direto ao replay
  - **Plano de Estudos**: plano IA gerado para o aluno, com cards de prioridade alta/mÃ©dia/baixa
- **Replayer.tsx**: suporte ao parÃ¢metro `?student=<id>` â€” usa endpoint do coach em vez do endpoint do jogador

---

## [v0.8.0] â€” 2026-04-25 â€” Sprint 1: Sistema Professor/Aluno

### Adicionado
- **Login/registro com papel**: toggle "Jogador / Professor" na tela de registro; papel enviado ao backend via `role` no body
- **Rotas por papel**: `CoachRoute` em `App.tsx` â€” professores sÃ£o redirecionados para `/coach-dashboard`; jogadores bloqueados de rotas de coach
- **`/coach-dashboard`**: dashboard do professor com stats (alunos, ativos 30d, melhoria mÃ©dia, melhor aluno), lista de alunos com tendÃªncia e link para detalhe
- **`/coach-dashboard/student/:id`**: histÃ³rico do aluno â€” grÃ¡fico de evoluÃ§Ã£o (recharts), tabela de leaks, torneios recentes
- **`/coach-dashboard/profile`**: formulÃ¡rio para o professor configurar nome, bio, especialidades, e-mail/link de contato
- **Chave de convite** (`InviteKeyWidget`): exibida no dashboard do professor com botÃ£o de cÃ³pia
- **Banner "Vincular Professor"** no dashboard do jogador com `AcceptCoachModal` para inserir a chave de convite
- **NavegaÃ§Ã£o condicional** no `HudHeader`: professores veem "Dashboard + Perfil"; jogadores veem nav padrÃ£o; botÃ£o Import oculto para professores

---

## [v0.7.0] â€” 2026-04-25 â€” HUD Stats completo + GGPoker

### Adicionado
- **Player HUD Stats** (8 indicadores): VPIP, PFR, AF, Flop Bet%, Fold-to-3BET, WTSD, **3BET%** e **W$SD** â€” todos computados a partir das decisÃµes armazenadas
- **3BET%**: detectado quando hero re-raised prÃ©-flop com `facing_size > 0`; coluna `is_3bet` na tabela `decisions`
- **W$SD**: detectado via `hero: shows` no raw_text (showdown real do hero); coluna `showdown_result` na tabela `decisions`
- **GGPoker parser**: suporte completo ao formato GGPoker â€” detecÃ§Ã£o automÃ¡tica por header, IDs `#SG.../#RC...`, hero sempre `Hero`
- **Fix hero detection GGPoker**: `HERO_DEALT_RE` usa `[^\[\n]+` para nÃ£o capturar mÃºltiplas linhas

### Corrigido
- `_normalize_action()` converte `'raises'` â†’ `'raise'`; verificaÃ§Ã£o `is_3bet` corrigida para os valores normalizados
- `_detect_showdown()` verifica `"hero: shows"` em vez de `"SHOW DOWN"` â€” elimina falsos positivos quando hero foldou
- `llm_explainer.py`: `e.get('field', 0)` retornava `None` quando campo existe com valor `None`; corrigido para `(e.get('field') or 0)` em 4 mÃ©tricas de evoluÃ§Ã£o
- Opacidade das cÃ©lulas "em breve" no HUD elevada de `/25` para `/50` (visÃ­veis)

---

## [2026-04-25e] â€” HUD Stats: fix 3BET e W$SD (normalize action + showdown participation)

### Corrigido
- **`backend/leaklab/pipeline.py`**: `is_3bet` verificava `'raises'/'all-in'` mas `_normalize_action()` converte para `'raise'/'jam'`; corrigido para os valores normalizados
- **`backend/api/app.py`**: `_detect_showdown()` agora verifica se hero mostrou cartas (`hero: shows`) em vez de apenas se houve showdown na mÃ£o â€” elimina falsos positivos quando hero foldou mas outros jogadores foram a showdown (reduz de ~100 para ~24 showdowns reais)

---

## [2026-04-25d] â€” HUD Stats: 3BET% e W$SD implementados

### Adicionado
- **`backend/database/schema.py`**: colunas `is_3bet BOOLEAN` e `showdown_result TEXT` na tabela `decisions`; migrations adicionadas para SQLite e PostgreSQL
- **`backend/leaklab/pipeline.py`**: flag `is_3bet` calculada em `build_decision_input` â€” True quando hero re-raised prÃ©-flop com `facing_size > 0` (alguÃ©m jÃ¡ tinha apostado antes)
- **`backend/api/app.py`**: funÃ§Ã£o `_detect_showdown(raw_text, hero)` detecta se mÃ£o foi a showdown e se hero coletou o pote; `is_3bet` e `showdown_result` propagados no enriched dict e salvos no banco
- **`backend/database/repositories.py`**: `save_decisions` inclui `is_3bet` e `showdown_result`; `get_player_stats` computa 3BET% (hands com is_3bet / total preflop hands) e W$SD (hands won at showdown / total showdown hands)
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: 3BET e W$SD removidos de `soon: true`; tipos atualizados para `number | null`; tooltips revisados
- **`frontend/src/lib/api.ts`**: `three_bet` e `w_at_sd` tipados como `number | null`

---

## [2026-04-25c] â€” HUD Stats: fix visibilidade cÃ©lulas "em breve" (3BET, W$SD)

### Corrigido
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: cÃ©lulas 3BET e W$SD estavam invisÃ­veis â€” opacidades do status `na` elevadas de `/25`â†’`/50` (valor), `/40`â†’`/60` (label e "em breve"), `/30`â†’`/50` (ref MTT); cÃ©lulas ficam visivelmente "desabilitadas" mas legÃ­veis

---

## [2026-04-25b] â€” GGPoker parser: suporte completo + fix hero detection

### Adicionado
- **`backend/leaklab/parser.py`**: suporte a GGPoker â€” detecÃ§Ã£o automÃ¡tica por header (`Poker Hand #`), split regex por site, ID regex `#(\w+)` para prefixos SG/RC/HD; funÃ§Ã£o `parse_hand_history()` unificada detecta site e parseia qualquer arquivo
- **`backend/api/app.py`**: `_detect_site()` atualizado para reconhecer GGPoker; `_extract_financials()` soma `collected X from pot` do hero para calcular prize em Spin & Go

### Corrigido
- **`backend/leaklab/parser.py`**: `HERO_DEALT_RE` alterado de `[^\[]+` para `[^\[\n]+` â€” impedia que o nome do hero capturasse mÃºltiplas linhas `Dealt to` de oponentes no formato GGPoker, onde cada jogador tem sua prÃ³pria linha

### Alterado
- **`CLAUDE.md`**: menÃ§Ã£o ao suporte a GGPoker adicionada Ã  descriÃ§Ã£o do projeto

---

## [2026-04-25a] â€” Player HUD Stats como strip full-width + LeaksPanel compacto

### Alterado
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: redesenhado como strip horizontal full-width com 4 cÃ©lulas (VPIP, PFR, AF, Flop Bet) separadas por dividers; header com contagem de mÃ£os; responsivo 2Ã—2 em mobile e 4Ã—1 em desktop
- **`frontend/src/components/hud/LeaksPanel.tsx`**: redesenhado como lista compacta â€” cada leak ocupa uma linha de ~36px com dot de severidade, label truncado, badge de contagem e botÃ£o Estudar inline; eliminados o card grande com parÃ¡grafo de descriÃ§Ã£o
- **`frontend/src/pages/Index.tsx`**: `PlayerStatsCard` movido para entre os KPIs e o grid principal (full-width, destaque mÃ¡ximo); removido do sidebar

---

## [2026-04-24d] â€” Player HUD Stats: VPIP, PFR, Aggression Factor, Flop Bet%

### Adicionado
- **`backend/database/repositories.py`**: nova funÃ§Ã£o `get_player_stats(user_id, days)` que agrega decisÃµes por mÃ£o e computa VPIP, PFR, AF (Aggression Factor) e Flop Bet% diretamente das decisÃµes armazenadas
- **`backend/api/app.py`**: novo endpoint `GET /metrics/player-stats?days=N` que retorna o perfil de jogo calculado
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: novo card HUD exibindo as 4 stats computÃ¡veis (VPIP, PFR, AF, Flop Bet%) com barra de progresso colorida vs. referÃªncia MTT; 4 stats futuras (3BET, Fold to 3BET, WTSD, W$SD) exibidas como "Em breve" com tooltip explicativo
- **`frontend/src/lib/api.ts`**: interface `PlayerStatsResponse` e mÃ©todo `metrics.playerStats(days)`
- **`frontend/src/pages/Index.tsx`**: `PlayerStatsCard` adicionado Ã  sidebar do dashboard

### ReferÃªncias MTT usadas
| Stat | Ref MTT | Status |
|------|---------|--------|
| VPIP | 12â€“22% | âœ… Calculado |
| PFR | 9â€“18% | âœ… Calculado |
| AF | 2.0â€“4.0x | âœ… Calculado |
| Flop Bet | 40â€“65% | âœ… Calculado |
| 3BET | 4â€“8% | ðŸ”œ Em breve |
| Fold to 3BET | 55â€“72% | ðŸ”œ Em breve |
| WTSD | 25â€“35% | ðŸ”œ Em breve |
| W$SD | 50â€“60% | ðŸ”œ Em breve |

---

## [2026-04-24c] â€” Cartas do villain reveladas no momento do "shows", nÃ£o sÃ³ no showdown final

### Corrigido
- **`backend/api/app.py`**: `_build_replay_data` agora prÃ©-escaneia o `raw_text` para linhas `player: shows [cards]` e acumula `current_revealed` conforme as aÃ§Ãµes ocorrem; `revealed_cards` Ã© incluÃ­do em cada step de action e street (nÃ£o apenas no step final de showdown)
- **`frontend/src/pages/Replayer.tsx`**: `buildSeats()` verifica `step.revealed_cards` em qualquer tipo de step, sem depender de `step.type === 'showdown'`; `revealed: true` Ã© setado assim que o backend sinaliza as cartas

---

## [2026-04-24b] â€” Showdown na mesa + apostas posicionadas dentro da mesa

### Corrigido
- **`frontend/src/components/hud/PokerTable.tsx`**: cartas dos villains agora exibidas no showdown â€” nova prop `revealed` em `Seat`; condiÃ§Ã£o `hidden` alterada para `!seat.hero && !seat.revealed`; chips de aposta movidos para fora do `SeatBubble` e renderizados como elementos absolutamente posicionados entre o assento e o centro da mesa via `betPosition(sx, sy, 0.42)`
- **`frontend/src/pages/Replayer.tsx`**: `buildSeats()` agora passa `revealed: true` para assentos de villain no step de showdown quando `revealed_cards` estÃ¡ presente

---

## [2026-04-24a] â€” Replayer conectado ao backend + botÃµes de replay nas mÃ£os

### Adicionado
- **`frontend/src/pages/Replayer.tsx`**: reescrito para consumir dados reais do backend via `GET /replay/<t>/<h>`; usa `useSearchParams` para ler `?t=` e `?h=` da URL; exibe mesa de poker com assentos, pot e board reais por step; log de aÃ§Ãµes com hero em destaque e erros marcados; painel de EV/feedback com equity, pot odds, M ratio e pressÃ£o ICM; estados de loading, erro e sem-parÃ¢metros
- **`frontend/src/lib/api.ts`**: interfaces `ReplaySeat`, `ReplayStep`, `ReplayData`; mÃ©todo `tournaments.replay(tournamentId, handId)` â†’ `GET /replay/:t/:h`
- **`frontend/src/pages/TournamentDetail.tsx`**: botÃ£o "Abrir no replayer" em cada card de mÃ£o (navega para `/replayer?t=<id>&h=<handId>`); botÃ£o "Replay completo" agora clicÃ¡vel (navega para primeira mÃ£o do torneio); link "Replayer" compacto na linha de aÃ§Ãµes quando anÃ¡lise IA jÃ¡ estÃ¡ carregada

### Corrigido
- **`frontend/src/pages/TournamentDetail.tsx`**: referÃªncia a `h.resultBb` (campo inexistente) substituÃ­da por `h.evDelta`

---

## [2026-04-23b] â€” UI leaklabs: onboarding, detalhe de torneio, AI Report

### Adicionado
- **`frontend/src/components/hud/EmptyDashboard.tsx`**: tela de onboarding para novos usuÃ¡rios â€” upload com drag-and-drop conectado ao `POST /analyze`, cards dos 3 mÃ³dulos com estilo `tactical-corners`, dispara `onComplete` para refresh do dashboard
- **`frontend/src/components/hud/TournamentAiReport.tsx`**: painel lateral deslizante de anÃ¡lise IA por torneio â€” chama `POST /analyze/tournament-summary` com `tournament_db_id`, exibe resumo cacheado (`llm_summary`) se jÃ¡ existir, seÃ§Ãµes colapsÃ¡veis em markdown com tonal por tipo (erro/ponto forte/neutro)
- **`frontend/src/pages/TournamentDetail.tsx`**: pÃ¡gina de detalhe de torneio â€” agrupa decisÃµes por mÃ£o (`groupByHand`), filtra por severidade e street, exibe cartas com `PlayingCard`, integra `TournamentAiReport` com ID real do banco
- **`frontend/src/index.css`**: variÃ¡veis CSS para cartas (`--card-face`, `--card-suit-dark`, `--card-suit-red`) e utilitÃ¡rio `.tactical-corners` com pseudo-elementos de canto

### Alterado
- **`frontend/src/lib/api.ts`**: adicionado tipo `TournamentDecision`; `tournaments.get()` retorna `{ tournament, decisions }`
- **`frontend/src/App.tsx`**: rota `/tournaments/:id` com `TournamentDetail` protegida por auth
- **`frontend/src/components/hud/HudHeader.tsx`**: branding atualizado de "PokerLeaks.os" â†’ "LeakLabs.ai"; item "Replayer" removido da navegaÃ§Ã£o
- **`frontend/src/pages/Index.tsx`**: exibe `EmptyDashboard` quando nÃ£o hÃ¡ torneios importados (primeiro acesso)
- **`frontend/src/pages/Tournaments.tsx`**: clique em linha navega para `/tournaments/:tournament_id`

---

## [2026-04-23a] â€” IntegraÃ§Ã£o completa backend + frontend React

### Adicionado
- **`frontend/src/lib/auth.tsx`**: contexto React de autenticaÃ§Ã£o (`AuthProvider`, `useAuth`) â€” gerencia token JWT via `sessionStorage`, verifica `/auth/me` na inicializaÃ§Ã£o, expÃµe `login`, `register`, `logout`
- **`frontend/src/pages/Login.tsx`**: pÃ¡gina de login/registro com tabs, design HUD, mensagem de erro inline e redirecionamento automÃ¡tico se jÃ¡ autenticado
- **`frontend/.env`**: variÃ¡vel `VITE_API_URL=http://localhost:5000` para dev local
- **`backend/api/app.py` â€” `POST /coach/chat`**: endpoint conversacional do AI Coach; carrega leaks e evoluÃ§Ã£o reais do usuÃ¡rio, chama `coach_chat_reply` e retorna a resposta do LLM
- **`backend/api/app.py` â€” `GET /coach/context`**: retorna `hands_analyzed`, `tournaments_analyzed`, `top_leaks`, `avg_score` e `standard_pct` do usuÃ¡rio para o painel de contexto do Coach
- **`backend/leaklab/llm_explainer.py` â€” `coach_chat_reply`**: funÃ§Ã£o de chat conversacional com Claude Haiku; injeta dados reais de desempenho do jogador como contexto no system prompt

### Alterado
- **`frontend/src/App.tsx`**: adicionado `AuthProvider`, rota `/login` e `ProtectedRoute` (redireciona para `/login` se nÃ£o autenticado) em todas as pÃ¡ginas internas
- **`frontend/src/components/hud/HudHeader.tsx`**: exibe username do usuÃ¡rio logado e botÃ£o de logout; `LogOut` icon via lucide-react
- **`frontend/src/pages/AICoach.tsx`**: conectado ao backend â€” carrega contexto via `GET /coach/context` na montagem, saudaÃ§Ã£o inicial personalizada com dados reais, chat conectado a `POST /coach/chat` com loading state e scroll automÃ¡tico
- **`frontend/src/components/hud/UploadZone.tsx`**: lÃª arquivo como texto, chama `POST /analyze`, exibe feedback visual (loading â†’ ok â†’ erro) e dispara callback `onResult` para refresh do dashboard
- **`frontend/src/components/hud/LeaksPanel.tsx`**: aceita prop `leaks` da API; mapeia `avg_score` para severidade (crÃ­tico/moderado/leve); fallback para dados demo quando sem dados reais
- **`frontend/src/components/hud/BankrollChart.tsx`**: aceita prop `evolution` da API; plota lucro cumulativo real; fallback para dados demo
- **`frontend/src/components/hud/RecentTournamentsTable.tsx`**: aceita prop `tournaments` da API; formata datas, profit e place reais; fallback para dados demo
- **`frontend/src/pages/Index.tsx`**: busca `GET /history/evolution` e `GET /history/tournaments` na montagem; calcula KPIs reais (ROI, ITM%, Avg Buy-In, Total Eventos); refresh automÃ¡tico apÃ³s upload
- **`frontend/src/pages/Tournaments.tsx`**: carrega lista real via `GET /history/tournaments`; loading state, filtro por rede e ordenaÃ§Ã£o funcional com dados reais

---

## [2026-04-23i] â€” MigraÃ§Ã£o frontend para React + TypeScript

### Alterado
- **Frontend migrado de HTML monolÃ­tico para React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui**
  - Base: projeto gerado pelo Lovable (poker-leak-finder) trazido para `frontend/`
  - `frontend/index.legacy.html` â€” backup do frontend vanilla anterior
  - `frontend/src/` â€” novo frontend React com arquitetura componentizada
  - `vercel.json` atualizado para build com `@vercel/static-build`
  - `.gitignore` atualizado: `frontend/node_modules/`, `frontend/dist/`

### MotivaÃ§Ã£o
- SeguranÃ§a: HTML monolÃ­tico sem isolamento de escopo, JWT exposto em JS inline, sem CSP
- Manutenibilidade: arquivo Ãºnico de ~3000 linhas impossÃ­vel de auditar e testar
- Arquitetura componentizada elimina classes de bugs de DOM stale e permite testes unitÃ¡rios

### PrÃ³ximos passos
- Conectar API client (`src/lib/api.ts`) ao backend Flask
- Implementar autenticaÃ§Ã£o (contexto JWT, rotas protegidas)
- Substituir dados mock por chamadas reais ao backend

---

## [2026-04-23h]

### Corrigido
- **BotÃ£o "Gerar Resumo" sem aÃ§Ã£o**: `tSummaryLoaded` persiste em memÃ³ria durante toda a sessÃ£o do browser. Torneios com o mesmo PokerStars ID (apÃ³s reset/reimport) bloqueavam silenciosamente a funÃ§Ã£o `generateTSummary` na linha `if(tSummaryLoaded[tid])return`. Corrigido limpando o objeto em `_renderTournamentList` sempre que a lista Ã© re-renderizada.

---

## [2026-04-23g]

### Corrigido
- **Coach IA retornava template estÃ¡tico**: `_call_llm_summary` usava `_json.dumps()` mas o mÃ³dulo foi importado como `json`. O `NameError` era silenciado pelo `except Exception`, fazendo o sistema cair sempre no fallback estÃ¡tico. Corrigido para `json.dumps()`.

---

## [2026-04-23f]

### Corrigido
- **Coach IA â€” "Torneio nÃ£o encontrado no banco"**: apÃ³s importar um torneio, o objeto inserido em `tourns[]` em `_applyRealData` nÃ£o tinha o campo `dbId` mapeado. O frontend buscava `tObj.dbId` para enviar ao endpoint `/analyze/tournament-summary`, encontrava `undefined` e mostrava o erro. Adicionado `dbId: data.tournament_db_id` ao objeto construÃ­do apÃ³s a anÃ¡lise.

---

## [2026-04-23e]

### Corrigido
- **Frontend `API_URL` com `file://`**: ao abrir `index.html` diretamente do sistema de arquivos, `location.hostname` Ã© `''` (string vazia) e a detecÃ§Ã£o de `localhost` falhava, direcionando todas as chamadas para o servidor de produÃ§Ã£o (Render). Adicionada verificaÃ§Ã£o `!h` para cobrir o protocolo `file://`.

---

## [2026-04-23d]

### Corrigido
- **`load_dotenv` com caminho absoluto**: substituÃ­do `os.path.dirname(__file__)` por `Path(__file__).resolve().parent` em `app.py` para evitar falha no subprocess do Flask reloader que nÃ£o resolvia caminhos relativos corretamente.
- **Timeout do study plan**: aumentado de 30s para 90s em `llm_explainer.py`; chamadas ao Claude Haiku para geraÃ§Ã£o de plano com 400+ decisÃµes podem ultrapassar 30s.

### Resultado
- Study plan com LLM funcional localmente: 6 cards gerados, resumo personalizado, `error: null`.

---

## [2026-04-23c]

### Adicionado
- **`backend/.env`** (gitignored): variÃ¡veis de ambiente para dev local (`ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`).
- **`python-dotenv`** adicionado a `requirements_dev.txt`; `app.py` carrega `.env` automaticamente via `load_dotenv()` na inicializaÃ§Ã£o.

---

## [2026-04-23b]

### Adicionado
- **`backend/requirements_dev.txt`**: dependÃªncias para desenvolvimento local sem `psycopg2-binary` (incompatÃ­vel com Python 3.13/Windows); ambiente local usa SQLite.

### Ambiente local
- Backend: `cd backend && python api/app.py` â†’ `http://localhost:5000`
- Frontend: abrir `frontend/index.html` no browser (detecta `localhost` automaticamente e aponta para porta 5000)

---

## [2026-04-23]

### Corrigido
- **Imports `gaphunter` â†’ `leaklab`**: 7 arquivos de teste importavam o nome antigo do pacote (`gaphunter`), causando `ModuleNotFoundError` em toda a suite `engine` e `regression`.
- **Coluna `raw_text` ausente no schema SQLite**: a coluna existia apenas na migraÃ§Ã£o PostgreSQL; adicionada ao `CREATE TABLE` e Ã  lista de migraÃ§Ãµes SQLite em `database/schema.py`, corrigindo 8 falhas na suite `database`.

### Adicionado
- **`CLAUDE.md`**: documentaÃ§Ã£o para Claude Code com comandos de build/teste, arquitetura e stack.
- **`CHANGELOG.md`**: este arquivo.
- **`.gitignore`**: entradas para `backend/torneio_ingles.txt` (fixture local com dados pessoais) e `.claude/` (configuraÃ§Ã£o do Claude Code).

### Resultado
- Testes: **227/227 passando** (todas as suites: engine, database, llm, api, regression).

