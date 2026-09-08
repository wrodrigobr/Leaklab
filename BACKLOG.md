# Backlog — PokerLeakLab

Ao concluir uma sprint, mover os itens para o CHANGELOG com o número da versão.

> **Sprints já entregues:** Sprints 1–13 + Sprint A–AW — ver CHANGELOG v0.9.0 a v0.82.2.
> **Próxima sprint:** Sprint AX — Onboarding para novos usuários

---

## Princípio de Produto

> **A plataforma é primariamente um coach IA autônomo para o aluno.**
> O aluno não precisa — e nunca deve precisar — de um coach humano para extrair valor completo do sistema.
> Análise de leaks, plano de estudos, replayer, gamificação e evolução de score são o **core** e funcionam de forma independente.
>
> O marketplace de coaches humanos é uma **camada adicional opcional** — um upgrade de valor, não um pré-requisito.
> Calls-to-action de contratação de coach devem ser **suaves e contextuais**, jamais bloqueantes ou centrais no fluxo principal.
> Sprints de IA têm prioridade estratégica maior do que sprints de marketplace.

---

## Roadmap de Sprints — Status Atual

| Sprint | Itens | Tema | Status |
|---|---|---|---|
| Sprint 1–3 | — | Infraestrutura, Student View, Study Plan | ✅ v0.9.0–v0.10.2 |
| Sprint 4 | BACK-001 + BACK-005 | Anotações de mãos + Selo Coach | ✅ v0.12.0 + v0.32.0 |
| Sprint 5 | BACK-003 + BACK-004 | Coach analytics multi-aluno | ✅ v0.13.0 |
| Sprint 6 | BACK-002 | Feed de progresso + baseline | ✅ v0.14.0 |
| Sprint 7 | BACK-006 pt.1 | Perfil estendido + reviews | ✅ v0.15.0 |
| Sprint 8 | BACK-006 pt.2 + BACK-013 | Diretório público + descoberta contextual | ✅ v0.16.0 |
| Sprint 9 | BACK-007 + BACK-012 | Upload múltiplo + perfil coach unificado | ✅ v0.17.0 |
| Sprint 10 | BACK-009 | Sistema de nível + gamificação | ✅ v0.18.0 |
| — | BACK-008 | Visualizador de ranges no replayer | ✅ v0.19.0 |
| Sprint 11 | BACK-010 | Planos comerciais + quota | ✅ v0.22.0 |
| Sprint 12 | BACK-011 | Anti-injection + moderação de conteúdo | ✅ v0.26.0–v0.27.0 |
| Sprint 13 | UX-004 | Menu de conta com plano e uso | ✅ v0.25.0 |
| Sprint A | UX-001 + UX-003 | Lista de torneios + tooltips auto-explicativos | ✅ v0.31.0 |
| Sprint 15 | BACK-015 | Gateway de pagamento (Stripe) | ✅ v0.29.0 |
| Sprint B | UX-002 | Responsividade mobile/tablet | ✅ v0.33.0 |
| Sprint C+E | BACK-014 + BACK-017 | Revenue share + Admin Panel | ✅ v0.34.0 |
| Sprint D | BACK-016 | WhatsApp Coaching Drills | ✅ v0.36.0 |
| Sprint F | UX-005 | Internacionalização (i18n) — PT/EN/ES | ✅ v0.35.0 |
| Sprint G | UX-006 | Header cleanup + i18n full coverage | ✅ v0.37.0 |
| Sprint H | UX-007 | Dashboard cards i18n — 11 componentes | ✅ v0.38.0 |
| Sprint I | PERF-001 + PERF-002 | ROI Attribution Engine + Leak Priority Optimizer | ✅ v0.39.0 |
| Sprint J | PERF-003 + PERF-004 + PERF-005 | Leak Progression + Pressure Collapse + Confidence Drift | ✅ v0.40.0 |
| Sprint K | PERF-006 | Ghost Table Simulator MVP | ✅ v0.41.0–v0.42.0 |
| Sprint L | PERF-007 | Decision DNA — assinatura estratégica do jogador | ✅ v0.43.0 |
| Sprint M | PERF-008 | Tournament Narrative Engine | ✅ v0.45.0 |
| Sprint N | PERF-009 | GGPoker Parser — detecção automática de formato | ✅ (já entregue) |
| Sprint O | FEAT-01 | Comparativo de Torneios | ✅ v0.46.0 |
| Sprint P | FEAT-04 | Relatório PDF Premium | ✅ v0.47.0 |
| Sprint Q | FEAT-02 + FEAT-03 | Daily Focus + XP Server-Side | ✅ v0.48.0 |
| Sprint R | FEAT-05 | SRS Adaptativo nos Drills | ✅ v0.49.0 |
| Sprint S | FEAT-06 | Leak Causal Map | ✅ v0.50.0 |
| Sprint T | FEAT-07 | Coach Effectiveness Metrics | ✅ v0.51.0 |
| Sprint U | FEAT-08 | Session Goals + AI Review | ✅ v0.52.0 |
| Sprint V | FEAT-09 + FEAT-10 | Coach Templates + Coach Messaging | ✅ v0.53.0 |
| Sprint W | FEAT-11 | Weekly Digest Email | ✅ v0.54.0 |
| Sprint Y | UX-008 | Coaches Directory — mobile layout + remover "professor" | ✅ v0.55.0 |
| Sprint Z | UX-009 | Torneios — data do torneio vs importação + exibir ano | ✅ v0.56.0 |
| Sprint AA | INFRA-001 | Correção de erros de build no Render (backend) e Vercel (frontend) | ✅ v0.57.0 |
| Sprint AB | UX-010 | Filtros de período no gráfico de Bankroll (1M/3M/1A/tudo) não funcionam | ✅ v0.58.0 |
| Sprint AC | UX-011 | Dashboard — remover nome do hero, "Centro de Comando" → "Dashboard", corrigir quebra de linha no subtítulo | ✅ v0.59.0 |
| Sprint AD | UX-012 | Dashboard — remover lista de últimos torneios (há menu próprio); liberar espaço para cards de indicadores | ✅ v0.60.0 |
| Sprint AE | UX-013 | Substituir "JAM" por "All In" em toda a plataforma (UI, textos, labels, parser output) | ✅ v0.63.1 |
| Sprint AF | UX-014 | Página do Coach (StudentDetail) — remover limitação horizontal, aproveitar melhor o espaço disponível em telas largas | ✅ v0.64.0 |
| Sprint AH | BACK-018 | Coach Application Flow — candidatura com aprovação manual pelo admin | ✅ v0.65.0 |
| Sprint AI | BACK-019 | Perfil demográfico do usuário — idade, localização, experiência de poker | ✅ v0.66.0 |
| Sprint AJ | UX-015 | Inbox global de mensagens para o coach — ver todas as conversas com badge de não lidas | ✅ v0.67.0 |
| Sprint AK | UX-016 | Badge de mensagens não lidas no dashboard/header do aluno → link direto para conversa com coach | ✅ v0.67.0 |
| Sprint AL | UX-017 | Dashboard personalizável — arrastar e reordenar cards, preferência salva por usuário | ✅ v0.70.0 |
| Sprint AM | UX-018 | Listagem de alunos do coach — tabela com busca, filtros (ativo/inativo, plano) e paginação | ✅ v0.68.0 |
| Sprint AN | UX-019 | Coach Chat Drawer — painel lateral de mensagens no header do aluno | ✅ v0.69.0 |
| Sprint AG | FEAT-12 | Página de Documentação / Wiki do Sistema | ✅ v0.71.0 |
| Sprint AO | i18n ext. | Cobertura i18n completa: LeakCausalMap, DraggableCard, Docs career section | ✅ v0.72.0 |
| — | bugfixes | Bugfixes: nomes de nível i18n no dashboard, narrativa LeakCausalMap em PT, drag handle UX | ✅ v0.73.0 |
| Sprint AP | FEAT-13 | Strategic Career Graph — projeção de carreira com regressão linear + sparkline + narrativa IA | ✅ v0.74.0 |
| Sprint AQ | FEAT-14 | Cognitive Failure Mapper — 5 padrões cognitivo-emocionais + CognitiveFailureCard | ✅ v0.75.0 |
| Sprint AQ+ | — | Dashboard UX Redesign — layout reorganizado, insight_row com Career + Cognitive lado a lado | ✅ v0.76.0 |
| Sprint AR | FEAT-15 | Personal Strategic Twin — perfil preditivo de spots custosos + narrativa LLM em 1ª pessoa | ✅ v0.77.0 |
| Sprint AS | FEAT-16 | AI Sparring Mode — jogo de mãos históricas com pause em decisões + feedback imediato + SRS | ✅ v0.78.0 |
| Sprint AT | — | Menu "Treinos" + redesign visual do Sparring (amber, StreetTimeline, HandRecap) | ✅ v0.79.0 |
| Sprint AU | — | PokerTable visual no Sparring — herói + vilões + board + pot em tela real | ✅ v0.80.0 |
| Sprint AV | — | Página /training + botões de ação contextuais no Sparring (facing_bet) | ✅ v0.81.0 |
| — | bugfixes | i18n sparring (arenaLabel/arenaDesc) + test suite verde (sys.executable, coach flow) | ✅ v0.81.1 |
| Sprint AW | — | Ghost Table Pressure Mode (30s timer + SVG ring + streak) + Sparring hand rotation | ✅ v0.82.0 |
| — | bugfixes | Perfil demográfico visível + i18n completo do perfil + telefone no perfil | ✅ v0.82.1–v0.82.2 |
| Sprint AX | FEAT-17 | Onboarding para novos usuários — modal 4 passos (welcome/upload/train/ready), flag `onboarding_completed`, skip, i18n PT/EN/ES | ✅ v0.83.0 |

