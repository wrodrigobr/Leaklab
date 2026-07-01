# Spec — Gamificação de Treino (estilo Duolingo)

Status: **Fase 1 em construção** (2026-06-30). Origem: discussão dono × IA.

## Princípio inegociável: dois eixos

- **ELO / leaks / ROI** = quão bom o jogador **é** (medido das mãos reais). NÃO se ganha treinando.
- **Treino (XP, nível, domínio, streak, missões)** = quanto o jogador **pratica e domina** os drills. Estilo Duolingo, ganho na hora.

Visual e copy SEMPRE separam os dois. O treino nunca finge mover o ELO; ele **prepara** o jogador pra mover o ELO quando joga. Mostrar delta de ELO/leak de uma sessão sintética = métrica de vaidade → proibido.

## Unidade central: a LIÇÃO (início, meio, fim, veredito)

- **Início:** card da lição ("BB defense vs c-bet do BTN · 12 spots · ~4 min · +120 XP").
- **Meio:** N drills (10–15) de UMA categoria (reusa `generate_canonical_spot`), barra de progresso + combo/streak na lição.
- **Fim — VEREDITO:** acerto %, XP ganho, **domínio antes→depois** da categoria, bônus "lição perfeita"/"sem hesitar", "revise seus erros" (link aos spots errados), level-up/conquista. Botões **Próxima lição** + **Finalizar** (→ dashboard).
- A mesma moldura serve sintético (Leak Trainer) e revisão de mãos reais (Ghost por `decision_id`).

## Curso = trilha de habilidades personalizada

- Categorias de leak viram trilha (unidades): fundamentos preflop → BB defense → vs 3-bet → aberturas → postflop…
- Tiers de domínio por habilidade: **Bronze → Prata → Ouro → Diamante**.
- Diferencial vs Duolingo: a trilha é **personalizada pelos leaks REAIS** (`get_leak_categories`) — o que mais sangra sobe ao topo, marcado "recomendado".

## Domínio por habilidade (coração honesto)

Medidor que enche com **acerto sustentado + retenção** (não só volume): EMA de acerto × fator de volume; **decai com o tempo** (reusa SRS do Ghost). "Ouro" = acerta com consistência ao longo do tempo, não "clicou 500×".

## Mecânicas diárias (Fase 2)

- Meta diária de XP ajustável (Casual 50 / Regular 100 / Intenso 200).
- Streak diário 🔥 + streak freeze (1 folga).
- Missões diárias (3 rotativas): "2 lições", "20 corretas", "treine seu leak nº1", "lição 90%+", "mantenha o streak". Semanais maiores.
- Lembretes via sistema de notificações existente.

## Progressão (Fase 1 nível; Fase 3 liga)

- **Nível/Rank de Treino** próprio (separado do ELO). Reusa XP global (`add_xp`) ou XP de treino dedicado.
- Conquistas/badges (motor existente + sino).
- Liga semanal de treino (Fase 3, opcional) por XP de treino — separada do leaderboard de stats reais.

## NÃO copiar do Duolingo

- **Hearts/energia (gate de erro):** contraproducente num coaching pago — queremos MAIS treino. Cortar.
- **Moeda pesada / pay-to-progress:** no máximo soft currency p/ streak-freeze e cosmético.

## Loop honesto completo

Treinar (lições/missões/domínio sobem) → Jogar (mãos reais) → Importar → ELO/leaks mostram se transferiu. O veredito da lição termina conectando: "você dominou X no treino, jogue e importe pra ver no jogo real".

## Reuso × novo

| Reusar | Novo |
|---|---|
| Leak Trainer (gera/grada), Ghost (mãos reais + SRS) | Moldura de LIÇÃO (início/fim/veredito) |
| XP global, conquistas, streak, nível, notificações | DOMÍNIO por categoria (persistido + decaimento) |
| `get_leak_categories` (leaks reais) | Missões diárias/semanais (estado por dia) |
| Leaderboard (stats reais) | Trilha/curso + tiers; liga de treino (opcional) |

## Faseamento

