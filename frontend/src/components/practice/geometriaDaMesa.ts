/**
 * A geometria da mesa do Prática: um estádio, nove lugares, e onde cada coisa fica em volta de
 * cada lugar. Tudo em PIXELS, a partir do tamanho medido do card.
 *
 * ── Por que tudo em px, e não em CSS ──────────────────────────────────────────────────────────
 *
 * A primeira versão media em `cqw`/`cqh` com `clamp()`, e as posições saíam em `%` com `calc()`.
 * Isso obrigava CADA regra a existir duas vezes: uma em aritmética (para o medidor de colisão) e
 * uma em string de CSS (para o navegador). Era a regra 5 da casa por construção, e custou caro em
 * 17/09: a mesa passou por cinco desenhos num dia, e a cada um eu tinha de reescrever as duas
 * versões e depois provar, com um teste, que elas concordavam.
 *
 * Agora o componente MEDE o próprio tamanho e chama `layoutDaMesa`, que devolve a caixa de cada
 * elemento em px. O medidor de colisão chama a MESMA função. Uma escrita, uma conta, e o teste
 * mede exatamente o que o jogador vê.
 *
 * ── O que o dono pediu, em ordem, e o que cada pedido mudou ───────────────────────────────────
 *
 * 1. "mantenha as mesmas proporcoes do gto wizard" → as medidas saem de uma tabela calibrada na
 *    captura deles.
 * 2. "ajustar assento por assento para nao haver sobreposições" → o medidor, que varre as 9
 *    posições do herói contra as 9 do botão em todos os tamanhos de card.
 * 3. "as bordas superiores e inferiores da mesa fiquem retas, e só curvemos as laterais...assim
 *    ganhamos espaço" → o contorno é um estádio, e não uma elipse.
 * 4. "em telas menores, a mesa está achatando" + "temos que ter um limite mínimo de achatamento"
 *    → o aspecto tem faixa, e fora dela a mesa para de deformar e passa a sobrar espaço.
 * 5. "e se reduzir muito, ele vira pra celular" (com a captura da mesa VERTICAL deles) → o
 *    aspecto acompanha o card dentro da faixa, e o estádio põe as retas no eixo maior: com a mesa
 *    larga elas ficam no topo e na base, com a mesa alta elas ficam nas laterais.
 */

/**
 * ── As medidas ───────────────────────────────────────────────────────────────────────────────
 *
 * `[piso, porLargura, porAltura, teto]`, em px: o valor é o MENOR entre a fração da largura e a da
 * altura do card, preso entre piso e teto.
 *
 * As duas dimensões, e não só a largura: com duas mesas a célula fica ~830x880 e com quatro
 * ~830x440, e a LARGURA é a mesma nos dois casos -- medir só por ela deixava os assentos do
 * tamanho de mesa apertada com o dobro de espaço vertical sobrando, que foi o "está tudo muito
 * pequeno" do dono.
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

/** A medida, em px, para um card de `w` x `h`. */
export function px(nome: Nome, w: number, h: number): number {
  const [piso, porLargura, porAltura, teto] = PARAMS[nome];
  const v = Math.min((porLargura * w) / 100, (porAltura * h) / 100);
  return Math.min(teto, Math.max(piso, v));
}

/** Folga mínima entre dois elementos vizinhos do mesmo assento, em px. */
export const FOLGA = 4;

/**
 * Quanto da arena o bloco de texto do centro ocupa.
 *
 * Era 52%, e nessa largura ele alcançava a ficha dos assentos das pontas. O texto do spot quebra
 * em duas linhas com 46%, e duas linhas legíveis valem mais que uma linha por cima da ficha.
 */
export const LARGURA_DO_CENTRO = 0.46;

