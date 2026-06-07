import { describe, it, expect } from "vitest";
import { generateHandHistory, type HandInput, type PlayerInput } from "./hhGenerator";

const players: PlayerInput[] = [1, 2, 3, 4, 5, 6].map(s => ({
  seat: s, name: s === 1 ? "Hero" : `P${s}`, stack: 10000,
}));

const hi = (over: Partial<HandInput>): HandInput => ({
  handId: "1", tournamentId: "9", sb: 50, bb: 100, ante: 0, maxSeats: 6,
  players, buttonSeat: 6, heroName: "Hero", heroCards: "Ac Jd", actions: [], board: {},
  ...over,
});

describe("hhGenerator — call = incremento (não total)", () => {
  it("call após o próprio open paga só o que falta (open 200 + 3bet 600 → calls 400)", () => {
    // Hero(SB) abre 200, P5 3beta a 600, Hero paga (total 600). PokerStars: 'calls 400'.
    const hh = generateHandHistory(hi({
      buttonSeat: 4, heroName: "Hero",
      actions: [
        { player: "Hero", street: "preflop", action: "raise", amount: 200 },
        { player: "P5", street: "preflop", action: "raise", amount: 600 },
        { player: "Hero", street: "preflop", action: "call", amount: 600 },
      ],
    }));
    expect(hh).toContain("Hero: calls 400");      // 600 total − 200 já investido
    expect(hh).not.toContain("Hero: calls 600");
  });

  it("cold call (sem investimento prévio) paga o total", () => {
    // P3 abre 250, P5 paga a frio (sem nada antes) → 'calls 250'
    const hh = generateHandHistory(hi({
      actions: [
        { player: "P3", street: "preflop", action: "raise", amount: 250 },
        { player: "P5", street: "preflop", action: "call", amount: 250 },
      ],
    }));
    expect(hh).toContain("P5: calls 250");
  });

  it("BB pagando um open desconta o big blind já postado (open 250 → BB calls 150)", () => {
    // button=6 → SB=seat1(Hero), BB=seat2(P2). UTG(seat3=P3) abre 250, BB paga.
    const hh = generateHandHistory(hi({
      actions: [
        { player: "P3", street: "preflop", action: "raise", amount: 250 },
        { player: "Hero", street: "preflop", action: "fold" }, // SB
        { player: "P2", street: "preflop", action: "call", amount: 250 }, // BB já tem 100
      ],
    }));
    expect(hh).toContain("P2: calls 150");        // 250 − 100 (BB postado)
  });
});
