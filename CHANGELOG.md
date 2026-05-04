# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Unreleased]

---

## [v0.54.0] — 2026-05-03 — Sprint W: FEAT-11 Weekly Digest Email

### Added
- **`backend/leaklab/email_digest.py`**: módulo de digest semanal — `build_digest_data` (coleta métricas dos últimos 7 dias: standard%, EV loss, drill atrasado, precisão), `build_digest_html` (template dark responsivo com EV bar visual), `send_digest_email` (SMTP via smtplib nativo com STARTTLS), `run_weekly_digest` (itera inscritos e envia). Sem dependências extras além da stdlib.
- **`backend/database/schema.py`**: coluna `digest_subscribed INTEGER NOT NULL DEFAULT 0` na tabela `users` (SQLite + Postgres migration).
- **`backend/database/repositories.py`**: `get_digest_subscribers` (usuários com `digest_subscribed=1` e `last_login` nos últimos 30 dias), `update_digest_subscription`.
- **`backend/api/app.py`**: `POST /player/digest/subscribe`, `POST /player/digest/unsubscribe` (autenticado), `GET /player/digest/unsubscribe` (link do email com token HMAC), `POST /admin/send-digest`; campo `digest_subscribed` incluído na resposta de `/auth/me`.
- **`frontend/src/lib/api.ts`**: campo `digest_subscribed` em `UserProfile`; módulo `digest` com `subscribe()` e `unsubscribe()`.
- **`frontend/src/pages/Index.tsx`**: banner de opt-in contextual — visível para players com dados que ainda não ativaram o digest; dispensável pelo X; botão "Ativar" chama `digest.subscribe()` e atualiza o perfil via `refreshUser()`.

---

## [v0.53.0] — 2026-05-03 — Sprint V: FEAT-09 Coach Templates + FEAT-10 Coach Messaging

### Added
- **`backend/database/schema.py`**: tabela `coach_plan_templates` (id, coach_id, name, target_archetype, cards_json) e `coach_messages` (id, coach_id, student_id, body, sender_role, decision_id, read_at) — SQLite + Postgres.
- **`backend/database/repositories.py`**: `get_coach_templates`, `create_coach_template`, `delete_coach_template`; `send_coach_message`, `get_coach_messages`, `mark_messages_read`, `get_unread_message_count`.
- **`backend/api/app.py`**: endpoints `GET/POST /coach/templates`, `DELETE /coach/templates/<id>`; `GET/POST /coach/student/<id>/messages`; `GET/POST /player/coach/messages`, `GET /player/messages/unread`.
- **`frontend/src/lib/api.ts`**: interfaces `CoachTemplate`, `CoachMessage`; métodos em `coachDashboard` (getTemplates, createTemplate, deleteTemplate, getMessages, sendMessage); módulo `playerMessages` (list, send, unreadCount).
- **`frontend/src/pages/coach/StudentDetail.tsx`**: aba "Mensagens" com chat bidirecional em tempo real (polling 15s), badge de não lidas na aba, botão "Salvar como template" nos cards substituídos do plano de estudos.
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: painel colapsável de chat para o player na página do AI Coach — mostra conversa com coach humano vinculado, badge de não lidas, envio via Enter.
- **`frontend/src/pages/AICoach.tsx`**: `CoachMessagesPanel` integrado na sidebar, visível apenas quando `user.coach_id` está presente.
- **`frontend/src/components/hud/HudHeader.tsx`**: badge de não lidas no header (ícone `MessageSquare` com contador) para players com coach vinculado — polling 60s, link para `/coach`.

---

## [v0.52.0] — 2026-05-03 — Sprint U: FEAT-08 Session Goals + AI Review

### Added
- **`backend/database/schema.py`**: tabela `session_goals` (SQLite + Postgres) — `id`, `user_id`, `goal_leak_spot`, `target_standard_pct`, `notes`, `tournament_id` (nullable), `llm_review`, `created_at`, `linked_at`.
- **`backend/database/repositories.py`**: `create_session_goal`, `link_session_goal`, `get_pending_session_goal`, `get_session_goal_by_tournament`, `save_session_review`.
- **`backend/leaklab/llm_explainer.py`**: `generate_session_review(goal, tournament)` — Claude Haiku (~300 tokens) compara meta pré-sessão com resultado real; 3 frases: atingiu/não atingiu meta, ponto técnico relevante, recomendação para próxima sessão. Fallback `_template_session_review` determinístico.
- **`backend/api/app.py`**: endpoints `POST /player/session-goals`, `GET /player/session-goals/pending`, `POST /player/session-goals/<id>/link`, `GET /player/session-review/<tournament_id>` (gera e persiste review on-demand).
- **`frontend/src/lib/api.ts`**: interfaces `SessionGoal`, `SessionReviewResponse`; métodos `metrics.createSessionGoal`, `metrics.pendingSessionGoal`, `metrics.linkSessionGoal`, `metrics.sessionReview`.
- **`frontend/src/components/hud/UploadQueue.tsx`**: `SessionGoalPanel` exportado — painel colapsável com campos spot de foco, meta de standard% e anotação livre; persiste goal ID em `sessionStorage`; hook `useUploadQueue` lê `ll_pending_goal` do `sessionStorage` após upload e chama `metrics.linkSessionGoal` automaticamente.
- **`frontend/src/pages/Index.tsx`**: `SessionGoalPanel` integrado ao dashboard (visível apenas para players).
- **`frontend/src/pages/TournamentDetail.tsx`**: card "Review da Sessão" exibido após narrativa quando há meta vinculada — mostra spot de foco, meta vs resultado real com indicador ✓/✗, review gerado por IA e anotação livre do jogador.

---

## [v0.51.0] — 2026-05-03 — Sprint T: FEAT-07 Coach Effectiveness Metrics

### Added
- **`backend/database/repositories.py`**: `get_coach_effectiveness_report(coach_id)` — itera todos os alunos com baseline, chama `get_baseline_comparison` por aluno, calcula delta de `standard_pct`, melhora mediana, % com melhora positiva e badge público (visível com ≥3 alunos e mediana positiva).
- **`backend/api/app.py`**: endpoint `GET /coach/effectiveness` (autenticado como coach). Perfil público `GET /coaches/<id>` passa a incluir `effectiveness_badge` e `effectiveness_median_delta`.
- **`frontend/src/lib/api.ts`**: interfaces `EffectivenessStudent`, `EffectivenessSummary`, `CoachEffectivenessReport`; módulo `coachEffectiveness` com método `report()`.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: aba "Efetividade" com 3 KPI cards (alunos analisados, melhora mediana, % com melhora), preview do badge público com indicação "visível no perfil público", tabela por aluno com before/after `standard_pct`, delta colorido e leaks corrigidos.
- **`frontend/src/pages/PublicCoachProfile.tsx`**: badge "Alunos melhoram +Xpp em standard_pct" exibido na seção de badges do perfil público quando disponível.

---

## [v0.50.0] — 2026-05-03 — Sprint S: FEAT-06 Leak Causal Map

### Added
- **`backend/leaklab/leak_causal_graph.py`**: `build_leak_graph(rows)` — analisa co-ocorrência de leaks entre torneios, calcula correlação de Jaccard por par (threshold 35%), retorna nós com `severity` (critical/moderate/minor por avg_score) e arestas ordenadas por correlação; label compacto (`PF Fold`, `FL Bet`, etc.); nós incluem `degree` (número de conexões).
- **`backend/leaklab/llm_explainer.py`**: `explain_leak_causality(edges, hero)` — 1 chamada Claude Haiku (~150 tokens) gerando 2-3 frases de diagnóstico causal para os 3 pares mais correlacionados; cache em memória por combinação de pares; fallback `_template_causality()` determinístico.
- **`backend/database/repositories.py`**: `get_leak_graph_data(user_id, days)` — busca todas as decisões com mistake do usuário no período, chama `build_leak_graph` e `explain_leak_causality`, retorna `{nodes, edges, narrative}`.
- **`backend/api/app.py`**: endpoint `GET /player/leak-graph?days=90`.
- **`frontend/src/lib/api.ts`**: interfaces `LeakGraphNode`, `LeakGraphEdge`, `LeakGraphResponse`; método `metrics.leakGraph(days)`.
- **`frontend/src/components/hud/LeakCausalMap.tsx`**: card com grafo SVG circular — nós coloridos por severidade (vermelho/âmbar/verde), arestas com espessura e opacidade proporcionais à correlação; interação: clique no nó destaca suas conexões e exibe detalhe com lista de co-ocorrências; narrativa LLM abaixo do grafo; legenda de cores.
- **`frontend/src/pages/Index.tsx`**: `LeakCausalMap` inserido após `LeaksPanel` quando há ≥ 3 nós; `metrics.leakGraph(90)` carregado no mount.

---

## [v0.49.0] — 2026-05-03 — Sprint R: FEAT-05 SRS Adaptativo nos Drills

### Added
- **`backend/database/schema.py`**: colunas `next_drill_at TEXT` e `srs_interval_days INTEGER DEFAULT 3` em `drill_sessions` (Postgres + SQLite migrations).
- **`backend/database/repositories.py`**: `save_drill_session` reescrito com lógica SRS — acerto dobra o intervalo (`3d → 7d → 14d → 28d → 60d`, cap em 60), erro reseta para 3 dias; calcula `next_drill_at = now + interval` e persiste ambos os campos. `get_drill_spots` reescrito — substitui filtro de `drilled_at >= 7 days` por LEFT JOIN na sessão mais recente por decisão, filtra por `next_drill_at IS NULL OR next_drill_at <= now`, ordena por mais atrasado primeiro; calcula `days_overdue` em Python (compatível SQLite + Postgres).
- **`backend/api/app.py`**: endpoint `POST /player/spots/drill/submit` passa a retornar `next_drill_at` e `srs_interval_days`.
- **`frontend/src/lib/api.ts`**: `DrillSpot` com campos `next_drill_at`, `srs_interval_days`, `days_overdue`; `DrillSubmitResult` com `next_drill_at` e `srs_interval_days`.
- **`frontend/src/pages/GhostTable.tsx`**: badge "próxima revisão em X dias" (verde=acerto, amarelo=reset) no card de resultado após cada drill; badge de dias de atraso discreto (vermelho/amarelo) na barra de progresso do spot ativo.
- **`frontend/src/components/hud/GhostDrillCard.tsx`**: prop `pendingSpots` opcional — exibe contador "N atrasados" com ícone Clock no header do card quando há spots vencidos.
- **`frontend/src/pages/Index.tsx`**: carrega `drill.spots({ limit: 20 })` no mount e passa `pendingSpots` para `GhostDrillCard`.

---

## [v0.48.0] — 2026-05-03 — Sprint Q: FEAT-02 Daily Focus + FEAT-03 XP Server-Side

### Added
- **`backend/database/schema.py`**: migrações para `xp_total INT DEFAULT 0`, `xp_streak INT DEFAULT 0`, `xp_last_activity DATE`, `daily_focus_done_at DATE` na tabela `users`; nova tabela `achievements` (`user_id`, `achievement_id`, `unlocked_at`).
- **`backend/database/repositories.py`**: `get_daily_focus(user_id)` — lógica determinística (zero LLM) que combina top EV-loss leak, drill com cooldown expirado e torneio não revisado; retorna `{primary, secondary[], valid_until, completed, streak}`. `mark_daily_focus_done(user_id)` — persiste data de conclusão. `add_xp(user_id, event_type, amount?)` — streak server-side: +1 se último XP foi ontem, reset se mais antigo; checa conquistas automaticamente via `_check_and_grant_achievements()`. `get_xp_status(user_id)`, `get_achievements(user_id)`. `_XP_AMOUNTS` (`tournament_imported=50`, `exercise_correct=10`, `drill_completed=25`, `drill_mastered=100`). 5 conquistas: `first_tournament`, `decisions_100`, `first_drill`, `streak_7`, `tournaments_10`.
- **`backend/api/app.py`**: 5 novos endpoints — `GET /player/daily-focus`, `POST /player/daily-focus/complete`, `GET /player/xp`, `POST /player/xp`, `GET /player/achievements`.
- **`frontend/src/components/hud/DailyFocusCard.tsx`**: card de foco diário — exibe ação primária e 2 secundárias com link direto; timer countdown até meia-noite; estado "concluído" com streak de dias; usa `useQuery` + `useMutation` via React Query.
- **`frontend/src/lib/api.ts`**: interfaces `DailyFocusData`, `DailyFocusAction`, `XpStatus`, `Achievement`; métodos `metrics.dailyFocus()`, `metrics.completeDailyFocus()`, `metrics.xpStatus()`, `metrics.addXp(event_type)`, `metrics.achievements()`.
- **`frontend/src/pages/Index.tsx`**: `DailyFocusCard` inserido acima da seção de KPIs (visível apenas quando há torneios importados).
- **`frontend/src/pages/StudyPlan.tsx`**: `metrics.addXp("exercise_correct")` disparado a cada resposta correta em exercício (fire-and-forget).
- **`frontend/src/components/hud/UploadQueue.tsx`**: `metrics.addXp("tournament_imported")` disparado após upload bem-sucedido de torneio.

---

## [v0.47.0] — 2026-05-03 — Sprint P: FEAT-04 Relatório PDF Premium