/**
 * ── A faixa do aspecto ───────────────────────────────────────────────────────────────────────
 *
 * Dentro dela a mesa usa o aspecto do espaço livre; fora dela ela para de deformar e sobra espaço
 * em volta -- que é o "limite mínimo de achatamento" que o dono pediu, e o que impede a mesa de
 * virar uma fita quando a janela encurta.
 *
 * ── O que NÃO decide estes dois números, e por quê ────────────────────────────────────────────
 *
 * O medidor de colisão. Medido em 17/09, com a varredura das 81 mãos sobre os 14 tamanhos de card:
 * ela fica LIMPA com teto em 2,4, 3, 3,6, 4,3, 6 e até 14, e com piso em 0,62, 0,55, 0,48 e 0,40.
 * O controle em 0,1 acusa 972 mãos, então o medidor detecta. Colisão simplesmente não é o que se
 * perde aqui -- num estádio, achatar faz as RETAS crescerem e os assentos se espalharem nelas, ao
 * contrário da elipse, onde eles se amontoavam nas pontas. O teto de 2,4 é herança da elipse, e
 * sobreviveu à troca de forma sem ninguém conferir se ainda protegia algo.
 *
 * O que decide é o aspecto que os cards REAIS oferecem, medido card a card:
 *
 *   desktop  1660x880 → 2,30 · 830x440 → 2,57 · 683x330 → 2,96 · 910x375 → 3,62 · 830x300 → 4,30
 *   celular  430x620 → 0,54 · 390x480 → 0,65 · 360x522 → 0,50 · 320x460 → 0,48 · 390x700 → 0,40
 *
 * A faixa cobre isso com uma folga, e é por isso que ela abre: com o teto em 2,4 o card de 910x375
 * do dono usava 493 de 733px de largura livre e ele cobrou ("a mesa nao esta ocupando o espaço
 * disponivel no seu box"). O primeiro valor que eu escrevi aqui foi 3,6, e o guarda daquele card
 * derrubou por 0,02: a margem nova mudou o espaço livre e com ele o aspecto oferecido, que subiu de
 * 3,57 para 3,62. Número escolhido para um caso específico erra quando o caso se move.
 *
 * Acima de 3,7 a mesa PARA, porque é aí que ela deixa de parecer mesa: uma mesa só numa janela de
 * 400px de altura oferece 6,75, e numa de 260px oferece 13,71 -- 1.820x122 é uma fita, que foi
 * exatamente a reclamação anterior dele ("a mesa está achatando a um ponto que fica totalmente
 * ilegível"). O card de 830x300, que é o mínimo que a configuração deixa abrir, oferece 4,30 e
 * também para: ali sobram 51px de cada lado, de propósito.
 */
export const ASPECTO_MIN = 0.46;
export const ASPECTO_MAX = 3.7;

export function aspectoDaMesa(livreW: number, livreH: number): number {
  const doEspaco = livreH > 0 ? livreW / livreH : ASPECTO_MAX;
  return Math.min(ASPECTO_MAX, Math.max(ASPECTO_MIN, doEspaco));
}

/**
 * A faixa do histórico da mão, no topo do card.
 *
 * O fator era 2,2 e virou 1,8 em 17/09: o dono pediu "se colocarmos as ações mais coladas no
 * topo, a mesa consegue crescer verticalmente, pra cima e para baixo". A faixa tinha folga acima e
 * abaixo dos chips, e folga de sobra na faixa do topo é altura tirada da mesa.
 *
 * 1,8 não é um número escolhido a olho: o chip tem a fonte (`leading-none`, então 1,0), mais
 * `py-0.5` nos dois lados (4px) e a borda (2px) -- com a fonte mínima de 9px isso dá 15px contra
 * uma faixa de 16,2. Abaixo de 1,8 o chip começa a ser cortado.
 */
export function alturaDoHistorico(w: number, h: number): number {
  return px("fHist", w, h) * 1.8;
}

