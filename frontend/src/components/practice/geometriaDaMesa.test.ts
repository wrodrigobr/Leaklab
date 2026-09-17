import { describe, it, expect } from "vitest";
import {
  ASPECTO_MAX,
  ENCOSTO_DA_CARTA,
  FOLGA,
  layoutDaMesa,
  ASPECTO_MIN,
  arena,
  aspectoDaMesa,
  alturaDoHistorico,
  margensDaArena,
  caixasDaMesa,
  direcaoDaFicha,
  direcaoDasCartas,
  direcaoDoDealer,
  lugares,
  podemEncostar,
  px,
  sobreposicao,
  vazamento,
  type Caixa,
} from "./geometriaDaMesa";

/**
 * O medidor de colisão da mesa do Prática.
 *
 * ── Por que ele existe ────────────────────────────────────────────────────────────────────────
 *
 * O dono: "melhorou mas vamos ter que ajustar assento por assento para nao haver sobreposições das
 * cartas, fichas, valores". Ajustar pela captura conserta o assento da captura, e o que não estava
 * naquela mão continua errado -- foi o que aconteceu nas duas primeiras rodadas.
 *
 * Aqui a varredura passa pelas 9 posições do herói contra as 9 do botão, em doze tamanhos de card,
 * e exige que nenhum par de caixas se sobreponha e que nada saia do card. A cada captura que ele
 * mandou, o tamanho dela entrou nesta lista -- e foi assim que apareceram as cartas fora do card no
 * celular (81 mãos de uma vez) e o achatamento da janela baixa.
 *
 * ── O que a medição decidiu nesta frente ──────────────────────────────────────────────────────
 *
 * O desenho passou por cinco versões num dia, e nenhuma foi escolhida a olho: contorno (elipse
 * para estádio), direção de cada elemento (cinco tentativas), aspecto (fixo para faixa), margem da
 * arena, e o mínimo de card em que a mesa cabe. Os números estão nos comentários da geometria, com
 * o que cada tentativa quebrou.
 */

/** Os tamanhos que importam. Cada um entrou aqui por uma captura ou uma medição. */
const CARDS = [
  { nome: "4 mesas (2x2) em 1680", w: 830, h: 440 },
  { nome: "4 mesas no monitor do dono (captura 17/09)", w: 910, h: 375 },
  { nome: "janela ACHATADA ao extremo", w: 1820, h: 260 },
  { nome: "4 mesas em 1366x768", w: 683, h: 330 },
  { nome: "2 mesas lado a lado", w: 830, h: 880 },
  { nome: "1 mesa no monitor", w: 1660, h: 880 },
  { nome: "1 mesa larga e baixa", w: 1660, h: 400 },
  { nome: "celular retrato (iPhone 12/13)", w: 390, h: 480 },
  { nome: "celular retrato alto", w: 390, h: 700 },
  { nome: "celular estreito (360)", w: 360, h: 522 },
  { nome: "celular estreito (320)", w: 320, h: 460 },
  { nome: "celular grande", w: 430, h: 620 },
  { nome: "card no minimo de altura", w: 830, h: 300 },
  { nome: "tablet", w: 600, h: 300 },
];

/** Aposta em TODOS os nove lugares, com valores largos: o texto da ficha é o que cresce mais e
 *  colide primeiro. */
const APOSTAS = [0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => ({
  i,
  texto: i % 2 ? "19.5" : "2.2",
}));

function conflitos(caixas: Caixa[], w: number, h: number): string[] {
  const achados: string[] = [];
  for (let a = 0; a < caixas.length; a++) {
    for (let b = a + 1; b < caixas.length; b++) {
      const area = sobreposicao(caixas[a], caixas[b]);
      // `podemEncostar` tem UM par declarado: o botão do dealer sobre o próprio pod, que é o
      // desenho do GTO Wizard. A exceção é nominal de propósito -- afrouxar o limite de área para
      // todos os pares deixaria passar qualquer sobreposição pequena de verdade.
      if (area > 1 && !podemEncostar(caixas[a].nome, caixas[b].nome)) {
        achados.push(`${caixas[a].nome} x ${caixas[b].nome} = ${Math.round(area)}px2`);
      }
    }
    const fora = vazamento(caixas[a], w, h);
    if (fora > 1) achados.push(`${caixas[a].nome} sai ${Math.round(fora)}px do card`);
  }
  return achados;
}

