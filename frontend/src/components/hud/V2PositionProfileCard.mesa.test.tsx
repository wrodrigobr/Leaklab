// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, within, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { V2PositionProfileCard } from "./V2PositionProfileCard";
import type { PositionProfileResponse, PlayerStatsResponse } from "@/lib/api";

/**
 * Seletor de tamanho de mesa (08/09), nascido do report de um fundador: "o UTG abre mais que o
 * UTG+1, deveria ser o inverso". A causa nao era o chart: a LINHA da grade e o rotulo da sala, e
 * somar mesas de tamanhos diferentes junta assentos diferentes (o UTG de 9-max tem 8 atras; o de
 * 6-max, 5). Aqui esta travado o que a TELA faz com isso:
 *   - os chips existem, marcam a mesa que o backend DECLARA ter aplicado e chamam o setter;
 *   - a mesa em vigor viaja para a matriz (o painel pede o MESMO recorte da grade);
 *   - a nota explica o filtro, e muda quando esta em "todas";
 *   - o cabecalho do solver mostra o range do CENARIO, nao a media nas maos que cairam;
 *   - amostra pequena esconde o numero do JOGADOR e mantem o do solver.
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
vi.setConfig({ testTimeout: 30000 });

const MATRIZ = {
  position: "UTG", stack_band: null, mesa: "8max", n: 1161, voce_pct: 16.0,
  solver_pct: 14.8, solver_pct_todas: 17.4, amostra_minima: 30, cobertura: 98,
  composicao: [{ mesa: 8, n: 1161, pct: 100 }],
  cells: { AKs: { n: 12, voce: 1, limp: 0, solver: 1 }, "72o": { n: 10, voce: 0, limp: 0, solver: 0 } },
  divergencias: [], minimo_maos: 8, divergencia_minima: 0.3,
};
beforeEach(() => {
  hands.mockReset();
  hands.mockResolvedValue(MATRIZ);
});

const ok = (value: number) => ({ value, band: "ok" as const });
const grade = (mesa: string | null, auto: boolean) => ({
  positions: [
    { position: "UTG", hands: 1161, stats: { vpip: ok(15), rfi: ok(16.0) } },
    { position: "BB", hands: 900, stats: { vpip: ok(37) } },
  ],
  total_hands: 2061, sempre: ["vpip", "rfi"], com_volume: [], stack_band: null, faixas: ["40+", "20-40", "<20"],
  mesa, mesas: ["9max", "8max", "7max", "6max", "curta"], mesa_auto: auto,
  distribuicao_de_mesas: {
    mesas: [{ mesa: "8max", n: 3985, pct: 45 }, { mesa: "7max", n: 2500, pct: 28 }],
    sugerida: "8max", n: 8800,
  },
}) as unknown as PositionProfileResponse;
const HUD = { total_hands: 2061, vpip: 25, rfi: 28 } as unknown as PlayerStatsResponse;

describe("seletor de tamanho de mesa", () => {
  it("mostra so as mesas que o jogador joga, marca a que esta em vigor e chama o setter", () => {
    const onMesa = vi.fn();
    render(<MemoryRouter><V2PositionProfileCard data={grade("8max", true)} geral={HUD} onStack={() => {}} onMesa={onMesa} /></MemoryRouter>);
    const chips = screen.getByTestId("chips-mesa");
    expect(within(chips).getByTestId("chip-mesa-8max").getAttribute("aria-pressed")).toBe("true");
    expect(within(chips).getByTestId("chip-mesa-todas").getAttribute("aria-pressed")).toBe("false");
    expect(within(chips).queryByTestId("chip-mesa-9max")).toBeNull();       // ele nao joga 9-max
    fireEvent.click(within(chips).getByTestId("chip-mesa-todas"));
    expect(onMesa).toHaveBeenCalledWith("todas");
  });

  it("a nota explica o recorte, e muda quando o filtro esta desligado", () => {
    const { unmount } = render(<MemoryRouter><V2PositionProfileCard data={grade("8max", true)} geral={HUD} onStack={() => {}} onMesa={() => {}} /></MemoryRouter>);
    expect(screen.getByTestId("nota-mesa").textContent).toContain("posProfile.tableNote");
    unmount();
    render(<MemoryRouter><V2PositionProfileCard data={grade(null, false)} geral={HUD} onStack={() => {}} onMesa={() => {}} /></MemoryRouter>);
    expect(screen.getByTestId("nota-mesa").textContent).toContain("posProfile.tableNoteAll");
  });

  it("a mesa em vigor viaja para a matriz, e o cabecalho do solver e o range do CENARIO", async () => {
    render(<MemoryRouter><V2PositionProfileCard data={grade("8max", true)} geral={HUD} lastN={30} onStack={() => {}} onMesa={() => {}} /></MemoryRouter>);
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    await waitFor(() => expect(hands).toHaveBeenCalledWith("UTG", 90, 30, null, "8max"));
    const modal = await screen.findByTestId("matriz-UTG");
    // 17,4 (as 169 maos) e NAO 14,8 (a media nas maos que cairam): com amostra pequena o
    // segundo contradiz a propria grade ao lado
    expect(modal.textContent).toContain("posProfile.matrix.wouldOpen:17.4");
    expect(modal.textContent).not.toContain("posProfile.matrix.wouldOpen:14.8");
    expect(screen.getByTestId("matriz-voce-pct").textContent).toContain("posProfile.matrix.opened:16");
    expect(screen.queryByTestId("matriz-mistura")).toBeNull();     // mesa filtrada: nao ha mistura a declarar
  });

  it("amostra pequena esconde o numero do jogador, mantem o do solver e declara a mistura", async () => {
    hands.mockResolvedValue({ ...MATRIZ, mesa: null, n: 10, voce_pct: null, solver_pct: 7.2, solver_pct_todas: 20.1,
                              composicao: [{ mesa: 7, n: 6, pct: 60 }, { mesa: 8, n: 4, pct: 40 }] });
    render(<MemoryRouter><V2PositionProfileCard data={grade(null, false)} geral={HUD} lastN={30} onStack={() => {}} onMesa={() => {}} /></MemoryRouter>);
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    const modal = await screen.findByTestId("matriz-UTG");
    expect(screen.getByTestId("matriz-voce-pct").textContent).toContain("posProfile.matrix.lowSampleShort");
    expect(modal.textContent).toContain("posProfile.matrix.wouldOpen:20.1");   // a referencia SAI
    expect(screen.getByTestId("matriz-amostra").textContent).toContain("posProfile.lowSampleMatrix:30");
    expect(screen.getByTestId("matriz-mistura").textContent).toContain("7-max 60%, 8-max 40%");
  });

  it("sem o setter, nenhum chip de mesa aparece (o card fora do dashboard segue como era)", () => {
    render(<MemoryRouter><V2PositionProfileCard data={grade(null, false)} geral={HUD} /></MemoryRouter>);
    expect(screen.queryByTestId("chips-mesa")).toBeNull();
  });
});
