// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from "vitest";
import { conviteCoachFechado, fecharConviteCoach } from "./conviteCoachDismiss";

describe("convite para vincular coach", () => {
  beforeEach(() => localStorage.clear());
  it("comeca aberto, fecha por usuario e fica fechado", () => {
    expect(conviteCoachFechado(7)).toBe(false);
    fecharConviteCoach(7);
    expect(conviteCoachFechado(7)).toBe(true);
    expect(conviteCoachFechado(8)).toBe(false);      // outro usuario nao herda
    expect(conviteCoachFechado(undefined)).toBe(false);
  });
});
