import { describe, it, expect } from "vitest";
import {
  ASPECTO_MAX,
  ASPECTO_MIN,
  arena,
  aspectoDaMesa,
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

  it("CONTROLE: a excecao do dealer vale SO para o proprio pod", () => {
    expect(podemEncostar("dealer:3", "pod:3")).toBe(true);
    expect(podemEncostar("pod:3", "dealer:3")).toBe(true);
    // e não para o pod do vizinho, nem para outros pares
    expect(podemEncostar("dealer:3", "pod:4")).toBe(false);
    expect(podemEncostar("cartas:3", "pod:3")).toBe(false);
    expect(podemEncostar("aposta:3", "centro")).toBe(false);
  });

  it("o aspecto ACOMPANHA o espaco, dentro da faixa", () => {
    // O pedido do dono, em três recados: "em telas menores, a mesa esta achatando a um ponto que
    // fica totalmente ilegivel", "temos que ter um limite minimo de achatamento", e a captura da
    // mesa VERTICAL deles com "e se reduzir muito, ele vira pra celular".
    expect(aspectoDaMesa(1000, 400)).toBeCloseTo(2.4, 6);   // largo: usa o próprio aspecto
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
