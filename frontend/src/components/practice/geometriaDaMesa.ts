/**
 * A geometria da mesa do Prática: uma elipse, nove lugares, e onde cada coisa fica em volta de
 * cada lugar.
 *
 * ── Por que isto saiu do componente ───────────────────────────────────────────────────────────
 *
 * O dono, na terceira rodada de ajuste da mesa: "melhorou mas vamos ter que ajustar assento por
 * assento para nao haver sobreposições das cartas, fichas, valores".
 *
 * Ajustar a olho, elemento por elemento, é o ping-pong que esta frente já pagou duas vezes: a
 * captura mostra o caso que ela mostra, e o assento que não estava naquela mão continua errado.
 * Com a geometria aqui, `caixasDaMesa` devolve a CAIXA de cada elemento em px para um tamanho de
 * card, e o teste varre as 9 posições do herói contra as 9 do botão exigindo que nada se
 * sobreponha e nada saia do card. O que a captura do dono mostrou é um caso entre 81.
 *
 * ── O que a medição achou, e as capturas não ──────────────────────────────────────────────────
 *
 * 1. O pod e as cartas do herói viviam no MESMO flex, centrado no ponto do trilho. Com cartas, o
 *    conjunto era centrado e o POD saía do lugar dele: na captura do dono, o assento do UTG+2
 *    aparece fora da linha da mesa.
 * 2. O "D" do dealer estava no canto do pod, por cima dele.
 * 3. As cartas e a ficha do MESMO assento iam as duas "para dentro", e se cruzavam em dois
 *    lugares, em todas as 9 posições do botão.
 * 4. As cartas de um assento encontravam o "D" do assento VIZINHO nas pontas da elipse, onde os
 *    vizinhos ficam a ~124px um do outro e não aos ~244px dos lugares de cima e de baixo.
 * 5. A ficha dos lugares das pontas entrava no bloco de texto do centro.
 * 6. Com 0,62 do raio, as fichas ficavam ÓRFÃS no meio do feltro, longe de quem apostou.
 */

/** Os ângulos dos nove lugares. O ângulo é do ASSENTO FÍSICO (`seat`), não da ordem de ação:
 *  o herói cai em qualquer um deles, e é por isso que o layout de cada lugar tem de funcionar
 *  para ele também. */
export const ANGULOS = [90, 130, 170, 210, 250, 290, 330, 10, 50] as const;

/**
 * ── As medidas ───────────────────────────────────────────────────────────────────────────────
 *
 * `[piso, porLargura, porAltura, teto]`: o valor é o MENOR entre a fração da largura (`cqw`) e a
 * da altura (`cqh`) do card, preso entre piso e teto em px.
 *
 * Por que as duas dimensões: com duas mesas a célula fica ~830x880 e com quatro ~830x440. A
 * LARGURA é a mesma nos dois casos, então medir só por ela deixava os assentos do tamanho de
 * mesa apertada com o dobro de espaço vertical sobrando -- o "está tudo muito pequeno" do dono.
 * A fração da ALTURA entra para o assento não estourar o trilho quando a célula é baixa.
 *
 * Uma tabela, dois consumidores: `M` (as strings de CSS que o componente usa) e `px` (o valor
 * resolvido, que o medidor de colisão usa). Sem isto seriam dois números para a mesma medida.
 */
export const PARAMS = {
  assento: [34, 6.6, 12.2, 76],
  cartaW: [26, 4.4, 8.2, 58],
  cartaH: [34, 6.0, 11.1, 78],
  fPos: [9, 1.7, 3.1, 19],
  fStack: [11, 2.0, 3.7, 23],
  fCarta: [15, 2.6, 4.8, 33],
  fNaipe: [12, 2.1, 3.9, 27],
  fSpot: [10, 1.7, 3.2, 20],
  fPote: [14, 2.6, 4.8, 32],
  fFicha: [11, 2.0, 3.7, 23],
  ficha: [9, 1.5, 2.8, 19],
  fHist: [9, 1.6, 3.0, 18],
  dealer: [14, 2.4, 4.4, 30],
  fDealer: [8, 1.4, 2.6, 17],
} as const satisfies Record<string, readonly [number, number, number, number]>;

export type Nome = keyof typeof PARAMS;

