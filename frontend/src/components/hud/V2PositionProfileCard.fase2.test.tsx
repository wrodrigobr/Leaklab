// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { V2PositionProfileCard } from "./V2PositionProfileCard";
import type { PlayerStatsResponse, PositionProfileResponse } from "@/lib/api";

/**
 * Fase 2 (06/09): 3-Bet e Fold 3-Bet do open com régua, e o tooltip com o VERBO do stat.
 * "Você abre X pontos a mais" numa célula de fold ao 3-bet seria copy errada em silêncio:
 * o teste ancora na chave de i18n escolhida por stat. E a cobertura só aparece quando é
 * parcial: dizer "100% das oportunidades têm chart" é ruído.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));

afterEach(cleanup);

const cel = (value: number, lo: number, hi: number, cobertura = 100) =>
  ({ value, band: "ok" as const, ref: { lo, hi, folga: 3, pesos: { "40bb vs UTG": 70, "30bb vs CO": 30 }, cobertura } });

const GRADE = {
  positions: [
    { position: "CO", hands: 900, stats: { rfi: cel(39, 34, 42), three_bet: cel(8.5, 2.5, 13), fold_to_3bet: cel(58.8, 88, 97, 91) } },
  ],
  total_hands: 900,
  sempre: ["rfi"],
  com_volume: ["three_bet", "fold_to_3bet"],
  stack_band: null,
  faixas: ["40+", "20-40", "<20"],
} as unknown as PositionProfileResponse;
const HUD = { total_hands: 900, rfi: 28, three_bet: 8, fold_to_3bet: 57 } as unknown as PlayerStatsResponse;

describe("fase 3: VPIP e PFR com a media do solver", () => {
  const media = (value: number, lo: number, hi: number, valor_coberto: number, cobertura = 88) =>
    ({ value, band: "ok" as const, ref: { lo, hi, folga: 3.3, pesos: { "50bb": 40, "40bb vs UTG": 30 }, cobertura, tipo: "media" as const, valor_coberto } });
  const grade = {
    ...GRADE,
    sempre: ["vpip", "pfr", "rfi"],
    positions: [{ position: "BTN", hands: 855, stats: { vpip: media(25.1, 29, 36.1, 26.2), pfr: media(20.4, 19.3, 25.5, 22), rfi: cel(51.9, 47.9, 58) } }],
  } as unknown as PositionProfileResponse;

  it("VPIP e PFR ganham regua quando o backend manda ref de tipo media", () => {
    render(<V2PositionProfileCard data={grade} geral={HUD} />);
    expect(screen.getByTestId("valor-vpip-BTN").getAttribute("data-fora")).toBe("below");
    expect(screen.getByTestId("valor-pfr-BTN").getAttribute("data-fora")).toBe("in");
  });

  it("o tooltip da media diz que e media nas suas maos, sem o diagnostico interno", async () => {
    render(<V2PositionProfileCard data={grade} geral={HUD} />);
    fireEvent.pointerMove(screen.getByText("25.1"));
    fireEvent.focus(screen.getByText("25.1"));
    expect((await screen.findAllByText(/posProfile[.]vsSolver[.]vpip[.]below:3[.]9/)).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/posProfile[.]solverYourHands/)).length).toBeGreaterThan(0);
    // o diagnostico interno (pesos dos charts, folga, cobertura) NAO vai para o jogador (dono, 07/09)
    expect(screen.queryByText(/posProfile[.]bandMean/)).toBeNull();
    expect(screen.queryByText(/posProfile[.]youCovered/)).toBeNull();
    expect(screen.queryByText(/posProfile[.]charts/)).toBeNull();
  });
});

describe("veredito em texto", () => {
  it("dentro da faixa nao ha frase; fora, a frase traz o tamanho do desvio", async () => {
    const grade = {
      ...GRADE,
      positions: [{ position: "CO", hands: 900, stats: { rfi: cel(39, 34, 42), three_bet: cel(16, 2.5, 13) } }],
    } as unknown as PositionProfileResponse;
    render(<V2PositionProfileCard data={grade} geral={HUD} />);
    fireEvent.pointerMove(screen.getByText("39"));
    fireEvent.focus(screen.getByText("39"));
    expect((await screen.findAllByText(/posProfile[.]solverHere/)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/posProfile[.]inSolver/)).toBeNull();          // dentro: sem frase
    expect(screen.queryByText(/posProfile[.]vsSolver/)).toBeNull();
    fireEvent.pointerMove(screen.getByText("16"));
    fireEvent.focus(screen.getByText("16"));
    expect((await screen.findAllByText(/posProfile[.]vsSolver[.]threeBet[.]above:3[.]0/)).length).toBeGreaterThan(0);
  });
});

describe("fase 2", () => {
  it("as tres colunas tem regua, cada uma na propria escala", () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} />);
    expect(screen.getByTestId("valor-rfi-CO").getAttribute("data-fora")).toBe("in");
    expect(screen.getByTestId("valor-three_bet-CO").getAttribute("data-fora")).toBe("in");
    expect(screen.getByTestId("valor-fold_to_3bet-CO").getAttribute("data-fora")).toBe("below");
    // o cabecalho nao repete "Fold 3Bet" do HUD com outro nome
    expect(screen.getAllByText("Fold 3Bet")).toHaveLength(1);
  });

  it("o tooltip usa o verbo do stat e nao expoe o diagnostico interno", async () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} />);
    fireEvent.pointerMove(screen.getByText("58.8"));
    fireEvent.focus(screen.getByText("58.8"));
    const frase = await screen.findAllByText(/posProfile\.vsSolver\.fold3bet\.below:29\.2/);
    expect(frase.length).toBeGreaterThan(0);
    expect(screen.queryByText(/posProfile\.coverage/)).toBeNull();     // cobertura e diagnostico interno
  });
});
