// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, within, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

/**
 * AY-32: as mãos por trás de uma linha do card "Leaks por custo", e o link para o replayer.
 * Pedido de um fundador: *"é possível cada uma dessas linhas ser clicável, e mostrar a lista de
 * mãos em que esta situação ocorreu? e nesta lista conseguirmos abrir o replayer?"*.
 *
 * O que está travado aqui é a HONESTIDADE da lista. Ela pede o spot EXATO da linha (street +
 * jogada + ideal), porque a consulta que já existia filtra só por street e assento e traria mãos
 * de outro par de ação. E quando o total não bate com o número da linha, a tela DIZ isso, em vez
 * de deixar o jogador concluir sozinho que faltou dado.
 */
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (k: string, o?: Record<string, unknown>) => (o && Object.keys(o).length ? `${k}:${Object.values(o).join(",")}` : k),
    i18n: { language: "pt-BR" },
  }),
}));
const navigate = vi.fn();
vi.mock("react-router-dom", async (orig) => {
  const real = await orig<typeof import("react-router-dom")>();
  return { ...real, useNavigate: () => navigate };
});
const evLeakHands = vi.fn();
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, metrics: { ...real.metrics, evLeakHands: (...a: unknown[]) => evLeakHands(...a) } };
});

import { MaosDoLeak } from "./MaosDoLeak";

const MAO = (id: number, cartas: string, ev: number) => ({
  decision_id: id, tournament_id: 900 + id, tournament: "SNG $2", hand_id: `H${id}`,
  played_at: "2026-09-01", position: "BB", hero_cards: cartas, board: "[]",
  stack_bb: 23.4, ev_loss_bb: ev, gto_label: "gto_critical", label: "clear_mistake",
});

function monta(esperado = 19) {
  return render(
    <MemoryRouter>
      <MaosDoLeak street="flop" actionTaken="fold" bestAction="call" esperado={esperado} lastN={50} />
    </MemoryRouter>
  );
}
beforeEach(() => { evLeakHands.mockReset(); navigate.mockReset(); });
afterEach(cleanup);

describe("mãos por trás de um leak", () => {
  it("pede o spot EXATO da linha, lista as mãos e abre o replayer", async () => {
    evLeakHands.mockResolvedValue({
      total: 19, loss_bb: 41.9, limit: 200, offset: 0,
      street: "flop", action_taken: "fold", best_action: "call",
      hands: [MAO(1, "KhJs", 6.4), MAO(2, "9h9d", 3.1)],
    });
    monta();
    // street + jogada + ideal: é o que impede a lista de trazer mãos de outro par de ação
    await waitFor(() => expect(evLeakHands).toHaveBeenCalledWith("flop", "fold", "call", 50, 200));
    const painel = await screen.findByTestId("leak-maos");
    expect(painel.textContent).toContain("v2.leakHandsTitle:19,41.9");
    expect(painel.textContent).toContain("v2.leakHandsPartial:2,19");   // declara que mostra parte
    const linha = within(painel).getByTestId("leak-mao-1");
    expect(linha.textContent).toContain("KhJs");
    expect(linha.textContent).toContain("−6.40bb");
    expect(screen.queryByTestId("leak-divergencia")).toBeNull();        // total bate: sem aviso
    fireEvent.click(within(linha).getByRole("button"));
    expect(navigate).toHaveBeenCalledWith("/replayer?t=901&h=H1");
  });

  it("quando a lista não bate com a linha, a tela declara em vez de calar", async () => {
    evLeakHands.mockResolvedValue({
      total: 12, loss_bb: 30.0, limit: 200, offset: 0,
      street: "flop", action_taken: "fold", best_action: "call", hands: [MAO(1, "KhJs", 6.4)],
    });
    monta(19);
    const aviso = await screen.findByTestId("leak-divergencia");
    expect(aviso.textContent).toContain("v2.leakHandsMismatch:12,19");
  });

  it("spot sem mão medida diz isso, e erro de rede também", async () => {
    evLeakHands.mockResolvedValue({ total: 0, loss_bb: 0, limit: 200, offset: 0,
      street: "flop", action_taken: "fold", best_action: "call", hands: [] });
    const { unmount } = monta(0);
    expect(await screen.findByText("v2.leakHandsEmpty")).toBeTruthy();
    unmount();
    evLeakHands.mockRejectedValue(new Error("500"));
    monta();
    expect(await screen.findByText("v2.leakHandsError")).toBeTruthy();
  });
});
