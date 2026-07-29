# GrindLab — Cobrança e Próximo Passo
### Especificação do sistema de acionamento do aluno (push, não pull)

> **Status:** spec consolidada · v1 · 2026-07-29
> Origem: pedido do usuário — *"o aluno precisa ser triggado do próximo passo, e não
> ficar apenas sob sua vontade estudar o que quer, e continuar perdendo dinheiro nas
> mesas"*. Baseada em medição do código em 2026-07-29 (commit `bc83c1b`), não em
> suposição. Complementa [protocolo-progressao.md](protocolo-progressao.md): aquela
> spec constrói o MOTOR pedagógico; esta constrói a IGNIÇÃO.
> Documento de trabalho para execução no Claude Code.

---

## 0. Diagnóstico: o sistema é 100% pull

O motor pedagógico está pronto e é bom — missão por EV ponderado, gate de domínio com
5 critérios, trilho lento (selo só com melhora provada no jogo real), reabertura por
regressão, SRS de drills e de ranges. **Nada disso age quando o aluno não vem.**

Medido no código (2026-07-29):

| Peça | Estado | O furo medido |
|---|---|---|
| Missão / gate / reabertura | Prontos | Só existem DENTRO de `/leak-trainer`. `Index.tsx` não menciona a missão uma única vez (`grep leak-trainer\|missão src/pages/Index.tsx` → 0 resultados) |
| Relatório de evolução | Gera sozinho por cadência (`_evolution_report_worker_loop` no serviço `web`) | Gera **em silêncio**: o loop só faz `log.info`. Nem sino, nem e-mail. O aluno só descobre se abrir `/evolucao` |
| E-mail digest | Construído, SMTP Brevo live | Só dispara pelo endpoint de **admin** (`admin_send_digest`, app.py:7799). Nunca sozinho |
| Sino de notificações | Existe, com contador e marcação de lida | Só 3 produtores: `coach_annotation`, `coach_trial_ending`, `achievement`. **Zero sobre treino** |
| SRS (`due_at` em `drill_sessions` e `range_card_srs`) | Agenda revisões | Revisão vencida não aciona nada. O "Volta em 3 dias" é promessa que ninguém cobra |
| Fim da análise de upload | Momento de maior dor (o aluno acabou de ver o prejuízo em bb) | Nenhuma prescrição. A análise termina nela mesma |

Há **cinco portas de entrada** de treino (missão do protocolo, Ghost Table, desafio
diário, academia, memorizar ranges) e nenhuma manda. Aluno com vontade escolhe
qualquer uma; aluno sem vontade não escolhe nenhuma — e as duas coisas são
invisíveis para o sistema.

---

## 1. Princípios de desenho (travados)

1. **Um único próximo passo por aluno, decidido no servidor, empurrado em toda
   superfície.** Não "opções de treino": uma prescrição. O aluno pode desobedecer,
   mas desobedece algo explícito, com o custo em bb na frente.

2. **Cobrança por EVENTO, nunca por calendário.** Regra já aprendida no relatório de
   evolução ("relatório por calendário treina o jogador a ignorar relatório").
   Notificação sem fato novo gasta a credibilidade de todas as seguintes — é a mesma
   régua do "amostra de 2 mãos não vira sugestão".

3. **Consequência honesta, nunca punição fake.** A punição real (perder dinheiro na
   mesa) já existe e é do mundo; o papel do sistema é tornar a conexão visível. O
   trilho lento já sabe dizer "você parou de treinar e voltou a errar" — falta só
   distribuí-lo.

4. **A precedência é UMA função pura** (`decidir_proximo_passo`), testável sem banco
   e sem relógio, no molde de `decidir_cadencia_relatorio`. Superfícies divergem
   quando cada uma calcula a sua verdade (lição do StrategyProvider e do veredito
   de 3 níveis).

---

## 2. Peça 1 — `GET /player/proximo-passo` (fonte única)

### 2.1 Contrato

```
GET /player/proximo-passo
→ {
    "passo": {
      "tipo": "leak_reaberto" | "revisao_vencida" | "missao" | "carta_nova" | "desafio_diario" | null,
      "titulo": str,            // "Abertura (RFI) de UTG · 50bb"
      "porque": str,            // "Você perdeu 14,4bb aqui, em 21 mãos reais"
      "custo_min": int,         // estimativa honesta: 4, 8, 13
      "cta_url": str,           // deep link: /leak-trainer?foco=...
      "ev_loss_bb": float|null,
      "n_maos": int|null
    },
    "fila": [ ...próximos 2, mesmo shape... ],   // o que vem depois, para contexto
    "meta_semanal": { "prometidas": int, "feitas": int } | null   // Fase 3
  }
```

