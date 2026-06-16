# PAY-01 — Revalidação do Stripe (pré-produção)

**Status:** Auditoria concluída 2026-06-16 · 5 bugs de correção **corrigidos** · 1 decisão de arquitetura **em aberto** (precisa do produto).

Escopo: `backend/leaklab/stripe_gateway.py`, `backend/api/app.py` (`/subscription/*`), `backend/database/repositories.py` (`save_payment`, `get_admin_dashboard_stats`, comp do coach). Objetivo: garantir que o meio de pagamento está funcional e correto **antes do launch**.

---

## Modelo atual (importante)

Não é uma **Subscription recorrente** do Stripe. É um **PaymentIntent único de 30 dias** (`pi_...`):
`create_subscription` cria um `PaymentIntent` (cartão, sem redirect), o frontend confirma e chama `/subscription/activate`, e o webhook `payment_intent.succeeded` confirma o mesmo pagamento. Isso tem consequências (ver D-1).

---

## Corrigido nesta revalidação

| # | Severidade | Achado | Correção |
|---|---|---|---|
| **B-1** | 🔴 Crítico | **Pagamento gravado em dobro.** Todo pagamento aprovado é salvo por **dois caminhos** p/ o mesmo `pi`: `/subscription/activate` (frontend) **e** o webhook `payment_intent.succeeded` — mais as **retentativas** de webhook do Stripe. `save_payment` era `INSERT` puro, sem `UNIQUE` em `gateway_id` → receita e histórico (`/invoices`, admin) inflados. | `save_payment` agora é **idempotente**: dedupe por `(gateway_id, status)` — se a linha já existe, devolve o id existente. |
| **B-2** | 🟠 Alto | **Pagamentos Stripe rotulados `gateway='mercadopago'`.** As chamadas de `save_payment` no fluxo Stripe não passavam `gateway=`, herdando o default `'mercadopago'`. Conciliação/relatórios por gateway ficavam errados. | `gateway='stripe'` nas duas chamadas (activate + webhook). |
| **B-3** | 🟠 Alto | **`/subscription/cancel` quebrado em produção.** `cancel_subscription(sub_id)` chamava `Subscription.cancel(pi_...)`, mas o id é um **PaymentIntent**, não uma Subscription → Stripe lança → 502, plano nunca cai. (O teste passava porque mockava `cancel_subscription`.) | `cancel_subscription` só chama o Stripe p/ ids `sub_...`; p/ `pi_...` faz **downgrade local** (não há subscription a cancelar). |
| **B-4** | 🟡 Médio | **MRR do admin subestimado pela metade.** `get_admin_dashboard_stats` usava `pro_users * 4900` (R$49), mas a cobrança real é `PLAN_AMOUNTS['pro']=99.00` (R$99). | `pro_users * 9900`, com comentário amarrando à fonte canônica. |
| **B-5** | 🟢 Baixo | **Marca "LeakLabs" na `description` do PaymentIntent** — texto **visível ao cliente** (recibo/fatura). | `description="GrindLab ..."`. |

Trilha de auditoria nova: webhook agora trata `payment_intent.payment_failed` → grava linha `status='failed'` (gateway `stripe`), **sem** alterar o plano.

**Testes:** `tests/test_subscription.py` 26 → **32** (+6): idempotência activate+webhook, idempotência de retentativa, rótulo `stripe`, cancel `pi_` sem chamar Stripe, `payment_failed` registrado, MRR = pro×9900.

---

## Decisão de arquitetura em aberto (precisa do produto)

### D-1 — Não há cobrança recorrente nem expiração automática

O modelo cobra **um PaymentIntent de 30 dias** e seta `plan='pro'` — mas:
- **Não renova** automaticamente (não é Subscription); não há `invoice.paid` recorrente.
- **Não expira:** `get_quota_status` lê `plan` direto, sem `plan_expires_at`. Uma vez pro, **fica pro p/ sempre** até cancelar manualmente (e o cancel estava quebrado — ver B-3).
- Sem tratamento de **falha de renovação** (só registramos a falha do PI inicial agora).

Ou seja: hoje o cliente paga **uma vez** e tem Pro **vitalício**. Isso é receita perdida (sem renovação) e/ou cobrança/UX inconsistente com "assinatura mensal".

**Opções:**
- **(A) Subscriptions de verdade** — migrar `create_subscription` p/ `stripe.Subscription`, tratar `invoice.paid` / `invoice.payment_failed` / `customer.subscription.deleted`, refletir no plano. Mais trabalho, modelo correto p/ recorrência.
- **(B) Expiração + cobrança manual** — manter PI único, adicionar `users.plan_expires_at` (= +30d na ativação) e um cron que faz downgrade quando vence; cliente recompra. Mais simples, sem auto-renovação.
- **(C) Aceitar como está** (Pro vitalício por R$99 único) — só se for decisão de produto consciente.

> **Recomendação:** (A) se "assinatura mensal" é a promessa ao cliente; (B) se quisermos lançar rápido sem complexidade de recorrência. **Não implementado** — fora do escopo de "revalidação", é mudança de modelo de cobrança.

---

## Checklist de smoke manual (Stripe Dashboard, antes do launch)

- [ ] `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` em **modo live** (nada de `sk_test`/`whsec_test` em prod).
- [ ] `STRIPE_PRICE_PRO` definido (se migrar p/ Subscriptions — D-1/A).
- [ ] Checkout real R$99 → cartão de teste → `/activate` → plano vira pro, **1** linha em `/invoices`.
- [ ] Reenviar o evento `payment_intent.succeeded` pelo Dashboard → **não** duplica (B-1).
- [ ] Webhook com assinatura inválida → 400 (já coberto por teste).
- [ ] `payment_intent.payment_failed` (cartão `4000000000000341`) → linha `failed`, plano segue free.
- [ ] Cancelar → plano cai p/ free sem erro (B-3).
- [ ] Admin dashboard: MRR = nº pro × R$99 (B-4); conciliação `coach_payments` bate com pagamentos pro reais.
