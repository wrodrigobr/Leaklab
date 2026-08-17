// A category_key e a UNICA taxonomia persistida — o parse dela nao pode regredir calado.
//
// `pf:<street>:<pos>` e a categoria de DEFESA postflop e `pf:<street>:<pos>:ini` a de
// INICIATIVA (c-bet e barrel), criada em 12/08 quando `hero_was_aggressor` deixou de ser coluna
// morta. A chave da defesa ficou SEM sufixo de proposito: `progression_attempts` e chaveado por
// ela e mudar o formato orfanaria o historico de treino de todo jogador.
import { describe, expect, it } from "vitest";

import { parseCategoryKey } from "./spotLabel";

describe("parseCategoryKey", () => {
  it("pf:street:pos:ini e a categoria de INICIATIVA", () => {
    expect(parseCategoryKey("pf:turn:SB:ini")).toEqual({
      kind: "postflop", street: "turn", position: "SB", vs_position: "", iniciativa: true,
    });
  });

  it("pf:street:pos segue sendo a DEFESA, com a chave antiga intacta", () => {
    expect(parseCategoryKey("pf:flop:BB")).toEqual({
      kind: "postflop", street: "flop", position: "BB", vs_position: "", iniciativa: false,
    });
  });

  it("pf:bb_defense legado nao quebra", () => {
    expect(parseCategoryKey("pf:bb_defense")).toEqual({
      kind: "postflop", position: "BB", vs_position: "BTN", street: "flop",
    });
  });

  it("pf:bb_3bet_pot tem identidade propria (nao cai no legado 'defende vs c-bet')", () => {
    expect(parseCategoryKey("pf:bb_3bet_pot")).toEqual({
      kind: "postflop", position: "BB", vs_position: "BTN", street: "flop", pote3bet: true,
    });
  });

  it("CONTROLE: chave preflop nao e tocada pelo parse postflop", () => {
    expect(parseCategoryKey("vs_rfi:BB:BTN:40")).toEqual({
      scenario: "vs_rfi", position: "BB", vs_position: "BTN", stack_bb: 40,
    });
  });
});
