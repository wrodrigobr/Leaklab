import { describe, it, expect } from "vitest";
import { selectWhy, type WhyInput } from "./replayWhy";

/**
 * Esta cascata já mentiu duas vezes para o jogador. Os dois casos viraram teste:
 *   · uma decisão PREFLOP recebendo "Spot postflop sem solução pré-computada";
 *   · um call vs 3-bet com equity vs mão aleatória exibida como evidência.
 *
 * O que os testes travam não é a implementação: é a PRIORIDADE. Num `else if` encadeado, um
 * ramo novo no lugar errado rouba o caso de outro em silêncio, e só se descobre por reclamação.
 */

const base: WhyInput = {
  isPostflop: false,
  isError: false,
  heroAction: "call",
  hasMultiwayAdvice: false,
  limpedPotHeuristic: false,
  equityNotRangeAware: false,
  preflopNoCoverageStrict: false,
  gtoSpotMismatch: false,
  isPfZone: false,
  hasEngineGtoConflict: false,
  hasMathEvidence: false,
  requiredIsAdjusted: false,
  hasGto: false,
  isHero: true,
  pg: null,
};
const w = (o: Partial<WhyInput>) => selectWhy({ ...base, ...o });

describe("selectWhy — street", () => {
  it("REGRESSÃO: decisão preflop sem GTO não recebe frase de postflop", () => {
    expect(w({ isPostflop: false, hasGto: false, isHero: true }).key).toBe("card.whyNoGtoPreflop");
  });

  it("decisão postflop sem GTO segue com a frase de postflop", () => {
    expect(w({ isPostflop: true, hasGto: false, isHero: true }).key).toBe("card.whyMultiway");
  });

  it("nenhuma chave de postflop escapa para preflop, em nenhuma combinação", () => {
    const postflopOnly = new Set(["card.whyMultiway", "card.whyEqStrong", "card.whyEqFavorable",
                                  "card.whyEqUnfavorable", "card.whyEqWeak"]);
    for (const hasGto of [true, false]) {
      for (const isHero of [true, false]) {
        for (const eq of [null, 0.2, 0.6, 0.9]) {
          const r = w({ isPostflop: false, hasGto, isHero, eq });
          expect(postflopOnly.has(r.key), `${r.key} vazou pra preflop`).toBe(false);
        }
      }
    }
  });
});

describe("selectWhy — prioridade", () => {
  it("multiway ganha de tudo: o why heads-up contradiria o fold", () => {
    expect(w({ hasMultiwayAdvice: true, limpedPotHeuristic: true, equityNotRangeAware: true,
               isPfZone: true }).key).toBe("card.whyMultiwayEstimate");
  });

  it("REGRESSÃO: equity não range-aware vem ANTES da cobertura, senão o card fica mudo", () => {
    // Sem esta ordem o veredito aparece nu: a barra de equity foi suprimida E a frase zerada.
    expect(w({ equityNotRangeAware: true, preflopNoCoverageStrict: true }).key)
      .toBe("card.whyRangeNotPrice");
  });

  it("sem cobertura e sem o caso acima, a frase é OMITIDA de propósito", () => {
    const r = w({ preflopNoCoverageStrict: true });
    expect(r.key).toBe("");
  });

  it("pote limpado ganha da cobertura", () => {
    expect(w({ limpedPotHeuristic: true, preflopNoCoverageStrict: true, heroPosition: "BB" }).key)
      .toBe("card.whyLimped");
  });

  // Reportado por um aluno no SB: o card dizia "Check é a opção grátis" numa posição em que
  // check NAO EXISTE — ele já pôs meia blind e precisa completar. A frase descrevia uma mesa
  // que não era a dele.
  it("fora do BB nao promete check gratis", () => {
    for (const pos of ["SB", "BTN", "CO", "HJ", "UTG"]) {
      expect(w({ limpedPotHeuristic: true, heroPosition: pos }).key)
        .toBe("card.whyLimpedForaDoBb");
    }
  });

  it("no BB segue com a frase do check gratis", () => {
    expect(w({ limpedPotHeuristic: true, heroPosition: "bb" }).key).toBe("card.whyLimped");
  });

  it("posicao ausente nao promete check gratis", () => {
    // Sem saber a posição, prometer "grátis" é a afirmação mais forte das duas — na dúvida,
    // a frase que não crava.
    expect(w({ limpedPotHeuristic: true }).key).toBe("card.whyLimpedForaDoBb");
  });
});

