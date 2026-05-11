#!/bin/bash
# setup_vm.sh — Configura a VM do Google Cloud para rodar o solver GTO.
# Executar como root (ou com sudo) na VM.
# Uso: bash setup_vm.sh <GTO_API_KEY>

set -euo pipefail

API_KEY="${1:-}"
if [ -z "$API_KEY" ]; then
  echo "Uso: bash setup_vm.sh <GTO_API_KEY>"
  echo "Exemplo: bash setup_vm.sh minha-chave-secreta-32chars"
  exit 1
fi

echo "=== 1. Dependências do sistema ==="
apt-get update -qq
apt-get install -y -qq build-essential curl git python3

echo "=== 2. Rust toolchain ==="
if ! command -v cargo &>/dev/null; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
  source "$HOME/.cargo/env"
else
  echo "Rust já instalado: $(rustc --version)"
fi
source "$HOME/.cargo/env"

echo "=== 3. Diretório da aplicação ==="
mkdir -p /opt/leaklab
useradd -r -s /bin/false leaklab 2>/dev/null || true
chown leaklab:leaklab /opt/leaklab

echo "=== 4. Clone do repositório ==="
if [ ! -d /opt/leaklab/backend ]; then
  # Ajuste a URL do seu repositório se necessário
  git clone https://github.com/wrodrigobr/Leaklab.git /opt/leaklab
else
  echo "Repositório já existe — atualizando..."
  git -C /opt/leaklab pull
fi

echo "=== 5. Compilando solver_cli (pode levar 2-5 min) ==="
cd /opt/leaklab/backend/gto_bot/solver_cli
cargo build --release
echo "Binário: $(ls -lh target/release/solver_cli)"

echo "=== 6. Systemd service ==="
# Substitui a API key no service file
sed "s/CHANGE_ME/$API_KEY/" \
  /opt/leaklab/backend/gto_bot/solver_api/leaklab-solver.service \
  > /etc/systemd/system/leaklab-solver.service

systemctl daemon-reload
systemctl enable leaklab-solver
systemctl start leaklab-solver

echo ""
echo "=== Setup concluído ==="
systemctl status leaklab-solver --no-pager
echo ""
echo "Teste: curl http://localhost:8765/health"
echo "GTO_SOLVER_URL=http://34.70.251.42:8765"
echo "GTO_SOLVER_API_KEY=$API_KEY"