`passo: null` é resposta válida (aluno em dia, sem revisão vencida, sem missão
aberta) e a UI mostra estado de descanso, nunca inventa urgência.

### 2.2 Precedência (função pura `decidir_proximo_passo`)

Entrada: dicts já carregados (nada de I/O dentro). Ordem:

1. **Leak REABERTO** (`training_proof.reopened_at` recente sem sessão posterior).
   O jogo real desmentiu o treino; nada é mais urgente.
2. **Revisão SRS vencida** — a mais atrasada primeiro, entre `drill_sessions.next_drill_at`
   e `range_card_srs.due_at` (unificadas por data, não por tipo).
3. **Missão em curso** do protocolo (o gate diz exatamente o que falta).
4. **Carta nova do alvo** (sugestão de memorização por leak real, já implementada)
   ou **desafio diário** não feito — o que tiver maior EV associado.
5. `null`.

Regras:
- Empate dentro do mesmo nível: maior `ev_loss_bb` ponderado por confiança (mesma
  régua do PIP — amostra pequena nunca lidera).
- A função NÃO consulta relógio: recebe `agora` como parâmetro (testabilidade, e é
  o que permitiu falsificar `decidir_cadencia`).

### 2.3 Consumidores obrigatórios

Dashboard (card líder), sino, e-mails, e a própria intro do `/leak-trainer`. Todos
pelo MESMO endpoint. Proibido recalcular precedência no cliente.

---

## 3. Peça 2 — O contrato pós-upload (gatilho mais quente)

Quando `/analyze` termina E o diagnóstico mudou (qualquer um):
- leak novo entrou no topo do currículo;
- leak existente REABRIU;
- missão recalculada apontou outra categoria;

então:
1. A resposta do upload (payload que o front já recebe) ganha o bloco
   `proximo_passo` (mesmo shape da Peça 1) — a tela de resultado da análise mostra
   a prescrição ao lado do prejuízo: *"Isto te custou 14bb em 21 mãos. Sessão de
   12 spots, uns 4 minutos."* Um clique → sessão.
2. Notificação no sino (`type: 'treino_prescrito'`, payload com o passo, link para
   o CTA).

**Por quê aqui:** é o único momento em que a dor e o remédio estão na mesma tela.
Custo baixo: o cálculo do currículo já roda no fim da análise.

Gate anti-ruído: só notifica se o diagnóstico MUDOU. Upload que não muda nada não
gera notificação (evento, não calendário).

---

## 4. Peça 3 — Dashboard lidera com a prescrição

Hoje o aluno loga e vê cards de diagnóstico. Diagnóstico sem próxima ação é extrato
bancário: informa e desmoraliza.

- O **primeiro card** do dashboard vira o próximo passo (consome a Peça 1): título,
  porquê em bb, custo em minutos, um botão.
- Estados: passo presente / em dia (mensagem de descanso + streak) / usuário novo
  sem upload (o CTA é subir torneio, não treinar).
- **Regra do projeto:** alteração no dashboard exige replanejar a posição de TODOS
  os cards antes de editar (memória `feedback_dashboard_reposition_before_change`).
  O plano de grid é parte da entrega da Fase 1, não um patch.
- Card segue o conceito do masonry de 2 colunas (`lg:col-span-6` + `useMasonryRows`).

---

## 5. Peça 4 — E-mails por evento

### 5.1 Infra existente (não construir de novo)

- SMTP Brevo live no CX23; `send_transactional_email` pronto.
- Opt-out LGPD e unsubscribe tokens prontos (`email_digest.py`).
- Corpo de e-mail só PT (regra existente do projeto).
- O modelo de régua certo já foi escrito e TESTADO: `decidir_cadencia_relatorio`
  (gatilhos por força, teto vence tudo, função pura). Replicar o desenho, não
  inventar outro.

### 5.2 Gatilhos (em ordem de força)

| Evento | Quando dispara | Conteúdo |
|---|---|---|
| **Leak reaberto** | No dia do evento | "Seus últimos torneios mostraram o erro de volta em X. O domínio foi zerado; a sessão de correção te espera." |
| **Relatório de evolução gerado** | No dia (hoje é gerado e ninguém fica sabendo — o desperdício mais óbvio) | Resumo do veredito + link. Reusa `build_digest_html`/layout |
| **Revisão SRS vencida há 48h+** | Uma vez por vencimento, nunca diária | "3 revisões te esperam (2 min). O reencontro no tempo certo é o que fixa." |
| **Inatividade com missão aberta** | 7 dias sem treinar E missão em curso | "Seu leak de vs_RFI segue custando nos seus uploads; a sessão continua te esperando." |

