# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Unreleased]

---

## [v0.99.3] — 2026-05-15 — feat(GTO-005/006): estimated_equity no banco + validação GTO 98-100% + threshold draw fix

### Added
- **`database/schema.py`**: coluna `estimated_equity REAL` adicionada à tabela `decisions` — migrations automáticas para SQLite e PostgreSQL
- **`database/repositories.py`**: `estimated_equity` incluído no INSERT de decisões (via `math.estimatedHandEquity` do pipeline)
- **`scripts/reeval_postflop.py`**: novo script de re-avaliação postflop — detecta draws fracos (equity_adj < 0.15) e draws fortes com equity insuficiente dado posição/stack, converte `best_action='bet'→'check'` em lote com `--dry-run` para preview

### Fixed
- **`postflop_range_evaluator.py`**: semi-bluff threshold `equity_adj >= 0.10` → `>= 0.15`. GUT+BDFD (0.14) e BDFD+BDSD (0.10) não justificam bet — confirmado por validação GTO Wizard (98% flop, 100% turn/river)
- **`scripts/gto_validation/playwright_compare.py`**: interceptor de headers registrado ANTES de `page.goto` — evitava race condition onde a página recarregava antes de capturar DPoP token; action format `B{size}` → `R{size}` (API GTO Wizard aceita apenas R, não B); parser `next-actions` corrigido para path real `next_actions.available_actions[].action.betsize`
- **`scripts/gto_validation/analyze_results.py`**: output reformatado para mostrar distribuição completa GTO (`check^82%  bet 18%<nós` em vez de `our=bet(18%)`); adicionado breakdown de erros por tipo; encoding UTF-8 no Windows

### Tests
- **`tests/test_postflop_evaluator.py`**: testes atualizados para threshold 0.15 — GUT+BDFD agora espera `check`, FD e OESD ainda esperam `bet`

---

## [v0.99.2] — 2026-05-13 — fix(AUD-001): guard fold→check restrito a BB — corrige regressão em 577 spots

### Fixed
- **`preflop_range_evaluator.py`**: `_recommended_action` retorna `'check'` apenas quando `position == 'BB'` e `facing_size == 0`. Demais posições (UTG/HJ/CO/BTN/SB) retornam `'fold'` para mãos fracas sem aposta — comportamento correto (escolha de não abrir)
- **`preflop_range_evaluator.py`**: filtro de `alternatives` também restrito a `BB` — outros posições podem ter `'fold'` como alternativa em borderline spots sem aposta
- **`decision_engine_v11.py`**: guard final `facingSize=0 → check` adicionado `and spot.get('position') == 'BB'`. Antes afetava 577 decisões de non-BB incorretamente
- **`api/app.py`** (`player_drill_submit`): guard serve-time restrito a `position == 'BB'`
- **`database/repositories.py`** (`get_sparring_hand`): guard serve-time restrito a `position == 'BB'`

### Data Migration
- **Phase 2 DB fix**: 20 decisões `BB + facing_bet IS NULL + best_action='fold'` atualizadas: `best_action → 'check'`. 13 dessas (action_taken='check') também tiveram `score → 0.02, label → 'standard'` (eram small_mistake/marginal por engano)

### Tests
- **`test_evaluators.py`**: 27 testes reescritos para comportamento correto por posição — BB check, non-BB fold para mãos fracas sem aposta
- **`test_postflop_evaluator.py`**: `test_preflop_unaffected` agora verifica range zones do postflop evaluator (não presença de 'check'), já que BB legítimamente retorna 'check' preflop

---

## [v0.99.1] — 2026-05-13 — fix(GTO-004): unidades facing_size_bb e threshold is_simple_spot

### Fixed
- **`api/app.py`**: revert `facing_size_bb` para `decision.get("facing_bet")` (BBs do DB). Estava usando `_spot.get("facingSize")` que retorna chips — `bet_bucket(6400)="40bb+"` em vez do correto `bet_bucket(1.0)="0-3bb"`, causando hash de lookup completamente errado
- **`gto_solver.py`**: `is_simple_spot` threshold `stack_bb <= 20` → `<= 25` para cobrir stacks de ~20bb, comuns em MTT. Stack de 20.1bb antes causava resolução assíncrona que nunca retornava ao frontend
- **`Replayer.tsx`**: indicador "⏳ Calculando…" exibido quando `gto_label` existe mas `stratSorted` ainda está vazio (solver ainda processando) — evita silêncio confuso para o usuário

---

## [v0.99.0] — 2026-05-13 — feat(GTO-009): solver_cli facing_size_bb + deploy VM — estratégia completa por nó de decisão

### Added
- **`solver_cli` (`main.rs`)**: novo campo opcional `facing_size_bb` (padrão 0.0). Quando > 0, após resolver o game tree completo, navega internamente para o nó onde OOP enfrenta a aposta do IP (`OOP check → IP bet closest_to(facing_size_bb) → OOP to act`) e retorna a estratégia de resposta (fold/call/raise/allin com frequências). Campo `facing_node: bool` na saída indica se a navegação foi bem-sucedida
- **`gto_solver.py`**: `solver_payload` agora inclui `facing_size_bb` → worker da fila e chamadas síncronas passam o campo automaticamente ao binary
- **Nós turn/river populados** para mão t=3910307458 h=257048692293 com estratégia completa: turn fold 55% / call 30% / raise 15%; river fold 56% / call 33% / raise 8% / allin 2%
- **Frontend** (`Replayer.tsx`): barras de frequência agora aparecem com qualquer número de ações (`>= 1` em vez de `>= 2`); `topFreqPct` inline removido da coluna "GTO recomenda" (frequência já visível nas barras)

### Technical
- Navegação no game tree: `navigate_to_facing_bet()` busca `Action::Check` no root (OOP) e depois o `Action::Bet/Raise/AllIn` mais próximo de `facing_chips` no nó IP; `game.back_to_root()` se o nó não existir
- Pot de referência para labels de resposta: `pot_chips + facing_chips` (mais preciso para raise percentages)
- Flop ainda sem multi-action strategy no servidor de teste (1 core/1GB): árvore de 3 streets excede 120s; produção (4 vCPU) suporta

---

## [v0.98.7] — 2026-05-12 — fix(UX-021): engine não penaliza BB check em pot não contestado

### Fixed
- **`decision_engine_v11.py`**: BB + preflop + check + facingSize=0 retorna imediatamente `label="standard"`, `bestAction="check"` sem calcular penalidades. Resultado no frontend: `is_error=false`, card mostra `✓ Correto` (ou não aparece se não há dados adicionais) em vez de `✗ Erro / Ideal: Fold`
- O fix de `preflop_gto_ranges.py` (v0.98.6) só eliminava o range analysis; a engine ainda calculava um erro independente baseado no `range_evaluation.recommendedPrimaryAction="fold"`

---

## [v0.98.6] — 2026-05-12 — fix(UX-020): BB free play não gera análise de range preflop

### Fixed
- **BB check em pot não contestado**: `analyze_preflop` retornava `available=True` com `action_quality="acceptable"` e nota "Fold correto" quando o BB simplesmente checkava seu free play. Corrigido: BB + scenario `rfi` + `action_taken="check"` retorna `available=False` imediatamente — painel de análise não aparece
- **`_rfi_notes` default incorreto**: o else que gerava "Fold correto" disparava para qualquer ação não-raise/jam fora do range (incluindo check/call). Corrigido para verificar explicitamente `act == 'fold'` antes de emitir essa nota

---

## [v0.98.5] — 2026-05-12 — feat(UX-019): DecisionCard unificado no /replayer React

### Changed
- **Painel lateral do Replayer React**: três seções separadas (Análise técnica, Preflop Range GTO, GTO Analysis) substituídas por um único `DecisionCard` por ação do hero
- **Hierarquia de veredito**: GTO Solver > Range preflop > Engine — `[GTO Solver]` / `[Range]` / `[Análise]` exibidos como tag discreta no banner, resolvendo ambiguidade de qual fonte priorizar
- **Banner unificado**: colorido por severidade (emerald/sky/amber/red), ícone + label em português sem jargão técnico ("Desvio Crítico" em vez de "gto_critical", "Leak Grave" em vez de "major_leak")
- **Comparação de ações**: "Você jogou / GTO recomenda" em 1 ou 2 colunas conforme discrepância; frequência top inline quando `gto_strategy` disponível
- **Barras de frequência do solver**: integradas no mesmo card, ação do jogador marcada com `←` em âmbar; EV diff `−0.18 BB vs ótimo` exibido quando `ev_bb` disponível
- **Rodapé contextual compacto**: M-ratio + ICM como grid 2 colunas, visível só quando campos presentes
- **Conflito engine vs GTO**: substituiu caixa âmbar separada por 1 linha footnote discreta (`Engine → FOLD / Solver → CHECK — priorizando GTO`)
- **Removido**: score breakdown (`math_penalty`, `range_penalty`, `context_penalty`) — debug output, não coaching; `error_score` com 3 casas decimais; palavra "Heurística" completamente eliminada da UI

---

## [v0.98.4] — 2026-05-12 — feat(UX-018): novo design de painéis no /replayer React

### Changed
- **Preflop Range GTO panel**: header banner colorido (ok/leak/grave) + badges em linha (in_range, hand_type, stack+bucket) + barra de range% com progress bar; remove layout de 2 colunas com ícone solto
- **GTO Analysis panel**: substitui grid de cards por barras horizontais de frequência — sorted desc, player action marcada com `←` em âmbar; verdict banner no topo (ok/mixed/bad) com background colorido por label; fallback para `gto_action` sem strategy preservado
- `isPlayedAction`: lógica de match flexível (prefixo bidirecional) para `bet_50pct`, `allin`, etc.

---

## [v0.98.3] — 2026-05-12 — feat(GTO-008): Replayer standalone com dados reais da API

### Added
- **Carregamento real de dados**: replayer lê `?t=<tournament_id>&h=<hand_id>` da URL, busca `ll_token` do `sessionStorage`, e chama `/replay/<t>/<h>` (ou `/coach/student/<student>/replay/<t>/<h>` com `?student=`)
- **Loading overlay**: spinner enquanto busca a API; sem travar a UI
- **Error overlay**: exibe mensagem de erro + botão "Carregar demo" como fallback
- **Fallback demo**: sem params → DEMO data (comportamento anterior preservado)
- **Vite multi-page build**: `leaklab-replayer-v3.html` adicionado como entry point do rollup → copiado para `dist/` no build de produção
- **Vercel**: rewrite explícito para `/leaklab-replayer-v3.html` antes do catch-all → servido como arquivo estático em produção

---

## [v0.98.2] — 2026-05-12 — feat(GTO-007): painel lateral no Replayer — heurística + GTO

### Added
- **Painel lateral direito** no Replayer standalone (`leaklab-replayer-v3.html`): aparece em toda ação do herói, desliza com `transition: width .25s ease`
- **Heuristic Card**: pré-flop mostra scenario/in-range/quality badges + range% + ações recomendadas; pós-flop mostra equity bar, pot odds, draw profile badge, M-ratio e ICM pressure
- **GTO Card**: verdict banner colorido (ok/mixed/bad), GTO rec vs ação do jogador, EV diff, barras de frequência de estratégia com marcação `←` na ação do jogador
- Funções JS: `gtoActionLabel`, `gtoVerdictClass`, `gtoVerdictText`, `isPlayerAct`, `stratFillClass`, `stratLblClass`, `rpRenderGtoCard`, `rpRenderHeuristicCard`, `rpRenderSidePanel`
- Demo data atualizado para exibir os dois cards sem API real

---

## [v0.98.1] — 2026-05-12 — fix(GTO-006): endpoint /decisions/<id>/gto — board truncation + hash fallbacks

### Fixed
- **Board truncation**: decisions table stores full board (4+ cards); endpoint now slices to street-appropriate length before hashing (flop→3, turn→4, river→5)
- **`hero_hand` guard removed**: endpoint previously returned 404 when hero_cards was empty (most decisions); now hero_hand is optional
- **`facing_bb` missing from hash**: `compute_spot_hash` call was missing the `facing_size_bb` arg — now passed correctly
- **Multi-step hash fallback**: endpoint tries 4 strategies in order — exact (hero_hand+facing), generic (no hand+facing), generic_nf (no facing), `get_gto_node_by_spot` (old hash scheme for legacy nodes)
- **Stored gto_action fallback**: if no node found at all but decision has `gto_label`/`gto_action` stored by worker, returns a synthetic single-action strategy so GTO panel always shows something
- **`get_decision_spot`**: added `gto_action` and `gto_label` to SELECT query
- **Hero card parsing**: handles both space-separated ("Jc Th") and concatenated ("JcTh") formats
- Result: 11/11 labeled decisions now return `found=True` with strategy (was 0/11)

---

## [v0.98.0] — 2026-05-12 — feat(GTO-004/005): GTO panel redesign + fixes chips→BB + solver stuck

### Added
- **GTO Panel redesign** (3 layers): Verdict banner (green/amber/red por `player_action_freq`), Full Strategy bars com barra da ação do jogador marcada (`←`), Context collapsível (position, street, stack, facing, exploitability)
- **`GtoStrategyAction` interface** em `api.ts`; `GtoDecisionResult` expandido com `strategy[]`, `player_action_freq`, `player_action_label`, `gto_action_label`, `ev_diff`, `exploitability_pct`
- **i18n**: novas chaves `gto.verdict.*`, `gto.ctx.*`, `gto.youPlayedLabel`, `gto.evDiffLabel`, `gto.exploitability`, `gto.strategyLabel`, `gto.contextLabel` nos 3 locales (PT/EN/ES)

### Fixed
- **GTO-004 chips→BB**: `facing_size_bb` em 3 locais do `app.py` usava `spot.get('facingSize')` (chips raw) em vez de `db_dec.get('facing_bet')` (BB normalizado da tabela `decisions`) — hashes errados corrigidos
- **GTO-005 solver stuck**: `hash_no_facing` fallback retornava nós sem aposta quando hero enfrentava bet → removido; nós corrompidos (`gto_action=NULL`) voltavam `found=True` com `strategy=[]` → fallback para enqueue corrigido
- **Endpoint `/player/decisions/<id>/gto`** reescrito: retorna `strategy` completa do nó, `player_action_freq` (fuzzy match), `ev_diff`, `exploitability_pct`, labels human-readable
- **`get_decision_spot`** em `repositories.py`: adicionado `facing_bet` ao SELECT

---

## [v0.97.0] — 2026-05-11 — feat(UX-020): stacks BB com precisão decimal + C-bet real no HUD

### Changed
- **Stacks sem arredondamento** (`PokerTableV3`): `fmtAmt` agora exibe 1 decimal quando necessário (`1.8 BB`), inteiros sem decimal (`4 BB`), espaço antes de "BB"
- **C-Bet substituiu Flop Bet** no HUD principal e em `StudentDetail`: indicador passa a medir apenas bets no flop como agressor pré-flop (denominator = oportunidades de c-bet, não total de decisões no flop)

### Fixed
- Backend `get_player_stats`: nova query SQL calcula `cbet_pct` via subquery que filtra hands onde hero raised/jammed preflop e viu o flop; campo `flop_bet_pct` removido
- Interface `PlayerStatsResponse` e `PlayerStats` atualizadas para `cbet_pct`

---

## [v0.96.0] — 2026-05-10 — feat(range-panel): contexto GTO integrado no painel de ranges

### Added
- **Banner de contexto GTO** no RangePanel: quando a mão é do hero, exibe:
  - Cenário detectado (RFI / vs Open / vs 3-Bet)
  - Badge in-range/fora do range com ícone e cor (verde/âmbar)
  - Quality badge: Correto / Aceitável / Leak / Leak grave
  - Ação recomendada pelo GTO e % do range
- **Seção "Análise GTO"** abaixo do grid: exibe as `pro_notes` da engine como bullet points explicativos
- **Auto-seleção de tab**: o tab correto (Open / Call / 3-Bet) é selecionado automaticamente com base no `scenario` da decisão (`rfi`→Open, `vs_rfi`→Call, `vs_3bet`→3-Bet)
- **vs_RFI usa opener correto**: quando disponível, usa `vs_position` do preflop_gto para selecionar o opener certo no JSON

---

## [v0.95.0] — 2026-05-10 — feat(range-panel): ranges dinâmicos do JSON por posição e stack depth

### Added
- **`GET /preflop-ranges`** — novo endpoint que serve ranges GTO preflop do `leaklab_gto_ranges.json` por posição e stack depth:
  - Parâmetros: `position` (ex: BTN) e `stack_bb` (float)
  - Retorna: `rfi` (mãos expandidas + %), `vs_rfi` (por opener), `vs_3bet` (4bet/call separados)
  - Stack bucket resolvido automaticamente pelo `_stack_bucket()` existente
  - Posições normalizadas via `_norm_pos()` (suporta UTG+1, MP1, etc.)

### Changed
- **`frontend/src/components/replayer/RangePanel.tsx`** — painel de ranges agora consome o endpoint `/preflop-ranges` em vez dos dados estáticos de `ranges.ts`:
  - Usa `step.hero_stack_bb` como stack depth da mão atual (coerente com a análise)
  - Mostra indicador de loading (`Loader2`) enquanto aguarda a API
  - Exibe `stack_bucket` no header para confirmação visual (ex: `50bb`)
  - Fallback automático para dados estáticos de `ranges.ts` se a API falhar
  - Label e description dinâmicos com % do range por stack depth
  - vs_RFI usa primeiro opener disponível no JSON para a posição selecionada

---

## [v0.94.0] — 2026-05-10 — feat(engine): preflop GTO range integrado no decision_engine

### Changed
- **`backend/leaklab/decision_engine_v11.py`** — `evaluate_decision()` agora aplica range GTO preflop após scoring de equity:
  - `_enrich_preflop_gto()`: chama `analyze_preflop()` para cada decisão preflop com posição, stack e cenário (RFI/vs RFI/vs 3bet)
  - `_preflop_gto_label_adjust()`: matriz completa de ajuste de label por `action_quality`:
    - `correct` → sempre `standard` (GTO confirma a ação do jogador)
    - `acceptable` → cap em `marginal` (subótimo mas defensável)
    - `leak` / `major_leak` → floor em `small_mistake` (não capeia `clear_mistake` para baixo)
  - `_best_action` sobrescrito com `recommended_actions[0]` do range quando GTO disponível
  - `preflop_gto` adicionado ao dict de retorno de `evaluate_decision()`

### Fixed
- Decisões preflop historicamente avaliadas só por equity threshold agora recebem classificação baseada em ranges GTO por posição e stack depth
- `bestAction` para preflop agora reflete a ação GTO recomendada, não apenas a heurística de equity

### Tests
- 32 testes existentes do engine: todos passando (sem regressão)
- 8 novos cenários preflop validados: `correct`, `acceptable`, `leak`, `major_leak` × RFI e vs_rfi

---

## [v0.93.0] — 2026-05-10 — feat(LLM-002): prompt de análise v2 — ICM como multiplicador, reverse implied odds e síntese de padrões

### Changed
- **`backend/leaklab/llm_explainer.py`** — `_build_payload()` e `system_prompt` completamente reescritos:
  - **ICM como multiplicador matemático**: equity mínima = pot odds × fator (×1.00 low / ×1.15 medium / ×1.30 high / ×1.50 bubble) — calculado em Python antes de enviar ao LLM, não estimado pelo modelo
  - **Reverse implied odds**: tier low/medium/high → subtrai 0/3/6pp da equity estimada; déficit final = equity mínima ICM − equity real ajustada
  - **Filtro M-Ratio obrigatório**: M<6 = push/fold puro (ações inválidas sinalizadas), M 6-12 = zona de pressão, M>12 = jogo normal; lógica integrada na construção do input
  - **Rastreamento de padrões recorrentes**: `error_pattern_tracker` conta ocorrências por tipo de erro na sessão; nota automática quando mesmo leak aparece N vezes
  - **BLOCO 4 — Síntese Final obrigatória**: Relatório de Padrões ao final de cada análise (leak dominante, stack depth crítico, padrão posicional, ICM sensibilidade, top 3 prioridades, EV recuperável)
  - **pfgto_block push/fold**: branch separado para M<6 com range de jam em vez de range de abertura padrão
  - **`max_tokens`** aumentado: `max(1200 × N, 3000)` para acomodar síntese final

### Added
- Constantes e helpers de módulo: `_ICM_MULTIPLIER`, `_REV_IMPL_ADJ_PP`, `_rev_impl_tier()`, `_m_zone()`, `_action_warning()`

---

## [v0.92.0] — 2026-05-10 — feat(GTO-004): preflop range GTO — análise completa por posição e stack depth

### Added
- **`backend/leaklab/preflop_gto_ranges.py`** (novo módulo): lê `leaklab_gto_ranges.json` e analisa decisões preflop cobrindo três cenários — RFI, vs RFI e vs 3bet — com classificador de qualidade (`correct/acceptable/leak/major_leak`) e notas profissionais por posição e stack depth
- **`backend/docs/leaklab_gto_ranges.json`**: ranges MTT 8-max validados (RFI por posição, vs RFI por abridor+defensor, vs 3bet) para buckets de stack 10bb–100bb
- **Frontend — painel Range GTO preflop** (`Replayer.tsx`): exibido para hero actions preflop com badge de qualidade, cenário (RFI/vs RFI/vs 3bet), indicador in-range (✓/✗), ação jogada vs recomendada, range %, stack depth e notas profissionais

### Changed
- **`backend/api/app.py`**: `_build_replay_data()` injeta `preflop_gto` em cada hero action preflop via `analyze_preflop()`
- **`backend/leaklab/llm_explainer.py`**: prompt do LLM inclui bloco `📊 Range GTO` para decisões preflop, com cenário, in-range, ação recomendada e notas profissionais
- **`frontend/src/lib/api.ts`**: `ReplayStep.preflop_gto` adicionado com interface tipada completa
- Painel GTO solver (Oracle) ocultado para hero actions preflop — preflop usa range tables; solver apenas para postflop

---

## [v0.91.0] — 2026-05-08 — feat(UX-012): Replayer — cartas inseridas no pod + inlay branco maior

### Changed
- **`leaklab-replayer-v3.html`**: refinamentos visuais nas cartas e fichas
  - **Cartas 30% atrás do pod**: cartas são renderizadas antes do pod (z-order atrás) e posicionadas para 70% visível / 30% tucked atrás do bloco do jogador; direction-aware (top seats: cartas abaixo do pod, bottom seats: acima)
  - **Inlay branco maior**: elipse central das fichas aumentada de `RX*0.42` para `RX*0.58` — dá espaço confortável para "100" (3 dígitos) sem truncamento

---

## [v0.90.0] — 2026-05-08 — feat(UX-011): Replayer — fichas casino com inlay branco + botão dealer redesenhado

### Changed
- **`leaklab-replayer-v3.html`**: refinamentos visuais premium nas fichas e botão dealer
  - **Inlay branco nas fichas**: elipse central agora branca (`rgba(255,255,255,0.92)`) em todas as denominações, com texto de valor sempre em preto `#111` — fidelidade a fichas de casino reais
  - **Botão dealer maior**: dimensões aumentadas de 13×7 para 16×9 (mesmo tamanho das fichas regulares); lado agora com 12 notches alinhados (técnica coseno, igual às demais fichas)
  - **Símbolo ★ no botão dealer**: substituição da letra "D" por estrela de 5 pontas desenhada em SVG path (`M0,-5 L1.18,-1.62 ...`), posicionada sobre inlay branco
  - **Fichas amarelas (denom 1)**: denominação 1 permanece amarela (`#f0d020`) — branca reservada exclusivamente para o chip dealer

---

## [v0.89.0] — 2026-05-08 — feat(UX-010): Replayer — fichas por denominação real + cards com naipe central vívido