/** A medida como CSS, para o componente. */
export function medida(p: readonly [number, number, number, number]): string {
  const [piso, porLargura, porAltura, teto] = p;
  return `clamp(${piso}px, min(${porLargura}cqw, ${porAltura}cqh), ${teto}px)`;
}

/** A MESMA medida resolvida em px, para o medidor: `min` e `clamp` do CSS, em aritmética. */
export function px(nome: Nome, w: number, h: number): number {
  const [piso, porLargura, porAltura, teto] = PARAMS[nome];
  const v = Math.min((porLargura * w) / 100, (porAltura * h) / 100);
  return Math.min(teto, Math.max(piso, v));
}

/** As strings de CSS, uma por medida. */
export const M = Object.fromEntries(
  Object.entries(PARAMS).map(([k, v]) => [k, medida(v)]),
) as Record<Nome, string>;

/** Folga mínima entre dois elementos vizinhos do mesmo assento, em px. */
export const FOLGA = 4;

/**
 * Quanto da arena o bloco de texto do centro ocupa.
 *
 * Era 52%, e nessa largura ele alcançava a ficha de aposta dos dois lugares das PONTAS da elipse,
 * que ficam na mesma altura dele. O texto do spot ("UTG+2 contra BTN, vs 3-bet") quebra em duas
 * linhas com 46%, e duas linhas de texto legível valem mais que uma linha por cima da ficha.
 */
export const LARGURA_DO_CENTRO = 0.46;

/**
 * A que fração do raio fica a ficha de aposta de cada assento.
 *
 * ── Por que 0,76, e não um número escolhido a olho ───────────────────────────────────────────
 *
 * Com 0,62 (a primeira tentativa de fugir do texto central) as fichas ficavam ÓRFÃS no meio do
 * feltro: na captura do dono, o `0.5` estava a uns 150px do pod do SB, e nada dizia de quem era a
 * aposta. A janela livre foi MEDIDA com o medidor de colisão, com aposta larga nos nove lugares e
 * nos quatro tamanhos de card:
 *
 *   >= 0,75       a ficha encosta no POD do próprio jogador
 *   0,56 a 0,74   livre
 *   <= 0,50       a ficha entra no bloco de texto do centro
 *
 * 0,73 é o mais perto do dono da aposta que cabe, com uma casa de folga na borda da janela. A
 * janela foi remedida quando a elipse passou a preencher a arena: com o desenho anterior o teto
 * era 0,77, e um número herdado de outra geometria é como se volta a ter ficha por cima de pod.
 */
export const ESCALA_DAS_FICHAS = 0.73;

/**
 * ── A elipse não tem raio escolhido a olho: ela PREENCHE a arena ──────────────────────────────
 *
 * A primeira versão cravava `rx: 44, ry: 39` do card. O medidor mostrou que número fixo não
 * resolve: com o botão do dealer saindo para FORA do trilho e o histórico ocupando a faixa do
 * topo, 39% de altura estoura o card na célula baixa (4 mesas, 440px) e sobra demais na célula
 * alta (2 mesas, 880px) -- e "sobra" é o vazio no meio do feltro que o dono reclamou.
 *
 * Agora a elipse preenche a ARENA, que é o card menos as margens que os elementos EXIGEM:
 *
 *   margem = metade do pod (o assento fica sobre a linha) + o botão do dealer (que sai para fora
 *            dela) + a folga
 *   topo   = a mesma margem, mais a faixa do histórico da mão
 *
 * Assim a mesa é alta quando há altura e achatada quando não há, sem nunca vazar, e o número sai
 * das medidas em vez de ser recalibrado a cada captura.
 */

/** A faixa do histórico da mão, no topo do card. Duas linhas, porque com nove assentos ele
 *  quebra. */
export function alturaDoHistorico(w: number, h: number): number {
  return px("fHist", w, h) * 2.6;
}

/** A margem que a arena precisa, em px: o pod fica SOBRE a linha e o botão sai para fora dela. */
export function margemDaArena(w: number, h: number): number {
  return px("assento", w, h) / 2 + px("dealer", w, h) + FOLGA;
}