/**
 * ── A margem, lado por lado, medida no DESENHO ────────────────────────────────────────────────
 *
 * A primeira versão pedia UM número e o aplicava nos quatro lados: o pior caso de tudo o que
 * pendura, em qualquer direção. Isso custou o espaço que o dono cobrou em 17/09 ("a mesa nao esta
 * ocupando o espaço disponivel no seu box"). Medido no card dele, 910x375: a margem gastava 180
 * dos 350px de altura útil, mais da metade, e sobrava arena de 170px para a mesa inteira.
 *
 * O erro era tratar as direções como se fossem a mesma. Numa mesa larga, o assento de uma reta
 * joga as cartas para CIMA ou para BAIXO -- e o que pendura ali é a ALTURA da carta (42px). Só o
 * assento de uma ponta joga as cartas para o LADO, e aí pendura a LARGURA das duas (64px).
 * Reservar 64 em cima também é reservar espaço para algo que nunca vai lá.
 *
 * Então a margem de cada lado é o quanto o desenho REALMENTE passa daquela borda: percorro os nove
 * assentos, monto o pod, as cartas e o botão de cada um com as mesmas funções que o componente usa,
 * e pergunto quanto cada caixa avança de cada lado. Nada é estimado.
 */
export function margensDaArena(w: number, h: number, a: number, arenaW: number, arenaH: number) {
  const pod = px("assento", w, h);
  const cartasW = px("cartaW", w, h) * 2 + 2;
  const cartasH = px("cartaH", w, h);
  const dl = px("dealer", w, h);
  const m = { esq: 0, dir: 0, topo: 0, base: 0 };

  const considere = (bx: number, by: number, bw: number, bh: number) => {
    m.esq = Math.max(m.esq, -bx);
    m.topo = Math.max(m.topo, -by);
    m.dir = Math.max(m.dir, bx + bw - arenaW);
    m.base = Math.max(m.base, by + bh - arenaH);
  };

  for (let i = 0; i < 9; i++) {
    const [pctX, pctY] = noContorno(i, a);
    const cx = (pctX / 100) * arenaW;
    const cy = (pctY / 100) * arenaH;

    considere(cx - pod / 2, cy - pod / 2, pod, pod);

    const dirCartas = direcaoDasCartas(i, a);
    const dCartas = distancia(dirCartas, pod, cartasW, cartasH);
    considere(
      cx + dirCartas[0] * dCartas - cartasW / 2,
      cy + dirCartas[1] * dCartas - cartasH / 2,
      cartasW,
      cartasH,
    );

    const dirD = direcaoDoDealer(i, a);
    const dD = distanciaDoDealer(pod);
    considere(cx + dirD[0] * dD - dl / 2, cy + dirD[1] * dD - dl / 2, dl, dl);
  }

  return {
    esq: Math.max(0, m.esq) + FOLGA,
    dir: Math.max(0, m.dir) + FOLGA,
    topo: Math.max(0, m.topo) + FOLGA,
    base: Math.max(0, m.base) + FOLGA,
  };
}

/**
 * A arena em px: onde o estádio cabe inteiro, com tudo o que pendura nele.
 *
 * ── Por que um laço, e não uma conta ──────────────────────────────────────────────────────────
 *
 * A margem depende da ORIENTAÇÃO da mesa (numa mesa larga pendura altura de carta em cima; numa
 * vertical, largura de carta), e a orientação depende do espaço que sobra depois da margem. Começo
 * com a arena ocupando o card inteiro, meço a margem, refaço a arena, e repito até a largura parar
 * de mudar.
 *
 * O laço tinha três passadas fixas, e o guarda do card do dono pegou o resíduo: a arena fechava em
 * 738,9px onde havia 741,7 livres. Não é erro de conta, é convergência -- os pontos do contorno
 * andam quando a arena cresce, e com eles a margem. Parar em `mudou < 0,25px` fecha, e o teto de
 * seis passadas está aqui para o laço nunca ser infinito num card degenerado.
 *
 * A margem PEDIDA pode não caber, e aí ela cede em proporção em vez de a arena virar negativa
 * (arena de largura negativa desenha a mesa do avesso, e o medidor mediria isso como se fosse mesa).
 */
