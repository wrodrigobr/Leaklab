import { describe, it, expect } from "vitest";
import { autoFinishAfterFold, totalPot, clockwiseFromSb, deriveStreet } from "./hhAutoFinish";
import { generateHandHistory, type HandInput, type PlayerInput, type HandAction } from "./hhGenerator";

const players: PlayerInput[] = [1, 2, 3, 4, 5, 6].map(s => ({
  seat: s, name: ["SB", "BB", "UTG", "HJ", "CO", "BTN"][s - 1], stack: 10000,
}));

// hero = BTN (seat6); foldou preflop após UTG abrir e HJ/CO pagarem (multiway)
const base = (actions: HandAction[]) => ({
  players, buttonSeat: 6, actions, sb: 50, bb: 100, ante: 0,
  board: { flop: [] as string[], turn: "", river: "" },
});

describe("hhAutoFinish", () => {
  it("clockwiseFromSb / deriveStreet básicos", () => {
    const cw = clockwiseFromSb(players, 6);
    expect(cw.map(p => p.name)).toEqual(["SB", "BB", "UTG", "HJ", "CO", "BTN"]);
    expect(deriveStreet({ flop: [], turn: "", river: "" })).toBe("preflop");
    expect(deriveStreet({ flop: ["As", "Kd", "2c"], turn: "", river: "" })).toBe("flop");
  });

  it("folda todos os ativos restantes pra um vencedor (hero já foldou)", () => {
    // UTG raise, HJ call, CO call, BTN(hero) FOLD, SB fold, BB fold → ativos: UTG,HJ,CO
    const acts: HandAction[] = [
      { player: "UTG", street: "preflop", action: "raise", amount: 250 },
      { player: "HJ", street: "preflop", action: "call", amount: 250 },
      { player: "CO", street: "preflop", action: "call", amount: 250 },
      { player: "BTN", street: "preflop", action: "fold" },
      { player: "SB", street: "preflop", action: "fold" },
      { player: "BB", street: "preflop", action: "fold" },
    ];
    const res = autoFinishAfterFold(base(acts), () => 0)!; // rand=0 → 1º ativo (UTG)
    expect(res).toBeTruthy();
    expect(res.winnerName).toBe("UTG");
    // novos folds: HJ e CO (os outros 2 ativos)
    const added = res.actions.slice(acts.length);
    expect(added.map(a => a.player).sort()).toEqual(["CO", "HJ"]);
    expect(added.every(a => a.action === "fold")).toBe(true);
    // só o vencedor sobra ativo → mão resolvida
    const folded = new Set(res.actions.filter(a => a.action === "fold").map(a => a.player));
    const active = clockwiseFromSb(players, 6).filter(p => !folded.has(p.name));
    expect(active.map(p => p.name)).toEqual(["UTG"]);
  });

  it("pote = antes + blinds + comprometido (UTG/HJ/CO 2.5bb cada)", () => {
    const acts: HandAction[] = [
      { player: "UTG", street: "preflop", action: "raise", amount: 250 },
      { player: "HJ", street: "preflop", action: "call", amount: 250 },
      { player: "CO", street: "preflop", action: "call", amount: 250 },
      { player: "BTN", street: "preflop", action: "fold" },
      { player: "SB", street: "preflop", action: "fold" },
      { player: "BB", street: "preflop", action: "fold" },
    ];
    // SB 50 + BB 100 + UTG 250 + HJ 250 + CO 250 = 900
    expect(totalPot(base(acts))).toBe(900);
  });

  it("escolhe vencedor por rand (último ativo)", () => {
    const acts: HandAction[] = [
      { player: "UTG", street: "preflop", action: "raise", amount: 250 },
      { player: "HJ", street: "preflop", action: "call", amount: 250 },
      { player: "CO", street: "preflop", action: "call", amount: 250 },
      { player: "BTN", street: "preflop", action: "fold" },
      { player: "SB", street: "preflop", action: "fold" },
      { player: "BB", street: "preflop", action: "fold" },
    ];
    const res = autoFinishAfterFold(base(acts), () => 0.99)!; // último ativo (CO)
    expect(res.winnerName).toBe("CO");
  });

  it("resultado gera um HH válido (parseável) com vencedor", () => {
    const acts: HandAction[] = [
      { player: "UTG", street: "preflop", action: "raise", amount: 250 },
      { player: "HJ", street: "preflop", action: "call", amount: 250 },
      { player: "BTN", street: "preflop", action: "fold" },
      { player: "SB", street: "preflop", action: "fold" },
      { player: "BB", street: "preflop", action: "fold" },
      { player: "CO", street: "preflop", action: "fold" },
    ];
    const res = autoFinishAfterFold(base(acts), () => 0)!; // ativos UTG,HJ → vencedor UTG
    const hi: HandInput = {
      handId: "100000001", tournamentId: "999999", buyIn: "1.00+0.10", level: "I",
      sb: 50, bb: 100, ante: 0, maxSeats: 6, players, buttonSeat: 6,
      heroName: "BTN", heroCards: "As Kd", actions: res.actions, board: {},
      winner: { player: res.winnerName, amount: res.potChips },
    };
    const hh = generateHandHistory(hi);
    expect(hh).toContain("PokerStars Hand #100000001");
    expect(hh).toContain("collected");
    expect(hh).toContain("BTN: folds");
  });
});
