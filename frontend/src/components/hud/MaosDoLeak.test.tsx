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

function monta() {
  return render(
    <MemoryRouter>
      <MaosDoLeak street="flop" actionTaken="fold" bestAction="call" lastN={50} />
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
    // As cartas sao DESENHADAS desde 16/09 (o baralho da mesa), entao a asserção olha as imagens
    // e não o texto. E olha a ORDEM: `KhJs` sai com o rei primeiro.
    expect(within(linha).getAllByRole("img").map((i) => i.getAttribute("alt"))).toEqual(["Kh", "Js"]);
    expect(linha.textContent).toContain("−6.40bb");
    fireEvent.click(within(linha).getByRole("button"));
    // O link leva o LEAK, e nao so a mao: e isso que liga a playlist no replayer, com o mesmo
    // recorte (`ln`) da lista. Sem isso o replayer navegaria pelas maos do torneio de origem.
    expect(navigate).toHaveBeenCalledWith(
      "/replayer?t=901&h=H1&leak=flop%3Afold%3Acall&ln=50");
  });

  it("a carta alta vem primeiro, mesmo quando a sala escreveu ao contrário", async () => {
    // O caso que o dono viu na tela: `4dAd`, com o quatro na frente do ás, porque o parser
    // guarda a ordem do ASSENTO. Quem ordena é `HeroHand`, num lugar só.
    evLeakHands.mockResolvedValue({
      total: 1, loss_bb: 2.3, limit: 200, offset: 0,
      street: "flop", action_taken: "fold", best_action: "call", hands: [MAO(7, "4dAd", 2.28)],
    });
    monta();
    const linha = await screen.findByTestId("leak-mao-7");
    expect(within(linha).getAllByRole("img").map((i) => i.getAttribute("alt"))).toEqual(["Ad", "4d"]);
  });

  it("a tela NUNCA expõe divergência entre a lista e a linha", async () => {
    // Era o oposto: este caso exigia que a tela DECLARASSE "a lista tem 12 e a linha diz 19".
    // Eu escrevi aquele aviso em 09/09 como honestidade e estava errado — divergência entre dois
    // números nossos é defeito nosso, e jogá-la na tela transfere ao jogador um problema que ele
    // não pode resolver. O dono viu em produção e classificou como bug.
    //
    // A régua agora é uma (`decisao_entra_no_leak`, no backend) e quem acusa a divergência é
    // `test_maos_do_leak`, que semeia multiway e zona de ICM e exige a reconciliação. Aqui só
    // garantimos que a vitrine não voltou a ter o aviso.
    evLeakHands.mockResolvedValue({
      total: 12, loss_bb: 30.0, limit: 200, offset: 0,
      street: "flop", action_taken: "fold", best_action: "call", hands: [MAO(1, "KhJs", 6.4)],
    });
    monta();
    const painel = await screen.findByTestId("leak-maos");
    expect(screen.queryByTestId("leak-divergencia")).toBeNull();
    expect(painel.textContent).not.toContain("leakHandsMismatch");
  });

  it("spot sem mão medida diz isso, e erro de rede também", async () => {
    evLeakHands.mockResolvedValue({ total: 0, loss_bb: 0, limit: 200, offset: 0,
      street: "flop", action_taken: "fold", best_action: "call", hands: [] });
    const { unmount } = monta();
    expect(await screen.findByText("v2.leakHandsEmpty")).toBeTruthy();
    unmount();
    evLeakHands.mockRejectedValue(new Error("500"));
    monta();
    expect(await screen.findByText("v2.leakHandsError")).toBeTruthy();
  });
});
