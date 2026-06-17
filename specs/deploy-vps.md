# Deploy em VPS único — seguro e performático (GrindLab)

**Status:** plano/runbook · criado 2026-06-17
**Objetivo:** hospedar **frontend + backend + Postgres** num único VPS Linux, barato, **seguro** e **performático**, com **backup offsite automatizado e testado**. O **solver fica numa máquina à parte** (CPU/RAM-intensivo + isolamento AGPL).

---

## 1. Arquitetura

```
                 ┌─────────── Cloudflare (proxy ON) ───────────┐
   Usuário ──▶   │  CDN global · TLS · DDoS · WAF · rate-limit  │
                 └───────────────────┬─────────────────────────┘
                                     │ (só IPs Cloudflare nas portas 80/443)
        ┌────────────────────────────▼─────────────────────────────┐
        │  VPS-APP (Linux, Hetzner CX22/CX32)                       │
        │  ┌──────────┐   ┌─────────────────┐   ┌────────────────┐  │
        │  │  Nginx   │──▶│ Gunicorn/Flask  │──▶│  PostgreSQL    │  │
        │  │ (static  │   │ (Docker, app)   │   │ (Docker, rede  │  │
        │  │  + proxy)│   └─────────────────┘   │  interna only) │  │
        │  └──────────┘                         └───────┬────────┘  │
        └────────────────────────────────────────────── │ ─────────┘
                                                         │ pg_dump nightly (cron)
                                                         ▼
                          Backblaze B2 / S3 (backup OFFSITE, criptografado)

   VPS-SOLVER (separado, beefy) ── solver_api ── acessível SÓ pelo VPS-APP
                                  (rede privada / allowlist; nunca público)
```

**Por que VPS único para o app:** Nginx serve o `dist/` estático **e** faz reverse-proxy pro Flask; Postgres roda no mesmo host mas **só na rede interna do Docker** (nunca exposto à internet). Cloudflare na frente esconde o IP de origem e absorve ataque/tráfego.

**Por que o solver fica fora:** CFR é CPU/RAM-bound e roubaria recurso do web app; e o binário AGPL deve ficar isolado server-side (ver [[project_agpl_solver_compliance]]). Comunicação VPS-APP → VPS-SOLVER por rede privada do provedor (Hetzner private network) ou firewall allowlist; o solver **nunca** escuta na internet pública.

---

## 2. Segurança (camadas)

**A. Cloudflare (proxy ON) — o maior ganho com menor esforço:**
- TLS grátis (Full Strict + Origin Certificate de 15 anos no Nginx), HSTS.
- **DDoS + WAF + Bot Fight** + rate-limit (regra p/ `/auth/*`, `/subscription/*`).
- Esconde o IP real do servidor → o firewall de origem só aceita **IPs da Cloudflare** nas portas 80/443.

**B. SSH e host:**
- SSH **só por chave** (`PasswordAuthentication no`), **root login off**, usuário sudo dedicado, `fail2ban`.
- `ufw`: default **deny**; permitir 22 (idealmente só seu IP ou via Cloudflare Tunnel), 80/443 **só dos ranges Cloudflare**. **Porta do Postgres NUNCA aberta.**
- `unattended-upgrades` (patches de segurança automáticos).

**C. Docker:**
- Postgres **sem `ports:` publicado** — só acessível pela rede interna `app-net`.
- Segredos em `.env` (`chmod 600`, **fora do git**) ou Docker secrets; nada de chave em imagem/repo.
- Containers com `restart: unless-stopped`, limites de recurso, e (onde der) usuário não-root.

**D. Aplicação (já no código):**
- `LEAKLAB_SECRET` ≥32 chars (startup falha sem isso em prod), `ALLOWED_ORIGINS` = domínio real (não `*`).
- Webhook do Stripe valida assinatura; rate-limiter já existe; anti-fraude do billing ([[project_billing_model]]).
- Headers no Nginx: HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP básica.
- Usuário do Postgres com privilégio mínimo (só o schema da app).

**E. Solver:** server-side only; reachable só do VPS-APP; binário nunca distribuído.

---

## 3. Backup (a maior preocupação) — "backup não testado = não tem backup"

**Estratégia 3-2-1:** 3 cópias, 2 mídias, 1 offsite.

