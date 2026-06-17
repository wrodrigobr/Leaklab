# Cloudflare — configuração completa (GrindLab)

**Status:** runbook · criado 2026-06-17 · complementa [`deploy-vps.md`](deploy-vps.md)
**Domínio:** `grindlabpoker.com`. Modelo **recomendado:** frontend no **Cloudflare Pages** + backend/Postgres no **Hetzner** (atrás do proxy Cloudflare).

> **"Cloudflare" faz 2 papéis distintos:**
> 1. **Cloudflare Pages** (§1.5) — *hospeda* o frontend estático na borda (grátis, CDN, TLS, deploy por git). É onde o **frontend** roda.
> 2. **Proxy/CDN** (§3–§8) — fica *na frente* do **backend** no Hetzner (`api.grindlabpoker.com`). O runbook de SSL/firewall/IP-real abaixo é para **o backend** — o Pages já traz TLS/CDN/DDoS prontos.

> 3 partes **tocam o servidor** (backend, não frontend): **§3** (SSL/Origin Cert), **§4** (firewall só-Cloudflare), **§5** (IP real do cliente). As demais são no painel.

---

## 0. Pré-requisitos
- Domínio registrado (em qualquer registrador) e acesso para **trocar os nameservers**.
- Conta na **Cloudflare** (plano **Free** basta).
- VPS provisionado com **IP público** (a "origem").

---

## 1. Adicionar os sites (dois domínios)
São **dois registros**: `grindlabpoker.com` (internacional) e `grindlabpoker.com.br` (Brasil). Decisão: **um é o canônico** (onde o site roda) e o outro **redireciona 301** para ele (SEO/marca: evita conteúdo duplicado). Recomendado: **`grindlabpoker.com.br` canônico** (público BR) e `.com` → 301 para `.com.br` — ou o inverso, é sua escolha; troca-se com 1 regra.

1. Cloudflare → **Add a site** → `grindlabpoker.com.br` → plano **Free**. Repita para `grindlabpoker.com` (cada domínio é uma "zona" separada).
2. Cada zona dá **2 nameservers**. **No registrador troque os nameservers:**
   - `.com.br` → no **registro.br** (painel → Alterar servidores DNS).
   - `.com` → no registrador onde você comprou.
   (Propaga de minutos a horas.) Status vira **Active** quando propagar.
3. **Redirect do secundário** (na zona do `.com`): **Rules → Redirect Rules** → "se hostname = `grindlabpoker.com` (ou `www`)" → **301** para `https://grindlabpoker.com.br/$1` (preserva o path). Assim só o canônico serve conteúdo.

---

## 1.5. Cloudflare Pages (frontend) — onde o frontend roda
1. **Workers & Pages → Create → Pages → Connect to Git** → repositório do projeto.
2. Build: **Framework: Vite**, **Build command:** `cd frontend && npm install && npm run build`, **Output dir:** `frontend/dist`.
3. **Environment variables (build):**
   - `VITE_API_URL=https://api.grindlabpoker.com` (o frontend resolve a API por essa var — `src/lib/api.ts`).
   - `VITE_STRIPE_PUBLISHABLE_KEY=pk_live_...`
4. **Custom domain:** ligue `grindlabpoker.com` (+ `www`) no projeto Pages → a Cloudflare cria os registros automaticamente.
5. Cada `git push` no branch de produção → build + deploy automático na borda. **TLS, CDN e DDoS já vêm embutidos** (frontend não precisa de Origin Cert nem firewall).

> SPA fallback (rotas do React em refresh/deep-link) é tratado pelo Pages automaticamente.

## 2. DNS records
No painel **DNS → Records**. Regra de ouro: **só o que é web fica proxied (nuvem laranja 🟠); SSH e solver NÃO**.

**Modelo recomendado (frontend no Pages + backend no Hetzner):**
| Tipo | Nome | Conteúdo | Proxy |
|---|---|---|---|
| (auto) | `grindlabpoker.com` + `www` | **Cloudflare Pages** (criado no §1.5) | 🟠 Proxied |
| A | `api` | `<IP do VPS Hetzner>` | 🟠 Proxied |
| A | `ssh` *(opcional)* | `<IP do VPS>` | ⚪ DNS only |

> **CORS:** frontend (`grindlabpoker.com`) e API (`api.grindlabpoker.com`) são origens distintas → no backend `ALLOWED_ORIGINS=https://grindlabpoker.com,https://www.grindlabpoker.com` (§9).
> ⚠️ O **VPS-SOLVER nunca entra no DNS** e nunca é proxied — só acessível pela rede privada do VPS-backend.

**Alternativa (VPS único serve tudo):** `grindlabpoker.com`/`www` → A para o IP do VPS (🟠); o Nginx serve o `dist/` estático + reverte pro Flask. Uma máquina só, mais ops, sem CORS. Ver [`deploy-vps.md`](deploy-vps.md).

---

## 3. SSL/TLS (toca o servidor) — **Full (Strict)** + Origin Certificate
**NUNCA use "Flexible"** (deixa Cloudflare↔origem em texto puro). O certo:

1. **SSL/TLS → Overview → modo: Full (Strict)**.
2. **SSL/TLS → Origin Server → Create Certificate** → gera um **Origin Certificate** (válido 15 anos, só confiável entre CF e sua origem). Salve os 2 arquivos: certificado (`.pem`) e chave privada (`.key`).
3. No VPS, instale no Nginx:
   ```nginx
   ssl_certificate     /etc/ssl/cloudflare/origin.pem;
   ssl_certificate_key /etc/ssl/cloudflare/origin.key;   # chmod 600
   ssl_protocols TLSv1.2 TLSv1.3;
   ```
