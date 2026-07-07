#!/usr/bin/env bash
# Comando único: cura N spots do Desafio do Dia e renderiza os posts (Stories quiz:
# pergunta + resposta por spot). Uso:  ./make-daily-posts.sh [N]   (padrão 5)
set -e
N="${1:-5}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Curando $N spots =="
python "$ROOT/backend/scripts/build_challenge_posts.py" --n "$N"

echo "== Renderizando (pergunta + resposta por spot) =="
cd "$ROOT/video" && npm run posts

echo "== Pronto: vídeos em video/out/ (diaN-pergunta.mp4 + diaN-resposta.mp4) =="