export function arena(w: number, h: number) {
  const hist = alturaDoHistorico(w, h);
  let aw = Math.max(1, w);
  let ah = Math.max(1, h - hist);
  let x = 0;
  let y = hist;
  let a = aspectoDaMesa(aw, ah);

  for (let passo = 0; passo < 6; passo++) {
    const antes = aw;
    const m = margensDaArena(w, h, a, aw, ah);
    // a margem cede em PROPORÇÃO: cortar um lado só deslocaria a mesa para fora do centro
    const cedeW = Math.min(1, (w * 0.8) / Math.max(1, m.esq + m.dir));
    const cedeH = Math.min(1, ((h - hist) * 0.8) / Math.max(1, m.topo + m.base));
    const esq = m.esq * cedeW;
    const topo = m.topo * cedeH;
    const livreW = Math.max(1, w - (m.esq + m.dir) * cedeW);
    const livreH = Math.max(1, h - hist - (m.topo + m.base) * cedeH);

    a = aspectoDaMesa(livreW, livreH);
    aw = livreW;
    ah = aw / a;
    if (ah > livreH) {
      ah = livreH;
      aw = ah * a;
    }
    x = esq + (livreW - aw) / 2;
    y = hist + topo + (livreH - ah) / 2;
    if (passo > 0 && Math.abs(aw - antes) < 0.25) break;
  }

  return { x, y, w: aw, h: ah, aspecto: a };
}

/**
 * O ponto do lugar `i` no contorno de um estádio de aspecto `a`, em % da arena.
 *
 * As retas ficam no eixo MAIOR: com a mesa larga, no topo e na base; com a mesa alta (o celular),
 * nas laterais. Os nove lugares saem por COMPRIMENTO DE ARCO (perímetro / 9) e não por ângulo --
 * por ângulo eles se amontoam nas pontas curvas e abrem no meio das retas.
 */
export function noContorno(i: number, a: number, escala = 1): [number, number] {
  const larg = 1;
  const alt = 1 / a;
  const raio = Math.min(larg, alt) / 2;
  const retaH = larg - 2 * raio;
  const retaV = alt - 2 * raio;
  const arco = (Math.PI * raio) / 2;
  const perimetro = 2 * retaH + 2 * retaV + 4 * arco;

  let s = ((((i * perimetro) / 9) % perimetro) + perimetro) % perimetro;
  const meiaBase = retaH / 2;
  let x = larg / 2;
  let y = alt;

  // do meio da BASE para a esquerda, e daí a volta inteira
  if (s <= meiaBase) {
    x = larg / 2 - s;
  } else if ((s -= meiaBase) <= arco) {
    const ang = s / raio;
    x = raio - raio * Math.sin(ang);
    y = alt - raio + raio * Math.cos(ang);
  } else if ((s -= arco) <= retaV) {
    x = 0;
    y = alt - raio - s;
  } else if ((s -= retaV) <= arco) {
    const ang = s / raio;
    x = raio - raio * Math.cos(ang);
    y = raio - raio * Math.sin(ang);
  } else if ((s -= arco) <= retaH) {
    x = raio + s;
    y = 0;
  } else if ((s -= retaH) <= arco) {
    const ang = s / raio;
    x = larg - raio + raio * Math.sin(ang);
    y = raio - raio * Math.cos(ang);
  } else if ((s -= arco) <= retaV) {
    x = larg;
    y = raio + s;
  } else if ((s -= retaV) <= arco) {
    const ang = s / raio;
    x = larg - raio + raio * Math.cos(ang);
    y = alt - raio + raio * Math.sin(ang);
  } else {
    s -= arco;
    x = larg / 2 + (meiaBase - s);
  }

  const pctX = (x / larg) * 100;
  const pctY = (y / alt) * 100;
  return [50 + (pctX - 50) * escala, 50 + (pctY - 50) * escala];
}

