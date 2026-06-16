# COACH-ONBOARDING — Coach como aluno + Pro de cortesia (3 meses) + meta de 15 pagantes

**Status:** P1 (backend) ✅ + P2 (frontend) ✅ implementadas 2026-06-16 · P3 (polish/backfill) pendente · criado 2026-06-16
**Origem:** "Não posso simplesmente dar Pro pro coach. Ao entrar ele também precisa das funcionalidades de aluno (Free). Ao alcançar 15 alunos indicados **e pagantes** ele mantém Pro. Mas ao ser aprovado ele tem **3 meses de Pro** para conseguir os 15; depois disso, **downgrade** se não bater a meta — restando só o **% por aluno pagante**."

---

## 1. Modelo / ciclo de vida do coach

```
Aprovação do coach
   │  role='coach', plan='pro', plan_source='coach_trial'
   │  coach_trial_ends_at = aprovação + 90 dias
   ▼
[ TRIAL: 3 meses de Pro ]  ── acesso pleno de aluno (upload/treino/insights) + visão de coach
   │
   ├── atingiu 15 indicados pagantes (a qualquer momento) ──► plan_source='coach_earned'  (Pro TRAVADO, permanente)
   │
   └── prazo vence sem 15 pagantes ──► DOWNGRADE: plan='free', plan_source=NULL
                                        mantém SÓ a comissão % por aluno pagante (comp 4/10 inalterada)
```

**Definições canônicas**
- **Indicado pagante** (métrica da meta dos 15): `invited_via_invite_id IS NOT NULL` **E** `link_status='approved'` **E** `plan='pro'`. Anti-gaming pela barreira de **pagamento real** (Stripe) — uma conta falsa teria de pagar R$99 pra contar.
- **Aluno ativo** (métrica da **comissão em dinheiro**, já existente): indicado pagante **+** importou nos últimos 30d. Mantida como está (faixas 4/10). São **duas métricas distintas e documentadas**: a meta dos 15 é sobre *assinatura*; a comissão é sobre *atividade recente*.
- **Trial:** 90 dias corridos a partir da aprovação.
- **Pro conquistado (`coach_earned`):** **permanente** — não reavalia churn depois de batido (não pune o coach se um aluno sair depois). O downgrade só acontece **no fim do trial** e só se a meta **não** foi atingida.
- **Comissão:** independente do plano do coach — após downgrade o coach segue recebendo o % por aluno pagante (comp atual).

---

## 2. Estado atual (levantado) e lacunas

| Aspecto | Hoje | Lacuna |
|---|---|---|
| Aprovação do coach | `approve_coach_application` seta `role='coach'`, plano fica `free` (default) — `repositories.py:4779` | precisa conceder o **trial Pro** + prazo |
| Acesso de aluno p/ coach | **bloqueado** no frontend: `ProtectedRoute` redireciona coach→`/coach-dashboard` (`App.tsx:59`); nav 100% segregada (`HudHeader.tsx:126`); upload escondido | precisa **liberar** rotas/nav de aluno p/ coach |
| Endpoints de aluno no backend | usam `@require_auth` (não travam por role) + quota por `users.plan` | em geral **já funcionam** p/ coach autenticado; o bloqueio é só de UI |
| Plano "perk" vs pago | só existe `users.plan`; sem distinção de origem | precisa `plan_source` p/ separar **cortesia** de **pago** (MRR, expiração) |
| Expiração de plano | inexistente (PAY-01 / D-1) | o trial de 3 meses **é** um caso de expiração → precisa job |
| MRR admin | conta todo `plan='pro'` (corrigido p/ R$99 no PAY-01) | precisa **excluir** Pro de cortesia do coach |

---

## 3. Modelo de dados (aditivo, backward-compat)

`users` ganha duas colunas (ambos backends + migrações PRAGMA-guarded):
- `plan_source TEXT` — `NULL`=pago/sem origem especial · `'coach_trial'` · `'coach_earned'`. (Opcional: marcar `'paid'` nas ativações Stripe p/ deixar explícito; default fica NULL = pago legado.)
- `coach_trial_ends_at TEXT` — datetime ISO do fim do trial (NULL p/ não-coaches).

Sem novas tabelas. Legados (coaches já existentes) → ver §7 (backfill).

---

## 4. Backend

**`repositories.py`**
1. `approve_coach_application(...)`: além de `role='coach'`, setar `plan='pro'`, `plan_source='coach_trial'`, `coach_trial_ends_at = now()+90d`.
2. `get_coach_paying_referred_count(coach_id) -> int`: COUNT de indicados pagantes (def. §1). **Métrica da meta.**
3. `maybe_promote_coach_earned(coach_id)`: se o coach é `coach_trial`/`coach_earned` e `paying_referred >= 15` → `plan_source='coach_earned'` (idempotente). Chamar de:
   - `approve_link_request` (coach aprovou um aluno),
   - ativação Stripe (`/subscription/activate` + webhook `payment_intent.succeeded`) quando um aluno **indicado** vira pro.
4. `expire_coach_trials() -> dict`: para cada coach `plan_source='coach_trial'` com `coach_trial_ends_at < now`:
   - `paying_referred >= 15` → `plan_source='coach_earned'` (mantém Pro);
   - senão → `plan='free'`, `plan_source=NULL` (downgrade). Retorna `{promoted, downgraded}` p/ log.
