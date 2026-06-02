# Captura GTO — pipeline GTO Solver (GTO Wizard)

Como spots preflop são capturados do GTO Solver e viram range no master.
Detalhes em `gto_wizard_client.py`, `gto_bot/solver_api/server.py`,
`scripts/fetch_null_canonical.py`, `leaklab/preflop_autocapture.py`.

## Cadeia

```
backend → HTTP → leaklab-solver (GCP, /opt/leaklab, :8765)
   → CDP → Chrome logado em app.gtowizard.com → GW API
```

Consultas preflop são **grátis** no GW. O servidor navega a SPA pro spot e
intercepta o response da API.

## Contratos da captura (cada um quebrou nesta sessão)

1. **history_spot dinâmico** (INV-5): = nº de tokens de ação. Fixo errado → nó errado → no-solution falso.
2. **Depths válidos** (INV-4): `_GW_VALID_DEPTHS` reflete a árvore simétrica; **70bb não existe** (só 60/80). Snap pro mais próximo; `+0.125` no frac (ex.: 32 → 32.125).
3. **Sizing por bucket** (INV-6): 3bet/squeeze = **RAI** raso (≤20bb), **R6** fundo. Open canônico **R2** (2bb). `build_canonical_pf` tenta na ordem do bucket com fallback.
4. **pf canônico, não real**: o pf REAL da mão (sizings/sequência reais) **não casa** na árvore do GW → no-solution. Captura usa pf canônico por POSIÇÕES (seat order 9-max).
5. **fast-fail no-solution**: `fetch_timeout` curto + `snap_raises=False` → no-solution falha em ~9-15s e **não trava** as requisições seguintes (a "degradação" era no-solution pendurando 70-90s).
6. **cold-caller no faces_squeeze**: quando o hero deu cold-call ANTES do squeeze, anexar o fold do opener no wrap pra o hero ser o `hero_position` correto (senão keya sob o opener).

## O que o GW NÃO resolve (limites inerentes)

- **Pote limpado** (ninguém aumenta) — GW MTT assume raise-or-fold; só BB-vs-SB-complete existe.
- **Open/3bet off-tree** (ex.: open 3bb a 17bb) — só os sizings GTO existem; desvio do vilão = no-solution (INV-8 / backlog #23).
- **4-bet pot a stack raso** — a 30bb o 3bet já é shove; 4-bet pot só existe ~40bb+ (backlog #21).
- Multiway squeeze de depth/estrutura específicos.

## Auto-capture on-demand

`preflop_autocapture.run_autocapture(tournament_id)` roda no fim do `/analyze`:
detecta NULLs cobríveis, busca o canônico, injeta no master (escrita atômica),
re-grada por ordem. Tabela `gto_preflop_capture` evita re-buscar no-solution.

## Deploy (INV-7)

Serviço roda de **`/opt/leaklab`**. Deploy: `bash ~/leaklab/backend/scripts/deploy_gto_server.sh`
(pull em /opt + restart + smoke). `_gw_subprocess.py` é spawnado fresco (pega
mudança sem restart); `server.py` exige restart.