/** A arena em px: onde a elipse cabe inteira, com tudo o que pendura nela. */
export function arena(w: number, h: number) {
  const m = margemDaArena(w, h);
  const topo = m + alturaDoHistorico(w, h);
  return { x: m, y: topo, w: w - 2 * m, h: h - topo - m };
}

/** A MESMA arena em CSS, para o componente. Conferida contra a de px no teste. */
export function arenaCss() {
  const m = `(${M.assento} / 2 + ${M.dealer} + ${FOLGA}px)`;
  return {
    left: `calc${m}`,
    right: `calc${m}`,
    bottom: `calc${m}`,
    top: `calc(${m} + ${M.fHist} * 2.6)`,
  };
}

/** `(x, y)` em % DA ARENA, sobre a elipse que a preenche. `escala < 1` traz para dentro. */
export function naElipse(grau: number, escala = 1): [number, number] {
  const r = (grau * Math.PI) / 180;
  return [50 + 50 * escala * Math.cos(r), 50 + 50 * escala * Math.sin(r)];
}

/** Os nove lugares, SOBRE a elipse. */
export const LUGARES: [number, number][] = ANGULOS.map((a) => naElipse(a));

/** A ficha de cada assento: mesma direção do dono dela, mais perto do centro. */
export const FICHAS: [number, number][] = ANGULOS.map((a) => naElipse(a, ESCALA_DAS_FICHAS));

function versor(i: number): [number, number] {
  const r = (ANGULOS[i] * Math.PI) / 180;
  return [Math.cos(r), Math.sin(r)];
}

/**
 * ── Três direções por assento, e nenhuma colisão por construção ──────────────────────────────
 *
 * Cada assento tem três coisas em volta dele: a ficha de aposta, as cartas (se for o herói) e o
 * botão do dealer (se for o botão). Dar a mesma direção para duas delas colide SEMPRE, e não em
 * algum caso raro: o medidor achou as cartas por cima da ficha do próprio herói em dois lugares,
 * nas 9 posições do botão.
 *
 * A ficha vai pelo raio da elipse (`FICHAS`), o botão sai para FORA em `(cos, sin)`, e as cartas
 * pela perpendicular `(-sin, cos)`.
 *
 * ── Por que direções unitárias em PX, e não a tangente da elipse ─────────────────────────────
 *
 * A tangente exata de uma elipse depende do achatamento dela, e o achatamento sai do tamanho da
 * arena -- que o CSS não conhece, porque quem resolve o `clamp` é o navegador. Uma direção que só
 * o medidor sabe calcular não serve para posicionar. `(cos, sin)` e `(-sin, cos)` são unitárias e
 * perpendiculares entre si no espaço de px, com módulo em px de verdade.
 *
 * O botão já esteve na tangente, e não deu: nas PONTAS da elipse os assentos vizinhos ficam a
 * ~124px um do outro, então as cartas de um e o "D" do vizinho se encontravam no meio do caminho.
 * Para fora do trilho ele não disputa espaço com ninguém.
 */
export function direcaoDoDealer(i: number): [number, number] {
  return versor(i);
}

/**
 * O aspecto de referência para decidir o SENTIDO das cartas.
 *
 * As cartas saem pela perpendicular, e a perpendicular tem dois sentidos: um aponta para o
 * assento anterior, o outro para o seguinte. Nas PONTAS da elipse achatada os vizinhos não ficam
 * à mesma distância (111px contra 153px, medido na arena de 4 mesas), então a escolha importa: o
 * medidor achou as cartas do lugar 1 por cima do pod do lugar 2 em todas as 9 posições do botão.
 *
 * 2,4 para 1 é o aspecto da arena no caso APERTADO (4 mesas, onde a altura é a metade). Decidir
 * pelo caso apertado é o certo: é onde a colisão acontece, e o medidor confere os outros três
 * tamanhos depois.
 */
const ASPECTO_DE_REFERENCIA = 2.4;

