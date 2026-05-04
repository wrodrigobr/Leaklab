# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprints 1–13 + Sprint A–AP — ver CHANGELOG v0.9.0 a v0.74.0.
> **Próxima sprint:** Sprint AQ — Cognitive Failure Mapper

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

---

## Próximas Sprints — Em Aberto

### [FEAT-14] — Cognitive Failure Mapper *(Sprint AQ)*

**Valor:** O mapeamento de padrões cognitivo-emocionais com base em sequências decisional reais é genuinamente o diferencial mais original da lista. Nenhuma ferramenta de poker faz isso.

**O que detecta** (padrões nas decisões ordenadas dentro de cada torneio):
- `revenge_aggression` — aumento de clear_mistakes após sequência de folds corretos (frustração)
- `fear_folding` — folding excessivo após bust de stack grande (medo de bust)
- `sunk_cost_continuation` — calls ruins nos rivers após investimento crescente no pot
- `entitlement_tilt` — sequência de clear_mistakes após bloco de decisões standard (relaxamento pós-boa-fase)
- `compensation_call` — call-downs excessivos nas N mãos após fold correto de strong hand

**Como funciona:**
- Analisa janelas deslizantes de 5–10 decisões consecutivas dentro de um torneio
- Correlaciona padrão de score com contexto anterior (sequência de folds, stack loss, pot investment)
- LLM (Haiku, ~200 tokens) gera o diagnóstico em linguagem natural com o padrão detectado e sugestão de correção

**Backend:**
- `backend/leaklab/cognitive_mapper.py` — detector de padrões cognitivos sobre sequência de decisões
- `backend/database/repositories.py` — `get_cognitive_failure_report(user_id, tournament_id=None)`
- `backend/api/app.py` — `GET /player/cognitive-failures?lang=`
- `backend/leaklab/llm_explainer.py` — `generate_cognitive_narrative(patterns, lang)`

**Frontend:**
- `frontend/src/components/hud/CognitiveFailureCard.tsx` — card no sidebar do dashboard
- Lista os padrões detectados com ícone de severidade, frequência e contexto de gatilho
- Narrativa LLM abaixo da lista
- Seção na página `/docs` com explicação dos padrões (3 locales)
- `frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json` — chaves `cognitiveFailure.*`

**Esforço:** ~16h backend + ~12h frontend

---

### [FEAT-15] — Personal Strategic Twin (simplificado) *(Sprint AR)*

**Valor:** Transforma os dados de frequência de erros por spot em linguagem preditiva: *"em spots de reshove M≤8 IP você erra 63% das vezes — esse é seu padrão mais custoso"*. Nenhum solver ou ferramenta de revisão apresenta os dados do próprio jogador dessa forma.

**O que NÃO é:** não é um modelo ML preditivo individual (exigiria meses de engenharia + dados de treinamento). É uma camada de apresentação sobre dados existentes.

**O que constrói:**
- Endpoint `GET /player/strategic-twin?lang=` que agrega:
  - Spots de alta frequência (top 5 por volume de decisões)
  - Spots com erro acima da média individual do jogador (% de clear_mistakes > player avg)
  - Padrão de contexto para cada spot (ICM level predominante, posição, street)
- LLM (Haiku, ~300 tokens) gera o card no estilo "twin diagnóstico": texto em 1ª pessoa, preditivo, com os 3 padrões mais custosos identificados

**Backend:**
- `backend/database/repositories.py` — `get_strategic_twin_profile(user_id)`
- `backend/api/app.py` — `GET /player/strategic-twin?lang=`
- `backend/leaklab/llm_explainer.py` — `generate_twin_narrative(profile, lang)`

**Frontend:**
- `frontend/src/components/hud/StrategicTwinCard.tsx` — card no sidebar do dashboard
- Cabeçalho: "Seu Perfil Estratégico" / "Your Strategic Profile"
- Corpo: lista dos 3 padrões mais custosos + narrativa LLM
- `frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json` — chaves `strategicTwin.*`

**Esforço:** ~10h backend + ~8h frontend

---

### [FEAT-16] — AI Sparring Mode no Ghost Table *(Sprint AS)*

**Valor:** Em vez de revisar texto sobre o spot de leak, o jogador joga a mão real que contém o leak, pausando em cada decisão e recebendo feedback imediato. Aprendizado por ação, não por leitura.

**Arquitetura:** "Sparring Mode" dentro do Ghost Table existente — reutiliza o visual do Replayer e o engine de avaliação de decisões. NÃO usa o `leaklab-replayer-v3.html` diretamente (timeline fixo sem ramificações).

**Como funciona:**
1. Sistema seleciona uma mão histórica do jogador que contém seu leak mais crítico
2. Replayer carrega a mão mas **pausa em cada ponto de decisão do hero** (`is_hero: true`)
3. Usuário escolhe sua ação (fold/call/raise/jam) com visual completo (cartas, board, pot, posições, M-ratio)
4. Engine avalia a escolha via `decision_engine_v11` → feedback imediato (score + label + explicação)
5. Mão continua com a ação escolhida pelo usuário (ou a ação real, como modo de comparação)
6. Ao final: resumo de todas as decisões + EV total perdido/ganho vs linha ideal

**O que reutiliza sem reescrita:**
- Componentes visuais do Replayer (cartas, board, pot, posições, stacks)
- Mecanismo de `submit_drill` do Ghost Table existente
- `decision_engine_v11` para avaliação
- Endpoints `/player/spots/drill` e `/player/spots/drill/submit`

**O que constrói:**
- Backend: endpoint `GET /player/sparring/hand` — serve mão completa em sparring mode (mesma estrutura de ReplayData + flag `sparring: true` + lista de `decision_points` com índice no timeline)
- Frontend: modo "Sparring" na página Ghost Table — intercepta pontos `is_hero: true` no timeline para mostrar botões de ação em vez de auto-avançar; painel de feedback inline; resumo final
- SRS: a mão completa vira um "drill spot" com dificuldade baseada no número de erros cometidos
- `frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json` — chaves `sparring.*`

**Arquivos:**
- `backend/api/app.py` — `GET /player/sparring/hand?spot_id=`
- `backend/database/repositories.py` — `get_sparring_hand(user_id, spot_id)`
- `frontend/src/pages/GhostTable.tsx` — modo sparring inline
- `frontend/src/components/hud/SparringFeedback.tsx` — painel de decisão + feedback

**Esforço:** ~12h backend + ~14h frontend

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
