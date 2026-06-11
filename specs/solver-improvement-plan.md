# Plano de Melhoria — Solver Texas Postflop

> Análise: jun/2026. Escopo: `solver_cli` (Rust), `solver_api/server.py` (VM GCP), `gto_solver.py` + fila no backend.
> **Nenhuma modificação foi feita** — este documento é o plano.

---

## 1. Diagnóstico — onde o tempo e o dinheiro vão hoje

### 1.1 O CFR **não** é single-thread — o pipeline é

O `solver_cli` usa `postflop-solver` com a feature `rayon` ligada (`Cargo.toml`): o solve em si já paraleliza nos 4 vCPUs da VM. O que é serial é tudo em volta:

| Camada | Problema | Arquivo |
|---|---|---|
| VM HTTP | `HTTPServer` puro (1 thread). Um solve de 2–4 min bloqueia `/health`, `/gw-spot` e qualquer outro solve | `server.py:1346` |
| Worker backend | Loop de **polling a cada 60s**, processa até 5 jobs **sequencialmente**, cada um bloqueando em HTTP até 240s | `app.py:7166`, `gto_solver.py:611` |
| Sem fila na VM | Requests concorrentes empilham no backlog TCP sem controle, sem visibilidade, sem prioridade | `server.py` |

Efeito: throughput ≈ 1 solve por vez ponta a ponta, e latência mínima de ~60s até para um river que resolve em 1s.

### 1.2 O desperdício dominante: resolver a MESMA árvore várias vezes

Dois problemas independentes que se multiplicam:

**(a) `spot_hash` inclui a mão do hero** (`gto_utils.py:132`) — mas o input do solver é só `board + ranges + stack + facing`. A mão do hero **não entra no solve**. Resultado: o mesmo jogo (mesmo board, mesmas ranges, mesmo stack) é re-resolvido para cada mão diferente que o hero teve naquele tipo de spot. Paga-se a fragmentação por mão **sem ganhar** estratégia por mão.

**(b) Sem isomorfismo de naipes.** `As Kd 2c` e `Ah Kc 2d` são o mesmo jogo estrategicamente. Há 22.100 flops brutos, mas só **1.755 classes isomórficas** (~12,6×). Os precomputes (`precompute_3bet_pots.py`, `precompute_ip_facing_bet.py`) e o cache de nós pagam essa redundância inteira.

[Provável] Combinados, (a)+(b) reduzem o volume de solves necessários em **5–20×** dependendo da distribuição real dos spots. É o maior ganho disponível, custa zero hardware, e ataca exatamente a queixa de consumo do servidor.

### 1.3 Qualidade: o veredito GTO é da RANGE, não da MÃO

`main.rs` agrega a estratégia ponderada da range inteira; `_gto_classify_from_strategy` (decision_engine) compara a ação do hero com essas frequências agregadas. Mas num board K72r a range checa 60% **enquanto AA aposta 90%** — o veredito correto é por mão. A lib já devolve `strategy[hand_idx + action_idx * num_hands]` por combo; o CLI **já tem o array** e joga a granularidade fora. O backend já manda `hero_hand` no `_meta` — só não chega ao CLI.

### 1.4 Achados menores

- `iterations` na saída **mente**: retorna `inp.max_iterations`, não as iterações reais executadas (`main.rs:292`).
- `solve()` no `server.py` cria temp file para alimentar stdin — `subprocess.run(input=...)` elimina I/O em disco.
- `turn_donk_sizes`/`river_donk_sizes = None`: linhas de **donk bet não existem na árvore** — spot do hero donkando cai em navegação falha/heurístico silenciosamente.
- 1 bet size por street (50/75/75%) é a escolha certa para flop deep (RAM), mas **desnecessariamente pobre no river/short-stack**, onde a árvore é minúscula — e o produto agora tem análise de sizing que se beneficiaria de 2–3 sizes.
- Compressão 16-bit só ativa acima de 1 GB; usá-la sempre dobra a folga de RAM com perda de precisão irrelevante para targets de 2–3%.
- Upstream `b-inary/postflop-solver` está com **desenvolvimento suspenso** — risco de dependência via `git` no Cargo.toml (sem pin de commit, build não-reprodutível se o repo sumir).
- VM 24/7 (4 vCPU/16 GB) acumula Chrome+Playwright (scraping GW) e solver no mesmo host — workloads com perfis opostos competindo por RAM, e custo fixo mesmo com fila vazia.

---

## 2. Plano — fases priorizadas por ganho/esforço

