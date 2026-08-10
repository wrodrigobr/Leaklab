// As tres metricas do card v2 e, sobretudo, o MOTIVO de cada ausencia.
//
// Medido no acervo: a linha fica parcialmente vazia em 76% dos cards. Se as quatro ausencias
// virarem a mesma celula em branco, o card passa tres quartos do tempo dizendo "nao sei" sem
// dizer de que. A distincao entre `fora_de_escala` (62 decisoes, numero impossivel) e
// `nao_confiavel` (264, valor que CABE no jogo mas nao merece confianca) foi decisao do usuario.
import { describe, expect, it } from "vitest";

import { metricasDoCard } from "./cardV2Metricas";

describe("metricas do card v2", () => {
  it("o ZERO aparece: nao custou nada e diferente de nao sei quanto custou", () => {
    const m = metricasDoCard({ evLossBb: 0, equity: 0.54, requerido: 0.29, acao: "call" });
    expect(m.evPerdido.valor).toBe("0.00bb");
    expect(m.evPerdido.motivo, "zero nao e ausencia").toBeUndefined();
  });

  it("cada ausencia de EV tem o SEU motivo, e nao um generico", () => {
    const casos = [
      ["sem_gabarito", "card.v2EvSemGabaritoCurto"],
      ["fora_de_escala", "card.v2EvForaDeEscalaCurto"],
      ["nao_confiavel", "card.v2EvNaoConfiavelCurto"],
    ] as const;
    const vistos = new Set<string>();
    for (const [motivo, curtoEsperado] of casos) {
      const m = metricasDoCard({ evLossBb: null, evLossMotivo: motivo, equity: 0.4 });
      expect(m.evPerdido.valor).toBeNull();
      expect(m.evPerdido.motivoCurto, `motivo ${motivo}`).toBe(curtoEsperado);
      vistos.add(m.evPerdido.motivoCurto!);
    }
    // CONTROLE: os tres precisam ser DIFERENTES entre si. Sem isto, mapear os tres para o mesmo
    // texto passaria nas assercoes acima se elas fossem menos especificas.
    expect(vistos.size, "dois motivos cairam no mesmo texto").toBe(3);
  });

  it("os 264 NAO sao chamados de fora de escala", () => {
    // Eles cabem no jogo — o que falta e confianca, nao escala. Chama-los de impossiveis seria
    // impreciso, e foi o ponto que o usuario levantou.
    const m = metricasDoCard({ evLossBb: null, evLossMotivo: "nao_confiavel", equity: 0.4 });
    expect(m.evPerdido.motivo).toBe("card.v2EvNaoConfiavel");
    expect(m.evPerdido.motivo).not.toBe("card.v2EvForaDeEscala");
  });

  it("sem motivo declarado, assume o MENOS alarmante", () => {
    // Inventar "fora de escala" por omissao nossa acusaria o solver de um defeito que pode nao
    // existir. `sem_gabarito` e o caso mais comum e o mais honesto como padrao.
    const m = metricasDoCard({ evLossBb: null, equity: 0.4 });
    expect(m.evPerdido.motivoCurto).toBe("card.v2EvSemGabaritoCurto");
  });

  it("pot odds: quem APOSTOU nao enfrentou preco, e isso nao e dado faltando", () => {
    for (const acao of ["bet", "raise", "shove", "jam", "check"]) {
      const m = metricasDoCard({ equity: 0.6, requerido: null, acao });
      expect(m.potOdds.motivoCurto, acao).toBe("card.v2OddsNaoEnfrentouApostaCurto");
    }
    // CONTROLE: pagando, o preco aparece.
    expect(metricasDoCard({ equity: 0.6, requerido: 0.29, acao: "call" }).potOdds.valor).toBe("29%");
  });

  it("CONTROLE: fold sem preco cai no generico, nao em 'nao pagou'", () => {
    // Foldar nao e apostar. Se nao ha preco registrado num fold, e dado faltando de verdade —
    // dizer "voce nao pagou" ali seria uma explicacao errada, que e pior que nenhuma.
    const m = metricasDoCard({ equity: 0.4, requerido: null, acao: "fold" });
    expect(m.potOdds.motivoCurto).toBe("card.v2SemDado");
  });

  it("o TOM segue o numero, e nao o veredito", () => {
    expect(metricasDoCard({ equity: 0.7 }).equity.tom).toBe("bom");
    expect(metricasDoCard({ equity: 0.2 }).equity.tom).toBe("ruim");
    expect(metricasDoCard({ equity: 0.45 }).equity.tom).toBe("neutro");
    expect(metricasDoCard({ evLossBb: 3.0, equity: 0.4 }).evPerdido.tom).toBe("ruim");
    expect(metricasDoCard({ evLossBb: 0.01, equity: 0.4 }).evPerdido.tom).toBe("neutro");
  });

  it("equity ausente nao imprime NaN", () => {
    const m = metricasDoCard({ equity: null });
    expect(m.equity.valor).toBeNull();
    expect(m.equity.motivoCurto).toBe("card.v2SemDado");
  });
});
