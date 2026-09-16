// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within, fireEvent, cleanup } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) =>
      o ? `${k}:${Object.values(o).join(",")}` : k,
  }),
}));
const evLeakHands = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, metrics: { ...real.metrics, evLeakHands: (...a: unknown[]) => evLeakHands(...a) } };
});

import { ColunaDoLeak } from "./ColunaDoLeak";

/**
 * A coluna com as mãos do leak, ao lado da mesa.
 *
 * ── O que ela precisa provar ──────────────────────────────────────────────────────────────────
 *
 * Que ela NÃO é o aside de 288px que removemos em 20/06. Aquele era fixo e encolhia a mesa em
 * toda mão, mesmo sem nada a mostrar. Esta só aparece com playlist de leak, é `absolute` no
 * contêiner da mesa (não empurra nada) e some no telefone, onde não há espaço ocioso.
 */

const MAO = (id: number, cartas: string, ev: number, tid: number) => ({
  decision_id: id, tournament_id: tid, tournament: "T", hand_id: `H${id}`,
  played_at: "2026-09-10", position: "HJ", hero_cards: cartas, board: "[]",
  stack_bb: 67, ev_loss_bb: ev, gto_label: "gto_critical", label: "clear_mistake",
});

// as quatro primeiras do leak real, com os torneios reais: elas ATRAVESSAM torneios
const HANDS = [MAO(1, "QhJd", 2.79, 18), MAO(2, "4dAd", 2.28, 2),
               MAO(3, "Kh7h", 1.82, 30), MAO(4, "3h3c", 1.66, 19)];

const SPOT = { street: "preflop", actionTaken: "call", bestAction: "fold" };

function monta(handId = "H3") {
  const aoIr = vi.fn();
  const r = render(
    <ColunaDoLeak spot={SPOT} lastN={50} handId={handId}
                  hrefDaMao={(h) => `/replayer?h=${h}&leak=x`} aoIr={aoIr} />);
  return { aoIr, ...r };
}

describe("coluna do leak", () => {
  beforeEach(() => {
    localStorage.clear();
    evLeakHands.mockReset();
    evLeakHands.mockResolvedValue({
      total: 12, loss_bb: 12.2, limit: 200, offset: 0,
      street: SPOT.street, action_taken: SPOT.actionTaken, best_action: SPOT.bestAction,
      hands: HANDS,
    });
  });

  // Sem isto o render do caso anterior fica no DOM e `findByTestId` acha dois.
  afterEach(cleanup);

  it("lista as mãos do leak com as cartas desenhadas, no mesmo recorte da lista", async () => {
    monta();
    const col = await screen.findByTestId("leak-coluna");
    // o `lastN` vai na chamada: a coluna responde pelo MESMO recorte do card que a gerou, senão
    // o "12" dela e o "12" do contador falariam de janelas diferentes
    expect(evLeakHands).toHaveBeenCalledWith("preflop", "call", "fold", 50, 200);
    const linha = within(col).getByTestId("leak-coluna-mao-2");
    // `4dAd` sai com o ás na frente — a ordenação mora em `HeroHand`
    expect(within(linha).getAllByRole("img").map((i) => i.getAttribute("alt"))).toEqual(["Ad", "4d"]);
    expect(linha.textContent).toContain("−2.28");
  });

  it("marca a mão atual e apaga as que já passaram", async () => {
    monta("H3");
    const col = await screen.findByTestId("leak-coluna");
    const atual = within(col).getByTestId("leak-coluna-mao-3");
    expect(atual.getAttribute("aria-current")).toBe("true");
    // as duas de cima (mais caras, já revistas) ficam apagadas; a de baixo, não
    expect(within(col).getByTestId("leak-coluna-mao-1").className).toContain("opacity-45");
    expect(within(col).getByTestId("leak-coluna-mao-4").className).not.toContain("opacity-45");
  });

  it("clicar numa mão navega pelo MESMO href da navegação por setas", async () => {
    // Sem isto a coluna seria uma segunda forma de montar o link, e a que erra manda o jogador
    // para uma mão que não existe naquele torneio.
    const { aoIr } = monta();
    const col = await screen.findByTestId("leak-coluna");
    fireEvent.click(within(col).getByTestId("leak-coluna-mao-4"));
    expect(aoIr).toHaveBeenCalledWith("/replayer?h=H4&leak=x");
  });

  it("recolhe, lembra a escolha, e volta a abrir", async () => {
    monta();
    const col = await screen.findByTestId("leak-coluna");
    fireEvent.click(within(col).getByRole("button", { name: "close" }));
    expect(screen.queryByTestId("leak-coluna")).toBeNull();
    expect(localStorage.getItem("replayer_coluna_leak")).toBe("false");
    // recolhida, sobra o botão que diz quantas mãos esperam
    expect((await screen.findByTestId("leak-coluna-abrir")).textContent).toContain("12");
  });

  it("some inteira quando o leak não tem mão medida", async () => {
    // A régua da casa: sem dado o bloco SOME, nunca renderiza vazio fingindo informação.
    evLeakHands.mockResolvedValue({
      total: 0, loss_bb: 0, limit: 200, offset: 0,
      street: SPOT.street, action_taken: SPOT.actionTaken, best_action: SPOT.bestAction, hands: [],
    });
    monta();
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByTestId("leak-coluna")).toBeNull();
    expect(screen.queryByTestId("leak-coluna-abrir")).toBeNull();
  });

  it("não empurra a mesa: é absolute e só aparece no desktop", async () => {
    // O que separa esta coluna do aside de 288px removido em 20/06. `absolute` não participa do
    // fluxo, então a mesa mantém a largura; `hidden lg:flex` a tira do telefone, onde não há
    // espaço ocioso para ocupar.
    monta();
    const col = await screen.findByTestId("leak-coluna");
    expect(col.className).toContain("absolute");
    expect(col.className).toContain("hidden");
    expect(col.className).toContain("lg:flex");
  });
});
