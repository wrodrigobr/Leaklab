# GrindLab — Protocolo de Progressão v2
### Especificação de build do loop de aprendizado e retenção

> **Status:** spec consolidada · v2 · 2026-07-25
> Substitui o rascunho v1. Incorpora: (a) a auditoria de fontes/consumidores de
> estratégia e a auditoria de ICM (feitas em 2026-07-25), (b) medições reais de
> sample no banco dev, (c) as decisões de design da discussão sobre mastery
> gating, interleaving e corpus de mãos reais.
> Documento de trabalho para execução no Claude Code.

---

## 0. Princípio central

O diferencial do GrindLab sobre concorrentes (RegLife e afins) **não é ter
mais conteúdo nem um plano mais bonito**. É que o loop **fecha no jogo real**.
Concorrentes medem "acertou 80% de 500 mãos treinadas" — desempenho num drill,
que não transfere garantidamente e esconde a magnitude do erro.

O GrindLab mede a única coisa que importa: **o EV perdido real, naquele tipo de
spot, nos torneios que o usuário sobe depois — caiu e se estabilizou?**

Se uma decisão de design conflitar com a honestidade da medição, a honestidade
vence. Um sistema que credita variância como progresso perde credibilidade no
primeiro mês em que o número reverte.

**Mudança central da v2:** a honestidade agora é implementada por **dois níveis
de estado por leak** (§1), não por um único gate. O gate de *progressão* é o
treino (rápido, sample infinito); o *selo* de correção é o jogo real (lento,
assíncrono). Misturá-los era a tensão não resolvida da v1.

### Dependências da v1 — status atualizado

1. ~~**Auditoria de ICM**~~ — **FEITA (2026-07-25).** Resultado: o grading é
   **chipEV puro**. ICM entra só como (a) nudge de ≤2pp na required equity na
   mesa final (via `icm_tax_pct` real de Malmuth-Harville, payouts aproximados
   hardcoded) e (b) gate que rebaixa Erro→marginal em **folds** apertados sob
   `icm_pressure == high`. Não há bubble factor nem conversão payout-aware do
   EV. Além disso, a correção estrutural (ranges ICM próprias) está **bloqueada**:
   GTO Wizard e GCP foram descontinuados; não há fonte de ranges ICM no curto
   prazo. **Decisão da v2: flag & exclude (§9), não "auditar antes".** Esperar
   um motor ICM que não tem caminho é adiar o loop indefinidamente.

2. **Canonicalização de spots** — **~70% existe.** `compute_spot_hash`
   (gto_utils) já canonicaliza street, posição, board com isomorfismo de
   naipes, stack bucket, bet bucket e pot_type. Gaps concretos a fechar na
   Fase 0 (§12): o hash não é persistido na tabela `decisions`; **dois esquemas
   de stack bucket divergentes coexistem** (`STACK_BUCKETS` 0-10/10-20/20-35/
   35-60/60-100 em gto_utils vs `_DEFAULT_BUCKETS` 10/14/17/20/30/40/50/75/100
   no preflop) e é preciso eleger UM antes de materializar a série temporal;
   `prev_action` só tem proxies (`is_3bet`, `preflop_raises_faced`); sem tag
   ICM na chave.

3. **(Nova) Higiene de dados** — pré-requisito que a v1 não listava. Existem
   **nós GTO degenerados residuais em produção** (bug do pot em fichas:
   `ev_bb` na casa de milhares). Um único outlier desses dentro de uma família
   destrói a série de EV. A query de progressão precisa de winsorização/cap
   de `ev_loss_bb` E a limpeza dos residuais precisa ser concluída. Idem:
   toda query cross-mão escopa por `tournament_id` (`hand_id` NÃO é único
   entre usuários).

---

## 1. A máquina de estados por leak (o coração da v2)

```
                     exame de mastery                 validação no jogo real
  EM TREINO  ────────(trilho rápido)───────▶  DOMINADO NO TREINO ────────▶  COMPROVADO NO JOGO
      ▲                                        (libera o próximo leak)          (o selo)
      │                                                 │
      └──────────────── REABERTURA ◀────────────────────┘
             (a) falha em revisão SRS do drill
             (b) EV real da família regrediu nos uploads recentes
```