4. **SSL/TLS → Edge Certificates:** ligue **Always Use HTTPS**, **Automatic HTTPS Rewrites**, **Minimum TLS 1.2**, e **HSTS** (Enable HSTS — max-age 6 meses, include subdomains; só depois de confirmar que tudo está em HTTPS).

---

## 4. Firewall de origem (toca o servidor) — só IPs da Cloudflare
Se o atacante descobrir o IP do VPS, ele **contorna a Cloudflare** indo direto na origem. Bloqueie isso: a origem só aceita 80/443 **dos ranges da Cloudflare**.

**No VPS (`ufw`):** permitir só os ranges de https://www.cloudflare.com/ips/ nas portas 80/443. Use o script `scripts/refresh_cloudflare_ips.sh` (gera regras ufw + um `include` do Nginx; rode por cron mensal — os ranges mudam raramente).

**No Nginx (defesa extra), restaure o IP real E recuse quem não vem da CF:**
```nginx
# /etc/nginx/conf.d/cloudflare.conf  (gerado pelo script)
set_real_ip_from 173.245.48.0/20;   # ... todos os ranges CF (v4 e v6)
real_ip_header CF-Connecting-IP;     # §5 — IP real do cliente
```

---

## 5. IP real do cliente (toca o código) — **gotcha do rate-limiter**
Com a Cloudflare proxiando, o backend vê o **IP da Cloudflare**, não o do usuário. Isso **quebra o rate-limiter** do app (`/analyze/guest` 10/h, `/subscription/checkout` 10/h) — todos os usuários viram "o mesmo IP". Conserto em 2 camadas:

1. **Nginx** restaura o IP real (já no §4: `real_ip_header CF-Connecting-IP`) e repassa:
   ```nginx
   proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   proxy_set_header X-Real-IP $remote_addr;
   ```
2. **Flask** precisa confiar no proxy para ler o IP real. Garantir `ProxyFix` na app:
   ```python
   from werkzeug.middleware.proxy_fix import ProxyFix
   app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
   ```
   (Validar se o `limiter` usa `get_remote_address` — com ProxyFix ele passa a ver o IP real.)

> Sem isso, o rate-limit anti-abuso fica inútil (ou bloqueia todo mundo de uma vez). **É a pegadinha mais comum atrás de Cloudflare.**

---

## 6. Cache (performance) — cachear estático, **nunca** API
**Rules → Cache Rules** (ou Page Rules no Free):
- **Cache os assets do frontend** (`/assets/*`, `*.js`, `*.css`, imagens): Edge TTL longo — eles têm hash no nome (`immutable`), então é seguro.
- **Bypass cache** em `/<api>/*`, `/subscription/*`, `/auth/*` e **`/subscription/webhook`** (respostas dinâmicas/privadas nunca podem ser cacheadas).
- HTML do SPA (`index.html`): **não cachear** (ou TTL curto), senão deploy novo não aparece.

---

## 7. WAF / Segurança (painel)
**Security → ...**
- **Bot Fight Mode**: ligado.
- **WAF Managed Rules**: ligadas (Free já tem o core).
- **Rate limiting rules** (Free permite 1 regra; priorize a mais sensível): ex. `(http.request.uri.path contains "/auth/login")` → mais de N req/min do mesmo IP → **Managed Challenge/Block**. (No Pro dá pra cobrir `/subscription/*` também.)
- **Security Level**: Medium; **Challenge Passage** padrão.
- **Scrape Shield**: Email Obfuscation + Hotlink Protection (opcional).

---

## 8. Stripe webhook — não bloquear/cachear
O Stripe chama `…/subscription/webhook` a partir dos **servidores dele** (não é navegador). Garanta:
- **Bypass cache** nessa rota (§6).
- Se alguma regra de WAF/Bot pegar tráfego sem JS, **crie exceção (Skip)** para o path `/subscription/webhook` (senão a Cloudflare desafia o Stripe e os eventos falham).
- A validação de assinatura do webhook (já no backend) continua sendo a verdadeira segurança da rota.

---

## 9. Config da aplicação (env)
- `ALLOWED_ORIGINS=https://grindlabpoker.com,https://www.grindlabpoker.com` (não `*`).
- Frontend chama a API pelo **mesmo domínio** (proxy `/api` no Nginx) → evita CORS e mixed-content.
- `VITE_STRIPE_PUBLISHABLE_KEY` no build do frontend.

---

## 10. Checklist de verificação (depois de configurar)
- [ ] `https://grindlabpoker.com` abre com **cadeado** e modo **Full (Strict)** (sem aviso de cert).
- [ ] `http://` redireciona pra `https://` (Always Use HTTPS).
- [ ] Acessar o **IP do VPS direto** no navegador (porta 80/443) → **recusado/timeout** (firewall só-CF funcionando).
- [ ] Logs do backend mostram **IPs reais** dos usuários (não ranges da Cloudflare) → ProxyFix/real_ip ok.
- [ ] Rate-limit do `/subscription/checkout` dispara por IP individual (testar) → não bloqueia todo mundo junto.
- [ ] Reenviar um evento de teste do Stripe → chega no `/subscription/webhook` (não é desafiado/cacheado).
- [ ] Asset com hash (`/assets/x.js`) responde com header de cache `HIT`; `/api/...` responde `BYPASS/DYNAMIC`.

---

## Entregáveis de código (a materializar)
- `scripts/refresh_cloudflare_ips.sh` — baixa os ranges CF, gera regras `ufw` + `conf.d/cloudflare.conf` do Nginx (cron mensal).
- `deploy/nginx/grindlab.conf` — server block com Origin Cert, real_ip, proxy headers, cache rules, security headers.
- `ProxyFix` no `api/app.py` (1 linha) — IP real do cliente atrás de proxy.
