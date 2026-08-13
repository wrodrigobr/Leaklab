// @vitest-environment jsdom
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { PokerTableV3 } from "./PokerTableV3";
import type { ReplayStep } from "@/lib/api";

/**
 * O pod do assento mostra a AÇÃO em cima e o STACK embaixo. Num call de all-in por menos
 * (caso real: torneio 3960586609, mão 259090517149 — CSM96 paga 4.056 fichas do jam do SB
 * e fica com stack 0), a mesa lia "CALL" com "0 BB" logo abaixo — como se o call fosse de
 * graça. O backend manda `amount: 4056` certo (provado no parser); o defeito era só de
 * exibição: o preço do call não aparecia em lugar NENHUM da mesa, porque as fichas à
 * frente somam a rodada inteira (raise anterior + call).
 *
 * O conserto tem duas partes, e cada uma tem assert próprio:
 *   1. CALL leva o preço junto: "CALL 20.3 BB".
 *   2. Stack zerado de jogador vivo vira "ALL-IN", não "0 BB".
 */
afterEach(cleanup);

// Réplica em miniatura da mão real: bb=200, hero abriu 400 e pagou 4.056 all-in.
function stepCallAllIn(overrides: Partial<ReplayStep> = {}): ReplayStep {
  return {
    type: "action",
    desc: "CSM96 calls",
    street: "preflop",
    seats: {
      "2": { player: "sbJam", stack: 6280, stack_bb: 31.4, pos: "SB" },
      "6": { player: "CSM96", stack: 4456, stack_bb: 22.3, pos: "UTG+2" },
    },
    hero: "CSM96",
    hero_cards: ["Ah", "Kh"],
    board: [],
    pot: 10936,
    pot_bb: 54.7,
    bets: { "6": 4456, "2": 6280 },
    folded: [],
    bb: 200,
    button: 2,
    player: "CSM96",
    seat: 6,
    action: "call",
    amount: 4056,
    is_hero: true,
    // stacks pós-ação: hero pagou tudo (0), SB já estava all-in (0)
    ...( { stacks: { "6": 0, "2": 0 } } as Partial<ReplayStep>),
    ...overrides,
  } as ReplayStep;
}

function renderTable(step: ReplayStep) {
  const { container } = render(
    <PokerTableV3 step={step} hero="CSM96" heroCards={["Ah", "Kh"]} bb={200} betUnit="bb" />,
  );
  return container;
}

describe("PokerTableV3 — call de all-in por menos", () => {
  it("o CALL exibe o valor pago (CALL 20.3 BB), não fica mudo sobre o preço", () => {
    const html = renderTable(stepCallAllIn()).innerHTML;
    expect(html).toContain("CALL 20.3 BB");
  });

  it("stack zerado de jogador vivo mostra ALL-IN, nunca 0 BB", () => {
    const html = renderTable(stepCallAllIn()).innerHTML;
    expect(html).toContain("ALL-IN");
    expect(html).not.toContain(">0 BB<");
  });

  it("call comum (com stack sobrando) continua mostrando o preço e o stack numérico", () => {
    // hero paga 400 e sobra stack — não é all-in
    const step = stepCallAllIn({
      amount: 400,
      ...( { stacks: { "6": 4056, "2": 6280 } } as Partial<ReplayStep>),
    });
    const html = renderTable(step).innerHTML;
    expect(html).toContain("CALL 2 BB");       // 400/200
    expect(html).toContain("20.3 BB");          // stack 4056/200
    expect(html).not.toContain("ALL-IN");
  });

  it("no showdown o stack zerado volta a ser número (0 = perdeu tudo, informação certa)", () => {
    const step = stepCallAllIn({
      type: "showdown",
      action: undefined,
      summary: { winners: [], seats: [], board: [], total_pot: 10936 },
    } as Partial<ReplayStep>);
    const html = renderTable(step).innerHTML;
    expect(html).not.toContain("ALL-IN");
  });
});