---

## Próximas Sprints — Em Aberto

### [SPRINT AY] — O que restou de 04-05/09  (plano de dev, escrito 05/09)

Ordenado por RISCO PARA O USUARIO, nao por esforco. Cada item carrega o numero que justifica
a posicao — item sem medicao fica embaixo de proposito.

**ENTREGUES 05/09**

| # | item | estado |
|---|---|---|
| AY-1 | **HUD do acumulador** (`opponent_stats`): 5 defeitos, erro somado contra o PT4 41,08pp -> 0,39pp. 7 mutacoes aplicadas, 7 acusadas. | ✅ **ENTREGUE 05/09** — `2933936e`, suite 2719/2719, deploy verificado DENTRO do container em torneio real de producao |
| AY-2 | **Frontend do perfil por posicao** (`V2PositionProfileCard` A4 + tooltip, wiring em `DashboardV2`/`Index`, i18n 3 locales). | ✅ **ENTREGUE 05/09** — `7317cc6f`, frontend 493/493, `tsc -p tsconfig.app.json` limpo, endpoint conferido em prod (Rullian: 26.575 maos, 8 assentos, 7-9 stats classificados por assento) |

**FILA — por impacto medido**

| # | item | por que aqui |
|---|---|---|
| AY-3 | **Filtro de volume evidente** + as duas observacoes do dono sobre o perfil por posicao. | ✅ **ENTREGUE 05/09** — `4cfb2ecf`, `08e46073`, `b542c375`, `1c4b9ce0`, `e1fdf5c7`. O escopo virou frase de largura inteira com a amostra junto. E a frente cresceu do que o dono achou: linha TOTAL, o assento LJ que faltava (334 decisoes em 70 torneios), a grade que parou de acusar por assento (5 de 6 jogadores eram acusados no BB pela regua errada), o trilho removido e o layout. Backend 2847/2847, frontend 497/497. | **Adendo 06/09:** grade com as 12 colunas do HUD, sempre, na ordem do HUD, colada abaixo dele; corte de amostra mantido, agora em `minimo_da_grade`. 3 mutacoes acusadas; a 1a rodada foi silencio porque os testes estavam abaixo do `__main__`.
| AY-4 | **Eixo de tempo: 27 funcoes por data de UPLOAD, 24 sem o filtro da tela.** | ✅ **ENTREGUE 05/09, deploy `e8e317e0` verificado no container** — 21 funcoes de ANALISE convertidas para `_build_tournament_filter` (data de JOGO + `last_n`); 6 declaradas PRESENCA/ADMIN com motivo; classificacao vive em `test_eixo_de_tempo.py` como tabela, com guarda N+1. Achado no caminho: a projecao de carreira usava `imported_at` como eixo X da regressao do ELO. 11 copias do parse do `last_n` viraram `_last_n_da_query()`. Provado em dev com usuario forjado (24 torneios em 24 meses, todos importados hoje): 7 cards exatos em 120/960/200. Guarda quebrado nos dois sentidos e acusou. PG smoke 200/200, frontend 497/497. **Efeito na tela e MENOR do que o enquadrado**: com o padrao Historico os cards de 90/180d ficam iguais para os usuarios atuais. A correcao aparece em quem usa "ultimos N", em quem importar acervo antigo, e nos endpoints por dias fora do dashboard (o card de nivel do plano de estudos passa a listar leaks de 30d de JOGO, nao de IMPORT). |
| AY-5 | **Onboarding: o X nao fecha.** | ✅ **ALARME FALSO, testado 05/09** — `OnboardingModal.test.tsx` (3/3): o X fecha quando a API responde e quando falha; so NAO fecha enquanto `completeOnboarding()` fica pendurada (o `if (saving) return` ainda ignora o 2o clique). Se o dono viu o sintoma, foi API travada — em dev o GTO server esta morto. Comportamento mantido de proposito: fechar antes de persistir faria o onboarding reabrir no proximo login se a rede falhar. O teste existente mockava o modal inteiro; o X nunca tinha sido exercitado. |
| AY-6 | **Plano de estudos: drift por BANDA + regenerar os 5 planos antigos.** Reescrito em 05/09 depois de o dono questionar a premissa: *"o plano deveria focar nos leaks; faz sentido trazer dados antigos e novos?"* — nao faz. A comparacao de periodos JA existe no relatorio de evolucao (40 mais recentes x anteriores); repeti-la no plano seria a mesma regra em dois lugares, e misturaria diagnostico (plano) com acompanhamento (evolucao). E regenerar por valor de HUD seria churn: o drift ignora magnitude de proposito. | ✅ **(1) ENTREGUE 05/09** — `_study_plan_drift_sig` passa a incluir a BANDA de cada stat do HUD (`player_stat_flags`), nao o valor — se um stat mudou de banda, o perfil mudou e o plano regenera; se so o numero mexeu dentro da banda, nao. Mesma logica qualitativa que o drift ja usa para os leaks. Pequeno. (2) Regenerar os 5 planos em prod UMA vez (`force_new`): o contexto de HUD deles e anterior aos consertos de 04-05/09. Acao pontual, decisao do dono — troca o que 5 pessoas ja leram. |
| AY-16 | **Historico capado em 50 e "ultimos N" pelo lado errado** (achado do dono, 06/09). `get_tournaments` com `limit=50` por padrao, tela sem `limit`; dashboard cortava `slice(-N)` numa lista DESC por importacao. | ✅ **ENTREGUE 06/09** — sem teto por padrao; `ultimosTorneios()` corta por data de jogo como o backend. 4 mutacoes, 4 acusadas. Ver CHANGELOG. |
| AY-20 | **Assento pela distancia ao botao** (achado do Rullian, 07/09: "pouca amostra pro Lojack; como determina LJ x UTG+2?"). O parser nomeia a partir do UTG; em mesa de 8 o "UTG+2" e o LJ (HJ, CO, BTN atras). | ✅ **ENTREGUE LOCALMENTE 07/09** — `sql_assento()`: CASE em SQL gerado do MESMO mapa das ranges (`_mapa_da_mesa`), aplicado no filtro por assento do HUD, na grade, no detalhe, nas referencias (vilao tambem), no DNA e na matriz. 5 testes, 3 mutacoes acusadas. |
| AY-23 | **Referencia de C-Bet IP/OOP pelo SOLVER nos proprios spots.** ENTREGUE LOCAL 07/09: no pelo `spot_hash`, P20-P80 da frequencia de aposta da range (regra do RFI), piso de cobertura 50%. Rullian (copia em dev): IP 48,9-88,5 (cobre 86%) contra 89,5; OOP 15,2-49,0 (cobre 56%) contra 68,5. Aberto: (a) a versao por MAO (hand-aware, `hand_view_for_spot`) como refinamento; (b) OOP a 40+bb fica sem referencia por cobertura, e a cobertura pos-flop deep e o AY-17. | Deploy junto com o pacote; conferir no Neon o custo da juncao com `gto_nodes`. |
| AY-26 | **Card acusa erro com best_action igual a jogada.** FECHADO 08/09: o gancho da fila drenada nao chamava o reconcile; corrigido e reparado em prod (413 decisoes, AUTO 62 -> 0). | Deploy 08/09. |
| AY-26b | **Restos do AY-26:** 32 decisoes `marginal` com best = jogada (a regra de 03/09 realinha so >= small_mistake; decidir se marginal entra), 14 delas `bet` x `bet_50pct` rotuladas gto_critical apesar de played_freq 0,6 (matcher antigo sem tamanho; reavaliar com `resync_postflop_gto.py --tid --apply` em dry-run antes), 1 GRAFIA shove x jam (played_freq 1,0 pela mao, minor pela range). | Proxima janela. |
| AY-29 | **O solver guarda o spot pelo ROTULO da sala, nao pelo assento efetivo (jogadores atras).** Achado 08/09 respondendo o dono ("o solver conseguiria saber se a mesa e 9/8/7/6 max?"). Hoje `compute_spot_hash` e a montagem de ranges do solve usam `position` cru: um flop de mesa 6 com o heroi no UTG e resolvido com o range de UTG 9-max (16,4% a 30bb) quando o assento real abre como LJ (24,7%); e o MESMO spot vindo de LJ em 9-max ganha chave diferente, entao resolvemos duas vezes o que e um no so. Nos nos usados em dev: UTG 629, UTG+1 387, UTG+2 212, LJ 21 (o LJ quase nao aparece porque a traducao nao acontece). 9-max e minoria do volume (prod 90d: mesa 8 45%, mesa 7 28%, mesa 6 12%, mesa 9 5%). **Correcao proposta:** usar o assento por jogadores atras (`_mapa_da_mesa`, o mesmo das referencias) na chave E na escolha das ranges — conserta o range e AUMENTA o reuso, porque funde spots equivalentes de mesas diferentes. **Cuidado:** nos de mesa curta ja gravados foram resolvidos com range errado; re-SOLVAR, nunca re-chavear (ver [[project_board_hash_bug]]). **MEDIDO EM PROD 08/09 (90 dias, 27.726 decisoes pos-flop):** (A) 18% (4.914) tem assento que MUDA na traducao — os pares comuns sao UTG+2->LJ (1.071), UTG->UTG+1 (1.068), UTG+1->UTG+2 (995). (B) Nas 2.575 com no e assento trocado, o range assumido no solve e MAIS ESTREITO que o real em media 4,0 pp (mediana 3,6, p90 6,8) e e mais estreito em 100% dos casos: vies numa direcao so. (C) **O ganho de reuso que eu previa NAO EXISTE: 27.717 spots distintos hoje, 27.717 com o assento efetivo, ZERO se fundiriam** — a chave carrega o board carta a carta, entao spots de mesas diferentes nunca coincidem no resto. Minha afirmacao anterior estava errada e a medicao a derrubou. Raio de dano: das 2.642 decisoes com no e assento trocado, 244 (9%) estao acusadas de erro hoje, 103 delas `gto_critical`. **Portanto o conserto vale por CORRECAO, nao por economia.** Mexer na chave obriga a re-solvar ~5 mil spots (os antigos viram orfaos; re-SOLVAR, nunca re-chavear). **Proximo passo antes de decidir:** re-solvar uma amostra das 244 acusacoes com o range do assento efetivo e contar quantas mudam de veredito. Sem esse numero, 4 pp de vies nao justificam mexer numa chave que ja custou caro. | Decisao do dono depois da amostra. |
| AY-28 | **Veredito por semelhanca enquanto o exato nao chega.** Passo 1 (card do admin) e a assinatura do spot ENTREGUES LOCAL 08/09. Medido em prod: semelhanca acerta a acao em 75%, erro/nao-erro em 79%; 60% das decisoes sem no ja teriam vizinho; critico->correto 3%. **Passo 2 ENTREGUE LOCAL 08/09 (noite):** `decisions.spot_assinatura` gravada no upload (backfill: 14.176 em dev), `leaklab/semelhanca.py` (vizinhos por assinatura de board, media ponderada da relacao da mao, cache `gto_tree_relacoes`), `vereditos_por_semelhanca` gravada no upload e comparada quando a fila drena (acao, erro/nao-erro, rotulo), curva no card do admin com a meta (85% erro/nao-erro com 3+ vizinhos, duas semanas). Nada ao jogador. Aguarda aprovacao do dono para o deploy; em prod rodar `backfill_spot_assinatura.py --aplicar --provisorios 14` depois do deploy para a curva comecar. **Medido em prod 08/09 com a assinatura corrigida (board cortado na street):** exato no momento do upload 3,0%, com vizinho 62,1%, respondivel na hora 65,1% (por semana de import: 45, 49, 62, 75%); acordo com o exato ação 78%, erro/nao-erro 84% (87% com 3+ vizinhos), rotulo 63%. O rotulo baixo e o motivo de a semelhanca nunca poder acusar GRAVIDADE no passo 3. **Passo 3 DECIDIDO pelo dono 08/09 (noite):** "mostrarmos com maior precisao se houve erro ou nao ja resolve bem, e deixar sem a gravidade nestes casos, ate que o solver rotule aquele spot" e "basta o usuario saber que aquele veredito e por semelhanca, antes da resolucao do spot no solver". Ou seja: o card mostra DIRECAO (houve desvio ou nao) com selo 'por semelhanca', SEM severidade, sem ev_loss e sem entrar no plano de estudo nem no score; quando o solve exato chega, o veredito e substituido pelo definitivo. Invariante a escrever: semelhanca nunca acusa gravidade. A curva do card do admin deixa de ser PORTAO e vira VIGIA (se o acordo cair, a exibicao sai). Proximo: (4) prioridade da fila: card aberto, provavel desvio, treino. | Um passo por vez, com homologacao. |
| AY-27 | **Teto do Pro: 200 torneios/mes e pouco para grinder?** Medido 08/09: fundador 65 bateu 200 em 4 dias (21 mil maos), fundador 62 com 280/mes; pagante 58 com 54, pagante 3 com 21. Entregue LOCAL: teto por usuario no admin + fundadores 1.000. Decidir o default do Pro (sugestao: 400; o custo real e a fila do solver e o Neon, nao a contagem) e ajustar a copy dos planos (guarda `test_copy_dos_planos`). | Decisao do dono. |
| AY-25 | **HUD: o agregado aponta, nao julga** (avaliacao externa de 07/09; o dono concordou com a direcao). (a) AF e Steal viram informativos, sem cor nem faixa: AF e heranca de cash, Steal mistura CO/BTN/SB e a grade ja tem RFI por assento com solver. (b) RFI, 3-Bet e Fold to 3-Bet no HUD mostram "N de M assentos fora do solver", vindo da grade, em vez de veredito por faixa fixa (o agregado pode ficar na faixa com todo assento errado). (c) VPIP/PFR do HUD com a referencia do solver nas proprias maos (a mesma funcao da grade), aposentando a faixa fixa. (d) RFI no HUD (rascunho aprovado em parte) entra junto, com a cor vinda dos assentos. Rejeitado: 'C-Bet e ruido' (a referencia por spot do AY-23 condiciona ao board) e 'Open Limp amostra pequena' (milhares de oportunidades). | Depois do deploy de 07/09. |
| AY-24 | **Habito: relatorio de novidades para os fundadores a cada deploy** (dono, 07/09: "podemos ter este habito com eles"). Formato: o que mudou, onde ver, como testar em 3 minutos, e AVISO do que muda de valor (Fold to 3-Bet, LJ). Linguagem do jogador, sem dado de outro usuario, sem jargao interno. O 1o esta pronto como rascunho (artefato 'GrindLab Novidades Setembro'), com [DATA DO DEPLOY] a preencher. Enviar pelo broadcast filtrado por `plan_source='founder'` ou no grupo do bot. | Sai junto com cada deploy; medir retorno pelos tickets e respostas. |
| AY-22 | **Buraco no chart: `40bb vs_3bet UTG+1 vs BTN` vazio** (achado 07/09; unica celula vazia do JSON). Os leitores agora devolvem None; recapturar a celula quando houver fonte preflop viva (ver AY-8). | Baixo; a regua do fold ao 3-bet do UTG+1 a 40bb vs BTN fica sem referencia ate la. |
| AY-21 | **Visao agrupada na grade por posicao (EP / MP / CO / BTN / SB / BB).** ENTREGUE LOCAL 07/09: chips Por assento / Agrupado; grupo = uniao das linhas dos assentos, mesmas stats e referencias; modal contra quem aceita o grupo. | Sai no deploy de 07/09. |
| AY-19 | **C-Bet IP / OOP no hover do C-Bet do HUD** (sugestao do Rullian, 07/09). Hoje o C-Bet e um numero so. IP/OOP no flop = o heroi age depois do vilao (ordem pos-flop SB..BTN); a decisao grava `position` e `vs_position` (o caller do open) e `n_active_opponents`; `isInPosition` do spot e por assento, cru. Plano: no `get_player_stats`, duas contas de c-bet com a mesma definicao de oportunidade (`hero_was_aggressor` no flop, sem aposta na frente) separadas por IP/OOP calculado de (position, vs_position); multiway (n_active_opponents > 1) declarado fora; o mesmo no `accumulate` (HUD do torneio/oponente). Tooltip do C-Bet mostra as duas com amostra; a grade por posicao pode ganhar a coluna depois. Referencia: charts postflop nao tem c-bet por posicao; fica sem regua, so numero. ~2-3h com testes. | ✅ **ENTREGUE LOCALMENTE 07/09** — tooltip do C-Bet com IP/OOP e amostra; duas fontes (decisoes x acoes cruas) provadas iguais no torneio congelado; 5 mutacoes acusadas. A matriz 13x13 (item c do AY-15) segue aberta. |
| AY-18 | **Fold to 3-Bet do HUD e a stat GERAL do PT4 mostrada contra a regua da stat AFTER RAISE** (feedback do Rullian, 06/09: "meu valor esta muito alto, +80%"; prod tem a definicao de 04/09). Em 04/09 o HUD passou para a `Fold to PF 3Bet` geral (inclui 3-bet a frio) e bateu com o PT4 (76,5 x 76,81); mas a referencia do card (55-72) e a regua (`STAT_REFERENCES` 50-60) sao da `Fold to PF 3Bet After Raise` (voce abriu e levou 3-bet), que e a que o jogador olha e a que o Rullian compara. Dev: geral 80,9 x do open 56,9. O HUD do oponente usa a mesma definicao geral. **Proposta:** HUD (heroi e oponente) passa a mostrar a After Raise (ja calculada como `fold_to_3bet_open` na grade), a geral fica como `fold_to_3bet_any` para o teste congelado do PT4 (o gabarito `alvo_pt4.json` so tem a geral, 76,92). **Validar com o Rullian:** pedir os DOIS numeros do PT4 dele (Fold to PF 3Bet e ... After Raise) e comparar com os nossos na conta dele em prod (precisa de ssh). | **ENTREGUE LOCALMENTE 06/09** (HUD heroi/oponente/torneio/replayer na After Raise; geral em `fold_to_3bet_any` para o gabarito; 4 mutacoes acusadas). Rullian em prod: geral 81,6 / After Raise 59,3 (CoinPoker 62,5, ele lembra ~65). O print dele nao tinha a coluna preflop (a ultima e Fold to FLOP 3Bet), mas validou VPIP/PFR/RFI/3Bet/WTSD/WSD/CBet/AF — RFI 26,90 exato, BTN 45,31 exato. Pedir a coluna Fold to PF 3Bet After Raise para fechar o numero. |
| AY-17 | **Solver 100% sob demanda: apagar o box base, so snapshot + burst** (ideia do dono, 06/09: "server gto muito tempo ocioso; criar so quando tiver necessidade"). O burst ja existe e esta LIGADO (cron tick 10/10min, cx43 EUR0,03/h, sobe pending>=400, desce <=50/20min; ver `scripts/burst_do_solver.py`). Virar o unico solver exige: (1) gatilho no UPLOAD (evento), nao no cron, senao a 1a analise da sessao espera ate 11min; (2) limiar pending>=1 e drenagem por fila vazia (~15min); (3) decidir a espera do solve por mao no replayer (~1-2min de boot quando nao ha servidor); (4) apagar o `grindlab-solver` (Hetzner cobra desligado) e manter so o snapshot. **Medir antes** em prod (`gto_hand_requests`): horas/dia com fila vazia, rajadas/dia e duracao — Hetzner cobra por hora iniciada, entao o custo e rajadas x horas; comparar com o box dedicado atual. | A medir com ssh aberto; decisao depois dos numeros. |
| AY-15 | **Perfil por posicao: regua volta SO onde ha chart, e RFI por assento** (feedback do Rullian + decisao do dono, 06/09). O dono queria a regua de volta e trouxe uma tabela de VPIP por assento; medida contra os nossos charts, a tabela e mais tight que o solver em todo assento (BTN 38-48 x 51-55, CO 25-32 x 38) — folclore, sem fonte. Decisao: referencia por assento vem dos NOSSOS ranges (`docs/leaklab_gto_ranges.json`), ponderada pela distribuicao de stack efetivo das maos do jogador naquele assento (o solver abre 55% no BTN a 100bb e 38% a 14bb; faixa fixa acusaria quem joga certo). **Fase 1:** coluna RFI (PFR nao serve, inclui 3-bet) com regua do chart de abertura, E filtro de stack no card (Todos / 40bb+ / 20-40bb / <20bb, casado com as profundidades dos charts; `decisions.effective_stack_bb` ja existe). Faixa escolhida = numeros das maos nela + chart daquela profundidade, sem media; "Todos" = ponderado pelos stacks do jogador no assento, pesos no tooltip. Custo declarado: ~200 maos por celula com 6k maos, mais "—". Exige detectar pote aberto ao chegar no hero, como o 3-bet ja conta raises antes. **Fase 2:** 3-Bet e Fold 3-Bet com regua, ponderada tambem por quem abriu. **Fora:** VPIP/PFR e todo o postflop seguem so o numero (sem referencia por assento defensavel). **Depois:** matriz 13x13 do que o jogador abriu por assento (Rullian manda print do PT4) (o filtro de stack ja esta na Fase 1). | **Fases 1 e 2 IMPLEMENTADAS LOCALMENTE 06/09**: a grade e "voce contra o solver, por assento" — RFI, 3-Bet e Fold 3-Bet do open, cada um com a faixa do chart (P20-P80 + folga), filtro de stack, o resto do HUD declarado fora com motivo. NAO deployada: front e back sobem juntos. **Fase 3 ENTREGUE LOCALMENTE 06/09** (VPIP/PFR = media do solver nas maos do jogador; cobertura >= 70%; folga estatistica; 6 mutacoes acusadas). **Aberto:** (b) **ENTREGUE LOCALMENTE 06/09**: painel "contra quem" ao clicar em 3-Bet/Fold 3-Bet (uma linha por oponente, mesma definicao do stat, regua estreita; corte de 30 oportunidades por linha). (c) **Matriz 13x13 das maos abertas por assento — ESPECIFICADA 06/09 pelo print do PT4 (Hand Range Visualizer)**: estatistica Raised First In por assento (Button no print), filtro de stack efetivo (90-300bb) e periodo; celula = mao + numero, modo Range (fatia da mao dentro das aberturas: AKo 2,78, AA 0,87) e modo Frequencia (o "Value" do PT4: abriu / recebeu com o pote intacto, comparavel ao chart); verde mais escuro = mais frequente; RFI geral em cima (29,10% em 16,1k oportunidades); clique na mao abre resumo (n, BB won, VPIP/PFR) e a lista das maos com a linha de acao. Nosso: `hero_cards` + pote intacto + assento + `effective_stack_bb` ja gravados; reaproveitar a matriz de `/ranges` com o chart do solver AO LADO (a diferenca vira visual mao a mao); chips de stack e recorte de volume da tela; clique -> lista com link para o replayer (`hand_id`). Estender depois para 3-bet contra quem e defesa da BB. ~1 dia. Depois do deploy do pacote e da decisao do AY-18. (d) o 400 mudo do filtro de stack visto no log de dev em 06/09 nao foi reproduzido pelo proxy; o backend agora loga o valor recebido — conferir no proximo clique do dono. **(c) matriz 13x13 ENTREGUE LOCAL 08/09** (modal pela celula RFI, voce x solver, divergencias; aguarda aprovacao e deploy). |
| AY-7 | **Recompute `opponent_profiles`** — ver item proprio no Backlog Futuro. | 43 celulas. Baixo, e ja medido. |
| AY-8 | **Ranges JSON: runtime x versionado** | ⏸ **ADIADO 06/09.** A captura preflop e caminho MORTO em producao: fonte e o GW descontinuado, `GTO_WIZARD_ENABLED=0`, tabela de rastreio nem existe la. So rodava em dev (flag `true` no `.env` local) e reescrevia o JSON versionado — quem mexeu no arquivo em 04/09 fui eu, importando 60 torneios em dev. O dono descartou o gate (uma linha, valor pequeno). Reabrir quando houver fonte preflop viva: captura em tabela, sobreposicao dentro do `_load()` preenchendo buraco sem substituir carta, `fonte` no spot, refresh por TTL por worker. Para nao sujar o git em dev: `GTO_WIZARD_ENABLED=false` no `.env` local. |