### Added
- **`backend/leaklab/report_generator.py`**: redesign completo — `build_html_report(t, decisions, phases, hero)` gera template HTML premium com Inter/JetBrains Mono (Google Fonts), paleta dark profissional, gráficos CSS puros (barras, indicadores de score coloridos por threshold). Seções: capa com hero + torneio + meta pills, KPI row (Standard%, Avg Score, Clear Mistakes%, Decisões), Quality Distribution com barras + referência MTT saudável, Phase Breakdown (Deep/Mid/Short Stack/Push/Fold), Top 5 Leaks com barra proporcional e score colorido, Performance por ICM Pressure, Top 10 Decisões Críticas com label badges.
- **`generate_pdf_bytes(html)`**: converte HTML para PDF via WeasyPrint; levanta `ImportError` se a lib não estiver disponível — o endpoint faz fallback automático para download HTML.
- **`backend/Dockerfile`**: adicionadas dependências de sistema para WeasyPrint — `libpango`, `libcairo2`, `libgdk-pixbuf2.0-0`, `libpangocairo`, `libffi-dev`, `fonts-liberation`.
- **`render.yaml`**: migrado de `runtime: python` para `runtime: docker` (necessário para instalar as dependências de sistema do WeasyPrint no Render).
- **`backend/requirements.txt`**: `weasyprint==62.3`.
- **`backend/api/app.py`**: endpoint `GET /history/tournament/<id>/report.pdf` — retorna PDF (`application/pdf`) ou HTML como fallback se WeasyPrint não disponível; `Content-Disposition: attachment`.
- **`frontend/src/lib/api.ts`**: `tournaments.downloadReport(tournamentId)` — fetch binário com auth header, cria blob URL e dispara download automaticamente.
- **`frontend/src/pages/TournamentDetail.tsx`**: botão "PDF" (ícone `FileDown`) ao lado do botão Replay; estado `pdfDownloading` com spinner enquanto gera.

### Changed
- **`backend/leaklab/report_generator.py`**: `generate_report()` (legacy) mantida e intacta para compatibilidade com callers existentes.

---

## [v0.46.0] — 2026-05-03 — Sprint O: FEAT-01 Comparativo de Torneios

### Added
- **`backend/database/repositories.py`**: `get_tournaments_comparison(user_id, ids)` — agrega por torneio: `standard_pct`, `avg_score`, `clear_pct`, hands/decisions count, profit, buy_in, place, phase breakdown e top 5 leaks; `_compute_comparison_leaks(decisions)` — calcula média de score por spot para o ranking de leaks.
- **`backend/leaklab/llm_explainer.py`**: `generate_comparison_narrative(items)` — narrativa comparativa de 2 frases via Claude Haiku (max 100 tokens); cache por `cmp_{id1}_{id2}...`; fallback `_template_comparison()` calcula delta de `standard_pct` entre primeiro e último torneio.
- **`backend/api/app.py`**: endpoint `GET /history/tournaments/compare?ids=A,B,C` — valida 2–4 IDs, retorna `{items: TournamentComparison[], narrative}`.
- **`frontend/src/lib/api.ts`**: interface `TournamentComparison` e método `tournaments.compare(ids)`.
- **`frontend/src/pages/TournamentCompare.tsx`**: página de comparativo lado a lado — componentes `Delta` (trend ±) e `QualityBar` (barra colorida por threshold); seções: narrativa LLM, cards de cabeçalho por torneio, tabela de qualidade (Standard%/Avg Score/Clear Mistakes%), phase breakdown (Deep/Mid/Short Stack/Push-Fold), top leaks com destaque amarelo para leaks compartilhados entre torneios; badge "▲ melhor" no melhor valor de cada métrica.
- **`frontend/src/pages/Tournaments.tsx`**: multi-seleção de 2–4 torneios via checkboxes (desktop e mobile); CTA "Comparar N torneios" com ícone aparece ao selecionar ≥ 2 itens; navega para `/tournaments/compare?ids=...`.
- **`frontend/src/App.tsx`**: rota `/tournaments/compare` adicionada antes de `/tournaments/:id`.
- **`backend/database/repositories.py`**: labels de fase de M-ratio padronizadas para inglês — `Deep Stack`, `Mid Stack`, `Short Stack`, `Push/Fold` (era PT-BR).

### Changed
- **`frontend/src/pages/TournamentDetail.tsx`**: tooltips das fases atualizados para inglês (Deep Stack / Mid Stack / Short Stack / Push/Fold).

---

## [v0.45.0] — 2026-05-03 — Sprint M: PERF-008 Tournament Narrative Engine

### Added
- **`backend/leaklab/llm_explainer.py`**: `generate_tournament_narrative(tournament_id, ctx)` — gera 2-3 frases descrevendo o arco de qualidade da sessão via Claude Haiku (max 130 tokens); cache em memória por `tournament_id`; fallback determinístico `_template_narrative()` se LLM indisponível.
- **`backend/api/app.py`**: endpoint `GET /history/tournament/<id>/narrative` — retorna `{narrative, quality_level}` (solid/regular/poor derivado de `standard_pct`); helper `_build_narrative_context()` agrega label counts, top leaks, ICM breakdown e pior fase do torneio.
- **`frontend/src/lib/api.ts`**: `tournaments.narrative(id)` → `{narrative, quality_level}`.
- **`frontend/src/pages/TournamentDetail.tsx`**: seção "Narrativa da Sessão" inline (entre stats grid e phase analysis) — badge de qualidade colorido + texto narrativo gerado pelo LLM, carregado automaticamente ao abrir o torneio.
- **`frontend/src/i18n/locales/*/tournaments.json`**: chaves `detail.narrative.*` em PT-BR, EN e ES.

---

## [v0.44.0] — 2026-05-03 — UX: LeaksPanel layout + PlayerDnaCard radar fix

### Changed
- **`LeaksPanel.tsx`**: redesign do layout de cada item — nome do leak em linha própria (sem truncate), badges reorganizadas com `justify-between` — n× badge e EV loss à esquerda como grupo, botão **Estudar** sempre ancorado à direita; elimina hack de `flex-1` spacer e overflow em cards com muitos badges simultâneos.
- **`PlayerDnaCard.tsx`**: corrige label "Disciplina" cortada no gráfico radar — `outerRadius="65%"` + margens aumentadas (`top:15 right:35 bottom:20 left:35`); remove `truncate` desnecessário nas labels do grid de stats.

---

## [v0.43.0] — 2026-05-03 — Sprint L: PERF-007 Decision DNA

### Backend — PERF-007

- **`repositories.py`** — `get_player_dna(user_id, days)`: agrega `decisions` em 5 métricas normalizadas (0-100):
  - `aggression_index` — % de ações que são raise/bet/jam (excluindo folds)
  - `fold_frequency` — % global de folds
  - `three_bet_pct` — % de preflop decisions com `is_3bet = True`
  - `positional_awareness` — diferencial de agressividade BTN/CO vs UTG/EP (escala 0-100, 50 = neutro)
  - `discipline` — standard% geral
  - `icm_awareness` (opcional) — ratio de standard% sob alta pressão ICM vs sem pressão ICM
  - `_classify_archetype()`: classifica em TAG / LAG / Nit / Calling Station / Balanced a partir das métricas
- **`app.py`** — `GET /player/dna?days=N`: retorna `{dna, sample_size}`; requer auth

### Frontend — PERF-007

- **`PlayerDnaCard.tsx`** (novo) — card com radar chart pentagon (Recharts RadarChart), badge de arquétipo colorido por tipo, grid de 6 métricas, descrição contextual do arquétipo; estado vazio com mensagem quando sample_size < 10
- **`pages/Index.tsx`** — fetch paralelo de `metrics.dna(90)`; `<PlayerDnaCard>` inserido entre o grid `RecentForm+DecisionQuality` e `BankrollChart`
- **`lib/api.ts`** — interfaces `PlayerDna`, `PlayerDnaResponse`; `metrics.dna(days)`

### i18n — 3 locales (pt-BR / en / es)

- `dashboard.json` — seção `dna.*`: title, tooltip, archetype label, sampleSize, noData, 6 axis labels, 5 archetype names + descriptions

### BACKLOG

- Sprint L (PERF-007) concluída; Sprint M (PERF-008 Tournament Narrative) e Sprint N (PERF-009 GGPoker Parser) aguardam priorização

---

## [v0.42.0] — 2026-05-03 — Sprint K pt.2: Ghost Table UX + Engine Notes + Drill-Dashboard Loop

### Backend — Ghost Table enhancements

- **`schema.py`** — colunas `pot_size REAL` e `facing_bet REAL` adicionadas à tabela `decisions` (SQLite + PostgreSQL, com migration automática)
- **`repositories.py`** — `save_decisions()`: extrai `potSize`/`facingSize` do `spot` e armazena em BB dividindo por `level_bb`; `get_drill_spots()`: inclui `pot_size` e `facing_bet` no SELECT; `get_decision_for_drill()`: expandido para retornar todos os campos necessários pelo `analyze_single_decision()`; `get_leak_roi_impact()`: JOIN com `drill_sessions` — adiciona `drill_count` e `drill_accuracy` por spot
- **`app.py`** — Bug fix crítico em `_analyze_hands()`: `enriched` dict agora inclui `'spot': di['spot']` (sem isso `pot_size`/`facing_bet` eram sempre `None`); `_GENERIC_NOTES` + `_enrich_note(row)`: detecta 3 strings genéricas legadas e as substitui por notas específicas geradas dos campos do banco (street, position, stack_bb, facing_bet, pot_size, m_ratio, ICM, label, score, action gap); aplicado em `history_tournament` e `coach_student_tournament`; novo endpoint `GET /player/drill-stats` (resumo leve sem carregar spots); novo endpoint `GET /player/spots/drill/<id>/analysis` com cache na tabela `llm_cache` (chave `drill_analysis:{decision_id}`) — chama Claude Haiku apenas na primeira vez
- **`decision_engine_v11.py`** — `build_interpretation()` reescrito: notas vazias para `standard`/`marginal`; para `small_mistake`/`clear_mistake` gera nota específica usando equity diff, draw context, M-Ratio zone, ICM pressure, range zone + position, facing bet context; sempre termina com "Ação esperada: X."

### Frontend — Ghost Table UX

- **`GhostTable.tsx`** — board cards limitados por street (preflop = 0, flop = 3, turn = 4, river = 5) para não revelar cartas futuras; `pot_size` e `facing_bet` em BB adicionados ao SituationBox; nota do motor movida da fase `active` para a fase `result` (não influencia decisão); renomeado "Análise da IA" → "Análise do Motor"; botão "Ver análise desta mão" (BookOpen) na fase result com `requestAnalysis()` → `drill.analysis(id)`; estado `analysis` e `analysisLoading` gerenciados; ações "JAM" renomeadas para "All-In" nas 3 locales
- **`GhostDrillCard.tsx`** (novo) — card sidebar no dashboard: mostra total de spots treinados, acerto %, avg delta dos últimos 30 dias; estado vazio com CTA "Iniciar drill" para `/ghost`
- **`LeaksPanel.tsx`** — badge "Treinando" (cinza) ou "Dominando" (primária) quando `drill_count > 0`; badge "Crítico" ocultado quando spot em treino; tooltip mostra `Ghost Table: Nx treinado (X% acerto)`
- **`pages/Index.tsx`** — fetch paralelo de `metrics.drillStats(30)`; `<GhostDrillCard stats={drillStats} />` inserido entre LevelCard e LeaksPanel

### i18n — 3 locales (pt-BR / en / es)

- **`ghost.json`** — chaves: `context.pot`, `context.facing`, `result.engineNote`, `result.requestAnalysis`, `result.analysisLoading`, `result.analysisError`, `situation.*`; `actions.jam` → "All-In"
- **`dashboard.json`** — chaves: `leaks.drillPracticing`, `leaks.drillMastering`, `ghost.title`, `ghost.spots`, `ghost.accuracy`, `ghost.continueStudy`, `ghost.noActivity`, `ghost.startNow`

### Removido

- **`backend/leaklab/mercadopago_gateway.py`** — arquivo legado do gateway Mercado Pago (migrado para Stripe em v0.29.0); removido para limpar o repositório

---

## [v0.41.0] — 2026-05-03 — Sprint K: PERF-006 Ghost Table Simulator MVP

### Backend — PERF-006
- `schema.py` — `drill_sessions` table (id, user_id, decision_id, new_action, new_score, original_score, delta, drilled_at) — SQLite + PostgreSQL
- `repositories.py` — `get_drill_spots()`: fetches undrilled mistake decisions (7-day cooldown); `save_drill_session()`: persists re-decision with score delta; `get_drill_stats()`: 30-day accuracy/total/avg_delta; `get_decision_for_drill()`: ownership-verified decision fetch
- `app.py` — `GET /player/spots/drill`: returns spots + stats; `POST /player/spots/drill/submit`: evaluates new_action vs best_action, scores 0.02 if correct else original_score

### Frontend — PERF-006
- `GhostTable.tsx` — full drill page with state machine (intro → loading → active → result → done): spot context card (street/ICM/position/stack/M-ratio/cards/board), 6 action buttons, result reveal, session accuracy, done screen
- `App.tsx` — `/ghost` route with `ProtectedRoute`
- `HudHeader.tsx` — "Ghost Table" nav item (Swords icon) for playerNavItems
- `i18n/locales/[pt-BR|en|es]/ghost.json` — new namespace (63 keys: drill UI, actions, result messages, stats)
- `i18n/locales/[pt-BR|en|es]/common.json` — `nav.ghost` key added
- `api.ts` — `DrillSpot`, `DrillStats`, `DrillSubmitResult` interfaces + `drill.spots()` + `drill.submit()`

---

## [v0.40.0] — 2026-05-03 — Sprint J: PERF-003+004+005 Leak Progression + Pressure Collapse + Drift

### Backend — PERF-003: Leak Progression (trend)

- **`repositories.py`** — `get_leak_roi_impact()` estendido: compara avg_score dos últimos 30 dias vs. 30-60 dias anteriores por spot; retorna `trend`: `improving` / `stagnant` / `regressing` / `new`

### Backend — PERF-004: Pressure Collapse Detection

