# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprints 1–13 + Sprint A–AW — ver CHANGELOG v0.9.0 a v0.82.2.
> **Próxima sprint:** Sprint AX — Onboarding para novos usuários

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
| Sprint AH | BACK-018 | Coach Application Flow — candidatura com aprovação manual pelo admin | ✅ v0.65.0 |
| Sprint AI | BACK-019 | Perfil demográfico do usuário — idade, localização, experiência de poker | ✅ v0.66.0 |
| Sprint AJ | UX-015 | Inbox global de mensagens para o coach — ver todas as conversas com badge de não lidas | ✅ v0.67.0 |
| Sprint AK | UX-016 | Badge de mensagens não lidas no dashboard/header do aluno → link direto para conversa com coach | ✅ v0.67.0 |
| Sprint AL | UX-017 | Dashboard personalizável — arrastar e reordenar cards, preferência salva por usuário | ✅ v0.70.0 |
| Sprint AM | UX-018 | Listagem de alunos do coach — tabela com busca, filtros (ativo/inativo, plano) e paginação | ✅ v0.68.0 |
| Sprint AN | UX-019 | Coach Chat Drawer — painel lateral de mensagens no header do aluno | ✅ v0.69.0 |
| Sprint AG | FEAT-12 | Página de Documentação / Wiki do Sistema | ✅ v0.71.0 |
| Sprint AO | i18n ext. | Cobertura i18n completa: LeakCausalMap, DraggableCard, Docs career section | ✅ v0.72.0 |
| — | bugfixes | Bugfixes: nomes de nível i18n no dashboard, narrativa LeakCausalMap em PT, drag handle UX | ✅ v0.73.0 |
| Sprint AP | FEAT-13 | Strategic Career Graph — projeção de carreira com regressão linear + sparkline + narrativa IA | ✅ v0.74.0 |
| Sprint AQ | FEAT-14 | Cognitive Failure Mapper — 5 padrões cognitivo-emocionais + CognitiveFailureCard | ✅ v0.75.0 |
| Sprint AQ+ | — | Dashboard UX Redesign — layout reorganizado, insight_row com Career + Cognitive lado a lado | ✅ v0.76.0 |
| Sprint AR | FEAT-15 | Personal Strategic Twin — perfil preditivo de spots custosos + narrativa LLM em 1ª pessoa | ✅ v0.77.0 |
| Sprint AS | FEAT-16 | AI Sparring Mode — jogo de mãos históricas com pause em decisões + feedback imediato + SRS | ✅ v0.78.0 |
| Sprint AT | — | Menu "Treinos" + redesign visual do Sparring (amber, StreetTimeline, HandRecap) | ✅ v0.79.0 |
| Sprint AU | — | PokerTable visual no Sparring — herói + vilões + board + pot em tela real | ✅ v0.80.0 |
| Sprint AV | — | Página /training + botões de ação contextuais no Sparring (facing_bet) | ✅ v0.81.0 |
| — | bugfixes | i18n sparring (arenaLabel/arenaDesc) + test suite verde (sys.executable, coach flow) | ✅ v0.81.1 |
| Sprint AW | — | Ghost Table Pressure Mode (30s timer + SVG ring + streak) + Sparring hand rotation | ✅ v0.82.0 |
| — | bugfixes | Perfil demográfico visível + i18n completo do perfil + telefone no perfil | ✅ v0.82.1–v0.82.2 |

---

## Próximas Sprints — Em Aberto

### [FEAT-17] — Onboarding para novos usuários *(Sprint AX)*

**Valor:** Não há fluxo guiado de boas-vindas após o registro. O usuário cai direto no dashboard sem saber o que fazer primeiro — aumenta abandono precoce e reduz a chance de o usuário fazer o primeiro upload.

**O que construir:**
- Modal de boas-vindas exibido uma única vez após o primeiro login (flag `onboarding_completed` no perfil do usuário)
- 3–4 passos: apresentar o produto, explicar o upload de hand history, mostrar onde ficam Ghost Table e Sparring, e convidar a importar o primeiro torneio
- CTA final: botão direto para a tela de análise (`/analyze`)
- Opção de pular (skip) em qualquer passo; ao pular ou concluir, flag gravada no backend

**Backend:**
- `backend/database/repositories.py` — campo `onboarding_completed` na tabela `users` (ou profile); `set_onboarding_completed(user_id)`
- `backend/api/app.py` — `POST /player/onboarding/complete`

**Frontend:**
- `frontend/src/components/OnboardingModal.tsx` — modal multi-step com stepper, ilustrações e copy contextualizado
- `frontend/src/pages/Index.tsx` — checa `user.onboarding_completed`; exibe modal se falso
- `frontend/src/i18n/locales/{pt-BR,en,es}/onboarding.json` — namespace `onboarding` com todos os textos (PT/EN/ES)

**Esforço estimado:** ~4h backend + ~12h frontend

---

### [FEAT-18] — Mobile audit + responsividade *(Sprint AY)*

**Valor:** O dashboard com cards arrastáveis nunca foi auditado em mobile. A experiência provavelmente está quebrada — drag handle é inutilizável em touch, cards podem ter overflow, e o nav colide com conteúdo em telas pequenas.

