#!/usr/bin/env bash
# setup_oracle.sh — Configura Oracle Cloud Always Free (Ampere A1 ARM64)
# Testado: Ubuntu 22.04 / Oracle Linux 8 + ARM64
#
# Uso:
#   chmod +x setup_oracle.sh
#   ./setup_oracle.sh
#
# Depois de rodar:
#   export DATABASE_URL="sqlite:////home/ubuntu/leaklab.db"
#   python3 ~/leaklab/backend/scripts/cloud/worker.py

set -euo pipefail

REPO_DIR="$HOME/leaklab"
SOLVER_DIR="$REPO_DIR/backend/gto_bot/solver_cli"
WORKER_DIR="$REPO_DIR/backend/scripts/cloud"

echo "=== LeakLab GTO Worker — Oracle Cloud Setup ==="
echo "Arch: $(uname -m)  OS: $(uname -s)"
echo

# ── 1. Dependências do sistema ────────────────────────────────────────────────
echo "→ Instalando dependências do sistema..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends \
        build-essential git curl python3 python3-pip python3-venv \
        libssl-dev pkg-config sqlite3
elif command -v dnf &>/dev/null; then
    sudo dnf install -y gcc git curl python3 python3-pip openssl-devel pkgconfig sqlite
else
    echo "WARN: gerenciador de pacotes não reconhecido — instale manualmente: gcc git curl python3"
fi

# ── 2. Rust ───────────────────────────────────────────────────────────────────
if ! command -v cargo &>/dev/null; then
    echo "→ Instalando Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
    # shellcheck source=/dev/null
    source "$HOME/.cargo/env"
else
    echo "→ Rust já instalado: $(rustc --version)"
    source "$HOME/.cargo/env" 2>/dev/null || true
fi

# ── 3. Clone / atualiza repositório ──────────────────────────────────────────
if [ -d "$REPO_DIR/.git" ]; then
    echo "→ Atualizando repositório..."
    git -C "$REPO_DIR" pull --ff-only
else
    echo "→ Clonando repositório..."
    echo "  IMPORTANTE: Informe a URL do seu repositório Git abaixo."
    echo "  Exemplo: https://github.com/SEU_USUARIO/leaklab.git"
    read -rp "  URL do repo Git: " GIT_URL
    git clone "$GIT_URL" "$REPO_DIR"
fi

# ── 4. Compilar solver_cli para Linux ARM64 ───────────────────────────────────
echo "→ Compilando solver_cli (pode levar 3-8 min)..."
cd "$SOLVER_DIR"
cargo build --release 2>&1 | tail -5
SOLVER_BIN="$SOLVER_DIR/target/release/solver_cli"
echo "  Binário: $SOLVER_BIN ($(du -sh "$SOLVER_BIN" | cut -f1))"

# Copia o binário para o diretório do worker (conveniente)
cp "$SOLVER_BIN" "$WORKER_DIR/solver_cli"
chmod +x "$WORKER_DIR/solver_cli"
echo "  Copiado para: $WORKER_DIR/solver_cli"

# ── 5. Python deps ────────────────────────────────────────────────────────────
echo "→ Instalando dependências Python..."
pip3 install --quiet --upgrade pip
pip3 install --quiet psycopg2-binary 2>/dev/null || true  # só se usar PostgreSQL

# ── 6. Exporta database do Windows (instrução) ───────────────────────────────
echo
echo "=== PRÓXIMO PASSO: transferir o banco de dados ==="
echo
echo "Se estiver usando SQLite local (Windows → Oracle):"
echo "  No Windows (PowerShell):"
echo "    scp C:\\Projetos\\leaklab\\backend\\leaklab.db ubuntu@<IP_ORACLE>:~/leaklab.db"
echo "  Na Oracle VM:"
echo "    export DATABASE_URL=sqlite:////home/ubuntu/leaklab.db"
echo
echo "Se estiver usando PostgreSQL:"
echo "  export DATABASE_URL=postgresql://user:senha@host:5432/leaklab"
echo

# ── 7. Systemd service (opcional) ─────────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/gto-worker.service"
echo "→ Criando serviço systemd opcional..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=LeakLab GTO Solver Worker
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORKER_DIR
Environment="SOLVER_BIN=$WORKER_DIR/solver_cli"
Environment="MAX_EXPLOIT=1.0"
Environment="SOLVER_TIMEOUT=120"
# Defina DATABASE_URL em /etc/gto-worker.env
EnvironmentFile=-/etc/gto-worker.env
ExecStart=/usr/bin/python3 $WORKER_DIR/worker.py
Restart=no
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "  Serviço criado: $SERVICE_FILE"
echo "  Para usar:"
echo "    echo 'DATABASE_URL=sqlite:////home/ubuntu/leaklab.db' | sudo tee /etc/gto-worker.env"
echo "    sudo systemctl daemon-reload"
echo "    sudo systemctl start gto-worker"
echo "    sudo journalctl -u gto-worker -f"

echo
echo "=== Setup completo! ==="
echo "Para rodar o worker manualmente:"
echo "  export DATABASE_URL=sqlite:////home/ubuntu/leaklab.db"
echo "  export SOLVER_BIN=$WORKER_DIR/solver_cli"
echo "  python3 $WORKER_DIR/worker.py"