- **`repositories.py`** — `get_pressure_profile(user_id, days)`: baseline score geral + avg_score por `icm_pressure`; calcula `collapse_delta = score_high - score_none`; flag `has_collapse` se delta > 0.08
- **`app.py`** — `GET /player/pressure-profile`

### Backend — PERF-005: Confidence Drift Monitor

- **`repositories.py`** — `get_confidence_drift(user_id, days=30)`: detecta torneios com avg_score > baseline × 1.30; retorna `drift_detected`, `severity` (mild/moderate/severe), lista de sessões afetadas
- **`app.py`** — `GET /player/confidence-drift`

### Frontend — Sprint J completo

- **`lib/api.ts`** — interfaces `PressureProfile`, `ConfidenceDrift`; `metrics.pressureProfile()`, `metrics.confidenceDrift()`; `LeakRoiData` expandido com campo `trend`
- **`components/hud/PressureProfileCard.tsx`** — novo card: barras de mistake_score por pressão ICM, badge "Colapso" / "Sólido", delta summary
- **`components/hud/LeaksPanel.tsx`** — ícones de tendência (↓ melhorando / → estagnado / ↑ regredindo) por leak
- **`pages/Index.tsx`** — fetch paralelo de `pressureProfile` + `confidenceDrift`; banner de alerta dismissível quando drift detectado; `PressureProfileCard` no sidebar
- **Locales** — chaves `pressure.*`, `drift.*` e `leaks.trend*` adicionadas a `dashboard.json` (PT-BR + EN + ES)

## [v0.39.0] — 2026-05-03 — Sprint I: PERF-001 + PERF-002 ROI Attribution + Leak Priority

### Backend — PERF-001: ROI Attribution Engine

- **`repositories.py`** — `get_leak_roi_impact(user_id, days)`: query enriquecida com `AVG(t.buy_in)`, `priority_score = n × avg_score`, `ev_loss_monthly = (n×30/days) × avg_score × avg_buy_in × 0.10`; ordenada por `priority_score DESC`
- **`app.py`** — `GET /player/leak-roi`: endpoint protegido por `@require_auth`; importa `get_leak_roi_impact`

### Frontend — PERF-001 + PERF-002

- **`lib/api.ts`** — interface `LeakRoiData` com campos `ev_loss_monthly`, `priority_score`, `priority_rank`; `metrics.leakRoi(days)`
- **`pages/Index.tsx`** — fetch paralelo de `leakRoi`; passa ao `LeaksPanel` quando disponível
- **`components/hud/LeaksPanel.tsx`** — custo mensal estimado por leak (`~$X/mês`); badge `CRÍTICO` com ícone chama para `priority_rank ≤ 3`
- **Locales** — chaves `leaks.critical` e `leaks.evLoss` adicionadas a `dashboard.json` (PT-BR + EN + ES)

### Backlog

- **`BACKLOG.md`** — roadmap atualizado com Sprint I (🔄), J, K (📋); specs completos de PERF-001 a PERF-006

## [v0.38.0] — 2026-05-03 — Sprint H: UX-007 Dashboard i18n — cards traduzidos

### Frontend — Dashboard cards i18n (bug fix)

- **`LeaksPanel.tsx`** — `spotLabel()` movido para dentro do componente; `t("leaks.*")` para título, botão estudar e descrição de leak
- **`BankrollChart.tsx`** — botões de período, título e estado vazio via `t("bankroll.*")`
- **`RecentTournamentsTable.tsx`** — cabeçalhos, status (Analisado/Em fila) e `formatDate` com `i18n.language` dinâmico
- **`DecisionQualityCard.tsx`** — array `LABELS` movido para dentro do componente; todos os rótulos via `t("decisions.*")`
- **`StreetBreakdown.tsx`** — título, tooltip e estado vazio via `t("streets.*")`
- **`PositionChart.tsx`** — título, tooltip e estado vazio via `t("positions.*")`
- **`RecentForm.tsx`** — `scoreDot()` movido para dentro do componente; legenda e título via `t("form.*")`
- **`IcmBreakdown.tsx`** — `ICM_LABEL` movido para dentro do componente; rótulos de pressão ICM e título via `t("icm.*")`
- **`LevelCard.tsx`** — nível, progresso, leaks bloqueadores e link de estudo via `t("level.*")`; pluralização i18next (`tournament_one`/`tournament_other`)
- **`EmptyDashboard.tsx`** — array `MODULES` movido para dentro do componente; upload section e módulos via `t("empty.*")`
- **`PlayerStatsCard.tsx`** — "em breve", "sem dados", "mãos" e mensagem vazia via `t("playerStats.*")`
- **Locales** — ~80 novas chaves adicionadas a `dashboard.json` (PT-BR + EN + ES)

## [v0.37.0] — 2026-05-02 — Sprint G: UX-006 Header Cleanup + i18n Full Coverage

### Frontend — Header simplification

- **`HudHeader.tsx`** — removidos badges (NEW/ALPHA) dos itens de nav, pill "Engine Active" e pill com nome do coach
- **`Index.tsx`** — coach badge movido para a seção hero do dashboard (abaixo do subtítulo), com ícone `GraduationCap` e ring sutil

### Frontend — i18n cobertura completa (5 novos namespaces, 3 idiomas)

- **Novos namespaces** — `aicoach`, `coaches`, `profile`, `replayer`, `landing` (PT-BR + EN + ES)
- **`NotFound.tsx`** — traduzido via `common.notFound.*`
- **`AICoach.tsx`** — traduzido via namespace `aicoach`; sugestões, saudação, painel de contexto e sessão
- **`Tournaments.tsx`** — traduzido; badges de formato, stats, cabeçalhos de tabela, estados vazios
- **`TournamentDetail.tsx`** — traduzido; `SEVERITY_META` e `FILTERS` movidos para dentro do componente; `ScoreLabel` inline
- **`StudyPlan.tsx`** — traduzido; toolbar, KPIs, diagnóstico, roadmap semanal, recursos, botões de dia
- **`CoachesDirectory.tsx`** — traduzido; `SORT_OPTIONS` movido para dentro de `FilterPanel`
- **`PublicCoachProfile.tsx`** — traduzido; loading, não encontrado, botão voltar, contadores
- **`StudentProfile.tsx`** — traduzido; títulos de seção, coach linkado, botões de unlink
- **`Replayer.tsx`** — traduzido; navegação de mãos, controles, action log, painel EV, formulário de anotação de coach, resultado do showdown
- **`Landing.tsx`** — traduzido completamente; arrays `PLANS`, `HOW_IT_WORKS`, `FEATURES` movidos para dentro dos sub-componentes; cada seção usa `useTranslation("landing")`
- **Locales atualizados** — `tournaments.json` + `common.json` + `study.json` com novas chaves; `landing.json` reescrito com estrutura completa (planos, CTA, footer)

---

## [v0.36.0] — 2026-05-02 — Sprint D: BACK-016 WhatsApp Coaching Drills

### Backend

- **`leaklab/whatsapp_bot.py`** — módulo do bot: `send_text()` (Cloud API v19), `handle_incoming()` (dispatcher), `_handle_answer()` (correção MCQ), `_send_question()` (busca top leak e gera exercício), `_generate_exercise()` (Claude Haiku → JSON com question/answer/explanation), `_fallback_exercise()` (template local sem LLM); estado de questões pendentes em dict in-memory por número
- **`api/app.py`** — 3 novas rotas:
  - `GET /whatsapp/webhook` — verificação de webhook pelo Meta (hub.challenge)
  - `POST /whatsapp/webhook` — recebe eventos Meta, despacha para `handle_incoming()`; sempre retorna 200 imediato
  - `PATCH /profile/phone` — vincula/desvincula número de WhatsApp ao usuário logado (validação E.164, unicidade)
  - `GET /auth/me` — agora retorna `whatsapp_phone`
- **`database/schema.py`** — migration `ALTER TABLE users ADD COLUMN whatsapp_phone TEXT UNIQUE` (Postgres + SQLite)
- **`database/repositories.py`** — `get_user_by_phone(phone)` + `update_user_phone(user_id, phone)`
- **`.env`** — adicionado `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`, `WHATSAPP_VERIFY_TOKEN`

### Frontend

- **`lib/api.ts`** — `auth.updatePhone(phone)` → `PATCH /profile/phone`; `UserProfile.whatsapp_phone` adicionado ao tipo
- **`pages/StudentProfile.tsx`** — nova seção "WhatsApp — Coaching Drills": campo para inserir número (formato DDI+DDD), botão Salvar e botão Desvincular; mostra número atual vinculado
- **`frontend/.env`** — `VITE_WHATSAPP_NUMBER=15556305701` (número sandbox Meta; substituir pelo número real em produção)

### Fluxo
1. Usuário vincula número em Perfil → WhatsApp
2. Clica "Iniciar no WhatsApp" no StudyPlan → abre conversa com o bot
3. Qualquer mensagem → bot busca top leak, gera MCQ via Claude Haiku, envia a questão
4. Usuário responde A/B/C/D → bot corrige e explica
5. Próxima mensagem → novo exercício

---

## [v0.35.0] — 2026-05-02 — Sprint F: UX-005 Internacionalização (i18n) PT/EN/ES

### Frontend

- **`i18n/index.ts`** — setup `i18next` + `i18next-browser-languagedetector`; auto-detecta via `localStorage` → `navigator.language`; fallback `pt-BR`; namespaces: `common`, `dashboard`, `tournaments`, `study`, `auth`
- **`main.tsx`** — importa `./i18n` para inicializar antes do React
- **Locales PT-BR** — `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **Locales EN** — `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **Locales ES** — `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **`HudHeader.tsx`** — `LanguageSwitcher` dropdown (🇧🇷 PT · 🇺🇸 EN · 🇪🇸 ES) no canto direito; nav labels e botão Import traduzidos via `t()`; preferência salva em `localStorage` (`leaklab_lang`)
- **`Login.tsx`** — labels, placeholders e estados de loading traduzidos via namespace `auth`
- **`Index.tsx`** — eyebrow, título, subtítulo, KPIs, AI Confidence e footer traduzidos via namespaces `dashboard` + `common`

---

## [v0.34.0] — 2026-05-02 — Sprint C+E: BACK-014 + BACK-017 Revenue Share + Admin Panel

### Backend

- **`schema.py`** — novo campo `users.referral_coach_id` + `users.suspended`; nova tabela `coach_payments` (coach_id, period YYYY-MM, active_students, amount_cents, status, paid_at) em SQLite e PostgreSQL via `_run_migrations`
- **`auth.py`** — novo decorator `require_admin()` que valida `role == 'admin'` no banco
- **`repositories.py`** — novas funções: `calculate_coach_payout()` (lógica de revenue share), `get_admin_dashboard_stats()`, `get_all_users()`, `get_all_users_count()`, `update_user_admin()`, `get_coaches_with_payout_status()`, `upsert_coach_payment()`, `mark_coach_payment_paid()`, `get_coach_finance_summary()`, `get_coach_finance_students()`, `get_coach_finance_history()`, `get_admin_activity_logs()`
- **`app.py`** — 10 novos endpoints:
  - `GET /admin/dashboard` — MRR estimado, usuários ativos, distribuição de planos, repasses pendentes
  - `GET /admin/users` — lista paginada com filtros (plan, role, search)
  - `PATCH /admin/users/<id>` — suspender/alterar plano
  - `GET /admin/finance/coaches` — repasses do ciclo com auto-upsert
  - `PATCH /admin/finance/coaches/<id>/pay` — marcar como pago
  - `GET /admin/finance/export.csv` — exportação CSV para processamento bancário
  - `GET /admin/logs` — últimas importações de torneios
  - `GET /coach/finance/summary` — ciclo atual do coach
  - `GET /coach/finance/students` — alunos com status de atividade
  - `GET /coach/finance/history` — histórico de repasses recebidos

### Frontend

- **`api.ts`** — tipos `AdminStats`, `AdminUser`, `CoachPayout`, `CoachFinanceSummary`, `CoachFinanceStudent`, `CoachPaymentRecord`; objetos `adminDashboard` e `coachFinance` com todas as chamadas
- **`pages/admin/AdminDashboard.tsx`** — painel admin com 4 abas: Visão Geral (KPIs + distribuição de planos), Usuários (tabela paginada com filtros, alterar plano inline, suspender/reativar), Financeiro (tabela de repasses por período, "Marcar pago", exportar CSV), Logs (últimas importações)
- **`CoachDashboard.tsx`** — nova aba "Financeiro": resumo do ciclo atual (alunos totais/ativos, receita estimada, mensalidade zerada), lista de alunos com badge Ativo/Inativo, histórico de repasses
- **`App.tsx`** — `AdminRoute` guard + rota `/admin`; `PublicRoute` redireciona admin para `/admin`
- **`HudHeader.tsx`** — nav item "Admin" com ícone Shield para role admin

### Regras de negócio implementadas
- 1–3 alunos ativos: mensalidade do coach zerada, R$0 de repasse
- 4–9 alunos ativos: mensalidade zerada + R$15/aluno/mês
- 10+ alunos ativos: mensalidade zerada + R$20/aluno/mês
- Aluno ativo = importou ≥1 torneio nos últimos 30 dias + plano PRO

---

## [v0.33.0] — 2026-05-02 — Sprint B: UX-002 Responsividade Mobile/Tablet

### Frontend

- **`HudHeader.tsx`** — bottom navigation bar fixa em mobile (`fixed bottom-0 z-50 md:hidden`) com ícone + label curto por rota; FAB de import (`fixed bottom-[72px] right-4 size-12`) substitui o botão de import do header em mobile; padding do header ajustado para `px-4 md:px-8`
- **`HudLayout.tsx`** — padding inferior `pb-28 md:pb-8` para deixar clearance acima do bottom nav fixo
- **`Index.tsx`** — grid de KPIs vai de 1-col para `grid-cols-2 lg:grid-cols-4` (2 colunas em mobile); sidebar com LevelCard/LeaksPanel usa `order-first lg:order-none` — aparece antes dos gráficos em mobile
- **`RecentTournamentsTable.tsx`** — modo duplo: lista de cards clicáveis `md:hidden` + tabela `hidden md:block overflow-x-auto`; `formatDateShort()` para data compacta nos cards mobile
- **`Tournaments.tsx`** — modo duplo: lista de cards mobile com profit, badge, delete + tabela desktop; empty state diferente por viewport
- **`Replayer.tsx`** — barra de controles vira sticky bottom em mobile (`sticky bottom-14 z-30 border-t bg-background/95 backdrop-blur-md`) e volta ao painel normal em desktop (`md:static md:border md:rounded-xl md:bg-hud-surface`)
- **`TournamentDetail.tsx`** — tabelas de fase (M-Ratio) e textura de board recebem `overflow-x-auto` para scroll horizontal em mobile
- **`StudentDetail.tsx`** — tabs do detalhe do aluno (coach view) recebem `overflow-x-auto` + `shrink-0` nos botões para scroll horizontal em telas pequenas

---

## [v0.32.0] — 2026-05-02 — Sprint 4: BACK-001 + BACK-005 (confirmados + gap fechado)

### Backend
- **`api/app.py` → `history_tournament`** — enriquece cada decisão com `has_annotation: bool` usando `get_annotations_for_decisions`; aluno agora sabe quais mãos têm anotação do coach sem fazer request extra

### Frontend
- **`api.ts`** — `TournamentDecision` ganha campo opcional `has_annotation?: boolean`
- **`TournamentDetail.tsx`** — `Hand.hasAnnotation` propagado via `groupByHand` (true se qualquer decisão do grupo tem anotação); badge "Coach" com ícone GraduationCap aparece ao lado do severity badge em mãos anotadas pelo coach

### Confirmado já implementado (BACK-001 e BACK-005 core)
- Tabela `coach_hand_annotations` + endpoints GET/POST/DELETE `/coach/student/:id/hand-annotations`
- `AnnotationForm` no `WorstTab` do `StudentDetail.tsx` (visão coach)
- Replayer: painel de anotação para coach (form com modo/ação/veredito) e balão read-only para aluno
- Ambos os endpoints de replay (`/replay/:t/:h` e `/coach/student/:id/replay/:t/:h`) incluem `coach_annotations`
- Badge "✓ Coach" na listagem de torneios do aluno (`Tournaments.tsx`) via `get_reviewed_tournament_ids()`

---

## [v0.31.0] — 2026-05-02 — Sprint A: UX-001 + UX-003 + LLM template upgrade

### Frontend — UX-001: Lista de torneios melhorada
- **`RecentTournamentsTable.tsx`** — fallback de nome agora usa `#tournament_id` (era `site`); badge detection estendida: +SAT (satellite), +KO (knockout/bounty/PKO), +SNG (sit & go variants); subtitle mostra `{hands_count} mãos` abaixo do ID
- **`Tournaments.tsx`** — coluna "ID" renomeada para "Torneio"; mesmas melhorias de badge e fallback; `{hands_count} mãos` no subtitle

