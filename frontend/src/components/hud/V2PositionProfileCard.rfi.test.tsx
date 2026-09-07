// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, within } from "@testing-library/react";
import { V2PositionProfileCard } from "./V2PositionProfileCard";
import type { PlayerStatsResponse, PositionProfileResponse } from "@/lib/api";

/**
 * A régua voltou SÓ no RFI (AY-15, 06/09), e o filtro de stack.
 *
 * O que um refactor quebra sem que nada mais falhe:
 * 1. A régua só existe onde o backend manda `ref`. Desenhar régua em VPIP/PFR seria voltar a
 *    acusar por assento com a régua do jogo inteiro, o defeito de 05/09.
 * 2. A tinta vai para o lado certo: valor ABAIXO da faixa pinta entre o valor e `lo`; ACIMA,
 *    entre `hi` e o valor. Trocar os lados passa verde em qualquer snapshot.
 * 3. Os chips chamam `onStack` com a faixa do backend (`faixas`), e "todos" é null.
 * 4. A BB mostra "n/a" no RFI, não "—": traço é amostra baixa, isto é regra.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));

afterEach(cleanup);

const ok = (value: number) => ({ value, band: "ok" as const });
const rfi = (value: number, lo: number, hi: number) =>
  ({ value, band: "ok" as const, ref: { lo, hi, folga: 3, pesos: { "50bb": 60, "30bb": 35, "10bb": 5 } } });

const GRADE = {
  positions: [
    { position: "UTG", hands: 400, stats: { vpip: ok(18), pfr: ok(17), rfi: rfi(22, 12, 19) } },   // acima
    { position: "BTN", hands: 500, stats: { vpip: ok(30), pfr: ok(25), rfi: rfi(40, 48, 58) } },   // abaixo
    { position: "BB", hands: 450, stats: { vpip: ok(35), pfr: ok(10) } },                            // sem RFI
  ],
  total_hands: 1350,
  sempre: ["vpip", "pfr", "rfi"],
  com_volume: [],
  stack_band: null,
  faixas: ["40+", "20-40", "<20"],
} as unknown as PositionProfileResponse;

const HUD = { total_hands: 1350, vpip: 27, pfr: 17, rfi: 31 } as unknown as PlayerStatsResponse;

describe("régua do RFI", () => {
  it("desenha régua SÓ na célula com ref, e pinta o excesso para o lado certo", () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} />);
    // a cor (data-fora) so onde ha ref: UTG e BTN no RFI; VPIP/PFR sem ref ficam brancos
    const comCor = screen.getAllByTestId(/^valor-rfi-/).filter((e) => e.getAttribute("data-fora"));
    expect(comCor).toHaveLength(2);                       // UTG e BTN; BB nao tem RFI; Total nao tem cor
    expect(screen.getAllByTestId(/^valor-vpip-/).every((e) => !e.getAttribute("data-fora"))).toBe(true);
    expect(screen.getAllByTestId(/^valor-pfr-/).every((e) => !e.getAttribute("data-fora"))).toBe(true);
    expect(comCor[0].getAttribute("data-fora")).toBe("above");   // UTG 22 > 19
    expect(comCor[1].getAttribute("data-fora")).toBe("below");   // BTN 40 < 48
    expect(comCor[0].textContent).toContain("▲");
    expect(comCor[1].textContent).toContain("▼");
  });

  it("a linha TOTAL mostra o RFI do HUD sem régua", () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} />);
    const total = screen.getByText("posProfile.total").closest("div")!;
    expect(within(total).getByText("31")).toBeTruthy();
    expect(within(total).queryByTestId("regua-rfi")).toBeNull();
  });

  it("a BB mostra n/a nas colunas de abertura, não o traço de amostra baixa", () => {
    const comFold = {
      ...GRADE,
      com_volume: ["fold_to_3bet"],
      positions: [...GRADE.positions.slice(0, 2),
                  { position: "BB", hands: 450, stats: { vpip: ok(35), pfr: ok(10), fold_to_3bet: ok(100) } }],
    } as unknown as PositionProfileResponse;
    render(<V2PositionProfileCard data={comFold} geral={HUD} />);
    expect(screen.getAllByText("n/a")).toHaveLength(2);      // RFI e Fold 3-Bet do open
    expect(screen.queryByText("100")).toBeNull();            // o "100" sem chart nao aparece
  });

  it("amostra baixa nao desenha regua nenhuma, so o traco", () => {
    const baixa = { value: 31, band: "low_sample" as const, ref: { lo: 12, hi: 19, folga: 3, pesos: {} } };
    const grade = { ...GRADE, positions: [{ position: "LJ", hands: 2, stats: { vpip: ok(1), pfr: ok(1), rfi: baixa } }] } as unknown as PositionProfileResponse;
    render(<V2PositionProfileCard data={grade} geral={{ ...HUD, rfi: 29 } as PlayerStatsResponse} />);
    const lj = screen.getByTestId("valor-rfi-LJ");
    expect(lj.getAttribute("data-fora")).toBeNull();      // sem cor
    expect(lj.textContent).toBe("—");                     // so o traco (o Total mostra 29)
    expect(screen.queryByText("31")).toBeNull();
  });
});

describe("filtro de stack", () => {
  it("os chips vêm das faixas do backend e chamam onStack; todos é null", () => {
    const onStack = vi.fn();
    render(<V2PositionProfileCard data={GRADE} geral={HUD} stack={null} onStack={onStack} />);
    fireEvent.click(screen.getByText("20–40bb"));
    expect(onStack).toHaveBeenCalledWith("20-40");
    fireEvent.click(screen.getByText("posProfile.stackAll"));
    expect(onStack).toHaveBeenCalledWith(null);
    expect(screen.getByText("40bb+").getAttribute("aria-pressed")).toBe("false");
  });

  it("sem onStack não há chips (card em modo só leitura)", () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} />);
    expect(screen.queryByText("20–40bb")).toBeNull();
  });

  it("com faixa escolhida o cabeçalho diz que as mãos são da faixa", () => {
    render(<V2PositionProfileCard data={{ ...GRADE, stack_band: "20-40" } as PositionProfileResponse}
                                  geral={HUD} stack="20-40" onStack={() => {}} />);
    expect(screen.getByText("posProfile.stackHands:1350")).toBeTruthy();
    expect(screen.getByText("20–40bb").getAttribute("aria-pressed")).toBe("true");
  });
});
