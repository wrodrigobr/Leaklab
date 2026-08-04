import { describe, it, expect } from "vitest";
import { custoDePagar, potOddsExigidas } from "./cardLogic";

/**
 * O que o jogador PAGA nao e o tamanho da aposta do vilao.
 *
 * `facing_bet` e o to-total (identifica o no GTO); o custo e o to-total menos o que o hero
 * ja tem na frente. A tela do drill calculava pot odds com o tamanho e por isso exigia
 * equity de 27,2% numa decisao real que custava 5,4% (mao 93440400037).
 */
describe("custoDePagar", () => {
  it("usa o custo quando ele existe, mesmo divergindo do tamanho da aposta", () => {
    // BB contra open de 2bb: a aposta e 2bb, o BB paga 1bb.
    expect(custoDePagar({ facing_bet: 2.0, facing_to_call_bb: 1.0 })).toBe(1.0);
  });

  it("cai no facing_bet em decisao antiga (coluna NULL), nunca em zero", () => {
    expect(custoDePagar({ facing_bet: 2.5, facing_to_call_bb: null })).toBe(2.5);
    expect(custoDePagar({ facing_bet: 2.5 })).toBe(2.5);
  });

  it("respeita custo ZERO — `??` e nao `||`", () => {
    // Ninguem apostou: pagar custa nada. Com `||` isto cairia no fallback e mostraria 3bb.
    expect(custoDePagar({ facing_bet: 3.0, facing_to_call_bb: 0 })).toBe(0);
  });

  it("sem nenhum dos dois, devolve zero em vez de NaN", () => {
    expect(custoDePagar({})).toBe(0);
  });
});

describe("potOddsExigidas", () => {
  it("soma o custo por fora do pote, que ja contem a aposta enfrentada", () => {
    // pote 12bb (aposta de 5 inclusa), paga-se 5 -> 5/17
    expect(potOddsExigidas(12, 5)).toBeCloseTo(5 / 17, 6);
  });

  it("o caso do relato: custo pequeno sobre pote grande nao vira exigencia alta", () => {
    // Hero subiu para 1.600 e leva all-in de 1.877,41: paga 0,69bb num pote de 11,2bb.
    const comCusto  = potOddsExigidas(11.19, 0.69)!;
    const comTamanho = potOddsExigidas(11.19, 4.69)!;   // o que a tela fazia antes
    expect(comCusto * 100).toBeLessThan(10);
    expect(comTamanho * 100).toBeGreaterThan(25);
  });

  it("sem aposta na frente nao ha pot odds", () => {
    expect(potOddsExigidas(10, 0)).toBeNull();
    expect(potOddsExigidas(null, 0)).toBeNull();
  });
});
