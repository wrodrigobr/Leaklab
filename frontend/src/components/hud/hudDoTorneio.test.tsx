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

  it("agrediu e NUNCA pagou nao e 'sem spot': a celula mostra 1/0 e diz o que houve", () => {
    // O defeito que o dono achou na tela (17/09): um torneio com C-Bet 100% (1/1) e o AF dizendo
    // "sem spot". O servidor contava a agressao (`pf_aggr=1`) e a celula a jogava fora.
    //
    // Zero call nao e zero oportunidade. Sao tres estados: sem acao postflop (nao ha o que
    // medir), agrediu e nunca pagou (razao indefinida) e agrediu e pagou (numero). Este caso
    // separa os dois primeiros, que antes eram o mesmo.
    render(<HudDoTorneio hud={{
      ...HUD,
      stats: { ...HUD.stats,
        af: { value: null, num: 1, den: 0, band: "so_agressao" as const, healthy: null } },
    }} />);
    expect(screen.getByText("1/0"), "a amostra do AF desapareceu").toBeTruthy();
    expect(screen.getByText("detail.hud.soAgressao")).toBeTruthy();
    // e o AF nao pode virar numero: dividir por zero numa tela e valor inventado
    expect(screen.queryByText("Infinity")).toBeNull();
    expect(screen.queryByText("NaN")).toBeNull();
  });

  it("CONTROLE: 'sem spot' continua valendo para quem nao teve acao nenhuma", () => {
    // Sem este, um componente que NUNCA mais dissesse "sem spot" passaria verde no caso acima.
    render(<HudDoTorneio hud={{
      ...HUD,
      stats: { ...HUD.stats,
        af: { value: null, num: 0, den: 0, band: "no_opportunity" as const, healthy: null } },
    }} />);
    expect(screen.getAllByText("detail.hud.noOpportunity").length).toBeGreaterThan(0);
    expect(screen.queryByText("detail.hud.soAgressao")).toBeNull();
  });
});
