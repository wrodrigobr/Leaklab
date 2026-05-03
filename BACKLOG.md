# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprints 1–13 + Sprint A–F + BACK-008 + BACK-015 — ver CHANGELOG v0.9.0 a v0.38.0.
> **Sprint atual:** Sprint J — PERF-003 (Leak Progression) + PERF-004 (Pressure Collapse) + PERF-005 (Confidence Drift)

---

## [BUG-001] — Prêmio do torneio calculado incorretamente

**Reportado:** 2026-04-26
**Severidade:** Alta — afeta KPIs financeiros (profit, ROI, ITM) exibidos no dashboard

**Status:** CORRIGIDO em `app.py` → `_extract_financials()` — reimportar torneios afetados para atualizar o banco.

Fix aplicado: quando herói é eliminado sem ITM no PokerStars (`finished the tournament` sem prêmio), `prize` é definido como `0.0` em vez de somar chips coletados em potes normais.

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
| **Sprint J** | **PERF-003 + PERF-004 + PERF-005** | **Leak Progression + Pressure Collapse + Confidence Drift** | 🔄 Em desenvolvimento |
| Sprint K | PERF-006 | Ghost Table Simulator MVP | 📋 Backlog |

---

## [UX-002] — Responsividade: Mobile & Tablet

**Reportado:** 2026-04-27
**Prioridade:** Alta — bloqueia acesso da maioria dos usuários que jogam no celular

**Problema:** O site foi desenvolvido como desktop-first. Menus, tabelas e cards não se adaptam a telas menores de 768px. Jogadores de poker frequentemente usam celular durante ou após sessões.

### Escopo mínimo (MVP mobile)

**Layout geral:**
- Sidebar de navegação vira bottom navigation bar em mobile (<768px)
- HUD header colapsa — botão de import fica fixo no canto inferior direito (FAB)
- Tipografia e espaçamentos ajustados para toque

**Dashboard (Index.tsx):**
- Cards de KPI empilham em coluna única
- Gráfico de evolução ocupa 100% de largura
- LevelCard exibe em versão compacta (`compact={true}`) em mobile
- RecentTournamentsTable vira lista vertical de cards (não tabela)

**Torneios (/tournaments):**
- Tabela vira lista de cards com swipe-to-action ou menu de três pontos
- Filtros entram em sheet/drawer deslizante

**Replayer:**
- Controles de replay viram barra bottom fixa
- Range matrix abre em modal fullscreen

**Coach area:**
- Alunos listados em cards em vez de tabela
- Detalhe do aluno usa tabs horizontais com scroll

### Abordagem técnica
- Tailwind breakpoints: `sm:` (640px), `md:` (768px), `lg:` (1024px)
- Testar com DevTools no mínimo: iPhone SE (375px), iPhone 14 Pro (390px), iPad (768px)
- Componentes críticos primeiro: nav, dashboard, tabela de torneios

### Esforço estimado
- Layout/navegação: ~4h
- Dashboard + cards: ~4h
- Torneios + tabelas: ~3h
- Replayer mobile: ~4h
- **Total: ~1 sprint grande (~15h)**

---

## [BACK-014] — Modelo de Revenue Share para Coaches

**Reportado:** 2026-04-27
**Tipo:** Comercial — modelo de negócio

### Visão do modelo

Coaches que indicam alunos ativos para a plataforma são recompensados com **revenue share mensal**, em vez de pagar mensalidade:

| Alunos ativos | Status do coach | Valor recebido |
|---|---|---|
| 0 | Paga plano Pro | — |
| 1–3 | Mensalidade zerada | R$ 0 |
| 4–9 | Mensalidade zerada + receita | R$ 15/aluno ativo/mês |
| 10+ | Elite — receita maior | R$ 20/aluno ativo/mês |

**Aluno ativo** = importou ≥ 1 torneio nos últimos 30 dias + está no plano Pro (paga mensalidade).

### Funcionalidades necessárias

**Painel do Coach — "Minhas Indicações":**
- Lista de alunos vinculados com status (ativo/inativo)
- Contador de alunos ativos no mês atual
- Estimativa de receita do mês
- Histórico de pagamentos recebidos (referência)