describe("selectWhy — evidência matemática descreve a AÇÃO TOMADA", () => {
  const math = { hasMathEvidence: true, isPostflop: true, eq: 0.60, req: 0.40 };

  it("hero foldou com preço fechando: a frase fala do fold, não do call", () => {
    // "Call lucrativo" quando o hero foldou soa como crítica oposta ao veredito.
    expect(w({ ...math, heroAction: "fold", profitable: true }).key).toBe("card.whyFoldLeftEv");
  });

  it("fold com margem apertada é breakeven, não 'deixou EV'", () => {
    expect(w({ ...math, eq: 0.42, req: 0.40, heroAction: "fold", profitable: true }).key)
      .toBe("card.whyFoldBreakeven");
  });

  it("fold correto quando o preço não fechava", () => {
    expect(w({ ...math, eq: 0.20, heroAction: "fold", profitable: false }).key)
      .toBe("card.whyFoldCorrect");
  });

  it("call lucrativo × perdedor", () => {
    expect(w({ ...math, heroAction: "call", profitable: true }).key).toBe("card.whyCallProfit");
    expect(w({ ...math, heroAction: "call", profitable: false }).key).toBe("card.whyCallLose");
  });

  it("agressão carrega a ação para a view formatar", () => {
    const r = w({ ...math, heroAction: "raise", profitable: true });
    expect(r.key).toBe("card.whyAggrProfit");
    expect(r.actionParams?.act).toBe("raise");
  });

  it("o rótulo de 'necessário' vem como CHAVE, traduzida pela view", () => {
    expect(w({ ...math, requiredIsAdjusted: true }).params?.reqLabelKey).toBe("card.reqLabelAdjusted");
    expect(w({ ...math, requiredIsAdjusted: false }).params?.reqLabelKey).toBe("card.reqLabelPotOdds");
  });
});

describe("selectWhy — range preflop", () => {
  it("mão dentro × fora da range, com o cenário como chave", () => {
    const dentro = w({ pg: { available: true, in_range: true, hand_type: "AQs",
                             scenario: "rfi", range_pct: 0.18, stack_bucket: "50bb" } });
    expect(dentro.key).toBe("card.whyInRange");
    expect(dentro.params?.scenKey).toBe("rfi");
    expect(dentro.params?.pct).toBe(" (18%)");

    expect(w({ pg: { available: true, in_range: false, hand_type: "72o",
                     scenario: "rfi", range_pct: 0 } }).key).toBe("card.whyOutRange");
  });

  it("range_pct zero não vira ' (0%)'", () => {
    expect(w({ pg: { available: true, in_range: true, range_pct: 0 } }).params?.pct).toBe("");
  });
});

describe("selectWhy — fallback", () => {
  it("sem nada aplicável, cai no contexto genérico", () => {
    expect(w({ hasGto: true, isHero: false }).key).toBe("card.whyContext");
  });

  it("nunca devolve undefined", () => {
    for (const isPostflop of [true, false]) {
      for (const hasGto of [true, false]) {
        expect(typeof w({ isPostflop, hasGto }).key).toBe("string");
      }
    }
  });
});

describe("acao diverge: a frase so fala de TAMANHO quando e tamanho", () => {
  const pgBase = { available: true, in_range: true, hand_type: "33",
                   scenario: "hu_rfi", range_pct: 0.988, stack_bucket: "17bb",
                   top_freq: 1.0 };
  const base = { isPostflop: false, isError: true, hasGto: true, isHero: true,
                 hasMathEvidence: false, requiredIsAdjusted: false,
                 hasMultiwayAdvice: false, limpedPotHeuristic: false,
                 equityNotRangeAware: false, preflopNoCoverageStrict: false,
                 gtoSpotMismatch: false, isPfZone: false, hasEngineGtoConflict: false } as never;

  it("min-raise onde a carta manda all-in -> fala do tamanho", () => {
    const r = selectWhy({ ...(base as object), heroAction: "raise", pg: pgBase,
                          recAction: "jam", heroActionRaw: "raise" } as never);
    expect(r.key).toBe("card.whyAcaoDivergeTamanho");
  });

  it("carta manda CALL e o jogador aumentou -> NAO fala de tamanho", () => {
    // Nao e questao de tamanho, e de acao. Afirmar "tamanho" ali seria explicar errado com
    // confianca — o defeito que o usuario apontou como "ficou vago" era isto por baixo.
    const r = selectWhy({ ...(base as object), heroAction: "raise", pg: pgBase,
                          recAction: "call", heroActionRaw: "raise" } as never);
    expect(r.key).toBe("card.whyAcaoDiverge");
  });

  it("acao igual a recomendada -> volta a descrever o range", () => {
    const r = selectWhy({ ...(base as object), heroAction: "jam", pg: pgBase,
                          recAction: "jam", heroActionRaw: "jam" } as never);
    expect(r.key).toBe("card.whyInRange");
  });
});
