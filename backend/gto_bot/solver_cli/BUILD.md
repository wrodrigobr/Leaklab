# solver_cli — Build & Deploy

## Requisitos

- Rust 1.70+ (`rustup update stable`)
- CPU com suporte AVX2 (Intel Haswell 2013+ / AMD Zen 2017+)
- Para deploy no Render (Linux): target `x86_64-unknown-linux-gnu`

## Build local (Windows)

```bash
cd backend/gto_bot/solver_cli
cargo build --release
```

Binário: `target/release/solver_cli.exe`

## Build para Linux (cross-compile ou no próprio Render)

```bash
# Instalar target Linux
rustup target add x86_64-unknown-linux-gnu

# Linux nativo (no servidor ou WSL)
cargo build --release
```

Binário: `target/release/solver_cli`

## Testar

```bash
echo '{"street":"flop","board":["Ah","Kd","2c"],"hero_range":"AA,KK,QQ,AKs","villain_range":"QQ+,AKs","hero_position":"OOP","pot_bb":10,"hero_stack_bb":40}' | ./target/release/solver_cli
```

## Integrar no Docker (Render)

No `Dockerfile`, adicione antes do `CMD`:

```dockerfile
COPY backend/gto_bot/solver_cli/target/release/solver_cli /app/gto_bot/solver_cli/target/release/solver_cli
RUN chmod +x /app/gto_bot/solver_cli/target/release/solver_cli
```

Ou compile no próprio Dockerfile:

```dockerfile
RUN apt-get install -y curl && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    . $HOME/.cargo/env && \
    cd /app/gto_bot/solver_cli && cargo build --release
```

## Variável de ambiente (opcional)

`GTO_SOLVER_BIN` — caminho absoluto do binário (sobrescreve o padrão).
Se não definida, o sistema procura em `backend/gto_bot/solver_cli/target/release/solver_cli`.
