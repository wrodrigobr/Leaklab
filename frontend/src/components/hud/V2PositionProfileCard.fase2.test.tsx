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
    { position: "CO", hands: 900, stats: { rfi: cel(39, 34, 42), three_bet: cel(8.5, 2.5, 13), fold_to_3bet_open: cel(58.8, 88, 97, 91) } },
  ],
  total_hands: 900,
  sempre: ["rfi"],
  com_volume: ["three_bet", "fold_to_3bet_open"],
  stack_band: null,
  faixas: ["40+", "20-40", "<20"],
} as unknown as PositionProfileResponse;
const HUD = { total_hands: 900, rfi: 28, three_bet: 8, fold_to_3bet_open: 57 } as unknown as PlayerStatsResponse;

describe("fase 2", () => {
  it("as tres colunas tem regua, cada uma na propria escala", () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} />);
    expect(screen.getByTestId("regua-rfi").getAttribute("data-fora")).toBe("in");
    expect(screen.getByTestId("regua-three_bet").getAttribute("data-fora")).toBe("in");
    expect(screen.getByTestId("regua-fold_to_3bet_open").getAttribute("data-fora")).toBe("below");
    // o cabecalho nao repete "Fold 3Bet" do HUD com outro nome
    expect(screen.getAllByText("Fold 3Bet")).toHaveLength(1);
  });

  it("o tooltip usa o verbo do stat e so mostra cobertura quando e parcial", async () => {
    render(<V2PositionProfileCard data={GRADE} geral={HUD} />);
    fireEvent.pointerMove(screen.getByText("58.8"));
    fireEvent.focus(screen.getByText("58.8"));
    const frase = await screen.findAllByText(/posProfile\.vsSolver\.fold3bet\.below:29\.2/);
    expect(frase.length).toBeGreaterThan(0);
    expect((await screen.findAllByText(/posProfile\.coverage:91/)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/posProfile\.coverage:100/)).toBeNull();
  });
});
