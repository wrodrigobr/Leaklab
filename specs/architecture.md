# Arquitetura — subsistemas e fluxo de dados

Visão de **fronteiras e contratos** entre subsistemas. Detalhe de arquivos está em `CLAUDE.md`.

## Fluxo principal (upload → veredito)

```
hand history (texto)
   │  parser.py            → ParsedHand (hero, ações, board, raw_text)
   ▼
pipeline.py                → decision inputs (di): 1 por decisão do hero
   │   cada di tem spot{position, vs, effectiveStackBb, facingSize,
   │   preflopRaisesFaced, heroWasAggressor, nPlayers, ...}
   ▼
decision_engine_v11.evaluate_decision(di)
   │   ├─ math/equity (equity, pot odds, draws)
   │   ├─ preflop_gto_ranges.analyze_preflop(...)   ← veredito GTO preflop
   │   └─ gto_nodes / GW (postflop)                  ← veredito GTO postflop
   ▼
repositories.save_decisions(...)   → tabela `decisions` (label, gto_label, gto_action, ...)
   ▼
produto serve o veredito ARMAZENADO (dashboard, replayer, ELO, leaks)
```

**Contrato-chave:** o veredito **armazenado** é a fonte de verdade que o produto
exibe. Qualquer path que **recompute** o veredito para display (replayer, etc.)
DEVE produzir o mesmo resultado que `evaluate_decision` produziu ao salvar
(ver [INV-1](invariants.md)).

## Subsistema GTO preflop (range-backed)

- **Fonte:** `backend/docs/leaklab_gto_ranges.json` (master), carregado em memória por `_load()`.
- **Captura:** spots vêm do **GTO Solver** (GTO Wizard) via o servidor GCP — ver [`gto-capture.md`](gto-capture.md).
- **Lookup:** `analyze_preflop()` roteia o spot para um cenário e busca a range — ver [`preflop-gto.md`](preflop-gto.md).
- **Auto-capture:** `preflop_autocapture.py` fecha NULLs cobríveis on-demand a cada upload.

## Subsistema GTO postflop

- **Fonte:** `gto_nodes` (solver local) + fallback ao GTO Solver (fila `wizard_pending`).
- Servido pelos workers em background do `app.py`.

## Servidor GTO (GCP)

- VM `leaklab-gto`; serviço systemd `leaklab-solver` rodando de **`/opt/leaklab`** (NÃO `~/leaklab`).
- Cadeia: backend → HTTP → solver_api (`server.py`) → CDP → Chrome logado no GTO Wizard.
- Deploy: `bash ~/leaklab/backend/scripts/deploy_gto_server.sh` (ver [INV-7](invariants.md)).

## Indicadores derivados (computados das decisões)

- **ELO** (`elo_engine.py`) — snapshotado em `player_elo_history`, recalculado por upload.
- **Leaks / aderência / Results×GTO** — computados on-read das decisões armazenadas.
- Como **derivam** das decisões, quando a range muda é preciso **reconciliar as
  decisões** (resync) e recalcular os snapshots (ELO). Ver [INV-2](invariants.md).

## Frontend

- React SPA (`/`, `/replayer`, `/docs`, admin). Em dev chama o backend **direto na :5000**
  (`BASE` no `api.ts`), não via proxy. CORS `*` em dev.
- Replayer: `src/pages/Replayer.tsx` (rota `/replayer`) + standalone `leaklab-replayer-v3.html`.