### Changed
- **`leaklab-replayer-v3.html`**: fichas e cartas redesenhadas com fidelidade PokerStars
  - **Fichas por denominação real**: sistema `breakChips(amount)` decompõe o valor em denominações (1000=ouro, 500=roxo, 100=preto, 25=verde, 5=vermelho, 1=branco); badge no topo mostra o valor da denominação da ficha mais alta (e.g. 25 para verde)
  - **Remoção de `potToChips`/`betToChips`**: call sites agora passam o valor real direto para `chipStackSVG`
  - **Cartas com naipe central vívido**: símbolo de naipe único e dominante no centro do card (opacidade plena); fonte escalada por largura do card (`fCenter = w*0.78`); rank em negrito com símbolo menor no canto topo-esquerdo; cores mais vívidas (#e50a0a para copas/ouros, #111 para espadas/paus)
  - **Verso das cartas**: padrão azul marinho limpo (remoção dos efeitos de diamante anteriores)
  - **Ficha Dealer premium**: botão D dourado/marfim posicionado geometricamente entre o pod e o centro da mesa (via atan2); badges de posição (BTN/BB/SB) removidos dos pods
  - **Perspectiva isolada**: apenas o SVG de background inclina (`rotateX(9deg)`); pods, fichas e cartas permanecem flat (dois SVGs em camadas separadas)

---

## [v0.88.0] — 2026-05-08 — feat(UX-009): Replayer v3 — fidelidade visual PokerStars

### Changed
- **`leaklab-replayer-v3.html`**: rewrite completo com qualidade PokerStars
  - **Perspectiva 3D real**: CSS `perspective:1100px` + `rotateX(9deg)` no container SVG — mesa inclina visualmente como nos softwares comerciais
  - **Mesa**: feltro verde vibrante (`#40b558→#1d6430`) + rail grafite escuro (`#252525→#0e0e0e`) substituindo o rail marrom anterior
  - **Seat pods**: pill-shaped (borda arredondada `rx=26`), 128×52px, posicionados no perímetro do rail (fora do feltro) — idêntico ao PokerStars
  - **Hero ring**: oval branca (`rgba(255,255,255,0.88)` stroke-width=3.5) ao redor do pod do hero
  - **Fichas 3D** (`chipStackSVG`): discos empilhados com 8 cores distintas, sombra, borda interna e highlight de luz — aplicado no pot e nas apostas individuais
  - **Cartas maiores**: board cards 50×68px com rank+suit topo-esquerdo e baixo-direito, suit central translúcido
  - **Dealer button**: círculo vermelho com "D" branco no canto do pod
  - **Badge de posição**: pill colorida (BTN=dourado, BB=vermelho, SB=laranja) sobreposta ao pod
  - **Fonte**: migração de Rajdhani → Inter para leitura mais nítida dos nomes e stacks
  - **Controles**: barra preta flat, abas de street sem bordas internas, botões circulares, aba ativa vermelha

---

## [v0.87.0] — 2026-05-08 — feat(UX): Replayer premium — redesign visual PokerStars-quality

### Changed
- **`leaklab-replayer-v3.html`**: redesign completo
  - Mesa SVG com feltro verde (`#2e7d46 → #1a5230`) e rail marrom/madeira via radial gradient
  - Hero sempre posicionado na parte inferior da mesa (rotOffset formula)
  - Nomes reais de todos os jogadores (removida anonimização "Villain")
  - Card backs com padrão X (linhas diagonais + losango), substituindo "?"
  - Hero ring: borda branca semitransparente ao redor do seat box do hero
  - Abas de street (`Pre-flop | Flop | Turn | River | Showdown`) substituindo dots de timeline
  - Slider de velocidade (`0.5× → 3×`) substituindo dropdown
  - Botão BB/chips para alternar unidade de exibição
  - Cartas posicionadas entre o seat e o centro da mesa (não mais flutuando para fora)
- **`frontend/src/components/hud/PokerTable.tsx`**: alinhado com novo estilo
  - Feltro: radial gradient verde (`#2e7d46 → #1a5230`) em vez do teal anterior
  - Rail: fundo marrom escuro (`#1a0a04`) com overlay radial (`#5a2510 → #2d1005`)
  - Feltro oval com `inset-[10%]` e `rounded-[50%]` para melhor proporção
  - Hero nameplate: `ring-2 ring-white/40 shadow-[0_0_12px_rgba(255,255,255,0.18)]` (hero ring branca)

---

## [v0.86.0] — 2026-05-08 — fix(UX): dashboard sem flash ao navegar de volta — cache de módulo

### Fixed
- **`Index.tsx`**: variável `_cachedTourns` no escopo de módulo (fora do componente) persiste o resultado de `tournaments.list()` entre navegações — na remontagem, `tourns` e `tournsLoaded` são inicializados a partir do cache, eliminando o flash de KPI cards com dashes antes do EmptyDashboard
- **`Index.tsx`**: condição para EmptyDashboard simplificada para `tournsLoaded && !hasData` (sem `!loading`) — o cache garante estado correto desde o primeiro render após navegação

---

## [v0.85.9] — 2026-05-08 — fix(UX): dashboard não pisca EmptyDashboard ao navegar de volta

### Fixed
- **`Index.tsx`**: adicionado flag `tournsLoaded` (boolean) que só vira `true` quando `tournaments.list()` retorna com sucesso — EmptyDashboard só aparece quando `!loading && tournsLoaded && !hasData`, evitando que uma falha silenciosa da API (catch → null) cause EmptyDashboard mesmo que o usuário tenha dados

---

## [v0.85.8] — 2026-05-08 — fix(UX): dashboard vazio exibe EmptyDashboard em vez dos KPI cards

### Changed
- **`Index.tsx`**: KPI cards e drift alert movidos para dentro do branch `hasData` — sem torneios importados, o dashboard exibe diretamente o `EmptyDashboard` com a área de upload, sem mostrar os cards com "—" e "Sem dados"
- **`Index.tsx`**: hints dos KPI cards simplificados (removidos fallbacks `t("kpis.noData")` e `t("kpis.eventsHintEmpty")` agora desnecessários)

---

## [v0.85.7] — 2026-05-08 — fix(UX): CareerGraphCard — contexto da janela de cálculo no nível atual

### Changed
- **`CareerGraphCard.tsx`**: adicionado rótulo "últimos 5 torneios" abaixo do percentual do nível atual para deixar claro que o valor é a média dos 5 torneios mais recentes (não o histórico completo)
- **i18n** (PT-BR/EN/ES `dashboard.json`): nova chave `career.currentWindow`

---

## [v0.85.6] — 2026-05-06 — fix(UX): LeakCausalMap — texto legível + tooltip no hover

### Changed
- **`LeakCausalMap.tsx`**: texto dentro dos círculos substituído por abreviação de 3-4 letras maiúsculas (`abbrev()`) com `fontSize=11` em vez do label completo ilegível em `fontSize=9`
- **`LeakCausalMap.tsx`**: raio mínimo dos círculos aumentado de 16 para 18px para acomodar melhor o texto
- **`LeakCausalMap.tsx`**: tooltip de hover adicionado — exibe label completo, contagem (n×), avg_score e severity badge; posicionamento inteligente (acima/abaixo) baseado na posição vertical do nó
- **`LeakCausalMap.tsx`**: hit area invisível (`r+6`) adicionado para facilitar o hover em círculos menores
- **`LeakCausalMap.tsx`**: painel de detalhe ao clicar agora exibe `node.label` completo em vez de `node.id`

---

## [v0.85.5] — 2026-05-06 — feat: Replayer redesign — full-screen, sem scroll, Range flutuante

### Changed
- **`Replayer.tsx`**: layout migrado de `HudLayout` para layout customizado `h-dvh overflow-hidden flex-col` — sem barra de rolagem, mesa ocupa todo o espaço disponível entre header e controles
- **`Replayer.tsx`**: `PokerTable` agora é constrangida pela altura (`max-h-[calc(100dvh-20rem)]`) em vez da largura — aspect-ratio calculado automaticamente sem overflow
- **`Replayer.tsx`**: `Action Log` removido — painéis contextuais (EV feedback, anotação coach, showdown) movidos para faixa horizontal compacta abaixo dos controles
- **`Replayer.tsx`**: botão **Range** movido para a barra de controles (ao lado de Speed/BB); sempre visível, desabilitado fora do preflop
- **`RangePanel.tsx`**: painel Range vira floating draggable no desktop (`fixed z-50`, arrastável pelo header via `onHeaderMouseDown`) e bottom sheet no mobile (backdrop + `max-h-72vh`)
- **`Replayer.tsx`**: identificação da mão (`MÃO 4/68` + progress bar) centralizada na mesma linha do botão Voltar via `grid grid-cols-3`
- **`Replayer.tsx`**: default de apostas alterado para `BB` em vez de chips
- **`Replayer.tsx`**: `pb-16 md:pb-2` no container mobile para não sobrepor a nav bar fixa
- **i18n** (`common.json` PT-BR/ES): `nav.study` encurtado para `"Estudos"` / `"Estudios"` (EN já era `"Study"`)
- **i18n** (`replayer.json` PT-BR/EN/ES): novas chaves `navigation.handLabel`, `navigation.prev`, `navigation.next`

---

## [v0.85.4] — 2026-05-06 — feat: campo Instagram no perfil público do coach

### Added
- **`coach_profiles`**: nova coluna `social_instagram TEXT` — schema criado com a coluna e migration (`ALTER TABLE ... ADD COLUMN`) adicionada para Postgres e SQLite
- **`upsert_coach_profile`** (repositories.py): parâmetro `social_instagram` adicionado ao INSERT/ON CONFLICT UPDATE
- **`/coach/profile` POST** (app.py): passa `social_instagram` do payload para o repositório
- **`CoachProfile` interface** (api.ts): campo `social_instagram: string | null`
- **`CoachProfile.tsx`** (editor do coach): campo "Instagram" com ícone `<Instagram />` após o campo Twitter/X — exibição e edição
- **`PublicCoachProfile.tsx`** (perfil público): ícone `<Instagram />` clicável na seção de redes sociais, ao lado de YouTube/Twitch/Twitter

---

## [v0.85.3] — 2026-05-06 — fix: admin Users tab não mostrava display_name dos coaches

### Fixed
- **`get_all_users` (repositories.py)**: adicionado `LEFT JOIN coach_profiles` para incluir `display_name` do perfil público do coach na listagem de usuários do admin
- **`get_all_users_count`**: mesma correção para manter contagem paginada consistente com a query principal; filtros de `plan` e `role` agora usam alias `u.` para evitar ambiguidade
- **Busca por display_name**: admin pode agora buscar coaches pelo nome público (ex: "Daniel Negreanu") no campo de busca da aba Users — antes só buscava por `username` e `email`
- **`AdminDashboard.tsx` UsersTab**: coaches com `display_name` são exibidos com o mesmo padrão da aba Finance: nome público em destaque + `@username` abaixo — elimina a confusão de um coach aparecer como "coach" na aba Users e "Daniel Negreanu" na aba Finance
- **`AdminUser` interface (api.ts)**: adicionado campo `display_name: string | null`

---

## [v0.85.2] — 2026-05-06 — fix: coach inbox mostrava só 1 conversa (filtro errado)

### Fixed
- **`CoachDashboard.tsx` `MensagensTab`**: o filtro `.filter((t) => t.last_sender_role === "student")` escondia todas as conversas onde o coach já havia respondido, deixando o inbox aparentemente vazio ou com 1 única thread. Removido o filtro — o inbox agora mostra **todas** as conversas
- **Badge do tab "Mensagens"**: trocado `filter(last_sender_role === "student").length` por `reduce(unread_count)` para contar mensagens não lidas reais, não apenas threads sem resposta
- **UX**: username em negrito e preview colorido para conversas com mensagens não lidas; prefixo `↩` para indicar threads que aguardam resposta do coach (aluno enviou último); empty state atualizado para "Nenhuma conversa ainda"

---

## [v0.85.1] — 2026-05-06 — feat: UX-009 — exemplos visuais interativos na /docs

### Added
- **Exemplos visuais** adicionados a 9 seções da documentação: Scoring, Top Leaks, Forma Recente, Qualidade das Decisões, Performance por Street, Performance por Posição, Colapso sob Pressão, Pressão ICM e Meu Nível
- **Componentes `ExampleBox`, `MiniBar`, `MiniScoreLine`, `MiniSessionBars`** em `Docs.tsx` para renderizar mini-réplicas dos indicadores reais com cores e proporções fiéis
- **Chaves de exemplo i18n** em PT, EN e ES para todas as 9 seções (`exampleLabel`, `example`, `example_*` por seção)

### Fixed
- `t("leaks.critical")` e `t("form.*")` no `Docs.tsx` agora usam `td` (namespace `dashboard`) em vez do namespace `docs` — evita fallback silencioso para chave literal

---

## [v0.85.0] — 2026-05-05 — feat: UX-008 — tooltips, renome Strategic Twin e docs expandida

### Added
- **HudTooltip** adicionado a 8 cards que estavam sem: `BankrollChart`, `CareerGraphCard`, `CognitiveFailureCard`, `GhostDrillCard`, `LeakCausalMap`, `LeaksPanel`, `LevelCard`, `StrategicTwinCard`
- **11 novas seções** em `/docs` cobrindo todos os cards do dashboard: Top Leaks, Mapa Causal, Forma Recente, Qualidade das Decisões, Performance por Street, Performance por Posição, Colapso sob Pressão, Pressão ICM, Evolução do Bankroll, Meu Nível — cada um com explicação de objetivo, conexão com leaks e orientação para iniciantes. Disponível em PT, EN e ES.
- **8 chaves de tooltip** novas no `dashboard.json` (3 locales) para os cards acima

### Changed
- **`StrategicTwinCard`** renomeado de "Perfil Estratégico" para "Tendências Estratégicas" (PT) / "Strategic Patterns" (EN) / "Tendencias Estratégicas" (ES) — elimina conflito de nome com `PlayerDnaCard` (Decision DNA)
- **`Docs.tsx`**: `SECTION_IDS` expandido de 12 para 23 seções com nav lateral totalmente funcional
- **`docs.json`** (3 locales): nav atualizado, seção `twin.title` atualizado com novo nome

---

## [v0.84.8] — 2026-05-05 — Fix: replay 404 no Sparring Mode

### Fixed
- **`backend/api/app.py`**: endpoint `/replay/<tournament_id>/<hand_id>` usava `get_tournament()` (busca por PokerStars tournament_id string), mas o Sparring envia o `id` inteiro do banco. Agora tenta `get_tournament_by_db_id` primeiro quando o parâmetro é numérico, com fallback para a busca por string — compatível com ambos os callers.

---

## [v0.84.7] — 2026-05-05 — Fix: Sparring 500 no PostgreSQL (HAVING alias)

### Fixed
- **`backend/database/repositories.py`**: `get_sparring_hand` usava `HAVING mistakes > 0` com alias de SELECT — PostgreSQL não permite aliases no HAVING (só SQLite). Substituído pela expressão completa `HAVING SUM(CASE WHEN ... THEN 1 ELSE 0 END) > 0` nas duas variantes da query (com e sem exclusão de mãos já vistas).

---

## [v0.84.6] — 2026-05-05 — Fix: Ghost Table 500 no PostgreSQL

### Fixed
- **`backend/database/repositories.py`**: `get_drill_stats` usava `datetime('now', ? || ' days')` — concatenação dinâmica de parâmetro não é convertida pelo regex do `_adapt()`, então `datetime()` chegava ao PostgreSQL que não conhece essa função. Substituído por cutoff pré-computado em Python (mesmo padrão de todas as outras funções do arquivo).

---

## [v0.84.5] — 2026-05-05 — UX: tabs na página Plano de Estudos

### Changed
- **`frontend/src/pages/StudyPlan.tsx`**: conteúdo reorganizado em 3 tabs — Diagnóstico, Roteiro, Exercícios — eliminando o scroll longo em coluna única. KPIs ficam sempre visíveis acima das tabs. Tab Diagnóstico mantém o layout 8/4 col no desktop.
- **`frontend/src/i18n/locales/*/study.json`**: adicionada chave `tabs.{diagnosis,schedule,exercises}` nas 3 locales (PT-BR / EN / ES).
- Aproveitado para substituir hardcoded `"Dia {n}"` pelo i18n `t("day.label", { n })` no roteiro semanal.

---

## [v0.84.4] — 2026-05-05 — Fix /coaches 500 + remoção do card WhatsApp

### Fixed
- **`backend/database/repositories.py`**: `ROUND(AVG(CAST(rating AS REAL)), 1)` → `NUMERIC` em 3 queries — PostgreSQL não aceita `ROUND(double precision, integer)`, somente `ROUND(numeric, integer)`. Causava 500 em `/coaches` e no endpoint de perfil do coach.

### Removed
- **`frontend/src/pages/StudyPlan.tsx`**: card "Treinar no WhatsApp" removido junto com variável `waNumber` e import `MessageCircle` (ambos inutilizados após remoção).

---

## [v0.84.3] — 2026-05-05 — Fix: 500/CORS em /study/plan após deploy de observabilidade

### Fixed
- **`backend/api/app.py`**: `_log_request` after_request handler agora envolto em `try/except` — uma falha no logging não mais substitui a resposta do endpoint por uma nova 500 sem CORS headers.
- **`backend/api/app.py`**: `sentry_sdk.init()` movido para APÓS `logging.basicConfig(force=True)` — impede que `force=True` remova o `LoggingIntegration` handler do Sentry ao inicializar depois.
- **`backend/api/app.py`**: imports do `sentry_sdk` agora dentro de `try/except ImportError` — app sobe normalmente em ambientes sem o SDK instalado (dev sem `pip install`).

---

## [v0.84.2] — 2026-05-05 — Auditoria de segurança + CLAUDE.md atualizado

### Security
- **`backend/api/app.py`**: CORS configurável via variável de ambiente `ALLOWED_ORIGINS` (padrão `*` em dev; em prod, restrito aos domínios explicitamente listados). Header `Vary: Origin` adicionado quando origin-specific.
- **`backend/api/app.py`**: `/health` não expõe mais tipo de banco nem `db_url_set` — retorna apenas `{status, version}`.
- **`backend/api/app.py`**: `/analyze/guest` recebe `@limiter.limit("10 per hour")` — endpoint público agora tem rate limiting.
- **`render.yaml`**: variável `ALLOWED_ORIGINS` adicionada com valor padrão `https://leaklab.vercel.app` (ajustar para domínio real antes de deploy).

### Docs
- **`CLAUDE.md`**: reescrito — arquitetura atualizada com todas as tabelas (18), endpoints principais, páginas frontend, módulos de features, variáveis de ambiente e notas de segurança/CORS. Era crítico: estava desatualizado desde v0.45.0.

### Not changed (false positives / low risk)
- `.env` com secrets: `backend/.env` está corretamente no `.gitignore`; `frontend/.env` contém apenas `pk_test_*` (Stripe publishable key — público por design).
- JWT secret: `auth.py` já levanta `RuntimeError` em produção se `LEAKLAB_SECRET` não estiver setado.
- `dangerouslySetInnerHTML` em `Docs.tsx`: strings vêm de JSON bundlado no build, sem input de usuário.

---

## [v0.84.1] — 2026-05-04 — Suporte: badge no header + fix estado reply no admin

### Fixed
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: `TicketRow.handleReply` chama `setOpen(false)` antes de invalidar queries — textarea some imediatamente ao confirmar envio, exibindo o card de "Resposta enviada".

### Changed
- **`frontend/src/components/hud/HudHeader.tsx`**: botão `LifeBuoy` adicionado no header (visível a todos os usuários não-admin). Badge vermelho aparece quando há tickets com resposta do admin. Clicar abre `SupportModal` diretamente na aba "Minhas mensagens" quando há respostas pendentes. `SupportModal` renderizado inline no header (igual ao drawer do coach).
- **`frontend/src/pages/Index.tsx`**: badge de suporte do footer removido para não-admin (movido para o header). Footer mantém apenas o badge de tickets abertos para admin.

---

## [v0.84.0] — 2026-05-04 — Suporte bidirecional: aluno visualiza resposta do admin

### Added
- **`backend/api/app.py`**: `GET /support/my-tickets` — retorna todos os tickets do usuário logado (com admin_reply e replied_at). `GET /support/my-tickets/unread` — contagem de tickets com resposta do admin.
- **`frontend/src/components/hud/SupportModal.tsx`**: reescrito com duas abas — "Nova mensagem" (formulário) e "Minhas mensagens" (histórico de tickets + respostas do admin). Badge na aba Minhas mensagens quando há respostas. Abre direto na aba inbox quando `initialTab="inbox"`.
- **`frontend/src/pages/Index.tsx`**: badge no botão Suporte do footer para alunos não-admin quando há tickets respondidos. Modal abre na aba inbox automaticamente nesse caso. `useQuery` para `myUnreadCount` com polling de 2min.
- **`frontend/src/lib/api.ts`**: interface `MyTicket` + métodos `support.myTickets()` e `support.myUnreadCount()`.

---

## [v0.83.9] — 2026-05-04 — Admin: exclusão permanente de usuários com confirmação

### Added
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: botão de lixeira por linha na aba Usuários. Abre `DeleteUserModal` com nome/email do alvo, campo de senha administrativa e aviso de irreversibilidade. Senha é verificada no backend antes de qualquer exclusão.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: `DeleteUserModal` — modal com ícone de alerta, input de senha com `autoFocus`, feedback de erro inline, botão "Excluir definitivamente" desabilitado até senha digitada.
- **`backend/api/app.py`**: `DELETE /admin/users/<uid>` — exige `admin_password` no body, verifica credenciais do admin via `verify_password`, bloqueia auto-exclusão, deleta todos os dados do usuário em cascata.
- **`backend/database/repositories.py`**: `delete_user_admin(user_id)` — remove decisões, torneios, cache LLM, tickets de suporte e o registro `users` em cascata, dentro de uma única transação.
- **`frontend/src/lib/api.ts`**: `adminDashboard.deleteUser(id, adminPassword)` método adicionado.

---

## [v0.83.8] — 2026-05-04 — Badge de tickets abertos + sistema de resposta no admin

### Added
- **`frontend/src/pages/Index.tsx`**: badge vermelho no botão "Suporte" do footer mostrando contagem de tickets abertos (admin only). Polling a cada 2 minutos via `useQuery`.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: aba "Suporte" agora exibe lista completa de tickets com sistema de resposta inline — textarea de reply, botão de envio, toggle "editar resposta", badges de status (open=vermelho, replied=azul). Consulta e invalida `admin-support-count` após resposta.
- **`backend/api/app.py`**: `POST /admin/support-tickets/<id>/reply` — atualiza `admin_reply`, `status='replied'` e `replied_at` (require_admin). `GET /admin/support-tickets/count` — retorna `{ open: N }` (require_admin).
- **`backend/database/schema.py`**: colunas `admin_reply TEXT` e `replied_at` adicionadas à tabela `support_tickets` em SQLite e PostgreSQL.
- **`frontend/src/lib/api.ts`**: métodos `support.unreadCount()` e `support.replyTicket(id, reply)` adicionados ao namespace `support`.

---

## [v0.83.6] — 2026-05-04 — Footer: remoção do status bar + modal de suporte

### Changed
- **`frontend/src/pages/Index.tsx`**: footer simplificado — removido "ENC: AES-256 • LATENCY: 14ms • SESSION_LOCKED" e link "Status". Mantidos apenas "Docs" e "Suporte". Suporte agora abre um modal em vez de ser um link morto.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: removidas chaves `sessionLocked` e `status_page`; adicionadas chaves `supportModal.*` com título, campos, categorias e mensagens de feedback nas 3 locales.

### Added
- **`frontend/src/components/hud/SupportModal.tsx`**: modal de contato com seletor de categoria (bug, dúvida, sugestão, cobrança, outro), campo de assunto e mensagem (2000 chars), pré-preenchimento de usuário/email, feedback de sucesso e erro. i18n nas 3 locales.
- **`backend/database/schema.py`**: tabela `support_tickets` (id, user_id, category, subject, message, status, created_at) criada em SQLite e PostgreSQL.
- **`backend/api/app.py`**: `POST /support/contact` — salva ticket no banco, exige mensagem não-vazia, requer autenticação.

---

## [v0.83.5] — 2026-05-04 — Bugfix: narrativas IA não atualizam ao trocar idioma

### Fixed
- **`frontend/src/pages/Index.tsx`**: adicionado `useEffect` separado com dependência `[i18n.language]` que re-busca apenas os 4 endpoints de narrativa sensíveis ao idioma (`leakGraph`, `career`, `cognitiveFailures`, `strategicTwin`) quando o locale muda. Guard `langMounted` evita double-fetch no mount inicial. Os demais dados (evolution, breakdown, tournaments, etc.) não são re-buscados desnecessariamente.

---

## [v0.83.4] — 2026-05-04 — Bugfix: termos de poker em inglês nos prompts LLM

### Fixed
- **`backend/leaklab/llm_explainer.py`**: adicionada constante `_POKER_TERMS_EN` com lista canônica de termos técnicos (fold, call, raise, bet, check, jam, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position, IP, OOP, shove, reshove, open, limp, squeeze). Instrução injetada em todos os system prompts: decisão, resumo de torneio, comparação, sessão review, coach chat e sparring. Elimina traduções indevidas como "ruas" (→ turn/river), "mão" (→ hand), "tabuleiro" (→ board) no texto gerado pela IA.
- **`backend/leaklab/llm_explainer.py`**: `_LANG_INSTRUCTIONS` atualizado para incluir a cláusula de poker terms nas 3 locales (PT-BR e ES).

---

## [v0.83.3] — 2026-05-04 — Bugfix: terminologia técnica e truncamento na Análise Comparativa

### Fixed
- **`backend/leaklab/llm_explainer.py`**: `max_tokens` da narrativa comparativa aumentado de 100 → 350 (texto era cortado no meio da segunda frase).
- **`backend/leaklab/llm_explainer.py`**: prompts de comparação, sessão e coach chat substituem `standard_pct`/`avg_score`/`clear_pct` por `Standard%`/`Score médio`/`Erros claros` — o LLM não mais repete nomes de variáveis no texto gerado.
- **`backend/leaklab/llm_explainer.py`**: corrigida interpolação dupla-chave `{{avg_score:.4f}}` → `{avg_score:.4f}` no prompt do plano de estudos — métricas reais agora chegam ao LLM em vez de placeholders literais.
- **`backend/leaklab/llm_explainer.py`**: template fallback `_template_comparison` e string de carreira usam `Standard%` em vez de `standard_pct`.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seção Trajetória de Carreira substituiu todos os `standard_pct` por `Standard%` (em negrito) nos valores de parágrafo e tabela.

---

## [v0.83.2] — 2026-05-04 — Bugfix: import múltiplo de torneios no EmptyDashboard

### Fixed
- **`frontend/src/components/hud/EmptyDashboard.tsx`**: refatorado para usar `useUploadQueue` (mesmo hook do HudHeader) em vez de `processFile` próprio. Agora aceita múltiplos arquivos via drag-and-drop e via seletor (`multiple`). O painel de fila com status por arquivo é exibido durante o processamento. Reset `e.target.value = ""` no `onChange` para permitir re-seleção do mesmo arquivo.

---

## [v0.83.1] — 2026-05-04 — Sprint AY: Mobile audit + responsividade

### Fixed
- **`frontend/src/components/hud/DraggableCard.tsx`**: drag handle sempre visível em mobile (`opacity-100 md:opacity-0 md:group-hover:opacity-100`); tamanho aumentado (`px-3 py-1 / size-4`) para alvo de toque adequado; `touch-none` para impedir scroll acidental durante drag.
- **`frontend/src/pages/GhostTable.tsx`**: botões de ação com `min-h-[44px]` — atende ao mínimo de toque iOS/Android HIG (era ~42px).
- **`frontend/src/pages/Sparring.tsx`**: mesmo fix de `min-h-[44px]` nos botões de ação contextuais.
- **`frontend/src/components/hud/HudHeader.tsx`**: `LanguageSwitcher` removido do `hidden sm:` — seletor de idioma agora acessível em mobile (era invisível em telas < 640px).
- **`frontend/src/pages/StudentProfile.tsx`**: grids de 2 colunas nos formulários de dados do jogador alterados para `grid-cols-1 sm:grid-cols-2` — campos não colapsam em telas < 400px.

---

## [v0.83.0] — 2026-05-04 — Sprint AX: Onboarding para novos usuários

### Added
- **`backend/database/schema.py`**: coluna `onboarding_completed` (BOOLEAN, default FALSE) adicionada à tabela `users` via migração em Postgres e SQLite.
- **`backend/database/repositories.py`**: `set_onboarding_completed(user_id)` — marca o onboarding como concluído no banco.
- **`backend/api/app.py`**: `POST /player/onboarding/complete` — endpoint para registrar conclusão ou skip do onboarding. Campo `onboarding_completed` incluído no payload de `GET /auth/me`.
- **`frontend/src/lib/api.ts`**: campo `onboarding_completed?: boolean` adicionado à interface `UserProfile`; `auth.completeOnboarding()` chama `POST /player/onboarding/complete`.
- **`frontend/src/components/hud/OnboardingModal.tsx`**: modal multi-step (4 passos) com stepper visual, ícones Lucide por etapa, botões Pular/Voltar/Próximo, CTA final navega para `/analyze`. Ao fechar (skip ou finish) chama `completeOnboarding()` e `refreshUser()` para não exibir novamente.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/onboarding.json`**: namespace `onboarding` completo nas 3 locales — passos welcome, upload, train, ready.
- **`frontend/src/i18n/index.ts`**: namespace `onboarding` registrado nas 3 locales.

### Changed
- **`frontend/src/pages/Index.tsx`**: estado `showOnboarding` inicializado com `!user?.onboarding_completed`; `<OnboardingModal>` renderizado condicionalmente ao lado do `<AcceptCoachModal>`.

---

## [v0.82.3] — 2026-05-04 — Docs: Pressure Mode + Sparring rotation + BACKLOG atualizado

### Changed
- **`frontend/src/pages/Docs.tsx`**: seção Ghost Table agora renderiza `ghost.p5` — descrição do Pressure Mode (cronômetro 30s, anel SVG, fold automático, badge 🔥 de streak).
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: adicionada chave `ghost.p5` nas 3 locales descrevendo o Pressure Mode. Chave `sparring.p2` atualizada para mencionar o mecanismo de rotação de mãos por sessão (exclusão de mãos já jogadas, ciclo de 90 dias).
- **`BACKLOG.md`**: Sprints AQ–AW e bugfixes v0.81.1–v0.82.2 movidos para tabela de concluídos. Seção "Em Aberto" atualizada: FEAT-14/15/16 (entregues) removidos; FEAT-17 (Onboarding) e FEAT-18 (Mobile audit) adicionados como próximas sprints AX e AY.

---

## [v0.82.2] — 2026-05-04 — Fix: perfil i18n completo + telefone no perfil + remoção WhatsApp Coaching

### Changed
- **`frontend/src/pages/StudentProfile.tsx`**: seção WhatsApp Coaching removida (integração Meta adiada). Campo "Telefone / WhatsApp" movido para dentro de "Dados do Jogador" — salvo em conjunto com os demais dados no mesmo botão; saves chamadom `profileApi.update()` + `authApi.updatePhone()`.
- **`frontend/src/pages/StudentProfile.tsx`**: i18n completo — todos os textos hardcoded da página substituídos por `t()`. Sub-componentes `CoachReviewWidget`, `CoachDiscoveryCard` e `NoCoachDiscovery` agora usam `useTranslation("profile")` e não têm nenhum string hardcoded em PT-BR.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/profile.json`**: adicionados grupos `email.*`, `password.*` (labels, placeholders, botões, toasts) e `coach.*` (review, discovery, unlink) — cobertura total da página em PT/EN/ES. Chaves `whatsapp.*` e `sections.whatsapp` removidas.

---

## [v0.82.1] — 2026-05-04 — Fix: perfil demográfico visível e editável na página de Perfil

### Added
- **`frontend/src/pages/StudentProfile.tsx`**: nova seção "Dados do Jogador" no topo da página de perfil — exibe e permite editar todos os 7 campos demográficos (ano de nascimento, país, estado, cidade, anos de experiência, modalidade, faixa de buy-in) mesmo quando ainda não preenchidos. Barra de progresso mostra quantos dos 5 campos essenciais estão completos; fica verde ao completar todos.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/profile.json`**: namespace `demo.*` adicionado nas 3 locales com todas as labels, opções de select e mensagens de status.

### Fixed
- **Dados do jogador preenchidos mas invisíveis**: os campos demográficos só existiam no `ProfileCompletionCard` do dashboard (descartável e que some após o preenchimento). Agora ficam sempre acessíveis via `/profile`, com valores carregados do backend e salvos via `PATCH /player/profile`.

---

## [v0.82.0] — 2026-05-04 — Sprint AW: Ghost Table Pressure Mode + Sparring hand rotation

### Added
- **`frontend/src/pages/GhostTable.tsx`**: **Pressure Mode** — toggle na intro desbloqueia modo cronometrado: 30 s por decisão, timeout dispara fold automático via `submitRef.current` (sem stale closure), streak de acertos exibido com badge 🔥 durante a sessão e tile dedicado na tela de conclusão.
- **`frontend/src/pages/GhostTable.tsx`**: `TimerRing` — anel SVG circular de contagem regressiva com transição CSS suave; vermelho quando ≤ 10 s. Botões de ação bloqueados após timeout até o próximo spot.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/ghost.json`**: chaves `pressure.toggle`, `pressure.desc`, `pressure.timedOut`, `pressure.streakLabel` adicionadas nas 3 locales.
- **`backend/database/repositories.py`**: parâmetro `exclude_hand_ids: list` em `get_sparring_hand` — filtra mãos já vistas na sessão; se todas as mãos foram excluídas, retorna o ciclo desde o início.
- **`backend/api/app.py`**: endpoint `GET /player/sparring/hand` passa `exclude_hand_ids` (comma-separated) para o repositório.
- **`frontend/src/lib/api.ts`**: `sparring.hand()` aceita `exclude_hand_ids?: string[]` e os envia como query param.
- **`frontend/src/pages/Sparring.tsx`**: `seenHandIds` ref — rastreia IDs de mãos já jogadas na sessão; `loadHand()` passa a lista para excluir ao buscar a próxima mão, garantindo rotação mesmo com múltiplas chamadas de "New Hand".

### Fixed
- **Sparring sempre exibia a mesma mão**: `get_sparring_hand` não tinha mecanismo de exclusão — `New Hand` sempre retornava a mão com o pior erro. Agora cada mão jogada é adicionada à lista de exclusão e a próxima chamada traz uma mão diferente.

---

## [v0.81.1] — 2026-05-04 — Bugfix: i18n sparring + test suite verde

### Fixed
- **`frontend/src/i18n/locales/{pt-BR,en,es}/sparring.json`**: chaves `arenaLabel` e `arenaDesc` adicionadas nas 3 locales — eram usadas pelo card de intro da fase idle do Sparring mas estavam ausentes nos arquivos de tradução (as chaves retornavam o próprio nome da chave em vez do texto traduzido).
- **`backend/tests/run_all_tests.py`**: substituído `python3` por `sys.executable` + adicionado `encoding='utf-8'` — `python3` no Windows apontava para Python 3.10 (sem suporte a backslash em f-strings), causando falsos negativos em 25 testes da suite de subscription.
- **`backend/tests/test_api_endpoints.py`**: 3 testes de coach registration atualizados para o novo fluxo `/auth/coach-apply` (coaches não se registram mais diretamente via `/auth/register`; login retorna 403 `coach_pending` até aprovação admin).
- **`backend/tests/test_subscription.py`**: 2 testes de webhook atualizados — `test_webhook_no_secret_allowed` e `test_webhook_subscription_deleted_downgrades` agora patcham `api.app.STRIPE_WEBHOOK_SECRET` para `""` evitando interferência do `.env` local; comportamento esperado corrigido para refletir a implementação atual do endpoint.

---

## [v0.81.0] — 2026-05-04 — Sprint AV: Página Treinos + Botões contextuais

### Added
- **`frontend/src/pages/Training.tsx`**: nova página `/training` — landing de treino com dois cards (Ghost Table e Sparring Mode), esquema visual primário vs amber, lista de features, CTAs diretos.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/training.json`**: namespace `training` com todas as strings da página nas 3 locales.
- **`frontend/src/i18n/index.ts`**: namespace `training` registrado nas 3 locales.
- **`frontend/src/App.tsx`**: rota `/training` adicionada (ProtectedRoute).

### Changed
- **`frontend/src/components/hud/HudHeader.tsx`**: `TrainingDropdown` removido — substituído por `NavLink` simples `/training` com `activePaths: ["/training", "/ghost", "/sparring"]`; código simplificado (sem `TrainingDropdown`, sem `ChevronDown`, sem `isDropdown`).
- **`frontend/src/pages/Sparring.tsx`**: botões de ação contextuais — `facing_bet > 0` exibe `[fold, call, raise, jam]`; `facing_bet == 0` exibe `[fold, check, bet, jam]`; `facing_bet == null` exibe todos os 6 (fallback). Grid adapta de 4 para 6 colunas conforme o conjunto.

---

## [v0.80.0] — 2026-05-04 — Sprint AU: PokerTable visual no Sparring

### Changed
- **`frontend/src/pages/Sparring.tsx`**: substituição da exibição plana de cartas pelo componente `PokerTable` completo — herói posicionado na parte inferior da mesa, vilões ao redor (N baseado em `num_players`), board real, pot real, stacks em BB. Exibido tanto na fase *playing* quanto na fase *feedback* (mesa congelada como contexto). Remove import direto de `PlayingCard` (agora encapsulado no `PokerTable`).

### Added
- **`frontend/src/pages/Sparring.tsx`**: helper `buildSparringSeats(step, heroCards)` — constrói o array `Seat[]` com herói (cartas reais + stack real) e vilões (cartas viradas + 100 BB estimado).

---

## [v0.79.0] — 2026-05-04 — Sprint AT: Menu "Treinos" + Sparring Visual

### Added
- **`frontend/src/components/hud/HudHeader.tsx`**: componente `TrainingDropdown` — agrupamento de Ghost Table e Sparring sob um menu "Treinos/Training/Entrenamiento" com dropdown no desktop; mobile mantém item único "Treinos" → `/ghost` com estado ativo cobrindo ambas as rotas (`/ghost`, `/sparring`).
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: chave `nav.training` adicionada ("Treinos" / "Training" / "Entrenamiento").

### Changed
- **`frontend/src/pages/Sparring.tsx`**: redesign visual completo para diferenciar do Ghost Table — esquema de cores amber/laranja, componente `StreetTimeline` (cadeia horizontal de pontos com ícones Flame/CheckCircle2/XCircle), componente `HandRecap` (histórico compacto de decisões anteriores), arena intro card com gradiente e ícone `Swords`.

---

## [v0.78.0] — 2026-05-04 — Sprint AS: AI Sparring Mode

### Added
- **`backend/database/repositories.py`**: `get_sparring_hand(user_id, hand_id, tournament_id)` — auto-seleciona a mão com pior erro nos últimos 90 dias (priorizando mãos com múltiplas decisões), retorna todas as decisões em ordem cronológica com contexto completo.
- **`backend/api/app.py`**: `GET /player/sparring/hand?hand_id=&tournament_id=` — serve mão para o modo Sparring.
- **`frontend/src/lib/api.ts`**: interfaces `SparringStep` e `SparringHand`; `sparring.hand(hand_id?, tournament_id?)`.
- **`frontend/src/pages/Sparring.tsx`**: nova página `/sparring` com 4 fases — playing (cartas + botões de ação), feedback (correto/errado, best action, delta, SRS, análise engine), summary (precisão geral, linha por decisão), idle. Reutiliza `PlayingCard`, `drill.submit`, `drill.analysis` e SRS do Ghost Table.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/sparring.json`**: namespace `sparring` com todas as strings da página (PT/EN/ES).
- **`frontend/src/i18n/index.ts`**: namespace `sparring` registrado nas 3 locales.
- **`frontend/src/pages/Docs.tsx`**: seção `sparring` com tabela de fases.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seção `sparring` na docs e chave `nav.sparring`.

### Changed
- **`frontend/src/App.tsx`**: rota `/sparring` adicionada (ProtectedRoute).
- **`frontend/src/components/hud/HudHeader.tsx`**: item "Sparring" adicionado ao nav de players.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: chave `nav.sparring` adicionada.

---

## [v0.77.0] — 2026-05-04 — Sprint AR: Personal Strategic Twin

### Added
- **`backend/database/repositories.py`**: `get_strategic_twin_profile(user_id, days=180)` — agrega spots por `(street, best_action, icm_pressure)`, calcula taxa de erro por spot, retorna taxa média do jogador, top 5 spots por volume e top 5 spots mais custosos (error_rate > avg + 10%, mín. 5 decisões).
- **`backend/leaklab/llm_explainer.py`**: `generate_twin_narrative(profile, lang)`, `_call_twin_narrative`, `_template_twin` — narrativa em 1ª pessoa preditiva (2-3 frases) com o spot mais custoso, tendência revelada e ajuste concreto; suporte PT/EN/ES; fallback determinístico.
- **`backend/api/app.py`**: `GET /player/strategic-twin?lang=&days=` — retorna perfil + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `TwinSpot` e `StrategicTwinProfile`; `metrics.strategicTwin(lang, days)`.
- **`frontend/src/components/hud/StrategicTwinCard.tsx`**: card lateral com taxa média de erro, lista dos 3 spots mais custosos (barra de erro vs linha de média do jogador, delta colorido, volume de decisões) e narrativa LLM. Totalmente i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seção `strategicTwin` com ações, streets, níveis de ICM e labels de UI.

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: `"twin"` adicionado ao tipo `SidebarSection`; incluído no `DEFAULT_LAYOUT.sidebar` ao final da lista — merge automático garante aparição para usuários existentes.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.strategicTwin(i18n.language)` no carregamento; renderiza `StrategicTwinCard` como card draggable no sidebar.

---

## [v0.76.0] — 2026-05-04 — Sprint AQ+: Dashboard UX Redesign

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: tipos `MainSection` e `SidebarSection` reescritos para novo modelo de layout. `MainSection` agora é `"quality_row" | "bankroll_row" | "street_row" | "dna_row" | "drill_row" | "insight_row"` (BankrollChart e PlayerDnaCard viram rows sortáveis). `SidebarSection` reduzido a `"leaks" | "causal_map" | "level"` (3 cards essenciais). `DEFAULT_LAYOUT` atualizado; merge automático migra layouts salvos de usuários existentes.
- **`frontend/src/pages/Index.tsx`**: função `renderMainRow(id)` unifica renderização das 6 rows do main column, incluindo `insight_row` que exibe `CareerGraphCard` e `CognitiveFailureCard` lado a lado em grid 2-col. `renderSidebarCard(id)` reduzido a 3 cards. `BankrollChart` e `PlayerDnaCard` agora são rows sortáveis (`bankroll_row`, `dna_row`) em vez de injetados entre rows via índice. Card `ai_confidence` removido. Import `HudTooltip` removido (era unused após remoção do card).

### Removed
- Card `ai_confidence` removido do layout — não havia dados suficientes para preencher de forma significativa.
- `career` e `cognitive_failures` removidos do sidebar — movidos para `insight_row` no main column onde ficam lado a lado com espaço adequado (~700px cada).

---

## [v0.75.0] — 2026-05-04 — Sprint AQ: Cognitive Failure Mapper

### Added
- **`backend/leaklab/cognitive_mapper.py`**: detector de 5 padrões cognitivo-emocionais sobre sequências de decisões — `revenge_aggression` (agressividade após folds corretos), `fear_folding` (folds incorretos após blowups), `sunk_cost` (calls ruins em múltiplas streets), `entitlement_tilt` (erros após boa sequência) e `compensation_call` (calls ruins após fold correto). Usa janelas deslizantes de 5–10 decisões por torneio; retorna padrões ordenados por frequência com severity (high/medium/low).
- **`backend/database/repositories.py`**: `get_cognitive_failure_report(user_id, days=90)` — consulta decisões dos últimos N dias ordenadas por torneio + id, e chama `analyze_cognitive_failures`.
- **`backend/leaklab/llm_explainer.py`**: `generate_cognitive_narrative(patterns, lang)`, `_call_cognitive_narrative`, `_template_cognitive` — narrativa de 2-3 frases com o padrão dominante, custo em EV e um hábito corretivo; suporte multilíngue (PT/EN/ES); fallback determinístico.
- **`backend/api/app.py`**: `GET /player/cognitive-failures?lang=&days=` — retorna relatório + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `CognitivePattern` e `CognitiveFailureData`; `metrics.cognitiveFailures(lang, days)`.
- **`frontend/src/components/hud/CognitiveFailureCard.tsx`**: card com lista de padrões detectados (nome traduzido, severity badge colorido, barra de frequência, descrição), narrativa LLM e estados de loading/empty. Totalmente i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seção `cognitiveFailure` com 5 nomes de padrão, 5 descrições, 3 níveis de severity.

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: adicionado `"cognitive_failures"` ao tipo `SidebarSection`; incluído no `DEFAULT_LAYOUT` entre `"career"` e `"ai_confidence"`.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.cognitiveFailures(i18n.language)` no carregamento; renderiza `CognitiveFailureCard` como card draggable no sidebar.

---

## [v0.74.0] — 2026-05-04 — Sprint AP: Strategic Career Graph

### Added
- **`backend/database/repositories.py`**: `get_career_projection(user_id)` — regressão linear pura (sem numpy) sobre histórico completo de `standard_pct`; calcula slope, projeção por torneio, datas estimadas para cada um dos 7 níveis, leaks bloqueadores (top 3, últimos 90d), e séries de sparkline (histórico + projeção curta).
- **`backend/leaklab/llm_explainer.py`**: `generate_career_narrative(projection, lang)` — narrativa de 2-3 frases sobre tendência, tempo para próximo nível e leak prioritário; template fallback se LLM indisponível; suporte multilíngue (PT/EN/ES).
- **`backend/api/app.py`**: `GET /player/career?lang=` — retorna projeção + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `CareerProjection` e `CareerMilestone`; `metrics.career(lang)`.
- **`frontend/src/components/hud/CareerGraphCard.tsx`**: card com sparkline SVG (linha histórica sólida + projeção tracejada), nível atual vs. próximo, milestones projetados, leaks bloqueadores e narrativa LLM. Totalmente i18n (PT/EN/ES).
- **`frontend/src/hooks/useDashboardLayout.ts`**: adicionado `"career"` como `SidebarSection`; incluído no `DEFAULT_LAYOUT` entre `"level"` e `"ai_confidence"`.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.career(i18n.language)` no carregamento; renderiza `CareerGraphCard` como card draggable no sidebar.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seção `career` com 15 chaves de tradução.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seção `career` + chave `nav.career` adicionadas.
- **`frontend/src/pages/Docs.tsx`**: nova seção `/docs#career` com tabela de termos e descrição da metodologia de projeção.

---

## [v0.73.0] — 2026-05-04 — Bugfix: i18n level names, LeakCausalMap narrative, drag handle

### Fixed
- **`frontend/src/components/hud/LevelCard.tsx`**: nomes de nível agora são traduzidos (PT/EN/ES) via chaves `level.names.*` no namespace `dashboard`; mapeamento `LEVEL_SLUG` converte strings PT do backend em slugs canônicos para cores, ícones e i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: adicionada seção `level.names` com os 7 nomes de nível em cada idioma.
- **`backend/leaklab/llm_explainer.py`**: `explain_leak_causality` e `_call_llm_causality` aceitam `lang` param — o prompt agora instrui o LLM a responder no idioma correto (PT/EN/ES); `max_tokens` aumentado de 150 para 280 para evitar truncamento da narrativa.
- **`backend/database/repositories.py`**: `get_leak_graph_data` aceita `lang` param e o passa para o LLM.
- **`backend/api/app.py`**: endpoint `GET /player/leak-graph` agora lê `?lang=` da query string.
- **`frontend/src/lib/api.ts`**: `metrics.leakGraph(days, lang)` passa idioma para o endpoint.
- **`frontend/src/pages/Index.tsx`**: `leakGraph` carregado com `i18n.language` para narrativa no idioma correto.
- **`frontend/src/components/hud/DraggableCard.tsx`**: grip handle movido para `left-3` (era `right-3`) — evita sobreposição com conteúdo como "90d" no canto direito do header.

---

## [v0.72.0] — 2026-05-04 — Sprint i18n: cobertura completa de novos componentes

### Changed
- **`frontend/src/pages/Docs.tsx`**: substituídos todos os placeholders por chaves i18n corretas — linhas da Ghost Table usam `t("ghost.result_hit/miss/mastery")`, termo de coaching usa `t("coaching.term_override")`, nomes de nível usam `t("gamification.level_*")`; removida importação `tc` desnecessária.
- **`frontend/src/components/hud/LeakCausalMap.tsx`**: adicionado `useTranslation("dashboard")`; substituídos todos os 5 textos hardcoded por chaves `t("leakCausalMap.*")` — título, aria-label, "Co-ocorre com", "limpar seleção", labels de severidade, "espessura = correlação".
- **`frontend/src/components/hud/HudHeader.tsx`**: título do drawer de chat do coach agora usa `t("coachMessages")` (fallback quando `coach_username` não está disponível); `title` do botão badge também i18n.
- **`frontend/src/components/hud/DraggableCard.tsx`**: tooltip "Arrastar para reordenar" agora usa `tc("actions.dragToReorder")`.
- **`frontend/src/pages/Index.tsx`**: botão "Restaurar padrão" agora usa `tc("actions.resetLayout")`.

---

## [v0.71.0] — 2026-05-04 — Sprint AG: FEAT-12 Página de Documentação

### Added
- **`frontend/src/pages/Docs.tsx`**: página `/docs` estilo wiki com 8 seções — Sistema de Scoring, Indicadores, Fases de M-Ratio, Decision DNA, Ghost Table/Drills, Comparativo de Torneios, Coaching, Gamificação. Sidebar fixa com navegação âncora e active highlight por IntersectionObserver. Tabelas com valores precisos extraídos do código (thresholds reais do engine, XP amounts, níveis, conquistas).
- **`frontend/src/App.tsx`**: rota `/docs` pública (AuthRoute).
- **`frontend/src/pages/Index.tsx`**: link "Docs" no footer agora aponta para `/docs`.

---

## [v0.70.0] — 2026-05-04 — Sprint AL: UX-017 Dashboard Personalizável

### Added
- **`backend/database/schema.py`**: coluna `dashboard_layout TEXT` na tabela `users` (SQLite + PostgreSQL).
- **`backend/database/repositories.py`**: `get_user_preferences(user_id)` e `save_user_preferences(user_id, layout)`.
- **`backend/api/app.py`**: `GET /player/preferences` e `PATCH /player/preferences`.
- **`frontend/package.json`**: dependências `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`.
- **`frontend/src/hooks/useDashboardLayout.ts`**: hook que carrega layout do servidor, persiste com debounce de 800ms e expõe `updateMain`, `updateSidebar`, `reset`.
- **`frontend/src/components/hud/DraggableCard.tsx`**: wrapper sortable com drag handle (⠿) visível ao hover no canto superior direito.
- **`frontend/src/lib/api.ts`**: interface `DashboardLayoutData`; objeto `preferences` com `get()` e `save()`.

### Changed
- **`frontend/src/pages/Index.tsx`**: coluna principal (3 linhas: quality_row, street_row, drill_row) e sidebar (leaks, causal_map, level, ai_confidence) agora são sortáveis via `@dnd-kit`. BankrollChart e PlayerDnaCard permanecem fixos. Botão "Restaurar padrão" no header do dashboard. Layout sincronizado entre devices via backend.

---

## [v0.69.0] — 2026-05-04 — Sprint AN: UX-019 Coach Chat Drawer

### Changed
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: adicionado prop `drawer` — quando `true`, renderiza como painel full-height (sem header colapsável, `flex-1 min-h-0`) para uso dentro do drawer flutuante.
- **`frontend/src/components/hud/HudHeader.tsx`**: ícone de mensagens no header agora é um botão que abre/fecha o drawer de chat em vez de navegar para `/coach`. Badge vermelho exibido somente quando há mensagens não lidas (badge oculto quando zero). Drawer renderizado como `fixed inset-y-0 right-0 w-full sm:w-96` com overlay semi-transparente; fecha com clique no overlay ou tecla Escape.
- **`frontend/src/pages/AICoach.tsx`**: `CoachMessagesPanel` removido da sidebar — chat agora está exclusivamente no drawer global do header.

---

## [v0.68.0] — 2026-05-03 — Sprint AM: UX-018 Tabela de Alunos com Busca e Filtros

### Changed
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: `AlunosTab` reescrita como tabela responsiva com busca por nome, filtro de status (Todos/Ativos/Inativos), ordenação por coluna (Aluno, Torneios, Último Import, Tendência) e paginação client-side (25 por página). Colunas responsivas: Torneios oculto em mobile, Último Import oculto abaixo de md, Tendência oculta abaixo de lg. Ícone de tendência colorido (verde↑/vermelho↓/cinza→). Badge Ativo/Inativo baseado em import nos últimos 30 dias. Contador "X–Y de Z" e botões Anterior/Próximo.

---

## [v0.67.0] — 2026-05-04 — Sprint AJ+AK: UX-015 Coach Inbox + UX-016 Student Badge

### Added
- **`backend/database/repositories.py`**: `get_coach_inbox(coach_id)` — agrega conversas por aluno com `last_message_body`, `last_message_at` e `unread_count`.
- **`backend/api/app.py`**: `GET /coach/messages/inbox` — retorna threads ordenadas por `last_message_at DESC`.
- **`frontend/src/lib/api.ts`**: interface `InboxThread`; `coachDashboard.inbox()`.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: aba "Mensagens" com inbox — avatar inicial, nome do aluno, prévia da última mensagem, timestamp relativo e badge vermelho de não lidas. Badge de não lidas total no botão da aba (polling 60s).

### Changed
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: mensagens não lidas do coach recebem highlight (`border-primary/30 bg-primary/5`). Badge no header da aba desaparece imediatamente ao abrir o painel via `invalidateQueries`.

### Backlog
- **Sprint AM (UX-018)** adicionado: listagem de alunos com tabela, busca, filtros e paginação.

---

## [v0.66.0] — 2026-05-03 — Sprint AI: BACK-019 Perfil Demográfico do Usuário

### Added
- **`backend/database/schema.py`**: 8 novas colunas em `users` — `birth_year`, `country`, `state_province`, `city`, `poker_experience_years`, `main_game_type`, `usual_buyin_range`, `profile_completed_at` (migrações Postgres e SQLite).
- **`backend/database/repositories.py`**: `get_user_demographics`, `update_user_demographics` (marca `profile_completed_at` quando campos core preenchidos), `get_demographics_aggregate` (dados anonimizados para o admin).
- **`backend/api/app.py`**: `GET /player/profile`, `PATCH /player/profile`, `GET /admin/demographics`; campo `profile_completed_at` adicionado à resposta do `/auth/me`.
- **`frontend/src/lib/api.ts`**: interface `DemographicProfile`; objeto `profile` com `get()` e `update()`; `adminDashboard.demographics()`.
- **`frontend/src/components/hud/ProfileCompletionCard.tsx`**: card colapsável no dashboard — exibido quando perfil não está completo; formulário com todos os campos demográficos; barra de progresso; nota LGPD; botão "Não mostrar mais" persiste em localStorage.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: painel "Perfis Demográficos" na aba Visão Geral — taxa de completion, top países, distribuição por tipo de jogo e faixa de buy-in.

### Changed
- **`frontend/src/pages/Index.tsx`**: `ProfileCompletionCard` inserido entre `DailyFocusCard` e `SessionGoalPanel`.
- **`backend/api/app.py`**: `/auth/me` passa a retornar `profile_completed_at`.

---

## [v0.65.0] — 2026-05-03 — Sprint AH: BACK-018 Coach Application Flow

### Added
- **`backend/database/schema.py`**: tabela `coach_applications` (user_id, instagram_handle, bio, specialties, experience_years, biggest_results, status pending/approved/rejected, admin_note, reviewed_at).
- **`backend/database/repositories.py`**: `create_coach_application`, `get_coach_applications`, `approve_coach_application`, `reject_coach_application`, helper `_now()`.
- **`backend/leaklab/email_digest.py`**: helper `send_transactional_email(to_email, subject, html_body)` reutilizando a infra SMTP do digest.
- **`backend/api/app.py`**: `POST /auth/coach-apply` (público, rate-limited 5/min) — cria usuário com role `coach_pending` + registro de candidatura. `GET /admin/coach-applications` + `POST /admin/coach-applications/<id>/approve` + `POST /admin/coach-applications/<id>/reject` — gestão pelo admin com envio de e-mail automático.
- **`frontend/src/pages/CoachApply.tsx`**: formulário público de candidatura (username, @instagram, email, senha, bio ≥30 chars, especialidades, anos de experiência, maiores resultados) com estado de confirmação.
- **`frontend/src/lib/api.ts`**: interface `CoachApplication`, métodos `adminDashboard.coachApplications`, `approveApplication`, `rejectApplication`; `coachApplyApi.apply`.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: aba "Candidaturas" com filtro por status, linhas expansíveis (bio/especialidades/resultados), botões aprovar/rejeitar com nota opcional.
- **`frontend/src/App.tsx`**: rota pública `/coach-apply`.

### Changed
- **`backend/api/app.py`**: `POST /auth/register` com `role: coach` retorna 400 — coaches devem usar `/auth/coach-apply`.
- **`backend/api/app.py`**: `POST /auth/login` com role `coach_pending` retorna 403 com `code: 'coach_pending'`.
- **`frontend/src/pages/Login.tsx`**: botão "Coach" na aba de registro redireciona para `/coach-apply`; mensagem de erro `coach_pending` tratada com texto específico.

### Fixed
- **`frontend/src/pages/coach/StudentDetail.tsx`**: Feed de Atividade exibia `standard_pct` multiplicado por 100 (ex.: 83% aparecia como 8300%). Removida duplicação de `* 100`.

---

## [v0.64.0] — 2026-05-03 — Sprint AF: UX-014 StudentDetail + CoachDashboard wide layout

### Changed
- **`frontend/src/pages/coach/StudentDetail.tsx`**: container `max-w-5xl` → `max-w-[1440px] px-4 md:px-8` (consistente com o dashboard principal). `OverviewTab` reestruturado para grid `lg:grid-cols-12` — coluna principal (8-col) com LevelCard + HUD stats + evolution chart + comparativo; aside (4-col) com Principais Leaks + Performance por Street + Performance por Posição. Evolution chart aumentado de 200px para 220px de altura.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: mesma atualização de container `max-w-5xl` → `max-w-[1440px] px-4 md:px-8`.

---

## [v0.63.0] — 2026-05-03 — Sprint AF-fix: Dashboard layout holes

### Fixed
- **`frontend/src/pages/Index.tsx`**: GhostDrillCard, PressureProfileCard e IcmBreakdown movidos para dentro da coluna principal (8-col) como subgrid `md:grid-cols-3` abaixo do PlayerDnaCard — elimina o "buraco" visual causado pela quebra de ritmo entre o grid 8+4 e o antigo row 4-col. AI Confidence card retorna para o aside, mantendo o painel lateral com conteúdo até o final.

---

## [v0.62.0] — 2026-05-03 — Sprint AF: Dashboard card reposition

### Changed
- **`frontend/src/pages/Index.tsx`**: GhostDrillCard, PressureProfileCard, IcmBreakdown e AI Confidence movidos da aside (4 col) para uma nova row full-width abaixo do grid principal, em `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`. Aside agora contém apenas LeaksPanel, LeakCausalMap e LevelCard — os cards analíticos mais críticos.

---

## [v0.61.0] — 2026-05-03 — Sprint AE: UX-013 "JAM" → "All In" na camada de display

### Added
- **`frontend/src/lib/utils.ts`**: função `formatAction(a: string)` — mapeia `"jam"` → `"All In"`, capitaliza demais ações. Identificadores internos do backend permanecem inalterados.

### Changed
- **`frontend/src/pages/GhostTable.tsx`**: `.toUpperCase()` direto nos valores de ação substituído por `formatAction(...).toUpperCase()` em 4 locais (originalMistake, bestAction subtitle, yourAction card, bestAction card).
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: `{d.action_taken}` e `{d.best_action}` na tabela de decisões encapsulados com `formatAction()`.
- **`frontend/src/pages/coach/StudentDetail.tsx`**: mesma correção nas duas tabelas de decisões e no card de detalhe (6 ocorrências).
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: tooltip de Flop Bet atualizado de "bet/raise/jam" para "bet/raise/all-in".

---

## [v0.60.0] — 2026-05-03 — Sprint AD: UX-012 Remove recent tournaments from dashboard

### Removed
- **`frontend/src/pages/Index.tsx`**: `RecentTournamentsTable` removido do dashboard — o menu /tournaments já serve essa função. O estado `tourns` e o fetch de `tournaments.list()` permanecem para os cálculos de KPI (ROI, ITM, Total Eventos, Total Mãos).

---

## [v0.59.0] — 2026-05-03 — Sprint AC: UX-011 Dashboard title/subtitle

### Changed
- **`frontend/src/i18n/locales/pt-BR|en|es/dashboard.json`**: `title` e `titleDefault` passam de "{{name}} — Centro de Comando / Command Center / Centro de Mando" para simplesmente `"Dashboard"` nos três idiomas. Subtitle encurtado para caber em uma linha sem quebra em viewports comuns.
- **`frontend/src/pages/Index.tsx`**: `<h1>` simplificado — removida interpolação `{name}` e o fallback `titleDefault`; ambas as keys agora retornam `"Dashboard"`.

---

## [v0.58.0] — 2026-05-03 — Sprint AB: UX-010 Bankroll period filters

### Fixed
- **`frontend/src/components/hud/BankrollChart.tsx`**: filtros de período (1M/3M/1Y/Tudo) agora funcionam — componente passou a ser self-contained, gerencia seu próprio estado de período e busca os dados via `useQuery` com o número correto de dias (30/90/365/3650). Botão ativo destacado corretamente. Spinner overlay durante refetch. Prop `evolution` removida (o componente não depende mais do parent para dados).
- **`frontend/src/pages/Index.tsx`**: `<BankrollChart>` sem prop — componente busca seus próprios dados.
- **`backend/requirements.txt`**: `python-dotenv==1.0.1` adicionado — estava faltando, causando `ModuleNotFoundError: No module named 'dotenv'` no boot do Gunicorn no Render.

---

## [v0.57.0] — 2026-05-03 — Sprint AA: INFRA-001 Build + display bugs

### Fixed
- **`vercel.json`**: substituído config quebrado `@vercel/static-build` com rotas `"/frontend/$1"` pelo formato moderno — `buildCommand` + `outputDirectory` + `rewrites` apontando tudo para `/index.html`; corrige roteamento do React Router em produção.
- **`backend/leaklab/email_digest.py`**: variável de ambiente do token de unsubscribe corrigida de `JWT_SECRET_KEY` para `LEAKLAB_SECRET` (alinhado com `database/auth.py` e `render.yaml`).
- **`frontend/src/pages/AICoach.tsx`**: `standard_pct` no painel de contexto exibia valor multiplicado por 100 duas vezes (ex: 85.18 → 8518%). O endpoint retorna já em % — removida a multiplicação `* 100` incorreta.

---

## [v0.56.0] — 2026-05-03 — Sprint Z: UX-009 Tournament date display

### Changed
- **`frontend/src/pages/Tournaments.tsx`**: `formatDate` agora exibe ano de 2 dígitos (`DD/MM/YY`) quando o torneio é de ano anterior ao atual — torneios do ano corrente continuam como `DD/MM`. Novo componente `TournamentDate` distingue visualmente `played_at` (data real do torneio) de `imported_at` (data de importação): quando `played_at` não está disponível, exibe a data de importação com label "importado" em tom reduzido. Aplicado na tabela desktop e nos cards mobile.

---

## [v0.55.0] — 2026-05-03 — Sprint Y: UX-008 Coaches Directory mobile + terminologia

### Changed
- **`frontend/src/pages/CoachesDirectory.tsx`**: layout mobile corrigido — filtros movidos para painel colapsável com toggle (botão mostra contagem de filtros ativos); sidebar visível apenas em `lg+`; grid muda de `md:grid-cols-2` para `sm:grid-cols-2` para usar melhor o espaço; `min-w-0` na coluna do grid evita overflow.
- **`frontend/src/pages/Login.tsx`**: seletor de role na tela de registro: "Professor" → "Coach".
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: título "Dashboard do Professor" → "Dashboard do Coach".
- **`frontend/src/i18n/locales/pt-BR/dashboard.json`**: banner de vínculo: "Tem um professor?" → "Tem um coach?".
- **`frontend/src/components/hud/AcceptCoachModal.tsx`**: 3 ocorrências de "professor" substituídas por "coach" (título do modal, mensagem de instrução, confirmação de sucesso).

---

## [v0.54.0] — 2026-05-03 — Sprint W: FEAT-11 Weekly Digest Email

### Added
- **`backend/leaklab/email_digest.py`**: módulo de digest semanal — `build_digest_data` (coleta métricas dos últimos 7 dias: standard%, EV loss, drill atrasado, precisão), `build_digest_html` (template dark responsivo com EV bar visual), `send_digest_email` (SMTP via smtplib nativo com STARTTLS), `run_weekly_digest` (itera inscritos e envia). Sem dependências extras além da stdlib.
- **`backend/database/schema.py`**: coluna `digest_subscribed INTEGER NOT NULL DEFAULT 0` na tabela `users` (SQLite + Postgres migration).
- **`backend/database/repositories.py`**: `get_digest_subscribers` (usuários com `digest_subscribed=1` e `last_login` nos últimos 30 dias), `update_digest_subscription`.
- **`backend/api/app.py`**: `POST /player/digest/subscribe`, `POST /player/digest/unsubscribe` (autenticado), `GET /player/digest/unsubscribe` (link do email com token HMAC), `POST /admin/send-digest`; campo `digest_subscribed` incluído na resposta de `/auth/me`.
- **`frontend/src/lib/api.ts`**: campo `digest_subscribed` em `UserProfile`; módulo `digest` com `subscribe()` e `unsubscribe()`.
- **`frontend/src/pages/Index.tsx`**: banner de opt-in contextual — visível para players com dados que ainda não ativaram o digest; dispensável pelo X; botão "Ativar" chama `digest.subscribe()` e atualiza o perfil via `refreshUser()`.

---

## [v0.53.0] — 2026-05-03 — Sprint V: FEAT-09 Coach Templates + FEAT-10 Coach Messaging

### Added
- **`backend/database/schema.py`**: tabela `coach_plan_templates` (id, coach_id, name, target_archetype, cards_json) e `coach_messages` (id, coach_id, student_id, body, sender_role, decision_id, read_at) — SQLite + Postgres.
- **`backend/database/repositories.py`**: `get_coach_templates`, `create_coach_template`, `delete_coach_template`; `send_coach_message`, `get_coach_messages`, `mark_messages_read`, `get_unread_message_count`.
- **`backend/api/app.py`**: endpoints `GET/POST /coach/templates`, `DELETE /coach/templates/<id>`; `GET/POST /coach/student/<id>/messages`; `GET/POST /player/coach/messages`, `GET /player/messages/unread`.
- **`frontend/src/lib/api.ts`**: interfaces `CoachTemplate`, `CoachMessage`; métodos em `coachDashboard` (getTemplates, createTemplate, deleteTemplate, getMessages, sendMessage); módulo `playerMessages` (list, send, unreadCount).
- **`frontend/src/pages/coach/StudentDetail.tsx`**: aba "Mensagens" com chat bidirecional em tempo real (polling 15s), badge de não lidas na aba, botão "Salvar como template" nos cards substituídos do plano de estudos.
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: painel colapsável de chat para o player na página do AI Coach — mostra conversa com coach humano vinculado, badge de não lidas, envio via Enter.
- **`frontend/src/pages/AICoach.tsx`**: `CoachMessagesPanel` integrado na sidebar, visível apenas quando `user.coach_id` está presente.
- **`frontend/src/components/hud/HudHeader.tsx`**: badge de não lidas no header (ícone `MessageSquare` com contador) para players com coach vinculado — polling 60s, link para `/coach`.

---

## [v0.52.0] — 2026-05-03 — Sprint U: FEAT-08 Session Goals + AI Review

### Added
- **`backend/database/schema.py`**: tabela `session_goals` (SQLite + Postgres) — `id`, `user_id`, `goal_leak_spot`, `target_standard_pct`, `notes`, `tournament_id` (nullable), `llm_review`, `created_at`, `linked_at`.
- **`backend/database/repositories.py`**: `create_session_goal`, `link_session_goal`, `get_pending_session_goal`, `get_session_goal_by_tournament`, `save_session_review`.
- **`backend/leaklab/llm_explainer.py`**: `generate_session_review(goal, tournament)` — Claude Haiku (~300 tokens) compara meta pré-sessão com resultado real; 3 frases: atingiu/não atingiu meta, ponto técnico relevante, recomendação para próxima sessão. Fallback `_template_session_review` determinístico.
- **`backend/api/app.py`**: endpoints `POST /player/session-goals`, `GET /player/session-goals/pending`, `POST /player/session-goals/<id>/link`, `GET /player/session-review/<tournament_id>` (gera e persiste review on-demand).
- **`frontend/src/lib/api.ts`**: interfaces `SessionGoal`, `SessionReviewResponse`; métodos `metrics.createSessionGoal`, `metrics.pendingSessionGoal`, `metrics.linkSessionGoal`, `metrics.sessionReview`.
- **`frontend/src/components/hud/UploadQueue.tsx`**: `SessionGoalPanel` exportado — painel colapsável com campos spot de foco, meta de standard% e anotação livre; persiste goal ID em `sessionStorage`; hook `useUploadQueue` lê `ll_pending_goal` do `sessionStorage` após upload e chama `metrics.linkSessionGoal` automaticamente.
- **`frontend/src/pages/Index.tsx`**: `SessionGoalPanel` integrado ao dashboard (visível apenas para players).
- **`frontend/src/pages/TournamentDetail.tsx`**: card "Review da Sessão" exibido após narrativa quando há meta vinculada — mostra spot de foco, meta vs resultado real com indicador ✓/✗, review gerado por IA e anotação livre do jogador.

---

## [v0.51.0] — 2026-05-03 — Sprint T: FEAT-07 Coach Effectiveness Metrics

### Added
- **`backend/database/repositories.py`**: `get_coach_effectiveness_report(coach_id)` — itera todos os alunos com baseline, chama `get_baseline_comparison` por aluno, calcula delta de `standard_pct`, melhora mediana, % com melhora positiva e badge público (visível com ≥3 alunos e mediana positiva).
- **`backend/api/app.py`**: endpoint `GET /coach/effectiveness` (autenticado como coach). Perfil público `GET /coaches/<id>` passa a incluir `effectiveness_badge` e `effectiveness_median_delta`.
- **`frontend/src/lib/api.ts`**: interfaces `EffectivenessStudent`, `EffectivenessSummary`, `CoachEffectivenessReport`; módulo `coachEffectiveness` com método `report()`.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: aba "Efetividade" com 3 KPI cards (alunos analisados, melhora mediana, % com melhora), preview do badge público com indicação "visível no perfil público", tabela por aluno com before/after `standard_pct`, delta colorido e leaks corrigidos.
- **`frontend/src/pages/PublicCoachProfile.tsx`**: badge "Alunos melhoram +Xpp em standard_pct" exibido na seção de badges do perfil público quando disponível.

---

## [v0.50.0] — 2026-05-03 — Sprint S: FEAT-06 Leak Causal Map

### Added
- **`backend/leaklab/leak_causal_graph.py`**: `build_leak_graph(rows)` — analisa co-ocorrência de leaks entre torneios, calcula correlação de Jaccard por par (threshold 35%), retorna nós com `severity` (critical/moderate/minor por avg_score) e arestas ordenadas por correlação; label compacto (`PF Fold`, `FL Bet`, etc.); nós incluem `degree` (número de conexões).
- **`backend/leaklab/llm_explainer.py`**: `explain_leak_causality(edges, hero)` — 1 chamada Claude Haiku (~150 tokens) gerando 2-3 frases de diagnóstico causal para os 3 pares mais correlacionados; cache em memória por combinação de pares; fallback `_template_causality()` determinístico.
- **`backend/database/repositories.py`**: `get_leak_graph_data(user_id, days)` — busca todas as decisões com mistake do usuário no período, chama `build_leak_graph` e `explain_leak_causality`, retorna `{nodes, edges, narrative}`.
- **`backend/api/app.py`**: endpoint `GET /player/leak-graph?days=90`.
- **`frontend/src/lib/api.ts`**: interfaces `LeakGraphNode`, `LeakGraphEdge`, `LeakGraphResponse`; método `metrics.leakGraph(days)`.
- **`frontend/src/components/hud/LeakCausalMap.tsx`**: card com grafo SVG circular — nós coloridos por severidade (vermelho/âmbar/verde), arestas com espessura e opacidade proporcionais à correlação; interação: clique no nó destaca suas conexões e exibe detalhe com lista de co-ocorrências; narrativa LLM abaixo do grafo; legenda de cores.
- **`frontend/src/pages/Index.tsx`**: `LeakCausalMap` inserido após `LeaksPanel` quando há ≥ 3 nós; `metrics.leakGraph(90)` carregado no mount.

---

## [v0.49.0] — 2026-05-03 — Sprint R: FEAT-05 SRS Adaptativo nos Drills

### Added
- **`backend/database/schema.py`**: colunas `next_drill_at TEXT` e `srs_interval_days INTEGER DEFAULT 3` em `drill_sessions` (Postgres + SQLite migrations).
- **`backend/database/repositories.py`**: `save_drill_session` reescrito com lógica SRS — acerto dobra o intervalo (`3d → 7d → 14d → 28d → 60d`, cap em 60), erro reseta para 3 dias; calcula `next_drill_at = now + interval` e persiste ambos os campos. `get_drill_spots` reescrito — substitui filtro de `drilled_at >= 7 days` por LEFT JOIN na sessão mais recente por decisão, filtra por `next_drill_at IS NULL OR next_drill_at <= now`, ordena por mais atrasado primeiro; calcula `days_overdue` em Python (compatível SQLite + Postgres).
- **`backend/api/app.py`**: endpoint `POST /player/spots/drill/submit` passa a retornar `next_drill_at` e `srs_interval_days`.
- **`frontend/src/lib/api.ts`**: `DrillSpot` com campos `next_drill_at`, `srs_interval_days`, `days_overdue`; `DrillSubmitResult` com `next_drill_at` e `srs_interval_days`.
- **`frontend/src/pages/GhostTable.tsx`**: badge "próxima revisão em X dias" (verde=acerto, amarelo=reset) no card de resultado após cada drill; badge de dias de atraso discreto (vermelho/amarelo) na barra de progresso do spot ativo.
- **`frontend/src/components/hud/GhostDrillCard.tsx`**: prop `pendingSpots` opcional — exibe contador "N atrasados" com ícone Clock no header do card quando há spots vencidos.
- **`frontend/src/pages/Index.tsx`**: carrega `drill.spots({ limit: 20 })` no mount e passa `pendingSpots` para `GhostDrillCard`.

---

## [v0.48.0] — 2026-05-03 — Sprint Q: FEAT-02 Daily Focus + FEAT-03 XP Server-Side

### Added
- **`backend/database/schema.py`**: migrações para `xp_total INT DEFAULT 0`, `xp_streak INT DEFAULT 0`, `xp_last_activity DATE`, `daily_focus_done_at DATE` na tabela `users`; nova tabela `achievements` (`user_id`, `achievement_id`, `unlocked_at`).
- **`backend/database/repositories.py`**: `get_daily_focus(user_id)` — lógica determinística (zero LLM) que combina top EV-loss leak, drill com cooldown expirado e torneio não revisado; retorna `{primary, secondary[], valid_until, completed, streak}`. `mark_daily_focus_done(user_id)` — persiste data de conclusão. `add_xp(user_id, event_type, amount?)` — streak server-side: +1 se último XP foi ontem, reset se mais antigo; checa conquistas automaticamente via `_check_and_grant_achievements()`. `get_xp_status(user_id)`, `get_achievements(user_id)`. `_XP_AMOUNTS` (`tournament_imported=50`, `exercise_correct=10`, `drill_completed=25`, `drill_mastered=100`). 5 conquistas: `first_tournament`, `decisions_100`, `first_drill`, `streak_7`, `tournaments_10`.
- **`backend/api/app.py`**: 5 novos endpoints — `GET /player/daily-focus`, `POST /player/daily-focus/complete`, `GET /player/xp`, `POST /player/xp`, `GET /player/achievements`.
- **`frontend/src/components/hud/DailyFocusCard.tsx`**: card de foco diário — exibe ação primária e 2 secundárias com link direto; timer countdown até meia-noite; estado "concluído" com streak de dias; usa `useQuery` + `useMutation` via React Query.
- **`frontend/src/lib/api.ts`**: interfaces `DailyFocusData`, `DailyFocusAction`, `XpStatus`, `Achievement`; métodos `metrics.dailyFocus()`, `metrics.completeDailyFocus()`, `metrics.xpStatus()`, `metrics.addXp(event_type)`, `metrics.achievements()`.
- **`frontend/src/pages/Index.tsx`**: `DailyFocusCard` inserido acima da seção de KPIs (visível apenas quando há torneios importados).
- **`frontend/src/pages/StudyPlan.tsx`**: `metrics.addXp("exercise_correct")` disparado a cada resposta correta em exercício (fire-and-forget).
- **`frontend/src/components/hud/UploadQueue.tsx`**: `metrics.addXp("tournament_imported")` disparado após upload bem-sucedido de torneio.

---

## [v0.47.0] — 2026-05-03 — Sprint P: FEAT-04 Relatório PDF Premium

### Added
- **`backend/leaklab/report_generator.py`**: redesign completo — `build_html_report(t, decisions, phases, hero)` gera template HTML premium com Inter/JetBrains Mono (Google Fonts), paleta dark profissional, gráficos CSS puros (barras, indicadores de score coloridos por threshold). Seções: capa com hero + torneio + meta pills, KPI row (Standard%, Avg Score, Clear Mistakes%, Decisões), Quality Distribution com barras + referência MTT saudável, Phase Breakdown (Deep/Mid/Short Stack/Push/Fold), Top 5 Leaks com barra proporcional e score colorido, Performance por ICM Pressure, Top 10 Decisões Críticas com label badges.
- **`generate_pdf_bytes(html)`**: converte HTML para PDF via WeasyPrint; levanta `ImportError` se a lib não estiver disponível — o endpoint faz fallback automático para download HTML.
- **`backend/Dockerfile`**: adicionadas dependências de sistema para WeasyPrint — `libpango`, `libcairo2`, `libgdk-pixbuf2.0-0`, `libpangocairo`, `libffi-dev`, `fonts-liberation`.
- **`render.yaml`**: migrado de `runtime: python` para `runtime: docker` (necessário para instalar as dependências de sistema do WeasyPrint no Render).
- **`backend/requirements.txt`**: `weasyprint==62.3`.
- **`backend/api/app.py`**: endpoint `GET /history/tournament/<id>/report.pdf` — retorna PDF (`application/pdf`) ou HTML como fallback se WeasyPrint não disponível; `Content-Disposition: attachment`.
- **`frontend/src/lib/api.ts`**: `tournaments.downloadReport(tournamentId)` — fetch binário com auth header, cria blob URL e dispara download automaticamente.
- **`frontend/src/pages/TournamentDetail.tsx`**: botão "PDF" (ícone `FileDown`) ao lado do botão Replay; estado `pdfDownloading` com spinner enquanto gera.

### Changed
- **`backend/leaklab/report_generator.py`**: `generate_report()` (legacy) mantida e intacta para compatibilidade com callers existentes.

---

## [v0.46.0] — 2026-05-03 — Sprint O: FEAT-01 Comparativo de Torneios

### Added
- **`backend/database/repositories.py`**: `get_tournaments_comparison(user_id, ids)` — agrega por torneio: `standard_pct`, `avg_score`, `clear_pct`, hands/decisions count, profit, buy_in, place, phase breakdown e top 5 leaks; `_compute_comparison_leaks(decisions)` — calcula média de score por spot para o ranking de leaks.
- **`backend/leaklab/llm_explainer.py`**: `generate_comparison_narrative(items)` — narrativa comparativa de 2 frases via Claude Haiku (max 100 tokens); cache por `cmp_{id1}_{id2}...`; fallback `_template_comparison()` calcula delta de `standard_pct` entre primeiro e último torneio.
- **`backend/api/app.py`**: endpoint `GET /history/tournaments/compare?ids=A,B,C` — valida 2–4 IDs, retorna `{items: TournamentComparison[], narrative}`.
- **`frontend/src/lib/api.ts`**: interface `TournamentComparison` e método `tournaments.compare(ids)`.
- **`frontend/src/pages/TournamentCompare.tsx`**: página de comparativo lado a lado — componentes `Delta` (trend ±) e `QualityBar` (barra colorida por threshold); seções: narrativa LLM, cards de cabeçalho por torneio, tabela de qualidade (Standard%/Avg Score/Clear Mistakes%), phase breakdown (Deep/Mid/Short Stack/Push-Fold), top leaks com destaque amarelo para leaks compartilhados entre torneios; badge "▲ melhor" no melhor valor de cada métrica.
- **`frontend/src/pages/Tournaments.tsx`**: multi-seleção de 2–4 torneios via checkboxes (desktop e mobile); CTA "Comparar N torneios" com ícone aparece ao selecionar ≥ 2 itens; navega para `/tournaments/compare?ids=...`.
- **`frontend/src/App.tsx`**: rota `/tournaments/compare` adicionada antes de `/tournaments/:id`.
- **`backend/database/repositories.py`**: labels de fase de M-ratio padronizadas para inglês — `Deep Stack`, `Mid Stack`, `Short Stack`, `Push/Fold` (era PT-BR).

### Changed
- **`frontend/src/pages/TournamentDetail.tsx`**: tooltips das fases atualizados para inglês (Deep Stack / Mid Stack / Short Stack / Push/Fold).

---

## [v0.45.0] — 2026-05-03 — Sprint M: PERF-008 Tournament Narrative Engine

### Added
- **`backend/leaklab/llm_explainer.py`**: `generate_tournament_narrative(tournament_id, ctx)` — gera 2-3 frases descrevendo o arco de qualidade da sessão via Claude Haiku (max 130 tokens); cache em memória por `tournament_id`; fallback determinístico `_template_narrative()` se LLM indisponível.
- **`backend/api/app.py`**: endpoint `GET /history/tournament/<id>/narrative` — retorna `{narrative, quality_level}` (solid/regular/poor derivado de `standard_pct`); helper `_build_narrative_context()` agrega label counts, top leaks, ICM breakdown e pior fase do torneio.
- **`frontend/src/lib/api.ts`**: `tournaments.narrative(id)` → `{narrative, quality_level}`.
- **`frontend/src/pages/TournamentDetail.tsx`**: seção "Narrativa da Sessão" inline (entre stats grid e phase analysis) — badge de qualidade colorido + texto narrativo gerado pelo LLM, carregado automaticamente ao abrir o torneio.
- **`frontend/src/i18n/locales/*/tournaments.json`**: chaves `detail.narrative.*` em PT-BR, EN e ES.

---

## [v0.44.0] — 2026-05-03 — UX: LeaksPanel layout + PlayerDnaCard radar fix

### Changed
- **`LeaksPanel.tsx`**: redesign do layout de cada item — nome do leak em linha própria (sem truncate), badges reorganizadas com `justify-between` — n× badge e EV loss à esquerda como grupo, botão **Estudar** sempre ancorado à direita; elimina hack de `flex-1` spacer e overflow em cards com muitos badges simultâneos.
- **`PlayerDnaCard.tsx`**: corrige label "Disciplina" cortada no gráfico radar — `outerRadius="65%"` + margens aumentadas (`top:15 right:35 bottom:20 left:35`); remove `truncate` desnecessário nas labels do grid de stats.

---

## [v0.43.0] — 2026-05-03 — Sprint L: PERF-007 Decision DNA

### Backend — PERF-007

- **`repositories.py`** — `get_player_dna(user_id, days)`: agrega `decisions` em 5 métricas normalizadas (0-100):
  - `aggression_index` — % de ações que são raise/bet/jam (excluindo folds)
  - `fold_frequency` — % global de folds
  - `three_bet_pct` — % de preflop decisions com `is_3bet = True`
  - `positional_awareness` — diferencial de agressividade BTN/CO vs UTG/EP (escala 0-100, 50 = neutro)
  - `discipline` — standard% geral
  - `icm_awareness` (opcional) — ratio de standard% sob alta pressão ICM vs sem pressão ICM
  - `_classify_archetype()`: classifica em TAG / LAG / Nit / Calling Station / Balanced a partir das métricas
- **`app.py`** — `GET /player/dna?days=N`: retorna `{dna, sample_size}`; requer auth

### Frontend — PERF-007

- **`PlayerDnaCard.tsx`** (novo) — card com radar chart pentagon (Recharts RadarChart), badge de arquétipo colorido por tipo, grid de 6 métricas, descrição contextual do arquétipo; estado vazio com mensagem quando sample_size < 10
- **`pages/Index.tsx`** — fetch paralelo de `metrics.dna(90)`; `<PlayerDnaCard>` inserido entre o grid `RecentForm+DecisionQuality` e `BankrollChart`
- **`lib/api.ts`** — interfaces `PlayerDna`, `PlayerDnaResponse`; `metrics.dna(days)`

### i18n — 3 locales (pt-BR / en / es)

- `dashboard.json` — seção `dna.*`: title, tooltip, archetype label, sampleSize, noData, 6 axis labels, 5 archetype names + descriptions

### BACKLOG

- Sprint L (PERF-007) concluída; Sprint M (PERF-008 Tournament Narrative) e Sprint N (PERF-009 GGPoker Parser) aguardam priorização

---

## [v0.42.0] — 2026-05-03 — Sprint K pt.2: Ghost Table UX + Engine Notes + Drill-Dashboard Loop

### Backend — Ghost Table enhancements

- **`schema.py`** — colunas `pot_size REAL` e `facing_bet REAL` adicionadas à tabela `decisions` (SQLite + PostgreSQL, com migration automática)
- **`repositories.py`** — `save_decisions()`: extrai `potSize`/`facingSize` do `spot` e armazena em BB dividindo por `level_bb`; `get_drill_spots()`: inclui `pot_size` e `facing_bet` no SELECT; `get_decision_for_drill()`: expandido para retornar todos os campos necessários pelo `analyze_single_decision()`; `get_leak_roi_impact()`: JOIN com `drill_sessions` — adiciona `drill_count` e `drill_accuracy` por spot
- **`app.py`** — Bug fix crítico em `_analyze_hands()`: `enriched` dict agora inclui `'spot': di['spot']` (sem isso `pot_size`/`facing_bet` eram sempre `None`); `_GENERIC_NOTES` + `_enrich_note(row)`: detecta 3 strings genéricas legadas e as substitui por notas específicas geradas dos campos do banco (street, position, stack_bb, facing_bet, pot_size, m_ratio, ICM, label, score, action gap); aplicado em `history_tournament` e `coach_student_tournament`; novo endpoint `GET /player/drill-stats` (resumo leve sem carregar spots); novo endpoint `GET /player/spots/drill/<id>/analysis` com cache na tabela `llm_cache` (chave `drill_analysis:{decision_id}`) — chama Claude Haiku apenas na primeira vez
- **`decision_engine_v11.py`** — `build_interpretation()` reescrito: notas vazias para `standard`/`marginal`; para `small_mistake`/`clear_mistake` gera nota específica usando equity diff, draw context, M-Ratio zone, ICM pressure, range zone + position, facing bet context; sempre termina com "Ação esperada: X."

### Frontend — Ghost Table UX

- **`GhostTable.tsx`** — board cards limitados por street (preflop = 0, flop = 3, turn = 4, river = 5) para não revelar cartas futuras; `pot_size` e `facing_bet` em BB adicionados ao SituationBox; nota do motor movida da fase `active` para a fase `result` (não influencia decisão); renomeado "Análise da IA" → "Análise do Motor"; botão "Ver análise desta mão" (BookOpen) na fase result com `requestAnalysis()` → `drill.analysis(id)`; estado `analysis` e `analysisLoading` gerenciados; ações "JAM" renomeadas para "All-In" nas 3 locales
- **`GhostDrillCard.tsx`** (novo) — card sidebar no dashboard: mostra total de spots treinados, acerto %, avg delta dos últimos 30 dias; estado vazio com CTA "Iniciar drill" para `/ghost`
- **`LeaksPanel.tsx`** — badge "Treinando" (cinza) ou "Dominando" (primária) quando `drill_count > 0`; badge "Crítico" ocultado quando spot em treino; tooltip mostra `Ghost Table: Nx treinado (X% acerto)`
- **`pages/Index.tsx`** — fetch paralelo de `metrics.drillStats(30)`; `<GhostDrillCard stats={drillStats} />` inserido entre LevelCard e LeaksPanel

### i18n — 3 locales (pt-BR / en / es)

- **`ghost.json`** — chaves: `context.pot`, `context.facing`, `result.engineNote`, `result.requestAnalysis`, `result.analysisLoading`, `result.analysisError`, `situation.*`; `actions.jam` → "All-In"
- **`dashboard.json`** — chaves: `leaks.drillPracticing`, `leaks.drillMastering`, `ghost.title`, `ghost.spots`, `ghost.accuracy`, `ghost.continueStudy`, `ghost.noActivity`, `ghost.startNow`

### Removido

- **`backend/leaklab/mercadopago_gateway.py`** — arquivo legado do gateway Mercado Pago (migrado para Stripe em v0.29.0); removido para limpar o repositório

---

## [v0.41.0] — 2026-05-03 — Sprint K: PERF-006 Ghost Table Simulator MVP

### Backend — PERF-006
- `schema.py` — `drill_sessions` table (id, user_id, decision_id, new_action, new_score, original_score, delta, drilled_at) — SQLite + PostgreSQL
- `repositories.py` — `get_drill_spots()`: fetches undrilled mistake decisions (7-day cooldown); `save_drill_session()`: persists re-decision with score delta; `get_drill_stats()`: 30-day accuracy/total/avg_delta; `get_decision_for_drill()`: ownership-verified decision fetch
- `app.py` — `GET /player/spots/drill`: returns spots + stats; `POST /player/spots/drill/submit`: evaluates new_action vs best_action, scores 0.02 if correct else original_score

### Frontend — PERF-006
- `GhostTable.tsx` — full drill page with state machine (intro → loading → active → result → done): spot context card (street/ICM/position/stack/M-ratio/cards/board), 6 action buttons, result reveal, session accuracy, done screen
- `App.tsx` — `/ghost` route with `ProtectedRoute`
- `HudHeader.tsx` — "Ghost Table" nav item (Swords icon) for playerNavItems
- `i18n/locales/[pt-BR|en|es]/ghost.json` — new namespace (63 keys: drill UI, actions, result messages, stats)
- `i18n/locales/[pt-BR|en|es]/common.json` — `nav.ghost` key added
- `api.ts` — `DrillSpot`, `DrillStats`, `DrillSubmitResult` interfaces + `drill.spots()` + `drill.submit()`

---

## [v0.40.0] — 2026-05-03 — Sprint J: PERF-003+004+005 Leak Progression + Pressure Collapse + Drift

### Backend — PERF-003: Leak Progression (trend)

- **`repositories.py`** — `get_leak_roi_impact()` estendido: compara avg_score dos últimos 30 dias vs. 30-60 dias anteriores por spot; retorna `trend`: `improving` / `stagnant` / `regressing` / `new`

### Backend — PERF-004: Pressure Collapse Detection

- **`repositories.py`** — `get_pressure_profile(user_id, days)`: baseline score geral + avg_score por `icm_pressure`; calcula `collapse_delta = score_high - score_none`; flag `has_collapse` se delta > 0.08
- **`app.py`** — `GET /player/pressure-profile`

### Backend — PERF-005: Confidence Drift Monitor

- **`repositories.py`** — `get_confidence_drift(user_id, days=30)`: detecta torneios com avg_score > baseline × 1.30; retorna `drift_detected`, `severity` (mild/moderate/severe), lista de sessões afetadas
- **`app.py`** — `GET /player/confidence-drift`

### Frontend — Sprint J completo

- **`lib/api.ts`** — interfaces `PressureProfile`, `ConfidenceDrift`; `metrics.pressureProfile()`, `metrics.confidenceDrift()`; `LeakRoiData` expandido com campo `trend`
- **`components/hud/PressureProfileCard.tsx`** — novo card: barras de mistake_score por pressão ICM, badge "Colapso" / "Sólido", delta summary
- **`components/hud/LeaksPanel.tsx`** — ícones de tendência (↓ melhorando / → estagnado / ↑ regredindo) por leak
- **`pages/Index.tsx`** — fetch paralelo de `pressureProfile` + `confidenceDrift`; banner de alerta dismissível quando drift detectado; `PressureProfileCard` no sidebar
- **Locales** — chaves `pressure.*`, `drift.*` e `leaks.trend*` adicionadas a `dashboard.json` (PT-BR + EN + ES)

## [v0.39.0] — 2026-05-03 — Sprint I: PERF-001 + PERF-002 ROI Attribution + Leak Priority

### Backend — PERF-001: ROI Attribution Engine

- **`repositories.py`** — `get_leak_roi_impact(user_id, days)`: query enriquecida com `AVG(t.buy_in)`, `priority_score = n × avg_score`, `ev_loss_monthly = (n×30/days) × avg_score × avg_buy_in × 0.10`; ordenada por `priority_score DESC`
- **`app.py`** — `GET /player/leak-roi`: endpoint protegido por `@require_auth`; importa `get_leak_roi_impact`

### Frontend — PERF-001 + PERF-002

- **`lib/api.ts`** — interface `LeakRoiData` com campos `ev_loss_monthly`, `priority_score`, `priority_rank`; `metrics.leakRoi(days)`
- **`pages/Index.tsx`** — fetch paralelo de `leakRoi`; passa ao `LeaksPanel` quando disponível
- **`components/hud/LeaksPanel.tsx`** — custo mensal estimado por leak (`~$X/mês`); badge `CRÍTICO` com ícone chama para `priority_rank ≤ 3`
- **Locales** — chaves `leaks.critical` e `leaks.evLoss` adicionadas a `dashboard.json` (PT-BR + EN + ES)

### Backlog

- **`BACKLOG.md`** — roadmap atualizado com Sprint I (🔄), J, K (📋); specs completos de PERF-001 a PERF-006

## [v0.38.0] — 2026-05-03 — Sprint H: UX-007 Dashboard i18n — cards traduzidos

### Frontend — Dashboard cards i18n (bug fix)

- **`LeaksPanel.tsx`** — `spotLabel()` movido para dentro do componente; `t("leaks.*")` para título, botão estudar e descrição de leak
- **`BankrollChart.tsx`** — botões de período, título e estado vazio via `t("bankroll.*")`
- **`RecentTournamentsTable.tsx`** — cabeçalhos, status (Analisado/Em fila) e `formatDate` com `i18n.language` dinâmico
- **`DecisionQualityCard.tsx`** — array `LABELS` movido para dentro do componente; todos os rótulos via `t("decisions.*")`
- **`StreetBreakdown.tsx`** — título, tooltip e estado vazio via `t("streets.*")`
- **`PositionChart.tsx`** — título, tooltip e estado vazio via `t("positions.*")`
- **`RecentForm.tsx`** — `scoreDot()` movido para dentro do componente; legenda e título via `t("form.*")`
- **`IcmBreakdown.tsx`** — `ICM_LABEL` movido para dentro do componente; rótulos de pressão ICM e título via `t("icm.*")`
- **`LevelCard.tsx`** — nível, progresso, leaks bloqueadores e link de estudo via `t("level.*")`; pluralização i18next (`tournament_one`/`tournament_other`)
- **`EmptyDashboard.tsx`** — array `MODULES` movido para dentro do componente; upload section e módulos via `t("empty.*")`
- **`PlayerStatsCard.tsx`** — "em breve", "sem dados", "mãos" e mensagem vazia via `t("playerStats.*")`
- **Locales** — ~80 novas chaves adicionadas a `dashboard.json` (PT-BR + EN + ES)

## [v0.37.0] — 2026-05-02 — Sprint G: UX-006 Header Cleanup + i18n Full Coverage

### Frontend — Header simplification

- **`HudHeader.tsx`** — removidos badges (NEW/ALPHA) dos itens de nav, pill "Engine Active" e pill com nome do coach
- **`Index.tsx`** — coach badge movido para a seção hero do dashboard (abaixo do subtítulo), com ícone `GraduationCap` e ring sutil

### Frontend — i18n cobertura completa (5 novos namespaces, 3 idiomas)

- **Novos namespaces** — `aicoach`, `coaches`, `profile`, `replayer`, `landing` (PT-BR + EN + ES)
- **`NotFound.tsx`** — traduzido via `common.notFound.*`
- **`AICoach.tsx`** — traduzido via namespace `aicoach`; sugestões, saudação, painel de contexto e sessão
- **`Tournaments.tsx`** — traduzido; badges de formato, stats, cabeçalhos de tabela, estados vazios
- **`TournamentDetail.tsx`** — traduzido; `SEVERITY_META` e `FILTERS` movidos para dentro do componente; `ScoreLabel` inline
- **`StudyPlan.tsx`** — traduzido; toolbar, KPIs, diagnóstico, roadmap semanal, recursos, botões de dia
- **`CoachesDirectory.tsx`** — traduzido; `SORT_OPTIONS` movido para dentro de `FilterPanel`
- **`PublicCoachProfile.tsx`** — traduzido; loading, não encontrado, botão voltar, contadores
- **`StudentProfile.tsx`** — traduzido; títulos de seção, coach linkado, botões de unlink
- **`Replayer.tsx`** — traduzido; navegação de mãos, controles, action log, painel EV, formulário de anotação de coach, resultado do showdown
- **`Landing.tsx`** — traduzido completamente; arrays `PLANS`, `HOW_IT_WORKS`, `FEATURES` movidos para dentro dos sub-componentes; cada seção usa `useTranslation("landing")`
- **Locales atualizados** — `tournaments.json` + `common.json` + `study.json` com novas chaves; `landing.json` reescrito com estrutura completa (planos, CTA, footer)

---

## [v0.36.0] — 2026-05-02 — Sprint D: BACK-016 WhatsApp Coaching Drills

### Backend

- **`leaklab/whatsapp_bot.py`** — módulo do bot: `send_text()` (Cloud API v19), `handle_incoming()` (dispatcher), `_handle_answer()` (correção MCQ), `_send_question()` (busca top leak e gera exercício), `_generate_exercise()` (Claude Haiku → JSON com question/answer/explanation), `_fallback_exercise()` (template local sem LLM); estado de questões pendentes em dict in-memory por número
- **`api/app.py`** — 3 novas rotas:
  - `GET /whatsapp/webhook` — verificação de webhook pelo Meta (hub.challenge)
  - `POST /whatsapp/webhook` — recebe eventos Meta, despacha para `handle_incoming()`; sempre retorna 200 imediato
  - `PATCH /profile/phone` — vincula/desvincula número de WhatsApp ao usuário logado (validação E.164, unicidade)
  - `GET /auth/me` — agora retorna `whatsapp_phone`
- **`database/schema.py`** — migration `ALTER TABLE users ADD COLUMN whatsapp_phone TEXT UNIQUE` (Postgres + SQLite)
- **`database/repositories.py`** — `get_user_by_phone(phone)` + `update_user_phone(user_id, phone)`
- **`.env`** — adicionado `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`, `WHATSAPP_VERIFY_TOKEN`

### Frontend

- **`lib/api.ts`** — `auth.updatePhone(phone)` → `PATCH /profile/phone`; `UserProfile.whatsapp_phone` adicionado ao tipo
- **`pages/StudentProfile.tsx`** — nova seção "WhatsApp — Coaching Drills": campo para inserir número (formato DDI+DDD), botão Salvar e botão Desvincular; mostra número atual vinculado
- **`frontend/.env`** — `VITE_WHATSAPP_NUMBER=15556305701` (número sandbox Meta; substituir pelo número real em produção)

### Fluxo
1. Usuário vincula número em Perfil → WhatsApp
2. Clica "Iniciar no WhatsApp" no StudyPlan → abre conversa com o bot
3. Qualquer mensagem → bot busca top leak, gera MCQ via Claude Haiku, envia a questão
4. Usuário responde A/B/C/D → bot corrige e explica
5. Próxima mensagem → novo exercício

---

## [v0.35.0] — 2026-05-02 — Sprint F: UX-005 Internacionalização (i18n) PT/EN/ES

### Frontend

- **`i18n/index.ts`** — setup `i18next` + `i18next-browser-languagedetector`; auto-detecta via `localStorage` → `navigator.language`; fallback `pt-BR`; namespaces: `common`, `dashboard`, `tournaments`, `study`, `auth`
- **`main.tsx`** — importa `./i18n` para inicializar antes do React
- **Locales PT-BR** — `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **Locales EN** — `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **Locales ES** — `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **`HudHeader.tsx`** — `LanguageSwitcher` dropdown (🇧🇷 PT · 🇺🇸 EN · 🇪🇸 ES) no canto direito; nav labels e botão Import traduzidos via `t()`; preferência salva em `localStorage` (`leaklab_lang`)
- **`Login.tsx`** — labels, placeholders e estados de loading traduzidos via namespace `auth`
- **`Index.tsx`** — eyebrow, título, subtítulo, KPIs, AI Confidence e footer traduzidos via namespaces `dashboard` + `common`

---

## [v0.34.0] — 2026-05-02 — Sprint C+E: BACK-014 + BACK-017 Revenue Share + Admin Panel

### Backend

- **`schema.py`** — novo campo `users.referral_coach_id` + `users.suspended`; nova tabela `coach_payments` (coach_id, period YYYY-MM, active_students, amount_cents, status, paid_at) em SQLite e PostgreSQL via `_run_migrations`
- **`auth.py`** — novo decorator `require_admin()` que valida `role == 'admin'` no banco
- **`repositories.py`** — novas funções: `calculate_coach_payout()` (lógica de revenue share), `get_admin_dashboard_stats()`, `get_all_users()`, `get_all_users_count()`, `update_user_admin()`, `get_coaches_with_payout_status()`, `upsert_coach_payment()`, `mark_coach_payment_paid()`, `get_coach_finance_summary()`, `get_coach_finance_students()`, `get_coach_finance_history()`, `get_admin_activity_logs()`
- **`app.py`** — 10 novos endpoints:
  - `GET /admin/dashboard` — MRR estimado, usuários ativos, distribuição de planos, repasses pendentes
  - `GET /admin/users` — lista paginada com filtros (plan, role, search)
  - `PATCH /admin/users/<id>` — suspender/alterar plano
  - `GET /admin/finance/coaches` — repasses do ciclo com auto-upsert
  - `PATCH /admin/finance/coaches/<id>/pay` — marcar como pago
  - `GET /admin/finance/export.csv` — exportação CSV para processamento bancário
  - `GET /admin/logs` — últimas importações de torneios
  - `GET /coach/finance/summary` — ciclo atual do coach
  - `GET /coach/finance/students` — alunos com status de atividade
  - `GET /coach/finance/history` — histórico de repasses recebidos

### Frontend

- **`api.ts`** — tipos `AdminStats`, `AdminUser`, `CoachPayout`, `CoachFinanceSummary`, `CoachFinanceStudent`, `CoachPaymentRecord`; objetos `adminDashboard` e `coachFinance` com todas as chamadas
- **`pages/admin/AdminDashboard.tsx`** — painel admin com 4 abas: Visão Geral (KPIs + distribuição de planos), Usuários (tabela paginada com filtros, alterar plano inline, suspender/reativar), Financeiro (tabela de repasses por período, "Marcar pago", exportar CSV), Logs (últimas importações)
- **`CoachDashboard.tsx`** — nova aba "Financeiro": resumo do ciclo atual (alunos totais/ativos, receita estimada, mensalidade zerada), lista de alunos com badge Ativo/Inativo, histórico de repasses
- **`App.tsx`** — `AdminRoute` guard + rota `/admin`; `PublicRoute` redireciona admin para `/admin`
- **`HudHeader.tsx`** — nav item "Admin" com ícone Shield para role admin

### Regras de negócio implementadas
- 1–3 alunos ativos: mensalidade do coach zerada, R$0 de repasse
- 4–9 alunos ativos: mensalidade zerada + R$15/aluno/mês
- 10+ alunos ativos: mensalidade zerada + R$20/aluno/mês
- Aluno ativo = importou ≥1 torneio nos últimos 30 dias + plano PRO

---

## [v0.33.0] — 2026-05-02 — Sprint B: UX-002 Responsividade Mobile/Tablet

### Frontend

- **`HudHeader.tsx`** — bottom navigation bar fixa em mobile (`fixed bottom-0 z-50 md:hidden`) com ícone + label curto por rota; FAB de import (`fixed bottom-[72px] right-4 size-12`) substitui o botão de import do header em mobile; padding do header ajustado para `px-4 md:px-8`
- **`HudLayout.tsx`** — padding inferior `pb-28 md:pb-8` para deixar clearance acima do bottom nav fixo
- **`Index.tsx`** — grid de KPIs vai de 1-col para `grid-cols-2 lg:grid-cols-4` (2 colunas em mobile); sidebar com LevelCard/LeaksPanel usa `order-first lg:order-none` — aparece antes dos gráficos em mobile
- **`RecentTournamentsTable.tsx`** — modo duplo: lista de cards clicáveis `md:hidden` + tabela `hidden md:block overflow-x-auto`; `formatDateShort()` para data compacta nos cards mobile
- **`Tournaments.tsx`** — modo duplo: lista de cards mobile com profit, badge, delete + tabela desktop; empty state diferente por viewport
- **`Replayer.tsx`** — barra de controles vira sticky bottom em mobile (`sticky bottom-14 z-30 border-t bg-background/95 backdrop-blur-md`) e volta ao painel normal em desktop (`md:static md:border md:rounded-xl md:bg-hud-surface`)
- **`TournamentDetail.tsx`** — tabelas de fase (M-Ratio) e textura de board recebem `overflow-x-auto` para scroll horizontal em mobile
- **`StudentDetail.tsx`** — tabs do detalhe do aluno (coach view) recebem `overflow-x-auto` + `shrink-0` nos botões para scroll horizontal em telas pequenas

---

## [v0.32.0] — 2026-05-02 — Sprint 4: BACK-001 + BACK-005 (confirmados + gap fechado)

### Backend
- **`api/app.py` → `history_tournament`** — enriquece cada decisão com `has_annotation: bool` usando `get_annotations_for_decisions`; aluno agora sabe quais mãos têm anotação do coach sem fazer request extra

### Frontend
- **`api.ts`** — `TournamentDecision` ganha campo opcional `has_annotation?: boolean`
- **`TournamentDetail.tsx`** — `Hand.hasAnnotation` propagado via `groupByHand` (true se qualquer decisão do grupo tem anotação); badge "Coach" com ícone GraduationCap aparece ao lado do severity badge em mãos anotadas pelo coach

### Confirmado já implementado (BACK-001 e BACK-005 core)
- Tabela `coach_hand_annotations` + endpoints GET/POST/DELETE `/coach/student/:id/hand-annotations`
- `AnnotationForm` no `WorstTab` do `StudentDetail.tsx` (visão coach)
- Replayer: painel de anotação para coach (form com modo/ação/veredito) e balão read-only para aluno
- Ambos os endpoints de replay (`/replay/:t/:h` e `/coach/student/:id/replay/:t/:h`) incluem `coach_annotations`
- Badge "✓ Coach" na listagem de torneios do aluno (`Tournaments.tsx`) via `get_reviewed_tournament_ids()`

---

## [v0.31.0] — 2026-05-02 — Sprint A: UX-001 + UX-003 + LLM template upgrade

### Frontend — UX-001: Lista de torneios melhorada
- **`RecentTournamentsTable.tsx`** — fallback de nome agora usa `#tournament_id` (era `site`); badge detection estendida: +SAT (satellite), +KO (knockout/bounty/PKO), +SNG (sit & go variants); subtitle mostra `{hands_count} mãos` abaixo do ID
- **`Tournaments.tsx`** — coluna "ID" renomeada para "Torneio"; mesmas melhorias de badge e fallback; `{hands_count} mãos` no subtitle

### Frontend — UX-003: Tooltips e score auto-explicativo
- **`TournamentDetail.tsx`** — componente `InfoTooltip` (HelpCircle + Radix Tooltip) adicionado a cabeçalhos das seções fase/textura e às colunas "Erros %" e "Score Médio"; tooltips explicam os thresholds (M-Ratio, texturas de board com exemplos de cartas, % de erro, faixas do score)
- **`TournamentDetail.tsx`** — componente `ScoreLabel` exibe rótulo colorido (Ótimo / Bom / Moderado / Alto) inline ao score para leitura imediata sem referência externa

### Backend / IA — LLM template upgrade
- **`llm_explainer.py`** — `analyze_single_decision` migrada de 3 parágrafos genéricos para template estruturado em 5 seções: ❌ O Erro / 📐 A Matemática / 🧭 O Contexto / ✅ A Ação Correta / 💡 A Lição; `max_tokens` 500 → 900

### Infra — BACK-007 (confirmado como já implementado)
- `UploadQueue.tsx` + `HudHeader.tsx` já implementavam upload múltiplo com fila sequencial — confirmado durante Sprint A; nenhuma mudança necessária

---

## [v0.30.0] — 2026-05-02 — Análise por Fase e Textura de Board

### Backend
- **`leaklab/board_texture.py`** — novo módulo: `classify_board_texture(board_json)` classifica boards pós-flop em `dry | coordinated | wet | monotone | paired` usando span de ranks e contagem de naipes
- **`repositories.py`** — `get_phase_analysis(tournament_db_id)`: agrupa decisões por fase (Folgado M≥20 / Médio M10-20 / Pressão M6-10 / Crítico M<6) derivando fase do `m_ratio`; `get_texture_analysis(tournament_db_id)`: classifica boards pós-flop e retorna stats por textura
- **`GET /history/tournament/<id>/phase_analysis`** — novo endpoint: retorna distribuição de erros e score médio por fase de torneio
- **`GET /history/tournament/<id>/texture_analysis`** — novo endpoint: retorna distribuição de erros pós-flop por textura de board

### Frontend
- **`TournamentDetail.tsx`** — duas novas seções entre o grid de stats e os filtros: tabela de Análise por Fase e tabela de Pós-Flop por Textura de Board; código de cores: verde (<25% erros), amarelo (25-40%), vermelho (>40%)
- **`api.ts`** — `tournaments.phaseAnalysis()` e `tournaments.textureAnalysis()`; novas interfaces `PhaseData` e `TextureData`

---

## [v0.29.0] — 2026-05-02 — BACK-015: Migração Mercado Pago → Stripe

### Pagamentos
- **`stripe_gateway.py`** — novo gateway: `create_subscription`, `cancel_subscription`, `get_subscription`, `get_payment`, `validate_webhook`; usa Stripe Subscriptions API com `payment_behavior=default_incomplete`
- **`POST /subscription/checkout`** — simplificado: recebe só `plan`, cria Stripe Customer + Subscription, retorna `{ client_secret, subscription_id }` para confirmação no frontend
- **`POST /subscription/activate`** — novo: verifica `PaymentIntent.status` e ativa o plano no banco (chamado pelo frontend após `stripe.confirmPayment`)
- **`POST /subscription/webhook`** — reescrito para eventos Stripe: `invoice.payment_succeeded` → ativa plano; `customer.subscription.deleted` → reverte para free; sem secret configurado aceita sem validação (dev mode)
- **`POST /subscription/cancel`** — usa `stripe.Subscription.cancel()` via gateway
- Removido `mercadopago_gateway.py` (todas as rotas MP descontinuadas)

### Frontend
- **`CheckoutModal.tsx`** — reescrito com `@stripe/stripe-js`; `loadStripe` + `PaymentElement` substitui 8 campos manuais do MP; `Promise.all` carrega SDK e intent em paralelo; confirmação via `stripe.confirmPayment({ redirect: 'if_required' })` + `/subscription/activate`
- **`api.ts`** — `checkout()` simplificado (só `plan`); novo `activate(plan, payment_intent_id, subscription_id)`

### Dependências
- `requirements.txt`: + `stripe==12.0.0`; removido `requests` (não mais usado pelo gateway)
- `package.json`: + `@stripe/stripe-js`

### Env vars necessárias
| Variável | Descrição |
|---|---|
| `STRIPE_SECRET_KEY` | Chave secreta Stripe (`sk_test_...` / `sk_live_...`) |
| `STRIPE_PUBLISHABLE_KEY` | Não usada no backend |
| `STRIPE_WEBHOOK_SECRET` | Secret do webhook Stripe (`whsec_...`) |
| `STRIPE_PRICE_STARTER` | Price ID do plano Starter (`price_...`) |
| `STRIPE_PRICE_PRO` | Price ID do plano Pro (`price_...`) |
| `VITE_STRIPE_PUBLISHABLE_KEY` | Chave pública Stripe para o frontend |

### Testes
- `test_subscription.py` reescrito: 25 testes cobrindo checkout, activate, invoices, cancel, webhook — 0 regressões

---

## [v0.28.1] — 2026-05-01 — BACK-015 fix: payer.identification + debugging

### Pagamentos
- **`mercadopago_gateway.py`** — `create_subscription` aceita `identification_type`/`identification_number`; inclui `payer.identification` no body do `/v1/payments` (obrigatório no Brasil); log completo do response de erro
- **`POST /subscription/checkout`** — extrai `identification_type`, `identification_number` e `payer_email` do body; `payer_email` do form substitui email do usuário quando fornecido (permite usar email de conta teste MP)
- **`CheckoutModal.tsx`** — extrai `identificationType`, `identificationNumber`, `cardholderEmail` de `getCardFormData()` e envia ao backend
- **`api.ts`** — `subscription.checkout()` aceita os novos campos

### Testes
- 2 novos testes: `test_checkout_forwards_identification`, `test_checkout_payer_email_override`
- 23 testes de subscription — 0 regressões

---

## [v0.28.0] — 2026-04-27 — BACK-015: Mercado Pago Transparent Checkout

### Pagamentos
- **`mercadopago_gateway.py`** — novo módulo: `get_or_create_plan`, `create_subscription`, `cancel_subscription`, `get_subscription`, `get_payment`, `validate_webhook_signature` (HMAC-SHA256)
- **`POST /subscription/checkout`** — cria assinatura recorrente MP via card token; rate limit 5/h; atualiza `plan` e `mp_subscription_id` do usuário no banco
- **`POST /subscription/webhook`** — recebe eventos MP (`subscription_preapproval`, `payment`); valida assinatura HMAC-SHA256; atualiza plano e salva pagamentos
- **`GET /subscription/invoices`** — retorna histórico de pagamentos do usuário (limit 20)
- **`POST /subscription/cancel`** — cancela assinatura MP ativa e reverte plano para `free`

### Schema
- Tabela `payments` (id, user_id, plan, amount_cents, currency, status, gateway, gateway_id, gateway_sub_id, period_start, period_end, created_at)
- Coluna `mp_subscription_id` adicionada a `users`

### Frontend
- **`CheckoutModal.tsx`** — modal de checkout transparente: carrega MP JS SDK v2 dinamicamente, inicializa `mp.cardForm()` com iframes seguros para dados do cartão, submete token ao backend, exibe sucesso/erro e chama `refreshUser()`
- **`AccountMenu.tsx`** — botões "Starter R$19" e "Pro R$39" abrem `CheckoutModal` (substituindo links `mailto:`)
- **`QuotaBanner.tsx`** — idem: botões de upgrade abrem `CheckoutModal`
- **`api.ts`** — `subscription.checkout()`, `subscription.invoices()`, `subscription.cancel()`

### Testes
- 227 testes — 0 regressões

---

## [v0.27.0] — 2026-04-27 — BACK-011 pt.2: Anti-Prompt Injection + Moderação de Conteúdo

### Segurança — Camada 1: Anti-Prompt Injection
- **`content_moderation.py`** — novo módulo com `sanitize_llm_input(text, max_len)`: remove 14 padrões de injection (EN + PT-BR) via regex antes de qualquer chamada ao LLM; tenta de role spoofing (`system:`, `assistant:`), token markers (`<|...|>`, `[INST]`), comandos de esquecimento e personas alternativas
- **`coach_chat_reply`** — mensagem do usuário sanitizada antes de entrar no payload do Claude
- **`analyze_single_decision`** — campo `note` (texto livre do hand history) sanitizado antes de ir ao LLM
- **`/coach/chat`** — sanitização no endpoint antes de repassar ao `coach_chat_reply`; erro interno não mais exposto na resposta
- **Anotações de coach** — `comment` sanitizado via `sanitize_llm_input` antes de salvar no banco
- Todas as tentativas detectadas são logadas com `log.warning` para análise posterior

### Segurança — Camada 2: Moderação de Conteúdo (blocklist local v1)
- **`moderate_text(text)`** — verifica texto livre contra blocklist PT-BR + EN cobrindo: discurso de ódio, ataques, spam/scam, links de redes sociais suspeitos, conteúdo adulto explícito; retorna `(is_clean, reason)` e loga flags
- **`/coach-profile` (POST)** — campo `bio` verificado antes de salvar; retorna 422 se flaggeado
- **`/coach/review` (POST)** — `review_text` verificado antes de salvar; retorna 422 se flaggeado
- **`/coach/student/:id/hand-annotations` (POST)** — `comment` verificado + sanitizado antes de salvar

### Schema
- Coluna `moderation_status TEXT DEFAULT 'approved'` adicionada a `coach_profiles`, `coach_reviews`, `coach_hand_annotations` (PostgreSQL: `ALTER TABLE IF NOT EXISTS`; SQLite: migration lazy)

### Testes
- 227 testes — 0 regressões

---

## [v0.26.0] — 2026-04-27 — BACK-011: Hardening de segurança

### Segurança — Crítico
- **bcrypt** — senhas agora armazenadas com bcrypt + salt aleatório; migração transparente: hashes SHA-256 legados são re-hasheados no próximo login com sucesso
- **SECRET_KEY forçado** — inicialização levanta `RuntimeError` em produção se `LEAKLAB_SECRET` não estiver definido ou tiver menos de 32 caracteres; aviso no terminal em desenvolvimento

### Segurança — Alta
- **`require_coach` usa role do banco** — antes validava o campo `role` do JWT (forjável); agora consulta o banco em cada requisição protegida
- **Token não aceito via URL** — `_extract_token()` removia fallback `?token=` que expunha tokens nos logs de servidor; aceita apenas `Authorization: Bearer` e cookie
- **IDOR em anotações de coach corrigido** — endpoint `POST /coach/student/:id/hand-annotations` agora valida que `decision_id` pertence ao aluno antes de salvar
- **Headers de segurança HTTP** — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy` adicionados a toda resposta; `Strict-Transport-Security` ativado em produção (`RENDER=true`)

### Segurança — Média
- **Rate limiting** — Flask-Limiter instalado; limites por IP: `/auth/register` 10/min, `/auth/login` 15/min, `/analyze` 30/h, `/analyze/decision` e `/analyze/hand-coach` 30/h, `/analyze/tournament-summary` 20/h; desativado automaticamente em testes (`app.testing`)
- **Validação de extensão de arquivo** — upload em `/analyze` rejeita arquivos que não terminem em `.txt`
- **Mensagens de erro sanitizadas** — exceções internas logadas com `log.exception()` em vez de expostas no corpo da resposta
- **Senha mínima 8 caracteres** — aumentado de 6 para 8 em `/auth/register`
- **Role restrito no cadastro** — valores fora de `player/coach` são coercidos para `player` silenciosamente

### Infraestrutura
- `bcrypt==4.2.1` e `Flask-Limiter==3.8.0` adicionados ao `requirements.txt`
- `repositories.py`: funções `_hash_password`, `_check_password`, `decision_belongs_to_student` extraídas; `update_user_email`, `change_user_password`, `check_password` migradas para usar bcrypt

### Testes
- 227 testes — 0 regressões

---

## [v0.25.0] — 2026-04-27 — UX-004: Menu de conta com plano e uso

### Adicionado
- **`AccountMenu`** — dropdown acessível ao clicar no nome/plano no header; exibe username, badge de plano colorido por tier (Free/Starter/Pro/Coach), barras de uso mensal (torneios + análises LeakLabs), CTAs de upgrade contextuais e links para Perfil e Sair
- **`/auth/me` inclui quota** — resposta agora inclui `plan`, `tournaments_used`, `ai_calls_used`, `plan_limits`; elimina segundo request separado ao `/subscription/status`

### Alterado
- **`HudHeader`** — item "Perfil" removido do menu de navegação do jogador; bloco username+logout substituído por `AccountMenu`; Dashboard corrigido para `/dashboard`
- **`UserProfile`** — interface TypeScript estendida com campos de quota
- **Dashboard (`Index.tsx`)** — `QuotaBanner` removido da sidebar (redundante com `AccountMenu`)

---

## [v0.24.0] — 2026-04-27 — Proposta B: 3 planos (Free / Starter / Pro)

### Adicionado
- **Plano Starter R$19/mês** — 20 torneios + 40 análises/mês; público alvo: jogador casual que ultrapassou o Free mas não precisa de volume de grinder
- **3 planos no `/subscription/plans`** — Free, Starter (R$19), Pro (R$39)

### Alterado
- **Plano Pro**: R$15 → **R$39/mês** — torneios ilimitados + 150 análises LeakLabs/mês
- **PLAN_LIMITS** — `starter: {tournaments: 20, ai_calls: 40}` · `pro: {tournaments: None, ai_calls: 150}`
- **Landing page** — seção Planos migrada para grid de 3 colunas; badge "Mais popular" no Starter, badge "Grinder" + destaque primário no Pro
- **QuotaBanner** — botões Starter R$19 + Pro R$39 lado a lado no banner de limite atingido

---

## [v0.23.0] — 2026-04-27 — UX-003: Landing page pública

### Adicionado
- **Landing page pública em `/`** — apresentação do produto para visitantes não autenticados; seções: Hero com níveis preview, Estatísticas, Como Funciona (3 passos), Funcionalidades (6 cards), Planos (Free vs Pro), CTA final e Footer
- **Rota `/dashboard`** — dashboard do jogador movido de `/` para `/dashboard`; usuários autenticados são redirecionados automaticamente para o destino correto ao acessar `/` ou `/login`
- **`PublicRoute`** — guarda de rota público: redireciona usuário já logado para `/dashboard` (jogador) ou `/coach-dashboard` (coach), evitando que veja a landing ou tela de login desnecessariamente

### Alterado
- `App.tsx` — `/` agora renderiza `Landing` (via `PublicRoute`); `/login` também usa `PublicRoute`; `/dashboard` é a nova rota protegida do jogador; `CoachRoute` redireciona não-coaches para `/dashboard`
- `Login.tsx` — pós-login redireciona jogador para `/dashboard` em vez de `/`
- `HudHeader.tsx` — logo aponta para `/dashboard` em vez de `/` (usuário autenticado)

---

## [v0.22.0] — 2026-04-27 — BACK-010: Freemium + quota + backlog expandido

### Adicionado
- **Planos freemium e controle de quota** — plano Free: 3 torneios/mês + 10 análises IA/mês; plano Pro: ilimitado; quota resetada automaticamente no início de cada mês (lazy reset por usuário)
- **Endpoints de subscription** — `GET /subscription/plans`, `GET /subscription/status`, `POST /subscription/upgrade`; upgrade manual em v1 (sem gateway de pagamento)
- **Middleware de quota no backend** — `_check_upload_quota()` antes do `/analyze`; `_check_ai_quota()` antes de `/analyze/decision`, `/analyze/hand-coach` e `/analyze/tournament-summary`; retorna HTTP 402 com `quota_exceeded: true` quando limite atingido
- **Cache de tournament summary** — `/analyze/tournament-summary` agora retorna o summary já salvo no banco quando disponível, sem chamar o LLM novamente; economiza quota e reduz latência
- **QuotaBanner no dashboard** — barra de uso de torneios e análises IA exibida na sidebar do dashboard; aparece somente para plano Free e apenas quando ≥ 80% do limite foi atingido; botão de upgrade via email em v1
- **Busca corrigida em /tournaments** — placeholder atualizado de "herói" para "nome, tipo (MTT/SNG) ou ID"
- **Backlog expandido** — UX-002 (responsividade mobile/tablet, ~15h) e BACK-014 (revenue share para coaches, ~20h) documentados com escopo, modelo de dados e esforço estimado

### Backend
- `backend/database/schema.py` — colunas `tournaments_this_month`, `ai_calls_this_month`, `quota_reset_at` na tabela `users`; migrations para SQLite e Postgres
- `backend/database/repositories.py` — `PLAN_LIMITS`, `get_quota_status()`, `increment_tournament_count()`, `increment_ai_calls()`, `_maybe_reset_quota()` (lazy reset mensal)
- `backend/api/app.py` — `_check_upload_quota()`, `_check_ai_quota()`; subscription endpoints; quota wiring em analyze + LLM endpoints

### Frontend
- `frontend/src/lib/api.ts` — interface `QuotaStatus`; namespace `subscription` com `status()`, `plans()`, `upgrade()`
- `frontend/src/components/hud/QuotaBanner.tsx` — componente novo com barras de progresso e CTA de upgrade
- `frontend/src/pages/Index.tsx` — `QuotaBanner` inserido no topo da sidebar
- `frontend/src/pages/Tournaments.tsx` — placeholder da busca corrigido

---

## [v0.21.0] — 2026-04-26 — UX: Logos de sites, auto-reload pós-import, níveis rebalanceados

### Adicionado
- **Logo dos sites na lista de torneios** — componente `SiteLogo` exibe favicon do site (PokerStars, GGPoker, 888Poker, Winamax, ACR) em container 24×24 com tooltip do nome completo; fallback para sigla em texto se a imagem falhar; visível na `RecentTournamentsTable` (dashboard) e na lista completa `/tournaments`

### Corrigido
- **Auto-reload pós-importação em qualquer tela** — `UploadQueue` agora dispara evento global `leaklab:tournament-imported` a cada arquivo processado; `Tournaments.tsx` escuta o evento e chama `reload()` automaticamente; antes, importar pelo botão do header na tela `/tournaments` não atualizava a lista
- **Badge SNG/MTT incorreto** — `_extract_tournament_name()` agora conta jogadores únicos no arquivo HH: ≤ 9 = SNG (sem reposição de mesa), > 9 = MTT (jogadores vindos de mesas quebradas); resolve badge "MTT" incorreto em Sit & Go PokerStars
- **Thresholds de nível rebalanceados** — escala anterior era leniente demais (Sólido começava em 75%); nova escala: Iniciante < 60%, Estudante 60–69%, Grinder 70–76%, Regular 77–85%, Sólido 86–91%, Expert 92–95%, Elite 96%+; calibrada para que 83–85% std_pct = Regular

### Frontend
- `frontend/src/components/hud/SiteLogo.tsx` — componente novo com mapa de favicons e fallback de sigla
- `frontend/src/components/hud/RecentTournamentsTable.tsx` — logo inline, badge corrigido
- `frontend/src/pages/Tournaments.tsx` — coluna Rede vira logo; listener de reload pós-import
- `frontend/src/components/hud/UploadQueue.tsx` — dispara `CustomEvent('leaklab:tournament-imported')` após cada upload concluído

### Backend
- `backend/database/repositories.py` — thresholds de `get_player_level()` atualizados
- `backend/api/app.py` — `_extract_tournament_name()` usa contagem de jogadores únicos para distinguir SNG de MTT

---

## [v0.20.0] — 2026-04-26 — UX-001: Nome e Tipo do Torneio na Lista

### Adicionado
- **Nome do torneio na lista de torneios** (UX-001) — substituído o par "site • nome do hero" pelo nome descritivo do torneio (ex: "Spin&Gold #14", "NLH $2.20"); badge "MTT" / "Spin&Go" ao lado do nome; subtext exibe site + ID interno para rastreabilidade
- Coluna `tournament_name TEXT` adicionada à tabela `tournaments` (SQLite + PostgreSQL); migration automática via `_run_migrations`

### Backend
- `backend/api/app.py` — novo helper `_extract_tournament_name()`: GGPoker extrai nome do header (`Tournament #N, Spin&Gold #14 Hold'em`); PokerStars constrói label do buy-in (`NLH $2.20`); chamado no `/analyze` e persistido com o torneio
- `backend/database/repositories.py` — `save_tournament()` aceita `tournament_name`; `get_tournaments()` inclui o campo no SELECT
- `backend/database/schema.py` — coluna `tournament_name TEXT` nas definições CREATE TABLE e nas migrations SQLite/Postgres

### Frontend
- `frontend/src/lib/api.ts` — `Tournament.tournament_name?: string | null` adicionado à interface
- `frontend/src/components/hud/RecentTournamentsTable.tsx` — helper `formatTournamentLabel()` e `formatBadge()`; célula "Torneio" exibe nome + badge de formato + subtext com site e ID
- `frontend/src/pages/coach/StudentDetail.tsx` — `TournamentsTab` usa `tournament_name ?? site` como label principal; subtext inclui site + ID

---

## [v0.19.0] — 2026-04-26 — BACK-008: Visualizador de Ranges + BUG-001: Prêmio de Torneio

### Adicionado
- **Visualizador de Ranges no Replayer** (BACK-008) — botão "Range" aparece durante o preflop; painel lateral 13×13 com ranges GTO-aproximadas para 6 posições (UTG, MP, HJ, CO, BTN, SB, BB); auto-detecta posição do herói e contexto (open vs facing raise); seletor manual de posição e tipo (Open · Call · 3-Bet); mão do herói destacada em amarelo; legenda com % de mãos e contagem de combos

### Corrigido
- **BUG-001 — Prêmio incorreto em torneios PokerStars** — quando eliminado sem ITM, o arquivo PokerStars contém apenas "hero finished the tournament" sem prêmio; o código caía no fallback GGPoker que somava todos os chips coletados em potes normais do jogo como prêmio; fix: detecta "finished the tournament" antes do fallback e define `prize = 0.0`; torneios afetados devem ser reimportados

### Frontend
- `frontend/src/data/ranges.ts` — ranges GTO-aproximadas para Open/Call/3-Bet por posição; expansor de notação de range ("AA-77", "AKs-A2s"); utils `cellHand`, `cellLabel`, `heroHand`, `getCellAction`, `rangeStats`
- `frontend/src/components/replayer/RangeGrid.tsx` — grid 13×13 com aspect-square, cores por ação (verde=raise, azul=call), destaque da mão do herói
- `frontend/src/components/replayer/RangePanel.tsx` — painel com auto-detecção de posição/contexto, seletores de posição e tipo, rodapé com posição detectada
- `frontend/src/pages/Replayer.tsx` — botão "Range" no header do Action Log (visível apenas no preflop); importa `RangePanel` e `LayoutGrid`

### Backend
- `backend/api/app.py` — fix em `_extract_financials()`: PokerStars bust-out sem prêmio define `prize = 0.0` ao invés de somar chips coletados em potes

---

## [v0.18.0] — 2026-04-26 — Sprint 10: Sistema de Nível do Jogador / Gamificação (BACK-009)

### Adicionado
- **Sistema de nível do jogador** — 7 níveis baseados no `standard_pct` médio dos últimos 20 torneios (ou 30 dias): Iniciante, Estudante, Grinder, Regular, Sólido, Expert, Elite; sem rótulos ofensivos; thresholds rebalanceados em v0.21.0
- **LevelCard** — componente visual com badge de nível (ícone + nome + cor por nível), barra de progresso para o próximo nível, threshold do próximo nível, leaks que bloqueiam avanço; modo `compact` para uso no dashboard do coach; link para o plano de estudos (opcional)
- **Dashboard do jogador** — `LevelCard` exibido na sidebar do Index.tsx ao lado dos leaks e ICM
- **Dashboard do coach** — `LevelCard` em modo compacto na aba "Visão Geral" de cada aluno; query `coach-student-level`

### Backend
- `get_player_level(user_id, min_tournaments=5, days=30)` — calcula nível, progresso (0-1), próximo nível, leaks bloqueadores, contagem de torneios usados
- `GET /metrics/level` — retorna nível do próprio jogador
- `GET /coach/student/:id/level` — retorna nível de um aluno (requer `@require_coach`)

### Frontend
- `LevelCard.tsx` — criado com cores por nível, barra de progresso, leaks bloqueadores, CTA de plano de estudos
- `api.ts` — interface `PlayerLevel`; `metrics.level()`; `coachDashboard.studentLevel(studentId)`
- `Index.tsx` — query `player-level` com React Query; `LevelCard` na sidebar
- `StudentDetail.tsx` — query `coach-student-level`; `LevelCard` compacto no topo da `OverviewTab`

---

## [v0.17.0] — 2026-04-26 — Sprint 9: Upload Múltiplo com Fila + Perfil do Coach Unificado (BACK-007 + BACK-012)

### Adicionado
- **Upload múltiplo de torneios** (BACK-007) — botão "Import" aceita múltiplos arquivos `.txt` de uma vez; fila processa sequencialmente com badge de status por arquivo (`Em fila`, `Processando…`, `Analisado ✓`, `Erro`); painel flutuante no canto inferior direito com botão "Fechar" após conclusão
- **Perfil do coach unificado** (BACK-012) — página `/coach-dashboard/profile` reescrita com todos os campos estendidos do Sprint 7 (foto, experiência, stakes, método, idiomas, maiores resultados, preços, trial, redes sociais) + aba "Avaliações" com distribuição de ratings; abas "Perfil Público" e "Avaliações" removidas do CoachDashboard

### Frontend
- `UploadQueue.tsx` — hook `useUploadQueue` + `QueuePanel` com `useReducer`; `fileMap` ref para mapear IDs aos `File` objetos sem poluir o estado
- `HudHeader.tsx` — input de upload agora com `multiple`; usa `useUploadQueue` ao invés de upload manual unitário; retorna `<>header + panel</>` via Fragment
- `CoachProfile.tsx` — reescrito completamente com `ProfileSection` + `AvaliacoesSection` internos; suprime a versão anterior com campos básicos apenas
- `CoachDashboard.tsx` — tabs "Perfil Público" e "Avaliações" removidos; imports de lucide e tipos relacionados limpos

---

## [v0.16.0] — 2026-04-26 — Sprint 8: Diretório Público de Coaches + Integração Contextual (BACK-006 pt.2 + BACK-013)

### Adicionado
- **Diretório público de coaches** (`/coaches`) — lista com filtros de especialidade, idioma, preço máximo, trial e ordenação; barra de busca por nome; sidebar colapsável; grid responsivo
- **Perfil público do coach** (`/coaches/:id`) — avatar, bio, especialidades, maiores resultados, distribuição de avaliações, reviews públicos, contato e links sociais; CTA contextual para vincular coach via chave de convite
- **Coaches no menu principal** — entrada "Coaches" adicionada ao `HudHeader` para jogadores
- **BACK-013 — Coaches contextuais no Plano de Estudos** — strip de coaches especializados no leak ativo, exibida somente para alunos sem coach; clique direciona ao perfil do coach
- **BACK-013 — Coaches no Perfil do aluno** — quando sem coach: lista top-3 coaches por rating + formulário de link por chave de convite; substitui botão antigo sem destino útil

### Backend
- `GET /coaches` aceita `specialty`, `language`, `trial`, `max_price`, `q`, `sort`, `limit` como filtros
- `GET /coaches/:id` retorna perfil completo + reviews públicos recentes
- `GET /coaches/:id/reviews` retorna reviews públicos paginados
- `GET /student/recommended-coaches` — endpoint para recomendação futura (stub)

### Frontend
- `CoachesDirectory.tsx` — nova página com `StarRow`, `CoachCard`, `FilterPanel`
- `PublicCoachProfile.tsx` — nova página com distribuição de rating, reviews, formulário de avaliação (alunos vinculados) e CTA de contratação
- `StudyPlan.tsx` — `CoachRecommendationStrip` + `CoachMiniCard` injetados no card de diagnóstico de leaks
- `StudentProfile.tsx` — `NoCoachDiscovery` com `CoachDiscoveryCard` e formulário de invite key
- `HudHeader.tsx` — "Coaches" adicionado ao nav de jogadores

---

## [v0.15.0] — 2026-04-26 — Sprint 7: Perfil Estendido do Coach + Sistema de Avaliações (BACK-006 pt.1)

### Adicionado
- **Aba "Perfil Público"** no CoachDashboard — formulário completo com foto, experiência, stakes, método de coaching, idiomas, maiores resultados, preços, disponibilidade e redes sociais; modo visualização / edição inline
- **Aba "Avaliações"** no CoachDashboard — aggregate de rating com barra de distribuição por estrela + lista de reviews recebidas
- **Avaliação de coach pelo aluno** — widget na página de perfil do aluno (`StudentProfile`) com StarPicker, comentário opcional, edição e exclusão; aparece somente quando há coach vinculado
- Tabela `coach_reviews` com constraint `UNIQUE(coach_id, student_id)` — 1 review por par aluno-coach

### Backend
- `coach_profiles`: 13 novos campos adicionados (`photo_url`, `experience_years`, `stakes`, `coaching_style`, `languages`, `biggest_results`, `price_per_session`, `price_monthly`, `trial_available`, `availability`, `social_youtube`, `social_twitch`, `social_twitter`)
- `GET /coach/profile` agora retorna `avg_rating` e `review_count` calculados em tempo real
- `POST /coach/review` — aluno envia/atualiza avaliação (upsert por par coach-aluno)
- `DELETE /coach/review` — aluno remove sua avaliação
- `GET /coach/my-review` — aluno consulta sua própria avaliação
- `GET /coach/reviews` — coach vê todas as avaliações recebidas com stats detalhados
- Migrations automáticas para SQLite e Postgres

---

## [v0.14.0] — 2026-04-26 — Sprint 6: Feed de Atividade + Baseline de Coaching (BACK-002)

### Adicionado
- **Aba "Progresso"** no perfil do aluno (coach) — baseline de coaching com comparação antes/depois + feed de atividade em timeline
- **Baseline de coaching** — coach define data de início do acompanhamento; armazenado por par `(coach_id, student_id)` com nota opcional; editável/removível
- **Comparação antes/depois** — métricas de score médio, % decisões standard e n° de torneios separadas pela data baseline; leaks top-5 em cada período; lista de leaks resolvidos
- **Feed de atividade** — timeline de torneios do aluno com marcos automáticos: "Melhora" (↓5pts score), "Regressão" (↑5pts score), "Alta Qualidade" (≥80% standard)
- Tabela `coach_baselines` no banco (SQLite e Postgres) com constraint `UNIQUE(coach_id, student_id)`

### Backend
- `GET/POST/DELETE /coach/student/:id/baseline` — gerenciar baseline de coaching
- `GET /coach/student/:id/activity-feed` — feed de torneios + marcos de performance (param `limit`)
- `GET /coach/student/:id/progress-report` — relatório comparativo antes/depois da baseline
- Novos repositórios: `get_coach_baseline`, `set_coach_baseline`, `delete_coach_baseline`, `get_student_activity_feed`, `get_baseline_comparison`

### Frontend
- Ícones `Activity, Flag, Star, BarChart2` adicionados
- Tipos `CoachBaseline, ActivityEvent, LeakSpot, PeriodMetrics, ProgressReport` em `api.ts`
- API functions `getBaseline`, `setBaseline`, `deleteBaseline`, `activityFeed`, `progressReport` em `coachDashboard`
- Componentes `ActivityTimeline`, `MetricsCompare`, `ProgressTab` em `StudentDetail.tsx`

---

## [v0.13.1] — 2026-04-26 — Combos de ação + classificação coach + Opção C de reclassificação

### Adicionado
- **Combo "Ação Correta"** nas anotações do coach — substituiu o campo livre por select com opções padrão do poker (fold, check, call, bet, raise, re-raise, all-in)
- **Combo "Classificação"** nas anotações — coach pode atribuir o veredito da decisão: Jogada Correta / Marginal / Erro Pequeno / Erro Claro; campo `coach_override_label` armazenado no banco
- Badge visual do veredito exibido no balloon de anotação (aluno e coach) e na listagem de "Mãos Críticas"
- **Opção C implementada** — `coach_override_label` é respeitado nas queries de `worst-decisions` do aluno: decisões marcadas como "Jogada Correta" ou "Marginal" pelo coach saem da lista de mãos críticas; avg_score do torneio **não** é alterado (métricas de performance permanecem do engine)

### Backend
- `coach_hand_annotations`: nova coluna `coach_override_label TEXT` — migrations automáticas SQLite + Postgres
- `upsert_annotation` aceita e persiste `coach_override_label`
- `POST /coach/student/:id/hand-annotations` aceita e valida `coach_override_label`
- `GET /coach/student/:id/worst-decisions` usa `COALESCE(coach_override_label, label)` para filtrar — decisões requalificadas pelo coach como corretas não aparecem mais na lista de erros

---

## [v0.13.0] — 2026-04-26 — Sprint 5: Atenção Urgente + Leaks Sistêmicos (BACK-003 + BACK-004)

### Adicionado
- **Aba "Atenção Urgente"** no Dashboard do Coach — tabela com as piores decisões de **todos os alunos** ao mesmo tempo, com filtros por aluno, street e label (erro claro / erro pequeno); botão "Replay" abre diretamente o replay do aluno na mão errada
- **Aba "Leaks Sistêmicos"** no Dashboard do Coach — lista de spots de erro agrupados por ocorrência, com destaque nos que afetam múltiplos alunos ("Leaks sistêmicos") vs. individuais; cada spot é expandível para ver quais alunos são afetados e quantas vezes
- **Filtro de período** (30/60/90 dias) na aba de Leaks Sistêmicos
- Dashboard do Coach reorganizado em **3 abas**: Alunos (existente) · Atenção Urgente · Leaks Sistêmicos

### Backend
- `repositories.py`: `get_all_students_worst_decisions(coach_id, n, student_id_filter, street_filter, label_filter)` — query cross-student com filtros dinâmicos
- `repositories.py`: `get_common_leaks(coach_id, days)` — agrupa erros por spot e retorna lista de alunos afetados por spot
- `GET /coach/all-worst-decisions` — piores decisões multi-aluno com filtros via query string
- `GET /coach/common-leaks` — leaks com breakdown por aluno

### Fix
- **Anotações do coach não apareciam no replay do aluno** — endpoint `GET /replay/<tournament_id>/<hand_id>` não incluía `coach_annotations`; agora busca e injeta as anotações do coach igual ao endpoint do coach student replay

---

## [v0.12.1] — 2026-04-26 — Fix: Replay para coaches + Anotação direto no Replayer (BACK-001 complemento)

### Corrigido
- **Replay inacessível para coaches** — rota `/replayer` estava envolvida em `ProtectedRoute` que redirecionava coaches para `/coach-dashboard`; criada `AuthRoute` que permite qualquer usuário autenticado acessar o replayer
- **Parâmetro `student` perdido na navegação de mãos** — botões "Mão anterior" / "Próxima mão" no Replayer não preservavam `?student=N` na URL; coach perdia o contexto e o replay passava a buscar dados do próprio jogador em vez do aluno

### Adicionado
- **Painel de anotação do coach no Replayer** — quando o coach acessa o replay de um aluno e a etapa atual é um erro do herói, o painel lateral exibe:
  - Botão "Anotar" (se sem anotação) ou anotação existente com botões "Editar" / "Remover"
  - Formulário inline com seletor de modo (Complementar / Substituir IA), textarea de comentário e campo de jogada correta
  - Salvar atualiza o estado local imediatamente sem re-fetch da mão inteira
- **`decisions` em estado no Replayer** — decisões do torneio são mantidas em memória para resolver `decision_id` de novos spots sem annotation existente (match por `hand_id + street + action_taken`)
- **BACK-007 adicionado ao backlog** — importação múltipla de torneios com fila + badge de progresso por arquivo

---

## [v0.12.0] — 2026-04-26 — Sprint 4: Anotações de Mãos + Selo Coach (BACK-001 + BACK-005)

### Adicionado
- **Anotações de mãos pelo coach** — na aba "Mãos Críticas" do perfil do aluno, o coach pode anotar qualquer decisão com dois modos:
  - **Complementar** — exibe a análise da IA + nota do coach empilhadas
  - **Substituir IA** — oculta a análise da IA, exibe apenas a nota do coach
- **Campo "Jogada correta"** — coach pode indicar a ação que considera correta para o spot anotado
- **Badge "Anotado"** — decisões com anotação exibem indicador visual na listagem
- **Balão do coach no Replayer** — ao chegar na ação anotada, o painel lateral exibe a nota do coach com destaque visual diferenciado do painel da IA
- **Selo "✓ Coach"** (BACK-005) — torneios revisados (com ao menos uma anotação) ganham badge roxo "Coach" na lista de torneios do aluno

### Backend
- Tabela `coach_hand_annotations` (SQLite + PostgreSQL) com migration automática
- `repositories.py`: `get_annotations`, `get_annotations_for_decisions`, `upsert_annotation`, `delete_annotation`, `get_reviewed_tournament_ids`
- `GET /coach/student/:id/hand-annotations` — lista anotações do coach para o aluno
- `POST /coach/student/:id/hand-annotations` — cria ou atualiza anotação por decision_id
- `DELETE /coach/student/:id/hand-annotations/:decision_id` — remove anotação
- Replay do coach (`/coach/student/:id/replay/...`) agora inclui `coach_annotations` na resposta
- `GET /history/tournaments` agora inclui `coach_reviewed: bool` por torneio

---

## [v0.11.1] — 2026-04-26 — Correções de ambiente local + segurança

### Corrigido
- **CORS local resolvido via Vite proxy** — todos os prefixos de API (`/auth`, `/history`, `/analyze`, `/study`, `/coach`, `/student`, `/tournaments`, `/replay`, `/metrics`, `/admin`, `/health`) são roteados pelo proxy do Vite, eliminando erros de CORS no desenvolvimento
- **`get_user_by_id` não importado** em `app.py` causava 500 em `/auth/me` — adicionado ao import
- **Coach redirecionado para `/coach-dashboard`** ao logar — `ProtectedRoute` agora redireciona coaches que tentam acessar rotas de aluno
- **Menu "Dashboard" do coach ficava ativo em `/coach-dashboard/profile`** — adicionado `end={true}` ao NavLink do dashboard do coach
- **Banner de vínculo não sumia após vincular coach** — `AcceptCoachModal` agora chama `refreshUser()` após sucesso, atualizando `user.coach_id` imediatamente
- **`GET /coach/profile` retornava 404** quando perfil não existia, causando loop de retentativas no `useQuery` — endpoint agora retorna `{}` (200)
- **Mensagens de erro no Login** — `TypeError` (ex: "Failed to fetch") exibe "Não foi possível conectar ao servidor" em vez da mensagem técnica bruta

### Segurança
- **Remoção de vínculo com coach exige senha atual** — `DELETE /student/coach` agora requer `password` no body; backend verifica hash antes de desvincular
- `repositories.py`: nova função `check_password(user_id, password)` reutilizável

---

## [v0.11.0] — 2026-04-26 — Perfil do aluno + segurança de conta

### Adicionado
- **Página `/profile`** para alunos: alterar e-mail (com confirmação de senha), trocar senha (verifica atual, mín. 8 chars), gerenciar vínculo de coach (remover com confirmação dupla)
- **Header**: badge do coach vinculado visível no topo quando aluno tem coach; link "Perfil" no nav do player
- **Plano de Estudos**: lock exibido sempre que o aluno tem coach vinculado (não só quando há overrides), mostrando o nome do coach
- **Banner de vínculo** no Dashboard: oculto quando aluno já tem coach vinculado

### Corrigido
- `/auth/me` agora retorna `coach_id` e `coach_username` — frontend usa para controle de acesso sem chamadas extras

### Backend
- `POST /auth/update-email` — atualiza e-mail após verificar senha atual
- `POST /auth/change-password` — verifica senha atual antes de atualizar
- `DELETE /student/coach` — remove vínculo com coach
- `repositories.py`: `update_user_email`, `change_user_password`, `unlink_student_coach`

---

## [v0.10.2] — 2026-04-25 — Plano de estudos com fonte única (canonical plan)

### Corrigido
- **Importar torneio nunca apaga o plano** — o plano de estudos só é substituído por ação explícita ("Gerar com IA" pelo aluno ou "Gerar novo plano" pelo coach)
- **Aluno com coach não pode regerar** — backend bloqueia `?new=1` se o aluno tiver coach vinculado
- **Overrides do coach aplicados no plano do aluno** — cards substituídos/comentados pelo coach já chegam modificados para o aluno via `/study/plan`, alinhando o conteúdo visto por ambos
- **Coach — StudyCardItem exibe recursos completos** (livros, vídeos, curso) para equiparar ao nível de detalhe do plano do aluno
- **Coach — "Substituir" gerencia recursos**: formulário de substituição inclui campos para livros (um por linha), vídeos (um por linha) e curso — coach pode indicar material próprio
- Recursos substituídos pelo coach são aplicados no plano do aluno via backend
- **Plano de estudos inconsistente entre aluno e coach**: aluno e coach agora compartilham o mesmo plano armazenado por chave estável `study_plan_current` no banco — não mais por hash dos dados, que podia divergir quando os dados mudavam entre as gerações
- **Botão "Gerar com IA"** agora força de fato uma nova geração (`?new=1`), sobrescrevendo o plano anterior no banco — antes apenas re-buscava o cache sem regenerar

### Adicionado
- **Coach — botão "Gerar novo plano"** na aba Plano de Estudos: gera um plano novo via IA para o aluno e o torna o plano canônico — o aluno passa a ver exatamente este plano
- Parâmetro `force_new` em `generate_study_plan()` e nos dois endpoints (`/study/plan?new=1`, `/coach/student/:id/study-plan?new=1`)

---

## [v0.10.1] — 2026-04-25 — Mãos Críticas com cartas + lock coach_managed

### Adicionado
- **WorstTab (Mãos Críticas)**: cada decisão agora exibe:
  - ID da mão (`hand_id`)
  - Cartas do herói como `PlayingCard` (tamanho sm)
  - Board cards (quando disponíveis)
- **Lock "Gerar com IA"** na tela do aluno: quando o coach tem overrides no plano, o botão é substituído por "Gerenciado pelo Coach" com ícone de cadeado
- **Backend `/study/plan`**: responde `coach_managed: true` quando existem overrides do coach para o aluno

---

## [v0.10.0] — 2026-04-25 — Sprint 3: Coach Study Plan + Comparativo Histórico

### Adicionado
- **Coach Study Plan interativo**: cada card do plano IA tem 3 ações do coach:
  - **Validar** (✓) — marca o card como aprovado (badge verde)
  - **Comentar** (💬) — abre textarea inline para nota visível ao aluno (badge âmbar)
  - **Substituir** (✏️) — formulário inline para reescrever título, diagnóstico e exercício (badge roxo)
  - Botão de remover anotação (ícone lixeira)
  - Resumo de status no topo: "X validados · Y comentados · Z substituídos"
- **Comparativo histórico** no OverviewTab:
  - Score médio e Standard% — primeiros 3 vs últimos 3 torneios
  - Delta com indicador visual: melhorou / piorou / estável
  - Total de torneios no período
- **Backend**: tabela `coach_study_overrides` (SQLite + PostgreSQL) com UNIQUE(coach_id, student_id, card_spot)
- **3 endpoints**: `GET/POST /coach/student/:id/study-overrides`, `DELETE /coach/student/:id/study-overrides/:spot`
- **Fixes**: replay link no WorstTab (`?tid=` → `?t=`), nome do aluno no header (era "Aluno #N")

---

## [v0.9.0] — 2026-04-25 — Sprint 2: Coach Full Student View

### Adicionado
- **6 novos endpoints backend** para o coach acessar dados completos do aluno:
  - `GET /coach/student/:id/stats` — HUD stats (VPIP, PFR, AF, 3BET%, W$SD…)
  - `GET /coach/student/:id/breakdown` — performance por street e posição
  - `GET /coach/student/:id/tournament/:tid` — detalhe de torneio + decisões
  - `GET /coach/student/:id/worst-decisions` — piores N decisões do aluno
  - `GET /coach/student/:id/study-plan` — plano de estudos IA do aluno
  - `GET /coach/student/:id/replay/:tid/:hid` — replay de mão do aluno
- **StudentDetail.tsx** totalmente reescrito com 4 abas:
  - **Visão Geral**: HUD Stats (8 indicadores), gráfico de evolução, leaks, performance por street (bar chart) e por posição
  - **Torneios**: lista completa clicável → detalhe com tabela de decisões + botão "Ver Replay"
  - **Mãos Críticas**: fila das 30 piores decisões (score, street, posição, ICM, M-ratio, ação vs. correto) com link direto ao replay
  - **Plano de Estudos**: plano IA gerado para o aluno, com cards de prioridade alta/média/baixa
- **Replayer.tsx**: suporte ao parâmetro `?student=<id>` — usa endpoint do coach em vez do endpoint do jogador

---

## [v0.8.0] — 2026-04-25 — Sprint 1: Sistema Professor/Aluno

### Adicionado
- **Login/registro com papel**: toggle "Jogador / Professor" na tela de registro; papel enviado ao backend via `role` no body
- **Rotas por papel**: `CoachRoute` em `App.tsx` — professores são redirecionados para `/coach-dashboard`; jogadores bloqueados de rotas de coach
- **`/coach-dashboard`**: dashboard do professor com stats (alunos, ativos 30d, melhoria média, melhor aluno), lista de alunos com tendência e link para detalhe
- **`/coach-dashboard/student/:id`**: histórico do aluno — gráfico de evolução (recharts), tabela de leaks, torneios recentes
- **`/coach-dashboard/profile`**: formulário para o professor configurar nome, bio, especialidades, e-mail/link de contato
- **Chave de convite** (`InviteKeyWidget`): exibida no dashboard do professor com botão de cópia
- **Banner "Vincular Professor"** no dashboard do jogador com `AcceptCoachModal` para inserir a chave de convite
- **Navegação condicional** no `HudHeader`: professores veem "Dashboard + Perfil"; jogadores veem nav padrão; botão Import oculto para professores

---

## [v0.7.0] — 2026-04-25 — HUD Stats completo + GGPoker

### Adicionado
- **Player HUD Stats** (8 indicadores): VPIP, PFR, AF, Flop Bet%, Fold-to-3BET, WTSD, **3BET%** e **W$SD** — todos computados a partir das decisões armazenadas
- **3BET%**: detectado quando hero re-raised pré-flop com `facing_size > 0`; coluna `is_3bet` na tabela `decisions`
- **W$SD**: detectado via `hero: shows` no raw_text (showdown real do hero); coluna `showdown_result` na tabela `decisions`
- **GGPoker parser**: suporte completo ao formato GGPoker — detecção automática por header, IDs `#SG.../#RC...`, hero sempre `Hero`
- **Fix hero detection GGPoker**: `HERO_DEALT_RE` usa `[^\[\n]+` para não capturar múltiplas linhas

### Corrigido
- `_normalize_action()` converte `'raises'` → `'raise'`; verificação `is_3bet` corrigida para os valores normalizados
- `_detect_showdown()` verifica `"hero: shows"` em vez de `"SHOW DOWN"` — elimina falsos positivos quando hero foldou
- `llm_explainer.py`: `e.get('field', 0)` retornava `None` quando campo existe com valor `None`; corrigido para `(e.get('field') or 0)` em 4 métricas de evolução
- Opacidade das células "em breve" no HUD elevada de `/25` para `/50` (visíveis)

---

## [2026-04-25e] — HUD Stats: fix 3BET e W$SD (normalize action + showdown participation)

### Corrigido
- **`backend/leaklab/pipeline.py`**: `is_3bet` verificava `'raises'/'all-in'` mas `_normalize_action()` converte para `'raise'/'jam'`; corrigido para os valores normalizados
- **`backend/api/app.py`**: `_detect_showdown()` agora verifica se hero mostrou cartas (`hero: shows`) em vez de apenas se houve showdown na mão — elimina falsos positivos quando hero foldou mas outros jogadores foram a showdown (reduz de ~100 para ~24 showdowns reais)

---

## [2026-04-25d] — HUD Stats: 3BET% e W$SD implementados

### Adicionado
- **`backend/database/schema.py`**: colunas `is_3bet BOOLEAN` e `showdown_result TEXT` na tabela `decisions`; migrations adicionadas para SQLite e PostgreSQL
- **`backend/leaklab/pipeline.py`**: flag `is_3bet` calculada em `build_decision_input` — True quando hero re-raised pré-flop com `facing_size > 0` (alguém já tinha apostado antes)
- **`backend/api/app.py`**: função `_detect_showdown(raw_text, hero)` detecta se mão foi a showdown e se hero coletou o pote; `is_3bet` e `showdown_result` propagados no enriched dict e salvos no banco
- **`backend/database/repositories.py`**: `save_decisions` inclui `is_3bet` e `showdown_result`; `get_player_stats` computa 3BET% (hands com is_3bet / total preflop hands) e W$SD (hands won at showdown / total showdown hands)
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: 3BET e W$SD removidos de `soon: true`; tipos atualizados para `number | null`; tooltips revisados
- **`frontend/src/lib/api.ts`**: `three_bet` e `w_at_sd` tipados como `number | null`

---

## [2026-04-25c] — HUD Stats: fix visibilidade células "em breve" (3BET, W$SD)

### Corrigido
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: células 3BET e W$SD estavam invisíveis — opacidades do status `na` elevadas de `/25`→`/50` (valor), `/40`→`/60` (label e "em breve"), `/30`→`/50` (ref MTT); células ficam visivelmente "desabilitadas" mas legíveis

---

## [2026-04-25b] — GGPoker parser: suporte completo + fix hero detection

### Adicionado
- **`backend/leaklab/parser.py`**: suporte a GGPoker — detecção automática por header (`Poker Hand #`), split regex por site, ID regex `#(\w+)` para prefixos SG/RC/HD; função `parse_hand_history()` unificada detecta site e parseia qualquer arquivo
- **`backend/api/app.py`**: `_detect_site()` atualizado para reconhecer GGPoker; `_extract_financials()` soma `collected X from pot` do hero para calcular prize em Spin & Go

### Corrigido
- **`backend/leaklab/parser.py`**: `HERO_DEALT_RE` alterado de `[^\[]+` para `[^\[\n]+` — impedia que o nome do hero capturasse múltiplas linhas `Dealt to` de oponentes no formato GGPoker, onde cada jogador tem sua própria linha

### Alterado
- **`CLAUDE.md`**: menção ao suporte a GGPoker adicionada à descrição do projeto

---

## [2026-04-25a] — Player HUD Stats como strip full-width + LeaksPanel compacto

### Alterado
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: redesenhado como strip horizontal full-width com 4 células (VPIP, PFR, AF, Flop Bet) separadas por dividers; header com contagem de mãos; responsivo 2×2 em mobile e 4×1 em desktop
- **`frontend/src/components/hud/LeaksPanel.tsx`**: redesenhado como lista compacta — cada leak ocupa uma linha de ~36px com dot de severidade, label truncado, badge de contagem e botão Estudar inline; eliminados o card grande com parágrafo de descrição
- **`frontend/src/pages/Index.tsx`**: `PlayerStatsCard` movido para entre os KPIs e o grid principal (full-width, destaque máximo); removido do sidebar

---

## [2026-04-24d] — Player HUD Stats: VPIP, PFR, Aggression Factor, Flop Bet%

### Adicionado
- **`backend/database/repositories.py`**: nova função `get_player_stats(user_id, days)` que agrega decisões por mão e computa VPIP, PFR, AF (Aggression Factor) e Flop Bet% diretamente das decisões armazenadas
- **`backend/api/app.py`**: novo endpoint `GET /metrics/player-stats?days=N` que retorna o perfil de jogo calculado
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: novo card HUD exibindo as 4 stats computáveis (VPIP, PFR, AF, Flop Bet%) com barra de progresso colorida vs. referência MTT; 4 stats futuras (3BET, Fold to 3BET, WTSD, W$SD) exibidas como "Em breve" com tooltip explicativo
- **`frontend/src/lib/api.ts`**: interface `PlayerStatsResponse` e método `metrics.playerStats(days)`
- **`frontend/src/pages/Index.tsx`**: `PlayerStatsCard` adicionado à sidebar do dashboard

### Referências MTT usadas
| Stat | Ref MTT | Status |
|------|---------|--------|
| VPIP | 12–22% | ✅ Calculado |
| PFR | 9–18% | ✅ Calculado |
| AF | 2.0–4.0x | ✅ Calculado |
| Flop Bet | 40–65% | ✅ Calculado |
| 3BET | 4–8% | 🔜 Em breve |
| Fold to 3BET | 55–72% | 🔜 Em breve |
| WTSD | 25–35% | 🔜 Em breve |
| W$SD | 50–60% | 🔜 Em breve |

---

## [2026-04-24c] — Cartas do villain reveladas no momento do "shows", não só no showdown final

### Corrigido
- **`backend/api/app.py`**: `_build_replay_data` agora pré-escaneia o `raw_text` para linhas `player: shows [cards]` e acumula `current_revealed` conforme as ações ocorrem; `revealed_cards` é incluído em cada step de action e street (não apenas no step final de showdown)
- **`frontend/src/pages/Replayer.tsx`**: `buildSeats()` verifica `step.revealed_cards` em qualquer tipo de step, sem depender de `step.type === 'showdown'`; `revealed: true` é setado assim que o backend sinaliza as cartas

---

## [2026-04-24b] — Showdown na mesa + apostas posicionadas dentro da mesa

### Corrigido
- **`frontend/src/components/hud/PokerTable.tsx`**: cartas dos villains agora exibidas no showdown — nova prop `revealed` em `Seat`; condição `hidden` alterada para `!seat.hero && !seat.revealed`; chips de aposta movidos para fora do `SeatBubble` e renderizados como elementos absolutamente posicionados entre o assento e o centro da mesa via `betPosition(sx, sy, 0.42)`
- **`frontend/src/pages/Replayer.tsx`**: `buildSeats()` agora passa `revealed: true` para assentos de villain no step de showdown quando `revealed_cards` está presente

---

## [2026-04-24a] — Replayer conectado ao backend + botões de replay nas mãos

### Adicionado
- **`frontend/src/pages/Replayer.tsx`**: reescrito para consumir dados reais do backend via `GET /replay/<t>/<h>`; usa `useSearchParams` para ler `?t=` e `?h=` da URL; exibe mesa de poker com assentos, pot e board reais por step; log de ações com hero em destaque e erros marcados; painel de EV/feedback com equity, pot odds, M ratio e pressão ICM; estados de loading, erro e sem-parâmetros
- **`frontend/src/lib/api.ts`**: interfaces `ReplaySeat`, `ReplayStep`, `ReplayData`; método `tournaments.replay(tournamentId, handId)` → `GET /replay/:t/:h`
- **`frontend/src/pages/TournamentDetail.tsx`**: botão "Abrir no replayer" em cada card de mão (navega para `/replayer?t=<id>&h=<handId>`); botão "Replay completo" agora clicável (navega para primeira mão do torneio); link "Replayer" compacto na linha de ações quando análise IA já está carregada

### Corrigido
- **`frontend/src/pages/TournamentDetail.tsx`**: referência a `h.resultBb` (campo inexistente) substituída por `h.evDelta`

---

## [2026-04-23b] — UI leaklabs: onboarding, detalhe de torneio, AI Report

### Adicionado
- **`frontend/src/components/hud/EmptyDashboard.tsx`**: tela de onboarding para novos usuários — upload com drag-and-drop conectado ao `POST /analyze`, cards dos 3 módulos com estilo `tactical-corners`, dispara `onComplete` para refresh do dashboard
- **`frontend/src/components/hud/TournamentAiReport.tsx`**: painel lateral deslizante de análise IA por torneio — chama `POST /analyze/tournament-summary` com `tournament_db_id`, exibe resumo cacheado (`llm_summary`) se já existir, seções colapsáveis em markdown com tonal por tipo (erro/ponto forte/neutro)
- **`frontend/src/pages/TournamentDetail.tsx`**: página de detalhe de torneio — agrupa decisões por mão (`groupByHand`), filtra por severidade e street, exibe cartas com `PlayingCard`, integra `TournamentAiReport` com ID real do banco
- **`frontend/src/index.css`**: variáveis CSS para cartas (`--card-face`, `--card-suit-dark`, `--card-suit-red`) e utilitário `.tactical-corners` com pseudo-elementos de canto

### Alterado
- **`frontend/src/lib/api.ts`**: adicionado tipo `TournamentDecision`; `tournaments.get()` retorna `{ tournament, decisions }`
- **`frontend/src/App.tsx`**: rota `/tournaments/:id` com `TournamentDetail` protegida por auth
- **`frontend/src/components/hud/HudHeader.tsx`**: branding atualizado de "PokerLeaks.os" → "LeakLabs.ai"; item "Replayer" removido da navegação
- **`frontend/src/pages/Index.tsx`**: exibe `EmptyDashboard` quando não há torneios importados (primeiro acesso)
- **`frontend/src/pages/Tournaments.tsx`**: clique em linha navega para `/tournaments/:tournament_id`

---

## [2026-04-23a] — Integração completa backend + frontend React

### Adicionado
- **`frontend/src/lib/auth.tsx`**: contexto React de autenticação (`AuthProvider`, `useAuth`) — gerencia token JWT via `sessionStorage`, verifica `/auth/me` na inicialização, expõe `login`, `register`, `logout`
- **`frontend/src/pages/Login.tsx`**: página de login/registro com tabs, design HUD, mensagem de erro inline e redirecionamento automático se já autenticado
- **`frontend/.env`**: variável `VITE_API_URL=http://localhost:5000` para dev local
- **`backend/api/app.py` — `POST /coach/chat`**: endpoint conversacional do AI Coach; carrega leaks e evolução reais do usuário, chama `coach_chat_reply` e retorna a resposta do LLM
- **`backend/api/app.py` — `GET /coach/context`**: retorna `hands_analyzed`, `tournaments_analyzed`, `top_leaks`, `avg_score` e `standard_pct` do usuário para o painel de contexto do Coach
- **`backend/leaklab/llm_explainer.py` — `coach_chat_reply`**: função de chat conversacional com Claude Haiku; injeta dados reais de desempenho do jogador como contexto no system prompt

### Alterado
- **`frontend/src/App.tsx`**: adicionado `AuthProvider`, rota `/login` e `ProtectedRoute` (redireciona para `/login` se não autenticado) em todas as páginas internas
- **`frontend/src/components/hud/HudHeader.tsx`**: exibe username do usuário logado e botão de logout; `LogOut` icon via lucide-react
- **`frontend/src/pages/AICoach.tsx`**: conectado ao backend — carrega contexto via `GET /coach/context` na montagem, saudação inicial personalizada com dados reais, chat conectado a `POST /coach/chat` com loading state e scroll automático
- **`frontend/src/components/hud/UploadZone.tsx`**: lê arquivo como texto, chama `POST /analyze`, exibe feedback visual (loading → ok → erro) e dispara callback `onResult` para refresh do dashboard
- **`frontend/src/components/hud/LeaksPanel.tsx`**: aceita prop `leaks` da API; mapeia `avg_score` para severidade (crítico/moderado/leve); fallback para dados demo quando sem dados reais
- **`frontend/src/components/hud/BankrollChart.tsx`**: aceita prop `evolution` da API; plota lucro cumulativo real; fallback para dados demo
- **`frontend/src/components/hud/RecentTournamentsTable.tsx`**: aceita prop `tournaments` da API; formata datas, profit e place reais; fallback para dados demo
- **`frontend/src/pages/Index.tsx`**: busca `GET /history/evolution` e `GET /history/tournaments` na montagem; calcula KPIs reais (ROI, ITM%, Avg Buy-In, Total Eventos); refresh automático após upload
- **`frontend/src/pages/Tournaments.tsx`**: carrega lista real via `GET /history/tournaments`; loading state, filtro por rede e ordenação funcional com dados reais

---

## [2026-04-23i] — Migração frontend para React + TypeScript

### Alterado
- **Frontend migrado de HTML monolítico para React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui**
  - Base: projeto gerado pelo Lovable (poker-leak-finder) trazido para `frontend/`
  - `frontend/index.legacy.html` — backup do frontend vanilla anterior
  - `frontend/src/` — novo frontend React com arquitetura componentizada
  - `vercel.json` atualizado para build com `@vercel/static-build`
  - `.gitignore` atualizado: `frontend/node_modules/`, `frontend/dist/`

### Motivação
- Segurança: HTML monolítico sem isolamento de escopo, JWT exposto em JS inline, sem CSP
- Manutenibilidade: arquivo único de ~3000 linhas impossível de auditar e testar
- Arquitetura componentizada elimina classes de bugs de DOM stale e permite testes unitários

### Próximos passos
- Conectar API client (`src/lib/api.ts`) ao backend Flask
- Implementar autenticação (contexto JWT, rotas protegidas)
- Substituir dados mock por chamadas reais ao backend

---

## [2026-04-23h]

### Corrigido
- **Botão "Gerar Resumo" sem ação**: `tSummaryLoaded` persiste em memória durante toda a sessão do browser. Torneios com o mesmo PokerStars ID (após reset/reimport) bloqueavam silenciosamente a função `generateTSummary` na linha `if(tSummaryLoaded[tid])return`. Corrigido limpando o objeto em `_renderTournamentList` sempre que a lista é re-renderizada.

---

## [2026-04-23g]

### Corrigido
- **Coach IA retornava template estático**: `_call_llm_summary` usava `_json.dumps()` mas o módulo foi importado como `json`. O `NameError` era silenciado pelo `except Exception`, fazendo o sistema cair sempre no fallback estático. Corrigido para `json.dumps()`.

---

## [2026-04-23f]

### Corrigido
- **Coach IA — "Torneio não encontrado no banco"**: após importar um torneio, o objeto inserido em `tourns[]` em `_applyRealData` não tinha o campo `dbId` mapeado. O frontend buscava `tObj.dbId` para enviar ao endpoint `/analyze/tournament-summary`, encontrava `undefined` e mostrava o erro. Adicionado `dbId: data.tournament_db_id` ao objeto construído após a análise.

---

## [2026-04-23e]

### Corrigido
- **Frontend `API_URL` com `file://`**: ao abrir `index.html` diretamente do sistema de arquivos, `location.hostname` é `''` (string vazia) e a detecção de `localhost` falhava, direcionando todas as chamadas para o servidor de produção (Render). Adicionada verificação `!h` para cobrir o protocolo `file://`.

---

## [2026-04-23d]

### Corrigido
- **`load_dotenv` com caminho absoluto**: substituído `os.path.dirname(__file__)` por `Path(__file__).resolve().parent` em `app.py` para evitar falha no subprocess do Flask reloader que não resolvia caminhos relativos corretamente.
- **Timeout do study plan**: aumentado de 30s para 90s em `llm_explainer.py`; chamadas ao Claude Haiku para geração de plano com 400+ decisões podem ultrapassar 30s.

### Resultado
- Study plan com LLM funcional localmente: 6 cards gerados, resumo personalizado, `error: null`.

---

## [2026-04-23c]

### Adicionado
- **`backend/.env`** (gitignored): variáveis de ambiente para dev local (`ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`).
- **`python-dotenv`** adicionado a `requirements_dev.txt`; `app.py` carrega `.env` automaticamente via `load_dotenv()` na inicialização.

---

## [2026-04-23b]

### Adicionado
- **`backend/requirements_dev.txt`**: dependências para desenvolvimento local sem `psycopg2-binary` (incompatível com Python 3.13/Windows); ambiente local usa SQLite.

### Ambiente local
- Backend: `cd backend && python api/app.py` → `http://localhost:5000`
- Frontend: abrir `frontend/index.html` no browser (detecta `localhost` automaticamente e aponta para porta 5000)

---

## [2026-04-23]

### Corrigido
- **Imports `gaphunter` → `leaklab`**: 7 arquivos de teste importavam o nome antigo do pacote (`gaphunter`), causando `ModuleNotFoundError` em toda a suite `engine` e `regression`.
- **Coluna `raw_text` ausente no schema SQLite**: a coluna existia apenas na migração PostgreSQL; adicionada ao `CREATE TABLE` e à lista de migrações SQLite em `database/schema.py`, corrigindo 8 falhas na suite `database`.

### Adicionado
- **`CLAUDE.md`**: documentação para Claude Code com comandos de build/teste, arquitetura e stack.
- **`CHANGELOG.md`**: este arquivo.
- **`.gitignore`**: entradas para `backend/torneio_ingles.txt` (fixture local com dados pessoais) e `.claude/` (configuração do Claude Code).

### Resultado
- Testes: **227/227 passando** (todas as suites: engine, database, llm, api, regression).
