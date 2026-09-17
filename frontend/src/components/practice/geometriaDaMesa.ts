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
 * ── O defeito que ela revelou de imediato ─────────────────────────────────────────────────────
 *
 * O pod e as cartas do herói viviam no MESMO flex, centrado no ponto do trilho. Com cartas, o
 * conjunto inteiro era centrado, então o POD saía do lugar dele: na captura do dono, o pod do
 * UTG+2 aparece fora da linha da mesa, à esquerda dela. O pod agora fica ancorado no ponto, e as
 * cartas são posicionadas por fora do fluxo, para um lado que depende de ONDE o assento está.
 */

/** A elipse. Tudo é derivado dela: mudar aqui move assentos, fichas e cartas juntos. */
export const TRILHO = { cx: 50, cy: 50, rx: 44, ry: 39 };

/** Os ângulos dos nove lugares. O ângulo é do ASSENTO FÍSICO (`seat`), não da ordem de ação:
 *  o herói cai em qualquer um deles, e é por isso que o layout de cada lugar tem de funcionar
 *  para ele também. */
export const ANGULOS = [90, 130, 170, 210, 250, 290, 330, 10, 50] as const;

/** `(x, y)` em %, sobre a elipse do trilho. `escala < 1` traz para DENTRO da mesa. */
export function naElipse(grau: number, escala = 1): [number, number] {
  const r = (grau * Math.PI) / 180;
  return [
    TRILHO.cx + TRILHO.rx * escala * Math.cos(r),
    TRILHO.cy + TRILHO.ry * escala * Math.sin(r),
  ];
}

/** Os nove lugares, SOBRE o trilho. */
export const LUGARES: [number, number][] = ANGULOS.map((a) => naElipse(a));

/** A ficha de cada assento: mesma direção, mais perto do centro, dentro da mesa. */
export const FICHAS: [number, number][] = ANGULOS.map((a) => naElipse(a, 0.62));

/**
 * ── As medidas ────────────────────────────────────────────────────────────────────────────────
 *
 * `[piso, porLargura, porAltura, teto]`: o valor é o MENOR entre a fração da largura (`cqw`) e a
 * da altura (`cqh`) do card, preso entre piso e teto em px.
 *
 * Por que as duas dimensões: com duas mesas a célula fica ~830x880 e com quatro ~830x440. A
 * LARGURA é a mesma nos dois casos, então medir só por ela deixava os assentos do tamanho de
 * mesa apertada com o dobro de espaço vertical sobrando. A fração da ALTURA entra para o assento
 * não estourar o trilho quando a célula é baixa.
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
 * Quanto da largura o bloco de texto do centro ocupa.
 *
 * Era 52%, e nessa largura ele alcancava a ficha de aposta dos dois lugares das PONTAS da elipse,
 * que ficam na mesma altura dele. O texto do spot ("UTG+2 contra BTN, vs 3-bet") quebra em duas
 * linhas com 46%, e duas linhas de texto legivel valem mais que uma linha por cima da ficha.
 */
export const LARGURA_DO_CENTRO = 0.46;

/**
 * Para onde vão as cartas do herói, a partir do lugar dele.
 *
 * - Nos lugares das PONTAS da elipse (`|cos|` grande) elas vão na vertical: ao lado, ali, elas
 *   entrariam no bloco de texto do centro, que ocupa a faixa do meio na mesma altura deles.
 * - Nos outros vão na horizontal, para DENTRO (o lado do centro), porque para fora sairiam do
 *   card.
 * - No lugar de baixo (`cos` zero) não há "dentro" horizontal: vão para a direita.
 */
export function ladoDasCartas(i: number): "cima" | "baixo" | "esquerda" | "direita" {
  const r = (ANGULOS[i] * Math.PI) / 180;
  const cos = Math.cos(r);
  const sin = Math.sin(r);
  if (Math.abs(cos) >= 0.8) return sin > 0 ? "cima" : "baixo";
  if (Math.abs(cos) < 0.01) return "direita";
  return cos > 0 ? "esquerda" : "direita";
}

/**
 * Para onde vai o botão do dealer: TANGENTE à elipse, nunca sobre o pod.
 *
 * Ele era `-bottom-0.5 -left-1` no canto do pod, ou seja POR CIMA dele, visível na captura do
 * dono onde o "D" cobre a borda do assento do BTN e ainda disputa espaço com a ficha de aposta.
 * A tangente é a direção que não aponta nem para o centro (onde está a ficha) nem para fora
 * (onde está a borda do card).
 */
export function direcaoDoDealer(i: number): [number, number] {
  const r = (ANGULOS[i] * Math.PI) / 180;
  // A tangente da ELIPSE, e nao a do circulo: os pontos sao (rx*cos, ry*sin), entao a derivada e
  // (-rx*sin, ry*cos). Com a tangente do circulo (-sin, cos) a direcao apontava parcialmente
  // para o centro nos lugares diagonais, que e de onde vem a ficha de aposta.
  const dx = -TRILHO.rx * Math.sin(r);
  const dy = TRILHO.ry * Math.cos(r);
  const n = Math.hypot(dx, dy);
  const s = sentidoDoDealer(i);
  return [(s * dx) / n, (s * dy) / n];
}

