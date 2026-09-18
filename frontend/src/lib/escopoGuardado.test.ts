// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";

import { ESCOPO_PADRAO, escopoValido, gravarEscopo, lerEscopo, pisoDaFaixa } from "./escopoGuardado";
import { MESES_MAXIMOS_DO_ESCOPO, TETO_DE_MAOS_DO_ESCOPO } from "./api";

/**
 * A escolha do filtro, guardada por usuário.
 *
 * ── O pedido (17/09) ──────────────────────────────────────────────────────────────────────────
 *
 * "e devemos manter sessao, sempre usar a ultima escolha dele".
 *
 * ── O que quebra calado, e por isso tem caso aqui ─────────────────────────────────────────────
 *
 * `localStorage` é editável pelo jogador, sobrevive a deploy e guarda o formato de uma versão
 * anterior do código. Um escopo inválido que passasse viraria uma query que o servidor ignora em
 * silêncio -- e a tela mostraria um número de escopo diferente do que a faixa verde declara, que é
 * exatamente o defeito que este filtro existe para não ter.
 */

describe("o escopo guardado", () => {
  beforeEach(() => localStorage.clear());

  it("volta a última escolha, por usuário", () => {
    gravarEscopo(7, { tipo: "maos", n: 5000 });
    expect(lerEscopo(7)).toEqual({ tipo: "maos", n: 5000 });
    // e NÃO vaza para outro usuário: dois jogadores na mesma máquina herdariam o filtro um do
    // outro, e o escopo decide o NÚMERO que a tela mostra
    expect(lerEscopo(8)).toEqual(ESCOPO_PADRAO);
  });

  it("sem usuário não guarda nem lê", () => {
    // A sessão resolve depois do primeiro render: gravar com `undefined` criaria uma chave órfã
    // que nenhum usuário lê.
    gravarEscopo(undefined, { tipo: "maos", n: 5000 });
    expect(localStorage.length).toBe(0);
    expect(lerEscopo(undefined)).toEqual(ESCOPO_PADRAO);
  });

  it("o padrão é HISTÓRICO, que é como a tela abria antes de existir persistência", () => {
    expect(ESCOPO_PADRAO).toEqual({ tipo: "torneios", n: 0 });
    expect(lerEscopo(7)).toEqual(ESCOPO_PADRAO);
  });

  it("lixo no storage vira o padrão, e não uma query inválida", () => {
    for (const bruto of ['{"tipo":"inventado"}', "não é json", "null", "[]",
                         '{"tipo":"maos","n":0}', '{"tipo":"periodo","de":"ontem","ate":"hoje"}']) {
      localStorage.setItem("escopo_dashboard_v1:7", bruto);
      expect(lerEscopo(7), `aceitou ${bruto}`).toEqual(ESCOPO_PADRAO);
    }
  });

  it("apara o que o servidor apararia, em vez de mandar e ser ignorado", () => {
    // O teto é o mesmo dos dois lados. Mandar 999 mil e deixar o servidor cortar faria a tela
    // dizer "últimas 999.000 mãos" enquanto os números seriam de 30 mil.
    expect(escopoValido({ tipo: "maos", n: 999999 }))
      .toEqual({ tipo: "maos", n: TETO_DE_MAOS_DO_ESCOPO });
  });

  it("faixa invertida é CORRIGIDA, e não descartada", () => {
    // Descartar devolveria o padrão sem explicação, e o jogador veria o acervo inteiro depois de
    // escolher um mês. Trocar os extremos entrega o que ele quis dizer.
    expect(escopoValido({ tipo: "periodo", de: "2026-06-30", ate: "2026-06-01" }))
      .toEqual({ tipo: "periodo", de: "2026-06-01", ate: "2026-06-30" });
  });

  it("o piso da faixa é o mesmo teto de meses do servidor", () => {
    const hoje = new Date("2026-09-17T12:00:00Z");
    const piso = pisoDaFaixa(hoje);
    expect(piso).toBe("2025-09-17");
    // e ele SEGUE a constante: um teto novo no servidor move o seletor junto
    const meses = (hoje.getFullYear() - Number(piso.slice(0, 4))) * 12
      + (hoje.getMonth() + 1 - Number(piso.slice(5, 7)));
    expect(meses).toBe(MESES_MAXIMOS_DO_ESCOPO);
  });

  it("storage bloqueado não derruba a tela", () => {
    // Navegador em modo privado, ou site com armazenamento bloqueado: o acessador LEVANTA, e a
    // casa já tem a regra de tratar isso em toda leitura de storage.
    const original = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() { throw new Error("bloqueado"); },
    });
    try {
      expect(lerEscopo(7)).toEqual(ESCOPO_PADRAO);
      expect(() => gravarEscopo(7, { tipo: "maos", n: 1000 })).not.toThrow();
    } finally {
      if (original) Object.defineProperty(window, "localStorage", original);
    }
  });
});
