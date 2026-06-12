# Changelog

Todas as mudanÃ§as notÃ¡veis neste projeto serÃ£o documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Unreleased]

### feat(training): auditoria dos treinos — validação hand-aware, variedade no drill, sparring leak-first ✅

> Auditoria completa de Ghost Table + Sparring contra 3 requisitos do usuário (treinar os PRÓPRIOS leaks; variar; validar com padrão GTO sem validação indevida). **O que já estava certo:** ambos usam só decisões/mãos reais do jogador (zero mãos sintéticas/aleatórias); drill com SRS [3,7,14,28,60d] filtrando só erros GTO; mix do solver respeitado (freq ≥30% = correto, 10–30% = desvio). **4 problemas corrigidos:** **(1) VALIDAÇÃO INDEVIDA (o mais sério):** o gabarito usava a frequência AGREGADA da range — num board onde a range checa 60% mas a mão específica aposta 95%, checar ganhava "correto" indevido. Agora `_resolve_best_action_from_node` consulta a árvore POR MÃO (`hand_view_for_spot`, populada pela campanha de ontem) antes do agregado — validado com dados reais: 20/30 decisões postflop já gradeiam pela mão exata. **(2) Fallback heurístico silencioso:** resposta ganha `validation_source` (gto_hand|gto_range|gto_stored|heuristic) e os DOIS treinos exibem selo da fonte (âmbar quando heurística) — fim do "acha que é GTO mas não é". **(3) Monotonia no drill:** lote diversificado (máx 2 spots por grupo street/ação, completa se faltar) — sessão de teste saiu com 7 grupos distintos em 10 spots. **(4) Sparring aleatório:** `_pick_gto_hand` agora prioriza mãos QUE CONTÊM um erro GTO seu (aleatório dentro do grupo = variedade) — teste real: 8/8 sorteios com erro presente. Bonus: equivalência call/jam de 95%→90% do stack (90–95% marcava jam como erro indevidamente). Docs atualizados (validação/variedade, 3 locales). api 75 + database 52 verdes.

### feat(dashboard): trajetória de carreira como ESCADA visual no V2 ✅

> Análise profunda do card a pedido do usuário. Estrutura de dados está sã (projeção ELO-unificada desde 2026-05-28 — milestones SÃO as bands, régua única). As 3 fraquezas eram de formato: **(1) Milestones eram 4 linhas de texto** — o card chama "Trajetória" mas não desenhava trajetória. No V2 viraram uma ESCADA vertical: linha conectando as bands, ● preenchido na cor = alcançado (✓ verde), ◉ anel na cor = próximo alvo (≈ N meses), ○ apagado = fora de alcance no ritmo atual. **(2) Curva de ELO sem escala** (forma pura) — a legenda agora mostra "1400 → 1480" no V2. **(3) Blocking leaks ilegíveis** ("flop/fold" cru) — reuso do template `v2.causalSpot` → "Fold no flop"; zero chave i18n nova. Clássico congelado mantém os formatos antigos. Typecheck verde.

### fix(dashboard): carreira sem ELO triplicado + padrões cognitivos com escala honesta e dominante ✅

> Análise crítica dos dois cards a pedido do usuário. **Trajetória de Carreira:** o ELO aparecia 3× no mesmo card — bloco hero do topo (forma recente), box "Forma recente" (MESMO número + MESMA barra de progresso duplicada) e box "Histórico". No V2 os dois boxes viraram UMA linha compacta: "Histórico: [band] 1430 · +50 vs histórico" (delta colorido) — o hero já é a forma recente; ~90px de altura recuperados no card mais alto da grade. Clássico mantém os dois boxes (congelado). De quebra, 5 strings hardcoded em PT ("Histórico", "Forma recente", "Rating recente/histórico", "X pra Banda") viraram i18n `career.*` nas 3 locales — PT byte-idêntico, EN/ES deixam de exibir português. **Padrões Cognitivos (V2):** a barra usava `freq*200` — 30% de frequência desenhava 60% de barra (escala invisível = mentira visual); agora é RELATIVA ao padrão mais frequente. E ganhou hierarquia: padrões ordenados por severidade>frequência, o primeiro destacado como "Padrão dominante" (bloco tingido na cor da severidade — mesma linguagem do epicentro do causal). Typecheck verde.

### fix(causal): nomes legíveis nos chips + conclusão do que a análise significa ✅

> Dois feedbacks do usuário no mapa causal V2. **(1) Abreviações ruins ("FL Fold"):** o label do backend vem abreviado (street 2 letras + ação), ilegível pro jogador. O `node.id` carrega o spot cru (`flop/fold`) — o front agora reconstrói o nome legível via template i18n `v2.causalSpot` ("Fold no flop" / "Fold on the flop" / "Fold en el flop"; streets e ações seguem em inglês — termos de poker). Backend intocado (o clássico continua usando o label abreviado no grafo, onde cabe). **(2) Conclusão:** novo parágrafo "O que isto significa" no rodapé do card — síntese DETERMINÍSTICA dos próprios dados (relação mais forte: "A e B apareceram nas mesmas mãos N vezes, sinal de que um desencadeia o outro" + epicentro: "ligado a N outros leaks, corrigi-lo derruba a cadeia"). Sem chamada de LLM e sem duplicar o carrossel (que tem a narrativa de IA aprofundada) — conteúdos distintos. Substitui o hint genérico de leitura. i18n nas 3 locales. Typecheck verde.

### fix(hud-stats): sempre visível no V2 + faixa completa na visão do coach ✅

> Feedback do usuário: "o HUD precisa estar no V2... infos valiosas para o jogador E para o coach". Dois problemas reais: **(1) No V2** o card existia (onda 6) mas com gate `playerStats.total_hands > 0` — se a query atrasasse/falhasse, o card sumia SILENCIOSAMENTE (diferente do clássico, que sempre renderiza e deixa o componente mostrar o estado vazio). Gate removido: `hasData && <PlayerStatsCard v2 />` — visível sempre. **(2) Na visão do coach** (`StudentDetail`), o aluno aparecia com 8 pílulas cruas (StatPill) — sem faixas de referência MTT, sem cor de status, sem badge de confiança amostral, e faltando 4 stats (Fold vs Bet, BB Defense, Steal, Open Limp). Substituídas pela MESMA faixa completa `PlayerStatsCard v2` do dashboard do aluno — o coach lê na hora o que está fora da linha, com a mesma régua que o aluno vê. StatPill morto removido. Typecheck verde.

### feat(dashboard): mapa causal intuitivo no V2 — "quando você erra A, erra B junto" ✅

> Feedback do usuário: o mapa causal (grafo circular SVG com nós e arestas) é confuso — linguagem de engenheiro, não de jogador. Novo `V2CausalMapCard` (V2-exclusivo; clássico mantém o grafo): **(1) Epicentro** — o leak mais conectado (maior degree, desempate por severidade/frequência) destacado num bloco teal: "conectado a N outros leaks — corrigir este derruba a cadeia"; **(2) Relações rankeadas** — as 5 conexões mais fortes como linhas "chip A → chip B" (chips com cor de severidade) + barra de força da correlação em % + "juntos em N mãos". Mesma informação do grafo (nodes/edges/correlation/co_occurrences), zero topologia pra decodificar. Sem narrativa (carrossel). i18n `v2.causal*` nas 3 locales. Typecheck verde; validação visual pendente do refresh do usuário (browser do preview degradou no ambiente — servidores ok).

### feat(dashboard): UX-2 onda 6 — paridade completa do V2 com o clássico (KPIs, HUD stats, drift, onboarding) ✅

> Fecha os 4 elementos que o clássico tinha e o V2 não: **(1) EmptyDashboard** — usuário sem dados agora vê o onboarding completo no V2 (antes: hero vazio com "sem dados"); **(2) strip de KPIs** sob o hero — ROI (verde/vermelho por sinal), ITM% e eventos+mãos em 3 chips compactos (reuso das chaves `kpis.*`); **(3) Player HUD Stats** (VPIP/PFR/AF/C-Bet/3-bet/W$SD/BB Defense/Steal/etc com barras de range vs referência MTT e badge de confiança amostral) — faixa completa com prop `v2` (casca ring, clássico intacto, sem duplicar o componente de 300 linhas); **(4) alerta de drift cognitivo** — mesma detecção/dismiss-por-fingerprint do clássico, visual V2 (ring âmbar). Tudo via props novas do DashboardV2 (`showEmpty`/`kpis`/`playerStats`/`drift`); zero i18n novo (reuso total). Verificado ao vivo no preview: banner de drift renderizou com dados reais do usuário de teste ("2 sessões abaixo do baseline"), HUD stats presente, grade sem overlaps; typecheck verde. Com isso o V2 tem TODA a informação do clássico — nenhum card ou indicador órfão.

### fix(header): mensagens unificadas — coach chat + suporte num único ícone (mobile sem sobreposição) ✅

> Feedback do usuário: no mobile os dois ícones de mensagem (suporte + chat do coach) sobrepunham o logotipo (somados ao sino/idioma/conta, os controles passavam de 375px). Consolidação: **um único botão "Mensagens"** com badge somado (não-lidas do coach + respostas de suporte). Aluno COM coach → mini-menu com 2 itens ("Mensagens do Coach" / "Suporte"), cada um com seu badge; SEM coach (ou coach role) → clique abre o suporte direto, sem menu. Esc e clique-fora fecham. Medido a 375px: logo termina em 182px, controles começam em 185px — sem sobreposição, sem overflow; fluxo clicado de ponta a ponta no preview (menu → item → painel correto abre). "Suporte" hardcoded virou i18n (`messages.*` em common, 3 locales). Desktop ganha o mesmo ícone único (1 slot a menos no header).

### fix(dashboard): validação E2E do layout — masonry à prova de ambiente + header sem overflow em tablet ✅

> Validação completa do layout renderizado (V2 + clássico, 1440/800/375px) com auditoria de geometria DOM: overlaps, vãos, overflow, cascas, header, bottom nav. **(1) Masonry (`useMasonryRows`) reescrito em 3 pontos de robustez**, após flagrar cards sobrepostos: `apply` sempre lê `ref.current` (o React pode SUBSTITUIR o nó da grade num remount atrás de loading — um closure preso no nó morto escrevia spans em DOM desconectado); debounce por `setTimeout` em vez de `requestAnimationFrame` (rAF não dispara em páginas sem foco/webviews — masonry congelava); guard de `setInterval` 600ms que re-anexa observers quando a identidade do nó muda e só escreve estilo quando o span muda. Resultado auditado: V2 14 cards e clássico 12 cards com zero overlaps/vãos/spans vazios, mesmo em ambiente sem rAF. **(2) Header (HudHeader): overflow horizontal da página inteira em 768–1280px** (nav de 7 itens + controles = ~1250px) — nav agora rola horizontalmente DENTRO do header (`min-w-0 overflow-x-auto`, scrollbar oculta, itens `shrink-0 whitespace-nowrap`), controles e logo fixos, label do IMPORTAR só ≥lg (ícone antes). Zero mudança ≥1280px. **(3) Auditado e aprovado:** bg `#0A0E1A` uniforme, cascas `bg-card/60 + ring` consistentes em todos os cards dos dois dashboards, header sticky com blur, bottom nav mobile (7 itens, padding 112px correto), hero 1-col no mobile, sem elemento vazando em nenhuma largura. Sem footer no desktop (por design — observação, não bug).

### feat(dashboard): UX-2 onda 5 — casca V2 nos cards pesados compartilhados (dna, career, causal map, ProLock) ✅

> Fecha o último resquício visual do V2: `dna`, `career` e `causal_map` são modernos por dentro (radar, sparkline+milestones, grafo SVG) mas usavam a casca legacy (`border bg-hud-surface`), destoando da grade. Duplicá-los como cards V2 seria drift de manutenção (são os 3 componentes mais pesados do dashboard) — em vez disso, prop **`v2`** aditiva (default false → clássico byte-idêntico, mesmo precedente do `hideNarrative`) que troca SÓ a casca externa para `ring-1 ring-border bg-card/60`. `ProLockCard` (visto por usuário Free no lugar de career/cognitive/twin/causal) ganhou o mesmo tratamento. `renderCard` propaga o flag. Com isso o V2 é 100% consistente: toda a grade fala `ring bg-card/60` + barras de gradiente + anéis + recharts. Zero i18n novo, zero mudança no clássico. Typecheck verde.

### feat(dashboard): UX-2 onda 4 — últimos 4 cards legacy do V2 modernizados ✅

> Fecha a modernização visual do V2: `results`, `pressure`, `cognitive` e `twin` ganharam versões V2-exclusivas (clássico congelado intacto), trocadas via o flag `v2` do `renderCard` — ProLock continua num lugar só. **`V2ResultsCard`**: os dois percentuais ("% das vitórias com erro crítico" / "% dos críticos escondidos") viraram barras de gradiente em vez de caixinhas. **`V2PressureCard`**: barras com gradiente coloridas pelo delta vs baseline + tick teal marcando o baseline (linguagem do marcador de média do twin). **`V2CognitiveCard`** e **`V2TwinCard`**: casca V2 (`ring bg-card/60`), barras de gradiente, badges em pílula — e SEM o bloco de narrativa (a narrativa vive só no carrossel de IA, completando o dedup da onda 3 por construção). Zero chaves i18n novas (reuso total dos namespaces `resultsVsGto.*`/`pressure.*`/`cognitiveFailure.*`/`strategicTwin.*`). Com isso, TODOS os cards do V2 falam a mesma linguagem visual; não há mais "era legacy" na grade. Typecheck verde.

### feat(dashboard): UX-2 onda 3 — medição GTO moderna no V2 + dedup das narrativas de IA ✅

> Continuação da modernização do V2 (análise completa de hierarquia + replanejamento da grade antes de editar, método firmado). **(1) Dedup confirmado e eliminado:** as narrativas de IA apareciam 2× no V2 — no carrossel (`V2AiInsightsCard`) E repetidas dentro dos 4 cards completos (twin, cognitive, career, causal_map). `renderCard(id, {v2:true})` agora passa `hideNarrative` (prop nova, default false → clássico intacto) aos 3 cards e omite `narrative` no `LeakCausalMap`; no V2 os cards mostram só o detalhe único (spots, padrões, milestones, grafo) e a narrativa vive apenas no carrossel. **(2) Trio modernizado (cards V2-exclusivos; legados seguem no clássico):** `V2QualityCard` — anel cônico de 4 segmentos (correta/mixed/leve/crítico) com alinhado% central, linguagem radial do coverage; `V2PositionCard` — barras horizontais de alinhado% por posição (cor por faixa ≥70/≥50, marcador de crítico%), linguagem do street card; `V2BankrollCard` — lucro acumulado em AreaChart recharts com gradiente teal (espelho financeiro do EV trend vermelho), tabs de período, sem modo demo (sem dados → some e o masonry fecha). **(3) Grade replanejada em clusters temáticos:** medição GTO (quality 4 + position 8) → resultado (bankroll 6 + results 6) → perfil (dna + twin) → pressão (pressure + cognitive) → futuro (career + causal_map). i18n: 3 chaves novas `v2.*` nas 3 locales (cards reusam as chaves legadas `gtoQuality.*`/`gtoPosition.*`/`bankroll.*`). Pendência onda 4: restyle de results, pressure, cognitive, twin. Typecheck verde; clássico congelado sem nenhuma mudança visual.

### fix(gto): river sem sangria — nós agregados bloqueavam o solve hand-aware (flag require_hand_aware) ✅

> Feedback do usuário: "não tenho sangramento nenhum em river? bem estranho". Investigação no DB local: river tinha 79 decisões, 76 com `gto_label`, **0 com `ev_loss_bb`** (flop/turn recebiam EV). Causa raiz CONFIRMADA por solve ao vivo: os spots de river já tinham nós **agregados** no `gto_nodes` (`strategy_json` sem `tree_hash`, herança do worker antigo — river done=99 na fila, 0 com tree_hash) e o `lookup_gto` retornava esse agregado na hora (`source=postflop_db`) **sem nunca disparar o solve hand-aware** → sem entrada em `gto_tree_strategies` → `hand_view_for_spot=None` → `ev_loss_bb=None` → card zerado. A campanha (`precompute_tree_campaign.py`) pulava essas classes porque `pre.found` era True (cobertura hand-aware real: flop 47/192, turn 45/126, river **1/71**). NÃO era o card, nem o reanalyze, nem filtro de vilão (só 2 spots UNKNOWN no river). **Fix:** novo flag `require_hand_aware` no `lookup_gto` (default **False** = comportamento byte-idêntico, /replay intacto): quando ligado, nó agregado sem tabela por-mão não satisfaz o lookup — fura também o GTO Wizard (agregado sem hand_table) e cai no solve Texas real, que gera o `hand_table`. Campanha agora só pula classes que já têm `hand_strategy` e solva com `require_hand_aware=True`. Verificado: flag off = agregado + 0 tentativas de solve; flag on = solve disparado; engine 362 + regression 31 verdes. Fluxo de correção: rodar a campanha (re-solva ~296 classes agregado-only, todo postflop) e depois `reanalyze_all_labels.py`. **Resultado da campanha (4,9h, 265 solves + 26 cópias, 13 falhas; reanalyze 1460 verificadas / 224 atualizadas):** trees hand-aware flop 47→161, turn 45→126, river **1→71 (todas as classes)**; decisões com `ev_loss_bb` — flop 38→124 (sangria 1,7→78,5 bb), turn 38→96 (12,4→54,9 bb), river **0→53 (0→16,6 bb)**. Flop era o maior sangramento invisível.

### feat(deep-dive): análise de mão flagada como loop agêntico (GTO real + mão completa + histórico) ✅

> Terceira feature do desenvolvimento "loop, não prompt", e o caso mais limpo: análise on-demand de UMA mão (alto valor, baixo volume, aberta). O single-shot `analyze_single_decision` cravava um nó GTO genérico no prompt e pedia pro modelo ESTIMAR equity/pot odds. O deep-dive troca estimativa por **investigação**, com 3 ferramentas parametrizadas pela decisão fixa no servidor (o modelo escolhe O QUE investigar, nunca monta params): **(1) `get_gto_solution`** → `lookup_gto` com a MÃO REAL do hero (preflop ou postflop) = estratégia com frequência + EV por ação, verdade do solver em vez de chute; roda DB-only (`block_remote=True, allow_remote_solve=False`) pra nunca disparar solve remoto lento. **(2) `get_full_hand`** (nova query `get_decisions_for_hand`) → todos os streets da mesma mão, pro modelo conectar a linha. **(3) `get_my_history_here`** (reusa `get_decisions_for_spot`) → o erro é recorrente ou pontual? Nova seção "🔁 Padrão" no output. Saída em Markdown — mesmo contrato `{analysis}` do single-shot → frontend (TournamentDetail) inalterado. `deep_dive_decision_agentic` (Haiku 4.5, máx 6 iterações + síntese final forçada). Endpoint `/analyze/decision` prefere o loop (cache próprio `:deep`), cai no single-shot legado em falha (flag `DEEP_DIVE_AGENTIC`). Verificado: llm 44 + api 75 + database 52 verdes; derivação de params, loop e dispatch das 3 tools (incl. `lookup_gto` DB-only sem rede) testados isoladamente.

### feat(study): gerador de plano de estudos como loop agêntico (investiga cada leak) ✅

> Segunda feature do desenvolvimento "loop, não prompt". **Altitude diferente do coach chat:** num plano de estudos NÃO faz sentido buscar os dados de resumo sob demanda — o plano é um diagnóstico COMPLETO e sempre quer leaks + EV + HUD. Esses seguem pré-carregados (como no single-shot). O que o loop adiciona é **investigação de profundidade variável**: para os 2-3 leaks que mais custam EV, o modelo puxa as MÃOS REAIS por trás deles (`get_leak_hands` → nova query `get_decisions_for_spot`: cartas, board, ação vs ideal, bb perdidos) e o detalhe de alinhamento GTO (`get_gto_alignment` por street/posição), e ancora cada módulo em dados concretos do jogador — não conselho genérico. Saída estruturada via ferramenta terminal `submit_study_plan` (schema validado pela API → JSON sempre válido, sem strip de markdown nem recuperação de truncamento). `generate_study_plan_agentic` (Haiku 4.5, máx 8 iterações + forced `tool_choice` na entrega). Cache compartilhado com o legado (db_key `study_plan_current`, plano canônico único por aluno). Ambos endpoints (`/study/plan` e `/coach/student/<id>/study-plan`) passam por `_gen_study_plan`: prefere o loop, cai no single-shot legado em qualquer falha (flag `STUDY_PLAN_AGENTIC`, default on). Schema dos cards idêntico ao legado → frontend e overrides de coach inalterados. Verificado: llm 44 + api 75 + database 52 verdes; loop, force-submit e nova query testados isoladamente.

### feat(ai-coach): AI Coach Chat reescrito como loop agêntico (tool use) ✅

> Mudança de arquitetura: o AI Coach Chat deixou de ser single-shot (todo o contexto do aluno — leaks, EV, frequências, evolução — pré-carregado no system prompt a cada mensagem) e passou a ser um **loop agêntico**. O modelo recebe 5 ferramentas (`get_top_leaks`, `get_ev_leaks`, `get_player_stats`, `get_action_frequencies`, `get_recent_tournaments`) e busca SOB DEMANDA apenas o dado relevante à pergunta — perguntas conceituais não disparam nenhuma query. Loop manual em `coach_chat_reply_agentic` (Haiku 4.5, raw HTTP, máx 6 iterações + síntese final forçada). Segurança: `user_id` injetado pelo servidor a cada execução de ferramenta — o modelo escolhe QUAL dado, nunca DE QUEM. Endpoint `/coach/chat` prefere o loop e cai no single-shot legado em qualquer falha (flag `COACH_CHAT_AGENTIC`, default on). Frontend (`AICoach.tsx`) ganhou chip "Consultou: leaks/EV/…" por resposta, tornando o loop visível; i18n `tools.*` nas 3 locales. Verificado: 44 testes llm + 75 api verdes, loop e dispatch de tools testados isoladamente.

### fix(ev): re-análise agora persiste ev_loss_bb + V2 sem leak finder duplicado ✅

> Dois feedbacks do usuário. **(1) "Onde você sangra" só mostrava preflop:** causa raiz — `reanalyze_all_labels.py` atualizava label/ação mas NÃO o `ev_loss_bb`, então decisões postflop existentes nunca ganhavam EV (só re-upload). O script agora sincroniza `ev_loss_bb`/`ev_loss_source` do `result['gto']` (preservando o antigo quando o novo é None — não apaga EV preflop do overlay). Fluxo completo: campanha de precompute → reanalyze → streets postflop aparecem no card. **(2) Leak finder duplicado no V2:** o ranking "Leaks por custo" do hero SUBSTITUI o `LeakFinderCard` — removido do `CARD_ORDER` do V2 (no clássico continua intacto).

### fix(dashboard): dots do carrossel de IA invisíveis sobre o fundo azul ✅

> Feedback do usuário: os indicadores de página do `V2AiInsightsCard` usavam `bg-muted/40` — contraste ~zero sobre o gradiente azul do card. Dots refeitos na família do azul (inativo `blue-200/25` + ring `blue-300/40`; ativo `blue-300` com ring e scale), tamanho up pra `size-2` (toque melhor) + tooltip com o nome do insight.

### feat(dashboard): UX-2 onda 2 — "onde você sangra" por street + carrossel de insights da IA ✅

> **(1) `V2StreetEvCard`:** bb perdidos por street em barras horizontais com escala compartilhada e cor por street (preflop roxo → river vermelho) — 1 olhada mostra onde o estudo rende mais. Backend: `get_ev_summary` ganhou `by_street` (SUM(ev_loss_bb)>0.05 por street, ordem canônica; validado com dados semeados). **(2) `V2AiInsightsCard`:** as narrativas de IA (Strategic Twin, padrão cognitivo, projeção de carreira, mapa causal) consolidadas num CARROSSEL premium (gradiente azul, setas + dots, aspas de citação) — 1 slot rotativo no lugar de 4 cards gigantes, como no mock; usuário Free vê lock com CTA Pro (`aiLocked`); os cards completos seguem na grade abaixo. O Index monta as narrativas dos dados JÁ buscados (zero fetch novo) e passa ao V2. Layout: carrossel col-7 + street col-5 na segunda linha do bento. i18n `v2.street*/ai*` (3 locales). Cards exclusivos do V2 — v1 congelado intacto.

### feat(dashboard): UX-2 onda 1 — gráficos modernos no V2 (área de EV + anéis de cobertura) ✅

> Usuário liberou remodelagem total dos cards do V2 (incl. novos tipos de gráfico, benchmark de tecnologia). Método combinado: ondas com validação visual — esta é a onda 1, com dados já disponíveis. **(1) `V2EvTrendCard`:** evolução do EV perdido/100 por torneio em AreaChart (recharts, gradiente vermelho translúcido, grid pontilhado discreto, tooltip dark — linguagem Linear/Vercel; "menor = melhor"). **(2) `V2CoverageCard`:** cobertura do solver em ANÉIS radiais (conic-gradient puro, sem lib) pre/post + nota viva de "postflop cresce sozinho". Backend: `get_ev_summary` ganhou `series` (EV/100 por torneio, últimos 12, gate de 5 decisões por ponto) e `coverage` (% decisões com gto_label por street group) — validado com dados semeados. Cards novos são EXCLUSIVOS do V2 (componentes próprios; os compartilhados com o v1 não foram tocados — congelamento respeitado). i18n `v2.trend*/cov*` (3 locales).

### fix(dashboard): DashboardV2 sem vãos — masonry real na grade de cards ✅

> Feedback do usuário: cards curtos deixavam blocos vazios na grade do V2 (grid 2-col com linhas esticadas pela altura do vizinho). Reusada a solução já existente do clássico: `useMasonryRows` (mede a altura real de cada card e seta `grid-row-end: span N`) + `grid-flow-dense` + spans de coluna do `SECTION_SPAN` — cards curtos liberam o vão e a grade empacota densa, mantendo a ORDEM fixa opinada do V2 (sem drag). Registrada também a decisão do usuário: os cards do V2 têm liberdade total de remodelagem (não precisam manter o visual atual) — vira o escopo do UX-2.

### feat(dashboard): DashboardV2 atrás de toggle — hero "Hoje" com EV/100 e leaks por CUSTO (UX-1) ✅

> Segunda entrega do redesign (specs/ux-proposal-2026.html), mesmo modelo v2 chaveável do card do replayer: `DashboardV2` nasce AO LADO do Index clássico (v1 byte-intocado; toggle persistido `dashboard_v2`, pills de ida/volta nos dois layouts). **Hero "Hoje"** responde a pergunta certa em 3s: **EV perdido/100 decisões** (métrica-líder — só possível com o ev_loss_bb hand-aware; tendência últimos 5 torneios vs 5 anteriores; gate de 10 decisões pra taxa honesta), **% de decisões sólidas**, e **CTA do leak mais caro** ("FOLD quando o melhor era CALL · flop · −4,2bb → Treinar agora" → /training). **Leaks por CUSTO**: novo `GET /player/ev-summary` (`get_ev_summary`) agrupa decisões por (street, jogou, melhor) e rankeia por SUM(ev_loss_bb) com share do prejuízo (pareto) — contagem de erros vira dinheiro. Abaixo do hero, os cards existentes REUSADOS em ordem fixa opinada via o próprio `renderCard` do Index (zero duplicação; masonry arrastável fica só no clássico). i18n `v2.*` em dashboard.json (3 locales). Validado: get_ev_summary funcional com dados semeados (ranking/share/tendência conferidos), py_compile, esbuild parse, JSONs ok; tsc/build no CI.

### feat(replayer): DecisionCardV2 atrás de toggle — custo em bb como manchete (UX-3) ✅

> Primeira entrega do redesign (specs/ux-proposal-2026.html), no modelo "v2 chaveável" decidido pelo usuário: layouts novos nascem AO LADO do atual (shells separados, componentes compartilhados), troca instantânea por toggle persistido (`localStorage replayer_card_v2`, default clássico) — rollback sem deploy, v1 congelado (só bugfix; tag `ux-baseline-v1` criada). **A mesa NÃO foi tocada** (decisão registrada: é cenário de gravação dos professores). O `DecisionCardV2` é prop-compatível com o v1 e INVERTE a hierarquia: v1 = dados sempre visíveis + prosa no toggle; v2 = história primeiro — **custo da decisão em bb como manchete** (−0,8bb vermelho/âmbar por severidade; "máximo EV ✓" verde quando jogou a melhor), "Você → Melhor" em 1 linha, evidência (range + Sua mão), **"Por quê" sempre visível**, e a matemática (SPR/equity/sizing/proNotes) atrás do olho. Pill discreto acima do card alterna os layouts. i18n `card.v2*` (3 locales). Validado: esbuild Linux real (a validação anterior por esbuild era inválida — binário win32 no node_modules; corrigido com toolchain em /tmp), JSONs ok; `npm run build`/tsc no CI.

### feat(replayer): bloco "Sua mão" no card — freq/EV da mão específica vs a média da range ✅

> Item 4 do plano pós-solver: o card mostrava só a estratégia AGREGADA da range (barras); o aluno com AA via "check 60%" sem saber que AA aposta 90%. O `lookup_gto` (path de leitura postflop_db) e o step do `/replay` agora carregam `hand_strategy` (freq + EV por ação da MÃO, via `hand_view_for_spot`/tree_hash — nós antigos sem tabela: campo nulo, UI intacta). O `GtoStrategyPanel` ganha o bloco **"Sua mão · A♥Q♥"** sob as barras da range: mini-barras por ação com a frequência DA MÃO e o EV em bb — ações sub-ótimas mostram o custo em âmbar ("−0,5bb"). Agregação por ação-base igual à das barras (sizes somados; EV da base = melhor size). i18n `card.handStrat`/`handStratTip` (3 locales). Validado: 7/7 testes hand_view, JSON dos 3 locales OK, esbuild parse OK (tsc completo no CI/build — sandbox não comporta).

### feat(gto): campanha de precompute ISOMÓRFICA — cobertura postflop em massa ✅

> Item 2 do plano pós-solver. A Fase 1 mudou a economia do precompute: 1 solve agora serve TODOS os spots da mesma classe de árvore (board isomorfo × qualquer mão do hero) — e com a Fase 3, cada solve novo também traz a tabela por mão (veredito hand-aware + ev_loss_bb) pra classe inteira. Novo `scripts/precompute_tree_campaign.py`: varre as decisões reais, agrupa os spots postflop por classe isomórfica (street + board canônico + posições + stack/bet bucket + pot_type + pot) e solva 1 representante por classe, ordenado por **quantos spots reais cada CFR cobre** (maior cobertura primeiro; empate: river>turn>flop, SJF). O dedup do lookup_gto faz o resto: classe já solvada vira CÓPIA instantânea (`tree_cache`), nó existente é pulado — **resumível por construção**. `--dry-run` lista as classes sem solvar; `--limit N` pra rodadas parciais. Leitura do DB em modo ro (sem lock contra o app vivo). Fluxo: `--dry-run` → rodar → `reanalyze_all_labels.py` (atualiza labels armazenados com os nós novos). Métrica de sucesso (plano §4): % cobertura GTO postflop por torneio deve SUBIR sem custo extra; o chip do torneio ("pós X% · em análise") é o termômetro.

### feat(ev): EV loss do solver fecha o circuito até a coluna `decisions` no POSTFLOP ✅

> O #24 (`ev_loss_bb` — bb perdidos vs a melhor ação) existia só no PREFLOP (overlay estático de EVs do GW); o postflop — onde os erros caros vivem — nunca teve o número. Com a Fase 3, o `_enrich_gto` passou a calcular o EV loss da MÃO no nó CFR; este fix fecha o fio: `ev_loss_source='solver_hand'` no retorno → `result['gto']` → `save_decisions` persiste `decisions.ev_loss_bb`/`ev_loss_source` (colunas e save path já existiam do #24 preflop — zero migração). O `DecisionCard` do replayer já renderiza `evLossBb` sem gate de street (badge colorido por severidade ≥0,5/≥2bb) → o postflop **acende sozinho** nos próximos uploads/re-análises, sem mudança de frontend. Validado E2E (`test_hand_view.py` 7/7): nó+tabela por mão → engine devolve 0,5bb/'solver_hand' → save → coluna confere. Próximo (plano): campanha de precompute isomórfica pra adensar cobertura, depois ranking de leaks por CUSTO (bb) em vez de contagem.

### feat(solver): Fase 3 — veredito HAND-AWARE (estratégia por mão) + EV loss em bb ✅

> O maior salto de qualidade pedagógica do plano: o veredito GTO usava a frequência AGREGADA da range — num K72r a range checa 65% enquanto AA aposta 90%; o jogador com AA que apostasse era rotulado "misto" e o que checasse era "correto", ambos errados. **Rust:** o `solver_cli` agora emite `actions` (ordem canônica) + `hand_table` (por combo do range do hero: frequência E **EV por ação** via `expected_values_detail` — 1 traversal extra, custo ~zero vs o solve; EVs em bb, combos bloqueados/peso-zero omitidos). **Persistência:** nova tabela `gto_tree_strategies` keyed por **tree_hash** (1 row por SOLVE, nos 2 backends) — sinergia direta com a Fase 1: a árvore é compartilhada entre mãos/boards isomorfos, então UMA tabela serve todos os spots da classe; cópias do dedup continuam hand-aware. **Leitura:** `hand_view_for_spot(tree_hash, spot_board, hero_hand)` mapeia a mão do spot para os naipes do board do SOLVE via novo `gto_utils.iso_suit_map` (+`map_cards_suits`) e devolve `{frequency, ev_bb, ev_loss_bb}` por ação. **Engine:** `_enrich_gto` classifica pela **frequência da mão** quando a tabela existe (senão agregado — comportamento legado intacto) e expõe `hand_aware`/`hand_strategy`/`ev_loss_bb` ("este check custou 0,5bb"); gated por `GTO_HAND_AWARE` (default **ON** — seguro: binário antigo nunca popula a tabela → no-op). `lookup_gto` anexa `hand_strategy` nos paths tree_cache/remote_solver; worker e solve síncrono persistem a tabela. **Validado:** `test_hand_view.py` 6/6 — iso_suit_map property-based (40 boards × permutações round-trip), visão da mão em board isomorfo (AcQc acha a linha de AhQh), e o teste-chave do engine: mesma situação, bet de AhQh → `gto_correct` (mão 90%) com `ev_loss_bb=0.0`, check → desvio com `ev_loss_bb=0.5`, flag OFF → `gto_mixed` agregado (legado). **Deploy:** requer rebuild do binário na VM; tabelas nascem nos PRÓXIMOS solves (nós antigos seguem agregados — re-solve popula). Surface no card do replayer (UI) fica para a fase seguinte.

### feat(solver): Fase 2 — concorrência na VM, worker event-driven, fila shortest-job-first ✅

> O pipeline era serial em três pontos. **(1) VM:** `server.py` usava `HTTPServer` puro (1 thread) — um solve de minutos bloqueava `/health`, `/gw-spot` e os demais solves no backlog TCP (inclusive a causa raiz do "GW degraded pendura o /replay 20–80s"). Agora `ThreadingHTTPServer` (daemon threads) + `BoundedSemaphore`: até `GTO_MAX_CONCURRENT_SOLVES` (default 2) CFRs simultâneos, cada subprocesso com `RAYON_NUM_THREADS` = vCPUs÷concorrência (default; override `GTO_RAYON_THREADS`) — sem oversubscription. **(2) Worker do backend:** o loop varria a fila a cada 60s (latência média ~30s mesmo com fila vazia). Novo `leaklab/solver_signals.py` (módulo separado evita import circular): `enqueue_solver_spot` aciona `notify_solver_queue()` → o worker (`_solver_queue_worker_loop`) usa `event.wait(timeout=60)` — reage na hora; o tick de 60s vira só varredura de segurança (resets/retries). **(3) Fila:** prioridade era flop>turn>river — os solves CAROS na frente dos baratos. Invertido pra shortest-job-first (`_priority`: river 7 > turn 6 > flop 5; preflop 8 intacto): river/turn solvem em segundos e saem na frente, minimizando a espera média. O roteamento síncrono de spots pequenos no upload (item 2b do plano) ficou DISPENSADO: worker event-driven + SJF entregam o mesmo efeito sem mexer no caminho do upload. **Validado funcional** (servidor real em loopback + binário fake lento): `/health` em 5ms DURANTE 3 solves; 3 solves com semáforo=2 → 3,1s/3,2s/6,3s (2 paralelos + 1 esperando); `RAYON_NUM_THREADS` propagado ao filho; enqueue acorda o worker imediatamente; SJF conferido. **Deploy na VM:** requer restart do serviço (e rebuild do binário p/ Fase 0) — **gated no backup do binário** (`solver_cli.baseline-20260611`, ver solver-rollback.md). Defaults na VM 4 vCPU: 2 solves × 2 threads.

### feat(solver): Fase 1 — dedup de solves por tree_hash + isomorfismo de naipes ✅

> Ataca o desperdício dominante do solver: a MESMA árvore CFR era resolvida várias vezes. Causa dupla: (1) o `spot_hash` inclui a mão do hero, mas a mão **não é input do solver** (que só vê board+ranges+stack+facing) — cada mão diferente do hero na mesma situação pagava um solve idêntico; (2) sem isomorfismo de naipes, `As Kd 2c` e `Ah Kc 2d` (mesmo jogo) eram solvados separadamente — há 22.100 flops brutos mas só 1.755 classes estratégicas (~12,6×). **Novo:** `gto_utils.canonical_board_key` (forma canônica do board sob as 24 permutações de naipes — lex-min, flop como conjunto, turn/river posicionais) e `compute_tree_hash` (identidade da ÁRVORE: street + board canônico + ranges + pot + stack + facing + hero_is_ip; SEM hero_hand e sem params de convergência). **Plumbing aditivo** (zero quebra nos read paths legados): coluna `tree_hash` em `gto_nodes` (+índice) e `gto_solver_queue` (2 backends); `enqueue_solver_spot` computa o tree_hash do spot_json automaticamente (todos os callers beneficiados sem mudança); `insert_gto_nodes` grava. **Dedup em 2 pontos:** o `lookup_gto` (solve síncrono) e o `run_solver_worker` (fila) consultam `get_gto_node_by_tree_hash` ANTES de solvar — árvore já solvada (outra mão do hero ou board isomorfo) vira CÓPIA instantânea do nó (estratégia agregada é invariante à mão e à permutação de naipes), `source` preservado, worker reporta `copied`. Nós antigos (tree_hash NULL) continuam servidos por spot_hash; novos solves populam o dedup daqui pra frente (banco é de teste — decisão registrada). **Validado:** `test_tree_hash.py` 10/10 (property-based de isomorfismo com 60 boards aleatórios × permutações; integração worker copia em vez de solvar — `copied=1, solved=0`); suites no sandbox: gto core 160/160, database 22/22, engine ~290 verdes (api/regression no CI — sandbox não abre o DB dev pelo mount e estoura timeout nos testes de equity, limitação de ambiente pré-existente).

### chore(solver): Fase 0 do plano de otimização — iterações reais, stdin direto, build reprodutível

> Início do plano `specs/solver-improvement-plan.md` (baseline: tag `solver-baseline-v1` + `specs/solver-rollback.md`). **(1) `iterations` mentia:** o output do `solver_cli` ecoava `max_iterations` em vez das iterações reais do CFR. O `run()` agora usa loop manual com `solve_step`/`compute_exploitability`/`finalize` — réplica exata do `solve()` upstream (mesma cadência de check a cada 10 iterações, conferida contra o fonte vendorizado) — e devolve a contagem real. **(2) stdin direto:** `server.py::solve` e `gto_solver._call_solver` passavam o spot via temp file (criar → reabrir → unlink a cada solve); agora `subprocess.run(input=...)` — sem I/O em disco, sem lixo órfão. **(3) Build reprodutível:** `postflop-solver` pinada no rev `9d1509f` (o mesmo do Cargo.lock) e fonte vendorizada em `solver_cli/vendor/` — upstream com desenvolvimento suspenso. **Atenção:** o binário da VM precisa de rebuild para o (1) valer em produção — antes, fazer o backup do binário (`solver_cli.baseline-20260611`, passos no solver-rollback.md). Validado: py_compile + teste funcional do caminho stdin nos 2 call sites; assinaturas conferidas contra o fonte da lib.


### feat(solver): Fase 2 — ranges corretas de POTE 3-BET no solver postflop ✅

> 19% dos spots postflop são pote-3bet, mas o solver sempre usava ranges **SRP** (opener RFI / caller call-vs-RFI) — larga demais (incluía lixo offsuit que ninguém paga vs 3-bet). Agora detecta o tipo de pote e usa as ranges REAIS capturadas: 3-bettor = `vs_RFI[opener][3bettor].raise_hands` (polarizada); caller = `vs_3bet[opener][3bettor].call_hands` (capada, mais forte). **Design backward-compat (zero regressão no SRP):** `compute_spot_hash` ganhou `pot_type` que, vazio/`srp`, **omite a chave → hash IDÊNTICO ao legado**; só `3bet`/`4bet` geram hash distinto (sem colisão com nós SRP). Read-only (`/replay`, engine) prefere o nó 3-bet e **cai no nó SRP** se o 3-bet não foi solvado (nunca pior). Plumbing: `hand_state_builder` deriva opener/3bettor/pot_type → spot (`potType`/`preflopOpener`/`preflop3bettor`) → engine + `/replay` + precompute. `scripts/precompute_3bet_pots.py`: 44 spots → 21 solvados, 23 já cobertos, 0 falhas. **Validado:** a mão de referência teve o veredito CORRIGIDO — o turn bet do hero saiu de `gto_critical` (check 92%/bet 8% com ranges SRP erradas) → `gto_mixed` (check 57%/**bet 42%** com ranges 3-bet); SRP intacto (hash legado byte-idêntico, +teste de regressão); gto 229/229, engine 362/362, api 42/42. **4-bet (1% dos spots) cai na aproximação SRP** (sem mapeamento de range 4-bet — fora do escopo). **Plano de sizing/3bet-light + solver IP/3bet-pot: COMPLETO.**

### feat(solver): Fase 1 — cobertura GTO p/ hero IP enfrentando aposta (postflop) ✅ DEPLOYADA

> Fecha a lacuna em que hero IP enfrentando aposta (ex.: pote 3-bet, OOP c-beta, IP dá flat call) não tinha veredito GTO (era bloqueado de propósito). Novo `navigate_to_ip_facing_bet` no `solver_cli/src/main.rs` (root → OOP bet closest(facing) → IP age) + reescrita do bloco de navegação do `run()` (4 casos agora). Liberado no `gto_solver.py` atrás do flag `TEXAS_HERO_IP_FACING`. **Deployado na VM** (binário rebuildado) + flag ligado + **precompute** (`scripts/precompute_ip_facing_bet.py`: 57 spots únicos → 26 solvados, 31 já cobertos, 0 falhas). **Validado:** binário na VM retorna `fold/call/raise/allin` (jogador certo, sem o bug original); a mão de referência `t=27 h=100000009` flop/call (IP vs 7,13bb) saiu de heurístico → `gto_mixed` (call 45%); **60 decisões IP-facing-bet agora cobertas, 0 heurísticas, 0 com bet/check errado**; reanálise atualizou 27 labels; gto 229/229, api 42/42. Precompute usa `facing=facingToBb` + `bb_chips=1.0` (hash em BB consistente com engine/replay; `_facing_solver_bb` em BB pro solver). **Caveat (Fase 2):** ranges ainda SRP — paridade com a cobertura OOP atual; correção de ranges de pote 3-bet é a próxima fase.

### fix(replay): tooltip da equity NECESSÁRIA repetia o texto da equity ESTIMADA

> No card preflop em modo audit, a linha de equity estimada e a de equity necessária mostravam o MESMO tooltip (`reqVsRandom/Range`, que descreve a equity *estimada* vs aleatória/range). A linha necessária reusava o override de `showAuditPreflop`. Removido: a necessária agora usa `reqSolverContextTip` (spot com solver — margem neutra, coerente com `isPpMuted=true` em audit) ou o tooltip de break-even (`reqTipRaw/Adjusted/Implicit`). Os dois ficam distintos.

### feat(coach): bloco de anotação em TODO spot do hero, não só nos erros

> O bloco de anotação do coach só aparecia quando a decisão era erro (gate `is_error` em `coachAnnotation`, `currentDecisionId` e no render). Removido o gate: o coach pode anotar qualquer spot do hero (jogada correta/marginal também — reforço, contexto, leak fino). O `decision_id` resolve da lista completa de decisões (`get_decisions` retorna todas); o backend já devolve `coach_annotations` de todas as decisões da mão. Mantido o gate `is_hero`.

### chore(reanalyze): re-análise dos labels do banco após o fix de facing-bet

> Rodado `reanalyze_all_labels.py` pra sincronizar os labels armazenados com o engine corrigido: 1460 decisões verificadas, **76 atualizadas**. Os spots postflop que enfrentam aposta tinham label `None` (não populado) ou desatualizado — agora preenchidos com o nó vs-bet correto (ex.: o flop fold vs 4,9bb da mão de referência: `None → gto_correct`; **36 folds facing-bet** que constavam como "mistake" viraram `standard`; None caiu de 87→61, sendo os 61 restantes genuinamente sem cobertura). Isso corrige o **dashboard/leak-finder/stats** (que leem o label armazenado) — o card do replayer já estava certo pelo fix do override. Script ganhou `PRAGMA busy_timeout=30000` (DB dev roda com o app.py vivo em WAL).

### fix(replay): nó GTO errado em decisão postflop que ENFRENTA aposta (recomendava "Bet" impossível)

> Bug sistêmico no /replay: numa decisão postflop **enfrentando uma aposta** (call/fold/raise), o card mostrava o nó de **PRIMEIRA AÇÃO** (bet/check) — recomendando "Bet", que é impossível quando há aposta na frente, e marcando o fold/call do hero como "Desvio Crítico". Causa: o override do /replay passava `facing_size_bb = decision.get('facing_bet')` ao `lookup_gto`, mas esse campo vem do **nó já casado** (=0 no nó de aposta), não do spot real → o hash batia no nó de facing=0 (bet/check). Corrigido pra usar o facing REAL do spot (`facingToBb`, em BB) — exatamente o que o `decision_engine` já usava (por isso o engine sempre esteve certo; só o override do display divergia). Ex.: flop fold enfrentando 4,9bb saía "Desvio Crítico / GTO recomenda Bet"; agora `gto_correct` com **fold 61% / call 19% / raise 15% / allin 5%** (o fold é a ação GTO mais comum). Preflop não é afetado (lookup_gto preflop ignora `facing_size_bb`). api 42/42.

### fix(stats): W$SD vazio no dashboard — showdown_result nunca era populado

> O indicador **W$SD** (`w_at_sd`, PlayerStatsCard) vinha vazio ("—"): a coluna `showdown_result` estava NULL em **todas** as 1467 decisions. `_detect_showdown` só reconhecia o formato de AÇÃO do PokerStars (`Hero: shows [...]`), mas estes dados (GGPoker) revelam as cartas só na seção **SUMMARY** (`Seat 4: Hero showed [...] and lost`, passado, sem `:` após o nome) → nunca casava → None. Novo `parser._extract_showdown_result` lê o SUMMARY (won/lost/None pelo veredito do hero; formato comum a PokerStars e GGPoker), exposto em `ParsedHand.showdown_result`; `_detect_showdown` agora delega a ele (mantém o fallback antigo). Backfill das 1467 decisions existentes (56 showdowns: 34 won / 22 lost) → **W$SD = 60,7%**. Uploads futuros populam automático. +1 teste; suíte completa 886/886.

### feat(sizing): Fase 3 — sizing postflop por heurística de textura (spots SEM nó GTO)

> Fecha o plano de sizing. Em spots postflop **sem cobertura GTO** (multiway/deep/sem nó) não há solver pra comparar — então `sizing_advisor.analyze_postflop_texture_sizing` dá um guia heurístico: board **seco** → aposta pequena (~33%, range bet — sem draw pra cobrar); **molhado** → maior (~66%, cobra os projetos); **muito molhado** (flush/straight) → grande (~85%+). `_board_texture` classifica dry/wet/very_wet por naipes+conexão; nudge IP/OOP + SPR baixo (comprometido tolera menor). **Bandas LARGAS de propósito** — em spot sem solver a latitude é grande, então só sinaliza OUTLIER claro (a aposta minúscula que não cobra o draw, o overbet sem motivo), não cada desvio do alvo de teoria; o `ideal` é o que o tooltip ensina. Só `bets` (não raises). Bloco "Sizing" no card mostra "33% · board molhado — pequena demais; o padrão é ~66%". Validado real: dos bets postflop sem nó, 15 ok / 11 flag (todos apostas ≤38% em board molhado — padrão real de small-ball do hero). +9 testes (29 no `test_sizing_advisor`); api 42/42.

### feat(sizing): #3 — tamanho do 3-bet vs padrão (IP ~3x / OOP ~4x, squeeze sobe)

> Fecha o conceito de 3bet-light com o sizing. `sizing_advisor.analyze_3bet_sizing` mede o 3-bet do hero como **múltiplo do open enfrentado**: IP ~3x, OOP ~4x (OOP cobra mais p/ negar realização e levar fold), squeeze (cold caller no meio) sobe ~1x. Dados do spot: `facingToBb` (open em bb), `isInPosition`, `callerPosition` (squeeze). Só raise enfrentando exatamente 1 raise (jam tem size forçado → fora). Bloco "Sizing" no card mostra "3,0x · IP no padrão (~3x do open)" / âmbar quando desvia. Validado real: 28 três-bets (3,0–3,3x IP, 3,5x OOP → todos ok). +7 testes (22 no `test_sizing_advisor`); api 42/42. **3bet-light agora completo: correção (range GW) + rótulo de intenção + 3bet% por oportunidades + sizing.**

### fix(stats): 3bet% do hero — denominador corrigido pra base de oportunidades

> O 3bet% do hero (`/metrics/player-stats` → `three_bet`, exibido no PlayerStatsCard) usava o denominador **errado**: `is_3bet` ÷ **todas** as mãos preflop. O padrão (HM/PT) é `is_3bet` ÷ **oportunidades** (mãos enfrentando um open, `facing_bet > 0`) — usar todas dilui o número ~3–5× e mascara overaggression. Nos dados reais do hero o stat saltou de **5,1% (parecia saudável, dentro de 4–8%) → 10,0% (overaggressive)** com 460 oportunidades. Agora gateado em ≥12 oportunidades (mesmo gate do `opponent_stats`) e expõe `three_bet_opp`. Tooltip do card explicita o denominador. database/api verdes. **Próximo no 3bet-light: #3 sizing do 3-bet (IP ~3x / OOP ~4x), junto da Fase 3 do sizing.**

### feat(3bet): rótulo de intenção do 3-bet — valor / merge / light(blefe)

> Ensina o conceito de **3-bet light**. A *correção* do 3-bet já era coberta pela range preflop do GW (a porção light está dentro do range polarizado); faltava o rótulo que diz QUE TIPO de 3-bet é. `bet_intent.threebet_strength_tier` classifica pela força preflop: **valor** (QQ+, AK — domina o continuing range), **merge/valor fino** (77–JJ, AQ/AJ, A6s+, broadways suited Q+, KQo), **light/blefe** (A2s–A5s, 22–66, suited connectors, mãos fracas — 3-beta por fold equity + blocker). `classify_3bet_intent` anexa `justified` pelo veredito GTO (intenção ≠ correção). Computado no engine (raise preflop enfrentando exatamente 1 raise = 3-bet/squeeze), flui via `live_decisions` → `_build_replay_data`, e aparece no card como bloco **"3-bet"** (verde valor / âmbar merge / azul light, com tooltip explicando o porquê, incl. "vs calling station não funciona"). Validado real: 11 três-bets (KK→valor, AQo/KQo/KJs→merge, A8o/ATo→light), inclusive 3-bet jams. +7 testes (32 no `test_bet_intent`).

### feat(sizing): Fase 2 — tamanho da aposta postflop vs o size do próprio nó GTO

> Postflop o solver **já dá o tamanho** (`bet_33pct`, `bet_75pct`, `raise_119pct`…) com frequência — então aqui não é heurística, é comparação direta. `sizing_advisor.gto_main_bet_size_pct` pega a ação agressiva de maior frequência do nó e converte pra % do pote (`_size_label_to_pct`: `pct` direto, `bb` via pote, `x`=vezes-o-pote); `analyze_postflop_sizing` compara com o size do hero (% do pote antes da aposta) por razão relativa (≥1,5× = grande demais; ≤0,6× = pequena demais; senão ok). Computado no step do `/replay` (aposta/raise postflop do hero com cobertura GTO) e mostrado no mesmo bloco **"Sizing"** ("33% · no padrão do solver (~36% do pote)" / âmbar quando desvia). Validado real (torneio 148): apostas postflop do hero batem o size do solver (33%/36%, 50%/49% → ok). +7 testes (15 no total). **Fase 3** (futuro): sizing postflop sem nó GTO, por heurística de textura (seco→pequeno, molhado→maior) + IP/OOP + SPR.

### feat(sizing): Fase 1 — análise do tamanho do open preflop (vs padrão de teoria)

> Começo da análise de **sizing** das apostas do hero. Como as ranges preflop do GW só dão *quais* mãos abrir (não o tamanho), o open usa **heurística de teoria**: padrão **2–2,5bb** (min-raise moderno); **SBxBB** sobe (~2,5–3bb) porque abrir min dá ao BB preço bom demais pra completar; **iso sobre limp** sobe mais (3bb+). Novo `leaklab/sizing_advisor.py::analyze_open_sizing` → `{key, status, params}` (open_ok / open_big / open_sb_small / open_iso_small). O size sai do raw da ação (`raises X to Y` → Y/bb; o `amount` é o "by", não o "to"; o spot.`raiseSizeBb` era o facing, não o open do hero). Computado no step do `/replay` (só no open do hero, `preflopRaisesFaced=0`) e mostrado no card como bloco **"Sizing"** (verde ok / âmbar quando desvia, com tooltip do porquê). Validado em dados reais (torneio 148): opens do hero saem `open_ok` (abre no padrão) + caso de iso detectado. `test_sizing_advisor` (8, suíte engine); api 42/42. **Fase 2** (postflop): comparar o size do hero com o do próprio nó GTO (que tem `bet_50pct` etc.).

### feat(table): chip do torneio — qualidade + cobertura GTO separada (pré/pós, postflop "em análise")

> Resolve a confusão do "44% GTO" de vez. O chip de status agora lidera com a **qualidade da sessão** (`standard_pct` — "80% sólido", o número que importa) e mostra a **cobertura GTO separada por street**: *"GTO · pré 92% · pós 10% · em análise"*. **Preflop** vem das ranges do GTO Wizard (cobertura ~imediata no upload, ~92%); **postflop** é resolvido sob demanda no GCP e **cresce com o tempo** — então é marcado **"em análise"** (postflop < 95%) em vez de cravar um % final, como o usuário pediu. Backend: `get_tournaments` passou a computar `preflop_coverage_pct`/`postflop_coverage_pct` (SUM por street). Frontend: chip redesenhado (qualidade no topo + split), tooltip explicando que postflop cresce conforme você revisa as mãos. i18n `table.qualitySolid/covPre/covPost/gtoAnalyzing/*Tooltip` (3 locales). Validado no #27 (std 80, pré 91.5%, pós 10.3%). tsc/JSON OK.

### copy(table): "44% GTO" → "cobertura GTO 44%" (era lido como nota de qualidade)

> O chip de status do torneio mostrava "✓ Analisado · {{pct}}% GTO" — a `gto_coverage_pct` (% de decisões COM nó GTO; o resto é heurístico). Mas "44% GTO" parecia uma **nota de qualidade**, contradizendo a narrativa ("80% das decisões dentro do padrão"). São métricas distintas: 44% = **cobertura** (quanto da sessão o solver analisou), 80% = **qualidade** (standard_pct, quantas decisões foram sólidas). Label reescrito pra **"cobertura GTO {{pct}}%"** (common + dashboard, 3 locales) — desambigua sem mudar o dado.

### feat(hud): Fase 3 — camada de EXPLOIT no card (ajuste vs GTO conforme o vilão)

> O ouro do HUD: o card agora mostra um bloco **"⚡ Ajuste vs oponente"** que sugere o desvio **exploitativo** sobre o veredito GTO/heurístico, conforme o perfil do vilão. `opponent_stats.compute_exploit(action, best_action, bet_intent, street, profile)` retorna `{key, params, severity}` com 6 regras ancoradas em stat: **dont_bluff_station** (blefe vs station → desista, é −EV), **value_thicker_station** (value vs station → aposte maior/fino), **station_bets_strength** (station apostando = força → overfold), **call_wider_aggro** (vs maniac/LAG → pague mais largo), **overfold_nit** (vs nit → folde marginais), **bluff_more_nit** (nit foldão → blefe mais). **Disciplina inegociável: só dispara com `confidence='high'`** (arquétipo confiável) e cada regra carrega o stat que a justifica — sem amostra, nada (não substitui o GTO, é ajuste). Integrado no `/replay` (computa por step a partir do contexto da decisão + `villain_profile`); frontend mostra o bloco em vermelho (severity high) ou âmbar (medium), logo abaixo do perfil. i18n `card.exploit*` (3 locales). **Validado em dados reais:** hero vs `Croesy0822` (calling station, high) → `station_bets_strength` dispara ("passivo apostando = força, overfold"). `test_opponent_stats` +5 (14 total); api 42/42. Conclui as Fases 1-3 do HUD de oponente.

### feat(hud): Fase 2 — perfil do vilão no card do replayer (com selo de amostra)

> Surface dos perfis da Fase 1: o card de decisão agora mostra um bloco **"Oponente"** com o arquétipo do vilão do spot + stats (VPIP/PFR/c-bet/F→cb/AF/WTSD) e **selo de confiança**. Plumbing: o `hand_state_builder` passou a capturar o **nome** do vilão (não só a posição) na `metadata.villain_name` — incl. o caso HU em que o vilão deu check (reusa a detecção do fix anterior); o `pipeline` expõe `spot.villainName`; o `/replay` anexa `villain_profile` a cada step via lookup no `opponent_profiles` por `t['id']` (id local — resolve a indireção de id externo). Frontend: bloco com badge colorido por arquétipo (calling_station=âmbar, nit=azul, tag=verde, lag=laranja, maniac=vermelho) + tooltip com o read geral ("calling station → não blefe, value fino"); quando a amostra é baixa, mostra **"amostra baixa"** em vez de um arquétipo falso (mesma honestidade da Fase 1). Stats gateados aparecem só quando passam o denominador. Validado: demo (vilão SB → unknown/low, honesto) + dados reais (torneio 148, hero vs `bodyanich07` = **TAG**, high, 37 mãos). i18n `card.villain*`/`archetype*` (3 locales). Sem integração no veredito ainda (Fase 3). pipeline/api/regressions verdes.

### feat(hud): Fase 1 — motor de stats de comportamento de oponente (read-only)

> Início do HUD de oponentes (estilo HM/PT3, mas pós-sessão = coaching de exploit, não overlay em tempo real). O parser já captura as ações de **todos** os jogadores da mesa, então dá pra construir o perfil até de mãos onde o hero foldou. Novo `leaklab/opponent_stats.py`: varre as ações → stats por jogador com **numerador E denominador** (oportunidades) — VPIP, PFR, 3-bet, fold-to-3bet, c-bet, fold-to-c-bet, AF (agressão postflop), WTSD — e classifica arquétipo (`calling_station`/`nit`/`tag`/`lag`/`maniac`/`unknown`). **Regra inegociável (igual ao resto da plataforma): nenhum read sem amostra** — abaixo do gate (denominador mínimo por stat) a taxa vem `None` e o arquétipo fica `unknown`; a UI mostraria "amostra baixa", não um palpite. Tabela `opponent_profiles` (torneio × jogador, nos 2 backends), repo `upsert_opponent_profile`/`get_opponent_profiles`, e `scripts/compute_opponent_profiles.py` (computa + persiste + detecta dados anonimizados). **Validado nos dados reais:** 10/11 torneios têm screen name (só a demo é anonimizada); 187 perfis, **34 arquétipos de alta confiança** (17 TAG, 8 calling stations, 5 LAG, 4 nits) — ex.: `Croesy0822` calling station com VPIP 43% e WTSD 80%, exatamente o caso de uso. Confirma que `c-bet`/`fold-to-c-bet` só ficam confiáveis em amostras grandes (torneios longos). Sem integração no motor de decisão ainda (Fase 3). `tests/test_opponent_stats.py` (9, suíte engine). **NÃO funciona em GG anônimo** (sem nome estável).

### fix(replay): "Erro ao carregar" — override travava 20–80s na query GW degraded

> O `/replay` levava 20–80s (múltiplos de ~20s) em mãos com spots postflop não-cobertos → o proxy/frontend dava timeout → "Erro ao carregar o replay". Causa: o override do replay chamava `lookup_gto(block_remote=(not gto_label))` — e a flag tem semântica **invertida** (`block_remote=True` NÃO bloqueia; faz o lookup **cair na query GTO Wizard**, `query_spot`, timeout 20s). Em spot não-coberto (`gto_label=None`) virava `block_remote=True` → query GW; com o GW **'degraded'** no servidor, cada chamada pendurava 20s (1 por spot não-coberto → 20/40/60/80s). Fix: o override passa **`block_remote=False`** (short-circuit read-only — sem GW nem Texas; spot coberto retorna o nó cacheado antes do short-circuit). Replays que levavam 60–80s agora carregam em **0.5–1.2s**, sem perda de cobertura nem do racional.

### feat(replayer): racional da jogada recomendada em spots heurísticos (o "porquê")

> Em spots GTO, as barras de estratégia + a intenção explicam a jogada; em spots **heurísticos** (multiway, deep>200, sem vilão) o card só mostrava o veredito + equity/SPR, sem dizer **por que** check/bet/call/fold é o ideal. Novo `explain_recommendation` (em `bet_intent.py`, determinístico, espelha a lógica do engine: força de mão via `made_hand_category` + projeto + board molhado + nº de oponentes + pot odds) devolve `{key, params}` por ação recomendada (`check_marginal[_mw]`, `check_strong`, `bet_value`/`bet_protection`/`bet_semibluff`/`bet_thin`, `call_odds`, `fold_no_odds`, `raise_value`/`raise_semibluff`, `shove_commit`). Integrado no `evaluate_decision` (`result['reco_rationale']`) e threadado ao step do `/replay`. O `Replayer.tsx` mostra o racional (caixa "Por que essa é a melhor jogada") **só em spots heurísticos** (`!hasGto`) — onde não há barras de estratégia pra explicar; em spots GTO fica oculto pra não duplicar. i18n estruturada (`card.rationale.*` + `rationaleTitle`, params {{eq}}/{{n}}/{{req}}) nas 3 locales. Ex. (check fraco 3-way): "Mão fraca/média (28%) sem projeto forte, em pote 3-way. Apostar value-corta e blefar contra vários raramente passa — check controla o pote." tsc + JSON OK.

### fix(gto): Opção B completa (solve deep no cap + selo) + /replay read-only (sem solves degenerados)

> O river HU 156bb mostrava "Sem cobertura GTO / deep" em vez da **Opção B** (servir >60bb como aproximação capada em 60bb + selo "≈ Aproximação") que havíamos decidido. Causa: a Opção B vivia só no `_enrich_gto` (que SERVE o nó), mas o `lookup_gto` (que SOLVA) **bloqueava >60bb** — spots que só ocorrem fundos nunca ganhavam nó. **(1)** `lookup_gto` agora solva 60–200bb no cap de 60 (>200 = heurístico); `_solver_params` já capava. **(2) Bug grave achado no caminho:** o override do `/replay` chamava `lookup_gto` com `pot_bb = potSize` (**FICHAS**, não BB) e disparava um **solve Texas dentro da requisição web** → SPR colapsava → nós **degenerados** (jam 0.97 / exploitability 0.01 falso, a assinatura do pot-bug). Pior, solvava spots **multiway** como HU. Fix: novo param `allow_remote_solve=False` no `lookup_gto` (o `/replay` é **read-only** — nunca solva na requisição, só lê nó existente); pot corrigido pra `potBb`. Purgados 2 nós degenerados criados pelo override. **(3)** `gto_coverage='deep'` agora só >200bb; `gto_depth_capped` derivado AO VIVO no step (postflop coberto + stack>60 = aproximação) em vez da coluna armazenada (que a re-análise não atualiza). Solvados 17 spots deep HU + re-análise. Validado na mão 100000004: flop (multiway) → nota honesta; turn/river (HU 156bb) → GTO check + selo "≈ Aproximação". i18n `deep` reescrita (>200bb).

### fix(replayer): cobertura GTO honesta (sem "Processando" eterno) + rótulo Custo/Margem

> Dois ajustes no card postflop após feedback. **(1) "Processando" enganoso:** spots que o solver heads-up nunca cobre (multiway, deep>60bb, hero IP enfrentando aposta, sem vilão) mostravam "Análise GTO: Processando — sem cobertura" (sugere que vai resolver) e disparavam auto-solve inútil — contradizendo o veredito `Heurística` já exibido. Backend passou a mandar `gto_coverage` no step (`covered|multiway|deep|ip_facing_bet|no_villain|pending`); o card mostra uma **nota honesta estática** por motivo (ex.: multiway → "você aposta dentro de 2+ jogadores; o solver é heads-up, então o veredito é heurístico com equity ajustada") e o auto-request só dispara em `pending` (solvável, nó ainda não existe). **(2) Custo vs Margem:** uma margem POSITIVA (`+10.6pp`) rotulada "Custo" não fazia sentido (custo é perda) — o bloco agora é **"Margem"** quando o valor é ≥0 e **"Custo"** quando &lt;0. i18n `card.noCoverage.*` + `blockMargin` + `noCoverageTitle` (3 locales). tsc + JSON OK.

### ux(replayer): card de decisão postflop reorganizado em 3 blocos narrativos

> Validação de UX do `DecisionCard` (template de 5 slots está bom; o problema era o **Slot 4**, com 5 indicadores soltos sem hierarquia). Achados: (1) **redundância** — o badge `Força média`, o `Equity 29% (fraca)` e o `GTO aposta 20%` contavam a mesma história em 3 lugares (e o "20%" repetia a barra do solver); (2) **sem agrupamento** entre geometria (SPR/Sizing) e matemática (Equity/Mín.EV); (3) **punchline enterrada** — num "Desvio Leve" o número que decide é o custo, escondido como `+pp` minúsculo; (4) **hierarquia plana**. Reescrito (escolha do usuário) em **3 blocos rotulados** que contam a história *o que fiz → o que o solver faz → por quê → quanto custa → geometria*: **SUA MÃO** (intenção + equity, fundidos — remove a redundância e o "GTO 20%"), **CUSTO** (a margem promovida, com qualificador de severidade alinhado ao `gto_label`), **GEOMETRIA** (SPR + sizing numa linha). Só afeta o card **postflop**; preflop mantém seu layout (equity/req gated em `!isPostflop`). i18n `card.blockHand/blockCost/blockGeo` + `costAligned/costMinor/costCritical/costPlus/costMinus` (3 locales). tsc + JSON OK.

### fix(gto)!: nós postflop com a estratégia do JOGADOR ERRADO (hero IP) — auditoria + correção total + relatório HTML

> **Bug crítico de correção.** O solver Texas (CFR) devolve sempre a estratégia do **player 0 = OOP**. Quando o hero está IN POSITION, a estratégia correta é a do player 1 (IP), só obtida com a flag `hero_is_ip`. Caminhos que furaram o `lookup_gto` (`cleanup_postflop_pot_bug.py` + um solve manual) não passavam a flag e ainda atribuíam ranges assumindo hero=IP sempre → nós `solver_cli` postflop podiam conter a **estratégia do vilão** e/ou **ranges trocados**. Ex. real: flop 7♥6♣9♣ HJ(hero,IP) vs UTG+1 ia gravado como `bet 52.8%`; o correto (IP, ranges reais) é `check 78.3%` — o veredito do jogador virava do avesso. **Verificação do binário do GCP:** solves idênticos batem bit a bit (determinístico) e a flag muda o resultado de forma estável → o binário respeita `hero_is_ip` e o bug era real. **Correção:** habilitado `TEXAS_HERO_IP=1` (.env); purgados os **175 nós `solver_cli` postflop** suspeitos (backup em `reports/`); re-solvado todo spot postflop HU via `lookup_gto` (atribui IP/OOP e ranges corretos) → **46 nós corretos** (exploitability mediana 1.35%, máx 2.66%); as **354 capturas `gto_wizard`** (preflop + 306 postflop) **não foram tocadas**. **89–103 decisões postflop mudaram de veredito** após a correção. Spots que o solver HU não cobre (multiway, hero IP enfrentando aposta, stack >60bb, sem vilão) ficam **heurísticos honestos** (sinalizados ao jogador, não dado errado). Nova ferramenta `scripts/postflop_correctness_audit.py` (snapshot → backup+purga → re-solve correto → re-análise → auditoria → **relatório HTML** em `reports/postflop_correctness_audit.html`, veredito **CALIBRADO**; resumível via sentinel). **Clear-stale:** a re-análise agora ZERA `gto_label` quando não há nó ao vivo (antes preservava o label antigo → vereditos GTO órfãos sem solve por trás). Cobertura GTO HONESTA: **216/328 decisões postflop** com nó real; o resto é heurístico sinalizado (deep>60bb, multiway, hero IP enfrentando aposta, sem vilão). Exploitability dos nós: mediana 1.35%, máx 2.66%. Board-bug do river: **0 restante** (fechado). Validado end-to-end na API do replay com o backend usando a flag.

### fix(replay): postflop sem gto_label armazenado ficava preso em "processando" (nó nascido após o import)

> Chicken-and-egg no `/replay`: o `gto_strategy` (que dispara o override ao vivo + persistência do label) só era buscado `if decision and gto_label` — então uma decisão postflop cujo label armazenado é `None` (nó GTO solvado DEPOIS do import, ex.: re-solve ou fix de board) **nunca** pegava o nó → `hasGto=False` → card travado em "processando" pra sempre. Fix: para decisão **postflop do hero**, tenta o `lookup_gto` mesmo sem label armazenado, usando **só cache local** (`block_remote=True`, não dispara solve remoto lento dentro do replay); e o bloco de override ao vivo agora **reatribui o `gto_label`/`gto_action` do step** a partir da estratégia (ground truth), não só `is_error`. Validado na mão do usuário (river bet Ac6c em 5c4dAd Qh Td, 155bb): após solvar o nó (check 79.9%, exploitability 1.97%), o river passou de "processando" → **gto_minor_deviation / check** + badge "Força média · GTO 20%". api 42/42. **Nota:** a persistência no `decisions` depende de `_db_hand` (decisões do torneio resolvido); na mão-demo `t=999999` (número externo, id real 375) o match não bate e não persiste — irrelevante pro replayer (deriva ao vivo a cada load), afeta só telas de leaks/stats dessa mão específica.

### fix(parser): board do river perdia a 5ª carta no formato "[flop] [turn] [river]" (sem GTO no river)

> Bug que deixava o **river sem análise GTO** (preso em "processando" pra sempre). O `_board_for_street` (hand_state_builder) montava o board por street com uma regex que só combinava **2 colchetes** (`[flop+turn] [river]`), mas o histórico exportado usa o formato **separado** — `*** RIVER *** [5c 4d Ad] [Qh] [Td]` (um colchete por street, 3 grupos) — então a **carta do river era descartada** e a decisão do river ficava com board de **4 cartas**. Efeito duplo: **(1)** o lookup GTO ao vivo computava o hash de um "river" malformado → nunca casava nó → o card mostrava "processando"; **(2)** o auto-solve enfileirava o mesmo spot quebrado → o solver não produzia nó válido → loop infinito. Fix: `_board_for_street` agora extrai **todos** os colchetes da linha (igual a `parser._extract_board`), cobrindo os dois formatos. Flop/turn intactos. Validado na mão do usuário (100000004): river passa a montar `[5c,4d,Ad,Qh,Td]` (5 cartas) e o spot fica pronto pra casar/solvar o nó (flop/turn já casavam via Option B, `depth_capped`). Regressão: `test_pipeline.py::test_board_for_street_separated_brackets` (separado + combinado); pipeline/tournament/multi_decision verdes. **Nota:** o nó GTO do river ainda precisa ser solvado (a fila tinha um 'done' órfão, solvado com stack errado 88.5bb e sem persistir nó) — com o board correto, um novo request enfileira o spot certo e o nó nasce quando o solver GCP estiver livre.

### fix(postflop): intenção da aposta — textos didáticos p/ iniciantes + "misto" não vira leak

> Refina a feature de intenção da aposta após feedback do usuário (um spot onde o GTO aposta 21% — misto — aparecia como leak vermelho com texto cheio de jargão "value-corta"/"showdown value"). **(1) Coerência:** `classify_bet_intent` agora respeita o `gto_label` — se o nó classifica a ação como `gto_correct`/`gto_mixed`, **não é leak** (mesmo abaixo de 25% de frequência), alinhado ao selo de avaliação da mão; só `gto_minor_deviation`/`gto_critical` (ou sem nó) mantêm o flag de leak. **(2) Linguagem:** todos os textos reescritos pra jogadores iniciantes, sem jargão — o rótulo "O meio (leak)" virou **"Força média"** (vermelho só quando é leak de fato) e os tooltips explicam o conceito em palavras simples ("as mãos piores foldam e só as melhores pagam — você só leva call quando está atrás; quase sempre dar check é melhor"). Atinge o badge do `Replayer.tsx` (`card.betIntent*`, 3 locales), o bloco do `llm_explainer` e o `/docs` `replayer.p7` (3 locales). `test_bet_intent.py` +2 (misto não-leak / crítico leak) → 25; llm/tsc verdes.

### feat(postflop): classificação de INTENÇÃO da aposta — value / proteção / semi-blefe / blefe / "o meio"

> Responde "por que apostar?" (enquadramento de pokerbrasil.com.br/porque-apostar): toda aposta tem 2 razões legítimas — **value** (call de pior; subdivide em *showdown* e *proteção*, esta só flop/turn) e **blefe** (fold de melhor; *semi-blefe* = blefe com draw). Apostar uma mão mediana com showdown value é **"o meio"** — value-corta (só pior folda, só melhor paga) e costuma ser leak. Novo módulo `leaklab/bet_intent.py`: um **tier de força de mão feita** self-contained (`made_hand_category` → value/middle/air, espelha o `academy._hand_bucket` mas separa overpair/two-pair/set [sempre value] do top-pair [depende do kicker ≥Q] e corrige **boards pareados** — par do board é compartilhado, não conta como dois pares do herói), `_board_wet` (proteção só em board com draw), e `classify_bet_intent` que usa o tier + `equity_adjustment` (draw forte ≥0.15 = semi-blefe) e tem o **nó GTO como árbitro** (`gto_bet_freq ≥ 0.25 → justified`). Integrado no `evaluate_decision` (`result['bet_intent']`, só em aposta/raise postflop; `None` caso contrário). Superfície: **(1)** bloco "INTENÇÃO DA APOSTA" no prompt do `llm_explainer` (com a freq de aposta do GTO + alerta de aposta sem fundamento); **(2)** badge colorido no `Replayer.tsx` (value=verde, semi-blefe=azul, blefe=âmbar, "o meio"=vermelho/leak) com tooltip — threadado via `live_decisions` → step (`bet_intent`); **(3)** `/docs` `replayer.p7` (conceito, 3 locales). Separação limpa: o `is_leak` do intent só flagra "meio"/blefe sem fundamento — o `gto_label` continua sinalizando o erro GTO de mãos de value à parte (sem dupla-penalização: AA em board pareado = `value_protection` + `gto_critical`, não "meio"). i18n `card.betIntent*` (3 locales). Testes: `tests/test_bet_intent.py` (23, no runner em `engine`). Validado em apostas reais: JTo top-pair-fraco → "o meio"/leak, AA overpair → value, draws → semi-blefe; engine/api/llm verdes.

### feat(gto): opção B — selo "≈ Aproximação" no replayer (persistência + display)

> Completa a opção B: o flag `depth_capped` (GTO aproximado em spots >60bb) agora é **persistido e exibido**. Schema: coluna `gto_depth_capped` (decisions, nos 2 backends + migrações). Gravado no `save_decisions` (INSERT da análise) e via resync. O replayer (`/replay`) surfaceia `gto_depth_capped` no step (live path via `_gto_index` + stored), e o `Replayer.tsx` mostra um **selo "≈ Aproximação"** (badge teal) com tooltip explicando que o solve é capado a 60bb (limite de RAM) e servido a um spot mais fundo — direção confiável, frequências exatas podem variar; com servidor maior vira exato. i18n `card.depthCapped`/`depthCappedTip` (3 locales). Validado: o spot do usuário (flop 5h6hQd, 152bb) retorna `gto_correct` + `gto_depth_capped=True` na API do replay; build OK.

### feat(gto): opção B — aproximação por profundidade (>60bb) + fix do facing FICHAS→BB no engine

> Dois fixes no `_enrich_gto` (decision_engine, o lookup que computa o `gto_label` postflop): **(1)** o guard só confiava em nós `solver_cli` quando `stack ≤ 60bb` (cap de RAM do solve), então **spots fundos (>60bb) ficavam sem `gto_label`**. Opção B: passa a servir o solve capado a 60bb como **aproximação** até 200bb, marcando `depth_capped=True` (o guard de SPR/allin continua rejeitando shove fundo → a aproximação só vale pras ações depth-robustas: check/bet/call/fold/raise). **(2)** Bug de unidade: o hash do nó usava `facingSize` (**fichas**) em vez de `facingToBb` (**BB**) → `bet_bucket` errado → **nenhuma decisão postflop com aposta** (fold/call/raise vs bet) casava o nó → `gto_label` perdido em TODO facing>0. Corrigido. Validado no spot do usuário (flop 5h6hQd, 152bb): check → **gto_correct**, fold vs 4.9bb → **gto_correct** (GTO folda 64%), ambos `depth_capped`. **Nota:** o cap de 60bb é limite de RAM/CPU da VM — com servidor maior (64GB+) dá pra subir o cap e tornar o GTO profundo EXATO em vez de aproximado.

### feat(plans): fase 3 — UX de upgrade (cards 🔒 Pro no dashboard)

> Frontend do gating da fase 1: os 4 cards de insight avançado (Career, Cognitive Failures, Leak Causal Map, Strategic Twin) agora mostram pro usuário **Free** um **`ProLockCard`** — cadeado + badge "Recurso Pro" + nome da feature + CTA "Fazer upgrade" que abre o `CheckoutModal` (após upgrade, `refreshUser` troca o lock pelo card real). Gate no cliente por `user.plan` (espelha o backend; segurança continua no 402 do servidor). Novo componente `ProLockCard` + strings i18n `proLock.*` (badge/desc/cta + nomes das 4 features) nas 3 locales. Mantém o shell visual dos cards (não quebra o masonry). Validado com usuário free real (dados do aluno): 4 cards travados, básicos abertos, build OK, tsc OK, zero erros. (Os fetches avançados já têm `.catch(()=>null)` → o 402 é silencioso.) **`/docs`:** badge "Recurso Pro" (`proOnly`, 3 locales) nas 4 seções gateadas (causal_map, career, cognitive, twin) — o doc explica o conceito e sinaliza a disponibilidade no Pro.

### feat(plans): fase 2 — tetos diários (fair-use) + limite de fila por usuário no solver

> Anti-abuso pra o Pro não ser "ilimitado" literal (proteção da margem de IA e da VM única do solver). **Tetos DIÁRIOS** (resetam na virada do dia): Pro = **AI Coach Chat 50/dia** + **solves GTO 20/dia** (mensal segue ilimitado); Free = chat 0 (já bloqueado). **Limite de fila por usuário** no solver: máx **10** jobs ativos (`pending`/`solver_queued`) simultâneos no Pro, **3** no Free — 1 aluno não monopoliza a fila/VM compartilhada. Schema: colunas `ai_chat_today`, `solves_today`, `quota_day_reset_at` (nos 2 `CREATE TABLE` + ambas as listas de migração — ALTER IF NOT EXISTS p/ PG e tupla-checada p/ SQLite). `PLAN_LIMITS` ganha `ai_chat_per_day`/`solves_per_day`/`max_pending_solves`. Novas funções: `_maybe_reset_daily_quota`, `increment_ai_chat`, `can_send_ai_chat`, `count_user_pending_solves`, `can_enqueue_solve`; `can_request_solve`/`increment_solves` agora contam o dia também. Enforçado em `/coach/chat` (429 `ai_chat_daily_limit`) e `/player/hands/<id>/request-gto` (429 `solve_queue_full`). Validado: cota 4/4 (test_pro_unlimited→test_pro_monthly_unlimited_daily_capped), API 42/42, funcional (chat 50/50→bloqueia, fila 10→bloqueia, free chat bloqueado). **Fase 3** (UX de upgrade) a seguir.

### copy(plans): cards de preço só listam o que ESTÁ incluso + refletem o gating

> A pedido do usuário, os cards de plano (landing + CheckoutModal) agora listam **apenas features inclusas** (sem itens negativos tipo "✗ Sem AI Coach Chat"). O Free dizia *"Acesso a todas as features de análise"* — **falso** após o gating da fase 1 (insights avançados viraram Pro). Free agora: 2 torneios/mês · 15 análises/mês · **"Análise GTO, leaks e estatísticas"** · **"5 solves GTO sob demanda/mês"** (positivo, era o "✗ Sem AI Coach Chat"). Pro ganha **"Insights avançados de IA (Strategic Twin, Cognitive, Causal Map)"** como diferencial (logo após os "ilimitados"). 3 locales (PT/EN/ES) + a lista hardcoded do CheckoutModal. Validado: JSON OK, tsc OK, sem negativos, cards renderizam balanceados.

### feat(plans): fase 1 — calibra limites Free/Pro + gateia insights avançados (Pro)

> Definição de planos pré-prod (controle de custo de IA/solver). **`PLAN_LIMITS`** ajustado: **Free** = 2 torneios/mês · 15 chamadas IA/mês · **5 solves GTO/mês** (era 10 — a VM do solver é escassa) · sem AI Coach Chat · **sem insights avançados**. **Pro** (R$99/mês) deixa de ser "ilimitado" literal e ganha **fair-use**: 200 torneios/mês · 300 chamadas IA/mês · AI Coach Chat · solves ilimitados (teto diário vem na fase 2) · insights avançados. Nova flag `advanced_insights` + helper `_check_advanced_insights` → **gateia 4 endpoints** (`/player/career`, `/player/cognitive-failures`, `/player/strategic-twin`, `/player/leak-graph`) com **402 `upgrade_required`** pra Free — esses cards de IA "inteligente" eram abertos a todos e **sem cota** (brecha de custo) e agora viram diferencial Pro. Os helpers de cota existentes já enforçam limite numérico (`limit is not None and used >= limit`), então os tetos do Pro passam a valer automaticamente. Validado: testes de cota 4/4, API 42/42. **Fase 2** (tetos diários ai_chat/solves + limite de fila por usuário no solver) e **fase 3** (UX de upgrade nos cards + /docs) a seguir.

### fix(brand): rodapé da landing usa o logo oficial (era wordmark "GrindLab.ai")

> O rodapé da landing mostrava um wordmark manual *"GrindLab**.ai**"* (ícone genérico `BarChart3` + texto) — nome errado (o produto é **GrindLab Poker**) e fora da diretriz de marca (sempre usar o SVG oficial). Substituído pelo logo `grindlab_final_horizontal.svg` (`h-7`), que já exibe "GrindLab POKER". O copyright (`© 2026 GrindLab · …`) já estava correto. Validado: rodapé renderiza o logo, sem ".ai", tsc OK.

### chore(gto): script de limpeza do bug de pot_bb (purga + re-análise + re-solve postflop)

> Os nós `solver_cli` postflop existentes foram gerados com o pot bugado (fichas) → degenerados. Novo `scripts/cleanup_postflop_pot_bug.py`: (1) **purga** todos os nós `solver_cli` postflop; (2) **re-analisa** cada torneio do `raw_text` (`parse → build_decision_inputs_for_hand`) e, por spot postflop, monta o spot com o **pot correto** (usa `spot['potBb']`/`['facingToBb']`, já em BB — robusto, sem depender de `level_bb`), solve no GCP e insere. **Validado no spot do usuário** (flop 5h6hQd, A♣J♦): antes *all-in 92.5% / 0.0% fake*; agora **check 98.5% / 2.14% real** (sem aposta) e **fold 64% · raise 17% · call 14% · allin 5% / 2.25% real** (vs aposta) — estratégias mistas coerentes. Garantias: só `solver_cli` postflop; **preflop GW e `gto_wizard` intocados**; solve exige `GTO_SOLVER_URL` (GCP). `--tournament` p/ targetar, `--apply` p/ executar.

### fix(gto): pot_bb do solver em FICHAS→BB (causa de estratégias postflop degeneradas)

> Auditando o veredito de um spot (flop 5h6hQd, A♣J♦), o solver retornava **all-in 92.5%** com ace-high **ar** e **exploitability 0.0%** — nonsense. Diagnóstico: o spot enviado ao solver tinha **`pot_bb` em FICHAS** (ex.: 1914) em vez de BB (19.14). O `main.rs` faz `pot_chips = pot_bb * 100` → pote **100× inflado** → SPR colapsa (~0.03) → `force_allin_threshold` força **all-in** em tudo → estratégia degenerada + solve trivial com exploitability 0.0% fake (passava o portão de qualidade). Causa: no builder do spot (`app.py`), o **facing** era convertido (`/_level_bb`) mas o **pot não** — em 2 caminhos que solvam+persistem (enqueue do postflop ~L6890 e re-análise/sync ~L6518). **Fix:** dividir `potSize` (fichas) por `_level_bb`/`level_bb` nos dois, igual ao facing. **Validado:** com o pot correto (19.14bb), o mesmo spot dá **check 98.4% / bet_50pct 1.6%, exploitability 2.3% real** — coerente com poker (ace-high air OOP em 3bet pot → check quase sempre). **Implicação:** todos os nós `solver_cli` postflop existentes foram gerados com o pot bugado → degenerados; precisam ser purgados e re-solvados com os spots reconstruídos (próximo passo). O lote de repopulação foi PARADO. (`4167` é display/`block_remote=False`, não solva — inofensivo.)

### fix(gto): normalize_gto_action aceita labels de size do solver (causa real dos ~89% sem nó)

> Validando a cadeia GCP (`GTO_SOLVER_URL=http://34.70.251.42:8765` já no `.env`, carregado por `load_dotenv` no app), o `/solve` respondeu certinho (exploitability 0–5%, ótimo) — mas re-solvar os órfãos os marcava `rejected`, **0 nós novos**. Causa raiz (mais profunda que o purge): o solver devolve ações **parametrizadas** no `strategy_json` (`raise_119pct`, `bet_50pct`, `raise_2.5x`); o `insert_gto_nodes` validava cada ação com `normalize_gto_action`, que fazia só lookup num dict e devolvia a string crua se não achasse → `raise_119pct` ficava "inválido" → nó **rejeitado**. Isso derrubava a persistência de **quase todo** postflop do solver_cli (~89% dos jobs `done` sem nó — não era só o purge). **Fix:** `normalize_gto_action` agora colapsa os labels de size pro canônico (`bet*→bet`, `raise*/Nbet/*pct/*x→raise`); o `strategy_json` **armazenado mantém o size original** (só validação e `gto_action` usam a forma colapsada). Validado: `raise_119pct→raise`, insert passou a retornar 1, e um lote de 10 órfãos solvou 10/10 (+nó) via GCP (nós 38→48). Novo `scripts/resolve_postflop_orphans.py` resolve os órfãos **direto** (solve GCP + insert, processo fresco) — não depende do worker vivo (que pode ter código antigo) nem mexe na fila `pending` (sem race). `requeue_orphaned_postflop.py` ganhou carga do `.env` (guard reflete config real) + `--limit`. **Solver SEMPRE no GCP** (scripts exigem `GTO_SOLVER_URL`); preflop GW e `gto_wizard` nunca tocados.

### fix(gto): postflop Texas vira keeper (deleção desativada) + re-enqueue dos spots órfãos

> **Fix 2** (causa raiz do "sem solução GTO" em spots postflop HU): o `purge_stale_texas_postflop.py` apagava **todos** os nós postflop do Texas (`source='solver_cli'`) — uma migração única porque os antigos foram solvados no depth errado (capados ~20bb) — **mas deixava os jobs como `done`**. O worker só processa `pending`, então os spots purgados **nunca re-solvavam** → 648 jobs `done` sem nó → no-coverage permanente (todo postflop, HU inclusive, mostrava "sem solução"). **Mudança de política (usuário):** a captura postflop do Texas no depth correto agora é **keeper** — preservada como a mina de ouro preflop do GTO Wizard. Mudanças: (1) `purge_stale_texas_postflop.py` — **deleção DESATIVADA por padrão** (`--apply` só avisa); escotilha `--force` pro caso legado, e mesmo o `--force` agora **re-enfileira** (`done`→`pending`) os spots que apaga, pra nunca mais orfanar. (2) Novo `scripts/requeue_orphaned_postflop.py` — reseta os 648 órfãos atuais (`done`+postflop+sem nó) → `pending` pro solver regenerar. **Garantias de segurança:** ambos mexem SÓ em `gto_nodes`/`gto_solver_queue` de `source='solver_cli'` postflop — **nunca tocam preflop nem `gto_wizard`** (`gto_preflop_ranges` é tabela separada). O re-enqueue **exige `GTO_SOLVER_URL`** (solver roda no **GCP**, não local) — sem isso, recusa pra não disparar solve local. Validado: dry-run detecta 648 órfãos; purge `--apply` corretamente desativado. (Execução do re-enqueue = passo de ops no contexto GCP.)

### fix(replayer): mensagem de "sem cobertura GTO" não afirma mais "multiway" em spots HU

> No replayer, um spot postflop **sem nó GTO** mostrava *"Solver processou mas não retornou solução — spot **multiway** sem cobertura"* (`card.statusDoneNoSolution`) e *"Spot **multiway** sem solução..."* (`card.whyMultiway`) — mas esses textos eram um **catch-all hardcoded**: apareciam pra QUALQUER postflop sem cobertura, sem checar o nº de jogadores no pote (`livePlayers`). Resultado: um spot **heads-up** (ex.: Hero vs BTN no flop) era rotulado como "multiway", confundindo o diagnóstico. Fix: reescrito "multiway" → "postflop" nos dois textos (3 locales PT/EN/ES). O sinal de multiway **real** continua correto e separado — o badge `card.multiway` ("Multiway · N-way") só aparece quando `livePlayers ≥ 3`. (Fix 1 de 2; o Fix 2 — por que o nó GTO não é persistido em ~89% dos jobs `done` — está em investigação.)

### style(brand): crop do viewBox do logo horizontal (centraliza + aumenta) + header da landing

> O logo `grindlab_final_horizontal.svg` parecia "sentado alto" no header (menos respiro em cima que embaixo). Diagnóstico via `getBBox()`: a arte ocupa só ~y6→79 do viewBox de altura 100 (whitespace topo **6** vs base **21**) — o box estava centralizado (folgas 8/9px), mas a arte dentro do SVG não. **Fix não-destrutivo:** crop do `viewBox` `0 0 283 100` → `8 4.4 263 76` (limites reais da arte + ~1.5 de margem simétrica; nenhuma arte alterada). Resultado: a arte passa a preencher o box → **centralizada e ~22% maior** no mesmo `h-class` (logo no header: 136→166px de largura). Beneficia as **5 telas** que usam o logo (header logado, landing, login, replayer, coach-apply). **Header da landing** (pré-login): logo `h-8`→`h-12` e barra `py-3`→`h-16` p/ ficar **idêntico ao header logado** (medido: ambos 48px alto × 166px, folgas 8/9). Validado: build OK, sem clip, screenshots conferidos.

### feat(landing): hero banner por idioma do usuário (i18n)

> O hero da landing usava uma imagem única (`grindlab_og_1200x630.png`). Agora seleciona a versão por idioma — `grindlab_og_en/es/ptbr.png` — via `i18n.language` (base da locale: `pt-BR`→pt; fallback EN). Validado: pt-BR→ptbr, en→en, es→es. **Nota sobre o `og:image` social** (`index.html`): esse é lido por crawlers (WhatsApp/FB/Twitter) que não rodam JS nem têm "usuário/idioma" — não dá pra trocar por idioma do usuário client-side; ficaria por URL/locale + edge (não feito agora).

### refactor(dashboard): remove IcmBreakdown (redundante com PressureProfile)

> Auditoria de baixo valor: `IcmBreakdown` (barras de `standard_rate` por nível de ICM high/med/low/none) e `PressureProfileCard` (barras de `avg_score` por nível de pressão none/low/med/high vs baseline + detecção de colapso) usam **o mesmo eixo** (no MTT, pressão = ICM) — e o Pressure é estritamente mais rico (baseline-relativo + colapso + resumo). IcmBreakdown era uma versão fraca/redundante → **removido** (`DashSection`/`DEFAULT_SECTIONS`/`SECTION_SPAN` + render + import; `evo.icm` não tinha outro consumidor, `evo` permanece). Dashboard 13→12 cards; masonry absorve. **Pressure+Twin NÃO foram mesclados** (revendo a ideia inicial): são lentes estruturalmente distintas (curva-por-nível+colapso vs lista de spots custosos), merge prejudicaria ambos. Validado: tsc (só erros pré-existentes), 12 cards, zero erros.

### style(header): logo GrindLab h-10 → h-12 (48px no header de 64px)

> A pedido do usuário, mais um aumento do logo do header. `h-10` (40px) → `h-12` (48px) — ocupa ~75% da altura da barra (`h-16`/64px), com ~8px de respiro de cada lado (teto confortável sem crescer a barra). Validado: logo medido 48×136px, header 65px, balanceado com a nav, zero erros.

### refactor(dashboard): diferencia os 2 cards de leak em papéis distintos (sem remover)

> Auditoria: `LeakFinder` e `LeaksPanel` pareciam duplicados (ambos "lista de top leaks"), mas têm taxonomias diferentes no backend (`get_ev_leaks` agrupa por posição×street×ação e ordena por EV-bb; `get_leak_roi_impact` agrupa por spot `street/ação`, com drill/trend/`/study` amarrados a essa chave) — merge real seria caro. Optado por **mantê-los com papéis distintos e não-contraditórios**: **Leak Finder = diagnóstico de EV** (onde você perde mais bb — *o quê corrigir*); **Fila de Treino** (ex-"Top Leaks Detectados") **= plano de treino** (progresso no Ghost Table, trend, atalho Estudar — *e agora*). Recast só de `leaks.title`/`leaks.tooltip` nas 3 locales (PT/EN/ES) deixando o papel óbvio e referenciando o Leak Finder como o diagnóstico. Para o espírito casar, `get_leak_roi_impact` agora **ordena a fila por impacto de EV** (`ev_loss_monthly`, empate→`priority_score` p/ robustez com buy_in=0) e re-numera `priority_rank`. Validado: 3 JSON OK, backend compila, ordenação EV-desc confirmada com dados reais (user 13). Nenhum card removido.

### refactor(dashboard): consolida cluster GTO (remove matriz + alignment-by-street)

> Auditoria de duplicação: o "% GTO alinhado" aparecia em 5 superfícies (KPI #03, Quality, Alignment-by-street, Position, Matrix posição×street). A **matriz é a união de posição×street** — os cards de street e posição eram só os "totais de margem" dela; e a matriz **agrupava as 9 posições reais em 6 buckets** (`EP/MP/...`), perdendo a distinção UTG vs UTG+2 vs LJ que o card de Posição preserva. Consolidado para **Quality** (total + distribuição correct/mixed/minor/critical) **+ Position** (9 posições, o recorte mais acionável). **Removidos** os cards `matrix` (`GtoAlignmentMatrixCard`) e `alignment`-by-street (`GtoAlignmentCard`) do dashboard + a query `gto-matrix`. A query `gto-alignment` permanece (alimenta a KPI #03 "padrão"). Dashboard 15→13 cards; o masonry 2-col [[project_dashboard_2col_masonry]] absorve a remoção sem replanejar spans. Validado: tsc (só erros pré-existentes), build OK, 13 cards, 2 colunas pares, zero erros. (A matriz/street podem voltar numa tela de drill/detalhe se necessário.)

### fix(gto): aposenta fallback pro GTO Wizard — spots órfãos não travam mais "processando"

> O indicador "N spots sendo processados pelo solver GTO" ficava **preso pra sempre**. Causa: quando o solver Texas (HU-only) falha num spot que não cobre (ex.: **multiway postflop**, 5-6 jogadores), o job vira `failed` na `gto_solver_queue`; um worker em background (`_mark_failed_solver_jobs_as_wizard_pending`) re-marcava as decisions correspondentes como `gto_label='wizard_pending'` (fallback pro GTO Wizard) **a cada 30s**. Mas o **GW foi cancelado** e **também é HU-only** → multiway nunca resolveria por nenhum motor → órfãos eternos, e `get_user_pending_gto_count` os contava como "pendentes" indefinidamente. Fix: (1) **aposenta o fallback** — `_mark_failed_solver_jobs_as_wizard_pending` vira no-op e sai do loop do worker; spots sem cobertura ficam com `gto_label` NULL ("sem dado GTO", estado honesto que as agregações de alinhamento já excluem). (2) **migração de dados** — `wizard_pending` → NULL (2 decisions) e os 29 jobs `gto_solver_queue` `failed` → `unsupported` (status terminal; `failed` era lido SÓ pelo re-marker aposentado, então é seguro — defende contra o worker antigo ainda em memória re-marcar antes do próximo restart). **Validado:** após >1 ciclo do worker, `wizard_pending=0`, pending-count do usuário = 0, durável sem reiniciar o backend. Diagnóstico: ambos os spots presos eram BB-flop multiway (6 e 5 players). Follow-up opcional (não feito): pular multiway no enqueue p/ parar de gerar jobs `failed`.

### feat(dashboard): masonry de 2 colunas uniformes (gap-free, posição estável)

> Refino do bento: o grid de 12 cols com spans mistos (4/6/8) + `grid-flow-dense` ainda deixava **vãos residuais** — medindo a geometria real (Playwright sobre dados reais), o pior era **491px ao lado do card `career`** (span-8, 634px de altura, com um card curto de 143px do lado). Causa: `grid-flow-dense` com `auto-rows: auto` **não faz masonry vertical** (um card curto ao lado de um alto deixa o vão); e os `span-8` ocupam só cols 1-8 (nunca a coluna 3) → a 3ª coluna "secava" no rodapé (~789px). Solução em 2 partes: (1) **masonry real** via novo hook `useMasonryRows` — mede a altura de cada card e seta `grid-row-end: span N` (N = altura / 8px) com `auto-rows-[8px]` + `gap-y-0` + `grid-flow-dense`, então os curtos liberam o vão e o grid empacota (re-mede via `ResizeObserver`/`MutationObserver` + resize; desliga abaixo de lg). (2) **2 colunas uniformes** — todo card vira `lg:col-span-6` (largura uniforme é o que torna o masonry de fato gap-free; full-width vira "barreira" que dessincroniza as colunas). Resultado medido: vãos internos = só o espaçamento (~30px), zero buraco grande; 676px é largura ótima p/ tudo (matriz 13×13, time-series, listas, radares). `DashboardLayoutData` atualizado p/ o shape `{sections}`. **Validado** com dados reais (10 torneios): 15 cards, 2 colunas pares e packadas, build OK, zero erros. Avaliação 2-col vs 3-col-binário registrada (2-col vence em estabilidade + gap-freeness). Conforme [[feedback_dashboard_reposition_before_change]].

### feat(dashboard): redesenho do layout em grid bento (packing, sem espaços vazios)

> O dashboard usava **2 colunas independentes** (`main` 8/12 + `sidebar` 4/12), cada uma uma pilha vertical (dnd `verticalListSortingStrategy`) com `items-start` → a coluna mais curta deixava **buraco vazio** ao lado da mais alta, e tudo ficava **empilhado**. Redesenhado como **grid bento único de 12 cols** com `grid-flow-dense` (backfilla os vãos) + spans por **tipo de conteúdo**: scores/breakdowns span-4, matriz/comparações/LeakFinder span-6 (LeakFinder é carro-chefe), gráficos/mapa span-8; responsivo (1-col → md 2-col → lg bento). `useDashboardLayout` migrado de `{main,sidebar}` pra **lista flat única** de 15 cards (`DashSection` + `SECTION_SPAN`); persistência no novo shape `{sections}` (layouts antigos `{main,sidebar}` caem no default do bento — migração silenciosa). Dnd de reorder mantido (1 `DndContext` + `rectSortingStrategy`). Dedup de Pressure/ICM (apareciam em main E sidebar). **Validado com dados reais** (10 torneios): 15 cards, multi-coluna balanceado e packado, sem coluna vazia, tsc 0, build OK, zero erros de console. Conforme [[feedback_dashboard_reposition_before_change]]: plano de spans aprovado ANTES de editar. **Header:** logo GrindLab `h-8`→`h-10` (40px num header de 64px). **Favicon:** re-copiado `src/assets/brand/favicon.svg` → `public/` + cache-bust `?v=2` (o servido estava velho).

### feat(brand): rebranding visual LeakLabs → GrindLab

> Rebranding **visual apenas** (NÃO mudou: pacote `leaklab`, `LEAKLAB_SECRET`, serviço `leaklab-solver`, rotas API, schema, repo, ou chaves internas lowercase `leaklab_lang`/`leaklab:tournament-imported`/`leaklab_drift`). **Logos:** wordmarks de texto ("LeakLabs.ai") → SVG `src/assets/brand/grindlab_final_horizontal.svg` (header, landing, coach-apply); watermark da mesa `LEAKLAB`→`GRINDLAB`; favicon = `grindlab_icon_traced.svg` em `public/`. **Cores** (`index.css`): `--background` `222 47% 4%` → `225 44% 7%` (= `#0A0E1A`), `--foreground` → `206 19% 91%` (= `#E3E8EC`); `--primary` já era o teal `#2DD4BF` (sem mudança). **Fonte:** headings em **Chakra Petch Bold** (Google Fonts + regra `h1–h6`; `.font-mono` da HUD tem precedência); família `heading` no tailwind. **Texto:** `LeakLabs`/`PokerLeakLab`/`LeakLab` → `GrindLab` nas locales PT/EN/ES (landing/academy/onboarding) + labels (AccountMenu, CheckoutModal, TournamentAiReport "GrindLab AI Coach", mailto), filename do report (`grindlab-report-`), e `index.html` (title/description/author/og). **Validado:** tsc 0, build OK (SVG bundlado), browser na landing + login → logo renderiza, bg `rgb(10,14,26)` exato, "GrindLab" presente, **zero "LeakLab" visível**, zero erros de console. **Wordmarks que tinham escapado** (corrigidos): Login (logo + placeholder `coach@pokergrindlab.com` + "GrindLab AI Engine"), Replayer (focus mode), e o standalone `leaklab-replayer-v3.html` (title + watermark). **Favicon + OG (assets do usuário em `src/assets/brand/`):** favicon set completo em `public/` (`favicon.ico`, `favicon.svg`, `apple-touch-icon.png` 180, `favicon-192/512.png`) + `grindlab-og.png` 1200×630; `index.html` com os `<link>` + `og:image`/`twitter:image` = `https://pokergrindlab.com/grindlab-og.png`. (O filename `leaklab-replayer-v3.html` em si fica — é referência interna.)

### fix(gto): 2 bugs de borda do batch postflop Texas (river/board + posição UTG+1/+2)

> No batch de população postflop, 2 edge bugs cortavam cobertura. **(1)** 11 spots com `street='river'` mas board de **4 cartas** (a carta de river some no parser) faziam o `solver_cli` abortar (`HTTP 500: "expected = Turn, actual = River"`). Adicionado **guard de consistência street×board** no `lookup_gto` (flop=3/turn=4/river=5) → spots inconsistentes pulam pro heurístico em vez de mandar payload inválido pro solver. **(2)** as posições `UTG+1`/`UTG+2` (que o pipeline produz) eram **rejeitadas** no `insert_gto_nodes` — `_GTO_VALID_POSITIONS` só tinha `UTG1`/`UTG2` → o nó não persistia; adicionadas ao conjunto válido. Validado: river-4-cartas pula instantâneo (sem 500); `UTG+1`/`UTG+2` aceitos. Suíte 810/810.

### fix(gto): correção da integração postflop do Texas (P0 — jogador / facing / ranges)

> A análise profunda do motor Texas (ver `docs/texas_solver_analysis.html`) achou **3 bugs de correção** que faziam o postflop servir dados do **jogador/facing/range errados**. Corrigidos no lado Python (`gto_solver.py`). **(2.1 — jogador errado):** o `solver_cli` SÓ devolve a estratégia do `player 0` (OOP), mas o `gto_solver` atribuía o hero a `ip_range` e lia o player 0 → o nó guardava a linha do **VILÃO**. Agora `_postflop_hero_is_ip` determina OOP/IP pela ordem de ação postflop, as ranges vão pros jogadores **certos**, e o Texas **só serve quando o hero é OOP** (player 0); hero IP cai no heurístico até o patch do `main.rs` (ler `player 1`). **(2.2 — facing em fichas):** `facingSize` chega em FICHAS mas o solver navega em **bb** → param `bb_chips` no `lookup_gto` converte facing→bb pro solve; facing>0 só é servido quando o bb é informado (sem navegação errada; o hash segue em bucket grosso — fino é P1). **(2.3 — ranges genéricas):** o solve usava `_DEFAULT_RANGES` largas → agora usa as **ranges REAIS capturadas do GW** (`_captured_range_str`: RFI do opener IP + call do defensor OOP, pelo bucket de stack) com fallback. **Validado:** hero OOP (BB) enfrentando c-bet 2.5bb → defesa GTO coerente do HERO `{fold 57% / call 26% / raise 17%}`, exploit 3%, com as ranges reais; hero IP (BTN) → pula (sem dado do jogador errado). Suíte 810/810. **IP-hero (P0, parte Rust):** `main.rs` patcheado — `navigate_to_ip_decision` (root → OOP check → IP age) + lê `private_cards(hero_player)`/`expected_values(hero_player)`; lado Python passa `hero_is_ip` e tem a flag **`TEXAS_HERO_IP`** (default OFF). Fica gated até **`cargo build` + deploy do binário na VM** (senão o binário antigo ignora a flag e devolve o player errado). Após o deploy, `TEXAS_HERO_IP=1` libera os heroes IP (c-bet). **Batch:** `scripts/solve_postflop_texas.py` popula os postflop NULL via Texas — hoje cobre **64 spots OOP** (HU ≤60bb); os 88 IP esperam o deploy do `main.rs`.

### feat(gto): reativa o solver Texas (CFR) no postflop HU, com travas de depth/SPR

> Com a assinatura do GW cancelada (sai em dias), o postflop volta a ser coberto pelo **solver Texas** (`b-inary/postflop-solver`, a lib que o `solver_cli` já usa — comprovadamente HU, igual ao GW). Reativado COM as travas que faltavam. **O bug do "shove de 150bb" era DEPTH** (solve capado a 20bb servido a spot fundo via o bucket de stack), **não o solver**: comprovado variando o stack (10→60bb: zero jam, exploitability 1.3–2.5%, estratégia coerente por depth). Mudanças: **(1)** `gto_solver.lookup_gto` re-habilita o solve Texas no postflop, mas só **stack ≤60bb** (acima, o cap de 60bb viraria aproximação → heurístico honesto) e com o **depth REAL** (`_solver_params_for_stack`, effective stack correto); **(2)** `decision_engine._enrich_gto` volta a ler nós `solver_cli`, com **gate de ≤60bb** + o **guard de SPR** existente (jam postflop só com SPR ≤3, qualquer fonte); **(3)** **normaliza os labels do solver** (`bet_50pct`→`bet`, `bet_2.5x`→`raise`, agregando) antes de gravar — sem isso o `insert_gto_nodes` rejeitava (`ações inválidas: ['bet_50pct']`) e o nó nunca persistia; **(4)** purga os **541 nós `solver_cli` postflop antigos** (depth de solve desconhecido/errado, indistinguíveis dos bons) via `scripts/purge_stale_texas_postflop.py` — repovoam no depth real ao reanalisar/solve. **Validado e2e:** solve flop BTN 40bb → persiste (source `solver_cli`, strategy_json canônico `{bet,check}`) → `_enrich_gto` lê → `gto_label='gto_correct'`; trava >60bb pula (found=False). Suíte **810/810**. **Análise dos pendentes (decisão do GW):** preflop tem 49 NULL, mas só 10 pares são GW-cobríveis e um autocapture completo colheu **0** (todos `impossible`/`no_solution` — são limped/BB-special/SB-complete + edge misclassificado que o GW também não resolve); os 178 NULL postflop são agora trabalho do Texas. **Conclusão: nada a capturar do GW antes de desativar** — o grid preflop (95%+) já está no banco.

### feat(hand-builder): empate (split do pote) + run-out automático no all-in

> Dois pedidos do usuário. **(1) Empate/split:** no showdown o seletor de vencedor virou **multi-select** — marque 2+ jogadores e o pote é **dividido igualmente** (resto em fichas vai pro primeiro), gerando uma linha `collected` por vencedor no HH + no summary. **(2) All-in run-out:** quando ≤1 jogador ativo ainda tem fichas (o resto está all-in) e a aposta já foi igualada, o **betting fecha** — o builder **não pede mais ação a cada nova carta** (não há o que apostar, as fichas já estão no pote); só preenche as cartas do board até o showdown. Implementado via `bettingClosed` (≤1 jogador com fichas + aposta igualada) → força `streetComplete=true` → o render mostra o prompt de **carta do board** em vez do card de ação (não toca em `currentActor`). State `showWinner: string` → **`winners: string[]`**; `hhGenerator` aceita `winners[]` (precedência sobre o `winner` legado, que segue funcionando). i18n 3 locales (`split`, `tieHint`). **Validado e2e (browser real):** hero all-in + BB call → card de ação some e só pede o board; preenche flop/turn/river → showdown; marcar BB+BTN → pote 20050 dividido em **10025 + 10025** (2 linhas `collected`), hint de split visível, zero erros de console. hhGenerator.test 5/5 (2 novos: split + winner legado), typecheck limpo.

### fix(gto): captura GW postflop via /gw-spot (o /gto-wizard estava morto no servidor)

> Pra substituir os nós Texas (agora ignorados) por GW nos spots postflop, o worker `capture_postflop_gw.py` batia no endpoint **`/gto-wizard`** — que **replica headers de auth capturados por um refresh loop DESLIGADO nesse servidor** (`GW_AUTH_REFRESH=0`) → sempre `503 auth_unavailable`. (Por isso o `/health` mostra `gto_wizard: degraded`: é o estado **NORMAL** desse servidor, não defeito; logar o Chrome de novo não muda nada.) O endpoint que funciona é **`/gw-spot`**, que **dirige a página real do Chrome logado** a cada request (não depende de `auth_ok`). Worker reescrito pra usar `query_spot_raw` (`/gw-spot`) com a linha de ações **encoded**. Dois fixes no `gw_action_encoder`: **(a)** raise = o **"raise to" TOTAL** do raw (`"raises 1 to 2"` → `R2.0`), não o incremento (`R1.0` jogava a linha pra fora da árvore); **(b)** **ordem canônica do board** (flop por rank decrescente + naipe s,h,d,c; turn/river anexados) — o servidor casa o `board=` EXATO na URL da API do GW, então fora de ordem → `subprocess_timeout`. Guarda a estratégia da **mão específica** do hero (`hand_freqs[hand_type]`) sob hash idêntico ao engine (`facingSize` cru, sem dividir por bb — o `/bb` antigo nunca casaria o lookup). **Spots multiway são pulados** (o GW só resolve postflop HU; consultar multiway só gera timeout de ~35s) — seguem no heurístico, honesto. Preflight tolerante à instabilidade (a página Chrome do servidor é serial e ocasionalmente trava/recupera) + retry por spot. Comprovado: params reais de HAR → `found=True` (check 46% / raise 54%); o MESMO spot com board reordenado → timeout (confirma a sensibilidade de ordem). Captura `--apply --resync` rodada em todos os torneios.

### fix(gto): ignora o solver Texas no postflop (dava "shove de 150bb"); usa só GTO Wizard

> O solver Texas (CFR, `source='solver_cli'`) roda **capped a stack curto (~20bb)** por limite de hardware; servido pra spots FUNDOS via o bucket de stack, recomendava **all-in absurdo** (ex.: UTG flop 152bb, pote 16bb, SPR 9 → "jam 92%"). Pior: penalizava o hero por NÃO jamar — checks corretos viravam `gto_critical`/`small_mistake` ("desvio crítico" num check de river). **Fix:** (1) o engine **ignora nós `solver_cli` no postflop** (`_postflop_gto_lookup` usa só `gto_wizard`; sem cobertura → heurístico honesto); (2) guard de **SPR** (rejeita qualquer jam postflop com stack/pote > 3, de qualquer fonte) — precisou expor `potBb` no spot (pipeline); (3) o **solve on-demand não cai mais no Texas** (`gto_solver.py` — só GW pra postflop; sem GW → não-encontrado). Há **358 nós GW** (todos com strategy_json, confiáveis) vs 478 Texas (105 jams) — os Texas ficam no banco mas inertes. **Decisões já salvas limpas** com `scripts/resync_postflop_gto.py --apply`: **61 decisões** em vários torneios reais corrigidas (jam→check/bet/call), `gto_critical/small_mistake` falsos → `standard`/correto; postflop jam/allin **59 → 0**. Suíte 810/810. **Capturar GW** desses spots agora é só pedir o solve (o pipeline usa GW). **Obs.:** em prod, rodar o resync após deploy.

### fix(hand-builder): "calls" agora é o incremento, não o total (somava o open de novo)

> Bug no `hhGenerator`: a linha de call usava `a.amount` (o TOTAL investido na street) em vez do INCREMENTO. Então, ao pagar um 3bet depois do próprio open, somava o open de novo — open 200 + `calls 857` = 1057 (10.6bb) no Replayer, em vez de igualar a 857 (8.6bb). Agora a linha de call desconta o já investido na street (`calls 657`), igual a `raise` já fazia — blinds postados contam como investimento (BB pagando open de 250 → `calls 150`). `hhGenerator.test.ts` (3: call após open, cold call, BB descontando o blind). Mãos JÁ salvas corrigidas pelo `scripts/fix_builder_tournament_names.py` (agora também recalcula call increments da estrutura das apostas — idempotente; só mãos builder, uploads reais intactos): tid 999999 → `Hero: calls 657`, pot 2357 consistente. typecheck + build + vitest 30/30.

### chore(scripts): fix_builder_tournament_names — reprocessa torneios do builder já salvos

> Mãos construídas no builder ANTES do fix de naming têm nomes posicionais stale no `raw_text` (ex.: o assento que é BTN chamado "UTG+1"), que o Replayer exibia competindo com a posição. `scripts/fix_builder_tournament_names.py` reprocessa: detecta mãos do builder (todos os nomes em {posições} ∪ {P1..P9, Hero} — uploads reais com nicks são IGNORADOS), reescreve cada nome no `raw_text` pela posição derivada (assento+button, hero → "Hero") com substituição via placeholders (sem colisão), e atualiza `tournaments.hero`. Dry-run por padrão, `--apply` grava; idempotente. As decisões não mudam (já guardam a posição certa); só `raw_text` (que o `/replay` re-parseia) e o `hero`. Rodado local: tid 999999 (5 mãos) → button=BTN/hero=Hero, `_build_replay_data` confirma pos==nome em todos os assentos. Outros 10 torneios (uploads reais) intactos.

### fix(replayer/hand-builder): posições corretas na mesa do Replayer (nome = posição)

> Duas correções pra um mesmo sintoma (no Replayer, o BTN num assento cujo label dizia outra posição). **(1) Bug real no backend `/replay`** (`_build_replay_data`): a derivação de posição usava uma tabela "forward" fixa (`BTN,SB,BB,UTG,UTG+1,UTG+2,LJ,HJ,CO`) que só batia em 9-max e rotulava errado o MIOLO das mesas menores (6-max dava UTG+1/UTG+2 em vez de HJ/CO) — afeta QUALQUER replay não-9-max, inclusive uploads reais. Trocado pela derivação autoritativa (clockwise a partir do SB + nomeação por índice, igual ao engine `_infer_position`/Decision Card; 'LJ' não 'MP1'). **(2) Builder:** o nome do jogador no HH gerado agora = a POSIÇÃO da mão (hero = "Hero"); antes era um id (e, em mãos antigas, um rótulo posicional stale tipo "UTG+1") exibido no card do Replayer competindo com a posição. Remap só na geração do HH (estado interno segue id neutro `P*`); hero "Hero" é estável entre mãos → `/analyze` (por-mão) agrupa certo. `positionNames` do front passou a usar 'LJ' (alinha builder + card + mesa). Validado: na mão 7-handed do usuário a nova derivação dá button→BTN, hero→BB, opener→HJ (bate com as decisões). Suíte backend 810/810, frontend typecheck + build + vitest 27/27. **Obs.:** mãos JÁ salvas têm os nomes stale no raw HH — a posição (tab) agora aparece certa, mas o NOME só fica limpo recriando a mão.

### feat(hand-builder): mãos não-sequenciais — escolhe a posição do hero; "Próxima mão" não roda o button

> Recriar **mãos avulsas** de vídeo (não o torneio inteiro): entre as mãos selecionadas o button andou de forma arbitrária e os stacks mudaram, então não dá pra assumir rotação +1 nem carryover. **"Próxima mão" agora só salva no arquivo e limpa a mão** — mantém button/stacks/hero como você deixou (removida a rotação automática do button e o carryover de stacks, que impunham valores errados). E há um controle **"Posição do hero nesta mão"** (UTG·HJ·CO·BTN·SB·BB): você clica a posição que o hero ocupa naquela mão e o builder ajusta o **button** pra isso — **respeitando a posição que você seleciona** — sem mover o hero de assento (a identidade dele fica estável entre as mãos do arquivo, então a análise agrupa tudo no mesmo hero). i18n 3 locales. **Validado e2e (browser real):** selecionar CO → hero vira CO; "Próxima mão" → hero CONTINUA CO (button não rodou); selecionar UTG → hero vira UTG. typecheck + build + vitest 27/27.

### feat(hand-builder): vencedor e pote auto-detectados (só escolhe no showdown)

> Você não precisa mais escolher vencedor nem digitar o pote a cada mão. O **pote** é 100% calculado das ações (antes + blinds + apostas, via `totalPot`) e mostrado como "X bb (calculado)". O **vencedor** é **auto-detectado** quando a mão termina por desistência (sobra 1 jogador ativo → ele venceu, "(detectado)"). Manual **só no showdown** (2+ jogadores chegam ao fim), porque aí depende das cartas dos vilões que você não digita — e mesmo assim é opcional (só afeta o "ganhei mas joguei errado", não a análise das suas decisões). Um `useEffect` preenche `showWinner`/`winAmount` ao fechar a mão sem sobrescrever escolha manual nem o auto-finish do hero-fold; a seção "Resultado" agora mostra os valores detectados/calculados e só exibe o `<select>` (limitado aos jogadores do showdown) quando `isShowdown`. Removido o input manual de pote. **Validado e2e (browser real):** mão ganha por fold → "VENCEDOR: BTN (detectado) · POTE: 11,5bb (calculado)", sem `<select>`. i18n 3 locales; typecheck + build + vitest 27/27.

### feat(hand-builder): "Finalizar mão" quando o hero folda (último agressor leva o pote)

> Depois que o hero folda, o resto da mão **não afeta a análise** (só decisões do hero contam) — então não faz sentido obrigar a completar villains/board/vencedor. Quando o hero registra um fold e a mão não acabou, aparece um aviso "o hero foldou…" + botão **"Finalizar mão"**: os villains ativos restantes foldam e o **último agressor ainda ativo leva o pote** (o mais realista — quem fez a última aposta/raise vence quando todos desistem); fallback pra vencedor aleatório só em pote sem agressão (limpado/checado). A mão fecha na street atual (sem precisar de board/showdown), pronta pro "Próxima mão". Pure/testável em `lib/hhAutoFinish.ts` (`autoFinishAfterFold` — último agressor, `rand` injetável no fallback; `totalPot`) + `hhAutoFinish.test.ts` (6: agressor vence ignorando rand, 3-bettor vence, fallback aleatório, HH parseável). **Validado:** round-trip backend de uma mão auto-finalizada → exatamente **1 decisão do hero** (BTN fold vs UTG = `gto_correct`), os folds dos villains **não** geram decisões espúrias; e2e (browser real) confirma o botão só aparecer após o hero foldar e a mão resolver com vencedor ("collected" no HH, "BTN: folds" preservado). i18n 3 locales; typecheck + build + vitest 27/27.

### feat(hand-builder): remover/adicionar posição (mesas 7/5-handed etc.)

> Mesas reais nem sempre têm o anel cheio (gente busta → 7, 5 jogadores). Cada chip de posição ganhou um **×** pra remover aquele jogador da mesa, e há um **"Adicionar posição"** + contador **"N jogadores"** abaixo da grade. Como as posições derivam do nº de jogadores (`positionNames(N)`, espelhando o backend `_position_names`), remover um seat re-deriva tudo certo pra qualquer N (2–9). Guardas: mínimo heads-up (2); se remover o hero ou o button, reatribui; remover/adicionar reseta a mão atual (as ações referenciam jogadores) com confirm. Jogador adicionado entra no próximo assento livre com nome único (`P{seat}`); o **log de ações agora mostra a posição** (via `positionOf`) em vez do nome cru, então fica legível com qualquer naming. **Validado:** round-trip backend de uma mesa **7-handed com gap de assento** → `hero=BTN, vs=UTG`, `_position_names(7)` correto e idêntico ao `positionNames(7)` do front; e2e (browser real) 8→6→5-handed (posições válidas) + adicionar de volta. typecheck + build + vitest 21/21.

### feat(hand-builder): carregar .txt pra continuar + undo geral (retomar a construção aos poucos)

> Pra montar um torneio **aos poucos**, em sessões. **(1) Carregar .txt:** botão "Carregar .txt" no topo lê um hand history PokerStars de volta pro builder em modo **continuação** — as mãos do arquivo viram as concluídas e a mesa/blinds/jogadores/button são lidos da **última mão**, prontos pra próxima (button rotaciona, hand_id +1). Novo `lib/hhImport.ts` (reverso parcial do `hhGenerator`: parseia cabeçalho/seats da última mão; mãos ficam raw, sem perda) + `hhImport.test.ts` (4 testes, round-trip com o gerador). **(2) Auto-restore** (já existia, confirmado): o estado inteiro — incluindo as mãos concluídas — persiste em `localStorage.handBuilderDraft` e é restaurado ao reabrir, então um torneio em construção não se perde. **(3) Undo geral:** botão "Desfazer" (no topo, sempre visível, + no card de ações) com histórico de até 60 snapshots — desfaz a última **ação, carta, "Próxima mão", troca de mesa ou carregamento** (não só a última ação como antes). Snapshots só em passos discretos (não por tecla nos stacks). **Validado e2e (Playwright, browser real):** undo remove ações passo a passo; carregar um .txt de 2 mãos (#010/#011, torneio 888888) restaura "2 no arquivo" e a mão seguinte vira #012. i18n 3 locales; typecheck + build + vitest 21/21.

### feat(hand-builder): construir torneio inteiro mão a mão (Próxima mão + overwrite)

> Pra montar um **torneio inteiro** num arquivo (caso: recriar de vídeo, mão após mão). A base multi-mão já existia (`nextHand` acumula em `completedHands`, rotaciona o button, incrementa o hand_id; `.txt`/analisar usam o arquivo todo) mas tinha 3 atritos, agora resolvidos: **(1)** o "Próxima mão" só aparecia depois de marcar vencedor+pote — agora há um botão **"Próxima mão →" sempre visível no painel** (habilita assim que a mão tem ações) e o vencedor virou **opcional** (sem vencedor, mantém os stacks pra você ajustar por mão; com vencedor, faz o carryover real). **(2)** contador claro **"Mão N · X no arquivo"** + dica do fluxo. **(3) re-analisar dava 409** "torneio já importado" (o builder sempre usa o id 999999): como o builder é **dono** do seu tournament_id, "Analisar torneio" agora **sobrescreve** (apaga o torneio anterior com esse id e reimporta) — re-análise idempotente. Posições rotacionam sozinhas a cada mão (seat fixo, button anda → seu hero passa de BTN a CO etc.); o **nome do hero fica estável** entre as mãos (necessário pra detecção consistente do hero; a posição é derivada por mão). i18n 3 locales. **Validado e2e (Playwright, browser real):** montei 2 mãos (BTN 3bet → Próxima mão → CO open) → "Analisar torneio" → 1 torneio com **as 2 decisões do hero** persistidas (BTN raise + CO raise, ambas `gto_correct`). typecheck + build ok.

### fix(hand-builder): "Analisar agora" agora realmente analisa (handoff estava morto)

> Achado no **teste e2e** (Playwright dirigindo o browser real, recriando uma mão). O botão "Analisar agora" gravava o HH em `localStorage.pendingImport` e redirecionava pra `/?import=builder` — mas **nada no app consumia esse flag** (o param se perdia no redirect `/`→`/dashboard`), então a mão recriada nunca era analisada. Agora o botão chama `tournaments.analyze(hh)` direto, com estado de **loading** ("Analisando…") + mensagem de erro amigável, e ao concluir navega pra `/tournaments/:id` (o torneio recém-analisado). Removido o `pendingImport`/`window.location` morto. Adicionado `data-card` nos botões do card picker (hook de teste). **Validado e2e ponta a ponta:** recriei UTG abre 2.5bb → BTN (hero) 3beta 3x → folds → "Analisar agora" → caiu em `/tournaments/999999` com a decisão do hero persistida (`gto_label=gto_correct`). i18n 3 locales (`analyzing`/`analyzeError`); typecheck + build ok.

### feat(hand-builder): atalhos de sizing contextuais no registro de ações

> Botões de sizing que preenchem o campo de aposta (em bb) conforme o contexto, pra recriar mãos sem fazer conta. **Open preflop** (só o BB na frente): `2bb · 2.5bb · 3bb`. **3bet/raise** (enfrentando uma aposta): `min` (raise mínimo) · `3x` (3× a aposta enfrentada) · `pot` (raise do tamanho do pote = `invested + pote + 2·toCall`). **Bet postflop** (sem aposta na frente): `⅓ · ½ · ⅔ · pot` (fração do pote). O `CurrentActorCard` agora recebe o **pote no momento da ação** (novo `potBefore`: antes + blinds + maior comprometido por jogador por street) e mostra "Pote: X bb" ao lado de Stack/Pra-pagar. Cada atalho preenche o campo (depois clica Bet/Raise) — tooltips i18n explicam cada um. Validado: open 2.5bb; 3bet vs 2.5bb → min 4 / 3x 7.5 / pot 8 bb; bet pot 5.5bb → ⅓ 1.8 / ½ 2.8 / pot 5.5; raise vs 3.7bb → min 7.4 / pot 16.6. typecheck + build + vitest 17/17.

### feat(hand-builder): redesenho "super simples" — position-first + bb-native (recriar mãos de vídeo)

> Reescrita do Hand Builder pra recriar spots de vídeo em poucos cliques. **Antes:** abria com cerimônia de metadados (Hand ID, Tournament ID, buy-in, level romano), stacks em **fichas** (você convertia bb na cabeça), e exigia adicionar+nomear cada jogador e escolher o seat do botão num diagrama — ~10 campos + 6 adds antes da 1ª ação. **Agora (modo simples por padrão):** escolhe **6/8/9-max** → posições já criadas (UTG…BTN, SB, BB), **stack uniforme em bb** (preset 40/75/100bb, editável por posição), **hero = clicar na ⭐** de uma posição. Tudo em **bb** (interno 1bb=100 fichas pra gerar HH limpo). Metadados de torneio + blinds custom + renomear jogadores foram pro bloco **"Avançado ▸"** recolhido. As posições exibidas agora espelham o **backend `_position_names`** (UTG/UTG+1/UTG+2/MP1/HJ/CO/BTN) — antes o front mostrava "LJ", divergindo do que a análise atribuía. Motor de ações (`CurrentActorCard` — de quem é a vez, stack, quanto pagar, presets call/2.5x/min-raise) e o `hhGenerator` (saída PokerStars) preservados. **i18n completo** (novo namespace `handbuilder`, 3 locales) — a página era 100% PT hardcoded. **Validado round-trip:** HH gerado pelo novo modelo (6-max, 100bb, hero=BTN) → parser+pipeline do backend derivam `pos=BTN vs=UTG`, `vs_rfi`, `gto_correct`. typecheck + build + vitest 17/17 ok.

### fix(preflop): #23 — open off-tree não marca fold de defesa marginal como crítico

> Mata uma classe de **falso-crítico**. As ranges de defesa (vs_rfi) usam o sizing canônico do GTO (open ~2-2.5bb); quando o vilão abre **maior** (off-tree, ex.: 3bb), o GW não tem o nó e o engine aplicava a defesa larga do open mínimo — marcando o fold de mãos marginais (ex.: 75o BB vs CO 3.3bb) como `gto_critical`. Vs um open maior a defesa correta é mais tight, então esse fold é **defensável**. **Detecção robusta:** computo o tamanho REAL do open em bb (`hand_state_builder._facing_to_total_at` lê o "raise **to** Y" do raw — PS loga incremento `raises 546 to 626`, GG loga total — e divide por bb; campo aditivo `facing_to_bb`, sem mexer no `facing_size` existente → zero risco a pot-odds/guards/storage), threado por `pipeline`→`decision_engine`→`analyze_preflop` e pelo path do card (`/replay` `_pf_result`). Comparo com o open canônico (`_canonical_open_bb` lê o R-code modal da RFI do opener, ex.: `R2.1`→2.1bb); se `facing_to_bb ≥ 1.4× canônico` → off-tree. **Rebaixa só a defesa MARGINAL** (call-dominada, via `hand_freq`: agg ≤ call) de `leak/major_leak`→`acceptable` (gto_mixed); **mão de value que o GTO 3beta (AA/KK/QQ/99) segue crítica** — foldar value nunca é defensável. Flag estruturada `open_size_mismatch` flui pro card → ressalva i18n (`card.openOversizeCaveat`, 3 locales) no "why" + /docs p2 (conceito). Sem cobertura/`facing_to_bb=0` → comportamento inalterado (fallback seguro). Validado em `torneio_ingles.txt` (400 mãos): 33 opens off-tree, **8 folds marginais rebaixados** (75o/K4s/A2o/66/Q7o/T4o + SB-jams 32/22bb), **5 folds de value mantidos críticos**. Testes `test_preflop_open_size.py` (7). Suíte **810/810**, vitest 17/17, typecheck ok — `test_tournament`/`test_multi_decision`/`test_invariants` verdes apesar do shift de label.

### feat(equity): #27 — equity preflop range-aware (vs a RFI range real do opener, não vs random)

> Fecha a lacuna da equity preflop: até agora o card estimava equity **vs uma mão aleatória** (`PREFLOP_EQ_VS_RANDOM`) — superestima quando o hero defende contra um open, pois a RFI range do opener é mais forte que a média. Agora, no cenário **vs_rfi** (open simples conhecido), a equity é calculada **vs a range de abertura GTO real daquela posição**. **Asset:** `scripts/gen_preflop_equity.py` gera a matriz mão-a-mão **169×169** (`leaklab/data/preflop_equity_169.json`) via **eval7** Monte Carlo (all-in até o river, com card removal por rejeição; simetria `eq[v][h]=1−eq[h][v]` pra metade do trabalho). **`leaklab/equity.py`**: `equity_vs_range(hero, {mão:peso})` = média ponderada por combos (par=6/suited=4/offsuit=12) × freq GTO. **`preflop_gto_ranges.villain_open_range(pos, stack, n, is_pko)`**: monta a `{mão:peso}` do opener a partir do `raise_hands`/`allin_hands` + `hand_freqs` reais do GW (PKO usa a range do estágio). **Wiring:** `pipeline.build_decision_input` injeta `villain_range` no metadata quando `preflop_raises_faced==1` e o opener é conhecido; `street_math_engine._estimate_hand_equity` usa `equity_vs_range` (fallback no vs-random sem cobertura). Sem acoplamento circular (equity.py só lê o JSON). **Display:** novo `equity_source` (`vs_range`|`vs_random`) flui pelo `/replay` (re-analisado ao vivo, sem migration) → badge **«vs range»** e tooltip honesto no card (i18n 3 locales), /docs `p5` atualizado (conceito). Escopo: só **vs_rfi** (open simples — o caso dominante e de maior EV); 3bet/4bet seguem vs-random (ranges estreitas, erro do proxy é menor) — documentado como refinamento futuro. Testes `test_equity_range_aware.py` (8: matriz sintética determinística + invariantes do asset real + villain range tight/wide). Validação: AKo vs UTG-range < AKo vs-random.

### feat(subscription): #26 — gating do solve GTO on-demand por cota de tier (receita)

> Monetiza o solve sob demanda (o pipeline já existia; faltava o gating). **Cota `solves` por plano** no `PLAN_LIMITS` (free: **10/mês**; pro/coach: ilimitado), espelhando a cota de torneios/ai_calls existente: coluna `users.solves_this_month` (migration PG+SQLite), reset mensal no `_maybe_reset_quota`, `increment_solves` + **`can_request_solve(user_id) → (permitido, restantes)`**, e `get_quota_status` agora expõe `solves_used` (o `/subscription/status` já serve o front). **Endpoint** `POST /player/hands/<id>/request-gto`: checa a cota ANTES de enfileirar — se estourou, **402 `solve_quota_exceeded`** com plano/usado/limite pro upsell; consome a cota só quando um solve NOVO entra na fila (idempotente — re-pedir um existente não cobra); devolve `solves_remaining`. **Frontend** (`Replayer.tsx`): novo estado `quota_exceeded` (detecta o 402), bloco de **upsell** (cadeado âmbar "limite atingido — faça upgrade", não erro), i18n 3 locales. Testes `test_solve_quota.py` (4: free bloqueia, pro ilimitado, reset mensal, status). Esforço baixo (gating sobre pipeline pronto), retorno de receita.

### fix(study-plan): IA indisponível não estoura erro pro usuário + corrige `last_n` no /study/plan

> Dois fixes na geração do plano: **(1)** `name 'last_n' is not defined` — ao ligar o `get_ev_leaks` no `/study/plan` eu copiei `last_n=last_n` de um template, mas esse endpoint só tem `days` → 500 ao gerar. Removido (usa só `days`; os outros 2 callers já estavam certos). **(2) Erro da API Anthropic vazava pro usuário** (ex.: sem saldo → "400 Client Error ... anthropic.com" na tela). Agora: o backend (`generate_study_plan`) loga o erro real e devolve um **código estável `ai_unavailable`** (nunca o `str(e)` cru); o front (`StudyPlan.tsx`) mostra mensagem amigável **"O gerador de IA está temporariamente indisponível — seus dados estão salvos, tente novamente"** e troca o hint enganoso "importe um torneio" por um retry honesto. i18n 3 locales (`study.aiUnavailable`/`retryHint`). Princípio: falha de IA é transitória e não deve assustar o usuário nem sugerir que ele perdeu dados.

### feat(ev-loss): plano de estudos + AI Coach priorizam por EV perdido (fecha o ciclo do #24/#25)

> O EV-loss agora **alimenta os geradores de IA** — não fica só no card. `generate_study_plan` e `coach_chat_reply` ganharam `ev_leaks` (do `get_ev_leaks`): o prompt recebe a seção **"Vazamentos por EV PERDIDO (bb deixados na mesa)"** com instrução explícita pra **ordenar o plano pela prioridade de EV** (o leak que mais sangra bb vale mais que um frequente porém barato) e citar o custo em bb no diagnóstico. Ligado em `/study/plan`, plano do coach pro aluno (`/coach/student/<id>/study-plan`) e no AI Coach chat (`/coach/chat`). Cache key do plano v5→**v6** (regenera os planos antigos sem EV; entra `ev_leaks` na chave). Testes: `test_study_plan_uses_ev_leaks` + cache key v6; suíte llm 44/44. Assim o plano deixa de priorizar por contagem de erros e passa a priorizar por **bb perdidos** — o sinal que o #24 trouxe.

### feat(leak-finder): #25 — Leak Finder consolidado (carro-chefe "LeakLab"), priorizado por EV

> O relatório-bandeira: consolida os vazamentos **priorizados pelo EV perdido (bb deixados na mesa)**, não por contagem de erros — reusando o `get_ev_leaks` do #24. Backend `repositories.get_consolidated_leak_report` (severidade high/medium/low por bb, total na mesa, top leak em destaque) + endpoint `GET /player/leak-finder`. Frontend `LeakFinderCard` (flagship no dashboard, seção GTO): headline com o total de bb vazados, lista priorizada dos top spots (posição · street · ação ideal · ×n + badge "−X bb" colorido por severidade), e coaching "ataque de cima pra baixo". `api.ts` (`LeakFinderData`/`leakFinder`), i18n 3 locales (`leakFinder.*`), /docs (indicador EV-loss agora aponta pro painel). Valida no user 13: leak nº1 = **BB preflop call (defesa) = 10,44 bb** em 21 decisões (de 35,92 bb em 76 leaks). Testes `test_ev_leaks.py` (3, +severidade/top_leak). Suíte 789/789, vitest 17/17, typecheck ok. Diferenciação vs concorrentes: priorização por **EV real**, não "leak finder — em breve". Próximo natural: drill-down por leak (link pro Ghost Table do spot).

### feat(ev-loss): #24 COMPLETO (Fases 1-5) — EV-loss por decisão, persistido, exibido e agregado

> Maior ROI do backlog. **Fase 0 (spike) = GO:** o GW traz EV **por mão e por ação** em `action_solutions[ação].evs` (fold=0 baseline; raise/call em bb). A ordem do array (não-trivial) é a das **chaves do `simple_hand_counters` do hero** (verificado 169/169 por vetor de freq). **Fase 1 (captura, sem túnel):** `parse_gw_har.extract_hand_evs` extrai `{mão:{code:ev}}`; `scripts/build_gto_evs.py` re-parseia os HARs do repo e gera o overlay `docs/leaklab_gto_evs.json` (**1913 spots, EM SEPARADO** das ranges p/ não inflar/arriscar o 9,3MB de freqs). Cobertura: **95% dos spots preflop de produção têm EV** (RFI 72/72, vs_RFI 324/324, vs_3bet 295/324). **Fase 2 (engine):** `analyze_preflop` ganha `_load_evs`/`_ev_loss_bb` e devolve **`ev_loss_bb`** = `max_ação(ev) − ev(ação do hero)` (clamp ≥0; NULL honesto sem cobertura; PKO pula — overlay próprio é futuro). Validado: foldar AA UTG @100 = **−13,87 bb**; raisear 72o = −0,70 bb; jogadas corretas = 0,0 bb — correlaciona com `action_quality` (gto_correct⟹~0). Teste `tests/test_ev_loss.py` (6) na suíte gto. **Fase 3 (persistência):** colunas `decisions.ev_loss_bb`/`ev_loss_source` (migration SQLite+PG), `save_decisions` grava (via `gto` no `decision_engine_v11`, que agora threada o ev_loss), `scripts/backfill_ev_loss.py` (dry-run/`--apply`). Backfill local: **724 decisões** com EV — e o invariante BATE no dado real: gto_critical avg **0,36 bb**, gto_mixed 0,03, gto_correct **0,0**. **Fase 4 (display):** `/replay` expõe `ev_loss_bb` no card; badge **"−X bb"** no `DecisionCard` (cor por magnitude: âmbar/laranja/vermelho), i18n 3 locales (`card.evLossTip`), indicador "EV-loss (bb)" no /docs (conceito). Refactor: `analyze_preflop` virou wrapper fino (`_analyze_preflop_impl` + `_attach_ev_loss`) p/ anexar o EV em TODO caminho de saída (inclui push/fold que retorna cedo). **Fase 5 (agregação — início do #25):** `repositories.get_ev_leaks` soma `ev_loss_bb` por spot (posição × street × ação ideal) e ranqueia pelo **total de bb deixados na mesa** (não por contagem de erros); endpoint `GET /player/ev-leaks`. Valida no user 13: leak #1 = **BB preflop call (defesa) = 10,44 bb** em 21 decisões, depois BTN fold 4,08 bb — 35,92 bb em 76 leaks. Testes `test_ev_loss.py` (6) + `test_ev_leaks.py` (2). Suíte 787/787, vitest 17/17, typecheck ok. **#24 fechado**; abre o caminho do #25 (Leak Finder consolidado: a UI flagship reusa o `get_ev_leaks`). Limitação: ev_loss só preflop (postflop/`gto_nodes` é extensão futura); PKO terá overlay de EV próprio.

### chore(gto-pko): exploração multi-depth + 1000p — limites do GW mapeados (mantém single-depth 200p)

> Investiguei expandir a cobertura PKO em **profundidade** (vários depths/estágio) e **field 1000p**. Achados (registrados p/ não re-investigar): **(1) Multi-depth marginal:** o GW oferece vários depths por estágio (probe 200p: PCT50=40/50/60, T3=20-50), mas a cobertura **colapsa nos short-stacks** (T3@20-35 só tem UTG RFI; re-raises a ≤40bb viram jam/RAI). E — decisivo — a hand history **só expõe os jogadores da mesa, não o field-remaining**, então o depth sozinho não determina o estágio (PCT50@60 vs PCT70@60 são ambíguos) e multi-depth não melhora a seleção. Mantido o modelo robusto **single-depth/estágio (1064 spots)**. `scripts/fetch_pko_depth_slice.py` (novo, captura fatias (estágio,depth) explícitas) validou PCT50@60 completo (133/133); dados ficam no pilot local, não promovidos. **(2) 1000p sem solução uniforme:** token confirmado (`ICMPKO8m1000`), patch de não-snapar depth para PKO (`server.py`, deployado), mas **nenhum depth uniforme resolve** (START 100-206, PCT50 40-70 — todos no-solution) e os HARs de 1000p são todos heterogêneos (replays). 1000p PKO parece **config-specific** OU exigiria um HAR uniforme (não replay) p/ ler os params. Produção segue 200p (1064 spots, 6 cenários, suíte 781/781 inalterada).

### feat(gto-pko): re-raises (vs_3bet/vs_4bet/faces_squeeze) — árvore preflop PKO 200p COMPLETA (1064 spots)

> Fecha a árvore preflop PKO no field 200p. `scripts/fetch_pko_reraise.py` captura os cenários de re-raise extraindo os sizings de cada nível das capturas anteriores (open←RFI, 3bet←vs_RFI, **4bet←vs_3bet** [por isso vs_3bet roda antes], squeeze←squeeze): **vs_3bet 224/224** (opener enfrenta 3bet), **vs_4bet 224/224** (3bettor enfrenta 4bet), **faces_squeeze 168/168** (cold-caller enfrenta squeeze; opener fixo UTG representativo). 100% sucesso, sem cascata. **Produção `leaklab_pko_ranges.json` = 1064 spots** (RFI 56 + vs_RFI 224 + squeeze 168 + vs_3bet 224 + vs_4bet 224 + faces_squeeze 168) — **toda a árvore preflop coberta em 200p**. **Engine:** o hook PKO do bloco unificado agora cobre os 4 cenários via `_section` (mesma chave `[hero][villain]` no Classic e PKO); RFI/vs_RFI via swap de `bk_data`. Fetchers parametrizados por `--field` (prontos p/ 1000p). `test_pko_engine.py`=15. Limitação: field fixo 200p no engine (1000p em captura); T2/FT config-specific; estágios do platô 50bb usam PCT50.

### feat(gto-pko): vs_RFI + squeeze capturados e integrados (8 estágios) — PKO 448 spots

> Estende a cobertura PKO de RFI para **vs_RFI** (defesa vs open) e **squeeze**. **Captura live** via `scripts/fetch_pko_vsrfi_squeeze.py`: usa o open-size correto por (estágio, posição) extraído da camada RFI (varia — START: BTN=R2.5/SB=R3.5/CO=R2.2), monta as linhas 8-max e consulta o proxy com checkpoint por estágio. **224/224 vs_RFI** (28 pares × 8 estágios) + **168/168 squeeze** (21 × 8, 1 caller representativo) — 100% de sucesso, sem cascata. *(Aprendizado: a falha inicial em linhas com raise NÃO era bug do proxy — era a cascata de página presa; com sessão fresca o page-driving resolve raise lines normalmente.)* **Produção** `leaklab_pko_ranges.json` agora **448 spots** (56 RFI + 224 vs_RFI + 168 squeeze); `build_pko_ranges_json.py` enriquece recursivamente o aninhamento (`vs_RFI[opener][defender]`, `squeeze[hero][opener]`). **Engine:** o overlay agora cobre RFI + vs_RFI (via swap de `bk_data`) + squeeze (hook próprio, já que o bloco squeeze lê de `data[ranges][bk_try]`, não `bk_data`); mesmo floor 45bb + fallback Classic. Squeeze PKO inclusive **acrescenta cobertura onde o Classic era NULL** (ex.: squeeze BTN/UTG @100bb). Testes `test_pko_engine.py` agora 12 (vs_RFI/squeeze aplicados, squeeze adiciona cobertura, cenários não-capturados [vs_3bet/vs_4bet] seguem Classic). Não-cobertos em PKO: vs_3bet/faces_squeeze/vs_4bet, field 1000p, T2/FT config-specific.

### feat(gto-pko): integração no engine — RFI usa ranges PKO em torneios bounty

> Fecha o loop: em torneio PKO, o `analyze_preflop` agora usa os **ranges PKO do GW** (capturados por estágio) no RFI, em vez do chipEV Classic. **Novo arquivo de produção** `docs/leaklab_pko_ranges.json` (committável, sem segredo) gerado por `scripts/build_pko_ranges_json.py` a partir da captura local — deriva as listas `raise_hands/allin_hands/call_hands/fold_hands` do `hand_freqs` (schema Classic-v3, pro grading RFI rodar igual). **Engine:** `_load_pko()` + `_pko_ranges_for(stack_bb)` seleciona o estágio pelo **depth** (stage↔depth acoplado: START=100/PCT90=90/PCT70=70/platô 50bb→PCT50); **floor em 45bb** (abaixo não há PKO → Classic push/fold); overlay no RFI troca só a FONTE de range (resto do grading idêntico), com `base['pko']`/`pko_stage`/`source='pko_gto'`. `is_pko` threadado do `decision_engine_v11` (via `context.isPko`, já detectado pelo parser por bounty/3-tier/keyword). **Fallback Classic** quando: não-PKO, stack <45bb, cenário ≠ RFI (vs_RFI/squeeze seguem Classic por ora), ou estágio config-specific (T2/FT). Efeito comprovado: UTG 99 @100bb abre **18,2% (PKO) vs 14,7% (Classic)** — bounty alarga o range. Teste `tests/test_pko_engine.py` (8 casos: seleção por depth+floor, overlay RFI, fallback fora-de-RFI/raso/não-PKO, PKO≠Classic) na suíte `gto`. Limitação documentada: distinguir os estágios do platô 50bb (PCT50/37/25/bubble/T3) exige field-remaining que a HH não traz → usa PCT50 representativo; field fixo 200p.

### fix(gto-pko): tokens reais dos estágios tardios + camada RFI 200p fecha em 8/10

> Os HARs dos estágios que faltavam revelaram que 3 dos meus tokens-palpite estavam errados: **37,5% left = `PCT37`** (não PCT375), **3 tables = `T3`** (não 3TABLES), **2 tables = `T2`** (não 2TABLES). Corrigido `humanize_stage` p/ reconhecer `T(\d+)` e os candidatos do `fetch_pko_rfi_layer.py` (+flag `--only` p/ re-rodar subconjunto). Re-captura: **PCT37 e T3 fecharam @50bb (7/7)** → camada RFI 200p agora em **8/10 estágios = 56 spots** (START/PCT90/PCT70/PCT50/PCT37/PCT25/BUBBLEMID/T3). **T2 e FT são config-specific:** com token CONFIRMADO do HAR, não resolvem em NENHUM depth uniforme (T2 testado em 50/88/40/75/100/60/30/20; FT em 40/50/20/15/100) — são os 2 estágios mais tardios, com stacks muito heterogêneos (HARs confirmam stacks_uniform=False), então o GW só os resolve por configuração, não tem solução uniforme canônica. No runtime ficam como aproximação ICM (proxy do estágio uniforme mais próximo, ex. T3/BUBBLEMID @50bb). test_pko_har_parser 8/8 (e2e em 7 estágios/37 spots).

### feat(gto-pko): camada RFI PKO 200p capturada — mapa stage→depth descoberto (6/10 estágios)

> `scripts/fetch_pko_rfi_layer.py`: por estágio, faz probe UTG "primeiro depth que resolve vence" (depth é acoplado ao estágio) e captura as 7 posições RFI 8-max. **Mapa stage→depth descoberto:** START=100, PCT90=90, PCT70=70, PCT50=**50**, PCT25=50, BUBBLEMID=50 — a profundidade canônica cai com o field e estabiliza em 50bb do mid-game em diante. (Achado: PCT50 canônico é 50bb, não 72 — o 72 do HAR era hand-replay, não a solução canônica.) **42 spots RFI capturados** (6 estágios × 7), `hand_freqs` íntegro; sanity ICM ok (SB abre 9-11% cedo/bolha → 17-18% mid-late com bounty). **4 MISS p/ confirmar token no GW:** `PCT375` (depth 50 resolve nos vizinhos → token errado, não depth), `3TABLES`/`2TABLES` (token/depth), `FT` (token confirmado no HAR mas só resolve com stacks heterogêneos — config-specific, não capturável uniforme). Próximo: usuário confirma os 3 tokens % / tables navegando no GW; FT fica como aproximação por-config. JSON em `ranges_gto/ko/` (fora do git).

### feat(gto-pko): fetcher live de ranges PKO + piloto START/200p/RFI validado end-to-end

> Com o proxy GW (`leaklab-solver`) acessível via túnel SSH (`-L 8765`) e o Chrome logado, capturei PKO **ao vivo** — e **sem mudança de código no cliente**: o `query_spot_raw` já aceitava `gametype=` override e o servidor já o honra, então bastou passar `MTTGeneral_ICMPKO8m{field}PT{stage}`. Novo `scripts/fetch_pko_ranges.py` (fundação do bulk-fetch): enumera RFI 8-max (7 posições) × field × stage × depth, consulta o proxy e grava no namespace `pko_ranges[{field}p][stage]['ranges'][bucket][scenario][hero]` (mesma topologia do `parse_gw_har`; `hand_freqs` em action codes p/ o engine reusar o lookup Classic). **Piloto START/200p/RFI:** 7/7 spots @100bb capturados, escada de open correta (UTG 18% → BTN 57%, SB 10%), `hand_freqs` íntegro (169 mãos, R2.1/F/RAI). **Descoberta que molda o bulk-fetch:** depths 50/30/20bb no START deram no-solution — e está CERTO: `START` = início = todo mundo deep, o GW só resolve cada estágio no **stack característico** dele (START~100bb, BUBBLEMID~50bb, PCT50~72bb, FT~100bb heterogêneo). Logo **depth é acoplado ao estágio** — o bulk-fetch deve mapear stage→depth(s) válido(s), não varrer todos os depths (evita ~40s/probe de no-solution). HARs/parse/piloto fora do git (`ranges_gto/ko/`). Próximo: mapa stage→depth + expandir cenários (vs_RFI/squeeze) e estágios.

### feat(gto-pko): parse_gw_har.py ingere PKO (8-max + eixo de estágio) — spec validado nos 4 HARs reais

> O GTO Solver Premium passou a ter PKO. Capturei 4 HARs reais (START/PCT50/BUBBLEMID/FT, field 200, 8-max) e estendi o `scripts/parse_gw_har.py` para ingeri-los — **reaproveitamento quase total**: mesmo endpoint `/v4/solutions/spot-solution/`, mesma resposta (`action_solutions` + `simple_hand_counters` do hero com as 169 mãos), mesmo vocabulário (F/C/R*/RAI). O **PKO está 100% embutido no `gametype`** (`MTTGeneral_ICMPKO{table}m{field}PT{STAGE}`) — o solver resolve a pressão de bounty server-side; a estratégia já vem ajustada (não modelamos bounty EV). **3 lacunas fechadas:** (1) **mapeamento 8-max** (`EIGHTMAX_SEAT`/`seat_map(table_size)` — pula UTG+2: `UTG,UTG+1,LJ,HJ,CO,BTN,SB,BB`, confirmado por `next_position`; `classify_spot` agora parametrizado por table_size, **Classic 9-max intacto**); (2) **eixo de estágio** (`parse_gametype` + `humanize_stage`: START→100% left, PCTn→n% left, PCT375→37.5%, BUBBLEMID→near bubble, NTABLES→N tables, FT→final table — tolerante a tokens novos; saída namespaceada `pko_ranges[{field}p][stage]['ranges'][bucket][scenario]`, mesma topologia do Classic pro engine reusar o lookup); (3) `parse_spot` guarda `stacks`/`stage`/`gametype` (estágios PCT50/FT têm stacks heterogêneos → bucket por depth é **aproximação ICM**, registrada). **Validado e2e nos 25 spots:** posições 8-max resolvem certo (`F-R2.1`→vs_rfi LJ vs UTG+1; `R2-C`→squeeze LJ vs UTG; `F`→rfi UTG+1), estágios humanizados ok, `hand_freqs` populado. Teste `tests/test_pko_har_parser.py` (8 casos: gametype, stage incl. extrapolados, 8-max classify, Classic 9-max regressão, e2e nos HARs com SKIP gracioso) na suíte `gto`. **HARs/parse ficam fora do git** (`.gitignore` `backend/docs/ranges_gto/ko/` — captura bruta grande; HAR como classe pode carregar token, embora estes estejam limpos). Próximo passo (quando quiser): bulk-fetch nos gametypes PKO p/ cobertura real. GTO 205/205.

### fix(revalidation): chave de match desambiguada por vs_position → drift 0 REAL

> O re-audit pós-resync ainda acusava **4 drifts "stale→NULL"**. Investigando, **não eram dados errados** — eram **falsos positivos da chave de match**. O differ (e o resync) casavam stored↔fresh por `(hand_id, street, action_taken)`, mas existem mãos onde o herói **age igual em 2 spots preflop distintos** (ex.: `call` vs open e depois `call` vs shove no mesmo hand). A chave de 3 campos **colidia** as 2 linhas; o `LIMIT 1` casava sempre a 1ª (menor id) e a 2ª ficava órfã/ambígua → drift fantasma. Fix: adicionar **`vs_position`** (= `spot.villainPosition`, que bate 1:1 com a coluna, incl. `unknown`) como 4º componente da chave — no `orchestrator._fetch_stored_decisions`/`_drift_against_stored` **e** no `resync_stale_decisions.py`. Efeito: os 4 falsos `stale→NULL` **sumiram**, e a desambiguação **revelou 2 drifts REAIS** de `label`/`best_action` que o resync ambíguo nunca alcançava (escrevia o veredito do spot CO na linha SB, e a 2ª linha ficava stale). Resync desambiguado aplicado (2 linhas: `257048851115`/SB `small_mistake/fold`→`standard/call`; `258867272112`/BB `clear_mistake`→`small_mistake`). **Re-audit: drift = 0 (stale→NULL: 0, não casadas: 0)** — convergência real, sem ruído de chave. Ambíguas residuais 218→210. +`test_vs_position_disambiguates` e fixtures de `test_revalidation_drift` atualizadas (9/9). GTO 197/197, pattern_scan 9/9 — operação de dado + tooling, engine intacto.

### chore(data): audit de acurácia (revalidation) + resync das decisões stale

> Rodei o **audit de acurácia** via o subsistema de revalidação (`scripts/revalidate.py`, read-only, 1122 decisões). Veredito: **o engine está acurado** — 92,2% aligned (engine = oracle); os 10 major_mismatch são limitação do oracle (cai no pot-odds ingênuo onde o engine acerta o GTO), não bugs. O achado real: o **banco estava STALE** — 97 decisões computadas com o engine ANTIGO, divergindo do recompute atual (consequência dos fixes da sessão: vs_4bet, shove↔allin, idealAction, SB-complete, off-tree, limp push/fold, vs_rfi rec…). O **Replayer ao vivo já mostrava certo** (`/replay` re-analisa); o stale afetava só o que é lido do banco (dashboard/métricas/leak reports). Novo `scripts/resync_stale_decisions.py` (dry-run por padrão, `--apply`) recomputa e atualiza `label`/`best_action`/`gto_label`/`gto_action`, **fechando o gap `stale→NULL`** (zera o gto_label quando o fresh é sem cobertura — ex.: limp/off-tree/multiway postflop — em vez de preservar o stale, que o `reanalyze_all_labels` antigo não fazia). Aplicado no DB local (backup antes; gitignored): ~97 decisões resincronizadas, **dry-run pós-apply = 0** (convergência total). Engine/scanner/vitest seguem verdes — operação só de dado.

### test(card): trava as regras de DISPLAY do Replayer (vitest) — fecha a lacuna do frontend

> O scanner de invariantes guarda o **output do backend**, mas as regras de **display** que os fixes das varreduras criaram viviam inline no `Replayer.tsx` e podiam regredir em silêncio (o scanner Python não alcança TSX). Extraí as 4 regras-chave para um módulo PURO `lib/cardLogic.ts` e religuei o Replayer a elas (não duplica — usa): **(1)** `computeEffectiveGtoLabel` (shove↔allin: shove num nó allin-dominante = correct), **(2)** `isMultiwayPot`/`livePlayers` (3+ no pote = aproximação HU), **(3)** `isPpMuted` (+pp neutro quando o veredito vem do solver/range OU ficaria verde mas a ação foi erro), **(4)** `idealActionSource` (preflop coberto usa o RANGE antes do gto_action do engine — o fix do squeeze "GTO recomenda Raise" não Call). **16 testes vitest** (`cardLogic.test.ts`) cobrindo os casos de bug de cada uma. Adicionado o step **vitest ao CI** (`ci-cd.yml`) — antes só os testes Python rodavam. Validado: 17 vitest verdes, typecheck verde, cards multiway ao vivo idênticos (religação sem mudança de comportamento). Agora o card está guardado nas duas pontas: scanner (backend) + vitest (display).

### fix(preflop-gto): jam curto sobre limp ganha veredito (push/fold, limp = dead money) + raise≈allin até 12bb

> Um **QQ BTN @7,9bb shove sobre um limp** mostrava **"Sem veredito GTO · Spot N/A"** — frustrante, porque é um push/fold trivial. Aprofundando: o limper estava no **HJ** (open-limp), e o **GTO não open-limpa de posição não-blind** → não existe nó vs-limp no solver pra capturar (cobertura real é inviável aí). Mas a stacks curtos, **um jam/fold sobre limp É a mesma decisão de push/fold** — o limp é só dead money, não cria nó novo. Fix: no short-circuit de pote limpado, um jam/fold **≤12bb** roteia pro range de **RFI (push/fold)** com flag `limp_dead_money` + caveat transparente no card **"≈ push/fold · limp tratado como dead money"** (não é "outro spot" — é o mesmo nó). Potes limpados deep ou call/iso-raise seguem honestamente sem cobertura. **Bug pré-existente exposto e corrigido junto:** o QQ jam vinha **leak** mesmo sem limp — a equivalência **raise≈allin** (jammar uma mão que o GTO min-raisa = mesma decisão committed) só valia a `<6bb`; estendido pro **bucket 10bb inteiro (≤12bb)**, então QQ/premium jam @8bb = correct, lixo segue major_leak, e ≥14bb raise≠allin segue distinto. Validado: o spot do user agora ✓ CORRETO. Engine 270/270, scanner de invariantes 0 violações, regressão `test_short_jam_over_limp_uses_pushfold`. 3 locales.

### feat(tooling): scanner de invariantes — estende pro POSTFLOP (gto_nodes)

> Estende o scanner de invariantes do card pro postflop: `scan_postflop()` varre os **~820 `gto_nodes`** (strategy do solver) e checa 5 invariantes que codificam a classe de bugs postflop das varreduras — (1) `strategy_json` normalizado (sum freq ≈1, não all-zero), (2) `gto_action` armazenado == ação dominante da strategy (pega gto_action stale/mismatch), (3) jogar a ação dominante nunca dá DESVIO CRÍTICO, (4) **shove↔allin**: num nó allin-dominante, jogar shove = `gto_correct` (não falso crítico — verifica o fix sobre TODO o dado real, não só amostras), (5) parse válido (tolera o formato aninhado `{strategy:{...}, preflop_actions}` de alguns nodes). Resultado: **0 violações** nos 823 nodes — a classe postflop (já fechada pelos fixes shove↔allin/+pp/heurística) agora tem guarda de regressão sobre o dado inteiro. Vira `test_postflop_card_invariants_all_zero`. Scanner total: 175k combos preflop + 823 nodes postflop, **0 violações**.

### feat(tooling): scanner de invariantes do Decision Card — fecha a classe de bugs de uma vez

> As varreduras visuais (card a card) estavam achando o **mesmo tipo de bug** repetidamente, porque o card é uma **camada de síntese** de ~5 fontes (ranges GTO, engine heurístico, gto_label armazenado, recompute ao vivo, pot odds) e os bugs moram nas **juntas** onde elas divergem. Em vez de continuar amostrando um card por varredura, criei `scripts/scan_card_invariants.py`: roda **TODA a matriz preflop coberta** (~960 spots × 169 mãos = **175k** chamadas a `analyze_preflop`) e checa **5 invariantes** que codificam a classe de bugs já encontrada — (1) `hand_freq` normalizado (raiz off-tree), (2) `in_range` ⇔ continuação real (SB Call 100% «fora»), (3) toda ação recomendada com freq ≥10% (vs_rfi «Shove/Call»), (4) ação dominante recomendada = maior freq (idealAction), (5) fold não graduado mais severo que a freq justifica (off-tree). **Logo achou 1 bug latente** que eu não tinha varrido visualmente: o `recommended_actions` da branch **RFI** também não filtrava freq (igual ao vs_rfi já corrigido) — ex.: RFI 33 @75bb listava `Fold / Raise` com raise 0,12% (33 estava em `raise_hands`). Fix aplicado (filtro ≥10% na RFI). Agora a matriz inteira passa: **0 violações**. Vira teste de regressão (`tests/test_card_invariants.py`, suíte `gto`) + um guard do shove↔allin postflop. Converte "bug aparece toda varredura" em "lista finita → corrige em lote → invariante não regride". Engine 270/270.

### fix(preflop-gto): vs_rfi — "GTO recomenda" não lista mais ação de freq ~0%

> A reverificação do vs_rfi achou uma imprecisão na caixa **"GTO recomenda"**: **99 BTN vs open @11bb** (GTO jama **Allin 99,9%**, Call 0,1%) recomendava **"Shove / Call"** — o "Call" entrava só porque 99 estava na **string `call_hands`** do range, apesar da freq de call ser ~0. O rec do vs_rfi incluía **toda** ação cuja mão estivesse na string, sem filtro de frequência (a branch mesclada vs_3bet/etc. já filtrava `≥10%`). Fix: o rec do vs_rfi passa a filtrar **≥10%** (igual à mesclada). Confirmado que **todos os 964 spots têm hand_freqs reais** (0 string-only), então o peso é sempre a freq da mão — o filtro é seguro. Agora 99 = "GTO recomenda **Shove**"; mistas legítimas seguem com as 2 ações (KK call/raise, QTo jam/call, KJs jam/call). Engine 270/270. (vs_rfi reverificado: KJs jam=correct, KK 3bet=correct, 99 fold=major_leak — shove↔allin e demais fixes intactos.)

### docs: /docs Replayer ganha "equity vs aleatória" e "Multiway" (conceitos das varreduras)

> Após a leva de varreduras, atualizei a doc do **Replayer** (`/docs`) com os 2 conceitos novos que o usuário vê no card — em nível conceitual (o que é / como ler), sem expor lógica interna. **p5 — equity "vs aleatória":** o indicador de equity é estimado vs uma mão aleatória (não o range real do oponente, que costuma ser menor); o veredicto vem da estratégia GTO da mão, não desse número. **p6 — Multiway:** em potes 3+ way o card mostra «Multiway · N-way» — a estratégia do solver é resolvida heads-up, então em multiway é aproximação (a equity já vem ajustada pro nº de oponentes). 3 locales (PT/EN/ES), termos de poker em inglês. (p4 já cobria "vs Limp"/pote limpado.) typecheck verde, render confirmado.

### fix(card): heurística postflop — evidência de EV bate com o veredito (sem "+EV" verde no "ERRO")

> A varredura no postflop **sem cobertura** (path "Heurística") achou uma contradição visual: uma aposta/raise marcada **"✗ ERRO"** (engine recomenda Check/Call) exibia o badge **"RAISE +EV" verde** e a margem **"+pp" verde** — porque a conta simples compara a ação a **fold** ("+EV vs fold"), enquanto o veredito a compara à **melhor jogada**. O usuário via "+EV" e "ERRO" juntos. (Pote limpado e o postflop heurístico de call/fold já eram consistentes; o problema era ação agressiva flagada como erro.) Fix (`Replayer.tsx`): o badge de EV do widget math passa a seguir o **veredito** (`mathActionIsEv = isActionOk`) e o `+pp` é **neutralizado** quando ficaria verde (eq ≥ necessária) mas a ação foi erro (`eq ≥ req && !isActionOk`). Agora um bet/raise-erro mostra "−EV"/+pp cinza, coerente com o "ERRO"; call/fold corretos seguem "+EV" verde. Mesma filosofia do +pp mudo no solver (a evidência não valida em verde uma ação que o veredito reprova). Validado: pfu_bet (ERRO) → +9,1pp agora cinza. typecheck verde. (Pote limpado: varrido, limpo — "Sem veredito GTO · vs Limp" honesto, sem bug.)

### fix(preflop-gto): mão off-tree (peso 0) não é mais falso "LEAK GRAVE" por foldar

> A varredura num spot faces_squeeze achou que **TT HJ vs squeeze do SB @18bb fold** dava **✗ LEAK GRAVE** — mas o card mostrava **"Fold 100%"** e recomendava **Fold**: contraditório (foldou exatamente o que o GTO faz). Causa: a entrada da mão no dado GW era **`{F:0, C:0}` (peso 0)** — mão off-tree / 0 combos no nó (ex.: TT teria 3betado preflop, não cold-callado, então não está no range do cold-caller). O branch populava `hf` toda-zero → `_vs_3bet_quality` via **0% em tudo → major_leak** ao foldar, enquanto a normalização de saída (INV-10) sobrescrevia o display p/ `fold:1.0`. Display ≠ base do veredito. Fix (`preflop_gto_ranges.py`, branch vs_3bet/faces_squeeze/squeeze/vs_4bet): se `sum(hf) < 0.001` (mão peso-0), normaliza `hf → {fold:1.0}` **antes** do grading — igual à saída. Agora foldar uma mão off-tree = **CORRETO** (default seguro), e jammar/calar = major_leak (off-tree). In-range intacto: JJ/ATs call=correct, fold=major_leak; 55 fold-fora-do-range=correct. **0 spots inteiros corrompidos** (a falha era por-mão), então é robustez geral. Engine 270/270.

### fix(preflop-gto): SB-complete (limp) no push/fold — card não é mais contraditório (rec=fold vs Call 100%)

> A varredura num spot push/fold achou que o SB curto joga uma estratégia **limp-or-jam** (ex.: AKs SB @10bb = **complete 100%**, AA/QQ completam 72-93%, AKo jama 100%) — dado real do GW (código `C`). Mas o `analyze_preflop` v3 assumia **"v3 não tem limp"** e ignorava o `C`, produzindo um card **triplamente contraditório** ao jammar AKs do SB: **"GTO RECOMENDA FOLD"** (mas o dado é "Call 100%"), **"Mão AKs · fora do range"** (mas está no range de complete), e **"✗ LEAK GRAVE"** (severidade dura demais — jammar um premium que o GTO limpa é EV próxima, não erro grave). Fix (`preflop_gto_ranges.py`, branch RFI v3): o código `C` (complete) entra no `recommended_actions` e marca a mão como `in_range`; jam/raise de uma mão que o GTO **completa** rebaixa `major_leak→leak`. Agora AKs SB jam = **⚠ LEAK · "GTO recomenda Call" · no range** (consistente), e completar AKs = **CORRETO**. Contido: só dispara pra mãos com `C` (= SB; não-SB RFI não tem complete). Validado: AKo SB (jama de verdade) intacto = correct; BTN/UTG RFI e 72o major_leak intactos. Engine 270/270. (Refinamento pendente — label "Complete/Limp" em vez de "Call" no card: backlog #22.)

### feat(card): indicador "Multiway · N-way" no postflop (solver HU é aproximação em pote 3+ way)

> A varredura num spot **multiway coberto** revelou que ~44 decisões postflop genuinamente **3-4 way** recebem cobertura do solver — que é resolvido **heads-up** — apresentada como autoridade (badge SOLVER, "DESVIO CRÍTICO" por apostar num pote 3-way), **sem indicar que é multiway**. Inconsistência: a **equity já é ajustada** pelo nº de oponentes (`street_math_engine`: `eq_HU / (1+0.3·(n−1))`, ex.: 4-way 36,3% = ~58% HU), mas a **estratégia do solver não** — é o read HU puro. Fix (`Replayer.tsx`): chip âmbar **"Multiway · {{n}}-way"** no card postflop quando há 3+ jogadores no pote (calculado de `seats − folded` do próprio step, frontend-only), com tooltip contextual (`multiwaySolverTip` quando solver-coberto = "estratégia HU é aproximação; ranges/frequências mudam com mais oponentes; equity já ajustada"; `multiwayTip` no heurístico). Mantém os vereditos (o read HU é a melhor referência disponível) mas o usuário sabe pesar. 3 locales. Validado: pote 4-way mostra "Multiway · 4-way", 3-way mostra "Multiway · 3-way". typecheck verde. (Opção escolhida pelo usuário entre caveat / gate de cobertura / aceitar.)

### fix(card): shove postflop não é mais falso "DESVIO CRÍTICO" (normaliza shove↔allin no label efetivo)

> A varredura num spot de **turn coberto** achou um bug grave: um turn onde o hero deu **shove** e o solver joga **Allin 96%** aparecia como **"✗ DESVIO CRÍTICO"** com "VOCÊ JOGOU SHOVE / GTO RECOMENDA SHOVE" — contraditório (shoveou o que o GTO shova 96% e era "erro grave"). Causa: `computeEffectiveGtoLabel` (`gtoUtils.ts`), que recalcula o label ao vivo pela estratégia do solver, normalizava as ações mas **não unificava shove/jam ↔ allin**. A estratégia usa `'allin'`, a ação jogada vem como `'shove'` → não casavam → frequência tratada como 0% → `gto_critical` falso. (Preflop coberto não usa essa função — usa `pg.action_quality` —, por isso só o postflop era afetado.) Fix: `normAction` mapeia `shove`/`jam`/`allin` → `'allin'` (canônico). Agora o turn shove vira **✓ CORRETO** (Shove 96%, sem caixa "GTO recomenda"). Bug **estrutural**: afetava todo shove postflop sobre node allin-dominante (2 confirmados no dataset local; escala com o volume) e também o **RangePanel** (mesma função compartilhada). typecheck verde; vereditos críticos legítimos (shove quando solver dá check 100%) seguem corretos.

### fix(card): postflop com solver — margem de pot odds (+pp) fica NEUTRA, não verde contradizendo o veredito

> A varredura num spot **postflop coberto** achou uma contradição: num flop com **"DESVIO CRÍTICO"** (apostar é erro grave — solver dá **Check 100%**), o card mostrava **"MÍN. EV 19,8% +42,2pp" em VERDE** — que lê como "apostar era +42pp lucrativo", contradizendo o próprio veredito. Causa: o `+pp` (equity − equity necessária) já era **mudo** no preflop coberto (`ppMuted = showAuditPreflop`), justamente porque a conta simples de pot odds pode contradizer o solver (que considera range inteiro e ruas futuras) — mas no **postflop** com cobertura solver ele continuava verde/vermelho. Fix (`Replayer.tsx`): `ppMuted = showAuditPreflop || effectiveGtoLabel` — neutraliza o `+pp` (cinza) sempre que o veredito vem do solver (range preflop **ou** estratégia postflop), com tooltip contextual novo (`reqSolverContextTip`, 3 locales) explicando que o solver é a base. A cor (verde/vermelho) fica **só** onde o pot odds É o veredito: postflop **sem** cobertura (card "Heurística", widget "Equity necessária vs Equity · −EV") e vs_shove. Regressão verificada ao vivo: postflop solver-coberto = +pp cinza; postflop sem cobertura = +pp verde mantido (ERRO/heurística). Afeta os ~85 spots postflop de desvio (gto_critical/minor) onde a conta simples diverge do solver. typecheck verde.

### fix(card): "GTO recomenda" no preflop coberto usa a ação dominante do RANGE, não o gto_action do engine

> A varredura num spot de **squeeze coberto** (hero squeezando — raríssimo nos dados, então validado com mão sintética: BTN squeeza vs UTG+UTG+1 @14bb) achou um bug na caixa **"GTO RECOMENDA"**. Para **AA @14bb**, o GTO joga **Raise 93%** / Call 7% (jammar é leak grave — a 14bb AA faz raise pra manter range largo), e o veredito LEAK GRAVE estava certo — mas a recomendação dizia **"GTO RECOMENDA CALL"**, contradizendo a própria barra "Raise 93%" do card. Causa: o `/replay` devolve `gto_action='call'` (= `best_action` do **engine**, heurística separada) e `gto_strategy=None`; no frontend o `idealAction` priorizava o path `hasGto` (→ `gto_action`) sobre `pg.recommended_actions` (= `['raise']`, a ação dominante do range GTO, **correta**). O **verdict** já priorizava o range (via `effectiveGtoLabel=null` no preflop coberto), mas o `idealAction` não — daí a inconsistência veredito × recomendação. Fix (`Replayer.tsx`): no preflop coberto (`!isPostflop && pg.available`), o `idealAction` usa `pg.recommended_actions` **antes** do `gto_action` stored, alinhando com o verdict. Agora AA = "GTO RECOMENDA **RAISE**". Regressão verificada: QQ vs_3bet segue "GTO recomenda Shove" (Allin 100%), AKs squeeze = correto, KJo squeeze = "fold". Postflop e push/fold (que dependem de `gto_action`/`gto_strategy`) intactos. Ferramentas: `make_squeeze_synth.py` (gera/valida/injeta squeeze sintético) + `squeeze_card_shots.mjs`. typecheck verde.

### fix(card): call-vs-shove (heurística) vira decisão de POT ODDS, não chrome de RFI

> A varredura no cenário **vs_shove** (hero paga um all-in sem dado GTO específico → `vs_shove_fallback`) revelou que o card reusava todo o chrome do RFI: **"RANGE DE ABERTURA X%"**, **"RANGE AGREGADO · Fold Y%"** e o chip verde **"Mão Z · no range"** — a referência errada pra uma decisão de *call vs shove*. Dois sintomas: **(1)** contradição — KJo BTN call @7,4bb mostrava chip verde "no range" **e** veredito **LEAK** ao mesmo tempo; **(2)** veredito errado — o fallback classificava pela qualidade da ação **'raise'** no range de abertura (que a stack curto é penalizada vs jam), marcando **LEAK** mesmo quando pelo **pot odds** o call é **+EV** (KJo: equity 60,5% > 47,3% necessária). Pior: KK pagando corretamente (2ª melhor mão) exibia um "Fold 70,5%" gigante (o fold% do range de abertura, irrelevante). Fix (frontend, `Replayer.tsx`): `vs_shove_fallback` agora é tratado como **decisão de math** — veredito, frase e evidência derivam de **equity × equity necessária** (mesmo widget "Pot Odds vs Equity" do postflop), badge **"Heurística"**, e o chrome de range de abertura é suprimido. Caveat "vs aleatória" mantido (a equity é a tabela vs-random, aproximada). Resultado: KJo e KK = **CORRETO** ("CALL +EV"), sem contradição; um call de fato −EV vira leak honesto. Tudo gated por um flag `isShoveFb` (false em todos os cards GTO comuns → zero regressão; vs_3bet/RFI/squeeze verificados intactos). Cobre os 2 sites de `vs_shove_fallback` do backend (ambos display). Edge raro (~5 spots no dataset local). typecheck verde.

### fix(card): equity preflop agora é vs-random REAL (tabela exata), não bucket cru

> A varredura do Decision Card num spot **vs_3bet coberto** confirmou que o cenário funciona nos 3 estados (JJ call = correto via mix Allin 58%/Call 42%; QQ call @15bb = leak grave "GTO recomenda Shove"; AQo shove = correto). O único achado foi a **linha EQUITY**: o valor vinha de um **heurístico de 6 buckets** (`street_math_engine._estimate_hand_equity`) mas o card a rotulava **"· vs random"** com precisão decimal — e o número não era vs-random: **todo par alto dava 64,0%** (JJ=QQ=KK=AA), e **AQo dava 45%** (vs random real ~64%). O label prometia uma precisão que o cálculo não tinha. Fix: tabela `PREFLOP_EQ_VS_RANDOM` com a equity exata de cada uma das **169 mãos** vs uma mão aleatória (all-in até o river), gerada por Monte Carlo com eval7 (100k amostras/mão — `scripts/gen_preflop_vs_random_equity.py`, ferramenta offline reproduzível). Agora AA=85,1%, QQ=80,0%, JJ=77,5%, AKs=67,2%, AQo=64,4%, 72o=34,7% — diferenciadas e fiéis ao label. Canonização inline (`'AsKh'→'AKo'`) + fallback no heurístico antigo se a mão não casar. Não é range-aware (isso segue como #27/Fase 2); só torna o "vs random" verídico. Postflop intacto. Testes: 753/753 (atualizado o invariante multiway-não-ajusta-preflop pro novo valor de AA).

### fix(preflop-gto): push/fold ultra-curto — jam de mão que o GTO abre não é mais "leak"

> A varredura num spot de push/fold confirmou que **não existe section `push_fold`** no dado: o jam de stack curto é coberto pelo **RFI v3** (que traz `allin` nas `hand_freqs` a partir de ~10bb). O card coberto sai limpo (ex.: **AKo UTG @5,8bb → "Allin 100%", veredito CORRETO**), e potes limpados continuam corretamente fora de cobertura (Q5o @1,8bb vs Limp = "Sem veredito GTO"). Mas dois problemas reais a <6bb: **(1)** o range usado é o bucket 10bb e a essa profundidade o range de **jam é bem mais largo** que o de abertura 10bb — um shove marginal (ex.: **K7o UTG @3,8bb**) virava **erro grave**; o softening sub-6bb (antes excluía RFI) agora **inclui RFI** (major→leak, leak→acceptable, flag `depth_approx`/"≈"). **(2)** mais sério: o range 10bb separa **raise (open)** de **allin**, mas a essa profundidade **abrir = jammar** (você está comprometido) — então **AA UTG @4bb** (range: raise 100%) era marcado **"leak"** ao dar shove. Fix: no grading RFI, a <6bb o jam credita `allin + raise` somados, tratando raise≈allin no push/fold. Resultado: AA/KK/AKo curtos = **correto**, K7o = leak (marginal, suavizado), 72o = leak (lixo, ainda penaliza), e RFI ≥6bb intacto (72o @9bb segue major_leak). Impacto no dataset local: 4 de 5 jams sub-6bb cobertos passaram de penalizados → corretos. Testes: engine 270/270.

### fix(preflop-gto): cenário vs_4bet (hero 3betou, enfrenta 4-bet) — roteamento + lookup

> A varredura num spot de vs_4bet revelou o mesmo padrão do squeeze: o dado **vs_4bet existe e é rico** (`vs_4bet[hero][4bettor]`, 30–100bb, todas as combinações de posição), mas o `analyze_preflop` **nunca roteava** pra vs_4bet — uma decisão vs_4bet (hero 3betou e enfrenta um 4-bet) caía em **vs_3bet** (range errado, resposta a 3bet em vez de a 4bet). Fix: novo branch de roteamento (`hero_was_aggressor and facing_raises >= 2` = open + 4bet) **antes** do vs_3bet; `vs_4bet` adicionado à branch de lookup mesclada (section `vs_4bet`, mesma estrutura `[hero][villain]`); pro-note com verbo/termo corretos (hero faz **5bet/jam vs 4bet**, não "4bet vs 4bet"). Validado com mão sintética (CO 3bet AKs, UTG 4bet @50bb): card mostra "Cenário vs 4-Bet", "Range de continuação 69%", "Call 86,1% / Allin 13,1%", veredito ACEITÁVEL (jam é 13% — minoritária válida). Testes: preflop 76, invariants 8, regression 26, tournament 8, multi 14. (Grade vs_4bet no RangePanel = extensão do #28.)

### feat(replayer): grade 13×13 vs 3-bet / squeeze no RangePanel (aba real) — #28

> Complemento do fix anterior: agora a aba **3-BET** existe de verdade e mostra a **grade 13×13 da range de continuação** do spot (não só o RFI de referência). **Backend** (`/preflop-ranges`): o vs_3bet usava a chave obsoleta `{pos}_RFI_vs_3bet` (sempre null); reescrito para a estrutura atual `vs_3bet[hero][3bettor]` (keyed por 3bettor, igual ao vs_rfi) com `frequencies` por mão montadas de `hand_freqs`; adicionado `squeeze[hero][opener]`; ambos com fallback de bucket (mesma tabela do engine). **Frontend** (`RangePanel`): tipo `ActionGrid` compartilhado; `buildRangeFromApi('3bet')` escolhe a fonte por cenário (vs_3bet ou squeeze) e o vilão (`gto.vs_position`), colorindo por `frequencies`; aba '3bet' disponível quando há dado. Confirmado: AJo vs UTG+2 3bet @17bb mostra a range de 4bet/allin (AA/AK/KK/QQ/JJ vermelho) com o hero em fold — 3,3% · 44 combos. api 42/42, gto 38/38.

### fix(replayer): RangePanel não aponta mais pra "aba 3bet" inexistente

> Na tela de ranges de uma decisão vs_3bet (ou squeeze), o painel mostrava a mensagem *"…a decisão está na aba 3bet"* — mas a **aba 3bet nunca existe**: o `/preflop-ranges` retorna `vs_3bet=null` para todas as posições/stacks (a grade 13×13 vs 3-bet não é exposta como aba; a range real está em `hand_freqs`, não no endpoint). A mensagem apontava pra uma aba que não renderiza. Fix: a mensagem só diz *"está na aba X"* quando a aba **realmente existe**; senão explica que a range específica está **no card de análise** (frequências da sua mão), ainda não disponível como grade 13×13. (Expor a grade vs_3bet/squeeze como aba = backlog #28.)

### fix(preflop-gto): cenário SQUEEZE (hero squeezando) — roteamento + lookup corrigidos

> A varredura do Decision Card num spot de squeeze revelou que o cenário **squeeze** (hero faz o squeeze: raise sobre open-raise + cold-call) estava quebrado em **dois níveis**: (1) **roteamento** — `caller_position` (posição do cold caller) não era computado nem threadado, então o hero-squeeze caía em **vs_rfi** (range errado, veredito potencialmente errado); (2) **lookup obsoleto** — a branch do squeeze buscava section `vs_squeeze` + chave flat (`{pos}_squeeze_vs_...`), formato antigo que **nunca casava** com o dado atual (`squeeze[hero][opener]`, idêntico ao faces_squeeze). Fix: `hand_state_builder` detecta o cold caller → `pipeline.callerPosition` → call sites de `/replay` e enriched passam `caller_position`; e a branch do squeeze foi **mesclada** na do vs_3bet/faces_squeeze (section `squeeze`, mesma estrutura). Agora: spot squeeze coberto → estratégia da mão (ex.: AKs UTG+2 vs UTG @20bb = Raise 11% / All-in 89%); spot sem dado → no-coverage honesto (não mais um veredito vs_rfi falso). **Validação com mão sintética (BTN squeeza AKs vs LJ @14bb):** card mostra "Range de squeeze 10%", "Cenário Squeeze", "Allin 99,8%", e a aba **3-BET do RangePanel** mostra a grade de squeeze completa (190 combos). **Pro-note do squeeze** ajustada: o hero **squeeza** (não "faz 4bet vs squeeze" — ele é o squeezador, não responde a um). Testes: preflop 76, invariants 8, regression 26, pipeline 8, tournament 8, multi 14.

### fix(replayer): chip "Mão · no range/fora" (não confundir com veredito) + não over-harsh sub-6bb

> Achados menores da varredura do Decision Card: **(#2)** o chip "Mão {hand} ✓/✗" usava ✓/✗ que parecia veredito de *ação* — mas é sobre estar **no range**. Ex.: "AJo ✓ + LEAK GRAVE" (mão no range, mas call vs shove foi erro grave) confundia. Trocado por rótulo de texto **"· no range" / "· fora do range"** + tooltip explicando que é range, não correção. **(#4)** o bucket mais baixo ('10bb') cobre 0–12bb, então um stack de 3–5bb usava o range de 10bb (com flats) e podia marcar veredito **over-harsh** (call defensável a 3bb pelas odds virava leak/major). Agora, sub-6bb facing open (não-RFI), a severidade é **rebaixada 1 nível** (major_leak→leak, leak→acceptable) + flag `depth_approx` — mesma filosofia do #23 (não punir onde o dado não cobre com precisão; o "≈" já sinaliza o depth). **(#3)** verificado: o grading por frequência (≥30%=correct) trata ação minoritária ~36% de mão mista como GTO-correta — **intencional** (ambos os lados de uma mista são corretos), sem mudança. Testes: preflop 76, invariants 8, regression 26, tournament 8, multi 14.

### fix(data): limpa gto_label stale de potes limpados (downstream)

> Complemento do guard de frontend: as **46 decisões de pote limpado** que tinham `gto_label` **armazenado** (scoring antigo, pré-feature do limp) poluíam gto-alignment, ELO e leak reports — e eram a raiz do veredito stale no card. Novo `scripts/backfill_clear_limp_gto.py` (dry-run por padrão, `--apply`, idempotente, cross-backend) re-avalia cada decisão preflop com `facing_limp` e zera `gto_label`/`gto_action` onde `coverage_reason='limped_pot'`. Rodado local: 46 limpos, re-run = 0 (idempotente). Potes limpados agora ficam **fora** das métricas GTO (NULL honesto), como deveriam.

### fix(replayer): pro-notes do faces_squeeze (termo + dedup) + bucket de stack "≈"

> **Pro-notes**: no faces_squeeze, a nota reusava `_vs_3bet_notes` e dizia **"vs 3bet"** (errado — é squeeze) e **duplicava o "why"** do card ("fora do range"). Agora `_vs_3bet_notes` é parametrizado por cenário (diz **"squeeze"** no faces_squeeze) e a nota de fold out-of-range correto é **suprimida** (o "why" já explica) — só aparece quando o jogador **desvia** (continua), aí explicando o erro. **Bucket de stack**: o GTO resolve em depths discretos (10/14/.../50/75/100bb); com stack 61,9bb o card mostrava "· 50BB" (parecia erro). Agora prefixa **"≈"** quando o bucket diverge do stack real (**"≈50bb"** = depth resolvido mais próximo). Testes verdes (preflop 76, invariants 8, regression 26).

### fix(replayer): equity não contradiz mais o veredito GTO (Fase 1 do EV range-aware)

> No Decision Card, a linha de equity mostrava **"Necess. 46,5% +3,5pp" em verde** ao lado de **"Fold 100% · Correto"** — parecia que o sistema se contradizia. Causa: a equity preflop é heurística **vs mão aleatória** (`_estimate_hand_equity` dá 0,50 fixo p/ par baixo), não vs o range real do squeeze (onde 55 tem ~38% < necessário). **Fase 1 (display guard):** quando há cobertura GTO preflop, o veredito do solver é a fonte de verdade — o `+pp` deixa de ser pintado de verde/vermelho (fica neutro) e a equity ganha o caveat **"vs aleatória"** + tooltip explicando. Resolve a contradição percebida. A Fase 2 (equity range-aware de verdade, via matriz 169×169) está no backlog #27.

### fix(replayer): label do range por cenário (não "abertura" sempre) + i18n de strings do card

> O Decision Card mostrava **"Range de abertura"** hardcoded em **todos** os cenários — errado em vs RFI / vs 3bet / vs Squeeze, onde o `range_pct` é defesa/continuação, não abertura. Agora o rótulo é por cenário: **abertura** (RFI), **defesa** (vs RFI), **continuação** (vs 3bet / vs Squeeze / vs 4bet), **squeeze**. De quebra, i18n de strings que estavam hardcoded em PT no card ("Estratégia do Solver", "Equity Necessária") — chaves nas 3 locales. Termos de poker (Equity, Pot Odds, Stack, M, ICM, SPR) seguem em inglês por regra.

### docs: nova seção "Revisão de Mão (Replayer)" no /docs

> Documenta conceitualmente (sem expor internals) como ler o Replayer: a **mesa** (posição de cada jogador UTG/LJ/HJ/CO/BTN/SB/BB, stack, dealer button, suas cartas), o **card de decisão** (mostra a estratégia GTO das **suas cartas específicas** — ex.: Fold 100% ou Raise 74% · All-in 26% — não o range agregado da posição, + veredicto e indicadores), e a **honestidade de cobertura** (potes limpados aparecem como "{pos} vs Limp", checks de opção não são avaliados). Nova entrada no nav + seção em `Docs.tsx`, i18n nas 3 locales.

### fix(replayer): FOLD não esmaece no próprio step + cor cinza neutra (não vermelho)

> O texto "FOLD" saía esmaecido porque o pod já recebia `opacity 0.28` (jogador foldado) **no mesmo step** da ação. Agora não escurece enquanto for a ação ativa (`isFolded && !isActive`) — o FOLD aparece em opacidade cheia com a borda dourada, e só apaga nos steps seguintes. A **cor** mudou de vermelho (`#e52020`, perto do all-in `#ff4040` e com cara de "erro") para **cinza neutro** (`#9aa0a8`) — fold é ação passiva.

### style(replayer): cartas com margem branca uniforme, sem contorno cinza + verso emoldurado

> Os SVGs do baralho são full-bleed (valor/naipe colados na borda) e tinham um contorno próprio (linha cinza). Correções: (1) `cardSVG` desenha a **moldura branca ajustada à proporção real do baralho** (~0,69), com margem **uniforme** ao redor — antes preencher o slot todo com `meet` deixava letterbox em cima/baixo (borda superior parecia maior que as laterais); (2) **contorno cinza removido na origem** — `stroke-width:0` no retângulo de fundo dos 52 SVGs (o índice do canto era colado demais pra recortar/pintar por cima sem cortá-lo), então a face é renderizada no tamanho natural, sem corte; (3) o **verso** (face-down) ganhou moldura **cinza azulado** (`#7c8696`, ~6%) — não branca, que chamava muito atenção contra o fundo escuro. Cobre hero, vilões e showdown de uma vez.

### fix(replayer): geometria de bet chips + dealer button sem sobreposições (modelo validado)

> As fichas de aposta e o dealer button usavam um modelo de **fração da distância ao centro** (`t2`/`perpOff`), que numa mesa **oval** dava folgas absolutas inconsistentes (78px a 139px do pod no mesmo `t2`) e — pior — bet e dealer eram calculados **independentemente**, colidindo em quase todos os assentos (101–651px² de interseção no teste), com o dealer invadindo as cartas em bottom seats. Reescrito com modelo **validado numericamente** (`scripts/chip_geometry_check.mjs`, 0 sobreposições em 6/8/9-max e hero em qualquer assento): bet chips ancoram na **borda distante de (pod ∪ cartas)** ao longo do vetor inboard + gap fixo (folga consistente, pula as cartas dos bottom seats); dealer **inboard, contido na elipse do feltro** (busca inboard×lateral escolhendo o ponto válido mais próximo do pod) — os pods ficam na borda/rail, então o dealer precisa vir pra dentro do verde, sem tocar pod/cartas/fichas. Winner chips (showdown) usam a mesma âncora. Confirmado por screenshots reais nos 3 breakpoints.

### feat(replayer): rótulos de posição na mesa + layout mobile usável (design pass)

> Revisão de design do Replayer com screenshots reais (harness Playwright `frontend/scripts/replayer_shots.mjs`, 3 breakpoints). Três entregas:
> - **Position labels na mesa:** cada cadeira agora mostra a posição (UTG/UTG+1/UTG+2/LJ/HJ/CO/BTN/SB/BB) numa tab no topo do pod — antes só nome+stack, o usuário tinha que contar a partir do dealer button. Hero em dourado; renderizada fora do grupo de opacity (visível mesmo quando o jogador folda, como o dealer button).
> - **Mobile usável:** o root era `h-dvh overflow-hidden` (viewport fixo) em todos os breakpoints → no celular a mesa era espremida e o **card de análise (o veredito) ficava cortado fora da tela**. Agora mobile rola (`min-h-dvh overflow-y-auto`) e a mesa dimensiona pela largura; o veredito aparece acima da dobra. Desktop mantém o split de viewport fixo (`lg:`).
> - **`MP` → `LJ`:** a mesa exibia "MP"; o GTO Solver (e o próprio engine, que normaliza `MP→LJ`) usa **LJ (LoJack)** em 9-max. Alinhado o `pos_names` do `/replay` ao Decision Card.

### fix(dev): proxy `/replay` colidia com a rota SPA `/replayer` (404 em load direto)

> O proxy do Vite usava o prefixo `/replay`, que casa também com **`/replayer`** (a rota do SPA). Resultado: abrir/recarregar/bookmarkar `localhost:8080/replayer?...` direto caía no 404 do backend (`{"error":"Rota não encontrada"}`) em vez de carregar o SPA — só funcionava navegando de dentro do app (client-side routing). Fix: chave do proxy `/replay` → `/replay/` (a API sempre chama `/replay/{t}/{h}` e `/replay/{id}/gto`, então a barra final preserva o proxy e libera `/replayer`). Descoberto via harness de screenshots do Replayer (`frontend/scripts/replayer_shots.mjs`, Playwright). Validado: `/replayer` serve SPA, `/replay/1/2` → backend 401.

### feat(replayer): pote limpado rotulado "{pos} vs Limp" em vez de NULL mudo (INV-12)

> Spots de **pote limpado** (limp sem raise: BB-check de opção, over-limp, iso-raise) ficavam `available=False` **silencioso** no Replayer — parecia falta de captura, mas é gap de cenário conhecido (cobrimos só árvores raise-first; backlog #22). `hand_state_builder` agora detecta o limp (`facing_limp`: `calls ≥ ~1bb` sem raise, hero não-agressor), `analyze_preflop` devolve `coverage_reason='limped_pot'`, e o Decision Card mostra **"Sem veredito GTO · {pos} vs Limp"** com tooltip explicando que não é falha de captura. i18n nas 3 locales. Dataset local: 8 spots. Novo invariante **INV-12** (`test_inv_limped_pot_coverage_reason`). Walk genuíno (sem limp) segue `available=False` sem rótulo. Engine 270/270, api verde, tsc ✓.

### fix(preflop-gto): `hand_freq` sempre é distribuição válida da mão quando available (INV-10)

> Causa-raiz do "Range agregado" no Decision Card/Replayer: para mãos **out-of-range** (sem entrada no GW), `analyze_preflop` devolvia `hand_freq=None` (path RFI, ex.: 83o) ou **`{tudo-zero}`** (path vs_rfi, ex.: 82o BTN vs HJ; faces_squeeze). O `Replayer.tsx` só usa `hand_freq` quando soma > 0 — com None/zero **caía no % AGREGADO** do range (distribuição da posição, ex.: "Fold 79,8% / Raise 12,7%") em vez do veredito da carta (Fold 100%). Sweep nas 832 decisões preflop reais achou **223 casos** (222 vs_rfi + 1 faces_squeeze) ainda caindo no agregado. **Fix estrutural** (não patch por-path): normalização única na saída de `analyze_preflop` — `available=True` sem distribuição válida ⇒ fold puro 100%. Novo invariante **INV-10** (`test_inv_hand_freq_distribution`, suite engine) trava a regressão. Sweep pós-fix: 0 inválidos em 832. Engine 268/268.

### feat(replayer): card mostra % de ação DA MÃO do jogador (não do range agregado)

> No `RangePanel`, novo bloco **"Estratégia da sua mão · {mão}"** com barra + % por ação **da carta específica do hero** (de `gto.hand_freq`): 83o → Fold 100%, AKo → Raise 74% / All-in 26%. Antes o card só destacava a legenda do **range agregado** (% de outras mãos), confuso — o jogador tem cartas específicas, a análise deve ser sobre a mão dele. `hand_freq` None → fold puro 100%. O grid 13×13 continua como **referência** da estratégia da posição (com a célula do hero em anel amarelo). Tipo do cenário em `api.ts` ganhou `faces_squeeze`/`squeeze`. Build ✓.

### docs(specs): pasta `docs/specs/` (contratos/invariantes) + `test_invariants.py`

> Base de proteção contra regressão: `docs/specs/` consolida os **contratos** do sistema (README com a filosofia "spec é contrato, não prosa", architecture, invariants, preflop-gto, gto-capture, decision-pipeline, glossary). O documento central `invariants.md` lista os **9 invariantes que nunca podem quebrar** (roteamento preflop, reconciliação label↔gto, NULL honesto, depths válidos, history_spot, sizing 3bet, deploy /opt, cegueira ao sizing do open, hero_won_hand) — cada um amarrado a um teste. Novo `backend/tests/test_invariants.py` (suite engine) guarda 5 invariantes code-testáveis (incl. o que pegaria o bug "call vs squeeze"). Backlog #23 registrado (vereditos sensíveis ao tamanho do open).

### fix(replay): rótulo do cenário `faces_squeeze` cru + auditoria do bug de squeeze

> O Replayer mostrava "Cenário **faces_squeeze**" (chave interna crua) porque os mapas de rótulo (`scenarioLabel` em `Replayer.tsx`, `SCENARIO_LABEL`/`SCENARIO_TO_TYPE` em `RangePanel.tsx`, e o standalone `leaklab-replayer-v3.html`) não tinham `faces_squeeze` nem `squeeze` → caíam no fallback que exibe a chave. Adicionados: `faces_squeeze`→"vs Squeeze", `squeeze`→"Squeeze", `vs_shove_fallback`→"vs Shove" (termos de poker em inglês, como "vs Open"/"vs 3-Bet"); `SCENARIO_TO_TYPE` mapeia faces_squeeze→'call' (defesa) e squeeze→'3bet'. **Auditoria do fix de squeeze anterior**: dos **40** spots `faces_squeeze` em 5 torneios, **18** o display divergia e **14 eram GRAVES** (correto=fold, mas o Replayer sugeria call/raise — ex.: `T4o BB vs BTN`, `54o`, `Q8o`, `K8o`). Todos resolvidos pelo fix dos 4 call sites; vereditos gravados sempre corretos.

### fix(replay): faces_squeeze sugeria "call" no Replayer (params faltando no recompute)

> O Replayer sugeria **call** num spot de squeeze (ex.: BB 54s enfrenta squeeze do SB a 30bb) enquanto o dashboard corretamente dizia **fold**. Causa: o endpoint `/replay` (e outros 3 paths de display: `/analyze` enriched, coach replay, GTO live override) **recomputavam `analyze_preflop` sem passar `facing_raises` e `hero_was_aggressor`** — sem o sinal `facing_raises>=2`, o roteamento não chegava em `faces_squeeze` e caía em `vs_rfi` (defesa larga do BB), que tem 54s no range → "call". Era o bug "call 45s vs squeeze" que o fix do `facing_raises` resolveu no engine, mas os 4 call sites de display ficaram de fora. Fix: os 4 passam agora `facing_raises` (de `preflopRaisesFaced`/coluna) + `hero_was_aggressor` + `n_players`. Confirmado: `/replay` agora dá `faces_squeeze / fold / correct`, igual ao veredito armazenado. Os vereditos GRAVADOS sempre estiveram certos (via `evaluate_decision`); só o display recomputado divergia. Preflop 76/76, regression 26/26.

### feat(dashboard #5): "Resultado × GTO" — erros de GTO escondidos atrás de vitórias

> Novo card **Results × GTO** (insight de coaching: *resultado ≠ processo*). Análise revelou que o #5 original (divergência `label`×`gto_label`) ficou **obsoleto** — o engine reconcilia os dois, então concordam por design (2/990 divergentes). O ângulo com valor real é **resultado × GTO**: decisões que foram **erro CLARO de GTO** (`gto_critical`) mas a mão foi **GANHA** (hero coletou o pote) — o resultado mascara o erro de processo. Dados (user 13): **37,6% dos erros claros ficaram escondidos atrás de vitórias**, e **41,5% das decisões em mãos ganhas foram erro claro**. Cadeia completa: coluna `decisions.hero_won_hand` (1/0/NULL, migração) + `_detect_hand_won` (hero collected, com/sem showdown) no `/analyze` + `save_decisions` + backfill (`scripts/backfill_hero_won_hand.py`, 231 mãos ganhas) + `get_results_vs_gto` (headline + spots recorrentes) + endpoint `GET /player/results-vs-gto` + `ResultsVsGtoCard` no Index (seção GTO). i18n pt-BR/en/es (`resultsVsGto.*`) + linha "Resultado × GTO" na tabela de indicadores do /docs. Testes: `test_detect_hand_won` + `test_results_vs_gto_endpoint` (API 42/42, database 22/22). Termos de poker (posição/street/ação) mantidos em inglês.

### docs(/docs): nota de cobertura preflop GTO (~95%) na seção de metodologia

> Adicionado parágrafo `gto_method.coverage` (3 locales pt-BR/en/es) na seção "Metodologia de Classificação GTO" do /docs: explica, em nível de **conceito**, que ~95% das decisões pré-flop padrão recebem veredicto GTO e que o que fica de fora (potes limpados, linhas não-padrão) aparece sem classificação — sem expor internos (sizings, snap de depth, etc.). Reflete o fechamento do preflop desta sessão (91,7%→95,1%).

### fix(preflop-gto): 3bet-shove (RAI) em stacks rasos → cobertura preflop 92,8%→94,4%

> Em stacks RASOS (10/14/20bb, e alguns 30/50bb) o 3bet/squeeze é um SHOVE (`RAI`), não um raise `R6` — o nó com `R6` **não existe** na árvore rasa do GTO Solver (`R2-...-R6-F` a 10bb = no-solution; `R2-...-RAI-F` resolve com 169 mãos). Os MISS de stack raso do backfill eram disso, não gap genuíno do GW. Fix em `build_canonical_pf`/`build_pf` (autocapture + `fetch_null_canonical`): o token do 3bet é parametrizado e tentado na ordem do bucket (`RAI` primeiro nos rasos, `R6` nos fundos) com fallback pro outro. Re-run do backfill: **OK 6→13** (só 3 MISS), +12 faces_squeeze no master → **+14 decisões fechadas, cobertura 92,8%→94,4%** (49 NULLs). O re-grade por ORDEM dentro da mão fechou +2 que o resync `(hand_id,action)` pulava (ambíguos). 0 conflito mantido. Descoberto por reprodução manual do usuário (URL com `RAI` resolvendo a 10bb).

### feat(preflop-gto): auto-capture ON-DEMAND fecha NULLs preflop organicamente nos uploads

> Novo módulo `leaklab/preflop_autocapture.py` + thread no fim do `/analyze`: quando um upload gera decisões preflop que o engine não cobre (`available=False`), busca o spot CANÔNICO no GTO Solver (pf por posições, `snap_raises=False` + `fetch_timeout=15` = fast-fail sem travar o servidor), **injeta no master de ranges** (escrita atômica) e **re-grada** as decisões afetadas — fechando os NULLs sem intervenção. Tabela `gto_preflop_capture` rastreia resultado por spot (captured/no_solution/impossible/failed) pra NÃO re-buscar no-solution genuíno a cada upload (não martela o GW). Re-grade casa decisões por ORDEM dentro da mão (fecha também mãos com 2+ decisões preflop da mesma ação, que o match por `(hand_id,action)` pulava). Reusa a classificação/conversão validadas no backfill (hero_position real do GW + seat-tracking). Provado end-to-end (teste controlado: spot revertido + decisão→NULL → autocapture re-captura e re-grada → `gto_correct` restaurado). Suites preflop 76/76 e API 40/40 verdes; cobertura 92,8% / 0 conflito intactos. Roda em daemon thread (bounded `max_spots=12`/upload), no-op quando GW desabilitado.

### feat(gto-server): fast-fail no-solution destrava captura em massa → cobertura preflop 91,7%→92,8%

> **Causa real da "degradação" do servidor (não era recurso — VM é 4 vCPU/16GB):** um no-solution que PENDURA (GW sem o nó) bloqueia as requisições seguintes pelo tempo do timeout — pior com o snap-retry (2 ciclos = ~90s de janela de bloqueio). Diagnóstico provou: 6 spots solúveis em sequência ficam rápidos (~8s); um único no-solution-timeout cascateava (aba fresca por fetch NÃO resolveu — o travamento é na requisição/sessão do GW). Fix: `fetch_timeout` configurável (`server.py`, 8-60s) + `snap_raises` exposto no client → o `fetch_null_canonical.py` usa `snap_raises=False` (pf canônicos R2/R6 não precisam de snap; pula o 2º ciclo) + `fetch_timeout=15` → no-solution falha em ~9-15s **sem cascata**. Mix solúvel↔no-solution agora 100% limpo. Com isso, o bulk capturou **6 pares** (vs 1 antes) — faces_squeeze 30/50bb (ex.: BB vs BTN cobre 4 decisões) → **+8 decisões NULL fechadas, cobertura 91,9%→92,8%** (63 NULLs restantes), 0 conflito / 0 drift. Os 18 MISS são no-solution GENUÍNOS confirmados (com fast-fail sem cascata, MISS = GW realmente não tem o nó). Restantes: shallow 10/14bb + estruturais → captura on-demand futura.

### fix(deploy): serviço GTO roda de /opt/leaklab — pulls em ~/leaklab nunca chegavam ao código vivo

> **Causa-raiz de "nenhum fix do servidor pegava":** o systemd `leaklab-solver` tem `WorkingDirectory=/opt/leaklab/backend/gto_bot/solver_api`, mas todos os `git pull` eram em `~/leaklab` (`/home/rodrigo_phpro/leaklab`). Por isso history_spot, auto-cura e perf-Cash não surtiam efeito — o código vivo era antigo. Deploy correto: `cd /opt/leaklab && sudo git pull && sudo systemctl restart leaklab-solver`. Após o pull no lugar certo, o history_spot foi **confirmado end-to-end**: o spot `100bb faces_squeeze LJ vs UTG+2` (antes "no-solution") capturou 169 mãos e cobriu 2 decisões NULL → cobertura preflop **91,7%→91,9%**. Pendência de produção: alinhar o deploy do servidor GTO pra apontar pro checkout versionado.

### fix(gto-server): auto-cura do _gw_subprocess + history_spot dinâmico (o "teto" de 91,7% era artificial)

> **O teto de cobertura preflop NÃO era real** — eram dois bugs no servidor GTO que só rodavam em produção (`/opt/leaklab`). (1) **history_spot fixo:** `_GW_APP_DEFAULTS` fixava `history_spot=7` em TODA navegação. É o índice do nó que a SPA do GTO Solver abre = nº de ações antes da decisão do hero. Com fixo 7, linhas de ≤7 tokens funcionavam (GW clampa p/ baixo), mas 8+ ações (ex.: BB enfrenta open+3bet após folds, `R2-F-F-F-F-F-R6-F`=8) abriam o nó ERRADO → a SPA pedia outro `preflop_actions`, o interceptor nunca casava → timeout = **no-solution FALSO**. Era o padrão exato dos 24 MISS do `fetch_null_canonical.py`. Fix (`query_gto_wizard_raw`): calcula `history_spot` pela contagem real de tokens (todas as streets) e injeta nos `api_params`. (2) **auto-cura (`_gw_subprocess`):** em timeout, troca por aba fresca e retenta 1×; em falha, deixa a página numa URL MTT limpa (RFI) pro próximo fetch não herdar o estado preso. Snap de depth (`30→32→32.125`) já estava certo. **Limitação remanescente:** o box do servidor é 1 core/1GB — cada navegação no-solution pina a CPU única e degrada os fetches seguintes (cascata), inviabilizando captura em massa sustentada; on-demand (1 spot por vez, box saudável) funciona. Backfill dos ~25 pares NULL fica para captura on-demand ou um box maior.

### fix(gto-server): history_spot dinâmico destrava spots de 8+ ações (o "teto" de 91,7% era artificial)

> **O teto de cobertura preflop NÃO era real** — era um bug. O `_GW_APP_DEFAULTS` do servidor GTO fixava `history_spot=7` em TODA navegação. O `history_spot` é o índice do nó que a SPA do GTO Solver abre = quantas ações ocorreram antes da decisão do hero. Com valor fixo 7, linhas de **≤7 tokens** funcionavam (o GW clampa p/ baixo e acerta o nó), mas linhas de **8+ ações** (ex.: BB enfrenta open+3bet após folds — `R2-F-F-F-F-F-R6-F` = 8) navegavam pro nó ERRADO (uma ação antes), a SPA pedia outro `preflop_actions`, e o interceptor nunca casava o response esperado → timeout = **no-solution FALSO**. Foi exatamente o padrão dos 24 MISS do `fetch_null_canonical.py` (todos 8+ tokens). Confirmado manualmente: a mesma URL com `history_spot=8` resolve. Fix em `server.py` (`query_gto_wizard_raw`): calcula `history_spot` dinamicamente pela contagem real de tokens de ação (preflop+flop+turn+river) e injeta nos `api_params` (sobrescreve o default). O snap de depth (`_snap_to_valid_depth(30)→32→32.125`, por causa do gap 25→32 na lista de válidos) já estava correto — stacks não eram o problema. **Requer deploy no servidor GTO (GCP): `git pull` + restart do `leaklab-solver`.** Depois: re-rodar `fetch_null_canonical.py` deve converter a maioria dos MISS em OK e elevar a cobertura preflop bem acima de 91,7%.

### chore(preflop-gto): teto prático de cobertura preflop confirmado em 91,7% (73 NULLs = honestos) [SUPERSEDED]

> ⚠️ **Conclusão revista** — o "teto" foi causado pelo bug de `history_spot` acima, não por ausência de soluções no GW. Mantido para histórico.

> Investigação conclusiva dos 73 NULLs preflop restantes via **fetch canônico direcionado** (`fetch_null_canonical.py`): em vez do pf REAL da mão (que não casa na árvore do GW), constrói o pf CANÔNICO a partir das posições (hero × 3bettor/opener, códigos R2/R6/C, ordem de seat 9-max). Dos 45 NULLs cobríveis em teoria (33 pares únicos): **8 são estruturalmente impossíveis** (vs age depois do hero — limp pots / quirks de posição), e **24 faces_squeeze dão no-solution no GW mesmo num servidor limpo**. Diagnóstico isolou a causa: as soluções MTT do GTO Solver são **esparsas** para spots multiway de squeeze — só resolvem quando (a) o hero age IMEDIATAMENTE após o 3bettor (um fold intermediário já mata: `R2-R6`→SB resolve, `R2-R6-F`→BB não) e (b) depth+sizes batem na árvore (mesmo pf resolve a 30bb mas não a 20bb). Conclusão: os 73 NULLs são **honestos** (o GW não tem essas soluções), não falha nossa. Cobertura preflop fica em **91,7%** (802/875); coerência 0 conflito / 0 drift. Os spots restantes ficam para captura on-demand futura, quando recorrerem em uploads reais com a árvore certa. `fetch_null_spots.py` (pf-real) e `fetch_null_canonical.py` (pf-canônico) mantidos como referência da investigação.

### perf(gto-server): detecção rápida do fallback-Cash corta no-solution de ~25s para ~2s

> O grind do seed preflop era dominado por **timeouts de ~25s em spots MTT sem solução**: o GTO Solver, ao não achar solução, redireciona a SPA para o default Cash (`gametype=Cash*`), cuja chamada de API **não bate** no matcher do alvo (que exige `gametype=MTT…`) → o `expect_response` esperava o timeout INTEIRO por um match que nunca vinha (~25s por dead-end, a ~3,5 nós/min). Fix em `_gw_subprocess.py`: o matcher agora reconhece TAMBÉM o request de fallback-Cash (`is_cash_fallback`) e retorna `no_solution_cash_fallback` (status 204) na hora — ~10x no grind dos dead-ends. Só dispara quando o alvo é MTT (fetch de Cash legítimo não afeta). Compõe com a fresh-tab recovery (que destrava a página presa no fetch seguinte). **Requer deploy no servidor GTO (GCP): `git pull` + restart do `leaklab-solver`.**

### feat(gto-seed): seed de buckets profundos (17–100bb) com poda multiway agressiva

> Run focado do `seed_preflop_gw.py --stacks 17,20,30,40,50,75,100 --max-calls 1` capturou spots dos buckets profundos (faces_squeeze/squeeze) — 6 spots novos no master (17bb). Cobertura preflop estável em 91,7% (os 73 NULLs restantes exigem pares hero×3bettor específicos de stack profundo que o walk limitado ainda não alcança no tempo do timeout-lento — destravados pelo perf acima, que permite o grind completo). Merge add-only; coerência 0 conflito / 0 drift.

### feat(preflop-gto): engine consome o cenário `faces_squeeze` + merge add-only do seed

> `analyze_preflop` agora roteia "cold/blind enfrenta open+3bet/squeeze" (`facing_raises>=2 and not hero_was_aggressor`) para o cenário **`faces_squeeze`** (lookup `ranges[bucket][faces_squeeze][hero][3bettor]`, mesma graduação do `vs_3bet`) em vez de `faces_3bet_uncovered`→NULL fixo. Com cobertura → grade real (ex.: cold vs jam a 10bb: AA=call `correct`, 72o=fold, call 72o=`major_leak`); sem cobertura → NULL honesto (mantém a proteção anti "call 45s vs squeeze"). Isso destrava o bucket B (39 NULLs preflop) à medida que o seed o cobre. `merge_seed_ranges.py` funde o JSON do seed no master em modo **add-only** (preenche lacunas, não sobrescreve RFI/vs_RFI/vs_3bet validados; `--overwrite` opcional; backup automático). Suite preflop 26+76 verde.

### feat(gto-seed): conversor JSONL→master de ranges (classificação correta + faces_squeeze)

> `convert_seed_to_ranges.py` mapeia os checkpoints do seed (`gw_preflop_seed/*.jsonl`) para a estrutura do master (`ranges[bucket][scenario][k1][k2]`). Classificação por **seat-tracking + hero_position real do GW** — não repete o bug do `classify_spot` (que assumia hero=opener em pote de 2 raises). Cobre rfi/vs_rfi/squeeze/vs_3bet e o cenário **novo `faces_squeeze`** (cold/blind enfrenta open+3bet/squeeze — o bucket B dos NULLs preflop). spot_data com `*_pct`/`*_hands`/`hand_freqs` (codes crus) no formato que o `analyze_preflop` consome. Validado: ex. UTG+2 vs jam a 10bb → call só com 99+/AKs (range correto), 0 nós pulados.

### fix(gto-server): `_fetch_via_page` roda Playwright sync em thread isolado (imune a event loop)

> O endpoint `/gw-spot` do servidor GTO (GCP, `gto_bot/solver_api/server.py`) falhava com *"Sync API inside the asyncio loop"*. 1ª tentativa (`ThreadPoolExecutor` por chamada) destravou a 1ª chamada mas **degradava após ~N fetches** — `sync_playwright().start()/.stop()` repetido (connect/disconnect CDP por chamada) vaza event loops / processos node. Fix definitivo: **thread-worker única** que cria o Playwright UMA vez, reusa a conexão CDP e processa TODOS os fetches + a captura de auth por uma fila (`_pw_worker_loop`/`_pw_run`), serializados naturalmente. Zero churn de start/stop. Destrava o seed/auto-captura preflop via GW de forma estável.

### fix(preflop-gto): hero-como-3bettor roteia para vs_rfi (não vs_3bet) — recupera grades reais

> Follow-up do bucket A. Quando o hero **É o 3bettor** (3beta um open, sem ter aberto), a decisão é de **defesa vs open** — deve ser gradeada pela frequência de 3bet do range `vs_rfi[defensor][opener]`, não por `vs_3bet[opener][3bettor]` (resposta do opener, estrutura errada que o fallback frouxo mascarava). Removido o branch `is_3bet_pot → vs_3bet`: hero-3bettor agora flui pra `vs_rfi`. **Recupera 13 grades reais** (ex.: SB jam vs CO open, HJ 3bet vs UTG+1 → `gto_correct`; CO 3bet quando GTO manda call → `gto_critical`) e converte 4 limp-reshove (SB limpa→BB iso→SB jam, sem range GTO) para NULL honesto. Cobertura preflop 89,6%→90,6%; coerência segue 0 conflito / 0 drift; suite 743/743. Aplica em uploads via `evaluate_decision`. Com isso, `is_3bet_pot` só roteia squeeze; os dois lados do 3bet têm scenario correto (opener→vs_3bet, 3bettor→vs_rfi).

### fix(preflop-gto): roteia "hero abriu + enfrenta 3bet" para vs_3bet + lookup exact-only (sem fallback de 3bettor aleatório)

> Análise dos 99 NULLs preflop revelou que **24 não eram falta de range — eram bug de roteamento**: quando o hero **abre** (RFI) e enfrenta um 3bet, `is_3bet_pot` vem `False` (o flag marca "hero FEZ o 3bet", não "hero ENFRENTA"), então caía em `vs_rfi` sem entrada pro pareamento opener×3bettor → NULL falso. A range `vs_3bet[opener][3bettor]` (GW v3) já cobre o caso. Novo branch em `analyze_preflop`: `hero_was_aggressor and facing_size>0 and vs_pos → vs_3bet`. Recupera 24 grades (verificados por match exato).
> No mesmo passo, **removido o fallback "qualquer 3bettor"** do lookup vs_3bet: com vs_pos desconhecido ou pareamento inexistente (ex.: `vs_3bet[SB][BTN]` — BTN age antes do SB, não pode 3betá-lo), aplicava a range de um 3bettor aleatório = **veredito GTO falso**. Agora é exact-only → NULL honesto. Isso zerou **16 grades de aproximação** (hero-como-3bettor mal-roteado) que existiam só por causa do fallback. Aplica automaticamente em uploads (`/analyze` → `evaluate_decision` → `save_decisions`). +3 testes de regressão; cobertura preflop 88,7%→89,6%; auditoria de coerência segue 0 conflito / 0 drift.
> **Follow-up identificado (não corrigido):** o espelho do bucket A — "hero É o 3bettor" (`is_3bet=True`) hoje roteia pra `vs_3bet[3bettor][opener]` (estrutura errada; era o que o fallback mascarava). O correto é gradeá-lo pela frequência de 3bet do `vs_rfi` do defensor. Hoje fica NULL honesto.

### fix(engine/revalidação): push/fold curtos — guard all-in não rebaixa mais commit para fold; oracle/differ deixam de inflar major_mismatch

> Investigação dos 6 `major_mismatch` short-stack restantes. Causa-raiz: em preflop o engine não computa equity-vs-range (`estimatedHandEquity=None`), então a porta `_eq >= _req` do guard de all-in era código morto que **sempre caía em fold** — rebaixava calls/commits triviais (AK/AJ vs shove). Agora, quando o range GTO recomendava comprometer o stack (`jam`/`call`) e o `jam` é impossível facing all-in, o guard colapsa em **call**, não fold.
> Dois ajustes no subsistema de revalidação corrigem a classificação: (1) `differ` deixa de tratar `call` como ação passiva — calar é commit/continuação, não desistência, então `call` vs `jam` não forma mais "swap agressivo↔passivo"; (2) `oracle` colapsa `jam→call` facing all-in que cobre o hero (não dá pra jam sobre um shove). Resultado: `major_mismatch` 6 → **0**, `aligned` 93,2% → **93,7%**.

### chore(data): reconciliação do gto postflop armazenado vs nodes limpos + script `resync_postflop_gto.py`

> O `gto_label`/`gto_action` postflop em `decisions` foi gravado contra a tabela `gto_nodes` **antes** da limpeza desta sessão (delete de nodes corrompidos, recuperação via bet_bucket, fix do `normalize_cards`). Como o produto serve o valor armazenado, 26 decisões estavam stale: **9 verditos sem node de respaldo** (vanished → NULL honesto), **4 recuperáveis não exibidos** (appeared), **9 drifts de label** (incl. **5 falsos `gto_critical` → `gto_minor_deviation`**, que super-penalizavam o player) e correções de `gto_action`. Novo script `resync_postflop_gto.py` regrava os 4 campos JUNTOS (label/best/gto_label/gto_action) do mesmo recompute fresco — evita `label_gto_conflict`; matching inequívoco; usa `busy_timeout` (DB local tem servidores dev vivos). Verificado: 0 conflito, 8/8 vanished genuinamente sem node, indicadores são live (sem cache a refazer). Preflop **não** tocado — o "drift" preflop reportado é artefato (disponibilidade do `_enrich_preflop_gto` é mais estrita que `analyze_preflop`; o `gto_correct` armazenado está respaldado).
> **Limpeza operacional** (DB dev): 1 decisão presa em `wizard_pending` era re-estampada a cada ciclo do worker (`_mark_failed_solver_jobs_as_wizard_pending`, match fuzzy street+position+stack±5+facing±1 contra jobs `failed`). Fix durável: rejeitado o job `failed` que fazia match (#1155) + zerado o `gto_label` (spot sem node = NULL honesto), para não reaparecer em restart. Também rejeitado 1 `gto_hand_requests` órfão (#202, `solver_queued` há 11 dias sem progresso, fila sem pendentes).

### chore(data): reconciliação do gto PREFLOP + auditoria de coerência total do banco

> Auditoria completa stored-vs-engine (preflop range-backed + postflop node-backed) achou **24 phantoms preflop**: `gto_correct`/`gto_critical` armazenados em spots que o engine atual marca `unavailable` — eram **non-RFI/limp** (SB limp-call vs BB, pareamentos de posição que só ocorrem após limp, BB check grátis) que as tabelas vs_RFI genuinamente não cobrem; o grade falso vinha de lógica anterior aos params `facing_raises`/`hero_was_aggressor` (fix de squeeze). `resync_postflop_gto.py` generalizado com `--street {preflop,postflop,all}`; reconciliados 22 phantom→NULL + 2 appeared (range agora cobre). Labels preservados (o gto phantom não dirigia o label). **Auditoria final: 0 `label_gto_conflict`, 0 `gto_label_no_action`, 0 `wizard_pending`, 0 drift (preflop e postflop, incl. multi-decision), cobertura honesta 88,7% preflop / 64% postflop — o restante é NULL honesto (sem solver/range), não verdito falso.**

## [v0.166.0] — 2026-06-01 — fix(engine): guard de all-in (unidades fichas×bb) — destrava jam do GTO

> Pós-auditoria pré-produção (dado real, seed fake removido): corrige o guard de all-in que comparava `facingSize` (fichas) com `effectiveStackBb` (bb) e rebaixava o `jam` recomendado pelo GTO. Auditoria: `major_mismatch` 25 → 6, `aligned` 91,1% → 93,2%.

### fix(engine): guard de all-in comparava facing (fichas) com stack (bb) — rebaixava jam do GTO
- A auditoria revelou 25 `major_mismatch` preflop onde o engine rebaixava o **`jam` recomendado pelo GTO** para `call`/`fold`. Causa: o guard "facing all-in" (`decision_engine_v11`) comparava `spot.facingSize` (em **fichas**) com `effectiveStackBb` (em **bb**) — ex.: facing 250 fichas tratado como 250bb >> stack 22bb → o guard disparava espúrio. Fix: converter o facing para bb via `context.levelBb` antes de comparar. O `bestAction` já era gto-first (linha 658); o guard é que o sabotava.
- **Resultado** (auditoria sobre dado real): `major_mismatch` **25 → 6** (-76%), `aligned` 91,1% → **93,2%**. Os 6 restantes são edge cases de short-stack push/fold (oracle heurístico vs engine), não bugs.
- **Sync de dado** (`scripts/sync_label_bestaction.py`): re-sincroniza `label`/`best_action` armazenados com o engine corrigido (66 decisões; sem tocar gto node-backed). 2 `label_gto_conflict` resultantes reconciliados via `_gto_label_cap`. Teste de regressão em `test_recent_regressions` (guard usa facing em bb; all-in genuíno ainda rebaixa).

## [v0.165.0] — 2026-06-01 — feat: Ranking de Alunos (#15) completo + auditoria de revalidação pré-produção + fixes preflop/GTO

> Destaques: **#15 Ranking de Alunos** end-to-end (opt-in/privacidade, handle único, snapshots/delta + cron local, coach view, badges/streaks, hall of fame, docs); **auditoria de revalidação pré-produção** (drift vs armazenado + scanner de padrões); **fix grave** de classificação preflop (squeeze tratado como vs_RFI); **fix** do lookup postflop (hero_hand corrompido na ingestão de nós); modo foco/tela cheia no Replayer; UX em colunas (rating/leaderboard/docs). Suite: 739 testes.

### fix(gto): hero_hand corrompido na ingestão de nós (lookup postflop) + recuperação
- **Root cause**: nós do `solver_cli` eram gravados com `hero_hand` char-split — `["4","A","d","d"]` em vez de `["4d","Ad"]` — porque `insert_gto_nodes` fazia `sorted(hero_hand)` com `hero_hand` chegando como **string** (`sorted("4dAd")`=`['4','A','d','d']`). Como `compute_spot_hash` ordena o hand, esses **137 nós (16%)** ficavam **inalcançáveis** pelo lookup hand-specific (caía no genérico board-level). Bug contínuo (15–29/05), solves desperdiçados.
- **Fix**: `gto_utils.normalize_cards()` conserta as 3 formas (lista correta / string / char-split) e é aplicado em `compute_spot_hash` e na gravação de `insert_gto_nodes` → ingestão robusta; lookups com lista correta inalterados.
- **Recuperação** (`scripts/fix_corrupt_gto_nodes.py`): brute-force do `bet_bucket` (6 valores) p/ casar o hash antigo → re-hash com o hand correto. **86 nós recuperados** (re-hash, voltam a ser alcançáveis), **51 deletados** (49 duplicatas de nós corretos + 2 não-recuperáveis). Corrompidos restantes: **0**.
- **Diagnóstico de contexto**: o lookup postflop estava **96% saudável** (156/163) — o alarme inicial foi super-generalizado de 1 nó. Restam **7 nós órfãos** (hash de fórmula antiga, pré-`acd7aba`) — desprezível, não afeta produção (exibe o stored). Teste em `test_recent_regressions`.

### fix(revalidation): correção dos achados reais da auditoria + precisão do scanner
- **`impossible_raise`** (1, crítico): linha com `best_action='jam'` enfrentando all-in (não dá pra jam — o guard atual dá fold). Era **stale**; corrigida para `fold`.
- **`faces_3bet_leftover`** (2, alto): squeeze-faced-cold residual (HJ cold-calling 3-bet) que o match do `fix_preflop_3bet_misclass` não pegou → gto limpo para NULL.
- **`gto_critical` stale no preflop** (11): squeeze-faced-cold dando "você cometeu erro crítico" em spots sem cobertura → limpos via novo `scripts/clear_stale_preflop_gto.py` (preflop-only, default só labels HARMFUL `gto_critical`/`minor_deviation`; `--all` p/ qualquer; matching seguro).
- **`multiway_highequity`**: check **removido** — usava `num_players` (tamanho da mesa), não oponentes ativos no pote (sem coluna) → 45 falsos positivos.
- **Drift `gto_label` agora confiável só no PREFLOP**: descoberto que o `evaluate_decision` postflop faz lookup on-demand de `gto_nodes` que **erra** (mismatch de spot_hash/hero_hand — inclusive node corrompido `["4","A","d","d"]`), então o "stale→NULL" postflop era **falso alarme** (labels postflop são solver-backed, legítimos). O drift de gto agora só dispara no preflop (fonte = ranges, autoritativa).
- **Pendências documentadas (não-bugs):** `gto_critical_fold` (69, lista de revisão — folds postflop legítimos), `postflop_mistake_no_gto` (24, gap de cobertura), e o **lookup postflop de gto_nodes** (a investigar — não afeta o que produção exibe, que é o stored). Suite completa verde.

### feat(revalidation): auditoria pré-produção — drift vs armazenado + scanner de padrões
- Estende o subsistema `leaklab/revalidation/` (que já compara engine-vs-oracle) com o que faltava pra uma revalidação completa antes de produção:
  - **Drift vs verdicto armazenado** (`orchestrator._fetch_stored_decisions` + `_drift_against_stored`): cada finding carrega `stored_*`/`fresh_*`/`drift`/`drift_fields`; tag especial **`gto_label:stale->NULL`** marca vereditos GTO armazenados que o recompute não produz mais — exatamente o que `reanalyze_all_labels` NÃO corrige (preserva).
  - **Scanner determinístico** (`leaklab/revalidation/pattern_scan.py`): 12 checks SQL de integridade/coerência (squeeze leftover, vs_position nulo, conflito label×gto, raise impossível, multiway high-equity, gto_critical em fold, duplicatas, hero_cards ausente, etc.) com count + ids + severidade + remediação. PKO como **caveat**, não divergência.
  - **Report** ganha 3 seções (Drift, Padrões suspeitos, Plano de correção); CLI `--scan-patterns/--no-scan-patterns`.
- **Read-only** (`--no-persist`): nada muta no banco. Correções ficam como passo revisado.
- **2 gaps de ferramenta sinalizados** no relatório: (1) "clear-stale-on-uncovered" geral (hoje só `fix_preflop_3bet_misclass.py`, só squeeze); (2) dedup de decisões duplicadas (inexistente).
- Testes: `test_revalidation_drift.py` (8) + `test_revalidation_pattern_scan.py` (9). Suites de revalidação existentes (oracle/differ/orchestrator/api/fixtures) sem regressão.
- **Exclusão de seed** (`exclude_seed=True` default, CLI `--include-seed`): os checks de dado real ignoram torneios FAKE do leaderboard; o caveat `seed_data` os conta à parte. Investigação confirmou que `UNIQUE(user_id, tournament_id)` já existe (0 violações) e não há duplicação real — os "474 duplicates" eram check impreciso + seed. Com seed excluído, o audit real mostra: gto_critical_fold 70, multiway_highequity 45, impossible_raise 1, faces_3bet_leftover 2.

### fix(preflop): squeeze/3-bet enfrentado a frio era classificado como vs_RFI (erro grave)
- **Bug**: quando o hero (cold caller / blind) enfrentava um **squeeze** (open + call + 3-bet) ou um 3-bet+, o engine colapsava o spot em **"vs_RFI"** (defesa vs open simples), aplicava o range larguíssimo de BB-vs-SB e recomendava, ex., **call 45s vs squeeze** — marcando um **fold correto como `gto_critical`** (e `small_mistake` no heurístico). Raiz: faltava o sinal "nº de raises de villains enfrentados"; o `is_3bet` do pipeline só significa "hero deu 3-bet".
- **Fix (3 camadas)**: `hand_state_builder` computa `preflop_raises_faced` + `hero_was_aggressor` da sequência de ações; `analyze_preflop` ganha guard — quando ≥2 raises enfrentados e hero não foi agressor, retorna **sem cobertura** (`faces_3bet_uncovered`, honesto) em vez de vs_RFI; `preflop_range_evaluator` (heurístico) folda borderline em squeeze a frio em vez de "call (set-mine)". Sinal persistido em **`decisions.preflop_raises_faced`** (migration PG+SQLite) e lido por `resync_preflop_all`/`sync_gto_labels` (proxy `hero_was_aggressor≈is_3bet`) p/ não reintroduzir.
- **Correção do dado**: `scripts/fix_preflop_3bet_misclass.py` (backfill da coluna + relabel via pipeline). Rodado local: **36 decisões** corrigidas em 10 torneios — as `gto_critical/call` em folds corretos viraram **NULL + best fold + label standard** (ex.: hand 257045883935, BB 45s vs squeeze).
- **Testes**: `test_recent_regressions` (guard do squeeze não vira vs_rfi/uncovered + hero-agressor não dispara; heurístico folda borderline a frio). Engine/regression sem quebra de distribuição.

### feat(replayer): modo foco / tela cheia para revisão de torneio
- Botão **"Tela cheia"** no top bar do Replayer: entra em **fullscreen real** (Fullscreen API) e oculta o `HudHeader` (nav, fila de upload, notificações, idioma, suporte) — o chrome do app que não serve à sessão de avaliação do coach.
- **Mantém o essencial**: mesa, controles e o painel de decisão/informações; adiciona o **logo LeakLabs** no top bar do modo foco (presença de marca, já que o header some). Largura passa a usar a tela inteira (sem o cap `max-w-[1600px]`).
- **Sair**: botão dedicado ou tecla **ESC** (sincronizado via `fullscreenchange`); degrada para modo-foco CSS se o navegador negar o fullscreen. O modo persiste ao navegar entre mãos. i18n PT/EN/ES (`replayer.focus.*`). Disponível para qualquer sessão (não só coach). Type-check + build limpos.

### docs(ranking): nova seção "Ranking de Alunos" na /docs (#15)
- Nova seção na `/docs` (entre Gamificação e Trajetória) cobrindo os recursos do ranking em nível **conceitual** (o que é e como ler — sem fórmulas/pesos/limiares internos, conforme o padrão das docs): propósito (por aprendizado, não dinheiro), **participação/privacidade** (opt-in + apelido anônimo), **sua posição e variação** (▲/▼/—), **campeões mensais** (hall of fame, anônimos sem opt-in) e **visão do coach**. Cross-link para a página de Rating ELO.
- A lista de **Conquistas** em Gamificação ganhou os 5 badges de ranking (🏅 Top 10, 🥉 Pódio, 👑 Nº 1, 📈 Crescente, ♠ Expert GTO). Nova entrada no índice/nav lateral + scroll-spy. i18n PT/EN/ES (bloco `ranking.*` + `gamification.ach_*`).

### feat(leaderboard): hall of fame — campeões mensais (#15)
- Card **"🏆 Campeões mensais"** na `/leaderboard` (sidebar): o **#1 do snapshot mais recente de cada mês**, mês mais novo primeiro. Aproveita a série de `leaderboard_snapshots`.
- **Privacidade**: só expõe a identidade de quem está com **opt-in** (via handle/username); campeão sem opt-in aparece como **Anônimo** (flag `anonymous`, localizada no frontend). Consistente com o resto do #15.
- **Backend**: `repositories.get_hall_of_fame(period_days, limit)` (1 por mês via dedup do mais recente); endpoint `GET /metrics/hall-of-fame`. **Frontend**: `HallOfFameCard` (mês formatado por locale via `Intl`), i18n PT/EN/ES (`hofTitle`/`anonymous`).
- Honesto: rende pouco agora (a série tem ~1 dia), mas a fundação preenche sozinha conforme os meses acumulam. Testes em `test_database` (1/mês, mais recente do mês vence, anônimo sem opt-in, período vazio).

### feat(leaderboard): badges de ranking + streaks (#15)
- **Streaks** já existiam (`add_xp` calcula dias consecutivos via `xp_last_activity`; conquista `streak_7`) — sem retrabalho. O ganho do #15 são **badges de ranking**, agora possíveis com os snapshots/rank_delta:
  - `rank_top10` 🏅, `rank_top3` 🥉, `rank_first` 👑 (posição geral entre elegíveis), `rank_climber` 📈 (subiu de posição, via `rank_delta`), `elo_expert` ♠ (banda Expert do ELO, ≥1924).
- **`grant_leaderboard_achievements(user_id, rank, rank_delta, elo)`**: concede (idempotente, UNIQUE user+key) e **notifica** cada novo selo, espelhando o padrão de `_check_and_grant_achievements`. Plugado no `GET /metrics/leaderboard` (best-effort, com base no `me.overall_rank`/`rank_delta`/`player_elo`).
- **Sem mudança de frontend**: os selos resolvem título/desc via `_ACH_META`, então aparecem sozinhos onde achievements são listados (`/player/achievements`) e no sino de notificações (tipo `achievement`, já genérico). Sem catálogo fixo de chaves no front.
- **Testes**: `test_database` (limiares top10/top3/#1, climber só com delta>0, elo_expert pela banda, idempotência, resolução via `_ACH_META`).

### feat(leaderboard): coach view — ranking dos próprios alunos (#15)
- O coach passa a ver um **ranking dos seus alunos** no CoachDashboard (aba Alunos, sidebar). Diferente do ranking público: ranqueia só os alunos **entre si**, com **nomes reais** e **sem filtro de opt-in** (o coach sempre vê os números do aluno — princípio do #15). Read-only, sem competição entre coaches. Alunos sem atividade no período entram como inelegíveis (com motivo), para o coach ver todos.
- **Backend**: `get_leaderboard_metrics` ganhou filtro opcional `user_ids` (restringe o cálculo a um conjunto); `repositories.get_coach_students_leaderboard(coach_id, period_days)` (alunos do coach via `get_students`, ranqueados entre si, inativos como inelegíveis); endpoint `GET /coach/students/leaderboard` (`@require_coach`).
- **Frontend**: card `CoachStudentsRanking` (react-query, `coachDashboard.studentsLeaderboard`) — rank + nome + ELO/mãos/torneios + score, e inelegíveis com motivo; i18n PT/EN/ES (`coachRankingTitle`/`coachRankingHint`/`coachRankingNoneEligible`).
- **Testes**: `test_database` (escopo — só os alunos do próprio coach, não-alunos fora, inativos como inelegíveis com nome real, coach sem alunos → vazio).

### feat(leaderboard): fundação de snapshots — histórico de posição + delta (#15)
- O ranking era sempre um retrato do instante (recomputado a cada request), sem memória do passado. Agora há **snapshots**: tabela `leaderboard_snapshots` (user_id, period_days, rank, score, dimensions_json, snapshot_at; migrations PG+SQLite + índice) gravando "fotografias" do ranking — a série temporal que alimenta o histórico e o **delta de posição** ("subiu/caiu X").
- **Modelo sob-demanda (substituto local do cron):** o `GET /metrics/leaderboard` grava um snapshot ~1/dia (guard `should_take_snapshot`, reusando o ranking já computado, best-effort) e injeta `me.rank_delta` (variação vs. snapshot anterior). `repositories`: `save_leaderboard_snapshot` (aceita `snapshot_at` p/ backfill/testes), `get_last_snapshot_at`, `take_leaderboard_snapshot`, `maybe_take_daily_snapshot`, `get_rank_delta`. `public_view` expõe `me.overall_rank` (posição entre todos os elegíveis — base estável do delta, existe mesmo opt-out).
- **Script p/ cron real:** `scripts/take_leaderboard_snapshot.py` (`--period`, `--force`) — ponto de entrada para Render cron / Windows Task Scheduler quando houver hosting.
- **Frontend:** card "Sua posição" passa a mostrar a **posição geral** + badge de **delta** (▲ subiu / ▼ caiu / —) e o status de visibilidade pública; i18n PT/EN/ES (`overallRank`/`publicYes`/`publicNo`/`rankDeltaSince`).
- **Pendente:** cron de verdade (scheduler/hosting) para gravar de forma confiável independente de acesso — hoje depende de alguém abrir a página. Registrado no backlog/memória.
- **Testes:** `test_database` (save/last/delta entre 2 batches, ignora sem-rank, isola por período). Validado end-to-end no DB local (script grava, guard pula 2ª no dia, delta correto).

### test(academy): seed fixa elimina flakiness do teste de variedade
- `test_academy_variety` media a variedade dos geradores com o `random` global — cujo estado, na suite completa, vinha "adiantado" por testes anteriores, fazendo o gerador mais apertado (`3bet_pot`, ~80% típico) oscilar abaixo do mínimo de 70% de vez em quando (falha intermitente). `setUp` agora faz `random.seed(20260530)` antes de cada teste → determinístico (3bet_pot fixo em 86%), imune à ordem da suite. Validado com 3 execuções idênticas.

### feat(leaderboard): fundação de opt-in/privacidade (#15)
- Antes, **todo** usuário elegível aparecia no ranking público pelo username, sem consentimento. Agora há 3 garantias de privacidade:
  - **Opt-in**: padrão é **não aparecer**; o aluno escolhe participar (`users.leaderboard_opt_in`, default false). A lista pública (`ranked`/`ineligible`) só inclui quem optou.
  - **Anonimato**: handle opcional (`users.leaderboard_handle`, máx 24 chars) substitui o username na vitrine pública; campos sensíveis (username cru, flag de opt-in) são removidos das linhas públicas.
  - **Sua posição sempre visível**: o endpoint retorna `me` — a linha do próprio usuário com nome real, score e rank público (ou `null` quando fora), mesmo sem opt-in. Coach segue vendo os números do aluno (visão pedagógica não passa pelo filtro).
- **Backend**: colunas em `users` (migrations PG+SQLite), `repositories.get_leaderboard_prefs`/`set_leaderboard_prefs` (+ `opt_in`/`handle` em `get_leaderboard_metrics`), função pura `leaderboard.public_view(result, viewer_id)` (filtro opt-in + anonimização + `me`, re-rank contíguo sem vazar ocultos), endpoints `GET`/`POST /player/leaderboard-prefs` e `me` no `/metrics/leaderboard`.
- **Handle único** (case-insensitive): `set_leaderboard_prefs` checa colisão com outro usuário antes de gravar e levanta `handle_taken` → endpoint responde **409**; índice único parcial `idx_users_lb_handle` (PG `LOWER(...)` / SQLite `COLLATE NOCASE`, ambos `WHERE handle IS NOT NULL`) como rede de segurança contra corrida. Evita dois alunos com o mesmo apelido (e impersonação por cópia de handle).
- **Frontend**: card "Sua participação" na `/leaderboard` (Switch opt-in + input de handle + salvar, i18n PT/EN/ES) e bloco "Sua posição" (rank público ou nudge "ative para aparecer"); linha do próprio usuário destacada na lista; erro "apelido já em uso" no 409.
- **Testes**: `test_leaderboard` (5 — filtro opt-out, anonimização por handle, `me` sempre presente com/sem opt-in, inelegível respeita opt-in) + `test_database` (round-trip + unicidade case-insensitive) + `test_api_endpoints` (GET default / POST / 409 de conflito). Type-check limpo.

### ux(rating/leaderboard): aproveitar a largura da tela (layout em colunas)
- As duas telas estavam presas em containers estreitos (`/rating` em `max-w-4xl` ~896px, `/leaderboard` em `max-w-3xl` ~768px) dentro de um `HudLayout` de 1440px — sobrava ~40–50% da largura vazia à direita.
- **`/rating`**: Hero (ELO/banda) em largura total; abaixo um grid 3 colunas — **principal (2/3)** com diagnóstico (por street + por stake) e as curvas de evolução **lado a lado** em telas largas (`xl:grid-cols-2`), e **sidebar (1/3)** com a escada de bandas (bloco alto e estreito, encaixe natural). Pior caso (usuário sem dados) degrada para coluna única `max-w-2xl`, sem buraco.
- **`/leaderboard`**: grid 3 colunas — **ranking (2/3)** como lista principal com as 4 barras de dimensão espalhando (`lg:grid-cols-4`), e **sidebar (1/3)** com a nota de pesos/elegibilidade e a lista de inelegíveis. Sem novas strings i18n; type-check limpo.
- **`/docs/rating`** (prosa): largura de leitura é proposital (linha longa demais prejudica legibilidade), então a faixa vazia à direita virou um **índice "Nesta página" fixo** (sticky TOC) com âncora para as 6 seções (`scroll-mt-24`), reusando os títulos já traduzidos — só a chave `rating.toc` nova nas 3 locales (PT/EN/ES). **Scroll-spy** (`IntersectionObserver`, `rootMargin` -96px/-60%) destaca a seção ativa conforme o usuário rola.

### feat(notifications): infra genérica de notificações in-app + trigger de banda do ELO (#19)
- **Substrato genérico** (não existia): tabela `notifications` (`type` + `payload` JSON language-agnostic + `link` + `read_at`; SQLite+Postgres). Repo: `create_notification` / `get_notifications` / `get_unread_notification_count` / `mark_notification_read` / `mark_all_notifications_read`. Endpoints `GET /player/notifications`, `/unread-count`, `POST /…/{id}/read`, `/read-all`.
- **Frontend**: `NotificationBell` no `HudHeader` — sino com badge de não-lidas, polling do contador (60s), dropdown (fecha ao clicar fora) que lista as notificações e marca todas como lidas ao abrir; clicar navega pro `link`. Texto renderizado por tipo via i18n (PT/EN/ES, namespace `common`).
- **Produtores plugados**: mudança de banda do ELO (`_recompute_user_elo` → `elo_band_up`/`elo_band_down`), **coach respondeu** (`send_coach_message` → `coach_message`/`student_message` p/ o destinatário), **conquista desbloqueada** (`_check_and_grant_achievements` → `achievement`, INSERT na mesma conexão p/ evitar lock) e **anotação de coach** (`upsert_annotation` → `coach_annotation` p/ o aluno). Gatilhos baseados em tempo (drill vencido, mudança de posição no ranking) ficam para quando houver scheduler. i18n + ícones por tipo no `NotificationBell`.
- **Testes** (`test_notifications.py`, suite database, 5): create/get/unread/mark-read/mark-all + isolamento por usuário + ordem + marcar só as próprias. Validado ao vivo (notificação criada → endpoint retorna → unread-count=1). database 41 / api 72: zero regressões; build OK.

### feat(leaderboard): integra o ELO como dimensão de aderência GTO (#19 ↔ #15)
- A dimensão **A (aderência GTO, 50%)** do ranking deixou de usar `aligned_pct` cru e passa a derivar do **ELO**: `A = expected_score(player_elo)` — probabilidade de bater o jogador médio (par 1500). Mais principiado (o ELO já pondera dificuldade por K-factor e é auto-calibrado). `get_leaderboard_metrics` computa o ELO do jogador a partir das mesmas decisões e expõe `player_elo`; `aligned_pct` segue para a evolução (B) e o desempate.
- **Frontend**: a linha de cada jogador na `/leaderboard` mostra o **ELO**; tipo `LeaderboardEntry.player_elo`.
- **Re-tune p/ skill-first**: como a curva logística do ELO comprime aderências altas (crusher: aligned 0.92 → ELO 1826 → dim GTO 87) e isso tinha derrubado o melhor jogador, os pesos foram de 50/25/15/10 para **60/20/10/10** (decisão de produto: ranking de habilidade) — o crusher (maior ELO) volta a #1 (77.4) à frente do grinder (76.4).
- **Testes** (`test_leaderboard`): dimensão A via ELO (par 1500 → 50; sobe com ELO), pesos, ordenação. Engine 250 / api 72: zero regressões.

### feat(elo): stake bracket — ELO segmentado por faixa de buy-in (Sprint 2 #19)
- **`elo_engine`**: `bracket_for(buy_in)` (micro ≤$5 / low $5–25 / mid $25–100 / high >$100) + `compute_player_elo_by_stake(user_id, decisions)` — segmenta o ELO por faixa, computando um rating independente por bracket (só faixas com ≥20 decisões com `gto_label`, anti-ruído). Aborda a limitação de justiça nº2 (jogar bem em micro ≠ em high-stakes).
- **`repositories.get_decisions_for_elo_by_stake`**: decisões com o `buy_in` do torneio. **Endpoint `/player/elo`** ganha `by_stake` (recomputado na leitura, como o decay; faixas com ELO+banda+nº). `by_street`/pico/histórico inalterados.
- **Frontend**: seção **"Por stake"** na `/rating` (mesmo padrão de "Por street"), mostrando só as faixas com dados. Tipo `EloResponse.by_stake` + i18n PT/EN/ES (labels das faixas com os cortes em $).
- **Testes** (`test_elo_engine`): `bracket_for` (cortes/limiares) + `compute_player_elo_by_stake` (agrupamento, mínimo por faixa, exclusão de sem-buy-in). Engine 249 / api 72: zero regressões. Validado ao vivo (user 13: só micro, 907 decs, ELO 1584 — pouca variedade de stake local, esperado).

### tune(leaderboard): pesos skill-first (aderência GTO domina)
- Recalibrados os pesos do ranking de **40/30/20/10** para **50/25/15/10** (GTO/evolução/engajamento/volume): a aderência GTO passa a ser metade do score, garantindo que o melhor jogador fique no topo sem ser ultrapassado por volume/engajamento. Resultado: crusher (GTO 92) sobe para #1 (77.6) à frente do grinder (76.8). Testes (`test_leaderboard`, via constantes) seguem verdes; pesos expostos no endpoint refletem na UI automaticamente.

### fix+feat(leaderboard): rota proxiada + item de menu (visibilidade)
- **Fix "Erro do servidor (HTTP 200)"**: o endpoint era `/leaderboard` (top-level), mas o proxy do Vite dev só encaminha prefixos específicos → o Vite servia o `index.html` (200 HTML) e o cliente quebrava no parse JSON. Movido para **`/metrics/leaderboard`** (prefixo já proxiado em dev) — funciona sem reiniciar o dev server e sem mexer no proxy. (Produção usa base URL absoluta, não afetada.)
- **Visibilidade**: adicionado item **"Ranking"** (ícone medalha) no nav principal (`HudHeader`), entre Torneios e Estudos — desktop + bottom nav mobile. `nav.leaderboard` nas 3 locales (`common`).

### feat(leaderboard): UI mínima do ranking de alunos (#15)
- **`pages/Leaderboard.tsx`** (nova, rota `/leaderboard`): consome `GET /leaderboard` (via `metrics.leaderboard()` em `api.ts`) e renderiza o ranking — rank (top-3 com tinta ouro/prata/bronze), nome, score, e **mini-barras das 4 dimensões** (GTO/evolução/engajamento/volume) — além da lista de **inelegíveis** com motivo e das notas de pesos/critério. Estados de loading/erro/vazio.
- **Entrada**: link "Ranking" (ícone troféu) no header da `/rating`. i18n nas 3 locales (`dashboard` → bloco `leaderboard.*`, 18 chaves). Termos de poker mantidos.
- Camada social (opt-in/privacidade, cron de snapshots, badges) segue deferida; esta é só a leitura do ranking. Build validado.

### fix(analyze): rejeita hand history sem identificador de torneio + seed de leaderboard
- **Bug**: um HH sem a linha `Tournament #…` (cash game / formato antigo) era salvo com `tournament_id` vazio → frontend gerava URLs `/tournament/` sem id, quebrando **abrir as mãos** e **excluir** (DELETE 500). `/analyze` agora **rejeita com 422** ("Apenas torneios MTT/SNG são suportados…") antes de persistir, evitando o registro quebrado.
- **`backend/scripts/seed_fake_leaderboard.py`** (novo, só SQLite local): cria 5 usuários fake com perfis distintos (crusher/improver/grinder/rookie/below-gate) — torneios + decisões com `gto_label` + drills — para exercitar o leaderboard (#15) localmente, onde só há 2 usuários reais. Idempotente (`--clean`).

### feat(leaderboard): fundação do ranking de alunos (#15, Sprint 1)
- **`leaklab/leaderboard.py`** (novo, motor PURO): rankeia por **aprendizado, não por $** — aderência GTO (40%) + evolução (30%) + engajamento (20%) + volume (10%). `score_player` normaliza cada dimensão (0..100) e `rank_leaderboard` separa elegíveis × inelegíveis, ordena (score desc, desempate determinístico) e atribui rank. **Guarda de elegibilidade** (anti micro-amostra/gaming): mín. 500 mãos, 10 torneios e 100 decisões com `gto_label`.
- **`repositories.get_leaderboard_metrics(period_days)`**: agrega por usuário (mãos, torneios, drills, decisões com cobertura GTO, aderência total e início×recente para a evolução) no período.
- **Endpoint `GET /leaderboard?period=90`**: monta métricas + ranqueia; retorna `ranked` + `ineligible` (com motivo) + pesos/limiares. UI pública, opt-in/privacidade e cron de snapshots **deferidos** (precisam de escala real de usuários).
- **Escopo consciente (local/solo)**: só a fundação backend — a parte social não é exercível com 2 usuários locais. Validado: ambos caem em `ineligible` (user 13 com 9 torneios falha o gate de 10 por 1; user 2 <500 mãos), confirmando a guarda; a lógica de ranking é coberta por testes sintéticos.
- **Testes** (`test_leaderboard.py`, suite engine, 7 casos): normalização, gates de elegibilidade, pesos por dimensão, direção da evolução, ordenação/rank + desempate, e limites do score. Engine 247 / api 72: zero regressões.

## [v0.164.0] — 2026-05-29 — feat(icm+elo): modelagem de ICM na mesa final + ELO (decay/testes/i18n) + parser 888/PartyPoker (desligado por flag)

> Destaques: **ICM** end-to-end (equity real na mesa final via PokerKit → `icm_tax` no scoring → feedback direcional → badge no Replayer → detector de leak "ICM Blindness" + backfill); **ELO** com testes do engine, decay por inatividade (Sprint 2 #19) e i18n completo (card + /rating + /docs/rating); suporte a **888poker/PartyPoker** (parser PartyGaming + extração financeira), **desligado por flag** `PARTYGAMING_ENABLED` (foco PS/GG); i18n do card de decisão do Replayer. Suíte completa: **691 testes, 0 falhas**.

### refactor(i18n): migra a /docs/rating para i18n (PT/EN/ES)
- **`DocsRating.tsx`** (página de teoria do ELO) era prosa PT hardcoded. Migrada para o namespace `docs` (bloco `rating.*`): eyebrow/título/descrição, 6 seções (texto via `dangerouslySetInnerHTML`, mesmo padrão do `Docs.tsx`), tabela de qualidade da decisão (Correta/Mista/Desvio…), tabela de bandas (nome + perfil) e as 4 notas. Componente reescrito data-driven (ícones de banda 🎯…👑 e ranges numéricos ficam no componente — neutros de idioma; só nomes/textos vêm do i18n).
- **Validado**: 13 chaves estáticas + 22 dinâmicas existem nas 3 locales; `vite build` sem erros. Conclui a localização de **toda a superfície de ELO** (card + /rating + /docs/rating).

### refactor(i18n): migra os cards de ELO para i18n (PT/EN/ES)
- **Débito removido**: `EloRatingCard.tsx` e `Rating.tsx` (`/rating`) eram PT hardcoded. Migrados para o namespace `dashboard` (bloco `elo.*`: **28 chaves** estáticas + sub-bloco `bands`), nas 3 locales — título, contagem de decisões, delta/decay, "próxima banda", eyebrow/título/descrição da página, "Por street", tabela de bandas ("você está aqui"), curvas de evolução, máx/mín do gráfico, e o `DeltaBadge`.
- **Nomes de banda localizados**: as 7 bandas (Iniciante…Elite) vêm do backend em PT; o frontend agora traduz via `t('elo.bands.<label>', { defaultValue: label })` (Beginner/Student/Solid… em EN; Principiante/Estudiante/Sólido… em ES). Ícone continua resolvido pelo label original (`LEVEL_ICONS`).
- **Termos de poker mantidos em inglês** (regra do projeto): Preflop/Flop/Turn/River.
- **Validado**: script confere que as 28 chaves `elo.*` + as 7 bandas existem nas 3 locales; sem PT visível remanescente; `vite build` sem erros de tipo. (Página `/docs/rating` — teoria — fica fora deste escopo de "cards".)

### feat(elo): decay por inatividade (Sprint 2 #19)
- **`elo_engine.apply_inactivity_decay(elo, weeks_inactive)`**: o ELO "esfria" enquanto o jogador não importa torneios. Padrões: **−2/semana**, **carência de 1 semana** (não pune logo), **cap total −20** (~10 semanas), **piso no INITIAL_ELO (1500)** — só esfria ratings acima do par; quem está no/abaixo dele não decai nem sobe. Retorna `(elo_ajustado, pts_decaídos)`.
- **Aplicado na leitura** (`GET /player/elo`): calcula semanas desde o último `imported_at` (novo repo `get_last_activity_at`) e decai **só o overall** (headline) — `by_street`, pico e histórico ficam crus. Snapshot persistido não muda; o decay é só de exibição (cresce com o tempo parado, sem precisar de upload). Response ganha `decay_applied` + `weeks_inactive`; `next_band` recalculado sobre o ELO decaído.
- **Frontend**: `EloRatingCard` e `/rating` mostram "−X inativo" (âmbar) com tooltip ("calibração por inatividade; importe um torneio para recuperar") quando `decay_applied > 0`. Tipo `EloResponse` atualizado.
- **Testes** (`test_elo_engine.py`): `test_inactivity_decay` (carência, −2/sem, cap, piso, no-decay no/abaixo do par). Validado end-to-end (user 13: 1.1 sem inativo → −0.2). Engine 240 / api 72: zero regressões; build OK.
- Demais itens do Sprint 2 (stake bracket, notificações, integração leaderboard #15) seguem pendentes/bloqueados; tooltip "+X pts/delta" já estava entregue.

### test(elo): cobertura do motor de ELO (lacuna fechada)
- **`backend/tests/test_elo_engine.py`** (novo, suite `engine`, 14 casos): o `elo_engine.py` era a única peça grande recente **sem testes**. Cobre `k_factor` (32/16/8), `expected_score` (par=0.5, ±400=10:1, simetria), `decision_score` (mapa GTO + **sem fallback heurístico**: None sem `gto_label`), `apply_decision` (direção/magnitude vs K), bandas (`band_full`/`next_band_for`, limiares 1570…2053, topo Elite sem próxima), `compute_player_elo_from_decisions` (sobe com acertos / cai com erros, exclusão de spots sem GTO, independência por street, streets inválidas puladas, ordenação por `created_at`), `compute_elo_curve` (1 ponto por torneio; torneios sem GTO omitidos) e `snapshot_to_dict`.
- Suite engine: **225 → 239 testes**, zero regressões.

### test: suite completa verde após as mudanças de ICM + desligar 888/Party
- Rodada a suite inteira (`tests/run_all_tests.py`): **676 testes, 0 falhas** (~342s). Por suite: engine 225, database 36, llm 43, api 72, regression 30, academy 12, gto 194, revalidation 64.
- Confirma que está tudo consistente: features de ICM (equity/scoring/feedback/badge/detector de leak), parser PartyGaming **desligado por flag** (testes `test_partygaming_*` e `test_icm` reativam a flag internamente e validam o código gateado), e nada regrediu no restante.

### chore(parser): desabilita detecção 888/PartyPoker (foco PS/GG) — reversível
- **Decisão de produto**: por ora o foco é **PokerStars/GGPoker**; 888/PartyPoker ficam para depois. O suporte **não foi removido** — apenas desligado por uma flag, reativável com 1 linha.
- **Flag `PARTYGAMING_ENABLED = False`** em `leaklab/parser.py`: gateia os dois `_detect_site` (parser + `app.py`, que lê a flag viva). Com ela desligada, arquivos 888/PartyPoker caem em `unknown` → "formato não suportado". Todo o parser PartyGaming (funções, regexes, extração financeira) e seus testes permanecem intactos.
- **Frontend** deixa de anunciar o que está desligado (mesma coerência do caso ACR/Winamax): `UploadZone` volta a listar só PokerStars/GGPoker; a tabela "Sites Suportados" da /docs idem; cópias de onboarding/landing/dashboard revertidas para "PokerStars/GGPoker" nas 3 locales. (`SiteLogo` mantém a entrada `partypoker` — inofensiva, pronta para reativar.)
- **Testes**: `test_partygaming_parser`, `test_partygaming_financials` e `test_icm` (usa uma fixture PartyPoker) reativam a flag no topo do arquivo — continuam validando o parser gateado. Suites regression (30) / engine (225) / api (72): zero regressões. Build do frontend OK.
- **ICM intacto**: equity, `icm_tax` no scoring, feedback, badge e detector de leak são site-agnósticos (rodam em PS/GG via `build_mtt_context`) e não foram tocados.
- **Reativar**: `PARTYGAMING_ENABLED = True` + readicionar 888/Party na vitrine do frontend (tudo no histórico do git).

### chore(backfill): popula icm_tax_pct nos torneios já importados
- **`backend/scripts/backfill_icm_tax.py`** (novo): recomputa o `icm_tax_pct` (contexto a nível de mão) a partir de `tournaments.raw_text` via `build_mtt_context` → `context_to_dict` — o mesmo caminho que o `/analyze` persiste — e atualiza todas as decisões da mão. Sem isso, decisões importadas antes da coluna existir ficavam NULL e o detector de leak ICM não as enxergava. Cross-backend (placeholders `?` auto-adaptados), **idempotente** (`WHERE icm_tax_pct IS NULL`), com `--dry-run` e `--limit`.
- Executado no banco local: 10 torneios / 858 mãos → **1122 decisões preenchidas**; 179 com `|tax| ≥ 8pp`, 38 spots de leak ICM (alto ICM + gamble errado). Re-run confirma idempotência (0 atualizações). End-to-end: o detector `icm_blindness` passou a surfacear (ex.: user 13 — high, 24 ocorrências / 52%).
- **Produção (Render/Postgres)**: rodar lá uma vez (`python scripts/backfill_icm_tax.py`) para popular os torneios já importados dos usuários — o script funciona em Postgres sem alteração.

### feat(cognitive): detector de leak ICM ("ICM Blindness") na mesa final
- **Novo padrão coachável** no Cognitive Failure Mapper: detecta o hábito de **arriscar a pilha em spots finos de alto ICM na mesa final** quando o ICM pede aperto. opp = decisão stack-risking (call/aposta/all-in) num spot com `|icm_tax| ≥ 8pp`; count = essa decisão foi erro. Frequência alta = cegueira a ICM. (`cognitive_mapper._icm_blindness`)
- **Persistência**: nova coluna `decisions.icm_tax_pct` (schema SQLite + Postgres + migrations). `save_decisions` grava `context.icmTaxPct` (já computado no pipeline via `calculate_icm`); `get_cognitive_failure_report` passa o campo ao detector. Decisões fora da mesa final têm `icm_tax_pct` NULL e são naturalmente ignoradas.
- **Narrativa** (`llm_explainer`): `icm_blindness` adicionado a `_PATTERN_NAMES_EN`, `_PATTERN_BEHAVIORS` (prompt do LLM) e aos templates de fallback `_PLAIN_PT/_EN/_ES` — explica em linguagem de jogador o prêmio de sobrevivência e dá uma dica acionável ("esse all-in ainda é +EV depois de descontar o prêmio de sobrevivência?").
- **Frontend**: o `CognitiveFailureCard` é data-driven — bastou `cognitiveFailure.patterns.icm_blindness` + `descriptions.icm_blindness` no `dashboard.json` (3 locales). Aparece automaticamente no card e alimenta o Mapa Cognitivo.
- **/docs**: nova linha "Cegueira a ICM" na tabela de Padrões Cognitivos (`Docs.tsx` + `cognitive.patterns.icm*` nas 3 locales).
- **Testes** (`test_icm.py`): caso cobrindo detecção (5 spots de alto ICM, 4 erros → severity high), exclusão de spots de baixo ICM/fora da FT (tax NULL), e ausência quando não há spots de alto ICM. Suites database (36) + engine (225) + api (72): zero regressões. Build do frontend validado.

### refactor(i18n): migra o card de decisão do Replayer para i18n (PT/EN/ES)
- **Débito removido**: `DecisionCard.tsx` e o `SidePanels` (`Replayer.tsx`) tinham dezenas de strings PT hardcoded. Migradas para o namespace `replayer` (bloco `card`, **91 chaves** nas 3 locales): rótulos de veredito (Correto/Misto/Desvio Leve/Crítico, Aceitável/Leak/Leak Grave/Sem dados, Erro), tooltips (Solver/Preflop/Engine, GTO label), source labels, `idealLabel` (GTO recomenda/Recomendado), footer (Você jogou, tooltips de Stack/M/ICM, ICM baixo/médio/alto), indicadores (SPR/Sizing/Equity/Necess. + descritores comprometido/médio/fundo/forte/favorável/marginal/fraca + audit Cenário/Mão), as narrativas `why` (interpolação via `{{eqPct}}`/`{{reqLabel}}`/…), o contexto de freq e as 6 mensagens de status GTO.
- **Termos de poker mantidos em inglês** (regra do projeto): Fold/Call/Raise/Allin/Check/Shove/Bet, RFI, SPR, Sizing, Equity, Solver, Engine, Preflop, Push/Fold, Leak, Spot N/A.
- **`DecisionCard`** passou a usar `useTranslation("replayer")`; no `SidePanels` o `t` já era prop. Padrão preservado (componente apresentacional recebe rótulos via prop quando aplicável).
- **Validado**: script confere que as 91 chaves `card.*` referenciadas existem nas 3 locales; nenhuma string PT visível remanescente (só comentários/log de dev); `vite build` sem erros de tipo.

### feat(replayer): badge ICM direcional na decisão (mesa final)
- **Badge visual** no footer do `DecisionCard` do Replayer, nos spots de **mesa final**, pelo sinal contínuo do ICM (`icm_tax` do `calculate_icm`): **ICM · risco alto** (pilha grande, equity ICM < fichas, âmbar), **ICM · sobrevivência** (short stack, equity > fichas, azul) ou **ICM · neutro** (stacks equilibrados). Substitui o chip heurístico "ICM alto/médio/baixo" quando disponível — é o sinal mais informativo ali. Tooltip explica a dinâmica. Fora da mesa final, mantém o chip heurístico.
- **Plumbing mínimo**: `_build_replay_data` já re-executa o engine ao vivo (`build_decision_inputs_for_hand`), cujo `context` já trazia `icmTaxPct`; bastou propagá-lo no `tech` → step (`icm_tax_pct`). `api.ts` (`ReplayStep`) e `Replayer.tsx` repassam ao `DecisionCard` via prop `icmBadge`.
- **i18n** nas 3 locales (`replayer.json` → bloco `icm`): rótulos e tooltips localizados injetados via prop (mantém o `DecisionCard` apresentacional). Qualitativo — sem número "duro" (payouts reais não vêm no HH). Build do frontend validado.

### feat(engine): feedback ICM direcional na decisão (mesa final)
- **`decision_engine_v11.build_interpretation`**: nos spots de **mesa final** (quando há `icmTaxPct`), o feedback da decisão agora explica a dinâmica ICM em linguagem de jogador, pelo **sinal do `icm_tax`**:
  - **pilha grande** (equity ICM < fração de fichas): "suas fichas valem menos que a fração no prize pool (retornos decrescentes); arriscar a stack exige mais equity — evite flips marginais, pressione os short stacks";
  - **pilha curta** (equity ICM > fração): "prêmio de sobrevivência — sobreviver tem valor real, seja seletivo ao arriscar a eliminação";
  - **equilibrado**: pressão ICM leve, mas todo all-in carrega risco de eliminação.
- **Qualitativo de propósito**: como os payouts reais não vêm no HH, a *forma* da pressão é confiável mas o valor não — então o texto **não expõe número "duro"** (% / $), alinhado à filosofia da /docs. Aparece só em mãos já marcadas como erro (onde explicar o porquê agrega).
- **Fallback preservado**: fora da mesa final (sem `icmTaxPct`), mantém o texto heurístico anterior (`icm_pressure` high/medium) — inalterado.
- **Testes** (`test_icm.py`): +1 caso cobrindo as 3 direções + o fallback. Suite engine (224): zero regressões.

### feat(engine): ICM tax contínuo no scoring (mesa final)
- **`decision_engine_v11.calc_pressure_adjustment`** ganhou param `icm_tax_pct`: na **mesa final** usa o sinal **contínuo** do ICM (`icmTaxPct`, vindo do `calculate_icm` via `mtt_context`) em vez do bucket grosseiro. `|icm_tax|` = intensidade da distorção ICM → eleva a **equity requerida** para arriscar a pilha (calls finos viram erro maior; folds apertados são perdoados — comportamento clássico de risk/survival premium). Escala suave `|tax|/100 × 0.06`, capada em **+0.02** e dentro do clamp global `[-0.03, 0.03]`.
- **Fallback preservado**: sem `icmTaxPct` (fora da mesa final), cai no heurístico anterior (`icm_pressure=="high"` em turn/river → +0.01) — **comportamento idêntico ao antigo**. Por isso a distribuição de labels do `test_tournament` (PokerStars 9-max, sem contexto FT) não muda.
- Ligado no scoring via `context.get("icmTaxPct")`. O caminho com `strategy_json` GTO (score por frequência) não é afetado — o ICM tax atua no caminho matemático (`adjustedRequiredEquity`).
- **Testes** (`test_icm.py`): +2 casos — escala contínua do `calc_pressure_adjustment` (tax 30→0.018, 8→0.0048, fallback heurístico) e efeito ponta-a-ponta (`evaluate_decision`: call fino na mesa final com ICM tax alto → `adjustedRequiredEquity` e score maiores). Suites engine (223) + regression (30): zero regressões.

### feat(mtt): ICM equity real na mesa final (calculate_icm vendorizado do PokerKit)
- **`backend/leaklab/icm.py`** (novo): `calculate_icm(payouts, chips)` **vendorizado verbatim** do PokerKit (MIT, `uoftcprg/pokerkit`) — ICM clássico por permutações, mantido idêntico ao upstream (com os doctests) para auditoria/atualização. Sem nova dependência (Python puro). Wrapper `hero_icm_equity()` devolve `equity_pct` (equity ICM do hero, % do prize pool), `chip_pct` (fração de fichas) e `tax_pct` (chip% − equity%: >0 em big stacks por retornos decrescentes, <0 em short stacks pelo prêmio de sobrevivência).
- **`mtt_context.py`**: na mesa final (2 ≤ jogadores ≤ 9) extrai os stacks de **todos** os assentos — cobrindo PokerStars/GGPoker (`(1500 in chips)`) **e** o dialeto PartyGaming (`( 500 )`/`( $826.51 )`/`( 86,425 )`) — e calcula a ICM equity do hero. Novos campos `icm_equity_pct` / `icm_chip_pct` / `icm_tax_pct` no `MTTContext` e no `context_to_dict` (`icmEquityPct`/`icmChipPct`/`icmTaxPct`). O `icm_pressure` heurístico foi **mantido intacto** (não-quebra; campos novos são extras). `active_players` ganhou fallback para contar assentos PartyGaming.
- **Aproximação documentada**: payouts reais não vêm no HH → usa uma **curva de pagamento padrão normalizada** (top-heavy, top-6 para limitar o custo combinatório de `permutations(P,K)`). Modela a *forma* da pressão ICM (stack grande vs. short), não o valor monetário exato.
- **Custo controlado**: só dispara com ≤ 9 jogadores; payouts limitados a 6 casas → `permutations` barato no hot path.
- **Testes** (`backend/tests/test_icm.py`, suite `engine`): 6 casos — bate com os doctests do PokerKit, direções de tax (igual/short/leader), guards, integração no `mtt_context` (mesa final PartyPoker STT: 4-way equilibrado → tax ≈ 0; HU chip leader → tax > 0) e campo grande (>9) sem ICM. Suites engine/regression: zero regressões.

### docs: nova seção "Sites Suportados & Importação" na /docs
- **`Docs.tsx`**: adicionada seção `import` como **primeira** da `/docs` (e no menu lateral) — antes não havia nenhuma seção sobre quais salas são suportadas nem como importar. Tabela com as **4 salas** (PokerStars, GGPoker, 888poker, PartyPoker), formatos (MTT · SNG · Cash/Spin) e onde obter o histórico de mãos. Nomes de sala/formatos hardcoded (neutros de idioma); só a coluna "onde obter" + textos via i18n.
- **Dica 888poker**: explica (em linguagem de usuário, sem expor lógica interna) que o resultado do torneio fica num arquivo *Tournament Summary* separado do HH — para registrar o prêmio, enviar HH + summary juntos.
- **i18n** nas 3 locales (PT/EN/ES): `nav.import` + bloco `import.*`. Build do frontend validado.

### feat(parser): extração financeira (buy-in/prêmio/data/nome) para 888poker e PartyPoker
- **`app.py._extract_financials`** ganhou parâmetro `site` e um branch PartyGaming: **888poker** lê buy-in de `Tournament #… $18.30 + $1.70` (buy-in + rake); **PartyPoker** lê `$X USD Buy-in`. Prêmio/place do hero via `Player <hero> finished in N place and received $X` (vencedor) / `…finished in N.` (bustou → prêmio 0); profit = prêmio − buy-in. O branch faz `return` cedo, sem tocar na lógica PokerStars/GGPoker.
- **`_extract_date`** passou a reconhecer os formatos novos: **888poker** `*** DD MM YYYY HH:MM:SS` e **PartyPoker** `Weekday, Month DD, … YYYY` (mês por nome, via `_MONTHS`).
- **`_extract_tournament_name`** ganhou branch **PartyPoker**: nome amigável da linha `Table <nome> (<trny>) Table #N` (ex.: "Powerfest #193 - Main Event $500,000 Gtd", "$1 Sit & Go Hero"); cai no heurístico SNG/MTT quando não há nome (e 888, que não traz nome explícito, usa o heurístico `SNG/MTT $buy-in`). Seat regex do heurístico relaxado de `(\S+)` para `(.+?)` (nomes com espaço).
- **Testes** (`backend/tests/test_partygaming_financials.py`, suite `api`): 5 casos contra as fixtures reais — 888 buy-in 20.00 + data; PartyPoker STT vencedor (buy-in 1 / prize 3 / place 1 / profit +2 / nome "Sit & Go"); PartyPoker MTT bustado (buy-in 215 / place 840 / profit −215 / nome "Powerfest"); cash sem financials; e **regressão garantindo que PokerStars não foi afetado**. Suites api: zero regressões.
- **Prêmio/place do 888 via Tournament Summary**: investigado o formato real — o **HH do 888 não contém linha de resultado** (só `** Summary **` por mão); o resultado fica num **arquivo `Tournament Summary` separado**:
  ```
  ***** Tournament Summary *****
  Tournament ID: 777
  Buy-In: $0.93 + $0.07
  Hero finished 1/3 and won $1.5
  ```
  `_extract_financials` (branch 888) agora lê esse bloco quando presente no conteúdo enviado (caso real: usuário sobe **HH + summary juntos**, como PokerTracker/HM importam — o `raw_full` então contém os dois): `<hero> finished P/T and won|lost X` → `place = P`; `won/lost X` tratado como **resultado líquido** (`won` → `prize = buy-in + X`, `profit = +X`; `lost` → `prize = 0`, `profit = −X` — "lost X" = perda do buy-in). Buy-in também lido do summary (`Buy-In: …`) como fallback.
  - **Moeda agnóstica**: regex de buy-in do 888 trocado de `\$…` fixo para `\D*?` antes do número — aceita `$`/`£`/`€` (ou símbolo perdido no encoding), já que o HH 888 não-USD usava `£0.93 + £0.07`.
  - Fixture real `tests/fixtures/pp888_tourney_summary.txt` (HH + summary, formato do `Mudr0x/DD-HHConverter`) + 2 testes (vencedor `won`, bustado `lost`, moeda não-USD). Parse + pipeline validados na fixture.
  - **Nota**: `won/lost` interpretado como líquido (bem sustentado pelo caso "lost X" = perde o buy-in). Upload só-summary (sem mãos) continua não-analisável — o resultado precisa vir junto do HH.

### feat(ui): expõe 888poker e PartyPoker na UI de upload
- **`UploadZone.tsx`**: badges de sites suportados agora refletem o que o parser realmente aceita — `PokerStars, GGPoker, 888poker, PartyPoker`. Removidos **ACR** e **Winamax**, que estavam anunciados mas não têm parser (upload falhava com "Nenhuma mão encontrada").
- **`SiteLogo.tsx`**: adicionada entrada `partypoker` (favicon + nome "PartyPoker") — torneios importados de PartyPoker passam a exibir logo/nome corretos na listagem; 888poker já tinha entrada. (O backend já persiste `site` via `_detect_site`, agora ciente dos dois.)
- **Copy i18n (PT/EN/ES)**: textos de onboarding (`upload.desc`/`upload.hint`), landing (`step1Desc`) e dashboard (`empty.desc`) atualizados de "PokerStars ou GGPoker" para incluir **888poker** e **PartyPoker**. Hint de onboarding nota que 888poker/PartyPoker salvam o histórico automaticamente na pasta do cliente.
- Build do frontend validado (vite, sem erros de tipo).

### feat(parser): suporte a 888poker e PartyPoker (dialeto PartyGaming)
- **Novo parser** para o formato compartilhado por 888poker e PartyPoker (herança Pacific/PartyGaming), bem diferente do PokerStars/GGPoker — quase toda linha muda: header (`***** [888poker] Hand History for Game N *****`), botão sem `#` (`Seat 4 is the button`), stacks em `( $600 )`/`( 86,425 )`, hero cards separados por vírgula (`[ 8c, Qs ]`), ações **sem `:`** (`Player raises [5,000]`), all-in próprio (`Player is all-In  [425]`), board por street com vírgula (`** Dealing Flop ** [ As, 5c, 9c ]`).
- **`backend/leaklab/parser.py`**: `_detect_site` reconhece `888poker` e `partypoker` (888 checado antes — seu header também contém "Hand History for Game"); `parse_hand_history` roteia os dois para `_parse_partygaming_hand`, que produz os mesmos `ParsedHand`/`ParsedAction` do parser legado — **nada a jusante muda** (pipeline/engine intactos). Trata as 5 variações de blinds (`$sb/$bb`, `Blinds(sb/bb)`, `Blinds-Antes(sb/bb -ante)`) e números com vírgula **ou espaço** como separador de milhar (`1 200` → 1200). `_extract_board` passou a aceitar cartas separadas por vírgula (acumula flop+turn+river, pois cada street só traz a carta nova). `app.py._detect_site` alinhado (888 antes de PartyPoker; `'888'` solto trocado por `'888poker'`).
- **Testes** (`backend/tests/test_partygaming_parser.py`, suite `regression`): 8 casos contra **hand histories reais** (fixtures em `tests/fixtures/`, extraídas de thlorenz/hhp) cobrindo cash + torneio dos dois sites — detecção de site, contagem de mãos, campos-chave, all-in, blinds em todos os formatos, board por vírgula, ruído (time bank / "has joined" / "finished" / posts) ignorado, e pipeline end-to-end sem crash nas 15 mãos.

### fix+feat(sparring): volta a aparecer mãos + foco em spots 100% GTO
- **Fix**: `get_sparring_hand` montava os steps com `r.get(...)` em `sqlite3.Row` (sem `.get()` em dev/SQLite) → `AttributeError` → 500 → nenhuma mão. Rows convertidas em dict.
- **Foco GTO**: seleção deixou de mirar nos *erros* do jogador (`gto_minor_deviation/gto_critical` dos últimos 90 dias, pool restrito) e passou a escolher mãos em que **toda decisão tem cobertura GTO** (`gto_action` preenchido), priorizando arcos multi-street (preflop→river) e randomizando. Assim todo spot do treino tem resposta e frequências confiáveis — as barras de **% por ação** (via `gto.decisionLookup`) já são exibidas no feedback. Validado: 14/15 mãos distintas, 100% cobertas, incl. postflop.
- **Avaliação pela distribuição GTO (postflop) — 3 níveis**: `/player/spots/drill/submit` (usado por Sparring **e** Ghost Table) avaliava só contra a ação **mais frequente** — marcava errado quem jogava uma ação **mista** legítima. Agora `_resolve_best_action_from_node` devolve as frequências do `strategy_json` e o grading classifica pela frequência da ação (definição embasada no princípio da indiferença — o solver só mistura ações de EV ~equivalente):
  - **acerto** = ação mais frequente **ou** freq ≥ 30% (linha mista co-ótima → selo "GTO Misto");
  - **desvio** = freq 10–30% (o solver joga, então **não é erro**; selo "Defensável");
  - **erro** = freq < 10%.
  Resposta ganha `gto_tier`, `mixed`, `gto_freq` e `gto_strategy` (mix completo). Selos `GtoMixedBadge` no veredito do Sparring e do Ghost Table; o mix (% por ação) é exibido sempre. (O Replayer não foi afetado — veredito dele já vinha do `gto_label` persistido, distribution-aware.)

### feat(academy): board strength variado + modo desafio + dicas
- **Variedade (anti-repetição)**: `generate_board_strength_question` agora sorteia cartas/boards sintéticos (variedade infinita) em vez de reciclar o histórico. Novos tipos além de `hand_classify`/`board_texture`: **made_vs_draw** (mão feita / draw / nada) e **identify_draw** (flush / straight / combo), reusando `_hand_bucket` + helpers de draw. Validado 400/400 questões distintas.
- **Modo desafio**: `AcademyQuizPage` ganha prop `challengeSize` — após N questões, tela final (acertos/N, precisão, XP) com **"Novo desafio"**; barra de stats vira progresso N/total. Board strength usa **20**; re-entrar inicia outras 20.
- **Dicas/ensino**: botão **"Ver dica"** revela o método (mental_tip) **antes** de responder; no feedback o método aparece **sempre** (não só quando erra). Vale para todos os exercícios. Cada exercício de **matemática** ganhou um bloco **"O que é"** (conceito) no card — os 6 tipos (pot odds, call/fold, EV, outs, equity, odds vs equity).

### feat(academy): exercícios GTO Preflop (Ranges GTO) — correção server-side
- **Novo módulo** na Academia que gera spots preflop a partir do `master_gw_ranges.json` (9-max) e pede a ação GTO (fold/call/raise/3-bet/4-bet). Cobre as condições: **open (RFI)**, **defesa vs open (call/3-bet)** e **vs 3-bet (4-bet/call)** — os 3 níveis (Iniciante/Intermediário/Avançado).
- **Correção 100% server-side** (`backend/leaklab/academy_gto_preflop.py` novo): a `/academy/gto-preflop/question` manda só o contexto do spot + opções; a `/academy/gto-preflop/submit` reavalia via `preflop_gto_ranges.analyze_preflop` e devolve o veredito (`correct`/`acceptable` = acerto), frequências GTO da mão e explicação. As ranges nunca vão pro cliente. Trata mixed strategy (call/3-bet ambos aceitáveis quando o solver mistura).
- **Endpoints** `GET /academy/gto-preflop/question?scenario={mixed|rfi|vs_rfi|vs_3bet}` e `POST /academy/gto-preflop/submit` (`app.py`); XP concedido no servidor (`academy_gto_preflop_correct`: RFI 20 / vs RFI 25 / vs 3-bet 30).
- **Frontend**: `AcademyGtoPreflop.tsx` renderiza a **mesa visual do Replayer** (`PokerTableV3`, o mesmo componente do Sparring) montando um `ReplayStep` 9-max sintético a partir do spot (hero + cartas, vilão/opener com a aposta, blinds, seats foldados). O jogador escolhe a ação no painel lateral (stats + contexto + ações/veredito) e recebe o veredito com as barras de frequência GTO. Botão **"Tabela de ranges"** abre o `RangePanel` do Replayer em overlay (grid 13×13 do spot, via `/preflop-ranges`) para consulta. Rota `/academy/gto-preflop`, tipos + client `gtoPreflop` em `api.ts`. **Dois níveis progressivos** no hub (antes *coming soon*): **Iniciante — Open (RFI)** (`?scenario=rfi`, só abertura) e **Avançado — Completo** (`?scenario=mixed`: open + defesa + vs 3-bet). i18n nas 3 locales.

### docs: revisão de acurácia das seções restantes da /docs
- Conferidas contra o backend as seções ainda não revisadas (`dna`, `leaks`, `causal_map`, `form`, `decisions`, `streets`, `positions`, `pressure`, `icm`, `bankroll`, `level`, `compare`, `gamification`): **todas factualmente corretas** e sem exposição de lógica interna.
- Validados os números: limiares de score `0.08 / 0.18 / 0.36` (= `decision_engine_v11._LABELS`), valores de XP `50 / 10 / 25 / 100` (= `repositories._XP_AMOUNTS`), e bandas/limiares de ELO `<1570 … ≥2053` (= `elo_engine.BANDS`) — tudo consistente com a /docs.
- **Fix**: docstring do módulo `elo_engine.py` listava bandas antigas (pré-unificação, `<1200 Iniciante / Casual / … / ≥2400 Elite`) que contradiziam a lista real `BANDS`. Atualizada para as 7 bandas atuais (Iniciante…Elite, 1570…2053).

### docs: revisão editorial da /docs — explicar conceitos sem expor a lógica interna
- **Princípio**: a documentação do usuário deve explicar **o que é** cada indicador/recurso e como interpretá-lo, sem revelar a engenharia interna ("não entregar o ouro"). Removidos de toda a `/docs`: nomes de variáveis/campos de código (`gto_label`, `facing_size`, `is_3bet_pot`, `action_quality`, `aligned_pct`, `error_rate`, `best_action`, `small_mistake`/`clear_mistake`), nomes de componentes (`GhostDrillCard`), comandos (`/sparring`), descrições de algoritmo/pipeline (pipeline de 3 fontes, regressão linear, janelas deslizantes, parsing de PKO, ciclagem do Sparring) e fórmulas/pesos proprietários (Leak ROI, efetividade do coach, threshold −2pp). **Mantidos** os números úteis ao usuário (intervalos de revisão, ELO por nível/banda, amostra mínima).
- **`gto_method`** reescrita nas 3 locales: removido o "pipeline de 3 fontes / solver nodes / reconciliação"; tabela de qualidade agora usa rótulos amigáveis (Correta/Aceitável/Leak/Leak grave) em vez dos enums crus. `Docs.tsx`: badges passam a usar chaves i18n (`correct_label`…`major_leak_label`).
- **Correção factual**: as Ranges GTO eram descritas como "MTT 8-max" (resíduo do JSON antigo RegLife) — corrigido para **9-max nativo** (`master_gw_ranges.json`, `MTTGeneralV2`, fonte da verdade desde v0.163.0).
- **`DocsRating.tsx`** (página /docs/rating): removida a fórmula ELO explícita, o mapeamento interno de score (`gto_correct`…), os exemplos de cálculo passo-a-passo e os K-factors exatos. Mantidos o conceito de ELO, a tabela de bandas (ELO por nível) e os insights de leitura do rating.
- **Revisão de acurácia**: confirmado que a doc não descreve features inexistentes e não há resíduo de "RegLife"/"GTO Wizard"/"8-max".
- **Menu lateral**: adicionado o **Rating ELO** ao menu lateral da `/docs` (`Docs.tsx`) como link de rota para `/docs/rating` (separador + ícone), com label `nav.rating` nas 3 locales. Antes só era acessível via link dentro da seção "Meu Nível".

### feat(elo): sistema de rating ELO para jogadores (backlog #19 — sprint 1)
- **Engine** (`backend/leaklab/elo_engine.py` novo): fórmula ELO clássica adaptada pra poker (cada decisão = partida vs solver ELO 3000). Score `S` derivado de `gto_label` (correct=1.0, mixed=0.7, minor=0.4, critical=0.0) com fallback heurístico (standard/marginal=0.5). K-factor dinâmico (32 <100 / 16 / 8). Bandas: Iniciante / Casual / Em desenvolvimento / Sólido / Avançado / Elite / Master / Grandmaster. ELO calculado overall + por street.
- **Schema** (`backend/database/schema.py`): nova tabela `player_elo_history` (SQLite + Postgres) com snapshots por user (`elo_overall + elo_preflop/flop/turn/river + counts + calculated_at`). Snapshot novo a cada upload — gera série temporal pro gráfico.
- **Repo** (`backend/database/repositories.py`): `insert_elo_snapshot`, `get_latest_elo`, `get_elo_history`, `get_decisions_for_elo`.
- **Endpoint** `GET /player/elo`: retorna ELO atual + by_street + bandas + histórico + delta 7d. Lazy compute na 1ª chamada se sem snapshot.
- **Trigger automático**: thread `_recompute_user_elo` no `/analyze` após upload — recalcula processando todas as decisions do user em ordem cronológica.
- **Frontend**:
  - `EloRatingCard.tsx` no Index — ELO atual + banda + delta 7d + link pra /rating
  - `Rating.tsx` (`/rating`) — hero card + breakdown por street + tabela de bandas (destacando atual) + sparkline de evolução
  - `DocsRating.tsx` (`/docs/rating`) — teoria ELO, fórmula, exemplo de cálculo step-by-step, mapeamento `gto_label → S`, tabela de bandas com perfis, notas (K dinâmico, recalculo automático)
- Validado local com user 13 (1033 decisions): overall ELO 3060 (Grandmaster), preflop 3126 / flop 2756 / turn 2632 / river 1941 — refletindo cobertura GTO maior em preflop.

### feat(gto): warm-up automático do cache GW após upload de torneio
- `backend/api/app.py`: nova função `_warmup_gw_multiway(hands, hero)` disparada em background thread após `save_tournament` no `/analyze`. Enumera decisões preflop do hero em todas as mãos, encoda `preflop_actions`, classifica scenario via `classify_multiway`, **filtra só os multiway** (scenarios `multiway/squeeze/vs_squeeze/5bet_or_higher` — onde `lookup_gto` HU local não tem cobertura), dedupa por (gametype, depth bucket 10bb, preflop_actions), e chama `lookup_for_hand_decision()` pra popular `gw_raw_cache`.
- Serializado via `_page_fetch_lock` no server remoto — não satura GW; tipicamente 30-80 spots únicos por torneio de 150 mãos, 15-40min em background.
- Próximo abrir do Replayer em qualquer dessas mãos já bate cache (<50ms) em vez de cache miss async.

### feat(replayer): mesa deslocada 25px ↓ + agregados de ação no RFI
- `frontend/src/components/hud/PokerTableV3.tsx`: `CY` (centro vertical do layout) `315 → 340`; ellipses do feltro e texto LEAKLAB acompanham (cy 315→340, cy 328→353, text y 326→351). Cartas de seats do topo (UTG/UTG+1) não são mais cortadas pela borda superior; folga inferior preservada.
- `backend/leaklab/preflop_gto_ranges.py`: cenário RFI agora expõe `raise_pct/allin_pct/call_pct/fold_pct` agregados no response do `analyze_preflop`. Frontend usa esses quando `hand_freq` específico é null (caso comum em spots sem hand_freqs do GW v3). Antes, barra do Decision Card mostrava só `Fold 78%` pq `raise_pct` não existia — agora mostra `Fold 78% + Raise 22%`.

### feat(replayer): barras de frequência GTO independentes por ação + cor fold amarela
- `frontend/src/pages/Replayer.tsx`: barra única stacked (fold/call/raise/allin coladas) substituída por uma barra horizontal independente por ação, ordenada por frequência decrescente. Cada linha mostra: bar + label colorido + %.
- `frontend/src/lib/actionColors.ts`: cor do `fold` alterada de `zinc-500` (cinza) para `yellow-300` (amarelo claro) — usuário achou o cinza pesado demais. Atualizada também a versão Tailwind (`ACTION_TW.fold`).

### fix(replayer): posicionamento de fichas de aposta e dealer button
- `frontend/src/components/hud/PokerTableV3.tsx`: bets de seats adjacentes ao hero (caso `isAdjT2`) estavam em `t2=0.72` (quase no pot) — ajustado pra `0.38` (próximo ao default 0.36), trazendo fichas pra perto do pod do jogador.
- Sign do `perpOff` em seats `bottom` adjacentes ao hero estava invertido: empurrava fichas EM DIREÇÃO ao hero (centralizando-as) em vez de afastar. Corrigido — agora seats à esquerda do hero se deslocam pra esquerda, e à direita pra direita. Magnitude também reduzida (32→24px).
- Dealer button reposicionado: `t=0.22/0.28/0.20` (próximo ao pod) com `perpSign=-1` consistente e ajuste vertical de `-12px` pra não sobrepor cartas/fichas de aposta.

### fix(gto): `/replay` não bloqueia em cache miss do multiway (warmup async)
- Bug: wiring inicial fazia `/replay` esperar ~30s por decisão hero preflop quando cache miss → mãos com 2+ decisões = 60-120s = browser timeout.
- Fix: novo param `cache_only=True` em `query_spot_raw()` e `lookup_for_hand_decision()` — no cache miss, retorna `None` imediatamente sem chamar o server GW.
- `/replay` usa `cache_only=True` no hot path. Cache miss → dispara background thread que faz o lookup completo (com cache write) pra popular pra próxima visita.
- Latência: cache hit 220ms (com `gto_strategy` + `hero_freq` populados); cache miss 80ms (sem GTO multiway no response — vem na próxima visita).

### feat(gto): wiring `/replay/<t>/<h>` — fallback multiway via `/gw-spot` (step 5)
- `backend/api/app.py:3548`: após `lookup_gto` (HU) falhar em fornecer estratégia preflop, fallback automático pra `lookup_for_hand_decision()` quando: (a) `gto_strategy is None`, (b) `action.street == 'preflop'`, (c) `action.player == hero`, (d) sem spot_mismatch.
- Quando o multiway lookup retorna sucesso, popula `gto_strategy` E adiciona `hero_freq` em cada entry da strategy (frequência específica da mão do hero — extraída de `hand_freqs[hand_type]`). Frontend pode usar pra mostrar Decision Card com a freq da mão jogada.
- Requer envs `GTO_WIZARD_ENABLED=true`, `GTO_SOLVER_URL`, `GTO_SOLVER_API_KEY` no backend. Sem isso, o fallback retorna None silenciosamente — comportamento atual preservado.
- Cache `gw_raw_cache` mata 99% da latência: primeira chamada ~30s (GW), repetidas ~12ms.

### feat(gto): cache `gw_raw_cache` + `lookup_for_hand_decision()` (step 4)
- `backend/database/schema.py`: nova tabela `gw_raw_cache` (SQLite + Postgres) com `cache_key` (hash de gametype/depth/preflop_actions/board), `payload_json`, e metadata.
- `backend/database/repositories.py`: `get_gw_raw_cache(key)` e `upsert_gw_raw_cache(...)` — UPSERT cross-backend.
- `backend/leaklab/gto_wizard_client.py`:
  - `_cache_key_for_spot(...)`: hash SHA256 truncado (24 chars) determinístico, independente de `hero_hand` (response cobre todos 169 hand_types).
  - `query_spot_raw(...)` agora consulta cache antes de chamar server; após sucesso, grava sob a chave ORIGINAL E a chave pós-snap (próximas chamadas com sizings imperfeitos batem cache direto).
  - `lookup_for_hand_decision(hand, decision_index, depth_bb)`: wrapper de conveniência que combina `encode_preflop_actions` + `classify_multiway` + `query_spot_raw`. Retorna o mesmo dict com `scenario` adicionado.
- **Validado end-to-end**: 1ª chamada 31.4s (encoder + snap + GW), 2ª chamada 0.012s (cache hit) — **2600x speedup**. Resultados corretos: 75o=100% fold, AA=96.5% raise.

### feat(gto): validação end-to-end completa (parser → encoder → GW)
- Pipeline completo testado com `teste_torneio_carma.txt` hand #100000002 (BB hero vs 4-way squeeze):
  - Encoder gerou `R2.0-F-F-C-F-C-R0.0` (com sizings errados — bug ante + bug parser "raises 0 to 0")
  - Server snappou pra `R2.1-F-F-C-F-C-R11.55` (sizings válidos descobertos via `spot-solution` do estado anterior)
  - GW retornou 200 com hero=BB, 169 hand_freqs corretos, 75o = 100% fold
- O snap é robusto a TANTO o sizing ante-adjusted QUANTO valores absurdos (R0.0): consulta árvore de ações válidas no estado anterior e snappa pro mais próximo. Bugs do encoder/parser ficam absorvidos pelo retry.

### feat(gto): server snappa raise sizings preflop pro válido mais próximo
- `backend/gto_bot/solver_api/server.py`: nova função `_snap_preflop_raise_sizes(api_params)` consulta `/v4/game-points/next-actions/` step-by-step pra cada token `R{x.y}` no `preflop_actions`, descobre os sizings que GW aceita pro estado atual, e snappea pro mais próximo. Após receber 204/404 na 1ª tentativa do `/gw-spot`, retry automático com versão snapped.
- Endereça o caso real validado empiricamente: GW MTTGeneral_8m 100bb só aceita `R2.1` pra open; encoder do client emite `R2.0` (sem ante-adjustment) → 404 → snap detecta R2.1 nos sizings válidos → retry → 200.
- Param `snap_raises` (default true) no payload do `/gw-spot` controla o comportamento.
- Trade-off: cache miss + snap = 2 navegações Playwright (~18s). Cache hit (futuro step 4) elimina.

### feat(gto): encoder ParsedHand → preflop_actions GW + classifier
- `backend/leaklab/gw_action_encoder.py` (novo): `encode_preflop_actions(hand, stop_index)` converte ações preflop em string GW (`R2.1-F-F-C-F-C-R11.55`). Inclui `find_hero_preflop_decisions()`, `num_seated_players()`, `gw_gametype_for()`, e `classify_multiway()` (scenarios: rfi/vs_rfi/vs_3bet/vs_4bet/squeeze/vs_squeeze/multiway/5bet_or_higher).
- Validado contra hand #100000002 do `teste_torneio_carma.txt`: scenario classificado como `vs_squeeze` com `is_multiway_with_callers=True` (BB hero facing 4-way 3bet squeeze).
- **Limitações conhecidas (não bloqueadoras pro encoder):**
  - Sizing ante-adjusted: GW codifica raise como R2.1 quando hand history tem `raises 2 to 2` (ante de 0.13×8). Encoder emite valor cru `R2.0`. Pode causar 404 → consumidor deve fazer snap.
  - Bug parser PokerStars: `raises 0 to 0` em formatos com ante aparece com `amount=0` (squeeze real perdido). Fix deve ser no parser, não no encoder.

### feat(gto): cliente `query_spot_raw()` + extração de `hand_freqs` pelo servidor
- `backend/leaklab/gto_wizard_client.py`: nova função `query_spot_raw()` que chama `POST /gw-spot`. Aceita `preflop_actions` encoded (formato GW) + street actions + board. Retorna `strategy` normalizada (action_codes → fold/call/raise/allin/bet) e `hand_freqs` por hand_type (ex `{"AJo": {"fold": 0.45, "raise": 0.55}}`).
- Helper `_normalize_gw_action(code, action_type)` converte `R2.1`, `RAI`, `F`, `C` etc para o vocabulário do engine, preservando `betsize_bb` quando aplicável.
- `backend/gto_bot/solver_api/server.py`: response de `/gw-spot` agora inclui `hero_position` + `hero_hand_freqs` extraídos de `players_info[hero].simple_hand_counters` (keyed por hand_type, evita o problema do array `strategy[169]` com ordem não-trivial). Param `include_hand_freqs` (default true).

### refactor(gto-bot): `/gw-spot` executa fetch in-page via CDP (auth-safe)
- `backend/gto_bot/solver_api/server.py`: nova helper `_fetch_via_page(api_path, params)` que abre conexão Playwright→CDP, encontra aba aberta do GW e roda `fetch()` dentro do contexto da página via `page.evaluate()`. Browser anexa `google-anal-id` automaticamente (signature ECDSA válida).
- `query_gto_wizard_raw` (`/gw-spot`) refatorado pra usar `_fetch_via_page` em vez de `requests.Session` + headers replay. Replay externo era rejeitado pelo GW (401) porque assinatura do token está atrelada ao TLS/JS context do browser.
- Trade-off: ~500ms-1s de overhead por request (abrir/fechar conexão Playwright); serializado via lock pra evitar race no sync_playwright.

### fix(gto-bot): captura aceita token `google-anal-id` (GW novo)
- `backend/gto_bot/solver_api/server.py`: `_capture_headers_via_cdp` agora aceita header `google-anal-id` como evidência de auth válida, não só `authorization`. GW migrou de Bearer JWT pra token ECDSA assinado client-side; antes, refresh sempre falhava com "Chrome não respondeu" mesmo com Chrome logado.

### feat(gto): endpoint `/gw-spot` para spots multiway (passthrough cru pro GW)
- `backend/gto_bot/solver_api/server.py`: nova função `query_gto_wizard_raw()` + rota `POST /gw-spot`. Cliente envia `preflop_actions` já encoded (formato GW: `R2.1-F-F-C-F-C-R11.55`) e servidor navega o Chrome pra URL do app GW correspondente, interceptando a response da API que o próprio GW dispara (com auth ECDSA do interceptor JS). Suporta multiway, squeeze e cold-callers — qualquer cenário que GW resolva.
- Response inclui `action_solutions[].strategy[169]` cru (frequência por hand_type 13×13) — permite extrair `hand_freqs` por mão específica no cliente.
- **Validado end-to-end** com mão multiway real (UTG+1 R2.1, HJ call, BTN call, SB R11.55, BB to act): retornou FOLD 96.66%, RAISE 2.57% (to 25.41bb), ALLIN 0.77%, com arrays strategy[169] preenchidos (FOLD: 165 mãos ativas, RAISE: 19, ALLIN: 12). Latência ~9s/request (overhead de navegar página + interceptar).

### fix(replayer): rota `/replay/<t>/<h>` não bloqueia mais em I/O remoto GTO offline
- `backend/leaklab/gto_solver.py`: novo parâmetro `block_remote=True` em `lookup_gto`. Quando `False`, pula GTO Wizard e solver remoto, retornando apenas dados do DB local.
- `backend/api/app.py`: chamada inline em `/replay/<t>/<h>` passa `block_remote=False` — frontend responde em <1s mesmo com servidor GTO offline (antes ficava 2min em "Carregando mão..." aguardando timeout).

### fix(frontend): silencia Vercel Analytics em dev
- `frontend/src/main.tsx`: `<Analytics />` só renderiza em produção (`import.meta.env.PROD`). Elimina 404s espúrios em `/_vercel/insights/view` durante `npm run dev`.

---

## [v0.163.0] — 2026-05-25 — feat(preflop): integração GTO Wizard v3 (900 spots 9-max nativo)

### Why
JSON RegLife v2.3.0 tinha bug sistemático de extração de pixels (cor azul-petróleo classificada como fold). Pares premium QQ-77 frequentemente apareciam em `fold_hands` em spots vs_RFI, gerando feedback errado para alunos. Substituído por JSON master coletado direto da API GTO Wizard via HARs navegando o tree do app — 900 spots GTO-quality em 9-max nativo cobrindo RFI + vs_RFI + vs_3bet + vs_4bet em 9 stacks (10-100bb).

### Coleta
- **RFI**: 72/72 (9 buckets × 8 posições openers)
- **vs_RFI**: 324/324 (9 buckets × 36 pairs opener/defender)
- **vs_3bet**: 324/324 (9 buckets × 36 pairs opener/3-bettor)
- **vs_4bet**: 180/180 (5 buckets 30-100bb × 36 pairs; ≤20bb não tem 4-bet sized)
- **Total: 900 spots GTO-Wizard puros**

### Mudanças no engine
- `preflop_gto_ranges.py:_POS_NORM`: agora 9-max nativo (UTG, UTG+1, UTG+2, LJ, HJ, CO, BTN, SB, BB). Mapeia 8-max → 9-max (MP → UTG+1; MP2 → UTG+2). Legacy UTG1 → UTG+1.
- `preflop_gto_ranges.py:analyze_preflop()` RFI: adapter detecta formato v3 (campo `open_pct` presente) vs v2 (`pct`). v3 usa `raise_hands`+`allin_hands` separados; recomendação derivada via `in_raise`/`in_allin`. Compat v2 preservada como fallback.
- `preflop_gto_ranges.py` vs_RFI: aliases simplificados — `UTG+1` agora é nativo (não precisa mais converter pra MP).
- **Workaround Backlog #17 removido** — pares premium QQ-77 vinham bugados no RegLife; JSON v3 tem dados corretos.

### Arquivos novos
- `backend/scripts/parse_gw_har.py` — parser HARs do GW (9-max nativo, categorização rfi/vs_rfi/vs_3bet/vs_4bet)
- `backend/scripts/fetch_gw_passive.py` — captura passiva via CDP (fallback)
- `backend/scripts/fetch_gw_rfi.py` — coleta RFI via Playwright (deprecated em favor de HAR manual)
- `backend/docs/ranges_gto/master_gw_ranges.json` — JSON master 9-max (fonte da verdade)
- `backend/docs/ranges_gto/{vs_rfi,vs_3bet,4bet}/*.har` — HARs fonte (200+ arquivos, organizados por opener)
- `backend/docs/leaklab_gto_ranges.bak.pre_gw_v3.json` — backup do JSON RegLife v2.3.0

### Reprocessamento
- 1118 decisions verificadas, **208 atualizadas** com novo JSON v3
- 208 mudanças adicionais via reconcile_label

### Testes
- Suite engine: 194/196 OK
  - `vs_rfi_88_call_in_range`: fixture esperava False, v3 mostra True (correto — RegLife antigo tinha bug)
  - `test_postflop_error_rate_reduced`: pré-existente (não relacionado)
- `test_engine_internal_consistency`: **91 violations residuais** (era 24 com v2). Causa: v3 tem ranges mais accurate, expondo decisions antes mascaradas pelo RegLife bugado. Follow-up: revisar `_reconcile_label` para promover label quando best_action diverge significativamente.

### Próximas categorias (não cobertas ainda)
- **Squeeze** (multiway 3-way) — ~450 spots
- **vs Squeeze** — ~450 spots
- 5-bet+ — ~50 spots

### Files
- **Changed**: `backend/leaklab/preflop_gto_ranges.py` (POS_NORM, RFI adapter, vs_RFI aliases, workaround removido)
- **Changed**: `backend/docs/leaklab_gto_ranges.json` (← `master_gw_ranges.json`)
- **New**: `backend/scripts/parse_gw_har.py`, `backend/scripts/fetch_gw_passive.py`, `backend/scripts/fetch_gw_rfi.py`
- **New**: `backend/docs/ranges_gto/` (master + HARs fonte)
- **New**: `backend/docs/leaklab_gto_ranges.bak.pre_gw_v3.json` (backup)

---

## [v0.162.0] — 2026-05-23 — fix(preflop): workaround para pares premium QQ-77 em vs_RFI

### Why
Descoberto que JSON `leaklab_gto_ranges.json` v2.3.0 tem bug sistemático de extração: cor azul-petróleo RGB(59,128,155) do PDF RegLife — que representa **call** — foi classificada erroneamente como **fold** pelo `extract_vsrfi_ranges.py`. Resultado: pares premium (QQ, JJ, TT, 99, 88, 77) e mãos como QJo apareciam em `fold_hands` em vários spots vs_RFI. Aluno com QQ defendendo open recebia "leak" se desse call — feedback completamente errado em centenas de mãos do banco.

### Fix temporário (Backlog #17 mantém solução definitiva)
- `backend/leaklab/preflop_gto_ranges.py:269-276`: guard em `analyze_preflop` para cenário `vs_rfi`. Quando hero tem QQ-77 e o lookup do JSON retorna `in_range=False`, força `in_range=True` com recomendação `jam` (stack ≤20bb) ou `call` (>20bb). Não aplica em PF zone (≤12bb usa lógica push/fold separada).
- Não corrige o JSON nem o Range Panel do frontend (esse continua mostrando QQ azul = fold no grid)
- Resolve impacto direto no Decision Card (verdict + recomendação)

### Validação
- Reprocessamento: 1118 decisions, **80 atualizadas** + 80 reconcile
- Test consistency: 24 → 25 violações (categorias residuais não cobertas pelo workaround)
- Suite engine: 33/33 OK

### Tentativa anterior (rejeitada)
Tentei re-extrair via pixel (opção C do plano). Descobri 2 bugs aninhados:
1. Cor azul-petróleo classificada como fold (corrigi)
2. `_detect_y_bounds` captura área errada em PNGs 100bb (apenas 1.7% pixels brancos vs 45-55% nos 17-20bb) — layout do PDF varia por stack

Re-extração pixel exigiria 1-2 dias de calibração. JSON e script restaurados via backup `leaklab_gto_ranges.bak.v2.3.0.json`. Solução definitiva (D) — validação programática contra GTO Wizard — documentada em Backlog #17.

### Files
- **Changed**: `backend/leaklab/preflop_gto_ranges.py` (+11 linhas guard)
- **New**: `backend/docs/leaklab_gto_ranges.bak.v2.3.0.json` (backup pré-tentativa)

---

## [v0.161.0] — 2026-05-23 — feat(replayer): DecisionCard template único + coerência verdict×math

### Why
Replayer mostrava 6+ variações de card (preflop, postflop math, push/fold banner, sem-GTO banner, spot-incompatível banner, conflito footnote) com layouts diferentes. Pior: inconsistências semânticas exibidas (verdict "Correto" + frase "Call lucrativo" + math card "Fold −EV") porque math card usava `pot_odds_equity` bruto enquanto engine classifica com `adjusted_required_equity` (pot_odds + realization_adj + pressure_adj).

### Fix 1 — DecisionCard template único (5 slots fixos)
Novo `frontend/src/components/replayer/DecisionCard.tsx`: template aplicado a TODOS os spots.
- **Slot 1** Verdict bar: icon + label + source badge + toggle 👁
- **Slot 2** Action comparison: Você jogou (+ Recomendado quando diverge)
- **Slot 3** Evidence: 1 widget primário (range bar | math card | solver bars | equity bar)
- **Slot 4** Indicators: chips/rows secundários (audit, SPR, Sizing) — sempre visíveis
- **Slot 5** Context footer: Stack · M · ICM

Toggle 👁: revela frase Why + pro_notes. Profissional vê só dados; iniciante ativa explicação.

Source badges com cor distinta: `Solver` (roxo), `Preflop` (foreground), `Engine` (muted), `Heurística` (cinza), `Push/Fold` (amber), `Spot N/A` (orange).

### Fix 2 — Banners separados eliminados (–193 linhas líquidas)
- Push/Fold Zone → source badge amber + frase no Why
- Sem cobertura GTO → source badge cinza + frase no Why
- Spot incompatível → source badge orange + frase no Why
- Conflito Engine vs GTO footnote → frase no Why quando diverge

### Fix 3 — Duplicação visual removida
- `✓` extra na coluna "Você jogou" (já existe `✓ Correto` no banner)
- "Fold 85% · Raise 15%" abaixo das barras do GtoStrategyPanel
- Audit trail movido para toggle (era sempre visível, redundante)

### Fix 4 — Tipografia consolidada (5 tamanhos → 3 níveis 10/11/13)
Opacidades agressivas (`/30`, `/40`, `/45`) substituídas por `text-muted-foreground`. Resolve violação WCAG SC 1.4.4 (texto em `[8px] opacity-40`).

### Fix 5 — Frase Why descreve a ação tomada, não a alternativa
Antes: `"Call lucrativo — equity 37% supera pot odds 33%"` aparecia mesmo quando hero foldou. Agora: para fold mostra `"Fold correto"`, `"Fold defensável (break-even)"` ou `"Fold deixou EV na mesa"` conforme margem.

### Fix 6 — adjusted_required_equity exposto ao frontend (coerência verdict × math)
- `backend/api/app.py`: endpoint do Replayer agora retorna `thresholds` do engine e popula `tech.adjusted_required_equity` no step
- `frontend/src/lib/api.ts`: novo campo `adjusted_required_equity?: number`
- `frontend/src/pages/Replayer.tsx`: `req = step.adjusted_required_equity ?? poRaw` — math card e frase Why usam o mesmo critério que o engine usa para classificar
- Math card label vira `"Equity Necessária"` (tooltip com pot odds bruto) quando há ajuste relevante
- Caso resolvido: fold com SPR 0.6, pot_odds=33%, eq=37%, adjusted=37% → verdict `Correto`, badge `Fold +EV`, frase `"Fold defensável — break-even"` — tudo coerente

### Fix 7 — Backend guard: fold com equity ≥ pot_odds + 3pp promove para small_mistake
`decision_engine_v11.py:apply_anti_rules`: nova regra postflop. Fold com `equity − pot_odds ≥ 3pp` + `label='standard'` é promovido para `small_mistake` + `best_action='call'`. Test unit `test_anti_fold_plus_ev_promotes_standard` cobre 4 casos. Reprocessamento aplicou em **89 decisions** + 76 mudanças via reconcile.

### Fix 8 — Test consistency interna
Novo `tests/test_engine_internal_consistency.py`: invariantes label/best_action/gto_label. Sessão: **85 → 24 violações (−72%)**. Resíduo é preflop sem pot_odds (backlog).

### Files
- **New**: `frontend/src/components/replayer/DecisionCard.tsx`, `backend/scripts/reanalyze_all_labels.py`, `backend/tests/test_engine_internal_consistency.py`
- **Changed**: `frontend/src/pages/Replayer.tsx` (–193 linhas líquidas), `frontend/src/components/replayer/GtoStrategyPanel.tsx`, `frontend/src/lib/api.ts`, `backend/api/app.py`, `backend/leaklab/decision_engine_v11.py`, `backend/tests/test_decision_engine.py`

---

## [v0.160.0] — 2026-05-23 — fix(engine): revalidação reduz majors 32 → 2 (-94%)

### Why
Relatório `revalidation_run_1` detectou 32 majors (2.9% das 1122 decisões). Em 4 padrões:
- 19 casos `engine='bet'` vs `oracle='raise'` em preflop (60%)
- 5 casos postflop jam não enumerado (16%)
- 5 casos multiway iso engine recomendava raise quando oracle diz call
- 3 casos SB push/fold engine sugeria call

### Fix 1 — bet↔raise preflop normalize (cobre 19/32)
- `decision_engine_v11.py`: guard `raise → bet` quando `facingSize=0` só dispara em **postflop**. Preflop RFI continua sendo `raise` (existe BB facing implícito)
- `revalidation/differ.py`: nova `_norm_for_compare(action, street)` trata `bet ↔ raise` como equivalentes em preflop. Postflop mantém distinção
- `revalidation/orchestrator.py` passa `street` ao differ

### Fix 2 — Push/Fold zone no engine (cobre 3/32 + extras)
- `preflop_range_evaluator.py`: `_recommended_action` ganha parâmetro `stack_bb`. Quando `stack_bb ≤ 14bb` (PF zone), retorna apenas `jam` ou `fold` — nunca `call`/`raise`/`limp`
  - core_range → jam (todas posições)
  - borderline → jam (BTN/SB/CO/HJ/LJ/MP), fold (UTG/UTG+1)
  - outside → fold
- `evaluate_preflop_range` extrai stack do state e passa adiante

### Fix 3 — postflop jam awareness (cobre 5/32)
- `decision_engine_v11.py`: quando GTO postflop sem strategy_json mas com `gto_label=gto_critical`, override `bestAction = gto.gto_action`. Antes só capeava o label, agora também corrige a recomendação (call → allin quando solver diz jam)

### Fix 4 — heurístico facing ≥ 2bb (cobre 5/32)
- `preflop_range_evaluator.py`: threshold de facing para tighter logic baixou de 3bb → **2bb**. Cobre iso-over-limp típicos (2-2.5x) que antes não disparavam set-mine/call para borderline

### Tweak adicional — oracle alts agressivas
- `revalidation/oracle.py:_heuristic_potodds`: quando `equity ≥ 0.55`, adiciona `raise` como alternative. Permite que engine.raise vs oracle.call vire `acceptable_alt` em vez de `major` quando hero tem equity confortável

### Resultados (1122 decisões)
| Métrica | Run #1 (baseline) | Run #4 (pós-fix) | Δ |
|---|---:|---:|---|
| Aligned | 89.5% | **98.3%** | +8.8pp |
| Major mismatch | 32 (2.9%) | **2 (0.2%)** | **-94%** |
| Acceptable alt | 79 (7.0%) | 15 (1.3%) | -64 (viraram aligned) |

### Majors residuais (2 — aceitos)
- **AQs UTG+2 30bb equity=0.49 facing iso**: spot mixed (4-bet ou call ambos GTO); equity abaixo do threshold 0.55 do oracle alt
- **K7s BTN 12bb vs all-in massivo**: PF zone heurístico recomendou jam, spot real é vs-shove com equity ruim — distinção que requer detecção de "facing all-in" no heurístico (TODO futuro)

### Validated
- Suites engine 194/195 (1 falha pré-existente postflop, sem relação), database 36/36, audit 8/8, reconcile 5/5
- Reprocess completo (1122 decisions) + sync + reconcile aplicados

### Próximo passo natural
- Refinar oracle/engine para spots vs-all-in (PF zone com facing >> stack)
- Considerar `revalidation_run_5` após mais torneios serem importados

---

## [v0.159.0] — 2026-05-22 — feat(push-fold): banner explícito + reconcile não mascara leak

### Added
- **Banner Push/Fold Zone no Replayer**: quando hero está em preflop com `stack_bb ≤ 12`, exibe banner âmbar explicando que apenas JAM ou FOLD são GTO em short stack. Esclarece dúvida do aluno sobre "por que call é leak"

### Fixed
- **`_reconcile_label` não mais mascara limp/call em push/fold zone**: antes, `gto_mixed → label='standard'` sempre. Agora: em PF zone (stack≤12bb preflop), se hero não-jam/fold com `gto_mixed`, demota para `small_mistake`. Não é "standard" limpar QTs UTG 10bb mesmo se GTO tiver 35% limp na strategy
- Assinatura de `_reconcile_label` ganha parâmetros opcionais `stack_bb`, `street`, `action_taken` para contexto. Callers em `update_decision_gto`, `resync_gto_labels_for_node`, `reconcile_tournament_labels` passam os campos do DB
- Função auxiliar `_is_pf_zone(stack_bb, street)` encapsula a heurística (≤12bb + preflop)

### Why
- **Reportado pelo usuário**: hand 260605903016 (QTs UTG 10.2bb, limp em zona push/fold) — engine via que era PF (best_action='jam') e GTO retornou gto_mixed → reconcile fazia `label='standard'`. Aluno via "decisão standard" mascarando o leak real
- Após fix: `label='small_mistake'`, gto_label permanece gto_mixed, mas aluno vê leak corretamente no dashboard

### Reprocess feito (decisão do user)
- Re-rodada do engine em todos os 10 torneios (1122 decisions) para aplicar fixes acumulados v0.151-v0.158 (is_3bet contextual, _POS_NORM corrigido, heurístico facing 3-bet+)
- Backup automático em `data/leaklab.backup.20260522_*.db`
- Cobertura GTO: 89.8% (postflop solver nodes reconectados via lookup natural)
- 4 labels reconciliados pelo demote PF

### Validated
- QTs UTG 10.2bb limp (id=28797): `label standard → small_mistake` ✓
- TypeScript verde, suite database 36/36, reconcile phase2 5/5

### Não fiz (deliberadamente)
- **A) Override de label em PF zone sem GTO** (escopo original): pulado pois B+C resolvem o caso do usuário. Pode ser adicionado se aparecerem outros casos sem gto_label em PF zone

---

## [v0.158.0] — 2026-05-22 — fix(heuristic): facing 3-bet+ vira set-mine/call para borderline + banner "Sem cobertura GTO"

### Fixed
- `_recommended_action` em `preflop_range_evaluator.py`: quando `facing_size >= 3bb` (hero enfrenta 3-bet ou squeeze), borderline hands (small pairs 44-77, suited connectors, broadway weak como K9s) → recomenda **call** (set-mine / implied odds) em vez de raise. Premium core hands (88+, broadway suited) em IP ainda podem 4-bet, OOP preferem call
- **Reportado pelo usuário**: hand 260886194685 (K9s UTG 44.9bb facing 4bb 3-bet + cold caller) — engine recomendava raise quando GTO correto é call/fold. Após fix: recomenda **call**

### Added
- Banner "Sem cobertura GTO" no Replayer: quando uma decisão do hero não tem `gto_label` (spot multiway sem solução pré-computada), exibe nota explícita explicando que a recomendação vem do engine heurístico, com confiança moderada, e que detalhes profissionais não estão disponíveis para esse tipo de spot

### Why
- Antes: usuário via "Recomendado: raise" em spot multiway sem entender que não havia dados de solver e a recomendação era heurística genérica que ignorava o facing_size grande
- Agora: heurístico sabe que facing 3-bet+ ≠ facing RFI; UI deixa transparente quando a fonte é heurística vs GTO

### Limitação
- Opener facing squeeze (open + 3bet + cold caller, hero=opener) continua sem cobertura GTO na conta atual do GW (`MTTGeneral` antigo retorna 204 para esses spots). Cobertura completa exigiria upgrade do plano GW para `MTTGeneralV2`

### Validated
- K9s UTG facing 4bb → recomenda `call` (era `raise`)
- 4c4s LJ facing 4bb → recomenda `call` (set-mine)
- AA UTG facing 4bb → recomenda `call` (OOP prefer manter range)
- AA BTN facing 4bb → recomenda `raise` (IP 4-bet)
- Sem facing (RFI): comportamento inalterado
- TypeScript verde, suite database 36/36 verde, engine 194/195 (1 falha pré-existente em test_postflop_error_rate_reduced, sem relação)

---

## [v0.157.0] — 2026-05-22 — fix(preflop): mapping 9-max → 8-max corrigido (MP1→HJ, MP2→CO)

### Fixed
- **Bug estrutural no `_POS_NORM`** (introduzido no commit 30fb9e7 em 10/maio): `MP1` colapsava para `LJ` e `MP2` para `HJ`, causando colisão geométrica quando o opener era `UTG+2` (também `LJ`)
- Quando hero=MP1 e opener=UTG+2, lookup virava `vs_RFI[LJ][LJ]` (não existe) → `available=False` → engine caía no heurístico genérico que recomendava raise mesmo com small pairs (set-mining seria correto)
- **Reportado pelo usuário**: hand 260886154914 (MP1 com 44 vs UTG+2 raise + UTG+1 limp, 70bb) — engine recomendava raise quando GTO correto é fold/call (set-mine)

### Changed
- `_POS_NORM` em `preflop_gto_ranges.py`: MP1 agora → HJ; MP2 → CO (mapping geométrico por índice de ação 9-max → 8-max)
- Mesma correção aplicada em `gto_bot/solver_api/server.py`, `scripts/enqueue_preflop_gw.py`, `scripts/compare_ranges_gw.py`, `scripts/validate_reglife_coherence.py` para consistência

### Validation feita antes do fix
- **V1 git blame**: confirmado commit de origem (30fb9e7), intenção era resolver `available=False` mas mapping foi geometricamente errado
- **V2 escopo real**: apenas 26 decisions afetadas (2.4% do banco) — 16 com position=MP1 + 10 com vs_position=MP1; zero MP2
- **V3 convenção**: 9-max PokerStars → 8-max RegLife: UTG+2 é 3ª (LJ), MP1 é 4ª (HJ), MP2 é 5ª (CO)
- **V5 tests**: nenhum test pinning este mapping; safe para mexer

### Validated post-fix
- Hand reportada (id=27337, 44 MP1): antes `gto_label=None` → agora `gto_correct, gto_action=fold` ✓
- 23 decisions re-syncadas com sucesso
- Cobertura GTO: 98.0% → 98.2%
- Suites database (36) verde. Falha em test_postflop_error_rate_reduced é pré-existente (não relacionada com preflop)

### Limitação documentada
- `_POS_NORM` continua collapsing 9-max → 8-max (lossy por design — não temos ranges 9-max no RegLife). Para conta com `MTTGeneralV2` no GW (9-max nativo), seria possível usar mapping 1:1 — fica como melhoria futura

---

## [v0.156.0] — 2026-05-22 — feat(study-plan): item #9 do backlog — plano de estudos GTO-first

### Added — Helper unificado em repositories.py
- `get_leak_ranking_gto_first(user_id, days, last_n, limit)` — retorna `{source, leaks}`:
  - Tenta `get_gto_leak_ranking` (GTO) primeiro
  - Fallback para `get_leak_roi_impact` (heurístico) quando GTO está vazio
  - Retorna `source='empty'` se ambos vazios
- Reutilizado por todos os endpoints que consomem leak ranking para recomendações

### Endpoints refatorados (GTO-first com fallback transparente)
- `/coach/student/<id>/study-plan` (coach gerando plano para aluno)
- `/study/plan` (aluno gerando próprio plano)
- `/coach/chat` (AI Coach conversacional)
- `/coach/context` (contexto greeting do AI Coach)
- `/history/evolution` (dashboard de evolução)
- `/coach/student/<id>/history` (dashboard do coach com leaks do aluno)
- `recommend_coaches_for_leaks` em repositories.py (recomendação de coaches)

### LLM Coach narrative atualizado
- `generate_study_plan()` ganha parâmetro `leak_source: str` e:
  - Inclui nota de fonte no prompt do Claude (alta confiança GTO vs moderada heurística)
  - Retorna `source` no payload final para frontend
- `coach_chat_reply()` ganha parâmetro `leak_source` que contextualiza a confiança da fonte ao Claude

### Frontend
- `StudyPlanResponse`, `EvolutionResponse`, `CoachContext` types ampliados com `source`/`leak_source`
- `StudyPlan.tsx`: badge "GTO" (verde) ou "Heurístico" (cinza) no header do plano de estudos, com tooltip explicando precisão
- i18n nas 3 locales: chaves novas `source.gto`, `source.heuristic` + tooltips

### Why
- Antes: plano de estudos, AI Coach e recomendações usavam `get_leak_summary` (heurístico) como fonte primária — gerava recomendações inconsistentes com o que o aluno via no Replayer
- Agora: tudo passa por `get_leak_ranking_gto_first` — recomendações refletem análise GTO real quando disponível, com fallback transparente quando não há cobertura
- Alinhado com Ghost Table/Sparring GTO-only (v0.146.x) e Fase 3 do item #2 (v0.151.0)

### Validated
- Smoke test: `get_leak_ranking_gto_first(13, 90)` retorna `source='gto'`, 10 leaks (banco real do user)
- Suites database (36) + api (64) — todas verdes, zero regressão
- TypeScript verde

### Próximo
- Item 3 (multiway equity HU) ou Item 10 (cap 100bb) ou Item 12 (Range Grid postflop)

---

## [v0.155.0] — 2026-05-22 — feat(gto): engine consome vs_squeeze (squeeze multiway com cobertura GTO)

### Added — `analyze_preflop` agora reconhece scenario `squeeze`
- `analyze_preflop()` ganha parâmetro `caller_position` (str): quando preenchido junto com `vs_position` em pote 3-bet, scenario passa a ser `'squeeze'` em vez de `'vs_3bet'`
- Lookup acontece em `bk_data['vs_squeeze'][<pos>_squeeze_vs_<opener>_open_<caller>_call]`
- Fallback de bucket: stack 28-29bb (bucket 30bb) cai para 40bb quando vs_squeeze não tem 30bb
- Mantém compatibilidade: sem `caller_position`, comportamento de vs_3bet inalterado

### Detector de squeeze no sync
- `_detect_squeeze_context()` em `sync_gto_labels_from_ranges.py`: parsea `raw_text` do hand history para identificar opener e cold caller. Retorna `(opener_pos, caller_pos)` quando padrão `raise + call + hero_raise` é detectado
- Mapeamento de seats → posições 8-max canonical (UTG, UTG+1, LJ, HJ, CO, BTN, SB, BB)
- Skip casos não-tradicionais (cold 4bet, limp+iso+squeeze, etc.)
- `_process_rows()` agora carrega `raw_text` por torneio (cache) e usa detector para spots `is_3bet=True`

### Bugs corrigidos durante implementação
- Regex de seats no detector: restringido ao header (antes de `*** HOLE CARDS ***`) para evitar match duplicado no SUMMARY com sufixos como "showed [...]"

### Validated
- Spot real do banco do user: decision id=26443 (CO AQs 28.5bb squeeze vs UTG+LJ) — antes sem `gto_label`, agora classificada como `gto_critical` (squeeze de AQs nesse spot deveria foldar)
- 1/2 squeeze spots reais do banco ganharam cobertura. O outro (26367, BTN KJs vs limp+iso+squeeze) é cenário não-tradicional não coberto pelo schema vs_squeeze (limper + raise ≠ raise + caller).
- Suites database (36) + audit phase 1 (8) + reconcile phase 2 (5) — todas verdes, zero regressão

### Cobertura efetiva no banco
- 2 squeezes reais identificados; 1 classificado pelo novo schema (50%)
- Pipeline pronto para qualquer torneio futuro com squeezes tradicionais

---

## [v0.154.0] — 2026-05-22 — feat(gto): ranges vs_squeeze extraídos do GTO Wizard (64 spots novos)

### Added — leaklab_gto_ranges.json v2.4.2
**+64 entries no schema novo `vs_squeeze`** (não conflita com vs_3bet/vs_4bet existentes):

Cobertura por bucket:
- **40bb**: 16 entries
- **50bb**: 16 entries (mapeia também 60bb)
- **75bb**: 16 entries (mapeia também 80bb)
- **100bb**: 16 entries

Combinações cobertas (16 únicas):
- `BTN_squeeze_vs_HJ_open_CO_call`, `BB_squeeze_vs_CO_open_BTN_call` (clássicos)
- `CO_squeeze_vs_UTG_open_UTGplus1_call`, `BB_squeeze_vs_UTG_open_UTGplus1_call`
- Outros squeezes UTG/MP/LJ/HJ/CO opener + caller intermediário

### Pipeline reprodutivel
- `extract_squeeze_ranges.py` (servidor GCP): 96 queries ao GW via Chrome CDP, decoding hand-by-hand do array `strategy[169]`. 80/96 sucesso (16 spots 30bb fora da árvore)
- **Mapping `index → hand` descoberto via probe empírico:** ranks low→high (`'2','3','4','5','6','7','8','9','T','J','Q','K','A'`), index = row*13+col, com convenção:
  - row==col → par
  - row>col → suited (rank maior primeiro)
  - row<col → offsuit (rank maior primeiro)
  - Validado com: AA=168, 23o=1, 32s=13, AKs=167
- `merge_squeeze_into_ranges.py`: merge controlado com backup automático

### Schema novo (não invasivo)
```json
"50bb": {
  "vs_squeeze": {
    "BB_squeeze_vs_CO_open_BTN_call": {
      "pct_squeeze": 0.1264, "pct_call": 0.5161, "pct_fold": 0.3575,
      "hands_4bet": "AA,KK,AKs,JJ,KTs,...",
      "hands_call": "22-77,A9s,JTs,...",
      "hands_fold": "resto",
      "hands_mixed": "...",
      "_source": "gto_wizard MTTGeneral 2026-05-22",
      "_preflop_actions": "F-F-F-F-R2.3-C-F"
    }
  }
}
```

### Validated
- Sample BTN squeeze vs HJ+CO 100bb: 10.7% squeeze (composição polarizada: AA/JJ/AKs + bluffs blocker)
- Sample BB squeeze vs CO+BTN 50bb: 12.6% squeeze + 51.6% call (BB defende wide)
- 0 erros 403 — todos os spots squeeze cobertos pela árvore atual
- Backup automático em `leaklab_gto_ranges.backup.20260522_171941.json`

### Não foi mexido
- Gametype mapping (`MTTGeneralV2` para HU, `MTTGeneral` antigo aceito) — mantido como estava
- gto_nodes cache — não tocado (reverti rollback dos inserts experimentais)
- Engine `analyze_preflop`, `compute_spot_hash` — não modificados
- Lookup atual continua funcionando para os cenários cobertos hoje

### Próximo passo natural
- Engine ainda não consome `vs_squeeze` (estrutura nova). Quando consumir: detectar spot multiway com cold caller em `pipeline.py` e chamar lookup no novo schema. Fica como sprint separada.

---

## [v0.153.0] — 2026-05-22 — feat(gto): benchmark + cache populado via GTO Wizard (100 spots preflop)

### Added
- Pipeline benchmark em 3 passos (separação local ↔ servidor GCP):
  - `bench_step1_prepare.py` (local): sample 100 spots preflop diversos do DB, parsea raw_text do hand history, reconstrói `preflop_actions` no formato GW
  - `bench_step2_call_gw.py` (servidor GCP): chama API GW via Chrome CDP (porta 9222), salva responses brutos
  - `bench_step3_persist.py` (local): persiste em `gto_nodes` usando `stack_bucket` canônico do projeto
- Confirmado empiricamente: gametype `MTTGeneral` é **8-max** (não 9-max). Mapping fold-count → posição: 0=UTG, 1=UTG+1, 2=LJ, 3=HJ, 4=CO, 5=BTN, 6=SB

### Cache populado
- **gto_nodes preflop: 46 → 97** (+51 novos)
- Distribuição: 0-10bb (15), 10-20bb (19), 20-35bb (38), 35-60bb (16), 60-100bb (5), 100bb+ (4)
- Cada node tem `strategy_json` rico (frequências por família de ação)

### Stats benchmark (100 spots preflop)
| HTTP status | Count | Significa |
|---|---|---|
| 200 OK | 51 | Estratégia retornada |
| 204 No Content | 39 | Spot existe na árvore mas sem solução na conta |
| 403 Forbidden | 10 | Sem permissão (vs_3bet/multiway na maioria) |

### Limitações descobertas e documentadas
- A conta atual NÃO tem acesso a `MTTGeneralV2` (V2 retorna 403 para tudo). Mantido `MTTGeneral` (antigo)
- Comparação "agree/disagree" inicial estava comparando NÍVEIS DIFERENTES (ação dominante do range completo vs ação tomada com mão específica) — **inválida**. Benchmark hand-by-hand requer descobrir ordem do array `strategy[169]` retornado por action_solution (TODO próximo passo)
- Multiway (squeeze, cold 4-bet) e vs_3bet pré-resolvidos na árvore atual: maioria retorna 204 — cobertura limitada para estes cenários

### Recovery do erro de bucket
- Primeira leva de 51 inserts usou stack_bucket no formato `Xbb` puro (`50bb`, `60bb`) inconsistente com o resto do projeto (`X-Ybb` range). Foram revertidos e re-inseridos usando `leaklab.gto_utils.stack_bucket()` canônico
- Backup automático criado antes da operação

### Próximo passo (pendente decisão)
- Para benchmark hand-by-hand real: descobrir mapeamento do array `strategy[169]` em cada `action_solution` (ordem das 169 hands em row-major do grid 13×13). Via probe direcionado, ~15min de trabalho.

---

## [v0.152.0] — 2026-05-22 — feat(gto): cobertura vs_3bet/vs_4bet completa (item #13 backlog)

### Added — leaklab_gto_ranges.json v2.4.1
**+19 entries vs_3bet** preenchendo gaps (NÃO sobrescreve entries existentes):
- 100bb: MP, LJ, HJ, SB
- 75bb: MP, LJ, HJ, CO, SB
- 50bb: MP, LJ, HJ, CO, SB
- 30bb: MP, LJ, HJ, CO, SB

**+18 entries vs_4bet** (cenário 3-bettor enfrentando 4-bet):
- 100bb / 75bb / 50bb: MP, HJ, CO, BTN, SB, BB
- Convenção: `<POS>_3bet_vs_4bet`. Engine ainda não consome (requer fix posterior em `analyze_preflop` se quiser usar)

### Pipeline
- `backend/docs/external_ranges/`: charts MIT do AHTOOOXA/poker-charts (Greenline + Pekarstas, 100bb 6-max cash) como fonte
- `backend/scripts/parse_external_ranges.py`: TS → JSON normalizado
- `backend/scripts/synthesize_missing_vs3bet.py`: agrega greenline+pekarstas por voto majoritário, mapeia 6-max → 8-max, aplica stack compression para 30/50bb
- `backend/scripts/validate_gaps.py`: sanity checks (4bet ⊆ RFI, AA/KK em 4-bet, spot check da hand reportada)
- `backend/scripts/merge_gaps.py`: merge controlado com backup automático

### Mapeamento 6-max → 8-max
- UTG → UTG; MP_6max → LJ_8max (via `_POS_NORM` existente); HJ → HJ (mapeia também MP2); CO/BTN/SB/BB → identidade
- LJ usa range de UTG_6max (mais tight); HJ usa MP_6max

### Stack compression
- 100bb / 75bb: identity
- 50bb: remove hands marginais do call range (A2s-A8s, T9s, 76s, etc.)
- 30bb: compression mais agressiva (remove broadway suited marginais, pares médios)

### Validated
- Sanity check passou (2 errors em SB são consequência do SB RFI estar anomalamente tight no JSON original, não dos novos ranges)
- Spot check: HJ 75bb vs CO 3-bet com A8s → fold ✓ (mão reportada pelo usuário)
- Cobertura GTO atual: 98.0% (já estava no mesmo nível desde fix de detecção de is_3bet — os novos ranges agora servem como base estrutural para análises futuras com cenários HJ/CO/SB vs 3-bet)
- Backup do JSON original em `backend/docs/leaklab_gto_ranges.backup.20260522_121305.json`

### Limitações
- Fontes Greenline + Pekarstas são 6-max 100bb cash; adaptação para 8-max MTT é aproximada (~5% diferença no range real esperado)
- Stack compression para 30/50bb é heurística baseada em conceitos GTO, não solver-exato
- vs_4bet não consumido pelo engine ainda (requer fix em `analyze_preflop` se desejar uso ativo)
- Multiway spots (squeeze, cold 4-bet, limpers) continuam sem cobertura — próximo natural é GTO Wizard

---

## [v0.151.2] — 2026-05-22 — fix(gto): cobertura vs_3bet — detecta is_3bet_pot por contexto

### Fixed
- **Bug crítico de cobertura vs_3bet**: `pipeline.py` marcava `is_3bet=True` somente quando o hero **dava** um 3-bet (action='raise' + facing_size>0). Quando o hero **foldava ou callava** ao 3-bet do villain, a flag ficava False — o engine acabava tentando lookup vs_RFI e retornando `available=False`, deixando `gto_label=None`
- Fix em `scripts/sync_gto_labels_from_ranges.py`: nova função `_build_vs3bet_context()` faz lookup intra-hand — se hero já deu raise antes nessa mesma hand preflop, a decisão seguinte com `facing_bet > 0` é semanticamente vs_3bet, independente da ação tomada
- Adicionado `hand_id` aos SELECTs do sync (preflop)

### Why
- Reportado pelo usuário: torneio 4002336128, hand 260886143567, decision id=27336 (fold A8s do HJ vs CO 3-bet) estava com `gto_label=None`. Após o fix, classificada como `gto_correct` — fold A8s vs 3-bet está fora do range de continuação (22%)
- Ranges vs_3bet **já estão** integrados no `analyze_preflop` (`preflop_gto_ranges.py:303-324`) e no JSON `leaklab_gto_ranges.json` para 30bb/50bb/100bb com fallback para outras posições/stacks. O bug era só na detecção do cenário

### Validated
- Cobertura GTO global: 96.9% → **98.0%** após sync global
- 13 decisions ganharam cobertura (4 no torneio 199 + 9 nos demais)
- Suites: database 36/36, audit phase 1 8/8, reconcile phase 2 5/5

### Backlog
- Item #13 (Ranges vs_3bet por posição) parcialmente atendido: a infra existe e funciona; falta completar tabela vs_3bet para 10/14/17/20/40/75bb e para posições HJ/CO/LJ/MP/SB nos stacks que já têm dados. Fica como continuidade do item #13

---

## [v0.151.0] — 2026-05-22 — feat(dashboard): Fase 3 do backlog #2 — transparência GTO no dashboard

### Backend
- `get_tournaments` (`repositories.py`): retorna `labels_reconciled_at` e `gto_coverage_pct` por torneio (calculado on-demand a partir de decisions.gto_label)
- `get_breakdown` (`repositories.py`): retorna `gto_coverage_pct`, `total_decisions` e `with_gto` no payload
- `/player/leak-roi` (`app.py`): retorna `{source: 'gto' | 'heuristic', leaks: [...]}` em vez de só a lista — frontend agora sabe a fonte explícita

### Frontend
- `Tournament` type (`api.ts`): novos campos opcionais `labels_reconciled_at` e `gto_coverage_pct`
- `metrics.leakRoi`: response type ampliado para incluir `source`
- `RecentTournamentsTable`: badge "Análise GTO em andamento" (loader animado) quando `labels_reconciled_at == null` — substitui o badge "Analisado". Quando reconcile concluído, badge "Analisado" passa a exibir `· X% GTO` ao lado (cobertura)
- `LeaksPanel`: badge "GTO" (verde) ou "Heurístico" (cinza) no header, sinalizando a fonte do ranking. Tooltips explicam a diferença
- i18n nas 3 locales (pt-BR, en, es): chaves novas em `table.gtoPending`, `table.gtoCoverage`, `leaks.sourceGto`, `leaks.sourceHeuristic` e tooltips

### Decisão
- `DecisionQualityCard.tsx` é órfão no projeto (não é importado em nenhum lugar) — task de aplicar badge nele foi descartada por irrelevância. Foco ficou nos cards efetivamente usados (`GtoQualityCard` já mostra coverage no header; agora `RecentTournamentsTable` e `LeaksPanel` também)

### Validated
- TypeScript compila sem erros (`npx tsc --noEmit`)
- Smoke test backend: endpoint `/player/leak-roi` registrado; `get_tournaments` retorna os novos campos no banco real
- Suites: database 36/36, fase 1 audit 8/8, fase 2 reconcile 5/5, api 64/64

### Next
- Fase 4: leak ranking com `source` propagado para o LLM Coach e plano de estudos (alinhado com item #9 do backlog)

---

## [v0.150.0] — 2026-05-22 — feat(reconcile): Fase 2 do backlog #2 — reconciliação observável e backfill

### Added
- Coluna `tournaments.labels_reconciled_at` (TIMESTAMP, SQLite + PostgreSQL) — marca quando o reconcile rodou pela última vez. Frontend pode usar para mostrar "análise GTO em andamento" quando NULL
- `POST /admin/reconcile-tournament/<tournament_db_id>` (require_admin) — força sync preflop + reconcile manual; retorna `{tournament_id, preflop_synced, reconciled, labels_reconciled_at}`
- `backend/scripts/backfill_label_reconciliation.py` — itera torneios e reconcilia tudo. Modos: `--dry-run`, `--user-id`, `--since`, `--no-sync`. Reporta pending antes e reconciliations realizadas
- `backend/tests/test_label_reconcile_phase2.py`: 5 testes cobrindo migration, reconcile com/sem mudanças, backfill dry-run e execução normal

### Changed
- `reconcile_tournament_labels` agora seta `labels_reconciled_at = CURRENT_TIMESTAMP` ao final, mesmo quando 0 mudanças — assim o dashboard sabe que a análise GTO foi aplicada

### Validated
- Backfill rodado no banco local: 105/105 decisions reconciliadas em 9 torneios
- Auditoria pós-backfill: 0 pending (era 105 = 9.66%)
- Suites database (36) + api (64) + audit phase 1 (8) + phase 2 (5) verdes

### Note
- Fase 2 originalmente previa fallback de hash matching em `resync_gto_labels_for_node` (Furo C), mas a auditoria reportou 0 divergências live vs stored no banco atual. Sem evidência do problema, o fallback foi adiado — o audit C continua sendo a detecção contínua. Será revisitado se aparecerem casos

### Next
- Fase 3: transparência no dashboard (badges de cobertura GTO, "análise em andamento" enquanto `labels_reconciled_at IS NULL`)
- Fase 4: leak ranking unificado com `source` explícito

---

## [v0.149.0] — 2026-05-22 — feat(audit): Fase 1 do backlog #2 — diagnóstico de coerência label vs gto_label

### Added
- `backend/scripts/audit_label_coherence.py`: script de auditoria read-only com 4 categorias:
  - **A) Reconciliação pendente** — decisions onde `_reconcile_label(label, gto_label) != label`, agrupadas por transição
  - **B) Cobertura GTO** — % de decisions com gto_label populado, por street e por posição
  - **C) Live vs stored** — decisions cujo gto_label recalculado pela strategy_json do nó atual diverge do gto_label armazenado (resync pendente)
  - **D) Confiança dos KPIs de torneio** — tournaments cujo `standard_pct` deriva de baixa cobertura GTO
  - CLI: `--user-id`, `--samples`, `--json`, `--scan-limit`
  - Função `run_audit(user_id, scan_limit)` reutilizada pelo endpoint
- `GET /admin/label-coherence` (protegido `@require_admin`): expõe o relatório em JSON, com filtros `user_id` e `scan_limit`
- `backend/tests/test_label_coherence_audit.py`: 8 testes de integração cobrindo as 4 categorias e o filtro por usuário

### Fixed
- `reconcile_tournament_labels` (`repositories.py`) substituía `except: return 0` silencioso por log estruturado (`log.exception`); agora falhas são visíveis em produção
- `_preflop_sync_and_reconcile` (`app.py`): cada etapa (sync preflop + reconcile) tem try/except próprio com logging; antes uma falha no sync abortava silenciosamente o reconcile

### Why
- Item #2 do backlog (CRÍTICO): dashboard exibia `label` heurístico enquanto Replayer mostrava `gto_label` GTO, levando o aluno a ver "Standard" no dashboard e descobrir erro crítico no Replayer
- Esta fase é diagnóstica: mede a extensão do problema antes de remediar. No banco local atual: 105 decisions (9.66%) em 9 torneios pendentes de reconciliação, dominadas por transições `standard → small_mistake (gto_critical)` (43 casos) e `clear_mistake → standard (gto_correct/mixed)` (37 casos)

### Next
- Fase 2: tornar reconcile observável (`tournaments.labels_reconciled_at`), endpoint admin para forçar reconciliação, comando de backfill
- Fase 3: transparência no dashboard (badges de cobertura GTO nos cards)
- Fase 4: leak ranking unificado com `source` explícito

---

## [v0.148.0] — 2026-05-22 — fix(replayer): call vs shove com mao premium classifica como Correto

### Fixed
- `_build_replay_data` (app.py): `_facing` era 0.0 para decisões sem `gto_label` no banco (live_decisions não carregava `facing_bet` de `gto_data` quando gto_label=None). Com facing=0.0, `analyze_preflop` entendia como spot RFI e retornava `quality='acceptable'` para KK call vs shove → exibia "Misto" sem contexto
- Correção: `_facing` agora também tenta `spot.facingSize / level_bb` quando `decision.facing_bet` não está disponível (conversão chips→BB)
- Adicionado fallback "call vs shove": quando `analyze_preflop` retorna `available=False` para um CALL com `facing >= 40% do stack`, o sistema verifica o range de abertura da mão. Se premium (RFI quality='correct') → `quality='correct'`; se borderline → `quality='acceptable'`; se fora do range → `leak`. Evita análise incorreta de spots sem dados específicos de vs_3bet
- Mesmo fallback aplicado no enriquecimento de `preflop_gto` em `all_decisions` (linha 3139)
- Campo `reasoning` adicionado ao resultado do fallback: "Mão premium em range de abertura — call de shove correto."
- Novo label de cenário no frontend: `vs_shove_fallback` → "Call vs Shove" em `RangePanel.tsx`
- `reasoning` exibido no banner de contexto GTO do RangePanel quando presente
- KK HJ 27.4bb call vs shove 17.7bb: agora classificado como "✓ Correto (GTO)" com nota de raciocínio

### Technical
- `api.ts`: tipo de `scenario` ampliado para incluir `vs_shove_fallback`; campo `reasoning?: string` adicionado ao tipo `preflop_gto`

---

## [v0.147.0] — 2026-05-22 — fix(replayer): bloqueia escrita de dados preflop agregados no banco

### Fixed
- `_build_replay_data` (app.py): terceiro vetor do bug KK — o bloco "live strategy" chamava `_upd_gto` para **todas** as streets incluindo preflop. Para KK com nó agregado (fold=72%), isso gravava `gto_action='fold'` e `gto_label='gto_minor_deviation'` no banco, corrompendo futuras consultas ao endpoint `get_decision_gto`
- Solução: o `_upd_gto` do bloco live-strategy agora é protegido por `if action.street != 'preflop'` — nós agregados nunca mais poluem o DB
- O bloco `preflop_override_action` agora também persiste os valores corretos (`gto_label`, `preflop_override_action`) no banco via `update_decision_gto`, sobrescrevendo qualquer dado incorreto que já exista
- Todos os 194 testes da suite GTO passam sem regressão

---

## [v0.146.0] — 2026-05-22 — fix(replayer): corrige bug KK na timeline de replay (_build_replay_data)

### Fixed
- `_build_replay_data` (app.py): segundo vetor do bug KK descoberto e corrigido. O bloco de "live strategy" usava `lookup_gto` para buscar a estratégia do nó — que retornava o nó **agregado** preflop (fold=72%, raise=28%). Para KK (raise no range com 28%), `live_freq=0.28 < 0.30` definia `is_error=True` mesmo quando o DB tinha `gto_label='gto_correct'`
- Adicionado bloco `preflop_override_action` na timeline: após o live-strategy block, chama `analyze_preflop` com a mão específica do herói. Se `quality in ('correct','acceptable')`: `is_error=False`, `reconciled_best=action`, `gto_label='gto_correct'`. Tem prioridade máxima sobre `live_top_act` e `gto_action` armazenado
- Novo campo na timeline: `gto_action: preflop_override_action or live_top_act or gto_action`
- 6 novos testes em `test_gto_enrichment.py` cobrindo o fluxo de override e o comportamento correto para mãos fora do range (72o UTG)

---

## [v0.145.0] — 2026-05-22 — feat(gto): blindagem total do pipeline GTO — 6 camadas de proteção

### Added
- `backend/leaklab/gto_utils.py`: `normalize_gto_action()` — canonicaliza shove/allin/all-in → jam; constantes `VALID_POSITIONS`, `VALID_GTO_ACTIONS`
- `backend/database/schema.py`: migration `is_aggregate BOOLEAN DEFAULT FALSE` na tabela `gto_nodes`
- `backend/database/repositories.py` — `insert_gto_nodes()` reescrito com sanity checks completos:
  - Rejeita nós com street/position/gto_action inválidos
  - Rejeita nós com `gto_freq` fora de `[0,1]`
  - Rejeita `strategy_json` com `freq_sum < 0.10` (dados corrompidos)
  - Marca nós preflop sem `hero_hand` como `is_aggregate=True` automaticamente
  - Normaliza `gto_action` via `normalize_gto_action()` antes de inserir
- `backend/leaklab/decision_engine_v11.py`:
  - `_validate_decision_input()` — valida stack_bb, facing_size, board cards, position antes do lookup GTO
  - `_log_gto_miss()` — logging estruturado de todos os fallbacks GTO silenciosos
  - Guard em `_enrich_gto`: strategy com `freq_sum < 0.10` descartada
  - Consistência score/label: quality=correct → `final_score = min(score, 0.08)`; acceptable → `min(score, 0.18)`
- `backend/api/app.py` — `get_decision_gto()`: campo `is_aggregate` e `gto_note` na resposta JSON
- `backend/scripts/audit_gto_nodes.py` — script de auditoria com 9 checks (C1–C9):
  - C9 detecta o padrão "KK bug" (preflop fold-dominant aggregate nodes)
  - `--fix` aplica correções seguras: normaliza ações, marca is_aggregate, limpa strategy corrompida
- `backend/tests/test_gto_utils_comprehensive.py` — 92 testes de `gto_utils.py`
- `backend/tests/test_gto_enrichment.py` — 51 testes de enrichment functions do engine
- `backend/tests/test_api_gto_endpoints.py` — 38 testes de endpoints GTO incl. regressão KK
- `backend/tests/run_all_tests.py` — suite `gto` registrada com 4 arquivos (188 testes)
- `.github/workflows/ci-cd.yml` — step dedicado `Suite GTO` (zero falhas permitidas) antes do deploy

### Fixed
- Regressão KK: nós preflop agregados não contaminam mais análise hand-specific via `is_aggregate` flag e override em `get_decision_gto()`

---

## [v0.144.0] — 2026-05-21 — fix(replayer): GTO preflop usa análise hand-specific, não estratégia agregada do range

### Fixed
- `get_decision_gto` (replayer): para streets preflop, o nó GTO da DB contém estratégia **agregada** do range (ex: "HJ abre 28% → fold 72% de todas as mãos"). O sistema usava erroneamente esse fold 72% como recomendação para KK, marcando KK open como "Desvio Leve" com "Solver → Fold"
- Adicionado bloco preflop override: após encontrar o nó, chama `analyze_preflop` com a mão específica do herói; se retornar `available=True`, sobrescreve `top_action` com a recomendação hand-specific (ex: KK → raise)
- O strategy display (fold 72% · raise 28%) é mantido como contexto do range — apenas o `gto_action` (recomendação) é corrigido

---

## [v0.143.0] — 2026-05-21 — fix(ui): corrige labels do Top Leaks e remove referência IA_CORE

### Fixed
- `LeaksPanel.tsx`: removido badge "IA_CORE v2.1" — apenas "DEMO" exibido em modo fallback
- `leaks.doing` i18n em PT-BR/EN/ES: semântica corrigida — `best_action` é a ação **recomendada** pelo GTO, não a ação errada do jogador. Labels anteriores diziam "dando X quando não devia" (invertido); agora: "deveria dar X"
- `aicoach.json` (3 locales): campo `model` corrigido de "Modelo tático v2.1" / "Tactical model v2.1" para "Claude Haiku" (modelo real em uso)

---

## [v0.142.0] — 2026-05-21 — fix(replayer): v4 dimensões e cor da borda fieis ao PS

### Fixed
- Borda refeita com dimensões medidas pixel-a-pixel na referência PS (`mesa ps.png`, 1441×767px)
  - Cor: `#242424` charcoal escuro (era mahogany quente — totalmente errado)
  - Espessura: +42px sobre o feltro (54px na imagem PS × escala 1120/1441)
  - Apenas 4 camadas de profundidade 3D (era 9), offsets sutis
  - Nenhum destaque quente — apenas linha especular `rgba(255,255,255,0.11)` na borda externa
- Feltro: `rx=435, ry=128` → ratio 3.40:1 (matches apparent oval do PS)
- CSS `rotateX` removido — perspectiva embutida diretamente no canvas (oval desenhado flat)
- Fundo: quase preto puro `#050606` com glow verde mínimo (PS-accurate)
- `CY=310, RY_SEAT=178` alinhados ao novo centro da mesa

## [v0.141.0] — 2026-05-21 — feat(replayer): v4 Canvas API — mesa ultra-realista

### Changed
- **`leaklab-replayer-v4.html`**: background da mesa migrado de SVG para Canvas 2D API
  - Maior controle de gradientes e texturas — qualidade visivelmente superior ao SVG
  - Mesa oval `rx=482, ry=172` (ratio 2.80:1 → aparente ~3.5:1 após CSS perspective)
  - Borda mahogany com 9 camadas de profundidade 3D (offset maior = face frontal mais visível)
  - Gradiente rim top-lit warm: `#8a6e54 → #6a4e38 → #422f20 → #0e0b08`
  - Catchlight externo `rgba(255,225,155,0.32)` + groove sombra 10px → separação clara feltro/borda
  - Textura de feltro: crosshatch diagonal (warp+weft, canvas clip)
  - Perspectiva reforçada: `rotateX(24deg)`, `perspective: 620px`
  - Slots de cartas comunitárias redesenhados: inset escuro com borda visível + inner glow

## [v0.140.0] — 2026-05-21 — feat(replayer): leaklab-replayer-v4 — mesa PS-quality

### Added
- **`leaklab-replayer-v4.html`**: redesign visual completo do replayer com qualidade PokerStars
  - Mesa oval ratio ~2.4:1 (era 1.9:1), igual ao PS
  - Borda 3D com 4 camadas de profundidade (bottom-face, side-face × 2, top-face) visíveis na perspectiva
  - CSS `rotateX(19deg)` com `perspective: 700px` para tilt dramático tipo casino
  - Felt verde rico com destaque central e vinheta escura nas bordas
  - Ambiente escuro com glow verde emanando da mesa (efeito luz de mesa)
  - Player pods PS-style: avatar circular (r=21) com silhueta, nameplate horizontal dark
  - Cartas sempre posicionadas ACIMA dos player spots
  - Face-down card back com padrão de diamantes e escudo LeakLab
  - Chip stacks mais altos (CH=5) com drop shadow

### Fixed
- Ghost Table: `originalMistake` removido das fases active e result (evita ancoragem)
- Ghost Table: label "Heads-up" agora só exibe quando `num_players <= 2`
- Ghost Table: painel duplicado "Você escolheu / Ação correta" removido do resultado
- Ghost Table: modal IA agora renderiza no branch full-screen correto (estava no HudLayout que não era montado)

---

## [v0.139.0] — 2026-05-21 — chore: plano Ghost Table confirmado completo

### Confirmed
- **FIX 1** (`raise→bet` guard): presente em `app.py:1057` e `decision_engine_v11.py:548` — sem aposta anterior, `raise` é normalizado para `bet`
- **FIX 2** (live GTO lookup no drill submit): `_resolve_best_action_from_node()` em `app.py:931` — mesma lógica do Replayer, com 3 fallbacks de hash e guard SPR
- **FIX 3** (`num_players` no GhostTable): `GhostTable.tsx:156` usa `Math.min(9, spot.num_players ?? 6)` — sem hardcode HU para postflop
- **FIX 4** (reset SRS): endpoint `DELETE /player/drill-sessions/reset` + botão "Reiniciar histórico de treino" na intro do Ghost Table + `drill.resetSessions()` no API client

Todos os 4 fixes do plano `fuzzy-percolating-parnas.md` confirmados implementados. Plano fechado.

---

## [v0.138.0] — 2026-05-21 — feat(gto): force-refresh todos os nós + invalidação de cache LLM

### Changed
- **`validate_nodes_vs_gw.py --force-refresh`**: re-consulta GTO Wizard para todos os 199 spots únicos das decisions postflop, substituindo nós antigos (criados com `stack_bucket` ou `solver_cli`) por estratégias com stack exato, facing_bet e num_players corretos. 235 decisions agora têm dados precisos
- **LLM cache invalidado**: 27 entradas removidas do banco (explicações geradas com gto_label antigo). Dashboard, planos de estudo e análises serão regenerados com dados corretos na próxima consulta
- **`/admin/llm-cache/clear`**: novo endpoint admin para invalidar LLM cache (banco + in-memory) sem precisar acessar banco diretamente

### Impact
- gto_critical flop: 78→80 | gto_correct flop: 40→42 | turn: distribuição rebalanceada com dados precisos de stack/facing/num_players
- Próximas explicações LLM gerarão contexto correto ("você tinha 42bb e foldou contra um c-bet de 1.6bb" vs "você tinha 50bb e...")

---

## [v0.137.0] — 2026-05-21 — fix(gto): cobertura postflop 100% — fallback root street via re-query

### Fixed
- **Fallback root street**: quando todos os retries de depth falham (facing_bet fracionário sem árvore no GW), re-consulta `query_gto_wizard` com `facing_size_bb=0`. Usa exatamente o mesmo code path que funciona, evitando interferência de sessão HTTP dos requests anteriores
- **BTN 13bb 4p facing=1.6bb**: último spot sem cobertura — agora retorna estratégia do root do flop (check 100%) via fallback

### Impact
- Cobertura postflop: **1 → 0 sem resposta** (100% de cobertura, 212/235 decisions com nó GTO)
- 1 decisão (#26960) atualizada: action=check, label=gto_critical

---

## [v0.136.0] — 2026-05-21 — fix(gto): cobertura postflop 98% — depths HU + MTTHUGeneral stacks vazio

### Fixed
- **MTTHUGeneral `stacks=""`**: HAR heads-up confirmou que o gametype HU não envia o parâmetro `stacks` (todos os outros gametypes enviam `stacks=X.125-X.125-...`). Adicionado `"stacks": ""` no `_TABLE_CONFIG[2]`
- **`_GW_HU_VALID_DEPTHS`**: depths válidos para HU completamente diferentes do 9p — `[13,14,15,16,18,20,25,26,27,28,40,41,50,51,60,61,62,63,64,65]` mapeados empiricamente. Depths 7–12 e 66+ sem solução em HU
- **`_GW_DEPTHS_BY_GAMETYPE`**: mapa gametype → lista de depths, permitindo snap e retry corretos por gametype
- **`_snap_to_valid_depth` / `_retry_depths`**: recebem `gametype` como parâmetro e usam a lista correta

### Impact
- Cobertura postflop: **4 → 1 sem resposta** (98% de cobertura, 211/235 decisions com nó GTO)
- 1 spot restante sem cobertura: BTN 13bb 4p com facing_bet=1.6 (reconstrução de action sequence para bet fracionário falha)
- 6 decisões HU propagadas com gto_label via resync

---

## [v0.135.0] — 2026-05-21 — fix(gto-server): cobertura postflop 93% — depths válidos, retry, multi-gametype

### Fixed
- **`_GW_VALID_DEPTHS`**: lista completa de 41 depths com solução no GTO Wizard MTT (mapeados empiricamente 7–200bb). GW não tem solução em todo inteiro — padrão: 7–25 contínuo, 26–60 pares+extras, depois saltos 70/80/100/130/160/200
- **`_snap_to_valid_depth`**: snap para o depth válido mais próximo (antes: inteiro mais próximo → gerava 403 em ~60% dos casos)
- **`_retry_depths` + retry on 403**: quando depth não tem solução para a posição/gametype, tenta até 4 depths alternativos em ordem de distância. Resolve CO 34bb→35bb, LJ 24bb→25bb, SB 37bb→38bb, BB 34bb 7p→35bb
- **Fallback de posição**: UTG+2 em 8-max → LJ; UTG+1 em 7-max → LJ (posição equivalente no gametype menor)
- **SB→BTN em 2p**: em mesas HU não existe posição SB — mapeado para BTN
- **Multi-gametype**: suporte a MTTHUGeneral (2p), MTTGeneral_3m/4m/5m/7m/8m e MTTGeneralV2 (9p)
- **`_postflop_preflop_seq`**: sequência preflop correta para todos os gametypes (folds para todos entre hero e BB, BB calls)

### Impact
- Cobertura postflop: **37 → 4 sem resposta** (93% de cobertura, 205/235 decisions)
- 81 decisions atualizadas com gto_action e gto_label via resync
- 4 spots sem cobertura restantes: 3 HU (MTTHUGeneral — requer HAR específico) + 1 BTN 13bb 4p

### Added
- `scripts/probe_gw_depths.py`: mapeia depths válidos por gametype empiricamente

---

## [v0.134.0] — 2026-05-20 — fix(parser): prêmio do vencedor PokerStars ("wins the tournament")

### Fixed
- **`_extract_financials`**: regex não capturava o vencedor — formato "hero wins the tournament and receives $X" usa verbos no presente ("wins"/"receives"), enquanto o código só cobria "finished...received" (lugar 2+). Fallback somava chips coletados em potes → valores absurdos (ex: +$41.106)
- Agora: vencedor capturado com `place=1` e `prize` correto

---

## [v0.133.0] — 2026-05-20 — fix(gto-server): snap de stack para depth válido no GTO Wizard

### Fixed
- **`_stack_frac`**: stacks fracionários (ex: 22.3bb → 22.425) retornavam 403 no GTO Wizard, pois GW só tem soluções em profundidades inteiras. Agora snapa para `round(stack_bb)` antes de adicionar 0.125

---

## [v0.132.0] — 2026-05-20 — fix(gto-server): MTTGeneralV2 9-max com stacks param, preflop correto, multi-gametype

### Fixed
- **`MTTGeneralV2`** (9-max): adicionado parâmetro `stacks=` com 9 valores iguais (era string vazia → 0 respostas)
- **`_TABLE_CONFIG`**: mapeamento completo num_players 2–9 → gametype/positions/open_size
- **`_postflop_preflop_seq`**: gerava sequências com contagem errada de ações (ex: UTG gerava 3 em vez de 9)
- **`positions`** MTTGeneralV2: incluído UTG+2 (era 8 posições → sem match para CO e abaixo)
- **`validate_nodes_vs_gw.py`**: SELECT agora inclui `d.num_players` — antes todas decisions defaultavam para 9p

---

## [v0.131.0] — 2026-05-20 — fix(gto-server): reverter MTTGeneralV2, manter fix de board por street

### Fixed
- **`GAMETYPE`**: revertido para `"MTTGeneral"` — `MTTGeneralV2` exige parâmetro `stacks` completo com todos os jogadores que nossa implementação não envia, causando 0 respostas
- **`query_gto_wizard` — turn/river**: simplificado para enviar `flop_actions=""` / `turn_actions=""` (root do street) com o board correto (4/5 cartas). Não usa `X-X` — notação de check-check não confirmada no HAR do GW
- O ganho real desta versão: turn queries agora enviam 4 cartas e river enviam 5, fazendo o GW consultar o tree correto em vez do flop tree

---

## [v0.130.0] — 2026-05-20 — fix(gto-server): turn/river enviavam apenas 3 cartas ao GW (tratados como flop)

### Fixed
- **`gto_bot/solver_api/server.py` — `_norm_board`**: recebia `max_cards` fixo em 3, enviando apenas o flop para GW em todos os streets. Turn e river agora enviam 4/5 cartas respectivamente, consultando o tree correto
- **`query_gto_wizard` — action sequences**: turn agora usa `flop_actions="X-X"` (check-check no flop para chegar ao turn root); river usa `flop_actions="X-X" + turn_actions="X-X"`. Quando `facing_size_bb > 0`, modela a aposta no street correto
- **`_nearest_valid_bet`**: generalizado para aceitar `street` e definir `{street}_actions` corretamente (antes sempre definia `flop_actions`)
- **`resync_gto_actions.py`**: expandido para processar TODAS as decisions postflop (com e sem gto_label), não apenas as que já tinham label — permite propagar labels de nós recém-inseridos pelo GW

### Impact
- Turn e river de spots cobertas pelo GW agora retornam SEM RESPOSTA pela razão correta (board sem solução) vs. antes onde eram silenciados pela truncagem do board
- Requer restart do servidor GCP (`gto_bot/solver_api/server.py`) para o fix entrar em vigor

---

## [v0.129.0] — 2026-05-20 — fix(admin): cobertura GTO inclui preflop_ranges como terceiro source

### Fixed
- **`GET /admin/dashboard`**: `coverage` agora inclui `preflop_ranges` (decisions preflop com gto_label validado via arquivo JSON de ranges) além de `solver_cli` e `gto_wizard`. `total` inclui os três. Antes, as ~696 decisions preflop cobertas não apareciam no painel
- **Admin UI — Cobertura por Fonte**: cada fonte tem cor distinta (emerald=preflop_ranges, blue=gto_wizard, amber=solver_cli) e subtitle explicativo. KPI tile renomeado para "Decisions Cobertas" com breakdown `nodes: X · preflop: Y`

---

## [v0.128.0] — 2026-05-20 — fix(data): limpeza de nós ruins + propagação de labels GTO

### Fixed
- **176 nós ruins deletados**: nós `solver_cli` com `position=range_string` (ex: `JJ+,AKs,...`) e `stack_bucket='solver'` criados por runs antigos do solver foram identificados e removidos. Hashes desses nós eram inacessíveis via `compute_spot_hash()` com position real, tornando-os dead code no banco
- **11 decisions nullificadas**: decisions que referenciavam os nós ruins (todas UTG+1/UTG+2 — posições não suportadas pelo GW) tiveram `gto_label/gto_action` nulificados para evitar classificações baseadas em dados corrompidos
- **82 nós solver_cli enriquecidos com strategy_json**: run `--no-strategy-only` enriqueceu 82 nós válidos com `strategy_json` detalhado via GW (84 respondidos de 511 processados; os demais são UTG+2/0-10bb/boards não cobertos pelo GW)
- **2 ações de nós corrigidas** onde GW divergia da ação armazenada pelo solver local
- **11 labels de decisions propagados**: `resync_gto_actions.py --apply` atualizou 11 decisions cujos nós GTO foram enriquecidos/corrigidos

### Added
- **`scripts/_cleanup_bad_nodes.py`**: identifica nós com position=range_string ou stack_bucket='solver', encontra decisions afetadas, nullifica labels e deleta os nós. Dry-run por padrão, `--apply` para executar

### Estado do banco após esta versão
- `gto_nodes`: 449 solver_cli (159 com strategy_json) + 167 gto_wizard (todos com strategy_json)
- Preflop: 696/704 decisions com label (99%) — 8 sem cobertura (UTG+1, UTG+2 não suportados)
- Flop: 32/94 com label (34%) | Turn: 18/50 (36%) | River: 6/19 (32%)
- Distribuição de labels: gto_correct=526, gto_critical=168, gto_mixed=47, gto_minor_deviation=11

---

## [v0.127.0] — 2026-05-20 — refactor(gto): validate_nodes_vs_gw usa servidor GCP em vez de token de browser

### Changed
- **`scripts/validate_nodes_vs_gw.py`** reescrito para usar `gto_wizard_client.query_spot()` (POST /gto-wizard no servidor GCP). Não requer mais `GW_ACCESS_TOKEN` de browser. Requer `GTO_SOLVER_URL`, `GTO_SOLVER_API_KEY` e `GTO_WIZARD_ENABLED=true` no `.env`. Verifica status do servidor antes de iniciar (`/gw-status`)
- Removida dependência de `GWAuth`/`GWClient`/`build_gw_params()` do benchmark script
- Formato de resposta adaptado para `gw_query()` → `strategy_json` correto no banco

---

## [v0.126.0] — 2026-05-20 — fix(data): revalidação completa preflop + limpeza de orphans postflop

### Fixed
- **Preflop — 84 decisions corrigidas**: `resync_preflop_all.py` revalidou TODAS as 708 decisions preflop contra os ranges JSON (não apenas as NULL). Principal padrão corrigido: shoves de short stack (5-15bb) classificados como `gto_correct` que deveriam ser `gto_mixed` (ação de frequência mista no push/fold correto). Também capturou inversões em spots vs_RFI e is_3bet
- **Postflop orphans — 34 decisions limpas**: decisions postflop com `gto_label` setado mas cujo nó GTO foi deletado na limpeza anterior (93 nodes corrompidos removidos em v0.123.0) foram identificadas e tiveram `gto_label/gto_action` nulificados. Agora são candidatas a cobertura via `validate_nodes_vs_gw.py --new-decisions`

### Added
- **`scripts/resync_preflop_all.py`**: revalida TODAS as decisions preflop contra ranges JSON (diferente de `sync_gto_labels_from_ranges.py` que só preenche NULL). Dry-run por padrão, `--apply` para salvar. Suporta `--user-id` e `--tid`

### Estado do banco após esta versão
- Preflop: 708 decisions, todas validadas contra ranges JSON (source of truth)
- Postflop com cobertura GTO: ~47 decisions com nó GTO válido encontrável
- Postflop sem cobertura: ~96 decisions (34 orphans + 62 nunca cobertas) — aguardando `validate_nodes_vs_gw.py --new-decisions`

---

## [v0.125.0] — 2026-05-20 — feat(gto): script de validação e enriquecimento de nós via GTO Wizard

### Added
- **`scripts/validate_nodes_vs_gw.py`**: script para validar e enriquecer nós `solver_cli` contra GTO Wizard.
  - Modo padrão: prioriza (1) nós com exploitability > 5%, (2) 515 nós sem `strategy_json`, (3) amostra aleatória ~10% dos demais
  - Modo `--new-decisions`: cobre decisões postflop sem nenhum nó GTO — consulta GW primeiro (GTO Wizard first pipeline), fallback para `run_gto_worker.py` (solver_cli)
  - Flags: `--apply`, `--limit N`, `--street`, `--high-exploit-only`, `--no-strategy-only`, `--sample-pct`, `--dry-run`, `--new-decisions`
  - Quando ação GW diverge da stored, atualiza `gto_action + gto_freq + source='gto_wizard'`
  - Sempre enriquece `strategy_json` com frequências completas do GW (melhora painel Estratégia GTO no Ghost Table)

---

## [v0.124.0] — 2026-05-20 — feat(ghost-table): exibe torneio e hand ID no contexto do spot

### Added
- **Ghost Table — `sitStrip`**: linha de referência discreta abaixo do contexto do spot mostrando nome do torneio, `#hand_id` e data. Permite identificar a mão original para busca manual quando necessário. Visível tanto no mobile quanto no desktop durante toda a sessão (fase active e result)

---

## [v0.123.0] — 2026-05-20 — fix(data): limpeza e ressincronização de gto_nodes e decisions.gto_action

### Fixed
- **`gto_nodes` (93 entradas removidas)**: deletados todos os nós `source=solver_cli` com `strategy_json` recomendando jam ≥ 80% em flop/turn/river com stack_bucket ≥ 20-35bb. Eram resultado de runs incorretos do solver onde `allin` dominava spots que deveriam ter check/bet. Muitos tinham boards com número errado de cartas para o street indicado (ex: flop com 4-5 cartas)
- **`decisions.gto_action` + `gto_label` (26 decisões corrigidas)**: ressincronizado contra `gto_nodes` limpos com board validation e guard SPR. Principais correções: normalização `allin → jam` e 2 mudanças de ação genuínas (ex: `allin → check` com reclassificação `gto_critical → gto_minor_deviation`)
- **`_resolve_best_action_from_node()` + `_valid_node()`**: adicionada validação de board após lookup — rejeita nós onde `board` do nó ≠ board da decisão, capturando colisões de hash SHA256[:16]
- **`get_decision_gto()` (Replayer)**: mesmo guard de board aplicado

### Added
- **`scripts/clean_gto_nodes.py`**: script de auditoria — lista nós suspeitos (board mismatch + jam implausível). `--delete --yes` para remover. Reutilizável em produção
- **`scripts/resync_gto_actions.py`** (reescrito): ressincroniza `decisions.gto_action` + `gto_label` usando lookup ao vivo com board validation e SPR guard. Dry-run por padrão, `--apply` para salvar

### Metrics
- Taxa de erro postflop: 51% → 38% (melhoria imediata após limpeza dos nós corrompidos)
- `gto_nodes`: 874 → 781 entradas válidas

---

## [v0.122.0] — 2026-05-20 — fix(ghost-table): guard SPR para nós GTO incorretos (jam implausível)

### Fixed
- **`_resolve_best_action_from_node()` (drill submit)**: se o nó retornar `jam` como ação dominante, `facing_bet = 0` e SPR (stack/pot) > 8, o nó é descartado como incorreto e o sistema usa `decisions.gto_action` como fallback. SPR > 8 sem aposta anterior torna jam como overbet de >8× o pote — GTO nunca recomenda jam como ação dominante nesse cenário
- **`get_decision_gto()` (Replayer `/replay/<id>/gto`)**: mesmo guard SPR aplicado ao painel Estratégia GTO — evita que a UI mostre "Shove 96%" para um spot onde o GTO correto é check/bet

### Root Cause
Nós do GTO Wizard em `gto_nodes` estavam sendo associados a spots diferentes via hash match com dados inválidos (ex: `strategy_json` com shove 96% para turn de Q4o com 28bb/pot 1.5bb = SPR 18.7). O guard de SPR detecta esses matches impossíveis sem precisar auditar o banco.

---

## [v0.121.0] — 2026-05-20 — fix(ghost-table): corrige lookup GTO Wizard no drill e replayer

### Fixed
- **`repositories.get_gto_node()`**: query ampliada para incluir nós do GTO Wizard (`source='gto_wizard'`) que possuem `strategy_json` mas `exploitability_pct = NULL` — antes eram sempre ignorados, causando fallback para `decisions.gto_action` (potencialmente desatualizado)
- **`_resolve_best_action_from_node()`** (drill submit): removido fallback d (`get_gto_node_by_spot`) que usava algoritmo de hash incompatível com `compute_spot_hash` e podia retornar nós aleatórios via colisão; adicionada validação pós-lookup (`node.street == street`)
- **`get_decision_gto()`** (endpoint Replayer `/replay/<id>/gto`): mesmas correções — removido fallback d, adicionada validação de street

### Why
Ghost Table mostrava recomendações erradas (ex: "shove" em flop 4-9-7 com A7o 33.7bb onde GTO é check, "shove" em KQK com Q8s 73.7bb). A cadeia de lookup chamava `get_gto_node()` que filtrava `exploitability_pct IS NOT NULL` — excluindo todos os nós GTO Wizard (armazenados com exploitability=NULL). Sem nó, o sistema usava `decisions.gto_action` que foi salvo por um worker via hash match que pode ter sido incorreto.

---

## [v0.120.0] — 2026-05-19 — feat(dashboard): GtoAlignmentCard — breakdown GTO por street (item 5)

### Added
- **`GET /player/gto-alignment`**: novo endpoint que retorna breakdown de alinhamento GTO por preflop/flop/turn/river — total, cobertura%, aligned%, correct/mixed/minor/critical por street
- **`repositories.get_gto_alignment_by_street()`**: query GROUP BY street com todas as métricas; janela de 90 dias
- **`frontend/src/components/hud/GtoAlignmentCard.tsx`**: card no dashboard com overall aligned%, mini stacked bar por street e cobertura
- **`frontend/src/lib/api.ts`**: interfaces `GtoAlignmentData` + `GtoAlignmentStreet`; função `metrics.gtoAlignment()`
- **i18n** (`pt-BR`, `en`, `es`): chave `gtoAlignment.*` em `dashboard.json`

### Backlog
- Item 5a (heatmap posição × street) adicionado ao backlog futuro — requer volume suficiente por (street × posição) para ser útil

---

## [v0.119.0] — 2026-05-19 — fix(preflop): SB complete aceitável em stacks sem limp_hands (Opção 2)

### Fixed
- **`preflop_gto_ranges.py` — `_rfi_quality`**: para SB com `is_sb=True`, quando a mão não está no raise range e o jogador completa (call/limp), retorna `acceptable` em vez de `leak`. Nos 6/9 stack buckets que já têm `limp_hands` preenchido, o comportamento existente é preservado. O fix afeta apenas os 3 buckets sem limp range (10bb, 40bb, 75bb)
- **`docs/leaklab_gto_ranges.json`**: reescrito em UTF-8 puro (encoding fix) — o metadata da validação introduziu um em-dash `\x97` que causava `UnicodeDecodeError` ao abrir no Linux/produção

### Why
GTO Wizard modela SB com fold/complete/raise. Nosso modelo tem apenas fold/raise. Para os stacks sem dados de complete zone, completar com uma mão fora do raise range não é um erro detectável — marcar como `leak` era um falso positivo.

---

## [v0.118.0] — 2026-05-19 — feat(validation): validação preflop ranges vs solver remoto (item 4)

### Added
- **`scripts/validate_ranges_vs_solver.py`** (novo): valida `leaklab_gto_ranges.json` contra o endpoint `/gto-wizard` do servidor remoto (GTO Wizard via CDP). Compara frequência de raise por posição × stack bucket
- **`scripts/gto_validation/comparison_preflop.json`**: resultado da validação — 42 spots comparados

### Fixed
- **SB 40bb RFI**: entrada com `fonte=None` e pct=70.7% (range quase full, interpolação incorreta). Corrigido para pct=43.1% usando SB 30bb como base (GW confirma freq similar nos dois stacks)
- **SB 75bb RFI**: entrada com `fonte=None` e pct=84.6% (full range). Corrigido para pct=12.8% via interpolação entre SB 50bb e SB 100bb RegLife

### Result
- 42/54 spots RFI comparados (12 skipped: 14bb e 75bb sem cobertura no plano GW)
- **Agreement (≤5%)**: 33 spots (79%)
- **Close (5–10%)**: 7 spots (17%)
- **Divergência (>10%)**: 2 spots — ambos SB, explicados por limitação de modelo (sem limp option vs GW que tem fold/complete/raise)
- Item 4 do backlog fechado: ranges validados e precisos para UTG/LJ/HJ/CO/BTN em todos os stacks

---

## [v0.117.0] — 2026-05-19 — feat(pipeline): deep dive 3-source GTO pipeline — FIX 1-5

### Fixed
- **FIX 1 — `decision_engine_v11.py`**: `gto_label`/`gto_action` preflop agora é persistido no DB no momento do upload. `analyze_preflop` retorna `available=True` → `result['gto']` preenchido → `save_decisions` armazena no DB. Antes, o campo ficava NULL até rodar o batch script manualmente
- **FIX 2 — `decision_engine_v11.py`**: `_enrich_preflop_gto()` agora passa `is_3bet_pot=bool(input_data.get('is_3bet', False))` para `analyze_preflop`. Spots de 3-bet são roteados para `scenario='vs_3bet'` em vez de `vs_rfi`
- **FIX 3 — `frontend/src/lib/gtoUtils.ts`** (novo arquivo): `computeEffectiveGtoLabel()` extraída para utilidade compartilhada. `Replayer.tsx` e `RangePanel.tsx` importam desta fonte única — elimina duplicação e risco de divergência futura
- **FIX 4 — `RangePanel.tsx`**: quando `solverOverridesRegLife=true`, o grid de ranges estático fica com `opacity-40 pointer-events-none` para indicar que é contexto, não o veredicto ativo. Elimina dois sinais contraditórios simultâneos
- **FIX 5 — `sync_gto_labels_from_ranges.py`**: refatorado para expor `sync_tournament(tournament_id)` como API pública. `api/app.py` chama `sync_tournament` + `reconcile_tournament_labels` no background thread `label-reconcile` após cada upload

### Result
- Pipeline 3 fontes coerente do upload ao Replayer: ranges estáticos → gto_nodes → heurístico, com fonte única exibida por vez
- `gto_label` preflop populado no momento do upload (antes: NULL até batch manual)
- Spots 3-bet avaliados no cenário correto via `is_3bet_pot`

---

## [v0.116.0] — 2026-05-19 — feat(pipeline): reconciliação label/gto_label automática

### Added
- **`database/repositories.py`**: `_reconcile_label(label, gto_label)` — helper de reconciliação; `reconcile_tournament_labels(tournament_id)` — reconcilia + recalcula `standard_pct` para um torneio
- **`api/app.py`**: background thread `label-reconcile` disparado após cada upload, aplica reconciliação automática para o novo torneio
- **`update_decision_gto`**: quando chamado sem `label` explícito (ex: Replayer salva veredicto ao vivo), agora reconcilia o label existente com o novo `gto_label`
- **`resync_gto_labels_for_node`**: quando solver atualiza `gto_label` via hash-match, agora também atualiza `label` via reconciliação
- **`sync_gto_labels_from_ranges.py`**: ao final do `--save`, chama `reconcile_tournament_labels` para os torneios afetados

### Result
- Qualquer novo upload, atualização do solver ou sync de ranges mantém `label` e `gto_label` automaticamente consistentes — sem mais intervenção manual

---

## [v0.115.0] — 2026-05-19 — fix(data): reconciliar label vs gto_label — zero conflitos

### Fixed
- **Desacordo `label`/`gto_label`**: dashboard dizia "Standard" enquanto Replayer mostrava erro GTO crítico. 173 decisões em 6 torneios reconciliadas usando regra de prioridade: GTO é autoritativo para direção (correto vs erro); quando ambos apontam erro, mantém o mais severo
- **98 `standard → small_mistake`**: engine disse ok, GTO disse crítico
- **61 upgrades** (43 `marginal→standard` + 18 `small_mistake→standard`): engine disse erro, GTO confirmou play correto
- **3 `marginal → small_mistake`** + **11 `clear_mistake → standard`**: ajustes de severidade
- `standard_pct` recalculado para todos os 6 torneios afetados
- `scripts/reconcile_labels_with_gto.py` adicionado para re-execução futura após novos uploads

### Result
- Zero conflitos `label`/`gto_label` na base — o que o dashboard mostra é o que o Replayer confirma

---

## [v0.114.0] — 2026-05-19 — feat(data-quality): cobertura preflop 98% — LJ push/fold + BB free-play

### Added
- **`leaklab_gto_ranges.json`**: posição `LJ` adicionada ao `push_fold` nos buckets `10bb`, `14bb` e `20bb` (baseada em UTG1 — posição adjacente em 6-max). Cobre casos `UTG+2` vs `UTG+1` que falhavam por alias
- **`sync_gto_labels_from_ranges.py`**: caso especial para BB free-play — quando BB checa sem facing bet, classifica automaticamente como `gto_correct` (ação trivialmente correta)

### Result
- Cobertura preflop: **696/704 (98%)** — antes ~79%, agora 8 restantes genuinamente irredutíveis
- Distribuição final: 527 `gto_correct` · 138 `gto_critical` · 22 `gto_minor_deviation` · 9 `gto_mixed`
- 8 casos irredutíveis documentados: 3x 3-bet sem `vs_position` (pipeline gap), 2x >100bb (sem dados), 1x BTN vs SB (ausente do RegLife), 2x outros

---

## [v0.113.0] — 2026-05-19 — fix(ranges): remover bluff-shoves trash offsuit de vs_RFI

### Fixed
- **`docs/leaklab_gto_ranges.json`**: removidos `32o, 42o+, 52o+, 62o+` das `raise_hands` de vs_RFI em todos os buckets e spots (116 entradas). Esses trash offsuits eram artefatos de solver de cash game que não se aplicam a MTT — causavam classificação incorreta de folds corretos como `gto_critical`
- Identificado via consulta manual no solver: SB 43o 28bb vs MP1 fold = correto; sistema marcava como erro
- 18 decisões revertidas para NULL e reprocessadas → 11 passaram para `gto_correct`

### Result
- `analyze_preflop` agora classifica folds de trash offsuit em spots vs_RFI como `correct` em vez de `gto_critical`

---

## [v0.112.0] — 2026-05-19 — feat(backend): sync_gto_labels_from_ranges

### Added
- **`backend/scripts/sync_gto_labels_from_ranges.py`**: preenche `gto_label`/`gto_action` para decisões preflop sem veredicto de solver, usando `analyze_preflop` com o range estático. Solver (gto_nodes) tem prioridade absoluta; este script só atua onde não há nó de solver
- Resultado: 146 de 201 decisões preflop sem gto_label classificadas — 101 `gto_correct`, 3 `gto_mixed`, 42 `gto_critical`

### Changed
- Quando range estático preflop confirma a ação do jogador, o badge "GTO ✓" passa a aparecer na lista de mãos em vez de nenhum indicador

---

## [v0.111.0] — 2026-05-19 — refactor(ui): simplificar indicadores de veredicto

### Changed
- **`TournamentDetail.tsx`**: removida linha lateral colorida (stripe esquerdo) e borda codificada por severidade — card tem borda neutra única. Eliminado visual duplicado de 3 indicadores para o mesmo veredicto
- **`TournamentDetail.tsx`**: badge engine (`Linha sólida`, `Atenção`, etc.) suprimido quando `category === "ok"` sem gtoLabel — ausência de badge comunica correção
- **`TournamentDetail.tsx`**: `leakTag` (texto `▸ small mistake`) suprimido sempre que `gtoLabel` existe — GTO já fala tudo
- **`Replayer.tsx`**: removido `GtoMixedBadge` do banner do solution card — label colorido já comunica o veredicto sem duplicar

### Principle
Uma fonte, um indicador: quando GTO existe → só o badge GTO fala; quando não existe → engine fala; badge ausente = jogada ok

---

## [v0.110.0] — 2026-05-19 — feat(replayer): badge GTO Misto com tooltip

### Added
- **`frontend/src/components/replayer/GtoMixedBadge.tsx`**: componente reutilizável com Radix Tooltip para três variantes:
  - `gto_mixed` → `◎ GTO Misto` (sky-400): ação do jogador tem 30–60% de frequência no equilíbrio
  - `gto_minor_deviation` → `◎ Defensável` (amber-400): ação com 10–30% de frequência, incomum mas defensável
  - `spot_mixed` → `◎ Spot Misto` (sky-400 suave): o spot em si tem ≥2 ações com ≥10% de frequência
- **`GtoStrategyPanel.tsx`**: badge `◎ Spot Misto` substitui parágrafo de texto pouco visível quando solver usa estratégia mista — tooltip explica o conceito ao hover

---

## [v0.109.0] — 2026-05-19 — fix(replayer): solver priority + UI cleanup

### Fixed
- **`Replayer.tsx`**: `gto_minor_deviation` reclassificado como não-erro — `isActionOk` e supressores de chips/notas agora incluem esta categoria
- **`Replayer.tsx`**: "⏳ Calculando…" substituído por mensagem honesta quando não há frequências de solver disponíveis
- **`Replayer.tsx`**: chip `Qualidade` e `pro_notes` suprimidos quando solver contradiz análise de range estático
- **`Replayer.tsx`**: `vs_position === 'UNKNOWN'` não exibe mais o chip de range
- **`RangePanel.tsx`**: banner neutralizado e conteúdo suprimido quando solver override ativo; texto "Veredicto do solver substitui análise de range estática"
- **`GtoStrategyPanel.tsx`**: nota de estratégia mista quando ≥2 ações têm ≥10% de frequência
- **`app.py`**: solver sempre persiste `gto_label`/`gto_action` no banco ao consultar — garante prioridade absoluta do solver sobre range estático
- **`sync_gto_labels_from_solver.py`**: batch sync que re-calcula gto_label a partir de gto_nodes via spot_hash

### Changed
- Thresholds `effectiveGtoLabel` alinhados entre frontend e backend: ≥60% → correct, ≥30% → mixed, ≥10% → minor_deviation, <10% → critical
- Nomes de marcas externas removidos de todo texto visível ao usuário: "RegLife" → "análise estática", "GTO Wizard" → "Solver GTO" / "solver"

---

## [v0.108.0] — 2026-05-19 — feat(gto): ranges push/fold para stacks curtos (10/14/20bb)

### Added
- **`backend/scripts/add_pushfold_ranges.py`**: script que integra ranges GTO push/fold (sem ICM, MTT full ring) ao JSON para stacks 10bb, 12bb, 15bb, 20bb; estrutura `push_fold[pos][stack] = {shove_hands, shove_pct, _source}`
- **`leaklab/preflop_gto_ranges.py`**: fallback push/fold em `analyze_preflop` para cenários RFI e vs_RFI quando não há dados RegLife (buckets 10bb/14bb); constante `_PUSHFOLD_BUCKET_STACK` mapeia bucket → stack keys; novas funções `_pushfold_quality` e `_pushfold_notes`
- **`docs/leaklab_gto_ranges.json` v2.4.0**: 20 entradas push/fold adicionadas — UTG/UTG1/CO/BTN/SB para stacks 10bb, 12bb, 15bb, 20bb_pf nos buckets correspondentes

### Changed
- `analyze_preflop`: ao não encontrar dados RegLife em RFI, consulta `push_fold[pos]` do bucket; em vs_RFI short-stack sem dados, usa shove range como reshove heurística

### Result
- Stacks curtos (10–15bb): análise disponível para todas as posições via push/fold GTO
- Spots classificados como leak/major_leak quando ação diverge do shove/fold GTO

---

## [v0.107.0] — 2026-05-19 — fix(gto): alias UTG1→MP no lookup vs_RFI + filtro facing_bet

### Fixed
- **`preflop_gto_ranges.py`**: opener `UTG+1` normalizava para `UTG1` mas JSON vs_RFI usa `MP` — adicionado alias `_VSRFI_OPENER_ALIAS = {'UTG1': 'MP'}` no lookup
- **`compare_reglife_spots.py`**: filtro `facing_bet >= 2.0` excluía opens curtos (<2bb em stacks rasos) — relaxado para `> 1.0` (exclui apenas limps puros de 1bb)

### Result
- vs_RFI cobertura: 29% → **43%** (RFI mantém 98%)
- Cobertura por stack: 40bb 90%, 50bb 74%, 30bb 55%, 100bb 55%, 14bb 41%
- Teto atual determinado pelos combos ausentes no RegLife PDF (10bb legacy: apenas 2 openers)

---

## [v0.106.0] — 2026-05-19 — chore(gto): recalcula gto_label com JSON v2.3.0 completo

### Changed
- Rodou `compare_reglife_spots.py --all --save` para RFI e vs_RFI com o JSON atualizado:
  - **RFI**: 340/347 decisões com gto_label (cobertura 98%)
  - **vs_RFI**: 64/115 decisões com gto_label (cobertura 56% — limitado pelos combos ausentes no RegLife PDF)
  - 40bb e 75bb agora cobertos via interpolação → 21 spots adicionais classificados

---

## [v0.105.0] — 2026-05-19 — feat(ranges): interpola vs_RFI 40bb e 75bb a partir de dados RegLife

### Added
- **`backend/scripts/interpolate_vsrfi.py`** — preenche vs_RFI de 40bb e 75bb por interpolação 50/50:
  - 40bb = média(30bb, 50bb): 28 spots com fold/call/raise/allin/aggr_pct
  - 75bb = média(50bb, 100bb): 27 spots com mesma estrutura
  - Spots marcados com `_source: "interpolated_reglife"` para distinguir de dados extraídos direto do PDF

### Changed
- **`backend/docs/leaklab_gto_ranges.json`** — versão 2.3.0:
  - 40bb e 75bb vs_RFI agora cobertos (antes: 6 e 12 spots em formato antigo)
  - Todos os 9 stacks têm cobertura vs_RFI com 7 openers cada
  - Cobertura total: 8 stacks com dados RegLife/interpolados + 10bb (push/fold legado)

---

## [v0.104.0] — 2026-05-19 — feat(gto): vs_position em decisions + comparação RFI+vs_RFI com RegLife

### Added
- **`decisions.vs_position`** — nova coluna para armazenar a posição do opener em spots vs_RFI:
  - Migração automática em `schema.py` (PostgreSQL + SQLite)
  - `save_decisions` em `repositories.py` salva `spot.villainPosition` neste campo para novos uploads
- **`backend/scripts/populate_vs_position.py`** — script retroativo que popula `vs_position` para as 346 decisões vs_RFI existentes re-parseando `tournaments.raw_text`:
  - Agrupa por torneio para evitar re-parse desnecessário
  - Usa `_infer_position` do `hand_state_builder` para mapear nome → posição
  - Resultado: 346 decisions atualizadas (UTG: 84, UTG+1: 57, HJ: 48, CO: 48, etc.)

### Changed
- **`backend/scripts/compare_reglife_spots.py`** — reescrito para comparar RFI + vs_RFI:
  - Passa `vs_position` para `analyze_preflop` em spots vs_RFI (facing_bet > 0, is_3bet=0)
  - Exibe coluna `VS` na tabela (posição do opener)
  - Seções separadas: "RFI Spots" e "vs_RFI Spots"
  - Suporta `--type rfi/vsrfi/both` e `--all` (todos os labels, não só mistakes)
  - Resumo geral com cobertura RegLife por tipo
  - Resultado: 100% cobertura RFI, 53% cobertura vs_RFI (restante = combos ausentes no RegLife)

---

## [v0.103.0] — 2026-05-19 — feat(ranges): extrai vs_RFI do PDF RegLife e adiciona lookup completo

### Added
- **`backend/scripts/render_reglife_pages.py`** (reescrito) — renderiza todas as 205 tabelas do PDF RegLife como PNG:
  - Detecta múltiplos títulos por página (1, 2 ou 3 tabelas) via posição Y, sem limite de half-page
  - Threshold de fonte baixado para 12pt (captura tabelas com título menor como `vsrfi_50bb_MP_vs_UTG`)
  - Override de página específica para corrigir typo no PDF (p071: "50 bbs" → 30bb)
  - Clip dinâmico por intervalo entre títulos consecutivos
- **`backend/scripts/extract_vsrfi_ranges.py`** — extrai ranges vs_RFI (3bet/call/fold) de 163 imagens:
  - Reutiliza classificador de pixels da RFI com 4 ações: fold (azul), call (verde), raise/3bet-size (vermelho claro), allin/3bet-push (vermelho escuro)
  - Estrutura: `ranges.[stack].vs_RFI.[opener].[defender]`
  - Campos: `fold_pct`, `call_pct`, `raise_pct`, `allin_pct`, `aggr_pct` (todos combo_pct / 1326)
  - Handstrings por ação: `fold_hands`, `call_hands`, `raise_hands`, `allin_hands`
- **`backend/scripts/add_combo_pct.py`** — adiciona `combo_pct` e `grid_pct` ao leaklab_gto_ranges.json

### Changed
- **`backend/docs/leaklab_gto_ranges.json`** — versão 2.2.0:
  - Adicionado bucket `17bb` com dados RegLife RFI + vs_RFI
  - 163 spots vs_RFI em 6 stacks (14bb, 17bb, 20bb, 30bb, 50bb, 100bb)
  - `pct` = `combo_pct` (combos reais / 1326); `grid_pct` preservado como backup
- **`backend/leaklab/preflop_gto_ranges.py`** — lookup vs_RFI atualizado para novo formato RegLife:
  - Suporte ao novo formato (chave direta de posição) e fallback ao formato antigo
  - `_vs_rfi_quality_new()` e `_vs_rfi_notes_new()` com base em fold/call/raise/allin por mão
  - Retorna `fold_pct`, `call_pct`, `raise_pct`, `allin_pct`, `fold_hands`, etc.
- **`backend/tests/test_preflop_gto_quality.py`** — teste `vs_rfi_AKo_fold_quality` atualizado para novo dado RegLife (CO AKo vs UTG 30bb é call, fold=leak)
- **`backend/docs/range_pages/`** — 205 imagens PNG (42 RFI + 163 vs_RFI) extraídas do PDF

---

## [v0.102.0] — 2026-05-18 — feat(ranges): atualiza leaklab_gto_ranges.json com dados RegLife via pixel analysis

### Added
- **`backend/scripts/extract_reglife_ranges.py`** — extrai ranges RFI dos 42 PNGs do PDF RegLife via análise de pixels:
  - Detecta bounds da grade 13×13 automaticamente por imagem (top vs bottom half pages)
  - Classifica cada célula por cor: raise (vermelho), fold (azul), limp/call (verde), shove (vermelho escuro)
  - Amostragem 5×5 por célula com filtro de pixels de texto/borda
  - Captura range de limp separado para SB em todos os stacks
  - Compressão de hands para notação poker padrão (ex: `44+,A4s+,K9s+`)
- **`backend/scripts/update_gto_ranges.py`** — atualiza `leaklab_gto_ranges.json` com dados RegLife preservando estrutura existente
- **`backend/scripts/probe_grid.py`** — utilitário de calibração para debug de imagens

### Changed
- **`backend/docs/leaklab_gto_ranges.json`** — versão 2.0.0 com dados RegLife solver-generated:
  - RFI ranges atualizados para 5 stacks: 14bb, 20bb, 30bb, 50bb, 100bb (todos os 7 posições)
  - 10bb, 40bb, 75bb preservados (push/fold e interpolações)
  - SB agora tem `limp_hands` e `limp_pct` separados (ex: SB 100bb: raise 3.6%, limp 88.2%)
  - Fonte marcada por entrada: `_fonte: "reglife_pdf/Xbb"` vs `"original"`
- **`backend/leaklab/preflop_gto_ranges.py`** — suporte ao limp range da SB:
  - `analyze_preflop`: lê `limp_hands`/`limp_pct` da SB e inclui `in_limp_range` na resposta
  - `_rfi_quality`: novos casos para limp correto, raise aceitável, fold leak da SB
  - `_rfi_notes`: mensagens contextualizadas para limp SB (range de limp, fold leak, raise aceitável)

---

## [v0.101.9] — 2026-05-17 — feat(gto): classificação inteligente + GTO Alignment Card no dashboard

### Changed
- **`backend/leaklab/decision_engine_v11.py`** — `_gto_classify_from_strategy` reescrita com lógica inteligente:
  - Extrai `ev_bb` de cada ação do `strategy_json` durante desserialização
  - Calcula `ev_diff` (custo real em BBs vs top action GTO)
  - Novos tiers: `≥60%` → correct; `≥25%` → mixed; `10-25%` → mixed se ev_diff < 0.15bb, senão minor_deviation; `<10%` → minor_deviation se ev_diff < 0.30bb, senão critical
  - Evita punir estratégias mistas legítimas (ex: call 15% com ev_diff 0.02bb deixa de ser `gto_critical`)

### Added
- **`GET /player/gto-quality`**: endpoint que retorna distribuição de `gto_label` nos últimos 90 dias (`gto_correct_pct`, `gto_mixed_pct`, `gto_minor_pct`, `gto_critical_pct`, `aligned_pct`, `coverage_pct`, `total_with_gto`)
- **`database/repositories.py`** — `get_gto_quality_breakdown(user_id, since_days=90)`
- **`frontend/src/components/hud/GtoQualityCard.tsx`** — card "Alinhamento GTO" no dashboard:
  - Barra empilhada com 4 segmentos coloridos (verde/azul/âmbar/vermelho)
  - Big number: % alinhado ao GTO (correct + mixed) com cor por desempenho
  - Legenda com percentuais por categoria
  - Oculto quando `total_with_gto < 10`
- **i18n** — chaves `gtoQuality.*` adicionadas em PT-BR, EN e ES

---

## [v0.101.8] — 2026-05-17 — feat(admin): painel de re-análise de labels preflop

### Added
- **`POST /admin/reanalyze-preflop-labels`**: endpoint admin que roda o pipeline completo server-side — re-parseia raw_text de todos os torneios, reconstrói decision inputs (com `facingSize`, `villainPosition`, `is_3bet`), re-executa `evaluate_decision` e corrige `decisions.label` onde difere. Recalcula `tournaments.standard_pct` nos torneios afetados. Idempotente.
- **AdminDashboard aba "GTO Worker"**: painel "Re-análise de Labels Preflop" com botão Executar, 3 KPIs (decisões verificadas / atualizadas / torneios afetados) e tabela de changes (hand_id · ação · label antes → depois)

---

## [v0.101.7] — 2026-05-17 — fix(gto): correção contradições GTO + re-análise labels preflop

### Fixed
- **`backend/leaklab/preflop_gto_ranges.py`** — todos os 5 bugs de contradição já corrigidos em versões anteriores:
  - BUG 1 (`_rfi_quality`): limp/call fora do range agora retorna `leak` em vez de `acceptable`
  - BUG 2 (`_vs_rfi_quality`): desvio de ação dentro do range agora retorna `leak` em vez de `acceptable`
  - BUG 3 (`_find_opener_key`): fallback silencioso para BTN_open removido — retorna `None` se sem match exato
  - BUG 4 (`analyze_preflop`): `facing_size > 0` → `vs_rfi` independente de `vs_position`
  - BUG 5 (`app.py`): `is_3bet_pot` passado corretamente para `analyze_preflop` em ambas as chamadas
- **`backend/scripts/reanalyze_preflop_labels.py`** — reescrito com pipeline completo:
  - Deduplicação por `(hand_id, position, action)` — evita double-update de DIs duplicados do pipeline
  - Recalcula `tournaments.standard_pct` nos torneios afetados (KPIs e RecentForm também atualizam)
  - Resultado: 700 decisões verificadas, 3 labels corrigidas em 3 torneios

---

## [v0.101.6] — 2026-05-17 — feat(study-plan): roteiro tático enriquecido com HUD stats

### Changed
- **`backend/leaklab/llm_explainer.py`**: `generate_study_plan` recebe agora `player_stats: dict` com todos os 12 HUD stats comportamentais
- **`_format_hud_stats_for_prompt()`**: nova função auxiliar que formata os stats com interpretação automática (`✓ dentro do range` / `⚠ acima/abaixo do ideal`) — o LLM recebe o contexto em linguagem de coach, não só números
- **Instrução de coaching**: novo parágrafo guia o LLM a cruzar VPIP/AF/BB Defense/Open Limp com os leaks para gerar módulos específicos de comportamento (ex: "VPIP alto + PFR baixo → loose-passive; AF abaixo de 2x → postflop passivo")
- Cache key atualizado para `v3` — invalida planos gerados sem HUD stats automaticamente na próxima chamada
- Ambos os endpoints `/study/plan` e `/coach/student/{id}/study-plan` passam os HUD stats

### Analysis
- Antes: LLM só recebia "frequência de erros por spot" — módulos eram genéricos
- Depois: LLM recebe perfil comportamental completo (12 stats + interpretação) — pode gerar módulos como "Você open limpa 8% das vezes (ideal 0-5%) — este módulo foca em eliminar limps e converter em opens ou folds"

---

## [v0.101.5] — 2026-05-17 — fix(i18n): textos hardcoded no dashboard

### Fixed
- **`CareerGraphCard.tsx`**: `"torneos"` hardcoded (espanhol) substituído por `t("career.analyzedCount")` — seguia o idioma errado independente da locale do usuário
- **`PlayerStatsCard.tsx`**: `"Ref MTT"` hardcoded substituído por `t("playerStats.refMtt")` — agora respeita o idioma
- Chaves adicionadas nas 3 locales (pt-BR, en, es)

---

## [v0.101.4] — 2026-05-17 — feat(hud): Pending GTO Notice + Open Limp% + fix StrategicTwin

### Added
- **`GET /player/pending-gto-count`**: endpoint que conta spots `wizard_pending` + `gto_hand_requests` pendentes para o usuário
- **Dashboard**: linha informativa com spinner `⏳ N spots GTO em análise no solver` entre os KPIs e PlayerStatsCard — visível apenas quando > 0; polling automático a cada 30s enquanto houver spots pendentes. Mensagem contextualmente correta: os HUD stats comportamentais (VPIP, PFR, etc.) NÃO são afetados pelo solver — só os indicadores do Replayer atualizam.
- **Open Limp%**: 4° stat da Row 3 do Player HUD Stats — % de limps preflop de posições non-BB sem aposta em frente (ref MTT ideal: 0–5%; acima de 8% = leak sério de fold equity). Row 3 agora 4 colunas simétricas com as demais rows.
- **`StrategicTwinCard`**: adicionado `"allin"` como alias de `"jam"` → "Shove" nas 3 locales; fallback gracioso para ações não mapeadas (exibe valor raw sem mostrar chave i18n)

---

## [v0.101.2] — 2026-05-17 — feat(dashboard): Confidence Drift Alert no topo + dismiss persistente

### Changed
- **`frontend/src/pages/Index.tsx`**: Confidence Drift Alert movido para o **topo absoluto** do dashboard (antes dos KPIs e do DailyFocusCard) — primeira informação visível quando há drift detectado
- **Dismiss persistente via `localStorage`**: ao fechar o alerta, ele não reaparece mesmo após recarregar a página; chave baseada em `userId + affected_sessions` — reseta automaticamente quando novos torneios são importados e o alerta muda de baseline
- **`GhostDrillCard` removido do dashboard**: drill_row agora exibe apenas `PressureProfileCard + IcmBreakdown` (grid-cols-2); o Ghost Table continua acessível via `/training`

---

## [v0.101.1] — 2026-05-17 — feat(hud): Fold to Flop Bet + BB Defense + Steal% no Player HUD Stats

### Added
- **`backend/database/repositories.py`** (`get_player_stats`): 3 novos stats calculados a partir do banco:
  - `fold_to_flop_bet`: % de folds no flop quando enfrenta aposta — proxy para **Fold to C-Bet** (o stat mais solicitado por coaches; ref MTT: 40–55%)
  - `bb_defense`: % de defesas da BB (call + 3-bet) ao enfrentar abertura pré-flop (ref MTT: 35–55%)
  - `steal_pct`: % de raises/shoves do BTN/CO/SB quando não há aposta anterior (ref MTT: 25–45%)
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: Row 3 com os 3 novos indicadores, cada um com barra de referência colorida (verde/amarelo/vermelho) e tooltip explicativo
- **`frontend/src/lib/api.ts`** (`PlayerStatsResponse`): 3 novos campos adicionados à interface

### Analysis
- Auditoria completa do HUD revelou: C-Bet% já existia (hero como aggressor); o que faltava era **Fold to C-Bet** (hero como caller/defender) — statísticas distintas e igualmente críticas. BB Defense e Steal% completam o perfil de jogo posicional.
- Stats não implementáveis com schema atual: Double Barrel (requer tracking cross-street), Check-Raise% (requer sequência intra-street), AF por street (sample muito pequeno no dataset atual)

---

## [v0.101.0] — 2026-05-17 — feat(docs): transparência GTO para coaches + audit trail no replayer

### Added
- **`frontend/src/pages/Docs.tsx`** + **`i18n/locales/*/docs.json`**: nova seção **"Metodologia de Classificação GTO"** (PT/EN/ES) explicando: os 3 cenários pré-flop (RFI, vs Open, vs 3-Bet), o pipeline de 4 etapas, a tabela de `action_quality` → impacto no label, os 8 buckets de stack (10bb–100bb com ranges exatos), quando `available=false` e a garantia de ausência de contradições — informação necessária para que coaches e professores entendam e recomendem o sistema com segurança
- **`frontend/src/pages/Replayer.tsx`**: **"Raciocínio do sistema"** — audit trail colapsável na Decision Card (botão 👁) mostrando o caminho de 4 etapas que gerou a classificação: Cenário → Range consultada (ex. UTG · 30bb) → Mão in/out (88 ✗) → Qualidade da ação (leak/correct/etc.). Disponível em todas as decisões pré-flop com `available=true`
- **`frontend/src/components/replayer/RangePanel.tsx`**: rodapé de metadados exibindo a fonte do range (`Nash MTT (local)` ou `tabelas estáticas`) e indicador quando análise GTO está indisponível — dá aos coaches clareza sobre qual dataset está sendo usado

---

## [v0.100.1] — 2026-05-17 — fix(gto): corrigir contradições no sistema de classificação preflop + testes de regressão

### Fixed
- **`backend/leaklab/preflop_gto_ranges.py`** — `_rfi_quality`: limp/call com mão **fora do range de abertura** classificava como `acceptable` em vez de `leak` — corrigido
- **`backend/leaklab/preflop_gto_ranges.py`** — `_vs_rfi_quality`: mão **in-range mas com ação diferente da recomendada** (ex: range recomenda call, hero 3-beta) classificava como `acceptable` em vez de `leak` — corrigido
- **`backend/leaklab/preflop_gto_ranges.py`** — `_find_opener_key`: fallback silencioso para `BTN_open` quando opener não encontrado causava análise com dados do **opener errado** (`available=True` falso); agora retorna `None` se não há correspondência exata — corrigido
- **`backend/leaklab/preflop_gto_ranges.py`** — `analyze_preflop`: `facing_size > 0` sem `vs_position` definia `scenario='rfi'` (abertura) em vez de `vs_rfi` (defesa), gerando recomendações invertidas — corrigido
- **`backend/api/app.py`** — linhas ~1508 e ~2927: `is_3bet_pot` nunca era passado para `analyze_preflop`; spots de 4-bet eram analisados como `vs_rfi` em vez de `vs_3bet` — corrigido
- **`frontend/vite.config.ts`** + **`frontend/src/components/replayer/RangePanel.tsx`**: `/preflop-ranges` não estava no proxy Vite, causando erro CORS silencioso; `apiData` ficava `null` e o componente exibia o range estático genérico (`CALL_IP`, 264 combos) em vez dos dados reais da API — corrigido

### Added
- **`backend/tests/test_preflop_gto_quality.py`** (novo): 76 testes de regressão cobrindo todos os classificadores de qualidade GTO (`_rfi_quality`, `_vs_rfi_quality`, `_vs_3bet_quality`), o lookup de opener (`_find_opener_key`), o ajuste de labels (`_preflop_gto_label_adjust`) e integração com dados reais via `analyze_preflop`

### Migration
- **`backend/scripts/reanalyze_preflop_labels.py`** (reescrito): re-analisa decisões preflop de todos os torneios importados usando o pipeline completo (`parse_hand_history` → `build_decision_inputs_for_hand` → `evaluate_decision`) — 40 decisions corrigidas no banco

---

## [v0.99.9] — 2026-05-16 — feat(replayer): odds ao vivo, GTO strategy panel, bounty badges, Ghost Table melhorias

### Added
- **`frontend/src/components/replayer/GtoStrategyPanel.tsx`** (novo): componente compartilhado que exibe a estratégia do solver com barras de frequência por ação, EV em BB, marcador da ação jogada e custo de oportunidade no rodapé. Reutilizado no Replayer e no Ghost Table (compact mode).
- **`frontend/src/pages/Replayer.tsx`** — Call Math Card: bloco compacto em steps de decisão postflop do hero exibindo pot odds vs equity com veredito +EV/-EV e EV estimado em BB.
- **`frontend/src/pages/Replayer.tsx`** — Bounty no showdown: badge `💀 $X` por seat no painel de resultados mostrando o bounty na cabeça do jogador e o ganho de KO quando aplicável.
- **`frontend/src/pages/GhostTable.tsx`** — indicador de pot odds na fase active (desktop sidebar + mobile), visível apenas quando há `facing_bet`.
- **`frontend/src/pages/GhostTable.tsx`** — GtoStrategyPanel compact no painel de resultado: após submit de um spot postflop, busca estratégia via `/replay/{id}/gto` e exibe frequências GTO da decisão.

### Changed
- **`frontend/src/components/hud/PokerTableV3.tsx`**: badge de bounty no SVG alterado de 🏆 verde para 💀 âmbar — mais coerente com a notação padrão de bounty.
- **`frontend/src/pages/Replayer.tsx`**: seção "Estratégia do Solver" agora usa `GtoStrategyPanel` em vez do rendering inline anterior.
- **`frontend/src/lib/api.ts`**: `GtoStrategyAction` recebe `ev_bb` e `exploitability_pct`; `ReplayStep` recebe `gto_strategy`; `ReplaySeat` recebe `bounty`.

---

## [v0.99.7] — 2026-05-16 — fix(replayer): LJ no RangePanel + jam→shove + GTO no prompt LLM

### Fixed
- **`frontend/src/data/ranges.ts`**: `LJ` adicionado ao `Position` type, `POSITIONS` e `normalizePosition` — antes retornava `null`, causando fallback para BTN e exibindo ranges errados
- **`frontend/src/data/ranges.ts`**: `PUSH_FOLD` agora tem entrada `LJ` em `≤15bb` (~33%) e `≤20bb` (~26%) com ranges Nash MTT interpoladas entre HJ e CO — inclui A8o em ambos os buckets
- **`frontend/src/components/replayer/RangePanel.tsx`**: `showGtoCtx` não depende mais de `pos === detectedPos`; banner GTO aparece sempre que `gto.available`, evitando inconsistência entre texto do engine e grid visual
- **`backend/leaklab/llm_explainer.py`**: `gto_solver_block` agora usa o campo `gto{}` completo do engine (strategy, frequências, exploitability) com fallback para campos raiz do banco — IA recebe dados objetivos do solver para análise postflop

### Changed
- **`frontend/src/lib/utils.ts`**, **`llm_explainer.py`**, **`i18n/locales/*/docs.json`**: "jam" substituído por "shove" em todo texto visível ao usuário (labels, prompts LLM, documentação, templates)

---

## [v0.99.5] — 2026-05-16 — feat(admin): GTO Worker dashboard

### Added
- **`backend/api/app.py`** (`GET /admin/gto/worker-status`): novo endpoint admin que retorna saúde do worker, contadores de fila (`gto_hand_requests` + `gto_solver_queue`), throughput por hora (últimas 24h), cobertura de `gto_nodes` por fonte e lista dos últimos 10 erros
- **`frontend/src/lib/api.ts`** (`GtoWorkerStatus`, `adminDashboard.gtoWorkerStatus()`): interface TypeScript e função de chamada para o novo endpoint
- **`frontend/src/pages/admin/AdminDashboard.tsx`** (`GtoWorkerTab`): nova tab "GTO Worker" no painel admin com indicador de saúde (ativo/ocioso), KPIs de fila, gráfico de throughput (Recharts BarChart), barra de cobertura por fonte e painel de erros recentes

---

## [v0.99.4] — 2026-05-15 — feat(GTO-011): análise GTO proativa e automática no import

### Added
- **`api/app.py`** (`_auto_queue_gto_for_tournament`): nova função que enfileira automaticamente `gto_hand_requests` para todas as mãos postflop após o import de um torneio — sem necessidade de intervenção do usuário
- **`api/app.py`** (`_analyze_impl`): dispara `_auto_queue_gto_for_tournament` em thread daemon imediatamente após `save_decisions()`
- **`database/repositories.py`** (`bulk_request_gto_for_hands`): INSERT OR IGNORE em lote na `gto_hand_requests` — idempotente, safe para reimports
- **`backend/scripts/migrate_gto_requests.py`**: script one-shot para enfileirar análise de torneios já importados

### Changed
- **`api/app.py`** (`_gto_hand_worker_loop`): batch aumentado de 3 → 10 requests por ciclo; intervalo adaptativo 5s (fila ocupada) / 30s (fila vazia)
- **`frontend/src/pages/Replayer.tsx`**: botão "Solicitar Análise GTO" removido — spots sem GTO exibem indicador automático "Analisando este spot automaticamente"
- **`leaklab/gto_solver.py`**: nós parciais (sem `strategy_json`) não retornam mais como definitivos — caem por para GTO Wizard; strategy retornada do DB ordenada por frequency desc
- **`leaklab/gto_solver.py`**: `gto_action` agora reflete a ação de maior frequência no strategy_json (antes usava campo direto podendo divergir)
- **`database/repositories.py`** (`insert_gto_nodes`): aceita nós do GTO Wizard sem `exploitability_pct`; aceita chave `strategy_json` diretamente além de `strategy_detail`

### Fixed
- **`api/app.py`** (`_process_gto_hand_request`): early returns corrigidos para retornar 4 valores (evitava `ValueError: not enough values to unpack`)
- **`api/app.py`** (`_build_replay_data`): `live_top_act` propagado corretamente ao campo `gto_action` — antes, strategy DB com `check 97%` sobrepunha GTO Wizard `allin 96%`; DB atualizado automaticamente quando `live_top_act` difere do `gto_action` armazenado

---

## [v0.99.3] â€” 2026-05-15 â€” feat(GTO-005/006): estimated_equity no banco + validaÃ§Ã£o GTO 98-100% + threshold draw fix

### Added
- **`database/schema.py`**: coluna `estimated_equity REAL` adicionada Ã  tabela `decisions` â€” migrations automÃ¡ticas para SQLite e PostgreSQL
- **`database/repositories.py`**: `estimated_equity` incluÃ­do no INSERT de decisÃµes (via `math.estimatedHandEquity` do pipeline)
- **`scripts/reeval_postflop.py`**: novo script de re-avaliaÃ§Ã£o postflop â€” detecta draws fracos (equity_adj < 0.15) e draws fortes com equity insuficiente dado posiÃ§Ã£o/stack, converte `best_action='bet'â†’'check'` em lote com `--dry-run` para preview

### Fixed
- **`postflop_range_evaluator.py`**: semi-bluff threshold `equity_adj >= 0.10` â†’ `>= 0.15`. GUT+BDFD (0.14) e BDFD+BDSD (0.10) nÃ£o justificam bet â€” confirmado por validaÃ§Ã£o GTO Wizard (98% flop, 100% turn/river)
- **`scripts/gto_validation/playwright_compare.py`**: interceptor de headers registrado ANTES de `page.goto` â€” evitava race condition onde a pÃ¡gina recarregava antes de capturar DPoP token; action format `B{size}` â†’ `R{size}` (API GTO Wizard aceita apenas R, nÃ£o B); parser `next-actions` corrigido para path real `next_actions.available_actions[].action.betsize`
- **`scripts/gto_validation/analyze_results.py`**: output reformatado para mostrar distribuiÃ§Ã£o completa GTO (`check^82%  bet 18%<nÃ³s` em vez de `our=bet(18%)`); adicionado breakdown de erros por tipo; encoding UTF-8 no Windows

### Tests
- **`tests/test_postflop_evaluator.py`**: testes atualizados para threshold 0.15 â€” GUT+BDFD agora espera `check`, FD e OESD ainda esperam `bet`

---

## [v0.99.2] â€” 2026-05-13 â€” fix(AUD-001): guard foldâ†’check restrito a BB â€” corrige regressÃ£o em 577 spots

### Fixed
- **`preflop_range_evaluator.py`**: `_recommended_action` retorna `'check'` apenas quando `position == 'BB'` e `facing_size == 0`. Demais posiÃ§Ãµes (UTG/HJ/CO/BTN/SB) retornam `'fold'` para mÃ£os fracas sem aposta â€” comportamento correto (escolha de nÃ£o abrir)
- **`preflop_range_evaluator.py`**: filtro de `alternatives` tambÃ©m restrito a `BB` â€” outros posiÃ§Ãµes podem ter `'fold'` como alternativa em borderline spots sem aposta
- **`decision_engine_v11.py`**: guard final `facingSize=0 â†’ check` adicionado `and spot.get('position') == 'BB'`. Antes afetava 577 decisÃµes de non-BB incorretamente
- **`api/app.py`** (`player_drill_submit`): guard serve-time restrito a `position == 'BB'`
- **`database/repositories.py`** (`get_sparring_hand`): guard serve-time restrito a `position == 'BB'`

### Data Migration
- **Phase 2 DB fix**: 20 decisÃµes `BB + facing_bet IS NULL + best_action='fold'` atualizadas: `best_action â†’ 'check'`. 13 dessas (action_taken='check') tambÃ©m tiveram `score â†’ 0.02, label â†’ 'standard'` (eram small_mistake/marginal por engano)

### Tests
- **`test_evaluators.py`**: 27 testes reescritos para comportamento correto por posiÃ§Ã£o â€” BB check, non-BB fold para mÃ£os fracas sem aposta
- **`test_postflop_evaluator.py`**: `test_preflop_unaffected` agora verifica range zones do postflop evaluator (nÃ£o presenÃ§a de 'check'), jÃ¡ que BB legÃ­timamente retorna 'check' preflop

---

## [v0.99.1] â€” 2026-05-13 â€” fix(GTO-004): unidades facing_size_bb e threshold is_simple_spot

### Fixed
- **`api/app.py`**: revert `facing_size_bb` para `decision.get("facing_bet")` (BBs do DB). Estava usando `_spot.get("facingSize")` que retorna chips â€” `bet_bucket(6400)="40bb+"` em vez do correto `bet_bucket(1.0)="0-3bb"`, causando hash de lookup completamente errado
- **`gto_solver.py`**: `is_simple_spot` threshold `stack_bb <= 20` â†’ `<= 25` para cobrir stacks de ~20bb, comuns em MTT. Stack de 20.1bb antes causava resoluÃ§Ã£o assÃ­ncrona que nunca retornava ao frontend
- **`Replayer.tsx`**: indicador "â³ Calculandoâ€¦" exibido quando `gto_label` existe mas `stratSorted` ainda estÃ¡ vazio (solver ainda processando) â€” evita silÃªncio confuso para o usuÃ¡rio

---

## [v0.99.0] â€” 2026-05-13 â€” feat(GTO-009): solver_cli facing_size_bb + deploy VM â€” estratÃ©gia completa por nÃ³ de decisÃ£o

### Added
- **`solver_cli` (`main.rs`)**: novo campo opcional `facing_size_bb` (padrÃ£o 0.0). Quando > 0, apÃ³s resolver o game tree completo, navega internamente para o nÃ³ onde OOP enfrenta a aposta do IP (`OOP check â†’ IP bet closest_to(facing_size_bb) â†’ OOP to act`) e retorna a estratÃ©gia de resposta (fold/call/raise/allin com frequÃªncias). Campo `facing_node: bool` na saÃ­da indica se a navegaÃ§Ã£o foi bem-sucedida
- **`gto_solver.py`**: `solver_payload` agora inclui `facing_size_bb` â†’ worker da fila e chamadas sÃ­ncronas passam o campo automaticamente ao binary
- **NÃ³s turn/river populados** para mÃ£o t=3910307458 h=257048692293 com estratÃ©gia completa: turn fold 55% / call 30% / raise 15%; river fold 56% / call 33% / raise 8% / allin 2%
- **Frontend** (`Replayer.tsx`): barras de frequÃªncia agora aparecem com qualquer nÃºmero de aÃ§Ãµes (`>= 1` em vez de `>= 2`); `topFreqPct` inline removido da coluna "GTO recomenda" (frequÃªncia jÃ¡ visÃ­vel nas barras)

### Technical
- NavegaÃ§Ã£o no game tree: `navigate_to_facing_bet()` busca `Action::Check` no root (OOP) e depois o `Action::Bet/Raise/AllIn` mais prÃ³ximo de `facing_chips` no nÃ³ IP; `game.back_to_root()` se o nÃ³ nÃ£o existir
- Pot de referÃªncia para labels de resposta: `pot_chips + facing_chips` (mais preciso para raise percentages)
- Flop ainda sem multi-action strategy no servidor de teste (1 core/1GB): Ã¡rvore de 3 streets excede 120s; produÃ§Ã£o (4 vCPU) suporta

---

## [v0.98.7] â€” 2026-05-12 â€” fix(UX-021): engine nÃ£o penaliza BB check em pot nÃ£o contestado

### Fixed
- **`decision_engine_v11.py`**: BB + preflop + check + facingSize=0 retorna imediatamente `label="standard"`, `bestAction="check"` sem calcular penalidades. Resultado no frontend: `is_error=false`, card mostra `âœ“ Correto` (ou nÃ£o aparece se nÃ£o hÃ¡ dados adicionais) em vez de `âœ— Erro / Ideal: Fold`
- O fix de `preflop_gto_ranges.py` (v0.98.6) sÃ³ eliminava o range analysis; a engine ainda calculava um erro independente baseado no `range_evaluation.recommendedPrimaryAction="fold"`

---

## [v0.98.6] â€” 2026-05-12 â€” fix(UX-020): BB free play nÃ£o gera anÃ¡lise de range preflop

### Fixed
- **BB check em pot nÃ£o contestado**: `analyze_preflop` retornava `available=True` com `action_quality="acceptable"` e nota "Fold correto" quando o BB simplesmente checkava seu free play. Corrigido: BB + scenario `rfi` + `action_taken="check"` retorna `available=False` imediatamente â€” painel de anÃ¡lise nÃ£o aparece
- **`_rfi_notes` default incorreto**: o else que gerava "Fold correto" disparava para qualquer aÃ§Ã£o nÃ£o-raise/jam fora do range (incluindo check/call). Corrigido para verificar explicitamente `act == 'fold'` antes de emitir essa nota

---

## [v0.98.5] â€” 2026-05-12 â€” feat(UX-019): DecisionCard unificado no /replayer React

### Changed
- **Painel lateral do Replayer React**: trÃªs seÃ§Ãµes separadas (AnÃ¡lise tÃ©cnica, Preflop Range GTO, GTO Analysis) substituÃ­das por um Ãºnico `DecisionCard` por aÃ§Ã£o do hero
- **Hierarquia de veredito**: GTO Solver > Range preflop > Engine â€” `[GTO Solver]` / `[Range]` / `[AnÃ¡lise]` exibidos como tag discreta no banner, resolvendo ambiguidade de qual fonte priorizar
- **Banner unificado**: colorido por severidade (emerald/sky/amber/red), Ã­cone + label em portuguÃªs sem jargÃ£o tÃ©cnico ("Desvio CrÃ­tico" em vez de "gto_critical", "Leak Grave" em vez de "major_leak")
- **ComparaÃ§Ã£o de aÃ§Ãµes**: "VocÃª jogou / GTO recomenda" em 1 ou 2 colunas conforme discrepÃ¢ncia; frequÃªncia top inline quando `gto_strategy` disponÃ­vel
- **Barras de frequÃªncia do solver**: integradas no mesmo card, aÃ§Ã£o do jogador marcada com `â†` em Ã¢mbar; EV diff `âˆ’0.18 BB vs Ã³timo` exibido quando `ev_bb` disponÃ­vel
- **RodapÃ© contextual compacto**: M-ratio + ICM como grid 2 colunas, visÃ­vel sÃ³ quando campos presentes
- **Conflito engine vs GTO**: substituiu caixa Ã¢mbar separada por 1 linha footnote discreta (`Engine â†’ FOLD / Solver â†’ CHECK â€” priorizando GTO`)
- **Removido**: score breakdown (`math_penalty`, `range_penalty`, `context_penalty`) â€” debug output, nÃ£o coaching; `error_score` com 3 casas decimais; palavra "HeurÃ­stica" completamente eliminada da UI

---

## [v0.98.4] â€” 2026-05-12 â€” feat(UX-018): novo design de painÃ©is no /replayer React

### Changed
- **Preflop Range GTO panel**: header banner colorido (ok/leak/grave) + badges em linha (in_range, hand_type, stack+bucket) + barra de range% com progress bar; remove layout de 2 colunas com Ã­cone solto
- **GTO Analysis panel**: substitui grid de cards por barras horizontais de frequÃªncia â€” sorted desc, player action marcada com `â†` em Ã¢mbar; verdict banner no topo (ok/mixed/bad) com background colorido por label; fallback para `gto_action` sem strategy preservado
- `isPlayedAction`: lÃ³gica de match flexÃ­vel (prefixo bidirecional) para `bet_50pct`, `allin`, etc.

---

## [v0.98.3] â€” 2026-05-12 â€” feat(GTO-008): Replayer standalone com dados reais da API

### Added
- **Carregamento real de dados**: replayer lÃª `?t=<tournament_id>&h=<hand_id>` da URL, busca `ll_token` do `sessionStorage`, e chama `/replay/<t>/<h>` (ou `/coach/student/<student>/replay/<t>/<h>` com `?student=`)
- **Loading overlay**: spinner enquanto busca a API; sem travar a UI
- **Error overlay**: exibe mensagem de erro + botÃ£o "Carregar demo" como fallback
- **Fallback demo**: sem params â†’ DEMO data (comportamento anterior preservado)
- **Vite multi-page build**: `leaklab-replayer-v3.html` adicionado como entry point do rollup â†’ copiado para `dist/` no build de produÃ§Ã£o
- **Vercel**: rewrite explÃ­cito para `/leaklab-replayer-v3.html` antes do catch-all â†’ servido como arquivo estÃ¡tico em produÃ§Ã£o

---

## [v0.98.2] â€” 2026-05-12 â€” feat(GTO-007): painel lateral no Replayer â€” heurÃ­stica + GTO

### Added
- **Painel lateral direito** no Replayer standalone (`leaklab-replayer-v3.html`): aparece em toda aÃ§Ã£o do herÃ³i, desliza com `transition: width .25s ease`
- **Heuristic Card**: prÃ©-flop mostra scenario/in-range/quality badges + range% + aÃ§Ãµes recomendadas; pÃ³s-flop mostra equity bar, pot odds, draw profile badge, M-ratio e ICM pressure
- **GTO Card**: verdict banner colorido (ok/mixed/bad), GTO rec vs aÃ§Ã£o do jogador, EV diff, barras de frequÃªncia de estratÃ©gia com marcaÃ§Ã£o `â†` na aÃ§Ã£o do jogador
- FunÃ§Ãµes JS: `gtoActionLabel`, `gtoVerdictClass`, `gtoVerdictText`, `isPlayerAct`, `stratFillClass`, `stratLblClass`, `rpRenderGtoCard`, `rpRenderHeuristicCard`, `rpRenderSidePanel`
- Demo data atualizado para exibir os dois cards sem API real

---

## [v0.98.1] â€” 2026-05-12 â€” fix(GTO-006): endpoint /decisions/<id>/gto â€” board truncation + hash fallbacks

### Fixed
- **Board truncation**: decisions table stores full board (4+ cards); endpoint now slices to street-appropriate length before hashing (flopâ†’3, turnâ†’4, riverâ†’5)
- **`hero_hand` guard removed**: endpoint previously returned 404 when hero_cards was empty (most decisions); now hero_hand is optional
- **`facing_bb` missing from hash**: `compute_spot_hash` call was missing the `facing_size_bb` arg â€” now passed correctly
- **Multi-step hash fallback**: endpoint tries 4 strategies in order â€” exact (hero_hand+facing), generic (no hand+facing), generic_nf (no facing), `get_gto_node_by_spot` (old hash scheme for legacy nodes)
- **Stored gto_action fallback**: if no node found at all but decision has `gto_label`/`gto_action` stored by worker, returns a synthetic single-action strategy so GTO panel always shows something
- **`get_decision_spot`**: added `gto_action` and `gto_label` to SELECT query
- **Hero card parsing**: handles both space-separated ("Jc Th") and concatenated ("JcTh") formats
- Result: 11/11 labeled decisions now return `found=True` with strategy (was 0/11)

---

## [v0.98.0] â€” 2026-05-12 â€” feat(GTO-004/005): GTO panel redesign + fixes chipsâ†’BB + solver stuck

### Added
- **GTO Panel redesign** (3 layers): Verdict banner (green/amber/red por `player_action_freq`), Full Strategy bars com barra da aÃ§Ã£o do jogador marcada (`â†`), Context collapsÃ­vel (position, street, stack, facing, exploitability)
- **`GtoStrategyAction` interface** em `api.ts`; `GtoDecisionResult` expandido com `strategy[]`, `player_action_freq`, `player_action_label`, `gto_action_label`, `ev_diff`, `exploitability_pct`
- **i18n**: novas chaves `gto.verdict.*`, `gto.ctx.*`, `gto.youPlayedLabel`, `gto.evDiffLabel`, `gto.exploitability`, `gto.strategyLabel`, `gto.contextLabel` nos 3 locales (PT/EN/ES)

### Fixed
- **GTO-004 chipsâ†’BB**: `facing_size_bb` em 3 locais do `app.py` usava `spot.get('facingSize')` (chips raw) em vez de `db_dec.get('facing_bet')` (BB normalizado da tabela `decisions`) â€” hashes errados corrigidos
- **GTO-005 solver stuck**: `hash_no_facing` fallback retornava nÃ³s sem aposta quando hero enfrentava bet â†’ removido; nÃ³s corrompidos (`gto_action=NULL`) voltavam `found=True` com `strategy=[]` â†’ fallback para enqueue corrigido
- **Endpoint `/player/decisions/<id>/gto`** reescrito: retorna `strategy` completa do nÃ³, `player_action_freq` (fuzzy match), `ev_diff`, `exploitability_pct`, labels human-readable
- **`get_decision_spot`** em `repositories.py`: adicionado `facing_bet` ao SELECT

---

## [v0.97.0] â€” 2026-05-11 â€” feat(UX-020): stacks BB com precisÃ£o decimal + C-bet real no HUD

### Changed
- **Stacks sem arredondamento** (`PokerTableV3`): `fmtAmt` agora exibe 1 decimal quando necessÃ¡rio (`1.8 BB`), inteiros sem decimal (`4 BB`), espaÃ§o antes de "BB"
- **C-Bet substituiu Flop Bet** no HUD principal e em `StudentDetail`: indicador passa a medir apenas bets no flop como agressor prÃ©-flop (denominator = oportunidades de c-bet, nÃ£o total de decisÃµes no flop)

### Fixed
- Backend `get_player_stats`: nova query SQL calcula `cbet_pct` via subquery que filtra hands onde hero raised/jammed preflop e viu o flop; campo `flop_bet_pct` removido
- Interface `PlayerStatsResponse` e `PlayerStats` atualizadas para `cbet_pct`

---

## [v0.96.0] â€” 2026-05-10 â€” feat(range-panel): contexto GTO integrado no painel de ranges

### Added
- **Banner de contexto GTO** no RangePanel: quando a mÃ£o Ã© do hero, exibe:
  - CenÃ¡rio detectado (RFI / vs Open / vs 3-Bet)
  - Badge in-range/fora do range com Ã­cone e cor (verde/Ã¢mbar)
  - Quality badge: Correto / AceitÃ¡vel / Leak / Leak grave
  - AÃ§Ã£o recomendada pelo GTO e % do range
- **SeÃ§Ã£o "AnÃ¡lise GTO"** abaixo do grid: exibe as `pro_notes` da engine como bullet points explicativos
- **Auto-seleÃ§Ã£o de tab**: o tab correto (Open / Call / 3-Bet) Ã© selecionado automaticamente com base no `scenario` da decisÃ£o (`rfi`â†’Open, `vs_rfi`â†’Call, `vs_3bet`â†’3-Bet)
- **vs_RFI usa opener correto**: quando disponÃ­vel, usa `vs_position` do preflop_gto para selecionar o opener certo no JSON

---

## [v0.95.0] â€” 2026-05-10 â€” feat(range-panel): ranges dinÃ¢micos do JSON por posiÃ§Ã£o e stack depth

### Added
- **`GET /preflop-ranges`** â€” novo endpoint que serve ranges GTO preflop do `leaklab_gto_ranges.json` por posiÃ§Ã£o e stack depth:
  - ParÃ¢metros: `position` (ex: BTN) e `stack_bb` (float)
  - Retorna: `rfi` (mÃ£os expandidas + %), `vs_rfi` (por opener), `vs_3bet` (4bet/call separados)
  - Stack bucket resolvido automaticamente pelo `_stack_bucket()` existente
  - PosiÃ§Ãµes normalizadas via `_norm_pos()` (suporta UTG+1, MP1, etc.)

### Changed
- **`frontend/src/components/replayer/RangePanel.tsx`** â€” painel de ranges agora consome o endpoint `/preflop-ranges` em vez dos dados estÃ¡ticos de `ranges.ts`:
  - Usa `step.hero_stack_bb` como stack depth da mÃ£o atual (coerente com a anÃ¡lise)
  - Mostra indicador de loading (`Loader2`) enquanto aguarda a API
  - Exibe `stack_bucket` no header para confirmaÃ§Ã£o visual (ex: `50bb`)
  - Fallback automÃ¡tico para dados estÃ¡ticos de `ranges.ts` se a API falhar
  - Label e description dinÃ¢micos com % do range por stack depth
  - vs_RFI usa primeiro opener disponÃ­vel no JSON para a posiÃ§Ã£o selecionada

---

## [v0.94.0] â€” 2026-05-10 â€” feat(engine): preflop GTO range integrado no decision_engine

### Changed
- **`backend/leaklab/decision_engine_v11.py`** â€” `evaluate_decision()` agora aplica range GTO preflop apÃ³s scoring de equity:
  - `_enrich_preflop_gto()`: chama `analyze_preflop()` para cada decisÃ£o preflop com posiÃ§Ã£o, stack e cenÃ¡rio (RFI/vs RFI/vs 3bet)
  - `_preflop_gto_label_adjust()`: matriz completa de ajuste de label por `action_quality`:
    - `correct` â†’ sempre `standard` (GTO confirma a aÃ§Ã£o do jogador)
    - `acceptable` â†’ cap em `marginal` (subÃ³timo mas defensÃ¡vel)
    - `leak` / `major_leak` â†’ floor em `small_mistake` (nÃ£o capeia `clear_mistake` para baixo)
  - `_best_action` sobrescrito com `recommended_actions[0]` do range quando GTO disponÃ­vel
  - `preflop_gto` adicionado ao dict de retorno de `evaluate_decision()`

### Fixed
- DecisÃµes preflop historicamente avaliadas sÃ³ por equity threshold agora recebem classificaÃ§Ã£o baseada em ranges GTO por posiÃ§Ã£o e stack depth
- `bestAction` para preflop agora reflete a aÃ§Ã£o GTO recomendada, nÃ£o apenas a heurÃ­stica de equity

### Tests
- 32 testes existentes do engine: todos passando (sem regressÃ£o)
- 8 novos cenÃ¡rios preflop validados: `correct`, `acceptable`, `leak`, `major_leak` Ã— RFI e vs_rfi

---

## [v0.93.0] â€” 2026-05-10 â€” feat(LLM-002): prompt de anÃ¡lise v2 â€” ICM como multiplicador, reverse implied odds e sÃ­ntese de padrÃµes

### Changed
- **`backend/leaklab/llm_explainer.py`** â€” `_build_payload()` e `system_prompt` completamente reescritos:
  - **ICM como multiplicador matemÃ¡tico**: equity mÃ­nima = pot odds Ã— fator (Ã—1.00 low / Ã—1.15 medium / Ã—1.30 high / Ã—1.50 bubble) â€” calculado em Python antes de enviar ao LLM, nÃ£o estimado pelo modelo
  - **Reverse implied odds**: tier low/medium/high â†’ subtrai 0/3/6pp da equity estimada; dÃ©ficit final = equity mÃ­nima ICM âˆ’ equity real ajustada
  - **Filtro M-Ratio obrigatÃ³rio**: M<6 = push/fold puro (aÃ§Ãµes invÃ¡lidas sinalizadas), M 6-12 = zona de pressÃ£o, M>12 = jogo normal; lÃ³gica integrada na construÃ§Ã£o do input
  - **Rastreamento de padrÃµes recorrentes**: `error_pattern_tracker` conta ocorrÃªncias por tipo de erro na sessÃ£o; nota automÃ¡tica quando mesmo leak aparece N vezes
  - **BLOCO 4 â€” SÃ­ntese Final obrigatÃ³ria**: RelatÃ³rio de PadrÃµes ao final de cada anÃ¡lise (leak dominante, stack depth crÃ­tico, padrÃ£o posicional, ICM sensibilidade, top 3 prioridades, EV recuperÃ¡vel)
  - **pfgto_block push/fold**: branch separado para M<6 com range de jam em vez de range de abertura padrÃ£o
  - **`max_tokens`** aumentado: `max(1200 Ã— N, 3000)` para acomodar sÃ­ntese final

### Added
- Constantes e helpers de mÃ³dulo: `_ICM_MULTIPLIER`, `_REV_IMPL_ADJ_PP`, `_rev_impl_tier()`, `_m_zone()`, `_action_warning()`

---

## [v0.92.0] â€” 2026-05-10 â€” feat(GTO-004): preflop range GTO â€” anÃ¡lise completa por posiÃ§Ã£o e stack depth

### Added
- **`backend/leaklab/preflop_gto_ranges.py`** (novo mÃ³dulo): lÃª `leaklab_gto_ranges.json` e analisa decisÃµes preflop cobrindo trÃªs cenÃ¡rios â€” RFI, vs RFI e vs 3bet â€” com classificador de qualidade (`correct/acceptable/leak/major_leak`) e notas profissionais por posiÃ§Ã£o e stack depth
- **`backend/docs/leaklab_gto_ranges.json`**: ranges MTT 8-max validados (RFI por posiÃ§Ã£o, vs RFI por abridor+defensor, vs 3bet) para buckets de stack 10bbâ€“100bb
- **Frontend â€” painel Range GTO preflop** (`Replayer.tsx`): exibido para hero actions preflop com badge de qualidade, cenÃ¡rio (RFI/vs RFI/vs 3bet), indicador in-range (âœ“/âœ—), aÃ§Ã£o jogada vs recomendada, range %, stack depth e notas profissionais

### Changed
- **`backend/api/app.py`**: `_build_replay_data()` injeta `preflop_gto` em cada hero action preflop via `analyze_preflop()`
- **`backend/leaklab/llm_explainer.py`**: prompt do LLM inclui bloco `ðŸ“Š Range GTO` para decisÃµes preflop, com cenÃ¡rio, in-range, aÃ§Ã£o recomendada e notas profissionais
- **`frontend/src/lib/api.ts`**: `ReplayStep.preflop_gto` adicionado com interface tipada completa
- Painel GTO solver (Oracle) ocultado para hero actions preflop â€” preflop usa range tables; solver apenas para postflop

---

## [v0.91.0] â€” 2026-05-08 â€” feat(UX-012): Replayer â€” cartas inseridas no pod + inlay branco maior

### Changed
- **`leaklab-replayer-v3.html`**: refinamentos visuais nas cartas e fichas
  - **Cartas 30% atrÃ¡s do pod**: cartas sÃ£o renderizadas antes do pod (z-order atrÃ¡s) e posicionadas para 70% visÃ­vel / 30% tucked atrÃ¡s do bloco do jogador; direction-aware (top seats: cartas abaixo do pod, bottom seats: acima)
  - **Inlay branco maior**: elipse central das fichas aumentada de `RX*0.42` para `RX*0.58` â€” dÃ¡ espaÃ§o confortÃ¡vel para "100" (3 dÃ­gitos) sem truncamento

---

## [v0.90.0] â€” 2026-05-08 â€” feat(UX-011): Replayer â€” fichas casino com inlay branco + botÃ£o dealer redesenhado

### Changed
- **`leaklab-replayer-v3.html`**: refinamentos visuais premium nas fichas e botÃ£o dealer
  - **Inlay branco nas fichas**: elipse central agora branca (`rgba(255,255,255,0.92)`) em todas as denominaÃ§Ãµes, com texto de valor sempre em preto `#111` â€” fidelidade a fichas de casino reais
  - **BotÃ£o dealer maior**: dimensÃµes aumentadas de 13Ã—7 para 16Ã—9 (mesmo tamanho das fichas regulares); lado agora com 12 notches alinhados (tÃ©cnica coseno, igual Ã s demais fichas)
  - **SÃ­mbolo â˜… no botÃ£o dealer**: substituiÃ§Ã£o da letra "D" por estrela de 5 pontas desenhada em SVG path (`M0,-5 L1.18,-1.62 ...`), posicionada sobre inlay branco
  - **Fichas amarelas (denom 1)**: denominaÃ§Ã£o 1 permanece amarela (`#f0d020`) â€” branca reservada exclusivamente para o chip dealer

---

## [v0.89.0] â€” 2026-05-08 â€” feat(UX-010): Replayer â€” fichas por denominaÃ§Ã£o real + cards com naipe central vÃ­vido

### Changed
- **`leaklab-replayer-v3.html`**: fichas e cartas redesenhadas com fidelidade PokerStars
  - **Fichas por denominaÃ§Ã£o real**: sistema `breakChips(amount)` decompÃµe o valor em denominaÃ§Ãµes (1000=ouro, 500=roxo, 100=preto, 25=verde, 5=vermelho, 1=branco); badge no topo mostra o valor da denominaÃ§Ã£o da ficha mais alta (e.g. 25 para verde)
  - **RemoÃ§Ã£o de `potToChips`/`betToChips`**: call sites agora passam o valor real direto para `chipStackSVG`
  - **Cartas com naipe central vÃ­vido**: sÃ­mbolo de naipe Ãºnico e dominante no centro do card (opacidade plena); fonte escalada por largura do card (`fCenter = w*0.78`); rank em negrito com sÃ­mbolo menor no canto topo-esquerdo; cores mais vÃ­vidas (#e50a0a para copas/ouros, #111 para espadas/paus)
  - **Verso das cartas**: padrÃ£o azul marinho limpo (remoÃ§Ã£o dos efeitos de diamante anteriores)
  - **Ficha Dealer premium**: botÃ£o D dourado/marfim posicionado geometricamente entre o pod e o centro da mesa (via atan2); badges de posiÃ§Ã£o (BTN/BB/SB) removidos dos pods
  - **Perspectiva isolada**: apenas o SVG de background inclina (`rotateX(9deg)`); pods, fichas e cartas permanecem flat (dois SVGs em camadas separadas)

---

## [v0.88.0] â€” 2026-05-08 â€” feat(UX-009): Replayer v3 â€” fidelidade visual PokerStars

### Changed
- **`leaklab-replayer-v3.html`**: rewrite completo com qualidade PokerStars
  - **Perspectiva 3D real**: CSS `perspective:1100px` + `rotateX(9deg)` no container SVG â€” mesa inclina visualmente como nos softwares comerciais
  - **Mesa**: feltro verde vibrante (`#40b558â†’#1d6430`) + rail grafite escuro (`#252525â†’#0e0e0e`) substituindo o rail marrom anterior
  - **Seat pods**: pill-shaped (borda arredondada `rx=26`), 128Ã—52px, posicionados no perÃ­metro do rail (fora do feltro) â€” idÃªntico ao PokerStars
  - **Hero ring**: oval branca (`rgba(255,255,255,0.88)` stroke-width=3.5) ao redor do pod do hero
  - **Fichas 3D** (`chipStackSVG`): discos empilhados com 8 cores distintas, sombra, borda interna e highlight de luz â€” aplicado no pot e nas apostas individuais
  - **Cartas maiores**: board cards 50Ã—68px com rank+suit topo-esquerdo e baixo-direito, suit central translÃºcido
  - **Dealer button**: cÃ­rculo vermelho com "D" branco no canto do pod
  - **Badge de posiÃ§Ã£o**: pill colorida (BTN=dourado, BB=vermelho, SB=laranja) sobreposta ao pod
  - **Fonte**: migraÃ§Ã£o de Rajdhani â†’ Inter para leitura mais nÃ­tida dos nomes e stacks
  - **Controles**: barra preta flat, abas de street sem bordas internas, botÃµes circulares, aba ativa vermelha

---

## [v0.87.0] â€” 2026-05-08 â€” feat(UX): Replayer premium â€” redesign visual PokerStars-quality

### Changed
- **`leaklab-replayer-v3.html`**: redesign completo
  - Mesa SVG com feltro verde (`#2e7d46 â†’ #1a5230`) e rail marrom/madeira via radial gradient
  - Hero sempre posicionado na parte inferior da mesa (rotOffset formula)
  - Nomes reais de todos os jogadores (removida anonimizaÃ§Ã£o "Villain")
  - Card backs com padrÃ£o X (linhas diagonais + losango), substituindo "?"
  - Hero ring: borda branca semitransparente ao redor do seat box do hero
  - Abas de street (`Pre-flop | Flop | Turn | River | Showdown`) substituindo dots de timeline
  - Slider de velocidade (`0.5Ã— â†’ 3Ã—`) substituindo dropdown
  - BotÃ£o BB/chips para alternar unidade de exibiÃ§Ã£o
  - Cartas posicionadas entre o seat e o centro da mesa (nÃ£o mais flutuando para fora)
- **`frontend/src/components/hud/PokerTable.tsx`**: alinhado com novo estilo
  - Feltro: radial gradient verde (`#2e7d46 â†’ #1a5230`) em vez do teal anterior
  - Rail: fundo marrom escuro (`#1a0a04`) com overlay radial (`#5a2510 â†’ #2d1005`)
  - Feltro oval com `inset-[10%]` e `rounded-[50%]` para melhor proporÃ§Ã£o
  - Hero nameplate: `ring-2 ring-white/40 shadow-[0_0_12px_rgba(255,255,255,0.18)]` (hero ring branca)

---

## [v0.86.0] â€” 2026-05-08 â€” fix(UX): dashboard sem flash ao navegar de volta â€” cache de mÃ³dulo

### Fixed
- **`Index.tsx`**: variÃ¡vel `_cachedTourns` no escopo de mÃ³dulo (fora do componente) persiste o resultado de `tournaments.list()` entre navegaÃ§Ãµes â€” na remontagem, `tourns` e `tournsLoaded` sÃ£o inicializados a partir do cache, eliminando o flash de KPI cards com dashes antes do EmptyDashboard
- **`Index.tsx`**: condiÃ§Ã£o para EmptyDashboard simplificada para `tournsLoaded && !hasData` (sem `!loading`) â€” o cache garante estado correto desde o primeiro render apÃ³s navegaÃ§Ã£o

---

## [v0.85.9] â€” 2026-05-08 â€” fix(UX): dashboard nÃ£o pisca EmptyDashboard ao navegar de volta

### Fixed
- **`Index.tsx`**: adicionado flag `tournsLoaded` (boolean) que sÃ³ vira `true` quando `tournaments.list()` retorna com sucesso â€” EmptyDashboard sÃ³ aparece quando `!loading && tournsLoaded && !hasData`, evitando que uma falha silenciosa da API (catch â†’ null) cause EmptyDashboard mesmo que o usuÃ¡rio tenha dados

---

## [v0.85.8] â€” 2026-05-08 â€” fix(UX): dashboard vazio exibe EmptyDashboard em vez dos KPI cards

### Changed
- **`Index.tsx`**: KPI cards e drift alert movidos para dentro do branch `hasData` â€” sem torneios importados, o dashboard exibe diretamente o `EmptyDashboard` com a Ã¡rea de upload, sem mostrar os cards com "â€”" e "Sem dados"
- **`Index.tsx`**: hints dos KPI cards simplificados (removidos fallbacks `t("kpis.noData")` e `t("kpis.eventsHintEmpty")` agora desnecessÃ¡rios)

---

## [v0.85.7] â€” 2026-05-08 â€” fix(UX): CareerGraphCard â€” contexto da janela de cÃ¡lculo no nÃ­vel atual

### Changed
- **`CareerGraphCard.tsx`**: adicionado rÃ³tulo "Ãºltimos 5 torneios" abaixo do percentual do nÃ­vel atual para deixar claro que o valor Ã© a mÃ©dia dos 5 torneios mais recentes (nÃ£o o histÃ³rico completo)
- **i18n** (PT-BR/EN/ES `dashboard.json`): nova chave `career.currentWindow`

---

## [v0.85.6] â€” 2026-05-06 â€” fix(UX): LeakCausalMap â€” texto legÃ­vel + tooltip no hover

### Changed
- **`LeakCausalMap.tsx`**: texto dentro dos cÃ­rculos substituÃ­do por abreviaÃ§Ã£o de 3-4 letras maiÃºsculas (`abbrev()`) com `fontSize=11` em vez do label completo ilegÃ­vel em `fontSize=9`
- **`LeakCausalMap.tsx`**: raio mÃ­nimo dos cÃ­rculos aumentado de 16 para 18px para acomodar melhor o texto
- **`LeakCausalMap.tsx`**: tooltip de hover adicionado â€” exibe label completo, contagem (nÃ—), avg_score e severity badge; posicionamento inteligente (acima/abaixo) baseado na posiÃ§Ã£o vertical do nÃ³
- **`LeakCausalMap.tsx`**: hit area invisÃ­vel (`r+6`) adicionado para facilitar o hover em cÃ­rculos menores
- **`LeakCausalMap.tsx`**: painel de detalhe ao clicar agora exibe `node.label` completo em vez de `node.id`

---

## [v0.85.5] â€” 2026-05-06 â€” feat: Replayer redesign â€” full-screen, sem scroll, Range flutuante

### Changed
- **`Replayer.tsx`**: layout migrado de `HudLayout` para layout customizado `h-dvh overflow-hidden flex-col` â€” sem barra de rolagem, mesa ocupa todo o espaÃ§o disponÃ­vel entre header e controles
- **`Replayer.tsx`**: `PokerTable` agora Ã© constrangida pela altura (`max-h-[calc(100dvh-20rem)]`) em vez da largura â€” aspect-ratio calculado automaticamente sem overflow
- **`Replayer.tsx`**: `Action Log` removido â€” painÃ©is contextuais (EV feedback, anotaÃ§Ã£o coach, showdown) movidos para faixa horizontal compacta abaixo dos controles
- **`Replayer.tsx`**: botÃ£o **Range** movido para a barra de controles (ao lado de Speed/BB); sempre visÃ­vel, desabilitado fora do preflop
- **`RangePanel.tsx`**: painel Range vira floating draggable no desktop (`fixed z-50`, arrastÃ¡vel pelo header via `onHeaderMouseDown`) e bottom sheet no mobile (backdrop + `max-h-72vh`)
- **`Replayer.tsx`**: identificaÃ§Ã£o da mÃ£o (`MÃƒO 4/68` + progress bar) centralizada na mesma linha do botÃ£o Voltar via `grid grid-cols-3`
- **`Replayer.tsx`**: default de apostas alterado para `BB` em vez de chips
- **`Replayer.tsx`**: `pb-16 md:pb-2` no container mobile para nÃ£o sobrepor a nav bar fixa
- **i18n** (`common.json` PT-BR/ES): `nav.study` encurtado para `"Estudos"` / `"Estudios"` (EN jÃ¡ era `"Study"`)
- **i18n** (`replayer.json` PT-BR/EN/ES): novas chaves `navigation.handLabel`, `navigation.prev`, `navigation.next`

---

## [v0.85.4] â€” 2026-05-06 â€” feat: campo Instagram no perfil pÃºblico do coach

### Added
- **`coach_profiles`**: nova coluna `social_instagram TEXT` â€” schema criado com a coluna e migration (`ALTER TABLE ... ADD COLUMN`) adicionada para Postgres e SQLite
- **`upsert_coach_profile`** (repositories.py): parÃ¢metro `social_instagram` adicionado ao INSERT/ON CONFLICT UPDATE
- **`/coach/profile` POST** (app.py): passa `social_instagram` do payload para o repositÃ³rio
- **`CoachProfile` interface** (api.ts): campo `social_instagram: string | null`
- **`CoachProfile.tsx`** (editor do coach): campo "Instagram" com Ã­cone `<Instagram />` apÃ³s o campo Twitter/X â€” exibiÃ§Ã£o e ediÃ§Ã£o
- **`PublicCoachProfile.tsx`** (perfil pÃºblico): Ã­cone `<Instagram />` clicÃ¡vel na seÃ§Ã£o de redes sociais, ao lado de YouTube/Twitch/Twitter

---

## [v0.85.3] â€” 2026-05-06 â€” fix: admin Users tab nÃ£o mostrava display_name dos coaches

### Fixed
- **`get_all_users` (repositories.py)**: adicionado `LEFT JOIN coach_profiles` para incluir `display_name` do perfil pÃºblico do coach na listagem de usuÃ¡rios do admin
- **`get_all_users_count`**: mesma correÃ§Ã£o para manter contagem paginada consistente com a query principal; filtros de `plan` e `role` agora usam alias `u.` para evitar ambiguidade
- **Busca por display_name**: admin pode agora buscar coaches pelo nome pÃºblico (ex: "Daniel Negreanu") no campo de busca da aba Users â€” antes sÃ³ buscava por `username` e `email`
- **`AdminDashboard.tsx` UsersTab**: coaches com `display_name` sÃ£o exibidos com o mesmo padrÃ£o da aba Finance: nome pÃºblico em destaque + `@username` abaixo â€” elimina a confusÃ£o de um coach aparecer como "coach" na aba Users e "Daniel Negreanu" na aba Finance
- **`AdminUser` interface (api.ts)**: adicionado campo `display_name: string | null`

---

## [v0.85.2] â€” 2026-05-06 â€” fix: coach inbox mostrava sÃ³ 1 conversa (filtro errado)

### Fixed
- **`CoachDashboard.tsx` `MensagensTab`**: o filtro `.filter((t) => t.last_sender_role === "student")` escondia todas as conversas onde o coach jÃ¡ havia respondido, deixando o inbox aparentemente vazio ou com 1 Ãºnica thread. Removido o filtro â€” o inbox agora mostra **todas** as conversas
- **Badge do tab "Mensagens"**: trocado `filter(last_sender_role === "student").length` por `reduce(unread_count)` para contar mensagens nÃ£o lidas reais, nÃ£o apenas threads sem resposta
- **UX**: username em negrito e preview colorido para conversas com mensagens nÃ£o lidas; prefixo `â†©` para indicar threads que aguardam resposta do coach (aluno enviou Ãºltimo); empty state atualizado para "Nenhuma conversa ainda"

---

## [v0.85.1] â€” 2026-05-06 â€” feat: UX-009 â€” exemplos visuais interativos na /docs

### Added
- **Exemplos visuais** adicionados a 9 seÃ§Ãµes da documentaÃ§Ã£o: Scoring, Top Leaks, Forma Recente, Qualidade das DecisÃµes, Performance por Street, Performance por PosiÃ§Ã£o, Colapso sob PressÃ£o, PressÃ£o ICM e Meu NÃ­vel
- **Componentes `ExampleBox`, `MiniBar`, `MiniScoreLine`, `MiniSessionBars`** em `Docs.tsx` para renderizar mini-rÃ©plicas dos indicadores reais com cores e proporÃ§Ãµes fiÃ©is
- **Chaves de exemplo i18n** em PT, EN e ES para todas as 9 seÃ§Ãµes (`exampleLabel`, `example`, `example_*` por seÃ§Ã£o)

### Fixed
- `t("leaks.critical")` e `t("form.*")` no `Docs.tsx` agora usam `td` (namespace `dashboard`) em vez do namespace `docs` â€” evita fallback silencioso para chave literal

---

## [v0.85.0] â€” 2026-05-05 â€” feat: UX-008 â€” tooltips, renome Strategic Twin e docs expandida

### Added
- **HudTooltip** adicionado a 8 cards que estavam sem: `BankrollChart`, `CareerGraphCard`, `CognitiveFailureCard`, `GhostDrillCard`, `LeakCausalMap`, `LeaksPanel`, `LevelCard`, `StrategicTwinCard`
- **11 novas seÃ§Ãµes** em `/docs` cobrindo todos os cards do dashboard: Top Leaks, Mapa Causal, Forma Recente, Qualidade das DecisÃµes, Performance por Street, Performance por PosiÃ§Ã£o, Colapso sob PressÃ£o, PressÃ£o ICM, EvoluÃ§Ã£o do Bankroll, Meu NÃ­vel â€” cada um com explicaÃ§Ã£o de objetivo, conexÃ£o com leaks e orientaÃ§Ã£o para iniciantes. DisponÃ­vel em PT, EN e ES.
- **8 chaves de tooltip** novas no `dashboard.json` (3 locales) para os cards acima

### Changed
- **`StrategicTwinCard`** renomeado de "Perfil EstratÃ©gico" para "TendÃªncias EstratÃ©gicas" (PT) / "Strategic Patterns" (EN) / "Tendencias EstratÃ©gicas" (ES) â€” elimina conflito de nome com `PlayerDnaCard` (Decision DNA)
- **`Docs.tsx`**: `SECTION_IDS` expandido de 12 para 23 seÃ§Ãµes com nav lateral totalmente funcional
- **`docs.json`** (3 locales): nav atualizado, seÃ§Ã£o `twin.title` atualizado com novo nome

---

## [v0.84.8] â€” 2026-05-05 â€” Fix: replay 404 no Sparring Mode

### Fixed
- **`backend/api/app.py`**: endpoint `/replay/<tournament_id>/<hand_id>` usava `get_tournament()` (busca por PokerStars tournament_id string), mas o Sparring envia o `id` inteiro do banco. Agora tenta `get_tournament_by_db_id` primeiro quando o parÃ¢metro Ã© numÃ©rico, com fallback para a busca por string â€” compatÃ­vel com ambos os callers.

---

## [v0.84.7] â€” 2026-05-05 â€” Fix: Sparring 500 no PostgreSQL (HAVING alias)

### Fixed
- **`backend/database/repositories.py`**: `get_sparring_hand` usava `HAVING mistakes > 0` com alias de SELECT â€” PostgreSQL nÃ£o permite aliases no HAVING (sÃ³ SQLite). SubstituÃ­do pela expressÃ£o completa `HAVING SUM(CASE WHEN ... THEN 1 ELSE 0 END) > 0` nas duas variantes da query (com e sem exclusÃ£o de mÃ£os jÃ¡ vistas).

---

## [v0.84.6] â€” 2026-05-05 â€” Fix: Ghost Table 500 no PostgreSQL

### Fixed
- **`backend/database/repositories.py`**: `get_drill_stats` usava `datetime('now', ? || ' days')` â€” concatenaÃ§Ã£o dinÃ¢mica de parÃ¢metro nÃ£o Ã© convertida pelo regex do `_adapt()`, entÃ£o `datetime()` chegava ao PostgreSQL que nÃ£o conhece essa funÃ§Ã£o. SubstituÃ­do por cutoff prÃ©-computado em Python (mesmo padrÃ£o de todas as outras funÃ§Ãµes do arquivo).

---

## [v0.84.5] â€” 2026-05-05 â€” UX: tabs na pÃ¡gina Plano de Estudos

### Changed
- **`frontend/src/pages/StudyPlan.tsx`**: conteÃºdo reorganizado em 3 tabs â€” DiagnÃ³stico, Roteiro, ExercÃ­cios â€” eliminando o scroll longo em coluna Ãºnica. KPIs ficam sempre visÃ­veis acima das tabs. Tab DiagnÃ³stico mantÃ©m o layout 8/4 col no desktop.
- **`frontend/src/i18n/locales/*/study.json`**: adicionada chave `tabs.{diagnosis,schedule,exercises}` nas 3 locales (PT-BR / EN / ES).
- Aproveitado para substituir hardcoded `"Dia {n}"` pelo i18n `t("day.label", { n })` no roteiro semanal.

---

## [v0.84.4] â€” 2026-05-05 â€” Fix /coaches 500 + remoÃ§Ã£o do card WhatsApp

### Fixed
- **`backend/database/repositories.py`**: `ROUND(AVG(CAST(rating AS REAL)), 1)` â†’ `NUMERIC` em 3 queries â€” PostgreSQL nÃ£o aceita `ROUND(double precision, integer)`, somente `ROUND(numeric, integer)`. Causava 500 em `/coaches` e no endpoint de perfil do coach.

### Removed
- **`frontend/src/pages/StudyPlan.tsx`**: card "Treinar no WhatsApp" removido junto com variÃ¡vel `waNumber` e import `MessageCircle` (ambos inutilizados apÃ³s remoÃ§Ã£o).

---

## [v0.84.3] â€” 2026-05-05 â€” Fix: 500/CORS em /study/plan apÃ³s deploy de observabilidade

### Fixed
- **`backend/api/app.py`**: `_log_request` after_request handler agora envolto em `try/except` â€” uma falha no logging nÃ£o mais substitui a resposta do endpoint por uma nova 500 sem CORS headers.
- **`backend/api/app.py`**: `sentry_sdk.init()` movido para APÃ“S `logging.basicConfig(force=True)` â€” impede que `force=True` remova o `LoggingIntegration` handler do Sentry ao inicializar depois.
- **`backend/api/app.py`**: imports do `sentry_sdk` agora dentro de `try/except ImportError` â€” app sobe normalmente em ambientes sem o SDK instalado (dev sem `pip install`).

---

## [v0.84.2] â€” 2026-05-05 â€” Auditoria de seguranÃ§a + CLAUDE.md atualizado

### Security
- **`backend/api/app.py`**: CORS configurÃ¡vel via variÃ¡vel de ambiente `ALLOWED_ORIGINS` (padrÃ£o `*` em dev; em prod, restrito aos domÃ­nios explicitamente listados). Header `Vary: Origin` adicionado quando origin-specific.
- **`backend/api/app.py`**: `/health` nÃ£o expÃµe mais tipo de banco nem `db_url_set` â€” retorna apenas `{status, version}`.
- **`backend/api/app.py`**: `/analyze/guest` recebe `@limiter.limit("10 per hour")` â€” endpoint pÃºblico agora tem rate limiting.
- **`render.yaml`**: variÃ¡vel `ALLOWED_ORIGINS` adicionada com valor padrÃ£o `https://leaklab.vercel.app` (ajustar para domÃ­nio real antes de deploy).

### Docs
- **`CLAUDE.md`**: reescrito â€” arquitetura atualizada com todas as tabelas (18), endpoints principais, pÃ¡ginas frontend, mÃ³dulos de features, variÃ¡veis de ambiente e notas de seguranÃ§a/CORS. Era crÃ­tico: estava desatualizado desde v0.45.0.

### Not changed (false positives / low risk)
- `.env` com secrets: `backend/.env` estÃ¡ corretamente no `.gitignore`; `frontend/.env` contÃ©m apenas `pk_test_*` (Stripe publishable key â€” pÃºblico por design).
- JWT secret: `auth.py` jÃ¡ levanta `RuntimeError` em produÃ§Ã£o se `LEAKLAB_SECRET` nÃ£o estiver setado.
- `dangerouslySetInnerHTML` em `Docs.tsx`: strings vÃªm de JSON bundlado no build, sem input de usuÃ¡rio.

---

## [v0.84.1] â€” 2026-05-04 â€” Suporte: badge no header + fix estado reply no admin

### Fixed
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: `TicketRow.handleReply` chama `setOpen(false)` antes de invalidar queries â€” textarea some imediatamente ao confirmar envio, exibindo o card de "Resposta enviada".

### Changed
- **`frontend/src/components/hud/HudHeader.tsx`**: botÃ£o `LifeBuoy` adicionado no header (visÃ­vel a todos os usuÃ¡rios nÃ£o-admin). Badge vermelho aparece quando hÃ¡ tickets com resposta do admin. Clicar abre `SupportModal` diretamente na aba "Minhas mensagens" quando hÃ¡ respostas pendentes. `SupportModal` renderizado inline no header (igual ao drawer do coach).
- **`frontend/src/pages/Index.tsx`**: badge de suporte do footer removido para nÃ£o-admin (movido para o header). Footer mantÃ©m apenas o badge de tickets abertos para admin.

---

## [v0.84.0] â€” 2026-05-04 â€” Suporte bidirecional: aluno visualiza resposta do admin

### Added
- **`backend/api/app.py`**: `GET /support/my-tickets` â€” retorna todos os tickets do usuÃ¡rio logado (com admin_reply e replied_at). `GET /support/my-tickets/unread` â€” contagem de tickets com resposta do admin.
- **`frontend/src/components/hud/SupportModal.tsx`**: reescrito com duas abas â€” "Nova mensagem" (formulÃ¡rio) e "Minhas mensagens" (histÃ³rico de tickets + respostas do admin). Badge na aba Minhas mensagens quando hÃ¡ respostas. Abre direto na aba inbox quando `initialTab="inbox"`.
- **`frontend/src/pages/Index.tsx`**: badge no botÃ£o Suporte do footer para alunos nÃ£o-admin quando hÃ¡ tickets respondidos. Modal abre na aba inbox automaticamente nesse caso. `useQuery` para `myUnreadCount` com polling de 2min.
- **`frontend/src/lib/api.ts`**: interface `MyTicket` + mÃ©todos `support.myTickets()` e `support.myUnreadCount()`.

---

## [v0.83.9] â€” 2026-05-04 â€” Admin: exclusÃ£o permanente de usuÃ¡rios com confirmaÃ§Ã£o

### Added
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: botÃ£o de lixeira por linha na aba UsuÃ¡rios. Abre `DeleteUserModal` com nome/email do alvo, campo de senha administrativa e aviso de irreversibilidade. Senha Ã© verificada no backend antes de qualquer exclusÃ£o.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: `DeleteUserModal` â€” modal com Ã­cone de alerta, input de senha com `autoFocus`, feedback de erro inline, botÃ£o "Excluir definitivamente" desabilitado atÃ© senha digitada.
- **`backend/api/app.py`**: `DELETE /admin/users/<uid>` â€” exige `admin_password` no body, verifica credenciais do admin via `verify_password`, bloqueia auto-exclusÃ£o, deleta todos os dados do usuÃ¡rio em cascata.
- **`backend/database/repositories.py`**: `delete_user_admin(user_id)` â€” remove decisÃµes, torneios, cache LLM, tickets de suporte e o registro `users` em cascata, dentro de uma Ãºnica transaÃ§Ã£o.
- **`frontend/src/lib/api.ts`**: `adminDashboard.deleteUser(id, adminPassword)` mÃ©todo adicionado.

---

## [v0.83.8] â€” 2026-05-04 â€” Badge de tickets abertos + sistema de resposta no admin

### Added
- **`frontend/src/pages/Index.tsx`**: badge vermelho no botÃ£o "Suporte" do footer mostrando contagem de tickets abertos (admin only). Polling a cada 2 minutos via `useQuery`.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: aba "Suporte" agora exibe lista completa de tickets com sistema de resposta inline â€” textarea de reply, botÃ£o de envio, toggle "editar resposta", badges de status (open=vermelho, replied=azul). Consulta e invalida `admin-support-count` apÃ³s resposta.
- **`backend/api/app.py`**: `POST /admin/support-tickets/<id>/reply` â€” atualiza `admin_reply`, `status='replied'` e `replied_at` (require_admin). `GET /admin/support-tickets/count` â€” retorna `{ open: N }` (require_admin).
- **`backend/database/schema.py`**: colunas `admin_reply TEXT` e `replied_at` adicionadas Ã  tabela `support_tickets` em SQLite e PostgreSQL.
- **`frontend/src/lib/api.ts`**: mÃ©todos `support.unreadCount()` e `support.replyTicket(id, reply)` adicionados ao namespace `support`.

---

## [v0.83.6] â€” 2026-05-04 â€” Footer: remoÃ§Ã£o do status bar + modal de suporte

### Changed
- **`frontend/src/pages/Index.tsx`**: footer simplificado â€” removido "ENC: AES-256 â€¢ LATENCY: 14ms â€¢ SESSION_LOCKED" e link "Status". Mantidos apenas "Docs" e "Suporte". Suporte agora abre um modal em vez de ser um link morto.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: removidas chaves `sessionLocked` e `status_page`; adicionadas chaves `supportModal.*` com tÃ­tulo, campos, categorias e mensagens de feedback nas 3 locales.

### Added
- **`frontend/src/components/hud/SupportModal.tsx`**: modal de contato com seletor de categoria (bug, dÃºvida, sugestÃ£o, cobranÃ§a, outro), campo de assunto e mensagem (2000 chars), prÃ©-preenchimento de usuÃ¡rio/email, feedback de sucesso e erro. i18n nas 3 locales.
- **`backend/database/schema.py`**: tabela `support_tickets` (id, user_id, category, subject, message, status, created_at) criada em SQLite e PostgreSQL.
- **`backend/api/app.py`**: `POST /support/contact` â€” salva ticket no banco, exige mensagem nÃ£o-vazia, requer autenticaÃ§Ã£o.

---

## [v0.83.5] â€” 2026-05-04 â€” Bugfix: narrativas IA nÃ£o atualizam ao trocar idioma

### Fixed
- **`frontend/src/pages/Index.tsx`**: adicionado `useEffect` separado com dependÃªncia `[i18n.language]` que re-busca apenas os 4 endpoints de narrativa sensÃ­veis ao idioma (`leakGraph`, `career`, `cognitiveFailures`, `strategicTwin`) quando o locale muda. Guard `langMounted` evita double-fetch no mount inicial. Os demais dados (evolution, breakdown, tournaments, etc.) nÃ£o sÃ£o re-buscados desnecessariamente.

---

## [v0.83.4] â€” 2026-05-04 â€” Bugfix: termos de poker em inglÃªs nos prompts LLM

### Fixed
- **`backend/leaklab/llm_explainer.py`**: adicionada constante `_POKER_TERMS_EN` com lista canÃ´nica de termos tÃ©cnicos (fold, call, raise, bet, check, jam, preflop, flop, turn, river, hand, spot, equity, ICM, M-ratio, stack, pot odds, range, 3-bet, c-bet, board, position, IP, OOP, shove, reshove, open, limp, squeeze). InstruÃ§Ã£o injetada em todos os system prompts: decisÃ£o, resumo de torneio, comparaÃ§Ã£o, sessÃ£o review, coach chat e sparring. Elimina traduÃ§Ãµes indevidas como "ruas" (â†’ turn/river), "mÃ£o" (â†’ hand), "tabuleiro" (â†’ board) no texto gerado pela IA.
- **`backend/leaklab/llm_explainer.py`**: `_LANG_INSTRUCTIONS` atualizado para incluir a clÃ¡usula de poker terms nas 3 locales (PT-BR e ES).

---

## [v0.83.3] â€” 2026-05-04 â€” Bugfix: terminologia tÃ©cnica e truncamento na AnÃ¡lise Comparativa

### Fixed
- **`backend/leaklab/llm_explainer.py`**: `max_tokens` da narrativa comparativa aumentado de 100 â†’ 350 (texto era cortado no meio da segunda frase).
- **`backend/leaklab/llm_explainer.py`**: prompts de comparaÃ§Ã£o, sessÃ£o e coach chat substituem `standard_pct`/`avg_score`/`clear_pct` por `Standard%`/`Score mÃ©dio`/`Erros claros` â€” o LLM nÃ£o mais repete nomes de variÃ¡veis no texto gerado.
- **`backend/leaklab/llm_explainer.py`**: corrigida interpolaÃ§Ã£o dupla-chave `{{avg_score:.4f}}` â†’ `{avg_score:.4f}` no prompt do plano de estudos â€” mÃ©tricas reais agora chegam ao LLM em vez de placeholders literais.
- **`backend/leaklab/llm_explainer.py`**: template fallback `_template_comparison` e string de carreira usam `Standard%` em vez de `standard_pct`.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seÃ§Ã£o TrajetÃ³ria de Carreira substituiu todos os `standard_pct` por `Standard%` (em negrito) nos valores de parÃ¡grafo e tabela.

---

## [v0.83.2] â€” 2026-05-04 â€” Bugfix: import mÃºltiplo de torneios no EmptyDashboard

### Fixed
- **`frontend/src/components/hud/EmptyDashboard.tsx`**: refatorado para usar `useUploadQueue` (mesmo hook do HudHeader) em vez de `processFile` prÃ³prio. Agora aceita mÃºltiplos arquivos via drag-and-drop e via seletor (`multiple`). O painel de fila com status por arquivo Ã© exibido durante o processamento. Reset `e.target.value = ""` no `onChange` para permitir re-seleÃ§Ã£o do mesmo arquivo.

---

## [v0.83.1] â€” 2026-05-04 â€” Sprint AY: Mobile audit + responsividade

### Fixed
- **`frontend/src/components/hud/DraggableCard.tsx`**: drag handle sempre visÃ­vel em mobile (`opacity-100 md:opacity-0 md:group-hover:opacity-100`); tamanho aumentado (`px-3 py-1 / size-4`) para alvo de toque adequado; `touch-none` para impedir scroll acidental durante drag.
- **`frontend/src/pages/GhostTable.tsx`**: botÃµes de aÃ§Ã£o com `min-h-[44px]` â€” atende ao mÃ­nimo de toque iOS/Android HIG (era ~42px).
- **`frontend/src/pages/Sparring.tsx`**: mesmo fix de `min-h-[44px]` nos botÃµes de aÃ§Ã£o contextuais.
- **`frontend/src/components/hud/HudHeader.tsx`**: `LanguageSwitcher` removido do `hidden sm:` â€” seletor de idioma agora acessÃ­vel em mobile (era invisÃ­vel em telas < 640px).
- **`frontend/src/pages/StudentProfile.tsx`**: grids de 2 colunas nos formulÃ¡rios de dados do jogador alterados para `grid-cols-1 sm:grid-cols-2` â€” campos nÃ£o colapsam em telas < 400px.

---

## [v0.83.0] â€” 2026-05-04 â€” Sprint AX: Onboarding para novos usuÃ¡rios

### Added
- **`backend/database/schema.py`**: coluna `onboarding_completed` (BOOLEAN, default FALSE) adicionada Ã  tabela `users` via migraÃ§Ã£o em Postgres e SQLite.
- **`backend/database/repositories.py`**: `set_onboarding_completed(user_id)` â€” marca o onboarding como concluÃ­do no banco.
- **`backend/api/app.py`**: `POST /player/onboarding/complete` â€” endpoint para registrar conclusÃ£o ou skip do onboarding. Campo `onboarding_completed` incluÃ­do no payload de `GET /auth/me`.
- **`frontend/src/lib/api.ts`**: campo `onboarding_completed?: boolean` adicionado Ã  interface `UserProfile`; `auth.completeOnboarding()` chama `POST /player/onboarding/complete`.
- **`frontend/src/components/hud/OnboardingModal.tsx`**: modal multi-step (4 passos) com stepper visual, Ã­cones Lucide por etapa, botÃµes Pular/Voltar/PrÃ³ximo, CTA final navega para `/analyze`. Ao fechar (skip ou finish) chama `completeOnboarding()` e `refreshUser()` para nÃ£o exibir novamente.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/onboarding.json`**: namespace `onboarding` completo nas 3 locales â€” passos welcome, upload, train, ready.
- **`frontend/src/i18n/index.ts`**: namespace `onboarding` registrado nas 3 locales.

### Changed
- **`frontend/src/pages/Index.tsx`**: estado `showOnboarding` inicializado com `!user?.onboarding_completed`; `<OnboardingModal>` renderizado condicionalmente ao lado do `<AcceptCoachModal>`.

---

## [v0.82.3] â€” 2026-05-04 â€” Docs: Pressure Mode + Sparring rotation + BACKLOG atualizado

### Changed
- **`frontend/src/pages/Docs.tsx`**: seÃ§Ã£o Ghost Table agora renderiza `ghost.p5` â€” descriÃ§Ã£o do Pressure Mode (cronÃ´metro 30s, anel SVG, fold automÃ¡tico, badge ðŸ”¥ de streak).
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: adicionada chave `ghost.p5` nas 3 locales descrevendo o Pressure Mode. Chave `sparring.p2` atualizada para mencionar o mecanismo de rotaÃ§Ã£o de mÃ£os por sessÃ£o (exclusÃ£o de mÃ£os jÃ¡ jogadas, ciclo de 90 dias).
- **`BACKLOG.md`**: Sprints AQâ€“AW e bugfixes v0.81.1â€“v0.82.2 movidos para tabela de concluÃ­dos. SeÃ§Ã£o "Em Aberto" atualizada: FEAT-14/15/16 (entregues) removidos; FEAT-17 (Onboarding) e FEAT-18 (Mobile audit) adicionados como prÃ³ximas sprints AX e AY.

---

## [v0.82.2] â€” 2026-05-04 â€” Fix: perfil i18n completo + telefone no perfil + remoÃ§Ã£o WhatsApp Coaching

### Changed
- **`frontend/src/pages/StudentProfile.tsx`**: seÃ§Ã£o WhatsApp Coaching removida (integraÃ§Ã£o Meta adiada). Campo "Telefone / WhatsApp" movido para dentro de "Dados do Jogador" â€” salvo em conjunto com os demais dados no mesmo botÃ£o; saves chamadom `profileApi.update()` + `authApi.updatePhone()`.
- **`frontend/src/pages/StudentProfile.tsx`**: i18n completo â€” todos os textos hardcoded da pÃ¡gina substituÃ­dos por `t()`. Sub-componentes `CoachReviewWidget`, `CoachDiscoveryCard` e `NoCoachDiscovery` agora usam `useTranslation("profile")` e nÃ£o tÃªm nenhum string hardcoded em PT-BR.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/profile.json`**: adicionados grupos `email.*`, `password.*` (labels, placeholders, botÃµes, toasts) e `coach.*` (review, discovery, unlink) â€” cobertura total da pÃ¡gina em PT/EN/ES. Chaves `whatsapp.*` e `sections.whatsapp` removidas.

---

## [v0.82.1] â€” 2026-05-04 â€” Fix: perfil demogrÃ¡fico visÃ­vel e editÃ¡vel na pÃ¡gina de Perfil

### Added
- **`frontend/src/pages/StudentProfile.tsx`**: nova seÃ§Ã£o "Dados do Jogador" no topo da pÃ¡gina de perfil â€” exibe e permite editar todos os 7 campos demogrÃ¡ficos (ano de nascimento, paÃ­s, estado, cidade, anos de experiÃªncia, modalidade, faixa de buy-in) mesmo quando ainda nÃ£o preenchidos. Barra de progresso mostra quantos dos 5 campos essenciais estÃ£o completos; fica verde ao completar todos.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/profile.json`**: namespace `demo.*` adicionado nas 3 locales com todas as labels, opÃ§Ãµes de select e mensagens de status.

### Fixed
- **Dados do jogador preenchidos mas invisÃ­veis**: os campos demogrÃ¡ficos sÃ³ existiam no `ProfileCompletionCard` do dashboard (descartÃ¡vel e que some apÃ³s o preenchimento). Agora ficam sempre acessÃ­veis via `/profile`, com valores carregados do backend e salvos via `PATCH /player/profile`.

---

## [v0.82.0] â€” 2026-05-04 â€” Sprint AW: Ghost Table Pressure Mode + Sparring hand rotation

### Added
- **`frontend/src/pages/GhostTable.tsx`**: **Pressure Mode** â€” toggle na intro desbloqueia modo cronometrado: 30 s por decisÃ£o, timeout dispara fold automÃ¡tico via `submitRef.current` (sem stale closure), streak de acertos exibido com badge ðŸ”¥ durante a sessÃ£o e tile dedicado na tela de conclusÃ£o.
- **`frontend/src/pages/GhostTable.tsx`**: `TimerRing` â€” anel SVG circular de contagem regressiva com transiÃ§Ã£o CSS suave; vermelho quando â‰¤ 10 s. BotÃµes de aÃ§Ã£o bloqueados apÃ³s timeout atÃ© o prÃ³ximo spot.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/ghost.json`**: chaves `pressure.toggle`, `pressure.desc`, `pressure.timedOut`, `pressure.streakLabel` adicionadas nas 3 locales.
- **`backend/database/repositories.py`**: parÃ¢metro `exclude_hand_ids: list` em `get_sparring_hand` â€” filtra mÃ£os jÃ¡ vistas na sessÃ£o; se todas as mÃ£os foram excluÃ­das, retorna o ciclo desde o inÃ­cio.
- **`backend/api/app.py`**: endpoint `GET /player/sparring/hand` passa `exclude_hand_ids` (comma-separated) para o repositÃ³rio.
- **`frontend/src/lib/api.ts`**: `sparring.hand()` aceita `exclude_hand_ids?: string[]` e os envia como query param.
- **`frontend/src/pages/Sparring.tsx`**: `seenHandIds` ref â€” rastreia IDs de mÃ£os jÃ¡ jogadas na sessÃ£o; `loadHand()` passa a lista para excluir ao buscar a prÃ³xima mÃ£o, garantindo rotaÃ§Ã£o mesmo com mÃºltiplas chamadas de "New Hand".

### Fixed
- **Sparring sempre exibia a mesma mÃ£o**: `get_sparring_hand` nÃ£o tinha mecanismo de exclusÃ£o â€” `New Hand` sempre retornava a mÃ£o com o pior erro. Agora cada mÃ£o jogada Ã© adicionada Ã  lista de exclusÃ£o e a prÃ³xima chamada traz uma mÃ£o diferente.

---

## [v0.81.1] â€” 2026-05-04 â€” Bugfix: i18n sparring + test suite verde

### Fixed
- **`frontend/src/i18n/locales/{pt-BR,en,es}/sparring.json`**: chaves `arenaLabel` e `arenaDesc` adicionadas nas 3 locales â€” eram usadas pelo card de intro da fase idle do Sparring mas estavam ausentes nos arquivos de traduÃ§Ã£o (as chaves retornavam o prÃ³prio nome da chave em vez do texto traduzido).
- **`backend/tests/run_all_tests.py`**: substituÃ­do `python3` por `sys.executable` + adicionado `encoding='utf-8'` â€” `python3` no Windows apontava para Python 3.10 (sem suporte a backslash em f-strings), causando falsos negativos em 25 testes da suite de subscription.
- **`backend/tests/test_api_endpoints.py`**: 3 testes de coach registration atualizados para o novo fluxo `/auth/coach-apply` (coaches nÃ£o se registram mais diretamente via `/auth/register`; login retorna 403 `coach_pending` atÃ© aprovaÃ§Ã£o admin).
- **`backend/tests/test_subscription.py`**: 2 testes de webhook atualizados â€” `test_webhook_no_secret_allowed` e `test_webhook_subscription_deleted_downgrades` agora patcham `api.app.STRIPE_WEBHOOK_SECRET` para `""` evitando interferÃªncia do `.env` local; comportamento esperado corrigido para refletir a implementaÃ§Ã£o atual do endpoint.

---

## [v0.81.0] â€” 2026-05-04 â€” Sprint AV: PÃ¡gina Treinos + BotÃµes contextuais

### Added
- **`frontend/src/pages/Training.tsx`**: nova pÃ¡gina `/training` â€” landing de treino com dois cards (Ghost Table e Sparring Mode), esquema visual primÃ¡rio vs amber, lista de features, CTAs diretos.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/training.json`**: namespace `training` com todas as strings da pÃ¡gina nas 3 locales.
- **`frontend/src/i18n/index.ts`**: namespace `training` registrado nas 3 locales.
- **`frontend/src/App.tsx`**: rota `/training` adicionada (ProtectedRoute).

### Changed
- **`frontend/src/components/hud/HudHeader.tsx`**: `TrainingDropdown` removido â€” substituÃ­do por `NavLink` simples `/training` com `activePaths: ["/training", "/ghost", "/sparring"]`; cÃ³digo simplificado (sem `TrainingDropdown`, sem `ChevronDown`, sem `isDropdown`).
- **`frontend/src/pages/Sparring.tsx`**: botÃµes de aÃ§Ã£o contextuais â€” `facing_bet > 0` exibe `[fold, call, raise, jam]`; `facing_bet == 0` exibe `[fold, check, bet, jam]`; `facing_bet == null` exibe todos os 6 (fallback). Grid adapta de 4 para 6 colunas conforme o conjunto.

---

## [v0.80.0] â€” 2026-05-04 â€” Sprint AU: PokerTable visual no Sparring

### Changed
- **`frontend/src/pages/Sparring.tsx`**: substituiÃ§Ã£o da exibiÃ§Ã£o plana de cartas pelo componente `PokerTable` completo â€” herÃ³i posicionado na parte inferior da mesa, vilÃµes ao redor (N baseado em `num_players`), board real, pot real, stacks em BB. Exibido tanto na fase *playing* quanto na fase *feedback* (mesa congelada como contexto). Remove import direto de `PlayingCard` (agora encapsulado no `PokerTable`).

### Added
- **`frontend/src/pages/Sparring.tsx`**: helper `buildSparringSeats(step, heroCards)` â€” constrÃ³i o array `Seat[]` com herÃ³i (cartas reais + stack real) e vilÃµes (cartas viradas + 100 BB estimado).

---

## [v0.79.0] â€” 2026-05-04 â€” Sprint AT: Menu "Treinos" + Sparring Visual

### Added
- **`frontend/src/components/hud/HudHeader.tsx`**: componente `TrainingDropdown` â€” agrupamento de Ghost Table e Sparring sob um menu "Treinos/Training/Entrenamiento" com dropdown no desktop; mobile mantÃ©m item Ãºnico "Treinos" â†’ `/ghost` com estado ativo cobrindo ambas as rotas (`/ghost`, `/sparring`).
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: chave `nav.training` adicionada ("Treinos" / "Training" / "Entrenamiento").

### Changed
- **`frontend/src/pages/Sparring.tsx`**: redesign visual completo para diferenciar do Ghost Table â€” esquema de cores amber/laranja, componente `StreetTimeline` (cadeia horizontal de pontos com Ã­cones Flame/CheckCircle2/XCircle), componente `HandRecap` (histÃ³rico compacto de decisÃµes anteriores), arena intro card com gradiente e Ã­cone `Swords`.

---

## [v0.78.0] â€” 2026-05-04 â€” Sprint AS: AI Sparring Mode

### Added
- **`backend/database/repositories.py`**: `get_sparring_hand(user_id, hand_id, tournament_id)` â€” auto-seleciona a mÃ£o com pior erro nos Ãºltimos 90 dias (priorizando mÃ£os com mÃºltiplas decisÃµes), retorna todas as decisÃµes em ordem cronolÃ³gica com contexto completo.
- **`backend/api/app.py`**: `GET /player/sparring/hand?hand_id=&tournament_id=` â€” serve mÃ£o para o modo Sparring.
- **`frontend/src/lib/api.ts`**: interfaces `SparringStep` e `SparringHand`; `sparring.hand(hand_id?, tournament_id?)`.
- **`frontend/src/pages/Sparring.tsx`**: nova pÃ¡gina `/sparring` com 4 fases â€” playing (cartas + botÃµes de aÃ§Ã£o), feedback (correto/errado, best action, delta, SRS, anÃ¡lise engine), summary (precisÃ£o geral, linha por decisÃ£o), idle. Reutiliza `PlayingCard`, `drill.submit`, `drill.analysis` e SRS do Ghost Table.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/sparring.json`**: namespace `sparring` com todas as strings da pÃ¡gina (PT/EN/ES).
- **`frontend/src/i18n/index.ts`**: namespace `sparring` registrado nas 3 locales.
- **`frontend/src/pages/Docs.tsx`**: seÃ§Ã£o `sparring` com tabela de fases.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seÃ§Ã£o `sparring` na docs e chave `nav.sparring`.

### Changed
- **`frontend/src/App.tsx`**: rota `/sparring` adicionada (ProtectedRoute).
- **`frontend/src/components/hud/HudHeader.tsx`**: item "Sparring" adicionado ao nav de players.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/common.json`**: chave `nav.sparring` adicionada.

---

## [v0.77.0] â€” 2026-05-04 â€” Sprint AR: Personal Strategic Twin

### Added
- **`backend/database/repositories.py`**: `get_strategic_twin_profile(user_id, days=180)` â€” agrega spots por `(street, best_action, icm_pressure)`, calcula taxa de erro por spot, retorna taxa mÃ©dia do jogador, top 5 spots por volume e top 5 spots mais custosos (error_rate > avg + 10%, mÃ­n. 5 decisÃµes).
- **`backend/leaklab/llm_explainer.py`**: `generate_twin_narrative(profile, lang)`, `_call_twin_narrative`, `_template_twin` â€” narrativa em 1Âª pessoa preditiva (2-3 frases) com o spot mais custoso, tendÃªncia revelada e ajuste concreto; suporte PT/EN/ES; fallback determinÃ­stico.
- **`backend/api/app.py`**: `GET /player/strategic-twin?lang=&days=` â€” retorna perfil + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `TwinSpot` e `StrategicTwinProfile`; `metrics.strategicTwin(lang, days)`.
- **`frontend/src/components/hud/StrategicTwinCard.tsx`**: card lateral com taxa mÃ©dia de erro, lista dos 3 spots mais custosos (barra de erro vs linha de mÃ©dia do jogador, delta colorido, volume de decisÃµes) e narrativa LLM. Totalmente i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seÃ§Ã£o `strategicTwin` com aÃ§Ãµes, streets, nÃ­veis de ICM e labels de UI.

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: `"twin"` adicionado ao tipo `SidebarSection`; incluÃ­do no `DEFAULT_LAYOUT.sidebar` ao final da lista â€” merge automÃ¡tico garante apariÃ§Ã£o para usuÃ¡rios existentes.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.strategicTwin(i18n.language)` no carregamento; renderiza `StrategicTwinCard` como card draggable no sidebar.

---

## [v0.76.0] â€” 2026-05-04 â€” Sprint AQ+: Dashboard UX Redesign

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: tipos `MainSection` e `SidebarSection` reescritos para novo modelo de layout. `MainSection` agora Ã© `"quality_row" | "bankroll_row" | "street_row" | "dna_row" | "drill_row" | "insight_row"` (BankrollChart e PlayerDnaCard viram rows sortÃ¡veis). `SidebarSection` reduzido a `"leaks" | "causal_map" | "level"` (3 cards essenciais). `DEFAULT_LAYOUT` atualizado; merge automÃ¡tico migra layouts salvos de usuÃ¡rios existentes.
- **`frontend/src/pages/Index.tsx`**: funÃ§Ã£o `renderMainRow(id)` unifica renderizaÃ§Ã£o das 6 rows do main column, incluindo `insight_row` que exibe `CareerGraphCard` e `CognitiveFailureCard` lado a lado em grid 2-col. `renderSidebarCard(id)` reduzido a 3 cards. `BankrollChart` e `PlayerDnaCard` agora sÃ£o rows sortÃ¡veis (`bankroll_row`, `dna_row`) em vez de injetados entre rows via Ã­ndice. Card `ai_confidence` removido. Import `HudTooltip` removido (era unused apÃ³s remoÃ§Ã£o do card).

### Removed
- Card `ai_confidence` removido do layout â€” nÃ£o havia dados suficientes para preencher de forma significativa.
- `career` e `cognitive_failures` removidos do sidebar â€” movidos para `insight_row` no main column onde ficam lado a lado com espaÃ§o adequado (~700px cada).

---

## [v0.75.0] â€” 2026-05-04 â€” Sprint AQ: Cognitive Failure Mapper

### Added
- **`backend/leaklab/cognitive_mapper.py`**: detector de 5 padrÃµes cognitivo-emocionais sobre sequÃªncias de decisÃµes â€” `revenge_aggression` (agressividade apÃ³s folds corretos), `fear_folding` (folds incorretos apÃ³s blowups), `sunk_cost` (calls ruins em mÃºltiplas streets), `entitlement_tilt` (erros apÃ³s boa sequÃªncia) e `compensation_call` (calls ruins apÃ³s fold correto). Usa janelas deslizantes de 5â€“10 decisÃµes por torneio; retorna padrÃµes ordenados por frequÃªncia com severity (high/medium/low).
- **`backend/database/repositories.py`**: `get_cognitive_failure_report(user_id, days=90)` â€” consulta decisÃµes dos Ãºltimos N dias ordenadas por torneio + id, e chama `analyze_cognitive_failures`.
- **`backend/leaklab/llm_explainer.py`**: `generate_cognitive_narrative(patterns, lang)`, `_call_cognitive_narrative`, `_template_cognitive` â€” narrativa de 2-3 frases com o padrÃ£o dominante, custo em EV e um hÃ¡bito corretivo; suporte multilÃ­ngue (PT/EN/ES); fallback determinÃ­stico.
- **`backend/api/app.py`**: `GET /player/cognitive-failures?lang=&days=` â€” retorna relatÃ³rio + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `CognitivePattern` e `CognitiveFailureData`; `metrics.cognitiveFailures(lang, days)`.
- **`frontend/src/components/hud/CognitiveFailureCard.tsx`**: card com lista de padrÃµes detectados (nome traduzido, severity badge colorido, barra de frequÃªncia, descriÃ§Ã£o), narrativa LLM e estados de loading/empty. Totalmente i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seÃ§Ã£o `cognitiveFailure` com 5 nomes de padrÃ£o, 5 descriÃ§Ãµes, 3 nÃ­veis de severity.

### Changed
- **`frontend/src/hooks/useDashboardLayout.ts`**: adicionado `"cognitive_failures"` ao tipo `SidebarSection`; incluÃ­do no `DEFAULT_LAYOUT` entre `"career"` e `"ai_confidence"`.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.cognitiveFailures(i18n.language)` no carregamento; renderiza `CognitiveFailureCard` como card draggable no sidebar.

---

## [v0.74.0] â€” 2026-05-04 â€” Sprint AP: Strategic Career Graph

### Added
- **`backend/database/repositories.py`**: `get_career_projection(user_id)` â€” regressÃ£o linear pura (sem numpy) sobre histÃ³rico completo de `standard_pct`; calcula slope, projeÃ§Ã£o por torneio, datas estimadas para cada um dos 7 nÃ­veis, leaks bloqueadores (top 3, Ãºltimos 90d), e sÃ©ries de sparkline (histÃ³rico + projeÃ§Ã£o curta).
- **`backend/leaklab/llm_explainer.py`**: `generate_career_narrative(projection, lang)` â€” narrativa de 2-3 frases sobre tendÃªncia, tempo para prÃ³ximo nÃ­vel e leak prioritÃ¡rio; template fallback se LLM indisponÃ­vel; suporte multilÃ­ngue (PT/EN/ES).
- **`backend/api/app.py`**: `GET /player/career?lang=` â€” retorna projeÃ§Ã£o + narrativa LLM.
- **`frontend/src/lib/api.ts`**: interfaces `CareerProjection` e `CareerMilestone`; `metrics.career(lang)`.
- **`frontend/src/components/hud/CareerGraphCard.tsx`**: card com sparkline SVG (linha histÃ³rica sÃ³lida + projeÃ§Ã£o tracejada), nÃ­vel atual vs. prÃ³ximo, milestones projetados, leaks bloqueadores e narrativa LLM. Totalmente i18n (PT/EN/ES).
- **`frontend/src/hooks/useDashboardLayout.ts`**: adicionado `"career"` como `SidebarSection`; incluÃ­do no `DEFAULT_LAYOUT` entre `"level"` e `"ai_confidence"`.
- **`frontend/src/pages/Index.tsx`**: busca `metrics.career(i18n.language)` no carregamento; renderiza `CareerGraphCard` como card draggable no sidebar.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: seÃ§Ã£o `career` com 15 chaves de traduÃ§Ã£o.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/docs.json`**: seÃ§Ã£o `career` + chave `nav.career` adicionadas.
- **`frontend/src/pages/Docs.tsx`**: nova seÃ§Ã£o `/docs#career` com tabela de termos e descriÃ§Ã£o da metodologia de projeÃ§Ã£o.

---

## [v0.73.0] â€” 2026-05-04 â€” Bugfix: i18n level names, LeakCausalMap narrative, drag handle

### Fixed
- **`frontend/src/components/hud/LevelCard.tsx`**: nomes de nÃ­vel agora sÃ£o traduzidos (PT/EN/ES) via chaves `level.names.*` no namespace `dashboard`; mapeamento `LEVEL_SLUG` converte strings PT do backend em slugs canÃ´nicos para cores, Ã­cones e i18n.
- **`frontend/src/i18n/locales/{pt-BR,en,es}/dashboard.json`**: adicionada seÃ§Ã£o `level.names` com os 7 nomes de nÃ­vel em cada idioma.
- **`backend/leaklab/llm_explainer.py`**: `explain_leak_causality` e `_call_llm_causality` aceitam `lang` param â€” o prompt agora instrui o LLM a responder no idioma correto (PT/EN/ES); `max_tokens` aumentado de 150 para 280 para evitar truncamento da narrativa.
- **`backend/database/repositories.py`**: `get_leak_graph_data` aceita `lang` param e o passa para o LLM.
- **`backend/api/app.py`**: endpoint `GET /player/leak-graph` agora lÃª `?lang=` da query string.
- **`frontend/src/lib/api.ts`**: `metrics.leakGraph(days, lang)` passa idioma para o endpoint.
- **`frontend/src/pages/Index.tsx`**: `leakGraph` carregado com `i18n.language` para narrativa no idioma correto.
- **`frontend/src/components/hud/DraggableCard.tsx`**: grip handle movido para `left-3` (era `right-3`) â€” evita sobreposiÃ§Ã£o com conteÃºdo como "90d" no canto direito do header.

---

## [v0.72.0] â€” 2026-05-04 â€” Sprint i18n: cobertura completa de novos componentes

### Changed
- **`frontend/src/pages/Docs.tsx`**: substituÃ­dos todos os placeholders por chaves i18n corretas â€” linhas da Ghost Table usam `t("ghost.result_hit/miss/mastery")`, termo de coaching usa `t("coaching.term_override")`, nomes de nÃ­vel usam `t("gamification.level_*")`; removida importaÃ§Ã£o `tc` desnecessÃ¡ria.
- **`frontend/src/components/hud/LeakCausalMap.tsx`**: adicionado `useTranslation("dashboard")`; substituÃ­dos todos os 5 textos hardcoded por chaves `t("leakCausalMap.*")` â€” tÃ­tulo, aria-label, "Co-ocorre com", "limpar seleÃ§Ã£o", labels de severidade, "espessura = correlaÃ§Ã£o".
- **`frontend/src/components/hud/HudHeader.tsx`**: tÃ­tulo do drawer de chat do coach agora usa `t("coachMessages")` (fallback quando `coach_username` nÃ£o estÃ¡ disponÃ­vel); `title` do botÃ£o badge tambÃ©m i18n.
- **`frontend/src/components/hud/DraggableCard.tsx`**: tooltip "Arrastar para reordenar" agora usa `tc("actions.dragToReorder")`.
- **`frontend/src/pages/Index.tsx`**: botÃ£o "Restaurar padrÃ£o" agora usa `tc("actions.resetLayout")`.

---

## [v0.71.0] â€” 2026-05-04 â€” Sprint AG: FEAT-12 PÃ¡gina de DocumentaÃ§Ã£o

### Added
- **`frontend/src/pages/Docs.tsx`**: pÃ¡gina `/docs` estilo wiki com 8 seÃ§Ãµes â€” Sistema de Scoring, Indicadores, Fases de M-Ratio, Decision DNA, Ghost Table/Drills, Comparativo de Torneios, Coaching, GamificaÃ§Ã£o. Sidebar fixa com navegaÃ§Ã£o Ã¢ncora e active highlight por IntersectionObserver. Tabelas com valores precisos extraÃ­dos do cÃ³digo (thresholds reais do engine, XP amounts, nÃ­veis, conquistas).
- **`frontend/src/App.tsx`**: rota `/docs` pÃºblica (AuthRoute).
- **`frontend/src/pages/Index.tsx`**: link "Docs" no footer agora aponta para `/docs`.

---

## [v0.70.0] â€” 2026-05-04 â€” Sprint AL: UX-017 Dashboard PersonalizÃ¡vel

### Added
- **`backend/database/schema.py`**: coluna `dashboard_layout TEXT` na tabela `users` (SQLite + PostgreSQL).
- **`backend/database/repositories.py`**: `get_user_preferences(user_id)` e `save_user_preferences(user_id, layout)`.
- **`backend/api/app.py`**: `GET /player/preferences` e `PATCH /player/preferences`.
- **`frontend/package.json`**: dependÃªncias `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`.
- **`frontend/src/hooks/useDashboardLayout.ts`**: hook que carrega layout do servidor, persiste com debounce de 800ms e expÃµe `updateMain`, `updateSidebar`, `reset`.
- **`frontend/src/components/hud/DraggableCard.tsx`**: wrapper sortable com drag handle (â ¿) visÃ­vel ao hover no canto superior direito.
- **`frontend/src/lib/api.ts`**: interface `DashboardLayoutData`; objeto `preferences` com `get()` e `save()`.

### Changed
- **`frontend/src/pages/Index.tsx`**: coluna principal (3 linhas: quality_row, street_row, drill_row) e sidebar (leaks, causal_map, level, ai_confidence) agora sÃ£o sortÃ¡veis via `@dnd-kit`. BankrollChart e PlayerDnaCard permanecem fixos. BotÃ£o "Restaurar padrÃ£o" no header do dashboard. Layout sincronizado entre devices via backend.

---

## [v0.69.0] â€” 2026-05-04 â€” Sprint AN: UX-019 Coach Chat Drawer

### Changed
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: adicionado prop `drawer` â€” quando `true`, renderiza como painel full-height (sem header colapsÃ¡vel, `flex-1 min-h-0`) para uso dentro do drawer flutuante.
- **`frontend/src/components/hud/HudHeader.tsx`**: Ã­cone de mensagens no header agora Ã© um botÃ£o que abre/fecha o drawer de chat em vez de navegar para `/coach`. Badge vermelho exibido somente quando hÃ¡ mensagens nÃ£o lidas (badge oculto quando zero). Drawer renderizado como `fixed inset-y-0 right-0 w-full sm:w-96` com overlay semi-transparente; fecha com clique no overlay ou tecla Escape.
- **`frontend/src/pages/AICoach.tsx`**: `CoachMessagesPanel` removido da sidebar â€” chat agora estÃ¡ exclusivamente no drawer global do header.

---

## [v0.68.0] â€” 2026-05-03 â€” Sprint AM: UX-018 Tabela de Alunos com Busca e Filtros

### Changed
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: `AlunosTab` reescrita como tabela responsiva com busca por nome, filtro de status (Todos/Ativos/Inativos), ordenaÃ§Ã£o por coluna (Aluno, Torneios, Ãšltimo Import, TendÃªncia) e paginaÃ§Ã£o client-side (25 por pÃ¡gina). Colunas responsivas: Torneios oculto em mobile, Ãšltimo Import oculto abaixo de md, TendÃªncia oculta abaixo de lg. Ãcone de tendÃªncia colorido (verdeâ†‘/vermelhoâ†“/cinzaâ†’). Badge Ativo/Inativo baseado em import nos Ãºltimos 30 dias. Contador "Xâ€“Y de Z" e botÃµes Anterior/PrÃ³ximo.

---

## [v0.67.0] â€” 2026-05-04 â€” Sprint AJ+AK: UX-015 Coach Inbox + UX-016 Student Badge

### Added
- **`backend/database/repositories.py`**: `get_coach_inbox(coach_id)` â€” agrega conversas por aluno com `last_message_body`, `last_message_at` e `unread_count`.
- **`backend/api/app.py`**: `GET /coach/messages/inbox` â€” retorna threads ordenadas por `last_message_at DESC`.
- **`frontend/src/lib/api.ts`**: interface `InboxThread`; `coachDashboard.inbox()`.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: aba "Mensagens" com inbox â€” avatar inicial, nome do aluno, prÃ©via da Ãºltima mensagem, timestamp relativo e badge vermelho de nÃ£o lidas. Badge de nÃ£o lidas total no botÃ£o da aba (polling 60s).

### Changed
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: mensagens nÃ£o lidas do coach recebem highlight (`border-primary/30 bg-primary/5`). Badge no header da aba desaparece imediatamente ao abrir o painel via `invalidateQueries`.

### Backlog
- **Sprint AM (UX-018)** adicionado: listagem de alunos com tabela, busca, filtros e paginaÃ§Ã£o.

---

## [v0.66.0] â€” 2026-05-03 â€” Sprint AI: BACK-019 Perfil DemogrÃ¡fico do UsuÃ¡rio

### Added
- **`backend/database/schema.py`**: 8 novas colunas em `users` â€” `birth_year`, `country`, `state_province`, `city`, `poker_experience_years`, `main_game_type`, `usual_buyin_range`, `profile_completed_at` (migraÃ§Ãµes Postgres e SQLite).
- **`backend/database/repositories.py`**: `get_user_demographics`, `update_user_demographics` (marca `profile_completed_at` quando campos core preenchidos), `get_demographics_aggregate` (dados anonimizados para o admin).
- **`backend/api/app.py`**: `GET /player/profile`, `PATCH /player/profile`, `GET /admin/demographics`; campo `profile_completed_at` adicionado Ã  resposta do `/auth/me`.
- **`frontend/src/lib/api.ts`**: interface `DemographicProfile`; objeto `profile` com `get()` e `update()`; `adminDashboard.demographics()`.
- **`frontend/src/components/hud/ProfileCompletionCard.tsx`**: card colapsÃ¡vel no dashboard â€” exibido quando perfil nÃ£o estÃ¡ completo; formulÃ¡rio com todos os campos demogrÃ¡ficos; barra de progresso; nota LGPD; botÃ£o "NÃ£o mostrar mais" persiste em localStorage.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: painel "Perfis DemogrÃ¡ficos" na aba VisÃ£o Geral â€” taxa de completion, top paÃ­ses, distribuiÃ§Ã£o por tipo de jogo e faixa de buy-in.

### Changed
- **`frontend/src/pages/Index.tsx`**: `ProfileCompletionCard` inserido entre `DailyFocusCard` e `SessionGoalPanel`.
- **`backend/api/app.py`**: `/auth/me` passa a retornar `profile_completed_at`.

---

## [v0.65.0] â€” 2026-05-03 â€” Sprint AH: BACK-018 Coach Application Flow

### Added
- **`backend/database/schema.py`**: tabela `coach_applications` (user_id, instagram_handle, bio, specialties, experience_years, biggest_results, status pending/approved/rejected, admin_note, reviewed_at).
- **`backend/database/repositories.py`**: `create_coach_application`, `get_coach_applications`, `approve_coach_application`, `reject_coach_application`, helper `_now()`.
- **`backend/leaklab/email_digest.py`**: helper `send_transactional_email(to_email, subject, html_body)` reutilizando a infra SMTP do digest.
- **`backend/api/app.py`**: `POST /auth/coach-apply` (pÃºblico, rate-limited 5/min) â€” cria usuÃ¡rio com role `coach_pending` + registro de candidatura. `GET /admin/coach-applications` + `POST /admin/coach-applications/<id>/approve` + `POST /admin/coach-applications/<id>/reject` â€” gestÃ£o pelo admin com envio de e-mail automÃ¡tico.
- **`frontend/src/pages/CoachApply.tsx`**: formulÃ¡rio pÃºblico de candidatura (username, @instagram, email, senha, bio â‰¥30 chars, especialidades, anos de experiÃªncia, maiores resultados) com estado de confirmaÃ§Ã£o.
- **`frontend/src/lib/api.ts`**: interface `CoachApplication`, mÃ©todos `adminDashboard.coachApplications`, `approveApplication`, `rejectApplication`; `coachApplyApi.apply`.
- **`frontend/src/pages/admin/AdminDashboard.tsx`**: aba "Candidaturas" com filtro por status, linhas expansÃ­veis (bio/especialidades/resultados), botÃµes aprovar/rejeitar com nota opcional.
- **`frontend/src/App.tsx`**: rota pÃºblica `/coach-apply`.

### Changed
- **`backend/api/app.py`**: `POST /auth/register` com `role: coach` retorna 400 â€” coaches devem usar `/auth/coach-apply`.
- **`backend/api/app.py`**: `POST /auth/login` com role `coach_pending` retorna 403 com `code: 'coach_pending'`.
- **`frontend/src/pages/Login.tsx`**: botÃ£o "Coach" na aba de registro redireciona para `/coach-apply`; mensagem de erro `coach_pending` tratada com texto especÃ­fico.

### Fixed
- **`frontend/src/pages/coach/StudentDetail.tsx`**: Feed de Atividade exibia `standard_pct` multiplicado por 100 (ex.: 83% aparecia como 8300%). Removida duplicaÃ§Ã£o de `* 100`.

---

## [v0.64.0] â€” 2026-05-03 â€” Sprint AF: UX-014 StudentDetail + CoachDashboard wide layout

### Changed
- **`frontend/src/pages/coach/StudentDetail.tsx`**: container `max-w-5xl` â†’ `max-w-[1440px] px-4 md:px-8` (consistente com o dashboard principal). `OverviewTab` reestruturado para grid `lg:grid-cols-12` â€” coluna principal (8-col) com LevelCard + HUD stats + evolution chart + comparativo; aside (4-col) com Principais Leaks + Performance por Street + Performance por PosiÃ§Ã£o. Evolution chart aumentado de 200px para 220px de altura.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: mesma atualizaÃ§Ã£o de container `max-w-5xl` â†’ `max-w-[1440px] px-4 md:px-8`.

---

## [v0.63.0] â€” 2026-05-03 â€” Sprint AF-fix: Dashboard layout holes

### Fixed
- **`frontend/src/pages/Index.tsx`**: GhostDrillCard, PressureProfileCard e IcmBreakdown movidos para dentro da coluna principal (8-col) como subgrid `md:grid-cols-3` abaixo do PlayerDnaCard â€” elimina o "buraco" visual causado pela quebra de ritmo entre o grid 8+4 e o antigo row 4-col. AI Confidence card retorna para o aside, mantendo o painel lateral com conteÃºdo atÃ© o final.

---

## [v0.62.0] â€” 2026-05-03 â€” Sprint AF: Dashboard card reposition

### Changed
- **`frontend/src/pages/Index.tsx`**: GhostDrillCard, PressureProfileCard, IcmBreakdown e AI Confidence movidos da aside (4 col) para uma nova row full-width abaixo do grid principal, em `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`. Aside agora contÃ©m apenas LeaksPanel, LeakCausalMap e LevelCard â€” os cards analÃ­ticos mais crÃ­ticos.

---

## [v0.61.0] â€” 2026-05-03 â€” Sprint AE: UX-013 "JAM" â†’ "All In" na camada de display

### Added
- **`frontend/src/lib/utils.ts`**: funÃ§Ã£o `formatAction(a: string)` â€” mapeia `"jam"` â†’ `"All In"`, capitaliza demais aÃ§Ãµes. Identificadores internos do backend permanecem inalterados.

### Changed
- **`frontend/src/pages/GhostTable.tsx`**: `.toUpperCase()` direto nos valores de aÃ§Ã£o substituÃ­do por `formatAction(...).toUpperCase()` em 4 locais (originalMistake, bestAction subtitle, yourAction card, bestAction card).
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: `{d.action_taken}` e `{d.best_action}` na tabela de decisÃµes encapsulados com `formatAction()`.
- **`frontend/src/pages/coach/StudentDetail.tsx`**: mesma correÃ§Ã£o nas duas tabelas de decisÃµes e no card de detalhe (6 ocorrÃªncias).
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: tooltip de Flop Bet atualizado de "bet/raise/jam" para "bet/raise/all-in".

---

## [v0.60.0] â€” 2026-05-03 â€” Sprint AD: UX-012 Remove recent tournaments from dashboard

### Removed
- **`frontend/src/pages/Index.tsx`**: `RecentTournamentsTable` removido do dashboard â€” o menu /tournaments jÃ¡ serve essa funÃ§Ã£o. O estado `tourns` e o fetch de `tournaments.list()` permanecem para os cÃ¡lculos de KPI (ROI, ITM, Total Eventos, Total MÃ£os).

---

## [v0.59.0] â€” 2026-05-03 â€” Sprint AC: UX-011 Dashboard title/subtitle

### Changed
- **`frontend/src/i18n/locales/pt-BR|en|es/dashboard.json`**: `title` e `titleDefault` passam de "{{name}} â€” Centro de Comando / Command Center / Centro de Mando" para simplesmente `"Dashboard"` nos trÃªs idiomas. Subtitle encurtado para caber em uma linha sem quebra em viewports comuns.
- **`frontend/src/pages/Index.tsx`**: `<h1>` simplificado â€” removida interpolaÃ§Ã£o `{name}` e o fallback `titleDefault`; ambas as keys agora retornam `"Dashboard"`.

---

## [v0.58.0] â€” 2026-05-03 â€” Sprint AB: UX-010 Bankroll period filters

### Fixed
- **`frontend/src/components/hud/BankrollChart.tsx`**: filtros de perÃ­odo (1M/3M/1Y/Tudo) agora funcionam â€” componente passou a ser self-contained, gerencia seu prÃ³prio estado de perÃ­odo e busca os dados via `useQuery` com o nÃºmero correto de dias (30/90/365/3650). BotÃ£o ativo destacado corretamente. Spinner overlay durante refetch. Prop `evolution` removida (o componente nÃ£o depende mais do parent para dados).
- **`frontend/src/pages/Index.tsx`**: `<BankrollChart>` sem prop â€” componente busca seus prÃ³prios dados.
- **`backend/requirements.txt`**: `python-dotenv==1.0.1` adicionado â€” estava faltando, causando `ModuleNotFoundError: No module named 'dotenv'` no boot do Gunicorn no Render.

---

## [v0.57.0] â€” 2026-05-03 â€” Sprint AA: INFRA-001 Build + display bugs

### Fixed
- **`vercel.json`**: substituÃ­do config quebrado `@vercel/static-build` com rotas `"/frontend/$1"` pelo formato moderno â€” `buildCommand` + `outputDirectory` + `rewrites` apontando tudo para `/index.html`; corrige roteamento do React Router em produÃ§Ã£o.
- **`backend/leaklab/email_digest.py`**: variÃ¡vel de ambiente do token de unsubscribe corrigida de `JWT_SECRET_KEY` para `LEAKLAB_SECRET` (alinhado com `database/auth.py` e `render.yaml`).
- **`frontend/src/pages/AICoach.tsx`**: `standard_pct` no painel de contexto exibia valor multiplicado por 100 duas vezes (ex: 85.18 â†’ 8518%). O endpoint retorna jÃ¡ em % â€” removida a multiplicaÃ§Ã£o `* 100` incorreta.

---

## [v0.56.0] â€” 2026-05-03 â€” Sprint Z: UX-009 Tournament date display

### Changed
- **`frontend/src/pages/Tournaments.tsx`**: `formatDate` agora exibe ano de 2 dÃ­gitos (`DD/MM/YY`) quando o torneio Ã© de ano anterior ao atual â€” torneios do ano corrente continuam como `DD/MM`. Novo componente `TournamentDate` distingue visualmente `played_at` (data real do torneio) de `imported_at` (data de importaÃ§Ã£o): quando `played_at` nÃ£o estÃ¡ disponÃ­vel, exibe a data de importaÃ§Ã£o com label "importado" em tom reduzido. Aplicado na tabela desktop e nos cards mobile.

---

## [v0.55.0] â€” 2026-05-03 â€” Sprint Y: UX-008 Coaches Directory mobile + terminologia

### Changed
- **`frontend/src/pages/CoachesDirectory.tsx`**: layout mobile corrigido â€” filtros movidos para painel colapsÃ¡vel com toggle (botÃ£o mostra contagem de filtros ativos); sidebar visÃ­vel apenas em `lg+`; grid muda de `md:grid-cols-2` para `sm:grid-cols-2` para usar melhor o espaÃ§o; `min-w-0` na coluna do grid evita overflow.
- **`frontend/src/pages/Login.tsx`**: seletor de role na tela de registro: "Professor" â†’ "Coach".
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: tÃ­tulo "Dashboard do Professor" â†’ "Dashboard do Coach".
- **`frontend/src/i18n/locales/pt-BR/dashboard.json`**: banner de vÃ­nculo: "Tem um professor?" â†’ "Tem um coach?".
- **`frontend/src/components/hud/AcceptCoachModal.tsx`**: 3 ocorrÃªncias de "professor" substituÃ­das por "coach" (tÃ­tulo do modal, mensagem de instruÃ§Ã£o, confirmaÃ§Ã£o de sucesso).

---

## [v0.54.0] â€” 2026-05-03 â€” Sprint W: FEAT-11 Weekly Digest Email

### Added
- **`backend/leaklab/email_digest.py`**: mÃ³dulo de digest semanal â€” `build_digest_data` (coleta mÃ©tricas dos Ãºltimos 7 dias: standard%, EV loss, drill atrasado, precisÃ£o), `build_digest_html` (template dark responsivo com EV bar visual), `send_digest_email` (SMTP via smtplib nativo com STARTTLS), `run_weekly_digest` (itera inscritos e envia). Sem dependÃªncias extras alÃ©m da stdlib.
- **`backend/database/schema.py`**: coluna `digest_subscribed INTEGER NOT NULL DEFAULT 0` na tabela `users` (SQLite + Postgres migration).
- **`backend/database/repositories.py`**: `get_digest_subscribers` (usuÃ¡rios com `digest_subscribed=1` e `last_login` nos Ãºltimos 30 dias), `update_digest_subscription`.
- **`backend/api/app.py`**: `POST /player/digest/subscribe`, `POST /player/digest/unsubscribe` (autenticado), `GET /player/digest/unsubscribe` (link do email com token HMAC), `POST /admin/send-digest`; campo `digest_subscribed` incluÃ­do na resposta de `/auth/me`.
- **`frontend/src/lib/api.ts`**: campo `digest_subscribed` em `UserProfile`; mÃ³dulo `digest` com `subscribe()` e `unsubscribe()`.
- **`frontend/src/pages/Index.tsx`**: banner de opt-in contextual â€” visÃ­vel para players com dados que ainda nÃ£o ativaram o digest; dispensÃ¡vel pelo X; botÃ£o "Ativar" chama `digest.subscribe()` e atualiza o perfil via `refreshUser()`.

---

## [v0.53.0] â€” 2026-05-03 â€” Sprint V: FEAT-09 Coach Templates + FEAT-10 Coach Messaging

### Added
- **`backend/database/schema.py`**: tabela `coach_plan_templates` (id, coach_id, name, target_archetype, cards_json) e `coach_messages` (id, coach_id, student_id, body, sender_role, decision_id, read_at) â€” SQLite + Postgres.
- **`backend/database/repositories.py`**: `get_coach_templates`, `create_coach_template`, `delete_coach_template`; `send_coach_message`, `get_coach_messages`, `mark_messages_read`, `get_unread_message_count`.
- **`backend/api/app.py`**: endpoints `GET/POST /coach/templates`, `DELETE /coach/templates/<id>`; `GET/POST /coach/student/<id>/messages`; `GET/POST /player/coach/messages`, `GET /player/messages/unread`.
- **`frontend/src/lib/api.ts`**: interfaces `CoachTemplate`, `CoachMessage`; mÃ©todos em `coachDashboard` (getTemplates, createTemplate, deleteTemplate, getMessages, sendMessage); mÃ³dulo `playerMessages` (list, send, unreadCount).
- **`frontend/src/pages/coach/StudentDetail.tsx`**: aba "Mensagens" com chat bidirecional em tempo real (polling 15s), badge de nÃ£o lidas na aba, botÃ£o "Salvar como template" nos cards substituÃ­dos do plano de estudos.
- **`frontend/src/components/hud/CoachMessagesPanel.tsx`**: painel colapsÃ¡vel de chat para o player na pÃ¡gina do AI Coach â€” mostra conversa com coach humano vinculado, badge de nÃ£o lidas, envio via Enter.
- **`frontend/src/pages/AICoach.tsx`**: `CoachMessagesPanel` integrado na sidebar, visÃ­vel apenas quando `user.coach_id` estÃ¡ presente.
- **`frontend/src/components/hud/HudHeader.tsx`**: badge de nÃ£o lidas no header (Ã­cone `MessageSquare` com contador) para players com coach vinculado â€” polling 60s, link para `/coach`.

---

## [v0.52.0] â€” 2026-05-03 â€” Sprint U: FEAT-08 Session Goals + AI Review

### Added
- **`backend/database/schema.py`**: tabela `session_goals` (SQLite + Postgres) â€” `id`, `user_id`, `goal_leak_spot`, `target_standard_pct`, `notes`, `tournament_id` (nullable), `llm_review`, `created_at`, `linked_at`.
- **`backend/database/repositories.py`**: `create_session_goal`, `link_session_goal`, `get_pending_session_goal`, `get_session_goal_by_tournament`, `save_session_review`.
- **`backend/leaklab/llm_explainer.py`**: `generate_session_review(goal, tournament)` â€” Claude Haiku (~300 tokens) compara meta prÃ©-sessÃ£o com resultado real; 3 frases: atingiu/nÃ£o atingiu meta, ponto tÃ©cnico relevante, recomendaÃ§Ã£o para prÃ³xima sessÃ£o. Fallback `_template_session_review` determinÃ­stico.
- **`backend/api/app.py`**: endpoints `POST /player/session-goals`, `GET /player/session-goals/pending`, `POST /player/session-goals/<id>/link`, `GET /player/session-review/<tournament_id>` (gera e persiste review on-demand).
- **`frontend/src/lib/api.ts`**: interfaces `SessionGoal`, `SessionReviewResponse`; mÃ©todos `metrics.createSessionGoal`, `metrics.pendingSessionGoal`, `metrics.linkSessionGoal`, `metrics.sessionReview`.
- **`frontend/src/components/hud/UploadQueue.tsx`**: `SessionGoalPanel` exportado â€” painel colapsÃ¡vel com campos spot de foco, meta de standard% e anotaÃ§Ã£o livre; persiste goal ID em `sessionStorage`; hook `useUploadQueue` lÃª `ll_pending_goal` do `sessionStorage` apÃ³s upload e chama `metrics.linkSessionGoal` automaticamente.
- **`frontend/src/pages/Index.tsx`**: `SessionGoalPanel` integrado ao dashboard (visÃ­vel apenas para players).
- **`frontend/src/pages/TournamentDetail.tsx`**: card "Review da SessÃ£o" exibido apÃ³s narrativa quando hÃ¡ meta vinculada â€” mostra spot de foco, meta vs resultado real com indicador âœ“/âœ—, review gerado por IA e anotaÃ§Ã£o livre do jogador.

---

## [v0.51.0] â€” 2026-05-03 â€” Sprint T: FEAT-07 Coach Effectiveness Metrics

### Added
- **`backend/database/repositories.py`**: `get_coach_effectiveness_report(coach_id)` â€” itera todos os alunos com baseline, chama `get_baseline_comparison` por aluno, calcula delta de `standard_pct`, melhora mediana, % com melhora positiva e badge pÃºblico (visÃ­vel com â‰¥3 alunos e mediana positiva).
- **`backend/api/app.py`**: endpoint `GET /coach/effectiveness` (autenticado como coach). Perfil pÃºblico `GET /coaches/<id>` passa a incluir `effectiveness_badge` e `effectiveness_median_delta`.
- **`frontend/src/lib/api.ts`**: interfaces `EffectivenessStudent`, `EffectivenessSummary`, `CoachEffectivenessReport`; mÃ³dulo `coachEffectiveness` com mÃ©todo `report()`.
- **`frontend/src/pages/coach/CoachDashboard.tsx`**: aba "Efetividade" com 3 KPI cards (alunos analisados, melhora mediana, % com melhora), preview do badge pÃºblico com indicaÃ§Ã£o "visÃ­vel no perfil pÃºblico", tabela por aluno com before/after `standard_pct`, delta colorido e leaks corrigidos.
- **`frontend/src/pages/PublicCoachProfile.tsx`**: badge "Alunos melhoram +Xpp em standard_pct" exibido na seÃ§Ã£o de badges do perfil pÃºblico quando disponÃ­vel.

---

## [v0.50.0] â€” 2026-05-03 â€” Sprint S: FEAT-06 Leak Causal Map

### Added
- **`backend/leaklab/leak_causal_graph.py`**: `build_leak_graph(rows)` â€” analisa co-ocorrÃªncia de leaks entre torneios, calcula correlaÃ§Ã£o de Jaccard por par (threshold 35%), retorna nÃ³s com `severity` (critical/moderate/minor por avg_score) e arestas ordenadas por correlaÃ§Ã£o; label compacto (`PF Fold`, `FL Bet`, etc.); nÃ³s incluem `degree` (nÃºmero de conexÃµes).
- **`backend/leaklab/llm_explainer.py`**: `explain_leak_causality(edges, hero)` â€” 1 chamada Claude Haiku (~150 tokens) gerando 2-3 frases de diagnÃ³stico causal para os 3 pares mais correlacionados; cache em memÃ³ria por combinaÃ§Ã£o de pares; fallback `_template_causality()` determinÃ­stico.
- **`backend/database/repositories.py`**: `get_leak_graph_data(user_id, days)` â€” busca todas as decisÃµes com mistake do usuÃ¡rio no perÃ­odo, chama `build_leak_graph` e `explain_leak_causality`, retorna `{nodes, edges, narrative}`.
- **`backend/api/app.py`**: endpoint `GET /player/leak-graph?days=90`.
- **`frontend/src/lib/api.ts`**: interfaces `LeakGraphNode`, `LeakGraphEdge`, `LeakGraphResponse`; mÃ©todo `metrics.leakGraph(days)`.
- **`frontend/src/components/hud/LeakCausalMap.tsx`**: card com grafo SVG circular â€” nÃ³s coloridos por severidade (vermelho/Ã¢mbar/verde), arestas com espessura e opacidade proporcionais Ã  correlaÃ§Ã£o; interaÃ§Ã£o: clique no nÃ³ destaca suas conexÃµes e exibe detalhe com lista de co-ocorrÃªncias; narrativa LLM abaixo do grafo; legenda de cores.
- **`frontend/src/pages/Index.tsx`**: `LeakCausalMap` inserido apÃ³s `LeaksPanel` quando hÃ¡ â‰¥ 3 nÃ³s; `metrics.leakGraph(90)` carregado no mount.

---

## [v0.49.0] â€” 2026-05-03 â€” Sprint R: FEAT-05 SRS Adaptativo nos Drills

### Added
- **`backend/database/schema.py`**: colunas `next_drill_at TEXT` e `srs_interval_days INTEGER DEFAULT 3` em `drill_sessions` (Postgres + SQLite migrations).
- **`backend/database/repositories.py`**: `save_drill_session` reescrito com lÃ³gica SRS â€” acerto dobra o intervalo (`3d â†’ 7d â†’ 14d â†’ 28d â†’ 60d`, cap em 60), erro reseta para 3 dias; calcula `next_drill_at = now + interval` e persiste ambos os campos. `get_drill_spots` reescrito â€” substitui filtro de `drilled_at >= 7 days` por LEFT JOIN na sessÃ£o mais recente por decisÃ£o, filtra por `next_drill_at IS NULL OR next_drill_at <= now`, ordena por mais atrasado primeiro; calcula `days_overdue` em Python (compatÃ­vel SQLite + Postgres).
- **`backend/api/app.py`**: endpoint `POST /player/spots/drill/submit` passa a retornar `next_drill_at` e `srs_interval_days`.
- **`frontend/src/lib/api.ts`**: `DrillSpot` com campos `next_drill_at`, `srs_interval_days`, `days_overdue`; `DrillSubmitResult` com `next_drill_at` e `srs_interval_days`.
- **`frontend/src/pages/GhostTable.tsx`**: badge "prÃ³xima revisÃ£o em X dias" (verde=acerto, amarelo=reset) no card de resultado apÃ³s cada drill; badge de dias de atraso discreto (vermelho/amarelo) na barra de progresso do spot ativo.
- **`frontend/src/components/hud/GhostDrillCard.tsx`**: prop `pendingSpots` opcional â€” exibe contador "N atrasados" com Ã­cone Clock no header do card quando hÃ¡ spots vencidos.
- **`frontend/src/pages/Index.tsx`**: carrega `drill.spots({ limit: 20 })` no mount e passa `pendingSpots` para `GhostDrillCard`.

---

## [v0.48.0] â€” 2026-05-03 â€” Sprint Q: FEAT-02 Daily Focus + FEAT-03 XP Server-Side

### Added
- **`backend/database/schema.py`**: migraÃ§Ãµes para `xp_total INT DEFAULT 0`, `xp_streak INT DEFAULT 0`, `xp_last_activity DATE`, `daily_focus_done_at DATE` na tabela `users`; nova tabela `achievements` (`user_id`, `achievement_id`, `unlocked_at`).
- **`backend/database/repositories.py`**: `get_daily_focus(user_id)` â€” lÃ³gica determinÃ­stica (zero LLM) que combina top EV-loss leak, drill com cooldown expirado e torneio nÃ£o revisado; retorna `{primary, secondary[], valid_until, completed, streak}`. `mark_daily_focus_done(user_id)` â€” persiste data de conclusÃ£o. `add_xp(user_id, event_type, amount?)` â€” streak server-side: +1 se Ãºltimo XP foi ontem, reset se mais antigo; checa conquistas automaticamente via `_check_and_grant_achievements()`. `get_xp_status(user_id)`, `get_achievements(user_id)`. `_XP_AMOUNTS` (`tournament_imported=50`, `exercise_correct=10`, `drill_completed=25`, `drill_mastered=100`). 5 conquistas: `first_tournament`, `decisions_100`, `first_drill`, `streak_7`, `tournaments_10`.
- **`backend/api/app.py`**: 5 novos endpoints â€” `GET /player/daily-focus`, `POST /player/daily-focus/complete`, `GET /player/xp`, `POST /player/xp`, `GET /player/achievements`.
- **`frontend/src/components/hud/DailyFocusCard.tsx`**: card de foco diÃ¡rio â€” exibe aÃ§Ã£o primÃ¡ria e 2 secundÃ¡rias com link direto; timer countdown atÃ© meia-noite; estado "concluÃ­do" com streak de dias; usa `useQuery` + `useMutation` via React Query.
- **`frontend/src/lib/api.ts`**: interfaces `DailyFocusData`, `DailyFocusAction`, `XpStatus`, `Achievement`; mÃ©todos `metrics.dailyFocus()`, `metrics.completeDailyFocus()`, `metrics.xpStatus()`, `metrics.addXp(event_type)`, `metrics.achievements()`.
- **`frontend/src/pages/Index.tsx`**: `DailyFocusCard` inserido acima da seÃ§Ã£o de KPIs (visÃ­vel apenas quando hÃ¡ torneios importados).
- **`frontend/src/pages/StudyPlan.tsx`**: `metrics.addXp("exercise_correct")` disparado a cada resposta correta em exercÃ­cio (fire-and-forget).
- **`frontend/src/components/hud/UploadQueue.tsx`**: `metrics.addXp("tournament_imported")` disparado apÃ³s upload bem-sucedido de torneio.

---

## [v0.47.0] â€” 2026-05-03 â€” Sprint P: FEAT-04 RelatÃ³rio PDF Premium

### Added
- **`backend/leaklab/report_generator.py`**: redesign completo â€” `build_html_report(t, decisions, phases, hero)` gera template HTML premium com Inter/JetBrains Mono (Google Fonts), paleta dark profissional, grÃ¡ficos CSS puros (barras, indicadores de score coloridos por threshold). SeÃ§Ãµes: capa com hero + torneio + meta pills, KPI row (Standard%, Avg Score, Clear Mistakes%, DecisÃµes), Quality Distribution com barras + referÃªncia MTT saudÃ¡vel, Phase Breakdown (Deep/Mid/Short Stack/Push/Fold), Top 5 Leaks com barra proporcional e score colorido, Performance por ICM Pressure, Top 10 DecisÃµes CrÃ­ticas com label badges.
- **`generate_pdf_bytes(html)`**: converte HTML para PDF via WeasyPrint; levanta `ImportError` se a lib nÃ£o estiver disponÃ­vel â€” o endpoint faz fallback automÃ¡tico para download HTML.
- **`backend/Dockerfile`**: adicionadas dependÃªncias de sistema para WeasyPrint â€” `libpango`, `libcairo2`, `libgdk-pixbuf2.0-0`, `libpangocairo`, `libffi-dev`, `fonts-liberation`.
- **`render.yaml`**: migrado de `runtime: python` para `runtime: docker` (necessÃ¡rio para instalar as dependÃªncias de sistema do WeasyPrint no Render).
- **`backend/requirements.txt`**: `weasyprint==62.3`.
- **`backend/api/app.py`**: endpoint `GET /history/tournament/<id>/report.pdf` â€” retorna PDF (`application/pdf`) ou HTML como fallback se WeasyPrint nÃ£o disponÃ­vel; `Content-Disposition: attachment`.
- **`frontend/src/lib/api.ts`**: `tournaments.downloadReport(tournamentId)` â€” fetch binÃ¡rio com auth header, cria blob URL e dispara download automaticamente.
- **`frontend/src/pages/TournamentDetail.tsx`**: botÃ£o "PDF" (Ã­cone `FileDown`) ao lado do botÃ£o Replay; estado `pdfDownloading` com spinner enquanto gera.

### Changed
- **`backend/leaklab/report_generator.py`**: `generate_report()` (legacy) mantida e intacta para compatibilidade com callers existentes.

---

## [v0.46.0] â€” 2026-05-03 â€” Sprint O: FEAT-01 Comparativo de Torneios

### Added
- **`backend/database/repositories.py`**: `get_tournaments_comparison(user_id, ids)` â€” agrega por torneio: `standard_pct`, `avg_score`, `clear_pct`, hands/decisions count, profit, buy_in, place, phase breakdown e top 5 leaks; `_compute_comparison_leaks(decisions)` â€” calcula mÃ©dia de score por spot para o ranking de leaks.
- **`backend/leaklab/llm_explainer.py`**: `generate_comparison_narrative(items)` â€” narrativa comparativa de 2 frases via Claude Haiku (max 100 tokens); cache por `cmp_{id1}_{id2}...`; fallback `_template_comparison()` calcula delta de `standard_pct` entre primeiro e Ãºltimo torneio.
- **`backend/api/app.py`**: endpoint `GET /history/tournaments/compare?ids=A,B,C` â€” valida 2â€“4 IDs, retorna `{items: TournamentComparison[], narrative}`.
- **`frontend/src/lib/api.ts`**: interface `TournamentComparison` e mÃ©todo `tournaments.compare(ids)`.
- **`frontend/src/pages/TournamentCompare.tsx`**: pÃ¡gina de comparativo lado a lado â€” componentes `Delta` (trend Â±) e `QualityBar` (barra colorida por threshold); seÃ§Ãµes: narrativa LLM, cards de cabeÃ§alho por torneio, tabela de qualidade (Standard%/Avg Score/Clear Mistakes%), phase breakdown (Deep/Mid/Short Stack/Push-Fold), top leaks com destaque amarelo para leaks compartilhados entre torneios; badge "â–² melhor" no melhor valor de cada mÃ©trica.
- **`frontend/src/pages/Tournaments.tsx`**: multi-seleÃ§Ã£o de 2â€“4 torneios via checkboxes (desktop e mobile); CTA "Comparar N torneios" com Ã­cone aparece ao selecionar â‰¥ 2 itens; navega para `/tournaments/compare?ids=...`.
- **`frontend/src/App.tsx`**: rota `/tournaments/compare` adicionada antes de `/tournaments/:id`.
- **`backend/database/repositories.py`**: labels de fase de M-ratio padronizadas para inglÃªs â€” `Deep Stack`, `Mid Stack`, `Short Stack`, `Push/Fold` (era PT-BR).

### Changed
- **`frontend/src/pages/TournamentDetail.tsx`**: tooltips das fases atualizados para inglÃªs (Deep Stack / Mid Stack / Short Stack / Push/Fold).

---

## [v0.45.0] â€” 2026-05-03 â€” Sprint M: PERF-008 Tournament Narrative Engine

### Added
- **`backend/leaklab/llm_explainer.py`**: `generate_tournament_narrative(tournament_id, ctx)` â€” gera 2-3 frases descrevendo o arco de qualidade da sessÃ£o via Claude Haiku (max 130 tokens); cache em memÃ³ria por `tournament_id`; fallback determinÃ­stico `_template_narrative()` se LLM indisponÃ­vel.
- **`backend/api/app.py`**: endpoint `GET /history/tournament/<id>/narrative` â€” retorna `{narrative, quality_level}` (solid/regular/poor derivado de `standard_pct`); helper `_build_narrative_context()` agrega label counts, top leaks, ICM breakdown e pior fase do torneio.
- **`frontend/src/lib/api.ts`**: `tournaments.narrative(id)` â†’ `{narrative, quality_level}`.
- **`frontend/src/pages/TournamentDetail.tsx`**: seÃ§Ã£o "Narrativa da SessÃ£o" inline (entre stats grid e phase analysis) â€” badge de qualidade colorido + texto narrativo gerado pelo LLM, carregado automaticamente ao abrir o torneio.
- **`frontend/src/i18n/locales/*/tournaments.json`**: chaves `detail.narrative.*` em PT-BR, EN e ES.

---

## [v0.44.0] â€” 2026-05-03 â€” UX: LeaksPanel layout + PlayerDnaCard radar fix

### Changed
- **`LeaksPanel.tsx`**: redesign do layout de cada item â€” nome do leak em linha prÃ³pria (sem truncate), badges reorganizadas com `justify-between` â€” nÃ— badge e EV loss Ã  esquerda como grupo, botÃ£o **Estudar** sempre ancorado Ã  direita; elimina hack de `flex-1` spacer e overflow em cards com muitos badges simultÃ¢neos.
- **`PlayerDnaCard.tsx`**: corrige label "Disciplina" cortada no grÃ¡fico radar â€” `outerRadius="65%"` + margens aumentadas (`top:15 right:35 bottom:20 left:35`); remove `truncate` desnecessÃ¡rio nas labels do grid de stats.

---

## [v0.43.0] â€” 2026-05-03 â€” Sprint L: PERF-007 Decision DNA

### Backend â€” PERF-007

- **`repositories.py`** â€” `get_player_dna(user_id, days)`: agrega `decisions` em 5 mÃ©tricas normalizadas (0-100):
  - `aggression_index` â€” % de aÃ§Ãµes que sÃ£o raise/bet/jam (excluindo folds)
  - `fold_frequency` â€” % global de folds
  - `three_bet_pct` â€” % de preflop decisions com `is_3bet = True`
  - `positional_awareness` â€” diferencial de agressividade BTN/CO vs UTG/EP (escala 0-100, 50 = neutro)
  - `discipline` â€” standard% geral
  - `icm_awareness` (opcional) â€” ratio de standard% sob alta pressÃ£o ICM vs sem pressÃ£o ICM
  - `_classify_archetype()`: classifica em TAG / LAG / Nit / Calling Station / Balanced a partir das mÃ©tricas
- **`app.py`** â€” `GET /player/dna?days=N`: retorna `{dna, sample_size}`; requer auth

### Frontend â€” PERF-007

- **`PlayerDnaCard.tsx`** (novo) â€” card com radar chart pentagon (Recharts RadarChart), badge de arquÃ©tipo colorido por tipo, grid de 6 mÃ©tricas, descriÃ§Ã£o contextual do arquÃ©tipo; estado vazio com mensagem quando sample_size < 10
- **`pages/Index.tsx`** â€” fetch paralelo de `metrics.dna(90)`; `<PlayerDnaCard>` inserido entre o grid `RecentForm+DecisionQuality` e `BankrollChart`
- **`lib/api.ts`** â€” interfaces `PlayerDna`, `PlayerDnaResponse`; `metrics.dna(days)`

### i18n â€” 3 locales (pt-BR / en / es)

- `dashboard.json` â€” seÃ§Ã£o `dna.*`: title, tooltip, archetype label, sampleSize, noData, 6 axis labels, 5 archetype names + descriptions

### BACKLOG

- Sprint L (PERF-007) concluÃ­da; Sprint M (PERF-008 Tournament Narrative) e Sprint N (PERF-009 GGPoker Parser) aguardam priorizaÃ§Ã£o

---

## [v0.42.0] â€” 2026-05-03 â€” Sprint K pt.2: Ghost Table UX + Engine Notes + Drill-Dashboard Loop

### Backend â€” Ghost Table enhancements

- **`schema.py`** â€” colunas `pot_size REAL` e `facing_bet REAL` adicionadas Ã  tabela `decisions` (SQLite + PostgreSQL, com migration automÃ¡tica)
- **`repositories.py`** â€” `save_decisions()`: extrai `potSize`/`facingSize` do `spot` e armazena em BB dividindo por `level_bb`; `get_drill_spots()`: inclui `pot_size` e `facing_bet` no SELECT; `get_decision_for_drill()`: expandido para retornar todos os campos necessÃ¡rios pelo `analyze_single_decision()`; `get_leak_roi_impact()`: JOIN com `drill_sessions` â€” adiciona `drill_count` e `drill_accuracy` por spot
- **`app.py`** â€” Bug fix crÃ­tico em `_analyze_hands()`: `enriched` dict agora inclui `'spot': di['spot']` (sem isso `pot_size`/`facing_bet` eram sempre `None`); `_GENERIC_NOTES` + `_enrich_note(row)`: detecta 3 strings genÃ©ricas legadas e as substitui por notas especÃ­ficas geradas dos campos do banco (street, position, stack_bb, facing_bet, pot_size, m_ratio, ICM, label, score, action gap); aplicado em `history_tournament` e `coach_student_tournament`; novo endpoint `GET /player/drill-stats` (resumo leve sem carregar spots); novo endpoint `GET /player/spots/drill/<id>/analysis` com cache na tabela `llm_cache` (chave `drill_analysis:{decision_id}`) â€” chama Claude Haiku apenas na primeira vez
- **`decision_engine_v11.py`** â€” `build_interpretation()` reescrito: notas vazias para `standard`/`marginal`; para `small_mistake`/`clear_mistake` gera nota especÃ­fica usando equity diff, draw context, M-Ratio zone, ICM pressure, range zone + position, facing bet context; sempre termina com "AÃ§Ã£o esperada: X."

### Frontend â€” Ghost Table UX

- **`GhostTable.tsx`** â€” board cards limitados por street (preflop = 0, flop = 3, turn = 4, river = 5) para nÃ£o revelar cartas futuras; `pot_size` e `facing_bet` em BB adicionados ao SituationBox; nota do motor movida da fase `active` para a fase `result` (nÃ£o influencia decisÃ£o); renomeado "AnÃ¡lise da IA" â†’ "AnÃ¡lise do Motor"; botÃ£o "Ver anÃ¡lise desta mÃ£o" (BookOpen) na fase result com `requestAnalysis()` â†’ `drill.analysis(id)`; estado `analysis` e `analysisLoading` gerenciados; aÃ§Ãµes "JAM" renomeadas para "All-In" nas 3 locales
- **`GhostDrillCard.tsx`** (novo) â€” card sidebar no dashboard: mostra total de spots treinados, acerto %, avg delta dos Ãºltimos 30 dias; estado vazio com CTA "Iniciar drill" para `/ghost`
- **`LeaksPanel.tsx`** â€” badge "Treinando" (cinza) ou "Dominando" (primÃ¡ria) quando `drill_count > 0`; badge "CrÃ­tico" ocultado quando spot em treino; tooltip mostra `Ghost Table: Nx treinado (X% acerto)`
- **`pages/Index.tsx`** â€” fetch paralelo de `metrics.drillStats(30)`; `<GhostDrillCard stats={drillStats} />` inserido entre LevelCard e LeaksPanel

### i18n â€” 3 locales (pt-BR / en / es)

- **`ghost.json`** â€” chaves: `context.pot`, `context.facing`, `result.engineNote`, `result.requestAnalysis`, `result.analysisLoading`, `result.analysisError`, `situation.*`; `actions.jam` â†’ "All-In"
- **`dashboard.json`** â€” chaves: `leaks.drillPracticing`, `leaks.drillMastering`, `ghost.title`, `ghost.spots`, `ghost.accuracy`, `ghost.continueStudy`, `ghost.noActivity`, `ghost.startNow`

### Removido

- **`backend/leaklab/mercadopago_gateway.py`** â€” arquivo legado do gateway Mercado Pago (migrado para Stripe em v0.29.0); removido para limpar o repositÃ³rio

---

## [v0.41.0] â€” 2026-05-03 â€” Sprint K: PERF-006 Ghost Table Simulator MVP

### Backend â€” PERF-006
- `schema.py` â€” `drill_sessions` table (id, user_id, decision_id, new_action, new_score, original_score, delta, drilled_at) â€” SQLite + PostgreSQL
- `repositories.py` â€” `get_drill_spots()`: fetches undrilled mistake decisions (7-day cooldown); `save_drill_session()`: persists re-decision with score delta; `get_drill_stats()`: 30-day accuracy/total/avg_delta; `get_decision_for_drill()`: ownership-verified decision fetch
- `app.py` â€” `GET /player/spots/drill`: returns spots + stats; `POST /player/spots/drill/submit`: evaluates new_action vs best_action, scores 0.02 if correct else original_score

### Frontend â€” PERF-006
- `GhostTable.tsx` â€” full drill page with state machine (intro â†’ loading â†’ active â†’ result â†’ done): spot context card (street/ICM/position/stack/M-ratio/cards/board), 6 action buttons, result reveal, session accuracy, done screen
- `App.tsx` â€” `/ghost` route with `ProtectedRoute`
- `HudHeader.tsx` â€” "Ghost Table" nav item (Swords icon) for playerNavItems
- `i18n/locales/[pt-BR|en|es]/ghost.json` â€” new namespace (63 keys: drill UI, actions, result messages, stats)
- `i18n/locales/[pt-BR|en|es]/common.json` â€” `nav.ghost` key added
- `api.ts` â€” `DrillSpot`, `DrillStats`, `DrillSubmitResult` interfaces + `drill.spots()` + `drill.submit()`

---

## [v0.40.0] â€” 2026-05-03 â€” Sprint J: PERF-003+004+005 Leak Progression + Pressure Collapse + Drift

### Backend â€” PERF-003: Leak Progression (trend)

- **`repositories.py`** â€” `get_leak_roi_impact()` estendido: compara avg_score dos Ãºltimos 30 dias vs. 30-60 dias anteriores por spot; retorna `trend`: `improving` / `stagnant` / `regressing` / `new`

### Backend â€” PERF-004: Pressure Collapse Detection

- **`repositories.py`** â€” `get_pressure_profile(user_id, days)`: baseline score geral + avg_score por `icm_pressure`; calcula `collapse_delta = score_high - score_none`; flag `has_collapse` se delta > 0.08
- **`app.py`** â€” `GET /player/pressure-profile`

### Backend â€” PERF-005: Confidence Drift Monitor

- **`repositories.py`** â€” `get_confidence_drift(user_id, days=30)`: detecta torneios com avg_score > baseline Ã— 1.30; retorna `drift_detected`, `severity` (mild/moderate/severe), lista de sessÃµes afetadas
- **`app.py`** â€” `GET /player/confidence-drift`

### Frontend â€” Sprint J completo

- **`lib/api.ts`** â€” interfaces `PressureProfile`, `ConfidenceDrift`; `metrics.pressureProfile()`, `metrics.confidenceDrift()`; `LeakRoiData` expandido com campo `trend`
- **`components/hud/PressureProfileCard.tsx`** â€” novo card: barras de mistake_score por pressÃ£o ICM, badge "Colapso" / "SÃ³lido", delta summary
- **`components/hud/LeaksPanel.tsx`** â€” Ã­cones de tendÃªncia (â†“ melhorando / â†’ estagnado / â†‘ regredindo) por leak
- **`pages/Index.tsx`** â€” fetch paralelo de `pressureProfile` + `confidenceDrift`; banner de alerta dismissÃ­vel quando drift detectado; `PressureProfileCard` no sidebar
- **Locales** â€” chaves `pressure.*`, `drift.*` e `leaks.trend*` adicionadas a `dashboard.json` (PT-BR + EN + ES)

## [v0.39.0] â€” 2026-05-03 â€” Sprint I: PERF-001 + PERF-002 ROI Attribution + Leak Priority

### Backend â€” PERF-001: ROI Attribution Engine

- **`repositories.py`** â€” `get_leak_roi_impact(user_id, days)`: query enriquecida com `AVG(t.buy_in)`, `priority_score = n Ã— avg_score`, `ev_loss_monthly = (nÃ—30/days) Ã— avg_score Ã— avg_buy_in Ã— 0.10`; ordenada por `priority_score DESC`
- **`app.py`** â€” `GET /player/leak-roi`: endpoint protegido por `@require_auth`; importa `get_leak_roi_impact`

### Frontend â€” PERF-001 + PERF-002

- **`lib/api.ts`** â€” interface `LeakRoiData` com campos `ev_loss_monthly`, `priority_score`, `priority_rank`; `metrics.leakRoi(days)`
- **`pages/Index.tsx`** â€” fetch paralelo de `leakRoi`; passa ao `LeaksPanel` quando disponÃ­vel
- **`components/hud/LeaksPanel.tsx`** â€” custo mensal estimado por leak (`~$X/mÃªs`); badge `CRÃTICO` com Ã­cone chama para `priority_rank â‰¤ 3`
- **Locales** â€” chaves `leaks.critical` e `leaks.evLoss` adicionadas a `dashboard.json` (PT-BR + EN + ES)

### Backlog

- **`BACKLOG.md`** â€” roadmap atualizado com Sprint I (ðŸ”„), J, K (ðŸ“‹); specs completos de PERF-001 a PERF-006

## [v0.38.0] â€” 2026-05-03 â€” Sprint H: UX-007 Dashboard i18n â€” cards traduzidos

### Frontend â€” Dashboard cards i18n (bug fix)

- **`LeaksPanel.tsx`** â€” `spotLabel()` movido para dentro do componente; `t("leaks.*")` para tÃ­tulo, botÃ£o estudar e descriÃ§Ã£o de leak
- **`BankrollChart.tsx`** â€” botÃµes de perÃ­odo, tÃ­tulo e estado vazio via `t("bankroll.*")`
- **`RecentTournamentsTable.tsx`** â€” cabeÃ§alhos, status (Analisado/Em fila) e `formatDate` com `i18n.language` dinÃ¢mico
- **`DecisionQualityCard.tsx`** â€” array `LABELS` movido para dentro do componente; todos os rÃ³tulos via `t("decisions.*")`
- **`StreetBreakdown.tsx`** â€” tÃ­tulo, tooltip e estado vazio via `t("streets.*")`
- **`PositionChart.tsx`** â€” tÃ­tulo, tooltip e estado vazio via `t("positions.*")`
- **`RecentForm.tsx`** â€” `scoreDot()` movido para dentro do componente; legenda e tÃ­tulo via `t("form.*")`
- **`IcmBreakdown.tsx`** â€” `ICM_LABEL` movido para dentro do componente; rÃ³tulos de pressÃ£o ICM e tÃ­tulo via `t("icm.*")`
- **`LevelCard.tsx`** â€” nÃ­vel, progresso, leaks bloqueadores e link de estudo via `t("level.*")`; pluralizaÃ§Ã£o i18next (`tournament_one`/`tournament_other`)
- **`EmptyDashboard.tsx`** â€” array `MODULES` movido para dentro do componente; upload section e mÃ³dulos via `t("empty.*")`
- **`PlayerStatsCard.tsx`** â€” "em breve", "sem dados", "mÃ£os" e mensagem vazia via `t("playerStats.*")`
- **Locales** â€” ~80 novas chaves adicionadas a `dashboard.json` (PT-BR + EN + ES)

## [v0.37.0] â€” 2026-05-02 â€” Sprint G: UX-006 Header Cleanup + i18n Full Coverage

### Frontend â€” Header simplification

- **`HudHeader.tsx`** â€” removidos badges (NEW/ALPHA) dos itens de nav, pill "Engine Active" e pill com nome do coach
- **`Index.tsx`** â€” coach badge movido para a seÃ§Ã£o hero do dashboard (abaixo do subtÃ­tulo), com Ã­cone `GraduationCap` e ring sutil

### Frontend â€” i18n cobertura completa (5 novos namespaces, 3 idiomas)

- **Novos namespaces** â€” `aicoach`, `coaches`, `profile`, `replayer`, `landing` (PT-BR + EN + ES)
- **`NotFound.tsx`** â€” traduzido via `common.notFound.*`
- **`AICoach.tsx`** â€” traduzido via namespace `aicoach`; sugestÃµes, saudaÃ§Ã£o, painel de contexto e sessÃ£o
- **`Tournaments.tsx`** â€” traduzido; badges de formato, stats, cabeÃ§alhos de tabela, estados vazios
- **`TournamentDetail.tsx`** â€” traduzido; `SEVERITY_META` e `FILTERS` movidos para dentro do componente; `ScoreLabel` inline
- **`StudyPlan.tsx`** â€” traduzido; toolbar, KPIs, diagnÃ³stico, roadmap semanal, recursos, botÃµes de dia
- **`CoachesDirectory.tsx`** â€” traduzido; `SORT_OPTIONS` movido para dentro de `FilterPanel`
- **`PublicCoachProfile.tsx`** â€” traduzido; loading, nÃ£o encontrado, botÃ£o voltar, contadores
- **`StudentProfile.tsx`** â€” traduzido; tÃ­tulos de seÃ§Ã£o, coach linkado, botÃµes de unlink
- **`Replayer.tsx`** â€” traduzido; navegaÃ§Ã£o de mÃ£os, controles, action log, painel EV, formulÃ¡rio de anotaÃ§Ã£o de coach, resultado do showdown
- **`Landing.tsx`** â€” traduzido completamente; arrays `PLANS`, `HOW_IT_WORKS`, `FEATURES` movidos para dentro dos sub-componentes; cada seÃ§Ã£o usa `useTranslation("landing")`
- **Locales atualizados** â€” `tournaments.json` + `common.json` + `study.json` com novas chaves; `landing.json` reescrito com estrutura completa (planos, CTA, footer)

---

## [v0.36.0] â€” 2026-05-02 â€” Sprint D: BACK-016 WhatsApp Coaching Drills

### Backend

- **`leaklab/whatsapp_bot.py`** â€” mÃ³dulo do bot: `send_text()` (Cloud API v19), `handle_incoming()` (dispatcher), `_handle_answer()` (correÃ§Ã£o MCQ), `_send_question()` (busca top leak e gera exercÃ­cio), `_generate_exercise()` (Claude Haiku â†’ JSON com question/answer/explanation), `_fallback_exercise()` (template local sem LLM); estado de questÃµes pendentes em dict in-memory por nÃºmero
- **`api/app.py`** â€” 3 novas rotas:
  - `GET /whatsapp/webhook` â€” verificaÃ§Ã£o de webhook pelo Meta (hub.challenge)
  - `POST /whatsapp/webhook` â€” recebe eventos Meta, despacha para `handle_incoming()`; sempre retorna 200 imediato
  - `PATCH /profile/phone` â€” vincula/desvincula nÃºmero de WhatsApp ao usuÃ¡rio logado (validaÃ§Ã£o E.164, unicidade)
  - `GET /auth/me` â€” agora retorna `whatsapp_phone`
- **`database/schema.py`** â€” migration `ALTER TABLE users ADD COLUMN whatsapp_phone TEXT UNIQUE` (Postgres + SQLite)
- **`database/repositories.py`** â€” `get_user_by_phone(phone)` + `update_user_phone(user_id, phone)`
- **`.env`** â€” adicionado `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`, `WHATSAPP_VERIFY_TOKEN`

### Frontend

- **`lib/api.ts`** â€” `auth.updatePhone(phone)` â†’ `PATCH /profile/phone`; `UserProfile.whatsapp_phone` adicionado ao tipo
- **`pages/StudentProfile.tsx`** â€” nova seÃ§Ã£o "WhatsApp â€” Coaching Drills": campo para inserir nÃºmero (formato DDI+DDD), botÃ£o Salvar e botÃ£o Desvincular; mostra nÃºmero atual vinculado
- **`frontend/.env`** â€” `VITE_WHATSAPP_NUMBER=15556305701` (nÃºmero sandbox Meta; substituir pelo nÃºmero real em produÃ§Ã£o)

### Fluxo
1. UsuÃ¡rio vincula nÃºmero em Perfil â†’ WhatsApp
2. Clica "Iniciar no WhatsApp" no StudyPlan â†’ abre conversa com o bot
3. Qualquer mensagem â†’ bot busca top leak, gera MCQ via Claude Haiku, envia a questÃ£o
4. UsuÃ¡rio responde A/B/C/D â†’ bot corrige e explica
5. PrÃ³xima mensagem â†’ novo exercÃ­cio

---

## [v0.35.0] â€” 2026-05-02 â€” Sprint F: UX-005 InternacionalizaÃ§Ã£o (i18n) PT/EN/ES

### Frontend

- **`i18n/index.ts`** â€” setup `i18next` + `i18next-browser-languagedetector`; auto-detecta via `localStorage` â†’ `navigator.language`; fallback `pt-BR`; namespaces: `common`, `dashboard`, `tournaments`, `study`, `auth`
- **`main.tsx`** â€” importa `./i18n` para inicializar antes do React
- **Locales PT-BR** â€” `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **Locales EN** â€” `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **Locales ES** â€” `common.json`, `dashboard.json`, `tournaments.json`, `study.json`, `auth.json`
- **`HudHeader.tsx`** â€” `LanguageSwitcher` dropdown (ðŸ‡§ðŸ‡· PT Â· ðŸ‡ºðŸ‡¸ EN Â· ðŸ‡ªðŸ‡¸ ES) no canto direito; nav labels e botÃ£o Import traduzidos via `t()`; preferÃªncia salva em `localStorage` (`leaklab_lang`)
- **`Login.tsx`** â€” labels, placeholders e estados de loading traduzidos via namespace `auth`
- **`Index.tsx`** â€” eyebrow, tÃ­tulo, subtÃ­tulo, KPIs, AI Confidence e footer traduzidos via namespaces `dashboard` + `common`

---

## [v0.34.0] â€” 2026-05-02 â€” Sprint C+E: BACK-014 + BACK-017 Revenue Share + Admin Panel

### Backend

- **`schema.py`** â€” novo campo `users.referral_coach_id` + `users.suspended`; nova tabela `coach_payments` (coach_id, period YYYY-MM, active_students, amount_cents, status, paid_at) em SQLite e PostgreSQL via `_run_migrations`
- **`auth.py`** â€” novo decorator `require_admin()` que valida `role == 'admin'` no banco
- **`repositories.py`** â€” novas funÃ§Ãµes: `calculate_coach_payout()` (lÃ³gica de revenue share), `get_admin_dashboard_stats()`, `get_all_users()`, `get_all_users_count()`, `update_user_admin()`, `get_coaches_with_payout_status()`, `upsert_coach_payment()`, `mark_coach_payment_paid()`, `get_coach_finance_summary()`, `get_coach_finance_students()`, `get_coach_finance_history()`, `get_admin_activity_logs()`
- **`app.py`** â€” 10 novos endpoints:
  - `GET /admin/dashboard` â€” MRR estimado, usuÃ¡rios ativos, distribuiÃ§Ã£o de planos, repasses pendentes
  - `GET /admin/users` â€” lista paginada com filtros (plan, role, search)
  - `PATCH /admin/users/<id>` â€” suspender/alterar plano
  - `GET /admin/finance/coaches` â€” repasses do ciclo com auto-upsert
  - `PATCH /admin/finance/coaches/<id>/pay` â€” marcar como pago
  - `GET /admin/finance/export.csv` â€” exportaÃ§Ã£o CSV para processamento bancÃ¡rio
  - `GET /admin/logs` â€” Ãºltimas importaÃ§Ãµes de torneios
  - `GET /coach/finance/summary` â€” ciclo atual do coach
  - `GET /coach/finance/students` â€” alunos com status de atividade
  - `GET /coach/finance/history` â€” histÃ³rico de repasses recebidos

### Frontend

- **`api.ts`** â€” tipos `AdminStats`, `AdminUser`, `CoachPayout`, `CoachFinanceSummary`, `CoachFinanceStudent`, `CoachPaymentRecord`; objetos `adminDashboard` e `coachFinance` com todas as chamadas
- **`pages/admin/AdminDashboard.tsx`** â€” painel admin com 4 abas: VisÃ£o Geral (KPIs + distribuiÃ§Ã£o de planos), UsuÃ¡rios (tabela paginada com filtros, alterar plano inline, suspender/reativar), Financeiro (tabela de repasses por perÃ­odo, "Marcar pago", exportar CSV), Logs (Ãºltimas importaÃ§Ãµes)
- **`CoachDashboard.tsx`** â€” nova aba "Financeiro": resumo do ciclo atual (alunos totais/ativos, receita estimada, mensalidade zerada), lista de alunos com badge Ativo/Inativo, histÃ³rico de repasses
- **`App.tsx`** â€” `AdminRoute` guard + rota `/admin`; `PublicRoute` redireciona admin para `/admin`
- **`HudHeader.tsx`** â€” nav item "Admin" com Ã­cone Shield para role admin

### Regras de negÃ³cio implementadas
- 1â€“3 alunos ativos: mensalidade do coach zerada, R$0 de repasse
- 4â€“9 alunos ativos: mensalidade zerada + R$15/aluno/mÃªs
- 10+ alunos ativos: mensalidade zerada + R$20/aluno/mÃªs
- Aluno ativo = importou â‰¥1 torneio nos Ãºltimos 30 dias + plano PRO

---

## [v0.33.0] â€” 2026-05-02 â€” Sprint B: UX-002 Responsividade Mobile/Tablet

### Frontend

- **`HudHeader.tsx`** â€” bottom navigation bar fixa em mobile (`fixed bottom-0 z-50 md:hidden`) com Ã­cone + label curto por rota; FAB de import (`fixed bottom-[72px] right-4 size-12`) substitui o botÃ£o de import do header em mobile; padding do header ajustado para `px-4 md:px-8`
- **`HudLayout.tsx`** â€” padding inferior `pb-28 md:pb-8` para deixar clearance acima do bottom nav fixo
- **`Index.tsx`** â€” grid de KPIs vai de 1-col para `grid-cols-2 lg:grid-cols-4` (2 colunas em mobile); sidebar com LevelCard/LeaksPanel usa `order-first lg:order-none` â€” aparece antes dos grÃ¡ficos em mobile
- **`RecentTournamentsTable.tsx`** â€” modo duplo: lista de cards clicÃ¡veis `md:hidden` + tabela `hidden md:block overflow-x-auto`; `formatDateShort()` para data compacta nos cards mobile
- **`Tournaments.tsx`** â€” modo duplo: lista de cards mobile com profit, badge, delete + tabela desktop; empty state diferente por viewport
- **`Replayer.tsx`** â€” barra de controles vira sticky bottom em mobile (`sticky bottom-14 z-30 border-t bg-background/95 backdrop-blur-md`) e volta ao painel normal em desktop (`md:static md:border md:rounded-xl md:bg-hud-surface`)
- **`TournamentDetail.tsx`** â€” tabelas de fase (M-Ratio) e textura de board recebem `overflow-x-auto` para scroll horizontal em mobile
- **`StudentDetail.tsx`** â€” tabs do detalhe do aluno (coach view) recebem `overflow-x-auto` + `shrink-0` nos botÃµes para scroll horizontal em telas pequenas

---

## [v0.32.0] â€” 2026-05-02 â€” Sprint 4: BACK-001 + BACK-005 (confirmados + gap fechado)

### Backend
- **`api/app.py` â†’ `history_tournament`** â€” enriquece cada decisÃ£o com `has_annotation: bool` usando `get_annotations_for_decisions`; aluno agora sabe quais mÃ£os tÃªm anotaÃ§Ã£o do coach sem fazer request extra

### Frontend
- **`api.ts`** â€” `TournamentDecision` ganha campo opcional `has_annotation?: boolean`
- **`TournamentDetail.tsx`** â€” `Hand.hasAnnotation` propagado via `groupByHand` (true se qualquer decisÃ£o do grupo tem anotaÃ§Ã£o); badge "Coach" com Ã­cone GraduationCap aparece ao lado do severity badge em mÃ£os anotadas pelo coach

### Confirmado jÃ¡ implementado (BACK-001 e BACK-005 core)
- Tabela `coach_hand_annotations` + endpoints GET/POST/DELETE `/coach/student/:id/hand-annotations`
- `AnnotationForm` no `WorstTab` do `StudentDetail.tsx` (visÃ£o coach)
- Replayer: painel de anotaÃ§Ã£o para coach (form com modo/aÃ§Ã£o/veredito) e balÃ£o read-only para aluno
- Ambos os endpoints de replay (`/replay/:t/:h` e `/coach/student/:id/replay/:t/:h`) incluem `coach_annotations`
- Badge "âœ“ Coach" na listagem de torneios do aluno (`Tournaments.tsx`) via `get_reviewed_tournament_ids()`

---

## [v0.31.0] â€” 2026-05-02 â€” Sprint A: UX-001 + UX-003 + LLM template upgrade

### Frontend â€” UX-001: Lista de torneios melhorada
- **`RecentTournamentsTable.tsx`** â€” fallback de nome agora usa `#tournament_id` (era `site`); badge detection estendida: +SAT (satellite), +KO (knockout/bounty/PKO), +SNG (sit & go variants); subtitle mostra `{hands_count} mÃ£os` abaixo do ID
- **`Tournaments.tsx`** â€” coluna "ID" renomeada para "Torneio"; mesmas melhorias de badge e fallback; `{hands_count} mÃ£os` no subtitle

### Frontend â€” UX-003: Tooltips e score auto-explicativo
- **`TournamentDetail.tsx`** â€” componente `InfoTooltip` (HelpCircle + Radix Tooltip) adicionado a cabeÃ§alhos das seÃ§Ãµes fase/textura e Ã s colunas "Erros %" e "Score MÃ©dio"; tooltips explicam os thresholds (M-Ratio, texturas de board com exemplos de cartas, % de erro, faixas do score)
- **`TournamentDetail.tsx`** â€” componente `ScoreLabel` exibe rÃ³tulo colorido (Ã“timo / Bom / Moderado / Alto) inline ao score para leitura imediata sem referÃªncia externa

### Backend / IA â€” LLM template upgrade
- **`llm_explainer.py`** â€” `analyze_single_decision` migrada de 3 parÃ¡grafos genÃ©ricos para template estruturado em 5 seÃ§Ãµes: âŒ O Erro / ðŸ“ A MatemÃ¡tica / ðŸ§­ O Contexto / âœ… A AÃ§Ã£o Correta / ðŸ’¡ A LiÃ§Ã£o; `max_tokens` 500 â†’ 900

### Infra â€” BACK-007 (confirmado como jÃ¡ implementado)
- `UploadQueue.tsx` + `HudHeader.tsx` jÃ¡ implementavam upload mÃºltiplo com fila sequencial â€” confirmado durante Sprint A; nenhuma mudanÃ§a necessÃ¡ria

---

## [v0.30.0] â€” 2026-05-02 â€” AnÃ¡lise por Fase e Textura de Board

### Backend
- **`leaklab/board_texture.py`** â€” novo mÃ³dulo: `classify_board_texture(board_json)` classifica boards pÃ³s-flop em `dry | coordinated | wet | monotone | paired` usando span de ranks e contagem de naipes
- **`repositories.py`** â€” `get_phase_analysis(tournament_db_id)`: agrupa decisÃµes por fase (Folgado Mâ‰¥20 / MÃ©dio M10-20 / PressÃ£o M6-10 / CrÃ­tico M<6) derivando fase do `m_ratio`; `get_texture_analysis(tournament_db_id)`: classifica boards pÃ³s-flop e retorna stats por textura
- **`GET /history/tournament/<id>/phase_analysis`** â€” novo endpoint: retorna distribuiÃ§Ã£o de erros e score mÃ©dio por fase de torneio
- **`GET /history/tournament/<id>/texture_analysis`** â€” novo endpoint: retorna distribuiÃ§Ã£o de erros pÃ³s-flop por textura de board

### Frontend
- **`TournamentDetail.tsx`** â€” duas novas seÃ§Ãµes entre o grid de stats e os filtros: tabela de AnÃ¡lise por Fase e tabela de PÃ³s-Flop por Textura de Board; cÃ³digo de cores: verde (<25% erros), amarelo (25-40%), vermelho (>40%)
- **`api.ts`** â€” `tournaments.phaseAnalysis()` e `tournaments.textureAnalysis()`; novas interfaces `PhaseData` e `TextureData`

---

## [v0.29.0] â€” 2026-05-02 â€” BACK-015: MigraÃ§Ã£o Mercado Pago â†’ Stripe

### Pagamentos
- **`stripe_gateway.py`** â€” novo gateway: `create_subscription`, `cancel_subscription`, `get_subscription`, `get_payment`, `validate_webhook`; usa Stripe Subscriptions API com `payment_behavior=default_incomplete`
- **`POST /subscription/checkout`** â€” simplificado: recebe sÃ³ `plan`, cria Stripe Customer + Subscription, retorna `{ client_secret, subscription_id }` para confirmaÃ§Ã£o no frontend
- **`POST /subscription/activate`** â€” novo: verifica `PaymentIntent.status` e ativa o plano no banco (chamado pelo frontend apÃ³s `stripe.confirmPayment`)
- **`POST /subscription/webhook`** â€” reescrito para eventos Stripe: `invoice.payment_succeeded` â†’ ativa plano; `customer.subscription.deleted` â†’ reverte para free; sem secret configurado aceita sem validaÃ§Ã£o (dev mode)
- **`POST /subscription/cancel`** â€” usa `stripe.Subscription.cancel()` via gateway
- Removido `mercadopago_gateway.py` (todas as rotas MP descontinuadas)

### Frontend
- **`CheckoutModal.tsx`** â€” reescrito com `@stripe/stripe-js`; `loadStripe` + `PaymentElement` substitui 8 campos manuais do MP; `Promise.all` carrega SDK e intent em paralelo; confirmaÃ§Ã£o via `stripe.confirmPayment({ redirect: 'if_required' })` + `/subscription/activate`
- **`api.ts`** â€” `checkout()` simplificado (sÃ³ `plan`); novo `activate(plan, payment_intent_id, subscription_id)`

### DependÃªncias
- `requirements.txt`: + `stripe==12.0.0`; removido `requests` (nÃ£o mais usado pelo gateway)
- `package.json`: + `@stripe/stripe-js`

### Env vars necessÃ¡rias
| VariÃ¡vel | DescriÃ§Ã£o |
|---|---|
| `STRIPE_SECRET_KEY` | Chave secreta Stripe (`sk_test_...` / `sk_live_...`) |
| `STRIPE_PUBLISHABLE_KEY` | NÃ£o usada no backend |
| `STRIPE_WEBHOOK_SECRET` | Secret do webhook Stripe (`whsec_...`) |
| `STRIPE_PRICE_STARTER` | Price ID do plano Starter (`price_...`) |
| `STRIPE_PRICE_PRO` | Price ID do plano Pro (`price_...`) |
| `VITE_STRIPE_PUBLISHABLE_KEY` | Chave pÃºblica Stripe para o frontend |

### Testes
- `test_subscription.py` reescrito: 25 testes cobrindo checkout, activate, invoices, cancel, webhook â€” 0 regressÃµes

---

## [v0.28.1] â€” 2026-05-01 â€” BACK-015 fix: payer.identification + debugging

### Pagamentos
- **`mercadopago_gateway.py`** â€” `create_subscription` aceita `identification_type`/`identification_number`; inclui `payer.identification` no body do `/v1/payments` (obrigatÃ³rio no Brasil); log completo do response de erro
- **`POST /subscription/checkout`** â€” extrai `identification_type`, `identification_number` e `payer_email` do body; `payer_email` do form substitui email do usuÃ¡rio quando fornecido (permite usar email de conta teste MP)
- **`CheckoutModal.tsx`** â€” extrai `identificationType`, `identificationNumber`, `cardholderEmail` de `getCardFormData()` e envia ao backend
- **`api.ts`** â€” `subscription.checkout()` aceita os novos campos

### Testes
- 2 novos testes: `test_checkout_forwards_identification`, `test_checkout_payer_email_override`
- 23 testes de subscription â€” 0 regressÃµes

---

## [v0.28.0] â€” 2026-04-27 â€” BACK-015: Mercado Pago Transparent Checkout

### Pagamentos
- **`mercadopago_gateway.py`** â€” novo mÃ³dulo: `get_or_create_plan`, `create_subscription`, `cancel_subscription`, `get_subscription`, `get_payment`, `validate_webhook_signature` (HMAC-SHA256)
- **`POST /subscription/checkout`** â€” cria assinatura recorrente MP via card token; rate limit 5/h; atualiza `plan` e `mp_subscription_id` do usuÃ¡rio no banco
- **`POST /subscription/webhook`** â€” recebe eventos MP (`subscription_preapproval`, `payment`); valida assinatura HMAC-SHA256; atualiza plano e salva pagamentos
- **`GET /subscription/invoices`** â€” retorna histÃ³rico de pagamentos do usuÃ¡rio (limit 20)
- **`POST /subscription/cancel`** â€” cancela assinatura MP ativa e reverte plano para `free`

### Schema
- Tabela `payments` (id, user_id, plan, amount_cents, currency, status, gateway, gateway_id, gateway_sub_id, period_start, period_end, created_at)
- Coluna `mp_subscription_id` adicionada a `users`

### Frontend
- **`CheckoutModal.tsx`** â€” modal de checkout transparente: carrega MP JS SDK v2 dinamicamente, inicializa `mp.cardForm()` com iframes seguros para dados do cartÃ£o, submete token ao backend, exibe sucesso/erro e chama `refreshUser()`
- **`AccountMenu.tsx`** â€” botÃµes "Starter R$19" e "Pro R$39" abrem `CheckoutModal` (substituindo links `mailto:`)
- **`QuotaBanner.tsx`** â€” idem: botÃµes de upgrade abrem `CheckoutModal`
- **`api.ts`** â€” `subscription.checkout()`, `subscription.invoices()`, `subscription.cancel()`

### Testes
- 227 testes â€” 0 regressÃµes

---

## [v0.27.0] â€” 2026-04-27 â€” BACK-011 pt.2: Anti-Prompt Injection + ModeraÃ§Ã£o de ConteÃºdo

### SeguranÃ§a â€” Camada 1: Anti-Prompt Injection
- **`content_moderation.py`** â€” novo mÃ³dulo com `sanitize_llm_input(text, max_len)`: remove 14 padrÃµes de injection (EN + PT-BR) via regex antes de qualquer chamada ao LLM; tenta de role spoofing (`system:`, `assistant:`), token markers (`<|...|>`, `[INST]`), comandos de esquecimento e personas alternativas
- **`coach_chat_reply`** â€” mensagem do usuÃ¡rio sanitizada antes de entrar no payload do Claude
- **`analyze_single_decision`** â€” campo `note` (texto livre do hand history) sanitizado antes de ir ao LLM
- **`/coach/chat`** â€” sanitizaÃ§Ã£o no endpoint antes de repassar ao `coach_chat_reply`; erro interno nÃ£o mais exposto na resposta
- **AnotaÃ§Ãµes de coach** â€” `comment` sanitizado via `sanitize_llm_input` antes de salvar no banco
- Todas as tentativas detectadas sÃ£o logadas com `log.warning` para anÃ¡lise posterior

### SeguranÃ§a â€” Camada 2: ModeraÃ§Ã£o de ConteÃºdo (blocklist local v1)
- **`moderate_text(text)`** â€” verifica texto livre contra blocklist PT-BR + EN cobrindo: discurso de Ã³dio, ataques, spam/scam, links de redes sociais suspeitos, conteÃºdo adulto explÃ­cito; retorna `(is_clean, reason)` e loga flags
- **`/coach-profile` (POST)** â€” campo `bio` verificado antes de salvar; retorna 422 se flaggeado
- **`/coach/review` (POST)** â€” `review_text` verificado antes de salvar; retorna 422 se flaggeado
- **`/coach/student/:id/hand-annotations` (POST)** â€” `comment` verificado + sanitizado antes de salvar

### Schema
- Coluna `moderation_status TEXT DEFAULT 'approved'` adicionada a `coach_profiles`, `coach_reviews`, `coach_hand_annotations` (PostgreSQL: `ALTER TABLE IF NOT EXISTS`; SQLite: migration lazy)

### Testes
- 227 testes â€” 0 regressÃµes

---

## [v0.26.0] â€” 2026-04-27 â€” BACK-011: Hardening de seguranÃ§a

### SeguranÃ§a â€” CrÃ­tico
- **bcrypt** â€” senhas agora armazenadas com bcrypt + salt aleatÃ³rio; migraÃ§Ã£o transparente: hashes SHA-256 legados sÃ£o re-hasheados no prÃ³ximo login com sucesso
- **SECRET_KEY forÃ§ado** â€” inicializaÃ§Ã£o levanta `RuntimeError` em produÃ§Ã£o se `LEAKLAB_SECRET` nÃ£o estiver definido ou tiver menos de 32 caracteres; aviso no terminal em desenvolvimento

### SeguranÃ§a â€” Alta
- **`require_coach` usa role do banco** â€” antes validava o campo `role` do JWT (forjÃ¡vel); agora consulta o banco em cada requisiÃ§Ã£o protegida
- **Token nÃ£o aceito via URL** â€” `_extract_token()` removia fallback `?token=` que expunha tokens nos logs de servidor; aceita apenas `Authorization: Bearer` e cookie
- **IDOR em anotaÃ§Ãµes de coach corrigido** â€” endpoint `POST /coach/student/:id/hand-annotations` agora valida que `decision_id` pertence ao aluno antes de salvar
- **Headers de seguranÃ§a HTTP** â€” `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy` adicionados a toda resposta; `Strict-Transport-Security` ativado em produÃ§Ã£o (`RENDER=true`)

### SeguranÃ§a â€” MÃ©dia
- **Rate limiting** â€” Flask-Limiter instalado; limites por IP: `/auth/register` 10/min, `/auth/login` 15/min, `/analyze` 30/h, `/analyze/decision` e `/analyze/hand-coach` 30/h, `/analyze/tournament-summary` 20/h; desativado automaticamente em testes (`app.testing`)
- **ValidaÃ§Ã£o de extensÃ£o de arquivo** â€” upload em `/analyze` rejeita arquivos que nÃ£o terminem em `.txt`
- **Mensagens de erro sanitizadas** â€” exceÃ§Ãµes internas logadas com `log.exception()` em vez de expostas no corpo da resposta
- **Senha mÃ­nima 8 caracteres** â€” aumentado de 6 para 8 em `/auth/register`
- **Role restrito no cadastro** â€” valores fora de `player/coach` sÃ£o coercidos para `player` silenciosamente

### Infraestrutura
- `bcrypt==4.2.1` e `Flask-Limiter==3.8.0` adicionados ao `requirements.txt`
- `repositories.py`: funÃ§Ãµes `_hash_password`, `_check_password`, `decision_belongs_to_student` extraÃ­das; `update_user_email`, `change_user_password`, `check_password` migradas para usar bcrypt

### Testes
- 227 testes â€” 0 regressÃµes

---

## [v0.25.0] â€” 2026-04-27 â€” UX-004: Menu de conta com plano e uso

### Adicionado
- **`AccountMenu`** â€” dropdown acessÃ­vel ao clicar no nome/plano no header; exibe username, badge de plano colorido por tier (Free/Starter/Pro/Coach), barras de uso mensal (torneios + anÃ¡lises LeakLabs), CTAs de upgrade contextuais e links para Perfil e Sair
- **`/auth/me` inclui quota** â€” resposta agora inclui `plan`, `tournaments_used`, `ai_calls_used`, `plan_limits`; elimina segundo request separado ao `/subscription/status`

### Alterado
- **`HudHeader`** â€” item "Perfil" removido do menu de navegaÃ§Ã£o do jogador; bloco username+logout substituÃ­do por `AccountMenu`; Dashboard corrigido para `/dashboard`
- **`UserProfile`** â€” interface TypeScript estendida com campos de quota
- **Dashboard (`Index.tsx`)** â€” `QuotaBanner` removido da sidebar (redundante com `AccountMenu`)

---

## [v0.24.0] â€” 2026-04-27 â€” Proposta B: 3 planos (Free / Starter / Pro)

### Adicionado
- **Plano Starter R$19/mÃªs** â€” 20 torneios + 40 anÃ¡lises/mÃªs; pÃºblico alvo: jogador casual que ultrapassou o Free mas nÃ£o precisa de volume de grinder
- **3 planos no `/subscription/plans`** â€” Free, Starter (R$19), Pro (R$39)

### Alterado
- **Plano Pro**: R$15 â†’ **R$39/mÃªs** â€” torneios ilimitados + 150 anÃ¡lises LeakLabs/mÃªs
- **PLAN_LIMITS** â€” `starter: {tournaments: 20, ai_calls: 40}` Â· `pro: {tournaments: None, ai_calls: 150}`
- **Landing page** â€” seÃ§Ã£o Planos migrada para grid de 3 colunas; badge "Mais popular" no Starter, badge "Grinder" + destaque primÃ¡rio no Pro
- **QuotaBanner** â€” botÃµes Starter R$19 + Pro R$39 lado a lado no banner de limite atingido

---

## [v0.23.0] â€” 2026-04-27 â€” UX-003: Landing page pÃºblica

### Adicionado
- **Landing page pÃºblica em `/`** â€” apresentaÃ§Ã£o do produto para visitantes nÃ£o autenticados; seÃ§Ãµes: Hero com nÃ­veis preview, EstatÃ­sticas, Como Funciona (3 passos), Funcionalidades (6 cards), Planos (Free vs Pro), CTA final e Footer
- **Rota `/dashboard`** â€” dashboard do jogador movido de `/` para `/dashboard`; usuÃ¡rios autenticados sÃ£o redirecionados automaticamente para o destino correto ao acessar `/` ou `/login`
- **`PublicRoute`** â€” guarda de rota pÃºblico: redireciona usuÃ¡rio jÃ¡ logado para `/dashboard` (jogador) ou `/coach-dashboard` (coach), evitando que veja a landing ou tela de login desnecessariamente

### Alterado
- `App.tsx` â€” `/` agora renderiza `Landing` (via `PublicRoute`); `/login` tambÃ©m usa `PublicRoute`; `/dashboard` Ã© a nova rota protegida do jogador; `CoachRoute` redireciona nÃ£o-coaches para `/dashboard`
- `Login.tsx` â€” pÃ³s-login redireciona jogador para `/dashboard` em vez de `/`
- `HudHeader.tsx` â€” logo aponta para `/dashboard` em vez de `/` (usuÃ¡rio autenticado)

---

## [v0.22.0] â€” 2026-04-27 â€” BACK-010: Freemium + quota + backlog expandido

### Adicionado
- **Planos freemium e controle de quota** â€” plano Free: 3 torneios/mÃªs + 10 anÃ¡lises IA/mÃªs; plano Pro: ilimitado; quota resetada automaticamente no inÃ­cio de cada mÃªs (lazy reset por usuÃ¡rio)
- **Endpoints de subscription** â€” `GET /subscription/plans`, `GET /subscription/status`, `POST /subscription/upgrade`; upgrade manual em v1 (sem gateway de pagamento)
- **Middleware de quota no backend** â€” `_check_upload_quota()` antes do `/analyze`; `_check_ai_quota()` antes de `/analyze/decision`, `/analyze/hand-coach` e `/analyze/tournament-summary`; retorna HTTP 402 com `quota_exceeded: true` quando limite atingido
- **Cache de tournament summary** â€” `/analyze/tournament-summary` agora retorna o summary jÃ¡ salvo no banco quando disponÃ­vel, sem chamar o LLM novamente; economiza quota e reduz latÃªncia
- **QuotaBanner no dashboard** â€” barra de uso de torneios e anÃ¡lises IA exibida na sidebar do dashboard; aparece somente para plano Free e apenas quando â‰¥ 80% do limite foi atingido; botÃ£o de upgrade via email em v1
- **Busca corrigida em /tournaments** â€” placeholder atualizado de "herÃ³i" para "nome, tipo (MTT/SNG) ou ID"
- **Backlog expandido** â€” UX-002 (responsividade mobile/tablet, ~15h) e BACK-014 (revenue share para coaches, ~20h) documentados com escopo, modelo de dados e esforÃ§o estimado

### Backend
- `backend/database/schema.py` â€” colunas `tournaments_this_month`, `ai_calls_this_month`, `quota_reset_at` na tabela `users`; migrations para SQLite e Postgres
- `backend/database/repositories.py` â€” `PLAN_LIMITS`, `get_quota_status()`, `increment_tournament_count()`, `increment_ai_calls()`, `_maybe_reset_quota()` (lazy reset mensal)
- `backend/api/app.py` â€” `_check_upload_quota()`, `_check_ai_quota()`; subscription endpoints; quota wiring em analyze + LLM endpoints

### Frontend
- `frontend/src/lib/api.ts` â€” interface `QuotaStatus`; namespace `subscription` com `status()`, `plans()`, `upgrade()`
- `frontend/src/components/hud/QuotaBanner.tsx` â€” componente novo com barras de progresso e CTA de upgrade
- `frontend/src/pages/Index.tsx` â€” `QuotaBanner` inserido no topo da sidebar
- `frontend/src/pages/Tournaments.tsx` â€” placeholder da busca corrigido

---

## [v0.21.0] â€” 2026-04-26 â€” UX: Logos de sites, auto-reload pÃ³s-import, nÃ­veis rebalanceados

### Adicionado
- **Logo dos sites na lista de torneios** â€” componente `SiteLogo` exibe favicon do site (PokerStars, GGPoker, 888Poker, Winamax, ACR) em container 24Ã—24 com tooltip do nome completo; fallback para sigla em texto se a imagem falhar; visÃ­vel na `RecentTournamentsTable` (dashboard) e na lista completa `/tournaments`

### Corrigido
- **Auto-reload pÃ³s-importaÃ§Ã£o em qualquer tela** â€” `UploadQueue` agora dispara evento global `leaklab:tournament-imported` a cada arquivo processado; `Tournaments.tsx` escuta o evento e chama `reload()` automaticamente; antes, importar pelo botÃ£o do header na tela `/tournaments` nÃ£o atualizava a lista
- **Badge SNG/MTT incorreto** â€” `_extract_tournament_name()` agora conta jogadores Ãºnicos no arquivo HH: â‰¤ 9 = SNG (sem reposiÃ§Ã£o de mesa), > 9 = MTT (jogadores vindos de mesas quebradas); resolve badge "MTT" incorreto em Sit & Go PokerStars
- **Thresholds de nÃ­vel rebalanceados** â€” escala anterior era leniente demais (SÃ³lido comeÃ§ava em 75%); nova escala: Iniciante < 60%, Estudante 60â€“69%, Grinder 70â€“76%, Regular 77â€“85%, SÃ³lido 86â€“91%, Expert 92â€“95%, Elite 96%+; calibrada para que 83â€“85% std_pct = Regular

### Frontend
- `frontend/src/components/hud/SiteLogo.tsx` â€” componente novo com mapa de favicons e fallback de sigla
- `frontend/src/components/hud/RecentTournamentsTable.tsx` â€” logo inline, badge corrigido
- `frontend/src/pages/Tournaments.tsx` â€” coluna Rede vira logo; listener de reload pÃ³s-import
- `frontend/src/components/hud/UploadQueue.tsx` â€” dispara `CustomEvent('leaklab:tournament-imported')` apÃ³s cada upload concluÃ­do

### Backend
- `backend/database/repositories.py` â€” thresholds de `get_player_level()` atualizados
- `backend/api/app.py` â€” `_extract_tournament_name()` usa contagem de jogadores Ãºnicos para distinguir SNG de MTT

---

## [v0.20.0] â€” 2026-04-26 â€” UX-001: Nome e Tipo do Torneio na Lista

### Adicionado
- **Nome do torneio na lista de torneios** (UX-001) â€” substituÃ­do o par "site â€¢ nome do hero" pelo nome descritivo do torneio (ex: "Spin&Gold #14", "NLH $2.20"); badge "MTT" / "Spin&Go" ao lado do nome; subtext exibe site + ID interno para rastreabilidade
- Coluna `tournament_name TEXT` adicionada Ã  tabela `tournaments` (SQLite + PostgreSQL); migration automÃ¡tica via `_run_migrations`

### Backend
- `backend/api/app.py` â€” novo helper `_extract_tournament_name()`: GGPoker extrai nome do header (`Tournament #N, Spin&Gold #14 Hold'em`); PokerStars constrÃ³i label do buy-in (`NLH $2.20`); chamado no `/analyze` e persistido com o torneio
- `backend/database/repositories.py` â€” `save_tournament()` aceita `tournament_name`; `get_tournaments()` inclui o campo no SELECT
- `backend/database/schema.py` â€” coluna `tournament_name TEXT` nas definiÃ§Ãµes CREATE TABLE e nas migrations SQLite/Postgres

### Frontend
- `frontend/src/lib/api.ts` â€” `Tournament.tournament_name?: string | null` adicionado Ã  interface
- `frontend/src/components/hud/RecentTournamentsTable.tsx` â€” helper `formatTournamentLabel()` e `formatBadge()`; cÃ©lula "Torneio" exibe nome + badge de formato + subtext com site e ID
- `frontend/src/pages/coach/StudentDetail.tsx` â€” `TournamentsTab` usa `tournament_name ?? site` como label principal; subtext inclui site + ID

---

## [v0.19.0] â€” 2026-04-26 â€” BACK-008: Visualizador de Ranges + BUG-001: PrÃªmio de Torneio

### Adicionado
- **Visualizador de Ranges no Replayer** (BACK-008) â€” botÃ£o "Range" aparece durante o preflop; painel lateral 13Ã—13 com ranges GTO-aproximadas para 6 posiÃ§Ãµes (UTG, MP, HJ, CO, BTN, SB, BB); auto-detecta posiÃ§Ã£o do herÃ³i e contexto (open vs facing raise); seletor manual de posiÃ§Ã£o e tipo (Open Â· Call Â· 3-Bet); mÃ£o do herÃ³i destacada em amarelo; legenda com % de mÃ£os e contagem de combos

### Corrigido
- **BUG-001 â€” PrÃªmio incorreto em torneios PokerStars** â€” quando eliminado sem ITM, o arquivo PokerStars contÃ©m apenas "hero finished the tournament" sem prÃªmio; o cÃ³digo caÃ­a no fallback GGPoker que somava todos os chips coletados em potes normais do jogo como prÃªmio; fix: detecta "finished the tournament" antes do fallback e define `prize = 0.0`; torneios afetados devem ser reimportados

### Frontend
- `frontend/src/data/ranges.ts` â€” ranges GTO-aproximadas para Open/Call/3-Bet por posiÃ§Ã£o; expansor de notaÃ§Ã£o de range ("AA-77", "AKs-A2s"); utils `cellHand`, `cellLabel`, `heroHand`, `getCellAction`, `rangeStats`
- `frontend/src/components/replayer/RangeGrid.tsx` â€” grid 13Ã—13 com aspect-square, cores por aÃ§Ã£o (verde=raise, azul=call), destaque da mÃ£o do herÃ³i
- `frontend/src/components/replayer/RangePanel.tsx` â€” painel com auto-detecÃ§Ã£o de posiÃ§Ã£o/contexto, seletores de posiÃ§Ã£o e tipo, rodapÃ© com posiÃ§Ã£o detectada
- `frontend/src/pages/Replayer.tsx` â€” botÃ£o "Range" no header do Action Log (visÃ­vel apenas no preflop); importa `RangePanel` e `LayoutGrid`

### Backend
- `backend/api/app.py` â€” fix em `_extract_financials()`: PokerStars bust-out sem prÃªmio define `prize = 0.0` ao invÃ©s de somar chips coletados em potes

---

## [v0.18.0] â€” 2026-04-26 â€” Sprint 10: Sistema de NÃ­vel do Jogador / GamificaÃ§Ã£o (BACK-009)

### Adicionado
- **Sistema de nÃ­vel do jogador** â€” 7 nÃ­veis baseados no `standard_pct` mÃ©dio dos Ãºltimos 20 torneios (ou 30 dias): Iniciante, Estudante, Grinder, Regular, SÃ³lido, Expert, Elite; sem rÃ³tulos ofensivos; thresholds rebalanceados em v0.21.0
- **LevelCard** â€” componente visual com badge de nÃ­vel (Ã­cone + nome + cor por nÃ­vel), barra de progresso para o prÃ³ximo nÃ­vel, threshold do prÃ³ximo nÃ­vel, leaks que bloqueiam avanÃ§o; modo `compact` para uso no dashboard do coach; link para o plano de estudos (opcional)
- **Dashboard do jogador** â€” `LevelCard` exibido na sidebar do Index.tsx ao lado dos leaks e ICM
- **Dashboard do coach** â€” `LevelCard` em modo compacto na aba "VisÃ£o Geral" de cada aluno; query `coach-student-level`

### Backend
- `get_player_level(user_id, min_tournaments=5, days=30)` â€” calcula nÃ­vel, progresso (0-1), prÃ³ximo nÃ­vel, leaks bloqueadores, contagem de torneios usados
- `GET /metrics/level` â€” retorna nÃ­vel do prÃ³prio jogador
- `GET /coach/student/:id/level` â€” retorna nÃ­vel de um aluno (requer `@require_coach`)

### Frontend
- `LevelCard.tsx` â€” criado com cores por nÃ­vel, barra de progresso, leaks bloqueadores, CTA de plano de estudos
- `api.ts` â€” interface `PlayerLevel`; `metrics.level()`; `coachDashboard.studentLevel(studentId)`
- `Index.tsx` â€” query `player-level` com React Query; `LevelCard` na sidebar
- `StudentDetail.tsx` â€” query `coach-student-level`; `LevelCard` compacto no topo da `OverviewTab`

---

## [v0.17.0] â€” 2026-04-26 â€” Sprint 9: Upload MÃºltiplo com Fila + Perfil do Coach Unificado (BACK-007 + BACK-012)

### Adicionado
- **Upload mÃºltiplo de torneios** (BACK-007) â€” botÃ£o "Import" aceita mÃºltiplos arquivos `.txt` de uma vez; fila processa sequencialmente com badge de status por arquivo (`Em fila`, `Processandoâ€¦`, `Analisado âœ“`, `Erro`); painel flutuante no canto inferior direito com botÃ£o "Fechar" apÃ³s conclusÃ£o
- **Perfil do coach unificado** (BACK-012) â€” pÃ¡gina `/coach-dashboard/profile` reescrita com todos os campos estendidos do Sprint 7 (foto, experiÃªncia, stakes, mÃ©todo, idiomas, maiores resultados, preÃ§os, trial, redes sociais) + aba "AvaliaÃ§Ãµes" com distribuiÃ§Ã£o de ratings; abas "Perfil PÃºblico" e "AvaliaÃ§Ãµes" removidas do CoachDashboard

### Frontend
- `UploadQueue.tsx` â€” hook `useUploadQueue` + `QueuePanel` com `useReducer`; `fileMap` ref para mapear IDs aos `File` objetos sem poluir o estado
- `HudHeader.tsx` â€” input de upload agora com `multiple`; usa `useUploadQueue` ao invÃ©s de upload manual unitÃ¡rio; retorna `<>header + panel</>` via Fragment
- `CoachProfile.tsx` â€” reescrito completamente com `ProfileSection` + `AvaliacoesSection` internos; suprime a versÃ£o anterior com campos bÃ¡sicos apenas
- `CoachDashboard.tsx` â€” tabs "Perfil PÃºblico" e "AvaliaÃ§Ãµes" removidos; imports de lucide e tipos relacionados limpos

---

## [v0.16.0] â€” 2026-04-26 â€” Sprint 8: DiretÃ³rio PÃºblico de Coaches + IntegraÃ§Ã£o Contextual (BACK-006 pt.2 + BACK-013)

### Adicionado
- **DiretÃ³rio pÃºblico de coaches** (`/coaches`) â€” lista com filtros de especialidade, idioma, preÃ§o mÃ¡ximo, trial e ordenaÃ§Ã£o; barra de busca por nome; sidebar colapsÃ¡vel; grid responsivo
- **Perfil pÃºblico do coach** (`/coaches/:id`) â€” avatar, bio, especialidades, maiores resultados, distribuiÃ§Ã£o de avaliaÃ§Ãµes, reviews pÃºblicos, contato e links sociais; CTA contextual para vincular coach via chave de convite
- **Coaches no menu principal** â€” entrada "Coaches" adicionada ao `HudHeader` para jogadores
- **BACK-013 â€” Coaches contextuais no Plano de Estudos** â€” strip de coaches especializados no leak ativo, exibida somente para alunos sem coach; clique direciona ao perfil do coach
- **BACK-013 â€” Coaches no Perfil do aluno** â€” quando sem coach: lista top-3 coaches por rating + formulÃ¡rio de link por chave de convite; substitui botÃ£o antigo sem destino Ãºtil

### Backend
- `GET /coaches` aceita `specialty`, `language`, `trial`, `max_price`, `q`, `sort`, `limit` como filtros
- `GET /coaches/:id` retorna perfil completo + reviews pÃºblicos recentes
- `GET /coaches/:id/reviews` retorna reviews pÃºblicos paginados
- `GET /student/recommended-coaches` â€” endpoint para recomendaÃ§Ã£o futura (stub)

### Frontend
- `CoachesDirectory.tsx` â€” nova pÃ¡gina com `StarRow`, `CoachCard`, `FilterPanel`
- `PublicCoachProfile.tsx` â€” nova pÃ¡gina com distribuiÃ§Ã£o de rating, reviews, formulÃ¡rio de avaliaÃ§Ã£o (alunos vinculados) e CTA de contrataÃ§Ã£o
- `StudyPlan.tsx` â€” `CoachRecommendationStrip` + `CoachMiniCard` injetados no card de diagnÃ³stico de leaks
- `StudentProfile.tsx` â€” `NoCoachDiscovery` com `CoachDiscoveryCard` e formulÃ¡rio de invite key
- `HudHeader.tsx` â€” "Coaches" adicionado ao nav de jogadores

---

## [v0.15.0] â€” 2026-04-26 â€” Sprint 7: Perfil Estendido do Coach + Sistema de AvaliaÃ§Ãµes (BACK-006 pt.1)

### Adicionado
- **Aba "Perfil PÃºblico"** no CoachDashboard â€” formulÃ¡rio completo com foto, experiÃªncia, stakes, mÃ©todo de coaching, idiomas, maiores resultados, preÃ§os, disponibilidade e redes sociais; modo visualizaÃ§Ã£o / ediÃ§Ã£o inline
- **Aba "AvaliaÃ§Ãµes"** no CoachDashboard â€” aggregate de rating com barra de distribuiÃ§Ã£o por estrela + lista de reviews recebidas
- **AvaliaÃ§Ã£o de coach pelo aluno** â€” widget na pÃ¡gina de perfil do aluno (`StudentProfile`) com StarPicker, comentÃ¡rio opcional, ediÃ§Ã£o e exclusÃ£o; aparece somente quando hÃ¡ coach vinculado
- Tabela `coach_reviews` com constraint `UNIQUE(coach_id, student_id)` â€” 1 review por par aluno-coach

### Backend
- `coach_profiles`: 13 novos campos adicionados (`photo_url`, `experience_years`, `stakes`, `coaching_style`, `languages`, `biggest_results`, `price_per_session`, `price_monthly`, `trial_available`, `availability`, `social_youtube`, `social_twitch`, `social_twitter`)
- `GET /coach/profile` agora retorna `avg_rating` e `review_count` calculados em tempo real
- `POST /coach/review` â€” aluno envia/atualiza avaliaÃ§Ã£o (upsert por par coach-aluno)
- `DELETE /coach/review` â€” aluno remove sua avaliaÃ§Ã£o
- `GET /coach/my-review` â€” aluno consulta sua prÃ³pria avaliaÃ§Ã£o
- `GET /coach/reviews` â€” coach vÃª todas as avaliaÃ§Ãµes recebidas com stats detalhados
- Migrations automÃ¡ticas para SQLite e Postgres

---

## [v0.14.0] â€” 2026-04-26 â€” Sprint 6: Feed de Atividade + Baseline de Coaching (BACK-002)

### Adicionado
- **Aba "Progresso"** no perfil do aluno (coach) â€” baseline de coaching com comparaÃ§Ã£o antes/depois + feed de atividade em timeline
- **Baseline de coaching** â€” coach define data de inÃ­cio do acompanhamento; armazenado por par `(coach_id, student_id)` com nota opcional; editÃ¡vel/removÃ­vel
- **ComparaÃ§Ã£o antes/depois** â€” mÃ©tricas de score mÃ©dio, % decisÃµes standard e nÂ° de torneios separadas pela data baseline; leaks top-5 em cada perÃ­odo; lista de leaks resolvidos
- **Feed de atividade** â€” timeline de torneios do aluno com marcos automÃ¡ticos: "Melhora" (â†“5pts score), "RegressÃ£o" (â†‘5pts score), "Alta Qualidade" (â‰¥80% standard)
- Tabela `coach_baselines` no banco (SQLite e Postgres) com constraint `UNIQUE(coach_id, student_id)`

### Backend
- `GET/POST/DELETE /coach/student/:id/baseline` â€” gerenciar baseline de coaching
- `GET /coach/student/:id/activity-feed` â€” feed de torneios + marcos de performance (param `limit`)
- `GET /coach/student/:id/progress-report` â€” relatÃ³rio comparativo antes/depois da baseline
- Novos repositÃ³rios: `get_coach_baseline`, `set_coach_baseline`, `delete_coach_baseline`, `get_student_activity_feed`, `get_baseline_comparison`

### Frontend
- Ãcones `Activity, Flag, Star, BarChart2` adicionados
- Tipos `CoachBaseline, ActivityEvent, LeakSpot, PeriodMetrics, ProgressReport` em `api.ts`
- API functions `getBaseline`, `setBaseline`, `deleteBaseline`, `activityFeed`, `progressReport` em `coachDashboard`
- Componentes `ActivityTimeline`, `MetricsCompare`, `ProgressTab` em `StudentDetail.tsx`

---

## [v0.13.1] â€” 2026-04-26 â€” Combos de aÃ§Ã£o + classificaÃ§Ã£o coach + OpÃ§Ã£o C de reclassificaÃ§Ã£o

### Adicionado
- **Combo "AÃ§Ã£o Correta"** nas anotaÃ§Ãµes do coach â€” substituiu o campo livre por select com opÃ§Ãµes padrÃ£o do poker (fold, check, call, bet, raise, re-raise, all-in)
- **Combo "ClassificaÃ§Ã£o"** nas anotaÃ§Ãµes â€” coach pode atribuir o veredito da decisÃ£o: Jogada Correta / Marginal / Erro Pequeno / Erro Claro; campo `coach_override_label` armazenado no banco
- Badge visual do veredito exibido no balloon de anotaÃ§Ã£o (aluno e coach) e na listagem de "MÃ£os CrÃ­ticas"
- **OpÃ§Ã£o C implementada** â€” `coach_override_label` Ã© respeitado nas queries de `worst-decisions` do aluno: decisÃµes marcadas como "Jogada Correta" ou "Marginal" pelo coach saem da lista de mÃ£os crÃ­ticas; avg_score do torneio **nÃ£o** Ã© alterado (mÃ©tricas de performance permanecem do engine)

### Backend
- `coach_hand_annotations`: nova coluna `coach_override_label TEXT` â€” migrations automÃ¡ticas SQLite + Postgres
- `upsert_annotation` aceita e persiste `coach_override_label`
- `POST /coach/student/:id/hand-annotations` aceita e valida `coach_override_label`
- `GET /coach/student/:id/worst-decisions` usa `COALESCE(coach_override_label, label)` para filtrar â€” decisÃµes requalificadas pelo coach como corretas nÃ£o aparecem mais na lista de erros

---

## [v0.13.0] â€” 2026-04-26 â€” Sprint 5: AtenÃ§Ã£o Urgente + Leaks SistÃªmicos (BACK-003 + BACK-004)

### Adicionado
- **Aba "AtenÃ§Ã£o Urgente"** no Dashboard do Coach â€” tabela com as piores decisÃµes de **todos os alunos** ao mesmo tempo, com filtros por aluno, street e label (erro claro / erro pequeno); botÃ£o "Replay" abre diretamente o replay do aluno na mÃ£o errada
- **Aba "Leaks SistÃªmicos"** no Dashboard do Coach â€” lista de spots de erro agrupados por ocorrÃªncia, com destaque nos que afetam mÃºltiplos alunos ("Leaks sistÃªmicos") vs. individuais; cada spot Ã© expandÃ­vel para ver quais alunos sÃ£o afetados e quantas vezes
- **Filtro de perÃ­odo** (30/60/90 dias) na aba de Leaks SistÃªmicos
- Dashboard do Coach reorganizado em **3 abas**: Alunos (existente) Â· AtenÃ§Ã£o Urgente Â· Leaks SistÃªmicos

### Backend
- `repositories.py`: `get_all_students_worst_decisions(coach_id, n, student_id_filter, street_filter, label_filter)` â€” query cross-student com filtros dinÃ¢micos
- `repositories.py`: `get_common_leaks(coach_id, days)` â€” agrupa erros por spot e retorna lista de alunos afetados por spot
- `GET /coach/all-worst-decisions` â€” piores decisÃµes multi-aluno com filtros via query string
- `GET /coach/common-leaks` â€” leaks com breakdown por aluno

### Fix
- **AnotaÃ§Ãµes do coach nÃ£o apareciam no replay do aluno** â€” endpoint `GET /replay/<tournament_id>/<hand_id>` nÃ£o incluÃ­a `coach_annotations`; agora busca e injeta as anotaÃ§Ãµes do coach igual ao endpoint do coach student replay

---

## [v0.12.1] â€” 2026-04-26 â€” Fix: Replay para coaches + AnotaÃ§Ã£o direto no Replayer (BACK-001 complemento)

### Corrigido
- **Replay inacessÃ­vel para coaches** â€” rota `/replayer` estava envolvida em `ProtectedRoute` que redirecionava coaches para `/coach-dashboard`; criada `AuthRoute` que permite qualquer usuÃ¡rio autenticado acessar o replayer
- **ParÃ¢metro `student` perdido na navegaÃ§Ã£o de mÃ£os** â€” botÃµes "MÃ£o anterior" / "PrÃ³xima mÃ£o" no Replayer nÃ£o preservavam `?student=N` na URL; coach perdia o contexto e o replay passava a buscar dados do prÃ³prio jogador em vez do aluno

### Adicionado
- **Painel de anotaÃ§Ã£o do coach no Replayer** â€” quando o coach acessa o replay de um aluno e a etapa atual Ã© um erro do herÃ³i, o painel lateral exibe:
  - BotÃ£o "Anotar" (se sem anotaÃ§Ã£o) ou anotaÃ§Ã£o existente com botÃµes "Editar" / "Remover"
  - FormulÃ¡rio inline com seletor de modo (Complementar / Substituir IA), textarea de comentÃ¡rio e campo de jogada correta
  - Salvar atualiza o estado local imediatamente sem re-fetch da mÃ£o inteira
- **`decisions` em estado no Replayer** â€” decisÃµes do torneio sÃ£o mantidas em memÃ³ria para resolver `decision_id` de novos spots sem annotation existente (match por `hand_id + street + action_taken`)
- **BACK-007 adicionado ao backlog** â€” importaÃ§Ã£o mÃºltipla de torneios com fila + badge de progresso por arquivo

---

## [v0.12.0] â€” 2026-04-26 â€” Sprint 4: AnotaÃ§Ãµes de MÃ£os + Selo Coach (BACK-001 + BACK-005)

### Adicionado
- **AnotaÃ§Ãµes de mÃ£os pelo coach** â€” na aba "MÃ£os CrÃ­ticas" do perfil do aluno, o coach pode anotar qualquer decisÃ£o com dois modos:
  - **Complementar** â€” exibe a anÃ¡lise da IA + nota do coach empilhadas
  - **Substituir IA** â€” oculta a anÃ¡lise da IA, exibe apenas a nota do coach
- **Campo "Jogada correta"** â€” coach pode indicar a aÃ§Ã£o que considera correta para o spot anotado
- **Badge "Anotado"** â€” decisÃµes com anotaÃ§Ã£o exibem indicador visual na listagem
- **BalÃ£o do coach no Replayer** â€” ao chegar na aÃ§Ã£o anotada, o painel lateral exibe a nota do coach com destaque visual diferenciado do painel da IA
- **Selo "âœ“ Coach"** (BACK-005) â€” torneios revisados (com ao menos uma anotaÃ§Ã£o) ganham badge roxo "Coach" na lista de torneios do aluno

### Backend
- Tabela `coach_hand_annotations` (SQLite + PostgreSQL) com migration automÃ¡tica
- `repositories.py`: `get_annotations`, `get_annotations_for_decisions`, `upsert_annotation`, `delete_annotation`, `get_reviewed_tournament_ids`
- `GET /coach/student/:id/hand-annotations` â€” lista anotaÃ§Ãµes do coach para o aluno
- `POST /coach/student/:id/hand-annotations` â€” cria ou atualiza anotaÃ§Ã£o por decision_id
- `DELETE /coach/student/:id/hand-annotations/:decision_id` â€” remove anotaÃ§Ã£o
- Replay do coach (`/coach/student/:id/replay/...`) agora inclui `coach_annotations` na resposta
- `GET /history/tournaments` agora inclui `coach_reviewed: bool` por torneio

---

## [v0.11.1] â€” 2026-04-26 â€” CorreÃ§Ãµes de ambiente local + seguranÃ§a

### Corrigido
- **CORS local resolvido via Vite proxy** â€” todos os prefixos de API (`/auth`, `/history`, `/analyze`, `/study`, `/coach`, `/student`, `/tournaments`, `/replay`, `/metrics`, `/admin`, `/health`) sÃ£o roteados pelo proxy do Vite, eliminando erros de CORS no desenvolvimento
- **`get_user_by_id` nÃ£o importado** em `app.py` causava 500 em `/auth/me` â€” adicionado ao import
- **Coach redirecionado para `/coach-dashboard`** ao logar â€” `ProtectedRoute` agora redireciona coaches que tentam acessar rotas de aluno
- **Menu "Dashboard" do coach ficava ativo em `/coach-dashboard/profile`** â€” adicionado `end={true}` ao NavLink do dashboard do coach
- **Banner de vÃ­nculo nÃ£o sumia apÃ³s vincular coach** â€” `AcceptCoachModal` agora chama `refreshUser()` apÃ³s sucesso, atualizando `user.coach_id` imediatamente
- **`GET /coach/profile` retornava 404** quando perfil nÃ£o existia, causando loop de retentativas no `useQuery` â€” endpoint agora retorna `{}` (200)
- **Mensagens de erro no Login** â€” `TypeError` (ex: "Failed to fetch") exibe "NÃ£o foi possÃ­vel conectar ao servidor" em vez da mensagem tÃ©cnica bruta

### SeguranÃ§a
- **RemoÃ§Ã£o de vÃ­nculo com coach exige senha atual** â€” `DELETE /student/coach` agora requer `password` no body; backend verifica hash antes de desvincular
- `repositories.py`: nova funÃ§Ã£o `check_password(user_id, password)` reutilizÃ¡vel

---

## [v0.11.0] â€” 2026-04-26 â€” Perfil do aluno + seguranÃ§a de conta

### Adicionado
- **PÃ¡gina `/profile`** para alunos: alterar e-mail (com confirmaÃ§Ã£o de senha), trocar senha (verifica atual, mÃ­n. 8 chars), gerenciar vÃ­nculo de coach (remover com confirmaÃ§Ã£o dupla)
- **Header**: badge do coach vinculado visÃ­vel no topo quando aluno tem coach; link "Perfil" no nav do player
- **Plano de Estudos**: lock exibido sempre que o aluno tem coach vinculado (nÃ£o sÃ³ quando hÃ¡ overrides), mostrando o nome do coach
- **Banner de vÃ­nculo** no Dashboard: oculto quando aluno jÃ¡ tem coach vinculado

### Corrigido
- `/auth/me` agora retorna `coach_id` e `coach_username` â€” frontend usa para controle de acesso sem chamadas extras

### Backend
- `POST /auth/update-email` â€” atualiza e-mail apÃ³s verificar senha atual
- `POST /auth/change-password` â€” verifica senha atual antes de atualizar
- `DELETE /student/coach` â€” remove vÃ­nculo com coach
- `repositories.py`: `update_user_email`, `change_user_password`, `unlink_student_coach`

---

## [v0.10.2] â€” 2026-04-25 â€” Plano de estudos com fonte Ãºnica (canonical plan)

### Corrigido
- **Importar torneio nunca apaga o plano** â€” o plano de estudos sÃ³ Ã© substituÃ­do por aÃ§Ã£o explÃ­cita ("Gerar com IA" pelo aluno ou "Gerar novo plano" pelo coach)
- **Aluno com coach nÃ£o pode regerar** â€” backend bloqueia `?new=1` se o aluno tiver coach vinculado
- **Overrides do coach aplicados no plano do aluno** â€” cards substituÃ­dos/comentados pelo coach jÃ¡ chegam modificados para o aluno via `/study/plan`, alinhando o conteÃºdo visto por ambos
- **Coach â€” StudyCardItem exibe recursos completos** (livros, vÃ­deos, curso) para equiparar ao nÃ­vel de detalhe do plano do aluno
- **Coach â€” "Substituir" gerencia recursos**: formulÃ¡rio de substituiÃ§Ã£o inclui campos para livros (um por linha), vÃ­deos (um por linha) e curso â€” coach pode indicar material prÃ³prio
- Recursos substituÃ­dos pelo coach sÃ£o aplicados no plano do aluno via backend
- **Plano de estudos inconsistente entre aluno e coach**: aluno e coach agora compartilham o mesmo plano armazenado por chave estÃ¡vel `study_plan_current` no banco â€” nÃ£o mais por hash dos dados, que podia divergir quando os dados mudavam entre as geraÃ§Ãµes
- **BotÃ£o "Gerar com IA"** agora forÃ§a de fato uma nova geraÃ§Ã£o (`?new=1`), sobrescrevendo o plano anterior no banco â€” antes apenas re-buscava o cache sem regenerar

### Adicionado
- **Coach â€” botÃ£o "Gerar novo plano"** na aba Plano de Estudos: gera um plano novo via IA para o aluno e o torna o plano canÃ´nico â€” o aluno passa a ver exatamente este plano
- ParÃ¢metro `force_new` em `generate_study_plan()` e nos dois endpoints (`/study/plan?new=1`, `/coach/student/:id/study-plan?new=1`)

---

## [v0.10.1] â€” 2026-04-25 â€” MÃ£os CrÃ­ticas com cartas + lock coach_managed

### Adicionado
- **WorstTab (MÃ£os CrÃ­ticas)**: cada decisÃ£o agora exibe:
  - ID da mÃ£o (`hand_id`)
  - Cartas do herÃ³i como `PlayingCard` (tamanho sm)
  - Board cards (quando disponÃ­veis)
- **Lock "Gerar com IA"** na tela do aluno: quando o coach tem overrides no plano, o botÃ£o Ã© substituÃ­do por "Gerenciado pelo Coach" com Ã­cone de cadeado
- **Backend `/study/plan`**: responde `coach_managed: true` quando existem overrides do coach para o aluno

---

## [v0.10.0] â€” 2026-04-25 â€” Sprint 3: Coach Study Plan + Comparativo HistÃ³rico

### Adicionado
- **Coach Study Plan interativo**: cada card do plano IA tem 3 aÃ§Ãµes do coach:
  - **Validar** (âœ“) â€” marca o card como aprovado (badge verde)
  - **Comentar** (ðŸ’¬) â€” abre textarea inline para nota visÃ­vel ao aluno (badge Ã¢mbar)
  - **Substituir** (âœï¸) â€” formulÃ¡rio inline para reescrever tÃ­tulo, diagnÃ³stico e exercÃ­cio (badge roxo)
  - BotÃ£o de remover anotaÃ§Ã£o (Ã­cone lixeira)
  - Resumo de status no topo: "X validados Â· Y comentados Â· Z substituÃ­dos"
- **Comparativo histÃ³rico** no OverviewTab:
  - Score mÃ©dio e Standard% â€” primeiros 3 vs Ãºltimos 3 torneios
  - Delta com indicador visual: melhorou / piorou / estÃ¡vel
  - Total de torneios no perÃ­odo
- **Backend**: tabela `coach_study_overrides` (SQLite + PostgreSQL) com UNIQUE(coach_id, student_id, card_spot)
- **3 endpoints**: `GET/POST /coach/student/:id/study-overrides`, `DELETE /coach/student/:id/study-overrides/:spot`
- **Fixes**: replay link no WorstTab (`?tid=` â†’ `?t=`), nome do aluno no header (era "Aluno #N")

---

## [v0.9.0] â€” 2026-04-25 â€” Sprint 2: Coach Full Student View

### Adicionado
- **6 novos endpoints backend** para o coach acessar dados completos do aluno:
  - `GET /coach/student/:id/stats` â€” HUD stats (VPIP, PFR, AF, 3BET%, W$SDâ€¦)
  - `GET /coach/student/:id/breakdown` â€” performance por street e posiÃ§Ã£o
  - `GET /coach/student/:id/tournament/:tid` â€” detalhe de torneio + decisÃµes
  - `GET /coach/student/:id/worst-decisions` â€” piores N decisÃµes do aluno
  - `GET /coach/student/:id/study-plan` â€” plano de estudos IA do aluno
  - `GET /coach/student/:id/replay/:tid/:hid` â€” replay de mÃ£o do aluno
- **StudentDetail.tsx** totalmente reescrito com 4 abas:
  - **VisÃ£o Geral**: HUD Stats (8 indicadores), grÃ¡fico de evoluÃ§Ã£o, leaks, performance por street (bar chart) e por posiÃ§Ã£o
  - **Torneios**: lista completa clicÃ¡vel â†’ detalhe com tabela de decisÃµes + botÃ£o "Ver Replay"
  - **MÃ£os CrÃ­ticas**: fila das 30 piores decisÃµes (score, street, posiÃ§Ã£o, ICM, M-ratio, aÃ§Ã£o vs. correto) com link direto ao replay
  - **Plano de Estudos**: plano IA gerado para o aluno, com cards de prioridade alta/mÃ©dia/baixa
- **Replayer.tsx**: suporte ao parÃ¢metro `?student=<id>` â€” usa endpoint do coach em vez do endpoint do jogador

---

## [v0.8.0] â€” 2026-04-25 â€” Sprint 1: Sistema Professor/Aluno

### Adicionado
- **Login/registro com papel**: toggle "Jogador / Professor" na tela de registro; papel enviado ao backend via `role` no body
- **Rotas por papel**: `CoachRoute` em `App.tsx` â€” professores sÃ£o redirecionados para `/coach-dashboard`; jogadores bloqueados de rotas de coach
- **`/coach-dashboard`**: dashboard do professor com stats (alunos, ativos 30d, melhoria mÃ©dia, melhor aluno), lista de alunos com tendÃªncia e link para detalhe
- **`/coach-dashboard/student/:id`**: histÃ³rico do aluno â€” grÃ¡fico de evoluÃ§Ã£o (recharts), tabela de leaks, torneios recentes
- **`/coach-dashboard/profile`**: formulÃ¡rio para o professor configurar nome, bio, especialidades, e-mail/link de contato
- **Chave de convite** (`InviteKeyWidget`): exibida no dashboard do professor com botÃ£o de cÃ³pia
- **Banner "Vincular Professor"** no dashboard do jogador com `AcceptCoachModal` para inserir a chave de convite
- **NavegaÃ§Ã£o condicional** no `HudHeader`: professores veem "Dashboard + Perfil"; jogadores veem nav padrÃ£o; botÃ£o Import oculto para professores

---

## [v0.7.0] â€” 2026-04-25 â€” HUD Stats completo + GGPoker

### Adicionado
- **Player HUD Stats** (8 indicadores): VPIP, PFR, AF, Flop Bet%, Fold-to-3BET, WTSD, **3BET%** e **W$SD** â€” todos computados a partir das decisÃµes armazenadas
- **3BET%**: detectado quando hero re-raised prÃ©-flop com `facing_size > 0`; coluna `is_3bet` na tabela `decisions`
- **W$SD**: detectado via `hero: shows` no raw_text (showdown real do hero); coluna `showdown_result` na tabela `decisions`
- **GGPoker parser**: suporte completo ao formato GGPoker â€” detecÃ§Ã£o automÃ¡tica por header, IDs `#SG.../#RC...`, hero sempre `Hero`
- **Fix hero detection GGPoker**: `HERO_DEALT_RE` usa `[^\[\n]+` para nÃ£o capturar mÃºltiplas linhas

### Corrigido
- `_normalize_action()` converte `'raises'` â†’ `'raise'`; verificaÃ§Ã£o `is_3bet` corrigida para os valores normalizados
- `_detect_showdown()` verifica `"hero: shows"` em vez de `"SHOW DOWN"` â€” elimina falsos positivos quando hero foldou
- `llm_explainer.py`: `e.get('field', 0)` retornava `None` quando campo existe com valor `None`; corrigido para `(e.get('field') or 0)` em 4 mÃ©tricas de evoluÃ§Ã£o
- Opacidade das cÃ©lulas "em breve" no HUD elevada de `/25` para `/50` (visÃ­veis)

---

## [2026-04-25e] â€” HUD Stats: fix 3BET e W$SD (normalize action + showdown participation)

### Corrigido
- **`backend/leaklab/pipeline.py`**: `is_3bet` verificava `'raises'/'all-in'` mas `_normalize_action()` converte para `'raise'/'jam'`; corrigido para os valores normalizados
- **`backend/api/app.py`**: `_detect_showdown()` agora verifica se hero mostrou cartas (`hero: shows`) em vez de apenas se houve showdown na mÃ£o â€” elimina falsos positivos quando hero foldou mas outros jogadores foram a showdown (reduz de ~100 para ~24 showdowns reais)

---

## [2026-04-25d] â€” HUD Stats: 3BET% e W$SD implementados

### Adicionado
- **`backend/database/schema.py`**: colunas `is_3bet BOOLEAN` e `showdown_result TEXT` na tabela `decisions`; migrations adicionadas para SQLite e PostgreSQL
- **`backend/leaklab/pipeline.py`**: flag `is_3bet` calculada em `build_decision_input` â€” True quando hero re-raised prÃ©-flop com `facing_size > 0` (alguÃ©m jÃ¡ tinha apostado antes)
- **`backend/api/app.py`**: funÃ§Ã£o `_detect_showdown(raw_text, hero)` detecta se mÃ£o foi a showdown e se hero coletou o pote; `is_3bet` e `showdown_result` propagados no enriched dict e salvos no banco
- **`backend/database/repositories.py`**: `save_decisions` inclui `is_3bet` e `showdown_result`; `get_player_stats` computa 3BET% (hands com is_3bet / total preflop hands) e W$SD (hands won at showdown / total showdown hands)
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: 3BET e W$SD removidos de `soon: true`; tipos atualizados para `number | null`; tooltips revisados
- **`frontend/src/lib/api.ts`**: `three_bet` e `w_at_sd` tipados como `number | null`

---

## [2026-04-25c] â€” HUD Stats: fix visibilidade cÃ©lulas "em breve" (3BET, W$SD)

### Corrigido
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: cÃ©lulas 3BET e W$SD estavam invisÃ­veis â€” opacidades do status `na` elevadas de `/25`â†’`/50` (valor), `/40`â†’`/60` (label e "em breve"), `/30`â†’`/50` (ref MTT); cÃ©lulas ficam visivelmente "desabilitadas" mas legÃ­veis

---

## [2026-04-25b] â€” GGPoker parser: suporte completo + fix hero detection

### Adicionado
- **`backend/leaklab/parser.py`**: suporte a GGPoker â€” detecÃ§Ã£o automÃ¡tica por header (`Poker Hand #`), split regex por site, ID regex `#(\w+)` para prefixos SG/RC/HD; funÃ§Ã£o `parse_hand_history()` unificada detecta site e parseia qualquer arquivo
- **`backend/api/app.py`**: `_detect_site()` atualizado para reconhecer GGPoker; `_extract_financials()` soma `collected X from pot` do hero para calcular prize em Spin & Go

### Corrigido
- **`backend/leaklab/parser.py`**: `HERO_DEALT_RE` alterado de `[^\[]+` para `[^\[\n]+` â€” impedia que o nome do hero capturasse mÃºltiplas linhas `Dealt to` de oponentes no formato GGPoker, onde cada jogador tem sua prÃ³pria linha

### Alterado
- **`CLAUDE.md`**: menÃ§Ã£o ao suporte a GGPoker adicionada Ã  descriÃ§Ã£o do projeto

---

## [2026-04-25a] â€” Player HUD Stats como strip full-width + LeaksPanel compacto

### Alterado
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: redesenhado como strip horizontal full-width com 4 cÃ©lulas (VPIP, PFR, AF, Flop Bet) separadas por dividers; header com contagem de mÃ£os; responsivo 2Ã—2 em mobile e 4Ã—1 em desktop
- **`frontend/src/components/hud/LeaksPanel.tsx`**: redesenhado como lista compacta â€” cada leak ocupa uma linha de ~36px com dot de severidade, label truncado, badge de contagem e botÃ£o Estudar inline; eliminados o card grande com parÃ¡grafo de descriÃ§Ã£o
- **`frontend/src/pages/Index.tsx`**: `PlayerStatsCard` movido para entre os KPIs e o grid principal (full-width, destaque mÃ¡ximo); removido do sidebar

---

## [2026-04-24d] â€” Player HUD Stats: VPIP, PFR, Aggression Factor, Flop Bet%

### Adicionado
- **`backend/database/repositories.py`**: nova funÃ§Ã£o `get_player_stats(user_id, days)` que agrega decisÃµes por mÃ£o e computa VPIP, PFR, AF (Aggression Factor) e Flop Bet% diretamente das decisÃµes armazenadas
- **`backend/api/app.py`**: novo endpoint `GET /metrics/player-stats?days=N` que retorna o perfil de jogo calculado
- **`frontend/src/components/hud/PlayerStatsCard.tsx`**: novo card HUD exibindo as 4 stats computÃ¡veis (VPIP, PFR, AF, Flop Bet%) com barra de progresso colorida vs. referÃªncia MTT; 4 stats futuras (3BET, Fold to 3BET, WTSD, W$SD) exibidas como "Em breve" com tooltip explicativo
- **`frontend/src/lib/api.ts`**: interface `PlayerStatsResponse` e mÃ©todo `metrics.playerStats(days)`
- **`frontend/src/pages/Index.tsx`**: `PlayerStatsCard` adicionado Ã  sidebar do dashboard

### ReferÃªncias MTT usadas
| Stat | Ref MTT | Status |
|------|---------|--------|
| VPIP | 12â€“22% | âœ… Calculado |
| PFR | 9â€“18% | âœ… Calculado |
| AF | 2.0â€“4.0x | âœ… Calculado |
| Flop Bet | 40â€“65% | âœ… Calculado |
| 3BET | 4â€“8% | ðŸ”œ Em breve |
| Fold to 3BET | 55â€“72% | ðŸ”œ Em breve |
| WTSD | 25â€“35% | ðŸ”œ Em breve |
| W$SD | 50â€“60% | ðŸ”œ Em breve |

---

## [2026-04-24c] â€” Cartas do villain reveladas no momento do "shows", nÃ£o sÃ³ no showdown final

### Corrigido
- **`backend/api/app.py`**: `_build_replay_data` agora prÃ©-escaneia o `raw_text` para linhas `player: shows [cards]` e acumula `current_revealed` conforme as aÃ§Ãµes ocorrem; `revealed_cards` Ã© incluÃ­do em cada step de action e street (nÃ£o apenas no step final de showdown)
- **`frontend/src/pages/Replayer.tsx`**: `buildSeats()` verifica `step.revealed_cards` em qualquer tipo de step, sem depender de `step.type === 'showdown'`; `revealed: true` Ã© setado assim que o backend sinaliza as cartas

---

## [2026-04-24b] â€” Showdown na mesa + apostas posicionadas dentro da mesa

### Corrigido
- **`frontend/src/components/hud/PokerTable.tsx`**: cartas dos villains agora exibidas no showdown â€” nova prop `revealed` em `Seat`; condiÃ§Ã£o `hidden` alterada para `!seat.hero && !seat.revealed`; chips de aposta movidos para fora do `SeatBubble` e renderizados como elementos absolutamente posicionados entre o assento e o centro da mesa via `betPosition(sx, sy, 0.42)`
- **`frontend/src/pages/Replayer.tsx`**: `buildSeats()` agora passa `revealed: true` para assentos de villain no step de showdown quando `revealed_cards` estÃ¡ presente

---

## [2026-04-24a] â€” Replayer conectado ao backend + botÃµes de replay nas mÃ£os

### Adicionado
- **`frontend/src/pages/Replayer.tsx`**: reescrito para consumir dados reais do backend via `GET /replay/<t>/<h>`; usa `useSearchParams` para ler `?t=` e `?h=` da URL; exibe mesa de poker com assentos, pot e board reais por step; log de aÃ§Ãµes com hero em destaque e erros marcados; painel de EV/feedback com equity, pot odds, M ratio e pressÃ£o ICM; estados de loading, erro e sem-parÃ¢metros
- **`frontend/src/lib/api.ts`**: interfaces `ReplaySeat`, `ReplayStep`, `ReplayData`; mÃ©todo `tournaments.replay(tournamentId, handId)` â†’ `GET /replay/:t/:h`
- **`frontend/src/pages/TournamentDetail.tsx`**: botÃ£o "Abrir no replayer" em cada card de mÃ£o (navega para `/replayer?t=<id>&h=<handId>`); botÃ£o "Replay completo" agora clicÃ¡vel (navega para primeira mÃ£o do torneio); link "Replayer" compacto na linha de aÃ§Ãµes quando anÃ¡lise IA jÃ¡ estÃ¡ carregada

### Corrigido
- **`frontend/src/pages/TournamentDetail.tsx`**: referÃªncia a `h.resultBb` (campo inexistente) substituÃ­da por `h.evDelta`

---

## [2026-04-23b] â€” UI leaklabs: onboarding, detalhe de torneio, AI Report

### Adicionado
- **`frontend/src/components/hud/EmptyDashboard.tsx`**: tela de onboarding para novos usuÃ¡rios â€” upload com drag-and-drop conectado ao `POST /analyze`, cards dos 3 mÃ³dulos com estilo `tactical-corners`, dispara `onComplete` para refresh do dashboard
- **`frontend/src/components/hud/TournamentAiReport.tsx`**: painel lateral deslizante de anÃ¡lise IA por torneio â€” chama `POST /analyze/tournament-summary` com `tournament_db_id`, exibe resumo cacheado (`llm_summary`) se jÃ¡ existir, seÃ§Ãµes colapsÃ¡veis em markdown com tonal por tipo (erro/ponto forte/neutro)
- **`frontend/src/pages/TournamentDetail.tsx`**: pÃ¡gina de detalhe de torneio â€” agrupa decisÃµes por mÃ£o (`groupByHand`), filtra por severidade e street, exibe cartas com `PlayingCard`, integra `TournamentAiReport` com ID real do banco
- **`frontend/src/index.css`**: variÃ¡veis CSS para cartas (`--card-face`, `--card-suit-dark`, `--card-suit-red`) e utilitÃ¡rio `.tactical-corners` com pseudo-elementos de canto

### Alterado
- **`frontend/src/lib/api.ts`**: adicionado tipo `TournamentDecision`; `tournaments.get()` retorna `{ tournament, decisions }`
- **`frontend/src/App.tsx`**: rota `/tournaments/:id` com `TournamentDetail` protegida por auth
- **`frontend/src/components/hud/HudHeader.tsx`**: branding atualizado de "PokerLeaks.os" â†’ "LeakLabs.ai"; item "Replayer" removido da navegaÃ§Ã£o
- **`frontend/src/pages/Index.tsx`**: exibe `EmptyDashboard` quando nÃ£o hÃ¡ torneios importados (primeiro acesso)
- **`frontend/src/pages/Tournaments.tsx`**: clique em linha navega para `/tournaments/:tournament_id`

---

## [2026-04-23a] â€” IntegraÃ§Ã£o completa backend + frontend React

### Adicionado
- **`frontend/src/lib/auth.tsx`**: contexto React de autenticaÃ§Ã£o (`AuthProvider`, `useAuth`) â€” gerencia token JWT via `sessionStorage`, verifica `/auth/me` na inicializaÃ§Ã£o, expÃµe `login`, `register`, `logout`
- **`frontend/src/pages/Login.tsx`**: pÃ¡gina de login/registro com tabs, design HUD, mensagem de erro inline e redirecionamento automÃ¡tico se jÃ¡ autenticado
- **`frontend/.env`**: variÃ¡vel `VITE_API_URL=http://localhost:5000` para dev local
- **`backend/api/app.py` â€” `POST /coach/chat`**: endpoint conversacional do AI Coach; carrega leaks e evoluÃ§Ã£o reais do usuÃ¡rio, chama `coach_chat_reply` e retorna a resposta do LLM
- **`backend/api/app.py` â€” `GET /coach/context`**: retorna `hands_analyzed`, `tournaments_analyzed`, `top_leaks`, `avg_score` e `standard_pct` do usuÃ¡rio para o painel de contexto do Coach
- **`backend/leaklab/llm_explainer.py` â€” `coach_chat_reply`**: funÃ§Ã£o de chat conversacional com Claude Haiku; injeta dados reais de desempenho do jogador como contexto no system prompt

### Alterado
- **`frontend/src/App.tsx`**: adicionado `AuthProvider`, rota `/login` e `ProtectedRoute` (redireciona para `/login` se nÃ£o autenticado) em todas as pÃ¡ginas internas
- **`frontend/src/components/hud/HudHeader.tsx`**: exibe username do usuÃ¡rio logado e botÃ£o de logout; `LogOut` icon via lucide-react
- **`frontend/src/pages/AICoach.tsx`**: conectado ao backend â€” carrega contexto via `GET /coach/context` na montagem, saudaÃ§Ã£o inicial personalizada com dados reais, chat conectado a `POST /coach/chat` com loading state e scroll automÃ¡tico
- **`frontend/src/components/hud/UploadZone.tsx`**: lÃª arquivo como texto, chama `POST /analyze`, exibe feedback visual (loading â†’ ok â†’ erro) e dispara callback `onResult` para refresh do dashboard
- **`frontend/src/components/hud/LeaksPanel.tsx`**: aceita prop `leaks` da API; mapeia `avg_score` para severidade (crÃ­tico/moderado/leve); fallback para dados demo quando sem dados reais
- **`frontend/src/components/hud/BankrollChart.tsx`**: aceita prop `evolution` da API; plota lucro cumulativo real; fallback para dados demo
- **`frontend/src/components/hud/RecentTournamentsTable.tsx`**: aceita prop `tournaments` da API; formata datas, profit e place reais; fallback para dados demo
- **`frontend/src/pages/Index.tsx`**: busca `GET /history/evolution` e `GET /history/tournaments` na montagem; calcula KPIs reais (ROI, ITM%, Avg Buy-In, Total Eventos); refresh automÃ¡tico apÃ³s upload
- **`frontend/src/pages/Tournaments.tsx`**: carrega lista real via `GET /history/tournaments`; loading state, filtro por rede e ordenaÃ§Ã£o funcional com dados reais

---

## [2026-04-23i] â€” MigraÃ§Ã£o frontend para React + TypeScript

### Alterado
- **Frontend migrado de HTML monolÃ­tico para React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui**
  - Base: projeto gerado pelo Lovable (poker-leak-finder) trazido para `frontend/`
  - `frontend/index.legacy.html` â€” backup do frontend vanilla anterior
  - `frontend/src/` â€” novo frontend React com arquitetura componentizada
  - `vercel.json` atualizado para build com `@vercel/static-build`
  - `.gitignore` atualizado: `frontend/node_modules/`, `frontend/dist/`

### MotivaÃ§Ã£o
- SeguranÃ§a: HTML monolÃ­tico sem isolamento de escopo, JWT exposto em JS inline, sem CSP
- Manutenibilidade: arquivo Ãºnico de ~3000 linhas impossÃ­vel de auditar e testar
- Arquitetura componentizada elimina classes de bugs de DOM stale e permite testes unitÃ¡rios

### PrÃ³ximos passos
- Conectar API client (`src/lib/api.ts`) ao backend Flask
- Implementar autenticaÃ§Ã£o (contexto JWT, rotas protegidas)
- Substituir dados mock por chamadas reais ao backend

---

## [2026-04-23h]

### Corrigido
- **BotÃ£o "Gerar Resumo" sem aÃ§Ã£o**: `tSummaryLoaded` persiste em memÃ³ria durante toda a sessÃ£o do browser. Torneios com o mesmo PokerStars ID (apÃ³s reset/reimport) bloqueavam silenciosamente a funÃ§Ã£o `generateTSummary` na linha `if(tSummaryLoaded[tid])return`. Corrigido limpando o objeto em `_renderTournamentList` sempre que a lista Ã© re-renderizada.

---

## [2026-04-23g]

### Corrigido
- **Coach IA retornava template estÃ¡tico**: `_call_llm_summary` usava `_json.dumps()` mas o mÃ³dulo foi importado como `json`. O `NameError` era silenciado pelo `except Exception`, fazendo o sistema cair sempre no fallback estÃ¡tico. Corrigido para `json.dumps()`.

---

## [2026-04-23f]

### Corrigido
- **Coach IA â€” "Torneio nÃ£o encontrado no banco"**: apÃ³s importar um torneio, o objeto inserido em `tourns[]` em `_applyRealData` nÃ£o tinha o campo `dbId` mapeado. O frontend buscava `tObj.dbId` para enviar ao endpoint `/analyze/tournament-summary`, encontrava `undefined` e mostrava o erro. Adicionado `dbId: data.tournament_db_id` ao objeto construÃ­do apÃ³s a anÃ¡lise.

---

## [2026-04-23e]

### Corrigido
- **Frontend `API_URL` com `file://`**: ao abrir `index.html` diretamente do sistema de arquivos, `location.hostname` Ã© `''` (string vazia) e a detecÃ§Ã£o de `localhost` falhava, direcionando todas as chamadas para o servidor de produÃ§Ã£o (Render). Adicionada verificaÃ§Ã£o `!h` para cobrir o protocolo `file://`.

---

## [2026-04-23d]

### Corrigido
- **`load_dotenv` com caminho absoluto**: substituÃ­do `os.path.dirname(__file__)` por `Path(__file__).resolve().parent` em `app.py` para evitar falha no subprocess do Flask reloader que nÃ£o resolvia caminhos relativos corretamente.
- **Timeout do study plan**: aumentado de 30s para 90s em `llm_explainer.py`; chamadas ao Claude Haiku para geraÃ§Ã£o de plano com 400+ decisÃµes podem ultrapassar 30s.

### Resultado
- Study plan com LLM funcional localmente: 6 cards gerados, resumo personalizado, `error: null`.

---

## [2026-04-23c]

### Adicionado
- **`backend/.env`** (gitignored): variÃ¡veis de ambiente para dev local (`ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`).
- **`python-dotenv`** adicionado a `requirements_dev.txt`; `app.py` carrega `.env` automaticamente via `load_dotenv()` na inicializaÃ§Ã£o.

---

## [2026-04-23b]

### Adicionado
- **`backend/requirements_dev.txt`**: dependÃªncias para desenvolvimento local sem `psycopg2-binary` (incompatÃ­vel com Python 3.13/Windows); ambiente local usa SQLite.

### Ambiente local
- Backend: `cd backend && python api/app.py` â†’ `http://localhost:5000`
- Frontend: abrir `frontend/index.html` no browser (detecta `localhost` automaticamente e aponta para porta 5000)

---

## [2026-04-23]

### Corrigido
- **Imports `gaphunter` â†’ `leaklab`**: 7 arquivos de teste importavam o nome antigo do pacote (`gaphunter`), causando `ModuleNotFoundError` em toda a suite `engine` e `regression`.
- **Coluna `raw_text` ausente no schema SQLite**: a coluna existia apenas na migraÃ§Ã£o PostgreSQL; adicionada ao `CREATE TABLE` e Ã  lista de migraÃ§Ãµes SQLite em `database/schema.py`, corrigindo 8 falhas na suite `database`.

### Adicionado
- **`CLAUDE.md`**: documentaÃ§Ã£o para Claude Code com comandos de build/teste, arquitetura e stack.
- **`CHANGELOG.md`**: este arquivo.
- **`.gitignore`**: entradas para `backend/torneio_ingles.txt` (fixture local com dados pessoais) e `.claude/` (configuraÃ§Ã£o do Claude Code).

### Resultado
- Testes: **227/227 passando** (todas as suites: engine, database, llm, api, regression).