1. **Dump lógico nightly** (`pg_dump -Fc`) → **criptografa** (`age`/`gpg`) → **upload offsite** (Backblaze B2 — barato — ou S3) via cron. Script: `scripts/backup_postgres.sh`.
2. **Retenção GFS:** 7 diários + 4 semanais + 6 mensais (rotação automática no bucket / lifecycle policy).
3. **Snapshot da VPS** semanal (Hetzner Snapshot, ~€0,01/GB/mês) → recuperação rápida da máquina inteira.
4. **Restore testado:** `scripts/restore_postgres.sh` + um lembrete mensal (`/schedule`) de **restaurar num container descartável e conferir**. Sem isso, o backup é fé, não garantia.
5. **Alerta de falha:** o cron pinga **healthchecks.io** (grátis) ao terminar; se não pingar, você recebe e-mail. Backup que falha calado é o pior cenário.
6. *(Opcional, avançado)* **PITR** com WAL archiving (`wal-g`/`pgbackrest`) p/ recuperar até o minuto — fica pra fase 2; o dump nightly cobre o MVP.

> **Alternativa de menor risco operacional:** usar **Postgres gerenciado (Neon/Supabase)** com backup automático e deixar só frontend+backend no VPS. Custa um pouco mais, mas você não cuida de backup. Recomendado se não quiser ser o responsável pelo banco no início — o resto do plano vale igual.

---

## 4. Performance

- **Cloudflare CDN** serve estáticos do edge global (Brotli, HTTP/2 e /3) → frontend rápido em qualquer região.
- **Nginx:** gzip/brotli, `dist/` com cache longo + `immutable` (assets com hash), `try_files` p/ SPA.
- **Gunicorn:** `workers = 2×vCPU + 1` (ou `gthread`), timeouts ajustados, atrás do Nginx.
- **Postgres:** tunar `shared_buffers`/`work_mem`/`effective_cache_size` ao tamanho da caixa; índices já existem; **PgBouncer** se a concorrência subir.
- **Solver isolado** → o web app nunca trava por causa de um solve.
- Disco **NVMe** + RAM suficiente pro cache do Postgres.

---

## 5. Sizing e custo (ordem de grandeza)

| Item | Sugestão | Custo |
|---|---|---|
| VPS-APP | Hetzner **CX22** (2 vCPU/4 GB) p/ começar; CX32 (4/8) se crescer | ~€4–8/mês |
| Backup offsite | Backblaze B2 (alguns GB) | ~€1/mês |
| Snapshots | Hetzner | centavos |
| CDN/TLS/WAF | Cloudflare Free | €0 |
| VPS-SOLVER | separado (ver discussão Hetzner/Contabo) | à parte |

**App inteiro (fora o solver): ~€5–10/mês**, com segurança e backup de verdade.

---

## 6. Entregáveis (a materializar na implementação)

- `deploy/docker-compose.yml` — `nginx`, `web` (Gunicorn/Flask, reusa o `backend/Dockerfile`), `db` (Postgres, rede interna).
- `deploy/nginx/grindlab.conf` — static SPA + reverse-proxy + headers + cache + TLS (Origin Cert Cloudflare).
- `deploy/.env.example` — todas as vars (LEAKLAB_SECRET, DATABASE_URL, STRIPE_*, ANTHROPIC_API_KEY, ALLOWED_ORIGINS, GTO_SOLVER_URL).
- `scripts/backup_postgres.sh` + `scripts/restore_postgres.sh` (dump cifrado → B2 + restore testável).
- `scripts/server_bootstrap.sh` — ufw + fail2ban + unattended-upgrades + Docker + usuário sudo + ranges Cloudflare.
- `deploy/README.md` — runbook passo a passo (provisão → bootstrap → TLS → subir → backup → cron → restore-test).

---

## 7. Ordem de execução

1. Provisionar VPS (Hetzner), apontar DNS no Cloudflare (proxy ON).
2. `server_bootstrap.sh` (firewall, ssh, fail2ban, docker, updates).
3. `.env` (segredos, `chmod 600`), Origin Certificate da Cloudflare no Nginx.
4. `docker compose up -d` (db → migrações automáticas no startup do app → web → nginx).
5. `backup_postgres.sh` no cron diário + healthchecks.io; snapshot semanal.
6. **Rodar `restore_postgres.sh` num container descartável e confirmar** (teste de fogo).
7. Crons da app no host: `expire_subscriptions.py`, `expire_coach_trials.py` (billing/coach).
8. Solver: subir `solver_api` no VPS-SOLVER e apontar `GTO_SOLVER_URL` (rede privada).

---

## Decisões em aberto (suas)

1. **Banco no VPS (mais barato, você cuida do backup) vs gerenciado Neon/Supabase (zero ops de backup, +US$).** Recomendo gerenciado se billing/usuários forem críticos e você não quiser ser o DBA.
2. **Provedor do VPS-APP:** Hetzner (melhor custo-benefício/confiabilidade) recomendado.
3. **PITR agora ou fase 2:** dump nightly cobre o MVP; WAL archiving fica pra depois.