### Frontend — UX-003: Tooltips e score auto-explicativo
- **`TournamentDetail.tsx`** — componente `InfoTooltip` (HelpCircle + Radix Tooltip) adicionado a cabeçalhos das seções fase/textura e às colunas "Erros %" e "Score Médio"; tooltips explicam os thresholds (M-Ratio, texturas de board com exemplos de cartas, % de erro, faixas do score)
- **`TournamentDetail.tsx`** — componente `ScoreLabel` exibe rótulo colorido (Ótimo / Bom / Moderado / Alto) inline ao score para leitura imediata sem referência externa

### Backend / IA — LLM template upgrade
- **`llm_explainer.py`** — `analyze_single_decision` migrada de 3 parágrafos genéricos para template estruturado em 5 seções: ❌ O Erro / 📐 A Matemática / 🧭 O Contexto / ✅ A Ação Correta / 💡 A Lição; `max_tokens` 500 → 900

### Infra — BACK-007 (confirmado como já implementado)
- `UploadQueue.tsx` + `HudHeader.tsx` já implementavam upload múltiplo com fila sequencial — confirmado durante Sprint A; nenhuma mudança necessária

---

## [v0.30.0] — 2026-05-02 — Análise por Fase e Textura de Board

### Backend
- **`leaklab/board_texture.py`** — novo módulo: `classify_board_texture(board_json)` classifica boards pós-flop em `dry | coordinated | wet | monotone | paired` usando span de ranks e contagem de naipes
- **`repositories.py`** — `get_phase_analysis(tournament_db_id)`: agrupa decisões por fase (Folgado M≥20 / Médio M10-20 / Pressão M6-10 / Crítico M<6) derivando fase do `m_ratio`; `get_texture_analysis(tournament_db_id)`: classifica boards pós-flop e retorna stats por textura
- **`GET /history/tournament/<id>/phase_analysis`** — novo endpoint: retorna distribuição de erros e score médio por fase de torneio
- **`GET /history/tournament/<id>/texture_analysis`** — novo endpoint: retorna distribuição de erros pós-flop por textura de board

### Frontend
- **`TournamentDetail.tsx`** — duas novas seções entre o grid de stats e os filtros: tabela de Análise por Fase e tabela de Pós-Flop por Textura de Board; código de cores: verde (<25% erros), amarelo (25-40%), vermelho (>40%)
- **`api.ts`** — `tournaments.phaseAnalysis()` e `tournaments.textureAnalysis()`; novas interfaces `PhaseData` e `TextureData`

---

## [v0.29.0] — 2026-05-02 — BACK-015: Migração Mercado Pago → Stripe

### Pagamentos
- **`stripe_gateway.py`** — novo gateway: `create_subscription`, `cancel_subscription`, `get_subscription`, `get_payment`, `validate_webhook`; usa Stripe Subscriptions API com `payment_behavior=default_incomplete`
- **`POST /subscription/checkout`** — simplificado: recebe só `plan`, cria Stripe Customer + Subscription, retorna `{ client_secret, subscription_id }` para confirmação no frontend
- **`POST /subscription/activate`** — novo: verifica `PaymentIntent.status` e ativa o plano no banco (chamado pelo frontend após `stripe.confirmPayment`)
- **`POST /subscription/webhook`** — reescrito para eventos Stripe: `invoice.payment_succeeded` → ativa plano; `customer.subscription.deleted` → reverte para free; sem secret configurado aceita sem validação (dev mode)
- **`POST /subscription/cancel`** — usa `stripe.Subscription.cancel()` via gateway
- Removido `mercadopago_gateway.py` (todas as rotas MP descontinuadas)

### Frontend
- **`CheckoutModal.tsx`** — reescrito com `@stripe/stripe-js`; `loadStripe` + `PaymentElement` substitui 8 campos manuais do MP; `Promise.all` carrega SDK e intent em paralelo; confirmação via `stripe.confirmPayment({ redirect: 'if_required' })` + `/subscription/activate`
- **`api.ts`** — `checkout()` simplificado (só `plan`); novo `activate(plan, payment_intent_id, subscription_id)`

### Dependências
- `requirements.txt`: + `stripe==12.0.0`; removido `requests` (não mais usado pelo gateway)
- `package.json`: + `@stripe/stripe-js`

### Env vars necessárias
| Variável | Descrição |
|---|---|
| `STRIPE_SECRET_KEY` | Chave secreta Stripe (`sk_test_...` / `sk_live_...`) |
| `STRIPE_PUBLISHABLE_KEY` | Não usada no backend |
| `STRIPE_WEBHOOK_SECRET` | Secret do webhook Stripe (`whsec_...`) |
| `STRIPE_PRICE_STARTER` | Price ID do plano Starter (`price_...`) |
| `STRIPE_PRICE_PRO` | Price ID do plano Pro (`price_...`) |
| `VITE_STRIPE_PUBLISHABLE_KEY` | Chave pública Stripe para o frontend |

### Testes
- `test_subscription.py` reescrito: 25 testes cobrindo checkout, activate, invoices, cancel, webhook — 0 regressões

---

## [v0.28.1] — 2026-05-01 — BACK-015 fix: payer.identification + debugging

### Pagamentos
- **`mercadopago_gateway.py`** — `create_subscription` aceita `identification_type`/`identification_number`; inclui `payer.identification` no body do `/v1/payments` (obrigatório no Brasil); log completo do response de erro
- **`POST /subscription/checkout`** — extrai `identification_type`, `identification_number` e `payer_email` do body; `payer_email` do form substitui email do usuário quando fornecido (permite usar email de conta teste MP)
- **`CheckoutModal.tsx`** — extrai `identificationType`, `identificationNumber`, `cardholderEmail` de `getCardFormData()` e envia ao backend
- **`api.ts`** — `subscription.checkout()` aceita os novos campos

### Testes
- 2 novos testes: `test_checkout_forwards_identification`, `test_checkout_payer_email_override`
- 23 testes de subscription — 0 regressões

---

## [v0.28.0] — 2026-04-27 — BACK-015: Mercado Pago Transparent Checkout

### Pagamentos
- **`mercadopago_gateway.py`** — novo módulo: `get_or_create_plan`, `create_subscription`, `cancel_subscription`, `get_subscription`, `get_payment`, `validate_webhook_signature` (HMAC-SHA256)
- **`POST /subscription/checkout`** — cria assinatura recorrente MP via card token; rate limit 5/h; atualiza `plan` e `mp_subscription_id` do usuário no banco
- **`POST /subscription/webhook`** — recebe eventos MP (`subscription_preapproval`, `payment`); valida assinatura HMAC-SHA256; atualiza plano e salva pagamentos
- **`GET /subscription/invoices`** — retorna histórico de pagamentos do usuário (limit 20)
- **`POST /subscription/cancel`** — cancela assinatura MP ativa e reverte plano para `free`

### Schema
- Tabela `payments` (id, user_id, plan, amount_cents, currency, status, gateway, gateway_id, gateway_sub_id, period_start, period_end, created_at)
- Coluna `mp_subscription_id` adicionada a `users`

### Frontend
- **`CheckoutModal.tsx`** — modal de checkout transparente: carrega MP JS SDK v2 dinamicamente, inicializa `mp.cardForm()` com iframes seguros para dados do cartão, submete token ao backend, exibe sucesso/erro e chama `refreshUser()`
- **`AccountMenu.tsx`** — botões "Starter R$19" e "Pro R$39" abrem `CheckoutModal` (substituindo links `mailto:`)
- **`QuotaBanner.tsx`** — idem: botões de upgrade abrem `CheckoutModal`
- **`api.ts`** — `subscription.checkout()`, `subscription.invoices()`, `subscription.cancel()`

### Testes
- 227 testes — 0 regressões

---

## [v0.27.0] — 2026-04-27 — BACK-011 pt.2: Anti-Prompt Injection + Moderação de Conteúdo

### Segurança — Camada 1: Anti-Prompt Injection
- **`content_moderation.py`** — novo módulo com `sanitize_llm_input(text, max_len)`: remove 14 padrões de injection (EN + PT-BR) via regex antes de qualquer chamada ao LLM; tenta de role spoofing (`system:`, `assistant:`), token markers (`<|...|>`, `[INST]`), comandos de esquecimento e personas alternativas
- **`coach_chat_reply`** — mensagem do usuário sanitizada antes de entrar no payload do Claude
- **`analyze_single_decision`** — campo `note` (texto livre do hand history) sanitizado antes de ir ao LLM
- **`/coach/chat`** — sanitização no endpoint antes de repassar ao `coach_chat_reply`; erro interno não mais exposto na resposta
- **Anotações de coach** — `comment` sanitizado via `sanitize_llm_input` antes de salvar no banco
- Todas as tentativas detectadas são logadas com `log.warning` para análise posterior

### Segurança — Camada 2: Moderação de Conteúdo (blocklist local v1)
- **`moderate_text(text)`** — verifica texto livre contra blocklist PT-BR + EN cobrindo: discurso de ódio, ataques, spam/scam, links de redes sociais suspeitos, conteúdo adulto explícito; retorna `(is_clean, reason)` e loga flags
- **`/coach-profile` (POST)** — campo `bio` verificado antes de salvar; retorna 422 se flaggeado
- **`/coach/review` (POST)** — `review_text` verificado antes de salvar; retorna 422 se flaggeado
- **`/coach/student/:id/hand-annotations` (POST)** — `comment` verificado + sanitizado antes de salvar

### Schema
- Coluna `moderation_status TEXT DEFAULT 'approved'` adicionada a `coach_profiles`, `coach_reviews`, `coach_hand_annotations` (PostgreSQL: `ALTER TABLE IF NOT EXISTS`; SQLite: migration lazy)

### Testes
- 227 testes — 0 regressões

---

## [v0.26.0] — 2026-04-27 — BACK-011: Hardening de segurança

### Segurança — Crítico
- **bcrypt** — senhas agora armazenadas com bcrypt + salt aleatório; migração transparente: hashes SHA-256 legados são re-hasheados no próximo login com sucesso
- **SECRET_KEY forçado** — inicialização levanta `RuntimeError` em produção se `LEAKLAB_SECRET` não estiver definido ou tiver menos de 32 caracteres; aviso no terminal em desenvolvimento

