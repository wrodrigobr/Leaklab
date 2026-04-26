# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Unreleased]

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
