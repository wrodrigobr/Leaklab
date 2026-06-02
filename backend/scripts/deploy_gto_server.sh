#!/usr/bin/env bash
#
# deploy_gto_server.sh — Deploy do servidor GTO (leaklab-solver) na VM GCP.
#
# IMPORTANTE: o systemd `leaklab-solver` roda de /opt/leaklab, NÃO de ~/leaklab.
# Pulls em ~/leaklab NÃO chegam ao serviço (foi a causa de "nenhum fix pegava").
# Use SEMPRE este script pra deployar — garante pull no checkout certo, restart
# e verificação de saúde, sem depender de lembrar o path.
#
# Uso (na VM): bash /opt/leaklab/backend/scripts/deploy_gto_server.sh
#
set -euo pipefail

REPO="${LEAKLAB_GTO_REPO:-/opt/leaklab}"
SERVICE="${LEAKLAB_GTO_SERVICE:-leaklab-solver}"

echo "==> Deploy GTO server (repo=$REPO service=$SERVICE)"

if [ ! -d "$REPO/.git" ]; then
  echo "ERRO: $REPO não é um checkout git. Confira o WorkingDirectory do serviço:"
  echo "  systemctl cat $SERVICE | grep -E 'ExecStart|WorkingDirectory'"
  exit 1
fi

echo "==> git pull --ff-only origin main em $REPO"
sudo git -C "$REPO" pull --ff-only origin main

echo "==> Commit ativo:"
git -C "$REPO" log -1 --oneline

echo "==> Reiniciando $SERVICE"
sudo systemctl restart "$SERVICE"
sleep 3

if systemctl is-active --quiet "$SERVICE"; then
  echo "==> OK: $SERVICE ativo"
else
  echo "==> FALHOU — últimas linhas do log:"
  sudo journalctl -u "$SERVICE" -n 25 --no-pager
  exit 1
fi

# Smoke test opcional: confirma que o /gw-status responde (não falha o deploy se ausente)
PORT="${LEAKLAB_GTO_PORT:-8765}"
if command -v curl >/dev/null 2>&1; then
  echo "==> Smoke test /gw-status (porta $PORT):"
  curl -s --max-time 8 "http://localhost:${PORT}/gw-status" || echo "(sem resposta — verifique manualmente)"
  echo
fi

echo "==> Deploy concluído."
