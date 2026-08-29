// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HudDoTorneio } from "./HudDoTorneio";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (k: string) => k }) }));
afterEach(cleanup);

/**
 * HUD do torneio: a faixa esperada aparece, e a cor diz dentro/fora (30/08, pedido do dono).
 * O contrato: valor×faixa compara dois fatos em qualquer amostra; stat sem faixa fica neutro;
 * sem oportunidade vira traço, nunca zero.
 */
const HUD = {
  available: true, hands: 42, archetype: null,
  stats: {
    vpip:     { value: 31, num: 13, den: 42, band: "low_sample" as const, healthy: [18, 24] as [number, number] },
    pfr:      { value: 20, num: 8,  den: 42, band: "low_sample" as const, healthy: [15, 21] as [number, number] },
    // cbet SEM faixa no fixture: exercita o caminho neutro numa celula que RENDERIZA
    cbet:     { value: 50, num: 1,  den: 2,  band: "low_sample" as const, healthy: null },
    fold3bet: { value: null, num: 0, den: 0, band: "no_opportunity" as const, healthy: null },
  },
};

describe("HUD do torneio", () => {
  it("mostra a régua na célula e pinta dentro/fora", () => {
    render(<HudDoTorneio hud={HUD} />);
    expect(screen.getByText(/18–24%/)).toBeTruthy();          // a régua do VPIP visível
    expect(screen.getByText("31%").className).toContain("text-amber-400");   // fora da faixa
    expect(screen.getByText("20%").className).toContain("text-primary");     // dentro
  });

  it("stat sem faixa declarada fica NEUTRO — não se pinta sem régua", () => {
    render(<HudDoTorneio hud={HUD} />);
    const el = screen.getByText("50%");
    expect(el.className).not.toContain("amber");
    expect(el.className).not.toContain("text-primary");
  });

  it("sem oportunidade vira traço, nunca 0", () => {
    render(<HudDoTorneio hud={HUD} />);
    expect(screen.getByText("—")).toBeTruthy();
    expect(screen.queryByText("0%")).toBeNull();
  });
});
