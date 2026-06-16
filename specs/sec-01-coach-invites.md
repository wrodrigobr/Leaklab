# SEC-01 — Convite single-use do coach (integridade da indicação)

**Status:** Fase 1 ✅ implementada (2026-06-15) · Fase 2 (aprovação) pendente
**Motivação:** a compensação do coach será por **alunos indicados e ativos**. Hoje a
indicação é burlável (chave permanente compartilhável). Esta spec fecha a integridade
da atribuição de referral **antes** de ligar a comp.

---

## 1. Problema (estado atual)

- `assign_invite_key(user_id)` gera **uma** chave `COACH-XXXXXX` por coach, **permanente e
  idempotente** (`repositories.py:2091`). Formato: `generate_invite_key()` = `COACH-` + `token_hex(3)` (2085).
- `link_student_to_coach(student_id, invite_key)` (2131): qualquer aluno com a chave se
  **auto-vincula** — seta `users.coach_id` + `users.invited_by_key`. Únicos guards: chave
  existe, não é o próprio, e `coach_profiles.max_students`. **Sem uso único, sem expiração,
  sem aprovação.**
- Front: `InviteKeyWidget.tsx` exibe a chave única + copiar; aluno cola em `POST /student/link-coach`
  (`app.py:2841`).

**Vetores:** (a) a chave passa de aluno para aluno → vínculos não-intencionais contam como
"indicados"; (b) a atribuição `invited_by_key` não distingue "indiquei deliberadamente" de
"alguém repassou meu código". Com comp por referral, isso é fraude/atribuição suja.

> Mitigação que já existe: comp exige `ativo = pro + importou em 30d`, então um código vazado
> só vira **dinheiro** se os alunos virarem pagantes ativos. Mas a **atribuição** já nasce suja.

---

## 2. Objetivo

Cada indicação é um **ato deliberado e único** do coach, atribuível com confiança. Duas camadas:

1. **Convite single-use** (base): código/link de uso único, com validade, consumido no resgate.
2. **Aprovação do coach** (reforço, fase 2): vínculo entra **pendente**; comp conta só aprovados.

---

## 3. Modelo de dados

Nova tabela `coach_invites` (migração em `database/schema.py`, idiom Postgres `ADD COLUMN IF
NOT EXISTS` / SQLite `PRAGMA table_info` guard — ver `_run_migrations`). CREATE em ambos backends:

```sql
CREATE TABLE IF NOT EXISTS coach_invites (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,   -- SERIAL no Postgres
    coach_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code         TEXT    NOT NULL UNIQUE,              -- ex.: COACH-INV-XXXXXXXX (single-use)
    status       TEXT    NOT NULL DEFAULT 'active',    -- active | redeemed | revoked | expired
    used_by      INTEGER REFERENCES users(id),         -- aluno que resgatou (NULL até resgate)
    used_at      TEXT,                                 -- timestamp do resgate
    expires_at   TEXT,                                 -- NULL = sem expiração; default +30d
    label        TEXT,                                 -- nota opcional do coach ("João do grupo X")
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_coach_invites_coach  ON coach_invites(coach_id);
CREATE INDEX IF NOT EXISTS idx_coach_invites_code   ON coach_invites(code);
CREATE INDEX IF NOT EXISTS idx_coach_invites_status ON coach_invites(coach_id, status);
```

**Atribuição de referral:** manter `users.invited_by_key` por backward-compat, mas a fonte
canônica de "indicado" passa a ser **`coach_invites.used_by`** (vínculo via convite single-use).
Adicionar `users.invited_via_invite_id INTEGER REFERENCES coach_invites(id)` p/ atribuição direta
e auditável (quem indicou, com qual convite, quando).

**Fase 2 (aprovação):** adicionar `users.link_status TEXT DEFAULT 'approved'` (`pending|approved|
rejected`). Comp conta só `approved`. Legados ficam `approved` (não quebra).

---

## 4. Geração do código

```python
def generate_single_use_invite_code() -> str:
    # distinto da chave de coach (COACH-XXXXXX); mais entropia (uso único, não-adivinhável)
    return "INV-" + secrets.token_urlsafe(9).upper().replace('_', '').replace('-', '')[:12]
```
- Unicidade garantida por loop de colisão (igual `assign_invite_key`).
- Link compartilhável: `https://<app>/join?invite=<code>` (deep-link → tela de resgate logado).

---

## 5. Backend

### 5.1 Repositories (`database/repositories.py`)
- `create_coach_invite(coach_id, *, expires_days=30, label=None) -> dict` — gera código único, insere `active`.
- `list_coach_invites(coach_id) -> list` — convites do coach + status (deriva `expired` on-read se `expires_at < now`).
- `revoke_coach_invite(coach_id, invite_id) -> bool` — só do próprio coach; só se `active`.
- `redeem_coach_invite(student_id, code) -> dict` — **transação**:
  1. `SELECT ... WHERE code=? AND status='active'` (lock); inexistente/usado/expirado/revogado → erro específico.
  2. valida `expires_at`, `coach_id != student_id`, `max_students` (reusa o guard atual).
  3. `UPDATE coach_invites SET status='redeemed', used_by=?, used_at=now WHERE id=?`.
  4. `UPDATE users SET coach_id=?, invited_by_key=<code legível>, invited_via_invite_id=? WHERE id=?`
     (+ `link_status='pending'` na fase 2).
  - Idempotência/corrida: o `WHERE status='active'` + `UPDATE` numa transação garante uso único
    (segundo resgate falha "já utilizado").
