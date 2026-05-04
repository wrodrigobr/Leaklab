# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprints 1–13 + Sprint A–T + BACK-008 + BACK-015 — ver CHANGELOG v0.9.0 a v0.51.0.
> **Sprint atual:** Sprint AE — UX-013 JAM → All In

---

## Princípio de Produto

> **A plataforma é primariamente um coach IA autônomo para o aluno.**
> O aluno não precisa — e nunca deve precisar — de um coach humano para extrair valor completo do sistema.
> Análise de leaks, plano de estudos, replayer, gamificação e evolução de score são o **core** e funcionam de forma independente.
>
> O marketplace de coaches humanos é uma **camada adicional opcional** — um upgrade de valor, não um pré-requisito.
> Calls-to-action de contratação de coach devem ser **suaves e contextuais**, jamais bloqueantes ou centrais no fluxo principal.
> Sprints de IA têm prioridade estratégica maior do que sprints de marketplace.

---

## Roadmap de Sprints — Status Atual

| Sprint | Itens | Tema | Status |
|---|---|---|---|
| Sprint 1–3 | — | Infraestrutura, Student View, Study Plan | ✅ v0.9.0–v0.10.2 |
| Sprint 4 | BACK-001 + BACK-005 | Anotações de mãos + Selo Coach | ✅ v0.12.0 + v0.32.0 |
| Sprint 5 | BACK-003 + BACK-004 | Coach analytics multi-aluno | ✅ v0.13.0 |
| Sprint 6 | BACK-002 | Feed de progresso + baseline | ✅ v0.14.0 |
| Sprint 7 | BACK-006 pt.1 | Perfil estendido + reviews | ✅ v0.15.0 |
| Sprint 8 | BACK-006 pt.2 + BACK-013 | Diretório público + descoberta contextual | ✅ v0.16.0 |
| Sprint 9 | BACK-007 + BACK-012 | Upload múltiplo + perfil coach unificado | ✅ v0.17.0 |
| Sprint 10 | BACK-009 | Sistema de nível + gamificação | ✅ v0.18.0 |
| — | BACK-008 | Visualizador de ranges no replayer | ✅ v0.19.0 |
| Sprint 11 | BACK-010 | Planos comerciais + quota | ✅ v0.22.0 |
| Sprint 12 | BACK-011 | Anti-injection + moderação de conteúdo | ✅ v0.26.0–v0.27.0 |
| Sprint 13 | UX-004 | Menu de conta com plano e uso | ✅ v0.25.0 |
| Sprint A | UX-001 + UX-003 | Lista de torneios + tooltips auto-explicativos | ✅ v0.31.0 |
| Sprint 15 | BACK-015 | Gateway de pagamento (Stripe) | ✅ v0.29.0 |
| Sprint B | UX-002 | Responsividade mobile/tablet | ✅ v0.33.0 |
| Sprint C+E | BACK-014 + BACK-017 | Revenue share + Admin Panel | ✅ v0.34.0 |
| Sprint D | BACK-016 | WhatsApp Coaching Drills | ✅ v0.36.0 |
| Sprint F | UX-005 | Internacionalização (i18n) — PT/EN/ES | ✅ v0.35.0 |
| Sprint G | UX-006 | Header cleanup + i18n full coverage | ✅ v0.37.0 |
| Sprint H | UX-007 | Dashboard cards i18n — 11 componentes | ✅ v0.38.0 |
| Sprint I | PERF-001 + PERF-002 | ROI Attribution Engine + Leak Priority Optimizer | ✅ v0.39.0 |
| Sprint J | PERF-003 + PERF-004 + PERF-005 | Leak Progression + Pressure Collapse + Confidence Drift | ✅ v0.40.0 |
| Sprint K | PERF-006 | Ghost Table Simulator MVP | ✅ v0.41.0–v0.42.0 |
| Sprint L | PERF-007 | Decision DNA — assinatura estratégica do jogador | ✅ v0.43.0 |
| Sprint M | PERF-008 | Tournament Narrative Engine | ✅ v0.45.0 |
| Sprint N | PERF-009 | GGPoker Parser — detecção automática de formato | ✅ (já entregue) |
| Sprint O | FEAT-01 | Comparativo de Torneios | ✅ v0.46.0 |
| Sprint P | FEAT-04 | Relatório PDF Premium | ✅ v0.47.0 |
| Sprint Q | FEAT-02 + FEAT-03 | Daily Focus + XP Server-Side | ✅ v0.48.0 |
| Sprint R | FEAT-05 | SRS Adaptativo nos Drills | ✅ v0.49.0 |
| Sprint S | FEAT-06 | Leak Causal Map | ✅ v0.50.0 |
| Sprint T | FEAT-07 | Coach Effectiveness Metrics | ✅ v0.51.0 |
| Sprint U | FEAT-08 | Session Goals + AI Review | ✅ v0.52.0 |
| Sprint V | FEAT-09 + FEAT-10 | Coach Templates + Coach Messaging | ✅ v0.53.0 |
| Sprint W | FEAT-11 | Weekly Digest Email | ✅ v0.54.0 |
| Sprint Y | UX-008 | Coaches Directory — mobile layout + remover "professor" | ✅ v0.55.0 |
| Sprint Z | UX-009 | Torneios — data do torneio vs importação + exibir ano | ✅ v0.56.0 |
| Sprint AA | INFRA-001 | Correção de erros de build no Render (backend) e Vercel (frontend) | ✅ v0.57.0 |
| Sprint AB | UX-010 | Filtros de período no gráfico de Bankroll (1M/3M/1A/tudo) não funcionam | ✅ v0.58.0 |
| Sprint AC | UX-011 | Dashboard — remover nome do hero, "Centro de Comando" → "Dashboard", corrigir quebra de linha no subtítulo | ✅ v0.59.0 |
| Sprint AD | UX-012 | Dashboard — remover lista de últimos torneios (há menu próprio); liberar espaço para cards de indicadores | ✅ v0.60.0 |
| Sprint AE | UX-013 | Substituir "JAM" por "All In" em toda a plataforma (UI, textos, labels, parser output) | ✅ v0.63.1 |
| Sprint AF | UX-014 | Página do Coach (StudentDetail) — remover limitação horizontal, aproveitar melhor o espaço disponível em telas largas | ✅ v0.64.0 |
| Sprint AL | UX-017 | Dashboard personalizável — arrastar e reordenar cards, preferência salva por usuário | ⏳ |
| Sprint AH | BACK-018 | Coach Application Flow — candidatura com aprovação manual pelo admin | ✅ v0.65.0 |
| Sprint AI | BACK-019 | Perfil demográfico do usuário — idade, localização, experiência de poker | ✅ v0.66.0 |
| Sprint AJ | UX-015 | Inbox global de mensagens para o coach — ver todas as conversas com badge de não lidas | ✅ v0.67.0 |
| Sprint AK | UX-016 | Badge de mensagens não lidas no dashboard/header do aluno → link direto para conversa com coach | ✅ v0.67.0 |
| Sprint AM | UX-018 | Listagem de alunos do coach — tabela com busca, filtros (ativo/inativo, plano) e paginação | ⏳ |
| Sprint AG | FEAT-12 | Página de Documentação / Wiki do Sistema (deixar por último) | ⏳ |

