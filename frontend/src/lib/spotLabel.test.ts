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

  it("postflop tem rótulo próprio (o cenário preflop não descreve a situação)", () => {
    expect(parseCategoryKey("pf:qualquer:coisa")).toEqual({
      kind: "postflop", position: "BB", vs_position: "BTN",
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