**O que auditar e corrigir:**
- Dashboard: drag & drop em touch (desabilitar ou substituir por reorder via botões ↑↓ em mobile)
- GhostTable e Sparring: botões de ação com tamanho mínimo de toque (44×44 px)
- HudHeader: nav em mobile (menu hambúrguer funcional em todas as rotas)
- Tabelas de docs e cards de análise: scroll horizontal em telas < 400px
- Formulários de perfil: inputs e labels não colapsam em mobile

**Abordagem:**
- Auditoria com DevTools (viewport 390×844 — iPhone 14) em todas as rotas principais
- Corrigir breakpoints e adicionar `touch-action` onde necessário
- Testar drag & drop em dispositivo real ou emulador iOS/Android

**Esforço estimado:** ~2h audit + ~10h correções

---

### [FEAT-19] — Modo Gravação da mesa (para coaches) *(adiado — "depois", sem sprint comprometida)*

**Valor:** Coaches gravam aulas/conteúdo a partir do replayer, mas a mesa não está preparada para captura (chrome ao redor, sem ferramentas de marcação). Um "Modo Gravação" transforma o replayer num palco limpo estilo transmissão (PokerGO), reutilizando todo o replayer existente — **é uma camada, não outra mesa**.

**Premissa técnica (validada na análise):** o replayer já tem `focusMode` (`Replayer.tsx:1427` — fullscreen nativo + esconde `HudHeader` + solta `max-w`). O Modo Gravação é `focusMode` turbinado: mesma `PokerTableV3`, mesmos controles, + overlays visuais. O telestrator desenha em coordenadas de TELA (anotação por cima), não precisa casar com as coords SVG da mesa.

**O que construir (por fases, cada uma entregável):**
- **Fase 1 — Palco limpo:** toggle `recMode`; mesa full-bleed **16:9** (trocar `aspect-[16/10]`); esconder `SidePanels` + card de decisão; atalhos de teclado por **street** (pula pro 1º step de preflop/flop/turn/river — reusa `stepIdx` + `step.street`). *Já útil para gravar.*
- **Fase 2 — Telestrator (o item caro):** **SVG overlay** absoluto sobre a mesa + barra de ferramentas (seta, círculo, caneta livre, cor, undo, limpar). SVG > canvas (vetor, fácil add/remove de formas, sem raster).
- **Fase 3 — Cursor-spotlight:** overlay com `radial-gradient` mask seguindo o mouse (escurece tudo menos um círculo). Toggle on/off.
- **Fase 4 — Pause + overlay de ranges:** ao pausar, mostra a matriz de range do spot por cima/ao lado (reusa os dados que o card já busca).

**Frontend (touch points):**
- `frontend/src/pages/Replayer.tsx` — estado `recMode` (estende `focusMode`); gating do `SidePanels`/card; container 16:9; handlers de teclado por street.
- `frontend/src/components/replayer/TableTelestrator.tsx` (novo) — overlay SVG de desenho + toolbar.
- `frontend/src/components/replayer/CursorSpotlight.tsx` (novo) — overlay de spotlight.
- i18n `replayer.json` (PT/EN/ES) para labels das ferramentas.

**Riscos/gotchas:** (1) telestrator é o grosso do esforço — o resto é casca; (2) `pointer-events` entre spotlight e caneta (gerenciar por z-index/ferramenta ativa); (3) decisão de UX: limpar desenho ao trocar de street (recomendado) vs manter; (4) "overlay de ranges" só preflop tem matriz pronta — postflop exigiria renderizar a estratégia do nó; (5) desktop-only (esconder toggle no mobile).

**Decisões pendentes (confirmar antes de codar):** acesso só-coach? · telestrator limpa por street? · overlay de ranges só preflop ou também postflop?

**Esforço estimado:** Fase 1 ~6h · Fase 2 ~16h · Fase 3 ~4h · Fase 4 ~8h (escopo a definir)

---

## Backlog Futuro (não priorizar agora)

| Item | Motivo de adiar |
|---|---|
| Tournament Future Simulation | Requer reescrita do parser para capturar chip stacks + payout structure; ~3–4 meses de engenharia. Game-changer no longo prazo. |
| Autonomous Evolution Engine | Precisa ≥500 usuários ativos com ≥10 sessões cada para adaptação pedagógica real — sem essa massa, seria heurística fake |
| Meta-Game Evolution Forecast | Requer pool de dados de milhares de jogadores — inviável sem volume de usuários |
| Adversarial Exploit Engine | Sistema captura apenas decisões do hero, não dados de oponentes — exigiria produto HUD, categoria diferente |
| Neural Population Benchmark | Vetores de estilo estratégico de múltiplos jogadores = produto de research, não SaaS early-stage |
| Self-Evolving Decision Engine | Auto-ajuste de thresholds sem ground truth validado por experts = risco de degradação silenciosa do engine |
| Counterfactual Replay | Exige simulação Monte Carlo prospectiva — não temos equity calculator para linhas hipotéticas |
| Reg Archetype Recognition | Exige dados de adversários; fora do escopo atual (análise do herói, não do field) |
| Competitive Benchmark Layer | Exige pool de dados de outros usuários; questões de privacidade + volume mínimo |
