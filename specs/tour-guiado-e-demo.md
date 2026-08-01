# Tour guiado + tela de demonstração

Status: **spec, sem código.** Aberta em 2026-08-01 a partir de um protótipo enviado pelo usuário
(`Index.tsx` com `GuidedTour`) e da decisão dele: *"eu gosto do tour guiado, podemos ter uma tela
de exemplo com dados fictícios para mostrar o que é cada coisa"*.

---

## 1. O problema que a tela de demonstração resolve

O tour do protótipo dispara 600ms depois do primeiro acesso e percorre indicadores, bankroll,
torneios e leaks. Nesse instante o usuário tem **zero torneios**: os cinco primeiros passos
apontariam para cards vazios.

Isso não é detalhe de implementação, é a restrição que já estava registrada em 2026-07-30: *um
tour que aponta para cards vazios ensina que o produto é vazio*.

**A saída escolhida pelo usuário:** o tour não roda sobre o dashboard do próprio jogador, roda
sobre uma tela de demonstração povoada. Ali cada card tem número, e explicar o que ele significa
passa a fazer sentido.

Isso muda o papel do tour. Ele deixa de ser "conheça a sua tela" (que não existe ainda) e vira
**"veja o que esta ferramenta entrega quando você tiver dados"** — que é exatamente o argumento de
venda que falta a quem acabou de se cadastrar.

---

## 2. Onde a tela vive

Rota própria, `/demo`, **fora** do dashboard do usuário.

Motivos, em ordem de peso:

1. **Não pode ser confundida com o dado do jogador.** Injetar números de exemplo no dashboard real
   cria um estado em que a tela mente sobre de quem é aquele ROI. Rota separada elimina a classe
   inteira de bug.
2. **Acessível sem dados e sem sair de onde está.** Serve o recém-cadastrado, e também quem só
   quer rever depois.
3. **Reusa os componentes reais.** `/demo` renderiza o `DashboardV2` de verdade, com os mesmos
   cards, recebendo dados de demonstração por prop. Sem cópia da vitrine — a regra que este
   projeto aplica desde o Decision Card de exemplo.

A tela carrega selo permanente de demonstração (mesmo padrão do selo `EXEMPLO` do Decision Card),
visível em qualquer scroll, não só no topo.

---

## 3. De onde vêm os números — DECISÃO EM ABERTO

O usuário disse "dados fictícios". Há duas formas, e a diferença é de custo, não de princípio.

**(a) Fabricados à mão.** Escrever um JSON com ROI, ITM, leaks, EV, cobertura GTO, projeção de
carreira etc.

**(b) Derivados de um torneio real, congelados e anonimizados.** Mesma técnica do
`decisao_exemplo.json` entregue hoje: um script roda a pipeline real sobre um torneio do dono do
produto, e o resultado vira fixture versionada.

**Recomendação: (b)**, e o argumento é prático, não moral. O dashboard tem 13 cards com números
**interdependentes**: o leak prioritário tem que ser coerente com o EV perdido, que tem que ser
coerente com a cobertura GTO, que tem que ser coerente com a projeção de carreira. Fabricar um
conjunto coerente à mão é trabalhoso e erra em silêncio — um card contradizendo outro é pior do
que card nenhum, porque ensina errado. Derivar de um torneio real dá coerência de graça, e o
gerador e o endpoint já existem.

O custo é praticamente o mesmo. Se a resposta for (a), a spec segue igual; muda só a origem do
arquivo.

---

## 4. Gatilho — quando o tour aparece

**Nunca automático logo após o cadastro.** Três entradas:

| entrada | onde | para quem |
|---|---|---|
| CTA no modal de boas-vindas | 3º passo do `OnboardingModal`, ao lado de "Importar agora" | recém-cadastrado |
| Botão "Tour guiado" | cabeçalho da `/demo` e do dashboard | qualquer um, a qualquer hora |
| Link no dashboard vazio | `EmptyDashboard`, junto de "Ver exemplo de análise" | quem ainda não subiu nada |

A ideia do botão persistente vem do protótipo e é boa: hoje o onboarding acontece uma vez e nunca
mais. Rever tem que ser barato.

---

## 5. Os passos

O protótipo mira um layout que **não existe mais** (`kpis`, `upload`, `bankroll`, `tournaments`,
`leaks` numa grade de 8+4 colunas). O dashboard vivo é o `DashboardV2`: banner do Próximo Passo,
faixa de KPIs e um bento de 13 cards em masonry de 2 colunas.