/** Qual dos dois sentidos da perpendicular aponta para o vizinho mais DISTANTE. */
function sentidoDasCartas(i: number): 1 | -1 {
  const ponto = (j: number): [number, number] => {
    const [x, y] = LUGARES[(j + 9) % 9];
    return [(x - 50) * ASPECTO_DE_REFERENCIA, y - 50];
  };
  const [x0, y0] = ponto(i);
  const dist = (j: number) => {
    const [x, y] = ponto(j);
    return Math.hypot(x - x0, y - y0);
  };
  const [c, s] = versor(i);
  // o vizinho para o lado de `(-s, c)`: o de indice seguinte na volta dos angulos
  const seguinte = dist(i + 1);
  const anterior = dist(i - 1);
  const [px1, py1] = ponto(i + 1);
  const paraSeguinte = (px1 - x0) * -s + (py1 - y0) * c > 0;
  const maisLongeEhSeguinte = seguinte >= anterior;
  return paraSeguinte === maisLongeEhSeguinte ? 1 : -1;
}

export function direcaoDasCartas(i: number): [number, number] {
  const [c, s] = versor(i);
  const k = sentidoDasCartas(i);
  return [-s * k, c * k];
}

/**
 * A distância, do centro do pod, de algo com `w` x `h` que sai na direção `dir`.
 *
 * Não é `(pod + tamanho) / 2`: as caixas são retangulares, e em direção diagonal a separação útil
 * é a PROJEÇÃO no eixo dominante. Com a conta simples, dois círculos que não se tocam ainda
 * tinham as caixas se cruzando nos cantos. Medir pela caixa é pessimista de propósito, porque
 * errar para o lado de acusar é o único erro barato aqui.
 */
function distancia(dir: [number, number], pod: number, w: number, h: number): number {
  const [dx, dy] = dir;
  const horizontal = Math.abs(dx) >= Math.abs(dy);
  const eixo = horizontal ? Math.abs(dx) : Math.abs(dy);
  const tamanho = horizontal ? w : h;
  return (pod + tamanho) / 2 / eixo + FOLGA;
}

export function distanciaDasCartas(i: number, pod: number, w: number, h: number): number {
  return distancia(direcaoDasCartas(i), pod, w, h);
}

export function distanciaDoDealer(i: number, pod: number, dealer: number): number {
  return distancia(direcaoDoDealer(i), pod, dealer, dealer);
}

/**
 * O deslocamento de um elemento como CSS, a partir do centro do pod.
 *
 * A MESMA conta de `distancia`, escrita em `calc` porque o componente não sabe o tamanho do card.
 * Duas escritas da mesma regra é o defeito da regra 5, então `geometriaDaMesa.test.ts` RESOLVE
 * estas strings com valores concretos e exige que batam com a conta em px. Verificado quebrando:
 * com a fórmula do CSS alterada, o medidor passou verde nas 81 mãos e só esse teste acusou.
 */
function deslocamentoCss(dir: [number, number], w: string, h: string): { x: string; y: string } {
  const [dx, dy] = dir;
  const horizontal = Math.abs(dx) >= Math.abs(dy);
  const eixo = horizontal ? Math.abs(dx) : Math.abs(dy);
  const tamanho = horizontal ? w : h;
  const d = `((${M.assento} + ${tamanho}) / 2 / ${eixo} + ${FOLGA}px)`;
  return { x: `calc(${dx} * ${d})`, y: `calc(${dy} * ${d})` };
}

/** As duas cartas lado a lado, com o gap: é a largura que sai do pod. */
export const LARGURA_DAS_CARTAS = `calc(${M.cartaW} * 2 + 2px)`;

export function deslocamentoDasCartasCss(i: number): { x: string; y: string } {
  return deslocamentoCss(direcaoDasCartas(i), LARGURA_DAS_CARTAS, M.cartaH);
}

export function deslocamentoDoDealerCss(i: number): { x: string; y: string } {
  return deslocamentoCss(direcaoDoDealer(i), M.dealer, M.dealer);
}

