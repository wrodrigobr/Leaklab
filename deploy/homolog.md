# Homologação local — réplica de prod antes de publicar

Diretriz de 02/09/2026 (primeiro dia com pagante real): todo deploy de backend não-trivial
passa antes por uma réplica local com a **mesma imagem Docker** e **Postgres de verdade**.
A suíte prova as funções em SQLite; a homologação prova a composição no dialeto de prod.

## Pré-requisito (uma vez)

1. Instalar o Docker Desktop para Windows (docker.com) e abrir até o daemon ficar verde.
2. `copy deploy\.env.homolog.example deploy\.env.homolog` — sem chaves de prod, como está.

## Banco: restaurar um retrato de prod (recomendado)

O Neon tem backup; para a réplica, gere um dump e restaure no Postgres local:

```powershell
# 1. subir só o banco
docker compose -f deploy/docker-compose.homolog.yml --env-file deploy/.env.homolog up -d db

# 2. dump do Neon (pega a connection string no console do Neon; roda de onde tiver pg_dump,
#    ou dentro do proprio container db, que ja tem os binarios do PG 16):
docker compose -f deploy/docker-compose.homolog.yml exec db sh -c "pg_dump '<NEON_URL>' -Fc -f /tmp/prod.dump"

# 3. restaurar no banco local
docker compose -f deploy/docker-compose.homolog.yml exec db sh -c "pg_restore -U leaklab -d leaklab --clean --if-exists /tmp/prod.dump"
```

Sem dump também funciona: o app roda as migrações num banco vazio no boot — serve para
homologar migração nova, não para homologar comportamento sobre dados reais.

**NUNCA** aponte o `DATABASE_URL` desta stack para o Neon de produção. O compose já fixa o
serviço `db` local; não sobrescreva.

## Subir e verificar

```powershell
docker compose -f deploy/docker-compose.homolog.yml --env-file deploy/.env.homolog up -d --build
# API: http://localhost:5001/health

# o MESMO portão de prod, contra a réplica:
docker compose -f deploy/docker-compose.homolog.yml exec web python /app/scripts/portao_pos_deploy.py
docker compose -f deploy/docker-compose.homolog.yml exec web python /app/scripts/varre_invariantes.py
```

Frontend contra a réplica: `cd frontend && npm run dev` com o proxy de `/api` apontado para
`localhost:5001` (ajuste temporário no `vite.config.ts`; não commitar).

## Derrubar

```powershell
docker compose -f deploy/docker-compose.homolog.yml down        # mantém o banco
docker compose -f deploy/docker-compose.homolog.yml down -v     # zera o banco
```

## O que NÃO se homologa aqui

- Cobrança (Stripe): jornada de pagamento nunca roda contra chave LIVE. Test mode, se preciso.
- Solver: sem `GTO_SOLVER_URL` a fila local enche e fica pendente — esperado. O box do solver
  é rede privada do Hetzner e não é alcançável daqui.
- nginx/TLS/Cloudflare: fora da stack de propósito.