---

## Próximas Sprints — Em Aberto

### [UX-018] — Listagem de Alunos com Tabela e Filtros *(Sprint AM)*

**Problema:** a lista de alunos no CoachDashboard é uma lista simples (`<ul>`) — com muitos alunos fica ilegível e sem capacidade de busca ou triagem.

**Solução:** substituir por tabela com busca por nome, filtros de status (ativo/inativo) e plano, ordenação por coluna e paginação client-side (25 por página).

**Escopo:**
- Busca por nome (debounce 300ms)
- Filtro "Status": Todos / Ativos / Inativos
- Filtro "Plano": Todos / Free / Pro / Premium
- Colunas clicáveis para ordenar: Aluno, Plano, Torneios, Último import, Status
- Paginação: botões Anterior / Próximo com contagem "1–25 de 47"
- Clique na linha → navega para `/coach-dashboard/student/:id`
- Sem mudança de backend — os dados já vêm via `GET /coach/students`

**Arquivos:**
- `frontend/src/pages/coach/CoachDashboard.tsx` — substituir `<ul>` da AlunosTab por tabela com filtros

**Esforço:** ~4h frontend puro

---

### [UX-017] — Dashboard Personalizável *(Sprint AL)*

**Problema:** o layout do dashboard é fixo — jogadores têm estilos e prioridades diferentes (alguns vivem no Ghost Table, outros focam no Leak Causal Map), mas todos veem a mesma ordem.

