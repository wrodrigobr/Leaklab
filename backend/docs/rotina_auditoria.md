# Rotina de auditoria, correção e validação

**Objetivo:** que o veredito seja confiável e coerente, no acervo e em torneio novo. Onde há
solver, a resposta é GTO e traz o custo em bb. Onde não há, o produto **diz que não sabe** em vez
de emitir heurística com a linguagem de GTO.

**Princípio de autonomia:** automatizar tudo que tem *oráculo* — uma fonte independente capaz de
dizer "certo" ou "errado" sem opinião. O resto sobe para decisão humana. Não é conservadorismo:
na 1ª rodada de auditoria por agentes, **4 de 6 achados eram falsos positivos**, e dois dos
"consertos" que eles pediam teriam causado dano que o bug não causava.

---

## Camada 1 — Invariantes (autônoma, contínua)

Roda na suíte (a cada commit) e por cron diário contra produção. **Nunca conserta. Só alerta.**

Cada invariante obedece a três regras, nascidas de falhas reais:

1. **Carrega o próprio controle.** A sonda tem que provar que *acharia* o defeito. Um zero sem
   controle não conta — nesta base já houve 6 medições contaminadas num único dia, todas com
   número tranquilizador.
2. **Mede o que a operação promete mexer.** Uma conferência que conta o acervo inteiro e imprime
   "esperado 0" mostrou 347 (os deliberadamente intocados) e quase passou por falha.
3. **Lê o CÓDIGO, não o comentário.** Duas mutações passaram verdes porque o teste casava com o
   comentário que explicava a regra, e não com a regra.

### Catálogo atual

| # | invariante | controle | estado |
|---|---|---|---|
| 1 | matriz `available:false` não serve `hand_freq` | spots cobertos que servem | verde |
| 2 | veredito de erro não contradiz freq ≥60% da ação jogada | erros com matriz | verde |
| 3 | `gto_critical` não sai como não-erro | total de `gto_critical` | verde |
| 4 | erro não tem `best_action` == ação jogada | total de erros | verde |
| 5 | postflop tem pote ≥ 1bb | total de postflop | verde |
| 6 | postflop vs aposta tem equity | postflop vs aposta | verde |
| 7 | score dentro da banda do label, nas 5 portas | passos com label e score | verde |
| 8 | matriz sem carta não serve `%` de grade | spots cobertos que servem | **18/26 vermelho** |
| 9 | `draw_profile` sem backdoor no turn/river | flop com backdoor legítimo | **639/870 vermelho** |
| 10 | `best_action` proporcional ao pote e ao stack | recomendações válidas | a construir |
| 11 | acusação com linguagem de GTO tem custo em bb | acusações com custo | a construir |

### Formato do alerta

```
[INVARIANTE 9] draw_profile com backdoor no turn: 639 de 870 (73%)
  controle: 1.161 no flop (legítimo) — a sonda enxerga
  exemplo:  257047614986  As3s em Qs 8s 9s Ad  ->  "BDSD" (é flush máximo FEITO)
  alcance:  73% do turn do acervo
```

Número, controle, exemplo nomeado e alcance. Sem isso, o alerta vira ruído e se aprende a ignorar.

---

## Camada 2 — Juízes de poker (autônoma na execução, nunca na conclusão)

Semanal, sobre um torneio **ainda não auditado**. Três agentes, ~18 decisões cada: preflop com
matriz, postflop das três ruas, e as acusações de erro.

### Briefing obrigatório

Sem ele, a rodada gasta tokens redescobrindo convenções. Com ele, os graves caíram de 5 para 0 no
juiz de preflop. Deve declarar:

- `matriz.stack_bb` é o stack **efetivo** (`min(hero, vilão)`); vs jam curto coincide com o call.
- `fold_pct` é da **grade**; `hand_freq.fold` é da **mão**. Divergirem é esperado.
- A carta do produto é a **referência**: divergência dela é observação, categoria separada.
- Equity de river é enumerada contra quem continua, não vs mão aleatória.
- `gto_label` (carta) tem precedência sobre `error_score` (heurístico) no veredito.

Amostragem: **só decisões**. `shows`/`mucks` não são jogadas — numa rodada, 12 de 20 linhas de um
agente foram eventos de showdown, e mais da metade daquele agente se perdeu.

### Triagem automática antes de chegar em você

A saída **não vira tarefa direto**. Passa pelos oráculos:

| oráculo | derruba |
|---|---|
| enumeração exata de equity no river (1.081 mãos, 6 ms) | "a equity está errada" |
| listas de abertura da carta | "a matriz serve mão fora do range" |
| ordem das aberturas por posição (monotônica) | "a posição lê a carta errada" |
| `effectiveStackBb` do pipeline | "a profundidade está trocada" |

O que o oráculo derruba morre na triagem. O que ele não cobre chega com o alcance já medido no
acervo. Na 1ª rodada isso teria convertido 6 achados em 2 reais sem você ler os outros 4.

---

## Camada 3 — O que continua exigindo decisão humana

1. **Escrita em dados de produção.** Sempre `--dry-run` antes, e o dry-run tem poder de veto: o
   backfill do score foi de 27 para 404 linhas ao ser inspecionado, e 347 delas rebaixariam
   decisões corretas.
2. **Decisão de política.** Qual fonte manda quando carta e heurístico discordam; onde ficam os
   pisos de severidade. Muda o que o produto **afirma**.
3. **Mudança que altera veredito**, mesmo com testes verdes — sempre precedida da medição de
   impacto (quantos vereditos mudam, em que direção, e quantos usuários trocam de ordem).

### A cicatriz que gerou a regra 3

O alinhamento do score passou em todas as verificações e ainda assim se pintou num canto: o
backfill elevou 57 linhas ao **piso** da banda, e quando a escala por custo chegou, ela não as
recuperava mais — já estavam "dentro". Coerentes e cegas.

**Regra:** valide a mudança de código e verifique no ambiente **antes** de escrever no acervo.
Nunca as duas coisas na mesma entrega.

---

## Ordem de construção

1. Camada 1 como cron diário + as invariantes 8, 9, 10 e 11 (as três primeiras já têm o defeito
   medido e esperando conserto).
2. Procedência do veredito: separar "GTO com custo" de "opinião do motor" na API e na tela. É o
   que transforma "confiável" em verificável — e habilita a invariante 11.
3. Camada 2 como cron semanal com a triagem por oráculo.

## O que a rotina NÃO resolve

Carta errada. Se a célula do solver estiver errada para uma profundidade, todas as camadas
concordam entre si e o produto ensina o erro com confiança total. Só re-captura ou revisão humana
da carta pega isso — um juiz sinalizou um caso assim (fold de `44` a 6,7bb efetivos), e ele está
corretamente fora do escopo de código.
