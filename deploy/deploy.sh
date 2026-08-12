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