### Segurança — Alta
- **`require_coach` usa role do banco** — antes validava o campo `role` do JWT (forjável); agora consulta o banco em cada requisição protegida
- **Token não aceito via URL** — `_extract_token()` removia fallback `?token=` que expunha tokens nos logs de servidor; aceita apenas `Authorization: Bearer` e cookie
- **IDOR em anotações de coach corrigido** — endpoint `POST /coach/student/:id/hand-annotations` agora valida que `decision_id` pertence ao aluno antes de salvar
- **Headers de segurança HTTP** — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy` adicionados a toda resposta; `Strict-Transport-Security` ativado em produção (`RENDER=true`)

### Segurança — Média
- **Rate limiting** — Flask-Limiter instalado; limites por IP: `/auth/register` 10/min, `/auth/login` 15/min, `/analyze` 30/h, `/analyze/decision` e `/analyze/hand-coach` 30/h, `/analyze/tournament-summary` 20/h; desativado automaticamente em testes (`app.testing`)
- **Validação de extensão de arquivo** — upload em `/analyze` rejeita arquivos que não terminem em `.txt`
- **Mensagens de erro sanitizadas** — exceções internas logadas com `log.exception()` em vez de expostas no corpo da resposta
- **Senha mínima 8 caracteres** — aumentado de 6 para 8 em `/auth/register`
- **Role restrito no cadastro** — valores fora de `player/coach` são coercidos para `player` silenciosamente

### Infraestrutura
- `bcrypt==4.2.1` e `Flask-Limiter==3.8.0` adicionados ao `requirements.txt`
- `repositories.py`: funções `_hash_password`, `_check_password`, `decision_belongs_to_student` extraídas; `update_user_email`, `change_user_password`, `check_password` migradas para usar bcrypt

### Testes
- 227 testes — 0 regressões

---

## [v0.25.0] — 2026-04-27 — UX-004: Menu de conta com plano e uso

### Adicionado
- **`AccountMenu`** — dropdown acessível ao clicar no nome/plano no header; exibe username, badge de plano colorido por tier (Free/Starter/Pro/Coach), barras de uso mensal (torneios + análises LeakLabs), CTAs de upgrade contextuais e links para Perfil e Sair
- **`/auth/me` inclui quota** — resposta agora inclui `plan`, `tournaments_used`, `ai_calls_used`, `plan_limits`; elimina segundo request separado ao `/subscription/status`

### Alterado
- **`HudHeader`** — item "Perfil" removido do menu de navegação do jogador; bloco username+logout substituído por `AccountMenu`; Dashboard corrigido para `/dashboard`
- **`UserProfile`** — interface TypeScript estendida com campos de quota
- **Dashboard (`Index.tsx`)** — `QuotaBanner` removido da sidebar (redundante com `AccountMenu`)

---

## [v0.24.0] — 2026-04-27 — Proposta B: 3 planos (Free / Starter / Pro)

### Adicionado
- **Plano Starter R$19/mês** — 20 torneios + 40 análises/mês; público alvo: jogador casual que ultrapassou o Free mas não precisa de volume de grinder
- **3 planos no `/subscription/plans`** — Free, Starter (R$19), Pro (R$39)

### Alterado
- **Plano Pro**: R$15 → **R$39/mês** — torneios ilimitados + 150 análises LeakLabs/mês
- **PLAN_LIMITS** — `starter: {tournaments: 20, ai_calls: 40}` · `pro: {tournaments: None, ai_calls: 150}`
- **Landing page** — seção Planos migrada para grid de 3 colunas; badge "Mais popular" no Starter, badge "Grinder" + destaque primário no Pro
- **QuotaBanner** — botões Starter R$19 + Pro R$39 lado a lado no banner de limite atingido

---

## [v0.23.0] — 2026-04-27 — UX-003: Landing page pública

### Adicionado
- **Landing page pública em `/`** — apresentação do produto para visitantes não autenticados; seções: Hero com níveis preview, Estatísticas, Como Funciona (3 passos), Funcionalidades (6 cards), Planos (Free vs Pro), CTA final e Footer
- **Rota `/dashboard`** — dashboard do jogador movido de `/` para `/dashboard`; usuários autenticados são redirecionados automaticamente para o destino correto ao acessar `/` ou `/login`
- **`PublicRoute`** — guarda de rota público: redireciona usuário já logado para `/dashboard` (jogador) ou `/coach-dashboard` (coach), evitando que veja a landing ou tela de login desnecessariamente

### Alterado
- `App.tsx` — `/` agora renderiza `Landing` (via `PublicRoute`); `/login` também usa `PublicRoute`; `/dashboard` é a nova rota protegida do jogador; `CoachRoute` redireciona não-coaches para `/dashboard`
- `Login.tsx` — pós-login redireciona jogador para `/dashboard` em vez de `/`
- `HudHeader.tsx` — logo aponta para `/dashboard` em vez de `/` (usuário autenticado)

---

## [v0.22.0] — 2026-04-27 — BACK-010: Freemium + quota + backlog expandido

### Adicionado
- **Planos freemium e controle de quota** — plano Free: 3 torneios/mês + 10 análises IA/mês; plano Pro: ilimitado; quota resetada automaticamente no início de cada mês (lazy reset por usuário)
- **Endpoints de subscription** — `GET /subscription/plans`, `GET /subscription/status`, `POST /subscription/upgrade`; upgrade manual em v1 (sem gateway de pagamento)
- **Middleware de quota no backend** — `_check_upload_quota()` antes do `/analyze`; `_check_ai_quota()` antes de `/analyze/decision`, `/analyze/hand-coach` e `/analyze/tournament-summary`; retorna HTTP 402 com `quota_exceeded: true` quando limite atingido
- **Cache de tournament summary** — `/analyze/tournament-summary` agora retorna o summary já salvo no banco quando disponível, sem chamar o LLM novamente; economiza quota e reduz latência
- **QuotaBanner no dashboard** — barra de uso de torneios e análises IA exibida na sidebar do dashboard; aparece somente para plano Free e apenas quando ≥ 80% do limite foi atingido; botão de upgrade via email em v1
- **Busca corrigida em /tournaments** — placeholder atualizado de "herói" para "nome, tipo (MTT/SNG) ou ID"
- **Backlog expandido** — UX-002 (responsividade mobile/tablet, ~15h) e BACK-014 (revenue share para coaches, ~20h) documentados com escopo, modelo de dados e esforço estimado

### Backend
- `backend/database/schema.py` — colunas `tournaments_this_month`, `ai_calls_this_month`, `quota_reset_at` na tabela `users`; migrations para SQLite e Postgres
- `backend/database/repositories.py` — `PLAN_LIMITS`, `get_quota_status()`, `increment_tournament_count()`, `increment_ai_calls()`, `_maybe_reset_quota()` (lazy reset mensal)
- `backend/api/app.py` — `_check_upload_quota()`, `_check_ai_quota()`; subscription endpoints; quota wiring em analyze + LLM endpoints

### Frontend
- `frontend/src/lib/api.ts` — interface `QuotaStatus`; namespace `subscription` com `status()`, `plans()`, `upgrade()`
- `frontend/src/components/hud/QuotaBanner.tsx` — componente novo com barras de progresso e CTA de upgrade
- `frontend/src/pages/Index.tsx` — `QuotaBanner` inserido no topo da sidebar
- `frontend/src/pages/Tournaments.tsx` — placeholder da busca corrigido

---

## [v0.21.0] — 2026-04-26 — UX: Logos de sites, auto-reload pós-import, níveis rebalanceados

### Adicionado
- **Logo dos sites na lista de torneios** — componente `SiteLogo` exibe favicon do site (PokerStars, GGPoker, 888Poker, Winamax, ACR) em container 24×24 com tooltip do nome completo; fallback para sigla em texto se a imagem falhar; visível na `RecentTournamentsTable` (dashboard) e na lista completa `/tournaments`

### Corrigido
- **Auto-reload pós-importação em qualquer tela** — `UploadQueue` agora dispara evento global `leaklab:tournament-imported` a cada arquivo processado; `Tournaments.tsx` escuta o evento e chama `reload()` automaticamente; antes, importar pelo botão do header na tela `/tournaments` não atualizava a lista
- **Badge SNG/MTT incorreto** — `_extract_tournament_name()` agora conta jogadores únicos no arquivo HH: ≤ 9 = SNG (sem reposição de mesa), > 9 = MTT (jogadores vindos de mesas quebradas); resolve badge "MTT" incorreto em Sit & Go PokerStars
- **Thresholds de nível rebalanceados** — escala anterior era leniente demais (Sólido começava em 75%); nova escala: Iniciante < 60%, Estudante 60–69%, Grinder 70–76%, Regular 77–85%, Sólido 86–91%, Expert 92–95%, Elite 96%+; calibrada para que 83–85% std_pct = Regular

### Frontend
- `frontend/src/components/hud/SiteLogo.tsx` — componente novo com mapa de favicons e fallback de sigla
- `frontend/src/components/hud/RecentTournamentsTable.tsx` — logo inline, badge corrigido
- `frontend/src/pages/Tournaments.tsx` — coluna Rede vira logo; listener de reload pós-import
- `frontend/src/components/hud/UploadQueue.tsx` — dispara `CustomEvent('leaklab:tournament-imported')` após cada upload concluído

### Backend
- `backend/database/repositories.py` — thresholds de `get_player_level()` atualizados
- `backend/api/app.py` — `_extract_tournament_name()` usa contagem de jogadores únicos para distinguir SNG de MTT

---

## [v0.20.0] — 2026-04-26 — UX-001: Nome e Tipo do Torneio na Lista

### Adicionado
- **Nome do torneio na lista de torneios** (UX-001) — substituído o par "site • nome do hero" pelo nome descritivo do torneio (ex: "Spin&Gold #14", "NLH $2.20"); badge "MTT" / "Spin&Go" ao lado do nome; subtext exibe site + ID interno para rastreabilidade
- Coluna `tournament_name TEXT` adicionada à tabela `tournaments` (SQLite + PostgreSQL); migration automática via `_run_migrations`

### Backend
- `backend/api/app.py` — novo helper `_extract_tournament_name()`: GGPoker extrai nome do header (`Tournament #N, Spin&Gold #14 Hold'em`); PokerStars constrói label do buy-in (`NLH $2.20`); chamado no `/analyze` e persistido com o torneio
- `backend/database/repositories.py` — `save_tournament()` aceita `tournament_name`; `get_tournaments()` inclui o campo no SELECT
- `backend/database/schema.py` — coluna `tournament_name TEXT` nas definições CREATE TABLE e nas migrations SQLite/Postgres

### Frontend
- `frontend/src/lib/api.ts` — `Tournament.tournament_name?: string | null` adicionado à interface
- `frontend/src/components/hud/RecentTournamentsTable.tsx` — helper `formatTournamentLabel()` e `formatBadge()`; célula "Torneio" exibe nome + badge de formato + subtext com site e ID
- `frontend/src/pages/coach/StudentDetail.tsx` — `TournamentsTab` usa `tournament_name ?? site` como label principal; subtext inclui site + ID

---

## [v0.19.0] — 2026-04-26 — BACK-008: Visualizador de Ranges + BUG-001: Prêmio de Torneio

### Adicionado
- **Visualizador de Ranges no Replayer** (BACK-008) — botão "Range" aparece durante o preflop; painel lateral 13×13 com ranges GTO-aproximadas para 6 posições (UTG, MP, HJ, CO, BTN, SB, BB); auto-detecta posição do herói e contexto (open vs facing raise); seletor manual de posição e tipo (Open · Call · 3-Bet); mão do herói destacada em amarelo; legenda com % de mãos e contagem de combos

### Corrigido
- **BUG-001 — Prêmio incorreto em torneios PokerStars** — quando eliminado sem ITM, o arquivo PokerStars contém apenas "hero finished the tournament" sem prêmio; o código caía no fallback GGPoker que somava todos os chips coletados em potes normais do jogo como prêmio; fix: detecta "finished the tournament" antes do fallback e define `prize = 0.0`; torneios afetados devem ser reimportados

### Frontend
- `frontend/src/data/ranges.ts` — ranges GTO-aproximadas para Open/Call/3-Bet por posição; expansor de notação de range ("AA-77", "AKs-A2s"); utils `cellHand`, `cellLabel`, `heroHand`, `getCellAction`, `rangeStats`
- `frontend/src/components/replayer/RangeGrid.tsx` — grid 13×13 com aspect-square, cores por ação (verde=raise, azul=call), destaque da mão do herói
- `frontend/src/components/replayer/RangePanel.tsx` — painel com auto-detecção de posição/contexto, seletores de posição e tipo, rodapé com posição detectada
- `frontend/src/pages/Replayer.tsx` — botão "Range" no header do Action Log (visível apenas no preflop); importa `RangePanel` e `LayoutGrid`

### Backend
- `backend/api/app.py` — fix em `_extract_financials()`: PokerStars bust-out sem prêmio define `prize = 0.0` ao invés de somar chips coletados em potes

---

## [v0.18.0] — 2026-04-26 — Sprint 10: Sistema de Nível do Jogador / Gamificação (BACK-009)

### Adicionado
- **Sistema de nível do jogador** — 7 níveis baseados no `standard_pct` médio dos últimos 20 torneios (ou 30 dias): Iniciante, Estudante, Grinder, Regular, Sólido, Expert, Elite; sem rótulos ofensivos; thresholds rebalanceados em v0.21.0
- **LevelCard** — componente visual com badge de nível (ícone + nome + cor por nível), barra de progresso para o próximo nível, threshold do próximo nível, leaks que bloqueiam avanço; modo `compact` para uso no dashboard do coach; link para o plano de estudos (opcional)
- **Dashboard do jogador** — `LevelCard` exibido na sidebar do Index.tsx ao lado dos leaks e ICM
- **Dashboard do coach** — `LevelCard` em modo compacto na aba "Visão Geral" de cada aluno; query `coach-student-level`

### Backend
- `get_player_level(user_id, min_tournaments=5, days=30)` — calcula nível, progresso (0-1), próximo nível, leaks bloqueadores, contagem de torneios usados
- `GET /metrics/level` — retorna nível do próprio jogador
- `GET /coach/student/:id/level` — retorna nível de um aluno (requer `@require_coach`)