**Painel Administrativo (backoffice):**
- Lista todos os coaches com alunos ativos, plano atual, valor a pagar e status do pagamento
- Filtros: por status, por valor mínimo de repasse
- Exportação CSV para processamento de pagamentos

**Backend — rastreamento:**
- Campo `referral_coach_id` no aluno (quem indicou — pode ser diferente do coach atual)
- Endpoint `GET /admin/revenue-report` — protegido por role `admin`
- Endpoint `GET /coach/referral-dashboard` — painel do coach

### Modelo de dados adicional
```sql
ALTER TABLE users ADD COLUMN referral_coach_id INTEGER REFERENCES users(id);

CREATE TABLE coach_payments (
    id              SERIAL PRIMARY KEY,
    coach_id        INTEGER NOT NULL REFERENCES users(id),
    period          TEXT    NOT NULL,  -- 'YYYY-MM'
    active_students INTEGER NOT NULL DEFAULT 0,
    amount_cents    INTEGER NOT NULL DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'pending',  -- pending | paid
    paid_at         TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Esforço estimado
- Backend (revenue query + endpoints admin + painel coach): ~8h
- Frontend coach (painel de indicações): ~4h
- Frontend admin (backoffice): ~8h
- **Total: ~1 sprint grande (~20h)**

---

## [BACK-016] — WhatsApp Coaching Drills (PRO)

**Reportado:** 2026-05-02
**Prioridade:** Alta — diferencial de produto e retenção PRO
**Plano PRO exclusivo** — usuários Starter acessam lições apenas dentro do app (StudyPlan.tsx)

### Visão

Usuário PRO cadastra seu número de WhatsApp nas configurações. Quando quiser treinar, envia qualquer mensagem para o número da LeakLab. O bot responde com uma pergunta de múltipla escolha baseada nos leaks ativos do usuário. A resposta é avaliada e o AI Coach explica o raciocínio correto se o usuário errar ou pedir mais detalhes.

Sem disparo automático pelo sistema — o usuário sempre inicia a sessão.

### Fluxo completo

```
1. Usuário salva telefone no perfil (Settings)
2. Usuário manda "oi" / "lição" / qualquer msg para o número WA Business
3. Webhook identifica usuário pelo telefone → busca leak/plano mais crítico
4. Bot envia pergunta múltipla escolha (ex: "M=7, BB é 2.5x, você tem A9o no CO…")
5. Usuário responde "a" / "b" / "c" / "d"
6. Acertou → "✓ Correto! streak: 3" + opção "próxima"
   Errou   → Claude gera explicação ≤300 chars + pergunta se quer mais
   "?" / "explicar" → Claude responde com contexto completo dos leaks do usuário
```

### Por que não precisa de template Meta

O usuário sempre inicia a conversa — o sistema está sempre dentro da janela de sessão de 24h da Meta. Sem templates, sem review, sem scheduler.

### Modelo de dados necessário

```sql
-- Adicionar ao users
ALTER TABLE users ADD COLUMN whatsapp_number TEXT;  -- formato E.164: +5511999999999