**[AY-11] `score` faz DOIS trabalhos incompativeis** — ⏸ decisao do dono: fica como esta, e a
separacao vira estudo proprio

Achado em 05/09 investigando os vermelhos do AY-10. Em producao, **4.062 decisoes com o score
fora da faixa do proprio label** (`_LABEL_MAX_SCORE`: standard 0,08 / marginal 0,18 /
small_mistake 0,35). Ainda 5,2% das 57.987 importadas em setembro — nao e residuo.

**ERREI O TAMANHO DUAS VEZES, e as duas a medicao me corrigiu. Fica registrado.**

*1o erro — inflei.* Afirmei que contaminava o plano de estudos, olhando
`priority_score = COUNT(*) * AVG(d.score)` e **sem ler o `WHERE` quatro linhas abaixo**:
`AND d.label IN ('small_mistake','clear_mistake')`. Os dois rankings selecionam por LABEL, e os
incoerentes sao `standard` (795) e `marginal` (3.255) — ficam de FORA. O `get_gto_leak_ranking`
nem usa score (peso fixo por `gto_label`). **O plano NAO e contaminado.**

*2o erro — "consertei" o que nao era defeito.* Escrevi uma trava final
(`min(score, teto[label])`) e ela quebrou dois testes: `test_street_multipliers_river_gt_preflop`
e `test_icm_tax_raises_required_equity_for_thin_call`. **Os dois estavam certos.** Medido: o
mesmo spot da 0,551 no preflop e 0,694 no river, ambos `small_mistake`; a trava colapsava os
quatro em 0,35 e apagava o multiplicador de street e a ordenacao dentro da banda. Revertido.