### 5.3 Regras duras

- **Teto: 1 e-mail de cobrança por semana**, o de maior força vence (mesma semântica
  do teto do relatório). Registrar envio em tabela própria
  (`engagement_emails`: user_id, tipo, enviado_em) — **no bloco isolado por
  SAVEPOINT do PG**, junto de `coach_commissions` (a lição de `range_card_srs`:
  try/except no meio da transação NÃO é abort-proof; a catraca
  `test_pg_migration_isolation.py` acusa se nascer no lugar errado).
- Decisão de enviar = função pura `decidir_email_cobranca(eventos, ultimo_envio,
  agora)`, testada nos dois sentidos (dispara quando deve, cala quando deve).
- Roda no worker que já está de pé (`web`, junto do
  `_evolution_report_worker_loop`) — **nunca em cron** (cron pendente já falhou
  duas vezes nesta operação; log de cron não vai em `/var/log`).
- Respeita opt-out; link de unsubscribe em todo e-mail.

---

## 6. Peça 5 — Meta declarada (compromisso do aluno)

- Uma pergunta, uma vez (onboarding ou primeiro acesso ao trainer):
  *"Quantas sessões por semana cabem na sua rotina?"* → 2 / 3 / 5.
- Coluna `users.weekly_training_goal` (**bloco SAVEPOINT do PG**).
- A cobrança passa a ser contra a meta DELE: *"Você prometeu 3, fez 0; seu erro no
  BB vs open segue nos seus uploads."* Não é o app cobrando, é o espelho.
- Aparece no card do dashboard (`meta_semanal` no payload da Peça 1) e no e-mail de
  inatividade.
- Meta é ajustável a qualquer momento; ajustar não apaga histórico.

---

## 7. Peça 6 — Distribuir o veredito que já existe

Reabertura e selo (`comprovado_no_jogo`) hoje só aparecem dentro do trainer.

- Relatório de evolução passa a incluir a seção "o que você provou / o que reabriu"
  (dados já existem em `training_proof`).
- Reabertura → notificação no sino + e-mail (Peça 4, gatilho 1).
- Selo comprovado → notificação de celebração (única exceção positiva: conquista
  REAL, medida no jogo — nunca inflação de badge).

---

## 8. Anti-requisitos (o que NÃO fazer)

1. **Não bloquear upload/análise** como alavanca de cobrança. Aluno pagante travado
   do que pagou cancela, não estuda.
2. **Não punir com perda** (XP negativo, streak quebrado com alarde). Duolingo cobra
   com presença, não com castigo.
3. **Não notificar sem fato novo.** Sem exceções. Cada notificação vazia barateia
   as cheias.
4. **Não criar um segundo agendador.** A precedência mora numa função pura; workers
   só dão o relógio.
5. **Não pedir a decisão ao LLM.** Prescrição é fato sobre os torneios do aluno
   (mesma regra do `treino_sugerido` do plano de estudos: fato em prompt volta
   alucinado).
6. **Não usar cron novo.** Worker no serviço que já está de pé.

---

## 9. Métricas de sucesso (deriváveis do banco hoje)

1. **% de sessões iniciadas por trigger** vs espontâneas (marcar origem na sessão:
   `?origem=dashboard|sino|email|pos_upload|espontanea`).
2. **Tempo entre reabertura e primeira sessão de correção** (hoje: não medido;
   esperado cair de "nunca/semanas" para dias).
3. **Funil de missão**: % de missões criadas que chegam a `dominado_no_treino`
   (hoje o funil não é medido fora do trainer).
4. Taxa de opt-out dos e-mails de cobrança (sobe = régua errada, rever teto).

---

## 10. Fases de entrega

### Fase 1 — Ignição · **ENTREGUE 2026-07-29** (commit `c63047a`)
- [x] `decidir_proximo_passo` pura + 12 testes; sabotada de propósito (missão na
      frente de reaberto), 2 testes acusam
- [x] `GET /player/proximo-passo`
- [x] Faixa líder no dashboard (`ProximoPassoBanner`, irmã do alerta de drift —
      plano de grid: nenhum card do masonry mudou; a ação ganhou a primeira dobra)
