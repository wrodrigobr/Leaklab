import { describe, expect, it } from "vitest";
import { emblemaDoCenario, emblemaDoCriterio, montarTrilha, placarDaTrilha } from "./trilhaTreino";
import type { ProgressionStatus, ProgressionStatusItem } from "./api";

/** Trilha (Training v2): a ordem dos nós e o estado de cada um são regra, não acaso. */

const item = (key: string, estado: ProgressionStatusItem["estado"], extra: Partial<ProgressionStatusItem> = {}) =>
  ({ key, estado, scenario: "vs_rfi", titulo: key,
     mastery: { dominado: false, criterios: [], faltando: [], janela: { n: 0, acerto_pct: 0 } },
     ...extra } as unknown as ProgressionStatusItem);

const status = (over: Partial<ProgressionStatus>): ProgressionStatus =>
  ({ ativa: null, proximas: [], dominadas: [], restantes: 0, items: [], ...over } as ProgressionStatus);

describe("montarTrilha", () => {
  it("ordena caminho: dominadas → ativa → próximas bloqueadas", () => {
    const nos = montarTrilha(status({
      dominadas: [item("a", "dominado_no_treino"), item("b", "comprovado_no_jogo")],
      ativa: item("c", "em_treino"),
      proximas: [item("d", "em_treino"), item("e", "em_treino")],
    }));
    expect(nos.map((n) => `${n.key}:${n.estado}`)).toEqual([
      "a:dominado", "b:comprovado", "c:ativo", "d:bloqueado", "e:bloqueado",
    ]);
  });

  it("leak reaberto NUNCA some da trilha — vem marcado", () => {
    const nos = montarTrilha(status({
      dominadas: [item("a", "dominado_no_treino", { reaberto: true })],
      ativa: item("b", "em_treino", { reaberto: true }),
    }));
    expect(nos[0].reaberto).toBe(true);
    expect(nos[1].reaberto).toBe(true);
  });

  it("dedup quando a ativa também aparece em próximas (backend antigo)", () => {
    const nos = montarTrilha(status({
      ativa: item("c", "em_treino"),
      proximas: [item("c", "em_treino"), item("d", "em_treino")],
    }));
    expect(nos.filter((n) => n.key === "c")).toHaveLength(1);
    expect(nos.map((n) => n.key)).toEqual(["c", "d"]);
  });

  it("status vazio ou ausente devolve trilha vazia (nunca quebra a página)", () => {
    expect(montarTrilha(undefined)).toEqual([]);
    expect(montarTrilha(status({}))).toEqual([]);
  });
});

describe("placarDaTrilha", () => {
  it("bb só entram COMPROVADOS no jogo — dominado no treino não é bb recuperado", () => {
    const nos = montarTrilha(status({
      dominadas: [
        item("a", "dominado_no_treino", { ev_loss_bb: -9 } as never),
        item("b", "comprovado_no_jogo", { ev_loss_bb: -5.24 } as never),
      ],
      ativa: item("c", "em_treino", { ev_loss_bb: -3 } as never),
    }));
    const p = placarDaTrilha(nos);
    expect(p.dominados).toBe(2);
    expect(p.total).toBe(3);
    expect(p.bbComprovados).toBe(5.2);   // só o comprovado; arredondado a 1 casa
  });

  it("comprovado REABERTO perde o bb do placar — regressão não mantém crédito", () => {
    const nos = montarTrilha(status({
      dominadas: [item("b", "comprovado_no_jogo", { ev_loss_bb: -5, reaberto: true } as never)],
    }));
    expect(placarDaTrilha(nos).bbComprovados).toBe(0);
  });
});

describe("emblemaDoCriterio", () => {
  it("cada critério do gate tem seu mostrador", () => {
    expect(emblemaDoCriterio("volume")).toBe("chip");
    expect(emblemaDoCriterio("precisao")).toBe("target");
    expect(emblemaDoCriterio("amplitude")).toBe("range");
    expect(emblemaDoCriterio("fronteira")).toBe("cards");
    expect(emblemaDoCriterio("transferencia")).toBe("clock");
  });
});

describe("emblemaDoCenario", () => {
  it("cada cenário tem seu emblema; desconhecido cai no alvo", () => {
    expect(emblemaDoCenario("rfi")).toBe("spade");
    expect(emblemaDoCenario("vs_rfi")).toBe("shield");
    expect(emblemaDoCenario("vs_3bet")).toBe("cards");
    expect(emblemaDoCenario("postflop")).toBe("chip");
    expect(emblemaDoCenario(undefined)).toBe("target");
  });
});
