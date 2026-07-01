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
  2. **Aplicar** — DESBLOQUEIA só quando o jogador **DOMINOU TODO o currículo no Diamante** (mastery≥90 em TODOS os pontos de falha, não um leak só). Correção do dono 2026-06-30: "meia dúzia de exercícios num leak e já sugerir torneio é muito pouco; abranger mais spots; só direcionar o torneio quando todos os pontos de falha estiverem no Diamante". A régua vem do backend (`training_readiness`): denominador = `build_curriculum(user)` (leaks reais mapeados + fundamentos/piloto postflop), numerador = quantos desses estão no Diamante. `ready = diamond == total`. Enquanto não fecha, o hub mostra **progresso honesto** (X/Y no Diamante + lista do que falta) em vez do convite. É SUGESTÃO, não bloqueio (o jogador sempre pode jogar/importar).
  3. **Provar** — após o upload, compara o indicador real antes×depois (a Fase 4 abaixo).
  ENTREGUE 2026-06-30: `training_readiness` no backend + `/overview.readiness` + gate no `Training.tsx` (painel de progresso quando bloqueado / CTA comemorativo quando `ready`). Teste `test_readiness_gate_requires_all_diamond`.
- **Fase 4 — Loop validado treino→jogo→prova (ideia do dono 2026-06-30):** depois de treinar uma categoria, dar uma **missão de jogar 1 torneio e fazer upload** (CTA na própria tela de treino). A plataforma processa o torneio e **compara os indicadores ANTES × AGORA** da(s) categoria(s) treinada(s), e mostra algo como *"neste torneio você reduziu em X% o leak de defesa de BB. Parabéns!"*. Fecha o loop: treinar → jogar com o foco na cabeça → subir → ver de cara se o indicador real melhorou. **É a forma HONESTA de mostrar "reflexo nos indicadores"** (vem da mão real, não do drill sintético).
  - **Caveats honestos (obrigatórios na copy):** 1 torneio é amostra pequena → variância alta; o dono já reconhece "mas outras coisas entraram". Então: (a) comparar com **confiança/amostra** (não cravar "melhorou" com 2 mãos); (b) mostrar também o que **piorou/entrou de novo** (honestidade, não só o win); (c) idealmente comparar **janelas** (últimos N torneios antes × depois do treino) e não só 1, ou deixar explícito que é "neste torneio" (snapshot, não tendência); (d) atribuição é correlação, não causa — frasear como "seu BB defense neste torneio foi melhor que sua média", não "o treino causou X%". Reusa o motor de leaks/EV por categoria que já existe (`get_leak_categories`/decisions). Depende do eixo de treino (Fases 1-2) pra saber o que o cara treinou.

## Modelo de dados (Fase 1)

`training_skill_progress (user_id, category_key, attempts, correct, mastery_ema, mastery, tier, last_practiced_at, UNIQUE(user_id, category_key))`.
- Mastery: `ema = ema*(1-α) + correct*α` (α≈0.2); `mastery = ema * min(1, attempts/20) * 100`; tier por faixa (Bronze<40 · Prata<70 · Ouro<90 · Diamante≥90). Decaimento por `last_practiced_at` na leitura (Fase 1 simples; SRS pleno na Fase 3).
- Categoria vem de `spot.category` (já presente no Leak Trainer).