**O que de fato existe:** o `score` faz dois trabalhos incompativeis.

| consumidor | quer |
|---|---|
| card / veredito | score coerente com o label |
| ranking e curva de evolucao | resolucao, inclusive ACIMA da banda |

Quando uma regra rebaixa o label (GTO valida a acao, gate de ICM, teto de pote limpado), os
dois querem coisas opostas. Hoje o motor atende o segundo.

**DECISAO (dono, 05/09): fica como esta.** O contrato foi DECLARADO no codigo, em cima de
`_LABEL_MAX_SCORE` — score acima do teto e por desenho, quem encontrar um nao achou bug.
Efeito aceito e medido: a curva de evolucao fica levemente PESSIMISTA (−0,7% a −11,9% conforme
o usuario). Sem isso, a proxima pessoa redescobre como defeito pela terceira vez.

**A ESTUDAR (pedido do dono): a opcao 2 — separar `score_heuristico` de `score_do_veredito`.**
Levantar beneficios e impactos antes de decidir:
  - *beneficio*: acaba a ambiguidade na raiz; cada consumidor le o campo que lhe serve; a curva
    de evolucao deixa de ser pessimista sem perder a ordenacao do ranking;
  - *impacto a medir*: coluna nova em `decisions` (migracao + backfill de 71 mil linhas);
    quais dos ~14 pontos do motor escrevem cada campo; todo consumidor de `score` (curva,
    ranking, priority_score, ELO?, card, replayer, revalidacao) tem de ser reclassificado um a
    um; e o acervo antigo fica com so um dos dois campos — decidir se reprocessa ou convive.
  - *alternativa a comparar*: reescalar o score proporcionalmente dentro da nova banda quando o
    label cai, em vez de dois campos. Preserva ordenacao e coerencia com UM campo, mas a conta
    de reescala e arbitraria e precisa de justificativa.