**Solução:** drag-and-drop para reordenar os cards do dashboard, com preferência salva por usuário.

**Escopo:**
- Cards arrastáveis: LeaksPanel, LeakCausalMap, LevelCard, GhostDrillCard, PressureProfileCard, IcmBreakdown, AI Confidence (os cards de posição fixa — KPIs, BankrollChart, PlayerDnaCard — permanecem fixos pois são hierarquicamente prioritários)
- Reordenação dentro de cada coluna (aside e coluna de baixo) — não troca de coluna
- Ícone de drag handle (⠿) visível ao hover no header de cada card
- Botão "Restaurar padrão" no header do dashboard

**Persistência — server-side:**
- Coluna `dashboard_layout TEXT` (JSON serializado) na tabela `users` — padrão `NULL` (= layout default)
- `GET /player/preferences` — retorna `{ dashboard_layout: string[] | null }` junto com outros dados do usuário; pode ser incluído na resposta do `/auth/me` para evitar request extra
- `PATCH /player/preferences` — recebe `{ dashboard_layout: string[] }` e persiste; debounce de 1s no frontend para não disparar a cada pixel arrastado
- Layout sincronizado entre devices automaticamente — ao abrir em outro browser, carrega a mesma ordem

**Biblioteca:** `@dnd-kit/core` + `@dnd-kit/sortable` (acessível, sem dependência de mouse, funciona em touch/mobile)

**Arquivos:**
- `backend/database/schema.py` — `ALTER TABLE users ADD COLUMN dashboard_layout TEXT DEFAULT NULL`
- `backend/database/repositories.py` — `get_user_preferences(user_id)`, `save_user_preferences(user_id, layout)`
- `backend/api/app.py` — `GET /player/preferences`, `PATCH /player/preferences`; adicionar `dashboard_layout` na resposta do `/auth/me`
- `frontend/package.json` — adicionar `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`
- `frontend/src/hooks/useDashboardLayout.ts` — hook que lê do `/auth/me` (ou `/player/preferences`) e persiste via `PATCH` com debounce
- `frontend/src/pages/Index.tsx` — envolver cards arrastáveis com `SortableContext`
- `frontend/src/components/hud/DraggableCard.tsx` — wrapper com drag handle
- `frontend/src/lib/api.ts` — `preferences.get()`, `preferences.save(layout)`

**Esforço:** ~4h backend + ~8h frontend

---

### [UX-015] — Inbox Global de Mensagens para o Coach *(Sprint AJ)*

**Problema:** o coach precisa abrir o perfil de cada aluno para verificar se há mensagens não lidas — inviável com muitos alunos.

**Solução:** inbox global no `CoachDashboard.tsx` — lista todas as conversas com badge de não lidas e acesso direto.

**Backend:**
- `GET /coach/messages/inbox` — retorna todas as conversas ativas: `[{student_id, student_username, last_message_body, last_message_at, unread_count}]`
- Ordenado por `last_message_at DESC` (conversa mais recente primeiro)

**Frontend:**
- Nova aba "Mensagens" no `CoachDashboard.tsx` (ao lado de Alunos, Analytics, etc.)
- Cada linha: avatar inicial, nome do aluno, prévia da última mensagem (truncada), timestamp relativo ("5 min", "ontem"), badge vermelho com contagem de não lidas
- Clique → abre `StudentDetail` do aluno direto na aba de Mensagens
- Badge de não lidas total no tab "Mensagens" do dashboard (polling 60s)

**Esforço:** ~4h backend + ~6h frontend

---

### [UX-016] — Badge de Mensagens Não Lidas no Aluno *(Sprint AK)*

**Problema:** o aluno só vê as mensagens do coach se navegar até a página AI Coach — sem nenhuma indicação visual de mensagem pendente.

**Solução:** badge no header e/ou dashboard do aluno com contagem de não lidas + link direto.