-- Estado de sessão WA (TTL 24h)
CREATE TABLE whatsapp_sessions (
    phone           TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    pending_card_id INTEGER REFERENCES study_cards(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Backend

- `GET /POST /whatsapp/webhook` — verificação + recebimento de mensagens Meta
- Identificação de usuário por `from` (número E.164)
- Geração de pergunta: reusa `StudyCard` do plano ativo ou gera via Claude a partir de `leaks_summary`
- Avaliação de resposta: compara letra com gabarito, armazena acerto no `study_cards`
- Chamada Claude (AI Coach): explicação curta personalizada com contexto do usuário (leaks, M-ratio habitual, nível atual)
- Variável de ambiente: `WHATSAPP_TOKEN` (token de acesso Meta), `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN`

### Frontend

- **`StudyPlan.tsx`** — CTA "Treinar no WhatsApp" já adicionado na sidebar; aparece automaticamente quando a variável `VITE_WHATSAPP_NUMBER` estiver configurada no Vercel; link `wa.me/{número}?text=lição` abre o WhatsApp com mensagem pré-preenchida; instrução "salve o número no celular" para descoberta orgânica
- **Settings/Perfil** — campo "WhatsApp" com formatação E.164 + instrução: "Envie qualquer mensagem para wa.me/[número] para começar"
- **Indicador visual** — badge "WA Ativo" no perfil quando número cadastrado + plano PRO

### Esforço estimado

- Setup Meta Business Account + número WA Business: ~2h (manual)
- Backend webhook + identificação + estado de sessão: ~5h
- Geração de perguntas + avaliação + streak: ~4h
- Integração Claude para explicações curtas: ~3h
- Frontend settings + instrução: ~2h
- **Total: ~1 sprint média (~14h) + setup Meta**

---

## [BACK-017] — Admin Panel + Financeiro de Coaches

**Reportado:** 2026-05-02
**Prioridade:** Alta — controle operacional do negócio
**Audiências:** (1) Proprietário do sistema (role `admin`) · (2) Coaches (role `coach`)

### Visão geral

Duas interfaces distintas com dados complementares:
- **Admin**: visão total da plataforma — usuários, saúde financeira, repasses pendentes
- **Coach**: visão do seu próprio negócio — alunos ativos, receita estimada, histórico de repasses

---

### Interface Admin (`/admin`)

#### Painel executivo (homepage do admin)

| Métrica | Descrição |
|---|---|
| MRR (Monthly Recurring Revenue) | Soma das mensalidades ativas no mês |
| Usuários ativos (30 dias) | Importaram ≥ 1 torneio |
| Planos: Starter / PRO / Coach | Contagem e % por plano |
| Churn rate mensal | % que cancelou vs. mês anterior |
| Total a repassar no ciclo atual | Soma de todos os repasses pendentes de coaches |

#### Gestão de usuários

- Tabela com: nome, email, plano, status (ativo/inativo), data de cadastro, último torneio importado, coach vinculado
- Filtros: plano, status, com/sem coach, data de cadastro
- Ações: suspender conta, alterar plano manualmente, desvincular coach

#### Financeiro — Repasses de Coaches

- Tabela por coach: nome, alunos ativos no período, valor bruto calculado, status (`pendente` / `pago`), data do repasse
- Regras de cálculo visíveis (1–3 alunos = mensalidade zerada; 4–9 = R$15/aluno; 10+ = R$20/aluno)
- Botão "Marcar como pago" por linha
- Exportação CSV do período (para processamento bancário)
- Histórico de repasses anteriores (últimos 12 meses)

#### Logs de atividade

- Últimas importações de torneios (usuário, timestamp, site, nº de mãos)
- Últimas análises geradas (custo estimado de tokens Claude)
- Erros recentes da pipeline (falhas de parsing, timeouts LLM)

---

### Interface Coach — aba "Financeiro" no dashboard (`/coach-dashboard`)

Nova aba "Financeiro" no `CoachDashboard.tsx`, ao lado das abas existentes.

#### Resumo do ciclo atual

| Bloco | Conteúdo |
|---|---|
| Alunos vinculados | Total (ativos + inativos) |
| Alunos ativos este mês | Com critério explícito: importou ≥1 torneio + plano PRO |
| Mensalidade este mês | R$0 (zerada) ou valor cobrado normal |
| Receita estimada | Valor calculado com base nos alunos ativos |
| Próximo repasse | Data estimada do próximo ciclo de pagamento |

#### Lista de alunos com status financeiro

- Cada aluno: nome, status (ativo/inativo), último torneio importado, plano atual, contribuição para o repasse
- Alunos inativos com destaque vermelho + dica "Incentive este aluno a importar torneios"

#### Histórico de repasses

- Tabela: período (mês/ano), alunos ativos, valor recebido, status (pendente/pago), data do crédito
- Linha do total acumulado

---

### Modelo de dados necessário

```sql
-- Já especificado em BACK-014:
ALTER TABLE users ADD COLUMN referral_coach_id INTEGER REFERENCES users(id);

CREATE TABLE coach_payments (
    id              SERIAL PRIMARY KEY,
    coach_id        INTEGER NOT NULL REFERENCES users(id),
    period          TEXT    NOT NULL,  -- 'YYYY-MM'
    active_students INTEGER NOT NULL DEFAULT 0,
    amount_cents    INTEGER NOT NULL DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'pending',
    paid_at         TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Backend

- `GET /admin/dashboard` — MRR, usuários ativos, contagem por plano, churn, total a repassar (role `admin`)
- `GET /admin/users` — lista paginada com filtros (role `admin`)
- `PATCH /admin/users/:id` — suspender / alterar plano (role `admin`)
- `GET /admin/finance/coaches` — repasses do ciclo com status (role `admin`)
- `PATCH /admin/finance/coaches/:id/pay` — marcar como pago (role `admin`)
- `GET /admin/finance/coaches/export.csv` — exportação (role `admin`)
- `GET /admin/logs/activity` — últimas importações e erros (role `admin`)
- `GET /coach/finance/summary` — resumo do ciclo atual para o coach autenticado
- `GET /coach/finance/students` — alunos com status financeiro
- `GET /coach/finance/history` — histórico de repasses recebidos

### Frontend

- **`/admin`** — nova rota protegida por `role === "admin"`; layout com sidebar de navegação (Painel, Usuários, Financeiro, Logs)
- **`CoachDashboard.tsx`** — nova aba "Financeiro" com os 3 blocos acima

### Esforço estimado

- Backend (7 endpoints admin + 3 coach + role guard): ~8h
- Frontend admin (dashboard + usuários + financeiro + logs): ~8h
- Frontend coach (aba financeiro): ~4h
- Cálculo de MRR + churn no backend: ~2h
- **Total: ~1 sprint grande (~22h)**

---

## [UX-005] — Internacionalização (i18n) — PT / EN / ES

**Reportado:** 2026-05-02
**Prioridade:** Alta — expande mercado para jogadores internacionais (EN) e latino-americanos não-brasileiros (ES)

### Visão

O site detecta automaticamente o idioma do browser do usuário e carrega as traduções correspondentes. O usuário pode trocar o idioma a qualquer momento via seletor no header. A preferência é salva no `localStorage`. Idiomas iniciais: Português (pt-BR, padrão), Inglês (en), Espanhol (es).

### Abordagem técnica

**Biblioteca:** `react-i18next` + `i18next` — padrão da indústria para React, suporta lazy loading de namespaces.

**Detecção automática:** plugin `i18next-browser-languagedetector` — detecta `navigator.language`, `localStorage`, `htmlTag` em cascata.

**Estrutura de arquivos:**
```
frontend/src/i18n/
  index.ts                  — init do i18next
  locales/
    pt-BR/
      common.json           — textos gerais (nav, botões, labels)
      dashboard.json        — KPIs, seções do dashboard
      tournaments.json      — tabela de torneios, filtros
      study.json            — plano de estudos, exercícios
      coach.json            — área de coach, anotações
      auth.json             — login, cadastro
    en/
      (mesmos arquivos)
    es/
      (mesmos arquivos)
```

**Seletor de idioma:** dropdown compacto no HudHeader (ao lado do AccountMenu), mostra bandeira + código (🇧🇷 PT · 🇺🇸 EN · 🇪🇸 ES). Em mobile aparece no AccountMenu.

**Componentes:** todos os textos hardcoded substituídos por `t('chave')` via hook `useTranslation()`. Componentes com interpolação (ex: "3 torneios analisados") usam `t('key', { count: 3 })`.

**Backend:** sem mudanças — labels de erros já são genéricos. O sistema de leaks usa chaves internas; as descrições em linguagem natural são geradas pelo Claude já no idioma do usuário (passar `language` no payload da chamada LLM).

### Escopo de tradução (MVP)

Prioridade máxima (telas com mais texto visível):
1. HudHeader (nav, botões)
2. Dashboard (KPIs, seções, tooltips)
3. Tournaments (tabela, filtros, badges)
4. StudyPlan (plano, exercícios, "como usar")
5. Login/cadastro

Prioridade média (após MVP):
6. TournamentDetail (fases, texturas, análise IA)
7. Replayer (action log, controles)
8. Coach area (StudentDetail, CoachDashboard)

### Dados não traduzidos (intencionalmente)
- Nomes de torneios (vindos do arquivo importado)
- Explicações geradas pelo Claude (a IA já responde no idioma do usuário)
- Poker terms técnicos (fold, check, raise — universais)

### Esforço estimado

- Setup i18next + detecção + seletor no header: ~3h
- Extração de textos PT-BR (mapeamento de todos os hardcoded strings): ~4h
- Tradução EN (nativa, revisão de poker terms): ~4h
- Tradução ES (revisar com falante nativo ou ajuste Claude): ~3h
- Integração nas telas de alta prioridade: ~4h
- **Total: ~1 sprint grande (~18h)**

---

## [PERF-001] — ROI Attribution Engine *(Sprint I)*

**Reportado:** 2026-05-03
**Prioridade:** Crítica — transforma análise técnica em custo financeiro real; diferencial de conversão

### Visão

Para cada leak detectado, estimar o custo mensal em dólares com base na frequência de ocorrência, severidade do erro (mistake_score) e buy-in médio dos torneios onde o leak aconteceu.

**Fórmula:**
```
ev_loss_monthly = (n × 30 / days) × avg_score × avg_buy_in × 0.10
```

O fator `0.10` é o calibrador empírico: cada unidade de mistake_score por ocorrência custa ~10% do buy-in. Um `clear_mistake` (score ≈ 0.6) em torneios de $10 custa ~$0.60/ocorrência.

### Campos retornados pelo novo endpoint

```json
{
  "leaks": [
    {
      "spot": "preflop/fold",
      "n": 15,
      "avg_score": 0.52,
      "total_score": 7.8,
      "avg_buy_in": 10.0,
      "ev_loss_monthly": 7.80,
      "priority_score": 7.80,
      "priority_rank": 1
    }
  ]
}
```

### Implementação

**Backend:**
- `repositories.py` — `get_leak_roi_impact(user_id, days)`: query enriquecida com `AVG(t.buy_in)` e cálculo de `priority_score = n × avg_score`; ordenada por `priority_score DESC`
- `app.py` — `GET /player/leak-roi`: protegido por `@require_auth`, retorna leaks com ROI

**Frontend:**
- `lib/api.ts` — interface `LeakRoiData` + `metrics.leakRoi(days)`
- `pages/Index.tsx` — fetch paralelo de `leakRoi` no `Promise.all` do dashboard
- `components/hud/LeaksPanel.tsx` — badge de custo mensal (`~$12/mês`) por leak; usa `leakRoi` se disponível
- Locales `dashboard.json` (PT/EN/ES) — chaves `leaks.evLoss`, `leaks.evLossSmall`

### Esforço estimado
- Backend (query + endpoint): ~3h
- Frontend (api.ts + Index + LeaksPanel): ~3h
- i18n (3 locales): ~0.5h
- **Total: ~6.5h**

---

## [PERF-002] — Leak Priority Optimizer *(Sprint I)*

**Reportado:** 2026-05-03
**Prioridade:** Crítica — torna o plano de estudos um diagnóstico real, não uma lista arbitrária

### Visão

Rankear leaks por `priority_score = n × avg_score` (frequência × severidade). Os 3 primeiros recebem badge "CRÍTICO". O plano de estudos é reordenado pelo mesmo critério.

O ordering atual (`avg_score DESC`) privilegia leaks raros mas severos. O novo ordering privilegia leaks com maior impacto total no resultado do jogador.

### Implementação

Integrada ao PERF-001: `get_leak_roi_impact()` já retorna `priority_score` e `priority_rank`.

**Frontend adicional:**
- `LeaksPanel.tsx` — badge `CRÍTICO` para `priority_rank <= 3`; ícone `Flame` vermelho
- Badge distinto de severity: severity é baseado em `avg_score`; priority badge é baseado em `priority_rank`

### Esforço estimado
- Embutido no PERF-001 (~1h extra no frontend)

---

## [PERF-003] — Leak Progression Engine *(Sprint J)*

**Reportado:** 2026-05-03
**Prioridade:** Alta — retenção; jogador precisa ver evolução para continuar usando a plataforma

### Visão

Rastrear evolução temporal dos leaks: severidade por semana, tendência de melhora/regressão, velocidade de correção. Exibir gráfico de linha por leak ao longo do tempo.

### Implementação

**Backend:**
- `repositories.py` — `get_leak_progression(user_id, weeks=8)`: agrupa decisões por `(spot, week)`, retorna `avg_score` por período
- `app.py` — `GET /player/leak-progression`

**Frontend:**
- Novo card no dashboard (ou aba no detail de leak) com gráfico de tendência
- Exibir: "Melhorando ↓", "Estagnado →", "Regredindo ↑" com base na slope

### Esforço estimado: ~5h backend + ~6h frontend

---

## [PERF-004] — Pressure Collapse Detection *(Sprint J)*

**Reportado:** 2026-05-03
**Prioridade:** Alta — diferencial MTT específico; `mtt_context.py` já fornece os dados

### Visão

Comparar `mistake_score` médio do jogador por contexto de pressão ICM (`high`/`medium`/`low`/`none`). Detectar se o jogador degrada tecnicamente em bubble, FT ou spots de alto ICM.

### Implementação

**Backend:**
- Query: `SELECT icm_pressure, AVG(score), COUNT(*) FROM decisions ... GROUP BY icm_pressure`
- Já parcialmente disponível em `get_icm_performance()` — estender para retornar `avg_score` segmentado
- Calcular `collapse_delta = avg_score_high - avg_score_none` (positivo = colapso sob pressão)
- `app.py` — `GET /player/pressure-profile`

**Frontend:**
- Novo card "Pressão ICM" com comparativo: score baseline vs. score em alta pressão
- Destaque vermelho se `collapse_delta > 0.08`

### Esforço estimado: ~3h backend + ~4h frontend

---

## [PERF-005] — Confidence Drift Monitor *(Sprint J)*

**Reportado:** 2026-05-03
**Prioridade:** Média-alta — mental game é sub-explorado por concorrentes

### Visão

Detectar degradação de qualidade técnica após sequências negativas: bad beats, pots grandes perdidos, sequência de 3+ torneios abaixo do baseline.

**Heurística:** identificar janelas de N decisões consecutivas onde `avg_score > baseline × 1.3` (30% acima do normal do jogador), especialmente após mãos com `showdown_result = 'lost'` em potes grandes.

### Implementação

**Backend:**
- `repositories.py` — `get_confidence_drift(user_id, days=30)`: janela deslizante de 10 decisões, flag drift se slope > threshold
- `app.py` — `GET /player/confidence-drift`

**Frontend:**
- Alerta contextual no dashboard: "Sessão X — possível tilt detectado"
- Badge discreto, não alarmista

### Esforço estimado: ~4h backend + ~3h frontend

---

## [PERF-006] — Ghost Table Simulator MVP *(Sprint K)*

**Reportado:** 2026-05-03
**Prioridade:** Alta — aprendizado ativo; diferencial de produto mais difícil de copiar

### Visão

Reapresentar spots reais do histórico do jogador para que ele tome nova decisão. Comparar: decisão original vs. nova decisão vs. ideal (`best_action`). Score a nova decisão com o engine.

### Fases do MVP

**Fase 1 (backend + API):**
- `GET /player/spots/drill` — retorna N spots filtráveis por leak, street, posição; exclui spots já revisados
- Payload: `{hand_context, hero_cards, board, street, position, stack_bb, m_ratio, original_action, best_action, score}`

**Fase 2 (frontend — drill mode):**
- Modo sequencial de spots: apresenta contexto da mão, pede ação (fold/call/raise/jam)
- Avalia com engine, exibe score comparativo, mostra explicação

**Fase 3 (persistência de sessão):**
- Registrar cada redecisão em `drill_sessions` para rastrear melhora no drill

### Modelo de dados

```sql
CREATE TABLE drill_sessions (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    decision_id   INTEGER NOT NULL REFERENCES decisions(id),
    new_action    TEXT    NOT NULL,
    new_score     REAL    NOT NULL,
    original_score REAL   NOT NULL,
    delta         REAL    NOT NULL,
    drilled_at    TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Esforço estimado: ~5h backend + ~10h frontend (UI intensiva)
