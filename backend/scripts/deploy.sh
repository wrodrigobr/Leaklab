#!/usr/bin/env bash
# Deploy de producao COM verificacao. Roda no host, dentro de ~/app.
#
#   ./scripts/deploy.sh                 # web + solver-consumer
#   ./scripts/deploy.sh web             # so um servico
#
# Existe por causa da regra 4 do CLAUDE.md: o codigo e BAKED na imagem, entao `git pull` no host
# nao muda o container. Ja declarei um conserto "verificado" depois de rodar o teste dentro de um
# container onde o bind mount apontava para o inode antigo.
#
# E por causa da regra que fechou a auditoria de 27/08: a suite prova as FUNCOES, o portao prova a
# COMPOSICAO das camadas na tela. Naquela rodada o portao pegou quatro violacoes que a suite
# inteira nao pegaria, porque nenhuma delas mora dentro de uma funcao.
#
# Falha barulhenta em qualquer etapa. Nada aqui e "melhor esforco".
set -euo pipefail

SERVICOS="${*:-web solver-consumer}"
cd "$(dirname "$0")/.." 2>/dev/null || true
[ -f docker-compose.yml ] || cd ~/app

echo "== 1/5  git pull"
ANTES="$(git rev-parse HEAD)"
git pull --ff-only
ESPERADO="$(git rev-parse --short HEAD)"
echo "   HEAD: $ESPERADO"

# ── O script atualiza a SI MESMO, e o bash le por posicao de byte ───────────────────────────
#
# Em 28/08 o passo 1 trouxe uma versao nova deste arquivo (com a conferencia de preco no passo 5)
# e o bash seguiu executando a VELHA: a saida imprimiu o texto antigo do passo 5 e **a conferencia
# nunca rodou**, enquanto os containers subiam com o codigo novo. Um portao que se
# auto-desatualiza e pior que portao nenhum: ele declara aprovado o que nao mediu.
#
# Se o proprio deploy.sh mudou no pull, re-executa a versao nova UMA vez. `LEAKLAB_DEPLOY_REEXEC`
# impede o laco infinito caso algo de errado na comparacao.
if [ "$ANTES" != "$(git rev-parse HEAD)" ] && [ -z "${LEAKLAB_DEPLOY_REEXEC:-}" ]; then
  if ! git diff --quiet "$ANTES" HEAD -- backend/scripts/deploy.sh; then
    echo "   este script mudou no pull -- re-executando a versao nova"
    LEAKLAB_DEPLOY_REEXEC=1 exec bash backend/scripts/deploy.sh "$@"
  fi
fi

echo "== 2/5  build (carimbando $ESPERADO na imagem)"
GIT_SHA="$ESPERADO" docker compose build $SERVICOS

echo "== 3/5  up"
docker compose up -d $SERVICOS

echo "== 4/5  o codigo esta DENTRO de cada container?"
for s in $SERVICOS; do
  c="$(docker compose ps -q "$s")"
  [ -n "$c" ] || { echo "   FALHOU: servico $s sem container"; exit 1; }
  dentro="$(docker exec "$c" cat /app/.git_sha 2>/dev/null || true)"
  # Imagem sem carimbo NAO passa. A tentacao aqui e cair num teste fraco ("consegue importar?")
  # e chamar isso de verificado -- que e exatamente o erro que este passo existe para impedir.
  if [ -z "$dentro" ] || [ "$dentro" = "desconhecido" ]; then
    echo "   FALHOU: $s roda imagem SEM carimbo de commit. Rebuild pelo deploy.sh."; exit 1
  elif [ "$dentro" != "$ESPERADO" ]; then
    echo "   FALHOU: $s roda $dentro, esperado $ESPERADO"; exit 1
  else
    echo "   $s: $dentro"
  fi
done

echo "== 5/5  portao de aceite (a TELA) + invariantes (o BANCO) + preco (o STRIPE)"
WEB="$(docker compose ps -q web)"
docker exec "$WEB" python /app/scripts/portao_pos_deploy.py
docker exec "$WEB" python /app/scripts/varre_invariantes.py
# O preco e a unica coisa aqui que vive FORA do nosso sistema, entao ele e perguntado ao dono do
# fato. Em 28/08 o painel do Stripe mostrava R$39 que nao existia na conta live: trocar o numero
# na tela confiando nele teria feito o site anunciar um valor e o cartao ser debitado de outro.
docker exec "$WEB" python /app/scripts/conferir_precos_no_stripe.py

echo
echo "DEPLOY OK — $ESPERADO no ar, portao aprovado, nenhuma invariante piorou."