**Observação:** parte desta feature já foi implementada no `HudHeader.tsx` (Sprint V) — há um `MessageSquare` com badge via polling 60s visível quando `user.coach_id` existe e `unreadCount > 0`. O que falta é:
- Confirmar que o link do badge leva para `/coach` (aba de AI Coach com o `CoachMessagesPanel`)
- Adicionar no `CoachMessagesPanel` um estado de "não lidas" mais visível (scroll automático, highlight nas mensagens novas)
- Verificar se o badge desaparece ao marcar como lido quando o painel é aberto

**Esforço:** ~2h (revisão e ajustes do que já existe)

---

### [BACK-019] — Perfil Demográfico do Usuário *(Sprint AI)*

**Problema atual:** o cadastro coleta apenas username, email, senha e role — sem dados que permitam benchmarks, segmentação ou pesquisa de produto.

**Estratégia:** não adicionar campos ao formulário de cadastro (evitar abandono). Os dados são coletados em um card "Complete seu perfil" exibido no dashboard pós-login — colapsável, voluntário, com nota LGPD clara.

**Campos coletados:**
- `birth_year` (INTEGER) — para faixa etária; não armazenar data exata
- `country` (TEXT) — país
- `state_province` (TEXT) — estado / província
- `city` (TEXT) — cidade
- `poker_experience_years` (INTEGER) — anos de experiência (0 = iniciante)
- `main_game_type` (TEXT) — `mtt` / `cash` / `spin` / `mixed`
- `usual_buyin_range` (TEXT) — `micro` (<$5) / `low` ($5–$30) / `mid` ($30–$200) / `high` (>$200)
- `profile_completed_at` (TIMESTAMP) — usado para controlar exibição do card; NULL = nunca preencheu

**Backend:**
- Migração com `ALTER TABLE users ADD COLUMN` para cada campo (SQLite + Postgres)
- `GET /player/profile` — retorna campos demográficos do usuário logado
- `PATCH /player/profile` — atualiza campos; marca `profile_completed_at`
- `GET /admin/demographics` (admin) — agrega dados anonimizados: distribuição por país/estado, faixa etária, experiência, game type — para uso em relatórios e produto

**Frontend:**
- `ProfileCompletionCard.tsx` — card colapsável no dashboard, exibido quando `user.profile_completed_at` é null; barra de progresso dos campos preenchidos; botão "Não mostrar novamente" armazena dismissal em `localStorage`; nota LGPD: *"Dados usados apenas para benchmarks agregados e anonimizados — nunca compartilhados individualmente"*
- `frontend/src/pages/StudentProfile.tsx` ou nova aba em configurações — formulário completo de edição do perfil demográfico
- `UserProfile` em `api.ts` — adicionar campos demográficos opcionais
- Dashboard admin — nova seção "Demographics" com distribuição geográfica e de experiência

**Uso dos dados (valor direto para o produto):**
- Benchmarks: "Sua standard% está X% acima da média de jogadores do Brasil com 2–5 anos de experiência"
- Segmentação de emails (digest por faixa de buyin)
- Pesquisa de produto: quais países têm maior engajamento, quais faixas de buyin têm maior retenção
- Futuramente: rankings regionais, torneios com filtro de stake

**Esforço:** ~8h backend + ~6h frontend

---

### [BACK-018] — Coach Application Flow *(Sprint AH)*

**Problema atual:** qualquer pessoa pode se registrar como coach livremente via `POST /auth/register` com `role: "coach"`, sem qualquer validação de profissionalismo.

**Solução:** fluxo de candidatura com aprovação manual pelo admin.

**Fluxo:**
1. Na página de registro, quem escolhe "Coach" é redirecionado para um formulário de candidatura — não cria conta imediatamente
2. Candidatura salva com status `pending`; conta criada com role `coach_pending` (sem acesso ao painel de coach e sem login)
3. Admin vê candidaturas pendentes no painel — pode aprovar ou rejeitar com nota opcional
4. Aprovação: role muda para `coach`, email de boas-vindas enviado via SMTP (mesmo do digest)
5. Rejeição: email com motivo opcional; conta pode ser removida ou mantida como registro