### Frontend
- `LevelCard.tsx` — criado com cores por nível, barra de progresso, leaks bloqueadores, CTA de plano de estudos
- `api.ts` — interface `PlayerLevel`; `metrics.level()`; `coachDashboard.studentLevel(studentId)`
- `Index.tsx` — query `player-level` com React Query; `LevelCard` na sidebar
- `StudentDetail.tsx` — query `coach-student-level`; `LevelCard` compacto no topo da `OverviewTab`

---

## [v0.17.0] — 2026-04-26 — Sprint 9: Upload Múltiplo com Fila + Perfil do Coach Unificado (BACK-007 + BACK-012)

### Adicionado
- **Upload múltiplo de torneios** (BACK-007) — botão "Import" aceita múltiplos arquivos `.txt` de uma vez; fila processa sequencialmente com badge de status por arquivo (`Em fila`, `Processando…`, `Analisado ✓`, `Erro`); painel flutuante no canto inferior direito com botão "Fechar" após conclusão
- **Perfil do coach unificado** (BACK-012) — página `/coach-dashboard/profile` reescrita com todos os campos estendidos do Sprint 7 (foto, experiência, stakes, método, idiomas, maiores resultados, preços, trial, redes sociais) + aba "Avaliações" com distribuição de ratings; abas "Perfil Público" e "Avaliações" removidas do CoachDashboard

### Frontend
- `UploadQueue.tsx` — hook `useUploadQueue` + `QueuePanel` com `useReducer`; `fileMap` ref para mapear IDs aos `File` objetos sem poluir o estado
- `HudHeader.tsx` — input de upload agora com `multiple`; usa `useUploadQueue` ao invés de upload manual unitário; retorna `<>header + panel</>` via Fragment
- `CoachProfile.tsx` — reescrito completamente com `ProfileSection` + `AvaliacoesSection` internos; suprime a versão anterior com campos básicos apenas
- `CoachDashboard.tsx` — tabs "Perfil Público" e "Avaliações" removidos; imports de lucide e tipos relacionados limpos

---

## [v0.16.0] — 2026-04-26 — Sprint 8: Diretório Público de Coaches + Integração Contextual (BACK-006 pt.2 + BACK-013)

### Adicionado
- **Diretório público de coaches** (`/coaches`) — lista com filtros de especialidade, idioma, preço máximo, trial e ordenação; barra de busca por nome; sidebar colapsável; grid responsivo
- **Perfil público do coach** (`/coaches/:id`) — avatar, bio, especialidades, maiores resultados, distribuição de avaliações, reviews públicos, contato e links sociais; CTA contextual para vincular coach via chave de convite
- **Coaches no menu principal** — entrada "Coaches" adicionada ao `HudHeader` para jogadores
- **BACK-013 — Coaches contextuais no Plano de Estudos** — strip de coaches especializados no leak ativo, exibida somente para alunos sem coach; clique direciona ao perfil do coach
- **BACK-013 — Coaches no Perfil do aluno** — quando sem coach: lista top-3 coaches por rating + formulário de link por chave de convite; substitui botão antigo sem destino útil

### Backend
- `GET /coaches` aceita `specialty`, `language`, `trial`, `max_price`, `q`, `sort`, `limit` como filtros
- `GET /coaches/:id` retorna perfil completo + reviews públicos recentes
- `GET /coaches/:id/reviews` retorna reviews públicos paginados
- `GET /student/recommended-coaches` — endpoint para recomendação futura (stub)

### Frontend
- `CoachesDirectory.tsx` — nova página com `StarRow`, `CoachCard`, `FilterPanel`
- `PublicCoachProfile.tsx` — nova página com distribuição de rating, reviews, formulário de avaliação (alunos vinculados) e CTA de contratação
- `StudyPlan.tsx` — `CoachRecommendationStrip` + `CoachMiniCard` injetados no card de diagnóstico de leaks
- `StudentProfile.tsx` — `NoCoachDiscovery` com `CoachDiscoveryCard` e formulário de invite key
- `HudHeader.tsx` — "Coaches" adicionado ao nav de jogadores

---

## [v0.15.0] — 2026-04-26 — Sprint 7: Perfil Estendido do Coach + Sistema de Avaliações (BACK-006 pt.1)

### Adicionado
- **Aba "Perfil Público"** no CoachDashboard — formulário completo com foto, experiência, stakes, método de coaching, idiomas, maiores resultados, preços, disponibilidade e redes sociais; modo visualização / edição inline
- **Aba "Avaliações"** no CoachDashboard — aggregate de rating com barra de distribuição por estrela + lista de reviews recebidas
- **Avaliação de coach pelo aluno** — widget na página de perfil do aluno (`StudentProfile`) com StarPicker, comentário opcional, edição e exclusão; aparece somente quando há coach vinculado
- Tabela `coach_reviews` com constraint `UNIQUE(coach_id, student_id)` — 1 review por par aluno-coach

### Backend
- `coach_profiles`: 13 novos campos adicionados (`photo_url`, `experience_years`, `stakes`, `coaching_style`, `languages`, `biggest_results`, `price_per_session`, `price_monthly`, `trial_available`, `availability`, `social_youtube`, `social_twitch`, `social_twitter`)
- `GET /coach/profile` agora retorna `avg_rating` e `review_count` calculados em tempo real
- `POST /coach/review` — aluno envia/atualiza avaliação (upsert por par coach-aluno)
- `DELETE /coach/review` — aluno remove sua avaliação
- `GET /coach/my-review` — aluno consulta sua própria avaliação
- `GET /coach/reviews` — coach vê todas as avaliações recebidas com stats detalhados
- Migrations automáticas para SQLite e Postgres

---

## [v0.14.0] — 2026-04-26 — Sprint 6: Feed de Atividade + Baseline de Coaching (BACK-002)

### Adicionado
- **Aba "Progresso"** no perfil do aluno (coach) — baseline de coaching com comparação antes/depois + feed de atividade em timeline
- **Baseline de coaching** — coach define data de início do acompanhamento; armazenado por par `(coach_id, student_id)` com nota opcional; editável/removível
- **Comparação antes/depois** — métricas de score médio, % decisões standard e n° de torneios separadas pela data baseline; leaks top-5 em cada período; lista de leaks resolvidos
- **Feed de atividade** — timeline de torneios do aluno com marcos automáticos: "Melhora" (↓5pts score), "Regressão" (↑5pts score), "Alta Qualidade" (≥80% standard)
- Tabela `coach_baselines` no banco (SQLite e Postgres) com constraint `UNIQUE(coach_id, student_id)`

### Backend
- `GET/POST/DELETE /coach/student/:id/baseline` — gerenciar baseline de coaching
- `GET /coach/student/:id/activity-feed` — feed de torneios + marcos de performance (param `limit`)
- `GET /coach/student/:id/progress-report` — relatório comparativo antes/depois da baseline
- Novos repositórios: `get_coach_baseline`, `set_coach_baseline`, `delete_coach_baseline`, `get_student_activity_feed`, `get_baseline_comparison`

### Frontend
- Ícones `Activity, Flag, Star, BarChart2` adicionados
- Tipos `CoachBaseline, ActivityEvent, LeakSpot, PeriodMetrics, ProgressReport` em `api.ts`
- API functions `getBaseline`, `setBaseline`, `deleteBaseline`, `activityFeed`, `progressReport` em `coachDashboard`
- Componentes `ActivityTimeline`, `MetricsCompare`, `ProgressTab` em `StudentDetail.tsx`

---

## [v0.13.1] — 2026-04-26 — Combos de ação + classificação coach + Opção C de reclassificação

### Adicionado
- **Combo "Ação Correta"** nas anotações do coach — substituiu o campo livre por select com opções padrão do poker (fold, check, call, bet, raise, re-raise, all-in)
- **Combo "Classificação"** nas anotações — coach pode atribuir o veredito da decisão: Jogada Correta / Marginal / Erro Pequeno / Erro Claro; campo `coach_override_label` armazenado no banco
- Badge visual do veredito exibido no balloon de anotação (aluno e coach) e na listagem de "Mãos Críticas"
- **Opção C implementada** — `coach_override_label` é respeitado nas queries de `worst-decisions` do aluno: decisões marcadas como "Jogada Correta" ou "Marginal" pelo coach saem da lista de mãos críticas; avg_score do torneio **não** é alterado (métricas de performance permanecem do engine)

### Backend
- `coach_hand_annotations`: nova coluna `coach_override_label TEXT` — migrations automáticas SQLite + Postgres
- `upsert_annotation` aceita e persiste `coach_override_label`
- `POST /coach/student/:id/hand-annotations` aceita e valida `coach_override_label`
- `GET /coach/student/:id/worst-decisions` usa `COALESCE(coach_override_label, label)` para filtrar — decisões requalificadas pelo coach como corretas não aparecem mais na lista de erros

---

## [v0.13.0] — 2026-04-26 — Sprint 5: Atenção Urgente + Leaks Sistêmicos (BACK-003 + BACK-004)

### Adicionado
- **Aba "Atenção Urgente"** no Dashboard do Coach — tabela com as piores decisões de **todos os alunos** ao mesmo tempo, com filtros por aluno, street e label (erro claro / erro pequeno); botão "Replay" abre diretamente o replay do aluno na mão errada
- **Aba "Leaks Sistêmicos"** no Dashboard do Coach — lista de spots de erro agrupados por ocorrência, com destaque nos que afetam múltiplos alunos ("Leaks sistêmicos") vs. individuais; cada spot é expandível para ver quais alunos são afetados e quantas vezes
- **Filtro de período** (30/60/90 dias) na aba de Leaks Sistêmicos
- Dashboard do Coach reorganizado em **3 abas**: Alunos (existente) · Atenção Urgente · Leaks Sistêmicos

### Backend
- `repositories.py`: `get_all_students_worst_decisions(coach_id, n, student_id_filter, street_filter, label_filter)` — query cross-student com filtros dinâmicos
- `repositories.py`: `get_common_leaks(coach_id, days)` — agrupa erros por spot e retorna lista de alunos afetados por spot
- `GET /coach/all-worst-decisions` — piores decisões multi-aluno com filtros via query string
- `GET /coach/common-leaks` — leaks com breakdown por aluno

### Fix
- **Anotações do coach não apareciam no replay do aluno** — endpoint `GET /replay/<tournament_id>/<hand_id>` não incluía `coach_annotations`; agora busca e injeta as anotações do coach igual ao endpoint do coach student replay

---

## [v0.12.1] — 2026-04-26 — Fix: Replay para coaches + Anotação direto no Replayer (BACK-001 complemento)

### Corrigido
- **Replay inacessível para coaches** — rota `/replayer` estava envolvida em `ProtectedRoute` que redirecionava coaches para `/coach-dashboard`; criada `AuthRoute` que permite qualquer usuário autenticado acessar o replayer
- **Parâmetro `student` perdido na navegação de mãos** — botões "Mão anterior" / "Próxima mão" no Replayer não preservavam `?student=N` na URL; coach perdia o contexto e o replay passava a buscar dados do próprio jogador em vez do aluno

### Adicionado
- **Painel de anotação do coach no Replayer** — quando o coach acessa o replay de um aluno e a etapa atual é um erro do herói, o painel lateral exibe:
  - Botão "Anotar" (se sem anotação) ou anotação existente com botões "Editar" / "Remover"
  - Formulário inline com seletor de modo (Complementar / Substituir IA), textarea de comentário e campo de jogada correta
  - Salvar atualiza o estado local imediatamente sem re-fetch da mão inteira
- **`decisions` em estado no Replayer** — decisões do torneio são mantidas em memória para resolver `decision_id` de novos spots sem annotation existente (match por `hand_id + street + action_taken`)
- **BACK-007 adicionado ao backlog** — importação múltipla de torneios com fila + badge de progresso por arquivo

---

## [v0.12.0] — 2026-04-26 — Sprint 4: Anotações de Mãos + Selo Coach (BACK-001 + BACK-005)

### Adicionado
- **Anotações de mãos pelo coach** — na aba "Mãos Críticas" do perfil do aluno, o coach pode anotar qualquer decisão com dois modos:
  - **Complementar** — exibe a análise da IA + nota do coach empilhadas
  - **Substituir IA** — oculta a análise da IA, exibe apenas a nota do coach
- **Campo "Jogada correta"** — coach pode indicar a ação que considera correta para o spot anotado
- **Badge "Anotado"** — decisões com anotação exibem indicador visual na listagem
- **Balão do coach no Replayer** — ao chegar na ação anotada, o painel lateral exibe a nota do coach com destaque visual diferenciado do painel da IA
- **Selo "✓ Coach"** (BACK-005) — torneios revisados (com ao menos uma anotação) ganham badge roxo "Coach" na lista de torneios do aluno

### Backend
- Tabela `coach_hand_annotations` (SQLite + PostgreSQL) com migration automática
- `repositories.py`: `get_annotations`, `get_annotations_for_decisions`, `upsert_annotation`, `delete_annotation`, `get_reviewed_tournament_ids`
- `GET /coach/student/:id/hand-annotations` — lista anotações do coach para o aluno
- `POST /coach/student/:id/hand-annotations` — cria ou atualiza anotação por decision_id
- `DELETE /coach/student/:id/hand-annotations/:decision_id` — remove anotação
- Replay do coach (`/coach/student/:id/replay/...`) agora inclui `coach_annotations` na resposta
- `GET /history/tournaments` agora inclui `coach_reviewed: bool` por torneio

---

## [v0.11.1] — 2026-04-26 — Correções de ambiente local + segurança

