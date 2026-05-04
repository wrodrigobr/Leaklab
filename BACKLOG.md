# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprints 1–13 + Sprint A–N + BACK-008 + BACK-015 — ver CHANGELOG v0.9.0 a v0.45.0.
> **Sprint atual:** Sprint O — FEAT-01 Comparativo de Torneios

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
| Sprint O | FEAT-01 | Comparativo de Torneios | 🔄 em andamento |
| Sprint P | FEAT-04 | Relatório PDF Premium | ⏳ |
| Sprint Q | FEAT-02 + FEAT-03 | Daily Focus + XP Server-Side | ⏳ |
| Sprint R | FEAT-05 | SRS Adaptativo nos Drills | ⏳ |
| Sprint S | FEAT-06 | Leak Causal Map | ⏳ |
| Sprint T | FEAT-07 | Coach Effectiveness Metrics | ⏳ |
| Sprint U | FEAT-08 | Session Goals + AI Review | ⏳ |
| Sprint V | FEAT-09 + FEAT-10 | Coach Templates + Coach Messaging | ⏳ |
| Sprint W | FEAT-11 | Weekly Digest Email | ⏳ |

---

## Próximas Sprints — Em Aberto

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

### Backlog Futuro (não priorizar agora)

| Item | Motivo de adiar |
|---|---|
| Counterfactual Replay | Exige simulação Monte Carlo prospectiva — não temos equity calculator para linhas hipotéticas |
| Reg Archetype Recognition | Exige dados de adversários; fora do escopo atual (análise do herói, não do field) |
| Competitive Benchmark Layer | Exige pool de dados de outros usuários; questões de privacidade + volume mínimo de usuários |