**Backend:**
- Tabela `coach_applications`: `id`, `user_id` (FK users), `instagram_handle`, `bio`, `specialties`, `experience_years`, `biggest_results`, `status` (`pending`/`approved`/`rejected`), `admin_note`, `created_at`, `reviewed_at`
- `POST /auth/coach-apply` — cria usuário com role `coach_pending` + salva candidatura (sem JWT, público)
- `GET /admin/coach-applications` — lista candidaturas por status
- `POST /admin/coach-applications/<id>/approve` — muda role para `coach`, envia email
- `POST /admin/coach-applications/<id>/reject` — armazena nota, envia email de rejeição opcional
- Bloquear login para role `coach_pending` — retorna 403 com mensagem "Candidatura em análise"

**Frontend:**
- `frontend/src/pages/CoachApply.tsx` — formulário público: nome, email, senha, @instagram, bio, especialidades, anos de experiência, maiores resultados; botão "Enviar candidatura"
- Página de confirmação pós-envio: "Candidatura recebida — você receberá um email quando for analisada"
- `frontend/src/pages/admin/AdminPanel.tsx` — nova aba "Candidaturas" com lista de pendentes, botões approve/reject, campo de nota
- Tela de login — exibir mensagem específica para `coach_pending` (não mostrar erro genérico de credenciais)

**Esforço:** ~10h backend + ~8h frontend

---

### [FEAT-01] — Comparativo de Torneios *(Sprint O — 🔄 em andamento)*

**Valor:** Compara qualidade técnica de decisão entre 2–4 torneios — não só resultado financeiro. Nenhuma outra ferramenta de poker faz isso.

**Backend:** `GET /history/tournaments/compare?ids=A,B,C` — agrega `standard_pct`, `avg_score`, `clear_pct`, top 3 leaks, phase breakdown, ICM collapse delta por torneio. Narrativa comparativa via LLM (Haiku, ~100 tokens).

**Frontend:** Multi-seleção em `/tournaments` → página `TournamentCompare.tsx` com tabela lado a lado + sparklines + leaks com delta colorido (verde=melhorou, vermelho=piorou).

**Esforço:** ~8h backend + ~10h frontend

---

### [FEAT-04] — Relatório PDF Premium *(Sprint P)*

**Valor:** Relatório com design profissional (Google Fonts, gráficos SVG, paleta dark) que coach envia ao aluno e jogador compartilha. Também marketing orgânico.

**Backend:** Redesign completo de `report_generator.py` com template Jinja2 + WeasyPrint para conversão PDF. Endpoint `GET /history/tournament/<id>/report.pdf`.

**Frontend:** Botão "Baixar PDF" em `TournamentDetail.tsx`.

**Esforço:** ~12h backend + ~2h frontend

---

### [FEAT-02] — Daily Focus *(Sprint Q — junto com FEAT-03)*

**Valor:** Elimina paralisia de decisão — diz exatamente o que fazer hoje com base nos dados reais do jogador. Zero LLM, lógica determinística.

**Backend:** `GET /player/daily-focus` — 1 ação primária + 2 secundárias com links diretos (leak drill, torneio pendente, estudo).

**Frontend:** `DailyFocusCard.tsx` no topo do dashboard com timer até meia-noite e badge "concluído".

**Esforço:** ~6h backend + ~5h frontend

---

### [FEAT-03] — XP e Progressão Server-Side *(Sprint Q — junto com FEAT-02)*

**Valor:** Elimina bug silencioso de retenção — XP vive em localStorage e reseta ao limpar o browser.

**Backend:** Colunas `xp_total`, `xp_updated_at` em `users`. Tabela `achievements`. Endpoints `/player/xp` e `/player/achievements`.

**Frontend:** `LevelCard.tsx` e `StudyPlan.tsx` migram de localStorage para API.

**Esforço:** ~8h backend + ~4h frontend

---

### [FEAT-05] — SRS Adaptativo nos Drills *(Sprint R)*

**Valor:** Substitui cooldown fixo de 7 dias por intervalos baseados em performance real (acerto → dobra, erro → reseta). Primeiro sistema SRS para poker baseado nas mãos do próprio jogador.

**Backend:** Campo `next_drill_at` em `drill_sessions`. `get_drill_spots` filtra por vencimento. Lógica: acerto → 3d→7d→14d→28d→60d; erro → reset 3d.

**Frontend:** `GhostDrillCard.tsx` e `GhostTable.tsx` exibem intervalo e indicador visual.

**Esforço:** ~10h backend + ~6h frontend

---

### [FEAT-06] — Leak Causal Map *(Sprint S)*

