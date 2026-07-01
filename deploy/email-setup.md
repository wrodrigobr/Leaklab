# Setup de email (Brevo + SMTP)

Como ligar o envio de email da GrindLab. O código já existe; falta só provedor SMTP
e as env vars no servidor da **API** (Hetzner CX23). O envio fica **desligado** até
`ADMIN_EMAIL_ENABLED=1` estar setado.

## O que roda hoje

| Fluxo | Função | Gate |
|---|---|---|
| Comunicado do admin (DM/broadcast) por email | `send_admin_email_bulk` | `ADMIN_EMAIL_ENABLED` (default off) |
| Digest semanal (opt-in) | `run_weekly_digest` | disparo manual `/admin/send-digest` |
| Email transacional (aprovação/rejeição de coach) | `send_transactional_email` | sempre que houver SMTP |

Sem SMTP configurado, todo envio é **no-op gracioso** (só loga). O sino de notificações
in-app funciona independente de email.

## 1. Conta Brevo

Criar em [brevo.com](https://www.brevo.com) (grátis, sem cartão). Free tier: ~300/dia,
~9.000/mês. SMTP nativo. Trigger de migração para Amazon SES: quando um broadcast passar
de 300 destinatários/dia.

## 2. Verificar o domínio `grindlabpoker.com`

Brevo → **Senders, Domains & Dedicated IPs → Domains → Add a domain**. Ele mostra os
registros para colar no **DNS da Cloudflare** (aba DNS do domínio). Tipicamente:

| Tipo | Nome | Valor | Nota |
|---|---|---|---|
| TXT | `@` (ou `brevo-code`) | código que o Brevo mostrar | autenticação do domínio |
| TXT (SPF) | `@` | inclui `include:spf.brevo.com` | se já houver SPF, só ADICIONE o include, não crie um segundo registro |
| TXT/CNAME (DKIM) | o que o Brevo indicar (`mail._domainkey`) | valor do Brevo | assinatura DKIM |
| TXT (DMARC) | `_dmarc` | `v=DMARC1; p=none; rua=mailto:rodrigo@grindlabpoker.com` | começar com `p=none` (monitora, não bloqueia) |

Gotcha Cloudflare: qualquer CNAME que o Brevo pedir tem que ficar **"DNS only" (nuvem
cinza)**, nunca proxied. Sem SPF+DKIM, o email cai em spam.

## 3. Credenciais SMTP

Brevo → **SMTP & API → SMTP** → gerar uma **SMTP key**.

```
SMTP_HOST      = smtp-relay.brevo.com
SMTP_PORT      = 587
SMTP_USER      = <login SMTP mostrado nessa tela>
SMTP_PASSWORD  = <a SMTP key gerada; NÃO é a senha da conta>
DIGEST_FROM    = noreply@grindlabpoker.com
APP_BASE_URL   = https://grindlabpoker.com
ADMIN_EMAIL_ENABLED = 1
```

## 4. Setar no servidor da API (CX23)

Os segredos ficam no arquivo `.env` da pasta do app; o `docker-compose.yml` usa
`env_file: .env`.

```bash
cd ~/app          # ou /home/deploy/app
nano .env         # colar as 7 variáveis acima
docker compose up -d                    # aplica (recria o container web)
docker compose logs --tail=40 web       # conferir que subiu
```

- Use `docker compose up -d`, **não** `restart` — o `restart` não relê o `env_file`.
- **Não** precisa `--build`; env é lido em runtime, não é baked na imagem.

Conferir que pegou:

```bash
docker compose exec web sh -lc 'echo $SMTP_HOST; echo $ADMIN_EMAIL_ENABLED'
# deve imprimir: smtp-relay.brevo.com  e  1
```

## 5. Reabilitar o toggle no frontend

O checkbox "Enviar também por email" (aba Mensagens do admin) está **desabilitado** de
propósito enquanto SMTP não existe. Depois de ligar, reabilitar em
`frontend/src/pages/admin/AdminDashboard.tsx` (remover `disabled`/`opacity-60` do `<label>`
e atualizar o texto de ajuda). Rebuild do Cloudflare Pages.

## 6. Testar antes de soltar

1. DM de teste **pra você mesmo** com o toggle de email ligado.
2. Confere: chegou na inbox (não spam), SPF/DKIM = "pass" no cabeçalho.
3. Clica em "Não quero mais receber emails" → deve zerar o `email_opt_in` e a página de
   descadastro aparece.

## Compliance (LGPD)

- Coluna `email_opt_in` (default 1). Todo comunicado por email tem rodapé de descadastro.
- Endpoint `GET /player/email/unsubscribe?uid=&token=` (token HMAC, salt próprio) zera o
  opt-in. `get_email_recipients` filtra quem descadastrou antes de enviar.
- O digest tem opt-out próprio (`digest_subscribed` + `/player/digest/unsubscribe`).