- **Em treino** — o leak ativo. Recebe ~60% dos reps da sessão diária (§4).
- **Dominado no treino** — passou no exame de mastery (§7). **É o gate de
  progressão:** libera o próximo leak da fila. Rápido (dias), sample infinito.
  Rótulo no produto: "dominado no treino" — nunca "corrigido".
- **Comprovado no jogo** — a validação estatística no trilho lento confirmou
  (§5). Assíncrono: chega semanas depois, sem bloquear a progressão. É o único
  estado que autoriza a frase "leak corrigido no jogo real".
- **Reabertura** — o superpoder inimitável: o teste de retenção não é só o
  drill de revisão, é o próprio jogo. Se o EV da família regride nos uploads,
  o leak reabre **mesmo que o usuário continue gabaritando o drill** — é
  exatamente o caso que denuncia memorização sem transferência. A reabertura
  é *feature de confiança*, não vergonha: "a ferramenta não me deixa mentir
  pra mim mesmo". Comunicar assim.

**Regra de progressão:** um leak ativo por vez (foco Kumon). A fila (top 3
visível + fila oculta) continua existindo; o que muda é que só UM está "em
treino". Válvulas de escape na §8.

---

## 2. Arquitetura de medição: os dois trilhos

| | Trilho rápido (drills) | Trilho lento (jogo real) |
|---|---|---|
| **Fonte** | Corpus de situações (§6) + spots sintéticos | Uploads de hand history |
| **Frequência** | Alta (diária) | Baixa (por torneio) |
| **Papel** | Gate de progressão ("dominado no treino"), reps, engajamento | **Selo ("comprovado no jogo") + gatilho de reabertura** |
| **Granularidade** | Spot canônico (fino) | **Família de spot (grosso)** — §3 |
| **Nunca** | Declara "corrigido no jogo" | É usado como métrica diária |

Marketing decorrente: *"a única ferramenta que prova que você melhorou no jogo
real, não num simulador"* — a frase aponta pro selo, não pro gate.

---

## 3. Granularidade: spot canônico × família de spot (correção estatística nº 1)

**O problema, medido no banco real** (usuário principal, 2.210 decisões em 17
torneios): numa granularidade MAIS GROSSA que a chave canônica da v1 (só
street × posição × cenário × stack bucket, sem sizing nem board bucket), há
**190 famílias com mediana de 6 decisões por família**; só 35/190 chegam a 20
decisões. Volume mensal real: 2-9 torneios (~1-2 decisões/mês numa família
mediana). Com a chave canônica completa, os samples fragmentam ainda mais.

Consequência: validar no spot canônico completo levaria de muitos meses a
nunca. A v1 tratava "spots raros" como exceção; eles são o **caso majoritário**.

**Decisão da v2 — dois níveis de granularidade com papéis distintos:**

- **Spot canônico** (posição × stack bucket × prev_action × sizing bucket ×
  board bucket) → usado pelo **drill** (gerar variação, calibrar dificuldade,
  exame de mastery). Sample infinito, granularidade fina é vantagem.
- **Família de spot** (street × cenário × posição × stack bucket; postflop em
  famílias largas tipo "c-bet em SRP como agressor") → usada pela **validação
  no jogo real** e pela curva de progressão. É onde 20+ decisões reais são
  atingíveis em semanas.

A família é o agrupamento de spots canônicos: `spot_family = f(spot_canonical)`
— derivável, sem tabela própria obrigatória.

---

## 4. Camadas pedagógicas

Base: **Mastery Learning (Bloom)** — avanço por domínio real, tempo variável.
Sobre ela:

- **Interleaving (correção da v2 — prática blocada engana).** Drillar só o
  leak ativo produz domínio *aparente* que não transfere: o usuário aprende
  "neste trainer a resposta é fold", não *quando* foldar. A literatura é
  clara: prática intercalada parece pior durante o treino e é muito melhor em
  retenção e transferência. **Composição da sessão diária:**

  | Fatia | Conteúdo | Papel |
  |---|---|---|
  | ~60% | Leak ativo (família em treino) | Foco, volume onde dói |
  | ~25% | Revisões SRS de leaks dominados | Retenção; intervalos crescentes |
  | ~15% | **Spots de discriminação** — famílias vizinhas onde a resposta MUDA | Anti-memorização; ensina o "quando" |

  Exemplo de discriminação: leak = "fold demais no BB vs open de BTN" →
  intercalar BB vs open de UTG (onde foldar mais é correto). Quem responde
  "defende" em tudo aprendeu o botão, não o conceito.