Os passos precisam ser remapeados para o que existe, e **curados**: 13 cards não viram 13 passos.

Ordem proposta, que segue a pergunta que o jogador faz, não a ordem do DOM:

1. **Próximo Passo** — "o que eu faço agora". É o que lidera a primeira dobra e é o motor de
   prescrição do produto. Começar por ele evita criar um segundo eixo de "o que fazer".
2. **KPIs** — ROI, ITM, volume. **Tem que dizer o volume mínimo de cada um** (ver §6).
3. **Leak Finder / leaks** — onde o EV vazou. É a promessa central da landing.
4. **Qualidade GTO** — de onde vem o veredito, e o que significa "sem cobertura".
5. **Evolução / carreira** — a prova de que melhorou, com o intervalo de confiança à vista.
6. **Treino** (item da navegação) — como o leak vira exercício. Único passo que aponta para
   navegação, não para número.

Âncoras declarativas via `data-tour="<nome>"`, ideia aproveitada do protótipo: o passo referencia
um nome, não um seletor CSS frágil.

**Regra dura:** passo cujo alvo não existe no DOM é **pulado**, nunca apontado. Na `/demo` todos
existem; no dashboard real (onde o tour também pode rodar) nem sempre.

---

## 6. O que o tour precisa dizer e o protótipo não diz

Cada indicador tem que declarar **quanto volume exige**. Medido em 2026-07-30: quem tem 258
decisões tem ZERO família validável. Sem isso, o jogador sobe um torneio, lê "ainda não dá para
afirmar" e conclui que o produto não funciona.

O passo 01 do protótipo ("é o termômetro rápido") é exatamente o texto que produz essa frustração.

---

## 7. Persistência — RESOLVIDO: não existe

A spec previa estado server-side junto de `onboarding_completed`. Ao implementar, a necessidade
**desapareceu**: o tour roda na `/demo`, que é PÚBLICA, e um visitante deslogado não tem estado no
servidor para consultar.

Como o tour nunca abre sozinho (§4: só por clique), não há nada a lembrar. Sem migração, sem
coluna nova, sem `localStorage`. O botão fica sempre disponível, que é o comportamento certo de
qualquer jeito: rever tem que ser barato.

Se um dia o tour rodar sobre o dashboard do próprio jogador e precisar abrir sozinho, aí sim
volta a decisão de persistir — e aí é server-side.

---

## 8. O que NÃO trazer do protótipo

- `ENC: AES-256` no rodapé. Selo sem lastro: `grep -i "aes|encrypt"` no backend inteiro dá zero. Foi
  removido do dropzone hoje pelo mesmo motivo.
- KPIs, "Sessão sincronizada há 2 min" e "Confiança da IA 87%" cravados no JSX.
- Onboarding em `localStorage`.
- O tour disparando sozinho após o cadastro.

## 9. O que trazer

- Botão "Tour guiado" persistente.
- `data-tour` como âncora declarativa.
- O passo que aponta para a navegação de treino/estudo.
- `resetOnboarding` como ferramenta de suporte/dev (mas server-side).

---

## 10. Fases

| fase | entrega | depende de |
|---|---|---|
| 0 | decidir a origem dos dados (§3) | usuário |
| 1 | fixture do dashboard de demonstração + endpoint | fase 0 |
| 2 | rota `/demo` renderizando `DashboardV2` real com selo | fase 1 |
| 3 | componente `GuidedTour` + âncoras `data-tour` | — |
| 4 | passos, copy nas 3 locales, volume mínimo por indicador | fase 3 |
| 5 | gatilhos (§4) + persistência server-side | fase 4 |

As fases 1-2 já entregam valor sozinhas: uma tela que mostra o produto povoado é útil mesmo sem
tour nenhum, e é o que falta hoje para quem chega do Instagram.

**Fases 1 a 4 ENTREGUES em 2026-08-01.** Da fase 5 entrou só o gatilho da própria `/demo` (botão
"Tour guiado" no selo); a persistência deixou de existir por não ser mais necessária (§7).

Faltam os outros dois gatilhos do §4: o CTA no 3º passo do `OnboardingModal` e o link no
`EmptyDashboard`. Ambos são um `Link to="/demo"` — nenhum deles depende de código novo.