/** Os nove lugares no contorno, em % da arena. */
export function lugares(a: number): [number, number][] {
  return [0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => noContorno(i, a));
}

/**
 * ── Três direções por assento, e as cinco tentativas que levaram a elas ───────────────────────
 *
 * A ficha vai pela NORMAL ao contorno para dentro, as cartas na direção OPOSTA (para fora), e o
 * botão do dealer pela TANGENTE, no sentido que se afasta das cartas. Nenhuma divide direção com
 * outra, em nenhum dos nove lugares.
 *
 * O caminho até aqui, porque cada tentativa quebrou de um jeito que a seguinte tinha de evitar:
 *
 * 1. Perpendicular ao raio (o desenho da elipse): no estádio isso aponta para FORA do card nos
 *    assentos da base, que ficam todos na mesma altura -- 28px de vazamento em nove mãos.
 * 2. Horizontal para dentro: nas pontas a ficha também é quase horizontal, e as duas se
 *    cruzaram -- 1.107px².
 * 3. Perpendicular à ficha, para o lado com mais espaço: 432 mãos com problema caíram para 155, e
 *    sobrou o celular, com as cartas invadindo o pod do vizinho.
 * 4. Abrir a base deslocando a distribuição meio passo: piorou, 155 para 173.
 * 5. Radial para fora: as fichas passaram a se encontrar no miolo, porque a margem que a carta
 *    exigia comeu a arena -- 162 mãos, agora por dentro.
 *
 * A normal resolve o que o raio não resolvia: nas retas, as fichas de assentos vizinhos saem
 * PARALELAS em vez de convergirem para o centro (elas se encostavam, 2px² no iPhone).
 */
export function direcaoDaFicha(i: number, a: number): [number, number] {
  const [x, y] = noContorno(i, a);
  const alt = (1 / a) * 100;                       // a altura da arena, em % da largura
  const raio = Math.min(100, alt) / 2;
  const py = (y / 100) * alt;                      // % da altura -> % da largura

  const naRetaH = y < 0.5 || y > 99.5;
  const naRetaV = x < 0.5 || x > 99.5;
  // nas retas, a normal é perpendicular à reta
  if (naRetaH && !naRetaV) return [0, y > 50 ? -1 : 1];
  if (naRetaV && !naRetaH) return [x > 50 ? -1 : 1, 0];

  // nas pontas, a normal sai do centro da ponta
  const cx = x < 50 ? raio : 100 - raio;
  const cy = py < alt / 2 ? raio : alt - raio;
  const dx = x - cx;
  const dy = py - cy;
  const n = Math.hypot(dx, dy) || 1;
  return [-dx / n, -dy / n];
}

/** As cartas do herói saem na direção OPOSTA à ficha: para fora do contorno, onde a margem da
 *  arena reservou espaço para elas. */
export function direcaoDasCartas(i: number, a: number): [number, number] {
  const [fx, fy] = direcaoDaFicha(i, a);
  return [-fx, -fy];
}

/**
 * O botão do dealer sai pela TANGENTE, no sentido que se afasta das cartas.
 *
 * A tangente é a direção que nem a ficha nem as cartas ocupam. Mas ela tem dois sentidos, e
 * escolhendo sem critério o "D" caía sobre as cartas do próprio assento em oito das 81 mãos.
 */
export function direcaoDoDealer(i: number, a: number): [number, number] {
  const [fx, fy] = direcaoDaFicha(i, a);
  const t: [number, number] = [-fy, fx];
  const [, cy] = direcaoDasCartas(i, a);
  return Math.sign(t[1]) === Math.sign(cy) && cy !== 0 ? [-t[0], -t[1]] : t;
}