describe("a geometria da mesa", () => {
  it("nenhuma caixa se sobrepoe nem sai do card, em NENHUMA das 81 maos", () => {
    const porTipo = new Map<string, number>();
    let maos = 0;
    for (const card of CARDS) {
      for (let heroi = 0; heroi < 9; heroi++) {
        for (let botao = 0; botao < 9; botao++) {
          const ruins = conflitos(
            caixasDaMesa({ w: card.w, h: card.h, heroi, botao, apostas: APOSTAS }),
            card.w,
            card.h,
          );
          if (ruins.length) maos++;
          for (const r of ruins) {
            // o resumo por TIPO é o que diz onde está a causa: "cartas x centro" em 12 mãos é um
            // defeito, não doze
            const tipo = `${card.nome}: ${r
              .replace(/:\d+/g, "")
              .replace(/ = \d+px2/, "")
              .replace(/ sai \d+px/, " sai")}`;
            porTipo.set(tipo, (porTipo.get(tipo) ?? 0) + 1);
          }
        }
      }
    }
    const resumo = [...porTipo.entries()].map(([k, n]) => `${k} (${n}x)`).join("\n");
    expect(resumo, `${maos} maos com problema`).toBe("");
  });

  it("CONTROLE: o medidor ACUSA sobreposicao e vazamento quando existem", () => {
    // Regra 1 da casa: o medidor precisa provar que detecta. Sem estes, a varredura acima poderia
    // passar verde medindo nada -- o "zero tranquilizador".
    const a: Caixa = { nome: "pod:0", x: 0, y: 0, w: 10, h: 10 };
    const b: Caixa = { nome: "aposta:1", x: 5, y: 5, w: 10, h: 10 };
    expect(sobreposicao(a, b)).toBe(25);
    expect(conflitos([a, b], 100, 100).length).toBe(1);
    // encostar sem área não é sobreposição
    expect(sobreposicao(a, { nome: "aposta:2", x: 10, y: 0, w: 10, h: 10 })).toBe(0);
    // e o vazamento é medido nas quatro bordas
    expect(vazamento({ nome: "x", x: -5, y: 0, w: 10, h: 10 }, 100, 100)).toBe(5);
    expect(vazamento({ nome: "x", x: 95, y: 0, w: 10, h: 10 }, 100, 100)).toBe(5);
    expect(vazamento({ nome: "x", x: 0, y: 0, w: 10, h: 10 }, 100, 100)).toBe(0);
  });

  it("CONTROLE: quem pode encostar so encosta no PROPRIO pod", () => {
    // Duas excecoes declaradas, e as duas sao desenho: o botao do dealer e a carta do heroi nascem
    // NO assento. Em 17/09 a carta entrou na lista, para devolver altura a mesa ("a parte superior
    // da mesa pode encostar mais nas infos de cima" / "a parte de baixo...encostar nos botoes de
    // acao...assim ela ganha em altura").
    expect(podemEncostar("dealer:3", "pod:3")).toBe(true);
    expect(podemEncostar("pod:3", "dealer:3")).toBe(true);
    expect(podemEncostar("cartas:3", "pod:3")).toBe(true);
    expect(podemEncostar("pod:3", "cartas:3")).toBe(true);
    // e NUNCA no pod do vizinho, que e o que separa desenho de defeito
    expect(podemEncostar("dealer:3", "pod:4")).toBe(false);
    expect(podemEncostar("cartas:3", "pod:4")).toBe(false);
    // nem entre si: os dois encostados no mesmo pod podem se alcancar, e isso e defeito -- e o que
    // limita o encosto a 10px (a varredura acusa 2 maos em 14px e 40 em 16px, todas `cartas x
    // dealer` no celular, onde o pod e pequeno)
    expect(podemEncostar("cartas:3", "dealer:3")).toBe(false);
    expect(podemEncostar("aposta:3", "centro")).toBe(false);
  });

  it("o aspecto ACOMPANHA o espaco, dentro da faixa", () => {
    // O pedido do dono, em três recados: "em telas menores, a mesa esta achatando a um ponto que
    // fica totalmente ilegivel", "temos que ter um limite minimo de achatamento", e a captura da
    // mesa VERTICAL deles com "e se reduzir muito, ele vira pra celular".
    expect(aspectoDaMesa(1000, 400)).toBeCloseTo(2.5, 6);   // largo: usa o próprio aspecto
    expect(aspectoDaMesa(400, 600)).toBeCloseTo(0.667, 3);  // alto: a mesa fica VERTICAL
    // e a faixa segura as pontas: sem ela a mesa viraria uma fita
    expect(aspectoDaMesa(1000, 50)).toBe(ASPECTO_MAX);
    expect(aspectoDaMesa(50, 1000)).toBe(ASPECTO_MIN);
    expect(ASPECTO_MIN).toBeLessThan(1);
    expect(ASPECTO_MAX).toBeGreaterThan(2);
  });

  it("a mesa NUNCA deforma fora da faixa, e nunca sai do card", () => {
    for (const { w, h, nome } of [
      ...CARDS,
      { nome: "extremo baixo", w: 830, h: 150 },
      { nome: "extremo estreito", w: 200, h: 700 },
    ]) {
      const a = arena(w, h);
      expect(a.w, `${nome} ficou sem largura`).toBeGreaterThan(0);
      expect(a.h, `${nome} ficou sem altura`).toBeGreaterThan(0);
      expect(a.w / a.h, `${nome} deformou`).toBeGreaterThanOrEqual(ASPECTO_MIN - 0.001);
      expect(a.w / a.h, `${nome} deformou`).toBeLessThanOrEqual(ASPECTO_MAX + 0.001);
      expect(a.x, `${nome} saiu pela esquerda`).toBeGreaterThanOrEqual(0);
      expect(a.y, `${nome} saiu pelo topo`).toBeGreaterThanOrEqual(0);
      expect(a.x + a.w, `${nome} saiu pela direita`).toBeLessThanOrEqual(w + 0.001);
      expect(a.y + a.h, `${nome} saiu por baixo`).toBeLessThanOrEqual(h + 0.001);
    }
  });

  it("a arena ENCOSTA no espaco livre: sobra so a margem que o desenho pede", () => {
    // O bug de 17/09, nas palavras do dono: "a mesa nao esta ocupando o espaco disponivel no seu
    // box....temos que aproveitar mais os espacos pra mesa ficar maior". No card dele (910x375) a
    // arena era 407x170 -- 20% da area do card, com 252px sobrando de CADA lado.
    //
    // Duas causas, e este caso cobre as duas: a margem era um numero igual nos quatro lados (180
    // dos 350px de altura util), e o teto do aspecto em 2,4 recusava os 3,57 que o espaco oferecia.
    for (const card of CARDS) {
      const a = arena(card.w, card.h);
      const m = margensDaArena(card.w, card.h, a.aspecto, a.w, a.h);
      const livreW = card.w - m.esq - m.dir;
      const livreH = card.h - alturaDoHistorico(card.w, card.h) - m.topo - m.base;
      const oferecido = livreW / livreH;
      if (oferecido >= ASPECTO_MIN && oferecido <= ASPECTO_MAX) {
        // dentro da faixa a mesa toma TUDO: os dois eixos encostam
        expect(a.w, `${card.nome}: sobrou largura`).toBeGreaterThan(livreW - 2);
        expect(a.h, `${card.nome}: sobrou altura`).toBeGreaterThan(livreH - 2);
      } else {
        // fora da faixa ela para de deformar, mas o eixo APERTADO ainda encosta -- e a sobra fica
        // no outro, que é o limite mínimo de achatamento que ele pediu antes
        const apertado = oferecido > ASPECTO_MAX ? a.h : a.w;
        const livre = oferecido > ASPECTO_MAX ? livreH : livreW;
        expect(apertado, `${card.nome}: nao encostou em nenhum eixo`).toBeGreaterThan(livre - 2);
      }
    }
  });

  it("o card do dono (910x375) usa a largura que o espaco OFERECE", () => {
    // Este caso ancora o TETO, que o anterior nao ancora: fora da faixa ele aceita a mesa parar de
    // deformar, e foi isso que escondeu o problema. Com o teto em 2,4 a arena media 493 de 733px
    // livres e sobravam 209px de cada lado -- o card oferece 3,57, e o teto tem de cobrir isso.
    const a = arena(910, 375);
    const m = margensDaArena(910, 375, a.aspecto, a.w, a.h);
    const livreW = 910 - m.esq - m.dir;
    expect(a.w, "a arena recusou a largura livre").toBeGreaterThan(livreW - 2);
    expect(
      (a.w * a.h) / (910 * 375),
      "a mesa voltou a ocupar pouco do card",
    ).toBeGreaterThan(0.4);
  });

  it("a margem e medida LADO A LADO, e nao um numero igual nos quatro", () => {
    // O que pendura de um assento depende da DIRECAO dele: na reta as cartas saem para cima ou
    // para baixo, e pendura a ALTURA de uma carta; so na ponta elas saem para o lado, e pendura a
    // LARGURA das duas. Reservar a largura em cima é reservar espaço para algo que nunca vai lá.
    for (const { w, h, nome } of CARDS) {
      const a = arena(w, h);
      const m = margensDaArena(w, h, a.aspecto, a.w, a.h);
      expect(m.topo, `${nome}: a margem de cima e a de lado`).toBeLessThan(m.esq);
      expect(m.base, `${nome}: a margem de baixo e a de lado`).toBeLessThan(m.dir);
    }
  });

  it("a MARGEM da arena sai da mesma conta da carta que o LAYOUT", () => {
    // O defeito que quase passou: o primeiro experimento de encosto da carta passou verde SEM
    // mudar a mesa. A conta da distancia da carta existia em dois lugares -- o layout, que
    // desenha, e a margem, que reserva -- e eu apliquei o encosto so no layout. Regra 5 dentro do
    // codigo do mesmo dia.
    //
    // Este caso ancora na CONTA, e nao no efeito: a margem de cima tem de ser exatamente o quanto
    // a carta que o layout desenhou sobe acima da arena, mais a folga da borda do card.
    const w = 910;
    const h = 385;
    const L = layoutDaMesa({ w, h, heroi: 4, botao: 0, apostas: [] });   // assento 4 = reta de cima
    const m = margensDaArena(w, h, L.arena.aspecto, L.arena.w, L.arena.h);
    expect(L.cartas, "o assento 4 tem de ter carta").toBeTruthy();
    const sobeAcimaDaArena = L.arena.y - L.cartas!.y;
    expect(m.topo, "a margem reserva um valor que o desenho nao usa")
      .toBeCloseTo(sobeAcimaDaArena + FOLGA, 1);
    // e o encosto tem de valer: em zero a mesa perde a altura que o dono pediu de volta
    expect(ENCOSTO_DA_CARTA).toBeGreaterThan(0);
  });

  it("o contorno e um ESTADIO: as retas ficam no eixo MAIOR", () => {
    // O pedido, com a captura deles: "ideal e que as bordas superiores e inferiores da mesa fiquem
    // retas, e so curvemos as laterais...assim ganhamos espaco". Ganha porque os assentos de uma
    // reta ficam na MESMA altura, em vez de descerem com a curva da elipse.
    const larga = lugares(2.4);
    const nasRetasH = larga.filter(([, y]) => y < 0.5 || y > 99.5);
    expect(nasRetasH.length, "mesa larga sem lugar nenhum nas retas de cima/baixo")
      .toBeGreaterThanOrEqual(4);
    const alturas = new Set(nasRetasH.map(([, y]) => Math.round(y)));
    expect(alturas.size, "os lugares das retas deviam estar em 0% ou 100%").toBeLessThanOrEqual(2);

    // com a mesa VERTICAL (o celular), as retas viram as LATERAIS
    const alta = lugares(0.62);
    const nasRetasV = alta.filter(([x]) => x < 0.5 || x > 99.5);
    expect(nasRetasV.length, "mesa alta sem lugar nenhum nas laterais retas")
      .toBeGreaterThanOrEqual(2);

    // e nenhum lugar sai da arena, em nenhum aspecto
    for (const a of [2.4, 1.0, 0.62]) {
      for (const [x, y] of lugares(a)) {
        expect(x).toBeGreaterThanOrEqual(-0.01);
        expect(x).toBeLessThanOrEqual(100.01);
        expect(y).toBeGreaterThanOrEqual(-0.01);
        expect(y).toBeLessThanOrEqual(100.01);
      }
    }
  });

  it("as TRES direcoes de cada assento nunca coincidem", () => {
    // Dar a mesma direção para duas delas colide SEMPRE, e não em caso raro: o medidor mostrou isso
    // cinco vezes enquanto esta geometria se acertava (28px de vazamento, 1.107px² de cartas sobre
    // a ficha, 155 mãos no celular, 173 ao abrir a base, 162 com as fichas no miolo).
    for (const a of [2.4, 1.6, 1.0, 0.62]) {
      for (let i = 0; i < 9; i++) {
        const f = direcaoDaFicha(i, a);
        const c = direcaoDasCartas(i, a);
        const d = direcaoDoDealer(i, a);
        const cos = (u: [number, number], v: [number, number]) => u[0] * v[0] + u[1] * v[1];
        expect(Math.hypot(f[0], f[1]), `ficha nao unitaria no lugar ${i}`).toBeCloseTo(1, 6);
        // cartas são o oposto da ficha, e o botão é perpendicular aos dois
        expect(cos(f, c), `ficha x cartas no lugar ${i} (aspecto ${a})`).toBeCloseTo(-1, 6);
        expect(cos(f, d), `ficha x botao no lugar ${i} (aspecto ${a})`).toBeCloseTo(0, 6);
        expect(cos(c, d), `cartas x botao no lugar ${i} (aspecto ${a})`).toBeCloseTo(0, 6);
      }
    }
  });

  it("as medidas respeitam piso e teto", () => {
    // O piso mantém a mesa legível num card pequeno; o teto impede um monitor largo de virar
    // cartaz. Os dois agem, e é por isso que o piso de carta não pode ser baixado para atender um
    // aparelho antigo: ele age no celular COMUM também.
    expect(px("assento", 200, 100)).toBe(34);
    expect(px("assento", 4000, 4000)).toBe(76);
    expect(px("assento", 830, 440)).toBeCloseTo(53.68, 1);
    expect(px("assento", 830, 880)).toBeCloseTo(54.78, 1);
  });

  it("o layout responde a um card SEM heroi e SEM botao", () => {
    // A mesa abre assim por um instante enquanto o spot carrega, e um `-1` virando índice de array
    // colocaria cartas no assento errado ou quebraria o render.
    const caixas = caixasDaMesa({ w: 830, h: 440, heroi: -1, botao: -1, apostas: [] });
    expect(caixas.some((c) => c.nome.startsWith("cartas"))).toBe(false);
    expect(caixas.some((c) => c.nome.startsWith("dealer"))).toBe(false);
    expect(caixas.filter((c) => c.nome.startsWith("pod")).length).toBe(9);
    expect(conflitos(caixas, 830, 440)).toEqual([]);
  });
});
