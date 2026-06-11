# Rollback do Solver — Baseline `solver-baseline-v1` (2026-06-11)

Estado de referência ANTES das otimizações do `specs/solver-improvement-plan.md`.

## O que compõe o baseline

| Item | Onde está | Status |
|---|---|---|
| Código completo (CLI Rust, server VM, cliente Python) | tag git `solver-baseline-v1` → commit `1998e78` | ✅ criada local — **rodar `git push origin solver-baseline-v1`** |
| Lib upstream `postflop-solver` (dev suspenso) | `backend/gto_bot/solver_cli/vendor/postflop-solver-9d1509f.tar.gz` (rev exato do Cargo.lock) | ✅ vendorizada no repo |
| Banco (gto_nodes, gto_solver_queue) | **NÃO salvo** — decisão: só dados de teste, reprocessável via re-upload + precompute scripts | ⏭️ pulado |
| Binário + flags da VM GCP | manual (passo abaixo) | ⚠️ pendente — fazer antes da Fase 2 |

## Flags de ambiente do baseline (backend `.env`)

```
TEXAS_HERO_IP=1
TEXAS_HERO_IP_FACING=1
```
(VM: `GTO_TIMEOUT=300`, `GW_AUTH_REFRESH=0` — conferir `/etc/systemd/system/leaklab-solver.service` e `.env` na VM.)

## Passo manual na VM (fazer UMA vez, antes de mexer na VM — Fase 2)

```bash
ssh <vm>
cd /opt/leaklab/backend/gto_bot/solver_cli/target/release
cp solver_cli solver_cli.baseline-20260611        # binário atual intocado
# As env vars da VM vivem no systemd unit (não há .env na VM):
sudo cp /etc/systemd/system/leaklab-solver.service /opt/leaklab/leaklab-solver.service.baseline-20260611
```
> ✅ Executado em 2026-06-11 (binário + unit).

## Como voltar ao estado atual (rollback completo)

1. **Código:** `git checkout solver-baseline-v1` (ou `git revert` dos commits novos para manter histórico).
2. **Binário VM:** `cp solver_cli.baseline-20260611 solver_cli && systemctl restart leaklab-solver` — ou rebuild: o `Cargo.lock` da tag pinna a lib no rev `9d1509f`; se o GitHub upstream sumir, extrair o tarball de `vendor/` e apontar o Cargo.toml com `path = `.
3. **Flags:** restaurar `.env` baseline (acima).
4. **Dados:** re-upload dos hand histories de teste + `scripts/precompute_*.py` + `reanalyze_all_labels.py` (decisão registrada: banco não é precioso).
5. **Validação de que o rollback funcionou:** suites `gto`, `engine`, `api` verdes + mão de referência `t=27 h=100000009` devolve turn `gto_mixed` (check 57%/bet 42%).

## Regra para as fases do plano

Toda migração de dados da Fase 1 (tree_hash/isomorfismo) deve ser **aditiva** (colunas/tabelas novas, nunca DROP/UPDATE destrutivo em `gto_nodes`) enquanto este baseline for o ponto de retorno.