**Gap menor, no mesmo lugar:** `_LABEL_MAX_SCORE['small_mistake'] = 0.35` e `_label_from_score`
usa `score <= 0.36`. Duas constantes discordando em 0,01, responsaveis por 12 das 4.062. Nao
unificado de proposito — mexer em fronteira de banda muda veredito de todo mundo.

**[AY-9] AUDITORIA DIRIGIDA POR MODO DE FALHA** — ✅ **ENTREGUE 05/09** como
`test_auditoria_por_modo_de_falha.py` (14 testes, na suite). Sete padroes, cada um com detector
que PROVA achar o caso conhecido (regra 1) e allowlist com motivo: P1 regra copiada, P2 guarda
que se desarma, P3 literal cru com helper canonico, P4 arquivo versionado escrito em runtime,
P5 chave de cache constante, P6 (so a forma estreita: `_preview` com SELECT proprio — a versao
larga flagrava 29 scripts legitimos e SAIU, pela regra de "sem detector confiavel nao entra"),
P7 copy com palavra de desenho. Tres detectores quebrados de proposito, todos acusaram. O
detector P5 aprendeu com um falso positivo (prefixo `cmp_` nao e chave constante).

**Achou na 1a rodada, antes do dono:** `posProfile.tooltip` descrevendo faixa verde e ponto
removidos na vespera — 4a vez a legenda desse card, 1a em que o detector pegou primeiro.
Reescrito nos 3 idiomas. E tres frentes novas, abaixo.

**[AY-12] `d.label IN ('small_mistake','clear_mistake')` em 8 funcoes** (achado P1). "O que
conta como erro" copiado 8 vezes. `critical` existe em `verdict._SEV` e nao esta em nenhuma —
latente (0 em prod), mas e a forma EXATA do `founder` fora do MRR. Virar `_SQL_ACUSADO` (fonte
unica) com varredura N+1, como `_sql_pro_pagante`. Trabalho mecanico, baixo risco.

**[AY-13] Dois mapas de posicao a mais** (achado P3) — ✅ **ENTREGUE 06/09.** `grupo_posicional`
(normaliza pelo mapa do motor, agrupa pela ordem canonica) e a fonte unica; DNA e matriz de
alinhamento passaram a usa-la. Em prod so o rotulo `LJ` muda de lugar (EP -> MP na matriz; passa
a ser "cedo" no DNA). 4 mutacoes, 4 acusadas — a 1a semente do teste saturava o indice e deixou
uma passar em silencio; refeita com proporcoes dentro da escala. `test_grupo_posicional.py` (6).

**[AY-14] `_preview` com SELECT proprio em `backfill_coach_trials` e `expire_coach_trials`**
(achado P6). A forma exata do `expire_subscriptions`, cujo dry-run listava fundadores que a
execucao nao tocava. Conferir se o filtro do preview e o MESMO da execucao; o certo e o dry-run
chamar a mesma funcao com `dry_run=True`.

**DIVIDAS DE ARVORE (limpar, nao esquecer)**

- `stash@{0}` "WIP analytics intencao vs trafego (04/09)" toca `api.ts` e `Index.tsx` — os MESMOS arquivos do perfil por posicao. **Vai conflitar.** Ao aplicar, o `playerStatsByPosition` precisa recuperar a flag `auto`.
- `stash@{1}` (de 2f90583) traz `server.log` e `frontend.log` — 52.299 insercoes de LOG. E lixo; confirmar com o dono e descartar.

**PENDENCIAS ANTIGAS QUE SEGUEM ABERTAS** (do fechamento de 04/09): GRAFIA residual na decision 364518; ACR PFR -0,81 e 3Bet -0,71 contra o PT4; BB com 259 maos a menos; `/analyze` quebrado em dev (GTO server morto no `.env` local); `link_subscription_id` sobrescreve; sumarios de torneio do Rullian para ICM; HUD configuravel com as definicoes do PT4.


### [PARSER-ACR] — Suporte a Hand History do ACR Poker ✅ COMPLETO 2026-07-01 (fases 1-6)