- [x] Bloco `proximo_passo` na resposta do `/analyze` (sempre) + notificação
      `treino_prescrito` (só quando o diagnóstico mudou)
- [x] Sino: `leak_reaberto` (no próprio ponto da reabertura), `relatorio_gerado`
      (no worker que antes só logava)
- [x] `progression_attempts.origem` (lista SAVEPOINT) + `?origem=` lido no trainer
      e enviado no grade; deep link `?foco=` cai direto no exercício prescrito
- **Verificado:** reabertura FORJADA em banco descartável apareceu nas 4 superfícies
  (endpoint, dashboard, sino, upload). **O forjamento pegou um bug real antes da
  entrega:** o loader lia reabertura via `get_training_proof`, que exige torneio
  pós-baseline — e a reabertura move o baseline, então o leak recém-reaberto era
  invisível até o upload seguinte. Corrigido com `listar_reaberturas` (tabela crua)
  e travado em `test_reabertura_recem_criada_e_visivel_no_banco_real`.

### Fase 2 — Cobrança por e-mail · **ENTREGUE 2026-07-29** (`ENGAGEMENT_EMAIL_ENABLED` OFF)
- [x] Tabela `engagement_emails` na lista SAVEPOINT (a catraca conferiu)
- [x] `decidir_email_cobranca` pura + 15 testes nos DOIS sentidos; sabotada (teto
      removido + interruptor ligado por padrão), 4 testes acusam
- [x] 4 gatilhos do §5.2 em `_cobranca_email_worker_loop`, no `solver-consumer`
- [x] Corpo só PT, sem travessão, com descadastro em todos e `origem=email` no CTA
- **Verificado:** ensaio do percurso completo com SMTP interceptado — relatório forjado
  virou e-mail (3502 bytes, assunto certo) e a segunda varredura na mesma semana calou.
- **Interruptor:** `ENGAGEMENT_EMAIL_ENABLED` nasce OFF e o worker sobe mesmo assim
  (ligar a flag não exige lembrar de um restart). Subir código é reversível; e-mail
  enviado não é.

### Fase 3 — Compromisso · **ENTREGUE 2026-07-29**
- [x] `users.weekly_training_goal` na lista SAVEPOINT
- [x] Pergunta única na intro do trainer (`MetaSemanalPrompt`), com saída "Depois"
- [x] `meta_semanal` no payload + selo na faixa do dashboard + frase no e-mail de
      inatividade ("você se comprometeu a treinar 3 dias por semana; esta semana foram 1")
- [x] `POST /player/meta-semanal`, aceitando só 2/3/5
- **DESVIO da spec, consciente:** a spec pedia "sessões por semana". `progression_attempts`
  não tem identidade de sessão, só carimbos — perguntar em sessões e contar dias devolveria
  um número que não responde à pergunta feita. **Pergunta e medida são ambas em DIAS**, e dia
  é a unidade melhor: 3 sessões numa terça é pior que 3 dias espalhados, que é a tese do SRS.
- **Verificado:** 10 testes, incluindo o fuso do aluno (quem treina 21h no Brasil está em outro
  dia no UTC, e na virada de domingo em outra SEMANA) e a fronteira de segunda 00:00. Sabotado
  (fuso ignorado), 3 testes acusam. No navegador: pergunta aparece, some ao responder, servidor
  confirma 3/1 e o selo "1 de 3 dias" chega na faixa do dashboard.

---

## 11. Decisões travadas nesta spec

| Decisão | Escolha | Alternativa rejeitada e porquê |
|---|---|---|
| Quem decide o próximo passo | Servidor, função pura única | Cliente/varias superfícies: divergência garantida (lição do veredito) |
| Cadência de cobrança | Por evento, teto semanal | Calendário: treina a ignorar (lição do relatório) |
| Consequência | Visibilidade do trilho lento | Punição de XP/bloqueio: cancela, não estuda |
| Onde rodam os workers | Serviço `web` existente | Cron: já falhou 2× nesta operação |
| Persistência de envio | Tabela própria no bloco SAVEPOINT | try/except "abort-proof": provado não ser (deploy de 29/07) |
| Prescrição | Calculada, nunca via LLM | Fato em prompt volta alucinado |

## 12. Pendências desta spec (decidir na execução)

- Copy exata dos e-mails (seguir régua: verdade em bb na primeira linha, zero
  travessão, termos de poker em inglês).
- Se o desafio diário entra na precedência 4 ou morre absorvido pela missão
  (medir uso real antes de decidir).
- Push notification web/PWA: fora de escopo até e-mail provar a régua.
