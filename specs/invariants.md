# Invariantes — o que nunca pode quebrar

Cada invariante é um **contrato**: se quebrar, o sistema corrompe vereditos
**silenciosamente** (sem erro). Cada um é guardado por um teste em
[`backend/tests/test_invariants.py`](../backend/tests/test_invariants.py)
(suite `engine`). **Mudou o comportamento? Atualize o teste E este doc juntos.**

---

### INV-1 — Todo path que mostra recomendação preflop usa os MESMOS sinais de roteamento

`analyze_preflop` roteia o cenário a partir de `facing_raises`, `hero_was_aggressor`,
`is_3bet_pot`, `vs_position`, `facing_size`. **Omitir `facing_raises`/`hero_was_aggressor`
muda o roteamento** (ex.: `faces_squeeze` → `vs_rfi`) e gera veredito errado
(bug "call 54s vs squeeze").

- **Regra:** os 4 paths de display que recomputam (`/replay`, `/analyze` enriched,
  coach replay, GTO live override em `app.py`) DEVEM passar `facing_raises` (de
  `preflopRaisesFaced`) + `hero_was_aggressor` + `n_players`, igual ao `evaluate_decision`.
- **Por quê:** lógica duplicada divergiu — 14 spots `faces_squeeze` em 5 torneios
  mostraram "call" indevido. Vereditos armazenados estavam certos; só o display divergia.
- **Guarda:** `test_inv_faces_squeeze_routing`, `test_inv_squeeze_offrange_folds`.
- **Ideal futuro:** consolidar os 4 call sites em 1 helper (fonte única).

### INV-2 — `label` e `gto_label` são consistentes (sem `label_gto_conflict`)

O engine **reconcilia** o `label` heurístico a partir do `gto_label` quando há
cobertura GTO. **Nunca** pode existir decisão com `label ∈ {small_mistake, clear_mistake}`
E `gto_label ∈ {gto_correct, gto_mixed}` (ou o inverso).

- **Por quê:** o produto exibiria veredito contraditório (painel diz erro, GTO diz certo).
- **Quando muda a range:** rodar `resync_postflop_gto.py --street preflop --apply` +
  re-grade por ordem (fecha mãos ambíguas). Ver [`preflop-gto.md`](preflop-gto.md).
- **Guarda:** `test_inv_no_label_gto_conflict` (característico sobre o DB local).

### INV-3 — Sem cobertura → `gto_label` NULL (NULL honesto), nunca veredito fabricado

`analyze_preflop` retorna `available=False` quando não há range pro spot. O lookup
é **exact-only** (pareamento opener×3bettor exato) — proibido aplicar a range de um
3bettor/opener aleatório como aproximação.

- **Por quê:** veredito fabricado é pior que ausência — engana o jogador e o ELO.
- **Guarda:** `test_inv_null_honesty`.

### INV-4 — Depths válidos do GTO Solver não incluem 70bb

`_GW_VALID_DEPTHS` (server.py) reflete a árvore simétrica do GW MTT. **70bb NÃO existe**
(só 60 e 80). Um stack ~70bb deve snapar pro válido mais próximo (60/80), nunca pro 70.

- **Por quê:** snapar pro 70 inexistente → no-solution falso (escondeu spots de 75bb).
- **Guarda:** `test_inv_gw_valid_depths`.

### INV-5 — `history_spot` = nº de tokens de ação (todas as streets)

O `history_spot` que a SPA do GW navega = quantas ações ocorreram antes da decisão.
Fixo errado (era 7) → linhas de 8+ ações abrem o nó errado → no-solution falso.

- **Por quê:** foi o "teto artificial" de 91,7%. `query_gto_wizard_raw` calcula dinamicamente.
- **Guarda:** `test_inv_history_spot_dynamic`.

### INV-6 — Sizing de 3bet/squeeze é RAI em stack raso, R6 em fundo

Em stacks rasos (≤20bb) o 3bet/squeeze é **shove (RAI)**; em fundos, **raise (R6)**.
A construção canônica do pf tenta na ordem do bucket com fallback.

- **Por quê:** `R2-...-R6-F` a 10bb = no-solution; `R2-...-RAI-F` resolve (169 mãos).
- **Guarda:** `test_inv_3bet_sizing_order`.

### INV-7 — O serviço GTO roda de `/opt/leaklab`

`systemd leaklab-solver` tem `WorkingDirectory=/opt/leaklab/...`. Pulls em `~/leaklab`
**não chegam ao código vivo** (`~/leaklab` é symlink → `/opt/leaklab`). Deploy via
`deploy_gto_server.sh`.

- **Por quê:** causou "nenhum fix do servidor pega". Operacional, não testável em CI.

### INV-8 — Vereditos preflop são "cegos ao tamanho do open" (LIMITAÇÃO conhecida)

As ranges usam o sizing GTO canônico (ex.: open `R2`=2bb). Vs um open **off-tree**
(ex.: 3bb), o GW **não tem solução** — o engine snapa pro 2bb e aplica a defesa larga.
**Não marcar `gto_critical`** quando o open real diverge muito do canônico (backlog #23).

- **Por quê:** flagra folds corretos como erro crítico (ex.: fold 75o vs open 3bb).
- **Status:** documentado; mitigação pendente (não há captura possível — é inerente ao solver).

### INV-9 — `hero_won_hand` ∈ {1, 0, NULL}; Results×GTO conta só `gto_critical`

`hero_won_hand=1` sse o hero coletou o pote. O insight "ganhei mas errei" conta
decisões com `hero_won_hand=1 AND gto_label='gto_critical'`.

- **Guarda:** `test_detect_hand_won`, `test_results_vs_gto_endpoint` (suite `api`).

### INV-10 — `hand_freq` é a distribuição da AÇÃO DA MÃO, nunca None/tudo-zero quando `available`

Quando `analyze_preflop` devolve `available=True`, `hand_freq` é a distribuição
de ação da **carta específica do hero** (`{fold,call,raise,allin}`, soma ~1) — é o
que o Decision Card e o RangePanel mostram. Mãos **out-of-range** (sem entrada no
GW) devolviam `None` ou `{tudo-zero}` em vários paths (rfi, vs_rfi, faces_squeeze);
o frontend então caía no **% AGREGADO do range** (distribuição da posição, ex.:
"Fold 79,8% / Raise 12,7%") em vez do veredito da mão (Fold 100%). Normalizado num
só ponto na saída de `analyze_preflop`: sem distribuição válida ⇒ fold puro 100%.

- **Guarda:** `test_inv_hand_freq_distribution` (suite `engine`).