/**
 * A distância, do centro do pod, de algo com `w` x `h` que sai na direção `dir`.
 *
 * Não é `(pod + tamanho) / 2`: as caixas são retangulares, e em direção diagonal a separação útil
 * é a PROJEÇÃO no eixo dominante. Com a conta simples, dois círculos que não se tocam ainda tinham
 * as caixas se cruzando nos cantos. Medir pela caixa é pessimista de propósito.
 */
function distancia(dir: [number, number], pod: number, w: number, h: number): number {
  const [dx, dy] = dir;
  const horizontal = Math.abs(dx) >= Math.abs(dy);
  const eixo = horizontal ? Math.abs(dx) : Math.abs(dy);
  const tamanho = horizontal ? w : h;
  return (pod + tamanho) / 2 / (eixo || 1) + FOLGA;
}

/**
 * O botão do dealer fica ENCOSTADO no pod, com metade dele sobre a borda.
 *
 * A uma folga, ele alcança o assento vizinho: no celular a arena é pequena, e o medidor achou o
 * "D" de um assento da base tocando as cartas de um assento da ponta. Colado ele não alcança
 * ninguém, e é o que o GTO Wizard faz -- na captura do dono, o "D" do BTN encosta na borda do pod.
 * A sobreposição com o próprio pod é desenho, e o medidor tem essa exceção declarada.
 */
export function distanciaDoDealer(pod: number): number {
  return pod / 2;
}

