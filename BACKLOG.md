# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprints 1–13 + Sprint A + BACK-008 + BACK-015 — ver CHANGELOG v0.9.0 a v0.32.0.

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
| **Sprint B** | **UX-002** | **Responsividade mobile/tablet** | ⏳ Pendente ~15h |
| **Sprint C** | **BACK-014** | **Revenue share para coaches** | ⏳ Pendente ~20h |

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