export type Caixa = {
  nome: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

/** Largura aproximada de um texto em fonte mono: ~0,62em por caractere. Aproximação declarada,
 *  e generosa de propósito: o medidor deve errar para o lado de acusar colisão que não existe,
 *  nunca para o lado de perder colisão que existe. */
export function larguraDeTexto(texto: string, fonte: number): number {
  return texto.length * fonte * 0.62;
}

export type ConfigDeMedida = {
  w: number;
  h: number;
  /** índice (0..8) do lugar onde está o herói */
  heroi: number;
  /** índice (0..8) do lugar com o botão */
  botao: number;
  /** quais lugares têm ficha de aposta, e com que texto */
  apostas?: { i: number; texto: string }[];
  /** o bloco de texto do centro ocupa espaço e entra na conta */
  centro?: boolean;
};

/**
 * Toda caixa desenhada na mesa, em px, para um card de `w` por `h`.
 *
 * O componente posiciona em % da arena e `clamp`; aqui a MESMA geometria é resolvida em px. As
 * duas contas saem das mesmas constantes (`LUGARES`, `FICHAS`, `PARAMS`, `arena`), que é o que
 * impede o medidor de medir uma mesa diferente da que o jogador vê.
 */
export function caixasDaMesa(cfg: ConfigDeMedida): Caixa[] {
  const { w, h, heroi, botao, apostas = [], centro = true } = cfg;
  const caixas: Caixa[] = [];
  const pod = px("assento", w, h);
  const cw = px("cartaW", w, h);
  const ch = px("cartaH", w, h);
  const dl = px("dealer", w, h);
  const fichaD = px("ficha", w, h);
  const fFicha = px("fFicha", w, h);
  const a = arena(w, h);

  /** Um ponto em % DA ARENA, resolvido em px do card. */
  const ponto = (p: [number, number]): [number, number] => [
    a.x + (p[0] / 100) * a.w,
    a.y + (p[1] / 100) * a.h,
  ];

  LUGARES.forEach((p, i) => {
    const [cx, cy] = ponto(p);
    caixas.push({ nome: `pod:${i}`, x: cx - pod / 2, y: cy - pod / 2, w: pod, h: pod });

    if (i === heroi) {
      const largura = cw * 2 + 2;
      const dir = direcaoDasCartas(i);
      const d = distanciaDasCartas(i, pod, largura, ch);
      caixas.push({
        nome: `cartas:${i}`,
        x: cx + dir[0] * d - largura / 2,
        y: cy + dir[1] * d - ch / 2,
        w: largura,
        h: ch,
      });
    }

    if (i === botao) {
      const [dx, dy] = direcaoDoDealer(i);
      const d = distanciaDoDealer(i, pod, dl);
      caixas.push({
        nome: `dealer:${i}`,
        x: cx + dx * d - dl / 2,
        y: cy + dy * d - dl / 2,
        w: dl,
        h: dl,
      });
    }
  });

  apostas.forEach(({ i, texto }) => {
    const [cx, cy] = ponto(FICHAS[i]);
    const largura = fichaD + 4 + larguraDeTexto(texto, fFicha);
    const altura = Math.max(fichaD, fFicha * 1.2);
    caixas.push({
      nome: `aposta:${i}`,
      x: cx - largura / 2,
      y: cy - altura / 2,
      w: largura,
      h: altura,
    });
  });

  // O histórico da mão ocupa a faixa do topo do CARD (fora da arena), e ficou de fora da primeira
  // versão do medidor: um esquecimento que deixaria o "D" de um assento de cima passar por baixo
  // dele sem ninguém ver. A arena já desconta esta faixa; o guarda existe para o dia em que
  // alguém mudar uma das duas contas e não a outra.
  caixas.push({ nome: "historico", x: 0, y: 0, w, h: alturaDoHistorico(w, h) });

  if (centro) {
    // o bloco do meio: uma fração da arena, e a altura das três linhas (spot, pote, "n na mao")
    const alturaCentro =
      px("fSpot", w, h) * 1.35 + px("fPote", w, h) * 1.25 + px("fHist", w, h) * 1.35;
    caixas.push({
      nome: "centro",
      x: a.x + a.w / 2 - (a.w * LARGURA_DO_CENTRO) / 2,
      y: a.y + a.h / 2 - alturaCentro / 2,
      w: a.w * LARGURA_DO_CENTRO,
      h: alturaCentro,
    });
  }

  return caixas;
}

/** Área da interseção de duas caixas, em px². Zero = não se tocam. */
export function sobreposicao(a: Caixa, b: Caixa): number {
  const dx = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
  const dy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
  return dx > 0 && dy > 0 ? dx * dy : 0;
}

/** Quanto a caixa sai do card, em px (0 = dentro). */
export function vazamento(c: Caixa, w: number, h: number): number {
  return Math.max(0, -c.x, -c.y, c.x + c.w - w, c.y + c.h - h);
}
