import { describe, it, expect } from "vitest";
import { buildStudyPlan } from "./planBuilder";

/**
 * A tela do plano nao pode quebrar com resposta torta do modelo (09/09).
 *
 * Achado auditando os 7 planos em producao: o do aluno 22 trazia `nao_focar_agora` como STRING
 * com um JSON dentro. O mapeamento usava `?? []`, que deixa a string passar; a secao entao testa
 * `.length > 0` (numa string, isso conta CARACTERES, logo passa) e chama `.map`, que string nao
 * tem. Resultado: a tela de plano daquele aluno quebrava.
 *
 * O backend passou a normalizar, mas a resposta do modelo nao e contrato: aqui a tela se defende
 * sozinha. Um plano com secao faltando e um plano; um plano que quebra a tela nao e nada.
 */
const t = ((k: string) => k) as unknown as Parameters<typeof buildStudyPlan>[1];

const base = {
  nivel: "intermediario",
  resumo: "Voce abre demais no pre-flop.",
  cards: [{ prioridade: "p1", titulo: "Abertura no CO", diagnostico: "d", conceitos: [], exercicio: "e", metrica: "m", spot: "s" }],
};

describe("planBuilder tolera resposta torta", () => {
  it("secao que veio como string nao vira lista de caracteres", () => {
    const plano = buildStudyPlan({ ...base, nao_focar_agora: '[{"item":"VPIP","motivo":"amostra"}]' } as never, t);
    expect(Array.isArray(plano.naoFocar)).toBe(true);
    expect(plano.naoFocar).toHaveLength(0);          // sem forma valida, secao vazia — nunca `.map` em string
  });

  it("secao ausente ou nula vira lista vazia", () => {
    const plano = buildStudyPlan({ ...base } as never, t);
    expect(plano.naoFocar).toEqual([]);
    expect(plano.observar).toEqual([]);
    const comNulo = buildStudyPlan({ ...base, nao_focar_agora: null, observar_mais_dados: undefined } as never, t);
    expect(comNulo.naoFocar).toEqual([]);
    expect(comNulo.observar).toEqual([]);
  });

  it("lista de verdade passa intacta", () => {
    const itens = [{ item: "SB river", motivo: "amostra pequena" }];
    const plano = buildStudyPlan({ ...base, nao_focar_agora: itens } as never, t);
    expect(plano.naoFocar).toEqual(itens);
  });
});
