// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, within, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { V2PositionProfileCard } from "./V2PositionProfileCard";
import type { PositionProfileResponse, PlayerStatsResponse } from "@/lib/api";

/**
 * Matriz 13x13 das maos abertas (AY-15 c): a celula RFI e clicavel e abre um modal com DUAS
 * grades (voce e solver, a mesma RangeGrid de /ranges) e a lista de divergencias, no recorte
 * da grade (assento e faixa de stack). A BB nao tem RFI, logo nao tem matriz.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));
const hands = vi.fn();
const detail = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, metrics: { ...real.metrics, playerStatsByPositionHands: (...a: unknown[]) => hands(...a), playerStatsByPositionDetail: (...a: unknown[]) => detail(...a) } };
});

afterEach(cleanup);
// tooltips do Radix e duas grades de 169 celulas passam de 5s com a suite inteira em paralelo
vi.setConfig({ testTimeout: 30000 });
beforeEach(() => {
  hands.mockReset();
  hands.mockResolvedValue({
    position: "UTG", stack_band: "20-40", n: 1211, voce_pct: 17.2, solver_pct: 18.5, cobertura: 98,
    cells: { AKs: { n: 12, voce: 1, limp: 0, solver: 1 }, T9s: { n: 9, voce: 0.444, limp: 0, solver: 1 }, "72o": { n: 10, voce: 0, limp: 0, solver: 0 }, AQs: { n: 0, voce: null, limp: null, solver: 1 }, AA: { n: 3, voce: 0.667, limp: 0.333, solver: 1 } },
    divergencias: [{ hand: "T9s", n: 9, voce: 0.444, solver: 1, delta: -0.556 }],
    minimo_maos: 8, divergencia_minima: 0.3,
  });
});

const ok = (value: number, lo?: number, hi?: number) =>
  ({ value, band: "ok" as const, ...(lo != null ? { ref: { lo, hi, folga: 3, pesos: {} } } : {}) });
const GRADE = {
  positions: [
    { position: "UTG", hands: 1211, stats: { vpip: ok(15), rfi: ok(17.2, 15, 25), three_bet: ok(4, 2, 8) } },
    { position: "HJ", hands: 700, stats: { vpip: ok(22), rfi: ok(27.9, 20, 32) } },
    { position: "BB", hands: 900, stats: { vpip: ok(37), three_bet: ok(8.5, 2, 19) } },
  ],
  total_hands: 2111, sempre: ["vpip", "rfi"], com_volume: ["three_bet"], stack_band: "20-40", faixas: ["40+", "20-40", "<20"],
} as unknown as PositionProfileResponse;
const HUD = { total_hands: 2111, vpip: 25, rfi: 28, three_bet: 8 } as unknown as PlayerStatsResponse;

function monta() {
  return render(<MemoryRouter><V2PositionProfileCard data={GRADE} geral={HUD} stack="20-40" lastN={30} onStack={() => {}} /></MemoryRouter>);
}

describe("matriz das maos abertas", () => {
  it("o RFI e clicavel e abre a matriz no recorte da grade, com as duas grades e as divergencias", async () => {
    monta();
    expect(screen.getByTestId("valor-rfi-UTG").className).toContain("underline");
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    expect(hands).toHaveBeenCalledWith("UTG", 90, 30, "20-40");
    const modal = await screen.findByTestId("matriz-UTG");
    expect(modal.textContent).toContain("posProfile.matrix.opps:1.211");
    expect(modal.textContent).toContain("posProfile.matrix.opened:17.2");
    expect(modal.textContent).toContain("posProfile.matrix.wouldOpen:18.5");
    expect(modal.textContent).toContain("posProfile.matrix.covers:98");        // cobertura no titulo, sem legenda
    expect(modal.textContent).toContain("posProfile.matrix.divergencesNote:8,30");
    expect(modal.textContent).not.toContain("legendYou");
    // duas grades de 169 celulas, a mesma RangeGrid de /ranges
    expect(within(screen.getByTestId("matriz-voce")).getAllByTitle(/^AKs:|^T9s:|^72o:|^AA:/).length).toBeGreaterThanOrEqual(4);
    expect(within(screen.getByTestId("matriz-solver")).getByTitle(/^T9s: Raise 100%/)).toBeTruthy();
    expect(within(screen.getByTestId("matriz-voce")).getByTitle(/^T9s: Raise 44%/)).toBeTruthy();
    // AQs nunca recebida: apagada na SUA grade com o aviso, e 100% raise na do solver (nao e fold)
    const aqs = within(screen.getByTestId("matriz-voce")).getByTitle("AQs: posProfile.matrix.neverDealt");
    expect(aqs.getAttribute("data-sem-dado")).toBe("true");
    expect(within(screen.getByTestId("matriz-solver")).getByTitle(/^AQs: Raise 100%/).getAttribute("data-sem-dado")).toBeNull();
    expect(within(screen.getByTestId("matriz-voce")).getByTitle(/^72o: Fold 100%/).getAttribute("data-sem-dado")).toBeNull();   // recebeu e foldou
    // AA: 2 raises e 1 limp; o limp aparece como Call, nunca como Fold
    expect(within(screen.getByTestId("matriz-voce")).getByTitle(/^AA: Raise 67% · Call 33%$/)).toBeTruthy();
    // a lista de divergencias
    const linha = within(screen.getByTestId("matriz-divergencias")).getByTestId("divergencia-T9s");
    expect(linha.textContent).toContain("T9s");
    expect(linha.textContent).toContain("44%");
    expect(linha.textContent).toContain("100%");
    expect(linha.textContent).toContain("-56 pp");
    // o "contra quem" nao foi pedido
    expect(detail).not.toHaveBeenCalled();
    // fecha pelo X
    fireEvent.click(screen.getByText("Close"));
    await waitFor(() => expect(screen.queryByTestId("matriz-UTG")).toBeNull());
  });

  it("os chips do modal trocam assento e stack sem sair dele, e pedem a matriz de novo", async () => {
    monta();
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    const sel = await screen.findByTestId("matriz-seletores");
    expect(within(sel).getByTestId("matriz-pos-UTG").getAttribute("aria-pressed")).toBe("true");
    expect(within(sel).queryByTestId("matriz-pos-BB")).toBeNull();                // a BB nao abre pote
    expect(within(sel).getByTestId("matriz-stack-20-40").getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(within(sel).getByTestId("matriz-stack-40+"));
    await waitFor(() => expect(hands).toHaveBeenLastCalledWith("UTG", 90, 30, "40+"));
    fireEvent.click(within(await screen.findByTestId("matriz-seletores")).getByTestId("matriz-pos-HJ"));
    await waitFor(() => expect(hands).toHaveBeenLastCalledWith("HJ", 90, 30, "40+"));
    fireEvent.click(within(await screen.findByTestId("matriz-seletores")).getByTestId("matriz-stack-todos"));
    await waitFor(() => expect(hands).toHaveBeenLastCalledWith("HJ", 90, 30, null));
  });

  it("a BB nao tem RFI nem matriz; o 3-Bet continua abrindo o contra quem", () => {
    detail.mockResolvedValue({ position: "BB", stat: "three_bet", stack_band: null, minimo: 30, rows: [], total: { n: 0, value: null, ref: null } });
    monta();
    expect(screen.queryByTestId("celula-rfi-BB")).toBeNull();
    fireEvent.click(screen.getByTestId("celula-three_bet-BB"));
    expect(detail).toHaveBeenCalled();
    expect(hands).not.toHaveBeenCalled();
  });

  it("sem carta para o recorte, o lado do solver diz isso em vez de um numero", async () => {
    hands.mockResolvedValue({ position: "UTG", stack_band: null, n: 20, voce_pct: 10, solver_pct: null, cobertura: 0,
      cells: { AKs: { n: 20, voce: 0.1, limp: 0, solver: null } }, divergencias: [], minimo_maos: 8, divergencia_minima: 0.3 });
    monta();
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    const modal = await screen.findByTestId("matriz-UTG");
    expect(modal.textContent).toContain("posProfile.matrix.noChart");
    expect(modal.textContent).toContain("posProfile.matrix.noDivergence:8,30");
  });
});