### Fase 0 — Correções triviais (½ dia, risco zero)

1. Reportar iterações reais do CFR (a lib retorna; hoje ecoa o input).
2. `server.py::solve` e `_call_solver`: stdin direto, sem temp file.
3. Pin de commit do `postflop-solver` no `Cargo.toml` (reprodutibilidade) e fork vendorizado no GitHub da org (proteção contra remoção do upstream).

**Validação:** rebuild + suite `gto` 229/229 + diff byte a byte de um solve de referência.

### Fase 1 — Eliminar solves redundantes (o maior ganho)

**1a. Separar `tree_hash` de `spot_hash`.**
Novo hash canônico **sem `hero_hand`** = identidade da árvore. O `spot_hash` legado continua existindo como chave de leitura (zero quebra nos read paths); nova coluna/tabela mapeia `spot_hash → tree_hash`. Fila deduplica por `tree_hash`; `gto_nodes` armazena por `tree_hash`. Mesmo padrão backward-compat já usado no `pot_type` (omissão preserva hash legado).

**1b. Canonicalização isomórfica de naipes.**
Antes de hashear/solvar: permutar naipes do board para forma canônica (ex.: ordem lexicográfica de primeira ocorrência) e aplicar a MESMA permutação às ranges (ranges em notação `AKs/AKo` são invariantes a permutação — só o board e combos específicos mudam). Na leitura, aplicar a permutação inversa à mão do hero antes de indexar. Guardar a permutação junto ao nó.

**Migração:** script único re-keya `gto_nodes` existentes (computa tree_hash canônico de cada nó, funde duplicatas mantendo o de menor exploitability) + teste de regressão garantindo que a mão de referência (`t=27 h=100000009`) devolve o mesmo veredito.

**Impacto estimado:** [Provável] 5–20× menos solves para a mesma cobertura; cache hit imediato em spots "novos" que são isomorfos de nós existentes — cobertura postflop percebida sobe sem rodar o solver.
**Esforço:** ~3–4 dias. **Risco principal:** erro na permutação inversa ao ler a mão do hero — coberto por teste property-based (solve de um board + solve do isomorfo ⇒ estratégias idênticas após mapeamento).

### Fase 2 — Concorrência e latência do pipeline

**2a. VM:** trocar `HTTPServer` → `ThreadingHTTPServer` + semáforo `MAX_CONCURRENT_SOLVES` (começar com 2) + `RAYON_NUM_THREADS=2` por processo (2×2 = 4 vCPUs, sem oversubscription). `/health` e `/gw-spot` deixam de ser bloqueados por solve em andamento — isso também corrige o sintoma "GW degraded pendura tudo 20s" já visto.

**2b. Roteamento por classe de tamanho:** o custo de um solve varia ~3 ordens de magnitude (river short-stack <1s; flop 60bb minutos). Usar `memory_usage()`/street/stack para rotear: spots pequenos resolvem **síncronos** na hora do upload (o `is_simple_spot` já existe, está subaproveitado); só árvore grande vai à fila. Dentro da fila, prioridade por custo estimado (rivers furam fila) — hoje a prioridade é só por street.

**2c. Backend worker:** substituir o tick fixo de 60s por **event-driven** (ao enfileirar, aciona o worker via `threading.Event`; mantém tick de 60s como fallback). Latência média da fila cai de ~30s+ para ~0 com fila vazia.

**Impacto:** [Provável] 2–3× throughput em fila cheia; latência percebida pelo usuário no replayer cai de minutos para segundos nos spots pequenos.
**Esforço:** ~2–3 dias. **Validação:** teste de carga com 20 spots mistos; medir p50/p95 de fila antes/depois.

### Fase 3 — Funcionalidades novas (mesma infra, produto melhor)

**3a. Estratégia POR MÃO do hero** — o upgrade pedagógico mais barato que existe aqui. CLI aceita `hero_hand` opcional → devolve, além do agregado, `hand_strategy` (frequências da mão específica) e `hand_ev`. O veredito (`_gto_classify`) passa a usar a frequência **da mão**, não da range. Custo computacional: ~zero (o array já está em memória). Sinergia com a Fase 1: a árvore é compartilhada entre mãos; só a leitura é por mão.

**3b. EV loss quantificado** — "este fold custou 0,8bb": navegar cada ação disponível (`play(i)` → `expected_values` → back) e devolver `ev_by_action`. O card mostra o custo em bb, não só "desvio crítico". Transforma a Margem/Custo atual (equity-based) em EV real de solver.