- **Fase 1 — A Lição:** moldura início/fim/veredito + **domínio por categoria** (persistido) + nível de treino + botão Finalizar. Tabela `training_skill_progress`; record no `/grade`; endpoint `/player/training/skills`; verdict enriquecido; lesson-select.
- **Fase 2 — Engajamento diário:** missões diárias/semanais + meta diária + streak/freeze + lembretes.
- **Fase 3 — O curso:** trilha (mapa) + tiers com decaimento + liga de treino + cosmético.
- **A JORNADA (framing, ideia do dono 2026-06-30) — 3 etapas, com GATE de prontidão:**
  1. **Treinar** — sempre disponível; constrói domínio nos leaks.
  2. **Aplicar** — gate ESCALONADO pela maturidade (rampa de onboarding, ideia do dono 2026-06-30: "pro iniciante, liberar só treino de fundamentos; conforme sobe torneios, ser mais exigente baseando nos leaks reais — incentiva o iniciante a jogar mais e subir"). O gargalo do iniciante não é domínio, é FALTA DE DADO → a meta dele é jogar/importar, não grindar drill. `training_readiness` escolhe o estágio pelo nº de torneios:
     - **iniciante** (<5 torneios OU sem leaks medidos): meta = importar os 1ºs torneios (revelar o jogo); progresso = torneios/5; CTA jogar/importar + treinar fundamentos.
     - **em formação** (5–14): top-3 leaks mais custosos no **Ouro** (amostra ainda p/p).
     - **consolidado** (15+): TODOS os leaks reais no **Diamante**.
     Denominador = leaks REAIS medidos (currículo com `n>0`); fundamentos e piloto postflop NÃO entram (não são falha medida). A exigência sobe em 2 dimensões (mais leaks + tier maior) e só mira leak quando a amostra é confiável. É SUGESTÃO, não bloqueio.
  3. **Provar** — após o upload, compara o indicador real antes×depois (a Fase 4 abaixo).
  ENTREGUE 2026-06-30: `training_readiness` (3 estágios) + `/overview.readiness` {stage,tournaments,target,total,done,ready,target_tier,pending} + gate no `Training.tsx` (painel por estágio) + tooltips explicativos em Treinar/Aplicar/Provar. Testes `test_readiness_beginner_stage`/`_developing_top3_gold`/`_consolidated_all_diamond`. Cortes 5/15 e top-3 são tunáveis.
- **Fase 4 — "Provar" ENTREGUE 2026-07-01:** decisões do dono (híbrido snapshot+janela; métrica = **aderência GTO %** da categoria). `training_proof` (baseline congelado quando começa a treinar a categoria, `_ensure_training_baseline` no `record_training_attempt` + lazy no `get_training_proof` p/ legados) × `after` = torneios importados após o baseline; `snapshot` = último torneio. `_category_adherence_filter` mapeia category_key→decisões reais (v1 preflop rfi/vs_rfi/vs_3bet; ignora stack p/ amostra). `/player/training/proof` + card "Provar" no hub (delta em pp, snapshot, aviso de amostra pequena quando after_n<10, disclaimer "comparação não causa"). Passo "Provar" da jornada vira ativo quando há prova. Só mostra categorias com dado NOVO (after_n>0) → exige o loop real. Teste `test_training_proof_before_after`. **Pendências:** postflop (v1 é preflop), e os caveats de "o que PIOROU" (hoje delta já mostra queda em vermelho, mas não há destaque separado).

- **Fase 4 (desenho original) — Loop validado treino→jogo→prova (ideia do dono 2026-06-30):** depois de treinar uma categoria, dar uma **missão de jogar 1 torneio e fazer upload** (CTA na própria tela de treino). A plataforma processa o torneio e **compara os indicadores ANTES × AGORA** da(s) categoria(s) treinada(s), e mostra algo como *"neste torneio você reduziu em X% o leak de defesa de BB. Parabéns!"*. Fecha o loop: treinar → jogar com o foco na cabeça → subir → ver de cara se o indicador real melhorou. **É a forma HONESTA de mostrar "reflexo nos indicadores"** (vem da mão real, não do drill sintético).
  - **Caveats honestos (obrigatórios na copy):** 1 torneio é amostra pequena → variância alta; o dono já reconhece "mas outras coisas entraram". Então: (a) comparar com **confiança/amostra** (não cravar "melhorou" com 2 mãos); (b) mostrar também o que **piorou/entrou de novo** (honestidade, não só o win); (c) idealmente comparar **janelas** (últimos N torneios antes × depois do treino) e não só 1, ou deixar explícito que é "neste torneio" (snapshot, não tendência); (d) atribuição é correlação, não causa — frasear como "seu BB defense neste torneio foi melhor que sua média", não "o treino causou X%". Reusa o motor de leaks/EV por categoria que já existe (`get_leak_categories`/decisions). Depende do eixo de treino (Fases 1-2) pra saber o que o cara treinou.

## Modelo de dados (Fase 1)

`training_skill_progress (user_id, category_key, attempts, correct, mastery_ema, mastery, tier, last_practiced_at, UNIQUE(user_id, category_key))`.
- Mastery: `ema = ema*(1-α) + correct*α` (α≈0.2); `mastery = ema * min(1, attempts/20) * 100`; tier por faixa (Bronze<40 · Prata<70 · Ouro<90 · Diamante≥90). Decaimento por `last_practiced_at` na leitura (Fase 1 simples; SRS pleno na Fase 3).
- Categoria vem de `spot.category` (já presente no Leak Trainer).