- **Comp:** `get_coach_finance_summary` / `get_coaches_with_payout_status` passam a contar
  **indicados ativos** = `users` com `invited_via_invite_id IS NOT NULL` (fase 2: `AND link_status='approved'`)
  `AND plan='pro' AND importou_30d`. Faixas inalteradas (decisão PAY/produto à parte).

### 5.2 Endpoints (`api/app.py`, `@require_coach` salvo o resgate)
- `POST /coach/invites` — body `{label?, expires_days?}` → cria, retorna `{code, link, expires_at}`.
- `GET  /coach/invites` — lista (active/redeemed/revoked/expired) com `used_by` (username) e datas.
- `DELETE /coach/invites/<id>` — revoga.
- `POST /student/redeem-invite` (`@require_auth`) — body `{code}` → `redeem_coach_invite`. **Substitui** o `link_coach` por chave permanente.
- **Compat:** manter `POST /student/link-coach` (chave `COACH-...`) atrás de flag `LEGACY_COACH_KEY_ENABLED` (default OFF em prod); `assign_invite_key`/`GET /coach/invite-key` ficam só p/ migração.
- **Fase 2:** `GET /coach/link-requests` (pendentes), `POST /coach/link-requests/<student_id>/approve|reject`.

### 5.3 Migração de dados
- Vínculos existentes (`users.coach_id` setado) → `link_status='approved'`, `invited_via_invite_id=NULL`
  (legados não contam como "indicado via convite" até decisão; ou backfill opcional gerando um
  `coach_invites` "legacy redeemed" por aluno já vinculado, p/ contar na comp — **decisão de produto**).

---

## 6. Frontend

- **`InviteKeyWidget.tsx` → `InviteManager`** (coach dashboard, aba Alunos / sidebar):
  - Botão **"Convidar aluno"** → cria convite → mostra **link + código** copiáveis (1 por pessoa).
  - **Lista de convites:** código, label, status (Ativo/Resgatado por @aluno/Expirado/Revogado),
    criado/expira, botão **Revogar** (só nos ativos).
  - Remove o "compartilhe esta chave com seus alunos" (passável) → copy passa a ser "gere um convite
    por aluno".
- **Tela de resgate do aluno** (`/join?invite=` ou input no perfil): mostra o coach-alvo, botão
  "Vincular"; erros claros (inválido/usado/expirado/limite atingido).
- **i18n** PT/EN/ES (novo namespace `invites` ou estender `coaches`). Sem hardcode.
- **`api.ts`:** `coachDashboard.createInvite/listInvites/revokeInvite`, `student.redeemInvite`.

---

## 7. Edge cases & segurança
- Resgate de convite já usado/expirado/revogado → erro específico (não vaza se o coach existe).
- Aluno já vinculado a OUTRO coach → bloquear (ou exigir `unlink_coach` antes — já existe em 434).
- `max_students` atingido → erro (reusa guard); convite **não** é consumido nesse caso.
- Corrida de duplo-resgate → transação garante 1 vencedor.
- Rate-limit em `POST /coach/invites` (evita geração em massa) e em `/student/redeem-invite` (brute-force de código — daí a entropia alta de `INV-`).
- Auditoria: `coach_invites` é o trilho de quem-indicou-quem-quando (útil p/ disputa de comp).

---

## 8. Testes (`tests/test_coach_system.py` + novo `test_coach_invites.py`)
- criar → listar → resgatar → status vira `redeemed`, `users.coach_id`/`invited_via_invite_id` setados.
- resgate de código usado/expirado/revogado → erro; convite não muda.
- duplo-resgate concorrente → exatamente 1 sucesso.
- `max_students` no resgate → erro e convite segue `active`.
- comp: contagem de "indicados ativos" usa `invited_via_invite_id` (+ `link_status` na fase 2).
- (fase 2) pendente não conta na comp até `approve`.

---

## 9. Faseamento
- **Fase 1 (base):** tabela + geração/lista/revogação/resgate single-use + `InviteManager` + i18n + testes. Liga a atribuição por `invited_via_invite_id`. **Pré-requisito da comp por referral.**
- **Fase 2 (aprovação):** `link_status` pendente + UI de aprovação + comp conta só aprovados.
- **Fase 3 (limpeza):** desligar a chave permanente legada em prod; migração/decisão sobre vínculos antigos.

**Esforço estimado:** Fase 1 ~6h back + ~8h front · Fase 2 ~4h back + ~5h front.

---

## 10. Decisões de produto pendentes (bloqueiam implementação)
1. **Vínculos legados contam como "indicado"?** (backfill `coach_invites` legacy ou só novos via convite.)
2. **Faixas de comp** (0 / R$15 / R$20) mudam ao trocar a base p/ "indicados ativos"? (cruza com PAY-01/financeiro.)
3. **Aprovação do coach** entra já na fase 1 ou fica pra fase 2?
4. **Expiração default** do convite (sugerido 30d) e se o coach pode gerar N convites simultâneos (sugerido sim, com rate-limit).