**COMPLETO:** ACR é o 3º site (branch `site=='acr'` no `leaklab/parser.py`): detecção `Game Hand #`, split próprio, seats sem "in chips" (decimal), antes/ações SEM dois-pontos, `raises X to Y`→total, all-in, board/showdown reusados. **Fase 5 (financeiro) FECHADA:** buy-in vem do FILENAME (`TN-$0{FULLSTOP}50`→$0.50) — o frontend manda o `filename` no `/analyze`, o backend parseia (`_acr_buyin_from_filename`), e o ACR **NÃO assume busted** (prize/profit=None="resultado desconhecido", não inventa prejuízo). Validado nos 3 arquivos reais (86 mãos → 136 decisões com posição); merge por hand_id no import. Testes `tests/test_acr_parser.py` (6, regression). **Prize/ROI via arquivo de RESULTADOS ✅ ENTREGUE 2026-07-01:** o ACR tem um Tournament Summary separado (`.ots`, JSON com place+prize por jogador). `parse_acr_results` + `POST /tournament/results` + botão "Resultado" na lista de torneios (`Tournaments.tsx`) completam prize/profit/place/buy_in — prize vem do arquivo real. Validado (MusashiBR 6º $1.19, profit +$0.64). Ver [`specs/acr-parser.md`](specs/acr-parser.md).

> _(FEAT-17 concluído em v0.83.0 — entrada movida para o roadmap acima. Verificado 2026-06-15: `OnboardingModal.tsx` 4 passos, gate via `ProtectedRoute` (só com user carregado), finish→`/dashboard`→CTA de upload do `EmptyDashboard`, i18n nas 3 locales, endpoint+coluna+repo presentes.)_

### [PAY] — Frente de pagamentos ✅ ENCERRADA 2026-06-17 (PAY-01 → PAY-04)

> **Linha completa.** [`specs/pay-01-stripe-audit.md`](specs/pay-01-stripe-audit.md).
> - **PAY-01** (revalidação): 5 bugs (dupla-gravação→idempotência; rótulo gateway; cancel quebrado; MRR R$49→R$99; marca no recibo) + `payment_intent.payment_failed`. D-1 (recorrência/expiração) ficou em aberto → resolvido em PAY-02/04.
> - **PAY-02** (plano anual + vigência): anual R$990 (2 meses grátis) + `plan_expires_at` (opção B); `get_quota_status` expira Pro vencido; cron `expire_subscriptions.py`.
> - **PAY-03** (anti-fraude + admin): `/activate` deriva tudo do PI real (ownership/ciclo/valor); `/subscription/upgrade` → admin-only; visão financeira admin (receita/MRR/ARR/gateways/duplicados/pagamentos). `test_stripe_hardening` (20).
> - **PAY-04** (recorrência automática): Stripe Subscriptions de verdade (cobra sozinho + dunning); webhooks `invoice.paid`/`payment_failed`/`customer.subscription.*`; Billing Portal; `plan_source='stripe_sub'` governado só por webhooks; `scripts/stripe_setup.py`. Retrocompat (PI legado segue válido).
> **Pendência = só operação:** criar Product+Prices recorrentes no Stripe (rodar `stripe_setup.py --apply`), setar env (`STRIPE_*`, `VITE_STRIPE_PUBLISHABLE_KEY`), registrar webhook, agendar crons (`expire_subscriptions.py`, `expire_coach_trials.py`) no host. Testes finais: api 116/116, database 88/88.

**Valor:** O meio de pagamento precisa estar comprovadamente funcional e correto antes do launch — qualquer falha aqui é receita perdida ou cobrança errada.

**O que revalidar** (`backend/leaklab/stripe_gateway.py`, `api/app.py` `/subscription/checkout` ~4972, `/subscription/webhook` ~5031):
- **Checkout:** `/subscription/checkout` cria a assinatura e devolve `client_secret`; `PLAN_AMOUNTS` batem com os preços reais; planos free/pro corretos.
- **Webhook:** `validate_webhook` rejeita sem `STRIPE_WEBHOOK_SECRET` (já guarda em 5038) e com assinatura inválida; cada `event_type` (invoice.paid, subscription.updated/deleted, payment_failed) atualiza `plan`/`payments` corretamente; **idempotência** (mesmo evento 2x não duplica).
- **Ciclo de vida:** upgrade, downgrade, cancelamento e falha de pagamento refletem no plano e na quota (`get_quota_status`).
- **Modo test × live:** confirmar chaves/ambiente; nada hardcoded de test em prod.
- **Conciliação coach:** `coach_payments` (repasse) bate com os pagamentos reais dos alunos pro.
- Entregar com testes (estender `tests/test_subscription.py`) + checklist de smoke manual no Stripe Dashboard.

### [COACH-02] — Coach como aluno + Pro de cortesia (3 meses) + meta de 15 pagantes ✅ COMPLETO 2026-06-16 (P1+P2+P3)

**Plano completo:** [`specs/coach-onboarding-trial.md`](specs/coach-onboarding-trial.md). **P1 (backend) ENTREGUE:** colunas `plan_source`+`coach_trial_ends_at`, trial na aprovação, `maybe_promote_coach_earned` (engatado em approve_link_request + Stripe), job `expire_coach_trials`, `GET /coach/trial-status`, MRR exclui perk, `test_coach_trial` 9/9. **P2 (frontend) ENTREGUE:** routing aberto p/ coach (dual-role), switch de workspace Coach⇄Minha conta no header, upload liberado, banner de trial no cockpit. **P3 ENTREGUE** (verificado no código 2026-06-29): aviso de fim de trial ≤7d via `notify_expiring_coach_trials` (em `expire_coach_trials.py`), backfill de coaches legados (`scripts/backfill_coach_trials.py`), docs + i18n. Pendência só operacional: cron `expire_coach_trials` agendado no host.

**Modelo:** ao ser aprovado, o coach ganha **3 meses de Pro de cortesia** + acesso pleno de **aluno** (upload/treino/insights) além da visão de coach. Meta: **15 indicados pagantes** (`invited_via_invite_id` + `link_status='approved'` + `plan='pro'` — barreira anti-gaming é o pagamento real). Bateu a meta a qualquer momento → `plan_source='coach_earned'` (Pro permanente). Não bateu até o fim do trial → **downgrade p/ Free**, restando só a **comissão %** por aluno pagante (comp 4/10 inalterada).

**Mudanças-chave:** `users.plan_source` + `users.coach_trial_ends_at`; `approve_coach_application` concede o trial; job diário `expire_coach_trials` (mesmo padrão do snapshot de leaderboard); `maybe_promote_coach_earned` engatado em `approve_link_request`/ativação Stripe; MRR admin exclui Pro de cortesia; frontend libera rotas de aluno p/ coach + **switch de workspace** (Modo Coach ⇄ Minha conta) + banner de trial no cockpit. Fases P1 (backend) / P2 (frontend) / P3 (polish+backfill).

**Conexões:** é a 1ª instância concreta de **expiração de plano** (PAY-01/D-1); reusa SEC-01 fase 2 (`link_status`); não conta como MRR (estende o fix B-4 do PAY-01).

**Decisões em aberto:** backfill de coaches legados (recomendado: novo trial de 90d); nav unificada vs switch (adotado switch); aviso de fim de trial in-app vs e-mail.

### [SEC-01] — Convite do coach single-use por aluno (integridade da indicação) *(criado 2026-06-15)*

**Problema:** hoje `assign_invite_key` gera **uma chave permanente e reutilizável por coach**; qualquer aluno com a chave se auto-vincula (`link_student_to_coach`) sem aprovação nem expiração — só limita por `max_students`. A chave **é passável de aluno para aluno**. Com a compensação por **indicados e ativos**, cada indicação precisa ser um ato deliberado e único, senão a atribuição de referral é burlável.

**Opções (decisão de produto):**
1. **Convites single-use (recomendado):** tabela `coach_invites` (code, coach_id, used_by, used_at, expires_at); coach clica "convidar aluno" → gera link/código único → consumido no resgate → não reutilizável. `users.invite_key` vira legado/backward-compat.
2. **Aprovação do coach (2ª camada):** mantém código compartilhável, mas o vínculo entra como **pendente** e o coach aprova; comp conta só aprovados (robusto mesmo se o código vazar).
3. **Stopgap barato:** `max_uses` + `expires_at` na chave atual.

**Recomendação:** (1) como base + (2) como reforço. Backend: nova tabela + endpoints de gerar/listar/revogar convite e resgate; frontend: `InviteKeyWidget` vira "gerar convite" (lista de convites e status). Pré-requisito de integridade antes de ligar a comp por referral.

