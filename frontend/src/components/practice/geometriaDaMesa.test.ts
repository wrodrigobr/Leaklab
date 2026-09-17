import { describe, it, expect } from "vitest";
import {
  ANGULOS,
  arena,
  arenaCss,
  FOLGA,
  LUGARES,
  PARAMS,
  caixasDaMesa,
  deslocamentoDasCartasCss,
  deslocamentoDoDealerCss,
  direcaoDaFicha,
  direcaoDasCartas,
  direcaoDoDealer,
  distanciaDasCartas,
  distanciaDoDealer,
  M,
  medida,
  px,
  sobreposicao,
  vazamento,
  type Caixa,
} from "./geometriaDaMesa";

/**
 * O pedido do dono: "melhorou mas vamos ter que ajustar assento por assento para nao haver
 * sobreposições das cartas, fichas, valores".
 *
 * Ajustar pela captura conserta o assento que estava na captura. Aqui a varredura passa pelas 9
 * posições do herói contra as 9 do botão, em três tamanhos de card, e exige que nenhum par de
 * caixas se sobreponha e que nada saia do card. São 81 mãos por tamanho, e a captura dele era
 * uma delas.
 */

/** Os tamanhos que importam, medidos na tela do dono (1674 de largura). */
const CARDS = [
  { nome: "4 mesas (2x2)", w: 830, h: 440 },
  { nome: "2 mesas (lado a lado)", w: 830, h: 880 },
  { nome: "4 mesas em 1366x768", w: 683, h: 330 },
  { nome: "1 mesa", w: 1660, h: 880 },
  // ── Celular (17/09) ──────────────────────────────────────────────────────────────────────
  // O dono abriu no telefone e as cartas do heroi apareceram FORA do card, uma delas por cima do
  // historico. A varredura nao pegava porque nenhum tamanho aqui tinha proporcao de celular: o
  // card mais estreito era 683x330, que e largo e baixo, e no telefone ele e estreito e ALTO.
  // Uma mesa ocupando a tela do iPhone menos a barra e os botoes de acao:
  { nome: "celular retrato (iPhone 12/13)", w: 390, h: 560 },
  { nome: "celular retrato grande", w: 430, h: 620 },
  { nome: "celular estreito (360, o minimo)", w: 360, h: 522 },
  { nome: "celular paisagem", w: 844, h: 300 },
];

/** Uma mão com aposta em vários assentos, incluindo valores largos (o texto da ficha é o que
 *  cresce mais e colide primeiro). */
const APOSTAS = [
  { i: 0, texto: "0.5" },
  { i: 1, texto: "2.2" },
  { i: 2, texto: "19.5" },
  { i: 3, texto: "8" },
  { i: 4, texto: "11.7" },
  { i: 5, texto: "0.5" },
  { i: 6, texto: "2.2" },
  { i: 7, texto: "19.5" },
  { i: 8, texto: "1" },
];

function conflitos(caixas: Caixa[], w: number, h: number) {
  const achados: string[] = [];
  for (let a = 0; a < caixas.length; a++) {
    for (let b = a + 1; b < caixas.length; b++) {
      // duas coisas do MESMO assento podem encostar? não: é exatamente o que o dono relatou.
      const area = sobreposicao(caixas[a], caixas[b]);
      if (area > 1) {
        achados.push(
          `${caixas[a].nome} x ${caixas[b].nome} = ${Math.round(area)}px2`,
        );
      }
    }
    const fora = vazamento(caixas[a], w, h);
    if (fora > 1) achados.push(`${caixas[a].nome} sai ${Math.round(fora)}px do card`);
  }
  return achados;
}

