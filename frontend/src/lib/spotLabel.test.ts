import { describe, it, expect } from "vitest";
import { parseCategoryKey } from "./spotLabel";

/**
 * A `category_key` é a ÚNICA taxonomia persistida do produto — se a leitura dela derrapar, o
 * rótulo mente sobre qual spot é. A profundidade faz parte da identidade: a mesma mão é shove a
 * 12bb e call a 30bb, então `rfi:SB::12` e `rfi:SB::30` NÃO são o mesmo leak.
 */
describe("parseCategoryKey", () => {
  it("lê um RFI (sem vs_position)", () => {
    expect(parseCategoryKey("rfi:SB::30")).toEqual({
      scenario: "rfi", position: "SB", vs_position: "", stack_bb: 30,
    });
  });

  it("lê uma defesa vs RFI", () => {
    expect(parseCategoryKey("vs_rfi:BB:CO:40")).toEqual({
      scenario: "vs_rfi", position: "BB", vs_position: "CO", stack_bb: 40,
    });
  });

  it("lê um vs 3-bet", () => {
    expect(parseCategoryKey("vs_3bet:CO:BTN:50")).toEqual({
      scenario: "vs_3bet", position: "CO", vs_position: "BTN", stack_bb: 50,
    });
  });

  it("postflop lê a STREET da chave em vez de presumir flop", () => {
    // `pf:` já foi UMA categoria só (BB vs BTN no flop) e a função devolvia isso fixo. Hoje o
    // backend produz `pf:<street>:<pos>` e agrupa domínio em `pf:flop` / `pf:turn` / `pf:river`:
    // com o valor fixo, as três habilidades apareciam com o MESMO nome na lista de domínio e a de
    // river anunciava "(flop)".
    expect(parseCategoryKey("pf:flop:BB")).toEqual({
      kind: "postflop", street: "flop", position: "BB", vs_position: "",
    });
    expect(parseCategoryKey("pf:river:SB")).toEqual({
      kind: "postflop", street: "river", position: "SB", vs_position: "",
    });
    // e as três são DISTINGUÍVEIS entre si, que é o ponto
    expect(parseCategoryKey("pf:flop:BB").street)
      .not.toBe(parseCategoryKey("pf:river:BB").street);
  });

  it("chave postflop legada continua entendida", () => {
    // `pf:bb_defense` é do catálogo estático e ainda existe no banco de quem treinou antes.
    expect(parseCategoryKey("pf:bb_defense")).toEqual({
      kind: "postflop", position: "BB", vs_position: "BTN", street: "flop",
    });
  });

  it("chave sem stack não inventa profundidade", () => {
    expect(parseCategoryKey("rfi:SB:").stack_bb).toBeNull();
    expect(parseCategoryKey("rfi:SB::0").stack_bb).toBeNull();
    expect(parseCategoryKey("rfi:SB::abc").stack_bb).toBeNull();
  });

  it("chave vazia não quebra", () => {
    expect(parseCategoryKey("")).toEqual({});
  });

  it("stacks diferentes são leaks diferentes", () => {
    expect(parseCategoryKey("rfi:SB::12").stack_bb).toBe(12);
    expect(parseCategoryKey("rfi:SB::30").stack_bb).toBe(30);
  });
});
