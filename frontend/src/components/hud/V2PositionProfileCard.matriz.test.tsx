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
    assentos: ["UTG", "LJ", "HJ", "CO", "BTN", "SB"],
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
  return render(<MemoryRouter><V2PositionProfileCard data={GRADE} geral={HUD} lastN={30} /></MemoryRouter>);
}

describe("matriz das maos abertas", () => {
  it("o RFI e clicavel e abre a matriz no recorte da grade, com as duas grades e as divergencias", async () => {
    monta();
    expect(screen.getByTestId("valor-rfi-UTG").className).toContain("underline");
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    // O modal nao herda recorte da grade (ela nao tem mais filtro): pede sem stack e sem mesa,
    // e o BACKEND escolhe onde ha mais maos e declara no payload.
    expect(hands).toHaveBeenCalledWith("UTG", 90, 30, null, null);
    const modal = await screen.findByTestId("matriz-UTG");
    // A comparacao e UM par de numeros sobre AS MESMAS maos (dono, 09/09: dois numeros de
    // solver era um a mais). 17,2 contra 18,5 = 1,3 ponto: dentro da folga, "no alvo".
    expect(screen.getByTestId("matriz-recorte").textContent).toContain("posProfile.matrix.recorte:UTG");
    expect(screen.getByTestId("matriz-voce-pct").textContent).toBe("17.2%");
    expect(screen.getByTestId("matriz-solver-pct").textContent).toBe("18.5%");
    expect(screen.getByTestId("matriz-delta").textContent).toContain("posProfile.matrix.deltaOk");
    expect(modal.textContent).toContain("posProfile.matrix.sameHandsCovered:1.211,98");   // cobertura na frase, nao no titulo
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
    // a BB nao abre pote: DESLIGADA e com o motivo, nao ausente (ausencia parecia esquecimento)
    const bb = within(sel).getByTestId("matriz-pos-BB") as HTMLButtonElement;
    expect(bb.disabled).toBe(true);
    expect(bb.title).toBe("posProfile.matrix.bbNoRfi");
    expect(within(sel).getByTestId("matriz-stack-20-40").getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(within(sel).getByTestId("matriz-stack-40+"));
    await waitFor(() => expect(hands).toHaveBeenLastCalledWith("UTG", 90, 30, "40+", null));
    fireEvent.click(within(await screen.findByTestId("matriz-seletores")).getByTestId("matriz-pos-HJ"));
    await waitFor(() => expect(hands).toHaveBeenLastCalledWith("HJ", 90, 30, "40+", null));
    // nao existe chip "todos" de stack
    expect(within(await screen.findByTestId("matriz-seletores")).queryByTestId("matriz-stack-todos")).toBeNull();
  });

  it("o tamanho da mesa e o terceiro filtro do modal, e os assentos seguem a mesa", async () => {
    // Ate 09/09 a mesa vinha herdada da grade sem aparecer no modal, e foi por isso que um
    // fundador nao sabia que olhava mesa de 7. Agora e chip, com a fatia do volume.
    hands.mockResolvedValue({
      position: "UTG", stack_band: "20-40", mesa: "8max", n: 1161, voce_pct: 16.0, solver_pct: 14.8, solver_pct_todas: 17.4,
      cobertura: 98, assentos: ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB"], jogadores_atras: 7,
      distribuicao_de_mesas: { mesas: [{ mesa: "8max", n: 3985, pct: 45 }, { mesa: "7max", n: 2500, pct: 28 }], sugerida: "8max", n: 6485 },
      distribuicao_de_stacks: { faixas: [{ faixa: "40+", n: 500, pct: 43 }, { faixa: "20-40", n: 661, pct: 57 }], sugerida: "20-40", n: 1161 },
      cells: { AKs: { n: 12, voce: 1, limp: 0, solver: 1 } }, divergencias: [], minimo_maos: 8, divergencia_minima: 0.3,
    });
    monta();
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    const sel = await screen.findByTestId("matriz-seletores");
    // mesa de 8 na mao: o UTG+1 EXISTE (convencao do dono); o chip da mesa mostra a fatia
    expect(within(sel).getByTestId("matriz-pos-UTG+1")).toBeTruthy();
    expect(within(sel).getByTestId("matriz-mesa-8max").getAttribute("aria-pressed")).toBe("true");
    expect(within(sel).getByTestId("matriz-mesa-8max").textContent).toContain("45%");
    expect(within(sel).getByTestId("matriz-stack-20-40").textContent).toContain("661");   // maos na faixa
    // a frase do recorte diz o que esta sendo comparado, e a linha do solver diz por que
    expect(screen.getByTestId("matriz-recorte").textContent).toContain("posProfile.matrix.recorte:UTG,posProfile.tableSize.8max,posProfile.matrix.stackWords.20-40,1.161");
    expect(screen.getByTestId("matriz-referencia").textContent).toContain("posProfile.matrix.behind:7");
    expect(screen.getByTestId("matriz-range-size").textContent).toContain("posProfile.matrix.rangeSize:17.4");
    // trocar a mesa pede a matriz de novo, sem fechar o modal
    fireEvent.click(within(sel).getByTestId("matriz-mesa-7max"));
    await waitFor(() => expect(hands).toHaveBeenLastCalledWith("UTG", 90, 30, "20-40", "7max"));
  });

  it("assento que nao existe na mesa nova volta para o UTG em vez de mostrar recorte vazio", async () => {
    // UTG+1 some com 7 na mao, LJ some com 6: o modal nao pode ficar num assento que a mesa nao tem
    hands.mockResolvedValueOnce({
      position: "HJ", stack_band: "20-40", mesa: "curta", n: 0, voce_pct: null, solver_pct: null, cobertura: 0,
      assentos: ["UTG", "CO", "BTN", "SB"], cells: {}, divergencias: [], minimo_maos: 8, divergencia_minima: 0.3,
    });
    monta();
    fireEvent.click(screen.getByTestId("celula-rfi-HJ"));
    await waitFor(() => expect(hands).toHaveBeenLastCalledWith("UTG", 90, 30, "20-40", "curta"));
  });

  /**
   * AY-34. Duvida de um fundador em 09/09: "to achando essa porcentagem que o solver abriria um
   * tanto quanto alta, de onde vem esse valor?". Vinha da carta CERTA: o "UTG" dele era de mesa
   * de 7, que tem 6 jogadores atras, e a carta de 6 atras abre bem mais que a de 8. O numero
   * estava certo e a tela nao dizia de onde vinha, nem que os dois lados do cabecalho olham
   * conjuntos diferentes (o dele so as maos que recebeu, o do solver o range inteiro).
   *
   * Dizer o nome do assento no vocabulario 9-max NAO resolve: a tela chama esse mesmo assento de
   * UTG, entao escrever "UTG+2" troca uma duvida por outra. O que fecha e quantos agem depois.
   */
  it("o solver declara de qual carta veio o numero, e o que o numero das SUAS maos seria", async () => {
    hands.mockResolvedValue({
      position: "UTG", stack_band: "40+", mesa: "7max", n: 1519, voce_pct: 17.5, solver_pct: 19.4,
      solver_pct_todas: 20.0, cobertura: 98, assento_da_carta: "UTG+2", jogadores_atras: 6,
      cells: { AA: { n: 3, voce: 1, limp: 0, solver: 1 } }, divergencias: [],
      minimo_maos: 8, divergencia_minima: 0.3,
    });
    render(<MemoryRouter><V2PositionProfileCard data={GRADE} geral={HUD} lastN={30} /></MemoryRouter>);
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    const ref = await screen.findByTestId("matriz-referencia");
    expect(ref.textContent).toContain("posProfile.matrix.behind:6");           // 6 por agir, nao "UTG+2"
    expect(ref.textContent).not.toContain("behindMixed");
    // o par comparavel: 17,5 contra 19,4 sobre AS MESMAS maos; o 20,0 (range inteiro) e so legenda
    expect(screen.getByTestId("matriz-voce-pct").textContent).toBe("17.5%");
    expect(screen.getByTestId("matriz-solver-pct").textContent).toBe("19.4%");
    expect(screen.getByTestId("matriz-range-size").textContent).toContain("posProfile.matrix.rangeSize:20.0");
  });

  it("recorte sem carta unica nao promete referencia", async () => {
    hands.mockResolvedValue({
      position: "UTG", stack_band: null, n: 3690, voce_pct: 17.2, solver_pct: 18.5,
      solver_pct_todas: 20.4, cobertura: 98, assento_da_carta: null, jogadores_atras: null,
      cells: { AA: { n: 3, voce: 1, limp: 0, solver: 1 } }, divergencias: [],
      minimo_maos: 8, divergencia_minima: 0.3,
    });
    render(<MemoryRouter><V2PositionProfileCard data={GRADE} geral={HUD} lastN={30} /></MemoryRouter>);
    fireEvent.click(screen.getByTestId("celula-rfi-UTG"));
    const ref = await screen.findByTestId("matriz-referencia");
    expect(ref.textContent).toContain("posProfile.matrix.behindMixed");
    expect(ref.textContent).not.toContain("posProfile.matrix.behind:");
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