**Valor:** Mostra como leaks se causam mutuamente — diagnóstico sistêmico, não lista de erros isolados. Diferencial único no mercado.

**Backend:** `leak_causal_graph.py` analisa co-ocorrência de leaks por torneio. LLM explica os 3 pares mais correlacionados. Endpoint `/player/leak-graph`.

**Frontend:** `LeakCausalMap.tsx` — grafo SVG com nós por severidade e arestas proporcionais à correlação.

**Esforço:** ~14h backend + ~12h frontend

---

### [FEAT-07] — Métricas de Efetividade do Coach *(Sprint T)*

**Valor:** ROI verificado por dados: "alunos melhoram X% em standard_pct em 60 dias". Argumento de vendas mais forte do setor para coaches sérios.

**Backend:** `get_coach_effectiveness_report` — delta `standard_pct`/`avg_score` antes vs após baseline por aluno.

**Frontend:** Aba "Efetividade" no `CoachDashboard.tsx` + badge verificado em `PublicCoachProfile.tsx`.

**Esforço:** ~12h backend + ~10h frontend

---

### [FEAT-08] — Session Goals + Review Pós-Sessão via IA *(Sprint U)*

**Valor:** Liga intenção pedagógica ao resultado mensurável. Modal de meta antes do torneio → review automático após import comparando meta vs realidade.

**Backend:** Tabela `session_goals`. `generate_session_review` (Haiku, ~300 tokens).

**Frontend:** Modal pré-import em `UploadQueue.tsx` + card review em `TournamentDetail.tsx`.

**Esforço:** ~16h backend + ~14h frontend

---

### [FEAT-09] — Templates de Plano de Estudo (Coach) *(Sprint V — junto com FEAT-10)*

**Valor:** Coach cria metodologia reutilizável por arquétipo de aluno. Reduz fricção e escala o atendimento.

**Backend:** Tabela `coach_plan_templates`. CRUD endpoints.

**Frontend:** "Salvar como template" em `StudentDetail.tsx` + dropdown de aplicação.

**Esforço:** ~6h backend + ~8h frontend

---

### [FEAT-10] — Mensagens Coach-Aluno com Contexto de Mão *(Sprint V — junto com FEAT-09)*

**Valor:** Chat in-app com referência direta à mão discutida + link para replayer. Elimina WhatsApp/Discord onde o contexto técnico se perde.

**Backend:** Tabela `coach_messages`. Endpoints bidirecionais.

**Frontend:** Painel de chat em `StudentDetail.tsx` + badge de não lidas em `HudHeader.tsx`.

**Esforço:** ~18h backend + ~16h frontend

---

### [FEAT-11] — Digest Semanal por Email *(Sprint W)*

**Valor:** Recupera usuários que não abriram o app — email com EV loss real da semana, drill atrasado e evolução de standard_pct. Zero LLM (determinístico).

**Backend:** `email_digest.py` + cron toda segunda 9h. Template Jinja2. Integração SendGrid/SES.

**Frontend:** Banner "ativar digest" no dashboard + opt-out via token.

**Esforço:** ~14h backend + ~4h frontend

---

### [FEAT-12] — Página de Documentação / Wiki do Sistema *(Sprint X)*

**Valor:** Reduz fricção de onboarding — novos usuários e coaches entendem o que cada indicador significa sem precisar pedir suporte. Aumenta confiança técnica no produto (especialmente com coaches que querem validar a metodologia antes de assinar).

**O que é:** Uma página `/docs` estilo wiki, com navegação lateral por seções, explicando em profundidade:
- Como funciona o sistema de scoring de decisões (score 0–1, labels: standard/marginal/clear_mistake/disaster)
- O que é e como interpretar cada indicador: Standard%, Avg Score, Clear Mistakes%, Leak ROI, ICM Pressure
- Fases de M-ratio: Deep Stack / Mid Stack / Short Stack / Push/Fold — critérios e o que muda
- Decision DNA: o que representa cada eixo do radar (Agressividade, Fold Frequency, 3-Bet%, Positional Awareness, Disciplina)
- Ghost Table: como funciona o drill de spots, o que é cooldown/SRS, como interpretar o resultado
- Como ler o Comparativo de Torneios: o que é Delta, como interpretar "▲ melhor"
- Coaching: o que é um baseline, como funciona a medição de evolução, o que significa "Coach Reviewed"
- Gamificação: como XP é calculado, critérios de nível, conquistas

