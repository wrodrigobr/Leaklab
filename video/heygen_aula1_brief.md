# HeyGen — Brief de produção: Módulo 1, Aula 1 (Conceitos / Posição)

> Objetivo: montar a Aula 1 no HeyGen usando o avatar + voz + legendas do HeyGen, e os
> **gráficos reais** exportados do nosso projeto Remotion como mídia de fundo. O HeyGen
> NÃO deve desenhar range grid nem mesa (ele erraria os números); esses vêm prontos de nós.

## Configuração do projeto (uma vez)
- **Idioma / voz:** Português (Brasil). Voz masculina ou feminina natural, tom de professor calmo e confiante. Velocidade normal (público iniciante). Sugestão de voz: uma PT-BR "conversacional", não robótica.
- **Formato:** 16:9, 1920x1080.
- **Brand kit:** fundo `#0A0E1A`, destaque teal `#2DD4BF`, texto claro `#E3E8EC`. Títulos em Chakra Petch, corpo em Space Grotesk (subir as fontes no Brand Kit).
- **Avatar (recomendado, híbrido):** avatar aparece SÓ na abertura (cena 1) e no fecho (cena 6), em tamanho médio à direita. Nas cenas técnicas (2 a 5), **esconder o avatar** (ou deixá-lo pequeno num canto) e deixar o gráfico ocupar a tela, com a voz do avatar em off. Isso respeita o formato "voz + gráficos" e usa o avatar como âncora humana.
- **Legendas:** ligadas, estilo limpo, na base. O HeyGen gera automático a partir do script.

## Regra de ouro dos gráficos
Nas cenas 2 (mesa), 4 (ranges) e 5 (exercício), **use como fundo os nossos arquivos**, não o gerador do HeyGen:
- Exporte do Remotion (`npm run render` ou `remotion still`) os clipes/frames de cada cena, OU capture a tela do próprio GrindLab.
- Suba como "Media" na cena do HeyGen e deixe o script (voz) por cima.

## Roteiro por cena (cole o SCRIPT de cada cena no editor do HeyGen)

O HeyGen cronometra a cena pela duração da fala; os segundos abaixo são só referência.

### Cena 1 — Hook (~13s) · avatar VISÍVEL
- **Script (voz):** "Existe uma vantagem no poker que não depende das suas cartas. Ela é grátis, todo profissional a usa, e a maioria dos amadores a ignora. É a posição."
- **Visual:** avatar médio à direita; à esquerda, título "A vantagem que não depende das suas cartas" + "A posição" em teal (fonte Chakra Petch).
- **Texto na tela:** MÓDULO 1 · FUNDAMENTOS.

### Cena 2 — A mesa / ordem de ação (~17s) · avatar OFF (voz em off)
- **Script (voz):** "Repara na mesa. A ação corre em ordem, e o botão é sempre o último a falar. Falar por último é ver o que todos fazem antes de decidir. Informação é poder, e a posição te dá informação de graça em toda mão."
- **Visual (mídia nossa):** a mesa oval 8-max com as posições, BTN destacado + dealer button (exportar do Remotion, cena "ordem").
- **Texto na tela:** "O botão fala por último."

### Cena 3 — IP vs OOP (~15s) · avatar OFF
- **Script (voz):** "In position, você joga com informação. Out of position, você joga no escuro. É por isso que as mesmas cartas rendem lucro do botão e prejuízo do UTG."
- **Visual:** dois painéis, IN POSITION (teal, "joga com informação") x OUT OF POSITION (escuro, "joga no escuro").
- **Texto na tela:** "Mesmas cartas, resultados opostos."

### Cena 4 — Ranges / demo (~20s) · avatar OFF · DADO REAL
- **Script (voz):** "Olha os dados reais do nosso solver. Do botão, você abre 53% das mãos, e KJ offsuit é abertura tranquila. Do UTG, com oito jogadores pra agir, você abre só 14%, e a mesma KJ offsuit vira fold. Cartas idênticas, decisões opostas, só a posição mudou."
- **Visual (mídia nossa, OBRIGATÓRIO):** os dois range grids 13x13 lado a lado, UTG (abre 14,4%) e BTN (abre 53,5%), com KJo destacado (anel vermelho no UTG = fold, teal no BTN = abre). Exportar do Remotion, cena "demo".
- **Texto na tela:** "Mesma mão, KJo: fold do UTG, raise do BTN."

### Cena 5 — Exercício (~17s) · avatar OFF
- **Script (voz):** "Sua vez. A-9 offsuit. Pior lugar pra jogar essa mão: UTG ou botão? Pensa um pouco. É o UTG. Muita gente pra agir depois, alta chance de estar dominado por mãos melhores. No botão, a mesma A-9 é abertura tranquila."
- **Visual:** pergunta grande "A-9 offsuit. Pior lugar pra jogar essa mão?" + botões UTG / BTN; após ~6s, UTG acende (resposta) + a explicação. Dica: inserir uma pausa visual (timer) enquanto a voz diz "pensa um pouco".
- **Texto na tela:** EXERCÍCIO.

### Cena 6 — Resumo + CTA (~18s) · avatar VISÍVEL
- **Script (voz):** "Recapitulando: o botão fala por último e decide com mais informação. In position você joga com dados, out of position no escuro. E força de mão é sempre relativa à posição. Agora sinta isso na prática, comece pela Academia, nível iniciante."
- **Visual:** avatar de volta; 3 bullets do resumo aparecendo um a um; botão final "Abrir Academia" em teal.
- **Texto na tela:** RESUMO.

## Alternativa: prompt único pro gerador de vídeo do HeyGen
Se quiser testar o modo "AI video from prompt" (menos controle, sem os nossos gráficos precisos):

> Crie uma vídeo-aula educativa de poker em português do Brasil, 16:9, tom de professor calmo para iniciantes. Fundo escuro (#0A0E1A) com destaques em teal (#2DD4BF), títulos geométricos. Um apresentador aparece na abertura e no fecho; no meio, a voz narra sobre gráficos. Estrutura em 6 blocos, com a narração exata: [colar os 6 scripts acima]. Legendas em português. Sem música alta, foco na fala.

Observação honesta: o modo prompt-único vai improvisar os gráficos e provavelmente errar os números do poker. Para conteúdo correto, use o modo por cenas com os nossos gráficos como mídia.

## Multilíngue
Depois de aprovar o PT, o HeyGen traduz o mesmo projeto para EN/ES (lip-sync + voz) trocando só o script de cada cena. Os gráficos (números) não mudam.