**3c. Bet sizes adaptativos por tamanho de árvore** — se `memory_usage()` estimado < limiar (river, turn short-stack): árvore com 3 sizes (33/66/125%) + donk sizes habilitados. Flop deep mantém 1 size. A análise de sizing (Fases 1–3 do sizing_advisor) ganha comparação real contra menu de sizes em vez de um size único.

**3d. Donk bets** — habilitar `turn_donk_sizes`/`river_donk_sizes` quando a linha do spot é donk (o hand_state_builder sabe). Fecha mais um buraco de cobertura "sem nó".

**3e. 4-bet pots** — pendência declarada no CHANGELOG (1% dos spots, hoje aproximação SRP). Mesma mecânica da Fase 2 do solver de 3-bet (range do 4-bettor = `raise_hands` vs 3-bet; caller = call vs 4-bet). Baixa prioridade pelo volume, mas o padrão já existe.

**Esforço:** 3a+3b ~2–3 dias; 3c+3d ~2 dias; 3e ~2 dias.

### Fase 4 — Custo de servidor

1. **Compressão 16-bit sempre** (ou limiar 256 MB): dobra a folga de RAM → ou sobe o cap de 60bb para ~80–100bb (menos "≈ Aproximação"), ou permite 2 solves grandes simultâneos.
2. **VM Spot/preemptível** para o solver: 60–91% de desconto no GCP; a fila já é resiliente a morte do worker (reset de `running` >10min em `app.py:7176`). Requer só systemd `Restart=always` + a Fase 2a.
3. **Separar scraping GW do solver**: o Chrome+Playwright é o motivo de a VM precisar ser 24/7 e ter 16 GB. Solver numa instância spot dedicada; Chrome numa e2-small. [Suposição] corte de ~40–60% do custo mensal total da VM — validar com a fatura atual.
4. **Precompute em burst**: para campanhas (ex.: re-solve pós Fase 1), Cloud Run jobs com 8 vCPU sob demanda em vez de deixar a fila escoando dias na VM pequena.

### Fase 5 — (Opcional, visão de futuro) Multiway postflop

A lib só resolve heads-up — limitação estrutural, não bug. Multiway CFR existe mas explode em RAM/tempo e nenhuma lib open-source madura cobre bem. Recomendação: **não** investir agora; o caminho honesto atual (heurístico sinalizado) está correto. Reavaliar quando 1.755 classes isomórficas de flop estiverem pré-computadas e sobrar capacidade.

---

## 3. Ordem recomendada e dependências

```
Fase 0 (½d) → Fase 1 (3-4d) → Fase 2 (2-3d) → Fase 3a/3b (2-3d) → Fase 4 (1-2d) → 3c/3d/3e
                   ↑ maior ROI                      ↑ maior valor pro aluno
```

Fase 1 antes da Fase 2: não adianta paralelizar solves que não deveriam acontecer. Fase 3a depende da Fase 1 (leitura por mão sobre árvore compartilhada). Fase 4 depende da 2a (VM precisa sobreviver a preempção com fila controlada).

## 4. Métricas de sucesso (medir antes e depois de cada fase)

- **Solves/dia** necessários para cobertura X (deve CAIR ~10× na Fase 1)
- **p50/p95 de espera na fila** (Fase 2: de minutos para segundos)
- **% cobertura GTO postflop** por torneio (deve SUBIR sem custo extra na Fase 1)
- **Custo mensal GCP** (Fase 4: meta −50%)
- **Exploitability mediana** dos nós (não pode piorar: hoje 1,35%)
- Suites: gto 229/229, engine 362/362, api 42/42 verdes em toda fase

## 5. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Re-key de hashes quebra read paths | `spot_hash` legado mantido como chave de leitura; mapeamento `spot_hash→tree_hash`; padrão pot_type já validado |
| Permutação isomórfica errada inverte naipes da mão | Teste property-based: solve(board) ≡ solve(isomorfo) após mapear |
| Oversubscription rayon (2 solves × 4 threads em 4 vCPUs) | `RAYON_NUM_THREADS=2` por processo, medir |
| Veredito por mão muda labels históricos em massa | Rodar `reanalyze_all_labels.py` (fluxo já existente) + comparar distribuição antes/depois |
| VM spot é preemptada no meio de solve | Fila já re-enfileira `running` órfão; perda máxima = 1 solve |
| Upstream da lib desaparece | Fork vendorizado + pin de commit (Fase 0) |
