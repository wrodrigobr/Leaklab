import { describe, it, expect } from "vitest";
import { splitHands, importHandHistory } from "./hhImport";
import { generateHandHistory, type HandInput } from "./hhGenerator";

const BB = 100;
const players = [1, 2, 3, 4, 5, 6].map(s => ({
  seat: s, name: ["SB", "BB", "UTG", "HJ", "CO", "BTN"][s - 1], stack: 100 * BB,
}));

const base = (handId: string, buttonSeat: number, heroName: string, cards: string): HandInput => ({
  handId, tournamentId: "999999", buyIn: "1.00+0.10", level: "I",
  sb: 50, bb: 100, ante: 0, maxSeats: 6, players, buttonSeat,
  heroName, heroCards: cards,
  actions: [
    { player: "UTG", street: "preflop", action: "raise", amount: 250 },
    { player: "HJ", street: "preflop", action: "fold" },
    { player: "CO", street: "preflop", action: "fold" },
    { player: "BTN", street: "preflop", action: "fold" },
    { player: "SB", street: "preflop", action: "fold" },
    { player: "BB", street: "preflop", action: "fold" },
  ],
  board: {},
});

describe("hhImport", () => {
  it("splitHands splits a multi-hand file", () => {
    const file = generateHandHistory(base("100000001", 6, "BTN", "As Kd")) +
      "\n\n\n" + generateHandHistory(base("100000002", 1, "BTN", "Qh Qs"));
    const hands = splitHands(file);
    expect(hands.length).toBe(2);
    expect(hands[0]).toContain("Hand #100000001");
    expect(hands[1]).toContain("Hand #100000002");
  });

  it("round-trips config from the LAST hand", () => {
    const file = generateHandHistory(base("100000001", 6, "BTN", "As Kd")) +
      "\n\n\n" + generateHandHistory(base("100000002", 1, "BTN", "Qh Qs"));
    const imp = importHandHistory(file)!;
    expect(imp).toBeTruthy();
    expect(imp.hands.length).toBe(2);
    expect(imp.handId).toBe("100000002");       // última mão
    expect(imp.tournamentId).toBe("999999");
    expect(imp.sb).toBe(50);
    expect(imp.bb).toBe(100);
    expect(imp.maxSeats).toBe(6);
    expect(imp.buttonSeat).toBe(1);             // button da última mão
    expect(imp.players.length).toBe(6);
    expect(imp.players.find(p => p.seat === 6)?.name).toBe("BTN");
    expect(imp.players.find(p => p.seat === 6)?.stack).toBe(10000);
    expect(imp.heroName).toBe("BTN");
    expect(imp.heroSeat).toBe(6);
  });

  it("parses ante and level", () => {
    const inp = base("100000001", 6, "BTN", "As Kd");
    inp.ante = 12; inp.level = "V";
    const imp = importHandHistory(generateHandHistory(inp))!;
    expect(imp.ante).toBe(12);
    expect(imp.level).toBe("V");
  });

  it("returns null on garbage / non-PokerStars text", () => {
    expect(importHandHistory("not a hand history")).toBeNull();
    expect(importHandHistory("")).toBeNull();
  });
});
