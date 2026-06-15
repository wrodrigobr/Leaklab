# Coach Cockpit — redesign da aba "Alunos"

**Status:** plano · criado 2026-06-15
**Objetivo:** transformar a aba **Alunos** do coach (`CoachDashboard.tsx`) no **cockpit** onde,
numa tela, o coach triage a turma em **dois eixos** — *coaching* (quem precisa de mim) e
*receita* (indicados, ativos, quanto recebo) — sem entrar aluno por aluno.

> Pré-leitura: a análise que originou este plano está no histórico; comp em
> `calculate_coach_payout` (0 / R$15 / R$20 por ativo); indicação em [`sec-01-coach-invites.md`](sec-01-coach-invites.md).

---

## 1. Problemas que o cockpit resolve

1. **Lista plana sem sinal de qualidade.** Hoje a linha mostra só *Aluno · Torneios · Último import
   · Tendência · Status*. Um coach com 20 alunos não sabe **quem está mal** sem clicar em cada um.
2. **Duas definições de "ativo" conflitantes.** Aba Alunos: importou em 30d (qualquer plano).
   Financeiro/payout: **pro + importou em 30d**. O coach vê "Ativo" em quem **não conta** pro dinheiro.
3. **Comp escondida.** Indicados/ativos/valor moram numa aba separada (Financeiro) — não no painel
   onde o coach trabalha.
4. **Torneios dos alunos soterrados.** 2 cliques por aluno; **não há feed cross-aluno** ("o que meus
   alunos jogaram esta semana?").

---

## 2. Arquitetura do cockpit (3 zonas na aba Alunos)

### Zona A — Faixa de topo: Receita & Saúde da turma (KPIs)
Strip de cards no topo (reusa `get_coach_finance_summary` + extensões):
- **Indicados** (via convite — SEC-01; fallback `invited_by_key`).
- **Ativos** (definição ÚNICA = pro + import 30d) — "conta R$".
- **Valor a receber** no período + **próxima faixa** ("faltam 2 ativos → R$15/aluno"). Motivador direto.
- **Precisam de atenção** (N) — alunos com score baixo OU crítica pendente OU mensagem não-lida.
- **Melhora média** (já existe).

### Zona B — Tabela de triagem (a lista enriquecida)
Cada linha de aluno passa a mostrar:
| Sinal | Fonte | Custo |
|---|---|---|
| avatar + nome | atual | — |
| selo **Indicado** | `invited_via_invite_id` (SEC-01) / `invited_by_key` | barato |
| selo **Ativo (conta R$)** vs **Inativo** vs **Recente·free** | plan + import 30d | barato |
| plano | `users.plan` | barato |
| **Score última sessão** (colorido) | `recent_tournament.avg_score` (já no payload) | **frontend-only** |
| Tendência | atual | — |
| **⚠ N críticas pendentes** (não-anotadas) | agregação `decisions` small/clear sem anotação do coach | médio |
| **✉ não-lidas** | inbox/`coach_messages` | médio |
| último import | atual | — |

- **Ordenar/filtrar por "precisa de atenção"** (novo filtro além de ativo/inativo).
- Linha clicável → `StudentDetail` (mantém).
- `StudentRow.tsx` ganha as colunas/selos; responsivo (esconde colunas <768/1024 como hoje).

### Zona C — Sidebar: Atividade & Ranking
- **Feed cross-aluno de torneios recentes (NOVO):** aluno · torneio · score · data · N crítico →
  clique abre o torneio do aluno (`/tournaments/{id}?student=`). Responde direto "o que jogaram".
- **Ranking de alunos** (mantém — `CoachStudentsRanking`).
- **Common leaks** (mantém).

---

## 3. Definição ÚNICA de "ativo"
Unificar tudo em **ativo = `plan='pro'` + importou em 30d** (a do payout). A lista deixa de marcar
"Ativo" para quem não conta. Três estados no selo:
- **Ativo · conta R$** (pro + 30d) · **Inativo** (sem import recente) · **Recente · free** (importou
  mas não-pro → não entra na comp; sinal pro coach converter).

---

## 4. Backend

### 4.1 Estender `GET /coach/students` (payload da lista — `StudentSummary`)
Adicionar campos (a maioria barata, mesma query/joins):
- `plan`, `is_active_paid` (pro+30d), `is_referred` (bool), `score_last` (= `recent_tournament.avg_score`).
- `critical_pending` (count de decisões small/clear **sem anotação do coach**) e `unread`
  (mensagens não lidas do aluno) — 2 agregações (preferir 2 queries agregadas por todos os alunos,
  não N+1).

### 4.2 Novo `GET /coach/recent-activity?limit=`
Torneios recentes de **todos** os alunos do coach: `student_id, username, tournament_id, name, site,
avg_score, imported_at, n_critical`. Reusa o padrão de `get_all_students_worst_decisions`
(`repositories.py:2804`). Ordena por `imported_at DESC`.

### 4.3 Faixa de topo
Reusar `get_coach_finance_summary` (já dá `active_students`, `amount_cents`, `total_students`) +
adicionar `referred_count` e `next_tier` (faixa seguinte + quantos faltam — derivado de
`calculate_coach_payout`).

---

## 5. Frontend (`CoachDashboard.tsx`, aba Alunos)
- Faixa de topo (KPIs comp + saúde) acima da tabela.
- Tabela enriquecida (`StudentRow.tsx`) + filtro "precisa de atenção" + ordenação nova.
- Sidebar: feed cross-aluno (novo card) + ranking + common leaks (mantêm).
- Reusa `VerdictTag`/paleta; selos compactos; i18n PT/EN/ES (sem hardcode).
- As 6 abas continuam (Financeiro detalhado segue na sua aba; só os KPIs sobem pro cockpit).

---

## 6. Faseamento
- **P1a — cockpit base (frontend + extensão barata):** score última sessão, unifica "ativo" (precisa
  `plan`+`is_active_paid` no payload), faixa de topo com comp (reusa finance summary + next_tier).
  *Maior ROI, quase tudo já disponível.*
- **P1b — sinais de atenção:** `critical_pending` + `unread` no payload + filtro/ordenação "precisa de atenção".
- **P2 — feed cross-aluno de torneios:** novo endpoint + card na sidebar.
- **P3 — paridade da aba Torneios do aluno:** dar à aba Torneios do `StudentDetail` a riqueza da
  `Tournaments.tsx` do jogador (busca/filtro por sala/sort/stats/badges).

**Esforço:** P1a ~6h · P1b ~6h · P2 ~6h · P3 ~8h.

---

## 7. Dependências / decisões
1. **"Indicados"** depende do SEC-01 para atribuição confiável; até lá, `invited_by_key` é aproximação.
2. **"Ativo" único = pro + 30d** — confirmar (cruza com PAY-01/financeiro).
3. **Layout:** manter as 6 abas (Alunos vira cockpit) — NÃO explodir em masonry; cockpit é tabela + strip + sidebar.
4. **"Crítica pendente"** = small/clear sem anotação do coach? Ou sem revisão (qualquer anotação)? (define a query.)
