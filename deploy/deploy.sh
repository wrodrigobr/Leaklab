#!/usr/bin/env bash
#
# Passos de deploy do backend, num lugar só.
#
# Roda DEPOIS da sincronização do git (que fica no chamador, de propósito: `git reset --hard`
# reescreveria este arquivo no meio da execução, e o bash lê script em pedaços).
#
# Existe porque o deploy acontece por dois caminhos — o job do GitHub Actions e o SSH manual — e
# procedimento duplicado diverge. Quando divergiu, o resultado foi um servidor com 22GB de cache
# esquecido: o passo de limpeza do job só rodava `docker image prune`, que NÃO toca no cache do
# buildkit, e a mão nunca soube que faltava algo.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== ARQUIVANDO LOG ==="
# `docker compose up --build` cria um container NOVO, e o histórico do anterior morre com ele.
# Medido em 21/08: fui procurar erros das últimas 24h em produção e o log começava minutos
# antes, no deploy. Sem isso, todo erro que um usuário encontra some no próximo deploy — e o
# programa de fundadores existe justamente para APRENDER com o que eles encontram.
#
# Não substitui o Sentry (que agrega, deduplica e alerta); é o piso para não perder o rastro.
mkdir -p logs
for _svc in web solver-consumer; do
  _cid="$(docker compose ps -q "$_svc" 2>/dev/null || true)"
  [ -n "$_cid" ] || continue
  _dest="logs/${_svc}-$(date -u +%Y%m%dT%H%M%SZ).log"
  # `|| true`: log indisponível não pode abortar o deploy (`set -e` mataria o script aqui).
  docker logs "$_cid" > "$_dest" 2>&1 || true
  echo "  $_svc -> $_dest ($(wc -l < "$_dest" 2>/dev/null || echo 0) linhas)"
done
# Teto de retenção: 30 arquivos por serviço. Sem isso o disco volta a encher em silêncio, que
# é exatamente o problema que a seção de LIMPEZA abaixo já teve uma vez.
ls -1t logs/web-*.log 2>/dev/null | tail -n +31 | xargs -r rm -f
ls -1t logs/solver-consumer-*.log 2>/dev/null | tail -n +31 | xargs -r rm -f

echo "=== BUILD ==="
# web E solver-consumer: os dois nascem do MESMO ./backend, mas `--build web` só recria o web.
# Medido em 12/08: o consumer rodava imagem de 30/07 — duas semanas de consertos (guarda do
# solve vazio, campos-viajantes do reconcile) deployados no web e NUNCA no processo que solva
# e reconcilia. `docker compose restart` também NÃO troca a imagem. Conferir o ambiente =
# conferir CADA container que executa o código, não o primeiro que responder.
docker compose up -d --build web solver-consumer

echo "=== LIMPEZA ==="
# Imagens soltas: o build anterior perde a tag `latest` e vira dangling.
docker image prune -f

# Cache do buildkit COM TETO. `docker image prune` não o alcança, e cada build acrescenta camadas:
# medido em 2026-08-01, 80 entradas somando 24,5GB, todas inativas, com o disco em 81%. O prune
# liberou 22GB de uma vez (81% → 23%).
#
# O teto mantém o build incremental rápido e impede a volta do problema. `--max-used-space` é o
# nome do flag no Docker 29+; em versões antigas era `--keep-storage`.
docker builder prune -f --max-used-space 5GB

echo "=== ESTADO ==="
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
df -h / | tail -1