### Corrigido
- **CORS local resolvido via Vite proxy** — todos os prefixos de API (`/auth`, `/history`, `/analyze`, `/study`, `/coach`, `/student`, `/tournaments`, `/replay`, `/metrics`, `/admin`, `/health`) são roteados pelo proxy do Vite, eliminando erros de CORS no desenvolvimento
- **`get_user_by_id` não importado** em `app.py` causava 500 em `/auth/me` — adicionado ao import
- **Coach redirecionado para `/coach-dashboard`** ao logar — `ProtectedRoute` agora redireciona coaches que tentam acessar rotas de aluno
- **Menu "Dashboard" do coach ficava ativo em `/coach-dashboard/profile`** — adicionado `end={true}` ao NavLink do dashboard do coach
- **Banner de vínculo não sumia após vincular coach** — `AcceptCoachModal` agora chama `refreshUser()` após sucesso, atualizando `user.coach_id` imediatamente
- **`GET /coach/profile` retornava 404** quando perfil não existia, causando loop de retentativas no `useQuery` — endpoint agora retorna `{}` (200)
- **Mensagens de erro no Login** — `TypeError` (ex: "Failed to fetch") exibe "Não foi possível conectar ao servidor" em vez da mensagem técnica bruta

### Segurança
- **Remoção de vínculo com coach exige senha atual** — `DELETE /student/coach` agora requer `password` no body; backend verifica hash antes de desvincular
- `repositories.py`: nova função `check_password(user_id, password)` reutilizável

---

## [v0.11.0] — 2026-04-26 — Perfil do aluno + segurança de conta

### Adicionado
- **Página `/profile`** para alunos: alterar e-mail (com confirmação de senha), trocar senha (verifica atual, mín. 8 chars), gerenciar vínculo de coach (remover com confirmação dupla)
- **Header**: badge do coach vinculado visível no topo quando aluno tem coach; link "Perfil" no nav do player
- **Plano de Estudos**: lock exibido sempre que o aluno tem coach vinculado (não só quando há overrides), mostrando o nome do coach
- **Banner de vínculo** no Dashboard: oculto quando aluno já tem coach vinculado

### Corrigido
- `/auth/me` agora retorna `coach_id` e `coach_username` — frontend usa para controle de acesso sem chamadas extras

### Backend
- `POST /auth/update-email` — atualiza e-mail após verificar senha atual
- `POST /auth/change-password` — verifica senha atual antes de atualizar
- `DELETE /student/coach` — remove vínculo com coach
- `repositories.py`: `update_user_email`, `change_user_password`, `unlink_student_coach`

---

## [v0.10.2] — 2026-04-25 — Plano de estudos com fonte única (canonical plan)

### Corrigido
- **Importar torneio nunca apaga o plano** — o plano de estudos só é substituído por ação explícita ("Gerar com IA" pelo aluno ou "Gerar novo plano" pelo coach)
- **Aluno com coach não pode regerar** — backend bloqueia `?new=1` se o aluno tiver coach vinculado
- **Overrides do coach aplicados no plano do aluno** — cards substituídos/comentados pelo coach já chegam modificados para o aluno via `/study/plan`, alinhando o conteúdo visto por ambos
- **Coach — StudyCardItem exibe recursos completos** (livros, vídeos, curso) para equiparar ao nível de detalhe do plano do aluno
- **Coach — "Substituir" gerencia recursos**: formulário de substituição inclui campos para livros (um por linha), vídeos (um por linha) e curso — coach pode indicar material próprio
- Recursos substituídos pelo coach são aplicados no plano do aluno via backend
- **Plano de estudos inconsistente entre aluno e coach**: aluno e coach agora compartilham o mesmo plano armazenado por chave estável `study_plan_current` no banco — não mais por hash dos dados, que podia divergir quando os dados mudavam entre as gerações
- **Botão "Gerar com IA"** agora força de fato uma nova geração (`?new=1`), sobrescrevendo o plano anterior no banco — antes apenas re-buscava o cache sem regenerar

### Adicionado
- **Coach — botão "Gerar novo plano"** na aba Plano de Estudos: gera um plano novo via IA para o aluno e o torna o plano canônico — o aluno passa a ver exatamente este plano
- Parâmetro `force_new` em `generate_study_plan()` e nos dois endpoints (`/study/plan?new=1`, `/coach/student/:id/study-plan?new=1`)

---

## [v0.10.1] — 2026-04-25 — Mãos Críticas com cartas + lock coach_managed

### Adicionado
- **WorstTab (Mãos Críticas)**: cada decisão agora exibe:
  - ID da mão (`hand_id`)
  - Cartas do herói como `PlayingCard` (tamanho sm)
  - Board cards (quando disponíveis)
- **Lock "Gerar com IA"** na tela do aluno: quando o coach tem overrides no plano, o botão é substituído por "Gerenciado pelo Coach" com ícone de cadeado
- **Backend `/study/plan`**: responde `coach_managed: true` quando existem overrides do coach para o aluno

---

## [v0.10.0] — 2026-04-25 — Sprint 3: Coach Study Plan + Comparativo Histórico

### Adicionado
- **Coach Study Plan interativo**: cada card do plano IA tem 3 ações do coach:
  - **Validar** (✓) — marca o card como aprovado (badge verde)
  - **Comentar** (💬) — abre textarea inline para nota visível ao aluno (badge âmbar)
  - **Substituir** (✏️) — formulário inline para reescrever título, diagnóstico e exercício (badge roxo)
  - Botão de remover anotação (ícone lixeira)
  - Resumo de status no topo: "X validados · Y comentados · Z substituídos"
- **Comparativo histórico** no OverviewTab:
  - Score médio e Standard% — primeiros 3 vs últimos 3 torneios
  - Delta com indicador visual: melhorou / piorou / estável
  - Total de torneios no período
- **Backend**: tabela `coach_study_overrides` (SQLite + PostgreSQL) com UNIQUE(coach_id, student_id, card_spot)
- **3 endpoints**: `GET/POST /coach/student/:id/study-overrides`, `DELETE /coach/student/:id/study-overrides/:spot`
- **Fixes**: replay link no WorstTab (`?tid=` → `?t=`), nome do aluno no header (era "Aluno #N")

---

## [v0.9.0] — 2026-04-25 — Sprint 2: Coach Full Student View

### Adicionado
- **6 novos endpoints backend** para o coach acessar dados completos do aluno:
  - `GET /coach/student/:id/stats` — HUD stats (VPIP, PFR, AF, 3BET%, W$SD…)
  - `GET /coach/student/:id/breakdown` — performance por street e posição
  - `GET /coach/student/:id/tournament/:tid` — detalhe de torneio + decisões
  - `GET /coach/student/:id/worst-decisions` — piores N decisões do aluno
  - `GET /coach/student/:id/study-plan` — plano de estudos IA do aluno
  - `GET /coach/student/:id/replay/:tid/:hid` — replay de mão do aluno
- **StudentDetail.tsx** totalmente reescrito com 4 abas:
  - **Visão Geral**: HUD Stats (8 indicadores), gráfico de evolução, leaks, performance por street (bar chart) e por posição
  - **Torneios**: lista completa clicável → detalhe com tabela de decisões + botão "Ver Replay"
  - **Mãos Críticas**: fila das 30 piores decisões (score, street, posição, ICM, M-ratio, ação vs. correto) com link direto ao replay
  - **Plano de Estudos**: plano IA gerado para o aluno, com cards de prioridade alta/média/baixa
- **Replayer.tsx**: suporte ao parâmetro `?student=<id>` — usa endpoint do coach em vez do endpoint do jogador

---

## [v0.8.0] — 2026-04-25 — Sprint 1: Sistema Professor/Aluno

### Adicionado
- **Login/registro com papel**: toggle "Jogador / Professor" na tela de registro; papel enviado ao backend via `role` no body
- **Rotas por papel**: `CoachRoute` em `App.tsx` — professores são redirecionados para `/coach-dashboard`; jogadores bloqueados de rotas de coach
- **`/coach-dashboard`**: dashboard do professor com stats (alunos, ativos 30d, melhoria média, melhor aluno), lista de alunos com tendência e link para detalhe
- **`/coach-dashboard/student/:id`**: histórico do aluno — gráfico de evolução (recharts), tabela de leaks, torneios recentes
- **`/coach-dashboard/profile`**: formulário para o professor configurar nome, bio, especialidades, e-mail/link de contato
- **Chave de convite** (`InviteKeyWidget`): exibida no dashboard do professor com botão de cópia
- **Banner "Vincular Professor"** no dashboard do jogador com `AcceptCoachModal` para inserir a chave de convite
- **Navegação condicional** no `HudHeader`: professores veem "Dashboard + Perfil"; jogadores veem nav padrão; botão Import oculto para professores

---

## [v0.7.0] — 2026-04-25 — HUD Stats completo + GGPoker

### Adicionado
- **Player HUD Stats** (8 indicadores): VPIP, PFR, AF, Flop Bet%, Fold-to-3BET, WTSD, **3BET%** e **W$SD** — todos computados a partir das decisões armazenadas
- **3BET%**: detectado quando hero re-raised pré-flop com `facing_size > 0`; coluna `is_3bet` na tabela `decisions`
- **W$SD**: detectado via `hero: shows` no raw_text (showdown real do hero); coluna `showdown_result` na tabela `decisions`
- **GGPoker parser**: suporte completo ao formato GGPoker — detecção automática por header, IDs `#SG.../#RC...`, hero sempre `Hero`
- **Fix hero detection GGPoker**: `HERO_DEALT_RE` usa `[^\[\n]+` para não capturar múltiplas linhas

### Corrigido
- `_normalize_action()` converte `'raises'` → `'raise'`; verificação `is_3bet` corrigida para os valores normalizados
- `_detect_showdown()` verifica `"hero: shows"` em vez de `"SHOW DOWN"` — elimina falsos positivos quando hero foldou
- `llm_explainer.py`: `e.get('field', 0)` retornava `None` quando campo existe com valor `None`; corrigido para `(e.get('field') or 0)` em 4 métricas de evolução
- Opacidade das células "em breve" no HUD elevada de `/25` para `/50` (visíveis)

---

## [2026-04-25e] — HUD Stats: fix 3BET e W$SD (normalize action + showdown participation)

### Corrigido
- **`backend/leaklab/pipeline.py`**: `is_3bet` verificava `'raises'/'all-in'` mas `_normalize_action()` converte para `'raise'/'jam'`; corrigido para os valores normalizados
- **`backend/api/app.py`**: `_detect_showdown()` agora verifica se hero mostrou cartas (`hero: shows`) em vez de apenas se houve showdown na mão — elimina falsos positivos quando hero foldou mas outros jogadores foram a showdown (reduz de ~100 para ~24 showdowns reais)

---

## [2026-04-25d] — HUD Stats: 3BET% e W$SD implementados

### Adicionado
- **`backend/database/schema.py`**: colunas `is_3bet BOOLEAN` e `showdown_result TEXT` na tabela `decisions`; migrations adicionadas para SQLite e PostgreSQL
- **`backend/leaklab/pipeline.py`**: flag `is_3bet` calculada em `build_decision_input` — True quando hero re-raised pré-flop com `facing_size > 0` (alguém já tinha apostado antes)
- **`backend/api/app.py`**: função `_detect_showdown(raw_text, hero)` detecta se mão foi a showdown e se hero coletou o pote; `is_3bet` e `showdown_result` propagados no enriched dict e salvos no banco
- **`backend/database/repositories.py`**: `save_decisions` inclui `is_3bet` e `showdown_result`; `get_player_stats` computa 3BET% (hands com is_3bet / total preflop hands) e W$SD (hands won at showdown / total showdown hands)
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: 3BET e W$SD removidos de `soon: true`; tipos atualizados para `number | null`; tooltips revisados
- **`frontend/src/lib/api.ts`**: `three_bet` e `w_at_sd` tipados como `number | null`

---

## [2026-04-25c] — HUD Stats: fix visibilidade células "em breve" (3BET, W$SD)

### Corrigido
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: células 3BET e W$SD estavam invisíveis — opacidades do status `na` elevadas de `/25`→`/50` (valor), `/40`→`/60` (label e "em breve"), `/30`→`/50` (ref MTT); células ficam visivelmente "desabilitadas" mas legíveis

---

## [2026-04-25b] — GGPoker parser: suporte completo + fix hero detection

### Adicionado
- **`backend/leaklab/parser.py`**: suporte a GGPoker — detecção automática por header (`Poker Hand #`), split regex por site, ID regex `#(\w+)` para prefixos SG/RC/HD; função `parse_hand_history()` unificada detecta site e parseia qualquer arquivo
- **`backend/api/app.py`**: `_detect_site()` atualizado para reconhecer GGPoker; `_extract_financials()` soma `collected X from pot` do hero para calcular prize em Spin & Go

### Corrigido
- **`backend/leaklab/parser.py`**: `HERO_DEALT_RE` alterado de `[^\[]+` para `[^\[\n]+` — impedia que o nome do hero capturasse múltiplas linhas `Dealt to` de oponentes no formato GGPoker, onde cada jogador tem sua própria linha

### Alterado
- **`CLAUDE.md`**: menção ao suporte a GGPoker adicionada à descrição do projeto

---

## [2026-04-25a] — Player HUD Stats como strip full-width + LeaksPanel compacto

### Alterado
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: redesenhado como strip horizontal full-width com 4 células (VPIP, PFR, AF, Flop Bet) separadas por dividers; header com contagem de mãos; responsivo 2×2 em mobile e 4×1 em desktop
- **`frontend/src/components/hud/LeaksPanel.tsx`**: redesenhado como lista compacta — cada leak ocupa uma linha de ~36px com dot de severidade, label truncado, badge de contagem e botão Estudar inline; eliminados o card grande com parágrafo de descrição
- **`frontend/src/pages/Index.tsx`**: `PlayerStatsCard` movido para entre os KPIs e o grid principal (full-width, destaque máximo); removido do sidebar