export type Caixa = {
  nome: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

/** Largura aproximada de um texto em fonte mono: ~0,62em por caractere. Aproximação declarada, e
 *  generosa de propósito -- o medidor deve errar para o lado de acusar colisão que não existe. */
export function larguraDeTexto(texto: string, fonte: number): number {
  return texto.length * fonte * 0.62;
}

export type ConfigDoLayout = {
  w: number;
  h: number;
  /** índice (0..8) do lugar do herói; `-1` = nenhum */
  heroi: number;
  /** índice (0..8) do lugar com o botão; `-1` = nenhum */
  botao: number;
  /** quais lugares têm ficha de aposta, e com que texto */
  apostas?: { i: number; texto: string }[];
  /** o bloco de texto do centro ocupa espaço e entra na conta */
  centro?: boolean;
};

/**
 * O layout inteiro da mesa, em px: a arena, cada pod, as cartas do herói, o botão do dealer, cada
 * ficha de aposta, o bloco do centro e a faixa do histórico.
 *
 * É a ÚNICA fonte do desenho: o componente posiciona com estes números e o medidor de colisão
 * verifica estes mesmos números. Antes havia duas contas (px e `calc`) e um teste provando que
 * elas concordavam; agora não há o que divergir.
 */
export function layoutDaMesa(cfg: ConfigDoLayout) {
  const { w, h, heroi, botao, apostas = [], centro = true } = cfg;
  const a = arena(w, h);
  const pod = px("assento", w, h);
  const cw = px("cartaW", w, h);
  const ch = px("cartaH", w, h);
  const dl = px("dealer", w, h);
  const fichaD = px("ficha", w, h);
  const fFicha = px("fFicha", w, h);
  const larguraDasCartas = cw * 2 + 2;

  const ponto = (p: [number, number]): [number, number] => [
    a.x + (p[0] / 100) * a.w,
    a.y + (p[1] / 100) * a.h,
  ];

  const pods = lugares(a.aspecto).map((p, i) => {
    const [cx, cy] = ponto(p);
    return {
      i,
      cx,
      cy,
      caixa: { nome: `pod:${i}`, x: cx - pod / 2, y: cy - pod / 2, w: pod, h: pod } as Caixa,
    };
  });

  const caixas: Caixa[] = pods.map((p) => p.caixa);

  let cartas: Caixa | null = null;
  if (heroi >= 0 && heroi < 9) {
    const p = pods[heroi];
    const dir = direcaoDasCartas(heroi, a.aspecto);
    const d = distancia(dir, pod, larguraDasCartas, ch);
    cartas = {
      nome: `cartas:${heroi}`,
      x: p.cx + dir[0] * d - larguraDasCartas / 2,
      y: p.cy + dir[1] * d - ch / 2,
      w: larguraDasCartas,
      h: ch,
    };
    caixas.push(cartas);
  }

  let dealer: Caixa | null = null;
  if (botao >= 0 && botao < 9) {
    const p = pods[botao];
    const dir = direcaoDoDealer(botao, a.aspecto);
    const d = distanciaDoDealer(pod);
    dealer = {
      nome: `dealer:${botao}`,
      x: p.cx + dir[0] * d - dl / 2,
      y: p.cy + dir[1] * d - dl / 2,
      w: dl,
      h: dl,
    };
    caixas.push(dealer);
  }

  const fichas = apostas
    .filter(({ i }) => i >= 0 && i < 9)
    .map(({ i, texto }) => {
      const p = pods[i];
      const largura = fichaD + 4 + larguraDeTexto(texto, fFicha);
      const altura = Math.max(fichaD, fFicha * 1.2);
      const dir = direcaoDaFicha(i, a.aspecto);
      const d = distancia(dir, pod, largura, altura);
      const caixa: Caixa = {
        nome: `aposta:${i}`,
        x: p.cx + dir[0] * d - largura / 2,
        y: p.cy + dir[1] * d - altura / 2,
        w: largura,
        h: altura,
      };
      caixas.push(caixa);
      return { i, caixa };
    });

  const historico: Caixa = { nome: "historico", x: 0, y: 0, w, h: alturaDoHistorico(w, h) };
  caixas.push(historico);

  let miolo: Caixa | null = null;
  if (centro) {
    const altura =
      px("fSpot", w, h) * 1.35 + px("fPote", w, h) * 1.25 + px("fHist", w, h) * 1.35;
    // A largura do centro NÃO é só uma fração da arena: ela também respeita o que as fichas
    // ocupam por dentro. Com a mesa VERTICAL (o celular), as fichas das laterais entram na
    // horizontal e a fração de 46% já alcançava o texto -- 81 mãos com problema em 360px, 162 em
    // 320px. O limite sai da própria conta da ficha, e não de um número escolhido a olho.
    const fichaLarga = fichaD + 4 + larguraDeTexto("19.5", fFicha);
    const entrada = distancia([1, 0], pod, fichaLarga, Math.max(fichaD, fFicha * 1.2));
    const sobraNoMeio = Math.max(20, a.w - 2 * (entrada + fichaLarga / 2));
    const largura = Math.min(a.w * LARGURA_DO_CENTRO, sobraNoMeio);
    miolo = {
      nome: "centro",
      x: a.x + a.w / 2 - largura / 2,
      y: a.y + a.h / 2 - altura / 2,
      w: largura,
      h: altura,
    };
    caixas.push(miolo);
  }

  return { arena: a, pods, cartas, dealer, fichas, historico, centro: miolo, caixas };
}

/** Só as caixas, para o medidor de colisão. */
export function caixasDaMesa(cfg: ConfigDoLayout): Caixa[] {
  return layoutDaMesa(cfg).caixas;
}

/**
 * Os pares que PODEM se tocar, por desenho.
 *
 * Existe um só: o botão do dealer encosta no próprio pod. Declarar a exceção é o oposto de
 * afrouxar o medidor -- sem ela, eu teria de baixar o limite de área em TODOS os pares, e aí
 * qualquer sobreposição pequena de verdade passaria junto.
 */
export function podemEncostar(a: string, b: string): boolean {
  const par = [a.split(":")[0], b.split(":")[0]].sort().join("x");
  const mesmoAssento = a.split(":")[1] === b.split(":")[1];
  return par === "dealerxpod" && mesmoAssento;
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
