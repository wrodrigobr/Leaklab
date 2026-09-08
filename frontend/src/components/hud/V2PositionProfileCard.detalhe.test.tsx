// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, within, waitFor } from "@testing-library/react";
import { V2PositionProfileCard } from "./V2PositionProfileCard";
import type { PlayerStatsResponse, PositionProfileResponse } from "@/lib/api";

/**
 * O painel "contra quem" (06/09). A faixa de 3-Bet e Fold 3-Bet e larga em "todos" por
 * natureza; aberta por oponente ela estreita. O que um refactor quebra em silencio:
 * 1. So 3-Bet e Fold 3-Bet abrem painel; RFI/VPIP nao (nao misturam oponentes).
 * 2. O painel pede ao backend o MESMO recorte (stack e last_n) da grade.
 * 3. E um modal: fecha pelo X; trocar a faixa de stack fecha.
 */
const detail = vi.fn();
vi.mock("@/lib/api", () => ({ metrics: { playerStatsByPositionDetail: (...a: unknown[]) => detail(...a) } }));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));

afterEach(cleanup);
beforeEach(() => {
  detail.mockReset();
  detail.mockResolvedValue({
    position: "BB", stat: "three_bet", stack_band: null, minimo: 30,
    rows: [
      { vs: "UTG", n: 120, value: 5.1, band: "ok", ref: { lo: 2, hi: 8, folga: 3, pesos: { "40bb vs UTG": 100 } } },
      { vs: "BTN", n: 12, value: 25, band: "low_sample", ref: { lo: 15, hi: 22, folga: 3, pesos: {} } },
    ],
    // o total e o numero da celula (8.5 em 132), fora da faixa 2-8: vermelho, seta para cima
    total: { n: 132, value: 8.5, ref: { lo: 2, hi: 8, folga: 3, pesos: {} } },
  });
});

const ok = (value: number, lo?: number, hi?: number) =>
  ({ value, band: "ok" as const, ...(lo != null ? { ref: { lo, hi, folga: 3, pesos: {} } } : {}) });
const GRADE = {
  positions: [{ position: "BB", hands: 800, stats: { vpip: ok(37), rfi: ok(20, 15, 25), three_bet: ok(8.5, 2, 19) } }],
  total_hands: 800, sempre: ["vpip", "rfi"], com_volume: ["three_bet"], stack_band: null, faixas: ["40+", "20-40", "<20"],
} as unknown as PositionProfileResponse;
const HUD = { total_hands: 800, vpip: 25, rfi: 28, three_bet: 8 } as unknown as PlayerStatsResponse;

describe("painel contra quem", () => {
  it("abre no clique do 3-Bet com o recorte da grade, lista por oponente num modal e fecha pelo X", async () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} stack="20-40" lastN={30} onStack={() => {}} />);
    fireEvent.click(screen.getByTestId("celula-three_bet-BB"));
    expect(detail).toHaveBeenCalledWith("BB", "three_bet", 90, 30, "20-40", "todas");   // sem mesa no payload = o jogador nao filtrou
    const painel = await screen.findByTestId("detalhe-three_bet-BB");
    // a linha Total vem PRIMEIRO, com o numero da celula, a soma das oportunidades e a cor
    const total = within(painel).getByTestId("detalhe-linha-total");
    expect(within(total).getByText("8.5")).toBeTruthy();
    expect(within(total).getByText("132")).toBeTruthy();
    expect(within(total).getByText("2–8")).toBeTruthy();
    expect(within(painel).getByTestId("detalhe-valor-total").getAttribute("data-fora")).toBe("above");
    expect(painel.querySelector("[data-testid^=detalhe-linha-]")!.getAttribute("data-testid")).toBe("detalhe-linha-total");
    const utg = within(painel).getByTestId("detalhe-linha-UTG");
    expect(within(utg).getByText("5.1")).toBeTruthy();
    expect(within(utg).getByText("2–8")).toBeTruthy();
    expect(within(utg).getByTestId("detalhe-valor-UTG")).toBeTruthy();
    const btn = within(painel).getByTestId("detalhe-linha-BTN");
    expect(within(btn).getByText("—")).toBeTruthy();                 // amostra baixa: sem numero
    expect(within(btn).getByTestId("detalhe-valor-BTN").getAttribute("data-fora")).toBeNull();   // sem cor
    // e um modal: fecha pelo X (o "Close" do DialogContent), nao pelo mesmo clique
    fireEvent.click(screen.getByText("Close"));
    await waitFor(() => expect(screen.queryByTestId("detalhe-three_bet-BB")).toBeNull());
  });

  it("o tooltip da celula clicavel tem o botao Ver detalhes, que abre o modal", async () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} stack={null} lastN={0} onStack={() => {}} />);
    const cel = screen.getByTestId("celula-three_bet-BB");
    fireEvent.pointerMove(cel); fireEvent.focus(cel);
    const botao = (await screen.findAllByTestId("ver-detalhes-three_bet-BB"))[0];
    fireEvent.click(botao);
    expect(await screen.findByTestId("detalhe-three_bet-BB")).toBeTruthy();
    expect(detail).toHaveBeenCalledWith("BB", "three_bet", 90, 0, null, "todas");
  });

  it("RFI e VPIP nao abrem painel, e so a celula clicavel e sublinhada", () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} />);
    expect(screen.queryByTestId("celula-rfi-BB")).toBeNull();
    expect(screen.queryByTestId("celula-vpip-BB")).toBeNull();
    expect(screen.getByTestId("valor-three_bet-BB").className).toContain("underline");
    expect(screen.getByTestId("valor-vpip-BB").className).not.toContain("underline");   // a BB nao tem RFI (n/a)
  });
});
