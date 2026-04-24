# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Unreleased]

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
