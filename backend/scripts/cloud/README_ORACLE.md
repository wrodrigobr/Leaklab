# GTO Solver — Oracle Cloud Always Free

Guia completo para rodar o solver nos 4 vCPUs Ampere A1 da Oracle Cloud.

---

## 1. Criar VM no Oracle Cloud

1. Acesse [cloud.oracle.com](https://cloud.oracle.com) → **Compute → Instances → Create Instance**
2. **Name**: `leaklab-gto`
3. **Image**: Ubuntu 22.04 (ou Oracle Linux 8)
4. **Shape**: `VM.Standard.A1.Flex`
   - OCPUs: **4**
   - RAM: **24 GB**
   - *(é o Always Free — sem custo)*
5. **Networking**: VCN padrão, subnet pública, **atribuir IP público**
6. **SSH keys**: faça upload da sua chave pública (`~/.ssh/id_rsa.pub`)
   - Se não tiver: `ssh-keygen -t rsa -b 4096` no terminal local
7. Clique **Create** e aguarde o status ficar `RUNNING` (~2 min)

---

## 2. Liberar porta SSH no firewall Oracle

No Console Oracle:
- **Networking → Virtual Cloud Networks → sua VCN → Security Lists → Default Security List**
- Confirme que existe regra: TCP, Source `0.0.0.0/0`, Destination Port `22`
  *(normalmente já existe por padrão)*

---

## 3. Conectar via SSH

```bash
# No terminal local (Mac/Linux/Git Bash no Windows)
ssh ubuntu@<IP_PUBLICO_DA_VM>
```

> **Dica Windows**: use o Git Bash ou o Windows Terminal com OpenSSH.  
> O IP público aparece na página da instância no console Oracle.

---

## 4. Rodar o setup na VM

```bash
# Na VM Oracle (após SSH):
curl -O https://raw.githubusercontent.com/SEU_USUARIO/leaklab/main/backend/scripts/cloud/setup_oracle.sh
# OU, se não tiver GitHub público, copie o arquivo via scp:
#   No Windows: scp C:\Projetos\leaklab\backend\scripts\cloud\setup_oracle.sh ubuntu@<IP>:~/

chmod +x setup_oracle.sh
./setup_oracle.sh
```

O script vai:
- Instalar Rust, gcc, Python 3, sqlite3
- Clonar o repositório (pedirá a URL do Git)
- Compilar `solver_cli` para ARM64 (~5 min)
- Criar o serviço systemd `gto-worker`

---

## 5. Transferir o banco de dados SQLite

O banco local está em `C:\Projetos\leaklab\backend\leaklab.db`.

**No Windows (PowerShell ou Git Bash):**
```bash
scp C:/Projetos/leaklab/backend/leaklab.db ubuntu@<IP_ORACLE>:/home/ubuntu/leaklab.db
```

> O arquivo tem ~2-10 MB — transfere em segundos.

---

## 6. Rodar o worker

```bash
# Na VM Oracle:
export DATABASE_URL=sqlite:////home/ubuntu/leaklab.db
export SOLVER_BIN=/home/ubuntu/leaklab/backend/scripts/cloud/solver_cli
export MAX_EXPLOIT=1.0
export SOLVER_TIMEOUT=120

python3 /home/ubuntu/leaklab/backend/scripts/cloud/worker.py
```

**Output esperado:**
```
START total=123 spots  solver=./solver_cli  max_exploit=1.0%
OK   a1b2c3d4 bet exploit=0.41% (12s) [1/123]
OK   e5f6g7h8 check exploit=0.78% (9s) [2/123]
...
DONE solved=118 rejected=3 failed=2 time=23.4min
```

> Com 4 vCPUs ARM64 sem restrições: ~10-15s por spot vs ~40s no Windows.  
> 123 spots → ~20-30 minutos no total.

---

## 7. Copiar resultados de volta para o Windows

Após o worker terminar, o banco `leaklab.db` na VM terá os 100+ spots em `gto_nodes`.

**Copiar de volta:**
```bash
# No Windows (PowerShell ou Git Bash):
scp ubuntu@<IP_ORACLE>:/home/ubuntu/leaklab.db C:/Projetos/leaklab/backend/leaklab.db
```

> **Atenção**: isso sobrescreve o banco local. Se houver dados novos localmente (novos uploads/análises), faça merge manual ou use `sqlite3 .dump` + import seletivo.

---

## 8. (Opcional) Rodar como serviço systemd

Para rodar em background e reiniciar automaticamente:

```bash
# Na VM Oracle:
echo 'DATABASE_URL=sqlite:////home/ubuntu/leaklab.db' | sudo tee /etc/gto-worker.env
echo 'SOLVER_BIN=/home/ubuntu/leaklab/backend/scripts/cloud/solver_cli' | sudo tee -a /etc/gto-worker.env

sudo systemctl daemon-reload
sudo systemctl start gto-worker

# Acompanhar logs em tempo real:
sudo journalctl -u gto-worker -f
```

---

## 9. (Opcional) PostgreSQL em vez de SQLite

Se o projeto migrar para PostgreSQL (Render/Supabase):

```bash
export DATABASE_URL=postgresql://user:senha@host:5432/leaklab
python3 worker.py
```

O worker detecta o protocolo automaticamente e usa `psycopg2`.

---

## Troubleshooting

| Problema | Solução |
|---|---|
| `solver_cli: not found` | Rode `cargo build --release` em `backend/gto_bot/solver_cli/` |
| `database is locked` | Apenas um worker por vez com SQLite |
| Spots com `exploit > 1%` → `REJ` | Normal — solver não convergiu; aumente `max_iterations` no spot_json |
| Timeout | Aumente `SOLVER_TIMEOUT=300` para spots difíceis |
| SSH recusado | Verifique security list no Oracle Console (porta 22) |
| `psycopg2` não instalado | `pip3 install psycopg2-binary` |

---

## Estimativas de performance

| Ambiente | Tempo/spot | 123 spots |
|---|---|---|
| Windows foreground (local) | ~40s | ~82 min |
| Oracle Ampere A1 ARM64 4vCPU | ~10-15s | ~20-30 min |
| Oracle A1 com 4 workers paralelos* | ~3-5s | ~8-12 min |

*Para paralelismo, rode 4 instâncias do worker simultaneamente.  
O campo `status='running'` no banco previne double-processing.