- **Repetição espaçada (SRS)** — spots dominados entram na fila de revisão com
  intervalos crescentes (1d, 3d, 7d, 14d, 30d…). Falha na revisão encurta o
  intervalo; falhas repetidas reabrem o leak. O eixo de domínio/decaimento SRS
  **já existe** no sistema de treino live; o delta é o segundo gatilho de
  reabertura vir do EV real (§1).

- **Corrective feedback (Bloom)** — ao falhar, NUNCA repetir a mesma
  intervenção. Escada concreta na §8.

- **Calibração de dificuldade (Ericsson)** — drills no limite da habilidade.
  O ranking de instrutividade do corpus (§6) alimenta isso: gap de EV grande
  = spot didático (início); gap pequeno = spot avançado.

- **Reflexão (Kolb)** — micro-pergunta antes da resposta ("por que você acha
  que pagou aqui?"). Barato, alto impacto.

- **Não gatear em velocidade.** Pressão de tempo treina snap judgment e
  penaliza exatamente o deliberar que queremos construir (o erro do Kumon
  mecânico). Sem cronômetro no exame de mastery.

- **Não herdar:** streak agressivo estilo Duolingo (reforça jogo compulsivo em
  gente apostando banca real).

- **Anti results-orientation:** ao servir mão real do corpus, **nunca mostrar
  o desfecho real da mão** como feedback. Feedback = estratégia/EV/frequências.
  Mostrar "e ele ganhou o pote" treina o vício nº 1 do público.

---

## 5. O núcleo estatístico (correções da v2)

### Métrica primária: taxa de erro, não média de EV

EV perdido por decisão é **zero-inflado e de cauda pesada** (maioria das
decisões ~0; poucas com perda grande). Média ± IC gaussiano com n=20 é frágil
e vulnerável a outliers (incl. nós degenerados residuais). Decisões:

1. **Métrica primária de validação = taxa de erro da família**: proporção de
   decisões reais com `ev_loss_bb > limiar` (limiar herdado do veredito de 3
   níveis já existente). Binomial → intervalo de Wilson, bem-comportado com
   sample pequeno, e alinhado ao veredito que o usuário já vê.
2. **EV médio da família** continua exibido (magnitude importa), mas com
   `ev_loss_bb` **winsorizado/capado** na query (defesa contra outlier e nó
   podre) e com banda de confiança por bootstrap quando exibida.

### "Comprovado no jogo" (o selo)

Todas as condições, medidas no trilho lento, na granularidade de **família**:

1. **Sample suficiente:** nº de decisões reais na família ≥ `min_decisions`
   (por família; famílias mais raras exigem mais tempo de coleta).
2. **Taxa de erro dentro da tolerância:** caiu para a faixa-alvo da família.
3. **Estabilidade:** intervalo de Wilson apertado o bastante.
4. **Excede o ruído — com baseline encolhido (correção winner's curse):** o
   Top-3 é selecionado por EV extremo, logo o baseline diagnóstico é inflado
   por construção — parte da "melhora" seria regressão à média mesmo se nada
   mudasse. Antes de comparar: **encolher o baseline** via empirical Bayes
   (shrinkage para a média populacional daquela família, ponderada pelo n do
   usuário). A melhora precisa exceder o IC **contra o baseline encolhido**.
5. **Cobertura explícita:** a validação só enxerga decisões com `ev_loss_bb`
   presente. No banco atual: **preflop 84%, flop 41%, turn 55%, river 56%**.
   O produto mostra a cobertura da família ("medido em X% das suas decisões
   deste tipo") — esconder isso é a desonestidade que o protocolo existe para
   evitar. Famílias com cobertura baixa demais não validam (ficam "dominado no
   treino" com aviso honesto).

### UX da espera honesta: barra de COLETA, não de resultado

Com gate honesto, um usuário de 5 torneios/mês veria "validando…" por semanas
— parece morto. Solução: **o progresso exibido é o de coleta de sample**
("validação: 14/24 decisões reais coletadas"), que avança toda semana, não
promete melhora, e educa sobre variância. A banda de confiança visível na
curva segue o mesmo princípio: mostrar incerteza constrói confiança num
público que entende variância.

### Reabertura (SRS + jogo real)

Um leak dominado/comprovado reabre se, nos uploads recentes (janela móvel),
a taxa de erro da família volta acima da tolerância com sample mínimo — OU se
falha revisões SRS repetidas no drill. Frequência de re-checagem cresce com o
tempo dominado (intervalos SRS).

---

## 6. Corpus de situações reais (a vantagem estrutural)

Drills gerados a partir de **mãos reais de outros usuários** — RegLife e afins
não têm corpus de mãos reais parseadas E avaliadas com contexto MTT. É a
resposta ao cold-start e ao sample infinito do trilho rápido.

**Pipeline:**
1. Minerar `decisions` cross-usuário por família de spot.
2. **Gate de cobertura:** só servir spot que o motor corrige com autoridade
   (princípio que o Leak Trainer já aplica: nunca servir spot sem solução).
   Postflop: só nós pré-solvados validados (padrão do
   `seed_leaktrainer_postflop.py`, exploitability < 3%).
3. **Anonimizar:** nomes de jogadores, IDs de torneio, qualquer identificador.
4. **Ranquear por instrutividade:** gap de EV entre a melhor e a segunda ação.
   Gap grande = spot claro (didático, início); gap pequeno = spot de fronteira
   (avançado, calibração de Ericsson).
5. Servir via Leak Trainer (executor existente), gabarito SEMPRE via
   StrategyProvider (fonte única — regra de projeto).

**Autoria manual:** o Hand Builder (existente, position-first + bb-native) vira
ferramenta de autoria de spots específicos para o sistema e para coaches.

**Cold start:** usuário novo (≤3 torneios no free tier) treina nos spots do
corpus da família diagnosticada com o pouco sample que tem + enquadramento
honesto: "seu plano afina conforme você sobe mais torneios".

---

## 7. Exame de mastery ("dominado no treino" — critérios)

"80% de 20 perguntas" é gameável por memorização. O exame por família exige:

1. **Cobertura estratificada da range** — questões sorteadas por estrato:
   núcleo (resposta clara), fronteira (mãos mistas — os tiers existentes
   `CORRECT_FREQ ≥ 0.30` / `MIN_FREQ ≥ 0.10` já tratam co-ótimas) e lixo claro.
   Dominar = acertar ATRAVÉS da range, não a mesma mão 20 vezes.
2. **Variação de contexto** — stacks dentro do bucket, agressores variados.
   Ouro didático: **pares que flipam** (mesma mão, stack/posição diferente,
   ação correta muda).
3. **Discriminação (~20% das questões)** — famílias vizinhas onde a regra NÃO
   se aplica, com acerto mínimo próprio. É o que separa conceito de botão.
4. **Estabilidade** — janela móvel (ex.: ≥85% nos últimos 30 reps, todos os
   estratos cobertos) e **zero erro grave** (resposta major_leak) no núcleo.
5. **Sem cronômetro** (§4).
6. **Composição do exame (padrão inicial, calibrar com dados):** ~20 questões
   = 8 núcleo + 6 fronteira/mistas + 4 discriminação + 2 revisão de leaks
   anteriores.

---

## 8. Escada de destravamento (quando o usuário empaca)

Gate duro sem escada = parede = churn. Ao falhar o exame repetidamente, a
intervenção MUDA (Bloom), nesta ordem:

- **(a) Troca a explicação** — aula da Academia da família (LessonKit existe;
  ligar aula↔família), ou explicação alternativa via coach IA.
- **(b) Decompõe a família** em sub-spot mais simples (ex.: "BB vs open" →
  primeiro só "vs min-raise 40bb+"), com mini-exame próprio.
- **(c) Checa pré-requisito** — falha em defesa vs 3-bet pode ser não conhecer
  ranges de open → roteia para a família pré-requisito antes.
- **(d) Estacionar** — última instância: oferece estacionar este leak e ativar
  o próximo da fila, registrando o motivo. Melhor um desvio explícito que um
  usuário parado. Leak estacionado volta à fila com prioridade.

Válvula permanente: o modo "explorar fundamentos" (já existe no seletor)
continua disponível, rotulado como prática livre, fora da progressão.

---

## 9. ICM: flag & exclude (dependência resolvida por decisão)

Com a auditoria feita (grading = chipEV puro) e a captura de ranges ICM
bloqueada (GW morto), a política é:

- Toda decisão/família carrega a flag de zona ICM (`icm_pressure`/`icm_tax_pct`
  já são produzidos e persistidos por decisão).
- **Spots em zona ICM ficam FORA da validação e do diagnóstico de leak do
  protocolo** (não entram no Top-3, não validam família). Exibidos com selo
  honesto "≈ análise chipEV — zona ICM não validável".
- Quando existir motor ICM real, a flag vira dimensão da chave e a exclusão
  cai. A entidade já prevê (`icm_context` nullable).

Racional: um diagnóstico errado lido uma vez é um erro; um diagnóstico errado
que vira plano de 30 dias com cobrança diária é um desastre de retenção.
Excluir é honesto; esperar é adiar o loop indefinidamente.

---

## 10. As cinco etapas (revisadas)

### Etapa 1 — Diagnóstico
Perfil (objetivo, banca, tempo/semana, ABI) + nível técnico **dos torneios
reais**. Top de leaks por EV perdido **ponderado por confiança** E com
**baseline encolhido** (§5.4) — a seleção já usa o shrinkage, não só a
validação. Zona ICM excluída (§9). Cold-start via corpus (§6).

### Etapa 2 — PIP
Top 3 visível, fila oculta (+3), **um leak ativo por vez** (§1). Grade de ABI
por banca × skill. Meta de volume mensal pelo tempo disponível. Definição de
"dominado no treino" (§7) e "comprovado no jogo" (§5) por família.

### Etapa 3 — ETJ (Estuda, Treina, Joga)
- **Estuda** — a v1 superestimou o gap: Academia com aulas (LessonKit), plano
  de estudo interno e a trava anti-alucinação (`_sanitize_study_resources`,
  blocklist) **já existem**. Delta: ligar aula↔família do PIP. LLM/coach como
  fallback para famílias sem aula.
- **Treina** — sessão composta 60/25/15 (§4), corpus (§6), exame (§7).
- **Joga** — sobe torneios; micro-reflexão de Kolb; barra de coleta (§5).

### Etapa 4 — Acompanhamento (IA com freio ético)
Cobra adesão aos compromissos que o usuário assinou (volume, cadência de
drills); reforça quando cumpre. **NUNCA** cobra volume de jogo em downswing ou
queda técnica: se os uploads mostram drift de qualidade vs baseline (o alerta
de drift já existe no dashboard — reusar o sinal), a IA sugere **pausar e
revisar**. Empurrar volume através de maré ruim, sobre banca real, é máquina
de tilt — dano ao usuário e passivo reputacional/legal.

### Etapa 5 — Progressão
A curva por família: taxa de erro (primária) + EV médio winsorizado, com banda
de confiança visível e cobertura explícita. Estados da §1. A reabertura
comunicada como prova de honestidade do sistema.

---

## 11. Entidades de dados (esboço — refinar no schema real)

Convenção do `schema.py` (multi-backend SQLite/PG, migrações abort-proof).

- **`spot_family`** — derivável de spot canônico; materializar como colunas em
  `decisions` (Fase 0): `spot_family_key` (street × cenário × posição × stack
  bucket UNIFICADO) e opcionalmente `spot_hash` (canônico fino, já computável).
- **`user_plan`** (PIP) — `id`, `user_id`, `created_at`, `status`, `abi_grade`,
  `monthly_volume_goal`, `time_per_week_h`, `objective`.
- **`plan_spots`** — `id`, `user_plan_id`, `family_key`, `priority_rank`,
  `state` (queued | active | drill_mastered | validated | parked | reopened),
  `baseline_error_rate_shrunk`, `tolerance`, `min_decisions`,
  `coverage_pct`, `srs_interval_days`, `last_checked_at`, `parked_reason`.
- **`mastery_exams`** — `id`, `user_id`, `family_key`, `taken_at`, `passed`,
  `strata_breakdown` (json: núcleo/fronteira/discriminação), `reps_window_acc`.
- **`drill_sessions`** — **já existe**; adicionar `family_key`,
  `difficulty_level`, `stratum` se faltarem.
- **`corpus_spots`** — `id`, `family_key`, `spot_hash`, `source` (anon),
  `instructiveness` (gap de EV), `coverage_ok`, `times_served`, `p_correct`
  (dificuldade empírica).
- **`progression_snapshots`** — materialização da query sobre `decisions` por
  família × janela: `user_id`, `family_key`, `window_start`, `window_end`,
  `n_decisions`, `n_covered`, `error_rate`, `wilson_low`, `wilson_high`,
  `ev_mean_winsorized`.
- **`commitments`** / **`adherence_log`** — como na v1 (+ `quality_drift_flag`).

> O coração de `progression_snapshots` é uma **query** (com winsorização e
> escopo por tournament_id); materializar é performance, não lógica.

---

## 12. Sequência de build (revisada — cada passo entrega valor sozinho)

0. **Higiene e unificação (novo, barato, evita refazer tudo depois).**
   Concluir limpeza dos nós degenerados residuais em prod + winsorização na
   query; **eleger e unificar o esquema de stack bucket**; definir política de
   cobertura (o que entra no universo de medição); materializar
   `spot_family_key` (e `spot_hash`) em `decisions`.

   > **EM EXECUÇÃO desde 2026-07-30.** Entregue: `backend/leaklab/familia_spot.py`
   > (fonte única da chave de família, do bucket de agregação e da winsorização)
   > + `tests/test_familia_spot.py`, 19 testes, 6 guardas verificados quebrando.
   >
   > **Correção que a medição impôs a este item.** "Eleger e unificar UM esquema
   > de stack bucket" está errado como literalmente escrito: os dois esquemas não
   > são versões rivais da mesma coisa. `_DEFAULT_BUCKETS`
   > (10/14/17/20/30/40/50/75/100bb) é **chave de lookup** — cada label é uma
   > profundidade para a qual EXISTE solução no arquivo de ranges; colapsá-la nas
   > faixas grossas faria um stack de 19bb procurar a solução de 10bb.
   > `STACK_BUCKETS` (0-10/10-20/20-35/35-60/60+) é **partição de agregação**.
   > O que se elege é qual serve a **chave de família**, e a resposta é o grosso.
   > Medido em produção (9216 decisões): grosso → 910 famílias, mediana 3,
   > 118 (13,0%) com ≥20 decisões; fino → 1391 famílias, mediana 2, 90 (6,5%).
   > O fino cortaria as famílias validáveis em 24%. Existe ainda um **terceiro**
   > esquema, em `scripts/gto_validation/spot_extractor.py`, que a spec não
   > listava (lista de snap `[10,13,15,17,20,25,30,40,50,75,100]`, com 13/15/25
   > que o de lookup não tem) — divergência a fechar.
   >
   > **Descoberta que esta spec não previu, e pesa mais que o bucket.** A
   > validação é POR USUÁRIO, e nesse denominador a granularidade do **cenário**
   > domina. Famílias com ≥20 decisões por usuário, medido em produção:
   >
   > | cenário | user 3 | user 43 | user 28 | user 26 |
   > |---|---|---|---|---|
   > | por posição do vilão | 48 | 28 | 1 | 0 |
   > | largo (`rfi`/`vs_rfi`/`vs_3bet`) | 59 | 47 | **11** | **5** |
   >
   > Usuários com ao menos uma família validável: 3 de 8 no cenário fino, 4 de 8
   > no largo. Por isso a família usa cenário largo e a posição do vilão fica
   > fora dela (vive no spot canônico, onde a amostra do drill aguenta).
   >
   > **Correção do cenário postflop (2026-07-30, depois da materialização).** A
   > primeira versão fazia o cenário postflop ser o próprio street, e isso estava
   > errado duas vezes: a chave saía `flop|flop|BTN|...` (o street já é o primeiro
   > campo, então o cenário não carregava informação), e — o que importa — a
   > família juntava "eu apostei" com "eu paguei uma aposta", ou seja, a série de
   > EV virava média de DUAS habilidades. A §3 desta spec já dava "c-bet em SRP
   > como agressor" como exemplo de família: o papel na mão É a distinção.
   > Corrigido para `agressor`/`defendendo` por `facing_bet`. Custo medido em
   > produção: os dois usuários com mais volume perdem 12% das famílias validáveis
   > (59→52 e 47→41); os três com pouco volume não perdem nada (9, 5 e 0).
   >
   > **Limite honesto a comunicar, não esconder:** quem tem 258 decisões tem ZERO
   > família validável. O selo "comprovado no jogo" é inalcançável para a maior
   > parte da base hoje, e a superfície precisa dizer "ainda não dá para afirmar"
   > em vez de renderizar vazio ou zero.
1. **Espinha de medição do trilho lento.** Query/snapshot de taxa de erro por
   família × janela, Wilson, shrinkage de baseline, flag ICM excluindo,
   cobertura explícita. Curva com banda. Usa só dados existentes. **Se isto
   não funcionar, nada do resto importa.**
2. **PIP mínimo.** Top 3 com baseline encolhido, 1 ativo, estados da §1 (sem
   exame ainda: gate provisório = critério atual do Leak Trainer).
3. **Corpus + exame de mastery.** Pipeline do corpus no Leak Trainer; exame
   estratificado com discriminação; estados `drill_mastered` reais.
4. **Composição de sessão + SRS + reabertura.** 60/25/15; revisões
   intercaladas; reabertura por falha SRS E por regressão de EV real (depende
   de 1 sólido).
5. **Acompanhamento (IA).** `commitments`/`adherence_log`, cobrança com
   guardrails (drift → pausa).
6. **Conteúdo do Estuda.** Ligar aulas existentes às famílias; LLM fallback;
   parceria de conteúdo por último.

**Regra transversal:** tudo é **delta sobre o sistema live** (jornada
Treinar→Jogar→Validar, eixo de domínio/SRS, missões diárias, Leak Trainer,
StrategyProvider como fonte única de gabarito, alerta de drift, Hand Builder,
pipeline de seed postflop). Construir sistema paralelo = dois eixos de
progresso discordando na cara do usuário.

---

## 13. Riscos e antipadrões (consultar antes de cada decisão)

- **Escalar erro do motor.** Zona ICM excluída (§9); cobertura explícita
  (§5.5); nós degenerados limpos/capados (Fase 0). Sem isso o loop treina
  leaks falsos com cobrança diária.
- **Creditar variância.** Shrinkage + Wilson + exceder IC (§5). Sem shrinkage,
  o Top-3 recompensa regressão à média por construção.
- **Domínio que não transfere.** Prática blocada pura; antídoto: interleaving
  60/25/15 + discriminação no exame + reabertura pelo jogo real.
- **Parede de mastery.** Gate duro sem escada de destravamento (§8) = churn.
- **Máquina de tilt.** IA cobrando volume em downswing; antídoto: guardrail de
  drift (Etapa 4).
- **Results-orientation.** Mostrar desfecho real da mão no drill; antídoto:
  feedback só de estratégia/EV (§4).
- **Alucinação de conteúdo.** Já mitigado (`_sanitize_study_resources`);
  manter a regra: descrever tipo de material, nunca fabricar títulos/URLs.
- **Biblioteca infinita.** Fila oculta, 1 ativo, 3 visíveis.
- **Sistema paralelo.** O maior risco novo: ignorar o que está live e duplicar
  gamificação. Regra transversal da §12.
- **Trabalho confortável.** Otimizar solver é gostoso e mensurável; o chassi
  de retenção é o que move aquisição/retenção. Este loop é o chassi.

---

*Fim da v2. Dependências críticas restantes: Fase 0 (higiene + unificação de
buckets + materialização da família). ICM deixou de ser bloqueante por decisão
(flag & exclude). A validação em família — não em spot canônico — é o que
torna a honestidade atingível no volume real dos usuários.*