**Spec detalhado:** [`specs/sec-01-coach-invites.md`](specs/sec-01-coach-invites.md) — modelo de dados (`coach_invites`), endpoints, fluxo de resgate transacional, migração/compat da chave legada, faseamento (single-use → aprovação) e 4 decisões de produto pendentes.

---

### [FEAT-18] — Mobile audit + responsividade *(Sprint AY)*

**Valor:** O dashboard com cards arrastáveis nunca foi auditado em mobile. A experiência provavelmente está quebrada — drag handle é inutilizável em touch, cards podem ter overflow, e o nav colide com conteúdo em telas pequenas.

**O que auditar e corrigir:**
- Dashboard: drag & drop em touch (desabilitar ou substituir por reorder via botões ↑↓ em mobile)
- GhostTable e Sparring: botões de ação com tamanho mínimo de toque (44×44 px)
- HudHeader: nav em mobile (menu hambúrguer funcional em todas as rotas)
- Tabelas de docs e cards de análise: scroll horizontal em telas < 400px
- Formulários de perfil: inputs e labels não colapsam em mobile

**Abordagem:**
- Auditoria com DevTools (viewport 390×844 — iPhone 14) em todas as rotas principais
- Corrigir breakpoints e adicionar `touch-action` onde necessário
- Testar drag & drop em dispositivo real ou emulador iOS/Android

**Esforço estimado:** ~2h audit + ~10h correções

---

### [FEAT-19] — Modo Gravação da mesa (para coaches) *(adiado — "depois", sem sprint comprometida)*

**Valor:** Coaches gravam aulas/conteúdo a partir do replayer, mas a mesa não está preparada para captura (chrome ao redor, sem ferramentas de marcação). Um "Modo Gravação" transforma o replayer num palco limpo estilo transmissão (PokerGO), reutilizando todo o replayer existente — **é uma camada, não outra mesa**.

**Premissa técnica (validada na análise):** o replayer já tem `focusMode` (`Replayer.tsx:1427` — fullscreen nativo + esconde `HudHeader` + solta `max-w`). O Modo Gravação é `focusMode` turbinado: mesma `PokerTableV3`, mesmos controles, + overlays visuais. O telestrator desenha em coordenadas de TELA (anotação por cima), não precisa casar com as coords SVG da mesa.

**O que construir (por fases, cada uma entregável):**
- **Fase 1 — Palco limpo:** toggle `recMode`; mesa full-bleed **16:9** (trocar `aspect-[16/10]`); esconder `SidePanels` + card de decisão; atalhos de teclado por **street** (pula pro 1º step de preflop/flop/turn/river — reusa `stepIdx` + `step.street`). *Já útil para gravar.*
- **Fase 2 — Telestrator (o item caro):** **SVG overlay** absoluto sobre a mesa + barra de ferramentas (seta, círculo, caneta livre, cor, undo, limpar). SVG > canvas (vetor, fácil add/remove de formas, sem raster).
- **Fase 3 — Cursor-spotlight:** overlay com `radial-gradient` mask seguindo o mouse (escurece tudo menos um círculo). Toggle on/off.
- **Fase 4 — Pause + overlay de ranges:** ao pausar, mostra a matriz de range do spot por cima/ao lado (reusa os dados que o card já busca).

**Frontend (touch points):**
- `frontend/src/pages/Replayer.tsx` — estado `recMode` (estende `focusMode`); gating do `SidePanels`/card; container 16:9; handlers de teclado por street.
- `frontend/src/components/replayer/TableTelestrator.tsx` (novo) — overlay SVG de desenho + toolbar.
- `frontend/src/components/replayer/CursorSpotlight.tsx` (novo) — overlay de spotlight.
- i18n `replayer.json` (PT/EN/ES) para labels das ferramentas.

**Riscos/gotchas:** (1) telestrator é o grosso do esforço — o resto é casca; (2) `pointer-events` entre spotlight e caneta (gerenciar por z-index/ferramenta ativa); (3) decisão de UX: limpar desenho ao trocar de street (recomendado) vs manter; (4) "overlay de ranges" só preflop tem matriz pronta — postflop exigiria renderizar a estratégia do nó; (5) desktop-only (esconder toggle no mobile).

**Decisões pendentes (confirmar antes de codar):** acesso só-coach? · telestrator limpa por street? · overlay de ranges só preflop ou também postflop?

**Esforço estimado:** Fase 1 ~6h · Fase 2 ~16h · Fase 3 ~4h · Fase 4 ~8h (escopo a definir)

---

### [FEAT-20] — Colapsar veredito para 3 níveis (Correto / Aceitável / Erro) *(✅ CONCLUÍDO 2026-06-15)*