5. `get_admin_dashboard_stats`: MRR conta `plan='pro' AND plan_source NOT IN ('coach_trial','coach_earned')` (cortesia não é receita).
6. `get_coach_trial_status(coach_id) -> dict`: `{plan, plan_source, trial_ends_at, days_left, paying_referred, target:15, is_pro, earned}`.

**`app.py`**
7. `GET /coach/trial-status` (`@require_coach`) → `get_coach_trial_status`. Alimenta o banner do cockpit.
8. **Liberar rotas de aluno p/ coach**: revisar guards. A maioria dos endpoints `/player/*` é `@require_auth` (ok). Conferir os que assumem role player e o `_check_*_quota` (coach em trial = pro → ilimitado; coach pós-downgrade = free → limites de free, comportamento correto).
9. Promoção em tempo real: chamar `maybe_promote_coach_earned` nos pontos do item 3.

**Job (cron) — `scripts/expire_coach_trials.py`**
10. Roda `expire_coach_trials()` diariamente. Mesmo padrão do snapshot de leaderboard (Windows Task Scheduler local `LeakLab-CoachTrialExpiry`; em prod, cron do host). `busy_timeout` no DB dev.

---

## 5. Frontend

1. **Roteamento** (`App.tsx`): coach passa a acessar rotas de aluno. `ProtectedRoute` aceita `role IN ('player','coach')` (admin segue separado). Coach mantém acesso às rotas `/coach-dashboard/*`.
2. **Navegação — switch de workspace** (`HudHeader.tsx`): toggle no topo **"Modo Coach" ⇄ "Minha conta"** (persistido em `localStorage`).
   - *Modo Coach:* `coachNavItems` (command center atual).
   - *Minha conta:* `playerNavItems` + botão de upload (coach como aluno).
   - Default ao logar como coach: Modo Coach.
   - *(decisão de UX adotada: switch de workspace — mantém dois contextos mentais limpos; reversível se preferir nav unificada.)*
3. **Banner de trial no cockpit** (`CoachDashboard.tsx`, reaproveitando a faixa de receita):
   - *Trial ativo:* "Pro de cortesia — **{days_left} dias** restantes · **{paying_referred}/15** alunos pagantes para manter o Pro" + barra de progresso.
   - *Conquistado:* "Pro garantido ✓ — 15 alunos pagantes atingidos."
   - *Pós-downgrade:* "Cortesia encerrada — plano Free. Alcance 15 pagantes ou faça upgrade. Você continua recebendo a comissão por aluno pagante."
4. **i18n** PT/EN/ES em todas as strings novas (as views de coach hoje são PT-only — manter padrão PT nas novas, mas o banner é candidato a i18n pleno).

---

## 6. Interações com trabalho recente

- **PAY-01 / D-1 (expiração):** o trial de 3 meses é a **primeira instância concreta** de expiração de plano. `expire_coach_trials` + `coach_trial_ends_at` viram o protótipo do mecanismo da opção B (cron + `plan_expires_at`) caso decidam aplicar a assinaturas de aluno também.
- **MRR (B-4):** acabamos de corrigir p/ R$99 × pro. Este plano **exclui** o Pro de cortesia do coach do MRR — senão cada coach novo infla o MRR em R$99 fantasma.
- **SEC-01 fase 2 (aprovação):** a métrica dos 15 reaproveita `link_status='approved'` + `invited_via_invite_id` já existentes. `maybe_promote_coach_earned` engata em `approve_link_request`.
- **Comp (4/10 ativos):** intacta. A meta dos 15 (pagantes) e a comissão (ativos) coexistem como rewards distintos.

---

## 7. Migração de coaches existentes (backfill)

Decisão de produto: coaches **já aprovados** hoje (plano free, sem trial) —
- **Opção recomendada:** conceder o trial de 3 meses a partir da data de migração (`plan='pro'`, `plan_source='coach_trial'`, `coach_trial_ends_at = migração+90d`) via `scripts/backfill_coach_trials.py --apply`, p/ não puni-los retroativamente.
- Alternativa: avaliar `paying_referred` imediatamente → quem já tem 15 vira `coach_earned`; o resto entra em trial.

---

## 8. Fases de entrega

- **P1 — Backend/base:** colunas + `approve_coach_application` (trial) + `expire_coach_trials` + `maybe_promote_coach_earned` + `get_coach_trial_status` + endpoint `/coach/trial-status` + MRR exclui cortesia + job + testes.
- **P2 — Frontend:** liberar rotas de aluno p/ coach + switch de workspace + banner de trial no cockpit.
- **P3 — Polish:** notificação "seu trial acaba em X dias", docs `/docs`, i18n, backfill de coaches legados.

## 9. Testes (P1)

- `approve_coach_application` → plan=pro, source=coach_trial, ends_at≈+90d.
- `maybe_promote_coach_earned`: 14 pagantes = trial; o 15º → earned (idempotente).
- `expire_coach_trials`: trial vencido com ≥15 → earned (Pro mantido); <15 → free + source NULL; trial não-vencido intacto.
- MRR exclui `coach_trial`/`coach_earned`.
- Coach autenticado acessa endpoint de aluno (upload/insights) durante o trial; pós-downgrade cai p/ limites free.
- `get_coach_trial_status` devolve days_left/paying_referred corretos.

## 10. Decisões em aberto (mínimas)

1. **Backfill de coaches legados** (§7): conceder trial novo vs avaliar meta na hora. *(recomendado: trial novo)*
2. **Nav unificada vs switch** (§5.2): adotei switch; confirmar.
3. **Aviso de fim de trial** (P3): in-app apenas vs e-mail também.