describe("a geometria da mesa", () => {
  it("nenhuma caixa se sobrepoe nem sai do card, em NENHUMA das 81 maos", () => {
    const falhas: string[] = [];
    for (const card of CARDS) {
      for (let heroi = 0; heroi < 9; heroi++) {
        for (let botao = 0; botao < 9; botao++) {
          const caixas = caixasDaMesa({
            w: card.w,
            h: card.h,
            heroi,
            botao,
            apostas: APOSTAS,
          });
          const ruins = conflitos(caixas, card.w, card.h);
          if (ruins.length) {
            falhas.push(`${card.nome} heroi=${heroi} botao=${botao}: ${ruins.join(" | ")}`);
          }
        }
      }
    }
    expect(falhas.slice(0, 40).join("\n"), `${falhas.length} maos com problema`).toBe("");
  });

  it("360px de largura e o MINIMO, e a fronteira esta medida", () => {
    // Abaixo de 360 as cartas do heroi encostam no pod do assento VIZINHO: com a arena pequena os
    // vizinhos ficam a ~85px, e as duas cartas mais a folga passam disso.
    //
    // Encolher as cartas resolveria (medido: 20x26 faz 320px caber), e a opcao foi recusada de
    // proposito. O piso das medidas age no celular COMUM tambem -- em 390x565 a fracao da largura
    // ja cai abaixo do piso --, entao baixar o piso para atender um aparelho de 2016 encolheria a
    // carta de 26 para 20px em todo telefone. As cartas sao a informacao que decide a mao.
    //
    // 360 cobre Galaxy S8 em diante e iPhone SE 2020; fica fora o iPhone SE de 2016 e o iPhone 5,
    // e neles a sobreposicao e visual, nao quebra. Este caso existe para que o limite seja
    // DECLARADO: quem mexer na geometria ve onde ela para de caber.
    const problemas = (w: number, h: number) => {
      let n = 0;
      for (let heroi = 0; heroi < 9; heroi++) {
        const caixas = caixasDaMesa({ w, h, heroi, botao: 0, apostas: APOSTAS });
        n += conflitos(caixas, w, h).length;
      }
      return n;
    };
    expect(problemas(360, 522), "360px tem de caber").toBe(0);
    // CONTROLE: a fronteira existe, e a medicao a ACHA. Sem isto, o caso acima poderia passar
    // verde porque a varredura nao mede nada.
    expect(problemas(320, 464), "em 320px a colisao e conhecida").toBeGreaterThan(0);
  });

  it("CONTROLE: o medidor ACUSA o botao do dealer no canto do pod, que era o layout antigo", () => {
    // Regra 1 da casa: o medidor precisa provar que detecta. O "D" era `-bottom-0.5 -left-1`
    // sobre o pod, e na captura do dono ele cobre a borda do assento do BTN. Se a varredura
    // acima passasse verde com ISTO também, ela não estaria medindo nada.
    const w = 830;
    const h = 440;
    const pod = px("assento", w, h);
    const dl = px("dealer", w, h);
    const [x, y] = LUGARES[6];
    const cx = (x / 100) * w;
    const cy = (y / 100) * h;
    const comoEraAntes: Caixa[] = [
      { nome: "pod:6", x: cx - pod / 2, y: cy - pod / 2, w: pod, h: pod },
      // canto inferior esquerdo, 2px para fora: exatamente o `-bottom-0.5 -left-1`
      { nome: "dealer:6(antigo)", x: cx - pod / 2 - 4, y: cy + pod / 2 - dl + 2, w: dl, h: dl },
    ];
    expect(conflitos(comoEraAntes, w, h).length).toBeGreaterThan(0);
  });

  it("CONTROLE: o medidor ACUSA as cartas empurrando o pod fora do lugar", () => {
    // O outro defeito da captura: pod e cartas no mesmo flex centrado no ponto do trilho faz o
    // POD sair da elipse (o UTG+2 dele aparece fora da linha). Reproduzido aqui: o conjunto
    // centrado deixa o pod deslocado para a esquerda, e o medidor tem de ver a caixa fora.
    const w = 830;
    const h = 440;
    const pod = px("assento", w, h);
    const cw = px("cartaW", w, h);
    const larguraDoConjunto = pod + 4 + (cw * 2 + 2);
    const [x, y] = LUGARES[2]; // o lugar mais à esquerda
    const cx = (x / 100) * w;
    const cy = (y / 100) * h;
    const comoEraAntes: Caixa[] = [
      { nome: "pod:2(no flex)", x: cx - larguraDoConjunto / 2, y: cy - pod / 2, w: pod, h: pod },
    ];
    // o pod deslocado sai do card pela esquerda
    expect(vazamento(comoEraAntes[0], w, h)).toBeGreaterThan(0);
  });

  it("CONTROLE: o medidor ACUSA sobreposicao que existe, e so ela", () => {
    const a: Caixa = { nome: "a", x: 0, y: 0, w: 10, h: 10 };
    const b: Caixa = { nome: "b", x: 5, y: 5, w: 10, h: 10 };
    const c: Caixa = { nome: "c", x: 20, y: 20, w: 10, h: 10 };
    expect(sobreposicao(a, b)).toBe(25);
    expect(sobreposicao(a, c)).toBe(0);
    // encostar (sem area) nao e sobreposicao
    expect(sobreposicao(a, { nome: "d", x: 10, y: 0, w: 10, h: 10 })).toBe(0);
  });

  it("o botao do dealer sai para FORA do trilho", () => {
    // Para fora ele nao disputa espaco com ninguem: a ficha vai para dentro e as cartas pela
    // perpendicular. O botao ja esteve na tangente, e la encontrava as cartas do assento VIZINHO
    // nas pontas da elipse, onde os vizinhos ficam a ~111px um do outro.
    for (let i = 0; i < 9; i++) {
      const [x, y] = LUGARES[i];
      const [dx, dy] = direcaoDoDealer(i);
      const n = Math.hypot(x - 50, y - 50);
      expect((dx * (x - 50) + dy * (y - 50)) / n, `lugar ${i}`).toBeCloseTo(1, 6);
    }
  });

  it("o CSS do botao do dealer RESOLVE no mesmo numero que a conta em px", () => {
    // A fórmula da distância existe duas vezes: em px (`distanciaDoDealer`, que o medidor usa) e
    // em `calc` (o que o navegador resolve). Duas escritas da mesma regra é o defeito da regra 5,
    // e aqui a segunda é conferida contra a primeira: a string é resolvida com valores concretos.
    //
    // Sem este teste, o medidor poderia aprovar 81 mãos de uma mesa que o jogador não vê.
    const resolve = (css: string, w: number, h: number) => {
      const s = css
        .split(M.assento).join(String(px("assento", w, h)))
        .split(M.dealer).join(String(px("dealer", w, h)))
        .split("calc(").join("(")
        .split("px").join("");
      // eslint-disable-next-line no-new-func
      return Function(`"use strict"; return (${s});`)() as number;
    };

    for (const { w, h } of CARDS) {
      const pod = px("assento", w, h);
      const dl = px("dealer", w, h);
      for (let i = 0; i < 9; i++) {
        const [dx, dy] = direcaoDoDealer(i);
        const d = distanciaDoDealer(i, pod, dl);
        const css = deslocamentoDoDealerCss(i);
        expect(resolve(css.x, w, h), `x do lugar ${i} em ${w}x${h}`).toBeCloseTo(dx * d, 6);
        expect(resolve(css.y, w, h), `y do lugar ${i} em ${w}x${h}`).toBeCloseTo(dy * d, 6);
      }
    }
  });

  it("a ARENA em CSS resolve na mesma arena da conta em px", () => {
    // A terceira regra escrita duas vezes (com a distancia do botao e a das cartas): `arena` em px
    // para o medidor, `arenaCss` em `calc` para o navegador. Se divergirem, o medidor aprova 81
    // maos de uma mesa que nao existe -- e a divergencia nao aparece em nenhuma captura, porque
    // os dois desenhos sao plausiveis.
    const resolve = (css: string, w: number, h: number) =>
      Function(
        `"use strict"; return (${css
          .split(M.assento).join(String(px("assento", w, h)))
          .split(M.dealer).join(String(px("dealer", w, h)))
          .split(M.fHist).join(String(px("fHist", w, h)))
          .split("calc(").join("(")
          .split("px").join("")});`,
      )() as number;

    for (const { w, h } of CARDS) {
      const a = arena(w, h);
      const css = arenaCss();
      expect(resolve(css.left, w, h), `left em ${w}x${h}`).toBeCloseTo(a.x, 6);
      expect(resolve(css.top, w, h), `top em ${w}x${h}`).toBeCloseTo(a.y, 6);
      // right e bottom sao margens: o que sobra tem de dar a largura e a altura da arena
      expect(w - a.x - resolve(css.right, w, h), `largura em ${w}x${h}`).toBeCloseTo(a.w, 6);
      expect(h - a.y - resolve(css.bottom, w, h), `altura em ${w}x${h}`).toBeCloseTo(a.h, 6);
    }
  });

  it("a arena SEMPRE sobra espaco para o que pendura nela", () => {
    // O piso e o teto das medidas podem, em card minusculo, deixar a margem maior que o proprio
    // card -- e ai a arena teria largura negativa e a mesa desapareceria. O guarda cobre do card
    // absurdo ao gigante.
    for (const [w, h] of [[220, 140], [400, 200], [683, 330], [830, 440], [1660, 880], [3000, 2000]]) {
      const a = arena(w, h);
      expect(a.w, `largura da arena em ${w}x${h}`).toBeGreaterThan(0);
      expect(a.h, `altura da arena em ${w}x${h}`).toBeGreaterThan(0);
    }
  });

  it("a medida em px e a MESMA conta da string de CSS", () => {
    // Uma tabela, dois consumidores. Se `px` divergir de `medida`, o medidor mede uma mesa que o
    // jogador não vê -- o pior defeito possível numa ferramenta de medição.
    expect(medida(PARAMS.assento)).toBe("clamp(34px, min(6.6cqw, 12.2cqh), 76px)");
    // 830x440: a altura é quem limita (12.2% de 440 = 53.7 < 6.6% de 830 = 54.8)
    expect(px("assento", 830, 440)).toBeCloseTo(53.68, 1);
    // 830x880: a largura limita
    expect(px("assento", 830, 880)).toBeCloseTo(54.78, 1);
    // card minúsculo: o piso segura
    expect(px("assento", 200, 100)).toBe(34);
    // card enorme: o teto segura
    expect(px("assento", 4000, 4000)).toBe(76);
  });

  it("a ficha sai do POD, para dentro, e nao numa fracao do raio", () => {
    // A fracao do raio amarrava a distancia ao tamanho da mesa, e quebrou nas duas pontas: fichas
    // orfas no meio do feltro quando a fracao era pequena, e fichas por cima do pod no celular,
    // onde a arena e pequena (52px2 medidos em 320px de largura).
    for (let i = 0; i < 9; i++) {
      const [x, y] = LUGARES[i];
      const [dx, dy] = direcaoDaFicha(i);
      const n = Math.hypot(x - 50, y - 50);
      // para DENTRO: contra a direcao do ponto
      expect((dx * (x - 50) + dy * (y - 50)) / n, `lugar ${i}`).toBeCloseTo(-1, 6);
      // e oposta ao botao do dealer, que sai para fora
      const [ex, ey] = direcaoDoDealer(i);
      expect(dx * ex + dy * ey, `lugar ${i}`).toBeCloseTo(-1, 6);
    }
  });

  it("a medida em px e a MESMA conta da string de CSS", () => {
    // Uma tabela, dois consumidores. Se `px` divergir de `medida`, o medidor mede uma mesa que o
    // jogador não vê -- o pior defeito possível numa ferramenta de medição.
    expect(medida(PARAMS.assento)).toBe("clamp(34px, min(6.6cqw, 12.2cqh), 76px)");
    // 830x440: a altura é quem limita (12.2% de 440 = 53.7 < 6.6% de 830 = 54.8)
    expect(px("assento", 830, 440)).toBeCloseTo(53.68, 1);
    // 830x880: a largura limita
    expect(px("assento", 830, 880)).toBeCloseTo(54.78, 1);
    // card minúsculo: o piso segura
    expect(px("assento", 200, 100)).toBe(34);
    // card enorme: o teto segura
    expect(px("assento", 4000, 4000)).toBe(76);
  });

  it("os nove lugares estao SOBRE a elipse que preenche a arena", () => {
    LUGARES.forEach(([x, y], i) => {
      // em % da arena, a elipse tem raio 50 nos dois eixos: o ponto esta na borda dela
      const r = Math.hypot((x - 50) / 50, (y - 50) / 50);
      expect(r, `lugar ${i}`).toBeCloseTo(1, 6);
    });
    expect(ANGULOS.length).toBe(9);
  });
});