---

## [2026-04-24d] — Player HUD Stats: VPIP, PFR, Aggression Factor, Flop Bet%

### Adicionado
- **`backend/database/repositories.py`**: nova função `get_player_stats(user_id, days)` que agrega decisões por mão e computa VPIP, PFR, AF (Aggression Factor) e Flop Bet% diretamente das decisões armazenadas
- **`backend/api/app.py`**: novo endpoint `GET /metrics/player-stats?days=N` que retorna o perfil de jogo calculado
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: novo card HUD exibindo as 4 stats computáveis (VPIP, PFR, AF, Flop Bet%) com barra de progresso colorida vs. referência MTT; 4 stats futuras (3BET, Fold to 3BET, WTSD, W$SD) exibidas como "Em breve" com tooltip explicativo
- **`frontend/src/lib/api.ts`**: interface `PlayerStatsResponse` e método `metrics.playerStats(days)`
- **`frontend/src/pages/Index.tsx`**: `PlayerStatsCard` adicionado à sidebar do dashboard

### Referências MTT usadas
| Stat | Ref MTT | Status |
|------|---------|--------|
| VPIP | 12–22% | ✅ Calculado |
| PFR | 9–18% | ✅ Calculado |
| AF | 2.0–4.0x | ✅ Calculado |
| Flop Bet | 40–65% | ✅ Calculado |
| 3BET | 4–8% | 🔜 Em breve |
| Fold to 3BET | 55–72% | 🔜 Em breve |
| WTSD | 25–35% | 🔜 Em breve |
| W$SD | 50–60% | 🔜 Em breve |

---

## [2026-04-24c] — Cartas do villain reveladas no momento do "shows", não só no showdown final

### Corrigido
- **`backend/api/app.py`**: `_build_replay_data` agora pré-escaneia o `raw_text` para linhas `player: shows [cards]` e acumula `current_revealed` conforme as ações ocorrem; `revealed_cards` é incluído em cada step de action e street (não apenas no step final de showdown)
- **`frontend/src/pages/Replayer.tsx`**: `buildSeats()` verifica `step.revealed_cards` em qualquer tipo de step, sem depender de `step.type === 'showdown'`; `revealed: true` é setado assim que o backend sinaliza as cartas

---

## [2026-04-24b] — Showdown na mesa + apostas posicionadas dentro da mesa

### Corrigido
- **`frontend/src/components/hud/PokerTable.tsx`**: cartas dos villains agora exibidas no showdown — nova prop `revealed` em `Seat`; condição `hidden` alterada para `!seat.hero && !seat.revealed`; chips de aposta movidos para fora do `SeatBubble` e renderizados como elementos absolutamente posicionados entre o assento e o centro da mesa via `betPosition(sx, sy, 0.42)`
- **`frontend/src/pages/Replayer.tsx`**: `buildSeats()` agora passa `revealed: true` para assentos de villain no step de showdown quando `revealed_cards` está presente

---

## [2026-04-24a] — Replayer conectado ao backend + botões de replay nas mãos

### Adicionado
- **`frontend/src/pages/Replayer.tsx`**: reescrito para consumir dados reais do backend via `GET /replay/<t>/<h>`; usa `useSearchParams` para ler `?t=` e `?h=` da URL; exibe mesa de poker com assentos, pot e board reais por step; log de ações com hero em destaque e erros marcados; painel de EV/feedback com equity, pot odds, M ratio e pressão ICM; estados de loading, erro e sem-parâmetros
- **`frontend/src/lib/api.ts`**: interfaces `ReplaySeat`, `ReplayStep`, `ReplayData`; método `tournaments.replay(tournamentId, handId)` → `GET /replay/:t/:h`
- **`frontend/src/pages/TournamentDetail.tsx`**: botão "Abrir no replayer" em cada card de mão (navega para `/replayer?t=<id>&h=<handId>`); botão "Replay completo" agora clicável (navega para primeira mão do torneio); link "Replayer" compacto na linha de ações quando análise IA já está carregada

### Corrigido
- **`frontend/src/pages/TournamentDetail.tsx`**: referência a `h.resultBb` (campo inexistente) substituída por `h.evDelta`

---

## [2026-04-23b] — UI leaklabs: onboarding, detalhe de torneio, AI Report

### Adicionado
- **`frontend/src/components/hud/EmptyDashboard.tsx`**: tela de onboarding para novos usuários — upload com drag-and-drop conectado ao `POST /analyze`, cards dos 3 módulos com estilo `tactical-corners`, dispara `onComplete` para refresh do dashboard
- **`frontend/src/components/hud/TournamentAiReport.tsx`**: painel lateral deslizante de análise IA por torneio — chama `POST /analyze/tournament-summary` com `tournament_db_id`, exibe resumo cacheado (`llm_summary`) se já existir, seções colapsáveis em markdown com tonal por tipo (erro/ponto forte/neutro)
- **`frontend/src/pages/TournamentDetail.tsx`**: página de detalhe de torneio — agrupa decisões por mão (`groupByHand`), filtra por severidade e street, exibe cartas com `PlayingCard`, integra `TournamentAiReport` com ID real do banco
- **`frontend/src/index.css`**: variáveis CSS para cartas (`--card-face`, `--card-suit-dark`, `--card-suit-red`) e utilitário `.tactical-corners` com pseudo-elementos de canto

### Alterado
- **`frontend/src/lib/api.ts`**: adicionado tipo `TournamentDecision`; `tournaments.get()` retorna `{ tournament, decisions }`
- **`frontend/src/App.tsx`**: rota `/tournaments/:id` com `TournamentDetail` protegida por auth
- **`frontend/src/components/hud/HudHeader.tsx`**: branding atualizado de "PokerLeaks.os" → "LeakLabs.ai"; item "Replayer" removido da navegação
- **`frontend/src/pages/Index.tsx`**: exibe `EmptyDashboard` quando não há torneios importados (primeiro acesso)
- **`frontend/src/pages/Tournaments.tsx`**: clique em linha navega para `/tournaments/:tournament_id`

---

## [2026-04-23a] — Integração completa backend + frontend React

### Adicionado
- **`frontend/src/lib/auth.tsx`**: contexto React de autenticação (`AuthProvider`, `useAuth`) — gerencia token JWT via `sessionStorage`, verifica `/auth/me` na inicialização, expõe `login`, `register`, `logout`
- **`frontend/src/pages/Login.tsx`**: página de login/registro com tabs, design HUD, mensagem de erro inline e redirecionamento automático se já autenticado
- **`frontend/.env`**: variável `VITE_API_URL=http://localhost:5000` para dev local
- **`backend/api/app.py` — `POST /coach/chat`**: endpoint conversacional do AI Coach; carrega leaks e evolução reais do usuário, chama `coach_chat_reply` e retorna a resposta do LLM
- **`backend/api/app.py` — `GET /coach/context`**: retorna `hands_analyzed`, `tournaments_analyzed`, `top_leaks`, `avg_score` e `standard_pct` do usuário para o painel de contexto do Coach
- **`backend/leaklab/llm_explainer.py` — `coach_chat_reply`**: função de chat conversacional com Claude Haiku; injeta dados reais de desempenho do jogador como contexto no system prompt

### Alterado
- **`frontend/src/App.tsx`**: adicionado `AuthProvider`, rota `/login` e `ProtectedRoute` (redireciona para `/login` se não autenticado) em todas as páginas internas
- **`frontend/src/components/hud/HudHeader.tsx`**: exibe username do usuário logado e botão de logout; `LogOut` icon via lucide-react
- **`frontend/src/pages/AICoach.tsx`**: conectado ao backend — carrega contexto via `GET /coach/context` na montagem, saudação inicial personalizada com dados reais, chat conectado a `POST /coach/chat` com loading state e scroll automático
- **`frontend/src/components/hud/UploadZone.tsx`**: lê arquivo como texto, chama `POST /analyze`, exibe feedback visual (loading → ok → erro) e dispara callback `onResult` para refresh do dashboard
- **`frontend/src/components/hud/LeaksPanel.tsx`**: aceita prop `leaks` da API; mapeia `avg_score` para severidade (crítico/moderado/leve); fallback para dados demo quando sem dados reais
- **`frontend/src/components/hud/BankrollChart.tsx`**: aceita prop `evolution` da API; plota lucro cumulativo real; fallback para dados demo
- **`frontend/src/components/hud/RecentTournamentsTable.tsx`**: aceita prop `tournaments` da API; formata datas, profit e place reais; fallback para dados demo
- **`frontend/src/pages/Index.tsx`**: busca `GET /history/evolution` e `GET /history/tournaments` na montagem; calcula KPIs reais (ROI, ITM%, Avg Buy-In, Total Eventos); refresh automático após upload
- **`frontend/src/pages/Tournaments.tsx`**: carrega lista real via `GET /history/tournaments`; loading state, filtro por rede e ordenação funcional com dados reais

---

## [2026-04-23i] — Migração frontend para React + TypeScript

### Alterado
- **Frontend migrado de HTML monolítico para React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui**
  - Base: projeto gerado pelo Lovable (poker-leak-finder) trazido para `frontend/`
  - `frontend/index.legacy.html` — backup do frontend vanilla anterior
  - `frontend/src/` — novo frontend React com arquitetura componentizada
  - `vercel.json` atualizado para build com `@vercel/static-build`
  - `.gitignore` atualizado: `frontend/node_modules/`, `frontend/dist/`

### Motivação
- Segurança: HTML monolítico sem isolamento de escopo, JWT exposto em JS inline, sem CSP
- Manutenibilidade: arquivo único de ~3000 linhas impossível de auditar e testar
- Arquitetura componentizada elimina classes de bugs de DOM stale e permite testes unitários

### Próximos passos
- Conectar API client (`src/lib/api.ts`) ao backend Flask
- Implementar autenticação (contexto JWT, rotas protegidas)
- Substituir dados mock por chamadas reais ao backend

---

## [2026-04-23h]

### Corrigido
- **Botão "Gerar Resumo" sem ação**: `tSummaryLoaded` persiste em memória durante toda a sessão do browser. Torneios com o mesmo PokerStars ID (após reset/reimport) bloqueavam silenciosamente a função `generateTSummary` na linha `if(tSummaryLoaded[tid])return`. Corrigido limpando o objeto em `_renderTournamentList` sempre que a lista é re-renderizada.

---

## [2026-04-23g]

### Corrigido
- **Coach IA retornava template estático**: `_call_llm_summary` usava `_json.dumps()` mas o módulo foi importado como `json`. O `NameError` era silenciado pelo `except Exception`, fazendo o sistema cair sempre no fallback estático. Corrigido para `json.dumps()`.

---

## [2026-04-23f]

### Corrigido
- **Coach IA — "Torneio não encontrado no banco"**: após importar um torneio, o objeto inserido em `tourns[]` em `_applyRealData` não tinha o campo `dbId` mapeado. O frontend buscava `tObj.dbId` para enviar ao endpoint `/analyze/tournament-summary`, encontrava `undefined` e mostrava o erro. Adicionado `dbId: data.tournament_db_id` ao objeto construído após a análise.

---

## [2026-04-23e]

### Corrigido
- **Frontend `API_URL` com `file://`**: ao abrir `index.html` diretamente do sistema de arquivos, `location.hostname` é `''` (string vazia) e a detecção de `localhost` falhava, direcionando todas as chamadas para o servidor de produção (Render). Adicionada verificação `!h` para cobrir o protocolo `file://`.

---

## [2026-04-23d]

### Corrigido
- **`load_dotenv` com caminho absoluto**: substituído `os.path.dirname(__file__)` por `Path(__file__).resolve().parent` em `app.py` para evitar falha no subprocess do Flask reloader que não resolvia caminhos relativos corretamente.
- **Timeout do study plan**: aumentado de 30s para 90s em `llm_explainer.py`; chamadas ao Claude Haiku para geração de plano com 400+ decisões podem ultrapassar 30s.

### Resultado
- Study plan com LLM funcional localmente: 6 cards gerados, resumo personalizado, `error: null`.

---

## [2026-04-23c]

### Adicionado
- **`backend/.env`** (gitignored): variáveis de ambiente para dev local (`ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`).
- **`python-dotenv`** adicionado a `requirements_dev.txt`; `app.py` carrega `.env` automaticamente via `load_dotenv()` na inicialização.

---

## [2026-04-23b]

### Adicionado
- **`backend/requirements_dev.txt`**: dependências para desenvolvimento local sem `psycopg2-binary` (incompatível com Python 3.13/Windows); ambiente local usa SQLite.

### Ambiente local
- Backend: `cd backend && python api/app.py` → `http://localhost:5000`
- Frontend: abrir `frontend/index.html` no browser (detecta `localhost` automaticamente e aponta para porta 5000)

---

## [2026-04-23]

### Corrigido
- **Imports `gaphunter` → `leaklab`**: 7 arquivos de teste importavam o nome antigo do pacote (`gaphunter`), causando `ModuleNotFoundError` em toda a suite `engine` e `regression`.
- **Coluna `raw_text` ausente no schema SQLite**: a coluna existia apenas na migração PostgreSQL; adicionada ao `CREATE TABLE` e à lista de migrações SQLite em `database/schema.py`, corrigindo 8 falhas na suite `database`.

### Adicionado
- **`CLAUDE.md`**: documentação para Claude Code com comandos de build/teste, arquitetura e stack.
- **`CHANGELOG.md`**: este arquivo.
- **`.gitignore`**: entradas para `backend/torneio_ingles.txt` (fixture local com dados pessoais) e `.claude/` (configuração do Claude Code).

### Resultado
- Testes: **227/227 passando** (todas as suites: engine, database, llm, api, regression).