/**
 * Qual dos DOIS sentidos da tangente o botao do dealer usa, em cada lugar.
 *
 * A tangente e uma reta, e tem dois lados. O medidor achou o que acontece quando o lado escolhido
 * coincide com o lado das cartas: nos lugares 2, 4, 6 e 8, com o heroi SENDO o botao, o "D" caia
 * por cima das cartas dele (373px2 no pior caso). O sentido e escolhido para se AFASTAR do lado
 * das cartas daquele lugar.
 *
 * Fixo por lugar, e nao por mao: se o "D" mudasse de lado conforme quem e o heroi, o jogador
 * perderia a referencia de onde procurar o botao -- que e metade do valor de ter um botao
 * desenhado.
 */
export function sentidoDoDealer(i: number): 1 | -1 {
  const r = (ANGULOS[i] * Math.PI) / 180;
  const tx = -TRILHO.rx * Math.sin(r);
  const ty = TRILHO.ry * Math.cos(r);
  const lado = ladoDasCartas(i);
  const c: [number, number] =
    lado === "direita" ? [1, 0] : lado === "esquerda" ? [-1, 0] : lado === "cima" ? [0, -1] : [0, 1];
  return tx * c[0] + ty * c[1] > 0 ? -1 : 1;
}

/**
 * A que distancia do centro do pod o botao do dealer fica, em px.
 *
 * Nao e `(pod + dealer) / 2`: as duas caixas sao quadradas, e em direcao diagonal a separacao
 * util e a PROJECAO da distancia no eixo dominante. Com a conta simples, dois circulos que nao se
 * tocam ainda tinham as caixas se cruzando nos cantos -- 23px2 que o medidor acusou e que a olho
 * nu ninguem veria. Medir com a caixa e pessimista de proposito, porque errar para o lado de
 * acusar e o unico erro barato aqui.
 */
export function distanciaDoDealer(i: number, pod: number, dealer: number): number {
  const [dx, dy] = direcaoDoDealer(i);
  const eixo = Math.max(Math.abs(dx), Math.abs(dy));
  return (pod + dealer) / 2 / eixo + FOLGA;
}

/**
 * O deslocamento do botao do dealer como CSS, a partir do centro do pod.
 *
 * A MESMA conta de `distanciaDoDealer`, escrita em `calc` porque o componente nao sabe o tamanho
 * do card (quem sabe e o navegador, resolvendo o `clamp`). Duas escritas da mesma regra e
 * exatamente o que a regra 5 da casa proibe, entao `geometriaDaMesa.test.ts` RESOLVE esta string
 * com valores concretos e exige que ela bata com a conta em px. Sem esse teste, o medidor poderia
 * aprovar uma mesa que o jogador nao ve.
 */
export function deslocamentoDoDealerCss(i: number): { x: string; y: string } {
  const [dx, dy] = direcaoDoDealer(i);
  const eixo = Math.max(Math.abs(dx), Math.abs(dy));
  const d = `((${M.assento} + ${M.dealer}) / 2 / ${eixo} + ${FOLGA}px)`;
  return { x: `calc(${dx} * ${d})`, y: `calc(${dy} * ${d})` };
}

/** De que lado, em CSS, as cartas do heroi saem do pod. A folga e medida da BORDA do pod, que e
 *  o que `caixasDaMesa` tambem faz. */
export function estiloDasCartas(i: number): {
  left?: string;
  right?: string;
  top?: string;
  bottom?: string;
  transform: string;
} {
  const fora = `calc(100% + ${FOLGA}px)`;
  switch (ladoDasCartas(i)) {
    case "direita":
      return { left: fora, top: "50%", transform: "translateY(-50%)" };
    case "esquerda":
      return { right: fora, top: "50%", transform: "translateY(-50%)" };
    case "cima":
      return { bottom: fora, left: "50%", transform: "translateX(-50%)" };
    default:
      return { top: fora, left: "50%", transform: "translateX(-50%)" };
  }
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
 * O componente posiciona em % e `clamp`; aqui a MESMA geometria é resolvida em px. As duas contas
 * saem das mesmas constantes (`LUGARES`, `FICHAS`, `PARAMS`), que é o que impede o medidor de
 * medir uma mesa diferente da que o jogador vê.
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

  const ponto = (p: [number, number]): [number, number] => [(p[0] / 100) * w, (p[1] / 100) * h];

  LUGARES.forEach((p, i) => {
    const [cx, cy] = ponto(p);
    caixas.push({ nome: `pod:${i}`, x: cx - pod / 2, y: cy - pod / 2, w: pod, h: pod });

    if (i === heroi) {
      const largura = cw * 2 + 2; // as duas cartas, lado a lado, com o gap
      const lado = ladoDasCartas(i);
      let x = cx - largura / 2;
      let y = cy - ch / 2;
      if (lado === "direita") x = cx + pod / 2 + FOLGA;
      if (lado === "esquerda") x = cx - pod / 2 - FOLGA - largura;
      if (lado === "cima") y = cy - pod / 2 - FOLGA - ch;
      if (lado === "baixo") y = cy + pod / 2 + FOLGA;
      caixas.push({ nome: `cartas:${i}`, x, y, w: largura, h: ch });
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

  if (centro) {
    // o bloco do meio: 52% da largura, e a altura das três linhas (spot, pote, "n na mao")
    const alturaCentro =
      px("fSpot", w, h) * 1.35 + px("fPote", w, h) * 1.25 + px("fHist", w, h) * 1.35;
    caixas.push({
      nome: "centro",
      x: w / 2 - (w * LARGURA_DO_CENTRO) / 2,
      y: h / 2 - alturaCentro / 2,
      w: w * LARGURA_DO_CENTRO,
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