**Valor:** Hoje duas escalas sobrepostas dirigem o display — `gto_label` (frequência: correct/mixed/minor/**critical**) e `label` (severidade EV: standard/marginal/small/clear). A dualidade é a raiz dos bugs card≠badge e do over-flag ("crítico num +0,01bb"). Colapsar **o display** para 3 níveis dirigidos por **severidade (EV)** encerra a dualidade e faz **card = badge por construção**.

**Decisão central:** colapso é **só no DISPLAY**. A magnitude interna (4 níveis de `label`/`gto_label`) **permanece** — ELO (`elo_engine`), leaderboard, ranking de leaks, study/recommendation, cognitive_mapper dependem dela. A **frequência deixa de ser veredito** (vira contexto nas barras de estratégia).

**Mapa:** standard→**Correto** · marginal→**Aceitável** · small_mistake/clear_mistake→**Erro**.

**Fases:**
- **Fase 1 ✅:** fonte única do mapeamento — `leaklab/verdict.py:verdict3(label)` (back) + `cardLogic.verdictLevel(label)` (front, puro+testado). *(commit 73235f4)*
- **Fase 2 ✅:** card do replayer — ~8 ramificações de veredito → 3, dirigido por `error_label` (severidade); snap do `/replay` torna `error_label` autoritativo (multiway-clear via advisor); `isActionOk` alinhado; barras de frequência viram contexto. i18n PT/EN/ES já presente. Validado no t27 (standard→Correto, marginal→Aceitável, small/clear→Erro, multiway advisor-driven). vitest 25/25, engine 362/362, api 76/76. *(commit aea7701)*
- **Fase 3 ✅:** demais superfícies via fonte única (`verdictLevelOrError` + `VERDICT_META` + `<VerdictTag>`, i18n `common:verdict.*`): `TournamentDetail` (veredito por mão dirigido só pela severidade; frequência GTO vira marcador de FONTE; filtro/stats/leakTag/meta recalculados), `StudentDetail` + `CoachDashboard` (badges + override do coach colapsados em 3; filtro clear/small removido), `DecisionQualityCard` (4→3 fatias), seletor de override do Replayer (3 opções). Ranking de leaks por bb perdidos já existia (`LeakFinderCard`). vitest 28/28, build ok. *(commit pendente)*
- **Fase 4 ✅:** `/docs` reescrita em 3 níveis (scoring + gto_method 4→3, parágrafo "magnitude interna preservada", Forma Recente/Qualidade das Decisões, vocabulário antigo e chaves órfãs removidos, PT/EN/ES); **RecentForm** colapsado 4→3 (miss da fase 3, `verdictLevelFromScore`); paridade de testes back↔front (`verdict.py` em `test_card_invariants`; `verdictLevelFromScore`/`VERDICT_META` em `cardLogic.test`). Linha de escopo: veredito por decisão/sessão = 3 níveis; KPIs de magnitude (Standard%/Clear Mistakes%/Avg Score/EV-loss) preservados.

**Resultado:** card = badge por construção em TODA superfície; frequência (gto_label) virou contexto; magnitude (label EV) preservada internamente p/ ELO/ranking/study. Suites verdes: cardLogic 29, card_invariants 6, card_verdict 11, adherence 6, database 60, api 76, engine 362.

**NÃO muda:** `label`/`gto_label` armazenados, engine, ELO, ranking — magnitude interna intacta.

**Decisões (defaults assumidos):** nomes Correto/Aceitável/Erro; `marginal`→Aceitável; ranking por bb perdidos; barras de frequência mantidas como contexto.

**Esforço estimado:** Fase 1 ~3h · Fase 2 ~10h · Fase 3 ~10h · Fase 4 ~4h

---

## Backlog Futuro (não priorizar agora)

| Item | Motivo de adiar |
|---|---|
| Tournament Future Simulation | Requer reescrita do parser para capturar chip stacks + payout structure; ~3–4 meses de engenharia. Game-changer no longo prazo. |
| Autonomous Evolution Engine | Precisa ≥500 usuários ativos com ≥10 sessões cada para adaptação pedagógica real — sem essa massa, seria heurística fake |
| Meta-Game Evolution Forecast | Requer pool de dados de milhares de jogadores — inviável sem volume de usuários |
| Adversarial Exploit Engine | Sistema captura apenas decisões do hero, não dados de oponentes — exigiria produto HUD, categoria diferente |
| Neural Population Benchmark | Vetores de estilo estratégico de múltiplos jogadores = produto de research, não SaaS early-stage |
| Self-Evolving Decision Engine | Auto-ajuste de thresholds sem ground truth validado por experts = risco de degradação silenciosa do engine |
| Counterfactual Replay | Exige simulação Monte Carlo prospectiva — não temos equity calculator para linhas hipotéticas |
| Reg Archetype Recognition | Exige dados de adversários; fora do escopo atual (análise do herói, não do field) |
| Competitive Benchmark Layer | Exige pool de dados de outros usuários; questões de privacidade + volume mínimo |
| Fechar os 18 gaps postflop HU sem GTO (5,4%) | Não é fechável por re-solve com a infra atual (ver CHANGELOG 2026-06-15 + `docs/postflop_hu_gto_gaps.md`). Exige engenharia do **solver**: (a) paralelismo/box maior — solves frescos estouram o timeout de 300s no VM single-thread; (b) storage 8-bit ou ranges menores — spots de range larga batem 6GB de RAM; (c) emitir o ramo de bet/raise/sizing do hero no nó — sem ele as ações agressivas são `ungradeable`. ROI baixo agora (só 7 dos 18 acionáveis, 6 ungradeable; 11 são linhas default). Ferramenta pronta: `scripts/solve_attach_postflop_hu_gaps.py` (resumível). |
| i18n dos corpos de email transacionais (verificação, boas-vindas, comunicado, digest) para EN/ES | Hoje os textos fixos dos emails são só PT (`email_digest.py`); a UI de cadastro/verificação já está i18n nos 3 idiomas. Baixa prioridade enquanto a base for majoritariamente PT. Ao fazer: passar o `locale` do usuário aos builders (`build_verification_email_html`, `build_welcome_email_html`, `build_admin_email_html`, digest) e mover as strings fixas para dicionários por idioma. |
| **Varredura do EIXO DE TEMPO: 27 funcoes filtram por data de UPLOAD** | O `_build_tournament_filter` passou a janelar por `COALESCE(played_at, imported_at)` em 03/09 (achado do dono: o Rullian subiu 280 torneios de 3+ meses em 25 horas, e "ultimos 50" virava uma fatia da ordem do script). O conserto foi onde o defeito APARECEU; **27 funcoes nunca adotaram o filtro** e seguem em `t.imported_at >= ?`, contra 7 na politica correta. Entre elas: `get_gto_leak_ranking` (alimenta o plano de estudos), `get_strategic_twin_profile`, `get_cognitive_failure_report`, `get_leak_graph_data`, `get_career_projection`, `get_player_dna`, `get_player_level`, `get_leaderboard_metrics`, `get_icm_performance`, `get_confidence_drift`, `get_pressure_profile`, `get_breakdown`, `get_leak_roi_impact`, `get_common_leaks`, `get_coach_impact_metrics`. **Impacto medido (05/09, 180d):** micheldienstmann25 ve **13.878 decisoes pelo eixo de upload contra 1.318 pelo de jogo — 10,5x**; o card descreve o jogador que ele era ha mais de 180 dias como perfil atual. wrodrigo +18%. Rullian e os demais, zero (importam conforme jogam, ou todo o historico cabe na janela). Afeta exatamente quem chega novo e sobe acervo antigo. **NAO trocar cegamente:** o comentario de `get_evolution_metrics` (linha ~1185) documenta uma excecao legitima — o CHECK DE PRESENCA de dados do plano de estudos precisa de `imported_at`, senao torneio jogado ha >90 dias e importado agora some e quebra o plano. A varredura tem de classificar funcao a funcao: janela de ANALISE ("como voce joga") vs PRESENCA de dados vs uso administrativo. Fechar com teste que varra as N+1. |
| **Recomputar `opponent_profiles` com o acumulador consertado** | Os perfis gravados vieram do `opponent_stats` anterior aos consertos de 05/09 (WTSD, c-bet, 3bet, fold-to-3bet, denominador). **Escopo medido antes de priorizar, e ele e pequeno:** dos 14.458 perfis, so **31 exibem WTSD** (0,21%), **9 exibem c-bet** (0,06%), **3 exibem fold-to-3bet** — e **14.311 de 14.458 (99%) tem arquetipo `unknown`**. Os gates de amostra do HUD de oponente absorveram quase todo o defeito; quem sentiu foi o HUD do TORNEIO, que por design nao tem gate — e esse e calculado ao vivo do texto cru, entao o deploy ja o consertou sem reprocesso. Ao rodar `scripts/compute_opponent_profiles.py --apply`: **ele NAO tem a guarda de CoinPoker que o `/analyze` tem**. O `/analyze` pula `site='coinpoker'` e ainda aplica `_per_hand_anon = len(profiles) > 60 and len(profiles) > 3 * len(hands)`, porque o CoinPoker troca o hash do jogador a cada mao (~4,4 nomes unicos por mao) e o calculo explode. O script so detecta GG anonimo (posicao como nome), que e outro padrao. Sao 97 torneios CoinPoker de 516 com raw_text. Regra 5: a guarda vive em 2 lugares e so existe em 1 — extrair para funcao antes de rodar. Ganho esperado: 43 celulas corrigidas e talvez 2 arquetipos `calling_station` reavaliados. |
| **Artefato versionado que o runtime reescreve: `docs/leaklab_gto_ranges.json`** | Descoberto em 05/09, por acaso, ao conferir o que ia num commit. `run_autocapture` dispara numa thread ao fim de **todo** `/analyze` e escreve no master de ranges. Consequências nos dois ambientes, ambas silenciosas: **em dev**, qualquer import suja o repositório (60 torneios importados para popular a tela de perfil por posição reescreveram 5 spots; conferido que o conteúdo era equivalente — mesmo `aggr_pct`, zero mãos divergentes — e descartado); **em prod**, o código é assado na imagem, então toda captura feita em produção **se perde no próximo deploy** e ninguém percebe, porque nada lê o arquivo de fora. O ponto cego que deixou isso durar: commits aqui são sempre `git add <caminhos>` explícitos, então arquivo que ninguém nomeia nunca aparece. **Achado mais grave, medido em 05/09:** `Dockerfile` sobe `gunicorn --workers 2`, e o `_write_lock` do autocapture é `threading.Lock` — protege threads dentro de UM processo, não entre processos. Cada worker tem seu próprio `_data` e **nunca recarrega** (`if _data is None`). Worker A captura, muta a memória dele e regrava o arquivo inteiro; worker B, com o dict obsoleto, regrava por cima e **apaga a captura do A**. Pior: `gto_preflop_capture` já marcou o spot como `captured` para não martelar o GW, então o dado some E o rastreamento impede a recaptura — buraco permanente que se defende sozinho. Desenho proposto: base estática segue no git (dado curado, revisável em diff); captura vai para tabela `gto_preflop_ranges` (spot_key → spot_data), única superfície de escrita; a leitura carrega o JSON e sobrepõe as capturas da tabela, com invalidação por versão (um SELECT no boot, não por decisão); promover captura ao master vira passo deliberado. Ao atacar: decidir se o master de ranges é **dado versionado** (e aí o autocapture escreve em outro lugar — tabela ou volume — e a promoção para o master é um passo deliberado) ou **cache de runtime** (e aí sai do git). Enquanto não se decide, vale um teste que falhe se um `/analyze` mexer no arquivo. |
| **Ativar win-back em prod** (código pronto, `run_winback`) | Feature entregue e testada, ativação adiada. Ao ligar: (1) deploy da API + rebuild do Pages (painel admin); (2) rodar a **prévia** (dry-run) no admin antes de qualquer envio; (3) setar `WINBACK_ENABLED=1` + agendar `scripts/run_winback.py` 1x/dia no cron do host; (4) opcional: backfill de `last_login` a partir do último `imported_at` (senão inativos legados só entram no radar após o próximo login). Estágios 7/21/45d, cooldown 7d. |