**Design:** Wiki-style dentro do HudLayout — sidebar fixa com links âncora, conteúdo em prosa técnica com exemplos, tabelas e badges reais do sistema. Sem imagens externas — usa os próprios componentes visuais do sistema como referência inline.

**Frontend only** — conteúdo estático, sem backend. Rota `/docs`.

**Esforço:** ~20h frontend (conteúdo + layout + navegação)

---

### [UX-008] — Coaches Directory — Mobile Layout + Padronização "Coach" *(Sprint Y)*

**Valor:** A página de coaches (`/coaches`) está com layout ruim em mobile — filtros e cards dos coaches cadastrados precisam ser reorganizados para uma experiência adequada em telas menores. Também há inconsistência terminológica: o termo "professor" aparece em algumas páginas e deve ser removido, mantendo sempre "Coach" como padrão em todo o sistema.

**Escopo:**
- Refatorar layout da página `CoachesDirectory.tsx`: filtros em coluna no mobile, cards com padding adequado
- Grep de toda a codebase por "professor" (strings visíveis ao usuário em PT-BR) e substituir por "Coach"
- Verificar i18n — todos os locales (PT-BR, EN, ES) devem usar "Coach" ou equivalente cultural correto

**Frontend only** — sem alterações de backend.

**Esforço:** ~5h frontend

---

### [UX-009] — Torneios — Data do Torneio vs Importação + Exibir Ano *(Sprint Z)*

**Valor:** A data exibida na tabela de torneios pode ser a data de importação (`imported_at`) em vez da data real do torneio (`played_at`). Além disso, o formato atual (DD/MM HH:MM) não mostra o ano — relevante para quem tem histórico de mais de um ano.

**Escopo:**
1. Verificar no backend se `played_at` é corretamente populado pelo parser (PokerStars e GGPoker) ou se fica como a data de importação
2. Atualizar `formatDate` em `Tournaments.tsx` para incluir o ano (ex: `DD/MM/YY` ou `DD/MM/YYYY`)
3. Se `played_at` não vier do arquivo, investigar como extrair do header da hand history e persistir corretamente
4. Manter ordenação padrão do mais recente para o mais antigo (já funciona via `sortDir: "desc"`)

**Esforço:** ~4h backend + ~1h frontend

---

### [INFRA-001] — Correção de Erros de Build no Render e Vercel *(Sprint AA)*

**Valor:** Garantir que os pipelines de CI/CD do Render (backend/Docker) e Vercel (frontend) funcionem sem erros após as mudanças recentes — WeasyPrint + render.yaml docker runtime, novos imports no frontend.

**Escopo:**
1. Verificar logs de build do Render após migração para `runtime: docker`
2. Verificar logs de build do Vercel após adição de novos componentes e imports
3. Corrigir quaisquer erros de tipagem, import missing, ou dependência ausente que apareçam no CI

**Esforço:** ~2h (diagnóstico + correção)

---

### [UX-012] — Dashboard — Remover Lista de Últimos Torneios *(Sprint AD)*

**Valor:** A lista de últimos torneios ocupa espaço no dashboard sem agregar informação única — o menu de Torneios já cobre essa necessidade com filtros e ordenação. Remover libera espaço para expandir os cards de indicadores (KPIs, gráficos, leaks).

**Escopo:**
- Remover o componente `RecentTournamentsTable` de `Index.tsx`
- Verificar se o componente é usado em outro lugar antes de deletar o arquivo
- Avaliar se o espaço liberado comporta um card adicional de indicador (ex: `ConfidenceDrift` ou `PressureProfileCard` promovidos para o topo)

**Frontend only** — sem alterações de backend.

**Esforço:** ~1h frontend

---

### Backlog Futuro (não priorizar agora)

| Item | Motivo de adiar |
|---|---|
| Counterfactual Replay | Exige simulação Monte Carlo prospectiva — não temos equity calculator para linhas hipotéticas |
| Reg Archetype Recognition | Exige dados de adversários; fora do escopo atual (análise do herói, não do field) |
| Competitive Benchmark Layer | Exige pool de dados de outros usuários; questões de privacidade + volume mínimo de usuários |
